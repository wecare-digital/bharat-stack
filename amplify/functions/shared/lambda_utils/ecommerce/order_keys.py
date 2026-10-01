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
#: The customer-facing number carries a readable prefix, e.g. `WD-ORD-K4M7PQR9`.
#:
#: The prefix is not decoration. This string is read aloud to support, pasted into a tracking
#: box and quoted in WhatsApp, and a bare `K4M7PQR9` is indistinguishable from a coupon, a
#: tracking id or a payment reference. `WD-ORD-` says what it is.
PUBLIC_ORDER_NUMBER_PREFIX = "WD-ORD-"

#: Random symbols after the prefix. EIGHT, and the number was chosen by measurement.
#:
#: The alphabet below is 30 symbols, so with a conditional-write reservation:
#:
#:     6 symbols  ~29.4 bits   729,000,000   50% chance of a collision by ~33,800 orders
#:     8 symbols  ~39.3 bits   656.1 billion 50% chance of a collision by ~1,015,000 orders
#:    12 symbols  ~58.9 bits   5.31e17       50% chance of a collision by ~914,000,000 orders
#:
#: A collision is never *wrong* - `reserve_public_order_number` refuses it and regenerates - so
#: the question is only whether the retry loop becomes the hot path, and whether the number is
#: guessable. At six symbols a blind guess against a 100,000-order corpus hits 1 in 7,290, which
#: is enumerable by anything that can make requests. At eight it is 1 in 6,561,000, and the retry
#: loop stays theoretical past a million orders. Twelve was the previous value and is more than
#: this business needs; eight keeps the number short enough to read aloud.
#:
#: Guessability still must not be the only thing protecting anything. A receipt is authorised by
#: a signed link or a session, never by knowing an order number - see `receipt_links.py`.
PUBLIC_ORDER_NUMBER_ENTROPY = 8

#: Total minted length: 7 characters of prefix plus 8 of entropy.
PUBLIC_ORDER_NUMBER_LENGTH = len(PUBLIC_ORDER_NUMBER_PREFIX) + PUBLIC_ORDER_NUMBER_ENTROPY

#: THIRTY symbols, and the exclusions are the point: 0, 1, I, L, O and U are gone, because they
#: are where transcription errors come from when a number is read down a phone line. The comment
#: here previously said "27 symbols ... ~57 bits" and both figures were wrong - the alphabet has
#: always been 30 characters, which over the old 12 positions was ~58.9 bits rather than 57.
PUBLIC_ORDER_NUMBER_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"

_PUBLIC_ORDER_NUMBER_RE = re.compile(
    r"^%s[%s]{%d}$" % (re.escape(PUBLIC_ORDER_NUMBER_PREFIX),
                       PUBLIC_ORDER_NUMBER_ALPHABET,
                       PUBLIC_ORDER_NUMBER_ENTROPY)
)

#: The bare 12-character form minted before the prefix existed.
#:
#: STILL VALID FOR LOOKUP, and that is not optional. Numbers already issued are printed on
#: receipts, sitting in customers' WhatsApp history and quoted to support. A validator that
#: stopped recognising them would break tracking and receipt resolution for every order placed
#: before this change, which is the one thing `never reused` was written to prevent.
#:
#: Nothing MINTS this form any more - `mint_public_order_number` only produces the prefixed one.
LEGACY_PUBLIC_ORDER_NUMBER_LENGTH = 12

