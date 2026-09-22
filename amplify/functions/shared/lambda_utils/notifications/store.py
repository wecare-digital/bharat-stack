"""Durable state for the notification domain, and the atomic claim-plus-publish.

Four records, and why they are four
-----------------------------------
``NotificationEvents``      one row per verified connected call (the parent claim)
``NotificationDeliveries``  one row per (call, channel) - the logical delivery
``NotificationAttempts``    append-only; one row per physical send attempt
``NotificationOutbox``      the work queue of record, leased by workers

The split between *delivery* and *attempt* is the brief's distinction between one
logical delivery and an unbounded number of physical attempts. Collapsing them - as
the retired module did, by incrementing ``attemptCount`` on the delivery row - means
the history of what was tried is overwritten by its own summary, so a duplicate and
a retry look identical after the fact.

Why claim-before-send is not enough on its own
----------------------------------------------
The retired module claimed, then sent, then recorded. That is strictly better than
send-then-record, and it is still not exactly-once: if the process dies after the
claim and before the enqueue, the claim row exists and says ``PENDING`` forever.
Nothing is holding the work. Plivo's redelivery then finds the claim already taken
and does nothing, so the customer is never notified and no alarm fires. Measured in
this repo: the RCS channel of the old design has exactly that shape, deliberately
left ``PENDING`` with a comment, and no worker was ever built to drain it.

So the claim and the job are written in **one** ``TransactWriteItems``. Either the
channel is claimed *and* there is a job to do it, or neither exists and the
provider's retry legitimately re-creates both. That is what makes a duplicate parent
event able to recover unfinished channel work, which the brief requires explicitly.

Fail closed, distinctly
-----------------------
Every store failure raises ``NotificationStoreUnavailable``, never a bare
``Exception`` and never a falsy return. A caller that cannot reach the store must
return a retryable 5xx and send nothing. This keeps the contract established by the
now-deleted ``pstn.claims`` and deliberately does NOT mirror
``lambda_utils.webhook_dedup``, which returns True on
error because dropping an inbound webhook is worse than processing it twice. For
*sending a customer a message* that reasoning inverts: a store outage would become
duplicate SMS to real people, billed to us, under our registered DLT sender, with
no bound on provider retries.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from lambda_utils.logging import get_logger, log_event

from . import states as states_mod

logger = get_logger(__name__)

# Literal defaults, not built from a prefix variable.
#
# `scripts/audit_data_model_drift.py` compares table-name literals in Python against
# `ListTables`. An f-string default is invisible to it, so a prefix-assembled name
# reports as LIVE_BUT_UNREFERENCED - the table exists but nothing can be shown to use
# it. That is the same blind spot that let `PstnNotificationDelivery` be referenced by
# code while existing nowhere: if the audit cannot trace the name, it cannot tell you
# the name is wrong.
EVENTS_TABLE = os.environ.get(
    "NOTIF_EVENTS_TABLE", "stack-wecare-digital-NotificationEvents")
DELIVERIES_TABLE = os.environ.get(
    "NOTIF_DELIVERIES_TABLE", "stack-wecare-digital-NotificationDeliveries")
ATTEMPTS_TABLE = os.environ.get(
    "NOTIF_ATTEMPTS_TABLE", "stack-wecare-digital-NotificationAttempts")
OUTBOX_TABLE = os.environ.get(
    "NOTIF_OUTBOX_TABLE", "stack-wecare-digital-NotificationOutbox")

#: 30 days. Long enough that no provider retry window can outlive a claim - a claim
#: expiring while a redelivery is still possible would permit a duplicate send -
#: and short enough that the tables do not grow without bound.
CLAIM_TTL_SECONDS = int(os.environ.get("NOTIF_CLAIM_TTL_SECONDS", str(30 * 24 * 3600)))

#: Attempt history outlives the claim: it is the audit trail, and the brief forbids
#: erasing audit history as part of the rebuild.
ATTEMPT_TTL_SECONDS = int(os.environ.get("NOTIF_ATTEMPT_TTL_SECONDS", str(90 * 24 * 3600)))

#: How long a worker may hold a job before another may reclaim it. Must exceed the
#: worker's own timeout, or a still-running worker's job gets taken and the send
#: happens twice.
LEASE_SECONDS = int(os.environ.get("NOTIF_LEASE_SECONDS", "300"))

MAX_ATTEMPTS = int(os.environ.get("NOTIF_MAX_ATTEMPTS", "3"))

_resource = None
_client = None


class NotificationStoreUnavailable(RuntimeError):
    """The store could not be reached, so the claim state is UNKNOWN.

    A distinct type so it cannot be swallowed by a broad `except Exception` written
    to tolerate provider errors. Callers must treat it as "do not send" and return a
    retryable 5xx.
    """


def _res():
    global _resource
    if _resource is None:
        import boto3
        _resource = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _resource


def _cli():
    global _client
    if _client is None:
        import boto3
        _client = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _client


def _s(value: Any) -> Dict[str, str]:
    return {"S": str(value)}


def _n(value: Any) -> Dict[str, str]:
    return {"N": str(int(value))}


def _bool(value: Any) -> Dict[str, bool]:
    return {"BOOL": bool(value)}


def claim_event_and_publish(event, decisions: Dict[str, Any], *,
                            request_id: str = "") -> Dict[str, Any]:
    """Claim the call, create one delivery per channel, and publish the eligible jobs.

    All of it in a single ``TransactWriteItems``, conditional on the parent claim not
    already existing. Outcomes:

    * ``{'claimed': True, ...}``   this process owns the call; jobs exist
    * ``{'claimed': False, 'reason': 'duplicate_connected_event'}``  somebody else does
    * raises ``NotificationStoreUnavailable``  state unknown; send nothing

    The conditional is on the **parent** only. The deliveries and outbox rows are
    unconditional puts inside the same transaction, which is safe precisely because
    the parent condition serialises the whole thing: if the parent already exists the
    transaction is rejected in its entirety and nothing is overwritten.

    Ineligible channels still get a delivery row, in ``SKIPPED``, with no outbox job.
    That is what makes "not applicable" auditable instead of absent.
    """
    from botocore.exceptions import ClientError

    now = int(time.time())
    expires = now + CLAIM_TTL_SECONDS
    parent = event.parent_claim_key

    items: List[Dict[str, Any]] = [{
        "Put": {
            "TableName": EVENTS_TABLE,
            "Item": {
                "eventClaimKey": _s(parent),
                "provider": _s(event.provider),
                "canonicalCallId": _s(event.canonical_call_id),
                "direction": _s(event.direction),
                "trigger": _s(event.trigger),
                "externalParty": _s(event.external_party),
                "businessNumber": _s(event.business_number),
                "isoCountry": _s(event.iso_country or ""),
                "connectedAt": _n(event.connected_at),
                "claimedAt": _n(now),
                "createdAt": _n(now),
                "expiresAt": _n(expires),
            },
            # The whole mechanism. One writer wins; concurrent duplicates lose.
            "ConditionExpression": "attribute_not_exists(eventClaimKey)",
        }
    }]

    published: List[str] = []
    skipped: List[str] = []

    for channel, decision in decisions.items():
        delivery_id = event.child_claim_key(channel)
        delivery: Dict[str, Any] = {
            "deliveryId": _s(delivery_id),
            "eventClaimKey": _s(parent),
            "provider": _s(event.provider),
            "canonicalCallId": _s(event.canonical_call_id),
            "channel": _s(channel),
            "state": _s(decision.state),
            states_mod.RANK_ATTRIBUTE: _n(states_mod.rank(decision.state)),
            "destination": _s(event.external_party),
            "isoCountry": _s(event.iso_country or ""),
            "eligibility": _s("ELIGIBLE" if decision.eligible else "INELIGIBLE"),
            "eligibilityReason": _s(decision.reason[:400]),
            "channelProvider": _s(decision.provider or ""),
            "attemptCount": _n(0),
            "maxAttempts": _n(MAX_ATTEMPTS),
            "createdAt": _n(now),
            "expiresAt": _n(expires),
        }
        for field, value in (("templateName", decision.template_name),
                             ("templateId", decision.template_id),
                             ("region", decision.region),
                             ("dltTemplateKey", decision.dlt_template_key),
                             ("senderLabel", decision.sender_label)):
            if value:
                delivery[field] = _s(value)
        if not decision.eligible:
            delivery["completedAt"] = _n(now)
            delivery["errorIsPermanent"] = _bool(True)

        items.append({"Put": {"TableName": DELIVERIES_TABLE, "Item": delivery}})

        if not decision.eligible:
            skipped.append(channel)
            continue

        items.append({"Put": {
            "TableName": OUTBOX_TABLE,
            "Item": {
                "jobId": _s(delivery_id),
                "deliveryId": _s(delivery_id),
                "eventClaimKey": _s(parent),
                "channel": _s(channel),
                "status": _s(states_mod.READY),
                "availableAt": _n(now),
                "leaseExpiresAt": _n(0),
                "leaseOwner": _s(""),
                "attemptCount": _n(0),
                "maxAttempts": _n(MAX_ATTEMPTS),
                "createdAt": _n(now),
                "expiresAt": _n(expires),
            },
        }})
        published.append(channel)

    try:
        _cli().transact_write_items(TransactItems=items)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        reasons = exc.response.get("CancellationReasons") or []
        if code == "TransactionCanceledException" and any(
                (r or {}).get("Code") == "ConditionalCheckFailed" for r in reasons):
            log_event(logger, "notif_event_duplicate", eventClaimKey=parent,
                      requestId=request_id)
            return {"claimed": False, "reason": "duplicate_connected_event",
                    "eventClaimKey": parent}
        log_event(logger, "notif_store_error", level="error", eventClaimKey=parent,
                  errorCode=code, alert="NOTIF_STORE_UNAVAILABLE", requestId=request_id)
        raise NotificationStoreUnavailable(
            f"store error ({code}); refusing to send unguarded") from exc
    except Exception as exc:  # noqa: BLE001 - see module docstring
        log_event(logger, "notif_store_error", level="error", eventClaimKey=parent,
                  errorType=type(exc).__name__,
                  alert="NOTIF_STORE_UNAVAILABLE", requestId=request_id)
        raise NotificationStoreUnavailable(
            "store unreachable; refusing to send unguarded") from exc

    log_event(logger, "notif_event_claimed", eventClaimKey=parent,
              provider=event.provider, direction=event.direction,
              publishedChannels=",".join(sorted(published)) or None,
              skippedChannels=",".join(sorted(skipped)) or None,
              requestId=request_id)
    return {"claimed": True, "eventClaimKey": parent,
            "published": published, "skipped": skipped}


def acquire_lease(job_id: str, *, owner: str = "", now: Optional[int] = None,
                  lease_seconds: Optional[int] = None) -> bool:
    """Take a job, or return False if somebody else holds a live lease.

    The condition admits three cases and no others: the job is ``READY``, or its
    lease has expired, or it is unleased. A live lease held by another worker is
    refused, which is what stops two workers sending the same channel.

    An expired lease being reclaimable is the crash-recovery path. It is also why
    ``LEASE_SECONDS`` must exceed the worker's Lambda timeout: reclaiming a lease
    from a worker that is still running would send twice.
    """
    from botocore.exceptions import ClientError

    stamp = int(now if now is not None else time.time())
    duration = int(lease_seconds if lease_seconds is not None else LEASE_SECONDS)
    holder = owner or f"worker-{uuid.uuid4().hex[:12]}"

    try:
        _res().Table(OUTBOX_TABLE).update_item(
            Key={"jobId": job_id},
            UpdateExpression=(
                "SET #status = :leased, leaseOwner = :owner, "
                "leaseExpiresAt = :expiry, leasedAt = :now"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":leased": states_mod.LEASED,
                ":owner": holder,
                ":expiry": stamp + duration,
                ":now": stamp,
                ":ready": states_mod.READY,
                ":stamp": stamp,
            },
            ConditionExpression=(
                "attribute_exists(jobId) AND "
                "(#status = :ready OR attribute_not_exists(leaseExpiresAt) "
                " OR leaseExpiresAt < :stamp)"
            ),
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise NotificationStoreUnavailable("outbox lease failed") from exc
    except Exception as exc:  # noqa: BLE001
        raise NotificationStoreUnavailable("outbox unreachable") from exc


def record_attempt(delivery_id: str, *, state: str, provider: str = "",
                   provider_message_id: str = "", error_category: str = "",
                   error_is_permanent: bool = False, request_id: str = "",
                   attempt_detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append an attempt and advance the delivery, guarded by the state machine.

    Two writes, deliberately not a transaction:

    * the attempt row is appended **unconditionally** - it is history, and history
      of a refused transition is still history worth having;
    * the delivery row moves only if `states.condition_expression()` permits it.

    Returns `{'applied': bool, 'reason': str, 'delivery': {...}}`. A refused
    transition is not an error: a late `SENT` arriving after `DELIVERED` is exactly
    what the guard is for, and the caller should carry on.
    """
    from botocore.exceptions import ClientError

    target = states_mod.normalize(state)
    if not target:
        raise ValueError(f"unknown delivery state {state!r}")

    now = int(time.time())
    attempt_id = f"{delivery_id}#{now}#{uuid.uuid4().hex[:8]}"

    attempt: Dict[str, Any] = {
        "attemptId": attempt_id,
        "deliveryId": delivery_id,
        "state": target,
        "at": now,
        "expiresAt": now + ATTEMPT_TTL_SECONDS,
    }
    if provider:
        attempt["provider"] = provider
    if provider_message_id:
        attempt["providerMessageId"] = provider_message_id
    if error_category:
        attempt["errorCategory"] = error_category[:200]
        attempt["errorIsPermanent"] = bool(error_is_permanent)
    if attempt_detail:
        # Bounded, and never a raw provider dump: an attempt row is read by
        # operators and must not become a place customer data accumulates.
        attempt["detail"] = json.dumps(attempt_detail, default=str)[:1000]

    try:
        _res().Table(ATTEMPTS_TABLE).put_item(Item=attempt)
    except Exception as exc:  # noqa: BLE001
        raise NotificationStoreUnavailable("attempt store unreachable") from exc

    sets = [
        "#state = :s",
        f"{states_mod.RANK_ATTRIBUTE} = :rank",
        "lastAttemptAt = :now",
        "attemptCount = if_not_exists(attemptCount, :zero) + :one",
        "firstAttemptAt = if_not_exists(firstAttemptAt, :now)",
        "lastAttemptId = :attemptId",
    ]
    values: Dict[str, Any] = {
        ":s": target,
        ":now": now,
        ":zero": 0,
        ":one": 1,
        ":attemptId": attempt_id,
    }
    values.update(states_mod.condition_values(target))

    if states_mod.is_terminal(target) or target in (states_mod.DELIVERED, states_mod.READ):
        sets.append("completedAt = :now")
    if provider:
        sets.append("channelProvider = :provider")
        values[":provider"] = provider
    if provider_message_id:
        sets.append("providerMessageId = :pmid")
        values[":pmid"] = provider_message_id
    if error_category:
        sets.append("errorCategory = :err")
        sets.append("errorIsPermanent = :perm")
        values[":err"] = error_category[:200]
        values[":perm"] = bool(error_is_permanent)

    try:
        result = _res().Table(DELIVERIES_TABLE).update_item(
            Key={"deliveryId": delivery_id},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues=values,
            ConditionExpression=(
                "attribute_exists(deliveryId) AND "
                + states_mod.condition_expression(target)
            ),
            ReturnValues="ALL_NEW",
        )
        log_event(logger, "notif_delivery_advanced", deliveryId=delivery_id,
                  state=target, provider=provider or None, requestId=request_id)
        return {"applied": True, "reason": "forward", "attemptId": attempt_id,
                "delivery": result.get("Attributes", {}) or {}}
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            current = get_delivery(delivery_id)
            if current is None:
                # No claim exists. Recording a send for an unclaimed call would
                # defeat the guard the whole design rests on.
                raise NotificationStoreUnavailable(
                    f"no delivery claim exists for {delivery_id}") from exc
            _, reason = states_mod.apply_receipt(current.get("state"), target)
            log_event(logger, "notif_delivery_transition_refused",
                      deliveryId=delivery_id, current=str(current.get("state")),
                      incoming=target, reason=reason, requestId=request_id)
            return {"applied": False, "reason": reason, "attemptId": attempt_id,
                    "delivery": current}
        raise NotificationStoreUnavailable("delivery store error") from exc
    except Exception as exc:  # noqa: BLE001
        raise NotificationStoreUnavailable("delivery store unreachable") from exc


