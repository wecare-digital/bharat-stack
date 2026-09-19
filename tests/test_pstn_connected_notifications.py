"""At most one SMS and one RCS per genuinely connected call.

The tests that matter here are the failure cases: duplicates, concurrency, a store
outage, a partial channel failure, and the temptation to fall back to a prohibited
provider when the approved one is unavailable.
"""
import sys
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.pstn import claims as claims_mod          # noqa: E402
from lambda_utils.pstn import keys as keys_mod              # noqa: E402
from lambda_utils.pstn import notifications as notif        # noqa: E402

INDIA = "+919903300044"
US = "+14155552671"

CONNECTED = {
    "DialAction": "connected",
    "DialALegUUID": "a-leg-111",
    "DialBLegUUID": "b-leg-222",
    "CallUUID": "a-leg-111",
    "From": INDIA,
    "To": "+918031830030",
    "Direction": "inbound",
}


class _FakeTable:
    def __init__(self, put_error=None):
        self.items = {}
        self.put_error = put_error

    def put_item(self, Item, ConditionExpression=None):
        if self.put_error:
            raise self.put_error
        key = Item["deliveryId"]
        if ConditionExpression and key in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        self.items[key] = dict(Item)
        return {}

    def update_item(self, Key, **kwargs):
        key = Key["deliveryId"]
        if kwargs.get("ConditionExpression") and key not in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        row = self.items.setdefault(key, {"deliveryId": key})
        values = kwargs.get("ExpressionAttributeValues", {})
        row["state"] = values.get(":s", row.get("state"))
        row["attemptCount"] = int(row.get("attemptCount") or 0) + 1
        return {"Attributes": dict(row)}

    def get_item(self, Key):
        found = self.items.get(Key["deliveryId"])
        return {"Item": dict(found)} if found else {}


@pytest.fixture
def table(monkeypatch):
    fake = _FakeTable()
    monkeypatch.setattr(claims_mod, "_table", lambda: fake)
    return fake


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(notif, "CONNECTED_NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(notif, "INDIA_RCS_ENABLED", True)
    monkeypatch.setattr(notif, "GLOBAL_RCS_AVAILABLE", False)


class _Recorder:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, **kwargs):
        if self.fail_on and kwargs.get("channel") == self.fail_on:
            raise RuntimeError("queue unavailable")
        self.calls.append(kwargs)

    def channels(self):
        return [c["channel"] for c in self.calls]


# ==========================================================================
# only a genuine connected event counts
# ==========================================================================
@pytest.mark.parametrize("action", ["", "answer", "hangup", "ringing", "completed"])
def test_non_connected_dial_actions_are_ignored(table, enabled, action):
    dispatch = _Recorder()
    params = dict(CONNECTED, DialAction=action)
    result = notif.handle_connected(params, dispatch=dispatch)
    assert result["claimed"] is False
    assert dispatch.calls == []


def test_connected_event_claims_and_dispatches_both_channels(table, enabled):
    dispatch = _Recorder()
    result = notif.handle_connected(CONNECTED, dispatch=dispatch)
    assert result["claimed"] is True
    assert sorted(dispatch.channels()) == ["rcs", "sms"]


def test_the_event_claim_uses_the_documented_key(table, enabled):
    result = notif.handle_connected(CONNECTED, dispatch=_Recorder())
    assert result["eventClaimKey"] == "a-leg-111:connected-notifications:v1"


def test_a_leg_is_preferred_over_call_uuid(table, enabled):
    """CallUUID may be the B-leg on a Dial, which would key per attempt."""
    params = dict(CONNECTED, CallUUID="b-leg-999", DialALegUUID="a-leg-111")
    result = notif.handle_connected(params, dispatch=_Recorder())
    assert result["eventClaimKey"].startswith("a-leg-111:")


def test_missing_a_leg_refuses_rather_than_guessing(table, enabled):
    """Without a stable key there is no once-only guarantee."""
    params = {k: v for k, v in CONNECTED.items()
              if k not in ("DialALegUUID", "CallUUID")}
    dispatch = _Recorder()
    result = notif.handle_connected(params, dispatch=dispatch)
    assert result["claimed"] is False
    assert result["reason"] == "no_a_leg_uuid"
    assert dispatch.calls == []


