"""Read-only access to retired-provider SMS history.

Retiring a provider must not destroy the record of traffic it carried. The
`AirtelSMSTable` rows are real messages that really were delivered by a carrier we
no longer use, and some of them were carried by a second retired aggregator that
wrote into the same table under its own provider label.

The only read path for that data used to be inside the Lambda being deleted, so
this module exists to keep the history reachable after the sender is gone.

The table is gone as well - measured, 2026-09-24
-----------------------------------------------
`ListTables` does not return `stack-wecare-digital-AirtelSMSTable`. It was deleted
on 2026-09-20 with the Airtel retirement, which `operations/system-cleanup` records
and this module did not. So every function below was reading a store that no longer
exists, and the live route that reaches them
(`sms-aws` -> `_legacy_history_route`) answered 500 as though the platform were
faulty.

The preservation intent above is unchanged and still correct; what changed is that
it was not honoured, and this module now says so instead of raising. The reads
report `storeAbsent` rather than an empty result, because "there is no record"
and "the record was deleted" are different answers and only one of them is true.
Whether to restore from a backup is a decision for whoever owns the retention
policy, and it cannot be taken while the code presents the loss as a 500.

Read-only by construction
-------------------------
There is no create and no update here. A historical record is a statement about
something that already happened; the only legitimate mutation is deletion under a
retention policy, which is `purge()` and is separately authorised.

Provider labelling
------------------
`normalize()` reports the ORIGINAL provider for every row and marks it
`isHistorical: True`. Rows are never relabelled as the current provider. A
message sent in 2026 by a retired carrier under a DLT template is evidence, and
rewriting its provider to make a dashboard tidy would destroy the audit trail -
including the ability to answer "which carrier delivered this" during a DLT
dispute.

The `provider` field is absent on the oldest rows, because at the time there was
only one sender. Those are reported as `legacy-india-operator` rather than guessed
at, so "we know it was the Indian A2P path" is not confused with "we know which
vendor".
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, Optional

from lambda_utils import retired_store

LEGACY_SMS_TABLE = os.environ.get("LEGACY_SMS_TABLE",
                                  "stack-wecare-digital-AirtelSMSTable")


def _store_absent() -> Dict[str, Any]:
    """The one description of the absence, so all four paths agree."""
    return {
        **retired_store.absent_payload(
            LEGACY_SMS_TABLE,
            what="Retired-provider SMS history",
            retired="Deleted 2026-09-20 with the Airtel retirement.",
        ),
        "messages": [],
        "count": 0,
    }

# Stored provider literals, mapped to a human label. These strings are DATA, not
# configuration: they describe traffic that really was sent that way and must not
# be rewritten. See docs/provider-retirement-inventory.md section 6.
_PROVIDER_LABELS = {
    "airtel": "Airtel IQ (retired 2026-09-19)",
    "sinch": "Sinch SMS (retired 2026-09-19)",
    "pinpoint": "AWS (classic Pinpoint, superseded)",
    "pinpoint-india": "AWS ap-south-1 (classic, superseded)",
    "aws": "AWS End User Messaging",
    "aws-end-user-messaging": "AWS End User Messaging",
}

# Rows predating the provider column. Deliberately vague - it names the route, not
# a vendor, because the vendor genuinely is not recorded.
_UNKNOWN_PROVIDER = "legacy-india-operator"
_UNKNOWN_LABEL = "Unrecorded legacy India A2P sender"


def _table():
    import boto3
    return boto3.resource(
        "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")
    ).Table(LEGACY_SMS_TABLE)


def _encode_cursor(key: Dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(key, default=str).encode()).decode()


def _decode_cursor(token: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(base64.b64decode(token).decode())
    except Exception:  # noqa: BLE001 - a bad cursor is a bad request, not a fault
        return None


def normalize(item: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy row -> API shape, with the original provider preserved."""
    raw_provider = str(item.get("provider") or "").strip().lower()
    provider = raw_provider or _UNKNOWN_PROVIDER
    label = _PROVIDER_LABELS.get(raw_provider, _UNKNOWN_LABEL if not raw_provider
                                 else raw_provider)
    created = item.get("createdAt") or 0
    return {
        "messageId": item.get("messageId", ""),
        "contactId": item.get("contactId", ""),
        "phoneNumber": item.get("phoneNumber", ""),
        "content": item.get("content", ""),
        "direction": item.get("direction", ""),
        "status": item.get("status", ""),
        "messageType": item.get("messageType", ""),
        "senderId": item.get("senderId", ""),
        "entityId": item.get("entityId", ""),
        "dltTemplateId": item.get("dltTemplateId", ""),
        "providerMessageId": item.get("providerMessageId", ""),
        "apiVersion": item.get("apiVersion", ""),
        "errorDetails": item.get("errorDetails", ""),
        "createdAt": int(float(created or 0)),
        # Retained exactly as stored.
        "provider": provider,
        "providerLabel": label,
        # So a UI cannot present this as current traffic by accident.
        "isHistorical": True,
        "readOnly": True,
    }


