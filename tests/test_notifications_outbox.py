"""Exactly-once: the transactional outbox, leases, and the crash windows.

The brief is explicit that claim-before-send alone is insufficient, and names the
four cases that must be covered: crash-before-enqueue, crash-after-provider-
acceptance, expired leases, and partial-channel failures. These tests cover each.

The defect being replaced
-------------------------
`pstn/notifications.handle_connected` claimed the channel, then called `dispatch`.
If the process died between those two steps the claim row survived saying `PENDING`,
owned by nothing. The provider's redelivery then found the claim taken and did
nothing, so the customer was never notified and no alarm fired. The old RCS path had
that shape *by design* - claimed, logged `plivo_rcs_deferred`, and no worker was ever
built to drain it, so every RCS row would have sat `PENDING` forever.

The fix is that the claim and the job are written in one `TransactWriteItems`. These
tests assert that property directly, by inspecting the transaction rather than
trusting it.

No AWS. A small in-memory double stands in for DynamoDB, implementing only the
operations the store uses and, importantly, the *conditional* semantics - a fake that
ignores ConditionExpression would make every one of these tests pass vacuously.
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

from lambda_utils.notifications import events as events_mod  # noqa: E402
from lambda_utils.notifications import policy as policy_mod  # noqa: E402
from lambda_utils.notifications import service as service_mod  # noqa: E402
from lambda_utils.notifications import states as states_mod  # noqa: E402
from lambda_utils.notifications import store as store_mod  # noqa: E402
from lambda_utils.notifications import suppression as suppression_mod  # noqa: E402

CUSTOMER = "+919876543210"
BUSINESS_PSTN = "+918031830030"
PHONE1_META = "1016149501586345"
A_LEG = "a-leg-uuid-1234"


class FakeClientError(Exception):
    def __init__(self, code, reasons=None):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}
        if reasons is not None:
            self.response["CancellationReasons"] = reasons


class FakeTable:
    """Implements put_item, get_item and update_item with real conditional semantics.

    Only the condition forms the store actually uses are supported, and anything else
    raises - a fake that silently accepted an unrecognised condition would let a
    broken guard pass its tests.
    """

    def __init__(self, store, name, key_attr):
        self.store = store
        self.name = name
        self.key_attr = key_attr

    def _rows(self):
        return self.store.tables.setdefault(self.name, {})

    def put_item(self, Item=None, ConditionExpression=None, **_):
        self.store.record(self.name, "put_item")
        if self.store.fail_with:
            raise self.store.fail_with
        key = Item[self.key_attr]
        if ConditionExpression and "attribute_not_exists" in str(ConditionExpression):
            if key in self._rows():
                raise FakeClientError("ConditionalCheckFailedException")
        self._rows()[key] = dict(Item)

    def get_item(self, Key=None, **_):
        self.store.record(self.name, "get_item")
        if self.store.fail_with:
            raise self.store.fail_with
        row = self._rows().get(Key[self.key_attr])
        return {"Item": dict(row)} if row else {}

    def query(self, IndexName=None, KeyConditionExpression=None, Limit=None, **_):
        """Only the one index the sweep uses: status + availableAt.

        Implemented against the condition's own values rather than accepting any query,
        so a sweep that queried the wrong index or dropped its time bound would fail here
        instead of silently returning everything.
        """
        self.store.record(self.name, "query")
        if self.store.fail_with:
            raise self.store.fail_with
        if IndexName != "status-availableAt-index":
            raise AssertionError(f"unexpected index {IndexName!r}")

        expr = KeyConditionExpression
        values = getattr(expr, "_values", ()) or ()
        wanted_status, cutoff = None, None
        for part in values:
            for attr in (getattr(part, "_values", ()) or ()):
                if isinstance(attr, str):
                    wanted_status = attr
                elif isinstance(attr, int):
                    cutoff = attr
        if wanted_status is None or cutoff is None:
            raise AssertionError("sweep query must bound both status and availableAt")

        items = [dict(r) for r in self._rows().values()
                 if r.get("status") == wanted_status
                 and int(r.get("availableAt") or 0) <= cutoff]
        items.sort(key=lambda r: int(r.get("availableAt") or 0))
        if Limit:
            items = items[:Limit]
        return {"Items": items, "Count": len(items)}

    def update_item(self, Key=None, UpdateExpression="", ConditionExpression=None,
                    ExpressionAttributeValues=None, ExpressionAttributeNames=None,
                    ReturnValues=None, **_):
        self.store.record(self.name, "update_item")
        if self.store.fail_with:
            raise self.store.fail_with
        key = Key[self.key_attr]
        rows = self._rows()
        existing = rows.get(key)

        cond = str(ConditionExpression or "")
        values = ExpressionAttributeValues or {}

        if "attribute_exists" in cond and existing is None:
            raise FakeClientError("ConditionalCheckFailedException")
        # The rewind guard: `#state IN (:rw0, ...)`. Evaluated separately from the
        # rank guard because the two condition shapes are mutually exclusive, and a
        # fake that only understood the rank form would silently pass every rewind.
        rewind_placeholders = [k for k in values if k.startswith(":rw")]
        if rewind_placeholders and "#state IN (:rw" in cond:
            if existing is not None and states_mod.RANK_ATTRIBUTE in existing:
                allowed = {values[k] for k in rewind_placeholders}
                if existing.get("state") not in allowed:
                    raise FakeClientError("ConditionalCheckFailedException")
                if states_mod.is_terminal(existing.get("state")):
                    raise FakeClientError("ConditionalCheckFailedException")
        elif states_mod.RANK_ATTRIBUTE in cond and existing is not None:
            current_rank = int(existing.get(states_mod.RANK_ATTRIBUTE, -1))
            if current_rank >= int(values.get(":rank", 0)):
                raise FakeClientError("ConditionalCheckFailedException")
            if states_mod.is_terminal(existing.get("state")):
                raise FakeClientError("ConditionalCheckFailedException")
        if "leaseExpiresAt" in cond and existing is not None:
            status = existing.get("status")
            lease_expiry = int(existing.get("leaseExpiresAt") or 0)
            stamp = int(values.get(":stamp", 0))
            if not (status == states_mod.READY or lease_expiry < stamp):
                raise FakeClientError("ConditionalCheckFailedException")

        row = dict(existing or {self.key_attr: key})
        # Apply only the assignments the store actually makes. Enough fidelity for the
        # guards under test without reimplementing DynamoDB's expression language.
        if ":s" in values:
            row["state" if self.name != store_mod.OUTBOX_TABLE else "status"] = values[":s"]
        if ":rank" in values:
            row[states_mod.RANK_ATTRIBUTE] = values[":rank"]
        if ":leased" in values:
            row["status"] = values[":leased"]
        if ":owner" in values:
            row["leaseOwner"] = values[":owner"]
        if ":expiry" in values:
            row["leaseExpiresAt"] = values[":expiry"]
        if ":pmid" in values:
            row["providerMessageId"] = values[":pmid"]
        if ":err" in values:
            row["errorCategory"] = values[":err"]
        if ":perm" in values:
            row["errorIsPermanent"] = values[":perm"]
        if ":provider" in values:
            row["channelProvider"] = values[":provider"]
        if ":available" in values:
            row["availableAt"] = values[":available"]
        if ":empty" in values and "leaseOwner = :empty" in UpdateExpression:
            row["leaseOwner"] = ""
            row["leaseExpiresAt"] = 0
        if "attemptCount" in UpdateExpression:
            row["attemptCount"] = int(row.get("attemptCount") or 0) + 1
        rows[key] = row
        return {"Attributes": dict(row)}


class FakeDynamo:
    """Holds the tables, records calls, and can be made to fail."""

    KEYS = {
        store_mod.EVENTS_TABLE: "eventClaimKey",
        store_mod.DELIVERIES_TABLE: "deliveryId",
        store_mod.ATTEMPTS_TABLE: "attemptId",
        store_mod.OUTBOX_TABLE: "jobId",
        suppression_mod.LEGACY_DEDUP_TABLE: "eventKey",
    }

    def __init__(self):
        self.tables = {}
        self.calls = []
        self.transactions = []
        self.fail_with = None
        self.transact_fail = None

    def record(self, table, op):
        self.calls.append((table, op))

    def Table(self, name):
        return FakeTable(self, name, self.KEYS.get(name, "id"))

    # --- the low-level client surface used for TransactWriteItems ---
    def transact_write_items(self, TransactItems=None):
        self.transactions.append(TransactItems)
        if self.transact_fail:
            raise self.transact_fail

        # Evaluate every condition FIRST, then apply. That is what makes it a
        # transaction, and a fake that applied as it went would hide a partial write.
        for item in TransactItems:
            put = item["Put"]
            table = put["TableName"]
            key_attr = self.KEYS[table]
            key = put["Item"][key_attr]["S"]
            if "attribute_not_exists" in str(put.get("ConditionExpression", "")):
                if key in self.tables.get(table, {}):
                    raise FakeClientError(
                        "TransactionCanceledException",
                        reasons=[{"Code": "ConditionalCheckFailed"}])

        for item in TransactItems:
            put = item["Put"]
            table = put["TableName"]
            key_attr = self.KEYS[table]
            row = {}
            for field, wrapped in put["Item"].items():
                row[field] = (wrapped.get("S") if "S" in wrapped
                              else int(wrapped["N"]) if "N" in wrapped
                              else wrapped.get("BOOL"))
            self.tables.setdefault(table, {})[row[key_attr]] = row

    def rows(self, table):
        return self.tables.get(table, {})


@pytest.fixture
def fake(monkeypatch):
    """Install the double and reset the modules' cached clients."""
    double = FakeDynamo()
    monkeypatch.setattr(store_mod, "_resource", double, raising=False)
    monkeypatch.setattr(store_mod, "_client", double, raising=False)
    monkeypatch.setattr(store_mod, "_res", lambda: double)
    monkeypatch.setattr(store_mod, "_cli", lambda: double)
    monkeypatch.setattr(suppression_mod, "_resource", double, raising=False)
    monkeypatch.setattr(suppression_mod, "_table", lambda: double.Table(
        suppression_mod.LEGACY_DEDUP_TABLE))
    # Import-time ClientError in the store resolves to botocore's; point the fake's
    # exception at the same place the store catches.
    import botocore.exceptions
    monkeypatch.setattr(botocore.exceptions, "ClientError", FakeClientError)
    return double


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    """Domain on, watermark in the past, RCS/WA off - the realistic QA posture."""
    monkeypatch.setenv(service_mod.FLAG_ENV, "true")
    monkeypatch.setattr(suppression_mod, "CUTOVER_WATERMARK", 1, raising=False)
    for var in ("SINCH_RCS_ENABLED", "AWS_RCS_AVAILABLE", "NOTIF_WA_VERIFIED_SENDERS"):
        monkeypatch.delenv(var, raising=False)
    yield


