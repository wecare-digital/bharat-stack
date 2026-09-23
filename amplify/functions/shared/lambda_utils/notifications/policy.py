"""Per-channel eligibility: may this channel be sent, by whom, with what template.

One decision function per channel, and a `decide_all` that returns exactly one
decision per channel. The shape matters: the brief requires that a connected call
produces *one logical delivery per channel*, including for channels that cannot be
sent. An ineligible channel yields a `SKIPPED` decision, not an absent one, because
"not applicable" and "we forgot" must be distinguishable on a dashboard.

Ineligible is terminal, and never a downgrade
---------------------------------------------
No channel ever falls back to another channel's provider. Sinch is approved for
India RCS only, so a non-India RCS destination is recorded
``SKIPPED / INELIGIBLE_UNSUPPORTED`` rather than routed to Sinch because it happens
to be reachable. "It would have worked" is not a reason to breach the provider
matrix, and a silent downgrade is how a prohibited provider re-enters a system that
documented its removal.

Template identity is not template approval
------------------------------------------
A template *name* is not its object id, and neither is evidence that Meta currently
has it APPROVED for that WABA, language and component set. This module records the
ids it was configured with and marks what has not been read back, so the gap is
visible at decision time instead of being discovered by a rejected send. Nothing
here contacts a provider - that would put a network call inside a signed webhook.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from lambda_utils.comms import numbers

from . import keys as keys_mod
from . import states as states_mod

CHANNEL_WHATSAPP = keys_mod.CHANNEL_WHATSAPP
CHANNEL_SMS = keys_mod.CHANNEL_SMS
CHANNEL_RCS = keys_mod.CHANNEL_RCS
CHANNELS = keys_mod.SUPPORTED_CHANNELS

PROVIDER_META = "meta-direct"
PROVIDER_AWS_EUM = "aws-end-user-messaging"
PROVIDER_SINCH_RCS = "sinch-rcs"
PROVIDER_AWS_RCS = "aws-end-user-messaging-rcs"

# --- WhatsApp -----------------------------------------------------------------
# WABA1 is the continuity sender. The brief is explicit that `wd_menu`'s approved
# body contains trailing backticks, that an approved template must not be edited in
# place, and that a clean `wd_call_followup_v1` is a separate provider task.
WA_TEMPLATE_NAME = os.environ.get("NOTIF_WA_TEMPLATE_NAME", "wd_menu")
WA_TEMPLATE_LANGUAGE = os.environ.get("NOTIF_WA_TEMPLATE_LANGUAGE", "en")

#: Meta phone-number id -> (template object id, label). Keyed by the number that
#: RECEIVED or PLACED the call, so a call on the secondary number is followed up
#: from the secondary number.
#:
#: This is the "never duplicate from WABA2" rule expressed as data: one phone id
#: resolves to exactly one template object, so there is no code path that can send
#: from both.
WA_SENDER_TEMPLATES = {
    "1016149501586345": ("998210796499191", "WABA1"),
    "1055232054343117": ("2429247000907048", "WABA2"),
}

#: Set to the phone ids whose template approval has been read back from Meta.
#: Empty by default: the brief requires revalidating APPROVED status before live
#: use, and an unverified template must yield SKIPPED rather than a rejected send.
_WA_VERIFIED_DEFAULT = ""

# --- SMS ----------------------------------------------------------------------
SMS_DLT_TEMPLATE_KEY = os.environ.get("NOTIF_SMS_DLT_TEMPLATE_KEY", "ivr-default")
SMS_INDIA_REGION = "ap-south-1"
SMS_DEFAULT_REGION = "us-east-1"

# --- RCS ----------------------------------------------------------------------
RCS_INDIA_TEMPLATE = os.environ.get("NOTIF_RCS_TEMPLATE_NAME", "rcsmenu")


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() == "true"


def wa_verified_senders() -> frozenset:
    raw = os.environ.get("NOTIF_WA_VERIFIED_SENDERS", _WA_VERIFIED_DEFAULT)
    return frozenset(p.strip() for p in str(raw).split(",") if p.strip())


class ChannelDecision:
    """Whether a channel may be sent, by whom, and with what.

    `state` is the state the delivery should be *created* in: `PENDING` for a
    channel that will be published to the outbox, `SKIPPED` for one that is
    terminally ineligible. Using the real state vocabulary here rather than a
    separate enum means the orchestrator does not translate, and a decision cannot
    name a state the machine does not have.
    """

    __slots__ = ("channel", "eligible", "provider", "reason", "state",
                 "template_name", "template_id", "region", "dlt_template_key",
                 "sender_label")

    def __init__(self, channel: str, *, eligible: bool, provider: str = "",
                 reason: str = "", template_name: str = "", template_id: str = "",
                 region: str = "", dlt_template_key: str = "",
                 sender_label: str = "") -> None:
        self.channel = channel
        self.eligible = eligible
        self.provider = provider
        self.reason = reason
        self.state = states_mod.PENDING if eligible else states_mod.SKIPPED
        self.template_name = template_name
        self.template_id = template_id
        self.region = region
        self.dlt_template_key = dlt_template_key
        self.sender_label = sender_label

    def as_dict(self) -> Dict:
        return {
            "channel": self.channel,
            "eligible": self.eligible,
            "provider": self.provider or None,
            "reason": self.reason,
            "state": self.state,
            "templateName": self.template_name or None,
            "templateId": self.template_id or None,
            "region": self.region or None,
            "dltTemplateKey": self.dlt_template_key or None,
            "senderLabel": self.sender_label or None,
        }


def decide_whatsapp(destination: str, *, sender_phone_id: str = "") -> ChannelDecision:
    """Meta Direct, from the number that carried the call. Never a cross-WABA send."""
    if not destination:
        return ChannelDecision(CHANNEL_WHATSAPP, eligible=False,
                               reason="no_destination")

    sender = str(sender_phone_id or "").strip()
    if not sender:
        # Refusing is the safe failure. Picking a default sender is how a caller
        # ends up answered from a number they never contacted, outside the 24-hour
        # window that belongs to the conversation they actually opened.
        return ChannelDecision(CHANNEL_WHATSAPP, eligible=False,
                               provider=PROVIDER_META,
                               reason="INELIGIBLE_SENDER_UNRESOLVED: no Meta phone "
                                      "id for the call; refusing to choose a WABA")

    mapping = WA_SENDER_TEMPLATES.get(sender)
    if not mapping:
        return ChannelDecision(CHANNEL_WHATSAPP, eligible=False,
                               provider=PROVIDER_META,
                               reason=f"INELIGIBLE_UNKNOWN_SENDER: {sender} is not a "
                                      "registered notification sender")

    template_id, label = mapping
    if sender not in wa_verified_senders():
        # The brief: revalidate APPROVED before live use, and if the secondary
        # template is unavailable record SKIPPED or FAILED - do NOT send a duplicate
        # from WABA1 without an explicit policy migration.
        return ChannelDecision(
            CHANNEL_WHATSAPP, eligible=False, provider=PROVIDER_META,
            template_name=WA_TEMPLATE_NAME, template_id=template_id,
            sender_label=label,
            reason=f"INELIGIBLE_TEMPLATE_UNVERIFIED: {WA_TEMPLATE_NAME} object "
                   f"{template_id} on {label} has not been read back as APPROVED "
                   "for this language and component set")

    return ChannelDecision(
        CHANNEL_WHATSAPP, eligible=True, provider=PROVIDER_META,
        template_name=WA_TEMPLATE_NAME, template_id=template_id,
        sender_label=label,
        reason=f"{label} -> Meta Direct, template object {template_id}")


def _india(destination: str) -> bool:
    """Is this destination Indian, whatever form it arrived in?

    `numbers.is_india` expects E.164, so calling it on a raw destination misclassifies a
    bare ten-digit Indian mobile as foreign: `is_india('9903300044')` is False while
    `is_india(to_e164('9903300044'))` is True.

    That mattered because the senders normalise and this did not, so the two layers
    disagreed about the same number. A bare ten-digit Indian mobile was declared
    `INELIGIBLE_UNSUPPORTED: non-India RCS requires AWS End User Messaging RCS` - both the
    wrong verdict and a misleading reason - while `rcs-send` would have accepted it happily.
    Normalising first makes eligibility and sending agree.
    """
    if not destination:
        return False
    e164 = numbers.to_e164(destination)
    return bool(e164) and numbers.is_india(e164)


def decide_sms(destination: str) -> ChannelDecision:
    """AWS End User Messaging for every destination. The region follows the number."""
    if not destination:
        return ChannelDecision(CHANNEL_SMS, eligible=False, reason="no_destination")

    if _india(destination):
        return ChannelDecision(
            CHANNEL_SMS, eligible=True, provider=PROVIDER_AWS_EUM,
            region=SMS_INDIA_REGION, dlt_template_key=SMS_DLT_TEMPLATE_KEY,
            reason=f"India -> AWS EUM {SMS_INDIA_REGION}, DLT key "
                   f"{SMS_DLT_TEMPLATE_KEY}")

    # Non-India carries no India DLT metadata. Attaching it would be invalid for the
    # destination, and the operator accepts the call while silently dropping the
    # message - a failure that looks like a success.
    return ChannelDecision(
        CHANNEL_SMS, eligible=True, provider=PROVIDER_AWS_EUM,
        region=SMS_DEFAULT_REGION,
        reason=f"non-India -> AWS EUM {SMS_DEFAULT_REGION}, no India DLT metadata")


def decide_rcs(destination: str) -> ChannelDecision:
    """India RCS is Sinch only. Non-India RCS is AWS, which is not provisioned here."""
    if not destination:
        return ChannelDecision(CHANNEL_RCS, eligible=False, reason="no_destination")

    if _india(destination):
        if not _flag("SINCH_RCS_ENABLED"):
            return ChannelDecision(
                CHANNEL_RCS, eligible=False, provider=PROVIDER_SINCH_RCS,
                reason="INELIGIBLE_UNSUPPORTED: India RCS is disabled "
                       "(SINCH_RCS_ENABLED is not true)")
        return ChannelDecision(
            CHANNEL_RCS, eligible=True, provider=PROVIDER_SINCH_RCS,
            template_name=RCS_INDIA_TEMPLATE,
            reason=f"India -> Sinch RCS template {RCS_INDIA_TEMPLATE} (the only "
                   "approved India RCS provider); template id/version UNVERIFIED")

    if not _flag("AWS_RCS_AVAILABLE"):
        return ChannelDecision(
            CHANNEL_RCS, eligible=False, provider=PROVIDER_AWS_RCS,
            reason="INELIGIBLE_UNSUPPORTED: non-India RCS requires AWS End User "
                   "Messaging RCS, which is not provisioned in this account. Sinch "
                   "is approved for India only and is NOT used as a fallback")

    return ChannelDecision(CHANNEL_RCS, eligible=True, provider=PROVIDER_AWS_RCS,
                           reason="non-India -> AWS End User Messaging RCS")


def decide(channel: str, destination: str, *, sender_phone_id: str = "") -> ChannelDecision:
    if channel == CHANNEL_WHATSAPP:
        return decide_whatsapp(destination, sender_phone_id=sender_phone_id)
    if channel == CHANNEL_SMS:
        return decide_sms(destination)
    if channel == CHANNEL_RCS:
        return decide_rcs(destination)
    raise ValueError(f"unknown channel {channel!r}")


def decide_all(destination: str, *, sender_phone_id: str = "") -> Dict[str, ChannelDecision]:
    """Exactly one decision per channel, always all three keys present.

    Callers must not filter this down to the eligible ones before creating
    deliveries: the ineligible ones are the `SKIPPED` records that make "not
    applicable" visible and auditable.
    """
    return {channel: decide(channel, destination, sender_phone_id=sender_phone_id)
            for channel in CHANNELS}
