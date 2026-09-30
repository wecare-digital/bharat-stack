"""The customer checkout front door for the headless WhatsApp/Razorpay flow.

Where this sits
---------------
    [customer, signed in]  --create-->  THIS  --create checkout-->  [Wix eCom]     (authoritative total)
                                          |
                                          |  readiness gate (live Meta readback)
                                          |  reserve reference_id, build PaymentAttempt
                                          v
                                   [order_details in WhatsApp]  -->  [Meta]  -->  [Razorpay]   (pays in-chat)

This handler is the *verifier's front half*: it decides an amount authoritatively, records a
PaymentAttempt, and hands the customer off to pay inside WhatsApp. It never charges anything itself
and never creates an order — an order exists only after the razorpay-webhook reconciliation verifies
a capture against Razorpay's API. That boundary is the whole design, so this handler imports the
post-PAID functions of `order_keys` not at all.

Four rules it enforces, each load-bearing
------------------------------------------
1. **Authority comes from the session, never the request.** The customer is proven by
   `customer_auth` (issuer-pinned to the customer pool), and every checkout is bound to that
   immutable `CUS_` id. A `paymentAttemptId` or `checkoutId` in the body is checked against the
   session with `authorize_resource`, so one customer cannot read another's attempt (IDOR).
2. **The amount is Wix's, in integer paise.** `wix_ecom.authoritative_total_paise` reads
   `priceSummary.total` — the browser cannot set or influence it, and a non-whole-paise total is
   refused, not rounded.
3. **Payments are readiness-gated on a live provider readback.** `payment_readiness.evaluate` must
   return `PAYMENT_READY` before an attempt is created; otherwise the CTA is refused with the
   blocking state. No local constant can make it ready.
4. **The reference is minted once, reserved, and sent byte-for-byte.** `order_keys` mints and
   reserves it under `PAYREF#`; it is never transformed after reservation.

Initiation is disabled by default
----------------------------------
`CHECKOUT_INITIATION_ENABLED` gates the actual WhatsApp order_details send. Off (the default), the
handler does everything up to and including reserving the attempt, and returns the attempt in a
`PAYMENT_INITIATION_DISABLED` state instead of sending a payable message. This is the same
posture as the Velo adapter's `initiationEnabled=false`: the plumbing is exercised end to end, but
no live payment request goes out until someone deliberately turns it on. It can only be turned on,
never made permissive by a value that also disables readiness.

Nothing plaintext is logged
---------------------------
No full phone number, no customer id in a form that identifies a person beyond its own opaque id,
no amount tied to a person, no exception text that could echo request content. Event names, opaque
ids, states and counts only.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import boto3

from lambda_utils import customer_auth, payment_readiness
from lambda_utils.ecommerce import order_keys, payment_attempt
from lambda_utils import wix_ecom
from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, extract_origin, options_response

logger = get_logger(__name__)

REGION = os.environ.get("AWS_REGION", "us-east-1")

#: The payment-attempt store and the commerce-keys (reference reservation) store.
PAYMENT_ATTEMPTS_TABLE = os.environ.get(
    "PAYMENT_ATTEMPTS_TABLE", payment_attempt.DEFAULT_TABLE_NAME)
COMMERCE_KEYS_TABLE = os.environ.get("COMMERCE_KEYS_TABLE", "")

#: Checkout mode marker on the attempt, so this path is distinguishable from any other and a test
#: can assert which flow created it. Headless WhatsApp/Razorpay, not the (set-aside) Velo provider.
CHECKOUT_MODE = "WIX_HEADLESS"

#: The in-chat payment sender and the identity of the paying WABA/config. These name the existing
#: order_details path; this handler invokes it rather than reimplementing the message build.
SENDER_FUNCTION = os.environ.get("SENDER_FUNCTION", "wecare-whatsapp-business-api:live")
PAYMENT_WABA_ID = os.environ.get("PAYMENT_WABA_ID", "2094615664435155")

#: Readiness inputs. Deliberately have NO safe default that could read as "ready": an empty MID or
#: configuration name makes `payment_readiness.evaluate` return CONFIGURATION_UNVERIFIED, which
#: blocks. They are set from the environment at deploy time and re-derived from a live read.
EXPECTED_CONFIGURATION_NAME = os.environ.get("EXPECTED_CONFIGURATION_NAME", "")
EXPECTED_PROVIDER_MID = os.environ.get("EXPECTED_PROVIDER_MID", "")

#: Off by default. The plumbing runs; the payable message does not go out until this is truthy.
INITIATION_ENABLED = str(
    os.environ.get("CHECKOUT_INITIATION_ENABLED", "")).strip().lower() in ("1", "true", "yes", "on")

_dynamodb = None
_lambda = None


def _table(name: str):
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return _dynamodb.Table(name)


def _attempts_table():
    return _table(PAYMENT_ATTEMPTS_TABLE)


def _keys_table():
    return _table(COMMERCE_KEYS_TABLE or order_keys.commerce_keys_table_name())


def _lambda_client():
    global _lambda
    if _lambda is None:
        _lambda = boto3.client("lambda", region_name=REGION)
    return _lambda


# ── readiness ────────────────────────────────────────────────────────────────

def _fetch_payment_configurations(waba_id: str) -> Dict[str, Any]:
    """Live Meta read of `GET /{waba}/payment_configurations`, via the WhatsApp business Lambda.

    Injected into `payment_readiness.evaluate` so this handler holds no Meta credential. The
    business-API Lambda already owns the Graph token and the read; we invoke its check route and
    return the parsed configurations payload it produces.
    """
    invoke_event = {
        "httpMethod": "GET",
        "path": "/wa-business/payment-config/raw",
        "queryStringParameters": {"wabaId": waba_id},
    }
    response = _lambda_client().invoke(
        FunctionName=SENDER_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(invoke_event).encode("utf-8"),
    )
    raw = response["Payload"].read()
    if response.get("FunctionError"):
        raise RuntimeError("payment-config read Lambda failed")
    result = json.loads(raw.decode("utf-8")) if raw else {}
    body = result.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (ValueError, TypeError):
            body = {}
    return body if isinstance(body, dict) else {}


def _readiness() -> payment_readiness.PaymentReadiness:
    return payment_readiness.evaluate(
        expected_waba_id=PAYMENT_WABA_ID,
        expected_configuration_name=EXPECTED_CONFIGURATION_NAME,
        expected_provider_mid=EXPECTED_PROVIDER_MID,
        fetch_configurations=_fetch_payment_configurations,
    )


# ── request plumbing ───────────────────────────────────────────────────────────

def _body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get("body")
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {k: v for k, v in event.items()
                if k not in ("requestContext", "headers", "httpMethod", "path",
                             "rawPath", "isBase64Encoded", "queryStringParameters")}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


def _action(event: Dict[str, Any], body: Dict[str, Any]) -> str:
    explicit = str(body.get("action") or event.get("action") or "").strip().lower()
    if explicit in ("create", "status"):
        return explicit
    path = str(event.get("rawPath") or event.get("path") or "").lower()
    if path.endswith("/status"):
        return "status"
    return "create"


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    origin = extract_origin(event)
    rc = event.get("requestContext", {}) or {}
    method = rc.get("http", {}).get("method", event.get("httpMethod", "")).upper()
    if method == "OPTIONS":
        return options_response(origin)

    # Every checkout action requires a proven customer session. Unlike registration/email-OTP,
    # this endpoint is NOT public: by the time a customer reaches checkout they have signed in, and
    # a checkout must be bound to an authenticated identity server-side (never to a body-supplied
    # customerId, phone or Wix buyerId).
    identity, denied = customer_auth.require_customer(event)
    if denied:
        return denied

    body = _body(event)
    action = _action(event, body)
    try:
        if action == "status":
            return _status(identity, body, origin)
        return _create(identity, body, origin)
    except customer_auth.CustomerNotAuthorized:
        # Same opaque 401 as unauthenticated, so the endpoint is not an IDOR oracle.
        return customer_auth.denied_response(event)
    except Exception as exc:  # noqa: BLE001
        logger.error(json.dumps({"event": "checkout_error",
                                 "action": action, "error": type(exc).__name__}))
        return cors_response(500, {"error": "INTERNAL_ERROR"}, origin)


def _create(identity: customer_auth.CustomerIdentity, body: Dict[str, Any],
            origin: str) -> Dict[str, Any]:
    """Resolve authoritative totals, gate on readiness, reserve an attempt, hand off to WhatsApp."""
    line_items = body.get("lineItems")
    if not isinstance(line_items, list) or not line_items:
        return cors_response(400, {"error": "LINE_ITEMS_REQUIRED",
                                   "message": "Your cart is empty."}, origin)

    # 1. Authoritative checkout + total, from Wix. The browser sent catalogue references and
    #    quantities; Wix computes the price. A non-INR or non-whole-paise total fails closed.
    try:
        checkout = wix_ecom.create_checkout(line_items)
        currency = wix_ecom.checkout_currency(checkout)
        if currency != "INR":
            logger.warning(json.dumps({"event": "checkout_non_inr", "currency": currency}))
            return cors_response(409, {"error": "UNSUPPORTED_CURRENCY"}, origin)
        amount_paise = wix_ecom.authoritative_total_paise(checkout)
    except wix_ecom.AmountNotWhole:
        return cors_response(409, {"error": "AMOUNT_NOT_SETTLED",
                                   "message": "We could not price this cart. Please try again."},
                             origin)
    except wix_ecom.WixEcomError:
        return cors_response(502, {"error": "CATALOGUE_UNAVAILABLE",
                                   "message": "The store is temporarily unavailable."}, origin)

    wix_checkout_id = str(checkout.get("id") or "")

    # 2. Readiness gate. A live provider readback must confirm PAYMENT_READY, or the CTA is refused
    #    with the blocking state. No local constant makes this pass.
    readiness = _readiness()
    if not readiness.ready:
        logger.info(json.dumps({"event": "checkout_not_ready", "state": readiness.state}))
        return cors_response(409, {
            "status": "payment_unavailable",
            "readiness": readiness.state,
            "message": "Payments are temporarily unavailable. No charge was made.",
        }, origin)

    # 3. Reserve a canonical reference bound to a fresh attempt id, then build the attempt. The
    #    reference is minted and durably reserved BEFORE it is used, and never transformed after.
    attempt_id = payment_attempt.new_payment_attempt_id()
    try:
        reference_id = order_keys.allocate_payment_reference(
            _keys_table(), payment_attempt_id=attempt_id,
            extra={"customerId": identity.customer_id,
                   "amountPaise": amount_paise, "currency": "INR",
                   "wixCheckoutId": wix_checkout_id, "checkoutMode": CHECKOUT_MODE},
        )
    except order_keys.OrderIdentityUnavailable:
        return cors_response(503, {"error": "TEMPORARILY_UNAVAILABLE",
                                   "message": "Please try again shortly."}, origin)

    attempt = payment_attempt.build(
        customer_id=identity.customer_id,
        reference_id=reference_id,
        amount_paise=amount_paise,
        configuration_name=EXPECTED_CONFIGURATION_NAME,
        wix_checkout_id=wix_checkout_id,
        payment_attempt_id=attempt_id,
    )
    attempt["checkoutMode"] = CHECKOUT_MODE
    attempt = payment_attempt.transition(
        attempt, payment_attempt.PAYMENT_READINESS_CHECKED)
    try:
        _attempts_table().put_item(
            Item=attempt,
            ConditionExpression="attribute_not_exists(paymentAttemptId)",
        )
    except Exception as error:  # noqa: BLE001
        logger.error(json.dumps({"event": "checkout_attempt_store_failed",
                                 "error": type(error).__name__}))
        return cors_response(503, {"error": "TEMPORARILY_UNAVAILABLE"}, origin)

    # 4. Hand off to the in-chat payment request — UNLESS initiation is disabled, in which case the
    #    attempt exists and is ready but no payable message goes out. Either way, NO order exists.
    if not INITIATION_ENABLED:
        logger.info(json.dumps({"event": "checkout_initiation_disabled",
                                "attemptId": attempt_id}))
        return cors_response(200, {
            "status": "PAYMENT_INITIATION_DISABLED",
            "paymentAttemptId": attempt_id,
            "amountPaise": amount_paise,
            "currency": "INR",
            "message": "Checkout prepared. Live payment initiation is currently disabled.",
        }, origin)

    sent = _send_order_details(
        phone=identity.phone, reference_id=reference_id,
        amount_paise=amount_paise, configuration_name=EXPECTED_CONFIGURATION_NAME,
        items=wix_ecom.line_item_summary(checkout))
    if not sent:
        # The attempt is stored and ready; the message did not go. A soft failure the client can
        # retry, and crucially still NO order and NO second charge — the reference is reusable for a
        # delivery retry because the attempt is unchanged.
        return cors_response(502, {
            "status": "SEND_FAILED",
            "paymentAttemptId": attempt_id,
            "message": "We could not open the payment. Please try again.",
        }, origin)

    _mark_request_sent(attempt_id)
    return cors_response(200, {
        "status": "PAYMENT_REQUEST_SENT",
        "paymentAttemptId": attempt_id,
        "amountPaise": amount_paise,
        "currency": "INR",
        "message": "Check WhatsApp to complete your payment.",
    }, origin)


def _status(identity: customer_auth.CustomerIdentity, body: Dict[str, Any],
            origin: str) -> Dict[str, Any]:
    """Return the customer-safe status of one of the caller's own payment attempts.

    IDOR-safe: the attempt is loaded by id and then `authorize_resource` refuses it unless it
    belongs to this session. A missing attempt and someone else's attempt return the identical
    opaque 401, so the endpoint cannot be used to discover which attempt ids are real.
    """
    attempt_id = str(body.get("paymentAttemptId") or "").strip()
    if not attempt_id:
        return cors_response(400, {"error": "PAYMENT_ATTEMPT_ID_REQUIRED"}, origin)

    try:
        stored = _attempts_table().get_item(
            Key={"paymentAttemptId": attempt_id}).get("Item")
    except Exception as error:  # noqa: BLE001
        logger.error(json.dumps({"event": "checkout_status_read_failed",
                                 "error": type(error).__name__}))
        return cors_response(503, {"error": "TEMPORARILY_UNAVAILABLE"}, origin)

    owned = customer_auth.authorize_resource(identity, stored, owner_field="customerId")
    # payment_history_entry never carries an order number for a non-paid attempt, and collapses a
    # failed one to the "Payment failed — no order created" label. It is the exact customer-facing
    # projection the status UI needs; the order number itself (when paid) is resolved elsewhere.
    entry = payment_attempt.payment_history_entry(owned)
    return cors_response(200, {"status": entry.get("status"), "attempt": entry}, origin)


# ── the WhatsApp order_details handoff ──────────────────────────────────────────

def _send_order_details(*, phone: str, reference_id: str, amount_paise: int,
                        configuration_name: str, items: list) -> bool:
    """Invoke the existing in-chat payment-request sender. Returns True on a 2xx.

    This does NOT build the order_details payload itself — `outbound-whatsapp`/`whatsapp-business-api`
    own that (`_build_payment_settings`, the interactive-payment path). We pass the reserved
    reference byte-for-byte, the authoritative paise amount, the configuration name and a price-free
    item summary, and let the sender construct the Meta message. Meta + Razorpay collect the money
    in-chat; nothing here charges anything.
    """
    invoke_event = {
        "httpMethod": "POST",
        "path": "/wa-business/messages/send/interactive-payment",
        "body": json.dumps({
            "to": "".join(ch for ch in str(phone or "") if ch.isdigit()),
            "reference_id": reference_id,
            "payment_configuration": configuration_name,
            "amount_paise": amount_paise,
            "currency": "INR",
            "items": items,
        }),
    }
    try:
        response = _lambda_client().invoke(
            FunctionName=SENDER_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps(invoke_event).encode("utf-8"),
        )
        raw = response["Payload"].read()
        if response.get("FunctionError"):
            return False
        result = json.loads(raw.decode("utf-8")) if raw else {}
        return int(result.get("statusCode") or 500) < 300
    except Exception as error:  # noqa: BLE001
        logger.error(json.dumps({"event": "checkout_send_failed",
                                 "error": type(error).__name__}))
        return False


def _mark_request_sent(attempt_id: str) -> None:
    """Advance the attempt to PAYMENT_REQUEST_SENT with the monotonic guard. Best-effort.

    Uses the same rank condition the state machine defines, so a late/duplicate write cannot move
    the attempt backwards. A failure here does not undo the send; the webhook reconciliation keys on
    the reference regardless of this marker.
    """
    try:
        _attempts_table().update_item(
            Key={"paymentAttemptId": attempt_id},
            UpdateExpression="SET #s = :s, " + payment_attempt.RANK_ATTRIBUTE
            + " = :r, updatedAt = :t",
            ConditionExpression=payment_attempt.condition_expression(),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": payment_attempt.PAYMENT_REQUEST_SENT,
                ":r": payment_attempt.rank(payment_attempt.PAYMENT_REQUEST_SENT),
                ":t": int(time.time()),
            },
        )
    except Exception as error:  # noqa: BLE001
        logger.info(json.dumps({"event": "checkout_mark_sent_skipped",
                               "error": type(error).__name__}))
