"""Section 8 website Razorpay Standard Checkout: the order-create and callback-verify logic.

The two coexisting flows, and why this is additive
--------------------------------------------------
`ecommerce/checkout/handler.py` already implements an IN-WHATSAPP Meta/Razorpay flow that reserves
a reference, gates on Meta payment readiness and (when initiation is enabled) sends an in-chat
`order_details` message, returning `PAYMENT_REQUEST_SENT`. That path is RETAINED — callers still
consume `PAYMENT_REQUEST_SENT` — and must not be removed until they are migrated.

This module is the WEBSITE path section 8 asks for: a hosted browser Razorpay Standard Checkout
modal. It is ADDITIVE and lives behind the SAME disabled initiation gate (`CHECKOUT_INITIATION_ENABLED`,
default off), so turning nothing on creates no payable gateway order. It is written handler-free —
every external dependency (the keys table, the quote loader, the Razorpay client) is injected — so
it is fully testable offline with the same `FakeDynamo` the other payment tests use.

What `prepare_checkout` guarantees before it ever calls Razorpay
----------------------------------------------------------------
1. Session/profile/cart/quote ownership. The caller passes a proven `customer_id`; the snapshot's
   `customer_id` must equal it, and the client-presented snapshot hash must `matches()` the
   immutable FEAT-001 snapshot. An expired snapshot is refused.
2. The amount is the FEAT-001 CALCULATOR total (`quote.as_payable_money()`), not the raw Wix
   total — a zero-total quote is not payable and never reaches the gateway.
3. INR only, and the account mode is derived from the live key id and persisted on the binding.
4. A customer-scoped request key is reserved BEFORE the external call. Same key + same intent
   resumes onto the one order already created (concurrent clicks coordinate); same key + CHANGED
   intent is rejected.
5. The initiation gate. Off (the default) -> `PAYMENT_INITIATION_DISABLED`, no gateway order, no
   payable attempt.

Only then does it create the Razorpay order, persist the id/account/mode/amount binding BEFORE
exposing options, and return ONLY the public key id, the stored gateway order id, the approved
amount/currency, the allowed prefill and the owned attempt reference.

Ambiguity, not a licence to double-charge
-----------------------------------------
If the order-create times out, or the create may have landed but the binding could not be saved,
the provider client raises `RazorpayUnavailable`. This module does NOT create a second payable
order. It uses the documented receipt-correlation lookup to discover whether the first create
landed, binds to it if so, and otherwise reports an ambiguous-pending state for reconciliation. It
never assumes an undocumented Orders-API idempotency.

What `verify_callback` guarantees
---------------------------------
The browser relays `razorpay_payment_id|razorpay_order_id|razorpay_signature`. This verifies the
HMAC using the SERVER-STORED gateway order id (never the browser's), rejects a result whose stored
order/account/amount/currency do not match the binding, and — crucially — treats a valid signature
as only a trigger: it STILL requires `razorpay_verify`'s authenticated captured-payment readback
before returning a paid state. Cart/resume data is kept until that verified-paid finalization.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from lambda_utils.ecommerce import order_keys, payment_attempt
from lambda_utils.ecommerce.checkout_pricing import QuoteSnapshot

logger = logging.getLogger(__name__)

#: Checkout mode marker, distinguishing the website path from the retained in-WhatsApp one.
CHECKOUT_MODE_WEBSITE = "WEBSITE_RAZORPAY_STANDARD"

# ── outcome states (the documented website contract, replacing PAYMENT_REQUEST_SENT) ──
#: Initiation gate is off: everything up to the external call ran, but no gateway order was
#: created and no payable attempt exists. The website equivalent of the in-chat
#: `PAYMENT_INITIATION_DISABLED`.
PAYMENT_INITIATION_DISABLED = "PAYMENT_INITIATION_DISABLED"
#: A gateway order exists and the browser may open Standard Checkout. Carries only the public,
#: owner-approved fields.
CHECKOUT_OPTIONS_READY = "CHECKOUT_OPTIONS_READY"
#: Ownership, snapshot or intent did not hold. No order was created.
CHECKOUT_REJECTED = "CHECKOUT_REJECTED"
#: The provider create was ambiguous (timeout / save failure) and correlation could not confirm a
#: landed order. For reconciliation; NEVER a second payable create.
CHECKOUT_AMBIGUOUS = "CHECKOUT_AMBIGUOUS"

#: Callback outcomes.
CALLBACK_VERIFIED_PAID = "VERIFIED_PAID"
CALLBACK_SIGNATURE_INVALID = "SIGNATURE_INVALID"
CALLBACK_BINDING_MISMATCH = "BINDING_MISMATCH"
CALLBACK_NOT_CAPTURED = "NOT_CAPTURED"


class CheckoutRejected(Exception):
    """A pre-create guard failed. Carries a stable `reason` code; never a provider/body string."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class PreparedCheckout:
    """The result of `prepare_checkout`. Only the browser-safe projection is in `options`."""

    status: str
    payment_attempt_id: str = ""
    gateway_order_id: str = ""
    options: Optional[Dict[str, Any]] = None
    reason: str = ""


