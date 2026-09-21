"""The outbound status lifecycle must only ever move forward.

Provenance
----------
A context trace on 2026-09-21 found two defects with no test coverage anywhere:

1. `_process_status` applied every status webhook with an unconditional
   `SET #status = :status`. Meta guarantees neither ordering nor exactly-once
   delivery, so the last webhook to arrive won whatever it said: a late `sent`
   overwrote `read`, and a re-delivered `failed` overwrote `delivered`.

2. The outbound sender persisted `status='sent'` at four call sites the moment
   Meta's send response returned 200. Meta's response carries a message id and, at
   most, `message_status: "accepted"` - never `sent`. So the row claimed a
   delivery signal the platform had not given, and it also hid defect 1, because
   the row was never in a state a real `sent` webhook would advance.

3. `_is_within_service_window` was only consulted when a contact row with an `id`
   existed; a send to a bare phone number skipped the 24-hour check entirely.

These tests pin all three. They run offline - no AWS, no provider calls.
"""

import sys
import time
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
FUNCTIONS = ROOT / "amplify" / "functions"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import wa_status  # noqa: E402

OUTBOUND = FUNCTIONS / "messaging" / "outbound-whatsapp" / "handler.py"
INBOUND = FUNCTIONS / "messaging" / "inbound-whatsapp-handler" / "handler.py"


class TestRanking:
    def test_the_documented_progression(self):
        assert (wa_status.rank("accepted") < wa_status.rank("sent")
                < wa_status.rank("failed") < wa_status.rank("delivered")
                < wa_status.rank("read"))

    def test_unknown_status_ranks_zero_and_never_wins(self):
        assert wa_status.rank("teleported") == 0
        assert wa_status.rank(None) == 0
        assert wa_status.rank("") == 0
        for known in ("accepted", "sent", "delivered", "read", "failed"):
            assert not wa_status.should_apply(known, "teleported"), known

    def test_case_and_whitespace_tolerated(self):
        assert wa_status.rank("  READ ") == wa_status.rank("read")


class TestForwardOnly:
    @pytest.mark.parametrize("current,incoming", [
        (None, "accepted"), (None, "sent"), ("accepted", "sent"),
        ("sent", "delivered"), ("delivered", "read"), ("sent", "failed"),
        ("accepted", "read"),
    ])
    def test_forward_transitions_apply(self, current, incoming):
        assert wa_status.should_apply(current, incoming)

    @pytest.mark.parametrize("current,incoming", [
        ("read", "sent"),        # the late-sent bug
        ("read", "delivered"),
        ("delivered", "sent"),
        ("delivered", "failed"),  # the re-delivered-failed bug
        ("read", "failed"),
        ("sent", "accepted"),
    ])
    def test_backward_transitions_are_refused(self, current, incoming):
        assert not wa_status.should_apply(current, incoming)

    @pytest.mark.parametrize("status", ["accepted", "sent", "delivered", "read", "failed"])
    def test_duplicate_delivery_is_refused(self, status):
        """Same rank is not forward, so a redelivered webhook is a no-op."""
        assert not wa_status.should_apply(status, status)

    def test_delivered_after_failed_is_allowed_and_documented(self):
        """A judgement, not a law - so it is asserted and explained, not implicit."""
        assert wa_status.should_apply("failed", "delivered")
        assert "positive evidence of" in wa_status.__doc__


class TestConditionExpression:
    def test_guards_on_the_rank_attribute(self):
        expr = wa_status.condition_expression()
        assert wa_status.RANK_ATTRIBUTE in expr
        assert "attribute_not_exists" in expr
        assert "<" in expr

    def test_pre_existing_rows_without_a_rank_are_let_through_once(self):
        """Rows written before this attribute existed must not be frozen."""
        assert f"attribute_not_exists({wa_status.RANK_ATTRIBUTE})" in \
            wa_status.condition_expression()

    def test_describe_never_leaks_content(self):
        assert "rank" in wa_status.describe("read")
        assert "rank 0" in wa_status.describe("nonsense")


class TestInboundAppliesTheGuard:
    """Structural: the handler is ~7k lines and its import pulls in AWS clients."""

    SRC = INBOUND.read_text()

    def test_status_update_is_conditional(self):
        assert "wa_status.condition_expression()" in self.SRC

    def test_rank_is_persisted_with_the_status(self):
        assert "wa_status.RANK_ATTRIBUTE" in self.SRC
        assert "wa_status.rank(status_value)" in self.SRC

    def test_a_refused_transition_is_logged_not_raised(self):
        assert "status_out_of_order_skipped" in self.SRC
        assert "ConditionalCheckFailedException" in self.SRC

    def test_a_real_error_still_raises(self):
        """Only the conditional failure is swallowed; anything else propagates.

        Anchored on the status handler's own except clause: the file contains
        other, unrelated ConditionalCheckFailedException handling.
        """
        idx = self.SRC.index("except ClientError as _ce:")
        window = self.SRC[idx:idx + 220]
        assert "ConditionalCheckFailedException" in window
        assert "raise" in window

    def test_the_canonical_mirror_cannot_regress_either(self):
        idx = self.SRC.index("canonical status mirror skipped")
        window = self.SRC[idx - 900:idx]
        assert "attribute_exists(id) AND" in window
        assert "condition_expression()" in window


