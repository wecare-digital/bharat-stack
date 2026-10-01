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

# Probe limiting for the unregistered-number reveal.
#
# Telling a caller `registered: "false"` is a usability decision that makes this
# endpoint enumerable - someone holding a list of numbers could learn which are
# customers. The answer is NOT to go back to silence, which stranded real people on a
# code screen no code would ever satisfy. It is to make bulk probing expensive.
#
# Counted per number, in DynamoDB with a TTL, because that is the only shared state a
# Cognito trigger has - the trigger receives no source IP, so IP-based limiting is not
# available here. Per-number is the right axis anyway: it directly bounds how fast one
# number can be tested, and an attacker enumerating a list gains nothing from spreading
# across numbers because each one still has to come back here.
PROBE_TABLE = os.environ.get("OTP_PROBE_TABLE", "stack-wecare-digital-DownloadGrantsTable")
PROBE_WINDOW_SECONDS = int(os.environ.get("OTP_PROBE_WINDOW_SECONDS", "3600"))
PROBE_MAX_PER_WINDOW = int(os.environ.get("OTP_PROBE_MAX_PER_WINDOW", "5"))

# Send throttle for REGISTERED numbers — the G5 fix.
#
# The probe counter above only runs on the userNotFound branch, so a *registered* number
# had no send limit at all: because the browser calls Cognito's public InitiateAuth
# directly (src/lib/customerAuth.ts), an attacker could loop it and drive unbounded
# WhatsApp messages to a real customer's handset. This counter bounds that.
#
# It is deliberately SEPARATE from the probe counter and fails in the OPPOSITE direction.
# The probe counter fails OPEN (a DynamoDB blip must not lock a customer out of files).
# This one fails CLOSED: it guards a path that sends a message and spends money to a real
# handset, so an unreadable counter must refuse the send. Same table, distinct key prefix.
#
# Per-phone only. A Cognito trigger event carries no client IP, so per-IP limiting is
# structurally impossible here — that axis belongs at an HTTP front door
# (lambda_utils.otp_throttle). Per-phone is the axis that protects the *person* whose
# handset would ring, and it is the one this trigger can enforce regardless of entry path.
SEND_TABLE = os.environ.get("OTP_SEND_TABLE", PROBE_TABLE)
SEND_WINDOW_SECONDS = int(os.environ.get("OTP_SEND_WINDOW_SECONDS", "3600"))
SEND_MAX_PER_WINDOW = int(os.environ.get("OTP_SEND_MAX_PER_WINDOW", "5"))

_ddb = None


class OtpSendThrottled(RuntimeError):
    """Too many OTP sends to this number in the window. Fails the challenge closed."""


def _probe_table():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
    return _ddb.Table(PROBE_TABLE)


def _probe_budget_exhausted(phone_digits: str) -> bool:
    """Whether this number has been probed too often lately.

    Fails OPEN on any error. A counter that cannot be read must not be able to lock a
    paying customer out of their own files; the worst case of failing open is that the
    enumeration budget is not enforced during a DynamoDB problem, which is a far
    smaller harm than refusing legitimate verification.
    """
    now = int(time.time())
    try:
        table = _probe_table()
        # Reuses the grants table with a distinct key prefix rather than standing up a
        # table for a counter. Same TTL attribute, so expiry is already handled.
        result = table.update_item(
            Key={"grantId": f"otpprobe#{phone_digits}"},
            UpdateExpression="ADD probes :one SET expiresAt = if_not_exists(expiresAt, :exp)",
            ExpressionAttributeValues={":one": 1, ":exp": now + PROBE_WINDOW_SECONDS},
            ReturnValues="ALL_NEW",
        )
        count = int(result.get("Attributes", {}).get("probes") or 0)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"event": "otp_probe_check_failed", "error": type(exc).__name__}))
        return False
    return count > PROBE_MAX_PER_WINDOW


