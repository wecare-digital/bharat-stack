"""Explicit CRM entities: Lead, Pipeline, Stage, Opportunity, Activity.

Why this exists at all
----------------------
Measured against the live account on 2026-09-22: **70 DynamoDB tables, and not one of
them is a CRM entity.** No Lead, no Pipeline, no Stage, no Opportunity, no Activity -
neither deployed nor declared in `amplify/data/resource.ts`, which holds 63 models.

So the sales pipeline was not modelled anywhere. What existed instead was five tables
that each carry a *fragment* of it and cannot be joined:

    FlowSubmission        an inbound form, with `status: open|in_progress|resolved`
    AdClickAttribution    an ad click mapped to a phone number
    SubmitRequest         a service request with its own status vocabulary
    Order / Invoice       the commercial outcome, once it exists
    ConversationMeta      per-conversation flags

Every one of those is a *record of an event*. None of them answers "who is in the
funnel, at what stage, worth how much, and what happened last" - which is the question
a CRM exists to answer. Answering it by scanning FlowSubmission and inferring intent
from a free-text status string is what this domain replaces.

Shape
-----
Mirrors `lambda_utils.notifications`, which is the established domain layout here:

    states.py     the stage/lead/opportunity state machines and their legality rules
    keys.py       deterministic identifiers, so a replayed webhook cannot double-write
    entities.py   row constructors - the only place a CRM row is shaped
    store.py      DynamoDB access, with the guards expressed as ConditionExpressions
    service.py    the use cases: capture a lead, qualify it, convert it, move a stage

Two invariants this package owns
--------------------------------
1. **Idempotency is per source reference, not per person.** A replayed Flow webhook must
   not create a second lead; two genuinely separate enquiries from the same person
   must. Those are different questions and `keys.py` keeps them apart - conflating
   them is the classic CRM duplicate bug in both directions.

2. **A converted lead converts once.** `service.convert_lead` returns the existing
   opportunity rather than creating a second one, enforced by a conditional write, not
   by a prior read. A read-then-write here loses to concurrent Lambda invocations,
   which is exactly the traffic shape this fleet has.

Contact linkage
---------------
CRM rows reference a contact as `contactId`, holding the Contact's **canonical `id`**
resolved through `lambda_utils.contact_key`. That is deliberate: `contactId` is the
spelling the outward API and `MessagesTable` already use, while `id` is the physical
key. See `contact_key` for why the two exist and why they are now guaranteed equal.
"""