class TestOutboundInitialStatus:
    SRC = OUTBOUND.read_text()

    def test_no_persisted_row_claims_sent_from_the_send_response(self):
        assert "status='sent'," not in self.SRC

    def test_initial_status_is_accepted(self):
        assert "WA_INITIAL_STATUS = 'accepted'" in self.SRC
        assert "status=WA_INITIAL_STATUS," in self.SRC

    def test_the_api_response_contract_is_deliberately_unchanged(self):
        """Three frontend call sites treat response status 'sent' as success."""
        assert "'status': 'sent'" in self.SRC
        idx = self.SRC.index("WA_INITIAL_STATUS = 'accepted'")
        rationale = self.SRC[idx - 700:idx]
        assert "success boolean" in rationale

    def test_accepted_ranks_below_every_webhook_status(self):
        """The whole point: a real `sent` webhook must be able to advance it."""
        assert wa_status.should_apply("accepted", "sent")
        assert wa_status.should_apply("accepted", "delivered")
        assert wa_status.should_apply("accepted", "failed")


class TestServiceWindow:
    """`_is_within_service_window` is pure, so exercise it directly."""

    @pytest.fixture(scope="class")
    def window(self):
        src = OUTBOUND.read_text()
        start = src.index("def _is_within_service_window")
        end = src.index("\ndef ", start + 10)
        ns = {"Decimal": Decimal, "time": time,
              "CUSTOMER_SERVICE_WINDOW_HOURS": 24,
              "Dict": dict, "Any": object}
        exec(compile(src[start:end], "<window>", "exec"), ns)  # noqa: S102
        return ns["_is_within_service_window"]

    def test_open_window(self, window):
        assert window({"lastInboundMessageAt": Decimal(str(int(time.time()) - 3600))})

    def test_closed_window(self, window):
        assert not window({"lastInboundMessageAt": Decimal(str(int(time.time()) - 90000))})

    def test_exactly_at_the_boundary_is_closed(self, window):
        assert not window({"lastInboundMessageAt": Decimal(str(int(time.time()) - 86400))})

    def test_missing_timestamp_fails_closed(self, window):
        assert not window({})
        assert not window({"lastInboundMessageAt": None})

    def test_iso_string_accepted(self, window):
        from datetime import datetime, timezone
        recent = datetime.fromtimestamp(time.time() - 60, tz=timezone.utc)
        assert window({"lastInboundMessageAt": recent.isoformat().replace("+00:00", "Z")})


class TestServiceWindowIsNotSkippable:
    SRC = OUTBOUND.read_text()

    def test_no_contact_record_means_no_open_window(self):
        """The old form defaulted True and only checked when contact['id'] existed."""
        assert "_is_within_service_window(contact) if contact else False" in self.SRC
        assert "within_window = True\n" not in self.SRC

    def test_the_block_is_observable(self):
        assert "send_blocked_outside_window" in self.SRC
        assert "hasContactRecord" in self.SRC


class TestErrorClassification:
    SRC = OUTBOUND.read_text()

    def test_graph_errors_is_actually_imported(self):
        """It existed and was tested, but no handler imported it."""
        assert "from lambda_utils import graph_errors" in self.SRC
        assert "graph_errors.normalize(" in self.SRC

    def test_subcode_is_captured_in_the_log_and_on_the_row(self):
        assert "'metaSubcode'" in self.SRC
        assert "'subcode': error_subcode" in self.SRC

    def test_permanent_vs_transient_is_recorded(self):
        assert "'classification': 'transient' if is_transient else 'permanent'" in self.SRC

    def test_the_per_code_retry_flag_is_consulted(self):
        """META_MESSAGE_ERRORS carried a `retry` boolean nothing ever read."""
        assert "table_entry.get('retry')" in self.SRC

    def test_classification_failure_cannot_break_the_error_path(self):
        idx = self.SRC.index("graph_errors.normalize(")
        window = self.SRC[idx - 200:idx + 300]
        assert "except Exception" in window

    def test_customer_phone_is_masked_in_every_log(self):
        """Six sites logged a customer number in cleartext, across dry-run,
        payload-built, reaction-error and send-error paths."""
        assert "'recipientPhone': mask_phone(recipient_phone)" in self.SRC
        assert "'recipientPhone': recipient_phone," not in self.SRC
        assert "'formattedPhone': _normalize_phone_number(recipient_phone)," not in self.SRC
        assert "'normalizedPhone': message_payload.get('to')," not in self.SRC


class TestGraphErrorsContract:
    """Pin the helper's shape, since the sender now depends on these keys.

    `normalize()` returns a NESTED envelope, `{'error': {...}}`. Reading the top
    level yields None for every field and fails silently, which is exactly the
    mistake this class exists to prevent recurring.
    """

    def test_the_envelope_is_nested(self):
        from lambda_utils import graph_errors
        out = graph_errors.normalize('{"error":{"code":1}}', 400)
        assert set(out) == {"error"}, "top level must be the single 'error' key"

    def test_normalize_exposes_what_the_sender_reads(self):
        from lambda_utils import graph_errors
        out = graph_errors.normalize(
            '{"error":{"code":131047,"error_subcode":2494055,'
            '"message":"Re-engagement","fbtrace_id":"Abc123"}}', 400)["error"]
        assert out["code"] == 131047
        assert out["error_subcode"] == 2494055
        assert out["fbtrace_id"] == "Abc123"
        assert out["is_transient"] is False
        assert out["retryable"] is False

    def test_a_5xx_is_transient(self):
        from lambda_utils import graph_errors
        out = graph_errors.normalize('{"error":{"code":131000}}', 503)["error"]
        assert out["is_transient"] is True
        assert out["retryable"] is True

    def test_unparsable_body_does_not_raise(self):
        from lambda_utils import graph_errors
        out = graph_errors.normalize("not json at all", 400)["error"]
        assert out["message"] == "not json at all"

    def test_the_handler_reads_the_nested_level(self):
        src = OUTBOUND.read_text()
        assert "graph_errors.normalize(error_body, http_code).get('error', {})" in src