def make_event(**overrides):
    params = {
        "DialAction": "connected", "DialALegUUID": A_LEG, "CallUUID": A_LEG,
        "Direction": "inbound", "From": CUSTOMER, "To": BUSINESS_PSTN,
    }
    params.update(overrides)
    event, reason = events_mod.from_plivo_dial_callback(params)
    assert event is not None, reason
    return event


# ══════════════════════════════════════════════════════════════════════════════
# Claim and publish are one write.
# ══════════════════════════════════════════════════════════════════════════════

class TestAtomicClaimAndPublish:
    def test_claim_and_jobs_are_a_single_transaction(self, fake):
        """The crash-before-enqueue defence. If these were two writes, a crash between
        them would leave a claim nothing owns - which is what the retired design did,
        and how a notification was lost silently."""
        event = make_event()
        decisions = policy_mod.decide_all(event.external_party,
                                          sender_phone_id=PHONE1_META)
        result = store_mod.claim_event_and_publish(event, decisions)

        assert result["claimed"] is True
        assert len(fake.transactions) == 1, "must be ONE transaction, not several"
        tables = [i["Put"]["TableName"] for i in fake.transactions[0]]
        assert store_mod.EVENTS_TABLE in tables
        assert store_mod.DELIVERIES_TABLE in tables
        assert store_mod.OUTBOX_TABLE in tables

    def test_exactly_one_delivery_per_channel(self, fake):
        event = make_event()
        store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))
        deliveries = fake.rows(store_mod.DELIVERIES_TABLE)
        assert len(deliveries) == 3
        assert {d["channel"] for d in deliveries.values()} == {"whatsapp", "sms", "rcs"}

    def test_the_parent_claim_is_the_only_conditional_write(self, fake):
        """Serialising on the parent is what makes the unconditional child puts safe:
        if the parent exists the whole transaction is rejected and nothing is
        overwritten."""
        event = make_event()
        store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))
        conditional = [i["Put"]["TableName"] for i in fake.transactions[0]
                       if "ConditionExpression" in i["Put"]]
        assert conditional == [store_mod.EVENTS_TABLE]

    def test_a_duplicate_connected_event_claims_nothing(self, fake):
        event = make_event()
        decisions = policy_mod.decide_all(event.external_party,
                                         sender_phone_id=PHONE1_META)
        first = store_mod.claim_event_and_publish(event, decisions)
        second = store_mod.claim_event_and_publish(event, decisions)

        assert first["claimed"] is True
        assert second["claimed"] is False
        assert second["reason"] == "duplicate_connected_event"
        assert len(fake.rows(store_mod.DELIVERIES_TABLE)) == 3, "no extra deliveries"

    def test_a_duplicate_does_not_overwrite_progress(self, fake):
        """A redelivered parent must not reset a channel that already advanced."""
        event = make_event()
        decisions = policy_mod.decide_all(event.external_party,
                                         sender_phone_id=PHONE1_META)
        store_mod.claim_event_and_publish(event, decisions)
        sms_id = event.child_claim_key("sms")
        store_mod.record_attempt(sms_id, state="SENT", provider="aws-end-user-messaging",
                                 provider_message_id="msg-1")

        store_mod.claim_event_and_publish(event, decisions)
        assert fake.rows(store_mod.DELIVERIES_TABLE)[sms_id]["state"] == "SENT"

    def test_two_different_calls_do_not_collide(self, fake):
        decisions_a = policy_mod.decide_all(CUSTOMER, sender_phone_id=PHONE1_META)
        event_a = make_event(DialALegUUID="call-A", CallUUID="call-A")
        event_b = make_event(DialALegUUID="call-B", CallUUID="call-B")
        assert store_mod.claim_event_and_publish(event_a, decisions_a)["claimed"] is True
        assert store_mod.claim_event_and_publish(event_b, decisions_a)["claimed"] is True
        assert len(fake.rows(store_mod.DELIVERIES_TABLE)) == 6


