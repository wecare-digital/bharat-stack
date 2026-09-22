"""Stops the v1 -> v2 version bump re-notifying callers who were already messaged.

The problem the version bump creates
------------------------------------
``keys.py`` moved the claim key from ``<aLegUuid>:connected-notifications:v1`` to
``{provider}:{callId}:connected-notifications:v2``. A new key means no collision
with an old claim - which is the point, and also the hazard: every call that was
already notified under the old system now looks unnotified, so switching v2 on would
send a second message to each of them.

Two mechanisms, because there are two populations
------------------------------------------------
**The watermark** covers the bulk. Any call whose connected timestamp precedes
``NOTIF_CUTOVER_WATERMARK`` is suppressed outright: it belongs to the old system's
era, and the new one has no business re-deciding it. This is the safety net that does
not depend on any historical row still existing.

**The legacy ledger** covers the overlap around cutover, per call. Here the
interesting detail is *which* store to read, and the answer is not the obvious one.

``PstnNotificationDelivery`` - the v1 claim table - **was never created in AWS**. It
is declared in ``backend.ts`` and ``data/resource.ts`` and referenced by
``pstn/claims.py``, but it is absent from all 66 live tables, so every v1 claim
attempt raised ``ClaimStoreUnavailable`` and the dial-events route answered 503
without sending. Confirmed by log measurement: ``plivo_dial_event`` fired **0** times
in 14 days. There is therefore nothing to migrate from it, and a suppression check
against it would be a check against an empty set - worse than useless, because it
would look like due diligence.

What *did* send is the prohibited hangup-triggered path:
``plivo_post_call_sms_queued`` fired **32** times in the same 14 days, claiming
``<CallUUID>:postcall`` in the shared ``WebhookDedup`` table. So that is the ledger
this module reads. For an inbound A-leg, ``CallUUID`` and ``DialALegUUID`` are the
same value, which is what makes the lookup possible at all.

Fail closed
-----------
An unreadable ledger returns "suppressed". The asymmetry is deliberate: a suppressed
notification that should have been sent is a missing message, visible and
recoverable; an unsuppressed one that should not have been sent is a duplicate to a
real customer, billed under our DLT sender, and not recoverable. When the check
cannot be made, the answer that cannot cause the unrecoverable outcome wins.
"""

from __future__ import annotations

import os
import time
from typing import Optional, Tuple

from lambda_utils.logging import get_logger, log_event

logger = get_logger(__name__)

#: Unix seconds. Calls that connected before this are never notified by v2.
#:
#: ``0`` means "no watermark set", and is treated as **suppress everything** rather
#: than "allow everything". An operator who enables the domain without setting a
#: watermark gets zero notifications - immediately visible - instead of a backfill
#: to every caller in the retention window.
CUTOVER_WATERMARK = int(os.environ.get("NOTIF_CUTOVER_WATERMARK", "0"))

#: The table the retired hangup-triggered SMS claimed into. Shared with other
#: webhook de-duplication, so this module only ever READS it.
LEGACY_DEDUP_TABLE = os.environ.get("WEBHOOK_DEDUP_TABLE",
                                    "stack-wecare-digital-WebhookDedup")

#: Suffix used by `plivo-answer._claim_once(call_uuid, 'postcall')`.
LEGACY_POSTCALL_SUFFIX = "postcall"

_resource = None


def _table():
    global _resource
    if _resource is None:
        import boto3
        _resource = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _resource.Table(LEGACY_DEDUP_TABLE)


def watermark() -> int:
    return CUTOVER_WATERMARK


def before_watermark(connected_at: int) -> bool:
    """True when this call predates cutover, including when no watermark is set."""
    if CUTOVER_WATERMARK <= 0:
        return True
    return int(connected_at or 0) < CUTOVER_WATERMARK


def legacy_already_notified(canonical_call_id: str, *, request_id: str = "") -> Tuple[bool, str]:
    """`(already_notified, reason)` from the retired producer's dedup ledger.

    Reads `<canonicalCallId>:postcall`, the key
    `plivo-answer._send_post_call_sms` de-duplicated on. A hit means this caller
    already received the `ivr-default` SMS for this call from the old path, so v2 must
    not send a second one.
    """
    call_id = str(canonical_call_id or "").strip()
    if not call_id:
        return True, "no_canonical_call_id"

    key = f"{call_id}:{LEGACY_POSTCALL_SUFFIX}"
    try:
        item = _table().get_item(Key={"eventKey": key}).get("Item")
    except Exception as exc:  # noqa: BLE001 - see module docstring
        log_event(logger, "notif_suppression_ledger_unreadable", level="error",
                  errorType=type(exc).__name__,
                  alert="NOTIF_SUPPRESSION_LEDGER_UNREADABLE", requestId=request_id)
        return True, "ledger_unreadable_fail_closed"

    if item:
        return True, "legacy_postcall_sms_already_sent"
    return False, ""


def should_suppress(event, *, check_legacy: bool = True,
                    request_id: str = "") -> Tuple[bool, str]:
    """Whether this connected call must not be notified by the v2 domain.

    Checked *before* the claim, so a suppressed call leaves no v2 rows at all. That
    keeps the tables a record of what the new domain actually did rather than a mix of
    real work and suppression markers.
    """
    if before_watermark(event.connected_at):
        return True, ("no_cutover_watermark_set" if CUTOVER_WATERMARK <= 0
                      else "before_cutover_watermark")

    if check_legacy:
        already, reason = legacy_already_notified(
            event.canonical_call_id, request_id=request_id)
        if already:
            return True, reason

    return False, ""


def describe() -> dict:
    """Config summary for a status endpoint. No recipient data."""
    return {
        "cutoverWatermark": CUTOVER_WATERMARK,
        "watermarkSet": CUTOVER_WATERMARK > 0,
        "legacyLedgerTable": LEGACY_DEDUP_TABLE,
        "suppressesEverything": CUTOVER_WATERMARK <= 0,
        "nowMinusWatermarkSeconds": (int(time.time()) - CUTOVER_WATERMARK
                                     if CUTOVER_WATERMARK > 0 else None),
    }
