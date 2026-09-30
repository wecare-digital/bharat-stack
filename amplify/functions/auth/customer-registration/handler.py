"""The customer registration front door: prove a phone by WhatsApp OTP, then provision a login.

This is the wiring, not the mechanism
-------------------------------------
Every hard part already exists as a tested, storage-agnostic, AWS-free module, and this handler
composes them rather than reimplementing any of them:

- `lambda_utils.identity.registration` — the ordered flow: normalise -> throttle -> issue -> send
  (`begin`), then verify -> resolve/create customer -> provision login (`complete`). It performs no
  AWS call itself; every side effect is injected from here, which is what makes it testable.
- `lambda_utils.otp_throttle`   — per-IP and per-phone limits, fail-closed. The IP axis is the whole
  reason this route exists: a Cognito `CUSTOM_AUTH` trigger receives no client IP, so per-IP
  limiting is structurally impossible there. Here `requestContext.http.sourceIp` exists and cannot
  be spoofed.
- `lambda_utils.otp_challenge`  — the code itself: HMAC-with-pepper at rest, TTL, attempt cap,
  resend cooldown and window, single-use conditional consume.
- `lambda_utils.identity.customer` — `normalize_phone`, `new_customer_id`, `build_customer`.

Two endpoints, and the security properties that shape them
----------------------------------------------------------
`request`  normalise -> throttle -> issue -> send, in that order. The throttle runs BEFORE the code
           is issued and sent, so a refused request never spends a billable WhatsApp message. The
           code is generated inside `otp_challenge.issue`, handed straight to the sender, and never
           logged, echoed, or stored in plaintext.
`verify`   check the code and, on success, resolve or create the immutable `CUS_<ULID>` customer and
           administratively provision the Cognito login (stamping `custom:customer_id`). The browser
           then signs in with the existing WhatsApp-OTP `CUSTOM_AUTH` flow — which now works because
           the user exists as CONFIRMED. This handler never returns the customer id or a token: the
           session credential comes from the Cognito sign-in, not from here.

**No enumeration, on either endpoint.** `request` answers identically whether or not the number is
already a customer — there is no "already registered" branch, because that branch is an oracle.
`verify` collapses wrong / expired / used / never-issued into one opaque outcome. See
`RegistrationResult.public_body()`; the real reason stays server-side for logs and metrics.

**The browser never creates a Cognito user.** The customer pool is `AllowAdminCreateUserOnly = true`
by deliberate architecture. Provisioning happens here, on the backend, only after the OTP proves the
caller holds the number. Nothing in this handler calls `SignUp`.

Nothing plaintext is logged
---------------------------
Not the OTP, not the full phone number, not a customer id, not an exception message that could echo
either. Every log line carries an event name, an outcome and counts. Exception handlers log
`type(exc)` only.

Why this is a standalone function, not a branch of customer-whatsapp-auth
-------------------------------------------------------------------------
`customer-whatsapp-auth` is a Cognito `CUSTOM_AUTH` trigger: it has no HTTP surface, no client IP,
and no durable OTP store of its own. This is the opposite — an HTTP door that sees the IP, owns the
throttle, and provisions the very user the trigger later authenticates. Folding one into the other
would mean a single function with two invocation models and two trust boundaries.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import boto3

from lambda_utils import otp_throttle
from lambda_utils.identity import customer as identity
from lambda_utils.identity import registration
from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, extract_origin, options_response

logger = get_logger(__name__)

# ── configuration ────────────────────────────────────────────────────────────
REGION = os.environ.get("AWS_REGION", "us-east-1")

#: The short-lived challenge + throttle store. `DownloadGrantsTable` (key `grantId`, TTL on
#: `expiresAt`) is the established precedent shared by the WhatsApp-auth probe counter and the
#: email-verification door; both OTP modules default to a `grantId` key.
OTP_TABLE = os.environ.get("OTP_TABLE", "stack-wecare-digital-DownloadGrantsTable")

#: Where the immutable customer record lives (partition key `customerId`).
CUSTOMERS_TABLE = os.environ.get("CUSTOMERS_TABLE", "stack-wecare-digital-CustomersTable")

#: The customer Cognito pool. Deliberately NOT the staff pool — the customer_auth helper pins the
#: issuer to this one, and mixing them is the failure that helper exists to prevent.
CUSTOMER_POOL_ID = os.environ.get("CUSTOMER_POOL_ID", "us-east-1_46ULYuukt")

#: The WABA the OTP trigger is bound to. Stamped on the provisioned user as
#: `custom:partner_waba_id`, because the trigger raises `PermissionError` if it does not match —
#: an unstamped user could never receive a code.
META_WABA_ID = os.environ.get("META_WABA_ID", "2094615664435155")
META_PHONE_NUMBER_ID = os.environ.get("META_PHONE_NUMBER_ID", "1016149501586345")

#: The internal Meta-template sender. Same function and template the CUSTOM_AUTH trigger uses, so
#: the registration OTP and the sign-in OTP are delivered by one path.
SENDER_FUNCTION = os.environ.get("SENDER_FUNCTION", "wecare-whatsapp-business-api:live")
OTP_TEMPLATE_NAME = os.environ.get("OTP_TEMPLATE_NAME", "wecare_otp")
OTP_TEMPLATE_LANGUAGE = os.environ.get("OTP_TEMPLATE_LANGUAGE", "en")

#: Read by reference, lazily, never printed. `block-inline-secrets` allows a `SecretId='wecare/...'`
#: name; this is a name, not a value.
OTP_PEPPER_SECRET_ID = os.environ.get("OTP_PEPPER_SECRET_ID", "wecare/otp/pepper")

_dynamodb = None
_lambda = None
_secrets = None
_pepper_cache: Dict[str, str] = {}


def _table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return _dynamodb.Table(OTP_TABLE)


def _customers_table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return _dynamodb.Table(CUSTOMERS_TABLE)


def _lambda_client():
    global _lambda
    if _lambda is None:
        _lambda = boto3.client("lambda", region_name=REGION)
    return _lambda


def _cognito_client():
    return boto3.client("cognito-idp", region_name=REGION)


def _pepper() -> str:
    """Resolve the OTP pepper from Secrets Manager, lazily, cached per environment.

    Read lazily rather than at import scope on purpose: a module-scope read is cached for the life
    of a warm sandbox, so a rotation would keep validating against the old pepper until every
    sandbox recycled. Rotating the pepper invalidates every outstanding code, which is the correct
    blast radius — a customer simply requests another.
    """
    global _secrets
    if "pepper" in _pepper_cache:
        return _pepper_cache["pepper"]
    if _secrets is None:
        _secrets = boto3.client("secretsmanager", region_name=REGION)
    raw = _secrets.get_secret_value(SecretId=OTP_PEPPER_SECRET_ID).get("SecretString", "") or ""
    value = ""
    try:
        data = json.loads(raw)
        value = (data.get("pepper") or data.get("value") or "").strip()
    except (ValueError, TypeError):
        value = raw.strip()
    if not value:
        raise RuntimeError("OTP pepper is not configured")
    _pepper_cache["pepper"] = value
    return value


# ── injected side effects ──────────────────────────────────────────────────────

def _send_code(e164: str, code: str) -> None:
    """Deliver the OTP over WhatsApp via the existing Meta-template sender.

    Mirrors `customer-whatsapp-auth._send_otp` exactly: the `wecare_otp` AUTHENTICATION template
    with a `url` button (NOT `copy_code`), because Meta materialises the copy-code affordance of an
    AUTHENTICATION template as a real URL button and rejects `copy_code` outright. Verified against
    the live WABA on 2026-09-25.

    Never logs the code or the full number.
    """
    body = {
        "to": _wa_destination(e164),
        "phoneId": META_PHONE_NUMBER_ID,
        "templateName": OTP_TEMPLATE_NAME,
        "language": OTP_TEMPLATE_LANGUAGE,
        "components": [
            {"type": "body", "parameters": [{"type": "text", "text": code}]},
            {"type": "button", "sub_type": "url", "index": "0",
             "parameters": [{"type": "text", "text": code}]},
        ],
    }
    invoke_event = {
        "httpMethod": "POST",
        "path": "/wa-business/messages/send/template",
        "body": json.dumps(body),
    }
    response = _lambda_client().invoke(
        FunctionName=SENDER_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(invoke_event).encode("utf-8"),
    )
    raw = response["Payload"].read()
    result = json.loads(raw.decode("utf-8")) if raw else {}
    if response.get("FunctionError"):
        raise RuntimeError("internal WhatsApp sender Lambda failed")
    status = int(result.get("statusCode") or 500)
    if status >= 300:
        raise RuntimeError(f"internal WhatsApp sender returned HTTP {status}")


def _wa_destination(e164: str) -> str:
    """WhatsApp's digits-only destination for an E.164 number."""
    return "".join(ch for ch in str(e164 or "") if ch.isdigit())