class TestIneligibleChannels:
    def test_an_ineligible_channel_gets_a_skipped_row_and_no_job(self, fake):
        """'Not applicable' must be visible and auditable, not absent - but it must not
        create work for a worker that can never succeed."""
        event = make_event()
        result = store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))

        # RCS off and the WhatsApp template unverified, so only SMS is publishable.
        assert result["published"] == ["sms"]
        assert sorted(result["skipped"]) == ["rcs", "whatsapp"]

        deliveries = fake.rows(store_mod.DELIVERIES_TABLE)
        assert deliveries[event.child_claim_key("rcs")]["state"] == "SKIPPED"
        assert deliveries[event.child_claim_key("whatsapp")]["state"] == "SKIPPED"
        assert deliveries[event.child_claim_key("sms")]["state"] == "PENDING"

        jobs = fake.rows(store_mod.OUTBOX_TABLE)
        assert list(jobs) == [event.child_claim_key("sms")]

    def test_skipped_rows_carry_their_reason_and_are_permanent(self, fake):
        event = make_event()
        store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))
        rcs = fake.rows(store_mod.DELIVERIES_TABLE)[event.child_claim_key("rcs")]
        assert rcs["errorIsPermanent"] is True
        assert "UNSUPPORTED" in rcs["eligibilityReason"]
        assert rcs["completedAt"] > 0

    def test_all_three_eligible_publishes_three_jobs(self, fake, monkeypatch):
        monkeypatch.setenv("SINCH_RCS_ENABLED", "true")
        monkeypatch.setenv("NOTIF_WA_VERIFIED_SENDERS", PHONE1_META)
        event = make_event()
        result = store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))
        assert sorted(result["published"]) == ["rcs", "sms", "whatsapp"]
        assert len(fake.rows(store_mod.OUTBOX_TABLE)) == 3


