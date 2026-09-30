"""Order-number reservation, and the Meta `reference_id` that joins a payment to an order.

Why this module exists
----------------------
Three subsystems have to agree on one identifier: the WhatsApp `order_details` message, the
Razorpay webhook, and the Wix order. Getting that join wrong produces the single failure
this domain cannot recover from - a customer charged twice, or a paid order with no record.

Three defects made that join unsafe, all measured rather than inferred:

1. ``_get_or_create_wd_order_number`` was **never idempotent**. Its reuse check was
   ``wdOrderNumber.startswith('WD-ORD-')``, but the generator emits
   ``'WD-ORD - 5B9ED0A3 - 22-02-2026 - 23:30:00 - IST'`` - a space at index 6, not a dash.
   So the check was false for every number it had ever written, and each call regenerated
   and overwrote the mapping. ``_enrich_order`` calls it per order per listing, so every
   refresh reissued every order number.

2. Its exception path returned a number it had **not stored**, so the one case where a
   collision is most likely - DynamoDB unavailable - was the case that skipped the
   uniqueness record entirely.

3. The order number was being pushed through ``_sanitize_reference_id`` to become the Meta
   ``reference_id``. Meta's Payments (India) reference says ``reference_id`` may not exceed
   **35 characters** and may contain only letters, numbers, underscores, dashes and dots.
   The order number is 46 characters and contains spaces and colons, so the sanitiser
   stripped it to ``WD-PAY-ORD5B9ED0A322022026233000IST`` and truncated at 35. Truncation on
   a join key is how two orders quietly become one payment.

So the order number is a **customer-facing display string** and the ``reference_id`` is a
**machine join key**, and this module keeps them separate. That is R2.9's rule, and the
charset and length limits above are the reason for it.

The key space
-------------
Namespaced rows in one table, keyed on a single partition attribute (``orderId`` on the
live ``stack-wecare-digital-WixOrderIds`` table - measured, and note the Amplify model in
``amplify/data/resource.ts`` declares ``wixOrderId``, which the physical table does not
use)::

    ORDERNO#<orderNumber>    SK-less uniqueness reservation; never expires, never reused
    REFERENCE#<referenceId>  Meta reference -> order number, the resolve-before-generate index

Neither row may ever carry a TTL. A reservation that expires is a number that gets reissued,
which defeats the entire point. The table this writes to has TTL ``DISABLED``; keep it that
way.

Failure posture
---------------
Everything here fails **closed**. A ``ConditionalCheckFailedException`` is a normal race and
is retried with a fresh candidate. Any other storage error raises
``OrderIdentityUnavailable`` and yields no identifier, because an unreserved number handed to
a caller is a duplicate waiting to be issued.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Meta Payments (India) constraints ───────────────────────────────────────────
# Source: Meta for Developers, "Receive payments via payment gateways on WhatsApp",
# Parameters Object -> reference_id. Updated 2026-05-21. Paraphrased: the value is required,
# case sensitive, must be non-empty, may contain only English letters, numbers, underscores,
# dashes or dots, and must not exceed 35 characters.
# https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/payments-in/pg
META_REFERENCE_ID_MAX_LENGTH = 35
_META_REFERENCE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,%d}$" % META_REFERENCE_ID_MAX_LENGTH)

#: Razorpay's `receipt` field tolerates 40 characters, so a valid reference_id always fits.
RAZORPAY_RECEIPT_MAX_LENGTH = 40

ORDER_NUMBER_PREFIX = "ORDERNO#"
REFERENCE_PREFIX = "REFERENCE#"

#: Default reference_id prefix. 7 characters, leaving 28 for entropy.
REFERENCE_ID_PREFIX = "WD-PAY-"

#: Crockford-style base32 without I, L, O, U - unambiguous when a human reads it off a
#: screen or a support ticket, and inside Meta's permitted charset.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

#: 14 symbols over a 32-symbol alphabet is 70 bits. The conditional write is what actually
#: guarantees uniqueness; this only has to make a collision rare enough that the retry loop
#: is never the hot path.
_REFERENCE_ENTROPY_SYMBOLS = 14

_DEFAULT_ATTEMPTS = 5

# Accepts both live spellings: the spaced display format the Wix path generates
# ('WD-ORD - A1B2C3D4 - ...') and the compact form the Order table's `orderId` uses
# ('WD-ORD-A1B2C3D4'). Written as one pattern deliberately - the bug this replaces was a
# `startswith` that silently recognised only one of them.
_WD_ORDER_NUMBER_RE = re.compile(r"^WD-ORD\s*-\s*[0-9A-F]{8}\b", re.IGNORECASE)


class OrderIdentityUnavailable(RuntimeError):
    """Raised when an identifier could not be durably reserved.

    Callers MUST propagate this. Falling back to an unreserved identifier is the defect
    this module exists to remove, so there is deliberately no "best effort" variant.
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

    Called before a send rather than after a rejection: an invalid `configuration_name` or
    `reference_id` surfaces at Meta as a generic failure that reads like an outage, and the
    customer simply cannot pay.
    """
    if not is_valid_meta_reference_id(value):
        raise ValueError(
            "reference_id must be 1-%d characters of [A-Za-z0-9._-]; "
            "got %r (length %d)"
            % (META_REFERENCE_ID_MAX_LENGTH, value, len(value) if isinstance(value, str) else -1)
        )
    return value


def is_wd_order_number(value: Any) -> bool:
    """True for a WD order number in either live format.

    Replaces `startswith('WD-ORD-')`, which never matched the spaced format the generator
    actually produces and so made the reuse check dead code.
    """
    return isinstance(value, str) and bool(_WD_ORDER_NUMBER_RE.match(value.strip()))


# ── minting ────────────────────────────────────────────────────────────────────

def mint_reference_id(prefix: str = REFERENCE_ID_PREFIX,
                      symbols: int = _REFERENCE_ENTROPY_SYMBOLS) -> str:
    """Mint a fresh Meta-safe `reference_id`.

    Uses `secrets`, never `random`. Two reasons, and the second is easy to miss: `random` is
    seeded per execution environment, and a SnapStart snapshot freezes that seed so every
    restored sandbox replays the same sequence. SnapStart is currently off across the fleet,
    but a payment join key is the last place to depend on that staying true.
    """
    candidate = prefix + "".join(secrets.choice(_ALPHABET) for _ in range(symbols))
    return assert_valid_meta_reference_id(candidate)


# ── reservation primitives ─────────────────────────────────────────────────────

def _reserve_row(table: Any, key_attr: str, key: str, item: Dict[str, Any]) -> bool:
    """Conditionally write one reservation row. True if won, False if already taken.

    Raises `OrderIdentityUnavailable` on anything that is not a lost race.
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
            "could not reserve %r: %s" % (key, type(error).__name__)
        ) from error


