"""Monotonic RCS delivery-status ordering, and permanent-failure classification.

Two defects this module exists to fix, both measured on 30 days of production DLR
traffic to 2026-09-22.

1. Status could move backwards
------------------------------
`rcs-dlr._process_delivery` applied every report with an unconditional

    SET #s = :status, dlrTime = :dlr, updatedAt = :now

Sinch guarantees neither ordering nor exactly-once on the callback, and the volumes
make the collision likely rather than theoretical: **728 `QUEUED_ON_CHANNEL`**,
**166 `DELIVERED`**, **62 `READ`**, **559 `FAILED`** over the window. A
`QUEUED_ON_CHANNEL` arriving after `DELIVERED` rewrote a delivered message back to
`sent`; a re-delivered `FAILED` rewrote `delivered` to `failed`. So the 166/62 figures
are a *floor*, not a measurement - some deliveries were almost certainly overwritten
before anyone read them.

This is the same defect fixed for WhatsApp in `lambda_utils.wa_status`, and the
mechanism here is deliberately identical: a rank persisted alongside the status, so the
guard is a DynamoDB `ConditionExpression` rather than a read-then-write race.

2. A permanently unreachable recipient was retried forever
----------------------------------------------------------
Every one of the 559 failures carried the same reason:

    "The underlying channel reported: Number is RCS disabled or Bot is not launched
     with the number's provider."

That is terminal for that recipient until either their handset enables RCS or the agent
is launched with their operator. Neither changes because we send again. Yet the
distribution shows one recipient was sent **90** messages and failed all 90, with a long
tail behind it - nothing in the system learned from a permanent failure.

`classify_failure` separates that terminal class from genuinely transient faults, so a
caller can suppress the hopeless ones instead of paying for them repeatedly. It does not
itself suppress anything; it only supplies the verdict.

Why the reason string is matched rather than a code
---------------------------------------------------
Sinch's RCS delivery report carries `reason.description` as prose and no stable
machine-readable subcode for this case. Matching prose is fragile, so the matcher keys
on several independent fragments and defaults to TRANSIENT when none is recognised -
because the cost of misreading a permanent failure as transient is a wasted retry, while
the reverse silently drops a recipient who could have been reached.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

#: Sinch RCS status -> our canonical status. Mirrors `rcs-dlr.RCS_STATUS_MAP`, which
#: this module supersedes as the single definition.
SINCH_TO_CANONICAL = {
    "QUEUED": "sent",
    "QUEUED_ON_CHANNEL": "queued_on_channel",
    "DELIVERED": "delivered",
    "READ": "read",
    "FAILED": "failed",
    "DELETED": "deleted",
}

#: The ladder. Reasoning for the three non-obvious placements:
#:
#: `queued_on_channel` sits above `sent` because it is strictly more information - Sinch
#: has handed the message to the RCS channel - but still below any handset signal.
#:
#: `failed` sits BELOW `delivered` and `read`. A failure report arriving after the
#: handset confirmed arrival is refused: positive evidence of delivery outranks an
#: earlier failure. A `failed` after `queued_on_channel` applies normally, which is the
#: common real case and accounts for the 559.
#:
#: `deleted` is highest because message revocation is an explicit later act by the
#: sender, not a delivery signal that could arrive out of order.
STATUS_RANK = {
    "pending": 10,
    "sent": 20,
    "queued_on_channel": 30,
    "failed": 40,
    "delivered": 50,
    "read": 60,
    "deleted": 70,
}

RANK_ATTRIBUTE = "rcsStatusRank"

TERMINAL_STATUSES = frozenset({"read", "deleted"})

# Fragments that identify the terminal "this recipient cannot receive RCS" class.
# Independent fragments rather than one exact string, because the prose has changed
# before and will again.
_PERMANENT_FRAGMENTS = (
    "rcs disabled",
    "not launched",
    "bot is not launched",
    "not rcs capable",
    "not capable",
    "invalid recipient",
    "recipient not found",
    "unregistered",
)

# Transient markers win over permanent ones when both appear, because a throttle or an
# outage can mention capability in passing.
_TRANSIENT_FRAGMENTS = (
    "timeout", "timed out", "throttl", "rate limit", "temporarily",
    "try again", "unavailable", "internal error", "server error",
)

PERMANENT = "PERMANENT"
TRANSIENT = "TRANSIENT"

_WHITESPACE = re.compile(r"\s+")


def canonical(sinch_status: Optional[str]) -> str:
    """Map a Sinch status onto our vocabulary; '' when unrecognised.

    Returning '' rather than lower-casing an unknown value keeps an unrecognised status
    at rank 0, so a status Sinch adds later cannot silently outrank `read`.
    """
    if not sinch_status:
        return ""
    key = str(sinch_status).strip().upper()
    return SINCH_TO_CANONICAL.get(key, "")


def rank(status: Optional[str]) -> int:
    """Rank of a canonical status; 0 for unknown or missing."""
    if not status:
        return 0
    return STATUS_RANK.get(str(status).strip().lower(), 0)


def is_terminal(status: Optional[str]) -> bool:
    return str(status or "").strip().lower() in TERMINAL_STATUSES


def should_apply(current: Optional[str], incoming: Optional[str]) -> Tuple[bool, str]:
    """`(apply, reason)` for a delivery report.

    `reason` is a short stable token, safe as a log field and a metric dimension.
    """
    incoming_rank = rank(incoming)
    if incoming_rank == 0:
        return False, "unknown_status"
    if not current:
        return True, "initial"
    if str(current).strip().lower() == str(incoming).strip().lower():
        return False, "duplicate_status"
    if is_terminal(current):
        return False, f"terminal_{str(current).strip().lower()}"
    if incoming_rank <= rank(current):
        return False, "out_of_order"
    return True, "forward"


def condition_expression() -> str:
    """Atomic form of `should_apply`, for a DynamoDB ConditionExpression.

    The `attribute_not_exists` arm admits both the first report for a message and every
    row written before this attribute existed - without it, the 730 messages already in
    the table would be frozen at whatever status they currently hold.
    """
    return (f"attribute_exists(id) AND "
            f"(attribute_not_exists({RANK_ATTRIBUTE}) OR {RANK_ATTRIBUTE} < :rank)")


def classify_failure(reason: Optional[str]) -> Tuple[str, str]:
    """`(disposition, category)` for a failure reason string.

    `PERMANENT` means sending to this recipient again cannot succeed until something
    outside our control changes - their handset enables RCS, or the agent is launched
    with their operator. `TRANSIENT` means a retry is reasonable.

    Defaults to `TRANSIENT` for an unrecognised reason: a wasted retry is cheaper than
    silently writing off a reachable customer.
    """
    text = _WHITESPACE.sub(" ", str(reason or "")).strip().lower()
    if not text:
        return TRANSIENT, "NO_REASON"

    for fragment in _TRANSIENT_FRAGMENTS:
        if fragment in text:
            return TRANSIENT, fragment.upper().replace(" ", "_")[:40]

    for fragment in _PERMANENT_FRAGMENTS:
        if fragment in text:
            return PERMANENT, fragment.upper().replace(" ", "_")[:40]

    return TRANSIENT, "UNRECOGNISED"


def is_rcs_unreachable(reason: Optional[str]) -> bool:
    """True for the specific 'RCS disabled or bot not launched' class.

    Narrower than `classify_failure` and named for what it means operationally: this
    recipient is not addressable over RCS right now, and 559 of 559 failures in the
    measured window were this.
    """
    disposition, _ = classify_failure(reason)
    if disposition != PERMANENT:
        return False
    text = _WHITESPACE.sub(" ", str(reason or "")).strip().lower()
    return any(f in text for f in ("rcs disabled", "not launched", "not capable"))


def describe(status: Optional[str]) -> str:
    """Short explanation, safe for logs. Never includes a recipient or content."""
    r = rank(status)
    if r == 0:
        return f"unknown status {status!r} (rank 0, will not overwrite a known status)"
    parts = [f"{status} (rank {r})"]
    if is_terminal(status):
        parts.append("terminal")
    return ", ".join(parts)
