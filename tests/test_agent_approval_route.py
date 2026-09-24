"""`POST /ai/approvals` - the route that records a human's yes.

Why this needs its own tests rather than relying on `test_agent_approvals.py`: that
file tests the approval RULES with a plan handed to it directly. This file tests the
things only the route can get wrong, and each of them has a specific consequence:

* The gate is Admin, and it is checked BEFORE anything is written. A model reaching
  this path would make the plan/approve split theatre.
* The approver comes from the verified token, never the body. A body field would let
  a caller name their own approver and walk straight past `_normalise_approver`.
* The path match is on segment boundaries. The substring version of this test is what
  let `/wa-business/webhooks-anything` skip authentication entirely.
* The response must not read as "sent". Every APPLY tool is still disabled, so a
  granted approval changes nothing about what can happen, and the body has to say so.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify/functions/shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.agent import approvals as appr  # noqa: E402
from lambda_utils.agent import drafts  # noqa: E402
from lambda_utils.agent import governance as gov  # noqa: E402
from lambda_utils.agent import plans as plan_module  # noqa: E402

HANDLER_PATH = ROOT / "amplify/functions/ai/ai-generate-response/handler.py"
APPLY_TOOL = "send_whatsapp"
QA_NUMBER = "+918100640044"
OPERATOR = "manish@wecare.digital"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("aigen_route", HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def in_memory_stores(mod):
    """Swap the Dynamo stores the handler installs at import for in-memory ones.

    That the handler installs Dynamo stores at import is itself asserted below - it is
    the line that makes the production path work at all.
    """
    prev_appr, prev_draft = appr.get_store(), drafts.get_store()
    appr.set_store(appr.InMemoryApprovalStore())
    drafts.set_store(drafts.InMemoryDraftStore())
    yield
    appr.set_store(prev_appr)
    drafts.set_store(prev_draft)


@pytest.fixture
def admin(mod, monkeypatch):
    """An authenticated Admin. Mirrors what `require_auth` puts on the event."""
    def allow(event, required_role=None):
        allow.required_role = required_role
        event["_auth"] = {"username": "wecare.digital", "email": OPERATOR,
                          "role": "Admin", "groups": ["Admin"]}
        return None
    allow.required_role = None
    monkeypatch.setattr(mod, "require_auth", allow)
    return allow


def a_plan(**arguments):
    return plan_module.build_plan(
        APPLY_TOOL,
        arguments or {"to": QA_NUMBER, "content": "your order has shipped"})


def request(path="/ai/approvals", method="POST", body=None):
    return {
        "requestContext": {"apiId": "zllr9lrg7j", "stage": "$default",
                           "http": {"method": method, "path": path,
                                    "sourceIp": "1.2.3.4"}},
        "headers": {"authorization": "Bearer token", "origin":
                    "https://wecare.digital"},
        "body": json.dumps(body or {}),
    }


def call(mod, event):
    return mod.handler(event, None)


def parsed(response):
    return json.loads(response["body"])


class TestTheProductionStoresAreInstalled:
    def test_import_switches_both_stores_to_dynamodb(self, mod):
        # Without this line an operator's yes in one request is gone by the next
        # invocation and every apply refuses. It is the whole reason the table exists.
        spec = importlib.util.spec_from_file_location("aigen_probe", HANDLER_PATH)
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        assert type(appr.get_store()).__name__ == "DynamoApprovalStore"
        assert type(drafts.get_store()).__name__ == "DynamoDraftStore"


class TestRouting:
    def test_the_approvals_path_is_matched(self, mod):
        assert mod._is_approvals_path(request()) is True

    def test_the_status_subpath_is_matched(self, mod):
        assert mod._is_approvals_path(request("/ai/approvals/status")) is True

    def test_the_generate_path_is_not(self, mod):
        assert mod._is_approvals_path(request("/ai/generate")) is False

    @pytest.mark.parametrize("path", [
        "/ai/approvalsX", "/ai/approvals-anything", "/x/ai/approvals",
        "/ai/approval",
    ])
    def test_a_lookalike_path_is_not_matched(self, mod, path):
        # Segment boundaries, not substrings. The substring form of this test is the
        # defect `path_is_exempt` carries a scar from.
        assert mod._is_approvals_path(request(path)) is False

    def test_a_stage_prefixed_path_is_matched(self, mod):
        event = request("/prod/ai/approvals")
        event["requestContext"]["stage"] = "prod"
        assert mod._is_approvals_path(event) is True


class TestTheGate:
    def test_it_asks_for_admin_specifically(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        call(mod, request(body={"planHash": plan.plan_hash}))
        assert admin.required_role == "Admin", (
            "the approve route must require Admin; a signed-in Viewer approving a "
            "customer send is the gap this route exists to close")

    def test_a_refused_caller_gets_the_auth_response_and_nothing_is_written(
            self, mod, monkeypatch):
        denied = {"statusCode": 403, "headers": {}, "body": json.dumps(
            {"error": "Insufficient permissions"})}
        monkeypatch.setattr(mod, "require_auth",
                            lambda event, required_role=None: denied)

        plan = a_plan()
        drafts.record(plan)
        response = call(mod, request(body={"planHash": plan.plan_hash}))

        assert response["statusCode"] == 403
        assert appr.get_store().get(plan.plan_hash) is None

    def test_the_gate_runs_before_the_body_is_trusted(self, mod, monkeypatch):
        denied = {"statusCode": 401, "headers": {}, "body": "{}"}
        monkeypatch.setattr(mod, "require_auth",
                            lambda event, required_role=None: denied)
        # A body naming an approver and a plan that does not exist. If any of it were
        # processed before the gate, this would not come back as a bare 401.
        response = call(mod, request(body={"planHash": "f" * 64,
                                           "approvedBy": "agent"}))
        assert response["statusCode"] == 401

    def test_only_post_is_accepted(self, mod, admin):
        response = call(mod, request(method="GET"))
        assert response["statusCode"] == 405


class TestTheApproverComesFromTheToken:
    def test_the_verified_email_is_recorded(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        body = parsed(call(mod, request(body={"planHash": plan.plan_hash})))
        assert body["approval"]["approvedBy"] == OPERATOR

    def test_a_body_supplied_approver_is_ignored(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        body = parsed(call(mod, request(body={
            "planHash": plan.plan_hash,
            "approvedBy": "agent",
            "approved_by": "assistant",
            "operator": "model",
        })))
        # Had any of those been honoured, `_normalise_approver` would have refused -
        # so a success carrying the token's identity is the proof.
        assert body["approval"]["approvedBy"] == OPERATOR


class TestTheClientSendsAHashAndNothingElseThatMatters:
    def test_a_hash_alone_is_sufficient(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        body = parsed(call(mod, request(body={"planHash": plan.plan_hash})))
        assert body["success"] is True
        assert body["approval"]["planHash"] == plan.plan_hash

    def test_arguments_in_the_body_cannot_redirect_the_approval(self, mod, admin):
        plan = a_plan(to=QA_NUMBER, content="your order has shipped")
        drafts.record(plan)
        body = parsed(call(mod, request(body={
            "planHash": plan.plan_hash,
            "tool": "send_sms",
            "arguments": {"to": "+441234567890", "content": "pay this now"},
        })))
        # The draft decides, not the request. The approval must cover the intent the
        # server drafted and the operator was shown.
        assert body["approval"]["tool"] == APPLY_TOOL
        stored = appr.get_store().get(plan.plan_hash)
        assert stored is not None and stored.tool == APPLY_TOOL

    def test_a_missing_hash_refuses(self, mod, admin):
        body = parsed(call(mod, request(body={})))
        assert body["success"] is False and body["refused"] is True
        assert "planHash" in body["reason"]

    def test_an_undrafted_hash_refuses(self, mod, admin):
        body = parsed(call(mod, request(body={"planHash": "0" * 64})))
        assert body["refused"] is True
        assert "no drafted plan" in body["reason"]

    def test_a_stale_catalog_version_refuses_with_its_own_reason(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        body = parsed(call(mod, request(body={
            "planHash": plan.plan_hash, "catalogVersion": "1"})))
        assert body["refused"] is True
        assert "catalog version" in body["reason"]


class TestTheResponseDoesNotReadAsSent:
    def test_no_key_a_caller_could_read_as_a_completed_send(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        body = parsed(call(mod, request(body={"planHash": plan.plan_hash})))
        for key in ("messageId", "waMessageId", "sentAt", "sent", "delivered",
                    "invoiceId"):
            assert key not in body, (
                f"{key} in an approval response would read as a side effect; the "
                f"placeholder createInvoice that returned success and wrote nothing "
                f"is the reason this is asserted")

    def test_it_states_that_the_tool_is_still_disabled(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        body = parsed(call(mod, request(body={"planHash": plan.plan_hash})))
        assert body["stillDisabled"] is True
        assert body["plan"]["wouldApply"] is False
        assert "Nothing has been sent" in body["nextStep"]

    def test_the_recipient_is_masked_in_the_response(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        response = call(mod, request(body={"planHash": plan.plan_hash}))
        raw = response["body"]
        assert QA_NUMBER not in raw
        assert "your order has shipped" not in raw
        assert parsed(response)["plan"]["arguments"]["to"] == "...0044"

    def test_a_refusal_carries_no_side_effect_key(self, mod, admin):
        body = parsed(call(mod, request(body={"planHash": "0" * 64})))
        assert set(body) == {"success", "refused", "reason", "planHash"}


class TestStatusDoesNotConsume:
    def test_status_reports_a_pending_approval(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        call(mod, request(body={"planHash": plan.plan_hash}))

        body = parsed(call(mod, request("/ai/approvals/status",
                                        body={"planHash": plan.plan_hash})))
        assert body["success"] is True
        assert body["approval"]["consumed"] is False

    def test_status_twice_still_leaves_it_usable(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        call(mod, request(body={"planHash": plan.plan_hash}))
        for _ in range(3):
            call(mod, request("/ai/approvals/status",
                              body={"planHash": plan.plan_hash}))
        assert appr.check(plan).is_consumed() is False

    def test_status_on_an_unapproved_plan_refuses(self, mod, admin):
        plan = a_plan()
        drafts.record(plan)
        body = parsed(call(mod, request("/ai/approvals/status",
                                        body={"planHash": plan.plan_hash})))
        assert body["refused"] is True
        assert "approved" in body["reason"]


class TestFailsClosed:
    def test_a_broken_approval_store_refuses_without_leaking_the_error(
            self, mod, admin):
        class Exploding:
            def put(self, approval):
                raise RuntimeError("table stack-wecare-digital-Secret not found")

            def get(self, plan_hash):
                raise RuntimeError("table stack-wecare-digital-Secret not found")

            def consume(self, plan_hash, now):
                raise RuntimeError("boom")

        appr.set_store(Exploding())
        plan = a_plan()
        drafts.record(plan)
        response = call(mod, request(body={"planHash": plan.plan_hash}))
        raw = response["body"]

        body = json.loads(raw)
        assert body["success"] is False and body["refused"] is True
        # The message can carry a table name, so it is withheld.
        assert "stack-wecare-digital-Secret" not in raw

    def test_a_broken_draft_store_refuses(self, mod, admin):
        class Exploding:
            def put(self, row):
                raise RuntimeError("no")

            def get(self, key):
                raise RuntimeError("no")

        drafts.set_store(Exploding())
        body = parsed(call(mod, request(body={"planHash": "a" * 64})))
        assert body["success"] is False and body["refused"] is True

    def test_unparseable_body_refuses(self, mod, admin):
        event = request()
        event["body"] = "{not json"
        body = parsed(call(mod, event))
        assert body["refused"] is True


class TestTheRefusalPathMakesAPlanApprovable:
    def test_a_refused_apply_records_a_draft_the_route_can_load(self, mod):
        refused = None
        try:
            gov.assert_executable(APPLY_TOOL)
        except gov.ToolRefused as exc:
            refused = exc
        assert refused is not None, f"{APPLY_TOOL} is no longer refused"

        result = mod._refuse_internal_tool(
            refused, {"to": QA_NUMBER, "content": "hello"}, "req-1")

        assert result["success"] is False and result["refused"] is True
        assert result["approvable"] is True
        loaded = drafts.load(result["plan"]["planHash"])
        assert loaded.tool == APPLY_TOOL
        assert loaded.arguments["to"] == QA_NUMBER

    def test_the_refusal_still_masks_what_it_shows_the_model(self, mod):
        try:
            gov.assert_executable(APPLY_TOOL)
        except gov.ToolRefused as exc:
            refused = exc
        result = mod._refuse_internal_tool(
            refused, {"to": QA_NUMBER, "content": "hello"}, "req-2")
        assert result["plan"]["arguments"]["to"] == "...0044"
        assert QA_NUMBER not in json.dumps(result)

    def test_a_failed_draft_write_reports_not_approvable_rather_than_raising(
            self, mod):
        class Exploding:
            def put(self, row):
                raise RuntimeError("no")

            def get(self, key):
                return None

        drafts.set_store(Exploding())
        try:
            gov.assert_executable(APPLY_TOOL)
        except gov.ToolRefused as exc:
            refused = exc

        result = mod._refuse_internal_tool(refused, {"to": QA_NUMBER}, "req-3")
        # A draft that fails to save means the operator cannot approve. That is a
        # refusal, which is the safe direction, and it must not become an error.
        assert result["approvable"] is False
        assert result["refused"] is True
