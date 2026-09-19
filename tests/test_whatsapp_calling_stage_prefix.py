"""Meta's WhatsApp webhook must reach the public branch, not the Admin auth gate.

The production outage this pins, measured 2026-09-19:

  Meta's app-level callback is https://api.wecare.digital/whatsapp, active, with
  `messages` and `calls` among 32 subscribed fields. The event arrives at the
  Lambda with path "/prod/whatsapp", because the custom domain mapping puts the
  stage in the path.

  The handler compared `normalized_path == '/whatsapp'`. "/prod/whatsapp" is not
  equal to it, so the public webhook branch was skipped and execution fell through
  to require_auth(required_role='Admin'), which answered 401.

  Evidence it was the routing and not the signature: `webhook_signature_rejected`
  appeared ZERO times in 12h while the function was invoked 541 times, so the
  signature branch was never reached at all.

  Consequence: 532 x 401 to Meta in 12 hours, and wecare-inbound-whatsapp received
  zero invocations for ~25 hours because nothing forwarded to it.

This is the same defect class already fixed in plivo-answer (ea570bcd). These
tests assert the stage-prefixed path routes identically to the bare one, in both
directions, so a third recurrence fails here.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

HANDLER = (ROOT / "amplify" / "functions" / "messaging" / "whatsapp-calling"
           / "handler.py")


@pytest.fixture
def wc(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    spec = importlib.util.spec_from_file_location("wc_stage_prefix", HANDLER)
    module = importlib.util.module_from_spec(spec)
    with pytest.MonkeyPatch.context() as mp:
        spec.loader.exec_module(module)
    return module


def _event(path, method="POST", body=None, stage="prod"):
    return {
        "requestContext": {
            "stage": stage,
            "apiId": "zllr9lrg7j",
            "domainName": "api.wecare.digital",
            "http": {"method": method, "path": path, "sourceIp": "31.13.115.1"},
        },
        "rawPath": path,
        "headers": {"x-hub-signature-256": "sha256=deadbeef"},
        "body": json.dumps(body if body is not None else {"object": "whatsapp_business_account"}),
    }


# --------------------------------------------------------------------------
# the routing fix
# --------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/whatsapp", "/prod/whatsapp"])
def test_meta_webhook_reaches_the_signature_check_not_the_auth_gate(wc, monkeypatch,
                                                                    path):
    """The 401 Meta received came from require_auth, never from the signature check.

    Asserting the SIGNATURE function is consulted proves the public branch was
    entered. Before the fix, "/prod/whatsapp" never got here.
    """
    consulted = []
    monkeypatch.setattr(wc, "_verify_webhook_signature",
                        lambda event, rid: consulted.append(True) or True)
    monkeypatch.setattr(wc, "_handle_webhook_event",
                        lambda payload, rid: {"statusCode": 200, "body": "{}"})
    monkeypatch.setattr(wc, "require_auth",
                        lambda *a, **k: pytest.fail(
                            "require_auth must NOT be reached for a Meta webhook"))

    response = wc.handler(_event(path), None)
    assert consulted == [True], "signature branch was not reached"
    assert response["statusCode"] == 200


@pytest.mark.parametrize("path", ["/whatsapp", "/prod/whatsapp"])
def test_get_verification_challenge_reaches_the_verifier(wc, monkeypatch, path):
    """Meta re-verifies the callback with GET. That must not hit the auth gate."""
    called = []
    monkeypatch.setattr(wc, "_verify_webhook", lambda qp, rid: called.append(True)
                        or {"statusCode": 200, "body": "CHALLENGE"})
    monkeypatch.setattr(wc, "require_auth",
                        lambda *a, **k: pytest.fail(
                            "require_auth must NOT be reached for GET verification"))
    wc.handler(_event(path, method="GET"), None)
    assert called == [True]


def test_a_bad_signature_is_still_rejected(wc, monkeypatch):
    """The fix must not turn the public route into an unauthenticated one."""
    monkeypatch.setattr(wc, "_verify_webhook_signature", lambda event, rid: False)
    monkeypatch.setattr(wc, "_handle_webhook_event",
                        lambda payload, rid: pytest.fail(
                            "must not process an unsigned webhook"))
    response = wc.handler(_event("/prod/whatsapp"), None)
    assert response["statusCode"] == 401


# --------------------------------------------------------------------------
# admin routes keep their auth
# --------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/whatsapp/config", "/prod/whatsapp/config"])
def test_admin_routes_still_require_auth(wc, monkeypatch, path):
    """Stripping the prefix must not accidentally expose the management routes."""
    denied = {"statusCode": 403, "body": '{"error":"forbidden"}'}
    monkeypatch.setattr(wc, "require_auth", lambda *a, **k: denied)
    response = wc.handler(_event(path, method="GET"), None)
    assert response is denied


# --------------------------------------------------------------------------
# the mechanism itself
# --------------------------------------------------------------------------
def test_stage_prefix_stripping_is_driven_by_the_stage_not_a_literal():
    """A hardcoded "prod" would reintroduce this on any second stage."""
    from lambda_utils.plivo_signature import normalize_path
    assert normalize_path({"rawPath": "/prod/whatsapp",
                           "requestContext": {"stage": "prod"}}) == "/whatsapp"
    assert normalize_path({"rawPath": "/staging/whatsapp",
                           "requestContext": {"stage": "staging"}}) == "/whatsapp"
    # no stage, or $default: leave the path alone
    assert normalize_path({"rawPath": "/whatsapp",
                           "requestContext": {"stage": "$default"}}) == "/whatsapp"
    assert normalize_path({"rawPath": "/whatsapp",
                           "requestContext": {}}) == "/whatsapp"


def test_the_handler_does_not_re_derive_the_stripping_logic():
    """Three copies of this logic is how the bug came back a second time."""
    source = HANDLER.read_text()
    assert "normalize_path" in source, "must reuse the tested shared helper"
