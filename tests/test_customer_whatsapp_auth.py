"""Tests for isolated customer Cognito -> WhatsApp OTP authentication."""
import importlib.util
import os
from pathlib import Path

import pytest


os.environ.setdefault("META_WABA_ID", "2513394156072604")
os.environ.setdefault("META_PHONE_NUMBER_ID", "1055232054343117")
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
    event = _event(
        "CreateAuthChallenge_Authentication",
        {
            "userAttributes": {
                "phone_number": "+919876543210",
                "custom:partner_waba_id": "2513394156072604",
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
            return b'{"statusCode": 200, "body": "{\"success\": true}"}'

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
    assert body["phoneId"] == "1055232054343117"
    assert body["templateName"] == "wecare_otp"
    assert body["language"] == "en"
    assert body["components"][0]["parameters"][0]["text"] == "123456"
    assert body["components"][1]["sub_type"] == "copy_code"
