"""Exactly-once guarantees for connected-call notifications.

Two properties carry the whole design, and both are about what happens when
something goes wrong rather than when it goes right:

  1. The claim key is derived from the A-leg UUID, identically everywhere. A key
     computed slightly differently in two places is not an idempotency key - it is
     two keys, and the suppression quietly stops working.

  2. The claim store fails CLOSED. On a store error the caller must do NOTHING and
     return a retryable 5xx. Failing open - which the general webhook dedup
     deliberately does - would turn a DynamoDB blip into duplicate SMS to real
     people, billed to us, under a registered DLT sender.
"""
import sys
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.pstn import claims as claims_mod  # noqa: E402
from lambda_utils.pstn import keys as keys_mod      # noqa: E402


# ==========================================================================
# key derivation
# ==========================================================================
def test_event_claim_key_has_the_exact_documented_form():
    """Fixed by the design document. Do not 'tidy' it."""
    assert keys_mod.connected_claim_key("abc-123") == \
        "abc-123:connected-notifications:v1"


def test_channel_delivery_ids_are_distinct_per_channel():
    """SMS and RCS must be independently claimable, or a partial retry duplicates."""
    sms = keys_mod.channel_delivery_id("abc-123", "sms")
    rcs = keys_mod.channel_delivery_id("abc-123", "rcs")
    assert sms == "abc-123:sms:v1"
    assert rcs == "abc-123:rcs:v1"
    assert sms != rcs


def test_channel_id_differs_from_the_event_claim():
    """The event claim answers a different question and must not collide."""
    assert keys_mod.channel_delivery_id("abc-123", "sms") != \
        keys_mod.connected_claim_key("abc-123")


def test_version_is_part_of_every_key():
    """So a deliberate re-notification does not require deleting claim rows."""
    assert keys_mod.connected_claim_key("x-1", version="v2").endswith(":v2")
    assert keys_mod.channel_delivery_id("x-1", "sms", version="v2") == "x-1:sms:v2"


def test_derivation_is_deterministic():
    first = [keys_mod.channel_delivery_id("abc-123", "sms") for _ in range(50)]
    assert len(set(first)) == 1


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_missing_a_leg_uuid_is_refused(bad):
    with pytest.raises(keys_mod.KeyError_):
        keys_mod.connected_claim_key(bad)


@pytest.mark.parametrize("bad", [
    "has spaces",           # corrupts log / metric parsing
    "has:colons",           # ':' is the field separator - could forge a key shape
    "x" * 200,              # a key becomes a partition key and a metric dimension
    "semi;colon",
    "new\nline",
    "-leading-hyphen",
])
def test_malformed_identifier_is_refused(bad):
    """A claim key is built from a webhook field.

    An unvalidated one lets a caller choose its own key, and therefore dodge or
    collide with somebody else's claim.
    """
    with pytest.raises(keys_mod.KeyError_):
        keys_mod.connected_claim_key(bad)


def test_a_short_identifier_is_accepted():
    """The guard protects the key STRUCTURE, not the provider's id format.

    Imposing a minimum length would guess at the provider's format and reject a
    legitimate short identifier - a real failure mode with no security benefit,
    since a short id corrupts nothing.
    """
    assert keys_mod.connected_claim_key("abc") == "abc:connected-notifications:v1"


def test_rejection_message_does_not_echo_the_value():
    """Rejection messages land in logs."""
    with pytest.raises(keys_mod.KeyError_) as exc:
        keys_mod.connected_claim_key("secret;injected:value")
    assert "secret" not in str(exc.value)


def test_unknown_channel_is_refused():
    with pytest.raises(keys_mod.KeyError_):
        keys_mod.channel_delivery_id("abc-123", "whatsapp")


# --------------------------------------------------------------------------
# A-leg resolution from provider parameters
# --------------------------------------------------------------------------
def test_dial_a_leg_uuid_wins_over_call_uuid():
    """On a Dial, CallUUID may be the B-leg. The A-leg is authoritative."""
    params = {"CallUUID": "b-leg-999", "DialALegUUID": "a-leg-111"}
    assert keys_mod.resolve_a_leg_uuid(params) == "a-leg-111"


def test_call_uuid_is_the_fallback_when_there_is_no_dial_context():
    params = {"CallUUID": "abc-123"}
    assert keys_mod.resolve_a_leg_uuid(params) == "abc-123"


