"""RCS delivery-status ordering and failure classification.

Measured on 30 days of production DLR traffic to 2026-09-22, which is what makes both
defects concrete rather than theoretical:

    QUEUED_ON_CHANNEL   728
    FAILED              559      every one the same terminal reason
    DELIVERED           166
    READ                 62

With 728 `QUEUED_ON_CHANNEL` against 166 `DELIVERED` and an unconditional
`SET #s = :status`, a queued report arriving after a delivered one rewrote the row back
to `sent`. So 166 was a floor, not a measurement.

And all 559 failures reported "Number is RCS disabled or Bot is not launched with the
number's provider" - terminal for that recipient - while one recipient was sent 90
messages and failed all 90, because nothing classified the failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import rcs_status  # noqa: E402

REAL_REASON = ("The underlying channel reported: Number is RCS disabled or Bot is not "
               "launched with the number's provider.")


class TestCanonicalMapping:
    @pytest.mark.parametrize("sinch,expected", [
        ("QUEUED", "sent"),
        ("QUEUED_ON_CHANNEL", "queued_on_channel"),
        ("DELIVERED", "delivered"),
        ("READ", "read"),
        ("FAILED", "failed"),
        ("DELETED", "deleted"),
    ])
    def test_every_observed_sinch_status_maps(self, sinch, expected):
        assert rcs_status.canonical(sinch) == expected

    def test_case_and_whitespace_tolerated(self):
        assert rcs_status.canonical("  delivered ") == "delivered"

    @pytest.mark.parametrize("unknown", ["", None, "TELEPORTED", "PENDING_MAYBE"])
    def test_an_unknown_status_maps_to_empty_not_a_guess(self, unknown):
        """Empty keeps it at rank 0, so a status Sinch adds later cannot silently
        outrank `read` before anybody has decided what it means."""
        assert rcs_status.canonical(unknown) == ""
        assert rcs_status.rank(rcs_status.canonical(unknown)) == 0


class TestTheLadder:
    def test_queued_on_channel_outranks_sent_but_not_a_handset_signal(self):
        assert rcs_status.rank("sent") < rcs_status.rank("queued_on_channel")
        assert rcs_status.rank("queued_on_channel") < rcs_status.rank("delivered")

    def test_failed_sits_below_delivered_and_read(self):
        """Positive evidence of arrival outranks an earlier failure report."""
        assert rcs_status.rank("failed") < rcs_status.rank("delivered")
        assert rcs_status.rank("failed") < rcs_status.rank("read")

    def test_the_production_collision_is_now_refused(self):
        """The exact case the volumes make likely: 728 queued reports against 166
        delivered."""
        applied, reason = rcs_status.should_apply("delivered", "queued_on_channel")
        assert applied is False
        assert reason == "out_of_order"

    def test_a_redelivered_failure_cannot_undo_a_delivery(self):
        applied, reason = rcs_status.should_apply("delivered", "failed")
        assert applied is False
        assert reason == "out_of_order"

    def test_failure_after_queued_applies_which_is_the_common_case(self):
        applied, reason = rcs_status.should_apply("queued_on_channel", "failed")
        assert applied is True
        assert reason == "forward"

    def test_the_normal_progression_is_allowed_end_to_end(self):
        chain = ["sent", "queued_on_channel", "delivered", "read"]
        for current, incoming in zip(chain, chain[1:]):
            applied, _ = rcs_status.should_apply(current, incoming)
            assert applied is True, f"{current} -> {incoming}"

    def test_first_report_always_applies(self):
        for status in rcs_status.STATUS_RANK:
            applied, reason = rcs_status.should_apply(None, status)
            assert applied is True and reason == "initial"

    def test_duplicate_is_distinguished_from_out_of_order(self):
        _, reason = rcs_status.should_apply("delivered", "delivered")
        assert reason == "duplicate_status"

    def test_read_is_terminal(self):
        assert rcs_status.is_terminal("read") is True
        for later in ("delivered", "failed", "queued_on_channel", "sent"):
            applied, reason = rcs_status.should_apply("read", later)
            assert applied is False
            assert reason == "terminal_read"

    def test_an_unknown_incoming_status_never_wins(self):
        for known in rcs_status.STATUS_RANK:
            applied, reason = rcs_status.should_apply(known, "teleported")
            assert applied is False
            assert reason == "unknown_status"


class TestAtomicGuard:
    def test_the_condition_requires_the_row_and_a_forward_rank(self):
        expr = rcs_status.condition_expression()
        assert "attribute_exists(id)" in expr
        assert rcs_status.RANK_ATTRIBUTE in expr
        assert "attribute_not_exists" in expr, (
            "the 730 rows already in the table have no rank attribute and must still "
            "accept their next report")


class TestFailureClassification:
    def test_the_real_production_reason_is_permanent(self):
        """559 of 559 failures in the measured window carried exactly this."""
        disposition, category = rcs_status.classify_failure(REAL_REASON)
        assert disposition == rcs_status.PERMANENT
        assert category

    def test_the_real_production_reason_is_flagged_unreachable(self):
        assert rcs_status.is_rcs_unreachable(REAL_REASON) is True

    @pytest.mark.parametrize("reason", [
        "Number is RCS disabled",
        "Bot is not launched with the number's provider",
        "handset is not RCS capable",
        "invalid recipient",
    ])
    def test_the_terminal_family_is_recognised(self, reason):
        assert rcs_status.classify_failure(reason)[0] == rcs_status.PERMANENT

    @pytest.mark.parametrize("reason", [
        "Request timed out", "throttled by the channel", "temporarily unavailable",
        "internal error, try again", "rate limit exceeded",
    ])
    def test_transient_faults_stay_retryable(self, reason):
        assert rcs_status.classify_failure(reason)[0] == rcs_status.TRANSIENT
        assert rcs_status.is_rcs_unreachable(reason) is False

    def test_a_transient_marker_wins_over_a_permanent_one(self):
        """A throttle or an outage can mention capability in passing, and misreading that
        as permanent would write off a reachable customer."""
        mixed = "temporarily unavailable: number is RCS disabled check pending"
        assert rcs_status.classify_failure(mixed)[0] == rcs_status.TRANSIENT

    @pytest.mark.parametrize("reason", ["", None, "   ", "something entirely new"])
    def test_an_unrecognised_reason_defaults_to_transient(self, reason):
        """A wasted retry is cheaper than silently writing off a reachable customer, so
        the default must not be PERMANENT."""
        assert rcs_status.classify_failure(reason)[0] == rcs_status.TRANSIENT
        assert rcs_status.is_rcs_unreachable(reason) is False

    def test_classification_is_case_and_whitespace_insensitive(self):
        noisy = "  NUMBER  IS   RCS\nDISABLED  "
        assert rcs_status.classify_failure(noisy)[0] == rcs_status.PERMANENT


class TestDescribeLeaksNothing:
    def test_describe_carries_no_recipient_or_content(self):
        text = rcs_status.describe("delivered")
        assert "delivered" in text and "50" in text
        assert rcs_status.is_terminal("read") is True
        assert "terminal" in rcs_status.describe("read")

    def test_unknown_status_is_described_as_rank_zero(self):
        assert "rank 0" in rcs_status.describe("nonsense")
