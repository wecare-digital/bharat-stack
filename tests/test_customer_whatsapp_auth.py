"""Tests for isolated customer Cognito -> WhatsApp OTP authentication."""
import importlib.util
import os
from pathlib import Path

import pytest


os.environ.setdefault("META_WABA_ID", "2094615664435155")
os.environ.setdefault("META_PHONE_NUMBER_ID", "1016149501586345")
os.environ.setdefault("OTP_TEMPLATE_NAME", "wecare_otp")
os.environ.setdefault("OTP_TEMPLATE_LANGUAGE", "en")

HANDLER = (
    Path(__file__).resolve().parents[1]
    / "amplify/functions/auth/customer-whatsapp-auth/handler.py"
)
_spec = importlib.util.spec_from_file_location(
    "customer_whatsapp_auth_under_test", HANDLER
)
auth = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(auth)


def _event(trigger, request=None):
    return {
        "triggerSource": trigger,
        "request": request or {},
        "response": {},
    }


def test_initial_challenge_requests_custom_challenge():
    event = _event("DefineAuthChallenge_Authentication", {"session": []})
    result = auth.handler(event, None)
    assert result["response"] == {
        "issueTokens": False,
        "failAuthentication": False,
        "challengeName": "CUSTOM_CHALLENGE",
    }


def test_successful_challenge_issues_tokens():
    event = _event(
        "DefineAuthChallenge_Authentication",
        {
            "session": [{
                "challengeName": "CUSTOM_CHALLENGE",
                "challengeResult": True,
            }]
        },
    )
    result = auth.handler(event, None)
    assert result["response"]["issueTokens"] is True
    assert result["response"]["failAuthentication"] is False


def test_three_failed_challenges_fail_authentication():
    event = _event(
        "DefineAuthChallenge_Authentication",
        {
            "session": [
                {
                    "challengeName": "CUSTOM_CHALLENGE",
                    "challengeResult": False,
                }
                for _ in range(3)
            ]
        },
    )
    result = auth.handler(event, None)
    assert result["response"]["issueTokens"] is False
    assert result["response"]["failAuthentication"] is True


def test_unknown_user_does_not_send_whatsapp(monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "_send_otp", lambda *args: sent.append(args))
    event = _event(
        "CreateAuthChallenge_Authentication",
        {
            "userNotFound": True,
            "userAttributes": {},
        },
    )
    result = auth.handler(event, None)
    assert sent == []
    assert (
        result["response"]["publicChallengeParameters"]["destination"]
        == "********"
    )


def test_cross_waba_user_is_rejected_before_send(monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "_send_otp", lambda *args: sent.append(args))
    event = _event(
        "CreateAuthChallenge_Authentication",
        {
            "userAttributes": {
                "phone_number": "+919876543210",
                "custom:partner_waba_id": "wrong-waba",
            }
        },
    )
    with pytest.raises(PermissionError):
        auth.handler(event, None)
    assert sent == []


def test_correct_waba_sends_six_digit_otp(monkeypatch):
    sent = []
    monkeypatch.setattr(
        auth,
        "_send_otp",
        lambda phone, otp: sent.append((phone, otp)),
    )
    # Within budget: let the send proceed. The throttle itself is exercised below.
    monkeypatch.setattr(auth, "_consume_send_budget", lambda digits: None)
    event = _event(
        "CreateAuthChallenge_Authentication",
        {
            "userAttributes": {
                "phone_number": "+919876543210",
                "custom:partner_waba_id": "2094615664435155",
            }
        },
    )
    result = auth.handler(event, None)

    assert len(sent) == 1
    phone, otp = sent[0]
    assert phone == "+919876543210"
    assert otp.isdigit() and len(otp) == 6
    assert (
        result["response"]["privateChallengeParameters"]["answer"]
        == otp
    )
    assert (
        result["response"]["publicChallengeParameters"]["destination"]
        == "********3210"
    )


def test_verify_accepts_correct_unexpired_code(monkeypatch):
    monkeypatch.setattr(auth.time, "time", lambda: 1_000)
    event = _event(
        "VerifyAuthChallengeResponse_Authentication",
        {
            "privateChallengeParameters": {
                "answer": "123456",
                "expiresAt": "1100",
            },
            "challengeAnswer": "123456",
        },
    )
    assert auth.handler(event, None)["response"]["answerCorrect"] is True


@pytest.mark.parametrize(
    ("answer", "expires_at"),
    [("654321", "1100"), ("123456", "999")],
)
def test_verify_rejects_wrong_or_expired_code(
    monkeypatch, answer, expires_at
):
    monkeypatch.setattr(auth.time, "time", lambda: 1_000)
    event = _event(
        "VerifyAuthChallengeResponse_Authentication",
        {
            "privateChallengeParameters": {
                "answer": "123456",
                "expiresAt": expires_at,
            },
            "challengeAnswer": answer,
        },
    )
    assert auth.handler(event, None)["response"]["answerCorrect"] is False


