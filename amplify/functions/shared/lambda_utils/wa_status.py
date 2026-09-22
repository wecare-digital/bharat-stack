"""Monotonic WhatsApp message-status ordering.

The problem this solves
-----------------------
Meta delivers one status webhook per transition, and the transport guarantees
neither order nor exactly-once. Until 2026-09-21 `_process_status` applied every
one with an unconditional

    SET #status = :status, statusUpdatedAt = :ts

so the last webhook to arrive won, whatever it said. Two consequences, both of
which corrupt what an operator sees in the inbox:

  * a late-arriving `sent` overwrites `read` - the message appears unread again
  * a re-delivered `failed` overwrites `delivered` - a delivered message appears
    to have failed, and the tooltip invents a reason for it

There was also no deduplication on the status path. Deduplicating by wamid alone
would be wrong there, because one wamid legitimately produces four status events;
the ordering guard below is the right shape, and it makes duplicates harmless as
a side effect since re-applying the same rank is refused.

The ranking
-----------
    accepted  1   we have Meta's send response, nothing more
    sent      2   Meta reports it left the platform
    failed    3   terminal for a message that never arrived
    delivered 4   reached the handset
    read      5   opened by the recipient

`accepted` exists because the send response is not a delivery signal. Meta's
response carries `messages[0].id` and, where present, `message_status:
"accepted"`. Writing `sent` at that moment claims something the platform has not
said yet.

`failed` sits between `sent` and `delivered` deliberately. A `failed` arriving
after `sent` applies, which is the common real case. A `failed` arriving after
`delivered` or `read` is refused, because a message that demonstrably reached the
handset did not fail. The residual oddity is that a `delivered` arriving after a
`failed` is allowed to win; that is the intended reading - positive evidence of
arrival is stronger than an earlier failure report - but it is a judgement, not a
law, so it is written down here rather than buried in a comparison.

An unknown status gets rank 0 and is therefore never applied over a known one.
That is deliberate: a status Meta adds in future should not silently outrank
`read` before anyone has decided what it means.
"""

from __future__ import annotations

from typing import Any, Optional

STATUS_RANK: dict[str, int] = {
    "accepted": 1,
    "sent": 2,
    "failed": 3,
    "delivered": 4,
    "read": 5,
}

# The attribute the rank is persisted under, so the guard can be expressed as a
# DynamoDB ConditionExpression rather than a read-then-write race.
RANK_ATTRIBUTE = "statusRank"


def rank(status: Optional[str]) -> int:
    """Rank of a status; 0 for unknown or missing."""
    if not status:
        return 0
    return STATUS_RANK.get(str(status).strip().lower(), 0)


def is_known(status: Optional[str]) -> bool:
    return rank(status) > 0


def should_apply(current: Optional[str], incoming: Optional[str]) -> bool:
    """Would `incoming` be a forward transition from `current`?

    Used for in-memory decisions and for tests. The authoritative enforcement is
    the ConditionExpression built by `condition_expression()`, because two
    webhooks can be processed concurrently and a read-then-write would let both
    through.
    """
    incoming_rank = rank(incoming)
    if incoming_rank == 0:
        return False
    return incoming_rank > rank(current)


def condition_expression() -> str:
    """Atomic guard: apply only when this rank beats the stored one.

    Rows written before this attribute existed have no `statusRank`, so the
    `attribute_not_exists` arm lets the first status after deployment through and
    establishes the rank from then on.
    """
    return f"attribute_not_exists({RANK_ATTRIBUTE}) OR {RANK_ATTRIBUTE} < :rank"


def terminal_statuses() -> frozenset:
    """Statuses after which no further transition is expected."""
    return frozenset({"read", "failed"})


def describe(status: Optional[str]) -> str:
    """Short explanation, safe for logs. Never includes message content."""
    r = rank(status)
    if r == 0:
        return f"unknown status {status!r}, rank 0, will not overwrite a known status"
    return f"{status} (rank {r})"
