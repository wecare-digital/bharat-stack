"""Secure file sharing for wecare.digital/get/secure.

Three tiers exist on the ``wecare-digital-get`` bucket. This function owns the
gated one:

    o/       open, auto-download, served straight off CloudFront. Not our concern.
    secure/  this file. A named customer, verified by WhatsApp OTP, pays per
             download and receives a single-use short-lived presigned URL.

Why the object key is opaque
----------------------------
Every upload lands at::

    secure/wecare-digital-<uuid4hex>-<uuid4hex><ext>

The key deliberately carries no customer name, no original filename and no
sequence number, so it cannot be guessed and one customer's key reveals nothing
about another's. The consequence is that the key is meaningless to a human, which
is precisely why ``SecureFilesTable`` exists: it is the only place that maps an
opaque key back to a person and a readable name. That table, not the key, answers
"which of these many files belongs to which customer" - via the
``owner-created-index`` GSI, so listing one customer's files is a query rather
than a table scan.

The key being unguessable is a convenience, not the control. CloudFront refuses
the whole ``secure/`` prefix outright (see
``amplify/functions/edge/get-miss-redirect``), so these objects are reachable
only through a presigned URL this function issues after checking ownership and
payment.

Refusal is deliberately uniform
-------------------------------
A caller who is not the owner, and a caller asking for a ``fileId`` that does not
exist, get the byte-identical 403 ``NOT_REGISTERED`` response. Distinguishing them
would confirm that a given file exists, which is the one fact the opaque key is
meant to withhold.

Two authentication paths, deliberately not shared
-------------------------------------------------
Admin routes use ``lambda_utils.middleware.require_auth``, which validates against
the **admin** pool. Customer routes must not: ``require_auth`` hardcodes the admin
pool id, so a customer token would pass ``get_user`` and then silently fall
through to role ``Viewer`` when its group lookup found nothing. Customer auth is
``_customer_identity`` below.

Payment is built but switched off
---------------------------------
``SECURE_FILES_PAYMENT_ENABLED`` defaults to off. While off, order creation
refuses rather than contacting Razorpay, so no payment configuration is touched
and no credential is read. Enabling it is an owner action.
"""

from __future__ import annotations

import base64
import json
import os
import secrets as pysecrets
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from lambda_utils.logging import get_logger
from lambda_utils.middleware import require_auth
from lambda_utils.response import cors_response, extract_origin, options_response

logger = get_logger(__name__)

REGION = os.environ.get("AWS_REGION", "us-east-1")

BUCKET = os.environ.get("SECURE_FILES_BUCKET", "wecare-digital-get")

# Everything gated lives under secure/. The edge function denies that whole prefix,
# so both sub-prefixes below inherit the deny automatically.
SECURE_PREFIX = "secure/"
# u/ holds the original exactly as the operator uploaded it, whatever the type.
UPLOAD_PREFIX = SECURE_PREFIX + "u/"
# d/ holds the rendition that can actually be delivered over WhatsApp. Only PDF and
# images render as something a recipient can open inline; anything else has no d/
# object and falls back to a download link. Recording that at upload time beats
# discovering it at send time, when a customer is already waiting.
DELIVER_PREFIX = SECURE_PREFIX + "d/"

# Types WhatsApp recipients can open inline. Documents may be up to 100MB, images
# 5MB, which is why the two are distinguished rather than lumped together.
DELIVERABLE_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_BYTES = 100 * 1024 * 1024
FILES_TABLE = os.environ.get("SECURE_FILES_TABLE", "stack-wecare-digital-SecureFilesTable")
GRANTS_TABLE = os.environ.get("DOWNLOAD_GRANTS_TABLE", "stack-wecare-digital-DownloadGrantsTable")