class TestStoreFailsClosed:
    def test_a_transaction_failure_raises_rather_than_returning_false(self, fake):
        """A caller must be able to tell 'somebody else claimed it' from 'I could not
        tell'. Returning False for both would send nothing in the first case and
        nothing in the second - but the second needs a retryable 5xx so the provider
        redelivers."""
        fake.transact_fail = FakeClientError("InternalServerError")
        event = make_event()
        with pytest.raises(store_mod.NotificationStoreUnavailable):
            store_mod.claim_event_and_publish(
                event, policy_mod.decide_all(event.external_party,
                                            sender_phone_id=PHONE1_META))

    def test_a_non_client_exception_also_raises_the_typed_error(self, fake):
        fake.transact_fail = RuntimeError("socket closed")
        event = make_event()
        with pytest.raises(store_mod.NotificationStoreUnavailable):
            store_mod.claim_event_and_publish(
                event, policy_mod.decide_all(event.external_party,
                                            sender_phone_id=PHONE1_META))

    def test_recording_against_an_unclaimed_delivery_raises(self, fake):
        """Recording a send for a call nobody claimed would defeat the guard the whole
        design rests on."""
        with pytest.raises(store_mod.NotificationStoreUnavailable):
            store_mod.record_attempt("plivo:never-claimed:connected-notifications:v2:sms",
                                     state="SENT")

    def test_read_errors_raise_rather_than_looking_like_absence(self, fake):
        fake.fail_with = RuntimeError("timeout")
        with pytest.raises(store_mod.NotificationStoreUnavailable):
            store_mod.get_delivery("anything")


# ══════════════════════════════════════════════════════════════════════════════
# Leases. Expired-lease recovery, and two workers never sending the same channel.
# ══════════════════════════════════════════════════════════════════════════════

