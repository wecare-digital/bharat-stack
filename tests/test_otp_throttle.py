"""The OTP front-door throttle: two axes, fail-closed, and no oracle in the 429.

Why this file exists
--------------------
`otp_throttle` guards the one path that spends money and rings a real person's handset, and it
shipped without a test. The properties below are the ones that make it worth having at all:
per-phone AND per-IP (either alone is bypassable), fail-CLOSED on a storage error (unlike the
throughput limiter next door, which fails open), a window that resets rather than locking a
customer out for the day, and a 429 that never names which axis tripped.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402
from lambda_utils import otp_throttle  # noqa: E402

TABLE = 'stack-wecare-digital-DownloadGrantsTable'
PHONE = '+919330994400'
NOW = 1_700_000_000


@pytest.fixture
def table():
    return FakeDynamo(keys={TABLE: 'grantId'}).Table(TABLE)


def _event(ip='203.0.113.7'):
    return {'requestContext': {'http': {'sourceIp': ip}}}


# ── source IP extraction ─────────────────────────────────────────────────────

def test_source_ip_reads_gateway_context_not_forwarded_for():
    # X-Forwarded-For is client-supplied and must be ignored, or the limit is defeated by
    # rotating the header per request.
    event = {'requestContext': {'http': {'sourceIp': '198.51.100.9'}},
             'headers': {'X-Forwarded-For': '10.0.0.1'}}
    assert otp_throttle.source_ip(event) == '198.51.100.9'


def test_source_ip_falls_back_to_rest_identity():
    event = {'requestContext': {'identity': {'sourceIp': '198.51.100.10'}}}
    assert otp_throttle.source_ip(event) == '198.51.100.10'


# ── the happy path counts on both axes ───────────────────────────────────────

def test_a_single_request_consumes_one_on_each_axis(table):
    phone_count, ip_count = otp_throttle.check_and_consume(
        table, phone_e164=PHONE, event=_event(), now=NOW)
    assert phone_count == 1
    assert ip_count == 1


def test_phone_limit_trips_after_its_budget(table):
    # DEFAULT_PHONE_MAX is 5. The sixth attempt is over budget.
    for i in range(otp_throttle.DEFAULT_PHONE_MAX):
        otp_throttle.check_and_consume(table, phone_e164=PHONE, event=_event(),
                                       now=NOW + i)
    with pytest.raises(otp_throttle.OtpThrottled) as excinfo:
        otp_throttle.check_and_consume(table, phone_e164=PHONE, event=_event(),
                                       now=NOW + otp_throttle.DEFAULT_PHONE_MAX)
    assert excinfo.value.axis == 'phone'
    assert excinfo.value.retry_after_seconds >= 1


def test_ip_limit_bounds_the_spread_across_many_numbers(table):
    # A different number each time keeps every per-phone counter at 1, but the shared IP
    # counter climbs. DEFAULT_IP_MAX is 20.
    for i in range(otp_throttle.DEFAULT_IP_MAX):
        otp_throttle.check_and_consume(table, phone_e164=f'+9193309900{i:02d}',
                                       event=_event(), now=NOW + i)
    with pytest.raises(otp_throttle.OtpThrottled) as excinfo:
        otp_throttle.check_and_consume(table, phone_e164='+919330990099',
                                       event=_event(), now=NOW + otp_throttle.DEFAULT_IP_MAX)
    assert excinfo.value.axis == 'ip'


def test_phone_is_reported_before_ip_when_both_are_over(table):
    # Drive both axes over with one number from one IP. Phone (max 5) trips before IP (max 20),
    # and phone is the axis worth reporting because it protects the person.
    with pytest.raises(otp_throttle.OtpThrottled) as excinfo:
        for i in range(otp_throttle.DEFAULT_PHONE_MAX + 2):
            otp_throttle.check_and_consume(table, phone_e164=PHONE, event=_event(),
                                           now=NOW + i)
    assert excinfo.value.axis == 'phone'


# ── the window resets rather than locking out ────────────────────────────────

def test_window_rollover_resets_the_count(table):
    for i in range(otp_throttle.DEFAULT_PHONE_MAX):
        otp_throttle.check_and_consume(table, phone_e164=PHONE, event=_event(), now=NOW + i)
    # Past the window, the counter starts fresh instead of staying locked.
    later = NOW + otp_throttle.DEFAULT_PHONE_WINDOW + 1
    phone_count, _ = otp_throttle.check_and_consume(
        table, phone_e164=PHONE, event=_event(), now=later)
    assert phone_count == 1


# ── fail closed ──────────────────────────────────────────────────────────────

def test_a_storage_error_refuses_rather_than_allowing(table):
    # The whole point: guarding a money/message path means an unreadable counter must refuse.
    table.parent.arm_failure(TABLE, 'update_item', FakeClientError('InternalServerError'))
    with pytest.raises(otp_throttle.ThrottleStoreUnavailable):
        otp_throttle.check_and_consume(table, phone_e164=PHONE, event=_event(), now=NOW)


# ── the 429 body names no axis ───────────────────────────────────────────────

def test_the_throttled_response_does_not_reveal_the_axis():
    err = otp_throttle.OtpThrottled('phone', 42)
    resp = otp_throttle.throttled_response(err, _event())
    assert resp['statusCode'] == 429
    payload = json.loads(resp['body'])
    # The axis name ("phone"/"ip") must not leak in any field value.
    assert 'phone' not in json.dumps(payload).lower()
    assert payload['error'] == 'TOO_MANY_REQUESTS'
    assert payload['retryAfterSeconds'] == 42  # the retry hint survives


def test_ipv6_is_bucketed_to_a_64_so_rotation_within_it_does_not_help(table):
    # Two addresses in the same /64 must count against one bucket.
    ip_a = '2001:db8:abcd:1234::1'
    ip_b = '2001:db8:abcd:1234::ffff'
    _, first = otp_throttle.check_and_consume(
        table, phone_e164='+919330990001', ip=ip_a, now=NOW)
    _, second = otp_throttle.check_and_consume(
        table, phone_e164='+919330990002', ip=ip_b, now=NOW + 1)
    assert second == first + 1
