"""Payment-attempt identity before payment, order identity only after payment.

The rule this module enforces
-----------------------------
**An order does not exist until a payment has been authoritatively verified as paid.** A cart
is not an order, a checkout is not an order, and a payment attempt is not an order. So the
identifiers split in two, and the split is the whole point of this file:

    before payment      paymentAttemptId (UUIDv7)  +  Meta reference_id
    after PAID          orderId (UUIDv7)           +  orderNumber (12 chars, public)

Nothing here will mint an order number as a side effect of starting a payment. An earlier
version of this module did exactly that - `allocate_order_identity` bound a Meta reference to a
freshly reserved order number at payment-request time - and it is gone rather than deprecated,
because a deprecated function that reserves an order number is a function someone calls.

Why reference_id and orderNumber cannot be the same string
----------------------------------------------------------
Meta's Payments (India) reference requires `reference_id` to be at most **35 characters** drawn
from letters, numbers, underscores, dashes and dots. The legacy WD order number is 46
characters and contains spaces and colons, so deriving one from the other meant stripping and
then truncating - and truncating a join key is how two orders quietly become one payment. They
are different identifiers with different consumers:

    reference_id   machine join key. Meta, Razorpay and our reconciliation agree on it.
                   Unordered, minted from `secrets`, never shown to a customer.
    orderNumber    human display string. Read aloud on the phone, typed into a tracking box.
                   12 characters, unambiguous alphabet, and deliberately NOT time-ordered.

`orderNumber` uses an alphabet without `0 O 1 I L` because it gets read aloud. `paymentAttemptId`
and `orderId` are UUIDv7 and *are* time-ordered, which is safe precisely because they are
internal - a time-ordered public number would leak order volume.

The key space
-------------
Namespaced rows on one partition attribute. Nothing here may ever carry a TTL: a uniqueness
reservation that expires is an identifier that gets reissued, which defeats the entire purpose.
The table this writes to has TTL `DISABLED`; keep it that way.

    PAYREF#<referenceId>            -> paymentAttemptId      before payment
    PAYMENTATTEMPT#<attemptId>      -> orderId, orderNumber   after PAID, the idempotency anchor
    PROVIDERPAYMENT#<transactionId> -> orderId                after PAID, provider uniqueness
    ORDERNO#<orderNumber>           -> reservation            after PAID
    REFERENCE#<referenceId>          legacy, read-only compatibility

Ordering matters and is not arbitrary. `orderId` is minted locally and costs nothing, so it is
minted *first* and used to claim both post-paid markers. Only the claim winner then reserves an
order number. A loser therefore never burns a number, and a crash between claiming and reserving
is recoverable because re-entry resolves the same claim and finds the number missing.

Failure posture
---------------
Everything fails **closed**. A `ConditionalCheckFailedException` is a normal race and is retried
with a fresh candidate. Any other storage error raises `OrderIdentityUnavailable` and yields no
identifier, because an unreserved identifier handed to a caller is a duplicate waiting to happen.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
from typing import Any, Callable, Dict, Optional, Tuple

from lambda_utils.identifiers import new_uuid7

logger = logging.getLogger(__name__)

# ── Meta Payments (India) constraints ───────────────────────────────────────────
# Source: Meta for Developers, "Receive payments via payment gateways on WhatsApp",
# Parameters Object -> reference_id (updated 2026-05-21). Paraphrased: required, case
# sensitive, non-empty, only English letters, numbers, underscores, dashes or dots, and not
# more than 35 characters.
# https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/payments-in/pg
META_REFERENCE_ID_MAX_LENGTH = 35
_META_REFERENCE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,%d}$" % META_REFERENCE_ID_MAX_LENGTH)

#: Razorpay's `receipt` tolerates 40 characters, so a valid reference_id always fits.
RAZORPAY_RECEIPT_MAX_LENGTH = 40

# ── key prefixes ───────────────────────────────────────────────────────────────
PAYMENT_REFERENCE_PREFIX = "PAYREF#"
PAYMENT_ATTEMPT_PREFIX = "PAYMENTATTEMPT#"
PROVIDER_PAYMENT_PREFIX = "PROVIDERPAYMENT#"
ORDER_NUMBER_PREFIX = "ORDERNO#"

#: Superseded by PAYMENT_REFERENCE_PREFIX. Retained read-only so rows written before the
#: order-after-payment rule remain resolvable; nothing writes it.
LEGACY_REFERENCE_PREFIX = "REFERENCE#"

# ── reference_id minting ───────────────────────────────────────────────────────
REFERENCE_ID_PREFIX = "WD-PAY-"

#: Crockford-style base32 without I, L, O, U. Inside Meta's permitted charset.
_REFERENCE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

#: 14 symbols over 32 is 70 bits. The conditional write is what guarantees uniqueness; this
#: only has to make a collision rare enough that the retry loop is never the hot path.
_REFERENCE_ENTROPY_SYMBOLS = 14

# ── public order number ────────────────────────────────────────────────────────
#: Exactly 12 characters, uppercase, URL-safe.
PUBLIC_ORDER_NUMBER_LENGTH = 12

#: Deliberately excludes 0, O, 1, I and L. This number is read aloud to support and typed into
#: a tracking box, and those five characters are where transcription errors come from. 27
#: symbols over 12 positions is ~57 bits, which with a conditional write is ample.
PUBLIC_ORDER_NUMBER_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"

_PUBLIC_ORDER_NUMBER_RE = re.compile(
    r"^[%s]{%d}$" % (PUBLIC_ORDER_NUMBER_ALPHABET, PUBLIC_ORDER_NUMBER_LENGTH)
)

_DEFAULT_ATTEMPTS = 5

# Accepts both legacy spellings: the spaced display format the Wix sync path generates
# ('WD-ORD - A1B2C3D4 - ...') and the compact form the Order table's `orderId` uses
# ('WD-ORD-A1B2C3D4'). One pattern deliberately - the bug this replaced was a `startswith`
# that silently recognised only one of them. New checkout orders use the 12-character number
# instead; this stays for orders synced from Wix, which already exist and are already paid.
_WD_ORDER_NUMBER_RE = re.compile(r"^WD-ORD\s*-\s*[0-9A-F]{8}\b", re.IGNORECASE)


class OrderIdentityUnavailable(RuntimeError):
    """An identifier could not be durably reserved.

    Callers MUST propagate this. Falling back to an unreserved identifier is the defect this
    module exists to remove, so there is deliberately no "best effort" variant.
    """


def _is_conditional_failure(error: Exception) -> bool:
    """True for a losing conditional write, which is a race to retry, not an outage."""
    response = getattr(error, "response", None) or {}
    return response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


# ── validation ─────────────────────────────────────────────────────────────────

def is_valid_meta_reference_id(value: Any) -> bool:
    """True when `value` satisfies Meta's documented charset and 35-character limit."""
    return isinstance(value, str) and bool(_META_REFERENCE_ID_RE.match(value))


