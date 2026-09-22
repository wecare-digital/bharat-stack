"""Drains the outbox: lease a job, send one channel, record what happened.

The three dispositions, and why two of them are not "retry"
----------------------------------------------------------
A failed send is not one thing. The brief requires distinguishing the case where the
provider may have accepted a send whose response was lost, and that case must not be
retried blindly:

``RETRY``                 definitely not sent. Throttled, refused before transmission,
                          store contention. Goes back to ``READY`` for a bounded retry.
``RECONCILE``             may have been sent. A timeout or a reset connection: the
                          request left us and no answer came back. Goes to
                          ``RECONCILIATION_REQUIRED``, and a human or a reconciler
                          resolves it against the provider before anything resends.
``PERMANENT``             cannot succeed. Bad destination, missing DLT template,
                          unapproved template, permission denied. Goes to ``FAILED``
                          immediately rather than burning the attempt budget.

Collapsing ``RECONCILE`` into ``RETRY`` is the tempting simplification and it is the
one that sends a customer two messages: a timeout after the provider took the request
looks identical to a refusal before it, and only one of those is safe to repeat.
Collapsing it into ``PERMANENT`` is the opposite error - it silently drops a
notification that probably did arrive, and marks it failed so nobody looks again.

Nothing here decides *whether* to send
--------------------------------------
Eligibility, recipient and trigger were settled when the job was published. The worker
re-reads the delivery only to check it is still actionable - a channel that reached a
terminal state while the job sat in the queue must not be sent again. That check is the
reason a duplicate SQS delivery is harmless.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from lambda_utils.logging import get_logger, log_event

from . import keys as keys_mod
from . import policy as policy_mod
from . import states as states_mod
from . import store as store_mod

logger = get_logger(__name__)

RETRY = "RETRY"
RECONCILE = "RECONCILE"
PERMANENT = "PERMANENT"
SENT = "SENT"

OUTBOUND_WHATSAPP_FUNCTION = os.environ.get(
    "OUTBOUND_WHATSAPP_FUNCTION", "wecare-outbound-whatsapp:live")

#: Backoff before a retried job becomes visible again. Bounded and short: the whole
#: point of the notification is timeliness, and the attempt ceiling in `store.py`
#: stops it running forever.
RETRY_BACKOFF_SECONDS = int(os.environ.get("NOTIF_RETRY_BACKOFF_SECONDS", "60"))

#: Markers that mean "the request may have reached the provider". Deliberately narrow:
#: widening this turns ordinary refusals into reconciliation work nobody does.
_AMBIGUOUS_MARKERS = (
    "timeout", "timed out", "read timeout", "connection reset",
    "connectionreset", "brokenpipe", "incompleteread",
)

#: Definitely-not-sent transient markers. These are refusals, so repeating them is safe.
_RETRYABLE_MARKERS = (
    "throttl", "toomanyrequests", "serviceunavailable", "service_unavailable",
    "internalserver", "internalfailure", "503", "500",
    "provisionedthroughputexceeded", "requestlimitexceeded",
)

#: Cannot clear by retrying.
_PERMANENT_MARKERS = (
    "missing_dlt_template", "unapproved_dlt", "invalid_phone", "invalid phone",
    "validationexception", "accessdenied", "unauthorized", "forbidden",
    "not_registered", "opted_out", "blocked", "prohibited_provider",
    "template_unverified", "unsupported", "destination", "optout",
)


def classify_send_outcome(error: Optional[str], error_code: str = "") -> Tuple[str, str]:
    """`(disposition, category)` for a failed send. See the module docstring.

    Order matters. Ambiguity is tested **first**, because several ambiguous errors also
    contain a retryable-looking word - `ReadTimeout` on a throttled endpoint, say - and
    treating that as a plain retry is the duplicate-send path.
    """
    code = str(error_code or "").strip()
    text = f"{code} {error or ''}".lower()
    category = (code or "UNKNOWN").upper()[:60]

    for marker in _AMBIGUOUS_MARKERS:
        if marker in text:
            return RECONCILE, (code or marker).upper()[:60]
    for marker in _PERMANENT_MARKERS:
        if marker in text:
            return PERMANENT, (code or marker).upper()[:60]
    for marker in _RETRYABLE_MARKERS:
        if marker in text:
            return RETRY, (code or marker).upper()[:60]

    # Unknown: retry, bounded. The claim prevents a retry duplicating a completed send,
    # so the cost of being wrong is one wasted attempt - whereas calling an unknown
    # fault permanent silently drops a real notification.
    return RETRY, category


# ── channel adapters ──────────────────────────────────────────────────────────
#
# Each returns `(disposition, provider_message_id, category)`. None of them raises:
# an adapter that throws would lose the attempt record, which is the one thing the
# worker must always write.


def _send_sms(delivery: Dict[str, Any], *, request_id: str) -> Tuple[str, str, str]:
    """AWS End User Messaging, through the shared dispatcher that owns the DLT gate."""
    from lambda_utils.comms.notify import send_notification_sms

    try:
        outcome = send_notification_sms(
            delivery.get("destination", ""),
            notification_body(),
            dlt_template_key=str(delivery.get("dltTemplateKey") or ""),
            campaign="connected-call-notification",
            request_id=request_id,
            wait=True,
        )
    except Exception as exc:  # noqa: BLE001 - see the note above
        disposition, category = classify_send_outcome(str(exc), type(exc).__name__)
        return disposition, "", category

    if outcome.queued and not outcome.error:
        return SENT, outcome.provider_message_id or "", ""
    disposition, category = classify_send_outcome(
        outcome.error or outcome.skipped_reason)
    return disposition, outcome.provider_message_id or "", category


def _send_whatsapp(delivery: Dict[str, Any], *, request_id: str) -> Tuple[str, str, str]:
    """Meta Direct, via `wecare-outbound-whatsapp` rather than a direct Graph call.

    The retired call-notification code called Graph itself, with its own retry, its own
    sleep and its own `_send_via_aws` fallback - a second sender in parallel with the
    one every other caller uses. Routing through the shared function means the send
    inherits the smoke-test lockdown, the 24-hour window check, the sender resolution
    that refuses to guess a WABA, and the status reconciliation.
    """
    import boto3

    sender = str(delivery.get("senderPhoneId") or "")
    template = str(delivery.get("templateName") or policy_mod.WA_TEMPLATE_NAME)
    payload = {
        "recipientPhone": delivery.get("destination", ""),
        "phoneNumberId": sender,
        "isTemplate": True,
        "templateName": template,
        "templateParams": [str(delivery.get("templateLanguage")
                               or policy_mod.WA_TEMPLATE_LANGUAGE)],
    }
    event = {"body": json.dumps(payload)}

    try:
        response = boto3.client("lambda").invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps(event).encode())
        raw = response.get("Payload")
        body = raw.read().decode() if hasattr(raw, "read") else str(raw or "")
        if response.get("FunctionError"):
            disposition, category = classify_send_outcome(body[:200], "FunctionError")
            return disposition, "", category
        parsed = json.loads(body or "{}")
        status = int(parsed.get("statusCode") or 0)
        inner = json.loads(parsed.get("body") or "{}") if parsed.get("body") else {}
        if 200 <= status < 300:
            return SENT, str(inner.get("whatsappMessageId")
                             or inner.get("messageId") or ""), ""
        disposition, category = classify_send_outcome(
            json.dumps(inner)[:200], f"HTTP_{status}")
        return disposition, "", category
    except Exception as exc:  # noqa: BLE001
        disposition, category = classify_send_outcome(str(exc), type(exc).__name__)
        return disposition, "", category


def _send_rcs(delivery: Dict[str, Any], *, request_id: str) -> Tuple[str, str, str]:
    """India RCS through the approved Sinch module. Never a fallback to another channel."""
    try:
        from lambda_utils.sinch_rcs import send_rcs_ivr_notification
        result = send_rcs_ivr_notification(delivery.get("destination", ""), request_id)
    except Exception as exc:  # noqa: BLE001
        disposition, category = classify_send_outcome(str(exc), type(exc).__name__)
        return disposition, "", category

    if isinstance(result, dict) and result.get("success"):
        return SENT, str(result.get("message_id") or ""), ""
    error = (result or {}).get("error") if isinstance(result, dict) else str(result)
    disposition, category = classify_send_outcome(str(error))
    return disposition, "", category


_ADAPTERS = {
    keys_mod.CHANNEL_SMS: _send_sms,
    keys_mod.CHANNEL_WHATSAPP: _send_whatsapp,
    keys_mod.CHANNEL_RCS: _send_rcs,
}


def notification_body() -> str:
    """The SMS body. Must equal the approved India DLT template byte for byte.

    The operator silently drops a mismatched body while the API call still succeeds, so
    a "small improvement" here produces a send that reports success and delivers
    nothing. Overridable only by environment, never edited inline.
    """
    return os.environ.get("NOTIF_SMS_BODY", (
        "Thanks for contacting WECARE.DIGITAL!\n\n"
        "Submit your request here: https://wecare.digital/selfservice "
        "or send us a message / voice note on WhatsApp: https://r.wecare.digital/wa.\n\n"
        "We'll review it and follow up if needed."
    ))


# ── the job ───────────────────────────────────────────────────────────────────


def process_job(job_id: str, *, owner: str = "", request_id: str = "") -> Dict[str, Any]:
    """Send one channel for one call, at most once.

    Returns a dict with `handled` and `reason`; never raises for a provider problem.
    Raises only `store.NotificationStoreUnavailable`, which the caller must treat as
    "leave the message on the queue".
    """
    holder = owner or f"worker-{uuid.uuid4().hex[:12]}"

    delivery = store_mod.get_delivery(job_id)
    if delivery is None:
        # A job with no delivery cannot be reconciled against anything. Dropping it is
        # correct: the alternative is sending with no record that we did.
        log_event(logger, "notif_worker_orphan_job", level="error", jobId=job_id,
                  alert="NOTIF_ORPHAN_JOB", requestId=request_id)
        return {"handled": False, "reason": "orphan_job"}

    channel = str(delivery.get("channel") or "")
    if channel not in _ADAPTERS:
        return {"handled": False, "reason": f"unknown_channel_{channel}"}

    # The check that makes a duplicate SQS delivery harmless.
    #
    # `is_sendable`, NOT `not is_terminal`. `ACCEPTED` is not terminal - `DELIVERED` and
    # `READ` follow it - so a terminality test would treat an already-sent channel as
    # work to do and send it a second time. `RECONCILIATION_REQUIRED` is excluded for
    # the opposite reason: it is actionable, but by a reconciler, because the provider
    # may already have sent the message.
    current = states_mod.normalize(delivery.get("state"))
    if not states_mod.is_sendable(current):
        store_mod.release_job(job_id, status=current or states_mod.READY)
        return {"handled": False, "reason": f"not_sendable_{(current or 'unknown').lower()}"}
    if not store_mod.is_retryable(delivery):
        store_mod.record_attempt(job_id, state=states_mod.FAILED,
                                 error_category="ATTEMPTS_EXHAUSTED",
                                 error_is_permanent=True, request_id=request_id)
        store_mod.release_job(job_id, status=states_mod.FAILED)
        return {"handled": False, "reason": "attempts_exhausted"}

    if not store_mod.acquire_lease(job_id, owner=holder):
        # Another worker holds a live lease. Not an error - it is the guard working.
        return {"handled": False, "reason": "lease_held_elsewhere"}

    store_mod.record_attempt(job_id, state=states_mod.LEASED, request_id=request_id)

    disposition, provider_message_id, category = _ADAPTERS[channel](
        delivery, request_id=request_id)

    if disposition == SENT:
        store_mod.record_attempt(job_id, state=states_mod.ACCEPTED,
                                 provider=str(delivery.get("channelProvider") or ""),
                                 provider_message_id=provider_message_id,
                                 request_id=request_id)
        store_mod.release_job(job_id, status=states_mod.ACCEPTED)
        log_event(logger, "notif_worker_accepted", jobId=job_id, channel=channel,
                  requestId=request_id)
        return {"handled": True, "reason": "accepted",
                "providerMessageId": provider_message_id}

    if disposition == RECONCILE:
        # The important branch. The provider may have sent it, so this is neither a
        # success to report nor a failure to retry.
        store_mod.record_attempt(job_id, state=states_mod.RECONCILIATION_REQUIRED,
                                 error_category=category, request_id=request_id)
        store_mod.release_job(job_id, status=states_mod.RECONCILIATION_REQUIRED)
        log_event(logger, "notif_worker_reconciliation_required", level="error",
                  jobId=job_id, channel=channel, category=category,
                  alert="NOTIF_RECONCILIATION_REQUIRED", requestId=request_id)
        return {"handled": True, "reason": "reconciliation_required",
                "category": category}

    if disposition == PERMANENT:
        store_mod.record_attempt(job_id, state=states_mod.FAILED,
                                 error_category=category, error_is_permanent=True,
                                 request_id=request_id)
        store_mod.release_job(job_id, status=states_mod.FAILED)
        log_event(logger, "notif_worker_failed_permanent", level="error", jobId=job_id,
                  channel=channel, category=category, requestId=request_id)
        return {"handled": True, "reason": "failed_permanent", "category": category}

    # RETRY. Definitely not sent, so repeating is safe.
    store_mod.record_attempt(job_id, state=states_mod.READY,
                             error_category=category, request_id=request_id)
    store_mod.release_job(job_id, status=states_mod.READY,
                          available_at=int(time.time()) + RETRY_BACKOFF_SECONDS)
    log_event(logger, "notif_worker_retry_scheduled", jobId=job_id, channel=channel,
              category=category, backoffSeconds=RETRY_BACKOFF_SECONDS,
              requestId=request_id)
    return {"handled": True, "reason": "retry_scheduled", "category": category}


def sweep_ready_jobs(*, limit: int = 25, now: Optional[int] = None,
                     request_id: str = "") -> Dict[str, Any]:
    """Find `READY` outbox rows whose time has come and process them.

    This is the crash-before-enqueue recovery path, and the reason the outbox is the
    queue of record rather than SQS. The claim transaction writes the outbox row; if the
    process dies before anything reaches SQS, the row is still `READY` and this sweep
    picks it up. Without it the transactional outbox would be decorative.

    Queries the `status-availableAt-index` rather than scanning, so cost does not grow
    with history.
    """
    from boto3.dynamodb.conditions import Key

    stamp = int(now if now is not None else time.time())
    try:
        result = store_mod._res().Table(store_mod.OUTBOX_TABLE).query(
            IndexName="status-availableAt-index",
            KeyConditionExpression=(Key("status").eq(states_mod.READY)
                                    & Key("availableAt").lte(stamp)),
            Limit=limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise store_mod.NotificationStoreUnavailable("outbox query failed") from exc

    outcomes = {}
    for row in result.get("Items", []):
        job_id = str(row.get("jobId") or "")
        if not job_id:
            continue
        try:
            outcome = process_job(job_id, request_id=request_id)
            outcomes[job_id] = outcome.get("reason")
        except store_mod.NotificationStoreUnavailable:
            # Leave it READY; the next sweep retries. Do not let one unreachable row
            # abandon the rest of the batch.
            outcomes[job_id] = "store_unavailable"

    log_event(logger, "notif_sweep_complete", examined=len(result.get("Items", [])),
              processed=len(outcomes), requestId=request_id)
    return {"examined": len(result.get("Items", [])), "outcomes": outcomes}
