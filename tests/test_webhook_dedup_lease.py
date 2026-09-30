"""A crashed handler must release its dedup claim, or the provider's retry is thrown away.

The defect this covers, stated as the sequence:

    claim -> handler raises -> claim remains -> provider retries -> "duplicate" -> DROPPED

`claim_event` takes the claim *before* the work and never releases it, so an exception anywhere in
the handler makes the retry look like a duplicate. On `payment.captured` that silently discards a
captured payment — and discards the exact mechanism that exists to recover from it.

The fix is opt-in, and these tests pin both halves: leased callers recover, and every existing
caller of plain `claim_event` keeps the permanent claim it depends on.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402
from lambda_utils import webhook_dedup as wd  # noqa: E402

TABLE = 'stack-wecare-digital-WebhookDedup'
EVENT = 'acc_X:payment.captured:1790100905'


@pytest.fixture
def table(monkeypatch):
    fake = FakeDynamo(keys={TABLE: 'eventId'})
    monkeypatch.setattr(wd, '_table', lambda: fake.Table(TABLE))
    return fake.Table(TABLE)


def _at(seconds):
    """Pin wall clock, since the lease is a time comparison."""
    return seconds


@pytest.fixture
def clock(monkeypatch):
    state = {'now': 1_700_000_000}
    monkeypatch.setattr(time, 'time', lambda: state['now'])
    return state


# ══════════════════════════════════════════════════════════════════════════════
# the lease
# ══════════════════════════════════════════════════════════════════════════════

def test_a_first_delivery_is_claimed(table, clock):
    assert wd.claim_event_with_lease(EVENT) is True


def test_a_redelivery_inside_the_lease_is_a_duplicate(table, clock):
    assert wd.claim_event_with_lease(EVENT, lease_seconds=900) is True
    clock['now'] += 60
    assert wd.claim_event_with_lease(EVENT, lease_seconds=900) is False


def test_a_crashed_handler_releases_its_claim_when_the_lease_lapses(table, clock):
    """The whole point. The handler never called complete_event, so the retry gets through."""
    assert wd.claim_event_with_lease(EVENT, lease_seconds=900) is True
    # ...handler raises. No complete_event.
    clock['now'] += 901
    assert wd.claim_event_with_lease(EVENT, lease_seconds=900) is True, \
        "a lapsed, uncompleted lease must be reclaimable or the retry is dropped"


def test_a_completed_event_is_never_reclaimable(table, clock):
    assert wd.claim_event_with_lease(EVENT, lease_seconds=900) is True
    wd.complete_event(EVENT)

    clock['now'] += 10_000
    assert wd.claim_event_with_lease(EVENT, lease_seconds=900) is False, \
        "a successful handler must close the claim permanently"


def test_completion_survives_far_beyond_the_lease(table, clock):
    wd.claim_event_with_lease(EVENT, lease_seconds=60)
    wd.complete_event(EVENT)
    clock['now'] += 90 * 24 * 3600
    assert wd.claim_event_with_lease(EVENT) is False


def test_two_workers_cannot_both_salvage_one_abandoned_lease(table, clock):
    """Compare-and-swap on the observed lease value, so the second salvage loses."""
    wd.claim_event_with_lease(EVENT, lease_seconds=60)
    clock['now'] += 61

    assert wd.claim_event_with_lease(EVENT, lease_seconds=60) is True
    # A second worker, still seeing the old lease it read a moment ago, must lose.
    assert wd.claim_event_with_lease(EVENT, lease_seconds=60) is False


def test_the_lease_is_recorded_on_the_row(table, clock):
    wd.claim_event_with_lease(EVENT, lease_seconds=300)
    row = table.get_item(Key={'eventId': EVENT})['Item']
    assert row['leaseExpiresAt'] == clock['now'] + 300
    assert 'completedAt' not in row
    assert row['ttl'] == row['expiresAt']


def test_completion_stamps_the_row(table, clock):
    wd.claim_event_with_lease(EVENT)
    wd.complete_event(EVENT)
    assert table.get_item(Key={'eventId': EVENT})['Item']['completedAt'] == clock['now']


# ══════════════════════════════════════════════════════════════════════════════
# legacy rows and the permanent claim must be untouched
# ══════════════════════════════════════════════════════════════════════════════

def test_a_legacy_row_without_a_lease_is_never_reclaimable(table, clock):
    """The 271 rows already in the live table carry eventId, expiresAt, processedAt, source and
    ttl — no lease. Reprocessing them would be a regression, not a fix."""
    table.put_item(Item={'eventId': EVENT, 'source': 'razorpay',
                         'processedAt': clock['now'] - 100,
                         'expiresAt': clock['now'] + 600_000,
                         'ttl': clock['now'] + 600_000})
    clock['now'] += 10_000
    assert wd.claim_event_with_lease(EVENT) is False


def test_a_row_written_by_plain_claim_event_is_not_reclaimable(table, clock):
    """Mixing the two styles on one event must not weaken the permanent one."""
    assert wd.claim_event(EVENT, source='whatsapp') is True
    clock['now'] += 10_000
    assert wd.claim_event_with_lease(EVENT) is False


def test_plain_claim_event_still_claims_permanently(table, clock):
    """Every existing caller depends on this: a Meta redelivery hours later must not re-insert
    the message."""
    assert wd.claim_event('wamid.abc', source='whatsapp_inbound') is True
    clock['now'] += 10_000
    assert wd.claim_event('wamid.abc', source='whatsapp_inbound') is False


def test_plain_claim_event_writes_no_lease(table, clock):
    wd.claim_event('wamid.abc', source='whatsapp_inbound')
    row = table.get_item(Key={'eventId': 'wamid.abc'})['Item']
    assert 'leaseExpiresAt' not in row


def test_is_duplicate_is_unchanged(table, clock):
    assert wd.is_duplicate('wamid.xyz') is False
    assert wd.is_duplicate('wamid.xyz') is True


# ══════════════════════════════════════════════════════════════════════════════
# failure posture
# ══════════════════════════════════════════════════════════════════════════════

def test_an_empty_event_id_is_processed(table, clock):
    assert wd.claim_event_with_lease('') is True
    assert wd.claim_event_with_lease(None) is True


def test_a_storage_error_fails_open(table, clock):
    """Fail open is correct here, and safer than it used to be: order creation is now guarded by
    its own conditional markers, so processing twice converges on one order."""
    table.parent.arm_failure(TABLE, 'put_item', FakeClientError('ProvisionedThroughputExceeded'))
    assert wd.claim_event_with_lease(EVENT) is True


def test_a_read_error_while_salvaging_fails_open(table, clock):
    wd.claim_event_with_lease(EVENT, lease_seconds=60)
    clock['now'] += 61
    table.parent.arm_failure(TABLE, 'get_item', FakeClientError('ThrottlingException'))
    assert wd.claim_event_with_lease(EVENT, lease_seconds=60) is True


def test_completion_never_raises(table, clock):
    wd.claim_event_with_lease(EVENT)
    table.parent.arm_failure(TABLE, 'update_item', FakeClientError('InternalServerError'))
    wd.complete_event(EVENT)  # must not raise


def test_completing_an_unknown_event_is_harmless(table, clock):
    wd.complete_event('never-claimed')
    wd.complete_event('')


def test_the_default_lease_is_long_enough_for_a_lambda_and_a_round_trip():
    """Must cover a Lambda timeout plus a provider verification call, without stalling recovery
    until the 7-day TTL."""
    assert 300 <= wd.DEFAULT_LEASE_SECONDS <= 3600