def assert_valid_meta_reference_id(value: Any) -> str:
    """Return `value` if Meta would accept it, else raise `ValueError`.

    Called before a send rather than after a rejection. An invalid `reference_id` surfaces at
    Meta as a generic failure that reads like an outage, and the customer simply cannot pay.

    Note what this deliberately does NOT do: truncate. The previous `_sanitize_reference_id`
    cut over-long values to 35 characters, which silently maps two distinct identifiers onto
    one and joins two orders to a single payment. Rejecting is the only safe response.
    """
    if not is_valid_meta_reference_id(value):
        raise ValueError(
            "reference_id must be 1-%d characters of [A-Za-z0-9._-] and is never truncated; "
            "got %r (length %d)"
            % (META_REFERENCE_ID_MAX_LENGTH, value,
               len(value) if isinstance(value, str) else -1)
        )
    return value


def is_public_order_number(value: Any) -> bool:
    """True for a 12-character public order number in the unambiguous alphabet."""
    return isinstance(value, str) and bool(_PUBLIC_ORDER_NUMBER_RE.match(value))


def is_wd_order_number(value: Any) -> bool:
    """True for a legacy WD order number in either live format.

    Replaces `startswith('WD-ORD-')`, which never matched the spaced format the generator
    actually produces and so made the reuse check dead code.
    """
    return isinstance(value, str) and bool(_WD_ORDER_NUMBER_RE.match(value.strip()))


