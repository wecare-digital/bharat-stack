"""Versioned tool catalog, immutable plans, idempotency, receipts and kill switches.

This is the governed path an APPLY would eventually travel. It is built now and
**every APPLY stays disabled**, so the machinery is exercised by these tests rather
than by a live side effect. Building it while nothing can use it is deliberate: the
alternative is building it under pressure, at the moment someone wants to turn a
send on.

The design decisions worth defending
-----------------------------------
A plan hash covers the tool, the catalog version and the arguments - and NOT the
timestamp. Two identical intents must produce the same key, because that is what
makes a retry idempotent. This is the `flow_completion` lesson repeated: a
deliberately coarse key merges two genuine requests *visibly*, while a key that is
too fine splits a retry and performs the side effect twice, invisibly. When the
side effect is a message to a customer or a payment, the second failure mode is the
one that costs money.

The catalog version is IN the hash. A plan approved under one version of the tool
definitions must not be applied under another, because the tool's meaning may have
changed underneath it. That is the whole content of the word "immutable" here.

Kill switches subtract only. An environment variable can turn a READ off; nothing
in the environment can turn an APPLY on. That asymmetry is the point - a switch
that could enable a send would be a live-send flag by another name, and the first
person to find it would throw it.

Receipts record refusals, not only successes. An audit trail that logs what worked
answers the wrong question; "what did the agent try to do" is what an operator
actually needs, and it was completely unavailable before.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

SHARED = pathlib.Path(__file__).resolve().parents[1] / "amplify/functions/shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.agent import governance as gov  # noqa: E402
from lambda_utils.agent import plans  # noqa: E402
from lambda_utils.agent import receipts  # noqa: E402

APPLY_TOOLS = tuple(sorted(t.name for t in gov.CATALOG.values()
                           if t.tool_class == gov.CLASS_APPLY))
READ_TOOLS = tuple(sorted(t.name for t in gov.CATALOG.values()
                          if t.tool_class == gov.CLASS_READ))


# ==========================================================================
# the catalog is versioned
# ==========================================================================
def test_the_catalog_has_a_version():
    assert isinstance(gov.CATALOG_VERSION, str)
    assert gov.CATALOG_VERSION.strip()


def test_the_version_is_not_a_timestamp():
    """A version that moves on every deploy invalidates every outstanding plan, so
    the mechanism would be abandoned within a week."""
    assert not gov.CATALOG_VERSION.replace("-", "").replace(".", "").isdigit() or \
        len(gov.CATALOG_VERSION) <= 8


def test_the_version_changes_when_the_catalog_changes(monkeypatch):
    """Not asserted by inspection - computed. A fingerprint over the tool names and
    classes, so adding or reclassifying a tool cannot silently keep the version."""
    before = plans.catalog_fingerprint()
    monkeypatch.setitem(gov.CATALOG, "somethingNew",
                        gov.Tool(name="somethingNew", tool_class=gov.CLASS_APPLY,
                                 enabled=False, summary="x", refusal="no",
                                 detail="because"))
    assert plans.catalog_fingerprint() != before


def test_the_fingerprint_ignores_prose(monkeypatch):
    """Rewording a refusal must not invalidate outstanding plans; reclassifying a
    tool must. The fingerprint covers name, class and enablement only."""
    before = plans.catalog_fingerprint()
    original = gov.CATALOG["sendSms"]
    monkeypatch.setitem(gov.CATALOG, "sendSms",
                        gov.Tool(name=original.name, tool_class=original.tool_class,
                                 enabled=original.enabled,
                                 summary="Reworded entirely.",
                                 refusal="Also reworded, at length.",
                                 detail="And the forensics too."))
    assert plans.catalog_fingerprint() == before

    monkeypatch.setitem(gov.CATALOG, "sendSms",
                        gov.Tool(name=original.name, tool_class=gov.CLASS_READ,
                                 enabled=original.enabled, summary=original.summary))
    assert plans.catalog_fingerprint() != before


# ==========================================================================
# plan hashes are deterministic and meaningful
# ==========================================================================
def test_the_same_intent_produces_the_same_hash():
    a = plans.build_plan("sendWhatsApp", {"phone": "+918100640044", "message": "hi"})
    b = plans.build_plan("sendWhatsApp", {"message": "hi", "phone": "+918100640044"})
    assert a.plan_hash == b.plan_hash, "argument order changed the hash"


def test_the_timestamp_is_not_in_the_hash():
    """Otherwise a retry is a different plan, and the idempotency key it derives is
    useless - which is how one intent becomes two messages."""
    a = plans.build_plan("sendSms", {"phone": "+918100640044"}, now=1_000_000)
    b = plans.build_plan("sendSms", {"phone": "+918100640044"}, now=9_999_999)
    assert a.plan_hash == b.plan_hash
    assert a.created_at != b.created_at


@pytest.mark.parametrize("mutation", [
    {"tool": "sendSms"},
    {"arguments": {"phone": "+918100640045"}},
    {"arguments": {"phone": "+918100640044", "message": "different"}},
    {"arguments": {}},
])
def test_a_different_intent_produces_a_different_hash(mutation):
    base = plans.build_plan("sendWhatsApp", {"phone": "+918100640044"})
    other = plans.build_plan(mutation.get("tool", "sendWhatsApp"),
                             mutation.get("arguments", {"phone": "+918100640044"}))
    assert other.plan_hash != base.plan_hash


def test_the_catalog_version_is_part_of_the_hash(monkeypatch):
    base = plans.build_plan("sendWhatsApp", {"phone": "+918100640044"})
    monkeypatch.setattr(gov, "CATALOG_VERSION", gov.CATALOG_VERSION + "-next")
    shifted = plans.build_plan("sendWhatsApp", {"phone": "+918100640044"})
    assert shifted.plan_hash != base.plan_hash


def test_the_hash_is_a_hex_digest_not_a_repr():
    plan = plans.build_plan("sendSms", {"phone": "+918100640044"})
    assert len(plan.plan_hash) == 64
    assert all(c in "0123456789abcdef" for c in plan.plan_hash)


def test_a_nested_argument_hashes_stably():
    a = plans.build_plan("createInvoice",
                         {"items": [{"sku": "b", "qty": 1}, {"sku": "a", "qty": 2}]})
    b = plans.build_plan("createInvoice",
                         {"items": [{"qty": 1, "sku": "b"}, {"qty": 2, "sku": "a"}]})
    assert a.plan_hash == b.plan_hash


def test_list_order_is_significant_because_it_can_be():
    """Key order in a mapping is not meaningful; element order in a list can be
    (line items, recipients). Reordering must therefore change the hash."""
    a = plans.build_plan("createInvoice", {"items": [{"sku": "a"}, {"sku": "b"}]})
    b = plans.build_plan("createInvoice", {"items": [{"sku": "b"}, {"sku": "a"}]})
    assert a.plan_hash != b.plan_hash


def test_an_unknown_tool_cannot_be_planned():
    with pytest.raises(gov.ToolUnknown):
        plans.build_plan("dropAllTables", {})


# ==========================================================================
# idempotency
# ==========================================================================
def test_the_idempotency_key_derives_from_the_plan_not_from_randomness():
    a = plans.build_plan("sendSms", {"phone": "+918100640044"})
    b = plans.build_plan("sendSms", {"phone": "+918100640044"})
    assert a.idempotency_key == b.idempotency_key
    assert a.plan_hash in a.idempotency_key


def test_the_idempotency_key_is_namespaced_by_tool():
    """So a collision cannot cross tools, and a key is readable in a log."""
    key = plans.build_plan("sendSms", {"phone": "+918100640044"}).idempotency_key
    assert key.startswith("sendSms#")


# ==========================================================================
# PLAN / dry-run: describes, never performs
# ==========================================================================
def test_a_plan_describes_what_would_happen_without_doing_it():
    plan = plans.build_plan("sendWhatsApp",
                            {"phone": "+918100640044", "message": "hello"})
    described = plans.describe_plan(plan)
    assert described["tool"] == "sendWhatsApp"
    assert described["toolClass"] == gov.CLASS_APPLY
    assert described["wouldApply"] is False
    assert described["planHash"] == plan.plan_hash
    assert described["catalogVersion"] == plan.catalog_version


def test_a_plan_description_masks_a_phone_number_but_the_hash_does_not():
    """Two claims that must both hold. The hash needs the real value or two
    different recipients collide into one plan; the description is logged and
    repeated, so it carries only the last four - the convention everywhere else in
    this codebase."""
    a = plans.build_plan("sendSms", {"phone": "+918100640044"})
    b = plans.build_plan("sendSms", {"phone": "+919876543210"})
    assert a.plan_hash != b.plan_hash, "the hash collapsed two recipients"

    described = plans.describe_plan(a)
    blob = str(described)
    assert "+918100640044" not in blob
    assert "918100640044" not in blob
    assert "0044" in blob, "the masked form should still be identifiable"


def test_a_plan_description_says_why_it_cannot_be_applied():
    described = plans.describe_plan(
        plans.build_plan("sendWhatsApp", {"phone": "+918100640044"}))
    assert described["refusal"].strip()


def test_planning_a_read_tool_is_pointless_and_says_so():
    """A READ has no plan/apply split - it just runs. Offering a plan for one
    invites a model to 'apply' a read and then narrate a side effect."""
    with pytest.raises(plans.PlanNotApplicable):
        plans.build_plan("getStats", {})


# ==========================================================================
# APPLY stays disabled — the load-bearing assertion of this item
# ==========================================================================
@pytest.mark.parametrize("tool", APPLY_TOOLS)
def test_no_plan_can_be_applied(tool):
    plan = plans.build_plan(tool, {"contactId": "c1"})
    with pytest.raises(gov.ToolRefused):
        plans.assert_plan_applicable(plan)


@pytest.mark.parametrize("env_name", [
    "AGENT_APPLY_ENABLED", "AGENT_ENABLE_APPLY", "AGENT_TOOLS_ENABLED",
    "AGENT_ENABLED_TOOLS", "AGENT_ALLOW_APPLY", "APPLY_ENABLED",
    "AGENT_TOOL_OVERRIDE", "AGENT_KILL_SWITCH", "AGENT_DISABLED_TOOLS",
])
def test_no_environment_variable_can_enable_an_apply(monkeypatch, env_name):
    """The asymmetry. A switch that could enable a send is a live-send flag by
    another name, and the first person to find it would throw it.

    Parameterised over plausible names rather than asserting the absence of one,
    because the failure mode is somebody ADDING such a variable later.
    """
    for value in ("1", "true", "TRUE", "yes", "all", "sendWhatsApp",
                  ",".join(APPLY_TOOLS)):
        monkeypatch.setenv(env_name, value)
        for tool in APPLY_TOOLS:
            assert gov.is_enabled(tool) is False, \
                f"{env_name}={value} enabled {tool}"
            with pytest.raises(gov.ToolRefused):
                gov.assert_executable(tool)


def test_the_source_contains_no_apply_enabling_flag():
    """A grep, because the test above can only cover names I thought of."""
    source = (SHARED / "lambda_utils/agent/governance.py").read_text()
    lowered = source.lower()
    for forbidden in ("apply_enabled", "enable_apply", "allow_apply",
                      "apply_allowed"):
        assert forbidden not in lowered, f"governance.py references {forbidden}"


# ==========================================================================
# kill switches subtract
# ==========================================================================
def test_a_read_tool_can_be_killed_by_name(monkeypatch):
    assert gov.is_enabled("getStats") is True
    monkeypatch.setenv("AGENT_DISABLED_TOOLS", "getStats")
    assert gov.is_enabled("getStats") is False
    assert gov.is_enabled("getContact") is True, "the kill was not surgical"


def test_the_disabled_list_tolerates_spacing_and_case(monkeypatch):
    monkeypatch.setenv("AGENT_DISABLED_TOOLS", "  GETSTATS , getContact ")
    assert gov.is_enabled("getStats") is False
    assert gov.is_enabled("getContact") is False


def test_the_global_kill_switch_stops_everything(monkeypatch):
    monkeypatch.setenv("AGENT_TOOLS_KILL_SWITCH", "true")
    for name in READ_TOOLS + APPLY_TOOLS:
        assert gov.is_enabled(name) is False


def test_a_killed_tool_refuses_with_a_distinguishable_reason(monkeypatch):
    """An operator needs to tell "switched off deliberately" from "never allowed"."""
    monkeypatch.setenv("AGENT_DISABLED_TOOLS", "getStats")
    with pytest.raises(gov.ToolRefused) as excinfo:
        gov.assert_executable("getStats")
    assert "kill switch" in excinfo.value.reason.lower()
    assert excinfo.value.tool_class == gov.CLASS_READ


def test_an_unset_kill_switch_changes_nothing(monkeypatch):
    monkeypatch.delenv("AGENT_DISABLED_TOOLS", raising=False)
    monkeypatch.delenv("AGENT_TOOLS_KILL_SWITCH", raising=False)
    for name in READ_TOOLS:
        assert gov.is_enabled(name) is True


def test_an_unknown_name_in_the_kill_list_is_ignored_not_fatal(monkeypatch):
    """A typo in an incident-response variable must not take the reads down."""
    monkeypatch.setenv("AGENT_DISABLED_TOOLS", "getStatz")
    assert gov.is_enabled("getStats") is True


# ==========================================================================
# receipts
# ==========================================================================
def test_a_receipt_links_to_the_plan_that_produced_it():
    plan = plans.build_plan("sendWhatsApp", {"phone": "+918100640044"})
    receipt = receipts.build_receipt(plan, result=receipts.RESULT_REFUSED,
                                     detail="APPLY is disabled")
    assert receipt["planHash"] == plan.plan_hash
    assert receipt["idempotencyKey"] == plan.idempotency_key
    assert receipt["catalogVersion"] == plan.catalog_version
    assert receipt["tool"] == "sendWhatsApp"


def test_a_receipt_records_a_refusal_not_only_a_success():
    """An audit trail that logs what worked answers the wrong question. "What did
    the agent try" is what an operator needs, and it was unavailable before."""
    plan = plans.build_plan("createInvoice", {"amount": "100"})
    receipt = receipts.build_receipt(plan, result=receipts.RESULT_REFUSED,
                                     detail="no")
    assert receipt["result"] == receipts.RESULT_REFUSED
    assert receipt["applied"] is False