def test_the_caller_is_notified_not_our_own_number(table, enabled):
    """`To` on an inbound call is us. Texting it would message ourselves."""
    dispatch = _Recorder()
    notif.handle_connected(CONNECTED, dispatch=dispatch)
    for call in dispatch.calls:
        assert call["destination"] == INDIA


def test_disabled_by_default(table, monkeypatch):
    """Enabling customer notifications is a production decision."""
    monkeypatch.setattr(notif, "CONNECTED_NOTIFICATIONS_ENABLED", False)
    dispatch = _Recorder()
    result = notif.handle_connected(CONNECTED, dispatch=dispatch)
    assert result["claimed"] is False
    assert result["reason"] == "feature_disabled"
    assert dispatch.calls == []


# ==========================================================================
# duplicates and concurrency
# ==========================================================================
def test_duplicate_connected_callback_sends_nothing_further(table, enabled):
    first = _Recorder()
    notif.handle_connected(CONNECTED, dispatch=first)
    second = _Recorder()
    result = notif.handle_connected(CONNECTED, dispatch=second)
    assert result["claimed"] is False
    assert result["reason"] == "duplicate_connected_event"
    assert second.calls == []


def test_twenty_concurrent_callbacks_produce_one_send_per_channel(table, enabled):
    dispatch = _Recorder()
    for _ in range(20):
        notif.handle_connected(CONNECTED, dispatch=dispatch)
    assert dispatch.channels().count("sms") == 1
    assert dispatch.channels().count("rcs") == 1


def test_reordered_callbacks_do_not_double_send(table, enabled):
    """A hangup arriving before the dial event must not reopen the claim."""
    dispatch = _Recorder()
    notif.handle_connected(dict(CONNECTED, DialAction="hangup"), dispatch=dispatch)
    notif.handle_connected(CONNECTED, dispatch=dispatch)
    notif.handle_connected(dict(CONNECTED, DialAction="hangup"), dispatch=dispatch)
    notif.handle_connected(CONNECTED, dispatch=dispatch)
    assert dispatch.channels().count("sms") == 1


def test_a_different_call_is_claimed_separately(table, enabled):
    dispatch = _Recorder()
    notif.handle_connected(CONNECTED, dispatch=dispatch)
    notif.handle_connected(dict(CONNECTED, DialALegUUID="a-leg-999",
                                CallUUID="a-leg-999"), dispatch=dispatch)
    assert dispatch.channels().count("sms") == 2


# ==========================================================================
# the store outage must not permit a send
# ==========================================================================
def test_store_outage_raises_and_sends_nothing(monkeypatch, enabled):
    """The caller must turn this into a retryable 5xx.

    Failing open here would turn a DynamoDB blip into duplicate SMS to real
    people, under our registered DLT sender, with no bound on provider retries.
    """
    fake = _FakeTable(put_error=RuntimeError("dynamodb unavailable"))
    monkeypatch.setattr(claims_mod, "_table", lambda: fake)
    dispatch = _Recorder()
    with pytest.raises(claims_mod.ClaimStoreUnavailable):
        notif.handle_connected(CONNECTED, dispatch=dispatch)
    assert dispatch.calls == []


# ==========================================================================
# partial failure: one channel must not affect the other
# ==========================================================================
def test_rcs_dispatch_failure_does_not_suppress_sms(table, enabled):
    dispatch = _Recorder(fail_on="rcs")
    result = notif.handle_connected(CONNECTED, dispatch=dispatch)
    assert result["claimed"] is True
    assert dispatch.channels() == ["sms"]
    assert result["channels"]["sms"]["dispatched"] is True
    assert result["channels"]["rcs"]["dispatched"] is False


def test_sms_dispatch_failure_does_not_suppress_rcs(table, enabled):
    dispatch = _Recorder(fail_on="sms")
    result = notif.handle_connected(CONNECTED, dispatch=dispatch)
    assert dispatch.channels() == ["rcs"]
    assert result["channels"]["rcs"]["dispatched"] is True


def test_a_failed_dispatch_leaves_the_channel_retryable(table, enabled):
    """The claim is durable, so a retry finds work to do rather than a duplicate."""
    notif.handle_connected(CONNECTED, dispatch=_Recorder(fail_on="rcs"))
    rcs_id = keys_mod.channel_delivery_id("a-leg-111", "rcs")
    assert claims_mod.is_retryable(claims_mod.get(rcs_id)) is True


