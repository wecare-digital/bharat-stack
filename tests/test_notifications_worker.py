"""The outbox worker: at-most-once sending, and the three failure dispositions.

The branch that matters most is `RECONCILE`. A timeout after the provider took the
request is indistinguishable at the call site from a refusal before it, and only one of
those is safe to repeat. Collapsing the two into "retry" is the duplicate-send path;
collapsing them into "failed" silently drops a notification that probably arrived and
marks it terminal so nobody looks again.

No AWS and no provider calls. The DynamoDB double from tests/test_notifications_outbox
is reused, and each adapter is replaced by a recorder.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.notifications import policy as policy_mod  # noqa: E402
from lambda_utils.notifications import service as service_mod  # noqa: E402
from lambda_utils.notifications import states as states_mod  # noqa: E402
from lambda_utils.notifications import store as store_mod  # noqa: E402
from lambda_utils.notifications import suppression as suppression_mod  # noqa: E402
from lambda_utils.notifications import worker as worker_mod  # noqa: E402

from tests.test_notifications_outbox import (  # noqa: E402
    FakeClientError, FakeDynamo, CUSTOMER, BUSINESS_PSTN, PHONE1_META, A_LEG,
)


@pytest.fixture
def fake(monkeypatch):
    double = FakeDynamo()
    monkeypatch.setattr(store_mod, "_res", lambda: double)
    monkeypatch.setattr(store_mod, "_cli", lambda: double)
    monkeypatch.setattr(suppression_mod, "_table",
                        lambda: double.Table(suppression_mod.LEGACY_DEDUP_TABLE))
    import botocore.exceptions
    monkeypatch.setattr(botocore.exceptions, "ClientError", FakeClientError)
    return double


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv(service_mod.FLAG_ENV, "true")
    monkeypatch.setattr(suppression_mod, "CUTOVER_WATERMARK", 1, raising=False)
    monkeypatch.setenv("NOTIF_WA_VERIFIED_SENDERS", PHONE1_META)
    monkeypatch.setenv("SINCH_RCS_ENABLED", "true")
    yield


def claim_all(fake):
    """A claimed call with all three channels eligible. Returns the child ids."""
    params = {"DialAction": "connected", "DialALegUUID": A_LEG, "CallUUID": A_LEG,
              "Direction": "inbound", "From": CUSTOMER, "To": BUSINESS_PSTN}
    result = service_mod.handle_connected_call(params, sender_phone_id=PHONE1_META)
    assert result["claimed"] is True, result
    parent = result["eventClaimKey"]
    return {c: f"{parent}:{c}" for c in ("whatsapp", "sms", "rcs")}


class Recorder:
    """Stands in for a channel adapter."""

    def __init__(self, disposition, message_id="", category=""):
        self.disposition = disposition
        self.message_id = message_id
        self.category = category
        self.calls = []

    def __call__(self, delivery, *, request_id=""):
        self.calls.append(delivery.get("deliveryId"))
        return self.disposition, self.message_id, self.category


def install(monkeypatch, channel, recorder):
    monkeypatch.setitem(worker_mod._ADAPTERS, channel, recorder)
    return recorder


# ══════════════════════════════════════════════════════════════════════════════
# Classification — the three dispositions.
# ══════════════════════════════════════════════════════════════════════════════

class TestClassification:
    @pytest.mark.parametrize("error", [
        "ReadTimeout", "connection reset by peer", "timed out after 15s",
        "BrokenPipeError", "IncompleteRead",
    ])
    def test_ambiguous_errors_go_to_reconcile_not_retry(self, error):
        """The request left us and no answer came back, so the provider may have sent
        it. Retrying would send a second message."""
        disposition, _ = worker_mod.classify_send_outcome(error)
        assert disposition == worker_mod.RECONCILE

    @pytest.mark.parametrize("error", [
        "ThrottlingException", "TooManyRequestsException", "ServiceUnavailable",
        "ProvisionedThroughputExceededException", "InternalServerError",
    ])
    def test_refusals_are_safe_to_retry(self, error):
        disposition, _ = worker_mod.classify_send_outcome(error)
        assert disposition == worker_mod.RETRY

    @pytest.mark.parametrize("error", [
        "MISSING_DLT_TEMPLATE", "invalid_phone", "ValidationException",
        "AccessDeniedException", "opted_out", "template_unverified", "unsupported",
    ])
    def test_hopeless_errors_fail_immediately(self, error):
        disposition, _ = worker_mod.classify_send_outcome(error)
        assert disposition == worker_mod.PERMANENT

    def test_a_timeout_that_also_looks_throttled_is_still_ambiguous(self):
        """Ordering test. Several ambiguous errors also contain a retryable-looking
        word - a ReadTimeout against a throttled endpoint - and treating that as a plain
        retry is exactly the duplicate-send path."""
        disposition, _ = worker_mod.classify_send_outcome(
            "ThrottlingException: read timeout on retry")
        assert disposition == worker_mod.RECONCILE

    def test_unknown_errors_retry_bounded(self):
        disposition, category = worker_mod.classify_send_outcome("something novel")
        assert disposition == worker_mod.RETRY
        assert category == "UNKNOWN"

    def test_the_ambiguous_list_is_deliberately_narrow(self):
        """Widening it turns ordinary refusals into reconciliation work nobody does."""
        assert len(worker_mod._AMBIGUOUS_MARKERS) <= 8


# ══════════════════════════════════════════════════════════════════════════════
# One job, one send.
# ══════════════════════════════════════════════════════════════════════════════

class TestSuccessPath:
    def test_a_successful_send_records_accepted_not_sent(self, fake, monkeypatch):
        """ACCEPTED, because a provider's 200 carries a message id and not evidence of
        transmission. SENT is what the provider tells us later."""
        ids = claim_all(fake)
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "prov-1"))
        out = worker_mod.process_job(ids["sms"])

        assert out["handled"] is True and out["reason"] == "accepted"
        assert rec.calls == [ids["sms"]]
        row = fake.rows(store_mod.DELIVERIES_TABLE)[ids["sms"]]
        assert row["state"] == "ACCEPTED"
        assert row["providerMessageId"] == "prov-1"

    def test_the_lease_is_taken_and_then_released(self, fake, monkeypatch):
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.SENT, "prov-1"))
        worker_mod.process_job(ids["sms"], owner="worker-1")
        job = fake.rows(store_mod.OUTBOX_TABLE)[ids["sms"]]
        assert job["status"] == "ACCEPTED"
        assert job["leaseOwner"] == ""

    def test_leased_is_recorded_before_the_send(self, fake, monkeypatch):
        """So a worker that dies mid-send leaves evidence it was trying."""
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        worker_mod.process_job(ids["sms"])
        attempts = [a["state"] for a in fake.rows(store_mod.ATTEMPTS_TABLE).values()
                    if a["deliveryId"] == ids["sms"]]
        assert "LEASED" in attempts
        assert "ACCEPTED" in attempts


class TestAtMostOnce:
    def test_a_duplicate_queue_delivery_does_not_send_twice(self, fake, monkeypatch):
        """SQS is at-least-once, so this is the normal case, not an edge case."""
        ids = claim_all(fake)
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "prov-1"))
        worker_mod.process_job(ids["sms"])
        worker_mod.process_job(ids["sms"])
        worker_mod.process_job(ids["sms"])
        assert len(rec.calls) == 1, "the channel must be sent exactly once"

    def test_a_terminal_delivery_is_never_sent(self, fake, monkeypatch):
        ids = claim_all(fake)
        store_mod.record_attempt(ids["sms"], state="LEASED")
        store_mod.record_attempt(ids["sms"], state="FAILED",
                                 error_category="INVALID_PHONE",
                                 error_is_permanent=True)
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        out = worker_mod.process_job(ids["sms"])
        assert out["handled"] is False
        assert out["reason"] == "not_sendable_failed"
        assert rec.calls == []

    def test_a_live_lease_elsewhere_blocks_the_send(self, fake, monkeypatch):
        ids = claim_all(fake)
        assert store_mod.acquire_lease(ids["sms"], owner="other-worker") is True
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        out = worker_mod.process_job(ids["sms"], owner="me")
        assert out["reason"] == "lease_held_elsewhere"
        assert rec.calls == []

    def test_an_exhausted_budget_fails_without_sending(self, fake, monkeypatch):
        ids = claim_all(fake)
        rows = fake.rows(store_mod.DELIVERIES_TABLE)
        rows[ids["sms"]]["attemptCount"] = 3
        rows[ids["sms"]]["maxAttempts"] = 3
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        out = worker_mod.process_job(ids["sms"])
        assert out["reason"] == "attempts_exhausted"
        assert rec.calls == []
        assert rows[ids["sms"]]["state"] == "FAILED"

    def test_an_orphan_job_is_dropped_not_sent(self, fake, monkeypatch):
        """A job with no delivery cannot be reconciled against anything, so sending
        would leave no record that we did."""
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        out = worker_mod.process_job("plivo:ghost:connected-notifications:v2:sms")
        assert out["handled"] is False and out["reason"] == "orphan_job"
        assert rec.calls == []


class TestReconcileBranch:
    def test_an_ambiguous_failure_is_not_retried(self, fake, monkeypatch):
        ids = claim_all(fake)
        rec = install(monkeypatch, "sms",
                      Recorder(worker_mod.RECONCILE, "", "READ_TIMEOUT"))
        out = worker_mod.process_job(ids["sms"])

        assert out["reason"] == "reconciliation_required"
        row = fake.rows(store_mod.DELIVERIES_TABLE)[ids["sms"]]
        assert row["state"] == "RECONCILIATION_REQUIRED"
        assert row["errorCategory"] == "READ_TIMEOUT"
        # Crucially NOT marked permanent: a human or reconciler must resolve it.
        assert row.get("errorIsPermanent") in (None, False)

    def test_reconciliation_is_not_a_terminal_state(self, fake, monkeypatch):
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.RECONCILE, "", "TIMEOUT"))
        worker_mod.process_job(ids["sms"])
        assert states_mod.is_terminal("RECONCILIATION_REQUIRED") is False

    def test_a_reconcile_job_is_not_picked_up_again_by_the_sweep(self, fake, monkeypatch):
        """It must not silently resend. The outbox row leaves READY."""
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.RECONCILE, "", "TIMEOUT"))
        worker_mod.process_job(ids["sms"])
        assert (fake.rows(store_mod.OUTBOX_TABLE)[ids["sms"]]["status"]
                == "RECONCILIATION_REQUIRED")

    def test_it_alarms(self, fake, monkeypatch, caplog):
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.RECONCILE, "", "TIMEOUT"))
        with caplog.at_level("ERROR"):
            worker_mod.process_job(ids["sms"])
        assert "NOTIF_RECONCILIATION_REQUIRED" in caplog.text


class TestRetryAndPermanent:
    def test_a_retryable_failure_returns_the_job_to_ready_with_backoff(self, fake, monkeypatch):
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.RETRY, "", "THROTTLED"))
        before = int(time.time())
        out = worker_mod.process_job(ids["sms"])

        assert out["reason"] == "retry_scheduled"
        job = fake.rows(store_mod.OUTBOX_TABLE)[ids["sms"]]
        assert job["status"] == "READY"
        assert int(job["availableAt"]) >= before + worker_mod.RETRY_BACKOFF_SECONDS
        assert fake.rows(store_mod.DELIVERIES_TABLE)[ids["sms"]]["state"] == "READY"

    def test_a_retried_job_can_then_succeed(self, fake, monkeypatch):
        """The retry edge end to end: LEASED -> READY -> LEASED -> ACCEPTED. The first
        draft of the state machine refused the READY step as out_of_order, which would
        have stranded this forever."""
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.RETRY, "", "THROTTLED"))
        worker_mod.process_job(ids["sms"])
        install(monkeypatch, "sms", Recorder(worker_mod.SENT, "prov-2"))
        out = worker_mod.process_job(ids["sms"])
        assert out["reason"] == "accepted"
        assert fake.rows(store_mod.DELIVERIES_TABLE)[ids["sms"]]["state"] == "ACCEPTED"

    def test_a_permanent_failure_is_terminal_and_marked_permanent(self, fake, monkeypatch):
        ids = claim_all(fake)
        install(monkeypatch, "sms",
                Recorder(worker_mod.PERMANENT, "", "MISSING_DLT_TEMPLATE"))
        out = worker_mod.process_job(ids["sms"])
        assert out["reason"] == "failed_permanent"
        row = fake.rows(store_mod.DELIVERIES_TABLE)[ids["sms"]]
        assert row["state"] == "FAILED"
        assert row["errorIsPermanent"] is True
        assert store_mod.is_retryable(row) is False


class TestChannelIndependence:
    def test_one_channel_failing_does_not_affect_the_others(self, fake, monkeypatch):
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.PERMANENT, "", "INVALID_PHONE"))
        install(monkeypatch, "whatsapp", Recorder(worker_mod.SENT, "wamid.X"))
        install(monkeypatch, "rcs", Recorder(worker_mod.RETRY, "", "THROTTLED"))

        worker_mod.process_job(ids["sms"])
        worker_mod.process_job(ids["whatsapp"])
        worker_mod.process_job(ids["rcs"])

        rows = fake.rows(store_mod.DELIVERIES_TABLE)
        assert rows[ids["sms"]]["state"] == "FAILED"
        assert rows[ids["whatsapp"]]["state"] == "ACCEPTED"
        assert rows[ids["rcs"]]["state"] == "READY"

    def test_each_channel_holds_its_own_lease(self, fake, monkeypatch):
        ids = claim_all(fake)
        assert store_mod.acquire_lease(ids["sms"], owner="a") is True
        assert store_mod.acquire_lease(ids["rcs"], owner="b") is True


class TestSweep:
    def test_the_sweep_picks_up_a_ready_job_nothing_enqueued(self, fake, monkeypatch):
        """Crash-before-enqueue recovery, and the reason the outbox is the queue of
        record. The claim transaction wrote the row; if the process died before anything
        reached SQS, the row is still READY and the sweep finds it. Without this the
        transactional outbox would be decorative."""
        ids = claim_all(fake)
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "prov-1"))
        result = worker_mod.sweep_ready_jobs()
        assert result["outcomes"].get(ids["sms"]) == "accepted"
        assert rec.calls == [ids["sms"]]

    def test_the_sweep_ignores_a_job_whose_backoff_has_not_elapsed(self, fake, monkeypatch):
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.RETRY, "", "THROTTLED"))
        worker_mod.process_job(ids["sms"])
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        result = worker_mod.sweep_ready_jobs(now=int(time.time()))
        assert ids["sms"] not in result["outcomes"]
        assert rec.calls == []

    def test_the_sweep_processes_it_once_the_backoff_elapses(self, fake, monkeypatch):
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.RETRY, "", "THROTTLED"))
        worker_mod.process_job(ids["sms"])
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        later = int(time.time()) + worker_mod.RETRY_BACKOFF_SECONDS + 1
        result = worker_mod.sweep_ready_jobs(now=later)
        assert result["outcomes"].get(ids["sms"]) == "accepted"
        assert rec.calls == [ids["sms"]]

    def test_one_unreachable_row_does_not_abandon_the_batch(self, fake, monkeypatch):
        ids = claim_all(fake)

        def _boom(delivery, *, request_id=""):
            raise store_mod.NotificationStoreUnavailable("gone")

        install(monkeypatch, "sms", _boom)
        install(monkeypatch, "rcs", Recorder(worker_mod.SENT, "p"))
        install(monkeypatch, "whatsapp", Recorder(worker_mod.SENT, "p"))
        result = worker_mod.sweep_ready_jobs()
        assert result["examined"] >= 1
        assert "store_unavailable" in result["outcomes"].values()
        # The other channels were still attempted.
        assert any(v == "accepted" for v in result["outcomes"].values())

    def test_a_skipped_channel_never_appears_in_the_sweep(self, fake, monkeypatch):
        """Ineligible channels get a delivery row but no outbox job, so there is no work
        for a worker that could never succeed."""
        monkeypatch.delenv("SINCH_RCS_ENABLED", raising=False)
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        install(monkeypatch, "whatsapp", Recorder(worker_mod.SENT, "p"))
        result = worker_mod.sweep_ready_jobs()
        assert ids["rcs"] not in result["outcomes"]
        assert ids["rcs"] not in fake.rows(store_mod.OUTBOX_TABLE)


class TestBodyIsNotEdited:
    def test_the_sms_body_matches_the_approved_dlt_template(self):
        """The operator silently drops a mismatched body while the API call still
        succeeds, so a 'small improvement' produces a send that reports success and
        delivers nothing."""
        body = worker_mod.notification_body()
        assert body.startswith("Thanks for contacting WECARE.DIGITAL!")
        assert "https://wecare.digital/selfservice" in body
        assert "https://wecare.digital/r/wa" in body
        assert body.endswith("We'll review it and follow up if needed.")

    def test_it_is_overridable_only_by_environment(self, monkeypatch):
        monkeypatch.setenv("NOTIF_SMS_BODY", "override")
        assert worker_mod.notification_body() == "override"


class TestNeverResendAnAlreadySentChannel:
    """`is_sendable`, not `not is_terminal`. This class exists because a failing test
    caught the difference: `ACCEPTED` is not terminal, so a terminality check treated an
    already-sent channel as work to do and sent it again - and a duplicate SQS delivery
    is the normal case, not an edge case."""

    @pytest.mark.parametrize("state", ["ACCEPTED", "SENT", "DELIVERED", "READ"])
    def test_a_channel_already_with_the_provider_is_not_resent(self, fake, monkeypatch, state):
        ids = claim_all(fake)
        fake.rows(store_mod.DELIVERIES_TABLE)[ids["sms"]]["state"] = state
        fake.rows(store_mod.DELIVERIES_TABLE)[ids["sms"]][states_mod.RANK_ATTRIBUTE] = \
            states_mod.rank(state)
        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        out = worker_mod.process_job(ids["sms"])
        assert out["handled"] is False
        assert out["reason"] == f"not_sendable_{state.lower()}"
        assert rec.calls == []

    def test_a_reconciliation_row_is_not_resent_by_the_worker(self, fake, monkeypatch):
        """The state exists precisely because the provider may already have sent it.
        Letting the sender act on it would defeat its whole purpose."""
        ids = claim_all(fake)
        install(monkeypatch, "sms", Recorder(worker_mod.RECONCILE, "", "TIMEOUT"))
        worker_mod.process_job(ids["sms"])

        rec = install(monkeypatch, "sms", Recorder(worker_mod.SENT, "p"))
        out = worker_mod.process_job(ids["sms"])
        assert out["handled"] is False
        assert out["reason"] == "not_sendable_reconciliation_required"
        assert rec.calls == []

    def test_reconciliation_is_actionable_but_not_sendable(self):
        """The two predicates disagree on exactly this state, and that is the point."""
        assert states_mod.is_actionable("RECONCILIATION_REQUIRED") is True
        assert states_mod.is_sendable("RECONCILIATION_REQUIRED") is False

    def test_accepted_is_neither_terminal_nor_sendable(self):
        assert states_mod.is_terminal("ACCEPTED") is False
        assert states_mod.is_sendable("ACCEPTED") is False

    def test_sendable_is_exactly_the_three_pre_send_states(self):
        assert states_mod.SENDABLE_STATES == frozenset({"PENDING", "READY", "LEASED"})