# The customer pool, NOT the admin pool. Tokens must prove they came from here.
CUSTOMER_POOL_ID = os.environ.get("CUSTOMER_USER_POOL_ID", "us-east-1_46ULYuukt")
CUSTOMER_POOL_ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{CUSTOMER_POOL_ID}"
PARTNER_GROUP = os.environ.get("PARTNER_GROUP", "Partner")
# The OTP trigger refuses a user whose WABA scope does not match, so new users
# must be stamped with the same value the auth Lambda expects.
META_WABA_ID = os.environ.get("META_WABA_ID", "2094615664435155")

PRICE_PAISE = int(os.environ.get("SECURE_FILE_PRICE_PAISE", "4900"))  # Rs. 49
UPLOAD_URL_TTL = int(os.environ.get("UPLOAD_URL_TTL_SECONDS", "900"))
DOWNLOAD_URL_TTL = int(os.environ.get("DOWNLOAD_URL_TTL_SECONDS", "60"))
GRANT_TTL = int(os.environ.get("GRANT_TTL_SECONDS", "1800"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))

_s3 = None
_ddb = None
_cognito = None


def _s3_client():
    global _s3
    if _s3 is None:
        # SigV4 + regional endpoint, so presigned URLs are valid in this region.
        from botocore.client import Config

        _s3 = boto3.client(
            "s3",
            region_name=REGION,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
    return _s3


def _table(name: str):
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource("dynamodb", region_name=REGION)
    return _ddb.Table(name)


def _cognito_client():
    global _cognito
    if _cognito is None:
        _cognito = boto3.client("cognito-idp", region_name=REGION)
    return _cognito


def _payment_enabled() -> bool:
    """Read per call, not captured at import.

    A posture switch that only takes effect once every warm sandbox recycles is
    not much of a switch.
    """
    return str(os.environ.get("SECURE_FILES_PAYMENT_ENABLED", "")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# ── phone handling ────────────────────────────────────────────────────────────

def normalise_phone(raw: str) -> str:
    """Digits-only E.164, matching the OTP Lambda's own normalisation.

    A 10-digit Indian mobile is prefixed with 91 so that the number an admin types
    and the number Cognito holds cannot drift apart - if they did, the customer
    would authenticate successfully and then own nothing.
    """
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(digits) == 10 and digits[:1] in "6789":
        digits = "91" + digits
    if not 10 <= len(digits) <= 15:
        raise ValueError("invalid phone number")
    return digits


def mask_phone(raw: str) -> str:
    """Last four only. Never log a full number."""
    try:
        digits = normalise_phone(raw)
    except ValueError:
        return "****"
    return ("*" * max(0, len(digits) - 4)) + digits[-4:]


# ── identity ──────────────────────────────────────────────────────────────────

def _jwt_claims_unverified(token: str) -> Dict[str, Any]:
    """Decode a JWT payload WITHOUT verifying it.

    Safe only because every caller below has already had AWS verify the token via
    ``get_user``. Once that succeeds the token is known to be genuine and
    unmodified, so its claims can be trusted. Never call this on its own.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _bearer(event: Dict[str, Any]) -> str:
    headers = event.get("headers") or {}
    raw = headers.get("authorization") or headers.get("Authorization") or ""
    return raw[7:].strip() if raw[:7].lower() == "bearer " else raw.strip()


def _customer_identity(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve the calling customer, or None.

    ``get_user`` is pool-agnostic: it validates the access token's signature and
    expiry against whichever pool issued it. That alone is not authorisation - a
    token from the admin pool would also pass. So the issuer claim is checked
    afterwards, which is sound precisely because ``get_user`` has already proven
    the token unmodified.
    """
    token = _bearer(event)
    if not token:
        return None
    try:
        user = _cognito_client().get_user(AccessToken=token)
    except ClientError:
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(json.dumps({"event": "customer_auth_error", "error": type(exc).__name__}))
        return None

    if _jwt_claims_unverified(token).get("iss") != CUSTOMER_POOL_ISSUER:
        logger.warning(json.dumps({"event": "customer_auth_wrong_pool"}))
        return None

    attrs = {a["Name"]: a["Value"] for a in user.get("UserAttributes", [])}
    phone = attrs.get("phone_number", "")
    if not phone:
        return None
    try:
        return {"username": user.get("Username", ""), "phone": normalise_phone(phone)}
    except ValueError:
        return None


# ── responses ─────────────────────────────────────────────────────────────────

def _not_registered(origin: str) -> Dict[str, Any]:
    """The single refusal used for wrong-owner AND nonexistent-file.

    Byte-identical in both cases on purpose. Returning 404 for one and 403 for the
    other would let a caller probe which file ids exist.
    """
    return cors_response(
        403,
        {
            "error": "NOT_REGISTERED",
            "message": "This file is not registered to your number.",
        },
        origin,
    )


def _decimal_safe(obj: Any) -> Any:
    """DynamoDB hands back Decimal; JSON does not want it."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_safe(v) for v in obj]
    return obj


def _public_file(item: Dict[str, Any], *, admin: bool) -> Dict[str, Any]:
    """Shape a record for the client. The S3 key never leaves the backend."""
    out = {
        "fileId": item.get("fileId"),
        "displayName": item.get("displayName"),
        "originalFilename": item.get("originalFilename"),
        "contentType": item.get("contentType"),
        "sizeBytes": item.get("sizeBytes"),
        "pricePaise": item.get("pricePaise"),
        "status": item.get("status"),
        "createdAt": item.get("createdAt"),
        "downloadCount": item.get("downloadCount", 0),
        # "pdf" / "image" arrive as a WhatsApp attachment; "link" goes out as a URL.
        "deliverable": item.get("deliverable", "unknown"),
    }
    if admin:
        out["ownerName"] = item.get("ownerName")
        out["ownerPhoneMasked"] = mask_phone(item.get("ownerPhone", ""))
        out["uploadedBy"] = item.get("uploadedBy")
    return _decimal_safe(out)


# ── admin: create the customer and the upload slot ────────────────────────────

def _ensure_customer_user(phone: str, name: str) -> str:
    """Create or update the phone-keyed customer so WhatsApp OTP can reach them.

    Three details matter and each has a reason:

    * ``MessageAction='SUPPRESS'`` - Cognito must not send an invite. There is no
      email on these users and an SMS invite would both cost money and bypass the
      WhatsApp channel this flow is built on.
    * a permanent random password - ``admin_create_user`` leaves the user in
      ``FORCE_CHANGE_PASSWORD``, which blocks CUSTOM_AUTH. Setting a permanent
      password moves them to ``CONFIRMED``. Nobody ever learns it; the only way in
      is a WhatsApp OTP. It is generated here, used once, and never logged or
      returned - putting it in a log or a response would turn a passwordless
      design into a credential leak.
    * ``custom:partner_waba_id`` - the OTP trigger raises ``PermissionError`` if
      this does not match its configured WABA, so an unstamped user could never
      receive a code.
    """
    client = _cognito_client()
    e164 = "+" + phone
    attrs = [
        {"Name": "phone_number", "Value": e164},
        {"Name": "phone_number_verified", "Value": "true"},
        {"Name": "custom:partner_waba_id", "Value": META_WABA_ID},
    ]
    if name:
        attrs.append({"Name": "name", "Value": name[:128]})

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
        username = e164
        client.admin_update_user_attributes(
            UserPoolId=CUSTOMER_POOL_ID, Username=username, UserAttributes=attrs
        )

    try:
        client.admin_add_user_to_group(
            UserPoolId=CUSTOMER_POOL_ID, Username=username, GroupName=PARTNER_GROUP
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            json.dumps({"event": "customer_group_add_failed", "error": type(exc).__name__})
        )
    return username


def _safe_extension(filename: str) -> str:
    """A short, conservative extension, or none.

    Taken from the original name only so the download arrives with a sensible
    suffix. Anything unexpected is dropped rather than sanitised, because the
    extension ends up in an S3 key.
    """
    _, _, tail = str(filename or "").rpartition(".")
    if tail and tail != filename and 1 <= len(tail) <= 8 and tail.isalnum():
        return "." + tail.lower()
    return ""


def _upload_init(event: Dict[str, Any], origin: str) -> Dict[str, Any]:
    body = json.loads(event.get("body") or "{}")
    name = str(body.get("name") or "").strip()
    display_name = str(body.get("displayName") or "").strip()
    filename = str(body.get("originalFilename") or "").strip()
    content_type = str(body.get("contentType") or "application/octet-stream").strip()
    size = int(body.get("sizeBytes") or 0)

    try:
        phone = normalise_phone(body.get("mobile"))
    except ValueError:
        return cors_response(400, {"error": "A valid mobile number is required"}, origin)
    if not name:
        return cors_response(400, {"error": "Customer name is required"}, origin)
    if not filename:
        return cors_response(400, {"error": "originalFilename is required"}, origin)
    if size <= 0 or size > MAX_UPLOAD_BYTES:
        return cors_response(
            400, {"error": f"sizeBytes must be between 1 and {MAX_UPLOAD_BYTES}"}, origin
        )

    username = _ensure_customer_user(phone, name)

    file_id = f"{uuid.uuid4().hex}-{uuid.uuid4().hex}"
    basename = f"wecare-digital-{file_id}{_safe_extension(filename)}"
    key = UPLOAD_PREFIX + basename
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    _table(FILES_TABLE).put_item(
        Item={
            "fileId": file_id,
            "s3Key": key,
            "ownerPhone": phone,
            "ownerName": name,
            "cognitoUsername": username,
            "displayName": display_name or filename,
            "originalFilename": filename,
            "contentType": content_type,
            "sizeBytes": size,
            "pricePaise": PRICE_PAISE,
            # Decided at confirm time, once the real object is measured rather than
            # trusted from the browser: "pdf", "image", or "link" when the type
            # cannot be opened inline on WhatsApp.
            "deliverable": "unknown",
            # pending until the object is actually in the bucket, so a failed
            # browser upload cannot leave a file the customer can be charged for
            "status": "pending",
            "downloadCount": 0,
            "uploadedBy": (event.get("_auth") or {}).get("username", ""),
            "createdAt": now,
        }
    )

    upload_url = _s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=UPLOAD_URL_TTL,
    )

    logger.info(
        json.dumps(
            {
                "event": "secure_file_upload_init",
                "fileId": file_id,
                "ownerPhone": mask_phone(phone),
                "sizeBytes": size,
            }
        )
    )
    return cors_response(
        201,
        {
            "fileId": file_id,
            "uploadUrl": upload_url,
            "expiresInSeconds": UPLOAD_URL_TTL,
            "contentType": content_type,
        },
        origin,
    )


def _classify_delivery(content_type: str, size: int) -> str:
    """Whether this file can be opened inline on WhatsApp: "pdf", "image" or "link".

    Judged on the object S3 actually holds, not on what the browser claimed, because
    the browser's Content-Type is a hint and a wrong one would only surface when a
    paying customer received something they could not open.
    """
    kind = DELIVERABLE_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if kind == "image" and size <= MAX_IMAGE_BYTES:
        return "image"
    if kind == "pdf" and size <= MAX_DOCUMENT_BYTES:
        return "pdf"
    # Too large, or a type that would arrive as an unopenable blob. Still sellable -
    # it just goes out as a download link rather than an attachment.
    return "link"


def _upload_confirm(file_id: str, origin: str) -> Dict[str, Any]:
    """Flip pending -> active, but only after proving the object is really there.

    Also creates the ``d/`` rendition when the file can be delivered over WhatsApp.
    That copy is server-side, so the bytes never travel through this function.
    """
    table = _table(FILES_TABLE)
    item = table.get_item(Key={"fileId": file_id}).get("Item")
    if not item:
        return cors_response(404, {"error": "Unknown fileId"}, origin)

    upload_key = item["s3Key"]
    try:
        head = _s3_client().head_object(Bucket=BUCKET, Key=upload_key)
    except ClientError:
        return cors_response(
            409, {"error": "Upload not found in storage; retry the upload"}, origin
        )

    size = int(head["ContentLength"])
    # Prefer what S3 recorded over what the browser asserted at upload-init.
    content_type = head.get("ContentType") or item.get("contentType") or ""
    deliverable = _classify_delivery(content_type, size)

    delivery_key = ""
    if deliverable in ("pdf", "image"):
        delivery_key = DELIVER_PREFIX + upload_key.split("/")[-1]
        try:
            _s3_client().copy_object(
                Bucket=BUCKET,
                Key=delivery_key,
                CopySource={"Bucket": BUCKET, "Key": upload_key},
                ContentType=content_type,
                MetadataDirective="REPLACE",
            )
        except ClientError as exc:
            # Not fatal: the file is still sellable as a download link. Record the
            # downgrade rather than failing an upload that otherwise succeeded.
            logger.warning(
                json.dumps({"event": "delivery_copy_failed", "fileId": file_id,
                            "error": exc.response["Error"]["Code"]})
            )
            deliverable, delivery_key = "link", ""

    table.update_item(
        Key={"fileId": file_id},
        UpdateExpression=(
            "SET #s = :active, sizeBytes = :size, contentType = :ct, "
            "deliverable = :d, deliveryKey = :dk"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":active": "active", ":size": size, ":ct": content_type,
            ":d": deliverable, ":dk": delivery_key,
        },
    )
    logger.info(
        json.dumps({"event": "secure_file_active", "fileId": file_id,
                    "deliverable": deliverable, "sizeBytes": size})
    )
    return cors_response(
        200,
        {"fileId": file_id, "status": "active", "sizeBytes": size,
         "deliverable": deliverable},
        origin,
    )


def _admin_list(event: Dict[str, Any], origin: str) -> Dict[str, Any]:
    """Every file, or one customer's, depending on ?mobile=."""
    params = event.get("queryStringParameters") or {}
    table = _table(FILES_TABLE)

    mobile = params.get("mobile")
    if mobile:
        try:
            phone = normalise_phone(mobile)
        except ValueError:
            return cors_response(400, {"error": "Invalid mobile number"}, origin)
        # the GSI is the whole point: one customer's files without a scan
        result = table.query(
            IndexName="owner-created-index",
            KeyConditionExpression="ownerPhone = :p",
            ExpressionAttributeValues={":p": phone},
            ScanIndexForward=False,
            Limit=100,
        )
    else:
        result = table.scan(Limit=100)

    items = sorted(
        result.get("Items", []), key=lambda i: str(i.get("createdAt", "")), reverse=True
    )
    return cors_response(
        200,
        {"files": [_public_file(i, admin=True) for i in items], "count": len(items)},
        origin,
    )


def _admin_revoke(file_id: str, origin: str) -> Dict[str, Any]:
    """Revoke rather than delete: the audit trail of who was charged survives."""
    try:
        _table(FILES_TABLE).update_item(
            Key={"fileId": file_id},
            UpdateExpression="SET #s = :revoked",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":revoked": "revoked"},
            ConditionExpression="attribute_exists(fileId)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return cors_response(404, {"error": "Unknown fileId"}, origin)
        raise
    return cors_response(200, {"fileId": file_id, "status": "revoked"}, origin)


# ── customer: list, order, download ───────────────────────────────────────────

def _customer_list(identity: Dict[str, Any], origin: str) -> Dict[str, Any]:
    result = _table(FILES_TABLE).query(
        IndexName="owner-created-index",
        KeyConditionExpression="ownerPhone = :p",
        ExpressionAttributeValues={":p": identity["phone"]},
        ScanIndexForward=False,
        Limit=100,
    )
    items = [i for i in result.get("Items", []) if i.get("status") == "active"]
    return cors_response(
        200,
        {
            "files": [_public_file(i, admin=False) for i in items],
            "count": len(items),
            "pricePaise": PRICE_PAISE,
        },
        origin,
    )


def _owned_active_file(file_id: str, identity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The record, but only if this caller owns it and it is active.

    Every failure mode returns None so callers cannot tell them apart.
    """
    item = _table(FILES_TABLE).get_item(Key={"fileId": file_id}).get("Item")
    if not item or item.get("status") != "active":
        return None
    if item.get("ownerPhone") != identity["phone"]:
        return None
    return item


def _create_order(file_id: str, identity: Dict[str, Any], origin: str) -> Dict[str, Any]:
    item = _owned_active_file(file_id, identity)
    if not item:
        return _not_registered(origin)

    if not _payment_enabled():
        # Refuse loudly rather than silently granting. Nothing here contacts
        # Razorpay or reads a credential while the flag is off.
        return cors_response(
            503,
            {
                "error": "PAYMENT_DISABLED",
                "message": "Paid downloads are not enabled yet.",
                "pricePaise": int(item.get("pricePaise", PRICE_PAISE)),
            },
            origin,
        )

    from razorpay_orders import create_order  # imported lazily: only needed when live

    order = create_order(
        amount_paise=int(item.get("pricePaise", PRICE_PAISE)),
        receipt=f"dl_{file_id[:24]}",
        notes={"fileId": file_id, "purpose": "secure_file_download"},
    )

    now = int(time.time())
    grant_id = uuid.uuid4().hex
    _table(GRANTS_TABLE).put_item(
        Item={
            "grantId": grant_id,
            "fileId": file_id,
            "ownerPhone": identity["phone"],
            "orderId": order["id"],
            "amountPaise": int(item.get("pricePaise", PRICE_PAISE)),
            # paid flips only in the webhook, never from a client callback
            "paid": False,
            "consumed": False,
            "createdAt": now,
            "expiresAt": now + GRANT_TTL,
        }
    )
    return cors_response(
        201,
        {
            "grantId": grant_id,
            "orderId": order["id"],
            "amountPaise": int(item.get("pricePaise", PRICE_PAISE)),
            "currency": "INR",
            "keyId": order.get("key_id", ""),
        },
        origin,
    )


def _reconcile_grant(grant_id: str, file_id: str, identity: Dict[str, Any]) -> bool:
    """Mark an unpaid grant paid if Razorpay says the order was actually captured.

    The safety net for a webhook that never arrives. Returns True only when the grant
    was genuinely unspent, belongs to this caller and this file, and Razorpay confirms
    a captured payment.

    Deliberately narrow. It refuses to touch a grant that is already ``consumed``, so
    it cannot be used to replay a spent download, and it writes ``paid`` through the
    same conditional guard the webhook uses.
    """
    if not _payment_enabled():
        return False

    table = _table(GRANTS_TABLE)
    grant = table.get_item(Key={"grantId": grant_id}).get("Item")

    # Every mismatch returns False, so this can never widen who may download what.
    if not grant:
        return False
    if grant.get("fileId") != file_id or grant.get("ownerPhone") != identity["phone"]:
        return False
    if grant.get("consumed"):
        return False
    if grant.get("paid"):
        # Already paid but the redeem still failed, so the cause was something else.
        return False

    order_id = str(grant.get("orderId") or "")
    if not order_id:
        return False

    try:
        from razorpay_orders import order_is_paid

        paid, payment_id, amount_paise = order_is_paid(order_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            json.dumps({"event": "grant_reconcile_failed", "error": type(exc).__name__})
        )
        return False

    if not paid:
        return False

    try:
        table.update_item(
            Key={"grantId": grant_id},
            UpdateExpression=(
                "SET paid = :true, paymentId = :pid, paidAmountPaise = :amt, "
                "paidAt = :now, paidVia = :via"
            ),
            ConditionExpression="attribute_exists(grantId) AND paid = :false",
            ExpressionAttributeValues={
                ":true": True,
                ":false": False,
                ":pid": payment_id,
                ":amt": int(amount_paise),
                ":now": int(time.time()),
                # Recorded so it is visible when the webhook is not doing its job.
                ":via": "reconcile",
            },
        )
    except ClientError:
        # Lost a race with the webhook. That is a success, not a failure.
        pass

    logger.info(
        json.dumps(
            {
                "event": "grant_reconciled_from_razorpay",
                "alert": "WEBHOOK_MAY_NOT_BE_SUBSCRIBED",
                "fileId": file_id,
                "amountPaise": int(amount_paise),
            }
        )
    )
    return True


def _redeem_after_reconcile(
    file_id: str,
    grant_id: str,
    identity: Dict[str, Any],
    item: Dict[str, Any],
    origin: str,
):
    """Spend a grant that reconciliation just marked paid.

    Still a conditional update, still single use - reconciliation changes only whether
    the grant is payable, never whether it has already been spent.
    """
    try:
        _table(GRANTS_TABLE).update_item(
            Key={"grantId": grant_id},
            UpdateExpression="SET consumed = :true, consumedAt = :now",
            ConditionExpression=(
                "attribute_exists(grantId) AND fileId = :fid AND ownerPhone = :p "
                "AND paid = :true AND consumed = :false"
            ),
            ExpressionAttributeValues={
                ":true": True,
                ":false": False,
                ":now": int(time.time()),
                ":fid": file_id,
                ":p": identity["phone"],
            },
        )
    except ClientError:
        return cors_response(
            403,
            {
                "error": "GRANT_NOT_REDEEMABLE",
                "message": "This download link is not valid. Please pay again to download.",
            },
            origin,
        )

    return cors_response(
        200,
        {
            "downloadUrl": _download_url(item),
            "expiresInSeconds": DOWNLOAD_URL_TTL,
        },
        origin,
    )


def _download_url(item: Dict[str, Any]) -> str:
    """A short-lived presigned GET that downloads under the readable filename."""
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": BUCKET,
            "Key": item["s3Key"],
            "ResponseContentDisposition": (
                f'attachment; filename="{item.get("originalFilename", "download")}"'
            ),
        },
        ExpiresIn=DOWNLOAD_URL_TTL,
    )


def _redeem(file_id: str, event: Dict[str, Any], identity: Dict[str, Any], origin: str):
    """Spend a paid grant for a 60-second presigned URL.

    The conditional update is the whole mechanism: it flips ``consumed`` only if it
    is currently false, so two concurrent requests cannot both win and a forwarded
    link is dead on second use.
    """
    params = event.get("queryStringParameters") or {}
    grant_id = str(params.get("grant") or "").strip()
    if not grant_id:
        return cors_response(400, {"error": "grant is required"}, origin)

    item = _owned_active_file(file_id, identity)
    if not item:
        return _not_registered(origin)

    try:
        updated = _table(GRANTS_TABLE).update_item(
            Key={"grantId": grant_id},
            UpdateExpression="SET consumed = :true, consumedAt = :now",
            ConditionExpression=(
                "attribute_exists(grantId) AND fileId = :fid AND ownerPhone = :p "
                "AND paid = :true AND consumed = :false"
            ),
            ExpressionAttributeValues={
                ":true": True,
                ":false": False,
                ":now": int(time.time()),
                ":fid": file_id,
                ":p": identity["phone"],
            },
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise

        # The grant is unpaid, already spent, expired, or not this caller's - the
        # condition cannot say which. Before refusing, check whether it is merely
        # unpaid *as far as we know*: the webhook may never have arrived.
        #
        # This is the difference between "the customer was charged and gets nothing"
        # and "the customer waits two seconds". It asks Razorpay directly, which is
        # the same authority the webhook relays, and never trusts the client.
        if _reconcile_grant(grant_id, file_id, identity):
            return _redeem_after_reconcile(file_id, grant_id, identity, item, origin)

        return cors_response(
            403,
            {
                "error": "GRANT_NOT_REDEEMABLE",
                "message": "This download link is not valid. Please pay again to download.",
            },
            origin,
        )

    # downloads under the readable name, never the opaque key
    url = _download_url(item)

    try:
        _table(FILES_TABLE).update_item(
            Key={"fileId": file_id},
            UpdateExpression="ADD downloadCount :one",
            ExpressionAttributeValues={":one": 1},
        )
    except ClientError:
        pass  # a missed counter must never fail a paid download

    logger.info(
        json.dumps(
            {
                "event": "secure_file_downloaded",
                "fileId": file_id,
                "ownerPhone": mask_phone(identity["phone"]),
                "paymentId": _decimal_safe(updated.get("Attributes", {})).get("paymentId", ""),
            }
        )
    )
    return cors_response(
        200, {"downloadUrl": url, "expiresInSeconds": DOWNLOAD_URL_TTL}, origin
    )


# ── routing ───────────────────────────────────────────────────────────────────

def _path_parts(event: Dict[str, Any]) -> Tuple[str, list]:
    rc = event.get("requestContext", {})
    raw = rc.get("http", {}).get("path") or event.get("rawPath") or event.get("path") or ""
    try:
        from lambda_utils.http_path import strip_stage

        raw = strip_stage(raw, str(rc.get("stage") or ""))
    except Exception:  # noqa: BLE001
        pass
    return raw, [p for p in raw.split("/") if p]


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    origin = extract_origin(event)
    rc = event.get("requestContext", {})
    method = (
        rc.get("http", {}).get("method") or event.get("httpMethod") or "GET"
    ).upper()
    if method == "OPTIONS":
        return options_response(origin)

    path, parts = _path_parts(event)
    # /secure-files/...  -> drop the leading segment
    tail = parts[1:] if parts and parts[0] == "secure-files" else parts

    try:
        # ---- customer surface ------------------------------------------------
        if tail[:1] == ["mine"] and method == "GET":
            identity = _customer_identity(event)
            if not identity:
                return cors_response(401, {"error": "Verification required"}, origin)
            return _customer_list(identity, origin)

        if len(tail) == 2 and tail[1] in ("order", "download"):
            identity = _customer_identity(event)
            if not identity:
                return cors_response(401, {"error": "Verification required"}, origin)
            if tail[1] == "order" and method == "POST":
                return _create_order(tail[0], identity, origin)
            if tail[1] == "download" and method == "GET":
                return _redeem(tail[0], event, identity, origin)
            return cors_response(405, {"error": "Method not allowed"}, origin)

        # ---- admin surface ---------------------------------------------------
        denied = require_auth(event, "Operator")
        if denied is not None:
            return denied

        if not tail:
            if method == "GET":
                return _admin_list(event, origin)
            return cors_response(405, {"error": "Method not allowed"}, origin)

        if tail == ["upload-init"] and method == "POST":
            return _upload_init(event, origin)
        if len(tail) == 2 and tail[1] == "confirm" and method == "POST":
            return _upload_confirm(tail[0], origin)
        if len(tail) == 2 and tail[1] == "revoke" and method == "POST":
            return _admin_revoke(tail[0], origin)

        return cors_response(404, {"error": f"Unknown route {path}"}, origin)

    except json.JSONDecodeError:
        return cors_response(400, {"error": "Body must be valid JSON"}, origin)
    except Exception as exc:  # noqa: BLE001
        # type only: an exception message can carry data we did not construct
        logger.error(json.dumps({"event": "secure_files_error", "error": type(exc).__name__}))
        return cors_response(500, {"error": "Internal error"}, origin)