def list_messages(*, limit: int = 100, cursor: str = "",
                  provider: str = "", status: str = "",
                  direction: str = "") -> Dict[str, Any]:
    """A page of legacy messages, newest first within the page.

    `provider` filters on the stored literal, which is how the retired Sinch SMS
    traffic is separated from the retired Airtel traffic - both live in this one
    table.

    Sorting is within the page only. The table has no time-ordered index, so this
    is a paginated scan; claiming a global ordering would be a lie about the data
    we actually fetched.
    """
    limit = max(1, min(int(limit or 100), 500))
    kwargs: Dict[str, Any] = {"Limit": limit}

    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded is None:
            return {"error": "invalid cursor", "errorCode": "INVALID_CURSOR"}
        kwargs["ExclusiveStartKey"] = decoded

    filters = []
    values: Dict[str, Any] = {}
    names: Dict[str, str] = {}
    if provider:
        filters.append("#p = :p")
        names["#p"] = "provider"
        values[":p"] = provider.strip().lower()
    if status:
        # `status` is a DynamoDB reserved word; the original implementation used
        # it unescaped in a FilterExpression, which fails at runtime.
        filters.append("#s = :s")
        names["#s"] = "status"
        values[":s"] = status
    if direction:
        filters.append("#d = :d")
        names["#d"] = "direction"
        values[":d"] = direction
    if filters:
        kwargs["FilterExpression"] = " AND ".join(filters)
        kwargs["ExpressionAttributeValues"] = values
        kwargs["ExpressionAttributeNames"] = names

    try:
        result = _table().scan(**kwargs)
    except Exception as exc:  # noqa: BLE001 - narrowed immediately below
        if retired_store.is_absent(exc):
            return _store_absent()
        raise
    items = result.get("Items", []) or []
    items.sort(key=lambda row: float(row.get("createdAt", 0) or 0), reverse=True)

    response: Dict[str, Any] = {
        "messages": [normalize(row) for row in items],
        "count": len(items),
        "readOnly": True,
        "sourceTable": LEGACY_SMS_TABLE,
        "note": ("Historical SMS from retired providers. Retained for audit and "
                 "DLT evidence. New SMS is sent only via AWS End User Messaging."),
        "pageOrderedOnly": True,
    }
    if result.get("LastEvaluatedKey"):
        response["nextToken"] = _encode_cursor(result["LastEvaluatedKey"])
    return response


def get_message(message_id: str) -> Optional[Dict[str, Any]]:
    if not message_id:
        return None
    try:
        item = _table().get_item(Key={"messageId": str(message_id)}).get("Item")
    except Exception as exc:  # noqa: BLE001 - narrowed immediately below
        if retired_store.is_absent(exc):
            # Indistinguishable from "no such message" to a caller looking up one
            # id, and that is the correct collapse: either way the record is not
            # retrievable. The list and counts paths report the absence, because
            # there the difference between "empty" and "gone" is the whole answer.
            return None
        raise
    return normalize(item) if item else None


def counts_by_provider() -> Dict[str, Any]:
    """Row counts per stored provider literal, for migration verification.

    Used to evidence that retiring a sender did not lose records: the counts here
    are the checksum a later deletion decision is checked against. A full scan is
    intentional - an approximate count cannot support that claim.
    """
    counts: Dict[str, int] = {}
    total = 0
    last_key = None
    table = _table()
    while True:
        kwargs: Dict[str, Any] = {
            "ProjectionExpression": "#p",
            "ExpressionAttributeNames": {"#p": "provider"},
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        try:
            result = table.scan(**kwargs)
        except Exception as exc:  # noqa: BLE001 - narrowed immediately below
            if retired_store.is_absent(exc):
                # Critically, do NOT return total=0 / exact=True here. This
                # function's output is the checksum a deletion decision is
                # justified against, and "zero rows, exactly" would read as
                # evidence that there was never anything to lose.
                return _store_absent()
            raise
        for row in result.get("Items", []) or []:
            key = str(row.get("provider") or "").strip().lower() or _UNKNOWN_PROVIDER
            counts[key] = counts.get(key, 0) + 1
            total += 1
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            break
    return {
        "total": total,
        "byProvider": dict(sorted(counts.items())),
        "sourceTable": LEGACY_SMS_TABLE,
        "exact": True,
    }


def purge(*, confirm_table: str) -> Dict[str, Any]:
    """Delete every legacy row. Requires the table name as a typed confirmation.

    This is the retention/right-to-erasure path, and it is destructive and
    irreversible. The caller must name the table it intends to empty, so that a
    misrouted request cannot clear history by arriving at the wrong endpoint.

    Authorisation is the caller's job. This function only makes the intent
    explicit; it does not decide who may act on it.
    """
    if confirm_table != LEGACY_SMS_TABLE:
        return {
            "error": ("Refusing to purge. Pass confirmTable exactly equal to the "
                      "table being emptied."),
            "errorCode": "CONFIRMATION_REQUIRED",
            "expected": LEGACY_SMS_TABLE,
        }
    table = _table()
    deleted = 0
    last_key = None
    while True:
        kwargs: Dict[str, Any] = {"ProjectionExpression": "messageId"}
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        try:
            result = table.scan(**kwargs)
        except Exception as exc:  # noqa: BLE001 - narrowed immediately below
            if retired_store.is_absent(exc):
                # Asked to erase something already erased. Not an error - the
                # caller's intent is satisfied - but it must not report a
                # deletion it did not perform.
                return {**_store_absent(), "deleted": 0, "alreadyAbsent": True}
            raise
        items = result.get("Items", []) or []
        if not items:
            break
        with table.batch_writer() as batch:
            for row in items:
                batch.delete_item(Key={"messageId": row["messageId"]})
                deleted += 1
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            break
    return {"deleted": deleted, "sourceTable": LEGACY_SMS_TABLE}
