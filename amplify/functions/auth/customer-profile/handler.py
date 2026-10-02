"""Authenticated checkout profile -> Workspace Contacts.

The customer's phone and customer id come only from customer_auth.require_customer(event).
The browser may submit first/last name, email, and a short-lived email verification proof. The
proof is bound to the normalized email by the public email-verification Lambda and stored in the
shared OTP table. This endpoint validates that proof server-side before any CRM write.

No marketing consent is inferred from making a purchase. New rows default opt-in/allowlist fields
to False; an existing contact's explicit choices are preserved.
"""

from __future__ import annotations

import hmac
import json
import os
import time
import uuid
from hashlib import sha256
from typing import Any, Dict, Optional

import boto3
from boto3.dynamodb.conditions import Key

from lambda_utils import contact_key, customer_auth, customer_session
from lambda_utils.identity import customer as identity
from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, extract_origin, options_response
from lambda_utils.validation import sanitize_html

logger = get_logger(__name__)

REGION = os.environ.get("AWS_REGION", "us-east-1")
OTP_TABLE = os.environ.get("OTP_TABLE", "stack-wecare-digital-DownloadGrantsTable")
CONTACTS_TABLE = os.environ.get("CONTACTS_TABLE", "stack-wecare-digital-ContactsTable")
OTP_PEPPER_SECRET_ID = os.environ.get("OTP_PEPPER_SECRET_ID", "wecare/otp/pepper")

PROOF_PURPOSE = "email_verification_proof"
PROOF_PREFIX = "email-proof#"
CUSTOMER_TAG = "Customer"

_dynamodb = None
_secrets = None
_pepper_cache: Dict[str, str] = {}


def _no_store(response: Dict[str, Any]) -> Dict[str, Any]:
    hardened = dict(response)
    hardened["headers"] = customer_session.harden_session_headers(response.get("headers") or {})
    return hardened


def _table(name: str):
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return _dynamodb.Table(name)


def _pepper() -> str:
    global _secrets
    if "pepper" in _pepper_cache:
        return _pepper_cache["pepper"]
    if _secrets is None:
        _secrets = boto3.client("secretsmanager", region_name=REGION)
    raw = _secrets.get_secret_value(SecretId=OTP_PEPPER_SECRET_ID).get("SecretString", "") or ""
    try:
        parsed = json.loads(raw)
        value = str(parsed.get("pepper") or parsed.get("value") or "").strip()
    except (ValueError, TypeError):
        value = raw.strip()
    if not value:
        raise RuntimeError("OTP pepper is not configured")
    _pepper_cache["pepper"] = value
    return value


def _proof_digest(email: str) -> str:
    return hmac.new(
        _pepper().encode("utf-8"),
        ("email-proof\x1f" + email).encode("utf-8"),
        sha256,
    ).hexdigest()


def _proof_valid(proof_id: Any, email: str) -> bool:
    proof = str(proof_id or "").strip()
    if not proof or len(proof) > 128:
        return False
    item = _table(OTP_TABLE).get_item(
        Key={"grantId": PROOF_PREFIX + proof}
    ).get("Item") or {}
    if item.get("purpose") != PROOF_PURPOSE:
        return False
    if int(item.get("expiresAt") or 0) < int(time.time()):
        return False
    stored = str(item.get("subjectDigest") or "")
    wanted = _proof_digest(email)
    return bool(stored) and hmac.compare_digest(stored, wanted)


def _body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get("body")
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _active_match(index: str, field: str, value: str) -> Optional[Dict[str, Any]]:
    result = _table(CONTACTS_TABLE).query(
        IndexName=index,
        KeyConditionExpression=Key(field).eq(value),
        Limit=5,
    )
    for item in result.get("Items") or []:
        if item.get("deletedAt") is None:
            return item
    return None


def _merge_tags(existing: Any) -> list[str]:
    values = existing if isinstance(existing, list) else []
    out = [str(value).strip() for value in values if str(value).strip()]
    if CUSTOMER_TAG.lower() not in {value.lower() for value in out}:
        out.append(CUSTOMER_TAG)
    return out