# ── minting ────────────────────────────────────────────────────────────────────

def new_payment_attempt_id() -> str:
    """A fresh internal payment-attempt identifier. Never shown to a customer."""
    return new_uuid7()


def new_order_id() -> str:
    """A fresh internal order identifier.

    Minted locally and used to claim the post-paid markers, so it must cost nothing and touch
    no storage. Never derived from the public order number, and never the other way round.
    """
    return new_uuid7()


def mint_payment_reference(prefix: str = REFERENCE_ID_PREFIX,
                           symbols: int = _REFERENCE_ENTROPY_SYMBOLS) -> str:
    """Mint a fresh Meta-safe `reference_id` for one payment attempt.

    Uses `secrets`, never `random`: `random` is seeded per execution environment and a
    SnapStart snapshot freezes that seed, so every restored sandbox would replay the same
    sequence. SnapStart is off across the fleet today, but a payment join key is the last place
    to depend on that remaining true.
    """
    candidate = prefix + "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(symbols))
    return assert_valid_meta_reference_id(candidate)


def mint_public_order_number() -> str:
    """Mint a candidate 12-character public order number.

    Unordered and carrying no timestamp, unlike `orderId`. Two reasons: a time-ordered public
    number leaks order volume to anyone holding two of them, and a customer-facing number must
    not imply anything about when the business is busy. It encodes no phone number, no email
    and no customer id - it is 12 symbols of CSPRNG output and nothing else.

    A candidate is not an order number until `reserve_public_order_number` has committed it.
    """
    return "".join(
        secrets.choice(PUBLIC_ORDER_NUMBER_ALPHABET)
        for _ in range(PUBLIC_ORDER_NUMBER_LENGTH)
    )


#: Superseded name, kept so existing callers on the send path keep working.
mint_reference_id = mint_payment_reference


# ── reservation primitive ──────────────────────────────────────────────────────

def _claim_row(table: Any, key_attr: str, key: str,
               item: Dict[str, Any]) -> bool:
    """Conditionally write one reservation row. True if won, False if already taken.

    Raises `OrderIdentityUnavailable` on anything that is not a lost race, so a throttle or an
    outage can never be mistaken for "already claimed".
    """
    payload = dict(item)
    payload[key_attr] = key
    try:
        table.put_item(
            Item=payload,
            ConditionExpression="attribute_not_exists(%s)" % key_attr,
        )
        return True
    except Exception as error:  # noqa: BLE001 - re-raised below unless it is a lost race
        if _is_conditional_failure(error):
            return False
        raise OrderIdentityUnavailable(
            "could not claim %r: %s" % (key, type(error).__name__)
        ) from error


def _read_row(table: Any, key_attr: str, key: str) -> Optional[Dict[str, Any]]:
    """Read one reservation row, or None. Raises on a storage error.

    A read failure must not be reported as absence: callers treat absence as "no order exists
    for this reference", and a throttle answering "absent" would let a payment event be
    discarded as unknown.
    """
    try:
        return table.get_item(Key={key_attr: key}).get("Item")
    except Exception as error:  # noqa: BLE001
        raise OrderIdentityUnavailable(
            "could not read %r: %s" % (key, type(error).__name__)
        ) from error


# ── before payment: the payment reference ──────────────────────────────────────

def reserve_payment_reference(table: Any,
                              *,
                              reference_id: str,
                              payment_attempt_id: str,
                              key_attr: str = "orderId",
                              extra: Optional[Dict[str, Any]] = None) -> bool:
    """Bind `reference_id` to one payment attempt. True if claimed, False if already bound.

    Note what this row does NOT contain: an order, an order number, or any hint that one will
    exist. That is the order-after-payment rule expressed in the data rather than in a comment.
    """
    assert_valid_meta_reference_id(reference_id)
    if not payment_attempt_id:
        raise ValueError("payment_attempt_id is required")

    item = {
        "kind": "PAYMENT_REFERENCE",
        "referenceId": reference_id,
        "paymentAttemptId": payment_attempt_id,
        "reservedAt": int(time.time()),
    }
    if extra:
        item.update(extra)
    return _claim_row(
        table, key_attr, PAYMENT_REFERENCE_PREFIX + reference_id, item
    )