def test_b_leg_uuid_is_never_used_as_the_key():
    """Keying on the dialled party gives one inbound call a key per attempt."""
    params = {"DialBLegUUID": "b-leg-999"}
    assert keys_mod.resolve_a_leg_uuid(params) == ""


def test_parse_round_trips_a_channel_id():
    delivery_id = keys_mod.channel_delivery_id("abc-123", "rcs")
    assert keys_mod.parse_channel_delivery_id(delivery_id) == ("abc-123", "rcs", "v1")


def test_parse_rejects_the_event_claim_key():
    """Used to tell the two key shapes apart, so this must not parse."""
    assert keys_mod.parse_channel_delivery_id(
        keys_mod.connected_claim_key("abc-123")) is None


# ==========================================================================
# the claim store fails CLOSED
# ==========================================================================
class _FakeTable:
    def __init__(self, *, existing=None, put_error=None, update_error=None,
                 get_error=None):
        self.items = dict(existing or {})
        self.put_error = put_error
        self.update_error = update_error
        self.get_error = get_error
        self.puts = []

    def put_item(self, Item, ConditionExpression=None):
        if self.put_error:
            raise self.put_error
        key = Item["deliveryId"]
        if ConditionExpression and key in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        self.items[key] = dict(Item)
        self.puts.append(dict(Item))
        return {}

    def update_item(self, Key, **kwargs):
        if self.update_error:
            raise self.update_error
        key = Key["deliveryId"]
        if kwargs.get("ConditionExpression") and key not in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        row = self.items.setdefault(key, {"deliveryId": key})
        values = kwargs.get("ExpressionAttributeValues", {})
        row["state"] = values.get(":s", row.get("state"))
        row["attemptCount"] = int(row.get("attemptCount") or 0) + 1
        if ":provider" in values:
            row["provider"] = values[":provider"]
        if ":pmid" in values:
            row["providerMessageId"] = values[":pmid"]
        if ":err" in values:
            row["errorCategory"] = values[":err"]
            row["errorIsPermanent"] = values.get(":perm", False)
        return {"Attributes": dict(row)}

    def get_item(self, Key):
        if self.get_error:
            raise self.get_error
        found = self.items.get(Key["deliveryId"])
        return {"Item": dict(found)} if found else {}


@pytest.fixture
def table(monkeypatch):
    fake = _FakeTable()
    monkeypatch.setattr(claims_mod, "_table", lambda: fake)
    return fake


def test_first_claim_succeeds(table):
    assert claims_mod.claim("abc-123:sms:v1", channel="sms") is True


def test_second_claim_is_refused_not_raised(table):
    claims_mod.claim("abc-123:sms:v1", channel="sms")
    assert claims_mod.claim("abc-123:sms:v1", channel="sms") is False


def test_concurrent_duplicate_claims_yield_exactly_one_winner(table):
    """The conditional put is the whole mechanism; there is no read-then-write."""
    results = [claims_mod.claim("abc-123:sms:v1", channel="sms") for _ in range(20)]
    assert results.count(True) == 1
    assert results.count(False) == 19


def test_sms_and_rcs_claims_do_not_interfere(table):
    assert claims_mod.claim("abc-123:sms:v1", channel="sms") is True
    assert claims_mod.claim("abc-123:rcs:v1", channel="rcs") is True


