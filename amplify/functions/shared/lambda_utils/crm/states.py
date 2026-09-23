"""Lead and opportunity state machines, and what makes a stage move legal.

Three separate questions, deliberately not collapsed
----------------------------------------------------
``lead_can_transition(a, b)``      may a lead move like this?
``opportunity_can_transition``     may an opportunity's *outcome* move like this?
``stage_move_is_legal(...)``       may an opportunity sit in this stage?

The third is not a state machine at all, and that is the point. Stage membership is
**configuration**, not lifecycle: a pipeline's stages are rows a user can add, rename
and reorder. Hard-coding stage transitions would mean a user reordering their pipeline
silently invalidates live opportunities. So stages are validated structurally - the
stage must belong to the opportunity's pipeline - while the *outcome* (open, won, lost)
is the thing with a real state machine.

Why stage movement is free, not forward-only
--------------------------------------------
Real deals regress. A prospect who reached Negotiation and went quiet belongs back in
Qualification, and a CRM that refuses that move gets worked around by the user creating
a duplicate opportunity - which destroys the forecast far more thoroughly than a
backwards move does. So any OPEN stage of the same pipeline is reachable from any other.

What is *not* free is leaving a terminal outcome. WON and LOST are commitments: a won
deal is reported in revenue, a lost one in win-rate. Silently reopening either
rewrites history that has already been counted. So leaving a terminal outcome requires
an explicit `reopen` - the caller has to say so.

Why `LOST -> WON` is refused outright
-------------------------------------
Not because it is implausible, but because it is ambiguous: it could mean "we were wrong
to mark it lost" or "they came back". The first is a correction, the second is a new
opportunity, and they mean opposite things to a win-rate figure. Forcing the caller
through `reopen -> OPEN -> WON` makes the correction explicit and leaves an Activity
row saying so.

Lead states
-----------
::

    NEW         captured, nobody has looked at it
    WORKING     someone is engaging
    NURTURING   real but not now; parked deliberately, not forgotten
    QUALIFIED   ready to become an opportunity
    CONVERTED   terminal; an opportunity exists and its id is on the lead
    DISQUALIFIED terminal; with a reason
    JUNK        terminal; spam, test traffic, a wrong number

`CONVERTED` is terminal and one-way. A converted lead must never move again, because its
opportunity is now the live record and two writers editing two rows is how the funnel
starts disagreeing with itself.

`JUNK` is separate from `DISQUALIFIED` because they mean different things to a
conversion rate: disqualified leads were real enquiries that did not fit, junk was never
an enquiry. Averaging them together flatters or damns the marketing spend depending on
how much spam arrives, which is not a signal anyone wants in that number.

`NURTURING` exists so that "not now" has somewhere to go that is not DISQUALIFIED.
Without it, every parked lead is either falsely dead or falsely active.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional, Tuple

# ---------------------------------------------------------------------------
# Lead lifecycle
# ---------------------------------------------------------------------------

LEAD_NEW = "NEW"
LEAD_WORKING = "WORKING"
LEAD_NURTURING = "NURTURING"
LEAD_QUALIFIED = "QUALIFIED"
LEAD_CONVERTED = "CONVERTED"
LEAD_DISQUALIFIED = "DISQUALIFIED"
LEAD_JUNK = "JUNK"

LEAD_STATES: Tuple[str, ...] = (
    LEAD_NEW, LEAD_WORKING, LEAD_NURTURING, LEAD_QUALIFIED,
    LEAD_CONVERTED, LEAD_DISQUALIFIED, LEAD_JUNK,
)

#: States from which nothing follows. `CONVERTED` is here because the opportunity is now
#: the record of truth; the other two because the lead is closed.
LEAD_TERMINAL: FrozenSet[str] = frozenset({LEAD_CONVERTED, LEAD_DISQUALIFIED, LEAD_JUNK})

#: Only a QUALIFIED lead may convert. Converting straight from NEW is tempting and wrong:
#: it produces opportunities nobody has assessed, which is how a forecast fills with
#: noise. `service.qualify_lead` is one call, so this costs a step, not a redesign.
LEAD_CONVERTIBLE: FrozenSet[str] = frozenset({LEAD_QUALIFIED})

_LEAD_EDGES: Dict[str, FrozenSet[str]] = {
    LEAD_NEW: frozenset({LEAD_WORKING, LEAD_NURTURING, LEAD_QUALIFIED,
                         LEAD_DISQUALIFIED, LEAD_JUNK}),
    # Working leads may be parked, qualified, or closed. They may also return to NEW,
    # which is what reassignment looks like when the previous owner never engaged.
    LEAD_WORKING: frozenset({LEAD_NEW, LEAD_NURTURING, LEAD_QUALIFIED,
                            LEAD_DISQUALIFIED, LEAD_JUNK}),
    # A nurtured lead waking up goes back to WORKING, not straight to QUALIFIED: the
    # re-engagement has to actually happen before it counts as assessed.
    LEAD_NURTURING: frozenset({LEAD_WORKING, LEAD_QUALIFIED,
                              LEAD_DISQUALIFIED, LEAD_JUNK}),
    # Qualified can still fall back - qualification is a judgement and judgements change.
    LEAD_QUALIFIED: frozenset({LEAD_WORKING, LEAD_NURTURING, LEAD_CONVERTED,
                              LEAD_DISQUALIFIED, LEAD_JUNK}),
    LEAD_CONVERTED: frozenset(),
    # A lead closed in error can be reopened to WORKING. Deliberately not to NEW: it has
    # been touched, and pretending otherwise corrupts response-time measurement.
    LEAD_DISQUALIFIED: frozenset({LEAD_WORKING}),
    LEAD_JUNK: frozenset({LEAD_WORKING}),
}


def lead_can_transition(current: Optional[str], target: str) -> bool:
    """Is this lead move legal? Unknown states are refused, not guessed."""
    if target not in LEAD_STATES:
        return False
    if current is None:
        # Creation. Only NEW is a legal starting point; anything else means a caller is
        # fabricating history, e.g. importing a lead as already CONVERTED with no
        # opportunity behind it.
        return target == LEAD_NEW
    if current not in LEAD_STATES:
        return False
    if current == target:
        # Idempotent re-assert of the same state is not a transition and must not be
        # treated as an error - webhook replays do this constantly.
        return True
    return target in _LEAD_EDGES.get(current, frozenset())


def lead_is_terminal(state: Optional[str]) -> bool:
    return state in LEAD_TERMINAL


def lead_is_convertible(state: Optional[str]) -> bool:
    return state in LEAD_CONVERTIBLE


# ---------------------------------------------------------------------------
# Opportunity outcome
# ---------------------------------------------------------------------------

OPP_OPEN = "OPEN"
OPP_WON = "WON"
OPP_LOST = "LOST"
OPP_ABANDONED = "ABANDONED"

OPPORTUNITY_STATES: Tuple[str, ...] = (OPP_OPEN, OPP_WON, OPP_LOST, OPP_ABANDONED)

OPPORTUNITY_TERMINAL: FrozenSet[str] = frozenset({OPP_WON, OPP_LOST, OPP_ABANDONED})

#: `ABANDONED` is not `LOST`. Lost means we competed and did not win, which belongs in a
#: win-rate denominator. Abandoned means the deal evaporated - the contact vanished, the
#: requirement was withdrawn - and counting that as a loss makes the sales process look
#: worse than it is. Both are terminal; only one is a competitive outcome.

_OPP_EDGES: Dict[str, FrozenSet[str]] = {
    OPP_OPEN: frozenset({OPP_WON, OPP_LOST, OPP_ABANDONED}),
    # Terminal outcomes reopen only to OPEN, and only with `reopen=True`. Note the
    # deliberate absence of WON <-> LOST: see the module docstring.
    OPP_WON: frozenset({OPP_OPEN}),
    OPP_LOST: frozenset({OPP_OPEN}),
    OPP_ABANDONED: frozenset({OPP_OPEN}),
}


def opportunity_can_transition(current: Optional[str], target: str, *,
                               reopen: bool = False) -> bool:
    """Is this outcome move legal?

    `reopen` is a required, explicit acknowledgement when leaving a terminal outcome. It
    is a parameter rather than a separate function so that every caller of this predicate
    has to decide, rather than a reopen path existing that some callers never learn about.
    """
    if target not in OPPORTUNITY_STATES:
        return False
    if current is None:
        return target == OPP_OPEN
    if current not in OPPORTUNITY_STATES:
        return False
    if current == target:
        return True
    if current in OPPORTUNITY_TERMINAL and not reopen:
        return False
    return target in _OPP_EDGES.get(current, frozenset())


def opportunity_is_terminal(state: Optional[str]) -> bool:
    return state in OPPORTUNITY_TERMINAL


def opportunity_is_open(state: Optional[str]) -> bool:
    return state == OPP_OPEN


# ---------------------------------------------------------------------------
# Stage membership
# ---------------------------------------------------------------------------

#: A stage's role within its pipeline. `OPEN` stages are the working funnel; the two
#: closed kinds exist so that entering a stage can *imply* an outcome, which is how every
#: usable CRM board works - dragging a card to "Won" should win the deal, not require a
#: second action the user will forget.
STAGE_OPEN = "OPEN"
STAGE_WON = "WON"
STAGE_LOST = "LOST"

STAGE_KINDS: Tuple[str, ...] = (STAGE_OPEN, STAGE_WON, STAGE_LOST)

#: Mapping from a closed stage kind to the outcome entering it implies. Absence means the
#: stage implies nothing and the outcome is left alone.
STAGE_KIND_OUTCOME: Dict[str, str] = {
    STAGE_WON: OPP_WON,
    STAGE_LOST: OPP_LOST,
}


class StageMoveRefused(ValueError):
    """A stage move that would corrupt the pipeline, with the reason.

    A distinct type because these are not user errors to be smoothed over - each one
    means either the request is wrong or two pipelines have been mixed up, and silently
    picking a stage would produce an opportunity nobody can find on any board.
    """


def stage_move_is_legal(*, opportunity_pipeline_id: str,
                        stage_pipeline_id: Optional[str],
                        stage_kind: Optional[str],
                        current_outcome: Optional[str],
                        reopen: bool = False) -> Tuple[bool, str]:
    """`(legal, reason)` for placing an opportunity in a stage.

    Structural first, lifecycle second. The cross-pipeline check comes before the outcome
    check because a stage from another pipeline makes the outcome question meaningless -
    and because that is the failure that actually happens, when a stage id is copied
    between environments or a pipeline is duplicated.
    """
    if not stage_pipeline_id:
        return False, "stage does not exist"
    if stage_pipeline_id != opportunity_pipeline_id:
        # The important one. An opportunity in a stage belonging to another pipeline
        # appears on no board: not its own (wrong stage) and not the other (wrong
        # pipeline). It is invisible rather than merely misplaced.
        return False, "stage belongs to a different pipeline"
    if stage_kind not in STAGE_KINDS:
        return False, f"stage has an unknown kind: {stage_kind!r}"

    implied = STAGE_KIND_OUTCOME.get(stage_kind)
    target_outcome = implied or OPP_OPEN

    if not opportunity_can_transition(current_outcome, target_outcome, reopen=reopen):
        if current_outcome in OPPORTUNITY_TERMINAL and not reopen:
            return False, (f"opportunity is {current_outcome}; pass reopen to move it "
                           "back into the funnel")
        return False, f"{current_outcome} -> {target_outcome} is not a legal outcome move"
    return True, "ok"


def outcome_for_stage_kind(stage_kind: Optional[str],
                           current_outcome: Optional[str]) -> str:
    """The outcome an opportunity should hold once it sits in a stage of this kind.

    An OPEN stage returns OPEN even when the opportunity was terminal, because moving a
    won deal back onto the board is precisely what reopening means. The legality of doing
    so is `stage_move_is_legal`'s job, not this function's - this one only says what the
    resulting value is.
    """
    implied = STAGE_KIND_OUTCOME.get(stage_kind or "")
    if implied:
        return implied
    return OPP_OPEN if current_outcome != OPP_OPEN else OPP_OPEN


# ---------------------------------------------------------------------------
# Activity kinds
# ---------------------------------------------------------------------------

#: The timeline is append-only and typed. Free-text activity types were considered and
#: rejected: within a month they become forty spellings of "call", and no report can
#: group them.
ACTIVITY_NOTE = "NOTE"
ACTIVITY_CALL = "CALL"
ACTIVITY_MESSAGE = "MESSAGE"
ACTIVITY_EMAIL = "EMAIL"
ACTIVITY_MEETING = "MEETING"
ACTIVITY_TASK = "TASK"
ACTIVITY_STAGE_CHANGE = "STAGE_CHANGE"
ACTIVITY_STATE_CHANGE = "STATE_CHANGE"
ACTIVITY_SYSTEM = "SYSTEM"

ACTIVITY_KINDS: Tuple[str, ...] = (
    ACTIVITY_NOTE, ACTIVITY_CALL, ACTIVITY_MESSAGE, ACTIVITY_EMAIL,
    ACTIVITY_MEETING, ACTIVITY_TASK, ACTIVITY_STAGE_CHANGE,
    ACTIVITY_STATE_CHANGE, ACTIVITY_SYSTEM,
)

#: Kinds the system writes and a user must not forge, because they are the audit trail
#: for stage and state movement. A user-supplied STAGE_CHANGE would let the timeline
#: claim a transition that never happened.
ACTIVITY_SYSTEM_ONLY: FrozenSet[str] = frozenset({
    ACTIVITY_STAGE_CHANGE, ACTIVITY_STATE_CHANGE, ACTIVITY_SYSTEM,
})

#: Kinds that represent an intention rather than a record, so they may be open or done.
#: Only TASK: a note is written, a call happened, but a task is owed.
ACTIVITY_COMPLETABLE: FrozenSet[str] = frozenset({ACTIVITY_TASK})


def activity_kind_is_valid(kind: Optional[str]) -> bool:
    return kind in ACTIVITY_KINDS


def activity_kind_is_user_writable(kind: Optional[str]) -> bool:
    return kind in ACTIVITY_KINDS and kind not in ACTIVITY_SYSTEM_ONLY
