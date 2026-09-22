"""Claim-key derivation for the shared notification domain. One definition only.

A key computed two slightly different ways is not an idempotency key, it is two
keys, and the duplicate suppression it was meant to provide has silently stopped
working. That is not hypothetical here: the system this replaces had exactly that
defect. ``plivo-answer``'s post-call SMS claimed ``<CallUUID>:postcall`` in the
shared ``WebhookDedup`` table while ``pstn/notifications`` claimed
``<DialALegUUID>:connected-notifications:v1`` in its own table. Same call, same
``ivr-default`` template, two stores, two key shapes, so neither could see the
other's claim.

The shapes
----------
::

    parent  {provider}:{canonicalCallId}:connected-notifications:v2
    child   {provider}:{canonicalCallId}:connected-notifications:v2:{channel}

The child is the parent plus a channel suffix, rather than an independently
assembled string, so the two can never drift apart and a child can always be
resolved back to its parent without a table read.

Why the provider is in the key
------------------------------
v1 keyed on a bare ``DialALegUUID``, which works only while one provider exists.
Meta call ids and Plivo leg UUIDs are both opaque strings from namespaces that make
no promise not to collide, and a collision would suppress a real customer's
notification - silently, and in a way no dashboard would show. The provider prefix
costs nothing and removes the question.

Why v2
------
v1 claims exist in the old store for calls that were genuinely notified. Reusing
v1 would inherit its rows; bumping to v2 without more would re-notify every one of
those callers. Neither is acceptable, which is why the version bump is paired with
the suppression ledger in ``suppression.py`` and a cutover watermark: v2 asks the
ledger whether v1 already served this call. The version lives in the key so that a
future deliberate re-notification is a one-line change rather than a mass deletion
of claim rows, which is indistinguishable from a bug.

Canonical call ids, per the brief
---------------------------------
``plivo`` -> ``DialALegUUID`` from the signed ``<Dial callbackUrl>`` callback. Not
``CallUUID``: on a ``<Dial>`` the A-leg is the original call and the B-leg is the
dialled party, callbacks arrive carrying either, and keying on ``CallUUID`` claims
the two legs separately - one call, two messages.

``meta`` -> the Meta call id from the signed ``calls`` webhook.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

#: Bump ONLY for a deliberate, documented re-notification, and only together with
#: a suppression-ledger entry that stops previously notified calls resending.
CONNECTED_NOTIFICATIONS_VERSION = "v2"

#: Fixed by the brief. Do not "tidy" it.
CONNECTED_NOTIFICATIONS_SUFFIX = "connected-notifications"

PROVIDER_PLIVO = "plivo"
PROVIDER_META = "meta"
SUPPORTED_PROVIDERS = (PROVIDER_PLIVO, PROVIDER_META)

CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_SMS = "sms"
CHANNEL_RCS = "rcs"

#: Logical dispatch priority. The brief is explicit that provider delivery order
#: cannot be guaranteed and that the three jobs are independent, so this ordering
#: is about which is attempted first, not about sequencing one behind another.
SUPPORTED_CHANNELS = (CHANNEL_WHATSAPP, CHANNEL_SMS, CHANNEL_RCS)

# Validated rather than trusted. A claim key is built from a webhook field, and an
# unvalidated field lets the caller choose its own key - so it could dodge its own
# claim, or collide with somebody else's.
#
# The guard protects the KEY STRUCTURE; it does not try to re-specify a provider's
# identifier format. `:` is the separator, so a value containing one could forge a
# different key shape. Whitespace and control characters corrupt log and metric
# parsing. Length is bounded because a key becomes a DynamoDB partition key and a
# CloudWatch metric dimension.
#
# No minimum length beyond non-empty: guessing a provider's id length would reject
# a legitimate short identifier, which is a real failure mode with no security
# benefit, since a short id corrupts nothing.
_CALL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,127}$")


class ClaimKeyError(ValueError):
    """An identifier that cannot safely be used to build a claim key."""


def _validate_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    if value not in SUPPORTED_PROVIDERS:
        raise ClaimKeyError(
            f"provider must be one of {', '.join(SUPPORTED_PROVIDERS)}, got {value!r}")
    return value


def _validate_call_id(canonical_call_id: str) -> str:
    value = str(canonical_call_id or "").strip()
    if not value:
        raise ClaimKeyError("canonical call id is required to build a claim key")
    if not _CALL_ID_RE.match(value):
        # Deliberately does not echo the value: this message lands in logs.
        raise ClaimKeyError(
            f"canonical call id is not usable as a claim key "
            f"(length {len(value)}, rejected by format check)")
    return value


def _validate_channel(channel: str) -> str:
    value = str(channel or "").strip().lower()
    if value not in SUPPORTED_CHANNELS:
        raise ClaimKeyError(
            f"channel must be one of {', '.join(SUPPORTED_CHANNELS)}, got {value!r}")
    return value


def parent_claim_key(provider: str, canonical_call_id: str,
                     version: str = CONNECTED_NOTIFICATIONS_VERSION) -> str:
    """The single claim for "this connected call has been handled".

        >>> parent_claim_key("plivo", "a-leg-123")
        'plivo:a-leg-123:connected-notifications:v2'
    """
    prov = _validate_provider(provider)
    call_id = _validate_call_id(canonical_call_id)
    return f"{prov}:{call_id}:{CONNECTED_NOTIFICATIONS_SUFFIX}:{version}"


def child_claim_key(provider: str, canonical_call_id: str, channel: str,
                    version: str = CONNECTED_NOTIFICATIONS_VERSION) -> str:
    """The per-channel claim, and the NotificationDeliveries identifier.

        >>> child_claim_key("meta", "wacid.ABC", "sms")
        'meta:wacid.ABC:connected-notifications:v2:sms'

    The record id IS the idempotency key, so a conditional put on the primary key
    is the entire mechanism: no secondary lookup, no read-then-write race.
    """
    return f"{parent_claim_key(provider, canonical_call_id, version)}:{_validate_channel(channel)}"


def child_of(parent_key: str, channel: str) -> str:
    """Derive a child from an existing parent key, without re-parsing its parts."""
    parent = str(parent_key or "").strip()
    if not parent:
        raise ClaimKeyError("parent key is required")
    return f"{parent}:{_validate_channel(channel)}"


def parse_child_key(child_key: str) -> Optional[Tuple[str, str, str, str]]:
    """`(provider, canonical_call_id, version, channel)`, or None if not a child key.

    Returns None rather than raising, because it is also used to *tell the two key
    shapes apart* - a parent claim is not a child key, and asking is not an error.
    """
    parts = str(child_key or "").split(":")
    if len(parts) != 5:
        return None
    provider, call_id, suffix, version, channel = parts
    if suffix != CONNECTED_NOTIFICATIONS_SUFFIX:
        return None
    if provider not in SUPPORTED_PROVIDERS or channel not in SUPPORTED_CHANNELS:
        return None
    if not call_id or not version:
        return None
    return provider, call_id, version, channel


def parse_parent_key(parent_key: str) -> Optional[Tuple[str, str, str]]:
    """`(provider, canonical_call_id, version)`, or None if not a parent key."""
    parts = str(parent_key or "").split(":")
    if len(parts) != 4:
        return None
    provider, call_id, suffix, version = parts
    if suffix != CONNECTED_NOTIFICATIONS_SUFFIX:
        return None
    if provider not in SUPPORTED_PROVIDERS:
        return None
    if not call_id or not version:
        return None
    return provider, call_id, version


def parent_of(child_key: str) -> str:
    """The parent claim a child belongs to, or `''` when the input is not a child."""
    parsed = parse_child_key(child_key)
    if not parsed:
        return ""
    provider, call_id, version, _channel = parsed
    return parent_claim_key(provider, call_id, version)


def legacy_v1_parent_key(a_leg_uuid: str) -> str:
    """The v1 key the retired PSTN module would have used for this call.

    Needed by the suppression ledger: before creating v2 work for a Plivo call, the
    orchestrator asks whether v1 already notified it. Without this the version bump
    would re-notify every caller who was served under v1.

    Deliberately permissive about format - it reads historical rows, and refusing to
    look one up because it fails today's stricter validation would defeat the point.
    """
    value = str(a_leg_uuid or "").strip()
    if not value:
        return ""
    return f"{value}:{CONNECTED_NOTIFICATIONS_SUFFIX}:v1"


def legacy_v1_child_key(a_leg_uuid: str, channel: str) -> str:
    """The v1 per-channel key, for the same reason as `legacy_v1_parent_key`.

    v1 only ever had `sms` and `rcs`; `whatsapp` was sent by a different, unclaimed
    code path. Asking for the whatsapp v1 key returns `''` rather than fabricating
    one, so a caller cannot conclude "not previously sent" from a key that never
    existed.
    """
    value = str(a_leg_uuid or "").strip()
    ch = str(channel or "").strip().lower()
    if not value or ch not in ("sms", "rcs"):
        return ""
    return f"{value}:{ch}:v1"