def test_only_an_applied_result_sets_applied_true():
    plan = plans.build_plan("sendSms", {"phone": "+918100640044"})
    for result in (receipts.RESULT_REFUSED, receipts.RESULT_DUPLICATE,
                   receipts.RESULT_FAILED):
        assert receipts.build_receipt(plan, result=result)["applied"] is False
    assert receipts.build_receipt(plan, result=receipts.RESULT_APPLIED)["applied"] is True


def test_an_unknown_result_is_refused_rather_than_recorded():
    """A receipt saying something unrecognised happened is worse than no receipt."""
    plan = plans.build_plan("sendSms", {"phone": "+918100640044"})
    with pytest.raises(ValueError):
        receipts.build_receipt(plan, result="probably-fine")


def test_a_receipt_masks_the_phone_number():
    plan = plans.build_plan("sendWhatsApp", {"phone": "+918100640044",
                                             "message": "hello"})
    blob = str(receipts.build_receipt(plan, result=receipts.RESULT_REFUSED))
    assert "918100640044" not in blob
    assert "0044" in blob


def test_a_receipt_carries_no_message_body():
    """The body is customer content. A receipt proves WHAT was attempted, and the
    plan hash already identifies the exact body without reproducing it."""
    plan = plans.build_plan("sendWhatsApp",
                            {"phone": "+918100640044",
                             "message": "Your OTP is 445566"})
    blob = str(receipts.build_receipt(plan, result=receipts.RESULT_REFUSED))
    assert "445566" not in blob
    assert "OTP" not in blob