class TestLeases:
    def _claim(self, fake):
        event = make_event()
        store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))
        return event, event.child_claim_key("sms")

    def test_a_worker_can_take_a_ready_job(self, fake):
        _, job = self._claim(fake)
        assert store_mod.acquire_lease(job, owner="worker-1") is True
        row = fake.rows(store_mod.OUTBOX_TABLE)[job]
        assert row["status"] == "LEASED"
        assert row["leaseOwner"] == "worker-1"

    def test_a_second_worker_is_refused_while_the_lease_is_live(self, fake):
        """This is what stops two workers sending the same channel."""
        _, job = self._claim(fake)
        now = int(time.time())
        assert store_mod.acquire_lease(job, owner="worker-1", now=now) is True
        assert store_mod.acquire_lease(job, owner="worker-2", now=now) is False
        assert fake.rows(store_mod.OUTBOX_TABLE)[job]["leaseOwner"] == "worker-1"

    def test_an_expired_lease_is_reclaimable(self, fake):
        """The crash-recovery path: a worker that died holding a lease must not block
        the job forever."""
        _, job = self._claim(fake)
        now = int(time.time())
        assert store_mod.acquire_lease(job, owner="worker-1", now=now,
                                       lease_seconds=60) is True
        assert store_mod.acquire_lease(job, owner="worker-2",
                                       now=now + 61) is True
        assert fake.rows(store_mod.OUTBOX_TABLE)[job]["leaseOwner"] == "worker-2"

    def test_a_lease_one_second_before_expiry_is_still_held(self, fake):
        _, job = self._claim(fake)
        now = int(time.time())
        store_mod.acquire_lease(job, owner="worker-1", now=now, lease_seconds=60)
        assert store_mod.acquire_lease(job, owner="worker-2", now=now + 59) is False

    def test_leasing_a_job_that_does_not_exist_is_refused(self, fake):
        assert store_mod.acquire_lease("no-such-job", owner="w") is False

    def test_release_for_retry_returns_it_to_ready(self, fake):
        _, job = self._claim(fake)
        store_mod.acquire_lease(job, owner="worker-1")
        store_mod.release_job(job, status=states_mod.READY)
        row = fake.rows(store_mod.OUTBOX_TABLE)[job]
        assert row["status"] == "READY"
        assert row["leaseOwner"] == ""
        assert row["leaseExpiresAt"] == 0
        assert store_mod.acquire_lease(job, owner="worker-2") is True

    def test_lease_seconds_default_exceeds_a_worker_timeout(self):
        """Reclaiming a lease from a worker that is still running would send twice, so
        the lease must outlive the worker's own Lambda timeout."""
        assert store_mod.LEASE_SECONDS >= 300


# ══════════════════════════════════════════════════════════════════════════════
# Attempts and receipts.
# ══════════════════════════════════════════════════════════════════════════════

class TestAttemptsAreAppendOnly:
    def _claimed_sms(self, fake):
        event = make_event()
        store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))
        return event.child_claim_key("sms")

    def test_every_attempt_writes_its_own_row(self, fake):
        """The brief distinguishes one logical delivery from many physical attempts.
        The retired design incremented a counter on the delivery row, so the history of
        what was tried was overwritten by its own summary."""
        sms = self._claimed_sms(fake)
        store_mod.record_attempt(sms, state="LEASED")
        store_mod.record_attempt(sms, state="SENT", provider="aws-end-user-messaging",
                                 provider_message_id="msg-1")
        store_mod.record_attempt(sms, state="DELIVERED")
        assert len(fake.rows(store_mod.ATTEMPTS_TABLE)) == 3

    def test_a_refused_transition_still_records_the_attempt(self, fake):
        """History of a refused transition is still history worth having."""
        sms = self._claimed_sms(fake)
        store_mod.record_attempt(sms, state="LEASED")
        store_mod.record_attempt(sms, state="SENT")
        store_mod.record_attempt(sms, state="DELIVERED")
        before = len(fake.rows(store_mod.ATTEMPTS_TABLE))

        result = store_mod.record_attempt(sms, state="SENT")
        assert result["applied"] is False
        assert result["reason"] == "out_of_order"
        assert len(fake.rows(store_mod.ATTEMPTS_TABLE)) == before + 1

    def test_a_late_sent_does_not_overwrite_delivered(self, fake):
        sms = self._claimed_sms(fake)
        store_mod.record_attempt(sms, state="LEASED")
        store_mod.record_attempt(sms, state="SENT")
        store_mod.record_attempt(sms, state="DELIVERED")
        store_mod.record_attempt(sms, state="SENT")
        assert fake.rows(store_mod.DELIVERIES_TABLE)[sms]["state"] == "DELIVERED"

    def test_attempt_count_increments_on_the_delivery(self, fake):
        sms = self._claimed_sms(fake)
        store_mod.record_attempt(sms, state="LEASED")
        store_mod.record_attempt(sms, state="READY")
        row = fake.rows(store_mod.DELIVERIES_TABLE)[sms]
        assert int(row["attemptCount"]) >= 2

    def test_provider_message_id_is_persisted(self, fake):
        sms = self._claimed_sms(fake)
        store_mod.record_attempt(sms, state="LEASED")
        store_mod.record_attempt(sms, state="ACCEPTED",
                                 provider_message_id="prov-abc")
        assert fake.rows(store_mod.DELIVERIES_TABLE)[sms]["providerMessageId"] == "prov-abc"

    def test_an_unknown_state_is_rejected_before_any_write(self, fake):
        sms = self._claimed_sms(fake)
        with pytest.raises(ValueError):
            store_mod.record_attempt(sms, state="TELEPORTED")
        assert len(fake.rows(store_mod.ATTEMPTS_TABLE)) == 0


