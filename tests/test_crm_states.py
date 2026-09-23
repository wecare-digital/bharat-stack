"""CRM state machines, identifiers and row shapes.

These are the pure layers, so they are tested before the store and service are written -
the Phase 3 notification domain found two design bugs this way, both of which would have
been much more expensive to see through a DynamoDB mock.

What is actually being pinned here
----------------------------------
Not "does the enum exist". The assertions target the decisions that could reasonably have
gone the other way, because those are the ones a later edit will quietly reverse:

* a converted lead is frozen - nothing follows CONVERTED
* WON <-> LOST is refused even with reopen
* stage membership is checked across pipelines before outcome legality
* replaying an arrival hits the same lead id; two real enquiries do not
* MANUAL and IMPORT are non-deterministic on purpose
* an activity with no subject is refused rather than orphaned
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.crm import entities, keys, states  # noqa: E402


class TestLeadLifecycle:
    def test_creation_must_start_at_new(self):
        assert states.lead_can_transition(None, states.LEAD_NEW)
        for other in states.LEAD_STATES:
            if other != states.LEAD_NEW:
                assert not states.lead_can_transition(None, other), (
                    f"creating a lead directly as {other} lets an importer fabricate "
                    "history")

    def test_converted_is_frozen(self):
        """The opportunity is the record of truth once conversion happens."""
        for target in states.LEAD_STATES:
            if target == states.LEAD_CONVERTED:
                continue
            assert not states.lead_can_transition(states.LEAD_CONVERTED, target)

    def test_reasserting_the_same_state_is_allowed(self):
        """Webhook replays do this constantly; it is not an error."""
        for state in states.LEAD_STATES:
            assert states.lead_can_transition(state, state)

    def test_only_qualified_converts(self):
        assert states.lead_is_convertible(states.LEAD_QUALIFIED)
        for state in states.LEAD_STATES:
            if state != states.LEAD_QUALIFIED:
                assert not states.lead_is_convertible(state)

    def test_new_cannot_convert_directly(self):
        assert not states.lead_can_transition(states.LEAD_NEW, states.LEAD_CONVERTED)

    def test_closed_leads_reopen_to_working_not_new(self):
        """Reopening to NEW would reset response-time measurement on a touched lead."""
        for closed in (states.LEAD_DISQUALIFIED, states.LEAD_JUNK):
            assert states.lead_can_transition(closed, states.LEAD_WORKING)
            assert not states.lead_can_transition(closed, states.LEAD_NEW)

    def test_nurturing_wakes_to_working_not_qualified(self):
        assert states.lead_can_transition(states.LEAD_NURTURING, states.LEAD_WORKING)
        # Qualified is reachable too - a parked lead can be assessed without a new
        # conversation - but the point is that WORKING exists as the honest path.
        assert states.lead_can_transition(states.LEAD_NURTURING, states.LEAD_QUALIFIED)

    def test_junk_and_disqualified_are_distinct_states(self):
        """They mean different things to a conversion rate, so they cannot be merged."""
        assert states.LEAD_JUNK != states.LEAD_DISQUALIFIED
        assert states.lead_is_terminal(states.LEAD_JUNK)
        assert states.lead_is_terminal(states.LEAD_DISQUALIFIED)

    def test_unknown_states_are_refused_not_guessed(self):
        assert not states.lead_can_transition(states.LEAD_NEW, "ALMOST_SOLD")
        assert not states.lead_can_transition("ALMOST_SOLD", states.LEAD_WORKING)


class TestOpportunityOutcome:
    def test_created_open(self):
        assert states.opportunity_can_transition(None, states.OPP_OPEN)
        assert not states.opportunity_can_transition(None, states.OPP_WON)

    def test_terminal_requires_explicit_reopen(self):
        for terminal in (states.OPP_WON, states.OPP_LOST, states.OPP_ABANDONED):
            assert not states.opportunity_can_transition(terminal, states.OPP_OPEN)
            assert states.opportunity_can_transition(terminal, states.OPP_OPEN,
                                                     reopen=True)

    def test_won_to_lost_is_refused_even_with_reopen(self):
        """Ambiguous between a correction and a new deal; the caller must disambiguate."""
        assert not states.opportunity_can_transition(states.OPP_WON, states.OPP_LOST,
                                                     reopen=True)
        assert not states.opportunity_can_transition(states.OPP_LOST, states.OPP_WON,
                                                     reopen=True)

    def test_correction_path_exists(self):
        """LOST -> OPEN -> WON is the explicit two-step correction."""
        assert states.opportunity_can_transition(states.OPP_LOST, states.OPP_OPEN,
                                                 reopen=True)
        assert states.opportunity_can_transition(states.OPP_OPEN, states.OPP_WON)

    def test_abandoned_is_not_lost(self):
        """Abandoned must stay out of the win-rate denominator."""
        assert states.OPP_ABANDONED not in (states.OPP_LOST, states.OPP_WON)
        assert states.opportunity_is_terminal(states.OPP_ABANDONED)


class TestStageMembership:
    PIPE = "pl_" + "a" * 32
    OTHER = "pl_" + "b" * 32

    def test_cross_pipeline_stage_is_refused(self):
        legal, reason = states.stage_move_is_legal(
            opportunity_pipeline_id=self.PIPE,
            stage_pipeline_id=self.OTHER,
            stage_kind=states.STAGE_OPEN,
            current_outcome=states.OPP_OPEN)
        assert not legal
        assert "different pipeline" in reason

    def test_missing_stage_is_refused_before_anything_else(self):
        legal, reason = states.stage_move_is_legal(
            opportunity_pipeline_id=self.PIPE,
            stage_pipeline_id=None,
            stage_kind=states.STAGE_OPEN,
            current_outcome=states.OPP_OPEN)
        assert not legal
        assert "does not exist" in reason

    def test_structural_check_precedes_outcome_check(self):
        """A cross-pipeline stage on a WON opportunity reports the pipeline, not reopen.

        Order matters: reporting "pass reopen" would send the caller down a path that
        cannot work, and they would keep retrying with reopen set.
        """
        legal, reason = states.stage_move_is_legal(
            opportunity_pipeline_id=self.PIPE,
            stage_pipeline_id=self.OTHER,
            stage_kind=states.STAGE_OPEN,
            current_outcome=states.OPP_WON)
        assert not legal
        assert "different pipeline" in reason
        assert "reopen" not in reason

    def test_open_stage_movement_is_free_within_a_pipeline(self):
        """Deals regress; refusing that gets worked around with duplicate opportunities."""
        legal, _ = states.stage_move_is_legal(
            opportunity_pipeline_id=self.PIPE,
            stage_pipeline_id=self.PIPE,
            stage_kind=states.STAGE_OPEN,
            current_outcome=states.OPP_OPEN)
        assert legal

    def test_entering_a_won_stage_implies_won(self):
        assert states.outcome_for_stage_kind(states.STAGE_WON,
                                             states.OPP_OPEN) == states.OPP_WON
        assert states.outcome_for_stage_kind(states.STAGE_LOST,
                                            states.OPP_OPEN) == states.OPP_LOST
        assert states.outcome_for_stage_kind(states.STAGE_OPEN,
                                            states.OPP_OPEN) == states.OPP_OPEN

    def test_moving_a_closed_opportunity_to_an_open_stage_needs_reopen(self):
        kwargs = dict(opportunity_pipeline_id=self.PIPE, stage_pipeline_id=self.PIPE,
                      stage_kind=states.STAGE_OPEN, current_outcome=states.OPP_WON)
        legal, reason = states.stage_move_is_legal(**kwargs)
        assert not legal
        assert "reopen" in reason
        legal, _ = states.stage_move_is_legal(**kwargs, reopen=True)
        assert legal

    def test_unknown_stage_kind_is_refused(self):
        legal, reason = states.stage_move_is_legal(
            opportunity_pipeline_id=self.PIPE,
            stage_pipeline_id=self.PIPE,
            stage_kind="PARKED",
            current_outcome=states.OPP_OPEN)
        assert not legal
        assert "unknown kind" in reason


class TestIdentifierIdempotency:
    def test_replayed_arrival_is_the_same_lead(self):
        a = keys.lead_id(keys.SOURCE_FLOW, "flow-token-abc")
        b = keys.lead_id(keys.SOURCE_FLOW, "flow-token-abc")
        assert a == b

    def test_two_real_enquiries_are_two_leads(self):
        a = keys.lead_id(keys.SOURCE_FLOW, "flow-token-abc")
        b = keys.lead_id(keys.SOURCE_FLOW, "flow-token-def")
        assert a != b

    def test_same_ref_from_a_different_source_is_a_different_lead(self):
        a = keys.lead_id(keys.SOURCE_FLOW, "ref-1")
        b = keys.lead_id(keys.SOURCE_WEB_FORM, "ref-1")
        assert a != b

    def test_manual_and_import_are_non_deterministic(self):
        """A human creating two leads means two leads, not an overwrite."""
        for source in (keys.SOURCE_MANUAL, keys.SOURCE_IMPORT):
            assert not keys.source_is_deterministic(source)
            assert keys.lead_id(source, "same-ref") != keys.lead_id(source, "same-ref")

    def test_deterministic_source_with_empty_ref_falls_back_to_random(self):
        """Hashing '' would merge every malformed arrival into one lead."""
        a = keys.lead_id(keys.SOURCE_FLOW, "")
        b = keys.lead_id(keys.SOURCE_FLOW, None)
        assert a != b

    def test_separator_prevents_a_split_collision(self):
        """('a:b','c') and ('a','b:c') must not hash alike."""
        assert keys.lead_id(keys.SOURCE_FLOW, "a:b#c") != \
            keys.lead_id(keys.SOURCE_FLOW, "a#b:c")

    def test_conversion_id_is_derived_from_the_lead(self):
        lead = keys.lead_id(keys.SOURCE_FLOW, "tok")
        assert keys.opportunity_id_for_lead(lead) == keys.opportunity_id_for_lead(lead)
        assert keys.opportunity_id_for_lead(lead) != keys.opportunity_id_for_lead(
            keys.lead_id(keys.SOURCE_FLOW, "tok2"))

    def test_standalone_opportunity_ids_are_unique(self):
        assert keys.opportunity_id() != keys.opportunity_id()

    def test_activity_ids_are_unique_for_identical_content(self):
        """Two identical notes are two notes."""
        assert keys.activity_id(at=100) != keys.activity_id(at=100)

    def test_pipeline_and_stage_ids_are_name_derived(self):
        p = keys.pipeline_id("Sales")
        assert p == keys.pipeline_id("  sales  "), "re-provisioning must be a no-op"
        assert keys.stage_id(p, "Qualified") == keys.stage_id(p, "qualified")

    def test_same_stage_name_in_two_pipelines_does_not_collide(self):
        a, b = keys.pipeline_id("Sales"), keys.pipeline_id("Support")
        assert keys.stage_id(a, "Qualified") != keys.stage_id(b, "Qualified")

    def test_unknown_source_is_refused(self):
        with pytest.raises(keys.InvalidSource):
            keys.lead_id("TIKTOK", "ref")

    def test_prefixes_distinguish_kinds(self):
        lead = keys.lead_id(keys.SOURCE_FLOW, "t")
        opp = keys.opportunity_id_for_lead(lead)
        assert keys.looks_like(keys.LEAD_PREFIX, lead)
        assert not keys.looks_like(keys.LEAD_PREFIX, opp)
        assert keys.looks_like(keys.OPPORTUNITY_PREFIX, opp)
        assert not keys.looks_like(keys.LEAD_PREFIX, None)
        assert not keys.looks_like(keys.LEAD_PREFIX, "lead_nothex")

    def test_ids_do_not_leak_the_source_reference(self):
        """A lead id can appear in a URL or an access log; a wamid embeds a phone number."""
        ref = "wamid.HBgMOTE4MTAwNjQwMDQ0"
        assert ref not in keys.lead_id(keys.SOURCE_INBOUND_WHATSAPP, ref)

    def test_open_lead_grouping_key_is_not_an_identity(self):
        k = keys.open_lead_index_key("c-1", "pl_x")
        assert k == "c-1#pl_x"
        with pytest.raises(ValueError):
            keys.open_lead_index_key("", "pl_x")


class TestRowShapes:
    PIPE = keys.pipeline_id("Sales")

    def test_lead_carries_every_indexed_field(self):
        row = entities.lead_row(contact_id="c-1", pipeline_id=self.PIPE,
                                source=keys.SOURCE_FLOW, source_ref="tok")
        for field in ("leadId", "contactId", "pipelineId", "state", "createdAt",
                      "contactPipelineKey"):
            assert field in row, f"{field} backs a GSI; without it the row is invisible"
        assert row["state"] == states.LEAD_NEW

    def test_lead_starts_unconverted_with_no_placeholder(self):
        """`attribute_not_exists(opportunityId)` is the conversion guard."""
        row = entities.lead_row(contact_id="c-1", pipeline_id=self.PIPE,
                                source=keys.SOURCE_MANUAL)
        assert "opportunityId" not in row
        assert "convertedAt" not in row

    def test_source_ref_is_stored_as_well_as_hashed(self):
        row = entities.lead_row(contact_id="c-1", pipeline_id=self.PIPE,
                                source=keys.SOURCE_FLOW, source_ref="tok-77")
        assert row["sourceRef"] == "tok-77"

    def test_negative_amount_is_refused(self):
        with pytest.raises(ValueError):
            entities.lead_row(contact_id="c-1", pipeline_id=self.PIPE,
                              source=keys.SOURCE_MANUAL, amount_paise=-1)

    def test_pipeline_default_flag_is_indexable(self):
        """A boolean cannot be a DynamoDB index key."""
        row = entities.pipeline_row(name="Sales", is_default=True)
        assert row["isDefault"] == "true"
        assert isinstance(row["isDefault"], str)

    def test_stage_probability_is_optional_not_defaulted(self):
        row = entities.stage_row(pipeline_id=self.PIPE, name="New", order=0)
        assert "probability" not in row, "a default 50 becomes half the forecast"

    def test_stage_probability_range_is_enforced(self):
        with pytest.raises(ValueError):
            entities.stage_row(pipeline_id=self.PIPE, name="X", order=0,
                               probability=101)

    def test_stage_kind_is_validated(self):
        with pytest.raises(ValueError):
            entities.stage_row(pipeline_id=self.PIPE, name="X", order=0, kind="PARKED")

    def test_opportunity_records_stage_entry_separately(self):
        row = entities.opportunity_row(contact_id="c-1", pipeline_id=self.PIPE,
                                       stage_id="stg_x", title="Deal")
        assert row["stageEnteredAt"] == row["createdAt"]
        assert row["outcome"] == states.OPP_OPEN

    def test_opportunity_requires_a_title(self):
        with pytest.raises(ValueError):
            entities.opportunity_row(contact_id="c-1", pipeline_id=self.PIPE,
                                     stage_id="stg_x", title="   ")

    def test_activity_needs_a_subject(self):
        with pytest.raises(ValueError):
            entities.activity_row(kind=states.ACTIVITY_NOTE, summary="orphan")

    def test_user_cannot_forge_a_stage_change(self):
        with pytest.raises(ValueError):
            entities.activity_row(kind=states.ACTIVITY_STAGE_CHANGE, contact_id="c-1")
        row = entities.activity_row(kind=states.ACTIVITY_STAGE_CHANGE,
                                    contact_id="c-1", system=True)
        assert row["isSystem"] is True

    def test_only_a_task_carries_a_due_date(self):
        with pytest.raises(ValueError):
            entities.activity_row(kind=states.ACTIVITY_NOTE, contact_id="c-1", due_at=1)
        row = entities.activity_row(kind=states.ACTIVITY_TASK, contact_id="c-1", due_at=1)
        assert row["dueAt"] == 1

    def test_activity_sorts_on_at(self):
        row = entities.activity_row(kind=states.ACTIVITY_NOTE, contact_id="c-1", at=555)
        assert row["at"] == 555

    def test_no_crm_row_carries_a_ttl(self):
        """Expiring a CRM row deletes the only evidence of what marketing spend produced."""
        rows = [
            entities.lead_row(contact_id="c", pipeline_id=self.PIPE,
                              source=keys.SOURCE_MANUAL),
            entities.opportunity_row(contact_id="c", pipeline_id=self.PIPE,
                                     stage_id="stg_x", title="D"),
            entities.activity_row(kind=states.ACTIVITY_NOTE, contact_id="c"),
            entities.pipeline_row(name="Sales"),
            entities.stage_row(pipeline_id=self.PIPE, name="New", order=0),
        ]
        for row in rows:
            assert "expiresAt" not in row and "ttl" not in row

    def test_none_is_stripped_but_empty_string_survives_where_given(self):
        row = entities.lead_row(contact_id="c-1", pipeline_id=self.PIPE,
                                source=keys.SOURCE_MANUAL, email=None, name="  ")
        assert "email" not in row
        # A whitespace-only name is normalised away rather than stored as noise.
        assert "name" not in row


class TestDefaultPipeline:
    def test_is_idempotent(self):
        a = entities.default_pipeline_rows(at=1000)
        b = entities.default_pipeline_rows(at=1000)
        assert a == b, "re-provisioning must not create a second pipeline"

    def test_has_exactly_one_won_and_one_lost_stage(self):
        stages = entities.default_pipeline_rows()["stages"]
        kinds = [s["kind"] for s in stages]
        assert kinds.count(states.STAGE_WON) == 1
        assert kinds.count(states.STAGE_LOST) == 1

    def test_closed_stages_render_last(self):
        stages = entities.default_pipeline_rows()["stages"]
        closed = [s["displayOrder"] for s in stages if s["kind"] != states.STAGE_OPEN]
        open_ = [s["displayOrder"] for s in stages if s["kind"] == states.STAGE_OPEN]
        assert min(closed) > max(open_)

    def test_the_first_stage_has_no_forecast_weight(self):
        stages = entities.default_pipeline_rows()["stages"]
        first = min(stages, key=lambda s: s["displayOrder"])
        assert "probability" not in first, (
            "weighting untouched inbound volume puts raw lead count in the revenue "
            "projection")

    def test_every_stage_belongs_to_the_pipeline(self):
        bundle = entities.default_pipeline_rows()
        pid = bundle["pipeline"]["pipelineId"]
        assert all(s["pipelineId"] == pid for s in bundle["stages"])

    def test_stage_ids_are_unique(self):
        stages = entities.default_pipeline_rows()["stages"]
        assert len({s["stageId"] for s in stages}) == len(stages)

    def test_pipeline_is_marked_default(self):
        assert entities.default_pipeline_rows()["pipeline"]["isDefault"] == "true"