def test_sender_payload_uses_approved_authentication_template(monkeypatch):
    calls = []

    class _Payload:
        def read(self):
            return b'{"statusCode": 200}'

    class _Lambda:
        def invoke(self, **kwargs):
            calls.append(kwargs)
            return {"StatusCode": 200, "Payload": _Payload()}

    monkeypatch.setattr(auth, "_lambda", _Lambda())
    auth._send_otp("+919876543210", "123456")

    import json

    event = json.loads(calls[0]["Payload"].decode("utf-8"))
    body = json.loads(event["body"])

    assert calls[0]["FunctionName"] == "wecare-whatsapp-business-api:live"
    assert event["path"] == "/wa-business/messages/send/template"
    assert body["phoneId"] == "1016149501586345"
    assert body["templateName"] == "wecare_otp"
    assert body["language"] == "en"
    assert body["components"][0]["parameters"][0]["text"] == "123456"
    # `url`, not `copy_code`. This asserted copy_code and was wrong against the live
    # WABA: wecare_otp is an AUTHENTICATION template whose copy-code affordance Meta
    # materialises as a real URL button (.../otp/code/?...&code=otp{{1}}), so the OTP is
    # a text substitution into that URL. Sending copy_code with a coupon_code parameter
    # is refused outright:
    #   (#132018) buttons: Button at index 0 must be of type Url
    # which surfaces to the caller only as "sender returned HTTP 400". Confirmed by a
    # live round trip 2026-09-25: copy_code fails, url succeeds.
    assert body["components"][1]["sub_type"] == "url"
    assert body["components"][1]["parameters"][0] == {"type": "text", "text": "123456"}


# ── send throttle (G5): a REGISTERED number is bounded, fail-closed ──────────────
#
# The gap this closes: the browser calls Cognito's public InitiateAuth directly
# (src/lib/customerAuth.ts), so before this a registered number had NO send limit and a
# loop drove unbounded WhatsApp messages to a real handset. The trigger is the one place
# that can bound the send regardless of how the flow was entered.

import sys as _sys  # noqa: E402

_sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
_sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402

SEND_TABLE = 'stack-wecare-digital-DownloadGrantsTable'


def _registered_event():
    return _event(
        "CreateAuthChallenge_Authentication",
        {"userAttributes": {"phone_number": "+919876543210",
                            "custom:partner_waba_id": "2094615664435155"}},
    )


def _wire_fake_table(monkeypatch):
    fake = FakeDynamo(keys={SEND_TABLE: 'grantId'})
    monkeypatch.setattr(auth, "_ddb", fake)
    return fake


def test_send_is_bounded_and_then_suppressed(monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "_send_otp", lambda phone, otp: sent.append((phone, otp)))
    monkeypatch.setattr(auth.time, "time", lambda: 1_700_000_000)
    _wire_fake_table(monkeypatch)

    # SEND_MAX_PER_WINDOW defaults to 5: the first five sends go, the sixth is suppressed.
    for _ in range(auth.SEND_MAX_PER_WINDOW):
        result = auth.handler(_registered_event(), None)
        # A code is always issued regardless, so the Cognito flow is unchanged.
        assert result["response"]["privateChallengeParameters"]["answer"].isdigit()
    assert len(sent) == auth.SEND_MAX_PER_WINDOW

    suppressed = auth.handler(_registered_event(), None)
    # No sixth message, but the response is indistinguishable from a normal issue.
    assert len(sent) == auth.SEND_MAX_PER_WINDOW
    assert suppressed["response"]["publicChallengeParameters"]["registered"] == "true"
    assert suppressed["response"]["privateChallengeParameters"]["answer"].isdigit()


def test_send_throttle_fails_closed_on_storage_error(monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "_send_otp", lambda phone, otp: sent.append((phone, otp)))
    monkeypatch.setattr(auth.time, "time", lambda: 1_700_000_000)
    fake = _wire_fake_table(monkeypatch)
    fake.arm_failure(SEND_TABLE, "update_item", FakeClientError("InternalServerError"))

    result = auth.handler(_registered_event(), None)
    # Fail closed: the message is NOT sent when the counter cannot be read.
    assert sent == []
    # But the challenge is still issued, so the flow does not break.
    assert result["response"]["privateChallengeParameters"]["answer"].isdigit()


def test_send_budget_resets_after_the_window(monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "_send_otp", lambda phone, otp: sent.append((phone, otp)))
    _wire_fake_table(monkeypatch)

    base = 1_700_000_000
    monkeypatch.setattr(auth.time, "time", lambda: base)
    for _ in range(auth.SEND_MAX_PER_WINDOW):
        auth.handler(_registered_event(), None)
    # Sixth in-window is suppressed.
    auth.handler(_registered_event(), None)
    assert len(sent) == auth.SEND_MAX_PER_WINDOW

    # Past the window, the counter resets and a send goes again.
    monkeypatch.setattr(auth.time, "time", lambda: base + auth.SEND_WINDOW_SECONDS + 1)
    auth.handler(_registered_event(), None)
    assert len(sent) == auth.SEND_MAX_PER_WINDOW + 1
