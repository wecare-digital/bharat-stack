"""The checkout provisioning contract, pinned so a later edit has to be deliberate.

Why these assertions and not others
-----------------------------------
`scripts/provision_checkout.py` creates a function on the live payment path. Three of its
properties are the difference between "deployed and inert" and "deployed and chargeable", and
none of them is visible from reading the handler:

1. **The gate is absent from the environment the script sets.** Not `"false"` - absent. A key
   that exists is a key someone can flip with one `update-function-configuration`; an absent key
   plus two empty readiness inputs means two separate owner actions are required.
2. **The integration targets the `live` alias, and the invoke permission is qualified to it.** A
   function-level permission does not authorise an alias invoke, and the failure is a 500 with no
   Lambda log line at all - the function is never entered, so there is nothing to debug.
3. **The role grants no Razorpay credential read.** `razorpay_orders.RAZORPAY_SECRET_ID` defaults
   to `wecare/razorpay/api`, but nothing in the handler's import closure reaches it, so granting
   the read would widen privilege for code that cannot run.

The route-key list is pinned as an exact tuple rather than a membership check, because the
interesting failure is an ADDED route - a `{proxy+}` or a `GET` would widen the public surface
past the two consumers that exist.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "provision_checkout.py"
TEMPLATE = ROOT / "amplify" / "infra" / "checkout.json"


@pytest.fixture(scope="module")
def provisioner():
    spec = importlib.util.spec_from_file_location("provision_checkout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provision_checkout"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("provision_checkout", None)


# ── the gate ──────────────────────────────────────────────────────────────────

def test_the_initiation_flag_is_absent_not_false(provisioner):
    """Absent, so enabling it is an addition rather than an edit of an existing value."""
    env = provisioner.expected_environment()
    assert "CHECKOUT_INITIATION_ENABLED" not in env


def test_both_readiness_inputs_are_empty(provisioner):
    """The second, independent block. `payment_readiness.evaluate` returns
    CONFIGURATION_UNVERIFIED on an empty configuration name or MID, so flipping the gate alone
    still cannot produce a payable message."""
    env = provisioner.expected_environment()
    assert env["EXPECTED_CONFIGURATION_NAME"] == ""
    assert env["EXPECTED_PROVIDER_MID"] == ""


def test_no_environment_value_looks_like_a_credential(provisioner):
    """Secret NAMES only. The manifest this feeds is committed to the repository."""
    env = provisioner.expected_environment()
    assert env["WIX_API_KEY_SECRET"] == "wecare/wix/headless-api-key"
    issuer_shapes = ("rzp_live_", "rzp_test_", "sk-", "AIza", "ghp_", "xoxb-",
                     "AKIA", "ASIA", "sk_live_", "-----BEGIN")
    for key, value in env.items():
        for shape in issuer_shapes:
            assert shape not in value, f"{key} carries an issuer-shaped value"


# ── routes and the alias-qualified invoke ─────────────────────────────────────

def test_exactly_two_route_keys_and_no_proxy(provisioner):
    assert provisioner.ROUTE_KEYS == (
        "POST /ecommerce/checkout",
        "POST /ecommerce/checkout/status",
    )
    for key in provisioner.ROUTE_KEYS:
        assert "{" not in key, f"{key} is a greedy/path-parameter route"
        assert key.startswith("POST "), f"{key} widens the surface past POST"


def test_the_integration_targets_the_live_alias(provisioner):
    """`:live`, not `$LATEST`. The 58 aliased functions in this fleet all work this way, and
    `lambda-snapstart-deploy` steering requires the alias to be what production invokes."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "def function_arn(" in source
    assert 'f"{arn}:{LIVE_ALIAS}" if qualified else arn' in source
    assert 'IntegrationType="AWS_PROXY"' in source
    assert 'PayloadFormatVersion="2.0"' in source
    assert "function_arn(qualified=True)" in source


def test_the_invoke_permission_is_qualified_to_the_alias(provisioner):
    """Every `add_permission` call is alias-qualified and takes its SourceArn from `source_arn()`.

    Asserted over the AST rather than by looking for one spelling: the scope lives in
    `source_arn()`, and a test that insists on the literal `SourceArn=source_arn()` fails when the
    value is hoisted to a local even though the property is unchanged. What must not be possible is
    an unqualified statement, or a SourceArn assembled somewhere other than `source_arn()`.
    """
    import ast
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    grants = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "add_permission"]
    assert grants, "the provisioner grants no invoke permission at all"

    for call in grants:
        kwargs = {kw.arg: ast.unparse(kw.value) for kw in call.keywords}
        assert kwargs.get("Qualifier") == "LIVE_ALIAS", \
            f"line {call.lineno}: a function-level statement does not authorise an alias invoke"
        assert kwargs.get("Principal") == "'apigateway.amazonaws.com'"
        arn, sid = kwargs.get("SourceArn"), kwargs.get("StatementId")
        owner = next(f for f in ast.walk(tree)
                     if isinstance(f, ast.FunctionDef)
                     and f.lineno <= call.lineno <= (f.end_lineno or call.lineno))
        # A local is fine, as long as it is bound to the two helpers that own scope and identity.
        # Tuple targets are paired element-wise off the AST rather than by splitting the unparsed
        # text, which cannot be done safely once a value contains a comma of its own.
        bound = {}
        for assign in (n for n in ast.walk(owner) if isinstance(n, ast.Assign)):
            for target in assign.targets:
                if isinstance(target, ast.Tuple) and isinstance(assign.value, ast.Tuple) \
                        and len(target.elts) == len(assign.value.elts):
                    for element, value in zip(target.elts, assign.value.elts):
                        bound[ast.unparse(element)] = ast.unparse(value)
                else:
                    bound[ast.unparse(target)] = ast.unparse(assign.value)
        assert arn.startswith("source_arn(") or bound.get(arn, "").startswith("source_arn("), \
            f"line {call.lineno}: SourceArn={arn} does not come from source_arn()"
        assert sid.startswith("route_statement_id(") \
            or bound.get(sid, "").startswith("route_statement_id("), \
            f"line {call.lineno}: StatementId={sid} does not come from route_statement_id()"


