"""CRM use cases under replay and concurrency.

Every test here answers "what happens when this is called twice", because every caller is a
webhook with at-least-once delivery. The fake in `crm_fake_dynamo` evaluates
ConditionExpressions for real and refuses expression forms it does not recognise, so these
exercise the actual guards rather than a stub that always says yes.

The index map below mirrors what `scripts/provision_crm_domain.py` creates. That pairing is
load-bearing: a query against an index that was never provisioned returns an empty result
in production rather than an error, so a board just looks permanently empty. Here it raises.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
for path in (str(SHARED), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402
from lambda_utils.crm import entities, keys, service, states, store  # noqa: E402

TABLE_KEYS = {
    store.PIPELINES_TABLE: "pipelineId",
    store.STAGES_TABLE: "stageId",
    store.LEADS_TABLE: "leadId",
    store.OPPORTUNITIES_TABLE: "opportunityId",
    store.ACTIVITIES_TABLE: "activityId",
}

#: {table: {index: (partition, sort)}} - must match provisioning exactly.
TABLE_INDEXES = {
    store.PIPELINES_TABLE: {
        "isDefault-index": ("isDefault", None),
    },
    store.STAGES_TABLE: {
        "pipelineId-displayOrder-index": ("pipelineId", "displayOrder"),
    },
    store.LEADS_TABLE: {
        "contactId-createdAt-index": ("contactId", "createdAt"),
        "state-createdAt-index": ("state", "createdAt"),
        "contactPipelineKey-index": ("contactPipelineKey", None),
    },
    store.OPPORTUNITIES_TABLE: {
        "contactId-createdAt-index": ("contactId", "createdAt"),
        "stageId-createdAt-index": ("stageId", "createdAt"),
    },
    store.ACTIVITIES_TABLE: {
        "contactId-at-index": ("contactId", "at"),
        "leadId-at-index": ("leadId", "at"),
        "opportunityId-at-index": ("opportunityId", "at"),
    },
}

CONTACT = "c-0001"


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDynamo(TABLE_KEYS, TABLE_INDEXES)
    monkeypatch.setattr(store, "_resource", lambda: fake)
    monkeypatch.setattr(store, "ClientError", FakeClientError)
    return fake


@pytest.fixture()
def pipeline(db):
    result = service.ensure_default_pipeline()
    return result["pipelineId"]


class TestProvisioning:
    def test_creates_pipeline_and_every_stage(self, db):
        result = service.ensure_default_pipeline()
        assert result["pipeline"] == "created"
        assert db.count(store.PIPELINES_TABLE) == 1
        assert db.count(store.STAGES_TABLE) == len(entities.DEFAULT_STAGES)

    def test_is_idempotent_and_does_not_reset_created_at(self, db):
        service.ensure_default_pipeline(at=1000)
        second = service.ensure_default_pipeline(at=9999)
        assert second["pipeline"] == "exists"
        assert db.count(store.PIPELINES_TABLE) == 1
        stored = db.all_rows(store.PIPELINES_TABLE)[0]
        assert stored["createdAt"] == 1000, (
            "re-provisioning must not rewrite createdAt on a live pipeline")

    def test_default_pipeline_is_found_by_index_not_scan(self, db, pipeline):
        found = store.default_pipeline()
        assert found and found["pipelineId"] == pipeline
        assert any(call[1].startswith("query:isDefault") for call in db.calls)

    def test_first_stage_skips_a_closed_stage(self, db, pipeline):
        """A reordered board must not drop new opportunities straight into Won."""
        won = next(s for s in store.list_stages(pipeline)
                   if s["kind"] == states.STAGE_WON)
        store.put_stage({**won, "displayOrder": -100}, overwrite=True)
        first = store.first_stage(pipeline)
        assert first["kind"] == states.STAGE_OPEN

    def test_stages_come_back_in_display_order(self, db, pipeline):
        orders = [s["displayOrder"] for s in store.list_stages(pipeline)]
        assert orders == sorted(orders)


class TestLeadCapture:
    def test_captures_a_lead_and_logs_it(self, db, pipeline):
        result = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                      source_ref="tok-1", subject="Needs a quote")
        assert result["outcome"] == "created"
        assert result["lead"]["state"] == states.LEAD_NEW
        assert db.count(store.LEADS_TABLE) == 1
        kinds = [a["kind"] for a in db.all_rows(store.ACTIVITIES_TABLE)]
        assert states.ACTIVITY_STATE_CHANGE in kinds

    def test_replayed_webhook_does_not_create_a_second_lead(self, db, pipeline):
        first = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                     source_ref="tok-1")
        second = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                      source_ref="tok-1")
        assert first["outcome"] == "created"
        assert second["outcome"] == "duplicate"
        assert db.count(store.LEADS_TABLE) == 1

    def test_replay_returns_the_stored_row_not_the_fresh_one(self, db, pipeline):
        """A replay must not report a worked lead as untouched."""
        created = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                       source_ref="tok-1")
        service.transition_lead(lead_id=created["lead"]["leadId"],
                                new_state=states.LEAD_WORKING)
        replay = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                      source_ref="tok-1")
        assert replay["outcome"] == "duplicate"
        assert replay["lead"]["state"] == states.LEAD_WORKING

    def test_two_real_enquiries_are_two_leads_by_default(self, db, pipeline):
        """Business duplicates are not collapsed unless asked for."""
        service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                             source_ref="tok-1")
        service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                             source_ref="tok-2")
        assert db.count(store.LEADS_TABLE) == 2

    def test_attach_to_open_lead_records_the_repeat_without_a_new_row(self, db, pipeline):
        service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                             source_ref="tok-1")
        again = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                     source_ref="tok-2", attach_to_open_lead=True)
        assert again["outcome"] == "attached"
        assert db.count(store.LEADS_TABLE) == 1
        summaries = [a.get("summary", "") for a in db.all_rows(store.ACTIVITIES_TABLE)]
        assert any("Repeat enquiry" in s for s in summaries), (
            "the second enquiry must still appear in the history")

    def test_attach_does_not_reuse_a_closed_lead(self, db, pipeline):
        first = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                     source_ref="tok-1")
        service.transition_lead(lead_id=first["lead"]["leadId"],
                                new_state=states.LEAD_JUNK)
        again = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                     source_ref="tok-2", attach_to_open_lead=True)
        assert again["outcome"] == "created"
        assert db.count(store.LEADS_TABLE) == 2

    def test_accepts_either_contact_spelling(self, db, pipeline):
        by_alias = service.capture_lead(contact={"contactId": CONTACT},
                                        source=keys.SOURCE_MANUAL)
        assert by_alias["lead"]["contactId"] == CONTACT

    def test_missing_contact_is_refused(self, db, pipeline):
        with pytest.raises(ValueError):
            service.capture_lead(contact_id="", source=keys.SOURCE_MANUAL)

    def test_unknown_pipeline_is_refused_not_created(self, db, pipeline):
        """Auto-provisioning mid-webhook would attach live leads to an unseen pipeline."""
        with pytest.raises(ValueError, match="does not exist"):
            service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_MANUAL,
                                 pipeline_id="pl_" + "f" * 32)

    def test_capture_without_provisioning_says_so(self, db):
        with pytest.raises(ValueError, match="no default pipeline"):
            service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_MANUAL)


class TestLeadProgression:
    def _lead(self):
        return service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                    source_ref="tok-1")["lead"]["leadId"]

    def test_transition_records_first_touch_once(self, db, pipeline):
        lead_id = self._lead()
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_WORKING)
        touched = store.get_lead(lead_id)["firstTouchedAt"]
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_NURTURING)
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_WORKING)
        assert store.get_lead(lead_id)["firstTouchedAt"] == touched, (
            "moving first touch forward makes a slow response look instant")

    def test_repeating_a_transition_is_already_not_an_error(self, db, pipeline):
        lead_id = self._lead()
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_WORKING)
        again = service.transition_lead(lead_id=lead_id, new_state=states.LEAD_WORKING)
        assert again["outcome"] == "already"

    def test_illegal_transition_is_refused_with_a_reason(self, db, pipeline):
        lead_id = self._lead()
        result = service.transition_lead(lead_id=lead_id, new_state=states.LEAD_CONVERTED)
        assert result["outcome"] == "refused"
        assert "not a legal" in result["reason"]

    def test_stale_expectation_is_refused_by_the_write_not_the_read(self, db, pipeline):
        """Simulates a concurrent change between read and write."""
        lead_id = self._lead()
        result = service.transition_lead(lead_id=lead_id, new_state=states.LEAD_WORKING,
                                         expected_state=states.LEAD_NURTURING)
        assert result["outcome"] == "refused"
        assert store.get_lead(lead_id)["state"] == states.LEAD_NEW

    def test_disqualify_reason_is_stored(self, db, pipeline):
        lead_id = self._lead()
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_DISQUALIFIED,
                                reason="Out of area")
        assert store.get_lead(lead_id)["disqualifiedReason"] == "Out of area"

    def test_unknown_lead_is_refused(self, db, pipeline):
        result = service.transition_lead(lead_id="lead_" + "0" * 32,
                                         new_state=states.LEAD_WORKING)
        assert result["outcome"] == "refused"

    def test_a_non_lead_id_raises_rather_than_returning_not_found(self, db, pipeline):
        with pytest.raises(ValueError):
            service.transition_lead(lead_id="opp_" + "0" * 32,
                                    new_state=states.LEAD_WORKING)


class TestConversion:
    def _qualified(self):
        lead_id = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                       source_ref="tok-1",
                                       subject="Bulk order")["lead"]["leadId"]
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_QUALIFIED)
        return lead_id

    def test_converts_a_qualified_lead(self, db, pipeline):
        lead_id = self._qualified()
        result = service.convert_lead(lead_id=lead_id, amount_paise=250000)
        assert result["outcome"] == "converted"
        assert result["opportunity"]["outcome"] == states.OPP_OPEN
        assert result["opportunity"]["amountPaise"] == 250000
        assert result["lead"]["state"] == states.LEAD_CONVERTED
        assert result["lead"]["opportunityId"] == result["opportunity"]["opportunityId"]

    def test_converting_twice_yields_one_opportunity(self, db, pipeline):
        lead_id = self._qualified()
        first = service.convert_lead(lead_id=lead_id)
        second = service.convert_lead(lead_id=lead_id)
        assert second["outcome"] == "already_converted"
        assert db.count(store.OPPORTUNITIES_TABLE) == 1
        assert second["opportunity"]["opportunityId"] == \
            first["opportunity"]["opportunityId"]

    def test_concurrent_conversion_converges_on_one_opportunity(self, db, pipeline):
        """The lead-claim loses, the opportunity id is shared, and it reports honestly."""
        lead_id = self._qualified()
        db.arm_failure(store.LEADS_TABLE, "update_item",
                       FakeClientError("ConditionalCheckFailedException"))
        result = service.convert_lead(lead_id=lead_id)
        assert result["outcome"] == "already_converted"
        assert db.count(store.OPPORTUNITIES_TABLE) == 1

    def test_an_orphan_opportunity_is_recoverable_by_retrying(self, db, pipeline):
        """Opportunity-first ordering must self-heal; lead-first would not.

        The lead claim fails, leaving an opportunity with the lead still QUALIFIED. The
        retry recomputes the same derived id, gets `exists`, and completes the claim.
        """
        lead_id = self._qualified()
        db.arm_failure(store.LEADS_TABLE, "update_item",
                       FakeClientError("ConditionalCheckFailedException"))
        service.convert_lead(lead_id=lead_id)
        assert store.get_lead(lead_id)["state"] == states.LEAD_QUALIFIED

        retry = service.convert_lead(lead_id=lead_id)
        assert retry["outcome"] == "converted"
        assert db.count(store.OPPORTUNITIES_TABLE) == 1
        assert store.get_lead(lead_id)["state"] == states.LEAD_CONVERTED

    def test_unqualified_lead_cannot_convert(self, db, pipeline):
        lead_id = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_MANUAL
                                       )["lead"]["leadId"]
        result = service.convert_lead(lead_id=lead_id)
        assert result["outcome"] == "refused"
        assert db.count(store.OPPORTUNITIES_TABLE) == 0

    def test_conversion_inherits_the_lead_amount_and_source(self, db, pipeline):
        lead_id = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_AD_CLICK,
                                       source_ref="click-9",
                                       amount_paise=99900)["lead"]["leadId"]
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_QUALIFIED)
        result = service.convert_lead(lead_id=lead_id)
        assert result["opportunity"]["amountPaise"] == 99900
        assert result["opportunity"]["source"] == keys.SOURCE_AD_CLICK

    def test_conversion_lands_in_the_first_open_stage(self, db, pipeline):
        lead_id = self._qualified()
        result = service.convert_lead(lead_id=lead_id)
        assert result["opportunity"]["stageId"] == store.first_stage(pipeline)["stageId"]

    def test_a_stage_from_another_pipeline_is_refused(self, db, pipeline):
        lead_id = self._qualified()
        other = entities.pipeline_row(name="Support")
        store.put_pipeline(other)
        foreign = entities.stage_row(pipeline_id=other["pipelineId"], name="Triage",
                                     order=0)
        store.put_stage(foreign)
        result = service.convert_lead(lead_id=lead_id, stage_id=foreign["stageId"])
        assert result["outcome"] == "refused"
        assert "different pipeline" in result["reason"]
        assert db.count(store.OPPORTUNITIES_TABLE) == 0

    def test_conversion_writes_both_audit_entries(self, db, pipeline):
        lead_id = self._qualified()
        service.convert_lead(lead_id=lead_id)
        kinds = [a["kind"] for a in db.all_rows(store.ACTIVITIES_TABLE)]
        assert kinds.count(states.ACTIVITY_STATE_CHANGE) >= 1
        assert kinds.count(states.ACTIVITY_STAGE_CHANGE) == 1


class TestStageMovement:
    def _opportunity(self, pipeline):
        lead_id = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                       source_ref="tok-1")["lead"]["leadId"]
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_QUALIFIED)
        return service.convert_lead(lead_id=lead_id)["opportunity"]["opportunityId"]

    def _stage(self, pipeline, name):
        return next(s for s in store.list_stages(pipeline) if s["name"] == name)

    def test_moves_between_open_stages(self, db, pipeline):
        opp = self._opportunity(pipeline)
        target = self._stage(pipeline, "Proposal")
        result = service.move_opportunity(opportunity_id=opp,
                                          stage_id=target["stageId"])
        assert result["outcome"] == "moved"
        assert result["opportunity"]["stageId"] == target["stageId"]
        assert result["opportunity"]["outcome"] == states.OPP_OPEN

    def test_entering_the_won_stage_wins_the_deal(self, db, pipeline):
        opp = self._opportunity(pipeline)
        won = self._stage(pipeline, "Won")
        result = service.move_opportunity(opportunity_id=opp, stage_id=won["stageId"])
        assert result["opportunity"]["outcome"] == states.OPP_WON
        assert result["opportunity"]["closedAt"]

    def test_reopening_clears_closed_at(self, db, pipeline):
        opp = self._opportunity(pipeline)
        won = self._stage(pipeline, "Won")
        service.move_opportunity(opportunity_id=opp, stage_id=won["stageId"])
        back = self._stage(pipeline, "Negotiation")
        result = service.move_opportunity(opportunity_id=opp, stage_id=back["stageId"],
                                          reopen=True)
        assert result["outcome"] == "moved"
        assert "closedAt" not in result["opportunity"], (
            "a stale closedAt on a live deal corrupts cycle time")

    def test_reopening_without_the_flag_is_refused(self, db, pipeline):
        opp = self._opportunity(pipeline)
        won = self._stage(pipeline, "Won")
        service.move_opportunity(opportunity_id=opp, stage_id=won["stageId"])
        back = self._stage(pipeline, "Negotiation")
        result = service.move_opportunity(opportunity_id=opp, stage_id=back["stageId"])
        assert result["outcome"] == "refused"
        assert "reopen" in result["reason"]

    def test_won_to_lost_directly_is_refused(self, db, pipeline):
        opp = self._opportunity(pipeline)
        service.move_opportunity(opportunity_id=opp,
                                 stage_id=self._stage(pipeline, "Won")["stageId"])
        result = service.move_opportunity(
            opportunity_id=opp, stage_id=self._stage(pipeline, "Lost")["stageId"],
            reopen=True)
        assert result["outcome"] == "refused"

    def test_re_dropping_on_the_same_stage_preserves_dwell_time(self, db, pipeline):
        opp = self._opportunity(pipeline)
        current = store.get_opportunity(opp)["stageId"]
        entered = store.get_opportunity(opp)["stageEnteredAt"]
        result = service.move_opportunity(opportunity_id=opp, stage_id=current)
        assert result["outcome"] == "unchanged"
        assert store.get_opportunity(opp)["stageEnteredAt"] == entered

    def test_cross_pipeline_move_is_refused(self, db, pipeline):
        opp = self._opportunity(pipeline)
        other = entities.pipeline_row(name="Support")
        store.put_pipeline(other)
        foreign = entities.stage_row(pipeline_id=other["pipelineId"], name="Triage",
                                     order=0)
        store.put_stage(foreign)
        result = service.move_opportunity(opportunity_id=opp,
                                          stage_id=foreign["stageId"])
        assert result["outcome"] == "refused"
        assert "different pipeline" in result["reason"]

    def test_nonexistent_stage_is_refused(self, db, pipeline):
        opp = self._opportunity(pipeline)
        result = service.move_opportunity(opportunity_id=opp,
                                          stage_id="stg_" + "0" * 32)
        assert result["outcome"] == "refused"
        assert "does not exist" in result["reason"]

    def test_lost_update_is_refused_by_compare_and_swap(self, db, pipeline):
        """Two users dragging the same card: the second must not silently win."""
        opp = self._opportunity(pipeline)
        db.arm_failure(store.OPPORTUNITIES_TABLE, "update_item",
                       FakeClientError("ConditionalCheckFailedException"))
        result = service.move_opportunity(
            opportunity_id=opp, stage_id=self._stage(pipeline, "Proposal")["stageId"])
        assert result["outcome"] == "refused"
        assert "moved since it was read" in result["reason"]

    def test_every_move_leaves_an_audit_entry(self, db, pipeline):
        opp = self._opportunity(pipeline)
        before = len([a for a in db.all_rows(store.ACTIVITIES_TABLE)
                      if a["kind"] == states.ACTIVITY_STAGE_CHANGE])
        service.move_opportunity(
            opportunity_id=opp, stage_id=self._stage(pipeline, "Proposal")["stageId"])
        after = len([a for a in db.all_rows(store.ACTIVITIES_TABLE)
                     if a["kind"] == states.ACTIVITY_STAGE_CHANGE])
        assert after == before + 1

    def test_a_non_opportunity_id_raises(self, db, pipeline):
        with pytest.raises(ValueError):
            service.move_opportunity(opportunity_id="lead_" + "0" * 32,
                                     stage_id="stg_" + "0" * 32)


class TestTimeline:
    def test_logs_a_user_activity(self, db, pipeline):
        result = service.log_activity(kind=states.ACTIVITY_CALL, contact_id=CONTACT,
                                      summary="Spoke about pricing")
        assert result["outcome"] == "logged"
        assert result["activity"]["isSystem"] is False

    def test_user_cannot_forge_a_stage_change(self, db, pipeline):
        for kind in sorted(states.ACTIVITY_SYSTEM_ONLY):
            with pytest.raises(ValueError):
                service.log_activity(kind=kind, contact_id=CONTACT)

    def test_timeline_needs_exactly_one_subject(self, db, pipeline):
        with pytest.raises(ValueError):
            store.timeline()
        with pytest.raises(ValueError):
            store.timeline(contact_id=CONTACT, lead_id="lead_" + "0" * 32)

    def test_timeline_is_newest_first(self, db, pipeline):
        for index in range(3):
            service.log_activity(kind=states.ACTIVITY_NOTE, contact_id=CONTACT,
                                 summary=f"note {index}")
        rows = store.timeline(contact_id=CONTACT, limit=10)
        stamps = [r["at"] for r in rows]
        assert stamps == sorted(stamps, reverse=True)

    def test_completing_a_task_keeps_the_first_completion_time(self, db, pipeline):
        task = service.log_activity(kind=states.ACTIVITY_TASK, contact_id=CONTACT,
                                    summary="Call back", due_at=1)["activity"]
        store.complete_activity(task["activityId"], at=500)
        with pytest.raises(store.Refused):
            store.complete_activity(task["activityId"], at=900)
        assert store.timeline(contact_id=CONTACT)[0]["completedAt"] == 500

    def test_a_note_cannot_be_completed(self, db, pipeline):
        note = service.log_activity(kind=states.ACTIVITY_NOTE,
                                    contact_id=CONTACT)["activity"]
        with pytest.raises(store.Refused):
            store.complete_activity(note["activityId"], at=1)

    def test_last_activity_bump_failure_does_not_fail_the_write(self, db, pipeline):
        """A sort hint must never cost a committed activity."""
        lead_id = service.capture_lead(contact_id=CONTACT,
                                       source=keys.SOURCE_MANUAL)["lead"]["leadId"]
        db.arm_failure(store.LEADS_TABLE, "update_item",
                       FakeClientError("ProvisionedThroughputExceededException"))
        result = service.log_activity(kind=states.ACTIVITY_NOTE, contact_id=CONTACT,
                                      lead_id=lead_id, summary="still recorded")
        assert result["outcome"] == "logged"


class TestContact360:
    def test_gathers_leads_opportunities_and_timeline(self, db, pipeline):
        lead_id = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                       source_ref="tok-1")["lead"]["leadId"]
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_QUALIFIED)
        service.convert_lead(lead_id=lead_id)
        service.log_activity(kind=states.ACTIVITY_NOTE, contact_id=CONTACT,
                             summary="hello")

        view = service.contact_360(contact_id=CONTACT)
        assert view["contactId"] == CONTACT
        assert len(view["leads"]) == 1
        assert len(view["opportunities"]) == 1
        assert view["activities"]

    def test_uses_no_scan(self, db, pipeline):
        service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_MANUAL)
        db.calls.clear()
        service.contact_360(contact_id=CONTACT)
        assert all("query:" in call[1] or call[1] == "get_item" for call in db.calls), (
            f"contact_360 must not scan; calls were {db.calls}")

    def test_resolves_the_contact_alias(self, db, pipeline):
        service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_MANUAL)
        view = service.contact_360(contact={"id": CONTACT, "contactId": CONTACT})
        assert view["contactId"] == CONTACT


class TestStoreGuardsAreLoadBearing:
    """The conditions, tested without the service layer's read in front of them.

    Added after a mutation check. Removing `attribute_not_exists(opportunityId)` from
    `mark_lead_converted`, and downgrading `move_stage`'s compare-and-swap to a presence
    check, broke **no test** - because `service.convert_lead` reads the lead first and
    short-circuits on `opportunityId`, and the concurrency tests above arm an artificial
    failure rather than provoking the real condition.

    A read short-circuit is a fine optimisation and a useless guard: the race it has to
    survive is precisely the one where both callers read before either writes. So these go
    at `store` directly, with no read in between, and they fail if the condition is weakened.
    """

    def _qualified_lead(self, pipeline):
        lead_id = service.capture_lead(contact_id=CONTACT, source=keys.SOURCE_FLOW,
                                       source_ref="tok-race")["lead"]["leadId"]
        service.transition_lead(lead_id=lead_id, new_state=states.LEAD_QUALIFIED)
        return lead_id

    def test_second_conversion_claim_is_refused(self, db, pipeline):
        """Both callers saw QUALIFIED with no opportunityId. Only one may claim it."""
        lead_id = self._qualified_lead(pipeline)
        opportunity_id = keys.opportunity_id_for_lead(lead_id)

        store.mark_lead_converted(lead_id, opportunity_id=opportunity_id, at=100)
        with pytest.raises(store.Refused) as first:
            store.mark_lead_converted(lead_id, opportunity_id=opportunity_id, at=200)
        assert first.value.reason == "already_converted"

        # And the claim did not move: the first conversion's timestamp survives.
        assert store.get_lead(lead_id)["convertedAt"] == 100

    def test_a_different_opportunity_cannot_steal_a_converted_lead(self, db, pipeline):
        lead_id = self._qualified_lead(pipeline)
        store.mark_lead_converted(lead_id, opportunity_id=keys.opportunity_id(), at=100)
        with pytest.raises(store.Refused):
            store.mark_lead_converted(lead_id, opportunity_id=keys.opportunity_id(),
                                      at=200)

    def test_an_unqualified_lead_cannot_be_claimed(self, db, pipeline):
        """The state half of the condition, independent of the opportunityId half."""
        lead_id = service.capture_lead(contact_id=CONTACT,
                                       source=keys.SOURCE_MANUAL)["lead"]["leadId"]
        with pytest.raises(store.Refused):
            store.mark_lead_converted(lead_id, opportunity_id=keys.opportunity_id(),
                                      at=100)

    def test_stage_move_with_a_stale_expected_stage_is_refused(self, db, pipeline):
        """The real lost-update race, provoked rather than simulated."""
        lead_id = self._qualified_lead(pipeline)
        opportunity_id = service.convert_lead(
            lead_id=lead_id)["opportunity"]["opportunityId"]
        stages = {s["name"]: s for s in store.list_stages(pipeline)}
        actual = store.get_opportunity(opportunity_id)["stageId"]

        # Caller A moves it.
        store.move_stage(opportunity_id,
                         expected_stage_id=actual,
                         expected_outcome=states.OPP_OPEN,
                         new_stage_id=stages["Proposal"]["stageId"],
                         new_outcome=states.OPP_OPEN, at=100)

        # Caller B still believes it is in the original stage.
        with pytest.raises(store.Refused) as refusal:
            store.move_stage(opportunity_id,
                             expected_stage_id=actual,
                             expected_outcome=states.OPP_OPEN,
                             new_stage_id=stages["Negotiation"]["stageId"],
                             new_outcome=states.OPP_OPEN, at=200)
        assert refusal.value.reason == "stale_stage"

        # A's move stands; B's is not silently applied on top.
        assert store.get_opportunity(opportunity_id)["stageId"] == \
            stages["Proposal"]["stageId"]

    def test_stage_move_with_a_stale_expected_outcome_is_refused(self, db, pipeline):
        """The outcome half of the swap, independently.

        A caller holding a view where the deal was OPEN must not move a deal someone else
        has already won - that would reopen it with no `reopen` decision and silently
        remove it from the revenue figure.
        """
        lead_id = self._qualified_lead(pipeline)
        opportunity_id = service.convert_lead(
            lead_id=lead_id)["opportunity"]["opportunityId"]
        stages = {s["name"]: s for s in store.list_stages(pipeline)}
        current = store.get_opportunity(opportunity_id)["stageId"]

        store.move_stage(opportunity_id, expected_stage_id=current,
                         expected_outcome=states.OPP_OPEN,
                         new_stage_id=stages["Won"]["stageId"],
                         new_outcome=states.OPP_WON, at=100)

        with pytest.raises(store.Refused):
            store.move_stage(opportunity_id,
                             expected_stage_id=stages["Won"]["stageId"],
                             expected_outcome=states.OPP_OPEN,   # stale
                             new_stage_id=stages["Proposal"]["stageId"],
                             new_outcome=states.OPP_OPEN, at=200)

    def test_lead_transition_cas_refuses_a_stale_state(self, db, pipeline):
        lead_id = service.capture_lead(contact_id=CONTACT,
                                       source=keys.SOURCE_MANUAL)["lead"]["leadId"]
        store.transition_lead(lead_id, expected_state=states.LEAD_NEW,
                              new_state=states.LEAD_WORKING, at=100)
        with pytest.raises(store.Refused) as refusal:
            store.transition_lead(lead_id, expected_state=states.LEAD_NEW,
                                  new_state=states.LEAD_JUNK, at=200)
        assert refusal.value.reason == "stale_state"
        assert store.get_lead(lead_id)["state"] == states.LEAD_WORKING

    def test_transition_refuses_an_illegal_move_before_touching_the_table(self, db,
                                                                         pipeline):
        lead_id = service.capture_lead(contact_id=CONTACT,
                                       source=keys.SOURCE_MANUAL)["lead"]["leadId"]
        db.calls.clear()
        with pytest.raises(ValueError):
            store.transition_lead(lead_id, expected_state=states.LEAD_NEW,
                                  new_state=states.LEAD_CONVERTED, at=100)
        assert not db.calls, "an illegal move must not reach DynamoDB at all"

    def test_capture_replay_is_refused_at_the_table(self, db, pipeline):
        row = entities.lead_row(contact_id=CONTACT, pipeline_id=pipeline,
                                source=keys.SOURCE_FLOW, source_ref="tok-x")
        assert store.capture_lead(row)[0] == "created"
        assert store.capture_lead(row)[0] == "duplicate"
        assert db.count(store.LEADS_TABLE) == 1

    def test_opportunity_insert_is_once_only(self, db, pipeline):
        row = entities.opportunity_row(contact_id=CONTACT, pipeline_id=pipeline,
                                       stage_id=store.first_stage(pipeline)["stageId"],
                                       title="Deal")
        assert store.create_opportunity(row)[0] == "created"
        assert store.create_opportunity(row)[0] == "exists"
        assert db.count(store.OPPORTUNITIES_TABLE) == 1

    def test_a_wrongly_prefixed_id_is_refused_before_the_write(self, db, pipeline):
        with pytest.raises(ValueError):
            store.capture_lead({"leadId": "opp_" + "0" * 32})
        with pytest.raises(ValueError):
            store.create_opportunity({"opportunityId": "lead_" + "0" * 32})


class TestProvisioningMatchesWhatTheCodeQueries:
    """`TABLE_INDEXES` above and `provision_crm_domain.TABLES` must agree exactly.

    The fake raises on an unknown index, which catches code querying an index that was
    never created - but only while the fake's map reflects reality. If the two drift, the
    fake starts approving queries against indexes that do not exist in AWS, and the
    protection silently evaporates.

    So the map is compared to the provisioning script itself. In production a query against
    a missing index returns an empty page rather than an error, so a lead queue or a board
    reads as "nothing here" with no fault reported anywhere.
    """

    @staticmethod
    def _provisioning():
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "provision_crm_domain", ROOT / "scripts" / "provision_crm_domain.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_same_tables(self):
        provisioning = self._provisioning()
        assert set(provisioning.TABLES) == set(TABLE_INDEXES), (
            "the fake and the provisioning script disagree about which tables exist")
        assert set(provisioning.TABLES) == set(TABLE_KEYS)

    def test_same_primary_keys(self):
        provisioning = self._provisioning()
        for table, spec in provisioning.TABLES.items():
            declared = [name for name, kind in spec["keys"] if kind == "HASH"]
            assert declared == [TABLE_KEYS[table]], (
                f"{table} partition key mismatch: {declared} vs {TABLE_KEYS[table]}")

    def test_same_indexes_with_the_same_keys(self):
        provisioning = self._provisioning()
        for table, spec in provisioning.TABLES.items():
            provisioned = {
                index_name: (
                    next(a for a, k in index_keys if k == "HASH"),
                    next((a for a, k in index_keys if k == "RANGE"), None),
                )
                for index_name, index_keys in spec.get("gsi", [])
            }
            assert provisioned == TABLE_INDEXES[table], (
                f"{table}: provisioned {provisioned} but the fake models "
                f"{TABLE_INDEXES[table]}")

    def test_every_indexed_attribute_is_declared(self):
        """DynamoDB rejects an index over an attribute absent from AttributeDefinitions."""
        provisioning = self._provisioning()
        for table, spec in provisioning.TABLES.items():
            declared = set(spec["attrs"])
            used = {name for name, _ in spec["keys"]}
            for _, index_keys in spec.get("gsi", []):
                used.update(name for name, _ in index_keys)
            assert used == declared, (
                f"{table}: attrs {sorted(declared)} vs keys+indexes {sorted(used)}; "
                "DynamoDB rejects both an undeclared indexed attribute and a declared "
                "unindexed one")

    def test_no_crm_table_is_given_a_ttl(self):
        provisioning = self._provisioning()
        for table, spec in provisioning.TABLES.items():
            assert "ttl" not in spec, (
                f"{table} must not expire; CRM rows are the business history")
            assert "expiresAt" not in spec["attrs"]


class TestDeclaredSchemaMatchesProvisioning:
    """`amplify/data/resource.ts` must agree with what is actually created.

    This is CRM-KEY-001 turned into a test. That defect was exactly this drift: the schema
    declared `.identifier(['contactId'])` while the live ContactsTable had always used `id`,
    and nothing anywhere compared the two. It survived because a schema file is never
    executed against the account - it is read by humans and by a deploy that was not run.

    Parsed with a regex rather than by executing TypeScript. The full alternative is
    `ampx generate` plus a CDK synth, which needs credentials and minutes; this needs
    neither and catches the specific mistake that has already happened once.
    """

    MODEL_FOR_TABLE = {
        "CrmPipelines": "CrmPipeline",
        "CrmStages": "CrmStage",
        "CrmLeads": "CrmLead",
        "CrmOpportunities": "CrmOpportunity",
        "CrmActivities": "CrmActivity",
    }

    @staticmethod
    def _schema_text():
        return (ROOT / "amplify" / "data" / "resource.ts").read_text(encoding="utf-8")

    @classmethod
    def _model_block(cls, model: str) -> str:
        import re

        text = cls._schema_text()
        start = text.index(f"  {model}: a\n")
        # Up to the model's own authorization line, which every model ends with.
        end = text.index("allow.authenticated()", start)
        return text[start:end]

    def test_every_crm_table_has_a_declared_model(self):
        text = self._schema_text()
        for model in self.MODEL_FOR_TABLE.values():
            assert f"  {model}: a\n" in text, (
                f"{model} is provisioned but not declared; that is the CRM-KEY-001 shape")

    def test_identifiers_match_the_provisioned_partition_keys(self):
        for table_suffix, model in self.MODEL_FOR_TABLE.items():
            table = f"{store.PREFIX}-{table_suffix}"
            expected = TABLE_KEYS[table]
            block = self._model_block(model)
            assert f".identifier( [ '{expected}' ] )" in block, (
                f"{model} must declare .identifier(['{expected}']) to match the "
                f"deployed key of {table}")

    def test_declared_indexes_match_the_provisioned_indexes(self):
        import re

        for table_suffix, model in self.MODEL_FOR_TABLE.items():
            table = f"{store.PREFIX}-{table_suffix}"
            block = self._model_block(model)

            declared = set()
            for match in re.finditer(
                    r"index\(\s*'(\w+)'\s*\)(?:\.sortKeys\(\s*\[\s*'(\w+)'\s*\]\s*\))?",
                    block):
                declared.add((match.group(1), match.group(2)))

            provisioned = {(partition, sort)
                           for partition, sort in TABLE_INDEXES[table].values()}
            assert declared == provisioned, (
                f"{model} declares indexes {sorted(declared)} but {table} has "
                f"{sorted(provisioned)}")

    def test_no_crm_model_declares_a_ttl(self):
        for model in self.MODEL_FOR_TABLE.values():
            block = self._model_block(model)
            assert "ttl:" not in block and "expiresAt" not in block, (
                f"{model} must not expire; a CRM row is the business history")

    def test_lead_does_not_default_its_opportunity_id(self):
        """A placeholder would break `attribute_not_exists(opportunityId)`."""
        block = self._model_block("CrmLead")
        assert "opportunityId: a.string()," in block
        assert "opportunityId: a.string().default" not in block

    def test_pipeline_default_flag_is_a_string_not_a_boolean(self):
        block = self._model_block("CrmPipeline")
        assert "isDefault: a.string().required()" in block, (
            "DynamoDB cannot index a boolean; a boolean here forces a scan per request")
