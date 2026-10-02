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

Two coexisting flows: the retained in-chat path and the additive website contract (section 8)
---------------------------------------------------------------------------------------------
This handler's `_create` returns ``PAYMENT_REQUEST_SENT`` for the IN-WHATSAPP flow above. That is
a RETAINED legacy response: callers still consume it, and it is NOT removed until they are migrated.
The in-WhatsApp vs website decision is an owner decision flagged in
``.agents/tasks/checkout-audit-2026-10-01/findings.md`` (the repo spec records "pay inside
WhatsApp" / "WhatsApp-only receipts"; the task asks for a website Razorpay Standard Checkout). Both
paths coexist behind the SAME ``CHECKOUT_INITIATION_ENABLED`` gate, default off.

The ADDITIVE website path lives in
``lambda_utils/ecommerce/website_checkout.py`` + ``lambda_utils/integrations/razorpay_orders.py``.
Its documented contract, which replaces ``PAYMENT_REQUEST_SENT`` for the website without deleting
it for the in-chat path, is:

    create  (gate off, the default)  -> ``PAYMENT_INITIATION_DISABLED``
            {paymentAttemptId}                 no gateway order, no payable attempt
    create  (gate on)                -> ``CHECKOUT_OPTIONS_READY``
            {keyId, orderId, amountPaise, currency, prefill, paymentAttemptId}
                                               ONLY these fields; keyId is the PUBLIC key id,
                                               orderId is the SERVER-STORED Razorpay gateway order
                                               id, amountPaise is the FEAT-001 calculator total
                                               (collection+fee+GST), never the raw Wix total.
    create  (ownership/snapshot/intent fails) -> ``CHECKOUT_REJECTED`` (no order created)
    create  (provider timeout/save ambiguity) -> ``CHECKOUT_AMBIGUOUS`` (never a 2nd payable order)

    callback (browser relays payment id/order id/signature) ->
            HMAC verified over the STORED gateway order id, then STILL requires
            ``razorpay_verify`` authoritative capture -> ``VERIFIED_PAID`` only after capture.

A Razorpay GATEWAY order exists before payment; an internal/Wix purchase order and public purchase
number exist ONLY after an authoritative capture. They are different objects. Cart/resume data is
kept until that verified-paid finalization. Partial payment is disabled for this release.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import boto3
from boto3.dynamodb.conditions import Key

from lambda_utils import customer_auth, payment_readiness
from lambda_utils.ecommerce import (
    cart_v2, checkout_pricing, customer_cart, order_keys, payment_attempt,
    purchase_intent, website_checkout)
from lambda_utils.integrations import razorpay_orders, razorpay_verify
from lambda_utils import wix_ecom
from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, extract_origin, options_response

logger = get_logger(__name__)

REGION = os.environ.get("AWS_REGION", "us-east-1")

#: The payment-attempt store and the commerce-keys (reference reservation) store.
PAYMENT_ATTEMPTS_TABLE = os.environ.get(
    "PAYMENT_ATTEMPTS_TABLE", payment_attempt.DEFAULT_TABLE_NAME)
COMMERCE_KEYS_TABLE = os.environ.get("COMMERCE_KEYS_TABLE", "")
CONTACTS_TABLE = os.environ.get("CONTACTS_TABLE", "stack-wecare-digital-ContactsTable")
WEBSITE_SNAPSHOT_TTL_SECONDS = 15 * 60

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

#: Loader for the authenticated customer's OWNED delivery address, injected rather than
#: imported.
#:
#: Signature: `(customer_id: str) -> dict | None`, returning a structured address in
#: `lambda_utils.identity.address` shape, or `None` when the customer has not chosen one.
#:
#: It is a seam rather than a call because this function has no customers table: its environment
#: carries `PAYMENT_ATTEMPTS_TABLE` and `COMMERCE_KEYS_TABLE` and nothing else. Wiring the
#: profile read is the remaining half of the producer chain, recorded in
#: `docs/execution/wix-cart-v2-migration-20261001.md` rather than faked here.
#:
#: While it is `None`, a Cart V2 checkout answers `DELIVERY_DETAILS_REQUIRED`. That is deliberate
#: and it is the whole reason this is not a default value: the delivery address is the place of
#: supply, so a placeholder would produce a real total with the wrong CGST/SGST-versus-IGST split
#: on an invoice carrying seller GSTIN 19AAFFW7196L1Z8 -- and that total would be charged. An
#: honest refusal is the cheaper failure.
LOAD_OWNED_ADDRESS = None

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
    if explicit in ("create", "status", "prepare", "verify"):
        return explicit
    path = str(event.get("rawPath") or event.get("path") or "").lower()
    if path.endswith("/status"):
        return "status"
    if path.endswith("/prepare-checkout"):
        return "prepare"
    if path.endswith("/verify-callback"):
        return "verify"
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
        if action == "prepare":
            return _website_prepare(identity, body, origin)
        if action == "verify":
            return _website_verify(identity, body, origin)
        return _create(identity, body, origin)
    except customer_auth.CustomerNotAuthorized:
        # Same opaque 401 as unauthenticated, so the endpoint is not an IDOR oracle.
        return customer_auth.denied_response(event)
    except Exception as exc:  # noqa: BLE001
        logger.error(json.dumps({"event": "checkout_error",
                                 "action": action, "error": type(exc).__name__}))
        return cors_response(500, {"error": "INTERNAL_ERROR"}, origin)


def _checkout_profile(identity: customer_auth.CustomerIdentity) -> Optional[Dict[str, Any]]:
    """The verified CRM profile for this signed-in phone, or None.

    The lookup key comes from the proven session. A browser cannot choose a phone/customer id.
    A row written by customer-profile carries both checkoutCustomerId and emailVerifiedAt; both
    have to match before its name/email are allowed into Razorpay prefill.
    """
    try:
        response = _table(CONTACTS_TABLE).query(
            IndexName="phone-index",
            KeyConditionExpression=Key("phone").eq(identity.phone),
            Limit=5,
        )
    except Exception as error:  # noqa: BLE001
        logger.error(json.dumps({"event": "checkout_profile_lookup_failed",
                                 "error": type(error).__name__}))
        raise
    for item in response.get("Items") or []:
        if item.get("deletedAt") is not None:
            continue
        if str(item.get("checkoutCustomerId") or "") != identity.customer_id:
            continue
        if not item.get("emailVerifiedAt"):
            continue
        if not str(item.get("email") or "").strip():
            continue
        return item
    return None


def _website_snapshot(identity: customer_auth.CustomerIdentity, line_items: list,
                      now: int):
    """Build the server-authoritative website payment snapshot.

    Cart V2 uses its existing owned-cart producer. Until V2 has an owned delivery address loader,
    the deployed V1 branch is converted into the same immutable QuoteSnapshot using Wix's
    authoritative checkout total, then the one central convenience-fee calculator.
    """
    if cart_v2.is_enabled():
        snapshot, _ = _v2_snapshot(identity, line_items)
        return snapshot

    checkout = wix_ecom.create_checkout(line_items)
    currency = wix_ecom.checkout_currency(checkout)
    if currency != "INR":
        raise checkout_pricing.PricingError("only INR is supported")
    collection_paise = wix_ecom.authoritative_total_paise(checkout)
    quote = checkout_pricing.compute_quote(collection_paise, currency="INR")
    checkout_id = str(checkout.get("id") or "")
    if not checkout_id:
        raise checkout_pricing.PricingError("Wix checkout id missing")
    return checkout_pricing.build_snapshot(
        customer_id=identity.customer_id,
        cart_id=checkout_id,
        cart_revision=0,
        quote=quote,
        created_at=now,
        ttl_seconds=WEBSITE_SNAPSHOT_TTL_SECONDS,
        site=wix_ecom.WIX_SITE_ID,
        items=wix_ecom.line_item_summary(checkout),
        address=None,
        delivery=None,
    )


def _reserve_website_attempt(attempt: Dict[str, Any]) -> None:
    _attempts_table().put_item(
        Item=attempt,
        ConditionExpression="attribute_not_exists(paymentAttemptId)",
    )


def _attempt_for_gateway_order(gateway_order_id: str) -> Optional[Dict[str, Any]]:
    binding = order_keys.resolve_gateway_order(_keys_table(), gateway_order_id) or {}
    attempt_id = str(binding.get("paymentAttemptId") or "")
    if not attempt_id:
        return None
    return _attempts_table().get_item(
        Key={"paymentAttemptId": attempt_id}
    ).get("Item")


def _website_prepare(identity: customer_auth.CustomerIdentity, body: Dict[str, Any],
                     origin: str) -> Dict[str, Any]:
    line_items = body.get("lineItems")
    request_key = str(body.get("requestKey") or "").strip()
    if not isinstance(line_items, list) or not line_items:
        return cors_response(400, {"error": "LINE_ITEMS_REQUIRED"}, origin)
    if not request_key or len(request_key) > 80:
        return cors_response(400, {"error": "REQUEST_KEY_REQUIRED"}, origin)

    profile = _checkout_profile(identity)
    if not profile:
        return cors_response(409, {
            "error": "PROFILE_REQUIRED",
            "message": "Verify your email and save your checkout details first.",
        }, origin)

    now = int(time.time())
    try:
        snapshot = _website_snapshot(identity, line_items, now)
        prepared = website_checkout.prepare_checkout(
            customer_id=identity.customer_id,
            snapshot=snapshot,
            presented_snapshot_hash=snapshot.snapshot_hash,
            request_key=request_key,
            now=now,
            keys_table=_keys_table(),
            create_order=razorpay_orders.create_order,
            find_order_by_receipt=razorpay_orders.find_order_by_receipt,
            account_mode_of=razorpay_orders.account_mode,
            initiation_enabled=INITIATION_ENABLED,
            prefill={
                "name": str(profile.get("name") or "").strip(),
                "email": str(profile.get("email") or "").strip(),
                "contact": identity.phone,
            },
            configuration_name=website_checkout.CHECKOUT_MODE_WEBSITE,
            reserve_attempt=_reserve_website_attempt,
        )
    except purchase_intent.DeliveryDetailsRequired:
        return cors_response(409, {"error": "DELIVERY_DETAILS_REQUIRED"}, origin)
    except website_checkout.CheckoutRejected as exc:
        return cors_response(409, {
            "status": website_checkout.CHECKOUT_REJECTED,
            "reason": exc.reason,
        }, origin)
    except (checkout_pricing.PricingError, wix_ecom.AmountNotWhole):
        return cors_response(409, {"error": "AMOUNT_NOT_SETTLED"}, origin)
    except wix_ecom.WixEcomError:
        return cors_response(502, {"error": "CATALOGUE_UNAVAILABLE"}, origin)
    except Exception as error:  # noqa: BLE001
        logger.error(json.dumps({"event": "website_checkout_prepare_failed",
                                 "error": type(error).__name__}))
        return cors_response(503, {"error": "TEMPORARILY_UNAVAILABLE"}, origin)

    payload: Dict[str, Any] = {
        "status": prepared.status,
        "paymentAttemptId": prepared.payment_attempt_id,
    }
    if prepared.options:
        payload["options"] = prepared.options
    if prepared.reason:
        payload["reason"] = prepared.reason
    status_code = 200 if prepared.status in (
        website_checkout.PAYMENT_INITIATION_DISABLED,
        website_checkout.CHECKOUT_OPTIONS_READY,
        website_checkout.CHECKOUT_AMBIGUOUS,
    ) else 409
    return cors_response(status_code, payload, origin)


def _website_verify(identity: customer_auth.CustomerIdentity, body: Dict[str, Any],
                    origin: str) -> Dict[str, Any]:
    order_id = str(body.get("razorpay_order_id") or "").strip()
    payment_id = str(body.get("razorpay_payment_id") or "").strip()
    signature = str(body.get("razorpay_signature") or "").strip()
    if not order_id or not payment_id or not signature:
        return cors_response(400, {"error": "CALLBACK_FIELDS_REQUIRED"}, origin)

    try:
        attempt = _attempt_for_gateway_order(order_id)
        owned = customer_auth.authorize_resource(identity, attempt, owner_field="customerId")
        verify_capture = razorpay_verify.verifier_for_event(
            payment_id=payment_id,
            order_id=order_id,
            load_attempt=lambda ref: _attempt_for_gateway_order(ref),
        )
        result = website_checkout.verify_callback(
            customer_id=identity.customer_id,
            presented_order_id=order_id,
            payment_id=payment_id,
            signature=signature,
            keys_table=_keys_table(),
            verify_signature=razorpay_orders.verify_checkout_signature,
            verify_capture=verify_capture,
            account_mode_of=razorpay_orders.account_mode,
        )
    except customer_auth.CustomerNotAuthorized:
        raise
    except Exception as error:  # noqa: BLE001
        logger.error(json.dumps({"event": "website_checkout_verify_failed",
                                 "error": type(error).__name__}))
        return cors_response(503, {"error": "TEMPORARILY_UNAVAILABLE"}, origin)

    if result.status == website_checkout.CALLBACK_VERIFIED_PAID:
        # The authoritative capture has been proven. Persist the provider binding + paid state so
        # status survives a lost browser response; the webhook still owns downstream order
        # reconciliation and is safe to replay against this monotonic state.
        advanced = payment_attempt.transition(
            owned,
            payment_attempt.PAYMENT_PAID,
            provider_payment_id=result.payment_id,
            provider_order_id=result.gateway_order_id,
        )
        try:
            _attempts_table().update_item(
                Key={"paymentAttemptId": result.payment_attempt_id},
                UpdateExpression=(
                    "SET #s=:s, attemptRank=:rank, paidAt=if_not_exists(paidAt,:paid), "
                    "updatedAt=:u, providerPaymentId=:pid, providerOrderId=:oid"
                ),
                ConditionExpression=payment_attempt.condition_expression(),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": advanced["status"],
                    ":rank": advanced[payment_attempt.RANK_ATTRIBUTE],
                    ":paid": advanced["paidAt"],
                    ":u": advanced["updatedAt"],
                    ":pid": result.payment_id,
                    ":oid": result.gateway_order_id,
                },
            )
        except Exception as error:  # noqa: BLE001
            logger.error(json.dumps({"event": "website_checkout_paid_persist_failed",
                                     "error": type(error).__name__}))
            return cors_response(503, {"error": "TEMPORARILY_UNAVAILABLE"}, origin)

    return cors_response(200, {
        "status": result.status,
        "paymentAttemptId": result.payment_attempt_id,
    }, origin)