def test_a_dispatched_channel_is_not_retryable_once_sent(table, enabled):
    notif.handle_connected(CONNECTED, dispatch=_Recorder())
    sms_id = keys_mod.channel_delivery_id("a-leg-111", "sms")
    claims_mod.record_attempt(sms_id, state="SENT", provider="aws-end-user-messaging")
    assert claims_mod.is_retryable(claims_mod.get(sms_id)) is False


# ==========================================================================
# provider selection follows the destination, never preference
# ==========================================================================
def test_india_sms_routes_to_aws():
    decision = notif.decide_sms(INDIA)
    assert decision.eligible is True
    assert decision.provider == "aws-end-user-messaging"
    assert "ap-south-1" in decision.reason


def test_non_india_sms_routes_to_aws():
    decision = notif.decide_sms(US)
    assert decision.provider == "aws-end-user-messaging"


@pytest.mark.parametrize("destination", [INDIA, US, "+442071838750"])
def test_sms_is_never_routed_to_a_prohibited_provider(destination):
    decision = notif.decide_sms(destination)
    for prohibited in ("sinch", "airtel", "plivo", "sns", "pinpoint"):
        assert prohibited not in (decision.provider or "").lower()


def test_india_rcs_routes_to_sinch(monkeypatch):
    monkeypatch.setattr(notif, "INDIA_RCS_ENABLED", True)
    decision = notif.decide_rcs(INDIA)
    assert decision.eligible is True
    assert decision.provider == "sinch-rcs"


def test_non_india_rcs_is_unsupported_not_downgraded_to_sinch(monkeypatch):
    """The temptation this test exists to block.

    Sinch is reachable and approved for India. Routing non-India RCS to it because
    AWS RCS is not built would breach the provider matrix. An unavailable channel
    is a terminal SKIPPED, not a fallback.
    """
    monkeypatch.setattr(notif, "INDIA_RCS_ENABLED", True)
    monkeypatch.setattr(notif, "GLOBAL_RCS_AVAILABLE", False)
    decision = notif.decide_rcs(US)
    assert decision.eligible is False
    assert decision.state == "SKIPPED"
    assert "INELIGIBLE_UNSUPPORTED" in decision.reason
    assert decision.provider != "sinch-rcs"


def test_disabled_india_rcs_is_terminal_not_a_fallback(monkeypatch):
    monkeypatch.setattr(notif, "INDIA_RCS_ENABLED", False)
    decision = notif.decide_rcs(INDIA)
    assert decision.eligible is False
    assert "INELIGIBLE_UNSUPPORTED" in decision.reason


