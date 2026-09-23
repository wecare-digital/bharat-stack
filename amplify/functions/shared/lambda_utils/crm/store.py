"""DynamoDB access for the CRM domain. The guards are ConditionExpressions, not reads.

The rule this module follows
----------------------------
Every invariant that two concurrent invocations could break is expressed as a
**ConditionExpression on the write**, never as a read followed by a write. This fleet runs
~58 Lambdas behind an HTTP API with no concurrency limit, and a Flow webhook plus an SQS
redrive plus a user clicking twice is an ordinary Tuesday. A read-then-write here produces
two opportunities for one lead, and the duplicate is not visibly wrong on either row - the
funnel just quietly counts the deal twice.

So:

    capture_lead       attribute_not_exists(leadId)                   replay is a no-op
    convert_lead       attribute_not_exists(opportunityId)            converts once
    move_stage         stageId = :expected AND outcome = :expected    lost update refused
    transition_lead    state = :expected                              lost update refused

`stageId = :expected` is a compare-and-swap, not a presence check. Two users dragging the
same card to different stages both succeed under a presence check, and the second silently
wins with no record that the first happened. Under CAS the loser gets `Refused` and can
re-read and retry, and both moves appear in the timeline.

What is *not* guarded here
--------------------------
Business-level duplicate leads. `find_open_lead` reports them; it does not prevent them.
That is deliberate - see `keys` on why person-level dedup is a read-time policy rather
than part of a row's identity.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    import boto3
    from boto3.dynamodb.conditions import Key
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - boto3 is present in every Lambda runtime
    boto3 = None
    Key = None
    ClientError = Exception

from . import keys as crm_keys
from . import states

PREFIX = "stack-wecare-digital"

# Written out in full rather than built with an f-string on purpose.
# `scripts/audit_data_model_drift.py` greps source for literal table names to reconcile
# code against the account, and an f-string default is invisible to it - the table shows up
# as LIVE_BUT_UNREFERENCED, which is a false positive. An audit that reports things that
# are fine gets ignored, and then it stops catching the things that are not.
PIPELINES_TABLE = os.environ.get("CRM_PIPELINES_TABLE",
                                 "stack-wecare-digital-CrmPipelines")
STAGES_TABLE = os.environ.get("CRM_STAGES_TABLE", "stack-wecare-digital-CrmStages")
LEADS_TABLE = os.environ.get("CRM_LEADS_TABLE", "stack-wecare-digital-CrmLeads")
OPPORTUNITIES_TABLE = os.environ.get("CRM_OPPORTUNITIES_TABLE",
                                     "stack-wecare-digital-CrmOpportunities")
ACTIVITIES_TABLE = os.environ.get("CRM_ACTIVITIES_TABLE",
                                  "stack-wecare-digital-CrmActivities")


class Refused(Exception):
    """A conditional write was rejected.

    Not an error in itself. It is the mechanism working: something else got there first,
    or the caller's view of the row is stale. The service layer decides whether that means
    "already done, return the existing row" or "re-read and retry".
    """

    def __init__(self, message: str, *, reason: str = "condition_failed") -> None:
        super().__init__(message)
        self.reason = reason


def _resource():
    if boto3 is None:  # pragma: no cover
        raise RuntimeError("boto3 unavailable")
    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION",
                                                                 "us-east-1"))


def _table(name: str):
    return _resource().Table(name)


def _is_condition_failure(exc: Exception) -> bool:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code")
    return code == "ConditionalCheckFailedException"


# ---------------------------------------------------------------------------
# Pipelines and stages
# ---------------------------------------------------------------------------

def put_pipeline(row: Mapping[str, Any], *, overwrite: bool = False) -> str:
    """Write a pipeline. `created` or `exists`.

    Idempotent by default: because `pipelineId` is derived from the name, re-running
    provisioning writes the same id, and `attribute_not_exists` turns that into a no-op
    rather than resetting `createdAt` on a pipeline that has been in use for months.
    """
    kwargs: Dict[str, Any] = {"Item": dict(row)}
    if not overwrite:
        kwargs["ConditionExpression"] = "attribute_not_exists(pipelineId)"
    try:
        _table(PIPELINES_TABLE).put_item(**kwargs)
        return "created"
    except ClientError as exc:
        if _is_condition_failure(exc):
            return "exists"
        raise


def put_stage(row: Mapping[str, Any], *, overwrite: bool = False) -> str:
    kwargs: Dict[str, Any] = {"Item": dict(row)}
    if not overwrite:
        kwargs["ConditionExpression"] = "attribute_not_exists(stageId)"
    try:
        _table(STAGES_TABLE).put_item(**kwargs)
        return "created"
    except ClientError as exc:
        if _is_condition_failure(exc):
            return "exists"
        raise


def get_pipeline(pipeline_id: str) -> Optional[Dict[str, Any]]:
    if not pipeline_id:
        return None
    return _table(PIPELINES_TABLE).get_item(Key={"pipelineId": pipeline_id}).get("Item")


def get_stage(stage_id: str) -> Optional[Dict[str, Any]]:
    if not stage_id:
        return None
    return _table(STAGES_TABLE).get_item(Key={"stageId": stage_id}).get("Item")


def list_stages(pipeline_id: str) -> List[Dict[str, Any]]:
    """A pipeline's stages in display order.

    Sorted on the index rather than in Python, because `displayOrder` is the GSI range key
    - the board renders in one query with no client-side sort to get wrong.
    """
    if not pipeline_id:
        return []
    resp = _table(STAGES_TABLE).query(
        IndexName="pipelineId-displayOrder-index",
        KeyConditionExpression=Key("pipelineId").eq(pipeline_id),
    )
    return list(resp.get("Items", []))


def default_pipeline() -> Optional[Dict[str, Any]]:
    """The pipeline flagged default, or `None`.

    A one-key query on a sparse-ish index rather than a scan. With 70 tables already in
    this account, a scan-per-request habit is how a read path becomes the cost line
    nobody can explain.
    """
    resp = _table(PIPELINES_TABLE).query(
        IndexName="isDefault-index",
        KeyConditionExpression=Key("isDefault").eq("true"),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def first_stage(pipeline_id: str) -> Optional[Dict[str, Any]]:
    """The entry stage of a pipeline: lowest display order among OPEN stages.

    Filters to OPEN deliberately. A pipeline whose lowest-ordered stage was a closed one -
    possible if someone reorders a board - would otherwise place every new opportunity
    directly into Won.
    """
    for stage in list_stages(pipeline_id):
        if stage.get("kind") == states.STAGE_OPEN:
            return stage
    return None


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def capture_lead(row: Mapping[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Insert a lead if its id is new. `('created'|'duplicate', row)`.

    On `duplicate` the stored row is returned, not the one passed in. A replay must see
    what is actually recorded - including any state movement since the first delivery -
    rather than the NEW row it just constructed, which would report a lead as untouched
    when a human has already worked it.
    """
    lead_id = row.get("leadId")
    if not crm_keys.looks_like(crm_keys.LEAD_PREFIX, lead_id):
        raise ValueError(f"not a lead id: {lead_id!r}")
    try:
        _table(LEADS_TABLE).put_item(
            Item=dict(row),
            ConditionExpression="attribute_not_exists(leadId)",
        )
        return "created", dict(row)
    except ClientError as exc:
        if _is_condition_failure(exc):
            existing = get_lead(str(lead_id))
            return "duplicate", existing or dict(row)
        raise