def get_delivery(delivery_id: str) -> Optional[Dict[str, Any]]:
    """Read a delivery, or None when unclaimed.

    Raises rather than returning None on a store error: "no claim" and "cannot tell"
    must not look the same to a caller deciding whether to send.
    """
    try:
        return _res().Table(DELIVERIES_TABLE).get_item(
            Key={"deliveryId": delivery_id}).get("Item")
    except Exception as exc:  # noqa: BLE001
        raise NotificationStoreUnavailable("delivery store unreachable on read") from exc


def get_event(event_claim_key: str) -> Optional[Dict[str, Any]]:
    try:
        return _res().Table(EVENTS_TABLE).get_item(
            Key={"eventClaimKey": event_claim_key}).get("Item")
    except Exception as exc:  # noqa: BLE001
        raise NotificationStoreUnavailable("event store unreachable on read") from exc


def is_retryable(record: Optional[Dict[str, Any]]) -> bool:
    """Whether a delivery should be attempted again.

    A terminal delivery is never retried, which is what stops a retry of one channel
    duplicating another. A permanent error is never retried either: DLT, destination,
    validation and permission failures do not clear, so retrying only burns the
    attempt budget and delays the dead-letter signal.
    """
    if not record:
        return True
    if states_mod.is_terminal(record.get("state")):
        return False
    if record.get("errorIsPermanent"):
        return False
    attempts = int(record.get("attemptCount") or 0)
    ceiling = int(record.get("maxAttempts") or MAX_ATTEMPTS)
    return attempts < ceiling


def release_job(job_id: str, *, status: str, available_at: Optional[int] = None) -> None:
    """Hand a job back, either for retry (`READY`) or as finished.

    Unconditional on purpose: the worker that holds the lease is the only caller, and
    a conditional release that failed would leave a live lease blocking recovery
    until it expired.
    """
    try:
        _res().Table(OUTBOX_TABLE).update_item(
            Key={"jobId": job_id},
            UpdateExpression=(
                "SET #status = :s, leaseOwner = :empty, leaseExpiresAt = :zero, "
                "availableAt = :available, attemptCount = if_not_exists(attemptCount, :zero) + :one"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":s": states_mod.normalize(status) or states_mod.READY,
                ":empty": "",
                ":zero": 0,
                ":one": 1,
                ":available": int(available_at if available_at is not None else time.time()),
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise NotificationStoreUnavailable("outbox unreachable on release") from exc


def table_names() -> Dict[str, str]:
    """The four physical table names, for diagnostics and the IaC drift audit."""
    return {
        "events": EVENTS_TABLE,
        "deliveries": DELIVERIES_TABLE,
        "attempts": ATTEMPTS_TABLE,
        "outbox": OUTBOX_TABLE,
    }
