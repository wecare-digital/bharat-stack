"""CRM use cases. Every one is safe to call twice.

Why that is the organising principle
------------------------------------
Leads arrive from webhooks - Meta Flow completions, ad clicks, inbound messages - and every
one of those is an at-least-once delivery. A CRM whose write path is only correct on first
delivery fills its funnel with duplicates, and duplicates are worse than missing rows here:
a missing lead gets noticed by a customer chasing a reply, while a duplicate silently
inflates the conversion denominator and nobody questions the report.

So each function below returns an outcome tag rather than raising on repetition:

    capture_lead     created | duplicate
    qualify_lead     transitioned | already
    convert_lead     converted | already_converted
    move_stage       moved | unchanged | refused

`already` and `duplicate` carry the stored row, so a caller can respond 200 with the real
record instead of 500 on a retry.

Ordering: the entity first, the timeline second
-----------------------------------------------
The state change is committed before its Activity is written, and an Activity failure does
not roll the change back. That is a deliberate trade. DynamoDB has no cross-table
transaction here without `TransactWriteItems`, and choosing the other order would let a
timeline claim a transition that did not happen - a strictly worse failure than a
transition with a missing timeline entry, which is visible by comparing the row to its
history and repairable after the fact.

Contact ids
-----------
Every function takes a contact id and resolves it through `contact_key`, so both spellings
work at the boundary. A CRM row always stores the canonical `id` value under `contactId`.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Mapping, Optional, Tuple

from .. import contact_key
from . import entities, keys, states, store


def _now() -> int:
    return int(time.time())


def _resolve_contact(contact_id: Optional[str],
                     contact: Optional[Mapping[str, Any]] = None) -> str:
    resolved = contact_key.resolve(contact, contact_id=contact_id)
    if not resolved:
        raise ValueError("a contact id is required")
    return resolved


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------

def ensure_default_pipeline(*, at: Optional[int] = None) -> Dict[str, Any]:
    """Create the default pipeline and its stages if absent. Idempotent.

    Safe to call on every cold start. All ids are name-derived, so a second call writes
    nothing and, importantly, does not reset `createdAt` on a pipeline in daily use.
    """
    now = at if at is not None else _now()
    bundle = entities.default_pipeline_rows(at=now)
    pipeline_result = store.put_pipeline(bundle["pipeline"])
    stage_results = [store.put_stage(stage) for stage in bundle["stages"]]
    return {
        "pipelineId": bundle["pipeline"]["pipelineId"],
        "pipeline": pipeline_result,
        "stages": stage_results,
        "created": pipeline_result == "created" or "created" in stage_results,
    }


def _target_pipeline(pipeline_id: Optional[str]) -> Dict[str, Any]:
    """The pipeline to use, explicit or default. Raises when neither resolves.

    Deliberately does not auto-provision. A missing pipeline during a webhook means
    provisioning has not run, and quietly creating one mid-request would attach live leads
    to a pipeline no admin has seen or configured.
    """
    if pipeline_id:
        pipeline = store.get_pipeline(pipeline_id)
        if not pipeline:
            raise ValueError(f"pipeline {pipeline_id} does not exist")
        return pipeline
    pipeline = store.default_pipeline()
    if not pipeline:
        raise ValueError("no default pipeline; run CRM provisioning first")
    return pipeline


# ---------------------------------------------------------------------------
# Lead capture
# ---------------------------------------------------------------------------

def capture_lead(*, contact_id: Optional[str] = None,
                 contact: Optional[Mapping[str, Any]] = None,
                 source: str,
                 source_ref: Optional[str] = None,
                 pipeline_id: Optional[str] = None,
                 attach_to_open_lead: bool = False,
                 actor: Optional[str] = None,
                 **fields: Any) -> Dict[str, Any]:
    """Capture an inbound lead. Replay-safe.

    Returns ``{'outcome': 'created'|'duplicate'|'attached', 'lead': row, ...}``.

    `attach_to_open_lead` is the business-duplicate policy, and it is **off by default**.
    Two enquiries are two leads unless the caller says otherwise, because silently folding
    the second into the first loses whatever the customer asked about the second time - and
    that loss is invisible, whereas an extra lead is visible and mergeable.

    When it is on and an open lead exists, no new lead is written; an Activity records the
    repeat contact against the existing one, so the second enquiry is still in the history.
    """
    resolved = _resolve_contact(contact_id, contact)
    pipeline = _target_pipeline(pipeline_id)
    target_pipeline_id = pipeline["pipelineId"]
    now = _now()

    if attach_to_open_lead:
        existing = store.find_open_lead(resolved, target_pipeline_id)
        if existing:
            note = entities.activity_row(
                kind=states.ACTIVITY_SYSTEM,
                contact_id=resolved,
                lead_id=existing["leadId"],
                summary=f"Repeat enquiry via {keys.normalize_source(source)}",
                reference=source_ref,
                actor=actor,
                system=True,
                metadata={"source": keys.normalize_source(source),
                          "sourceRef": source_ref},
                at=now,
            )
            store.append_activity(note)
            store.touch_last_activity(lead_id=existing["leadId"], at=now)
            return {"outcome": "attached", "lead": existing,
                    "pipelineId": target_pipeline_id}

    row = entities.lead_row(contact_id=resolved, pipeline_id=target_pipeline_id,
                            source=source, source_ref=source_ref, at=now, **fields)
    outcome, stored = store.capture_lead(row)

    if outcome == "created":
        store.append_activity(entities.state_change_activity(
            lead_id=stored["leadId"], contact_id=resolved,
            from_state=None, to_state=states.LEAD_NEW,
            actor=actor, reason=f"Captured from {stored['source']}", at=now))

    return {"outcome": outcome, "lead": stored, "pipelineId": target_pipeline_id}


# ---------------------------------------------------------------------------
# Lead progression
# ---------------------------------------------------------------------------

def transition_lead(*, lead_id: str, new_state: str,
                    actor: Optional[str] = None,
                    reason: Optional[str] = None,
                    expected_state: Optional[str] = None) -> Dict[str, Any]:
    """Move a lead. Returns ``{'outcome': 'transitioned'|'already'|'refused', ...}``.

    Reads the lead only to learn `expected_state` for the compare-and-swap; the decision is
    still made by the conditional write, so a concurrent change between the read and the
    write is refused rather than silently overwriting.

    A caller who already knows the state passes `expected_state` and skips the read.
    """
    if not keys.looks_like(keys.LEAD_PREFIX, lead_id):
        raise ValueError(f"not a lead id: {lead_id!r}")

    lead = store.get_lead(lead_id)
    if not lead:
        return {"outcome": "refused", "reason": "no such lead", "lead": None}

    current = expected_state or lead.get("state")
    if current == new_state:
        # Not an error. Two clicks, or a retried request.
        return {"outcome": "already", "lead": lead}

    if not states.lead_can_transition(current, new_state):
        return {"outcome": "refused",
                "reason": f"{current} -> {new_state} is not a legal lead move",
                "lead": lead}

    now = _now()
    extra: Dict[str, Any] = {}
    # First human touch is captured once and never moved, because response time is measured
    # from it and a later overwrite would make every slow response look instant.
    if current == states.LEAD_NEW and not lead.get("firstTouchedAt"):
        extra["firstTouchedAt"] = now
    if new_state == states.LEAD_DISQUALIFIED and reason:
        extra["disqualifiedReason"] = reason

    try:
        updated = store.transition_lead(lead_id, expected_state=current,
                                        new_state=new_state, at=now, extra=extra)
    except store.Refused as refusal:
        return {"outcome": "refused", "reason": str(refusal),
                "lead": store.get_lead(lead_id)}

    store.append_activity(entities.state_change_activity(
        lead_id=lead_id, contact_id=lead.get("contactId"),
        from_state=current, to_state=new_state, actor=actor, reason=reason, at=now))
    return {"outcome": "transitioned", "lead": updated}


def qualify_lead(*, lead_id: str, actor: Optional[str] = None,
                 reason: Optional[str] = None) -> Dict[str, Any]:
    """Shorthand for the QUALIFIED transition, which conversion requires."""
    return transition_lead(lead_id=lead_id, new_state=states.LEAD_QUALIFIED,
                           actor=actor, reason=reason)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def convert_lead(*, lead_id: str, title: Optional[str] = None,
                 amount_paise: Optional[int] = None,
                 stage_id: Optional[str] = None,
                 owner: Optional[str] = None,
                 expected_close_at: Optional[int] = None,
                 actor: Optional[str] = None) -> Dict[str, Any]:
    """Turn a qualified lead into an opportunity. Exactly once, under concurrency.

    Returns ``{'outcome': 'converted'|'already_converted'|'refused', ...}``.

    The order here is the interesting part. The opportunity is written **first**, then the
    lead is marked converted:

    * opportunity first, then a failed lead update: an orphan opportunity exists and the
      lead still reads QUALIFIED. Retrying converges, because the opportunity id is derived
      from the lead - the retry gets `exists` for the same row and then completes the lead
      update. Self-healing.
    * lead first, then a failed opportunity write: the lead claims CONVERTED and points at
      an opportunity that does not exist. Every screen following that link 404s, and no
      retry can fix it because the lead is now terminal and frozen.

    So the recoverable failure is chosen deliberately.
    """
    if not keys.looks_like(keys.LEAD_PREFIX, lead_id):
        raise ValueError(f"not a lead id: {lead_id!r}")

    lead = store.get_lead(lead_id)
    if not lead:
        return {"outcome": "refused", "reason": "no such lead"}

    if lead.get("opportunityId"):
        existing = store.get_opportunity(str(lead["opportunityId"]))
        return {"outcome": "already_converted", "lead": lead, "opportunity": existing}

    if not states.lead_is_convertible(lead.get("state")):
        return {"outcome": "refused",
                "reason": (f"lead is {lead.get('state')}; only "
                           f"{states.LEAD_QUALIFIED} converts"),
                "lead": lead}

    pipeline_id = str(lead.get("pipelineId") or "")
    stage = store.get_stage(stage_id) if stage_id else store.first_stage(pipeline_id)
    if not stage:
        return {"outcome": "refused",
                "reason": "pipeline has no open stage to place the opportunity in",
                "lead": lead}
    if stage.get("pipelineId") != pipeline_id:
        return {"outcome": "refused",
                "reason": "stage belongs to a different pipeline", "lead": lead}

    now = _now()
    opportunity = entities.opportunity_row(
        contact_id=str(lead["contactId"]),
        pipeline_id=pipeline_id,
        stage_id=str(stage["stageId"]),
        title=title or lead.get("subject") or f"Opportunity for {lead['contactId']}",
        opportunity_id=keys.opportunity_id_for_lead(lead_id),
        lead_id=lead_id,
        amount_paise=amount_paise if amount_paise is not None
        else lead.get("amountPaise"),
        owner=owner or lead.get("ownerId"),
        source=lead.get("source"),
        expected_close_at=expected_close_at,
        at=now,
    )
    _, stored_opportunity = store.create_opportunity(opportunity)

    try:
        updated_lead = store.mark_lead_converted(
            lead_id, opportunity_id=str(stored_opportunity["opportunityId"]), at=now)
    except store.Refused:
        # Another invocation claimed it. Both computed the same opportunity id, so the one
        # row is correct and shared - this is success, reported honestly as a repeat.
        return {"outcome": "already_converted",
                "lead": store.get_lead(lead_id),
                "opportunity": stored_opportunity}

    store.append_activity(entities.state_change_activity(
        lead_id=lead_id, contact_id=str(lead["contactId"]),
        from_state=states.LEAD_QUALIFIED, to_state=states.LEAD_CONVERTED,
        actor=actor, reason="Converted to opportunity", at=now))
    store.append_activity(entities.stage_change_activity(
        opportunity_id=str(stored_opportunity["opportunityId"]),
        contact_id=str(lead["contactId"]),
        from_stage=None, to_stage=str(stage["stageId"]),
        from_outcome=None, to_outcome=states.OPP_OPEN,
        actor=actor, reason="Created from lead", at=now))

    return {"outcome": "converted", "lead": updated_lead,
            "opportunity": stored_opportunity}


# ---------------------------------------------------------------------------
# Stage movement
# ---------------------------------------------------------------------------

def move_opportunity(*, opportunity_id: str, stage_id: str,
                     reopen: bool = False,
                     close_reason: Optional[str] = None,
                     actor: Optional[str] = None) -> Dict[str, Any]:
    """Move an opportunity to a stage, deriving the outcome from the stage's kind.

    Returns ``{'outcome': 'moved'|'unchanged'|'refused', ...}``.

    Dragging a card onto Won wins the deal. That is the behaviour every board has, and
    requiring a separate "now mark it won" step is how boards end up full of cards sitting
    in Won with outcome OPEN - counted on the board and absent from the revenue figure.
    """
    if not keys.looks_like(keys.OPPORTUNITY_PREFIX, opportunity_id):
        raise ValueError(f"not an opportunity id: {opportunity_id!r}")

    opportunity = store.get_opportunity(opportunity_id)
    if not opportunity:
        return {"outcome": "refused", "reason": "no such opportunity"}

    stage = store.get_stage(stage_id)
    legal, reason = states.stage_move_is_legal(
        opportunity_pipeline_id=str(opportunity.get("pipelineId") or ""),
        stage_pipeline_id=(stage or {}).get("pipelineId"),
        stage_kind=(stage or {}).get("kind"),
        current_outcome=opportunity.get("outcome"),
        reopen=reopen,
    )
    if not legal:
        return {"outcome": "refused", "reason": reason, "opportunity": opportunity}

    current_stage = str(opportunity.get("stageId") or "")
    current_outcome = str(opportunity.get("outcome") or states.OPP_OPEN)
    new_outcome = states.outcome_for_stage_kind(stage.get("kind"), current_outcome)

    if current_stage == stage_id and current_outcome == new_outcome:
        # A re-drop onto the same column. Returning early keeps `stageEnteredAt` intact -
        # bumping it would reset the dwell-time measurement that identifies a stuck deal.
        return {"outcome": "unchanged", "opportunity": opportunity}

    now = _now()
    try:
        updated = store.move_stage(
            opportunity_id,
            expected_stage_id=current_stage,
            expected_outcome=current_outcome,
            new_stage_id=stage_id,
            new_outcome=new_outcome,
            at=now,
            close_reason=close_reason,
        )
    except store.Refused as refusal:
        return {"outcome": "refused", "reason": str(refusal),
                "opportunity": store.get_opportunity(opportunity_id)}

    store.append_activity(entities.stage_change_activity(
        opportunity_id=opportunity_id,
        contact_id=opportunity.get("contactId"),
        from_stage=current_stage or None, to_stage=stage_id,
        from_outcome=current_outcome, to_outcome=new_outcome,
        actor=actor, reason=close_reason, at=now))

    return {"outcome": "moved", "opportunity": updated,
            "from": {"stageId": current_stage, "outcome": current_outcome},
            "to": {"stageId": stage_id, "outcome": new_outcome}}


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def log_activity(*, kind: str, contact_id: Optional[str] = None,
                 contact: Optional[Mapping[str, Any]] = None,
                 lead_id: Optional[str] = None,
                 opportunity_id: Optional[str] = None,
                 actor: Optional[str] = None,
                 **fields: Any) -> Dict[str, Any]:
    """Append a user activity. System-only kinds are refused here.

    The gate is `entities.activity_row`'s `system` flag, which this function never sets -
    so no route reachable by a user can forge a STAGE_CHANGE, and the timeline stays
    trustworthy as the audit trail for stage movement.
    """
    if not states.activity_kind_is_user_writable(kind):
        raise ValueError(f"{kind} is written by the system only")

    resolved = contact_key.resolve(contact, contact_id=contact_id) or None
    now = _now()
    row = entities.activity_row(kind=kind, contact_id=resolved, lead_id=lead_id,
                               opportunity_id=opportunity_id, actor=actor,
                               at=now, **fields)
    stored = store.append_activity(row)
    store.touch_last_activity(lead_id=lead_id, opportunity_id=opportunity_id, at=now)
    return {"outcome": "logged", "activity": stored}


def contact_360(*, contact_id: Optional[str] = None,
                contact: Optional[Mapping[str, Any]] = None,
                limit: int = 25) -> Dict[str, Any]:
    """Everything the CRM knows about one contact.

    Three queries, no scan. The `contactId` value is echoed back resolved, so a caller that
    passed the `contactId` alias can tell which canonical id was used - useful when a
    row's two identifiers have drifted and `contact_key` logged a mismatch.
    """
    resolved = _resolve_contact(contact_id, contact)
    return {
        "contactId": resolved,
        "leads": store.leads_for_contact(resolved, limit=limit),
        "opportunities": store.opportunities_for_contact(resolved, limit=limit),
        "activities": store.timeline(contact_id=resolved, limit=limit),
    }
