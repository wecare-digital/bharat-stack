"""The softphone device/session state machine, and the leg distinction that matters.

Two different things called "connected"
---------------------------------------
This is the whole reason the module exists, and it is the mistake the brief singles out.

A browser softphone call has **two legs**:

    leg A   our Lambda -> Plivo -> the browser SDK        the agent's own connection
    leg B   Plivo -> the PSTN -> the customer's handset   the other party

The Browser SDK raises `onCallAnswered` when **leg A** is up. That means the agent's tab
is in the call. It says nothing at all about whether the customer picked up: leg B may
still be ringing, may hit voicemail, may fail on a carrier reject.

If those are conflated, the consequences are concrete and all bad. The UI shows
"connected" while the customer's phone is still ringing. Talk-time billing starts early.
And - the one that reaches a customer - the connected-call notification fires, so somebody
who never answered receives a WhatsApp message saying we spoke. `lambda_utils.notifications`
exists to gate that, and its gate is only as good as the signal it is handed.

So this module keeps two separate fields and never derives one from the other:

    localLegState     the SDK's view of the agent's own connection
    remoteLegState    the provider's view of the far party

`remote_party_answered()` returns True only on a provider Dial callback reporting the
B-leg answered. There is deliberately no code path where a local event sets the remote
state - `apply_local_event` cannot write `remoteLegState` at all.

Registration is not readiness
-----------------------------
A registered endpoint is reachable; it is not necessarily staffed. An agent can be
registered with the tab in the background, on another call, or on a break. So presence is
tracked separately from registration, and `can_receive_call` requires both.

Why every transition is explicit
--------------------------------
The Browser SDK's events arrive out of order under poor networks - `onCallTerminated`
before `onCallAnswered` is routine on a flaky connection. An implicit state machine that
just assigns whatever arrived last would then leave a session stuck "on a call" that
ended. `apply_local_event` refuses a backwards transition and reports it, which is the
same rank-guard reasoning already used for `wa_status`, `rcs_status` and `payment_status`.
"""

from __future__ import annotations

import time
from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

UNREGISTERED = "UNREGISTERED"
REGISTERING = "REGISTERING"
REGISTERED = "REGISTERED"
REGISTRATION_FAILED = "REGISTRATION_FAILED"

REGISTRATION_STATES: Tuple[str, ...] = (
    UNREGISTERED, REGISTERING, REGISTERED, REGISTRATION_FAILED,
)

_REGISTRATION_EDGES: Dict[str, FrozenSet[str]] = {
    UNREGISTERED: frozenset({REGISTERING}),
    # A token expiring mid-session drops us to REGISTERING, not UNREGISTERED: the tab is
    # still open and intends to be registered, and the distinction is what tells an
    # operator "reconnecting" apart from "signed out".
    REGISTERING: frozenset({REGISTERED, REGISTRATION_FAILED, UNREGISTERED}),
    REGISTERED: frozenset({REGISTERING, UNREGISTERED, REGISTRATION_FAILED}),
    REGISTRATION_FAILED: frozenset({REGISTERING, UNREGISTERED}),
}

# ---------------------------------------------------------------------------
# Presence - staffed, not merely reachable
# ---------------------------------------------------------------------------

AVAILABLE = "AVAILABLE"
BUSY = "BUSY"
AWAY = "AWAY"
OFFLINE = "OFFLINE"

PRESENCE_STATES: Tuple[str, ...] = (AVAILABLE, BUSY, AWAY, OFFLINE)

#: Presence values that accept a new call. `BUSY` is excluded because it is set when a
#: call starts, so including it would let one agent take two calls.
PRESENCE_ACCEPTS_CALL: FrozenSet[str] = frozenset({AVAILABLE})

# ---------------------------------------------------------------------------
# Local leg - the SDK's view of the agent's own connection
# ---------------------------------------------------------------------------