def reserve_order_number(table: Any,
                         order_date: str = "",
                         *,
                         key_attr: str = "orderId",
                         generate: Optional[Callable[[str], str]] = None,
                         attempts: int = _DEFAULT_ATTEMPTS,
                         extra: Optional[Dict[str, Any]] = None) -> str:
    """Generate and durably reserve a unique order number, or raise.

    The reservation row is written **before** the number is returned, so no caller can ever
    hold a number that storage has not committed to. That ordering is the whole contract.
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
        if _reserve_row(table, key_attr, ORDER_NUMBER_PREFIX + candidate, item):
            return candidate
        logger.warning(
            "order number collision on attempt %d/%d; regenerating", attempt, attempts
        )

    raise OrderIdentityUnavailable(
        "exhausted %d attempts reserving an order number" % attempts
    )


def resolve_reference(table: Any, reference_id: str, *,
                      key_attr: str = "orderId") -> Optional[Dict[str, Any]]:
    """Return the reservation row for `reference_id`, or None.

    None means **no order exists for this reference**. Per the reconciliation design, a
    payment event must not create an order, so a caller seeing None fails the event for
    staff attention rather than minting anything.
    """
    if not reference_id:
        return None
    try:
        response = table.get_item(Key={key_attr: REFERENCE_PREFIX + reference_id})
    except Exception as error:  # noqa: BLE001
        raise OrderIdentityUnavailable(
            "could not read reference %r: %s" % (reference_id, type(error).__name__)
        ) from error
    return response.get("Item")


def allocate_order_identity(table: Any,
                            *,
                            order_date: str = "",
                            reference_id: Optional[str] = None,
                            key_attr: str = "orderId",
                            generate: Optional[Callable[[str], str]] = None,
                            attempts: int = _DEFAULT_ATTEMPTS,
                            extra: Optional[Dict[str, Any]] = None
                            ) -> Tuple[str, str, bool]:
    """Resolve-before-generate. Returns `(reference_id, order_number, created)`.

    `created` is False when an existing reference was resolved, which is what makes a
    redelivered Meta event or a retried Lambda land on the order that already exists instead
    of minting a second one.

    When two workers race on the same fresh reference, one wins the conditional write and the
    loser re-reads and adopts the winner's order number. The loser's own reservation row stays
    behind, permanently burning that number. That is deliberate: burning a number is
    invisible to everyone, whereas reusing one issues a duplicate.
    """
    if reference_id is not None:
        assert_valid_meta_reference_id(reference_id)
        existing = resolve_reference(table, reference_id, key_attr=key_attr)
        if existing and existing.get("orderNumber"):
            return reference_id, existing["orderNumber"], False
    else:
        reference_id = mint_reference_id()

    order_number = reserve_order_number(
        table, order_date, key_attr=key_attr, generate=generate,
        attempts=attempts, extra=extra,
    )

    item = {
        "kind": "REFERENCE_BINDING",
        "referenceId": reference_id,
        "orderNumber": order_number,
        "boundAt": int(time.time()),
    }
    if extra:
        item.update(extra)

    if _reserve_row(table, key_attr, REFERENCE_PREFIX + reference_id, item):
        return reference_id, order_number, True

    # Lost the bind race. The winner's binding is authoritative.
    winner = resolve_reference(table, reference_id, key_attr=key_attr)
    if winner and winner.get("orderNumber"):
        logger.warning(
            "reference bind race lost; adopting the stored order number and "
            "abandoning the one just reserved"
        )
        return reference_id, winner["orderNumber"], False

    raise OrderIdentityUnavailable(
        "reference %r was claimed but holds no order number" % reference_id
    )


def order_ids_table_name() -> str:
    """The provisioned table holding these rows. TTL must stay disabled on it."""
    return os.environ.get("WIX_ORDER_IDS_TABLE", "stack-wecare-digital-WixOrderIds")


__all__ = [
    "META_REFERENCE_ID_MAX_LENGTH",
    "RAZORPAY_RECEIPT_MAX_LENGTH",
    "ORDER_NUMBER_PREFIX",
    "REFERENCE_PREFIX",
    "REFERENCE_ID_PREFIX",
    "OrderIdentityUnavailable",
    "is_valid_meta_reference_id",
    "assert_valid_meta_reference_id",
    "is_wd_order_number",
    "mint_reference_id",
    "reserve_order_number",
    "resolve_reference",
    "allocate_order_identity",
    "order_ids_table_name",
]