def _consume_send_budget(phone_digits: str) -> None:
    """Count one OTP send for this number, or raise `OtpSendThrottled` when over budget.

    Fails CLOSED: any storage error raises `OtpSendThrottled` too, because this guards a
    path that messages a real handset and an unreadable counter must refuse rather than
    send. That is the deliberate opposite of `_probe_budget_exhausted`, which fails open.

    A window that has rolled over resets, so a legitimate customer is not locked out for
    the rest of the hour — the counter bounds bursts, it does not permanently cap a number.
    """
    now = int(time.time())
    try:
        result = _probe_table().update_item(  # same DownloadGrantsTable, distinct key
            Key={"grantId": f"otpsend#{phone_digits}"},
            UpdateExpression=(
                "ADD sends :one "
                "SET windowStartedAt = if_not_exists(windowStartedAt, :now), "
                "expiresAt = if_not_exists(expiresAt, :exp)"
            ),
            ExpressionAttributeValues={
                ":one": 1, ":now": now, ":exp": now + SEND_WINDOW_SECONDS},
            ReturnValues="ALL_NEW",
        )
        attrs = result.get("Attributes", {})
        count = int(attrs.get("sends") or 0)
        started = int(attrs.get("windowStartedAt") or now)
    except Exception as exc:  # noqa: BLE001
        # Fail CLOSED — see the docstring. Refuse the send rather than risk flooding a handset.
        print(json.dumps({"event": "otp_send_budget_check_failed",
                          "error": type(exc).__name__}))
        raise OtpSendThrottled("send budget could not be verified") from exc

    if now - started >= SEND_WINDOW_SECONDS:
        # Window rolled over: reset to a fresh count of 1 rather than staying locked.
        try:
            _probe_table().put_item(Item={
                "grantId": f"otpsend#{phone_digits}", "sends": 1,
                "windowStartedAt": now, "expiresAt": now + SEND_WINDOW_SECONDS})
        except Exception as exc:  # noqa: BLE001
            raise OtpSendThrottled("send budget could not be rolled") from exc
        return

    if count > SEND_MAX_PER_WINDOW:
        print(json.dumps({"event": "otp_send_budget_exhausted", "sends": count}))
        raise OtpSendThrottled(f"{count} sends already in the current window")


