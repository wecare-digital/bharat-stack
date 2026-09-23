"""Row constructors. The only place a CRM row is shaped.

Why constructors rather than dicts at the call site
---------------------------------------------------
Every field that a query depends on has to be present and of the right type, and DynamoDB
will not tell you otherwise - it accepts a row missing its GSI key and simply omits it
from the index. The row is stored, the write "succeeds", and the record is invisible to
every board and every report. Nothing raises, then or later.

That failure mode is why these are functions. A lead built here always carries
`contactId`, `pipelineId`, `state` and `createdAt`, because the leads-by-contact and
leads-by-state indexes are defined on them.

Money is integer paise
----------------------
`amountPaise`, matching `FlowSubmission.paymentAmount` which is already paise, and
`Payment`. Floats are not used for currency anywhere in this domain: `0.1 + 0.2` is
famously not `0.3`, and a forecast that sums a few thousand float rupees drifts visibly.
The field name carries the unit so no caller has to remember it - `amount` alone is how
a rupee value ends up in a paise column, silently off by 100x.

Timestamps are integer epoch seconds
------------------------------------
Matching `FlowSubmission`, `PstnCall` and the notification domain. Not ISO strings: they
sort lexicographically only while the format is identical, and a single row written with
a timezone offset breaks range queries on the sort key in a way that is very hard to see.

`None` is stripped, `''` is not
-------------------------------
DynamoDB rejects empty *sets* but accepts empty strings, and the two mean different
things here: absent (never captured) versus captured-as-blank. Stripping `None` keeps rows
small and lets `attribute_not_exists` work as a real signal; keeping `''` preserves the
distinction where a caller deliberately blanked a field.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Mapping, Optional

from . import keys, states

#: Leads carry no TTL. A CRM record is the business history - the funnel, the win rate,
#: the source attribution - and expiring it would delete the only evidence of what
#: marketing spend produced. Contrast `MessagesTable` (30 days) and `FlowDraft` (7 days),
#: which hold transport detail rather than outcomes.
NO_TTL = None


def _now() -> int:
    return int(time.time())


def _compact(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Drop `None` values only. See the module docstring on why `''` survives."""
    return {k: v for k, v in row.items() if v is not None}


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# Pipeline and Stage - configuration
# ---------------------------------------------------------------------------

def pipeline_row(*, name: str, description: Optional[str] = None,
                 is_default: bool = False, active: bool = True,
                 at: Optional[int] = None) -> Dict[str, Any]:
    """A pipeline. Id is derived from the name so re-provisioning is idempotent."""
    label = (name or "").strip()
    if not label:
        raise ValueError("pipeline name is required")
    now = at if at is not None else _now()
    return _compact({
        "pipelineId": keys.pipeline_id(label),
        "name": label,
        "description": _clean(description),
        # Stored as a string, not a boolean, because it is a GSI partition key and
        # DynamoDB cannot index a boolean attribute. `"true"`/`"false"` keeps the
        # single-default lookup a one-key query instead of a scan with a filter.
        "isDefault": "true" if is_default else "false",
        "active": bool(active),
        "createdAt": now,
        "updatedAt": now,
    })


def stage_row(*, pipeline_id: str, name: str, order: int,
              kind: str = states.STAGE_OPEN,
              probability: Optional[int] = None,
              at: Optional[int] = None) -> Dict[str, Any]:
    """A stage within a pipeline.

    `order` is display position only. Opportunities reference `stageId`, never `order`, so
    reordering a board is a cheap metadata update rather than a rewrite of every live
    opportunity - and an opportunity cannot end up in the wrong stage because someone
    inserted a new one in the middle.

    `probability` is a forecast weight in whole percent. Optional, because an honest
    "unknown" is more useful than a default 50 that quietly becomes half the pipeline
    value in every report.
    """
    if not pipeline_id:
        raise ValueError("pipeline id is required")
    label = (name or "").strip()
    if not label:
        raise ValueError("stage name is required")
    if kind not in states.STAGE_KINDS:
        raise ValueError(f"stage kind must be one of {states.STAGE_KINDS}, got {kind!r}")
    if probability is not None and not 0 <= int(probability) <= 100:
        raise ValueError("probability must be whole percent between 0 and 100")
    now = at if at is not None else _now()
    return _compact({
        "stageId": keys.stage_id(pipeline_id, label),
        "pipelineId": pipeline_id,
        "name": label,
        "kind": kind,
        "displayOrder": int(order),
        "probability": None if probability is None else int(probability),
        "createdAt": now,
        "updatedAt": now,
    })


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------