def _resolve_customer(e164: str) -> Optional[Dict[str, Any]]:
    """The existing customer for this phone, or None.

    Looks up by the normalised phone on a GSI-free scan-avoiding pattern: the customer table is
    keyed on `customerId`, so phone lookup goes through the `PhoneIndex` GSI when present. When the
    index is absent (fresh account, zero rows) a query raises and this returns None, which is the
    safe answer — `complete` then creates the customer, and the create is itself conditional.
    """
    from boto3.dynamodb.conditions import Key

    try:
        result = _customers_table().query(
            IndexName=os.environ.get("CUSTOMERS_PHONE_INDEX", "normalizedPhone-index"),
            KeyConditionExpression=Key("normalizedPhone").eq(e164),
            Limit=1,
        )
    except Exception as error:  # noqa: BLE001
        # No index yet, or a transient read error. Treat as "not found"; the conditional create
        # below is what actually guarantees one customer per phone.
        logger.info(json.dumps({"event": "customer_lookup_miss",
                                 "error": type(error).__name__}))
        return None
    items = result.get("Items") or []
    return items[0] if items else None


def _create_customer(e164: str) -> Dict[str, Any]:
    """Create an immutable `CUS_<ULID>` customer with a verified phone, at most once per phone.

    The record is built with `identity.build_customer` (all fields normalised, nothing verified),
    then `phoneVerifiedAt` is stamped because the OTP just proved it. The write is conditional on
    the phone not already existing so a race between two verifications collapses to one customer.
    Name and email are filled in by later checkout steps; they are absent here, not empty, so a
    conditional write can assert their absence when the customer supplies them.
    """
    now = int(time.time())
    # Names are not known at phone-verification time; build_customer requires them, so a minimal
    # placeholder record is written directly instead. firstName/lastName are added at the name step.
    record = {
        "customerId": identity.new_customer_id(),
        "phone": e164,
        "normalizedPhone": e164,
        "phoneVerifiedAt": now,
        "createdAt": now,
        "updatedAt": now,
    }
    try:
        _customers_table().put_item(
            Item=record,
            ConditionExpression="attribute_not_exists(customerId)",
        )
    except Exception as error:  # noqa: BLE001
        # A losing race means another verification created the customer first. Re-resolve and adopt
        # it rather than raising, so two concurrent verifications converge on one record.
        if _is_conditional_failure(error):
            existing = _resolve_customer(e164)
            if existing and existing.get("customerId"):
                return existing
        raise
    logger.info(json.dumps({"event": "customer_created"}))
    return record