def get_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    if not lead_id:
        return None
    return _table(LEADS_TABLE).get_item(Key={"leadId": lead_id}).get("Item")


def transition_lead(lead_id: str, *, expected_state: str, new_state: str,
                    at: int, extra: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Compare-and-swap a lead's state. Raises `Refused` when the state has moved.

    `expected_state` is required rather than optional. An unconditional state write is how
    a "disqualify" click lands on a lead that a colleague converted two seconds earlier,
    producing a DISQUALIFIED lead pointing at a live opportunity.
    """
    if not states.lead_can_transition(expected_state, new_state):
        raise ValueError(f"{expected_state} -> {new_state} is not a legal lead move")

    sets = ["#s = :new", "updatedAt = :at"]
    names = {"#s": "state"}
    values: Dict[str, Any] = {":new": new_state, ":expected": expected_state, ":at": at}

    for index, (field, value) in enumerate(sorted((extra or {}).items())):
        if value is None:
            continue
        placeholder = f":x{index}"
        sets.append(f"#f{index} = {placeholder}")
        names[f"#f{index}"] = field
        values[placeholder] = value

    try:
        resp = _table(LEADS_TABLE).update_item(
            Key={"leadId": lead_id},
            UpdateExpression="SET " + ", ".join(sets),
            ConditionExpression="attribute_exists(leadId) AND #s = :expected",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return resp.get("Attributes", {})
    except ClientError as exc:
        if _is_condition_failure(exc):
            raise Refused(
                f"lead {lead_id} is no longer in {expected_state}",
                reason="stale_state") from exc
        raise


def mark_lead_converted(lead_id: str, *, opportunity_id: str, at: int) -> Dict[str, Any]:
    """Claim the conversion. Raises `Refused` if the lead already converted.

    Two conditions, and both are load-bearing. `attribute_not_exists(opportunityId)` makes
    conversion once-only without a read. `state = QUALIFIED` stops a disqualified lead
    being converted by a request that was in flight when it was closed.
    """
    try:
        resp = _table(LEADS_TABLE).update_item(
            Key={"leadId": lead_id},
            UpdateExpression=("SET #s = :converted, opportunityId = :opp, "
                              "convertedAt = :at, updatedAt = :at"),
            ConditionExpression=("attribute_exists(leadId) "
                                 "AND attribute_not_exists(opportunityId) "
                                 "AND #s = :qualified"),
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={
                ":converted": states.LEAD_CONVERTED,
                ":qualified": states.LEAD_QUALIFIED,
                ":opp": opportunity_id,
                ":at": at,
            },
            ReturnValues="ALL_NEW",
        )
        return resp.get("Attributes", {})
    except ClientError as exc:
        if _is_condition_failure(exc):
            raise Refused(f"lead {lead_id} is not a qualified, unconverted lead",
                          reason="already_converted") from exc
        raise


def find_open_lead(contact_id: str, pipeline_id: str) -> Optional[Dict[str, Any]]:
    """An existing non-terminal lead for this contact in this pipeline, if any.

    Reports; does not enforce. The caller decides whether a second enquiry should attach to
    the open lead or start a new one - a decision that depends on the business, not on the
    data model, which is why it is not a uniqueness constraint.
    """
    if not (contact_id and pipeline_id):
        return None
    resp = _table(LEADS_TABLE).query(
        IndexName="contactPipelineKey-index",
        KeyConditionExpression=Key("contactPipelineKey").eq(
            crm_keys.open_lead_index_key(contact_id, pipeline_id)),
    )
    for item in resp.get("Items", []):
        if not states.lead_is_terminal(item.get("state")):
            return item
    return None


def leads_for_contact(contact_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    if not contact_id:
        return []
    resp = _table(LEADS_TABLE).query(
        IndexName="contactId-createdAt-index",
        KeyConditionExpression=Key("contactId").eq(contact_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    return list(resp.get("Items", []))


def leads_by_state(state: str, *, limit: int = 100) -> List[Dict[str, Any]]:
    """Leads in one state, newest first. The queue view."""
    resp = _table(LEADS_TABLE).query(
        IndexName="state-createdAt-index",
        KeyConditionExpression=Key("state").eq(state),
        ScanIndexForward=False,
        Limit=limit,
    )
    return list(resp.get("Items", []))


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

def create_opportunity(row: Mapping[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Insert an opportunity if its id is new. `('created'|'exists', row)`.

    For a lead conversion the id is derived from the lead, so a concurrent second
    conversion lands here and gets `exists` with the first opportunity - which is the
    correct answer, not an error.
    """
    opportunity_id = row.get("opportunityId")
    if not crm_keys.looks_like(crm_keys.OPPORTUNITY_PREFIX, opportunity_id):
        raise ValueError(f"not an opportunity id: {opportunity_id!r}")
    try:
        _table(OPPORTUNITIES_TABLE).put_item(
            Item=dict(row),
            ConditionExpression="attribute_not_exists(opportunityId)",
        )
        return "created", dict(row)
    except ClientError as exc:
        if _is_condition_failure(exc):
            existing = get_opportunity(str(opportunity_id))
            return "exists", existing or dict(row)
        raise


def get_opportunity(opportunity_id: str) -> Optional[Dict[str, Any]]:
    if not opportunity_id:
        return None
    return _table(OPPORTUNITIES_TABLE).get_item(
        Key={"opportunityId": opportunity_id}).get("Item")


def move_stage(opportunity_id: str, *, expected_stage_id: str, expected_outcome: str,
               new_stage_id: str, new_outcome: str, at: int,
               close_reason: Optional[str] = None) -> Dict[str, Any]:
    """Compare-and-swap an opportunity's stage and outcome together.

    Both are swapped in one update because they must agree: an opportunity in a Won stage
    with outcome OPEN appears on the board *and* in the revenue figure, and no single
    reader can tell which is the mistake. Two updates cannot be made atomic here, so one
    update it is.

    `closedAt` is set when moving into a terminal outcome and removed when reopening,
    because a stale `closedAt` on a live deal corrupts every cycle-time measurement.
    """
    sets = ["stageId = :stage", "outcome = :outcome", "updatedAt = :at",
            "stageEnteredAt = :at"]
    removes: List[str] = []
    values: Dict[str, Any] = {
        ":stage": new_stage_id,
        ":outcome": new_outcome,
        ":at": at,
        ":expectedStage": expected_stage_id,
        ":expectedOutcome": expected_outcome,
    }

    if new_outcome in states.OPPORTUNITY_TERMINAL:
        sets.append("closedAt = :at")
        if close_reason:
            sets.append("closeReason = :reason")
            values[":reason"] = close_reason
    else:
        removes.extend(["closedAt", "closeReason"])

    expression = "SET " + ", ".join(sets)
    if removes:
        expression += " REMOVE " + ", ".join(removes)

    try:
        resp = _table(OPPORTUNITIES_TABLE).update_item(
            Key={"opportunityId": opportunity_id},
            UpdateExpression=expression,
            ConditionExpression=("attribute_exists(opportunityId) "
                                 "AND stageId = :expectedStage "
                                 "AND outcome = :expectedOutcome"),
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return resp.get("Attributes", {})
    except ClientError as exc:
        if _is_condition_failure(exc):
            raise Refused(
                f"opportunity {opportunity_id} has moved since it was read",
                reason="stale_stage") from exc
        raise


def opportunities_for_contact(contact_id: str, *,
                              limit: int = 50) -> List[Dict[str, Any]]:
    if not contact_id:
        return []
    resp = _table(OPPORTUNITIES_TABLE).query(
        IndexName="contactId-createdAt-index",
        KeyConditionExpression=Key("contactId").eq(contact_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    return list(resp.get("Items", []))


def opportunities_in_stage(stage_id: str, *, limit: int = 200) -> List[Dict[str, Any]]:
    """One board column. Paged by the caller rather than scanned."""
    if not stage_id:
        return []
    resp = _table(OPPORTUNITIES_TABLE).query(
        IndexName="stageId-createdAt-index",
        KeyConditionExpression=Key("stageId").eq(stage_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    return list(resp.get("Items", []))


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

def append_activity(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Append a timeline entry.

    `attribute_not_exists(activityId)` even though ids are random: it costs nothing and
    turns the one-in-astronomical collision into a visible error rather than a silently
    overwritten history entry. The timeline is append-only, so an overwrite here is
    unrecoverable.
    """
    try:
        _table(ACTIVITIES_TABLE).put_item(
            Item=dict(row),
            ConditionExpression="attribute_not_exists(activityId)",
        )
        return dict(row)
    except ClientError as exc:
        if _is_condition_failure(exc):
            raise Refused("activity id already exists", reason="duplicate") from exc
        raise


def timeline(*, contact_id: Optional[str] = None, lead_id: Optional[str] = None,
             opportunity_id: Optional[str] = None,
             limit: int = 50) -> List[Dict[str, Any]]:
    """Newest-first activities for exactly one subject.

    Exactly one, refused otherwise. A combined timeline needs a merge across three indexes
    with its own ordering rules, and silently answering with just one of them would look
    like a working combined view while omitting most of it.
    """
    provided = [(name, value) for name, value in (
        ("contactId-at-index", contact_id),
        ("leadId-at-index", lead_id),
        ("opportunityId-at-index", opportunity_id),
    ) if value]
    if len(provided) != 1:
        raise ValueError("timeline takes exactly one of contact, lead or opportunity")
    index_name, value = provided[0]
    field = index_name.split("-")[0]
    resp = _table(ACTIVITIES_TABLE).query(
        IndexName=index_name,
        KeyConditionExpression=Key(field).eq(value),
        ScanIndexForward=False,
        Limit=limit,
    )
    return list(resp.get("Items", []))


def complete_activity(activity_id: str, *, at: int) -> Dict[str, Any]:
    """Mark a task done. Refused if it is already done, or is not a task.

    `attribute_not_exists(completedAt)` keeps the first completion time, which is the one
    that matters for an SLA. Re-completing would move the timestamp forward and make a
    late task look punctual.
    """
    try:
        resp = _table(ACTIVITIES_TABLE).update_item(
            Key={"activityId": activity_id},
            UpdateExpression="SET completedAt = :at",
            ConditionExpression=("attribute_exists(activityId) "
                                 "AND attribute_not_exists(completedAt) "
                                 "AND kind = :task"),
            ExpressionAttributeValues={":at": at, ":task": states.ACTIVITY_TASK},
            ReturnValues="ALL_NEW",
        )
        return resp.get("Attributes", {})
    except ClientError as exc:
        if _is_condition_failure(exc):
            raise Refused(f"activity {activity_id} is not an open task",
                          reason="not_open_task") from exc
        raise


def touch_last_activity(*, lead_id: Optional[str] = None,
                        opportunity_id: Optional[str] = None, at: int) -> None:
    """Best-effort `lastActivityAt` bump.

    Swallows failure on purpose. This is a convenience denormalisation for sorting a list
    by recency; the activity row itself is already committed, and failing the caller's
    request because a sort hint could not be updated would trade a real write for a
    cosmetic one.
    """
    try:
        if lead_id:
            _table(LEADS_TABLE).update_item(
                Key={"leadId": lead_id},
                UpdateExpression="SET lastActivityAt = :at",
                ConditionExpression="attribute_exists(leadId)",
                ExpressionAttributeValues={":at": at},
            )
        if opportunity_id:
            _table(OPPORTUNITIES_TABLE).update_item(
                Key={"opportunityId": opportunity_id},
                UpdateExpression="SET lastActivityAt = :at",
                ConditionExpression="attribute_exists(opportunityId)",
                ExpressionAttributeValues={":at": at},
            )
    except ClientError:
        return