def test_recording_a_receipt_never_raises(monkeypatch):
    """Matches the existing audit helper's contract. Note the limit recorded in the
    module: fail-open is right for an audit of a refusal and NOT sufficient for a
    receipt of a real side effect - see the docstring."""
    plan = plans.build_plan("sendSms", {"phone": "+918100640044"})

    def boom(**kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(receipts.audit, "record_audit", boom)
    assert receipts.record_receipt(plan, result=receipts.RESULT_REFUSED) is None


def test_recording_goes_through_the_existing_audit_sink(monkeypatch):
    """Not a second parallel trail. AuditLogsTable already exists and already
    masks."""
    seen = {}
    monkeypatch.setattr(receipts.audit, "record_audit",
                        lambda **kw: seen.update(kw) or "log-1")
    plan = plans.build_plan("sendWhatsApp", {"phone": "+918100640044"})
    assert receipts.record_receipt(plan, result=receipts.RESULT_REFUSED) == "log-1"
    assert seen["action"] == "agent.tool.refused"
    assert seen["resource_id"] == plan.plan_hash


# ==========================================================================
# the handler surface: a refusal that carries a plan
# ==========================================================================
import importlib.util  # noqa: E402
import json as _json  # noqa: E402

_HANDLER_PATH = (pathlib.Path(__file__).resolve().parents[1]
                 / "amplify/functions/ai/agent-action-group/handler.py")


@pytest.fixture()
def agent(monkeypatch):
    spec = importlib.util.spec_from_file_location("agent_plans_under_test",
                                                  _HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakeTable:
        def __init__(self, name):
            self.name = name
            self.items = []

        def scan(self, **kwargs):
            return {"Items": list(self.items)}

        def query(self, **kwargs):
            return {"Items": list(self.items)}

        def get_item(self, Key):  # noqa: N803
            return {}

    class FakeClient:
        def describe_table(self, TableName):  # noqa: N803
            return {"Table": {"ItemCount": 1}}

    class FakeResource:
        class meta:  # noqa: N801
            client = FakeClient()

        def Table(self, name):  # noqa: N802
            return FakeTable(name)

    monkeypatch.setattr(module, "dynamodb", FakeResource())

    import lambda_utils.middleware as mw
    monkeypatch.setattr(mw, "require_auth", lambda event: None)

    # Capture receipts instead of writing to AuditLogsTable.
    written = []
    monkeypatch.setattr(receipts.audit, "record_audit",
                        lambda **kw: written.append(kw) or "log-1")
    module._written_receipts = written
    return module


def _call(agent, function=None, api_path=None, **params):
    event = {"actionGroup": "wecare-actions",
             "parameters": [{"name": k, "value": v} for k, v in params.items()]}
    if function:
        event["function"] = function
    if api_path:
        event["apiPath"] = api_path
    response = agent.handler(event, None)
    body = response["response"]["functionResponse"]["responseBody"]["TEXT"]["body"]
    return _json.loads(body)


def test_a_refused_send_comes_back_with_a_dry_run_plan(agent):
    """A bare "no" tells an agent nothing it can act on, and leaves it free to
    invent a narration. A hashed plan gives it something a person can approve."""
    result = _call(agent, function="sendWhatsApp",
                   phone="+918100640044", message="hello there")
    assert result["refused"] is True
    plan = result["plan"]
    assert plan["tool"] == "sendWhatsApp"
    assert plan["wouldApply"] is False
    assert len(plan["planHash"]) == 64
    assert plan["catalogVersion"] == gov.CATALOG_VERSION


def test_the_returned_plan_masks_the_number_and_omits_the_body(agent):
    result = _call(agent, function="sendWhatsApp",
                   phone="+918100640044", message="Your OTP is 445566")
    blob = str(result["plan"])
    assert "918100640044" not in blob
    assert "445566" not in blob
    assert "0044" in blob


def test_the_plan_hash_is_stable_across_two_identical_attempts(agent):
    """So a retry is recognisably the same intent rather than a second one."""
    first = _call(agent, function="sendSms", phone="+918100640044", message="x")
    second = _call(agent, function="sendSms", phone="+918100640044", message="x")
    assert first["plan"]["planHash"] == second["plan"]["planHash"]


def test_the_refusal_tells_the_agent_what_to_do_next(agent):
    result = _call(agent, function="sendEmail", email="a@b.test", message="hi")
    assert "do not state" in result["nextStep"].lower()


def test_a_refused_attempt_writes_a_receipt(agent):
    """Before this there was no trace at all, so a prompt repeatedly trying to send
    looked identical to a well-behaved one."""
    _call(agent, function="sendWhatsApp", phone="+918100640044", message="hi")
    assert len(agent._written_receipts) == 1
    written = agent._written_receipts[0]
    assert written["action"] == "agent.tool.refused"
    assert written["resource_type"] == "agent_tool"
    assert written["details"]["applied"] is False


def test_the_receipt_is_keyed_on_the_plan_hash(agent):
    result = _call(agent, function="sendSms", phone="+918100640044", message="hi")
    assert agent._written_receipts[0]["resource_id"] == result["plan"]["planHash"]


def test_a_receipt_failure_does_not_break_the_refusal(agent, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(receipts.audit, "record_audit", boom)
    result = _call(agent, function="sendSms", phone="+918100640044", message="hi")
    assert result["refused"] is True
    assert "plan" in result


def test_a_read_refused_by_the_kill_switch_gets_no_plan(agent, monkeypatch):
    """Manufacturing a plan for a read would imply it is a side effect awaiting
    approval."""
    monkeypatch.setenv("AGENT_DISABLED_TOOLS", "getStats")
    result = _call(agent, function="getStats")
    assert result["refused"] is True
    assert "plan" not in result
    assert "kill switch" in result["error"].lower()


def test_the_global_kill_switch_stops_the_reads_too(agent, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLS_KILL_SWITCH", "true")
    for tool in READ_TOOLS:
        assert _call(agent, function=tool)["refused"] is True


def test_list_tools_reports_the_catalog_and_its_version(agent):
    result = _call(agent, function="listTools")
    assert result["success"] is True
    assert result["catalogVersion"] == gov.CATALOG_VERSION
    assert set(result["enabled"]) == set(READ_TOOLS)
    assert set(result["refused"]) == set(APPLY_TOOLS)


def test_list_tools_says_retrying_will_not_help(agent):
    """A model told only "not permitted" retries. Saying so explicitly is cheaper
    than the retry loop."""
    assert "retrying" in _call(agent, function="listTools")["message"].lower()


def test_list_tools_leaks_no_topology(agent):
    blob = str(_call(agent, function="listTools")).lower()
    for leak in ("stack-wecare-digital", "wecare-outbound", "arn:aws", "dynamodb"):
        assert leak not in blob