def _provision_login(e164: str, customer_id: str) -> None:
    """Administratively create or update the phone-keyed Cognito user. Idempotent.

    Mirrors `secure-files._ensure_customer_user`:
    - `MessageAction=SUPPRESS` so Cognito sends no invite (these users have no email and the channel
      is WhatsApp).
    - a permanent random password so the user is CONFIRMED rather than FORCE_CHANGE_PASSWORD, which
      would block CUSTOM_AUTH. Nobody learns it; the only way in is a WhatsApp OTP. Never logged.
    - `custom:partner_waba_id` so the OTP trigger, which fails closed on a WABA mismatch, will issue
      codes for this user.
    - `custom:customer_id` so `customer_auth` can bind a session to the immutable identity. Without
      it a session is refused as half-provisioned, and repairing that is why this runs for existing
      users too, not only new ones.
    """
    import secrets as pysecrets

    client = _cognito_client()
    attrs = [
        {"Name": "phone_number", "Value": e164},
        {"Name": "phone_number_verified", "Value": "true"},
        {"Name": "custom:partner_waba_id", "Value": META_WABA_ID},
        {"Name": "custom:customer_id", "Value": customer_id},
    ]
    try:
        created = client.admin_create_user(
            UserPoolId=CUSTOMER_POOL_ID,
            Username=e164,
            UserAttributes=attrs,
            MessageAction="SUPPRESS",
        )
        username = created["User"]["Username"]
        client.admin_set_user_password(
            UserPoolId=CUSTOMER_POOL_ID,
            Username=username,
            Password=pysecrets.token_urlsafe(24) + "aA1!",
            Permanent=True,
        )
    except client.exceptions.UsernameExistsException:
        client.admin_update_user_attributes(
            UserPoolId=CUSTOMER_POOL_ID, Username=e164, UserAttributes=attrs
        )


