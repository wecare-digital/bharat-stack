"""The CRM API surface: auth posture, role gating, no scans, one payment vocabulary.

Measured before building, 2026-09-23: the API `zllr9lrg7j` carries 326 routes with **0**
gateway authorizers — 300 authenticate inside the handler, 5 are deliberately public, 0 are
OPEN. So the requirement "surface this through existing authorized APIs" means joining that
pattern on the same API, not standing up a new one, and `scripts/audit_route_auth.py` must
stay at 0 OPEN afterwards.

What these tests concentrate on is the handful of ways an internal API leaks or costs money:

* a route that forgets `require_auth`
* a write reachable by a Viewer
* an actor taken from the request body, so a user can attribute a stage change to a colleague
* a list endpoint with no required filter, which is a table scan wearing a nice URL
* five payment vocabularies reaching the caller unnormalised
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
CRM_DIR = ROOT / "amplify" / "functions" / "core" / "crm"
#: `CRM_DIR` is deliberately NOT added to sys.path. Every Lambda here has a `handler.py`, so
#: putting one of their directories on the path invites the same name collision this file
#: already hit once - see `_handler_module`.
for path in (str(SHARED), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

HANDLER_PATH = CRM_DIR / "handler.py"
PROVISION_PATH = ROOT / "scripts" / "provision_crm_api.py"


def code_only(path: Path) -> str:
    """Source with docstrings and comments stripped.

    The handler documents each decision in prose, so a naive substring search would report the
    documentation as the behaviour. Comments are blanked in place rather than by rejoining
    tokens - rejoining splits expressions across lines and makes these assertions unfailable,
    a mistake already made once in this repo.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    docstrings: set = set()
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            docstrings.update(range(first.lineno,
                                    (first.end_lineno or first.lineno) + 1))
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                if 1 <= row <= len(lines):
                    lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return "\n".join(line for n, line in enumerate(lines, start=1)
                     if n not in docstrings)