LOCAL_IDLE = "IDLE"
LOCAL_RINGING = "RINGING"          # inbound, the agent's tab is alerting
LOCAL_DIALING = "DIALING"          # outbound, the SDK is placing the call
LOCAL_CONNECTED = "LOCAL_CONNECTED"
LOCAL_ENDED = "ENDED"
LOCAL_FAILED = "FAILED"

LOCAL_STATES: Tuple[str, ...] = (
    LOCAL_IDLE, LOCAL_RINGING, LOCAL_DIALING, LOCAL_CONNECTED,
    LOCAL_ENDED, LOCAL_FAILED,
)

#: Rank, so an out-of-order SDK event cannot move the session backwards.
#: `onCallTerminated` arriving before `onCallAnswered` is routine on a poor network.
LOCAL_RANK: Dict[str, int] = {
    LOCAL_IDLE: 0,
    LOCAL_RINGING: 10,
    LOCAL_DIALING: 10,
    LOCAL_CONNECTED: 20,
    LOCAL_FAILED: 30,
    LOCAL_ENDED: 40,
}

#: The Browser SDK event names, mapped to local-leg states. Names verified against
#: Plivo's Browser SDK reference; anything unlisted is refused rather than guessed, so a
#: new SDK event cannot silently drive the machine.
SDK_EVENTS: Dict[str, str] = {
    "onCalling": LOCAL_DIALING,
    "onIncomingCall": LOCAL_RINGING,
    "onCallAnswered": LOCAL_CONNECTED,
    "onCallTerminated": LOCAL_ENDED,
    "onCallFailed": LOCAL_FAILED,
    "onCallRemoteRinging": LOCAL_DIALING,
    "onMediaConnected": LOCAL_CONNECTED,
}

# ---------------------------------------------------------------------------
# Remote leg - the provider's view of the far party
# ---------------------------------------------------------------------------

REMOTE_UNKNOWN = "UNKNOWN"
REMOTE_RINGING = "RINGING"
REMOTE_ANSWERED = "ANSWERED"
REMOTE_NO_ANSWER = "NO_ANSWER"
REMOTE_BUSY = "BUSY"
REMOTE_FAILED = "FAILED"
REMOTE_COMPLETED = "COMPLETED"

REMOTE_STATES: Tuple[str, ...] = (
    REMOTE_UNKNOWN, REMOTE_RINGING, REMOTE_ANSWERED, REMOTE_NO_ANSWER,
    REMOTE_BUSY, REMOTE_FAILED, REMOTE_COMPLETED,
)

#: Provider Dial-callback `DialBLegStatus` / `DialStatus` values, mapped onto the remote
#: leg. Only these establish what the far party did.
PROVIDER_DIAL_STATUS: Dict[str, str] = {
    "answer": REMOTE_ANSWERED,
    "answered": REMOTE_ANSWERED,
    "completed": REMOTE_COMPLETED,
    "ringing": REMOTE_RINGING,
    "no-answer": REMOTE_NO_ANSWER,
    "noanswer": REMOTE_NO_ANSWER,
    "timeout": REMOTE_NO_ANSWER,
    "busy": REMOTE_BUSY,
    "failed": REMOTE_FAILED,
    "cancel": REMOTE_FAILED,
    "canceled": REMOTE_FAILED,
    "cancelled": REMOTE_FAILED,
}

#: The only remote states that mean the far party was actually on the call. A
#: connected-call notification may fire for these and nothing else.
REMOTE_TALKED: FrozenSet[str] = frozenset({REMOTE_ANSWERED, REMOTE_COMPLETED})


class TransitionRefused(ValueError):
    """A state move that would misreport the call. Carries the reason, never a number."""


# ---------------------------------------------------------------------------
# Session records
# ---------------------------------------------------------------------------