def resolve_payment_reference(table: Any, reference_id: str, *,
                              key_attr: str = "orderId") -> Optional[Dict[str, Any]]:
    """The payment-attempt row for `reference_id`, or None.

    None means **no payment attempt exists for this reference**. A payment event must not
    create one: an event naming an unknown reference is either a forgery or a lost write, and
    both call for staff attention rather than a new attempt.

    Falls back to the legacy `REFERENCE#` prefix so rows written before the split still
    resolve. Nothing writes that prefix any more.
    """
    if not reference_id:
        return None
    row = _read_row(table, key_attr, PAYMENT_REFERENCE_PREFIX + reference_id)
    if row is not None:
        return row
    return _read_row(table, key_attr, LEGACY_REFERENCE_PREFIX + reference_id)


def allocate_payment_reference(table: Any,
                               *,
                               payment_attempt_id: str,
                               key_attr: str = "orderId",
                               attempts: int = _DEFAULT_ATTEMPTS,
                               extra: Optional[Dict[str, Any]] = None) -> str:
    """Mint and durably bind a fresh reference for a payment attempt, or raise.

    Reserves before returning, so no caller can hold a reference that storage has not
    committed to. Creates **no order identity of any kind**.
    """
    for attempt in range(1, max(1, attempts) + 1):
        candidate = mint_payment_reference()
        if reserve_payment_reference(
            table, reference_id=candidate, payment_attempt_id=payment_attempt_id,
            key_attr=key_attr, extra=extra,
        ):
            return candidate
        logger.warning(
            "payment reference collision on attempt %d/%d; regenerating", attempt, attempts
        )
    raise OrderIdentityUnavailable(
        "exhausted %d attempts allocating a payment reference" % attempts
    )


# ── after PAID: order identity ─────────────────────────────────────────────────

def reserve_public_order_number(table: Any,
                                *,
                                order_id: str,
                                key_attr: str = "orderId",
                                generate: Optional[Callable[[], str]] = None,
                                attempts: int = _DEFAULT_ATTEMPTS,
                                extra: Optional[Dict[str, Any]] = None) -> str:
    """Generate and durably reserve a unique 12-character public order number, or raise.

    Call this only after a payment has been authoritatively verified as paid. The reservation
    row is written **before** the number is returned, so no caller can ever hold a number that
    storage has not committed to; that ordering is the whole contract.
    """
    generate = generate or mint_public_order_number
    now = int(time.time())

    for attempt in range(1, max(1, attempts) + 1):
        candidate = generate()
        item = {
            "kind": "ORDER_NUMBER_RESERVATION",
            "orderNumber": candidate,
            # `orderIdRef`, not `orderId`: on this table `orderId` IS the partition attribute,
            # so a business field of the same name would be overwritten by the key and the
            # link back to the order would vanish silently.
            "orderIdRef": order_id,
            "reservedAt": now,
        }
        if extra:
            item.update(extra)
        if _claim_row(table, key_attr, ORDER_NUMBER_PREFIX + candidate, item):
            return candidate
        logger.warning(
            "public order number collision on attempt %d/%d; regenerating",
            attempt, attempts,
        )

    raise OrderIdentityUnavailable(
        "exhausted %d attempts reserving a public order number" % attempts
    )