def _normalise_phone(phone: str) -> str:
    """Return WhatsApp's digits-only E.164 destination, honouring the country code written.

    This duplicates `lambda_utils.identity.customer.normalize_phone_preserving_country`,
    which is the canonical implementation. The duplication is forced, not sloppy: this
    function is packaged `standalone=True` (`scripts/deploy_all_lambdas.py:174`, "handler.py
    only") and the deployed function has `Layers: null`, so it cannot import `lambda_utils`
    at all. Adding an import would break its live package. A drift-agreement test in
    `tests/test_phone_country_code_preservation.py` asserts the two agree on every row of one
    shared case table, modulo the `+`, which is the only thing keeping them in step.

    The defect being fixed here was independently written and is the same one: stripping to
    digits first made a ten-digit foreign number indistinguishable from an Indian mobile, so
    `91` was prepended to a complete number and the sign-in OTP for a Singapore customer
    would go to an unrelated Indian handset. The country-code decision therefore has to
    happen on the original text, before any digit strip - which is what the branch below does.

    Today every value reaching here is the Cognito `phone_number` attribute, which is always
    stored in E.164 with a leading `+`, so the strict marker requirement costs nothing.
    """
    text = str(phone or "").strip()
    # Separators only. The `+` and the `00` must survive this step - removing them first is
    # exactly the bug.
    #
    # `not ch.isspace()` rather than an explicit `" \t"` set, because the canonical
    # implementation compacts with `re.sub(r"[\s\-().]", "", text)` and `\s` matches every
    # codepoint for which `str.isspace()` is true - verified exhaustively across all
    # 0x110000 codepoints, zero disagreements. An explicit ASCII set would diverge on a
    # non-breaking space (U+00A0): the canonical function would keep it, see `rest` starting
    # with a literal space-then-zero and reject, while this copy would drop nothing and read
    # the leading zeros as part of the number. That divergence lands on the OTP destination,
    # so the two predicates have to be the same predicate, not two spellings that happen to
    # agree on the current test table.
    compact = "".join(ch for ch in text if not ch.isspace() and ch not in "-().")

    if compact.startswith("+"):
        rest = compact[1:]
    elif compact.startswith("00"):
        rest = compact[2:]
    else:
        raise ValueError("a country code is required; expected +<code> or 00<code>")

    if rest.startswith("0"):
        raise ValueError("a country code does not start with zero")

    # `ch in "0123456789"` rather than `ch.isdigit()`, and this is the same class of care the
    # separator comment above describes - applied to the second predicate.
    #
    # `str.isdigit()` is true for anything with Numeric_Type=Digit, which is a wider set than
    # the Nd-only class the canonical `re.sub(r"[^0-9]", ...)` strips: the two disagree on 128
    # codepoints, beginning with U+00B2 SUPERSCRIPT TWO and U+1369. Measured before this was
    # tightened: `+65\u00b291234567` gave the canonical function `6591234567` and this one
    # `65\u00b291234567`. The docstring promises a digits-only destination, and that value is
    # used as the `_consume_send_budget` key and as the WhatsApp send `to` field, so a
    # non-digit surviving here is a wrong throttle bucket and a malformed send target.
    #
    # An explicit ASCII membership test is exact against `[^0-9]` by construction rather than
    # by coincidence, and it needs no import - which keeps this file `standalone=True`.
    digits = "".join(ch for ch in rest if ch in "0123456789")
    # India only, exactly one zero. No other country gets trunk handling, because guessing
    # one per country is the same mistake in a new coat.
    if digits.startswith("91") and digits[2:3] == "0":
        digits = "91" + digits[3:]
    # 8..15 rather than the previous 10..15, to match the canonical implementation. A tighter
    # bound here than at the registration door would let a customer register successfully and
    # then be unable to sign in, which is the same class of harm being fixed.
    if not 8 <= len(digits) <= 15:
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
            # `url`, not `copy_code`.
            #
            # `wecare_otp` is an AUTHENTICATION template, and Meta materialises its
            # copy-code affordance as a real URL button:
            #   https://www.whatsapp.com/otp/code/?...&code=otp{{1}}
            # so the OTP is a text substitution into that URL, not a coupon code.
            #
            # Sending `sub_type: "copy_code"` with a `coupon_code` parameter is
            # rejected outright:
            #   (#132018) buttons: Button at index 0 must be of type Url
            # which surfaces here only as "sender returned HTTP 400". Verified
            # against the live WABA on 2026-09-25 - the round trip failed with
            # copy_code and succeeds with url.
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [{"type": "text", "text": otp}],
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
    #
    # `registered: "false"` is returned to the caller deliberately, and it is a
    # considered trade rather than an oversight.
    #
    # Hiding it makes this endpoint non-enumerable: a prober cannot learn which
    # numbers are customers. The cost is that a mistyped digit produces a code
    # screen and then total silence, with no way for the person to tell "wrong
    # number" from "message is slow" - and no code will ever arrive, so they wait
    # forever. That dead end was reached within a minute of the first real test.
    #
    # Revealing it is defensible HERE specifically because every recipient is
    # registered by hand by an operator, there is no self-sign-up, and the fact
    # being disclosed is only "this number is a customer" to someone who already
    # knows the number. That is a low-value disclosure against a high-frequency
    # usability failure.
    #
    # It does mean the endpoint is enumerable. If that becomes a concern, the fix
    # is a rate limit on this trigger keyed on source IP, not re-hiding the flag -
    # going back to silence would restore the dead end.
    if bool(request.get("userNotFound")):
        event["response"]["publicChallengeParameters"]["destination"] = "********"
        # Rate-limited, so the reveal cannot be used to sweep a list of numbers. Past
        # the budget the answer becomes indistinguishable from a registered number,
        # which is the same posture as before the reveal existed - but only for a
        # caller who has already probed this number five times in an hour, not for
        # someone who simply mistyped once.
        # `userName` is TOP-LEVEL on a Cognito trigger event, not inside `request`.
        # Reading it from `request` yielded an empty string, so the budget check was
        # skipped and eight consecutive probes all got the reveal.
        username = str(event.get("userName") or "")
        digits = "".join(ch for ch in username if ch.isdigit())
        if digits and _probe_budget_exhausted(digits):
            print(json.dumps({"event": "otp_probe_budget_exhausted"}))
            event["response"]["publicChallengeParameters"]["registered"] = "unknown"
        else:
            event["response"]["publicChallengeParameters"]["registered"] = "false"
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
    event["response"]["publicChallengeParameters"]["registered"] = "true"

    # Send throttle, per phone, fail-closed. This is the G5 fix: without it a registered
    # number had no send limit, so looping the browser's direct InitiateAuth call flooded a
    # real handset. Over budget, the challenge is still issued so the Cognito flow is
    # unchanged and the endpoint stays non-enumerable — the customer simply keeps using the
    # code they were already sent moments ago. Only the outbound MESSAGE is suppressed.
    digits = _normalise_phone(phone)
    try:
        _consume_send_budget(digits)
    except OtpSendThrottled:
        # No send. Do not reveal throttling to the caller — the public parameters are
        # identical to a normal issue, so this is invisible from outside and cannot be used
        # to probe the limit. The private challenge answer is still set, so a code the
        # customer already holds continues to verify.
        print(json.dumps({"event": "customer_whatsapp_otp_send_suppressed",
                          "reason": "send_budget"}))
        return event

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