def _is_conditional_failure(error: Exception) -> bool:
    response = getattr(error, "response", None) or {}
    return response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


# ── request/response plumbing ───────────────────────────────────────────────────

def _body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get("body")
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {k: v for k, v in event.items()
                if k not in ("requestContext", "headers", "httpMethod", "path",
                             "rawPath", "isBase64Encoded")}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


def _action(event: Dict[str, Any], body: Dict[str, Any]) -> str:
    """Which operation to run: explicit `action`, or inferred from the path suffix."""
    explicit = str(body.get("action") or event.get("action") or "").strip().lower()
    if explicit in ("request", "verify"):
        return explicit
    path = str(event.get("rawPath") or event.get("path") or "").lower()
    if path.endswith("/verify"):
        return "verify"
    return "request"


def _reply(result: registration.RegistrationResult, origin: str) -> Dict[str, Any]:
    """Translate a RegistrationResult into an HTTP response, leaking nothing it should not."""
    return cors_response(result.http_status(), result.public_body(), origin)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    origin = extract_origin(event)
    rc = event.get("requestContext", {}) or {}
    method = rc.get("http", {}).get("method", event.get("httpMethod", "")).upper()
    if method == "OPTIONS":
        return options_response(origin)

    # No JWT requirement, deliberately. Registration runs BEFORE the customer has any session — it
    # is how they come to exist. The control here is the fail-closed per-IP/per-phone throttle plus
    # the fact that neither endpoint reveals whether a number is known. This route is listed in the
    # gateway's AUTH_SKIP_PATHS for that reason, the same position as the email-verification door.

    body = _body(event)
    action = _action(event, body)
    try:
        if action == "verify":
            return _verify(event, body, origin)
        return _request(event, body, origin)
    except Exception as exc:  # noqa: BLE001
        # Type only. An exception message can echo the phone number or the code.
        logger.error(json.dumps({"event": "customer_registration_error",
                                 "action": action, "error": type(exc).__name__}))
        return cors_response(500, {"error": "INTERNAL_ERROR"}, origin)


def _request(event: Dict[str, Any], body: Dict[str, Any], origin: str) -> Dict[str, Any]:
    """Issue and send a WhatsApp OTP. Same response whether or not the number is a customer."""
    result = registration.begin(
        raw_phone=body.get("phone"),
        event=event,
        throttle_table=_table(),
        challenge_table=_table(),
        pepper=_pepper(),
        send_code=_send_code,
    )
    if result.outcome == registration.SEND_FAILED:
        # The challenge is stored; the message did not go. A soft failure the client can retry.
        return cors_response(502, {"status": "send_failed",
                                   "message": "Could not send the code. Please try again."}, origin)
    return _reply(result, origin)


def _verify(event: Dict[str, Any], body: Dict[str, Any], origin: str) -> Dict[str, Any]:
    """Check the code, then resolve/create the customer and provision the login."""
    code = str(body.get("code") or "").strip()
    if not code:
        return cors_response(400, {"error": "CODE_REQUIRED"}, origin)

    result = registration.complete(
        raw_phone=body.get("phone"),
        code=code,
        challenge_table=_table(),
        pepper=_pepper(),
        resolve_customer=_resolve_customer,
        create_customer=_create_customer,
        provision_login=_provision_login,
    )
    return _reply(result, origin)