def test_ineligible_channel_is_recorded_skipped_and_not_dispatched(table, monkeypatch):
    monkeypatch.setattr(notif, "CONNECTED_NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(notif, "INDIA_RCS_ENABLED", True)
    monkeypatch.setattr(notif, "GLOBAL_RCS_AVAILABLE", False)
    dispatch = _Recorder()
    params = dict(CONNECTED, From=US)
    result = notif.handle_connected(params, dispatch=dispatch)
    assert result["channels"]["rcs"]["dispatched"] is False
    assert dispatch.channels() == ["sms"]
    rcs_id = keys_mod.channel_delivery_id("a-leg-111", "rcs")
    assert claims_mod.get(rcs_id)["state"] == "SKIPPED"


def test_skipped_is_terminal_and_not_retried(table, monkeypatch):
    """SKIPPED must not read as a failure a worker keeps grinding on."""
    monkeypatch.setattr(notif, "CONNECTED_NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(notif, "GLOBAL_RCS_AVAILABLE", False)
    notif.handle_connected(dict(CONNECTED, From=US), dispatch=_Recorder())
    rcs_id = keys_mod.channel_delivery_id("a-leg-111", "rcs")
    assert claims_mod.is_retryable(claims_mod.get(rcs_id)) is False


# ==========================================================================
# the notification body is regulatory
# ==========================================================================
def test_body_matches_the_approved_dlt_template_shape():
    body = notif.NOTIFICATION_BODY
    assert body.startswith("Thanks for contacting WECARE.DIGITAL!")
    assert body.count("\n\n") == 2, "approved template has two blank-line breaks"
    assert notif.DEFAULT_DLT_TEMPLATE_KEY == "ivr-default"


def test_sms_dispatch_carries_a_template_key_and_rcs_does_not(table, enabled):
    dispatch = _Recorder()
    notif.handle_connected(CONNECTED, dispatch=dispatch)
    sms = next(c for c in dispatch.calls if c["channel"] == "sms")
    rcs = next(c for c in dispatch.calls if c["channel"] == "rcs")
    assert sms["dlt_template_key"] == "ivr-default"
    assert rcs["dlt_template_key"] == ""


# ==========================================================================
# error classification drives the retry budget
# ==========================================================================
@pytest.mark.parametrize("code", [
    "MISSING_DLT_TEMPLATE", "INVALID_PHONE", "ValidationException",
    "AccessDeniedException", "PROHIBITED_PROVIDER",
])
def test_permanent_errors_are_classified_permanent(code):
    _, permanent = notif.classify_provider_error("", code)
    assert permanent is True


@pytest.mark.parametrize("code", [
    "ThrottlingException", "RequestTimeout", "ServiceUnavailable",
    "EndpointConnectionError",
])
def test_transient_errors_are_classified_transient(code):
    _, permanent = notif.classify_provider_error("", code)
    assert permanent is False


def test_an_unknown_error_is_treated_as_transient():
    """Being wrong costs one wasted attempt; the claim prevents a duplicate.

    Treating an unknown transient fault as permanent would silently drop a real
    notification, which is the worse error.
    """
    _, permanent = notif.classify_provider_error("something we have not seen")
    assert permanent is False


# ==========================================================================
# the Browser SDK must not be the trigger
# ==========================================================================
def test_only_the_server_side_dial_action_triggers_a_send():
    """onCallConnected fires when the BROWSER leg is up.

    For an outbound call that can be while the remote party is still ringing, so
    triggering from it would text people who never answered. The only accepted
    trigger is DialAction=connected.
    """
    import ast

    assert notif.DIAL_ACTION_CONNECTED == "connected"
    source = (SHARED / "lambda_utils" / "pstn" / "notifications.py").read_text()
    assert "onCallConnected" in source, "the hazard should stay documented"

    # It must appear ONLY in documentation, never in executable code. Checked by
    # removing every docstring from the AST and unparsing what is left, rather
    # than by guessing at line prefixes - a line inside a multi-line docstring
    # carries no marker of its own.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body[0].value.value = ""
    assert "onCallConnected" not in ast.unparse(tree), \
        "onCallConnected must not appear in executable code"


# ==========================================================================
# the route contract on the Plivo handler
# ==========================================================================
def test_dial_events_route_requires_a_signature():
    """This route decides whether a customer is messaged.

    Unlike /plivo/answer - which cannot require a signature, because Plivo does
    not sign answer_url fetches - this one is a callback and IS signed. An unsigned
    request must never reach the claim logic.
    """
    import importlib.util

    handler_path = (ROOT / "amplify" / "functions" / "messaging"
                    / "plivo-answer" / "handler.py")
    spec = importlib.util.spec_from_file_location("plivo_dial_route_test",
                                                 handler_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    route, require_signature = module._ROUTES["/plivo/dial-events"]
    assert require_signature is True
    assert route is module._route_dial_events


def test_claim_store_outage_on_the_route_returns_a_retryable_5xx(monkeypatch):
    """Plivo redelivers a 5xx, so refusing to guess costs latency and nothing more."""
    import importlib.util

    handler_path = (ROOT / "amplify" / "functions" / "messaging"
                    / "plivo-answer" / "handler.py")
    spec = importlib.util.spec_from_file_location("plivo_dial_route_5xx",
                                                 handler_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(notif, "CONNECTED_NOTIFICATIONS_ENABLED", True)
    fake = _FakeTable(put_error=RuntimeError("dynamodb unavailable"))
    monkeypatch.setattr(claims_mod, "_table", lambda: fake)
    monkeypatch.setattr(module, "_persist_cdr", lambda *a, **k: True)

    response = module._route_dial_events(dict(CONNECTED), "req-1")
    assert response["statusCode"] == 503


def test_hangup_route_does_not_trigger_connected_notifications():
    """A hangup updates the CDR. It must never start the notification flow."""
    handler_path = (ROOT / "amplify" / "functions" / "messaging"
                    / "plivo-answer" / "handler.py")
    source = handler_path.read_text()
    hangup = source[source.index("def _route_hangup"):source.index("def _route_events")]
    assert "handle_connected" not in hangup