def provisioning():
    spec = importlib.util.spec_from_file_location("provision_crm_api", PROVISION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ===========================================================================
# Auth posture
# ===========================================================================

class TestAuthPosture:
    def test_the_handler_authenticates(self):
        code = code_only(HANDLER_PATH)
        assert "require_auth(event)" in code

    def test_auth_precedes_every_dispatch(self):
        """A route added below the gate inherits it; one added above would not."""
        code = code_only(HANDLER_PATH)
        gate = code.index("require_auth(event)")
        dispatch = code.index("def _route(")
        assert gate < dispatch, (
            "require_auth must run before any routing decision")
        # And the router itself must not be reachable from handler() before the gate.
        handler_body = code[code.index("def handler("):dispatch]
        assert handler_body.index("require_auth(event)") < handler_body.index("_route(")

    def test_writes_require_the_operator_role(self):
        code = code_only(HANDLER_PATH)
        assert "required_role=WRITE_ROLE" in code
        assert "WRITE_ROLE = 'Operator'" in code

    def test_the_role_gate_covers_every_mutating_method(self):
        """Gated once by method, so a new write route cannot be added without it."""
        code = code_only(HANDLER_PATH)
        for method in ("'POST'", "'PATCH'", "'PUT'", "'DELETE'"):
            assert method in code, f"{method} missing from the write-method gate"

    def test_options_is_answered_before_auth(self):
        """CORS preflight carries no Authorization header by design."""
        code = code_only(HANDLER_PATH)
        assert code.index("options_response(origin)") < code.index("require_auth(event)")

    def test_no_auth_skip_path_is_introduced(self):
        """Nothing in this surface is self-authenticating, so nothing may be exempt."""
        code = code_only(HANDLER_PATH)
        assert "AUTH_SKIP_PATHS" not in code
        assert "path_is_exempt" not in code

    def test_routes_are_registered_with_handler_level_auth(self):
        """Matches the 300 existing routes; audit_route_auth recognises this pattern."""
        module = provisioning()
        code = code_only(PROVISION_PATH)
        assert 'AuthorizationType="NONE"' in code
        assert len(module.ROUTES) == 12

    def test_no_proxy_route_hides_the_surface(self):
        """An explicit route per method is what lets the auth audit reason about each one."""
        module = provisioning()
        for route in module.ROUTES:
            assert "{proxy+}" not in route, f"{route} hides which methods exist"
            assert route.split(" ")[0] in ("GET", "POST", "PATCH", "PUT", "DELETE")

    def test_the_gateway_permission_is_scoped_to_this_api(self):
        """A wildcard SourceArn is invisible until a second API exists."""
        code = code_only(PROVISION_PATH)
        assert "execute-api:{REGION}:{ACCOUNT}:{API_ID}" in code

    def test_the_integration_targets_the_alias_not_latest(self):
        module = provisioning()
        assert module.function_arn().endswith(":live")
        assert module.function_arn(qualified=False).endswith(":wecare-crm")


# ===========================================================================
# The actor cannot be forged
# ===========================================================================

class TestActorComesFromTheToken:
    def test_actor_reads_the_verified_auth_context(self):
        code = code_only(HANDLER_PATH)
        assert "_auth" in code and "username" in code
        actor_fn = code[code.index("def _actor("):]
        actor_fn = actor_fn[:actor_fn.index("def ", 10)]
        assert "event.get('_auth')" in actor_fn
        assert "body" not in actor_fn, (
            "the actor must never come from the request body; that would let any "
            "authenticated user attribute a stage change to a colleague")

    def test_no_write_path_reads_an_actor_from_the_body(self):
        code = code_only(HANDLER_PATH)
        for forbidden in ("body.get('actor')", "body.get('actorId')",
                          'body.get("actor")', 'body.get("actorId")'):
            assert forbidden not in code, f"{forbidden} makes the audit trail forgeable"

    def test_every_service_write_passes_the_token_actor(self):
        code = code_only(HANDLER_PATH)
        for call in ("crm_service.capture_lead(", "crm_service.transition_lead(",
                     "crm_service.convert_lead(", "crm_service.move_opportunity(",
                     "crm_service.log_activity("):
            start = code.index(call)
            window = code[start:start + 700]
            assert "actor=actor" in window, f"{call} does not pass the token actor"


# ===========================================================================
# No scans
# ===========================================================================

class TestNoScans:
    def test_the_handler_never_scans(self):
        """The account already holds 75 tables; a scan behind a list URL is the cost line
        nobody can explain, and on a board view it would be one scan per column."""
        code = code_only(HANDLER_PATH)
        assert ".scan(" not in code

    def test_listing_leads_requires_a_filter(self):
        code = code_only(HANDLER_PATH)
        leads = code[code.index("def _leads("):code.index("def _lead(")]
        assert "state or contactId is required" in leads

    def test_listing_opportunities_requires_a_filter(self):
        code = code_only(HANDLER_PATH)
        start = code.index("def _opportunities(")
        block = code[start:code.index("def _opportunity(")]
        assert "stageId or contactId is required" in block

    def test_a_timeline_needs_exactly_one_subject(self):
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _activities("):code.index("def _log_activity(")]
        assert "exactly one of contactId, leadId or opportunityId" in block

    def test_payments_are_fetched_by_key_not_scanned(self):
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _payments_for_contact("):]
        assert "get_item(Key={'id': payment_id})" in block
        assert ".scan(" not in block

    def test_every_list_response_is_capped(self):
        module = _handler_module()
        assert module.MAX_LIMIT == 200
        assert module._limit({"limit": "100000"}) == 200
        assert module._limit({"limit": "-5"}) == 1
        assert module._limit({}) == module.DEFAULT_LIMIT
        assert module._limit({"limit": "abc"}) == module.DEFAULT_LIMIT


_CRM_HANDLER = None


def _handler_module():
    """Load the CRM handler under a unique module name.

    Loaded by explicit path rather than `import handler`, because dozens of Lambdas in this
    repo each have a `handler.py` and `sys.modules['handler']` resolves to whichever one an
    earlier test imported first. Running this file alone passed; running the full suite
    imported a different handler and the attribute lookups failed. A unique name removes the
    collision entirely.
    """
    global _CRM_HANDLER
    if _CRM_HANDLER is None:
        spec = importlib.util.spec_from_file_location("wecare_crm_handler", HANDLER_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CRM_HANDLER = module
    return _CRM_HANDLER


# ===========================================================================
# Payment vocabulary
# ===========================================================================

class TestOnePaymentVocabulary:
    def test_payment_state_is_normalised_on_read(self):
        """Four tables spell the same state five ways; Phase 4d left storage alone."""
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _payments_for_contact("):]
        assert "payment_status.canonical(" in block

    def test_the_raw_value_is_also_returned(self):
        """An operator reconciling against a provider console needs what was stored."""
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _payments_for_contact("):]
        assert "'paymentStateRaw'" in block
        assert "'stateRaw'" in block

    def test_amounts_are_integer_paise_plus_a_string(self):
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _payments_for_contact("):]
        assert "payment_status.paise(" in block
        assert "payment_status.rupees_str(" in block

    def test_paise_coercion_refuses_a_fractional_value(self):
        module = _handler_module()
        with pytest.raises(ValueError):
            module._paise_or_none(2500.5)
        assert module._paise_or_none(2500) == 2500
        assert module._paise_or_none(None) is None
        assert module._paise_or_none("") is None

    def test_decimals_are_made_json_safe_without_becoming_floats(self):
        from decimal import Decimal

        module = _handler_module()
        assert module._json_safe(Decimal("250000")) == 250000
        assert isinstance(module._json_safe(Decimal("250000")), int)
        assert module._json_safe(Decimal("2.5")) == 2.5
        assert module._json_safe({"a": [Decimal("1")]}) == {"a": [1]}
        # And the result must actually serialise.
        json.dumps(module._json_safe({"amountPaise": Decimal("250000")}))


# ===========================================================================
# Domain guards reaching the API
# ===========================================================================

class TestDomainGuardsAreSurfaced:
    def test_a_system_activity_kind_cannot_be_logged_by_a_user(self):
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _log_activity("):]
        assert "activity_kind_is_user_writable(" in block

    def test_the_lead_source_is_forced_not_taken_from_the_body(self):
        """A caller declaring WHATSAPP_INBOUND would mint a VERIFIED provenance claim."""
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _capture("):code.index("def _transition(")]
        assert "crm_keys.SOURCE_MANUAL" in block
        assert "body.get('source')" not in block

    def test_a_stale_write_returns_409_not_400(self):
        """The payload was fine and the row moved: re-read and retry, not fix the body."""
        code = code_only(HANDLER_PATH)
        assert code.count("cors_response(409") >= 3

    def test_a_repeated_conversion_is_200_with_the_existing_opportunity(self):
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _convert("):]
        assert "already_converted" in block
        assert "cors_response(200" in block

    def test_contact_ids_resolve_through_contact_key(self):
        """Callers may pass either spelling; CRM-KEY-001 is why that is explicit."""
        code = code_only(HANDLER_PATH)
        assert code.count("contact_key.resolve(") >= 4

    def test_a_diverged_contact_row_is_reported(self):
        code = code_only(HANDLER_PATH)
        assert "contact_key.assert_consistent(" in code
        assert "contact_key_mismatch" in code

    def test_a_missing_pipeline_says_how_to_fix_it(self):
        code = code_only(HANDLER_PATH)
        block = code[code.index("def _pipelines("):code.index("def _leads(")]
        assert "provision_crm_domain" in block
        assert "cors_response(503" in block


# ===========================================================================
# Provisioning shape
# ===========================================================================

class TestProvisioning:
    def test_no_credential_shaped_environment_variable(self):
        """This surface reads no provider credential at all."""
        module = provisioning()
        for key in module.ENVIRONMENT:
            assert not any(t in key.upper()
                           for t in ("PASSWORD", "SECRET", "TOKEN", "KEY")), key

    def test_environment_names_every_crm_table(self):
        module = provisioning()
        for suffix in ("CrmPipelines", "CrmStages", "CrmLeads",
                       "CrmOpportunities", "CrmActivities"):
            assert any(v.endswith(suffix) for v in module.ENVIRONMENT.values()), suffix

    def test_table_names_match_the_store_defaults(self):
        """A mismatch here points the API at tables that do not exist."""
        from lambda_utils.crm import store

        module = provisioning()
        assert module.ENVIRONMENT["CRM_LEADS_TABLE"] == store.LEADS_TABLE
        assert module.ENVIRONMENT["CRM_STAGES_TABLE"] == store.STAGES_TABLE
        assert module.ENVIRONMENT["CRM_PIPELINES_TABLE"] == store.PIPELINES_TABLE
        assert module.ENVIRONMENT["CRM_OPPORTUNITIES_TABLE"] == store.OPPORTUNITIES_TABLE
        assert module.ENVIRONMENT["CRM_ACTIVITIES_TABLE"] == store.ACTIVITIES_TABLE

    def test_routes_cover_every_entity(self):
        module = provisioning()
        joined = " ".join(module.ROUTES)
        for entity in ("/crm/pipelines", "/crm/leads", "/crm/opportunities",
                       "/crm/activities", "/crm/contacts/"):
            assert entity in joined, entity

    def test_the_function_is_in_the_deploy_map(self):
        """Otherwise the first provisioning deploy is also the last one."""
        deploy = (ROOT / "scripts" / "deploy_all_lambdas.py").read_text(encoding="utf-8")
        assert 'Spec("wecare-crm", "core/crm")' in deploy

    def test_provisioning_is_idempotent_by_construction(self):
        code = code_only(PROVISION_PATH)
        for guard in ("if function_exists():", 'return item["IntegrationId"], "exists"',
                      'results[route_key] = "exists"'):
            assert guard in code, guard

    def test_a_conflicting_route_is_reported_not_repointed(self):
        code = code_only(PROVISION_PATH)
        assert "CONFLICT" in code