def claim_order_for_payment(table: Any,
                            *,
                            payment_attempt_id: str,
                            order_id: str,
                            provider_transaction_id: str = "",
                            key_attr: str = "orderId",
                            extra: Optional[Dict[str, Any]] = None
                            ) -> Tuple[str, bool]:
    """Claim the right to create exactly one order for one paid payment. Idempotent.

    Returns `(orderId, won)`. `won` is False when an order already exists, and the returned
    `orderId` is then the existing one - which is what makes a redelivered `payment.captured`,
    a concurrent reconciliation and a staff-triggered retry all converge on one order.

    Two markers, claimed in this order and for different reasons:

      `PROVIDERPAYMENT#<txn>`   one Razorpay payment may fund at most one order. Claimed
                                first, because it is the constraint an attacker or a provider
                                retry would attack.
      `PAYMENTATTEMPT#<id>`     one attempt yields at most one order. The anchor every
                                downstream step re-reads.

    Losing either claim returns the winner's `orderId` rather than raising, because two workers
    reconciling the same payment is expected, not exceptional.
    """
    if not payment_attempt_id:
        raise ValueError("payment_attempt_id is required")
    if not order_id:
        raise ValueError("order_id is required")

    now = int(time.time())
    base = {"orderIdRef": order_id, "claimedAt": now,
            "paymentAttemptId": payment_attempt_id}
    if extra:
        base.update(extra)

    if provider_transaction_id:
        item = dict(base, kind="PROVIDER_PAYMENT_CLAIM",
                    providerTransactionId=provider_transaction_id)
        if not _claim_row(table, key_attr,
                          PROVIDER_PAYMENT_PREFIX + provider_transaction_id, item):
            existing = _read_row(
                table, key_attr, PROVIDER_PAYMENT_PREFIX + provider_transaction_id
            ) or {}
            winner = existing.get("orderIdRef") or ""
            if not winner:
                raise OrderIdentityUnavailable(
                    "provider payment %r is claimed but names no order"
                    % provider_transaction_id
                )
            logger.warning("provider payment already funded an order; adopting it")
            return winner, False

    item = dict(base, kind="PAYMENT_ATTEMPT_ORDER")
    if _claim_row(table, key_attr,
                  PAYMENT_ATTEMPT_PREFIX + payment_attempt_id, item):
        return order_id, True

    existing = _read_row(
        table, key_attr, PAYMENT_ATTEMPT_PREFIX + payment_attempt_id
    ) or {}
    winner = existing.get("orderIdRef") or ""
    if not winner:
        raise OrderIdentityUnavailable(
            "payment attempt %r is claimed but names no order" % payment_attempt_id
        )
    return winner, False


def record_order_number_on_claim(table: Any,
                                 *,
                                 payment_attempt_id: str,
                                 order_number: str,
                                 key_attr: str = "orderId") -> None:
    """Write the reserved order number onto the attempt's claim row.

    Separate from `claim_order_for_payment` because the number does not exist yet at claim
    time, and that sequence is deliberate: the claim decides who may create the order, and only
    the winner then reserves a number, so a loser never burns one.

    The gap between the two is what makes re-entry necessary rather than optional - a crash in
    between leaves a claim with no number, and `resolve_order_for_payment` reports exactly that
    so the caller reserves one and calls this again.
    """
    if not is_public_order_number(order_number):
        raise ValueError("order_number is not a valid 12-character public order number")
    try:
        table.update_item(
            Key={key_attr: PAYMENT_ATTEMPT_PREFIX + payment_attempt_id},
            UpdateExpression="SET orderNumber = :n, numberedAt = :t",
            ConditionExpression="attribute_exists(%s)" % key_attr,
            ExpressionAttributeValues={":n": order_number, ":t": int(time.time())},
        )
    except Exception as error:  # noqa: BLE001
        raise OrderIdentityUnavailable(
            "could not record the order number for attempt %r: %s"
            % (payment_attempt_id, type(error).__name__)
        ) from error


def resolve_order_for_provider_payment(table: Any, provider_transaction_id: str, *,
                                       key_attr: str = "orderId"
                                       ) -> Optional[Dict[str, Any]]:
    """The order claim for a provider transaction, or None.

    Needed because a caller that loses the `PROVIDERPAYMENT#` claim holds the *wrong* attempt id
    to look up: the order belongs to whichever attempt won, not to the one asking. Without this,
    that caller sees "the provider claim is taken, but there is no order for my attempt" and
    reasonably concludes it should finish the job — reserving a **second** public order number
    for an order that already has one.

    Found by the test asserting that one provider payment cannot fund two orders across two
    attempts, which is exactly the case this resolves.
    """
    if not provider_transaction_id:
        return None
    claim = _read_row(
        table, key_attr, PROVIDER_PAYMENT_PREFIX + provider_transaction_id)
    if not claim:
        return None
    winner_attempt = str(claim.get("paymentAttemptId") or "")
    if not winner_attempt:
        return claim
    # The attempt row is the one carrying `orderNumber`; the provider row only names the order.
    return _read_row(
        table, key_attr, PAYMENT_ATTEMPT_PREFIX + winner_attempt) or claim