def lead_row(*, contact_id: str, pipeline_id: str, source: str,
             source_ref: Optional[str] = None,
             phone: Optional[str] = None,
             name: Optional[str] = None,
             email: Optional[str] = None,
             subject: Optional[str] = None,
             detail: Optional[str] = None,
             owner: Optional[str] = None,
             channel: Optional[str] = None,
             campaign: Optional[str] = None,
             amount_paise: Optional[int] = None,
             metadata: Optional[Mapping[str, Any]] = None,
             at: Optional[int] = None) -> Dict[str, Any]:
    """A captured lead, always in state `NEW`.

    Creating a lead in any other state is refused by `states.lead_can_transition(None, x)`,
    so an importer cannot fabricate a `CONVERTED` lead with no opportunity behind it - a
    row that inflates the conversion rate and links to nothing.

    `sourceRef` is stored as well as hashed into the id. The hash makes replay idempotent;
    the stored value is what lets a human answer "which Flow submission was this?", which
    a digest cannot.
    """
    if not contact_id:
        raise ValueError("contact id is required")
    if not pipeline_id:
        raise ValueError("pipeline id is required")
    normalized_source = keys.normalize_source(source)
    now = at if at is not None else _now()
    if amount_paise is not None and int(amount_paise) < 0:
        raise ValueError("amountPaise cannot be negative")

    return _compact({
        "leadId": keys.lead_id(normalized_source, source_ref),
        "contactId": contact_id,
        "pipelineId": pipeline_id,
        "state": states.LEAD_NEW,
        "source": normalized_source,
        "sourceRef": _clean(source_ref),
        # Grouping key for "already has an open lead here?". A query dimension, not part
        # of identity - see keys.open_lead_index_key.
        "contactPipelineKey": keys.open_lead_index_key(contact_id, pipeline_id),
        "phone": _clean(phone),
        "name": _clean(name),
        "email": _clean(email),
        "subject": _clean(subject),
        "detail": _clean(detail),
        "ownerId": _clean(owner),
        "channel": _clean(channel),
        "campaign": _clean(campaign),
        "amountPaise": None if amount_paise is None else int(amount_paise),
        "metadata": dict(metadata) if metadata else None,
        # Set on conversion. Its absence is what `convert_lead`'s conditional write tests,
        # so it must never be initialised to a placeholder.
        "opportunityId": None,
        "convertedAt": None,
        "disqualifiedReason": None,
        "createdAt": now,
        "updatedAt": now,
        # Response-time measurement needs the moment of first human contact, which is not
        # the same as createdAt and cannot be reconstructed later.
        "firstTouchedAt": None,
        "lastActivityAt": None,
    })


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------

def opportunity_row(*, contact_id: str, pipeline_id: str, stage_id: str,
                    title: str,
                    opportunity_id: Optional[str] = None,
                    lead_id: Optional[str] = None,
                    amount_paise: Optional[int] = None,
                    currency: str = "INR",
                    owner: Optional[str] = None,
                    source: Optional[str] = None,
                    expected_close_at: Optional[int] = None,
                    metadata: Optional[Mapping[str, Any]] = None,
                    at: Optional[int] = None) -> Dict[str, Any]:
    """An opportunity, always created `OPEN`.

    `stageEnteredAt` is separate from `createdAt` because stage *dwell time* is the number
    that identifies a stuck funnel, and it cannot be derived from row age once the
    opportunity has moved even once.
    """
    if not contact_id:
        raise ValueError("contact id is required")
    if not pipeline_id:
        raise ValueError("pipeline id is required")
    if not stage_id:
        raise ValueError("stage id is required")
    label = (title or "").strip()
    if not label:
        raise ValueError("opportunity title is required")
    if amount_paise is not None and int(amount_paise) < 0:
        raise ValueError("amountPaise cannot be negative")
    now = at if at is not None else _now()

    return _compact({
        "opportunityId": opportunity_id or keys.opportunity_id(),
        "contactId": contact_id,
        "pipelineId": pipeline_id,
        "stageId": stage_id,
        "title": label,
        "outcome": states.OPP_OPEN,
        "leadId": _clean(lead_id),
        "amountPaise": None if amount_paise is None else int(amount_paise),
        "currency": (currency or "INR").upper(),
        "ownerId": _clean(owner),
        "source": _clean(source),
        "expectedCloseAt": expected_close_at,
        "metadata": dict(metadata) if metadata else None,
        "createdAt": now,
        "updatedAt": now,
        "stageEnteredAt": now,
        "closedAt": None,
        "closeReason": None,
        "lastActivityAt": None,
    })


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

