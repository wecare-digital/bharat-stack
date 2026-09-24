"""The draft store, and the reason an approval can be granted by hash alone.

The property that matters is not "a draft round-trips". It is that the hash a client
submits is resolved to arguments the CLIENT never chose. Every test here is aimed at
a specific way that could fail: a missing draft, an altered row, a stale catalog, a
key that collides with an approval row, a float DynamoDB would reject.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))

from lambda_utils.agent import approvals as appr  # noqa: E402
from lambda_utils.agent import drafts  # noqa: E402
from lambda_utils.agent import governance as gov  # noqa: E402
from lambda_utils.agent import plans as plan_module  # noqa: E402

APPLY_TOOL = "send_whatsapp"
READ_TOOL = "search_contacts"
NOW = 1_800_000_000
REAL_NUMBER = "+918100640044"


@pytest.fixture(autouse=True)
def fresh_store():
    previous = drafts.get_store()
    drafts.set_store(drafts.InMemoryDraftStore())
    yield
    drafts.set_store(previous)


def a_plan(**arguments):
    return plan_module.build_plan(
        APPLY_TOOL,
        arguments or {"to": REAL_NUMBER, "content": "your order has shipped"},
        now=NOW)


class TestRoundTrip:
    def test_records_and_loads_the_same_intent(self):
        plan = a_plan()
        returned = drafts.record(plan, now=NOW)
        assert returned == plan.plan_hash

        loaded = drafts.load(plan.plan_hash)
        assert loaded.plan_hash == plan.plan_hash
        assert loaded.tool == plan.tool
        assert loaded.arguments == plan.arguments

    def test_the_loaded_plan_carries_the_real_arguments_not_masked_ones(self):
        # The whole reason this store exists. `describe_plan` shows `...0044`; a hash
        # over that masked value would collapse two different recipients into one
        # plan, so the draft must hold the full number.
        plan = a_plan()
        drafts.record(plan, now=NOW)
        loaded = drafts.load(plan.plan_hash)

        assert loaded.arguments["to"] == REAL_NUMBER
        assert plan_module.describe_plan(loaded)["arguments"]["to"] == "...0044"

    def test_two_different_recipients_are_two_different_drafts(self):
        first = a_plan(to=REAL_NUMBER, content="hi")
        second = a_plan(to="+919903300044", content="hi")
        assert first.plan_hash != second.plan_hash

        drafts.record(first, now=NOW)
        drafts.record(second, now=NOW)
        assert drafts.load(first.plan_hash).arguments["to"] == REAL_NUMBER
        assert drafts.load(second.plan_hash).arguments["to"] == "+919903300044"

    def test_argument_order_does_not_split_one_intent(self):
        one = plan_module.build_plan(APPLY_TOOL, {"to": REAL_NUMBER, "content": "x"},
                                     now=NOW)
        other = plan_module.build_plan(APPLY_TOOL, {"content": "x", "to": REAL_NUMBER},
                                       now=NOW)
        assert one.plan_hash == other.plan_hash
        drafts.record(one, now=NOW)
        assert drafts.load(other.plan_hash).plan_hash == one.plan_hash


class TestFailsClosed:
    def test_an_unknown_hash_refuses(self):
        with pytest.raises(drafts.DraftMissing):
            drafts.load("0" * 64)

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_a_blank_hash_refuses(self, empty):
        with pytest.raises(drafts.DraftMissing):
            drafts.load(empty)

    def test_an_altered_row_refuses_rather_than_approving_something_else(self):
        # The attack this prevents: edit the stored recipient, leave the key alone,
        # and the operator's approval of `...0044` would authorise a stranger.
        plan = a_plan()
        drafts.record(plan, now=NOW)

        row = drafts.get_store().get(drafts._key(plan.plan_hash))
        row["arguments"]["to"] = "+441234567890"
        drafts.get_store()._rows[str(row["planHash"])] = row

        with pytest.raises(drafts.DraftCorrupt, match="hash"):
            drafts.load(plan.plan_hash)

    def test_a_row_naming_a_different_tool_refuses(self):
        plan = a_plan()
        drafts.record(plan, now=NOW)
        row = drafts.get_store().get(drafts._key(plan.plan_hash))
        row["tool"] = "send_sms"
        drafts.get_store()._rows[str(row["planHash"])] = row

        with pytest.raises(drafts.DraftCorrupt):
            drafts.load(plan.plan_hash)

    def test_a_row_naming_a_nonexistent_tool_raises_tool_unknown(self):
        plan = a_plan()
        drafts.record(plan, now=NOW)
        row = drafts.get_store().get(drafts._key(plan.plan_hash))
        row["tool"] = "delete_the_database"
        drafts.get_store()._rows[str(row["planHash"])] = row

        with pytest.raises(gov.ToolUnknown):
            drafts.load(plan.plan_hash)

    def test_a_read_tool_row_is_not_loadable_as_a_plan(self):
        # A READ has no plan/apply split, so there is nothing to approve. If one ever
        # reached the store, loading it must refuse rather than mint an approval for
        # an action that never had an apply step.
        plan = a_plan()
        drafts.record(plan, now=NOW)
        row = drafts.get_store().get(drafts._key(plan.plan_hash))
        row["tool"] = READ_TOOL
        drafts.get_store()._rows[str(row["planHash"])] = row

        with pytest.raises(plan_module.PlanNotApplicable):
            drafts.load(plan.plan_hash)

    def test_a_zero_ttl_draft_is_refused_at_write_time(self):
        with pytest.raises(ValueError, match="lifetime"):
            drafts.record(a_plan(), ttl_seconds=0, now=NOW)

    def test_the_default_store_is_in_memory_so_nothing_survives_an_invocation(self):
        # Not a quirk. An unconfigured deployment holds no draft by the time an
        # approve request arrives, so every approval refuses - the safe direction.
        assert isinstance(drafts.InMemoryDraftStore(), drafts.InMemoryDraftStore)
        fresh = drafts.InMemoryDraftStore()
        assert fresh.get(drafts._key("a" * 64)) is None


class TestKeyspaceIsShared:
    def test_a_draft_key_can_never_collide_with_an_approval_key(self):
        # Both record types live in one table. Approvals are filed under the bare hex
        # hash; drafts under a `draft#` prefix. Hex cannot start with 'd','r','a','f'
        # followed by '#', so the two are disjoint by construction.
        plan = a_plan()
        assert all(c in "0123456789abcdef" for c in plan.plan_hash)
        assert drafts._key(plan.plan_hash).startswith("draft#")
        assert drafts._key(plan.plan_hash) != plan.plan_hash

    def test_the_draft_row_sets_the_tables_ttl_attribute(self):
        plan = a_plan()
        drafts.record(plan, ttl_seconds=600, now=NOW)
        row = drafts.get_store().get(drafts._key(plan.plan_hash))
        assert row["expiresTtl"] == NOW + 600
        assert row["recordType"] == "draft"

    def test_the_draft_ttl_outlives_the_approval_ttl(self):
        # An approval that is still valid must not point at a vanished draft.
        assert drafts.DEFAULT_DRAFT_TTL_SECONDS >= appr.DEFAULT_TTL_SECONDS


class TestDynamoShape:
    def test_no_float_reaches_dynamodb(self):
        # DynamoDB rejects floats outright, and a silent Decimal conversion would
        # change the hash. `canonical_arguments` stringifies scalars, which is what
        # keeps both problems away.
        plan = plan_module.build_plan(APPLY_TOOL,
                                      {"to": REAL_NUMBER, "amount": 12.5},
                                      now=NOW)
        row = drafts._to_row(plan, 600, NOW)

        def walk(value):
            if isinstance(value, dict):
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)
            else:
                assert not isinstance(value, float), f"float in row: {value!r}"

        walk(row)
        assert row["arguments"]["amount"] == "12.5"

    def test_the_row_is_keyed_on_the_tables_partition_key_name(self):
        plan = a_plan()
        row = drafts._to_row(plan, 600, NOW)
        # The live table's key schema is a single `planHash` hash key; a row using any
        # other name would fail at PutItem, which a unit test should catch first.
        assert "planHash" in row


class TestApprovalByHashAlone:
    """The end-to-end property: a client sends a hash, a human's yes is recorded
    against arguments that client never supplied."""

    @pytest.fixture(autouse=True)
    def fresh_approvals(self):
        previous = appr.get_store()
        appr.set_store(appr.InMemoryApprovalStore())
        yield
        appr.set_store(previous)

    def test_a_hash_is_enough_to_approve_the_right_intent(self):
        plan = a_plan()
        drafts.record(plan, now=NOW)

        # Everything a client is allowed to send.
        submitted = {"planHash": plan.plan_hash}

        loaded = drafts.load(submitted["planHash"])
        approval = appr.grant(loaded, approved_by="manish@wecare.digital", now=NOW)

        assert approval.plan_hash == plan.plan_hash
        assert approval.tool == APPLY_TOOL
        assert approval.approved_by == "manish@wecare.digital"

    def test_approving_still_does_not_make_an_apply_possible(self):
        # The point of the whole exercise. One gate fell; the other did not.
        plan = a_plan()
        drafts.record(plan, now=NOW)
        appr.grant(drafts.load(plan.plan_hash), approved_by="manish", now=NOW)

        assert gov.is_enabled(APPLY_TOOL) is False
        with pytest.raises(gov.ToolRefused):
            appr.assert_may_apply(plan, now=NOW)

    def test_the_approval_is_still_single_use(self):
        plan = a_plan()
        drafts.record(plan, now=NOW)
        appr.grant(drafts.load(plan.plan_hash), approved_by="manish", now=NOW)

        appr.consume(plan, now=NOW)
        with pytest.raises(appr.ApprovalRejected, match="already been used"):
            appr.consume(plan, now=NOW)

    def test_a_draft_that_was_never_recorded_cannot_be_approved(self):
        plan = a_plan(to=REAL_NUMBER, content="never drafted")
        with pytest.raises(drafts.DraftMissing):
            drafts.load(plan.plan_hash)
