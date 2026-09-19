"""Fail-CLOSED atomic claims, for side effects that must happen at most once.

The contract, and the whole reason this exists
----------------------------------------------
    claim(...)  ->  True   you hold the claim; perform the side effect
                    False  somebody else holds it; do nothing
                    raises ClaimStoreUnavailable  state unknown; do NOTHING and
                                                  return a retryable 5xx

The third outcome is the point. `lambda_utils.webhook_dedup.claim_event` returns
True on a DynamoDB error, so a store outage means "process it anyway". For
ingesting an inbound event that is correct - dropping a real webhook is worse than
processing it twice.

For sending a customer a message it is not. Failing open there turns a store
outage into duplicate SMS to real people, billed to us, under our registered DLT
sender, with no upper bound on how many times the provider retries. Plivo will
redeliver a 5xx, so refusing to guess costs a delay and nothing else.

Both behaviours are right for their own job. They are separate modules rather than
one module with a flag, because a flag gets passed wrongly eventually and the
failure is invisible until it is expensive.

Never put a payload in a key
----------------------------
Claim keys are logged, emitted as metric dimensions and stored. `keys.py` builds
them from provider identifiers only - never a webhook body, a token or a phone
number.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from lambda_utils.logging import get_logger, log_event

logger = get_logger(__name__)

# Deliberately NOT the shared WebhookDedup table. A claim here means "a customer
# notification decision was made", which has a different retention requirement and
# a different blast radius from webhook de-duplication, and mixing them would let a
# sweep of one purge the other.
CLAIM_TABLE = os.environ.get("PSTN_CLAIM_TABLE",
                             "stack-wecare-digital-PstnNotificationDelivery")

# 30 days. Long enough that a provider's retry window cannot outlive a claim;
# short enough that the table does not grow without bound. A claim expiring while
# retries are still possible would permit a duplicate send.
CLAIM_TTL_SECONDS = int(os.environ.get("PSTN_CLAIM_TTL_SECONDS", str(30 * 24 * 3600)))

_resource = None


class ClaimStoreUnavailable(RuntimeError):
    """The claim store could not be reached, so the claim state is UNKNOWN.

    Callers must treat this as "do not perform the side effect" and return a
    retryable 5xx. It is a distinct type so it cannot be swallowed by a broad
    `except Exception` that was written to tolerate provider errors.
    """


def _table():
    global _resource
    if _resource is None:
        import boto3
        _resource = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _resource.Table(CLAIM_TABLE)


def claim(claim_id: str, *, call_id: str = "", channel: str = "",
          a_leg_uuid: str = "", attributes: Optional[Dict[str, Any]] = None,
          request_id: str = "") -> bool:
    """Atomically claim `claim_id`. See the module docstring for the contract.

    The conditional put is on the PRIMARY KEY, so the claim and the record are the
    same write. There is no read-then-write window for two concurrent workers to
    both pass.
    """
    from botocore.exceptions import ClientError

    key = str(claim_id or "").strip()
    if not key:
        # Not a store problem, so not ClaimStoreUnavailable: a caller that cannot
        # name what it is claiming has a bug, and proceeding would be unguarded.
        raise ValueError("claim_id is required")

    now = int(time.time())
    item: Dict[str, Any] = {
        "deliveryId": key,
        "claimedAt": now,
        "state": "PENDING",
        "attemptCount": 0,
        "createdAt": now,
        "expiresAt": now + CLAIM_TTL_SECONDS,
    }
    if call_id:
        item["callId"] = call_id
    if channel:
        item["channel"] = channel
    if a_leg_uuid:
        item["aLegUuid"] = a_leg_uuid
    if attributes:
        for field, value in attributes.items():
            if value not in (None, ""):
                item[field] = value

    try:
        _table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(deliveryId)",
        )
        log_event(logger, "pstn_claim_acquired", claimId=key, channel=channel or None,
                  requestId=request_id)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            log_event(logger, "pstn_claim_duplicate", claimId=key,
                      channel=channel or None, requestId=request_id)
            return False
        log_event(logger, "pstn_claim_store_error", level="error",
                  claimId=key, channel=channel or None, errorCode=code,
                  alert="PSTN_CLAIM_STORE_UNAVAILABLE", requestId=request_id)
        raise ClaimStoreUnavailable(
            f"claim store error ({code}); refusing to send unguarded") from exc
    except Exception as exc:  # noqa: BLE001 - see module docstring
        log_event(logger, "pstn_claim_store_error", level="error",
                  claimId=key, channel=channel or None,
                  errorType=type(exc).__name__,
                  alert="PSTN_CLAIM_STORE_UNAVAILABLE", requestId=request_id)
        raise ClaimStoreUnavailable(
            "claim store unreachable; refusing to send unguarded") from exc


def record_attempt(claim_id: str, *, state: str, provider: str = "",
                   provider_message_id: str = "", error_category: str = "",
                   error_is_permanent: bool = False,
                   request_id: str = "") -> Dict[str, Any]:
    """Advance a claimed delivery to a terminal or retryable state.

    Increments `attemptCount` atomically and appends to `statusTransitions`, so
    the history of a delivery survives even when two workers race - the count is
    the evidence that a retry happened rather than a duplicate claim.

    Raises ClaimStoreUnavailable on a store failure, for the same reason `claim`
    does: a caller that cannot record the outcome must not report success.
    """
    from botocore.exceptions import ClientError

    key = str(claim_id or "").strip()
    if not key:
        raise ValueError("claim_id is required")
    if state not in ("PENDING", "SENT", "FAILED", "SKIPPED"):
        raise ValueError(f"invalid delivery state {state!r}")

    now = int(time.time())
    transition = f'{{"state":"{state}","at":{now}}}'

    expression_names = {"#s": "state"}
    expression_values: Dict[str, Any] = {
        ":s": state,
        ":one": 1,
        ":zero": 0,
        ":now": now,
        ":transition": [transition],
        ":empty": [],
    }
    sets = [
        "#s = :s",
        "lastAttemptAt = :now",
        "attemptCount = if_not_exists(attemptCount, :zero) + :one",
        "firstAttemptAt = if_not_exists(firstAttemptAt, :now)",
        "statusTransitions = list_append(if_not_exists(statusTransitions, :empty), :transition)",
    ]
    if state in ("SENT", "FAILED", "SKIPPED"):
        sets.append("completedAt = :now")
    if provider:
        sets.append("provider = :provider")
        expression_values[":provider"] = provider
    if provider_message_id:
        sets.append("providerMessageId = :pmid")
        expression_values[":pmid"] = provider_message_id
    if error_category:
        sets.append("errorCategory = :err")
        expression_values[":err"] = error_category
        sets.append("errorIsPermanent = :perm")
        expression_values[":perm"] = bool(error_is_permanent)

    try:
        result = _table().update_item(
            Key={"deliveryId": key},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
            # Refuse to resurrect a claim that was never made. Creating the row
            # here would mean a worker could record a send for a call nobody
            # claimed, which is exactly the guard being relied on.
            ConditionExpression="attribute_exists(deliveryId)",
            ReturnValues="ALL_NEW",
        )
        log_event(logger, "pstn_delivery_recorded", claimId=key, state=state,
                  provider=provider or None, requestId=request_id)
        return result.get("Attributes", {}) or {}
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            raise ClaimStoreUnavailable(
                f"no claim exists for {key}; refusing to record an unclaimed send"
            ) from exc
        raise ClaimStoreUnavailable(f"claim store error ({code})") from exc
    except Exception as exc:  # noqa: BLE001
        raise ClaimStoreUnavailable("claim store unreachable") from exc


def get(claim_id: str) -> Optional[Dict[str, Any]]:
    """Read a delivery record. Returns None when unclaimed.

    Raises ClaimStoreUnavailable on a store failure rather than returning None: a
    read error and "no claim" must not look the same to a caller deciding whether
    to send.
    """
    key = str(claim_id or "").strip()
    if not key:
        return None
    try:
        return _table().get_item(Key={"deliveryId": key}).get("Item")
    except Exception as exc:  # noqa: BLE001
        raise ClaimStoreUnavailable("claim store unreachable on read") from exc


def is_retryable(record: Optional[Dict[str, Any]]) -> bool:
    """Whether an existing delivery should be attempted again.

    A completed channel is never retried, which is what stops a retry of one
    channel from duplicating the other. A permanent error is never retried either,
    because DLT, destination, validation and permission failures do not clear -
    retrying them just burns the attempt budget and delays the dead-letter signal.
    """
    if not record:
        return True
    state = str(record.get("state") or "").upper()
    if state == "SENT":
        return False
    if state == "SKIPPED":
        return False
    if record.get("errorIsPermanent"):
        return False
    attempts = int(record.get("attemptCount") or 0)
    max_attempts = int(record.get("maxAttempts") or 3)
    return attempts < max_attempts