def resolve_order_for_payment(table: Any, payment_attempt_id: str, *,
                              key_attr: str = "orderId") -> Optional[Dict[str, Any]]:
    """The order claim for a payment attempt, or None when no order exists yet.

    None is the expected answer for every attempt that is pending, failed, cancelled or
    expired. It is not an error, and it must never be turned into one - "this attempt has no
    order" is the normal state for most attempts.
    """
    if not payment_attempt_id:
        return None
    return _read_row(table, key_attr, PAYMENT_ATTEMPT_PREFIX + payment_attempt_id)


def commerce_keys_table_name() -> str:
    """The provisioned table holding these rows. TTL must stay disabled on it.

    Indirected through an env var so the rows can move to a dedicated table without a code
    change. It currently defaults to the order-id mapping table, which was chosen because it is
    already provisioned, is keyed on a single string partition (`orderId`, measured - note the
    Amplify model in `amplify/data/resource.ts` declares `wixOrderId`, which the physical table
    does not use), has TTL disabled, and held zero items.
    """
    return os.environ.get(
        "COMMERCE_KEYS_TABLE",
        os.environ.get("WIX_ORDER_IDS_TABLE", "stack-wecare-digital-WixOrderIds"),
    )


#: Superseded name, kept for the Wix sync path.
order_ids_table_name = commerce_keys_table_name


# ── legacy: WD order numbers for orders synced from Wix ─────────────────────────

def reserve_order_number(table: Any,
                         order_date: str = "",
                         *,
                         key_attr: str = "orderId",
                         generate: Optional[Callable[[str], str]] = None,
                         attempts: int = _DEFAULT_ATTEMPTS,
                         extra: Optional[Dict[str, Any]] = None) -> str:
    """Reserve a legacy WD-ORD number for an order that already exists in Wix.

    This is NOT the checkout path. It serves `wix-store`'s sync and backfill, which assign a
    display number to orders Wix already holds and has already collected payment for - so no
    order is being created here and the order-after-payment rule is not in play.

    New orders created by our own checkout get `reserve_public_order_number` instead.
    """
    if generate is None:
        from lambda_utils.ecommerce.wix_domain import _generate_wd_order_number
        generate = _generate_wd_order_number

    now = int(time.time())
    for attempt in range(1, max(1, attempts) + 1):
        candidate = generate(order_date)
        item = {
            "kind": "ORDER_NUMBER_RESERVATION",
            "orderNumber": candidate,
            "reservedAt": now,
        }
        if extra:
            item.update(extra)
        if _claim_row(table, key_attr, ORDER_NUMBER_PREFIX + candidate, item):
            return candidate
        logger.warning(
            "order number collision on attempt %d/%d; regenerating", attempt, attempts
        )

    raise OrderIdentityUnavailable(
        "exhausted %d attempts reserving an order number" % attempts
    )


__all__ = [
    "META_REFERENCE_ID_MAX_LENGTH",
    "RAZORPAY_RECEIPT_MAX_LENGTH",
    "PUBLIC_ORDER_NUMBER_LENGTH",
    "PUBLIC_ORDER_NUMBER_ALPHABET",
    "PAYMENT_REFERENCE_PREFIX",
    "PAYMENT_ATTEMPT_PREFIX",
    "PROVIDER_PAYMENT_PREFIX",
    "ORDER_NUMBER_PREFIX",
    "LEGACY_REFERENCE_PREFIX",
    "REFERENCE_ID_PREFIX",
    "OrderIdentityUnavailable",
    "is_valid_meta_reference_id",
    "assert_valid_meta_reference_id",
    "is_public_order_number",
    "is_wd_order_number",
    "new_payment_attempt_id",
    "new_order_id",
    "mint_payment_reference",
    "mint_reference_id",
    "mint_public_order_number",
    "reserve_payment_reference",
    "resolve_payment_reference",
    "allocate_payment_reference",
    "reserve_public_order_number",
    "claim_order_for_payment",
    "record_order_number_on_claim",
    "resolve_order_for_payment",
    "resolve_order_for_provider_payment",
    "reserve_order_number",
    "commerce_keys_table_name",
    "order_ids_table_name",
]
