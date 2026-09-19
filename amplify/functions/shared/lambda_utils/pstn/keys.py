"""Idempotency key derivation for connected-call notifications.

One module so the key format is defined exactly once. A key that is computed
slightly differently in two places is not an idempotency key at all - it is two
keys, and the duplicate suppression it was supposed to provide silently stops
working.

The event claim
---------------
    <DialALegUUID>:connected-notifications:v1

The A-leg UUID, not `CallUUID`. On a `<Dial>` the A-leg is the original inbound
call and the B-leg is the dialled party; callbacks arrive carrying either, and the
A-leg is the only identifier stable across both. Keying on `CallUUID` would claim
the two legs separately and send the customer two messages.

The per-channel claim
---------------------
    <DialALegUUID>:<channel>:v1

The event claim answers "has this connected call been handled". The channel claims
answer "has SMS been sent" and "has RCS been sent" independently, so a retry that
follows a partial failure completes the missing channel without resending the
finished one. One claim covering both channels could not express that.

Versioning
----------
`v1` is part of the key on purpose. If the notification content or channel set
changes in a way that SHOULD reach customers who already received v1, the version
is bumped and the new key does not collide with the old claim. Without it, the
only way to re-notify would be deleting claim rows, which is indistinguishable
from a bug.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Bump ONLY for a deliberate, documented re-notification. Changing it silently
# re-sends to every caller whose v1 claim exists.
CONNECTED_NOTIFICATIONS_VERSION = "v1"

# The event-claim suffix. Fixed by the design document; do not "tidy" it.
CONNECTED_NOTIFICATIONS_SUFFIX = "connected-notifications"

SUPPORTED_CHANNELS = ("sms", "rcs")

# Validated rather than trusted: a claim key is built from a webhook field, and an
# unvalidated one lets a caller choose its own key - so it could dodge, or collide
# with, somebody else's claim.
#
# The guard's job is to protect the KEY STRUCTURE, not to re-specify the provider's
# identifier format. `:` is the field separator, so a value containing one could
# forge a different key shape; whitespace and control characters corrupt log and
# metric parsing. An overlong value is refused because a key becomes a DynamoDB
# partition key and a metric dimension.
#
# It deliberately does NOT impose a minimum length beyond non-empty. Guessing the
# provider's id length would reject a legitimate short identifier - a real failure
# mode, and one with no security benefit, since a short id corrupts nothing.
_UUID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,127}$")


class KeyError_(ValueError):
    """An identifier that cannot safely be used to build a claim key."""


def _validate_leg_uuid(a_leg_uuid: str) -> str:
    value = str(a_leg_uuid or "").strip()
    if not value:
        raise KeyError_("A-leg UUID is required to build a claim key")
    if not _UUID_RE.match(value):
        # Deliberately does not echo the value into the message: it lands in logs.
        raise KeyError_(
            f"A-leg UUID is not usable as a claim key "
            f"(length {len(value)}, rejected by format check)")
    return value


def connected_claim_key(a_leg_uuid: str,
                        version: str = CONNECTED_NOTIFICATIONS_VERSION) -> str:
    """The single claim for "this connected call has been handled".

        >>> connected_claim_key("abc-123")
        'abc-123:connected-notifications:v1'
    """
    leg = _validate_leg_uuid(a_leg_uuid)
    return f"{leg}:{CONNECTED_NOTIFICATIONS_SUFFIX}:{version}"


def channel_delivery_id(a_leg_uuid: str, channel: str,
                        version: str = CONNECTED_NOTIFICATIONS_VERSION) -> str:
    """The per-channel claim, and the PstnNotificationDelivery identifier.

        >>> channel_delivery_id("abc-123", "sms")
        'abc-123:sms:v1'

    The record id IS the idempotency key, so a conditional put on the primary key
    is the whole mechanism. No secondary lookup, no read-then-write race.
    """
    leg = _validate_leg_uuid(a_leg_uuid)
    ch = str(channel or "").strip().lower()
    if ch not in SUPPORTED_CHANNELS:
        raise KeyError_(
            f"channel must be one of {', '.join(SUPPORTED_CHANNELS)}, got {ch!r}")
    return f"{leg}:{ch}:{version}"


def parse_channel_delivery_id(delivery_id: str) -> Optional[Tuple[str, str, str]]:
    """(a_leg_uuid, channel, version), or None when it is not a channel id.

    Used by workers that receive a delivery id and need the call it belongs to
    without a table read. Returns None rather than raising, because it is also
    used to TELL the two key shapes apart - the event claim is not a channel id.
    """
    parts = str(delivery_id or "").split(":")
    if len(parts) != 3:
        return None
    leg, channel, version = parts
    if channel not in SUPPORTED_CHANNELS:
        return None
    if not leg or not version:
        return None
    return leg, channel, version


def resolve_a_leg_uuid(params: dict) -> str:
    """The canonical A-leg from a Plivo callback's parameters.

    Preference order matters. `DialALegUUID` is present on Dial callbacks and is
    authoritative. `CallUUID` is the fallback for callbacks that carry no Dial
    context - on the A-leg those are the same value, which is why the fallback is
    safe, but it is a fallback and not an equal.

    `DialBLegUUID` is never used: keying on the dialled party would give one
    inbound call a different claim per attempt.
    """
    for field in ("DialALegUUID", "ALegUUID", "CallUUID"):
        value = str(params.get(field) or "").strip()
        if value:
            return value
    return ""