def new_session(*, session_id: str, actor: str, endpoint_username: str,
                at: Optional[int] = None) -> Dict[str, Any]:
    """A fresh softphone session, unregistered and with both legs unknown.

    `actor` is required: a session that cannot be attributed to a signed-in user cannot be
    audited, and the token route binds the Plivo endpoint to exactly one actor.
    """
    if not session_id:
        raise ValueError("session_id is required")
    if not actor:
        raise ValueError("actor is required; an unattributable session cannot be audited")
    if not endpoint_username:
        raise ValueError("endpoint_username is required")
    now = at if at is not None else int(time.time())
    return {
        "sessionId": session_id,
        "actorId": actor,
        "endpointUsername": endpoint_username,
        "registration": UNREGISTERED,
        "presence": OFFLINE,
        # The two legs, kept apart on purpose. See the module docstring.
        "localLegState": LOCAL_IDLE,
        "localLegRank": LOCAL_RANK[LOCAL_IDLE],
        "remoteLegState": REMOTE_UNKNOWN,
        "createdAt": now,
        "updatedAt": now,
        "lastSeenAt": now,
        # TTL: a tab closed without signing out leaves a row behind, and a stale
        # "AVAILABLE" agent is worse than no record - it routes calls into a void.
        "expiresAt": now + 86400,
    }


def registration_can_transition(current: Optional[str], target: str) -> bool:
    if target not in REGISTRATION_STATES:
        return False
    if current is None:
        return target == UNREGISTERED
    if current not in REGISTRATION_STATES:
        return False
    if current == target:
        return True
    return target in _REGISTRATION_EDGES.get(current, frozenset())


def local_rank(state: Optional[str]) -> int:
    """Rank of a local-leg state; 0 for unknown, so it never wins."""
    if not state:
        return 0
    return LOCAL_RANK.get(str(state), 0)


def apply_local_event(session: Mapping[str, Any], sdk_event: str, *,
                      at: Optional[int] = None) -> Dict[str, Any]:
    """Apply a Browser SDK event to the LOCAL leg only.

    Cannot write `remoteLegState` - by construction, not by convention. That is the
    guarantee that stops `onCallAnswered` being read as "the customer answered", which
    would start billing early and fire a connected-call notification at somebody who
    never picked up.

    Refuses a backwards move. `onCallTerminated` before `onCallAnswered` is ordinary on a
    poor network, and assigning whatever arrived last would leave a session stuck on a call
    that ended.
    """
    target = SDK_EVENTS.get(str(sdk_event))
    if not target:
        raise TransitionRefused(
            f"unknown Browser SDK event {sdk_event!r}; refusing rather than guessing "
            f"(known: {sorted(SDK_EVENTS)})")

    current = str(session.get("localLegState") or LOCAL_IDLE)
    if local_rank(target) < local_rank(current):
        raise TransitionRefused(
            f"{sdk_event} would move the local leg backwards, {current} -> {target}; "
            "SDK events arrive out of order on a poor network")

    now = at if at is not None else int(time.time())
    updated = dict(session)
    updated["localLegState"] = target
    updated["localLegRank"] = local_rank(target)
    updated["updatedAt"] = now
    updated["lastSeenAt"] = now
    if target == LOCAL_CONNECTED:
        # Named so no reader can mistake it for the moment the customer answered.
        updated["localLegConnectedAt"] = now
    if target in (LOCAL_ENDED, LOCAL_FAILED):
        updated["localLegEndedAt"] = now
    # Deliberately absent: any write to remoteLegState.
    return updated


def apply_provider_dial_status(session: Mapping[str, Any], dial_status: str, *,
                               at: Optional[int] = None) -> Dict[str, Any]:
    """Apply a provider Dial callback to the REMOTE leg only.

    This is the only function that may establish what the far party did, and it is the only
    input `remote_party_answered` trusts.
    """
    target = PROVIDER_DIAL_STATUS.get(str(dial_status or "").strip().lower())
    if not target:
        raise TransitionRefused(
            f"unknown provider dial status {dial_status!r}; refusing rather than guessing")

    now = at if at is not None else int(time.time())
    updated = dict(session)
    current = str(session.get("remoteLegState") or REMOTE_UNKNOWN)

    # Once the far party has demonstrably talked, a later `ringing` or `no-answer` for the
    # same leg is stale and must not erase that fact - the same reasoning as `failed`
    # ranking below `delivered` in wa_status.
    if current in REMOTE_TALKED and target not in REMOTE_TALKED:
        raise TransitionRefused(
            f"remote leg is {current}; refusing to overwrite positive answer evidence "
            f"with {target}")

    updated["remoteLegState"] = target
    updated["updatedAt"] = now
    if target == REMOTE_ANSWERED and not updated.get("remotePartyAnsweredAt"):
        # Captured once. This is the timestamp talk time and any connected-call
        # notification must key on.
        updated["remotePartyAnsweredAt"] = now
    return updated