_LEGACY_PUBLIC_ORDER_NUMBER_RE = re.compile(
    r"^[%s]{%d}$" % (PUBLIC_ORDER_NUMBER_ALPHABET, LEGACY_PUBLIC_ORDER_NUMBER_LENGTH)
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
    """True for any public order number this system has ever issued.

    Accepts BOTH the current `WD-ORD-XXXXXXXX` form and the bare 12-character form minted before
    the prefix existed. Use this wherever a customer-supplied number is being resolved - tracking,
    receipt lookup, support - because refusing a historical number would break every order placed
    before the change.

    Use `is_current_public_order_number` where the question is "did we just mint this correctly".
    """
    if not isinstance(value, str):
        return False
    return bool(_PUBLIC_ORDER_NUMBER_RE.match(value)
                or _LEGACY_PUBLIC_ORDER_NUMBER_RE.match(value))


def is_current_public_order_number(value: Any) -> bool:
    """True only for the current `WD-ORD-` + 8 form.

    Separate from `is_public_order_number` on purpose. A test that asserts the minter produces the
    current format must not pass just because the legacy shape is still accepted for lookup, which
    is exactly how a format migration quietly fails to happen.
    """
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
    """Mint a candidate public order number: `WD-ORD-` plus 8 CSPRNG symbols.

    Unordered and carrying no timestamp, unlike `orderId`. Two reasons: a time-ordered public
    number leaks order volume to anyone holding two of them, and a customer-facing number must
    not imply anything about when the business is busy. It encodes no phone number, no email
    and no customer id - the tail is 8 symbols of CSPRNG output and nothing else.

    The ENTROPY is generated, the prefix is a constant. A reader should never have to wonder
    whether `WD-ORD-` came out of the random source.

    A candidate is not an order number until `reserve_public_order_number` has committed it.
    """
    tail = "".join(
        secrets.choice(PUBLIC_ORDER_NUMBER_ALPHABET)
        for _ in range(PUBLIC_ORDER_NUMBER_ENTROPY)
    )
    return PUBLIC_ORDER_NUMBER_PREFIX + tail


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
        return table.get_item(Key={key_attr: key}, ConsistentRead=True).get("Item")
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
            "paymentAttemptId": payment_attempt_id,
            "providerTransactionId": provider_transaction_id}
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
            if existing.get("paymentAttemptId") != payment_attempt_id:
                return winner, False
            # Recover a crash between provider and attempt claims using the
            # committed identity. Never mint a second order for that payment.
            order_id = winner
            base["orderIdRef"] = winner

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
                                 key_attr: str = "orderId") -> str:
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
            ConditionExpression="attribute_exists(%s) AND attribute_not_exists(orderNumber)" % key_attr,
            ExpressionAttributeValues={":n": order_number, ":t": int(time.time())},
        )
        return order_number
    except Exception as error:  # noqa: BLE001
        if _is_conditional_failure(error):
            existing = resolve_order_for_payment(table, payment_attempt_id, key_attr=key_attr) or {}
            canonical = existing.get("orderNumber")
            if is_public_order_number(canonical):
                return canonical
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


# ── durable capture quarantine: a recoverable intake row, not an alert ──────────
#: A capture the webhook could not authoritatively clear. Parked as a DURABLE row so it
#: survives after Razorpay stops retrying - an alert log does not. One row per payment id,
#: so a redelivery of the same unverified capture updates the same intake rather than piling
#: up duplicates. Writes NOTHING financial: it only records that a human must look.
QUARANTINE_PREFIX = "CAPTUREQUARANTINE#"

#: A stored wallet top-up intent. The self-service top-up flow reserves one of these BEFORE
#: the payment link is created, so a `payment.captured` for a wallet top-up can be bound to a
#: customer/amount the business actually asked for - rather than trusting the event notes.
TOPUP_INTENT_PREFIX = "TOPUPINTENT#"

#: The idempotency marker that makes one captured payment credit a wallet exactly once. Claimed
#: conditionally before `partner_billing.topup`, so a duplicate webhook delivery loses the claim
#: and credits nothing.
TOPUP_CREDIT_PREFIX = "TOPUPCREDIT#"


