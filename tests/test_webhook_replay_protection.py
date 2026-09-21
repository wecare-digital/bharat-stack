"""Replay protection must not be defeatable by the replayer.

`whatsapp-calling/_validate_webhook_timestamp` wrapped its whole traversal in one
try/except that caught `(ValueError, TypeError)` and returned True, commented
"fail open on parse errors — don't block legitimate events". Two consequences, one
of them a hole:

1. `int('not-a-number')` raised, was swallowed, and the event was accepted. So
   anyone replaying a captured signature-valid payload only had to corrupt the
   timestamp to bypass the 5-minute window completely.
2. Because the try wrapped the traversal rather than a single parse, one malformed
   value aborted the loop. A payload carrying a malformed timestamp in entry 1 and
   a genuinely stale one in entry 2 was accepted without the stale one ever being
   looked at.

The corrected rule distinguishes absent from unreadable. Absent stays allowed -
Meta really does omit `time` on some event shapes and rejecting those would drop
live traffic. Unreadable is rejected, because a value we cannot parse is not
evidence of freshness.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARED = ROOT / 'amplify' / 'functions' / 'shared'
CALLING = ROOT / 'amplify' / 'functions' / 'messaging' / 'whatsapp-calling' / 'handler.py'
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))


def _load():
    """Unique module name — `handler` is contested by every function in the suite."""
    spec = importlib.util.spec_from_file_location('whatsapp_calling_replay_handler', CALLING)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wc = _load()
WINDOW = wc.WEBHOOK_MAX_AGE_SECONDS


def _entry(ts):
    return {'entry': [{'time': ts}]}


def _call(ts):
    return {'entry': [{'changes': [{'value': {'calls': [{'timestamp': ts}]}}]}]}


UNPARSABLE = ['not-a-number', 'NaN', '12x34', '0x1f', 'null', '1,700,000,000',
              '2026-09-21T00:00:00Z', {}, [], True]


class TestTheHoleThatWasOpen:
    """The regression proper: a corrupted timestamp must not buy a free pass."""

    @pytest.mark.parametrize('bad', UNPARSABLE)
    def test_verdict_is_unparsable_not_ok(self, bad):
        # `True` is the odd one: bool is an int subclass, so int(True) == 1, which
        # is 1970 and therefore stale. Either way it is not 'ok'.
        assert wc._timestamp_verdict(bad, int(time.time())) in ('unparsable', 'stale')

    @pytest.mark.parametrize('bad', UNPARSABLE)
    def test_present_but_unparsable_entry_time_rejects(self, bad):
        assert wc._validate_webhook_timestamp(_entry(bad), 'req') is False

    @pytest.mark.parametrize('bad', UNPARSABLE)
    def test_present_but_unparsable_call_timestamp_rejects(self, bad):
        assert wc._validate_webhook_timestamp(_call(bad), 'req') is False

    def test_a_malformed_timestamp_no_longer_hides_a_stale_one(self):
        """Consequence 2. The old single enclosing try aborted the traversal on
        the malformed value in entry 1, so the stale value in entry 2 was never
        examined and the whole payload was accepted."""
        stale = int(time.time()) - (WINDOW + 300)
        body = {'entry': [{'time': 'not-a-number'}, {'time': str(stale)}]}
        assert wc._validate_webhook_timestamp(body, 'req') is False

    def test_stale_is_found_even_when_a_later_entry_is_malformed(self):
        stale = int(time.time()) - (WINDOW + 300)
        body = {'entry': [{'time': str(stale)}, {'time': 'not-a-number'}]}
        assert wc._validate_webhook_timestamp(body, 'req') is False


class TestAbsentIsStillAllowed:
    """Absence is not a failure. Rejecting it would drop real Meta traffic."""

    def test_no_timestamp_anywhere(self):
        assert wc._validate_webhook_timestamp({'entry': [{'changes': [{'value': {}}]}]}, 'req') is True

    def test_entry_without_time_key(self):
        assert wc._validate_webhook_timestamp({'entry': [{}]}, 'req') is True

    def test_empty_body(self):
        assert wc._validate_webhook_timestamp({}, 'req') is True

    def test_no_entries(self):
        assert wc._validate_webhook_timestamp({'entry': []}, 'req') is True

    def test_none_timestamp_is_absent_not_unparsable(self):
        assert wc._timestamp_verdict(None, int(time.time())) == 'absent'
        assert wc._validate_webhook_timestamp(_entry(None), 'req') is True


class TestFreshAndStale:
    def test_recent_passes(self):
        assert wc._validate_webhook_timestamp(_entry(str(int(time.time()) - 10)), 'req') is True

    def test_int_as_well_as_str(self):
        assert wc._validate_webhook_timestamp(_entry(int(time.time()) - 10), 'req') is True

    def test_stale_entry_time_rejected(self):
        assert wc._validate_webhook_timestamp(_entry(str(int(time.time()) - 600)), 'req') is False

    def test_stale_call_timestamp_rejected(self):
        assert wc._validate_webhook_timestamp(_call(str(int(time.time()) - 400)), 'req') is False

    def test_exactly_at_the_boundary_passes(self):
        now = int(time.time())
        assert wc._timestamp_verdict(now - WINDOW, now) == 'ok'
        assert wc._timestamp_verdict(now - WINDOW - 1, now) == 'stale'

    def test_modest_clock_skew_tolerated(self):
        """Meta's clock running slightly ahead of ours must not reject traffic."""
        now = int(time.time())
        assert wc._timestamp_verdict(now + 30, now) == 'ok'
        assert wc._timestamp_verdict(now + WINDOW, now) == 'ok'

    def test_far_future_rejected(self):
        """A far-future stamp never expires, so one captured event would replay
        forever."""
        now = int(time.time())
        assert wc._timestamp_verdict(now + WINDOW + 1, now) == 'future'
        assert wc._validate_webhook_timestamp(_entry(str(now + 86400)), 'req') is False


