"""Connected-call notifications: at most one SMS and one RCS per call.

The authoritative "connected" signal
------------------------------------
The server-side Plivo `<Dial callbackUrl>` event where `DialAction=connected`.

NOT the Browser SDK's `onCallConnected`. For an outbound call that fires when the
BROWSER leg is up, which can be while the remote party is still ringing. Triggering
a customer message from it would text people who never answered.

Order of operations, and why it is this way
-------------------------------------------
    1. verify signature            (caller's job, before reaching here)
    2. resolve the canonical A-leg
    3. claim the EVENT once        fail closed
    4. claim each CHANNEL once     fail closed, independently
    5. decide eligibility per channel
    6. send
    7. record the outcome

Claim before send, always. The reverse - send then record - loses the claim if the
process dies between the two, and the provider's retry then sends a second message.
A delayed message is recoverable; a duplicate is not.

If any claim step cannot reach the store, this raises and the caller must return a
retryable 5xx. Plivo redelivers, so the cost of refusing to guess is latency.

Channel independence
--------------------
SMS and RCS hold separate claims, so:

  * an SMS failure does not suppress RCS, and vice versa;
  * a retry after a partial failure completes only the missing channel;
  * a completed channel is never resent, because `is_retryable` refuses it.

Provider selection is a function of the destination, not of caller preference:

    SMS  every country          AWS End User Messaging
                                +91 -> ap-south-1 with DLT; else us-east-1
    RCS  eligible +91           Sinch  (the only approved India RCS)
         eligible non-India     AWS End User Messaging RCS
         anything else          terminal INELIGIBLE / UNSUPPORTED, never a
                                fallback to a prohibited provider

AWS RCS does not exist in this account yet. Non-India RCS is therefore recorded
SKIPPED / UNSUPPORTED rather than quietly routed to Sinch - Sinch is approved for
India only, and "it would have worked" is not a reason to breach the matrix.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from lambda_utils.comms import numbers
from lambda_utils.logging import get_logger, log_event

from . import claims as claims_mod
from . import keys as keys_mod

logger = get_logger(__name__)

DIAL_ACTION_CONNECTED = "connected"

CHANNEL_SMS = "sms"
CHANNEL_RCS = "rcs"
CHANNELS = (CHANNEL_SMS, CHANNEL_RCS)

# The notification body must match approved DLT template `ivr-default` character
# for character. The operator silently drops mismatched content while the API call
# still succeeds, so do not "improve" this copy.
DEFAULT_DLT_TEMPLATE_KEY = os.environ.get("PSTN_DLT_TEMPLATE_KEY", "ivr-default")
NOTIFICATION_BODY = os.environ.get("PSTN_NOTIFICATION_BODY", (
    "Thanks for contacting WECARE.DIGITAL!\n\n"
    "Submit your request here: https://wecare.digital/selfservice "
    "or send us a message / voice note on WhatsApp: https://r.wecare.digital/wa.\n\n"
    "We'll review it and follow up if needed."
))

# Off by default. Enabling it is a production decision, not a deployment artefact.
CONNECTED_NOTIFICATIONS_ENABLED = os.environ.get(
    "PSTN_CONNECTED_NOTIFICATIONS_ENABLED", "false").lower() == "true"

# India RCS is live via Sinch. AWS RCS is not built in this account, so non-India
# RCS has no approved provider and is recorded as unsupported rather than guessed.
INDIA_RCS_ENABLED = os.environ.get("SINCH_RCS_ENABLED", "false").lower() == "true"
GLOBAL_RCS_AVAILABLE = os.environ.get(
    "AWS_RCS_AVAILABLE", "false").lower() == "true"


class ConnectedEvent:
    """A normalised, validated Plivo dial callback."""

    __slots__ = ("a_leg_uuid", "b_leg_uuid", "call_uuid", "dial_action",
                 "direction", "caller", "callee", "is_connected")

    def __init__(self, params: Dict[str, Any]) -> None:
        self.dial_action = str(params.get("DialAction") or "").strip().lower()
        self.a_leg_uuid = keys_mod.resolve_a_leg_uuid(params)
        self.b_leg_uuid = str(params.get("DialBLegUUID") or "").strip()
        self.call_uuid = str(params.get("CallUUID") or "").strip()
        self.direction = str(params.get("Direction") or "").strip().lower()
        # `From` is the caller on an inbound call. That is who gets the message -
        # never `To`, which on inbound is our own number.
        self.caller = numbers.to_e164(params.get("From") or "")
        self.callee = numbers.to_e164(params.get("To") or "")
        self.is_connected = self.dial_action == DIAL_ACTION_CONNECTED

    def as_dict(self) -> Dict[str, Any]:
        return {
            "dialAction": self.dial_action,
            "aLegUuid": self.a_leg_uuid,
            "bLegUuid": self.b_leg_uuid or None,
            "direction": self.direction or None,
            "isConnected": self.is_connected,
            # Last four only. A full number in a log is an unnecessary disclosure.
            "callerLast4": self.caller[-4:] if self.caller else None,
        }


class ChannelDecision:
    """Whether a channel may be sent, and by whom."""

    __slots__ = ("channel", "eligible", "provider", "reason", "state")

    def __init__(self, channel: str, *, eligible: bool, provider: str = "",
                 reason: str = "", state: str = "PENDING") -> None:
        self.channel = channel
        self.eligible = eligible
        self.provider = provider
        self.reason = reason
        self.state = state

    def as_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "eligible": self.eligible,
            "provider": self.provider or None,
            "reason": self.reason,
            "state": self.state,
        }


def decide_sms(destination: str) -> ChannelDecision:
    """SMS is always AWS End User Messaging. The region follows the destination."""
    if not destination:
        return ChannelDecision(CHANNEL_SMS, eligible=False,
                               reason="no destination", state="SKIPPED")
    if numbers.is_india(destination):
        return ChannelDecision(
            CHANNEL_SMS, eligible=True, provider="aws-end-user-messaging",
            reason="India -> AWS ap-south-1, DLT template required")
    return ChannelDecision(
        CHANNEL_SMS, eligible=True, provider="aws-end-user-messaging",
        reason="non-India -> AWS configured default region")


def decide_rcs(destination: str) -> ChannelDecision:
    """India RCS is Sinch only. Non-India RCS is AWS, which is not built here.

    An unavailable channel is recorded as a terminal SKIPPED with an explicit
    reason. It is NOT downgraded to a different provider: Sinch is approved for
    India only, and routing non-India traffic to it because it happens to be
    reachable would breach the provider matrix.
    """
    if not destination:
        return ChannelDecision(CHANNEL_RCS, eligible=False,
                               reason="no destination", state="SKIPPED")

    if numbers.is_india(destination):
        if not INDIA_RCS_ENABLED:
            return ChannelDecision(
                CHANNEL_RCS, eligible=False, provider="sinch-rcs",
                reason="INELIGIBLE_UNSUPPORTED: India RCS is disabled "
                       "(SINCH_RCS_ENABLED is not true)",
                state="SKIPPED")
        return ChannelDecision(
            CHANNEL_RCS, eligible=True, provider="sinch-rcs",
            reason="India -> Sinch RCS (the only approved India RCS provider)")

    if not GLOBAL_RCS_AVAILABLE:
        return ChannelDecision(
            CHANNEL_RCS, eligible=False, provider="aws-rcs",
            reason="INELIGIBLE_UNSUPPORTED: non-India RCS requires AWS End User "
                   "Messaging RCS, which is not configured in this account. "
                   "Sinch is approved for India only and is NOT used as a "
                   "fallback.",
            state="SKIPPED")
    return ChannelDecision(
        CHANNEL_RCS, eligible=True, provider="aws-rcs",
        reason="non-India -> AWS End User Messaging RCS")


def decide(channel: str, destination: str) -> ChannelDecision:
    if channel == CHANNEL_SMS:
        return decide_sms(destination)
    if channel == CHANNEL_RCS:
        return decide_rcs(destination)
    raise ValueError(f"unknown channel {channel!r}")


def handle_connected(params: Dict[str, Any], *, request_id: str = "",
                     dispatch=None) -> Dict[str, Any]:
    """Claim a connected call and create one delivery record per channel.

    Raises `claims.ClaimStoreUnavailable` when the store cannot be reached. The
    caller MUST convert that into a retryable 5xx and must not send anything.

    `dispatch` is injected so the queue mechanism is the caller's choice and this
    stays unit-testable without SQS. It is called once per eligible channel, after
    that channel's claim succeeds.
    """
    event = ConnectedEvent(params)

    if not event.is_connected:
        log_event(logger, "pstn_dial_event_ignored",
                  dialAction=event.dial_action or "(none)", requestId=request_id)
        return {"claimed": False, "reason": "not_a_connected_event",
                "event": event.as_dict()}

    if not event.a_leg_uuid:
        # Without the A-leg there is no safe key, so there is no way to guarantee
        # once-only. Refuse rather than fall back to an unstable identifier.
        log_event(logger, "pstn_connected_missing_a_leg", level="error",
                  alert="PSTN_CONNECTED_NO_A_LEG", requestId=request_id)
        return {"claimed": False, "reason": "no_a_leg_uuid",
                "event": event.as_dict()}

    if not CONNECTED_NOTIFICATIONS_ENABLED:
        log_event(logger, "pstn_connected_notifications_disabled",
                  aLegUuid=event.a_leg_uuid, requestId=request_id)
        return {"claimed": False, "reason": "feature_disabled",
                "event": event.as_dict()}

    destination = event.caller
    event_claim = keys_mod.connected_claim_key(event.a_leg_uuid)

    # Step 3. The event claim. Fails closed - see the module docstring.
    if not claims_mod.claim(event_claim, a_leg_uuid=event.a_leg_uuid,
                            channel="event", request_id=request_id,
                            attributes={"destination": destination,
                                        "isoCountry": numbers.iso_country(destination) or ""}):
        log_event(logger, "pstn_connected_duplicate", aLegUuid=event.a_leg_uuid,
                  requestId=request_id)
        return {"claimed": False, "reason": "duplicate_connected_event",
                "event": event.as_dict()}

    # Steps 4-5. Per-channel claims and eligibility, independently.
    results: Dict[str, Any] = {}
    for channel in CHANNELS:
        decision = decide(channel, destination)
        delivery_id = keys_mod.channel_delivery_id(event.a_leg_uuid, channel)

        claimed = claims_mod.claim(
            delivery_id, a_leg_uuid=event.a_leg_uuid, channel=channel,
            request_id=request_id,
            attributes={
                "destination": destination,
                "isoCountry": numbers.iso_country(destination) or "",
                "provider": decision.provider,
                "eligibility": "ELIGIBLE" if decision.eligible else "INELIGIBLE",
                "eligibilityReason": decision.reason,
                "dltTemplateKey": (DEFAULT_DLT_TEMPLATE_KEY
                                   if channel == CHANNEL_SMS else ""),
            })

        if not claimed:
            results[channel] = {"claimed": False, "reason": "already_claimed",
                               **decision.as_dict()}
            continue

        if not decision.eligible:
            # Terminal, and recorded as such, so a dashboard can tell "not
            # applicable" from "broken".
            claims_mod.record_attempt(delivery_id, state="SKIPPED",
                                      provider=decision.provider,
                                      error_category=decision.reason[:120],
                                      error_is_permanent=True,
                                      request_id=request_id)
            results[channel] = {"claimed": True, "dispatched": False,
                                **decision.as_dict()}
            continue

        # Step 6. Dispatch. Independent per channel, so one failing to enqueue
        # does not prevent the other.
        dispatched = False
        if dispatch is not None:
            try:
                dispatch(channel=channel, delivery_id=delivery_id,
                         destination=destination, body=NOTIFICATION_BODY,
                         provider=decision.provider,
                         dlt_template_key=(DEFAULT_DLT_TEMPLATE_KEY
                                           if channel == CHANNEL_SMS else ""),
                         a_leg_uuid=event.a_leg_uuid, request_id=request_id)
                dispatched = True
            except Exception as exc:  # noqa: BLE001
                # The claim is already durable, so the channel is PENDING and a
                # retry will find it retryable. Do not fail the whole callback:
                # that would make Plivo redeliver and re-attempt the OTHER
                # channel, which has already been claimed.
                log_event(logger, "pstn_dispatch_failed", level="error",
                          channel=channel, deliveryId=delivery_id,
                          errorType=type(exc).__name__, requestId=request_id)
        results[channel] = {"claimed": True, "dispatched": dispatched,
                            "deliveryId": delivery_id, **decision.as_dict()}

    log_event(logger, "pstn_connected_claimed", aLegUuid=event.a_leg_uuid,
              smsDispatched=results.get(CHANNEL_SMS, {}).get("dispatched"),
              rcsDispatched=results.get(CHANNEL_RCS, {}).get("dispatched"),
              requestId=request_id)

    return {"claimed": True, "event": event.as_dict(), "channels": results,
            "eventClaimKey": event_claim}


def classify_provider_error(error: Optional[str], error_code: str = "") -> tuple:
    """(category, is_permanent) for a send failure.

    Permanent means retrying cannot succeed, so the attempt budget should not be
    spent on it and the dead-letter signal should be immediate. DLT, destination,
    validation and permission failures are permanent by nature; throttling and
    timeouts are not.
    """
    code = str(error_code or "").strip()
    text = f"{code} {error or ''}".lower()

    permanent_markers = (
        "missing_dlt_template", "unapproved_dlt", "invalid_phone",
        "invalid phone", "validationexception", "accessdenied",
        "unauthorized", "forbidden", "not_registered", "opted_out",
        "destination", "blocked", "prohibited_provider",
    )
    for marker in permanent_markers:
        if marker in text:
            return (code or marker).upper()[:60], True

    transient_markers = ("throttl", "timeout", "timed out", "unavailable",
                         "serviceexception", "internalserver", "5xx",
                         "connectionerror", "endpointconnectionerror")
    for marker in transient_markers:
        if marker in text:
            return (code or marker).upper()[:60], False

    # Unknown errors are treated as TRANSIENT on purpose. A retry of something
    # already delivered is prevented by the claim, so the cost of being wrong here
    # is a wasted attempt; treating an unknown transient fault as permanent would
    # silently drop a real notification.
    return (code or "UNKNOWN").upper()[:60], False