def record_capture_quarantine(table: Any,
                              *,
                              payment_id: str,
                              reference_id: str = "",
                              outcome: str = "",
                              key_attr: str = "orderId",
                              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Durably park an unverified capture for a human. Returns the stored/known row.

    Idempotent and recoverable, which is the whole reason it exists. The money may or may not
    have moved and the webhook could not tell, so this records the fact rather than guessing.
    Keyed by payment id, because that is the one identifier a capture always carries and the one
    a human reconciling it will search by. A redelivery of the same unverified capture finds the
    row already present and leaves it untouched (its `acknowledged` state and `createdAt` are
    preserved), so acknowledging an event does not make it reappear and re-alert.

    Writes NOTHING financial: no invoice is marked paid, no wallet is credited, no order is
    created. On a storage error it raises `OrderIdentityUnavailable` - the caller must not treat
    a failed park as a successful one, because that would silently drop the only recovery record.
    """
    if not payment_id:
        raise ValueError("payment_id is required to quarantine a capture")
    now = int(time.time())
    item = {
        "kind": "CAPTURE_QUARANTINE",
        "paymentId": payment_id,
        "referenceId": reference_id or "",
        "outcome": outcome or "",
        "status": "UNRESOLVED",
        "acknowledged": False,
        "createdAt": now,
    }
    if extra:
        item.update(extra)
    key = QUARANTINE_PREFIX + payment_id
    if _claim_row(table, key_attr, key, item):
        return item
    # Already parked by an earlier delivery. Return the existing row so the caller can see it is
    # recoverable; never overwrite it, so an acknowledgement is not undone by a retry.
    existing = _read_row(table, key_attr, key)
    return existing or item


def resolve_capture_quarantine(table: Any, payment_id: str, *,
                               key_attr: str = "orderId") -> Optional[Dict[str, Any]]:
    """The quarantine intake row for a payment id, or None. Raises only on a storage error."""
    if not payment_id:
        return None
    return _read_row(table, key_attr, QUARANTINE_PREFIX + payment_id)


def acknowledge_capture_quarantine(table: Any,
                                   *,
                                   payment_id: str,
                                   actor: str = "staff",
                                   key_attr: str = "orderId") -> Optional[Dict[str, Any]]:
    """Mark a parked capture acknowledged WITHOUT deleting it, so it stays recoverable.

    Acknowledgement records that a human has seen the intake; it does not resolve or discharge
    it. The row is retained (never TTL'd, never deleted) precisely so that an acknowledged event
    remains recoverable after Razorpay has stopped retrying - the alert log it replaced could not
    offer that. Returns the updated row, or None if there is nothing parked under this id.
    """
    if not payment_id:
        return None
    key = QUARANTINE_PREFIX + payment_id
    try:
        table.update_item(
            Key={key_attr: key},
            UpdateExpression="SET acknowledged = :a, acknowledgedBy = :who, acknowledgedAt = :t",
            ConditionExpression="attribute_exists(%s)" % key_attr,
            ExpressionAttributeValues={":a": True, ":who": actor or "staff",
                                       ":t": int(time.time())},
        )
    except Exception as error:  # noqa: BLE001
        if _is_conditional_failure(error):
            return None
        raise OrderIdentityUnavailable(
            "could not acknowledge quarantine %r: %s" % (payment_id, type(error).__name__)
        ) from error
    return resolve_capture_quarantine(table, payment_id, key_attr=key_attr)


def claim_legacy_invoice_payment(table: Any,
                                 *,
                                 payment_id: str,
                                 invoice_id: str,
                                 reference_id: str = "",
                                 key_attr: str = "orderId",
                                 extra: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Claim the right to settle exactly one legacy invoice for one Razorpay payment. Idempotent.

    Returns `(won, invoiceIdRef)`. `won` is True only when THIS call wrote the claim. When the
    marker already exists, `won` is False and `invoiceIdRef` is the invoice the claim is already
    bound to - which is what defeats a replay: a second signature-valid `payment.captured`
    carrying the SAME `payment_id` under a DIFFERENT referenceId finds the claim already held for
    the first invoice and settles nothing.

    Shares the `PROVIDERPAYMENT#<payment_id>` namespace with `claim_order_for_payment`, so a single
    provider payment can fund at most one thing across BOTH the commerce and the legacy paths: if
    the commerce reconciler already claimed this payment for an order, the legacy claim loses, and
    vice-versa. The marker is claimed BEFORE any invoice write, so one payment settles one invoice.
    """
    if not payment_id:
        raise ValueError("payment_id is required")
    if not invoice_id:
        raise ValueError("invoice_id is required")
    now = int(time.time())
    item = {
        "kind": "LEGACY_INVOICE_PAYMENT_CLAIM",
        "invoiceIdRef": invoice_id,
        "providerTransactionId": payment_id,
        "referenceId": reference_id or "",
        "claimedAt": now,
    }
    if extra:
        item.update(extra)
    key = PROVIDER_PAYMENT_PREFIX + payment_id
    if _claim_row(table, key_attr, key, item):
        return True, invoice_id
    existing = _read_row(table, key_attr, key) or {}
    return False, str(existing.get("invoiceIdRef") or "")


def release_legacy_invoice_payment_claim(table: Any,
                                         *,
                                         payment_id: str,
                                         invoice_id: str,
                                         key_attr: str = "orderId") -> bool:
    """Release a legacy one-time payment claim that settled NO invoice row. Returns True if deleted.

    The companion to `claim_legacy_invoice_payment`. The legacy settle on the Razorpay webhook is a
    second, independent query against the referenceId GSI run AFTER this claim is taken, so a settle
    that then no-ops (the row vanished, a duplicate made it ambiguous, or the write errored) would
    otherwise strand the payment: the irreversible claim is held with no paid row behind it, and no
    redelivery can ever settle. The caller detects "nothing settled" and calls this to release the
    claim so a legitimate redelivery can re-claim and re-attempt.

    Money-safety rests on the DELETE being CONDITIONAL, never unconditional:

      * `kind = LEGACY_INVOICE_PAYMENT_CLAIM`  - never remove a commerce `PROVIDER_PAYMENT_CLAIM`
        that happens to share the `PROVIDERPAYMENT#<payment_id>` namespace. A commerce order claim
        must stay irrevocable.
      * `invoiceIdRef = <invoice_id>`          - only release the claim THIS legacy settlement took,
        not one another worker has since re-bound to a different invoice.
      * `providerTransactionId = <payment_id>` - belt and braces that the row is for this payment.

    If the row no longer matches (already released, re-bound, or a commerce claim), the conditional
    delete loses and this returns False - a no-op, which is correct: there is nothing of ours to
    release. A conditional-check failure is the only tolerated error; anything else raises
    `OrderIdentityUnavailable` so a throttle is never mistaken for "released".

    The caller invokes this ONLY after confirming no invoice row was settled for this payment, so at
    release time no invoice is paid anywhere for it: releasing the claim cannot enable a double
    settle, it only lets the one legitimate settlement happen on a later delivery.
    """
    if not payment_id:
        raise ValueError("payment_id is required")
    if not invoice_id:
        raise ValueError("invoice_id is required")
    key = PROVIDER_PAYMENT_PREFIX + payment_id
    try:
        table.delete_item(
            Key={key_attr: key},
            ConditionExpression=(
                "#k = :kind AND invoiceIdRef = :inv AND providerTransactionId = :pid"
            ),
            ExpressionAttributeNames={"#k": "kind"},
            ExpressionAttributeValues={
                ":kind": "LEGACY_INVOICE_PAYMENT_CLAIM",
                ":inv": invoice_id,
                ":pid": payment_id,
            },
        )
        return True
    except Exception as error:  # noqa: BLE001 - re-raised below unless it is a lost condition
        if _is_conditional_failure(error):
            return False
        raise OrderIdentityUnavailable(
            "could not release %r: %s" % (key, type(error).__name__)
        ) from error


def reserve_topup_intent(table: Any,
                         *,
                         reference_id: str,
                         waba_id: str,
                         amount_paise: int,
                         currency: str = "INR",
                         key_attr: str = "orderId",
                         extra: Optional[Dict[str, Any]] = None) -> bool:
    """Record a wallet top-up the business actually asked for. True if reserved, False if bound.

    Written at top-up-initiation time, before the payment link exists, so the later
    `payment.captured` has a stored customer (`waba_id`) and amount to bind the credit to. The
    webhook never invents these from the event notes - absence of this row means the capture is
    not an authorised top-up and must not credit anything.
    """
    if not reference_id:
        raise ValueError("reference_id is required")
    if not waba_id:
        raise ValueError("waba_id is required")
    from lambda_utils.ecommerce.money import positive_paise
    amount_paise = positive_paise(amount_paise)
    item = {
        "kind": "TOPUP_INTENT",
        "referenceId": reference_id,
        "wabaId": waba_id,
        "amountPaise": amount_paise,
        "currency": currency or "INR",
        "reservedAt": int(time.time()),
    }
    if extra:
        item.update(extra)
    return _claim_row(table, key_attr, TOPUP_INTENT_PREFIX + reference_id, item)


def resolve_topup_intent(table: Any, reference_id: str, *,
                         key_attr: str = "orderId") -> Optional[Dict[str, Any]]:
    """The stored top-up intent for a reference, or None when no top-up was authorised."""
    if not reference_id:
        return None
    return _read_row(table, key_attr, TOPUP_INTENT_PREFIX + reference_id)


def claim_topup_credit(table: Any,
                       *,
                       payment_id: str,
                       reference_id: str = "",
                       waba_id: str = "",
                       amount_paise: int = 0,
                       key_attr: str = "orderId") -> bool:
    """Claim the right to credit a wallet for one captured payment. Idempotent.

    True on the first delivery (the caller may credit), False on every redelivery (already
    credited). Keyed by payment id, so one Razorpay capture credits a wallet exactly once no
    matter how many times the webhook is delivered. The claim is written BEFORE the credit, so
    even a crash between claim and credit cannot double-credit - a redelivery sees the claim and
    stops.
    """
    if not payment_id:
        raise ValueError("payment_id is required")
    item = {
        "kind": "TOPUP_CREDIT",
        "paymentId": payment_id,
        "referenceId": reference_id or "",
        "wabaId": waba_id or "",
        "amountPaise": int(amount_paise or 0),
        "creditedAt": int(time.time()),
    }
    return _claim_row(table, key_attr, TOPUP_CREDIT_PREFIX + payment_id, item)


# ── website Standard Checkout: request key + gateway-order binding (section 8) ──
#: A customer-scoped, intent-fingerprinted request key reserved BEFORE the external order-create
#: call. Two rapid clicks on "Pay" with the SAME intent must coordinate onto ONE gateway order,
#: and a changed intent (different amount, cart revision or snapshot hash) under a resumed key
#: must be refused rather than silently paying the old amount. The key names the attempt; the
#: fingerprint pins the intent, and the two are checked together.
REQUEST_KEY_PREFIX = "REQUESTKEY#"

#: The persisted binding of a created Razorpay gateway order to the attempt/account/mode/amount
#: it was created for. Written BEFORE checkout options are exposed to the browser, so a callback
#: can be checked against the stored order id/account/mode/amount rather than anything the browser
#: relayed. A Razorpay GATEWAY order is NOT an internal/Wix purchase order and carries no public
#: order number — that exists only after an authoritative capture. These are different objects.
GATEWAY_ORDER_PREFIX = "GATEWAYORDER#"


def reserve_checkout_request_key(table: Any,
                                 *,
                                 customer_id: str,
                                 request_key: str,
                                 intent_fingerprint: str,
                                 payment_attempt_id: str,
                                 key_attr: str = "orderId",
                                 extra: Optional[Dict[str, Any]] = None
                                 ) -> Tuple[Dict[str, Any], bool]:
    """Reserve a customer-scoped request key before any external order-create. Idempotent.

    Returns `(row, won)`:

      won is True   this click is the first with this key; the caller proceeds to create the
                    gateway order. The row records the intent fingerprint so a later resume can
                    be checked against it.
      won is False  this key already exists. The returned row is the EXISTING reservation. The
                    caller MUST compare `intentFingerprint` before resuming: the same intent
                    resumes onto the already-created order (concurrent clicks coordinate), and a
                    DIFFERENT intent must be rejected rather than charged.

    The key is namespaced by customer so one customer cannot reserve or resume another's request
    key. The fingerprint is the caller's hash over the frozen intent (amount, currency, cart
    revision, snapshot hash); this module stores and returns it but does not interpret it.
    """
    if not customer_id:
        raise ValueError("customer_id is required")
    if not request_key:
        raise ValueError("request_key is required")
    if not intent_fingerprint:
        raise ValueError("intent_fingerprint is required")
    if not payment_attempt_id:
        raise ValueError("payment_attempt_id is required")
    now = int(time.time())
    item = {
        "kind": "CHECKOUT_REQUEST_KEY",
        "customerId": customer_id,
        "requestKey": request_key,
        "intentFingerprint": intent_fingerprint,
        "paymentAttemptId": payment_attempt_id,
        "reservedAt": now,
    }
    if extra:
        item.update(extra)
    key = REQUEST_KEY_PREFIX + customer_id + "#" + request_key
    if _claim_row(table, key_attr, key, item):
        return item, True
    existing = _read_row(table, key_attr, key)
    if existing is None:
        # A lost race whose winner's row we then could not read is an outage, not a resume.
        raise OrderIdentityUnavailable(
            "request key %r is claimed but could not be read" % request_key)
    return existing, False


def bind_gateway_order(table: Any,
                       *,
                       gateway_order_id: str,
                       payment_attempt_id: str,
                       request_key: str,
                       amount_paise: int,
                       account_key_id: str,
                       account_mode: str,
                       currency: str = "INR",
                       key_attr: str = "orderId",
                       extra: Optional[Dict[str, Any]] = None) -> bool:
    """Durably persist a created gateway order's id/account/mode/amount BEFORE exposing options.

    True if this binding was written, False if the gateway order id was already bound (a resumed
    create landing on the same provider order). The binding is what a callback is verified
    against: the stored order id selects the HMAC input, and the stored account/mode/amount/currency
    are what a result must match. Writes NOTHING financial and mints NO public order number — a
    gateway order is only an intent to pay.
    """
    if not gateway_order_id:
        raise ValueError("gateway_order_id is required")
    if not payment_attempt_id:
        raise ValueError("payment_attempt_id is required")
    from lambda_utils.ecommerce.money import positive_paise
    amount_paise = positive_paise(amount_paise)
    item = {
        "kind": "GATEWAY_ORDER_BINDING",
        "gatewayOrderId": gateway_order_id,
        "paymentAttemptId": payment_attempt_id,
        "requestKey": request_key or "",
        "amountPaise": amount_paise,
        "currency": currency or "INR",
        "accountKeyId": account_key_id or "",
        "accountMode": account_mode or "",
        "boundAt": int(time.time()),
    }
    if extra:
        item.update(extra)
    return _claim_row(table, key_attr, GATEWAY_ORDER_PREFIX + gateway_order_id, item)


def resolve_gateway_order(table: Any, gateway_order_id: str, *,
                          key_attr: str = "orderId") -> Optional[Dict[str, Any]]:
    """The stored binding for a gateway order id, or None.

    None means we never created this order — a callback naming an unknown gateway order id is
    either a forgery or a lost write, and either way must not settle anything.
    """
    if not gateway_order_id:
        return None
    return _read_row(table, key_attr, GATEWAY_ORDER_PREFIX + gateway_order_id)


__all__ = [
    "META_REFERENCE_ID_MAX_LENGTH",
    "RAZORPAY_RECEIPT_MAX_LENGTH",
    "PUBLIC_ORDER_NUMBER_PREFIX",
    "PUBLIC_ORDER_NUMBER_ENTROPY",
    "PUBLIC_ORDER_NUMBER_LENGTH",
    "PUBLIC_ORDER_NUMBER_ALPHABET",
    "LEGACY_PUBLIC_ORDER_NUMBER_LENGTH",
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
    "is_current_public_order_number",
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
    "QUARANTINE_PREFIX",
    "TOPUP_INTENT_PREFIX",
    "TOPUP_CREDIT_PREFIX",
    "record_capture_quarantine",
    "resolve_capture_quarantine",
    "acknowledge_capture_quarantine",
    "reserve_topup_intent",
    "resolve_topup_intent",
    "claim_topup_credit",
    "REQUEST_KEY_PREFIX",
    "GATEWAY_ORDER_PREFIX",
    "reserve_checkout_request_key",
    "bind_gateway_order",
    "resolve_gateway_order",
]
