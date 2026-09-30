"""One business order, each downstream side effect exactly once — across every retry.

The gap this closes
-------------------
`order_creation` + `order_keys` already guarantee **one order** per verified payment, with
conditional claims on `PROVIDERPAYMENT#` and `PAYMENTATTEMPT#`. But an order is only the first
step. The reconciliation pipeline (design.md, R7/R9/R10) then performs a series of *separate*
externally-visible side effects:

    create the Wix order · record the external payment in Wix · generate the receipt ·
    send the WhatsApp confirmation

Each one must happen **at most once**, and each must be *individually* retryable — a failure at
"send confirmation" must not re-create the Wix order or re-record the payment. A single
event-level dedup cannot express that: it is all-or-nothing per event, and it is keyed on the
webhook delivery, not on the business order. So this module adds a guard keyed on
`(orderId, sideEffect)`, which is the granularity the pipeline actually needs.

Why a claim, and why it fails CLOSED
------------------------------------
Every side effect here either spends money in Wix, records against a payment, or messages a real
customer. Running one twice is the failure this whole subsystem exists to prevent. So the guard
is a conditional `attribute_not_exists` claim — the same mechanism as `order_keys` — and any
storage error `raises` rather than returning "go ahead". That is the opposite of the webhook
dedup helper, which fails *open* so a transient blip never drops an event: here, "I could not
prove this has not already run" must mean "do not run it", because a duplicate charge or a
duplicate customer message is not recoverable by a retry.

Two-phase: claim, then confirm
------------------------------
`claim(order_id, effect)` writes a `pending` marker conditionally. Only the winner proceeds.
`confirm(order_id, effect, result)` stamps it `done` and records a small result reference
(a Wix order id, a receipt id, a message id) so a later reader can find what the side effect
produced without re-deriving it.

A claim that is never confirmed is the recoverable state: `resolve(order_id, effect)` reports it
as `pending`, and the pipeline's own retry re-enters. Unlike the webhook lease, this guard does
**not** auto-expire — a half-finished Wix order must not silently become claimable again and
produce a second one; recovery is an explicit, audited retry that reads the pending marker and
reads back the external outcome before confirming success or authorizing another call.
A pending marker is never permission to repeat an external mutation.

Storage-agnostic
----------------
The table is injected, so this module holds no AWS client, reads no credential, and is fully
unit-testable. It writes namespaced rows onto the same commerce-keys table the order claims use,
so it inherits that table's TTL-DISABLED guarantee — a side-effect marker that expired would be
a side effect that could run twice.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

#: Namespace on the shared commerce-keys table. `SIDEEFFECT#<orderId>#<effect>` -> marker row.
SIDE_EFFECT_PREFIX = "SIDEEFFECT#"

# ── the side effects the reconciliation pipeline performs, each guarded once ─────
WIX_ORDER = "wix_order"
WIX_PAYMENT = "wix_payment"
RECEIPT = "receipt"
CONFIRMATION = "confirmation"

#: The closed set. A caller passing anything else is a bug, not a new side effect — adding one
#: is a deliberate edit here, so a typo can never silently create an unguarded effect.
KNOWN_EFFECTS = frozenset({WIX_ORDER, WIX_PAYMENT, RECEIPT, CONFIRMATION})

# ── marker states ────────────────────────────────────────────────────────────
PENDING = "pending"
DONE = "done"


class SideEffectGuardUnavailable(RuntimeError):
    """The guard could not be read or written, so the side effect must NOT run.

    Fails closed on purpose: a side effect that spends money or messages a customer cannot be
    allowed to run when we cannot prove it has not already run.
    """


def _key(order_id: str, effect: str) -> str:
    return f"{SIDE_EFFECT_PREFIX}{order_id}#{effect}"


def _is_conditional_failure(error: Exception) -> bool:
    response = getattr(error, "response", None) or {}
    return response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _validate(order_id: str, effect: str) -> None:
    if not order_id:
        raise ValueError("order_id is required")
    if effect not in KNOWN_EFFECTS:
        raise ValueError(
            f"unknown side effect {effect!r}; add it to KNOWN_EFFECTS deliberately "
            f"rather than guarding a typo")


def claim(table: Any, *, order_id: str, effect: str,
          key_attr: str = "orderId", now: Optional[int] = None) -> bool:
    """Claim the right to perform `effect` for `order_id`, once. Returns True to the winner.

    Returns False when the effect is already claimed or done — the caller then reads the existing
    marker via `resolve` rather than performing the effect again. Raises
    `SideEffectGuardUnavailable` on any non-conditional storage error, because an unprovable state
    must block the effect.
    """
    _validate(order_id, effect)
    moment = int(time.time()) if now is None else int(now)
    item = {
        key_attr: _key(order_id, effect),
        "kind": "SIDE_EFFECT_MARKER",
        "orderIdRef": order_id,
        "effect": effect,
        "state": PENDING,
        "claimedAt": moment,
    }
    try:
        table.put_item(Item=item,
                       ConditionExpression=f"attribute_not_exists({key_attr})")
        return True
    except Exception as error:  # noqa: BLE001
        if _is_conditional_failure(error):
            logger.info('{"event":"side_effect_already_claimed","effect":"%s"}', effect)
            return False
        raise SideEffectGuardUnavailable(
            f"could not claim {effect} for the order: {type(error).__name__}") from error


def confirm(table: Any, *, order_id: str, effect: str,
            result: Optional[Dict[str, Any]] = None,
            key_attr: str = "orderId", now: Optional[int] = None) -> None:
    """Mark `effect` done and record a small result reference. Call only after it succeeded.

    Conditional on the marker existing, so a confirm without a preceding claim is refused — that
    ordering is what makes a crash between claim and confirm show up as `pending` on re-entry
    rather than silently completing.
    """
    _validate(order_id, effect)
    moment = int(time.time()) if now is None else int(now)
    values: Dict[str, Any] = {":done": DONE, ":now": moment}
    set_parts = ["state = :done", "confirmedAt = :now"]
    if result:
        # A compact reference to what the effect produced (wixOrderId, receiptId, messageId),
        # so a later reader finds it without re-deriving. Never a full payload.
        values[":result"] = result
        set_parts.append("result = :result")
    try:
        table.update_item(
            Key={key_attr: _key(order_id, effect)},
            UpdateExpression="SET " + ", ".join(set_parts),
            ConditionExpression=f"attribute_exists({key_attr})",
            ExpressionAttributeValues=values,
        )
    except Exception as error:  # noqa: BLE001
        raise SideEffectGuardUnavailable(
            f"could not confirm {effect} for the order: {type(error).__name__}") from error


def resolve(table: Any, *, order_id: str, effect: str,
            key_attr: str = "orderId") -> Optional[Dict[str, Any]]:
    """The marker for `(order_id, effect)`, or None when it was never claimed.

    Lets a retry decide what to do: None -> claim and run; state `pending` -> a previous run died
    mid-effect, finish it; state `done` -> already complete, reuse `result`.
    """
    _validate(order_id, effect)
    try:
        return (table.get_item(Key={key_attr: _key(order_id, effect)},
                               ConsistentRead=True).get("Item")) or None
    except Exception as error:  # noqa: BLE001
        raise SideEffectGuardUnavailable(
            f"could not read the {effect} marker: {type(error).__name__}") from error


def is_done(table: Any, *, order_id: str, effect: str,
            key_attr: str = "orderId") -> bool:
    """True when `effect` has already completed for `order_id`."""
    marker = resolve(table, order_id=order_id, effect=effect, key_attr=key_attr)
    return bool(marker and marker.get("state") == DONE)


__all__ = [
    "SIDE_EFFECT_PREFIX",
    "WIX_ORDER",
    "WIX_PAYMENT",
    "RECEIPT",
    "CONFIRMATION",
    "KNOWN_EFFECTS",
    "PENDING",
    "DONE",
    "SideEffectGuardUnavailable",
    "claim",
    "confirm",
    "resolve",
    "is_done",
]
