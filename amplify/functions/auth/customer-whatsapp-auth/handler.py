"""Cognito CUSTOM_AUTH challenge delivered through WhatsApp.

This function is deliberately isolated from the normal outbound messaging Lambda.
It generates/verifies Cognito custom challenges and invokes the existing
wecare-whatsapp-business-api:live Lambda only for Meta template delivery.

Security invariants:
- never log the OTP or the complete destination phone number
- never read/store Meta credentials here
- fail closed if the user's tenant WABA does not match the configured WABA
- customer users are provisioned administratively; public self-sign-up stays off
"""

from __future__ import annotations

import json
import os
import secrets
import time

import boto3


_lambda = None


def _lambda_client():
    """Create the AWS client lazily so imports/tests never need AWS config."""
    global _lambda
    if _lambda is None:
        _lambda = boto3.client(
            "lambda",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return _lambda

SENDER_FUNCTION = os.environ.get(
    "SENDER_FUNCTION", "wecare-whatsapp-business-api:live"
)
META_WABA_ID = os.environ["META_WABA_ID"]
META_PHONE_NUMBER_ID = os.environ["META_PHONE_NUMBER_ID"]
TEMPLATE_NAME = os.environ.get("OTP_TEMPLATE_NAME", "wecare_otp")
TEMPLATE_LANGUAGE = os.environ.get("OTP_TEMPLATE_LANGUAGE", "en")
OTP_TTL_SECONDS = int(os.environ.get("OTP_TTL_SECONDS", "600"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "3"))


def _normalise_phone(phone: str) -> str:
    """Return WhatsApp's digits-only E.164 destination."""
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 10 and digits[:1] in "6789":
        digits = "91" + digits
    if not 10 <= len(digits) <= 15:
        raise ValueError("invalid E.164 phone number")
    return digits


def _mask_phone(phone: str) -> str:
    digits = _normalise_phone(phone)
    return ("*" * max(0, len(digits) - 4)) + digits[-4:]


def _send_otp(phone: str, otp: str) -> None:
    """Invoke the existing Meta Graph sender through its internal Lambda path."""
    body = {
        "to": _normalise_phone(phone),
        "phoneId": META_PHONE_NUMBER_ID,
        "templateName": TEMPLATE_NAME,
        "language": TEMPLATE_LANGUAGE,
        "components": [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": otp}],
            },
            {
                "type": "button",
                "sub_type": "copy_code",
                "index": "0",
                "parameters": [
                    {"type": "coupon_code", "coupon_code": otp}
                ],
            },
        ],
    }
    event = {
        "httpMethod": "POST",
        "path": "/wa-business/messages/send/template",
        "body": json.dumps(body),
    }
    response = _lambda_client().invoke(
        FunctionName=SENDER_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(event).encode("utf-8"),
    )
    raw = response["Payload"].read()
    result = json.loads(raw.decode("utf-8")) if raw else {}

    if response.get("FunctionError"):
        raise RuntimeError("internal WhatsApp sender Lambda failed")
    status = int(result.get("statusCode") or 500)
    if status >= 300:
        raise RuntimeError(
            f"internal WhatsApp sender returned HTTP {status}"
        )


def _define_auth_challenge(event: dict) -> dict:
    session = event.get("request", {}).get("session") or []
    attempts = [
        item
        for item in session
        if item.get("challengeName") == "CUSTOM_CHALLENGE"
    ]

    if attempts and attempts[-1].get("challengeResult") is True:
        event["response"]["issueTokens"] = True
        event["response"]["failAuthentication"] = False
    elif len(attempts) >= MAX_ATTEMPTS:
        event["response"]["issueTokens"] = False
        event["response"]["failAuthentication"] = True
    else:
        event["response"]["issueTokens"] = False
        event["response"]["failAuthentication"] = False
        event["response"]["challengeName"] = "CUSTOM_CHALLENGE"
    return event


def _create_auth_challenge(event: dict) -> dict:
    request = event.get("request", {})
    attributes = request.get("userAttributes") or {}

    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    expires_at = int(time.time()) + OTP_TTL_SECONDS

    event["response"]["privateChallengeParameters"] = {
        "answer": otp,
        "expiresAt": str(expires_at),
    }
    event["response"]["challengeMetadata"] = "WHATSAPP_OTP"
    event["response"]["publicChallengeParameters"] = {
        "deliveryMedium": "WHATSAPP",
        "expiresInSeconds": str(OTP_TTL_SECONDS),
    }

    # PreventUserExistenceErrors can present a synthetic unknown-user event.
    # Do not send a message in that case.
    if bool(request.get("userNotFound")):
        event["response"]["publicChallengeParameters"]["destination"] = "********"
        return event

    user_waba = attributes.get("custom:partner_waba_id")
    if user_waba != META_WABA_ID:
        raise PermissionError("customer user is not scoped to configured WABA")

    phone = attributes.get("phone_number")
    if not phone:
        raise ValueError("customer user has no phone_number attribute")

    event["response"]["publicChallengeParameters"]["destination"] = _mask_phone(
        phone
    )
    _send_otp(phone, otp)

    # Metadata only. Do not log the OTP or unmasked number.
    print(
        json.dumps(
            {
                "event": "customer_whatsapp_otp_sent",
                "wabaId": META_WABA_ID,
                "template": TEMPLATE_NAME,
            }
        )
    )
    return event


def _verify_auth_challenge(event: dict) -> dict:
    request = event.get("request", {})
    private = request.get("privateChallengeParameters") or {}
    expected = str(private.get("answer") or "")
    expires_at = int(private.get("expiresAt") or "0")
    supplied = str(request.get("challengeAnswer") or "")

    event["response"]["answerCorrect"] = bool(
        not bool(request.get("userNotFound"))
        and expected
        and time.time() <= expires_at
        and secrets.compare_digest(expected, supplied)
    )
    return event


def handler(event: dict, context) -> dict:
    trigger = event.get("triggerSource", "")
    if trigger.startswith("DefineAuthChallenge_"):
        return _define_auth_challenge(event)
    if trigger.startswith("CreateAuthChallenge_"):
        return _create_auth_challenge(event)
    if trigger.startswith("VerifyAuthChallengeResponse_"):
        return _verify_auth_challenge(event)
    raise ValueError(f"unsupported Cognito trigger: {trigger}")