def remote_party_answered(session: Optional[Mapping[str, Any]]) -> bool:
    """Did the OTHER party actually answer?

    The only safe basis for starting talk-time billing or firing a connected-call
    notification. Reads `remoteLegState` exclusively: a local leg of `LOCAL_CONNECTED`
    means the agent's browser is in the call, which is not the same fact and never implies
    this one.
    """
    if not session:
        return False
    return str(session.get("remoteLegState") or "") in REMOTE_TALKED


def local_leg_connected(session: Optional[Mapping[str, Any]]) -> bool:
    """Is the agent's own browser connected? Not a delivery signal for anything."""
    if not session:
        return False
    return str(session.get("localLegState") or "") == LOCAL_CONNECTED


def talk_time_seconds(session: Optional[Mapping[str, Any]]) -> Optional[int]:
    """Billable talk time, or None when the far party never answered.

    None rather than 0, because 0 reads as "a call that connected and lasted no time",
    while None says "there was no conversation to measure". Anything summing these must
    make that distinction, and a default of 0 would hide unanswered calls inside an
    average.
    """
    if not remote_party_answered(session):
        return None
    started = session.get("remotePartyAnsweredAt")
    ended = session.get("localLegEndedAt") or session.get("updatedAt")
    try:
        duration = int(ended) - int(started)
    except (TypeError, ValueError):
        return None
    return max(0, duration)


def can_receive_call(session: Optional[Mapping[str, Any]]) -> Tuple[bool, str]:
    """`(ready, reason)` for routing an inbound call to this session.

    Registration and presence are both required. A registered endpoint is reachable but
    not necessarily staffed - the tab may be in the background, the agent on a break - and
    routing a customer to a reachable-but-unstaffed browser is a call that rings out.
    """
    if not session:
        return False, "no session"
    registration = str(session.get("registration") or "")
    if registration != REGISTERED:
        return False, f"endpoint is {registration or 'UNREGISTERED'}, not {REGISTERED}"
    presence = str(session.get("presence") or "")
    if presence not in PRESENCE_ACCEPTS_CALL:
        return False, f"agent presence is {presence or 'OFFLINE'}"
    if str(session.get("localLegState")) in (LOCAL_RINGING, LOCAL_DIALING,
                                             LOCAL_CONNECTED):
        return False, "session is already on a call"
    return True, "ready"


def describe(session: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Operator-facing summary. No token, no phone number.

    Reports both legs separately and spells out the difference, because the single most
    likely misreading of this data is treating `localLegConnected` as the customer being on
    the call.
    """
    if not session:
        return {"present": False}
    ready, reason = can_receive_call(session)
    return {
        "present": True,
        "sessionId": session.get("sessionId", ""),
        "actorId": session.get("actorId", ""),
        "registration": session.get("registration", UNREGISTERED),
        "presence": session.get("presence", OFFLINE),
        "localLegState": session.get("localLegState", LOCAL_IDLE),
        "localLegConnected": local_leg_connected(session),
        "remoteLegState": session.get("remoteLegState", REMOTE_UNKNOWN),
        "remotePartyAnswered": remote_party_answered(session),
        "talkTimeSeconds": talk_time_seconds(session),
        "canReceiveCall": ready,
        "readiness": reason,
        "note": ("localLegConnected is the agent's browser being in the call. "
                 "remotePartyAnswered is the other party picking up. Only the second "
                 "may start billing or fire a connected-call notification."),
    }
