"""Lambda wrapper for the notification outbox worker.

Deliberately thin. Every decision - trigger validity, recipient, eligibility, claim,
state transition, retry-versus-reconcile - lives in `lambda_utils.notifications`, which
is unit-testable without AWS. This file only translates an invocation shape into calls
on that domain, which is why it has no business logic to test separately.

Three invocation shapes
-----------------------
**SQS batch.** The normal path. One message per job id. Uses partial batch failure
(`batchItemFailures`), so one poison message does not redrive the whole batch - which
would re-process jobs that already succeeded, and with at-least-once delivery that means
re-examining channels that have already been sent.

**Scheduled sweep.** The recovery path, and the reason the outbox is the queue of record
rather than SQS. The claim transaction writes the outbox row; if the process dies before
anything reaches SQS, the row is still `READY` and the sweep finds it. Without this the
transactional outbox would be decorative.

**Direct invoke** `{"action": "sweep"}` for operators, and `{"action": "status"}` which
reports configuration without touching a provider or a customer.

Failure handling
----------------
A store failure raises `NotificationStoreUnavailable`, and the message is returned to the
queue rather than acknowledged. That is the correct direction: the alternative is dropping
a notification because DynamoDB was briefly unreachable. A *provider* failure is not an
error here at all - the worker records it and the job is either retried, reconciled or
failed, so the message is acknowledged.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from lambda_utils.logging import get_logger, log_event
from lambda_utils.notifications import service as notif_service
from lambda_utils.notifications import store as notif_store
from lambda_utils.notifications import worker as notif_worker

logger = get_logger(__name__)

SWEEP_LIMIT = int(os.environ.get("NOTIF_SWEEP_LIMIT", "25"))


def _job_id_from_record(record: Dict[str, Any]) -> str:
    """The job id from one SQS record, tolerating a bare-string body.

    A bare string is accepted because the sweep and any operator replay both publish the
    id directly; refusing it would make the recovery path depend on an envelope it has no
    reason to build.
    """
    body = record.get("body") or ""
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return str(body).strip()
    if isinstance(parsed, dict):
        return str(parsed.get("jobId") or parsed.get("deliveryId") or "").strip()
    return str(parsed).strip()


def _handle_sqs(records: List[Dict[str, Any]], request_id: str) -> Dict[str, Any]:
    failures: List[Dict[str, str]] = []
    outcomes: Dict[str, str] = {}

    for record in records:
        message_id = record.get("messageId", "")
        job_id = _job_id_from_record(record)
        if not job_id:
            # Unparseable: acknowledge it. Returning it would redrive forever, and there
            # is no job to recover.
            log_event(logger, "notif_worker_unparseable_message", level="error",
                      messageId=message_id, requestId=request_id)
            outcomes[message_id] = "unparseable"
            continue
        try:
            result = notif_worker.process_job(job_id, request_id=request_id)
            outcomes[job_id] = str(result.get("reason"))
        except notif_store.NotificationStoreUnavailable:
            # Do not acknowledge: the state is unknown and the job must be re-examined.
            log_event(logger, "notif_worker_store_unavailable", level="error",
                      jobId=job_id, alert="NOTIF_STORE_UNAVAILABLE",
                      requestId=request_id)
            failures.append({"itemIdentifier": message_id})
            outcomes[job_id] = "store_unavailable"

    log_event(logger, "notif_worker_batch", received=len(records),
              returned=len(failures), requestId=request_id)
    return {"batchItemFailures": failures, "outcomes": outcomes}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "local") if context else "local"

    if isinstance(event, dict) and event.get("Records"):
        return _handle_sqs(event["Records"], request_id)

    action = str((event or {}).get("action") or "").strip().lower()

    if action == "status":
        # Safe to call at any time: reads configuration only.
        return {"statusCode": 200, "body": json.dumps(notif_service.describe(),
                                                      default=str)}

    if action == "sweep" or (isinstance(event, dict) and event.get("source") == "aws.events"):
        if not notif_service.is_enabled():
            # Nothing can be claimed while the domain is off, so there is nothing to
            # sweep. Reported rather than silently returning an empty result.
            log_event(logger, "notif_sweep_skipped_disabled", requestId=request_id)
            return {"statusCode": 200,
                    "body": json.dumps({"swept": 0, "reason": "feature_disabled"})}
        try:
            result = notif_worker.sweep_ready_jobs(limit=SWEEP_LIMIT,
                                                  request_id=request_id)
        except notif_store.NotificationStoreUnavailable as exc:
            log_event(logger, "notif_sweep_store_unavailable", level="error",
                      error=type(exc).__name__, alert="NOTIF_STORE_UNAVAILABLE",
                      requestId=request_id)
            return {"statusCode": 503,
                    "body": json.dumps({"error": "store unavailable"})}
        return {"statusCode": 200, "body": json.dumps(result, default=str)}

    job_id = str((event or {}).get("jobId") or "").strip()
    if job_id:
        result = notif_worker.process_job(job_id, request_id=request_id)
        return {"statusCode": 200, "body": json.dumps(result, default=str)}

    log_event(logger, "notif_worker_unrecognised_event", level="warning",
              topLevelKeys=sorted((event or {}).keys())[:10], requestId=request_id)
    return {"statusCode": 400,
            "body": json.dumps({"error": "expected SQS Records, action, or jobId"})}