class TestMalformedShapeIsRejectedNotIgnored:
    """An unwalkable container may be hiding a stale timestamp, so it is refused.

    The old code raised AttributeError on several of these and surfaced a 500 -
    fail-closed, but badly, since Meta retries a 500 indefinitely. The trap when
    fixing that is to make the traversal tolerant and silently *skip* the shape,
    which converts a noisy 500 into a quiet accept. A first draft of this change
    did exactly that and `test_calls_as_an_object_still_sees_the_stale_timestamp`
    below is the case that caught it.
    """

    @pytest.mark.parametrize('body', [
        {'entry': {'time': '123'}},                     # entry an object, not a list
        {'entry': ['a string']},                        # entry item not an object
        {'entry': [{'changes': {'value': {}}}]},        # changes an object
        {'entry': [{'changes': ['x']}]},                # change item not an object
        {'entry': [{'changes': [{'value': 'x'}]}]},     # value not an object
        {'entry': [{'changes': [{'value': {'calls': 'x'}}]}]},    # calls a scalar
        {'entry': [{'changes': [{'value': {'calls': ['x']}}]}]},  # call not an object
        'not a dict at all',
        None,
        42,
    ])
    def test_unwalkable_shape_rejects(self, body):
        assert wc._validate_webhook_timestamp(body, 'req') is False

    def test_calls_as_an_object_still_sees_the_stale_timestamp(self):
        """`calls` as a single object is the plausible shape change, so it is read
        as one call rather than skipped. Skipping it accepted this payload."""
        stale = int(time.time()) - 900
        body = {'entry': [{'changes': [{'value': {'calls': {'timestamp': str(stale)}}}]}]}
        assert wc._validate_webhook_timestamp(body, 'req') is False

    def test_calls_as_an_object_with_a_fresh_timestamp_passes(self):
        fresh = int(time.time()) - 5
        body = {'entry': [{'changes': [{'value': {'calls': {'timestamp': str(fresh)}}}]}]}
        assert wc._validate_webhook_timestamp(body, 'req') is True

    @pytest.mark.parametrize('body', [
        {},                                   # empty POST
        {'entry': None},                      # entry: null
        {'entry': [{'changes': None}]},       # no changes
        {'entry': [{'changes': [{'value': None}]}]},
    ])
    def test_absent_containers_stay_allowed(self, body):
        """Absence is not malformation. Meta omits these on real event types and
        rejecting them would drop live traffic."""
        assert wc._validate_webhook_timestamp(body, 'req') is True

    def test_nothing_raises_for_any_of_the_above(self):
        for body in ({'entry': {'x': 1}}, None, 'x', 42, {'entry': [[]]},
                     {'entry': [{'changes': [{'value': {'calls': [[]]}}]}]}):
            wc._validate_webhook_timestamp(body, 'req')  # must not raise


class TestLoggingIsBounded:
    def test_attacker_controlled_value_is_capped_in_the_log(self, caplog):
        with caplog.at_level('WARNING'):
            assert wc._validate_webhook_timestamp(_entry('A' * 5000), 'req') is False
        assert 'webhook_timestamp_rejected' in caplog.text
        assert 'A' * 5000 not in caplog.text