def activity_row(*, kind: str, contact_id: Optional[str] = None,
                 lead_id: Optional[str] = None,
                 opportunity_id: Optional[str] = None,
                 summary: Optional[str] = None,
                 body: Optional[str] = None,
                 actor: Optional[str] = None,
                 channel: Optional[str] = None,
                 reference: Optional[str] = None,
                 due_at: Optional[int] = None,
                 system: bool = False,
                 metadata: Optional[Mapping[str, Any]] = None,
                 at: Optional[int] = None) -> Dict[str, Any]:
    """One append-only timeline entry.

    Requires at least one subject. An activity attached to nothing is unreachable from
    every screen - it is written, it is billed for, and no query will ever return it.

    `system` gates the three system-only kinds. A user-supplied `STAGE_CHANGE` could claim
    a transition that never happened, which makes the timeline useless as the audit trail
    for stage movement - its main job.
    """
    if not states.activity_kind_is_valid(kind):
        raise ValueError(f"unknown activity kind {kind!r}")
    if kind in states.ACTIVITY_SYSTEM_ONLY and not system:
        raise ValueError(f"{kind} is written by the system only")
    if not (contact_id or lead_id or opportunity_id):
        raise ValueError("an activity needs at least one of contact, lead or opportunity")
    if due_at is not None and kind not in states.ACTIVITY_COMPLETABLE:
        raise ValueError(f"{kind} cannot carry a due date; only "
                         f"{sorted(states.ACTIVITY_COMPLETABLE)} can")
    now = at if at is not None else _now()

    return _compact({
        "activityId": keys.activity_id(at=now),
        "kind": kind,
        "contactId": _clean(contact_id),
        "leadId": _clean(lead_id),
        "opportunityId": _clean(opportunity_id),
        "summary": _clean(summary),
        "body": _clean(body),
        "actorId": _clean(actor),
        "channel": _clean(channel),
        # A provider id - wamid, call id, payment id - so a timeline entry can be traced
        # back to the transport record that caused it.
        "reference": _clean(reference),
        "isSystem": bool(system),
        "dueAt": due_at,
        "completedAt": None,
        "metadata": dict(metadata) if metadata else None,
        # `at` rather than `createdAt`: this is the sort key of the timeline index, and the
        # shorter name is what `store.py` ranges on.
        "at": now,
        "createdAt": now,
    })


def stage_change_activity(*, opportunity_id: str, contact_id: Optional[str],
                          from_stage: Optional[str], to_stage: str,
                          from_outcome: Optional[str], to_outcome: str,
                          actor: Optional[str] = None,
                          reason: Optional[str] = None,
                          at: Optional[int] = None) -> Dict[str, Any]:
    """The audit entry for a stage move. Written by the service, never by a caller."""
    return activity_row(
        kind=states.ACTIVITY_STAGE_CHANGE,
        contact_id=contact_id,
        opportunity_id=opportunity_id,
        summary=f"Stage: {from_stage or '(new)'} -> {to_stage}",
        body=reason,
        actor=actor,
        system=True,
        metadata={
            "fromStageId": from_stage,
            "toStageId": to_stage,
            "fromOutcome": from_outcome,
            "toOutcome": to_outcome,
        },
        at=at,
    )


def state_change_activity(*, lead_id: str, contact_id: Optional[str],
                          from_state: Optional[str], to_state: str,
                          actor: Optional[str] = None,
                          reason: Optional[str] = None,
                          at: Optional[int] = None) -> Dict[str, Any]:
    """The audit entry for a lead state move."""
    return activity_row(
        kind=states.ACTIVITY_STATE_CHANGE,
        contact_id=contact_id,
        lead_id=lead_id,
        summary=f"Lead: {from_state or '(new)'} -> {to_state}",
        body=reason,
        actor=actor,
        system=True,
        metadata={"fromState": from_state, "toState": to_state},
        at=at,
    )


# ---------------------------------------------------------------------------
# Default pipeline
# ---------------------------------------------------------------------------

#: The default pipeline's stages. Ordered, with the two closed stages last so a board
#: renders left to right in the order a deal actually travels.
#:
#: Probabilities are deliberately absent from `New` and present from `Contacted` onward:
#: an untouched lead has no meaningful forecast weight, and giving it one puts raw inbound
#: volume into the revenue projection.
DEFAULT_PIPELINE_NAME = "Sales"

DEFAULT_STAGES = (
    ("New", states.STAGE_OPEN, None),
    ("Contacted", states.STAGE_OPEN, 10),
    ("Qualified", states.STAGE_OPEN, 30),
    ("Proposal", states.STAGE_OPEN, 60),
    ("Negotiation", states.STAGE_OPEN, 80),
    ("Won", states.STAGE_WON, 100),
    ("Lost", states.STAGE_LOST, 0),
)


def default_pipeline_rows(at: Optional[int] = None) -> Dict[str, Any]:
    """`{'pipeline': row, 'stages': [rows]}` for the out-of-the-box pipeline.

    Every id here is derived from the names, so running provisioning twice produces
    byte-identical rows rather than a second pipeline nobody notices until the board
    splits in half.
    """
    now = at if at is not None else _now()
    pipeline = pipeline_row(name=DEFAULT_PIPELINE_NAME, is_default=True,
                            description="Default sales pipeline", at=now)
    stages: List[Dict[str, Any]] = [
        stage_row(pipeline_id=pipeline["pipelineId"], name=name, order=index * 10,
                  kind=kind, probability=probability, at=now)
        for index, (name, kind, probability) in enumerate(DEFAULT_STAGES)
    ]
    return {"pipeline": pipeline, "stages": stages}