def test_the_source_arn_holds_no_wildcard_at_all(provisioner, monkeypatch):
    """Narrowed twice on 2026-10-01, and the second step is the one that matters.

    `{API_ID}/*/*` authorised any stage and any method/path on this API - scoped to one API, so
    never a wildcard over the account, but 360 routes wider than the two that exist. The obvious
    replacement was the prefix `prod/POST/ecommerce/*`, and it was measured to be insufficient:
    another session had already added `POST /ecommerce/customer-session`, so the prefix matched a
    third route belonging to a different function. A prefix is a namespace somebody else can grow
    into.

    So: one statement per route key, each carrying that route's exact ARN. Asserted on the rendered
    value, so an edit that keeps the shape and widens the scope still fails.
    """
    monkeypatch.setattr(provisioner, "_account_id_cache", "775261844268")
    assert provisioner.API_ID == "zllr9lrg7j"
    assert provisioner.STAGE == "prod"

    rendered = {key: provisioner.source_arn(key) for key in provisioner.ROUTE_KEYS}
    assert rendered == {
        "POST /ecommerce/checkout":
            "arn:aws:execute-api:us-east-1:775261844268:zllr9lrg7j/prod/POST/ecommerce/checkout",
        "POST /ecommerce/checkout/status":
            "arn:aws:execute-api:us-east-1:775261844268:zllr9lrg7j/prod/POST/ecommerce/"
            "checkout/status",
    }
    for key, arn in rendered.items():
        assert "*" not in arn, f"{key} -> {arn} still carries a wildcard"

    # And the sibling route another session owns must NOT be covered by any of them.
    foreign = ("arn:aws:execute-api:us-east-1:775261844268:zllr9lrg7j/prod/POST/"
               "ecommerce/customer-session")
    assert foreign not in rendered.values()
    assert not any(foreign.startswith(arn.rstrip("*")) and arn.endswith("*")
                   for arn in rendered.values())


def test_one_statement_id_per_route_and_they_are_distinct(provisioner):
    ids = [provisioner.route_statement_id(k) for k in provisioner.ROUTE_KEYS]
    assert ids == ["apigateway-invoke-post-ecommerce-checkout",
                   "apigateway-invoke-post-ecommerce-checkout-status"]
    assert len(set(ids)) == len(ids), "two routes would share one statement"
    # Lambda accepts [a-zA-Z0-9-_]+ only; a '/' or ' ' here is a ValidationException at runtime.
    for sid in ids:
        assert all(c.isalnum() or c in "-_" for c in sid), sid
    assert not set(ids) & set(provisioner.LEGACY_STATEMENT_IDS)