def intent_fingerprint(snapshot: QuoteSnapshot) -> str:
    """A stable fingerprint of the purchase intent, for request-key coordination.

    Covers exactly what must not change silently between two clicks: the customer, the cart and
    its revision, the immutable snapshot hash, the payable total and the currency. A changed cart
    produces a new snapshot hash, which changes this fingerprint, which is how a resumed request
    key with a different intent is detected and refused. SHA-256 over a canonical string.
    """
    quote = snapshot.quote
    material = "|".join([
        snapshot.customer_id,
        snapshot.cart_id,
        str(snapshot.cart_revision),
        snapshot.snapshot_hash,
        str(quote.total_payable_paise),
        quote.currency,
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _browser_options(*, key_id: str, gateway_order_id: str, amount_paise: int,
                     currency: str, prefill: Mapping[str, Any],
                     payment_attempt_id: str) -> Dict[str, Any]:
    """Exactly the fields the browser is allowed to receive. Nothing else.

    No secret, no raw Wix total, no customer id, no full binding. The prefill is restricted to the
    name/email/contact Razorpay's checkout documents, and only values the caller passed through
    from the proven session/profile.
    """
    allowed_prefill = {}
    for field in ("name", "email", "contact"):
        value = prefill.get(field) if isinstance(prefill, Mapping) else None
        if value:
            allowed_prefill[field] = value
    return {
        "keyId": key_id,
        "orderId": gateway_order_id,
        "amountPaise": int(amount_paise),
        "currency": currency,
        "prefill": allowed_prefill,
        "paymentAttemptId": payment_attempt_id,
    }


def prepare_checkout(*,
                     customer_id: str,
                     snapshot: QuoteSnapshot,
                     presented_snapshot_hash: str,
                     request_key: str,
                     now: int,
                     keys_table: Any,
                     create_order: Callable[..., Dict[str, Any]],
                     find_order_by_receipt: Callable[[str], Optional[Dict[str, Any]]],
                     account_mode_of: Callable[[str], str],
                     initiation_enabled: bool,
                     prefill: Optional[Mapping[str, Any]] = None,
                     configuration_name: str = CHECKOUT_MODE_WEBSITE,
                     reserve_attempt: Optional[Callable[[Dict[str, Any]], None]] = None,
                     ) -> PreparedCheckout:
    """Run every pre-create guard, then (only if enabled) create and bind the gateway order.

    The Razorpay client is injected as `create_order`/`find_order_by_receipt`/`account_mode_of`
    so this is testable with mocks exactly as the other payment tests mock the provider. The
    attempt store is `keys_table` plus an optional `reserve_attempt` sink for the PaymentAttempt
    record (the handler supplies the conditional put; tests may omit it).
    """
    prefill = prefill or {}

    # 1. Ownership + immutable snapshot. The snapshot is the customer's; the browser-presented hash
    #    must match it; it must not be expired. Any failure rejects WITHOUT creating anything.
    if not customer_id or snapshot.customer_id != customer_id:
        raise CheckoutRejected("OWNERSHIP")
    if not snapshot.matches(presented_snapshot_hash):
        raise CheckoutRejected("SNAPSHOT_MISMATCH")
    if snapshot.is_expired(now):
        raise CheckoutRejected("SNAPSHOT_EXPIRED")

    quote = snapshot.quote
    if quote.currency != "INR":
        raise CheckoutRejected("UNSUPPORTED_CURRENCY")
    # 2. The amount is the FEAT-001 calculator total. `as_payable_money` raises for a zero total,
    #    so a non-payable quote never reaches the gateway.
    if not quote.is_payable:
        raise CheckoutRejected("NOT_PAYABLE")
    payable = quote.as_payable_money()
    amount_paise = payable.paise

    fingerprint = intent_fingerprint(snapshot)

    # 3. Reserve the customer-scoped request key BEFORE any external call. Coordinate concurrent
    #    clicks and reject a changed intent on a resumed key.
    attempt_id = payment_attempt.new_payment_attempt_id()
    reservation, won = order_keys.reserve_checkout_request_key(
        keys_table, customer_id=customer_id, request_key=request_key,
        intent_fingerprint=fingerprint, payment_attempt_id=attempt_id,
        extra={"snapshotHash": snapshot.snapshot_hash, "amountPaise": amount_paise},
    )
    if not won:
        # A prior click reserved this key. Same intent -> resume; changed intent -> reject.
        if str(reservation.get("intentFingerprint") or "") != fingerprint:
            raise CheckoutRejected("INTENT_CHANGED")
        attempt_id = str(reservation.get("paymentAttemptId") or attempt_id)
        existing_order_id = str(reservation.get("gatewayOrderId") or "")
        if existing_order_id:
            # The order was already created on an earlier click; resume onto it rather than make
            # a second payable order.
            binding = order_keys.resolve_gateway_order(keys_table, existing_order_id) or {}
            return _ready_from_binding(binding, prefill, create_key_id=binding.get("accountKeyId"))

    # 4. The initiation gate. Off (default): no gateway order, no payable attempt. We have already
    #    reserved the request key, which is harmless (it carries no money and no order).
    if not initiation_enabled:
        logger.info('{"event":"website_checkout_initiation_disabled"}')
        return PreparedCheckout(
            status=PAYMENT_INITIATION_DISABLED,
            payment_attempt_id=attempt_id,
        )

    # 5. Create the gateway order. The receipt is the request key, which is unique to this attempt
    #    and is what the ambiguity-recovery lookup correlates on.
    receipt = f"wk_{request_key}"[:order_keys.RAZORPAY_RECEIPT_MAX_LENGTH]
    try:
        order = create_order(
            amount_paise=amount_paise, receipt=receipt,
            notes={"paymentAttemptId": attempt_id, "customerId": customer_id,
                   "snapshotHash": snapshot.snapshot_hash},
        )
    except Exception as error:  # noqa: BLE001 - the provider client's RazorpayUnavailable, etc.
        return _recover_ambiguous_create(
            keys_table=keys_table, find_order_by_receipt=find_order_by_receipt,
            receipt=receipt, attempt_id=attempt_id, request_key=request_key,
            amount_paise=amount_paise, currency="INR", account_mode_of=account_mode_of,
            prefill=prefill, error=error, reserve_attempt=reserve_attempt,
        )

    return _bind_and_ready(
        keys_table=keys_table, order=order, attempt_id=attempt_id, request_key=request_key,
        amount_paise=amount_paise, currency="INR", account_mode_of=account_mode_of,
        prefill=prefill, reserve_attempt=reserve_attempt, customer_id=customer_id,
        configuration_name=configuration_name,
    )


def _bind_and_ready(*, keys_table, order, attempt_id, request_key, amount_paise, currency,
                    account_mode_of, prefill, reserve_attempt, customer_id,
                    configuration_name) -> PreparedCheckout:
    gateway_order_id = str(order.get("id") or "")
    key_id = str(order.get("key_id") or "")
    if not gateway_order_id or not key_id:
        # A create that returned no id/key is as ambiguous as a timeout: do not expose options,
        # and do not create a second order.
        raise CheckoutRejected("PROVIDER_INCOMPLETE")

    mode = account_mode_of(key_id)
    try:
        order_keys.bind_gateway_order(
            keys_table, gateway_order_id=gateway_order_id, payment_attempt_id=attempt_id,
            request_key=request_key, amount_paise=amount_paise, account_key_id=key_id,
            account_mode=mode, currency=currency,
        )
    except order_keys.OrderIdentityUnavailable:
        # The order may exist on Razorpay's side but we could not persist the binding: AMBIGUOUS.
        # We cannot expose options without a stored binding to verify a callback against, and we
        # must not create a second order. Report ambiguous for reconciliation via the receipt.
        return PreparedCheckout(status=CHECKOUT_AMBIGUOUS, payment_attempt_id=attempt_id,
                                gateway_order_id=gateway_order_id, reason="BINDING_SAVE_FAILED")

    # Link the request key to the created order so a concurrent/retried click resumes onto it.
    _link_request_key_to_order(keys_table, customer_id, request_key, gateway_order_id)

    if reserve_attempt is not None:
        attempt = payment_attempt.build(
            customer_id=customer_id, reference_id=gateway_order_id,
            amount_paise=amount_paise, configuration_name=configuration_name,
            payment_attempt_id=attempt_id,
        )
        attempt["checkoutMode"] = CHECKOUT_MODE_WEBSITE
        attempt["providerOrderId"] = gateway_order_id
        reserve_attempt(attempt)

    options = _browser_options(
        key_id=key_id, gateway_order_id=gateway_order_id, amount_paise=amount_paise,
        currency=currency, prefill=prefill, payment_attempt_id=attempt_id)
    return PreparedCheckout(status=CHECKOUT_OPTIONS_READY, payment_attempt_id=attempt_id,
                            gateway_order_id=gateway_order_id, options=options)


def _ready_from_binding(binding: Dict[str, Any], prefill, *, create_key_id) -> PreparedCheckout:
    """Rebuild the ready response from a stored binding (a resumed click)."""
    gateway_order_id = str(binding.get("gatewayOrderId") or "")
    attempt_id = str(binding.get("paymentAttemptId") or "")
    key_id = str(binding.get("accountKeyId") or create_key_id or "")
    options = _browser_options(
        key_id=key_id, gateway_order_id=gateway_order_id,
        amount_paise=int(binding.get("amountPaise") or 0),
        currency=str(binding.get("currency") or "INR"), prefill=prefill,
        payment_attempt_id=attempt_id)
    return PreparedCheckout(status=CHECKOUT_OPTIONS_READY, payment_attempt_id=attempt_id,
                            gateway_order_id=gateway_order_id, options=options)


def _link_request_key_to_order(keys_table, customer_id, request_key, gateway_order_id) -> None:
    """Best-effort: record the created order id on the request-key row for resume.

    A failure here does not undo the created order or its binding; a resumed click simply falls
    back to the ambiguity-correlation path keyed on the receipt. Never raises into the caller.
    """
    key = order_keys.REQUEST_KEY_PREFIX + customer_id + "#" + request_key
    try:
        keys_table.update_item(
            Key={"orderId": key},
            UpdateExpression="SET gatewayOrderId = :g",
            ConditionExpression="attribute_exists(orderId)",
            ExpressionAttributeValues={":g": gateway_order_id},
        )
    except Exception as error:  # noqa: BLE001
        logger.info('{"event":"website_checkout_requestkey_link_skipped","error":"%s"}',
                    type(error).__name__)


def _recover_ambiguous_create(*, keys_table, find_order_by_receipt, receipt, attempt_id,
                              request_key, amount_paise, currency, account_mode_of, prefill,
                              error, reserve_attempt) -> PreparedCheckout:
    """A create raised. Correlate by receipt; NEVER blindly create a second payable order."""
    logger.warning('{"event":"website_checkout_create_ambiguous","error":"%s"}',
                   type(error).__name__)
    try:
        landed = find_order_by_receipt(receipt)
    except Exception as lookup_error:  # noqa: BLE001 - lookup itself unreachable
        logger.warning('{"event":"website_checkout_correlation_unreachable","error":"%s"}',
                       type(lookup_error).__name__)
        landed = None
    if landed and str(landed.get("id") or ""):
        # The first create DID land. Bind to it and expose options; no second order is created.
        return _bind_and_ready(
            keys_table=keys_table, order=landed, attempt_id=attempt_id, request_key=request_key,
            amount_paise=amount_paise, currency=currency, account_mode_of=account_mode_of,
            prefill=prefill, reserve_attempt=reserve_attempt,
            customer_id=str(landed.get("notes", {}).get("customerId") or ""),
            configuration_name=CHECKOUT_MODE_WEBSITE,
        )
    # Could not confirm a landed order. Report ambiguous-pending for reconciliation.
    return PreparedCheckout(status=CHECKOUT_AMBIGUOUS, payment_attempt_id=attempt_id,
                            reason="CREATE_UNCONFIRMED")


# ── the browser-result callback ────────────────────────────────────────────────

@dataclass(frozen=True)
class CallbackResult:
    status: str
    payment_attempt_id: str = ""
    gateway_order_id: str = ""
    payment_id: str = ""
    amount_paise: int = 0
    currency: str = ""


def verify_callback(*,
                    customer_id: str,
                    presented_order_id: str,
                    payment_id: str,
                    signature: str,
                    keys_table: Any,
                    verify_signature: Callable[..., bool],
                    verify_capture: Callable[[str], Tuple[bool, str, int, str]],
                    ) -> CallbackResult:
    """Verify a browser Standard Checkout result against the SERVER-STORED binding, then capture.

    `verify_signature(stored_order_id, payment_id, signature)` is the injected HMAC check (over the
    STORED order id). `verify_capture(reference_id)` is `razorpay_verify.verifier_for_event`'s
    closure, which performs the authenticated captured-payment readback bound to the attempt.

    Order of checks, each load-bearing:
      - Resolve the binding by the stored gateway order id. An unknown order id is a mismatch.
      - Ownership: the attempt behind the binding must belong to this customer (checked by the
        caller via the attempt row; here we require the binding to resolve and carry the attempt).
      - HMAC over the STORED order id (never the browser's `presented_order_id`).
      - A valid signature is still only a trigger: require `verify_capture` to confirm a capture,
        and the captured amount/currency to equal the stored binding, before VERIFIED_PAID.
    """
    binding = order_keys.resolve_gateway_order(keys_table, presented_order_id)
    if not binding:
        return CallbackResult(status=CALLBACK_BINDING_MISMATCH)
    stored_order_id = str(binding.get("gatewayOrderId") or "")
    attempt_id = str(binding.get("paymentAttemptId") or "")
    stored_amount = int(binding.get("amountPaise") or 0)
    stored_currency = str(binding.get("currency") or "")

    # HMAC is computed over the STORED order id, not anything the browser relayed.
    if not verify_signature(stored_order_id=stored_order_id, payment_id=payment_id,
                            signature=signature):
        return CallbackResult(status=CALLBACK_SIGNATURE_INVALID,
                              payment_attempt_id=attempt_id, gateway_order_id=stored_order_id)

    # Signed success is only a trigger. Require an authenticated captured-payment readback.
    captured, provider_payment_id, amount_paise, currency = verify_capture(stored_order_id)
    if not captured:
        return CallbackResult(status=CALLBACK_NOT_CAPTURED,
                              payment_attempt_id=attempt_id, gateway_order_id=stored_order_id)
    if amount_paise != stored_amount or currency != stored_currency:
        # A capture for a different amount/currency than the one we bound must not settle.
        return CallbackResult(status=CALLBACK_BINDING_MISMATCH,
                              payment_attempt_id=attempt_id, gateway_order_id=stored_order_id)

    return CallbackResult(status=CALLBACK_VERIFIED_PAID, payment_attempt_id=attempt_id,
                          gateway_order_id=stored_order_id, payment_id=provider_payment_id,
                          amount_paise=amount_paise, currency=currency)


__all__ = [
    "CHECKOUT_MODE_WEBSITE",
    "PAYMENT_INITIATION_DISABLED",
    "CHECKOUT_OPTIONS_READY",
    "CHECKOUT_REJECTED",
    "CHECKOUT_AMBIGUOUS",
    "CALLBACK_VERIFIED_PAID",
    "CALLBACK_SIGNATURE_INVALID",
    "CALLBACK_BINDING_MISMATCH",
    "CALLBACK_NOT_CAPTURED",
    "CheckoutRejected",
    "PreparedCheckout",
    "CallbackResult",
    "intent_fingerprint",
    "prepare_checkout",
    "verify_callback",
]