def _upsert_contact(*, customer_id: str, phone: str, email: str,
                    first_name: str, last_name: str) -> Dict[str, Any]:
    phone_match = _active_match("phone-index", "phone", phone)
    email_match = _active_match("email-index", "email", email)
    phone_id = contact_key.resolve(phone_match) if phone_match else ""
    email_id = contact_key.resolve(email_match) if email_match else ""
    if phone_id and email_id and phone_id != email_id:
        raise ValueError("CONTACT_IDENTITY_CONFLICT")

    now = int(time.time())
    name = f"{first_name} {last_name}".strip()
    existing = phone_match or email_match
    table = _table(CONTACTS_TABLE)

    if existing:
        contact_id = contact_key.resolve(existing)
        table.update_item(
            Key={"id": contact_id},
            UpdateExpression=(
                "SET #name=:name, firstName=:first, lastName=:last, phone=:phone, email=:email, "
                "tags=:tags, checkoutCustomerId=:customer, "
                "phoneVerifiedAt=if_not_exists(phoneVerifiedAt,:now), "
                "emailVerifiedAt=:now, checkoutProfileUpdatedAt=:now, updatedAt=:now"
            ),
            ExpressionAttributeNames={"#name": "name"},
            ExpressionAttributeValues={
                ":name": name,
                ":first": first_name,
                ":last": last_name,
                ":phone": phone,
                ":email": email,
                ":tags": _merge_tags(existing.get("tags")),
                ":customer": customer_id,
                ":now": now,
            },
        )
        return {"contactId": contact_id, "created": False}

    # One signed-in customer converges onto one deterministic CRM id when no prior phone/email row exists.
    contact_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"wecare:checkout-customer:{customer_id}"))
    item = {
        **contact_key.contact_item_keys(contact_id),
        "name": name,
        "firstName": first_name,
        "lastName": last_name,
        "phone": phone,
        "email": email,
        "tags": [CUSTOMER_TAG],
        "checkoutCustomerId": customer_id,
        "phoneVerifiedAt": now,
        "emailVerifiedAt": now,
        "checkoutProfileUpdatedAt": now,
        # Purchase/transactional identity is not marketing consent.
        "optInWhatsApp": False,
        "optInEmail": False,
        "optInSms": False,
        "allowlistWhatsApp": False,
        "allowlistEmail": False,
        "allowlistSms": False,
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
        return {"contactId": contact_id, "created": True}
    except Exception as exc:  # noqa: BLE001
        response = getattr(exc, "response", None) or {}
        if response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        table.update_item(
            Key={"id": contact_id},
            UpdateExpression=(
                "SET #name=:name, firstName=:first, lastName=:last, phone=:phone, email=:email, "
                "emailVerifiedAt=:now, phoneVerifiedAt=if_not_exists(phoneVerifiedAt,:now), "
                "checkoutProfileUpdatedAt=:now, updatedAt=:now"
            ),
            ExpressionAttributeNames={"#name": "name"},
            ExpressionAttributeValues={
                ":name": name, ":first": first_name, ":last": last_name,
                ":phone": phone, ":email": email, ":now": now,
            },
        )
        return {"contactId": contact_id, "created": False}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    origin = extract_origin(event)
    rc = event.get("requestContext", {}) or {}
    method = rc.get("http", {}).get("method", event.get("httpMethod", "")).upper()
    if method == "OPTIONS":
        return _no_store(options_response(origin))
    if method != "POST":
        return _no_store(cors_response(405, {"error": "METHOD_NOT_ALLOWED"}, origin))

    identity_session, denied = customer_auth.require_customer(event)
    if denied:
        return _no_store(denied)

    body = _body(event)
    allowed = {"firstName", "lastName", "email", "emailProof"}
    if set(body) - allowed:
        return _no_store(cors_response(400, {"error": "UNEXPECTED_FIELD"}, origin))

    first_name = sanitize_html(body.get("firstName"), max_length=100).strip()
    last_name = sanitize_html(body.get("lastName"), max_length=100).strip()
    if not first_name or not last_name:
        return _no_store(cors_response(400, {"error": "NAME_REQUIRED"}, origin))

    try:
        email = identity.normalize_email(body.get("email"))
        phone = identity.normalize_phone_preserving_country(identity_session.phone)
    except identity.InvalidEmailAddress:
        return _no_store(cors_response(400, {"error": "INVALID_EMAIL"}, origin))
    except identity.InvalidPhoneNumber:
        return _no_store(cors_response(400, {"error": "INVALID_SESSION_PHONE"}, origin))

    try:
        if not _proof_valid(body.get("emailProof"), email):
            return _no_store(cors_response(400, {"error": "EMAIL_VERIFICATION_REQUIRED"}, origin))
        result = _upsert_contact(
            customer_id=identity_session.customer_id,
            phone=phone,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
    except ValueError as exc:
        if str(exc) == "CONTACT_IDENTITY_CONFLICT":
            return _no_store(cors_response(409, {"error": "CONTACT_IDENTITY_CONFLICT"}, origin))
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(json.dumps({"event": "customer_profile_error", "error": type(exc).__name__}))
        return _no_store(cors_response(500, {"error": "INTERNAL_ERROR"}, origin))

    logger.info(json.dumps({"event": "checkout_customer_profile_saved",
                            "created": bool(result.get("created"))}))
    return _no_store(cors_response(200, {
        "status": "PROFILE_READY",
        "contactId": result["contactId"],
        "name": f"{first_name} {last_name}".strip(),
        "email": email,
        "phone": phone,
    }, origin))