def test_the_narrowing_adds_before_it_removes(provisioner):
    """`add_permission` cannot edit a statement, and remove-then-add under one id leaves a window
    where the routes resolve to a target API Gateway is not authorised to invoke - a 500 with no
    Lambda log line. So the narrow statements carry NEW ids, and the superseded ones come off only
    after they are in place."""
    assert provisioner.LEGACY_STATEMENT_IDS == (
        "apigateway-invoke-checkout", "apigateway-invoke-checkout-ecommerce")
    body = SCRIPT.read_text(encoding="utf-8") \
        .split("def ensure_invoke_permission")[1].split("\ndef ")[0]
    assert body.index("add_permission(") < body.index("remove_permission("), \
        "a superseded statement comes off before the narrow ones go on"


def test_verify_reads_every_invoke_statement_back(provisioner):
    """A missing statement, one scoped wider than its route, a superseded one left behind, or an
    EXTRA one nobody here created must all FAIL rather than be inferred from the routes existing."""
    body = SCRIPT.read_text(encoding="utf-8").split("def verify(")[1].split("\ndef ")[0]
    assert "live_policy_statements()" in body
    assert "LEGACY_STATEMENT_IDS" in body
    assert "_statement_source_arn(" in body
    assert "route_statement_id(" in body
    assert "unexpected" in body, "an extra statement would pass unnoticed"


def test_route_creation_never_deletes_or_retargets(provisioner):
    """Additive only. 359 pre-existing routes belong to other functions."""
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("delete_route", "delete_integration", "update_route",
                      "update_integration", "delete_function", "delete_alias"):
        assert forbidden not in source, f"provisioner calls {forbidden}"


# ── IAM: least privilege, and what it deliberately omits ──────────────────────

def _policy(provisioner) -> dict:
    """The inline policy document as the script writes it, without calling AWS."""
    source = SCRIPT.read_text(encoding="utf-8")
    body = source.split("least_privilege = ")[1].split("\n    iam().put_role_policy")[0]
    # The literal interpolates REGION, the account and five constants.
    namespace = {
        "REGION": provisioner.REGION, "acct": "775261844268",
        "WIX_API_KEY_SECRET": provisioner.WIX_API_KEY_SECRET,
        "PAYMENT_ATTEMPTS_TABLE": provisioner.PAYMENT_ATTEMPTS_TABLE,
        "COMMERCE_KEYS_TABLE": provisioner.COMMERCE_KEYS_TABLE,
        "SENDER_FUNCTION": provisioner.SENDER_FUNCTION,
        "LIVE_ALIAS": provisioner.LIVE_ALIAS,
    }
    return eval(body, {"__builtins__": {}}, namespace)  # noqa: S307 - our own source


def test_the_role_grants_no_razorpay_credential_read(provisioner):
    """Deliberate. `razorpay_orders` defaults to `wecare/razorpay/api`, but nothing in the
    handler's import closure reaches it - the website Razorpay path ships in the ZIP and is not
    wired in, pending the owner's architecture decision. This grant is the prerequisite for that
    decision, not something to pre-emptively hand over."""
    actions = json.dumps(_policy(provisioner))
    assert "wecare/razorpay/api" not in actions
    assert "razorpay" not in actions.lower()


def test_the_role_names_only_the_wix_secret(provisioner):
    secrets = [r for s in _policy(provisioner)["Statement"]
               if "secretsmanager:GetSecretValue" in s["Action"] for r in s["Resource"]]
    assert secrets == [
        "arn:aws:secretsmanager:us-east-1:775261844268:secret:wecare/wix/headless-api-key-*"]


def test_the_role_cannot_delete_a_payment_attempt(provisioner):
    """A failed attempt is the evidence that no charge became an order. Deleting one destroys
    the only record that the amount was refused."""
    actions = {a for s in _policy(provisioner)["Statement"] for a in s["Action"]}
    assert "dynamodb:DeleteItem" not in actions
    assert actions >= {"dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"}


