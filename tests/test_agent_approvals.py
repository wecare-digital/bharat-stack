"""Tests for the approval layer — the missing third of plan / approval / receipt.

The properties under test are the ones whose absence has a named failure:
single-use so an approval is not a replay token, bound to an exact intent so it is
not a standing licence, expiring so a stale yes cannot be spent, not grantable by
the agent, and failing closed on every error path.

Every APPLY tool is still `enabled=False`, so `assert_may_apply` must refuse even
with a perfectly valid approval. That is the point: two independent gates, and this
module only builds the second one.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))

from lambda_utils.agent import approvals as appr  # noqa: E402
from lambda_utils.agent import governance as gov  # noqa: E402
from lambda_utils.agent import plans as plan_module  # noqa: E402

APPLY_TOOL = "send_whatsapp"
READ_TOOL = "search_contacts"
NOW = 1_800_000_000


@pytest.fixture(autouse=True)
def fresh_store():
    """A clean store per test, restored afterwards."""
    previous = appr.get_store()
    appr.set_store(appr.InMemoryApprovalStore())
    yield
    appr.set_store(previous)


def a_plan(**arguments):
    return plan_module.build_plan(APPLY_TOOL, arguments or {"to": "+911234567890",
                                                            "content": "hello"},
                                  now=NOW)


class TestGrantRequiresAHuman:
    def test_grants_for_a_named_operator(self):
        approval = appr.grant(a_plan(), approved_by="manish", now=NOW)
        assert approval.approved_by == "manish"
        assert approval.consumed_at is None

    @pytest.mark.parametrize("who", [
        "", "   ", "agent", "Agent", "ASSISTANT", "model", "bedrock", "system",
        "none", "null", "anonymous", "unknown",
    ])
    def test_refuses_a_non_human_approver(self, who):
        # An approval recorded against 'agent' is the model approving its own send,
        # which is the arrangement this whole module exists to prevent.
        with pytest.raises(appr.ApprovalRejected, match="operator"):
            appr.grant(a_plan(), approved_by=who, now=NOW)

    def test_refuses_to_approve_a_read(self):
        plan = plan_module.Plan(
            tool=READ_TOOL, tool_class=gov.CLASS_READ,
            catalog_version=gov.CATALOG_VERSION, arguments={},
            created_at=NOW, plan_hash="x", idempotency_key="y")
        with pytest.raises(appr.ApprovalRejected, match="nothing to"):
            appr.grant(plan, approved_by="manish", now=NOW)

    def test_refuses_a_zero_lifetime_approval(self):
        with pytest.raises(appr.ApprovalRejected, match="no lifetime"):
            appr.grant(a_plan(), approved_by="manish", ttl_seconds=0, now=NOW)


class TestBoundToOneExactIntent:
    def test_a_different_argument_is_a_different_approval(self):
        # The whole reason the approval carries a plan hash: approving a message to
        # one number must not authorise the same message to another.
        first = a_plan(to="+911111111111", content="hi")
        second = a_plan(to="+912222222222", content="hi")
        assert first.plan_hash != second.plan_hash
        appr.grant(first, approved_by="manish", now=NOW)
        appr.check(first, now=NOW)
        with pytest.raises(appr.ApprovalRejected, match="no operator has approved"):
            appr.check(second, now=NOW)

    def test_equivalent_arguments_share_one_approval(self):
        # A model may send 1 or "1" and mean the same thing; two plans for one
        # intent would make an operator approve the same action twice.
        a = a_plan(to="+911111111111", count=1)
        b = a_plan(to="+911111111111", count="1")
        assert a.plan_hash == b.plan_hash

    def test_refuses_a_plan_altered_after_it_was_built(self):
        plan = a_plan()
        tampered = plan_module.Plan(
            tool=plan.tool, tool_class=plan.tool_class,
            catalog_version=plan.catalog_version,
            arguments={"to": "+919999999999", "content": "hello"},
            created_at=plan.created_at, plan_hash=plan.plan_hash,
            idempotency_key=plan.idempotency_key)
        with pytest.raises(appr.ApprovalRejected, match="altered"):
            appr.grant(tampered, approved_by="manish", now=NOW)

    def test_refuses_a_plan_from_another_catalog_version(self):
        plan = a_plan()
        stale = plan_module.Plan(
            tool=plan.tool, tool_class=plan.tool_class,
            catalog_version="0", arguments=plan.arguments,
            created_at=plan.created_at, plan_hash=plan.plan_hash,
            idempotency_key=plan.idempotency_key)
        with pytest.raises(appr.ApprovalRejected, match="catalog version"):
            appr.grant(stale, approved_by="manish", now=NOW)


class TestSingleUse:
    def test_consume_succeeds_once(self):
        plan = a_plan()
        appr.grant(plan, approved_by="manish", now=NOW)
        used = appr.consume(plan, now=NOW)
        assert used.is_consumed()

    def test_second_consume_is_refused(self):
        # Without this an approval is a replay token: one yes, a thousand sends,
        # and a receipt trail that looks legitimate.
        plan = a_plan()
        appr.grant(plan, approved_by="manish", now=NOW)
        appr.consume(plan, now=NOW)
        with pytest.raises(appr.ApprovalRejected, match="already been used"):
            appr.consume(plan, now=NOW)

    def test_check_does_not_consume(self):
        plan = a_plan()
        appr.grant(plan, approved_by="manish", now=NOW)
        appr.check(plan, now=NOW)
        appr.check(plan, now=NOW)
        # Still spendable, because check is for showing an operator what is pending.
        assert appr.consume(plan, now=NOW).is_consumed()

    def test_a_concurrent_winner_leaves_the_loser_with_nothing(self):
        """The race single-use exists to lose safely."""
        plan = a_plan()
        appr.grant(plan, approved_by="manish", now=NOW)

        class TakenInBetween(appr.InMemoryApprovalStore):
            def consume(self, plan_hash, now):
                return None  # somebody else won

        store = TakenInBetween()
        store.put(appr.Approval(
            plan_hash=plan.plan_hash, tool=plan.tool,
            catalog_version=plan.catalog_version, approved_by="manish",
            approved_at=NOW, expires_at=NOW + 900))
        appr.set_store(store)
        with pytest.raises(appr.ApprovalRejected, match="another request"):
            appr.consume(plan, now=NOW)


class TestExpiry:
    def test_an_expired_approval_is_refused(self):
        plan = a_plan()
        appr.grant(plan, approved_by="manish", ttl_seconds=60, now=NOW)
        with pytest.raises(appr.ApprovalRejected, match="expired"):
            appr.check(plan, now=NOW + 61)

    def test_it_is_usable_inside_the_window(self):
        plan = a_plan()
        appr.grant(plan, approved_by="manish", ttl_seconds=60, now=NOW)
        assert appr.check(plan, now=NOW + 59).approved_by == "manish"

    def test_expiry_is_inclusive_at_the_boundary(self):
        plan = a_plan()
        appr.grant(plan, approved_by="manish", ttl_seconds=60, now=NOW)
        with pytest.raises(appr.ApprovalRejected, match="expired"):
            appr.check(plan, now=NOW + 60)

    def test_the_default_window_is_short(self):
        # A long default turns an approval into a licence.
        assert 0 < appr.DEFAULT_TTL_SECONDS <= 3600


class TestFailsClosed:
    def test_a_missing_approval_refuses(self):
        with pytest.raises(appr.ApprovalRejected, match="no operator has approved"):
            appr.check(a_plan(), now=NOW)

    def test_a_broken_store_refuses_rather_than_passing(self):
        class Broken(appr.InMemoryApprovalStore):
            def get(self, plan_hash):
                raise RuntimeError("table gone")

        appr.set_store(Broken())
        with pytest.raises(appr.ApprovalRejected, match="could not be read"):
            appr.check(a_plan(), now=NOW)

    def test_a_store_that_fails_on_consume_applies_nothing(self):
        plan = a_plan()

        class BrokenConsume(appr.InMemoryApprovalStore):
            def consume(self, plan_hash, now):
                raise RuntimeError("write failed")

        store = BrokenConsume()
        store.put(appr.Approval(
            plan_hash=plan.plan_hash, tool=plan.tool,
            catalog_version=plan.catalog_version, approved_by="manish",
            approved_at=NOW, expires_at=NOW + 900))
        appr.set_store(store)
        with pytest.raises(appr.ApprovalRejected, match="nothing was applied"):
            appr.consume(plan, now=NOW)

    def test_the_default_store_cannot_satisfy_a_later_invocation(self):
        # In production a Lambda's memory does not outlive the request, so the
        # default store refusing everything is the intended fail-safe.
        assert isinstance(appr.InMemoryApprovalStore(), appr.InMemoryApprovalStore)
        fresh = appr.InMemoryApprovalStore()
        assert fresh.get("anything") is None


class TestRefusalShape:
    def test_a_refusal_carries_no_key_that_looks_like_success(self):
        # The direct lesson of the placeholder createInvoice, which returned
        # {'success': True, 'invoiceId': ...} and wrote nothing.
        try:
            appr.check(a_plan(), now=NOW)
        except appr.ApprovalRejected as exc:
            result = exc.as_result()
        assert result["success"] is False
        assert result["refused"] is True
        for forbidden in ("messageId", "invoiceId", "sentAt", "id"):
            assert forbidden not in result

    def test_describe_omits_the_arguments(self):
        # Arguments may hold a phone number and a message body; plans.py already
        # owns the redaction rules and a second copy is a second thing to get wrong.
        plan = a_plan()
        approval = appr.grant(plan, approved_by="manish", now=NOW)
        described = appr.describe(approval)
        assert "arguments" not in described
        assert described["approvedBy"] == "manish"
        assert described["consumed"] is False


class TestBothGatesStillHold:
    def test_apply_is_refused_even_with_a_valid_approval(self):
        """The headline: this module enables nothing.

        Every APPLY tool is still enabled=False in the catalog, so an apply is
        refused for two independent reasons. Both have to change, separately and
        deliberately.
        """
        plan = a_plan()
        appr.grant(plan, approved_by="manish", now=NOW)
        with pytest.raises(gov.ToolRefused):
            appr.assert_may_apply(plan, now=NOW)

    def test_the_catalog_gate_reports_first(self):
        # A disabled tool must not report an approval problem, or somebody goes
        # hunting the wrong thing.
        plan = a_plan()
        with pytest.raises(gov.ToolRefused):
            appr.assert_may_apply(plan, now=NOW)

    def test_no_apply_tool_became_enabled(self):
        enabled = [n for n, t in gov.CATALOG.items()
                   if t.tool_class == gov.CLASS_APPLY and t.enabled]
        assert enabled == []

    def test_there_is_still_no_environment_variable_that_enables_an_apply(self,
                                                                         monkeypatch):
        for name in ("AGENT_ENABLE_APPLY", "AGENT_APPLY_ENABLED",
                     "AGENT_ENABLE_TOOLS", "AGENT_ALLOW_SEND",
                     "AGENT_APPROVALS_ENABLED"):
            monkeypatch.setenv(name, "true")
        assert gov.is_enabled(APPLY_TOOL) is False