class TestPartialChannelFailure:
    def test_one_channel_failing_does_not_touch_another(self, fake, monkeypatch):
        """The brief: a failure on one channel must not suppress or duplicate another."""
        monkeypatch.setenv("SINCH_RCS_ENABLED", "true")
        monkeypatch.setenv("NOTIF_WA_VERIFIED_SENDERS", PHONE1_META)
        event = make_event()
        store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))

        sms, wa = event.child_claim_key("sms"), event.child_claim_key("whatsapp")
        store_mod.record_attempt(sms, state="LEASED")
        store_mod.record_attempt(sms, state="FAILED", error_category="INVALID_PHONE",
                                 error_is_permanent=True)
        store_mod.record_attempt(wa, state="LEASED")
        store_mod.record_attempt(wa, state="SENT", provider_message_id="wamid.X")

        deliveries = fake.rows(store_mod.DELIVERIES_TABLE)
        assert deliveries[sms]["state"] == "FAILED"
        assert deliveries[wa]["state"] == "SENT"
        assert deliveries[event.child_claim_key("rcs")]["state"] == "PENDING"

    def test_a_completed_channel_is_never_retryable(self, fake):
        """What stops a retry of one channel duplicating a finished one."""
        for terminal in ("READ", "FAILED", "SKIPPED"):
            assert store_mod.is_retryable({"state": terminal}) is False

    def test_a_permanent_error_is_never_retryable(self, fake):
        assert store_mod.is_retryable(
            {"state": "PENDING", "errorIsPermanent": True}) is False

    def test_the_attempt_budget_is_bounded(self, fake):
        assert store_mod.is_retryable(
            {"state": "PENDING", "attemptCount": 3, "maxAttempts": 3}) is False
        assert store_mod.is_retryable(
            {"state": "PENDING", "attemptCount": 2, "maxAttempts": 3}) is True

    def test_an_absent_record_is_retryable(self, fake):
        assert store_mod.is_retryable(None) is True


class TestReconciliationRequired:
    def test_unknown_provider_acceptance_is_recordable_and_not_a_failure(self, fake):
        """The brief: if the provider accepted a send but its response was lost, record
        RECONCILIATION_REQUIRED and reconcile before resending. Reporting it as FAILED
        would invite exactly the resend that must not happen."""
        event = make_event()
        store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))
        sms = event.child_claim_key("sms")
        store_mod.record_attempt(sms, state="LEASED")
        result = store_mod.record_attempt(sms, state=service_mod.reconciliation_state())

        assert result["applied"] is True
        row = fake.rows(store_mod.DELIVERIES_TABLE)[sms]
        assert row["state"] == "RECONCILIATION_REQUIRED"
        assert states_mod.is_terminal("RECONCILIATION_REQUIRED") is False
        assert store_mod.is_retryable(row) is True

    def test_a_real_outcome_later_replaces_it(self, fake):
        event = make_event()
        store_mod.claim_event_and_publish(
            event, policy_mod.decide_all(event.external_party,
                                        sender_phone_id=PHONE1_META))
        sms = event.child_claim_key("sms")
        store_mod.record_attempt(sms, state="LEASED")
        store_mod.record_attempt(sms, state="RECONCILIATION_REQUIRED")
        assert store_mod.record_attempt(sms, state="DELIVERED")["applied"] is True
        assert fake.rows(store_mod.DELIVERIES_TABLE)[sms]["state"] == "DELIVERED"


