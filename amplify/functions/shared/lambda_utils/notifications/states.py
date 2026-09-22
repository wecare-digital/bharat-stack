"""The notification delivery state machine: legal moves, and which receipt wins.

Two questions, deliberately answered by two different mechanisms
---------------------------------------------------------------
``can_transition(a, b)``  is this move legal at all?
``rank(state)``           if two receipts race, which one is further along?

They are not the same question and collapsing them produces a subtle bug either
way round. A pure transition table cannot decide a race, because both moves are
individually legal and the loser overwrites the winner depending on arrival order.
A pure rank comparison cannot express "SKIPPED is decided before we ever send, so
nothing follows it" - rank would happily let a stray `SENT` land on a channel that
was never eligible.

So: the table is the authority on legality, the rank is the authority on ordering,
and ``apply_receipt`` requires **both**. The DynamoDB guard in ``store.py``
enforces the same pair as one ConditionExpression, because a read-then-write here
is exactly the race being defended against.

The ladder
----------
::

    PENDING                  10   claimed, nothing published yet
    READY                    20   published to the outbox, awaiting a worker
    LEASED                   30   a worker holds it
    RECONCILIATION_REQUIRED  40   we called the provider; outcome unknown
    ACCEPTED                 50   provider took it; not a delivery signal
    SENT                     60   provider reports it left their platform
    FAILED                   70   terminal, permanent
    DELIVERED                80   reached the handset
    READ                     90   opened
    SKIPPED                  95   terminal by policy; never on a sent channel

Three placements are judgements rather than arithmetic, so they are written down
here instead of being implied by the numbers:

``ACCEPTED`` is separate from ``SENT`` for the same reason it is in
``lambda_utils.wa_status``: a provider's 200 to a send request carries a message
id, not evidence of transmission. Writing ``SENT`` at that moment claims something
the provider has not said. This mattered in production once already - see the
Phase 2 status lifecycle fix - and the notification domain must not reintroduce it.

``FAILED`` (70) sits **below** ``DELIVERED`` (80). A failure report arriving after
the handset confirmed arrival is refused: positive evidence of delivery is
stronger than an earlier, possibly stale, failure. A ``FAILED`` after ``SENT``
applies normally, which is the common real case.

``SKIPPED`` (95) outranks everything, which looks odd until you check the table:
it is reachable only from ``PENDING`` and ``READY``. The high rank stops a late
receipt from a *different* channel's confused worker resurrecting a channel that
policy already closed; the table stops it being reached after a send. Both guards
point the same way.

``RECONCILIATION_REQUIRED`` (40) is below ``ACCEPTED`` on purpose. It means "we do
not know", and any real outcome we later learn - accepted, sent, delivered, failed
- is more informative and must be allowed to replace it. It is not a failure and
must never be reported as one; the brief requires it whenever a provider may have
accepted a send but the response was lost.

Transient failure is not a state
--------------------------------
There is no ``TRANSIENT_FAILED``. A transient fault returns the delivery to
``READY`` for a bounded retry, and only a permanent fault or an exhausted attempt
budget reaches ``FAILED``. That is why ``LEASED -> READY`` is legal: it is the
retry edge, and it is also how an expired lease is reclaimed.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple

PENDING = "PENDING"
READY = "READY"
LEASED = "LEASED"
RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
ACCEPTED = "ACCEPTED"
SENT = "SENT"
FAILED = "FAILED"
DELIVERED = "DELIVERED"
READ = "READ"
SKIPPED = "SKIPPED"

STATE_RANK: dict = {
    PENDING: 10,
    READY: 20,
    LEASED: 30,
    RECONCILIATION_REQUIRED: 40,
    ACCEPTED: 50,
    SENT: 60,
    FAILED: 70,
    DELIVERED: 80,
    READ: 90,
    SKIPPED: 95,
}

ALL_STATES = frozenset(STATE_RANK)

#: Nothing follows these. ``DELIVERED`` is absent deliberately - ``READ`` follows it.
TERMINAL_STATES = frozenset({READ, FAILED, SKIPPED})

#: States from which *someone* may still be required to act - a sender or a reconciler.
ACTIONABLE_STATES = frozenset({PENDING, READY, LEASED, RECONCILIATION_REQUIRED})

#: States from which a SEND may still happen. Narrower than `ACTIONABLE_STATES`, and
#: narrower than "not terminal", which is the distinction that matters.
#:
#: Two states are deliberately excluded:
#:
#: ``ACCEPTED`` is not terminal - ``DELIVERED`` and ``READ`` follow it - so a
#: "not terminal, not out of attempts" test treats it as work to do and sends the
#: message a second time. A duplicate queue delivery is the normal case with SQS, not an
#: edge case, so that test is wrong exactly when it matters most. Found by a failing
#: test, not by review.
#:
#: ``RECONCILIATION_REQUIRED`` is actionable, but by a *reconciler*, not by the sender.
#: Letting the sender act on it would defeat its entire purpose: the state exists
#: precisely because the provider may already have sent the message.
SENDABLE_STATES = frozenset({PENDING, READY, LEASED})

#: The attribute the rank is persisted under, so the ordering guard can be a
#: ConditionExpression rather than a read-then-write.
RANK_ATTRIBUTE = "stateRank"

#: Transitions that are deliberately BACKWARDS on the ladder.
#:
#: The rank guard exists to reject a stale receipt from a provider - a late `SENT`
#: landing on a row that already reached `DELIVERED`. It must not reject a rewind
#: the system itself performs on purpose, and there are exactly two of those: a
#: transient failure handing the job back for a bounded retry, and a reconciler
#: handing an unknown outcome back for one more attempt. Both land on `READY`, both
#: move down the ladder, and both are correct.
#:
#: This distinction was missing in the first draft and the tests caught it: a
#: transient retry was refused as `out_of_order`, which would have stranded every
#: retryable delivery at `LEASED` until its lease expired, forever. Rank alone
#: cannot express "backwards, but intended", so the intended edges are enumerated.
#:
#: Enumerated rather than inferred: a rule like "any move to READY is a rewind"
#: would also admit `DELIVERED -> READY`, which is not a retry, it is losing a
#: delivery confirmation.
REWIND_EDGES = frozenset({
    (LEASED, READY),
    (RECONCILIATION_REQUIRED, READY),
})

#: Reverse index of `REWIND_EDGES`, for building the atomic guard: to rewind to
#: `READY` the stored state must be one of these.
REWIND_SOURCES: dict = {}
for _source, _target in REWIND_EDGES:
    REWIND_SOURCES.setdefault(_target, set()).add(_source)
REWIND_SOURCES = {k: tuple(sorted(v)) for k, v in REWIND_SOURCES.items()}

_ALLOWED: dict = {
    # Claimed but not yet published. SKIPPED here is the ineligible-channel path.
    PENDING: frozenset({READY, SKIPPED, FAILED}),
    # Published to the outbox. A worker leases it; policy may still close it.
    READY: frozenset({LEASED, SKIPPED, FAILED}),
    # A worker holds it. READY is the retry/lease-reclaim edge.
    LEASED: frozenset({READY, ACCEPTED, SENT, FAILED, RECONCILIATION_REQUIRED}),
    # We do not know what the provider did. Any real answer may replace it, and a
    # reconciler may hand it back for one more bounded attempt.
    RECONCILIATION_REQUIRED: frozenset({READY, ACCEPTED, SENT, DELIVERED, READ, FAILED}),
    # Provider took it. Receipts may now arrive in any order.
    ACCEPTED: frozenset({SENT, DELIVERED, READ, FAILED}),
    SENT: frozenset({DELIVERED, READ, FAILED}),
    DELIVERED: frozenset({READ}),
    READ: frozenset(),
    FAILED: frozenset(),
    SKIPPED: frozenset(),
}


def normalize(state: Optional[str]) -> str:
    """Upper-cased, trimmed state name, or `''` when it is not a known state.

    Returning `''` rather than raising lets callers treat an unrecognised state as
    "no information", which is the safe reading for a value that arrived from a
    provider or from an older row written before a state existed.
    """
    if not state:
        return ""
    candidate = str(state).strip().upper()
    return candidate if candidate in ALL_STATES else ""


def rank(state: Optional[str]) -> int:
    """Position on the ladder; 0 for unknown or missing.

    0 means an unknown state can never win a comparison, so a state added by a
    future provider integration cannot silently outrank ``READ`` before anybody has
    decided what it means.
    """
    return STATE_RANK.get(normalize(state), 0)


def is_terminal(state: Optional[str]) -> bool:
    return normalize(state) in TERMINAL_STATES


def is_actionable(state: Optional[str]) -> bool:
    """Whether a worker or reconciler may still need to do something."""
    return normalize(state) in ACTIONABLE_STATES


def is_sendable(state: Optional[str]) -> bool:
    """Whether a SEND may still be attempted. See `SENDABLE_STATES`.

    This is the check a worker wants, not `not is_terminal(...)`.
    """
    return normalize(state) in SENDABLE_STATES


def is_rewind(current: Optional[str], incoming: Optional[str]) -> bool:
    """Is this one of the two intentional backwards moves? See `REWIND_EDGES`."""
    return (normalize(current), normalize(incoming)) in REWIND_EDGES


def can_transition(current: Optional[str], incoming: Optional[str]) -> bool:
    """Is `current -> incoming` a legal move?

    An absent `current` is treated as the start of life, so the initial write of
    any state is legal. A transition to the *same* state is not legal: it would be
    a duplicate, and the caller needs to be able to tell a duplicate from progress.
    """
    target = normalize(incoming)
    if not target:
        return False
    source = normalize(current)
    if not source:
        return True
    return target in _ALLOWED.get(source, frozenset())


def apply_receipt(current: Optional[str], incoming: Optional[str]) -> Tuple[bool, str]:
    """`(should_apply, reason)` for a receipt or worker outcome.

    Requires the move to be **both** legal and forward. `reason` is a short stable
    token, safe to log and to use as a metric dimension.
    """
    target = normalize(incoming)
    if not target:
        return False, "unknown_state"

    source = normalize(current)
    if not source:
        return True, "initial"

    if source == target:
        return False, "duplicate_state"
    if is_terminal(source):
        return False, f"terminal_{source.lower()}"

    # A deliberate rewind is exempt from the rank check, because it is backwards on
    # purpose. It is still checked against the transition table, so only the two
    # enumerated edges qualify.
    if is_rewind(source, target):
        return True, "rewind"

    # Rank BEFORE legality, and the order is the whole point of the two reasons.
    #
    # A late `SENT` landing on a row that already reached `DELIVERED` is normal,
    # expected provider behaviour - Meta really does deliver status webhooks out of
    # order. Reporting that as `illegal_transition` would send an operator hunting a
    # bug that is not there. `out_of_order` says "a stale receipt arrived and was
    # correctly ignored", which is the truth.
    #
    # Checking legality first would swallow it: `DELIVERED`'s only successor is
    # `READ`, so the table rejects `SENT` before the rank comparison ever runs.
    # `illegal_transition` is then reserved for a move that is genuinely forward but
    # not permitted - `PENDING -> DELIVERED`, say - which does indicate something
    # unexpected upstream.
    if rank(target) <= rank(source):
        return False, "out_of_order"
    if not can_transition(source, target):
        return False, "illegal_transition"
    return True, "forward"


def condition_expression(incoming: Optional[str] = None, *,
                         allow_initial: bool = True) -> str:
    """The atomic form of `apply_receipt`, for a DynamoDB ConditionExpression.

    Pairs with `condition_values(incoming)`, and the two must be built from the same
    `incoming` - the guard shape depends on it.

    **Receipt guard** (the normal case): the rank must move forward, and the current
    state must not already be terminal. Expressed against ``stateRank`` rather than
    ``state`` so one numeric comparison covers the whole ladder. The
    ``attribute_not_exists`` arm admits the first write for a delivery, and also
    admits rows written before this attribute existed - without it, migrated history
    would be frozen at whatever state it held.

    **Rewind guard** (`incoming` is a rewind target, i.e. ``READY``): a rank
    comparison is the wrong test, because the move is backwards by design. Instead the
    stored state must be exactly one of the declared rewind sources. That is stricter
    than the rank form, not looser: it admits `LEASED -> READY` and
    `RECONCILIATION_REQUIRED -> READY` and nothing else, so it cannot be used to
    rewind a `DELIVERED` row and lose a delivery confirmation.
    """
    not_terminal = ("(attribute_not_exists(#state) OR NOT #state IN "
                    "(:t_read, :t_failed, :t_skipped))")

    sources = REWIND_SOURCES.get(normalize(incoming)) if incoming else None
    if sources:
        placeholders = ", ".join(f":rw{i}" for i in range(len(sources)))
        rewind = f"#state IN ({placeholders})"
        if allow_initial:
            rewind = f"(attribute_not_exists({RANK_ATTRIBUTE}) OR {rewind})"
        return f"{rewind} AND {not_terminal}"

    forward = f"{RANK_ATTRIBUTE} < :rank"
    if allow_initial:
        forward = f"(attribute_not_exists({RANK_ATTRIBUTE}) OR {forward})"
    return f"{forward} AND {not_terminal}"


def condition_values(incoming: str) -> dict:
    """ExpressionAttributeValues for `condition_expression(incoming)`.

    Always supplies ``:rank`` even for a rewind, because the update expression sets
    ``stateRank`` regardless of which guard shape was used - the row's rank must end
    up matching its state either way.
    """
    values = {
        ":rank": rank(incoming),
        ":t_read": READ,
        ":t_failed": FAILED,
        ":t_skipped": SKIPPED,
    }
    for index, source in enumerate(REWIND_SOURCES.get(normalize(incoming), ())):
        values[f":rw{index}"] = source
    return values


def describe(state: Optional[str]) -> str:
    """Short explanation, safe for logs. Never includes recipient or content."""
    normalized = normalize(state)
    if not normalized:
        return f"unknown state {state!r} (rank 0, cannot overwrite a known state)"
    parts = [f"{normalized} (rank {STATE_RANK[normalized]})"]
    if normalized in TERMINAL_STATES:
        parts.append("terminal")
    elif normalized in ACTIONABLE_STATES:
        parts.append("actionable")
    return ", ".join(parts)


def successors(state: Optional[str]) -> Iterable[str]:
    """Legal next states, for diagnostics and for the transition tests."""
    return sorted(_ALLOWED.get(normalize(state), frozenset()))
