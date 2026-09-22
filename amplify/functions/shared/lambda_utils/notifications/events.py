"""The provider-neutral `ConnectedCallEvent`, and the only two adapters that build it.

Why a normalized event at all
-----------------------------
The system this replaces had eight notification producers across four Lambdas,
each deciding for itself what "the call connected" meant and who to tell. Seven of
the eight were triggered by something that is not a connection: hangup, terminate,
Asterisk ``post_call_sip``, or a CDR row being ingested. Centralising the *trigger*
decision here is the point of the module - a producer cannot get it wrong if it
cannot construct the event.

Construction is therefore total and fail-closed: `from_plivo_dial_callback` either
returns a valid event or returns `None` with a stable reason. There is no partially
valid event, and there is no path that yields an event for a non-connected state.

The recipient rule, and the bug it fixes
----------------------------------------
    inbound call   -> notify the external CALLER
    outbound call  -> notify the external CALLEE
    never notify a business number, in either direction

The retired module got this wrong in the one place that was supposed to be
canonical. `pstn/notifications.handle_connected` parsed `Direction` and then did
``destination = event.caller`` unconditionally, with a comment asserting that
``From`` is the caller - true on inbound, and on an outbound Plivo dial ``From`` is
our own CLI. So an outbound connected call would have texted
``+919330994400``: our own business number, billed to us, under our own DLT sender.

Direction is the rule; the business-number registry is the backstop. Both are
enforced, because they fail differently. A wrong `Direction` from the provider
defeats the rule but not the registry, and a business number we forgot to register
defeats the registry but not the rule. Requiring both means a single mistake in
either is not sufficient to message ourselves.

Missing direction is a refusal, not a guess
-------------------------------------------
If `Direction` is absent or unrecognised there is no safe default. Guessing
inbound would text our own number on every outbound call; guessing outbound would
text the agent endpoint on every inbound one. The event is refused with
`ambiguous_direction`, which surfaces as a retryable non-send rather than a wrong
send.

Meta is deliberately not wired up
---------------------------------
`from_meta_call_event` exists and refuses everything. See `META_TRIGGER_NOTE`.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, Tuple

from lambda_utils.comms import numbers

from . import keys as keys_mod

DIRECTION_INBOUND = "inbound"
DIRECTION_OUTBOUND = "outbound"

#: Plivo's authoritative connected signal on a ``<Dial callbackUrl>``.
#:
#: Verified against Plivo's official "Dial status reporting" documentation on
#: 2026-09-21: the callback ``DialAction`` parameter takes ``answer``,
#: ``connected``, ``hangup`` and ``digits``. Only ``connected`` means the B-leg
#: answered and the two legs are bridged.
#:
#: ``answer`` is NOT it. On an outbound dial ``answer`` can fire for the A-leg
#: while the remote party is still ringing, which is the same class of mistake as
#: trusting the Browser SDK's ``onCallConnected``.
PLIVO_DIAL_ACTION_CONNECTED = "connected"

#: Everything else Plivo can put in ``DialAction``. Listed explicitly so a new
#: value from the provider is refused as unknown rather than silently treated as a
#: connection.
PLIVO_DIAL_ACTIONS_NOT_CONNECTED = ("answer", "hangup", "digits")

META_TRIGGER_NOTE = (
    "Meta's remote-party-connected state is UNVERIFIED. The official "
    "cloud-api/calling/call-events documentation was not retrievable on "
    "2026-09-21, and the account itself has delivered ZERO call events in 14 days "
    "(12,180 log lines in /aws/lambda/wecare-whatsapp-calling, of which 1,397 are "
    "webhook_received and 1,396 are message forwards, and 0 are call_event). The "
    "handler's existing `connect` branch is call SETUP, not a remote answer, and "
    "`terminate` is a disconnect. The brief forbids inventing a webhook event or "
    "using hangup as connection evidence, so no Meta event is accepted as a "
    "trigger until the official schema is read back and recorded."
)

#: Numbers that must never be messaged as a notification recipient, because they
#: are ours. Overridable so a new business number does not require a deploy to
#: protect, but it defaults to the full known set rather than to empty - an empty
#: default would make a misconfiguration silently remove the backstop.
#:
#:   +919330994400  WABA1 / primary WhatsApp Calling, Meta phone id 1016149501586345
#:   +919903300044  WABA2 / secondary WhatsApp Calling, Meta phone id 1055232054343117
#:   +918031830030  Plivo PSTN business number
_DEFAULT_BUSINESS_NUMBERS = "+919330994400,+919903300044,+918031830030"


def business_numbers() -> frozenset:
    """The registry of our own numbers, normalized to digits for comparison."""
    raw = os.environ.get("NOTIF_BUSINESS_NUMBERS", _DEFAULT_BUSINESS_NUMBERS)
    out = set()
    for entry in str(raw).split(","):
        digits = "".join(c for c in entry if c.isdigit())
        if digits:
            out.add(digits)
    return frozenset(out)


def is_business_number(phone: Optional[str]) -> bool:
    digits = "".join(c for c in str(phone or "") if c.isdigit())
    return bool(digits) and digits in business_numbers()


class ConnectedCallEvent:
    """A verified, normalized remote-party-connected call.

    Holding one of these is the assertion that a provider confirmed the remote
    party is connected, that the canonical id is safe to use as a claim key, and
    that `external_party` is a customer rather than one of our own numbers. Nothing
    downstream re-checks those, so nothing may construct this directly from a
    webhook body without going through an adapter.
    """

    __slots__ = ("provider", "canonical_call_id", "direction", "business_number",
                 "external_party", "connected_at", "trigger", "iso_country")

    def __init__(self, *, provider: str, canonical_call_id: str, direction: str,
                 business_number: str, external_party: str, trigger: str,
                 connected_at: Optional[int] = None) -> None:
        self.provider = provider
        self.canonical_call_id = canonical_call_id
        self.direction = direction
        self.business_number = business_number
        self.external_party = external_party
        self.trigger = trigger
        self.connected_at = int(connected_at if connected_at is not None else time.time())
        self.iso_country = numbers.iso_country(external_party) or ""

    @property
    def parent_claim_key(self) -> str:
        return keys_mod.parent_claim_key(self.provider, self.canonical_call_id)

    def child_claim_key(self, channel: str) -> str:
        return keys_mod.child_claim_key(self.provider, self.canonical_call_id, channel)

    def as_dict(self) -> Dict[str, Any]:
        """Log-safe representation. Never the full external number."""
        return {
            "provider": self.provider,
            "canonicalCallId": self.canonical_call_id,
            "direction": self.direction,
            "trigger": self.trigger,
            "businessNumberLast4": numbers.last4(self.business_number),
            "externalPartyLast4": numbers.last4(self.external_party),
            "isoCountry": self.iso_country or None,
            "connectedAt": self.connected_at,
        }


def _select_external_party(direction: str, caller: str, callee: str
                           ) -> Tuple[str, str, str]:
    """`(external_party, business_number, reason)` for a direction.

    `reason` is `''` on success. The two sides are returned together so the
    business-number backstop can check the one we chose against the one we did not.
    """
    if direction == DIRECTION_INBOUND:
        # They rang us: the A-leg caller is the customer.
        return caller, callee, ""
    if direction == DIRECTION_OUTBOUND:
        # We rang them: the dialled party is the customer.
        return callee, caller, ""
    return "", "", "ambiguous_direction"


def _normalize_direction(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in ("inbound", "in", "incoming"):
        return DIRECTION_INBOUND
    if value in ("outbound", "out", "outgoing", "outbound-api", "outbound_api"):
        return DIRECTION_OUTBOUND
    return ""


def from_plivo_dial_callback(params: Dict[str, Any], *, connected_at: Optional[int] = None
                            ) -> Tuple[Optional[ConnectedCallEvent], str]:
    """Build an event from a **signature-verified** Plivo `<Dial callbackUrl>` POST.

    The caller must have verified the Plivo signature already; this function has no
    way to tell a signed request from a forged one, and it is the function that
    decides whether a customer gets messaged.

    Returns `(event, '')` or `(None, reason)`. Reasons are stable tokens safe to log
    and to use as metric dimensions.
    """
    dial_action = str(params.get("DialAction") or "").strip().lower()
    if dial_action != PLIVO_DIAL_ACTION_CONNECTED:
        if not dial_action:
            return None, "no_dial_action"
        if dial_action in PLIVO_DIAL_ACTIONS_NOT_CONNECTED:
            return None, f"not_connected_{dial_action}"
        return None, "unknown_dial_action"

    # DialALegUUID, never CallUUID or DialBLegUUID. The A-leg is the only
    # identifier stable across both legs of a <Dial>; keying on CallUUID claims the
    # legs separately and sends one call two messages.
    canonical = str(params.get("DialALegUUID") or params.get("ALegUUID") or "").strip()
    if not canonical:
        return None, "no_a_leg_uuid"

    direction = _normalize_direction(params.get("Direction"))
    if not direction:
        return None, "ambiguous_direction"

    caller = numbers.to_e164(params.get("From") or "")
    callee = numbers.to_e164(params.get("To") or "")

    external, business, reason = _select_external_party(direction, caller, callee)
    if reason:
        return None, reason
    if not external:
        return None, "no_external_party"

    # The backstop. Reached only when `Direction` disagrees with reality, which is
    # exactly the case the rule alone cannot catch.
    if is_business_number(external):
        return None, "recipient_is_business_number"

    try:
        keys_mod.parent_claim_key(keys_mod.PROVIDER_PLIVO, canonical)
    except keys_mod.ClaimKeyError:
        # An id that cannot be a claim key cannot be made idempotent, so there is
        # no safe way to send for it.
        return None, "unsafe_canonical_call_id"

    return ConnectedCallEvent(
        provider=keys_mod.PROVIDER_PLIVO,
        canonical_call_id=canonical,
        direction=direction,
        business_number=business,
        external_party=external,
        trigger="plivo_dial_action_connected",
        connected_at=connected_at,
    ), ""


def from_meta_call_event(call: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None,
                         *, connected_at: Optional[int] = None
                         ) -> Tuple[Optional[ConnectedCallEvent], str]:
    """Refuses every Meta call event. See `META_TRIGGER_NOTE`.

    This is not a stub left unfinished - it is the designed behaviour until Meta's
    remote-connected state is verified from official documentation. The adapter
    exists so that the WhatsApp Calling path has one obvious place to be enabled,
    and so that nothing else in the codebase is tempted to treat `connect` or
    `terminate` as a connection in the meantime.

    `connect` is call setup: Meta sends it with the SDP offer, before anyone has
    answered. `terminate` is a disconnect, which the brief names explicitly as not
    a trigger. Accepting either would reproduce the defect this phase removes.
    """
    event_type = str((call or {}).get("event") or (call or {}).get("type") or "").strip().lower()
    if event_type in ("connect", "terminate", "call_permission_response",
                      "call_permission_status", "ringing", "offer", "accept",
                      "reject", "pre_accept"):
        return None, f"meta_state_not_a_trigger_{event_type}"
    return None, "meta_connected_state_unverified"