class TestErrorClassification:
    @pytest.mark.parametrize("error", [
        "MISSING_DLT_TEMPLATE", "invalid_phone", "ValidationException",
        "AccessDenied", "opted_out", "template_unverified", "unsupported",
    ])
    def test_permanent_errors_are_not_retried(self, error):
        _, permanent = service_mod.classify_provider_error(error)
        assert permanent is True

    @pytest.mark.parametrize("error", [
        "ThrottlingException", "timeout", "ServiceUnavailable",
        "InternalServerError", "EndpointConnectionError",
    ])
    def test_transient_errors_are_retried(self, error):
        _, permanent = service_mod.classify_provider_error(error)
        assert permanent is False

    def test_an_unknown_error_is_treated_as_transient(self):
        """The claim already prevents a retry duplicating a completed send, so the cost
        of being wrong is a wasted attempt - whereas calling an unknown transient fault
        permanent silently drops a real notification."""
        category, permanent = service_mod.classify_provider_error("something new")
        assert permanent is False
        assert category == "UNKNOWN"

    def test_no_error_is_transient_unknown(self):
        assert service_mod.classify_provider_error(None) == ("UNKNOWN", False)


# ══════════════════════════════════════════════════════════════════════════════
# The service: flag, suppression, and the no-writes-when-off guarantee.
# ══════════════════════════════════════════════════════════════════════════════

def connected_params(**overrides):
    params = {
        "DialAction": "connected", "DialALegUUID": A_LEG, "CallUUID": A_LEG,
        "Direction": "inbound", "From": CUSTOMER, "To": BUSINESS_PSTN,
    }
    params.update(overrides)
    return params


class TestFlagOffWritesNothing:
    def test_disabled_domain_writes_no_rows_at_all(self, fake, monkeypatch):
        """Not merely 'does not send' - does not write. The tables must describe what
        the domain really did, not what it would have done."""
        monkeypatch.setenv(service_mod.FLAG_ENV, "false")
        result = service_mod.handle_connected_call(connected_params(),
                                                  sender_phone_id=PHONE1_META)
        assert result["claimed"] is False
        assert result["reason"] == "feature_disabled"
        assert fake.transactions == []
        assert fake.rows(store_mod.EVENTS_TABLE) == {}
        assert fake.rows(store_mod.DELIVERIES_TABLE) == {}
        assert fake.rows(store_mod.OUTBOX_TABLE) == {}

    def test_the_flag_defaults_off(self, fake, monkeypatch):
        monkeypatch.delenv(service_mod.FLAG_ENV, raising=False)
        assert service_mod.is_enabled() is False

    @pytest.mark.parametrize("value", ["1", "yes", "TRUE ", "on", "false", ""])
    def test_only_exact_true_enables_it(self, monkeypatch, value):
        monkeypatch.setenv(service_mod.FLAG_ENV, value)
        assert service_mod.is_enabled() is (value.strip().lower() == "true")

    def test_the_flag_is_read_at_call_time_not_import_time(self, fake, monkeypatch):
        """The retired module read it at module scope, so the value froze into a warm
        sandbox and flipping the variable did nothing until a version was published."""
        monkeypatch.setenv(service_mod.FLAG_ENV, "false")
        assert service_mod.is_enabled() is False
        monkeypatch.setenv(service_mod.FLAG_ENV, "true")
        assert service_mod.is_enabled() is True

    def test_a_non_trigger_writes_nothing_even_when_enabled(self, fake):
        result = service_mod.handle_connected_call(
            connected_params(DialAction="hangup"), sender_phone_id=PHONE1_META)
        assert result["claimed"] is False
        assert result["reason"] == "not_connected_hangup"
        assert fake.transactions == []


class TestSuppression:
    def test_no_watermark_suppresses_everything(self, fake, monkeypatch):
        """An operator who enables the domain without setting a watermark gets zero
        notifications - immediately visible - rather than a backfill to every caller in
        the retention window."""
        monkeypatch.setattr(suppression_mod, "CUTOVER_WATERMARK", 0, raising=False)
        result = service_mod.handle_connected_call(connected_params(),
                                                  sender_phone_id=PHONE1_META)
        assert result["claimed"] is False
        assert result["reason"] == "suppressed_no_cutover_watermark_set"
        assert fake.transactions == []

    def test_a_call_before_the_watermark_is_suppressed(self, fake, monkeypatch):
        future = int(time.time()) + 3600
        monkeypatch.setattr(suppression_mod, "CUTOVER_WATERMARK", future, raising=False)
        result = service_mod.handle_connected_call(connected_params(),
                                                  sender_phone_id=PHONE1_META)
        assert result["reason"] == "suppressed_before_cutover_watermark"
        assert fake.transactions == []

    def test_a_call_the_legacy_path_already_notified_is_suppressed(self, fake):
        """The 32 real sends measured over 14 days went out keyed `<CallUUID>:postcall`
        in WebhookDedup. Enabling v2 must not send those callers a second message."""
        fake.tables.setdefault(suppression_mod.LEGACY_DEDUP_TABLE, {})[
            f"{A_LEG}:postcall"] = {"eventKey": f"{A_LEG}:postcall"}
        result = service_mod.handle_connected_call(connected_params(),
                                                  sender_phone_id=PHONE1_META)
        assert result["claimed"] is False
        assert result["reason"] == "suppressed_legacy_postcall_sms_already_sent"
        assert fake.transactions == []

    def test_a_call_the_legacy_path_did_not_notify_proceeds(self, fake):
        result = service_mod.handle_connected_call(connected_params(),
                                                  sender_phone_id=PHONE1_META)
        assert result["claimed"] is True

    def test_an_unreadable_ledger_suppresses(self, fake, monkeypatch):
        """A suppressed notification that should have been sent is a missing message:
        visible and recoverable. An unsuppressed one that should not have been sent is a
        duplicate to a real customer under our DLT sender, and is not."""
        def _boom():
            raise RuntimeError("ledger down")
        monkeypatch.setattr(suppression_mod, "_table", _boom)
        result = service_mod.handle_connected_call(connected_params(),
                                                  sender_phone_id=PHONE1_META)
        assert result["claimed"] is False
        assert result["reason"] == "suppressed_ledger_unreadable_fail_closed"
        assert fake.transactions == []

    def test_suppression_is_checked_before_the_claim(self, fake, monkeypatch):
        """So a suppressed call leaves no v2 rows, keeping the tables a record of real
        work rather than a mix of work and suppression markers."""
        monkeypatch.setattr(suppression_mod, "CUTOVER_WATERMARK", 0, raising=False)
        service_mod.handle_connected_call(connected_params(), sender_phone_id=PHONE1_META)
        assert fake.rows(store_mod.EVENTS_TABLE) == {}