def test_the_role_names_only_the_two_known_tables(provisioner):
    tables = [r for s in _policy(provisioner)["Statement"]
              for r in s["Resource"] if ":table/" in r]
    assert sorted(tables) == sorted([
        "arn:aws:dynamodb:us-east-1:775261844268:table/"
        "stack-wecare-digital-PaymentAttemptsTable",
        "arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-WixOrderIds"])
    for table in tables:
        assert not table.endswith("*"), f"{table} is a wildcard over the fleet's tables"


def test_the_role_holds_no_cognito_permission(provisioner):
    """`customer_auth.authenticate` calls GetUser with the CUSTOMER'S OWN access token, which
    authorises itself. An IAM grant here would be privilege the function cannot use."""
    assert "cognito" not in json.dumps(_policy(provisioner)).lower()


def test_the_shared_fleet_role_is_never_touched(provisioner):
    """`wecare-digital-lambda-role` is shared by ~65 functions. A statement added for checkout
    would widen every one of them.

    Asserted over the AST rather than the text, for the same reason
    `tests/test_payment_vocabulary_at_decision_points.py` walks the AST: the comment explaining
    why the shared role must not be touched necessarily contains its name. A text search makes
    the explanation indistinguishable from the offence.
    """
    import ast
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))

    # Docstrings are `ast.Constant` nodes too, so they have to come out explicitly - the very
    # prose explaining this rule mentions the role it forbids, which is the trap the AST was
    # supposed to avoid.
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = (node.body or [None])[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                docstrings.add(id(first.value))

    offenders = [f"line {n.lineno}: string literal names the shared role"
                 for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and id(n) not in docstrings
                 and "wecare-digital-lambda-role" in n.value]
    assert not offenders, "\n  ".join(offenders)

    # The property that actually matters: every RoleName the script passes is checkout's own.
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        for kw in call.keywords:
            if kw.arg == "RoleName":
                rendered = ast.unparse(kw.value)
                assert rendered in ("ROLE_NAME", "'wecare-checkout-role'"), \
                    f"line {call.lineno}: RoleName={rendered}"
    assert provisioner.ROLE_NAME == "wecare-checkout-role"


# ── the grant report reports, and never grants ────────────────────────────────

def test_the_grant_report_only_simulates(provisioner):
    """`report_required_grants` must never repair what it finds. An agent that widens a role to
    clear its own finding has removed the finding, not the risk."""
    source = SCRIPT.read_text(encoding="utf-8")
    body = source.split("def report_required_grants")[1].split("\ndef ")[0]
    assert "simulate_principal_policy" in body
    for forbidden in ("put_role_policy", "attach_role_policy", "put_user_policy",
                      "create_policy", "put_group_policy"):
        assert forbidden not in body, f"the grant report calls {forbidden}"


# ── and what it reports has to reach the exit code ────────────────────────────

class _FakeIam:
    """Just enough IAM to drive `report_required_grants` without touching an account."""

    def __init__(self, *, decisions=None, simulate_error=None, role_error=None):
        self.decisions = decisions or {}
        self.simulate_error = simulate_error
        self.role_error = role_error

    def get_role(self, RoleName):  # noqa: N803 - boto3 casing
        if self.role_error:
            raise self.role_error
        return {"Role": {"Arn": f"arn:aws:iam::775261844268:role/{RoleName}"}}

    def simulate_principal_policy(self, **kwargs):  # noqa: N803
        if self.simulate_error:
            raise self.simulate_error
        return {"EvaluationResults": [
            {"EvalActionName": action,
             "EvalDecision": self.decisions.get(action, "allowed")}
            for action in kwargs["ActionNames"]]}


def _client_error(code: str):
    from botocore.exceptions import ClientError
    return ClientError({"Error": {"Code": code, "Message": code}}, "Simulate")


@pytest.fixture
def grant_report(provisioner, monkeypatch):
    """`report_required_grants` with IAM and STS stubbed out."""
    monkeypatch.setattr(provisioner, "_account_id_cache", "775261844268")

    def _run(fake, members):
        monkeypatch.setattr(provisioner, "iam", lambda: fake)
        return provisioner.report_required_grants(members)
    return _run


_CLEAN_MEMBERS = {
    "handler.py": b"from lambda_utils import a\n",
    "lambda_utils/__init__.py": b"",
    "lambda_utils/a.py": b"table.update_item(ConditionExpression='attribute_not_exists(pk)')\n",
}
_TRANSACTING_MEMBERS = {
    "handler.py": b"from lambda_utils import a\n",
    "lambda_utils/__init__.py": b"",
    "lambda_utils/a.py": b"client.transact_write_items(TransactItems=[])\n",
}


def test_a_measured_and_sufficient_role_reports_no_problem(grant_report):
    """The baseline: ConditionCheckItem denied, nothing in the closure needs it."""
    fake = _FakeIam(decisions={"dynamodb:ConditionCheckItem": "implicitDeny"})
    assert grant_report(fake, _CLEAN_MEMBERS) == []


def test_a_required_grant_is_returned_so_verify_can_fail_on_it(grant_report):
    """The defect this test exists for: the finding used to PRINT and the script exited 0, so the
    day a TransactWriteItems call enters the closure the operator gets a function missing a
    permission and a gate reporting success. Latent is not harmless - it is wrong in exactly the
    circumstance the check was written for."""
    fake = _FakeIam(decisions={"dynamodb:ConditionCheckItem": "implicitDeny"})
    problems = grant_report(fake, _TRANSACTING_MEMBERS)
    assert problems, "a REQUIRED GRANT must be returned, not only printed"
    assert any("ConditionCheckItem" in p for p in problems)
    assert any("lambda_utils/a.py" in p for p in problems), \
        "the finding must name the call site, or it is not actionable"


def test_an_unmeasured_simulation_is_a_problem_not_a_pass(grant_report):
    """A run that measured nothing must not be indistinguishable from one that measured
    everything and found nothing."""
    fake = _FakeIam(simulate_error=_client_error("AccessDenied"))
    problems = grant_report(fake, _CLEAN_MEMBERS)
    assert problems and "NOT MEASURED" in problems[0]
    assert "AccessDenied" in problems[0]


def test_an_unreadable_role_is_a_problem_not_a_pass(grant_report):
    fake = _FakeIam(role_error=_client_error("NoSuchEntity"))
    problems = grant_report(fake, _CLEAN_MEMBERS)
    assert problems and "NOT MEASURED" in problems[0]


def test_an_unmeasured_import_closure_is_not_read_as_not_required(grant_report):
    """`members=None` means the package could not be rebuilt. The old code treated that as the
    empty list - "measured, needs nothing" - which is a different fact."""
    fake = _FakeIam(decisions={"dynamodb:ConditionCheckItem": "implicitDeny"})
    problems = grant_report(fake, None)
    assert problems and "NOT JUDGED" in problems[0]


def test_a_denied_action_the_inline_policy_grants_is_a_problem(grant_report):
    """GetItem/PutItem/UpdateItem are granted outright by CheckoutLeastPrivilege. A deny means the
    live role is not what this script wrote, and the function cannot record a payment attempt."""
    fake = _FakeIam(decisions={"dynamodb:PutItem": "implicitDeny",
                               "dynamodb:ConditionCheckItem": "implicitDeny"})
    problems = grant_report(fake, _CLEAN_MEMBERS)
    assert any("dynamodb:PutItem" in p for p in problems)


def test_verify_adds_the_grant_report_to_its_own_problem_list(provisioner):
    """The one-line fix, pinned. `verify()` called `report_required_grants(members)` and dropped
    the return value, so a REQUIRED GRANT printed while the function returned 0."""
    body = SCRIPT.read_text(encoding="utf-8").split("def verify(")[1].split("\ndef ")[0]
    assert "problems.extend(report_required_grants(members))" in body
    assert "\n    report_required_grants(members)\n" not in body, \
        "the return value is discarded again"
    # And the exit code is still driven by that list.
    assert "if problems:" in body and "return 1" in body


def test_condition_check_item_is_judged_on_the_import_closure(provisioner):
    """Scoped to what the handler can actually reach, not to the 112-file ZIP.

    `build_zip` ships the whole `lambda_utils` tree without pruning, so `crm/service.py` and
    `notifications/store.py` are present and both use `TransactWriteItems`. Neither is imported
    by checkout. Judging on the ZIP reported a `ConditionCheckItem` grant the function can never
    need - and a report that cries wolf is one nobody reads.
    """
    members = {
        "handler.py": b"from lambda_utils import a\n",
        "lambda_utils/__init__.py": b"",
        "lambda_utils/a.py": b"x = 1\n",
        "lambda_utils/unreached.py": b"client.transact_write_items()\n",
    }
    closure = provisioner.import_closure(members)
    assert "lambda_utils/a.py" in closure
    assert "lambda_utils/unreached.py" not in closure
    assert provisioner._package_needs_transactions(members) == []

    members["lambda_utils/a.py"] = b"client.transact_write_items()\n"
    assert provisioner._package_needs_transactions(members) != []


# ── packaging must be validated before the function is created ────────────────

def test_the_package_is_validated_before_create(provisioner):
    """`deploy_all_lambdas.py` validates only AFTER `get_function_configuration` succeeds, so for
    an absent function it takes the `awaiting_provisioning` branch and never validates. An
    unresolved import would therefore first appear as a cold-start `Unable to import module` on a
    real customer request."""
    source = SCRIPT.read_text(encoding="utf-8")
    build_at = source.index("zip_bytes, members, errors, warnings = build_package")
    create_at = source.index("print(f\"Lambda: {ensure_function(")
    assert build_at < create_at, "the package is built after the create call"
    assert "if report_package(zip_bytes, members, errors, warnings):\n        return 1" in source


def test_packaging_is_delegated_so_the_two_scripts_cannot_drift(provisioner):
    """One packer. This script creates the function; deploy_all_lambdas.py updates it forever
    after. Two packers meant the first package and every later one were assembled differently."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "dal.build_zip(spec)" in source
    assert "dal.validate(spec, members, frozenset())" in source
    assert 'dal.validate_handler(members, "handler.handler")' in source
    assert "_zip_package" not in source, "the private packer is back"


def test_source_root_lets_a_clean_archive_be_packaged(provisioner):
    """The shared working tree is routinely dirty with other sessions' edits. A package built
    from it ships a handler whose siblings are stale."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"--source-root"' in source
    body = source.split("def _deploy_module")[1].split("\ndef ")[0]
    # The globals must be re-pointed BEFORE a Spec is built: Spec.__init__ resolves its source
    # from the module-level FUNCTIONS at construction time.
    assert body.index("module.FUNCTIONS = functions") < body.index("return module")
    assert "dal.Spec(FUNCTION_NAME" in source.split("def build_package")[1]


def _synthetic_root(base):
    """A directory `is_repo_root` accepts, with nothing else in it."""
    handler = base / "amplify" / "functions" / "ecommerce" / "checkout" / "handler.py"
    handler.parent.mkdir(parents=True)
    handler.write_text("def handler(e, c):\n    return None\n")
    return base


def test_verify_defaults_to_the_deploy_export_not_the_working_tree(
        provisioner, tmp_path, monkeypatch):
    """`--verify` is a statement ABOUT the deployed artifact. Defaulting its closure to the working
    tree meant the verdict could be about a package nobody deployed - and in this repo that tree
    routinely carries three other sessions' uncommitted edits, all of which build_zip packages."""
    export = _synthetic_root(tmp_path / "deploy-export")
    monkeypatch.setattr(provisioner, "DEPLOY_SOURCE_ROOT", export)

    root, why = provisioner.resolve_source_root(None, prefer_deploy_export=True)
    assert root == export.resolve()
    assert "deploy export" in why

    # A provisioning run packages what the operator points it at, and says which that is.
    root, why = provisioner.resolve_source_root(None, prefer_deploy_export=False)
    assert root == provisioner.ROOT
    assert "WORKING TREE" in why


def test_an_explicit_source_root_always_wins(provisioner, tmp_path, monkeypatch):
    export = _synthetic_root(tmp_path / "deploy-export")
    given = _synthetic_root(tmp_path / "given")
    monkeypatch.setattr(provisioner, "DEPLOY_SOURCE_ROOT", export)
    root, why = provisioner.resolve_source_root(str(given), prefer_deploy_export=True)
    assert root == given.resolve()
    assert "command line" in why


def test_a_missing_deploy_export_falls_back_and_says_so(provisioner, tmp_path, monkeypatch):
    """`.scratch/` is gitignored, so on a fresh checkout the export is simply absent. Falling back
    is right; falling back silently is not - the verdict would read as being about the artifact."""
    monkeypatch.setattr(provisioner, "DEPLOY_SOURCE_ROOT", tmp_path / "does-not-exist")
    root, why = provisioner.resolve_source_root(None, prefer_deploy_export=True)
    assert root == provisioner.ROOT
    assert "WORKING TREE" in why and "not the deployed artifact" in why


def test_the_verdict_is_never_anonymous(provisioner):
    """Whichever root won, `verify` prints it. Finding the closure was judged from the wrong tree
    is only possible if the tree is named in the output."""
    source = SCRIPT.read_text(encoding="utf-8")
    verify_body = source.split("def verify(")[1].split("\ndef ")[0]
    assert "grant report closure:" in verify_body
    main_body = source.split("def main(")[1]
    assert "source_note=why" in main_body
    assert 'print(f"source root: {why}")' in main_body


# ── the IaC declaration matches what the script creates ───────────────────────

def test_the_template_declares_the_same_two_routes():
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    keys = sorted(r["Properties"]["RouteKey"] for r in template["Resources"].values()
                  if r["Type"] == "AWS::ApiGatewayV2::Route")
    assert keys == ["POST /ecommerce/checkout", "POST /ecommerce/checkout/status"]


def test_the_template_keeps_the_gate_absent():
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    env = (template["Resources"]["CheckoutFunction"]["Properties"]
           ["Environment"]["Variables"])
    assert "CHECKOUT_INITIATION_ENABLED" not in env
    assert env["EXPECTED_CONFIGURATION_NAME"] == ""
    assert env["EXPECTED_PROVIDER_MID"] == ""


def test_the_template_qualifies_every_invoke_permission():
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    permissions = {name: r["Properties"] for name, r in template["Resources"].items()
                   if r["Type"] == "AWS::Lambda::Permission"}
    assert len(permissions) == 2, "one statement per route - see WhyOneStatementPerRoute"
    for name, permission in permissions.items():
        assert permission["Qualifier"] == "live", name
        assert permission["Principal"] == "apigateway.amazonaws.com", name
        assert "SourceArn" in permission, \
            f"{name}: an unscoped permission lets any API invoke this"


def test_the_template_matches_the_route_arns_the_script_grants(provisioner, monkeypatch):
    """The template is the declaration of record. If it still carried `/*/*` after the script was
    narrowed, the record would describe a grant nobody holds."""
    monkeypatch.setattr(provisioner, "_account_id_cache", "775261844268")
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    declared = sorted(r["Properties"]["SourceArn"]["Fn::Sub"]
                      for r in template["Resources"].values()
                      if r["Type"] == "AWS::Lambda::Permission")
    # The template parameterises region/account/api; render the script's ARNs the same way.
    wanted = sorted(
        provisioner.source_arn(key)
        .replace("us-east-1", "${AWS::Region}", 1)
        .replace("775261844268", "${AWS::AccountId}", 1)
        .replace(provisioner.API_ID, "${ApiId}", 1)
        for key in provisioner.ROUTE_KEYS)
    assert declared == wanted
    for arn in declared:
        assert "*" not in arn.replace("${", ""), f"{arn} carries a wildcard"


def test_the_template_is_not_wired_into_the_amplify_backend():
    """HTTP API zllr9lrg7j is not CloudFormation-managed, and backend.ts states the Python
    Lambdas are not managed by Amplify Gen 2. Importing this template into `defineBackend` would
    create a second API and put a live payment function under a stack that can delete it."""
    backend = (ROOT / "amplify" / "backend.ts").read_text(encoding="utf-8")
    assert "infra/checkout" not in backend
    assert "checkout.json" not in backend


def test_the_manifest_records_the_function_without_the_gate():
    manifest = json.loads(
        (ROOT / "config" / "lambda-env-manifest.json").read_text(encoding="utf-8"))
    entry = manifest["functions"]["wecare-checkout"]
    assert "CHECKOUT_INITIATION_ENABLED" not in entry
    assert entry["EXPECTED_CONFIGURATION_NAME"] == ""
    assert entry["EXPECTED_PROVIDER_MID"] == ""
    assert entry["WIX_API_KEY_SECRET"] == "wecare/wix/headless-api-key"
    assert manifest["_functions"] == len(manifest["functions"])
    assert manifest["_variables"] == sum(len(v) for v in manifest["functions"].values())