def _wix_request(endpoint: str, method: str = "GET",
                 body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Transport for the Cart V2 adapter, delegating to `wix_ecom`'s authenticated client.

    `wix_ecom._request` already owns the credential (read by reference from Secrets Manager,
    lazily, at request time) and the site header. Reusing it keeps one authenticated client in
    this package rather than giving Cart V2 a second one that would need its own lazy-read
    discipline to stay rotation-safe.
    """
    return wix_ecom._request(endpoint, method=method, body=body)


def _v2_catalog_items(line_items: list) -> list:
    """Bridge the browser's `{catalogReference, quantity}` shape to Cart V2's catalog items.

    `cart_v2.catalog_item` demands exactly `{productId, variantId, quantity}` with both ids as
    UUIDs, while the browser sends a nested `catalogReference` and may omit the variant.
    Resolving a product's single visible, in-stock variant against the live catalogue -- and
    refusing to guess when there is more than one -- is work `wix_ecom.normalized_catalog_items`
    already does correctly, so this reuses it rather than growing a second copy that could
    disagree about which variant a cart line means.
    """
    return [{"productId": line["catalogReference"]["catalogItemId"],
             "variantId": line["catalogReference"]["options"]["variantId"],
             "quantity": line["quantity"]}
            for line in wix_ecom.normalized_catalog_items(line_items)]


def _require_same_basket(cart: Dict[str, Any], requested: list) -> None:
    """Refuse when the customer's saved cart is not the basket this request asked to price.

    Reusing the saved cart is what keeps one purchase to one cart, but the cart is maintained by
    the `/wix-store/cart` route, so it can legitimately hold something else by the time checkout
    is pressed -- a second tab, another device, an edit made after this page loaded. Pricing it
    anyway would charge for a basket the customer is not looking at, which is worse than asking
    them to review it.

    Quantities are compared on `requestedQuantity`, never `confirmedQuantity`: Wix reduces the
    confirmed figure to available stock, and reporting that reduction is `CartQuantityReduced`'s
    job. Reading it here would turn an out-of-stock item into "your cart changed".
    """
    asked: Dict[tuple, int] = {}
    for item in requested:
        key = (str(item["productId"]).lower(), str(item["variantId"]).lower())
        asked[key] = asked.get(key, 0) + int(item["quantity"])
    saved: Dict[tuple, int] = {}
    for line in cart.get("lineItems") or []:
        reference = (line.get("source") or {}).get("catalogReference") or {}
        quantities = line.get("quantityInfo") or {}
        key = (str(reference.get("catalogItemId") or "").lower(),
               str((reference.get("options") or {}).get("variantId") or "").lower())
        quantity = quantities.get("requestedQuantity")
        if quantity is None:
            quantity = quantities.get("confirmedQuantity")
        saved[key] = saved.get(key, 0) + int(quantity or 0)
    if saved != asked:
        logger.info(json.dumps({"event": "checkout_cart_basket_mismatch",
                                "savedLines": len(saved), "requestedLines": len(asked)}))
        raise cart_v2.CartContractError("the saved cart is not the basket that was requested")


def _v2_snapshot(identity: customer_auth.CustomerIdentity, line_items: list):
    """The Cart V2 price authority. Returns `(snapshot, price_free_items)`.

    This is the producer half of the chain `website_checkout` and `customer_receipt` already
    consume, and which nothing in production produced before. `QuoteSnapshot.quote`'s
    `collection_before_convenience_paise` is Wix's own `summary.priceSummary.total` -- items,
    discounts, delivery and supply GST, all computed by Wix from the catalogue and the delivery
    address. This handler adds nothing to that figure; `compute_quote` adds only our convenience
    fee and the GST on that fee, and `total_payable_paise` is what a customer pays.

    ORDERING IS LOAD-BEARING, NOT STYLE. The owned address is resolved BEFORE any call that can
    write to Wix. A cart created and then refused is a real cart abandoned on the live site, one
    per attempt, and nothing deletes it; an earlier revision created the cart first and then
    discovered there was no address, so every attempt leaked one. A request that cannot be priced
    must be refused before it leaves anything behind.

    The cart itself is resolved before it is generated. `customer_cart` already owns identity-keyed
    cart persistence and its lock protocol, so this asks it for the customer's existing cart and
    lets it create one only when there is none -- a retried checkout then reuses the same Wix cart
    instead of minting another.

    Raises `purchase_intent.DeliveryDetailsRequired` when no owned address is on file or the cart
    has no delivery method, which is a recoverable step in the purchase flow rather than an
    error.
    """
    loader = LOAD_OWNED_ADDRESS
    owned = loader(identity.customer_id) if callable(loader) else None
    if not owned:
        raise purchase_intent.DeliveryDetailsRequired("no owned delivery address on file")

    adapter = cart_v2.CartV2(_wix_request)
    requested = _v2_catalog_items(line_items)
    cart_id, created = customer_cart.CustomerCart(_keys_table(), adapter).ensure(
        identity, requested)
    if not created:
        _require_same_basket(adapter.get(cart_id), requested)

    prepared = purchase_intent.prepare_delivery(adapter, cart_id, owned)
    snapshot = purchase_intent.build_intent(
        adapter, customer_id=identity.customer_id, cart_id=cart_id,
        owned_address=owned, now=int(time.time()), site=wix_ecom.WIX_SITE_ID)
    # Names and quantities only, for the payment request and the receipt. Line money never
    # travels with the item list: the authoritative amount is the one computed once, above, and
    # the snapshot hash already covers the per-line figures Wix calculated.
    items = [{"name": _translatable(line.get("name")),
              "quantity": int((line.get("quantityInfo") or {}).get("confirmedQuantity") or 1)}
             for line in (prepared.get("lineItems") or [])]
    return snapshot, items


def _translatable(value: Any) -> str:
    """Cart V2 renamed `lineItems[].productName` to `name` and changed it to a translatable
    string, so a plain `str()` would render a dict. Original preferred over translated, matching
    `wix_ecom.line_item_summary`'s existing behaviour on the V1 shape."""
    if isinstance(value, dict):
        return str(value.get("original") or value.get("translated") or "")
    return str(value or "")


def _create(identity: customer_auth.CustomerIdentity, body: Dict[str, Any],
            origin: str) -> Dict[str, Any]:
    """Resolve authoritative totals, gate on readiness, reserve an attempt, hand off to WhatsApp."""
    line_items = body.get("lineItems")
    if not isinstance(line_items, list) or not line_items:
        return cors_response(400, {"error": "LINE_ITEMS_REQUIRED",
                                   "message": "Your cart is empty."}, origin)

    # 1. Authoritative total, from Wix. The browser sent catalogue references and quantities;
    #    Wix computes the price. A non-INR or non-whole-paise total fails closed.
    #
    #    Checkout V1 is what serves: Cart V2 is opt-in behind `WIX_CART_V2_ENABLED`
    #    (`cart_v2.is_enabled`), which is absent on every function, so absence keeps V1. Both are
    #    the SAME checkout mode -- website Razorpay Standard Checkout -- differing only in which
    #    Wix API prices the cart. Neither routes a customer to a Wix-hosted checkout surface.
    wix_checkout_id = ""
    snapshot = None
    if cart_v2.is_enabled():
        try:
            snapshot, item_summary = _v2_snapshot(identity, line_items)
            # The amount a customer pays is the CALCULATOR total -- Wix's collection total plus
            # our convenience fee plus the GST on that fee -- not the raw Wix total. That is the
            # contract section 8 of this module's docstring states for the website path, and
            # before the Cart V2 producer existed there was no code path that honoured it.
            amount_paise = snapshot.quote.total_payable_paise
        except purchase_intent.DeliveryDetailsRequired:
            # Not an error. The customer has not chosen where this is going, and Cart V2 is right
            # to refuse a price for an unknown destination: delivery is a component of the total
            # and the address is the place of supply. Never substitute a default address.
            logger.info(json.dumps({"event": "checkout_delivery_details_required"}))
            return cors_response(409, {
                "error": "DELIVERY_DETAILS_REQUIRED",
                "message": "Choose a delivery address and method to see your final total.",
            }, origin)
        except cart_v2.CartItemUnavailable as unavailable:
            # Checkout V1 dropped a missing item and priced what was left, so a cart could shrink
            # silently between review and payment. Named per line so the customer can act, and the
            # line ids and statuses are safe to return: they are opaque and carry no personal data.
            logger.info(json.dumps({"event": "checkout_item_unavailable",
                                    "count": len(unavailable.items)}))
            return cors_response(409, {
                "error": "ITEMS_UNAVAILABLE", "items": unavailable.items,
                "message": "Some items are no longer available. Please review your cart.",
            }, origin)
        except cart_v2.CartQuantityReduced as reduced:
            # Wix still auto-reduces `confirmedQuantity` to available stock in V2, and it prices the
            # reduced amount -- so the money reconciles perfectly while being the total for goods
            # the customer did not agree to buy. Refused and shown, never silently accepted.
            logger.info(json.dumps({"event": "checkout_quantity_reduced",
                                    "count": len(reduced.items)}))
            return cors_response(409, {
                "error": "QUANTITY_REDUCED", "items": reduced.items,
                "message": "Some items are available in smaller quantities than you asked for. "
                           "Please confirm the new amounts.",
            }, origin)
        except cart_v2.CartContractError:
            return cors_response(409, {"error": "CART_NOT_PAYABLE",
                                       "message": "Please review your cart and try again."},
                                 origin)
        except customer_cart.CartBusy:
            # A cart whose last Wix outcome is unknown. Never priced and never reused until it is
            # reconciled -- the same answer `/wix-store/cart` gives, in the same vocabulary, so a
            # locked cart does not read as two different problems on two routes.
            logger.info(json.dumps({"event": "checkout_cart_reconciliation_required"}))
            return cors_response(409, {
                "error": "CART_RECONCILIATION_REQUIRED",
                "message": "Your cart is being updated. Please try again shortly.",
            }, origin)
        except wix_ecom.WixEcomError:
            return cors_response(502, {"error": "CATALOGUE_UNAVAILABLE",
                                       "message": "The store is temporarily unavailable."}, origin)
        except ValueError:
            return cors_response(409, {"error": "AMOUNT_NOT_SETTLED",
                                       "message": "We could not price this cart. Please try "
                                                  "again."}, origin)
    else:
        try:
            checkout = wix_ecom.create_checkout(line_items)
            currency = wix_ecom.checkout_currency(checkout)
            if currency != "INR":
                logger.warning(json.dumps({"event": "checkout_non_inr", "currency": currency}))
                return cors_response(409, {"error": "UNSUPPORTED_CURRENCY"}, origin)
            amount_paise = wix_ecom.authoritative_total_paise(checkout)
        except wix_ecom.AmountNotWhole:
            return cors_response(409, {"error": "AMOUNT_NOT_SETTLED",
                                       "message": "We could not price this cart. Please try "
                                                  "again."},
                                 origin)
        except wix_ecom.WixEcomError:
            return cors_response(502, {"error": "CATALOGUE_UNAVAILABLE",
                                       "message": "The store is temporarily unavailable."}, origin)
        # Retained only on the V1 branch. In Cart V2 the cart id IS the checkout id, so a
        # separate `wixCheckoutId` has nothing to identify.
        wix_checkout_id = str(checkout.get("id") or "")
        item_summary = wix_ecom.line_item_summary(checkout)

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
        extra = {"customerId": identity.customer_id,
                 "amountPaise": amount_paise, "currency": "INR",
                 "wixCheckoutId": wix_checkout_id, "checkoutMode": CHECKOUT_MODE}
        if snapshot is not None:
            # The Cart V2 join keys. `wixCartId` + `cartRevision` is what reconciliation matches
            # on, and `quoteHash` is what proves the paid amount is the one the customer
            # reviewed -- a cart edit produces a different hash rather than mutating this one.
            # `collectionPaise` is recorded beside the payable amount so the convenience fee and
            # its GST stay auditable instead of being inferred from a difference.
            extra.update(wixCartId=snapshot.cart_id, cartRevision=snapshot.cart_revision,
                         quoteHash=snapshot.snapshot_hash,
                         collectionPaise=snapshot.quote.collection_before_convenience_paise,
                         quoteExpiresAt=snapshot.expires_at,
                         policyVersion=snapshot.policy_version)
        reference_id = order_keys.allocate_payment_reference(
            _keys_table(), payment_attempt_id=attempt_id, extra=extra,
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
        items=item_summary)
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