class TestServiceEndToEnd:
    def test_one_connected_call_produces_three_logical_deliveries(self, fake, monkeypatch):
        """The phase's headline requirement, with all three channels eligible."""
        monkeypatch.setenv("SINCH_RCS_ENABLED", "true")
        monkeypatch.setenv("NOTIF_WA_VERIFIED_SENDERS", PHONE1_META)
        result = service_mod.handle_connected_call(connected_params(),
                                                  sender_phone_id=PHONE1_META)
        assert result["claimed"] is True
        assert sorted(result["published"]) == ["rcs", "sms", "whatsapp"]
        assert len(fake.rows(store_mod.DELIVERIES_TABLE)) == 3
        assert len(fake.rows(store_mod.OUTBOX_TABLE)) == 3

    def test_a_replayed_callback_produces_no_second_copy(self, fake, monkeypatch):
        monkeypatch.setenv("SINCH_RCS_ENABLED", "true")
        monkeypatch.setenv("NOTIF_WA_VERIFIED_SENDERS", PHONE1_META)
        for _ in range(5):
            service_mod.handle_connected_call(connected_params(),
                                              sender_phone_id=PHONE1_META)
        assert len(fake.rows(store_mod.DELIVERIES_TABLE)) == 3
        assert len(fake.rows(store_mod.OUTBOX_TABLE)) == 3

    def test_hangup_after_connected_schedules_nothing_more(self, fake, monkeypatch):
        """The brief: the connected event schedules the three deliveries; hangup must
        never schedule another copy."""
        monkeypatch.setenv("NOTIF_WA_VERIFIED_SENDERS", PHONE1_META)
        service_mod.handle_connected_call(connected_params(), sender_phone_id=PHONE1_META)
        before = dict(fake.rows(store_mod.OUTBOX_TABLE))
        service_mod.handle_connected_call(connected_params(DialAction="hangup"),
                                         sender_phone_id=PHONE1_META)
        assert fake.rows(store_mod.OUTBOX_TABLE) == before

    def test_an_outbound_call_notifies_the_customer_not_our_own_number(self, fake):
        result = service_mod.handle_connected_call(
            connected_params(Direction="outbound", From=BUSINESS_PSTN, To=CUSTOMER),
            sender_phone_id=PHONE1_META)
        assert result["claimed"] is True
        assert result["event"]["externalPartyLast4"] == CUSTOMER[-4:]
        event_row = list(fake.rows(store_mod.EVENTS_TABLE).values())[0]
        assert event_row["externalParty"] == CUSTOMER

    def test_describe_leaks_no_recipient_data(self, fake):
        described = service_mod.describe()
        assert described["claimVersion"] == "v2"
        assert set(described["channels"]) == {"whatsapp", "sms", "rcs"}
        assert CUSTOMER not in str(described)
        assert "UNVERIFIED" in described["metaTriggerNote"]

    def test_store_unavailable_propagates_for_a_retryable_5xx(self, fake):
        fake.transact_fail = FakeClientError("ProvisionedThroughputExceededException")
        with pytest.raises(store_mod.NotificationStoreUnavailable):
            service_mod.handle_connected_call(connected_params(),
                                              sender_phone_id=PHONE1_META)