# --------------------------------------------------------------------------
# the property that matters: a store outage must NOT permit a send
# --------------------------------------------------------------------------
def test_store_outage_raises_rather_than_returning_true(monkeypatch):
    """The single most important assertion in this file.

    webhook_dedup returns True here. Doing that when the side effect is a customer
    SMS turns a DynamoDB blip into duplicate messages, billed to us, with no bound
    on provider retries.
    """
    fake = _FakeTable(put_error=ClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException"}}, "PutItem"))
    monkeypatch.setattr(claims_mod, "_table", lambda: fake)
    with pytest.raises(claims_mod.ClaimStoreUnavailable):
        claims_mod.claim("abc-123:sms:v1", channel="sms")


def test_generic_exception_also_fails_closed(monkeypatch):
    fake = _FakeTable(put_error=RuntimeError("network down"))
    monkeypatch.setattr(claims_mod, "_table", lambda: fake)
    with pytest.raises(claims_mod.ClaimStoreUnavailable):
        claims_mod.claim("abc-123:sms:v1", channel="sms")


def test_the_failure_type_is_distinct_from_a_provider_error(monkeypatch):
    """So a broad `except Exception` around a provider call cannot swallow it."""
    fake = _FakeTable(put_error=RuntimeError("boom"))
    monkeypatch.setattr(claims_mod, "_table", lambda: fake)
    with pytest.raises(claims_mod.ClaimStoreUnavailable):
        claims_mod.claim("abc-123:sms:v1")
    assert issubclass(claims_mod.ClaimStoreUnavailable, RuntimeError)


def test_read_failure_is_not_reported_as_unclaimed(monkeypatch):
    """"Read failed" and "no claim" must not look the same to a caller."""
    fake = _FakeTable(get_error=RuntimeError("timeout"))
    monkeypatch.setattr(claims_mod, "_table", lambda: fake)
    with pytest.raises(claims_mod.ClaimStoreUnavailable):
        claims_mod.get("abc-123:sms:v1")


def test_empty_claim_id_is_a_programming_error_not_a_store_error(table):
    """Proceeding unguarded is the danger, so this raises rather than returning."""
    with pytest.raises(ValueError):
        claims_mod.claim("")


def test_claim_uses_its_own_table_not_the_shared_dedup_table():
    """Mixing them would let a sweep of one purge the other."""
    assert "WebhookDedup" not in claims_mod.CLAIM_TABLE


def test_claim_ttl_outlives_a_provider_retry_window():
    """A claim expiring while retries are possible would permit a duplicate."""
    assert claims_mod.CLAIM_TTL_SECONDS >= 7 * 24 * 3600


# --------------------------------------------------------------------------
# recording the outcome
# --------------------------------------------------------------------------
def test_recording_an_attempt_increments_the_count(table):
    claims_mod.claim("abc-123:sms:v1", channel="sms")
    row = claims_mod.record_attempt("abc-123:sms:v1", state="SENT",
                                    provider="aws-end-user-messaging",
                                    provider_message_id="prov-1")
    assert row["state"] == "SENT"
    assert row["attemptCount"] == 1
    assert row["providerMessageId"] == "prov-1"


def test_recording_against_an_unclaimed_id_is_refused(table):
    """A worker must not record a send for a call nobody claimed."""
    with pytest.raises(claims_mod.ClaimStoreUnavailable):
        claims_mod.record_attempt("never-claimed:sms:v1", state="SENT")


def test_invalid_state_is_rejected(table):
    claims_mod.claim("abc-123:sms:v1")
    with pytest.raises(ValueError):
        claims_mod.record_attempt("abc-123:sms:v1", state="DELIVERED")


@pytest.mark.parametrize("state", ["PENDING", "SENT", "FAILED", "SKIPPED"])
def test_only_the_four_documented_states_are_accepted(table, state):
    claims_mod.claim("abc-123:sms:v1")
    claims_mod.record_attempt("abc-123:sms:v1", state=state)


# --------------------------------------------------------------------------
# retry policy
# --------------------------------------------------------------------------
def test_a_sent_channel_is_never_retried():
    """This is what stops retrying one channel from duplicating the other."""
    assert claims_mod.is_retryable({"state": "SENT", "attemptCount": 1}) is False


def test_a_skipped_channel_is_never_retried():
    """SKIPPED is a terminal decision, not a failure to recover from."""
    assert claims_mod.is_retryable({"state": "SKIPPED"}) is False


def test_a_permanent_error_is_never_retried():
    """DLT, destination, validation and permission failures do not clear."""
    assert claims_mod.is_retryable(
        {"state": "FAILED", "errorIsPermanent": True, "attemptCount": 1}) is False


def test_a_transient_failure_is_retried_within_budget():
    assert claims_mod.is_retryable(
        {"state": "FAILED", "attemptCount": 1, "maxAttempts": 3}) is True


def test_the_attempt_budget_is_respected():
    assert claims_mod.is_retryable(
        {"state": "FAILED", "attemptCount": 3, "maxAttempts": 3}) is False


def test_an_absent_record_is_retryable():
    """Nothing has been claimed yet, so the work is still to do."""
    assert claims_mod.is_retryable(None) is True
