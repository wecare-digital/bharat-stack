#!/usr/bin/env python3
"""Provision and verify the customer checkout Lambda.

What it stands up
-----------------
- A least-privilege execution role: logs; read of the Wix admin API key secret; read/write on the
  payment-attempts table and the commerce-keys (reference reservation) table; and
  `lambda:InvokeFunction` on the WhatsApp business Lambda (used for the readiness payment-config
  read and, once initiation is enabled, the in-chat order_details send). It has NO Cognito IAM
  permission — `customer_auth.authenticate` calls `GetUser` with the *customer's own* access token,
  which authorises itself and needs no role permission. It has NO order-creation permission of any
  kind, because checkout never creates an order.
- The function `wecare-checkout`, then a published version and the `live` alias.
- The two HTTP API routes its only two consumers call, an `AWS_PROXY` integration pointing at the
  `live` alias, and the alias-qualified `lambda:AddPermission` that lets API Gateway invoke it.
  Without that last piece a route exists and answers 500 with no Lambda log line at all, because a
  function-level statement does not authorise an *alias* invoke — the exact failure
  `scripts/provision_missing_ui_routes.py` documents for `POST /plivo/dial-events`.

Initiation stays OFF. `CHECKOUT_INITIATION_ENABLED` is deliberately absent from the environment
this script sets, so the deployed function prepares attempts and reserves references but sends no
payable message until someone sets that flag on purpose. Readiness inputs
(`EXPECTED_CONFIGURATION_NAME`, `EXPECTED_PROVIDER_MID`) are also left empty here, so even if
initiation were flipped on, `payment_readiness` blocks until an owner supplies the values from a
live Meta/Razorpay read. There is no path from this script to a live charge.

Packaging is delegated, deliberately
------------------------------------
The ZIP is built by `scripts/deploy_all_lambdas.build_zip` and checked by its `validate` /
`validate_handler`, rather than by a private zip helper here. Two reasons, both load-bearing:

1. **The two scripts can no longer produce different bytes for the same function.** This script
   creates `wecare-checkout`; `deploy_all_lambdas.py` updates it forever after. A private packer
   here meant the first package and every later one were assembled by different code.
2. **Validation now happens BEFORE `create_function`.** `deploy_all_lambdas.py` calls
   `get_function_configuration` before `validate()`, so for an absent function it takes the
   `awaiting_provisioning` branch and never validates — its `--dry-run` could not check this
   function until after it existed. An unresolved import would therefore have surfaced as a
   cold-start `Unable to import module` on the first real request.

`--source-root` exists so the package can be built from a clean `git archive` of reviewed code
while the script itself runs from the working tree. The shared tree is routinely dirty with other
sessions' in-flight edits, and a package built from it would ship a handler whose siblings are
stale.

Usage:
    python scripts/provision_checkout.py --dry-run
    python scripts/provision_checkout.py --dry-run --source-root .scratch/deploy-checkout
    python scripts/provision_checkout.py --source-root .scratch/deploy-checkout
    python scripts/provision_checkout.py --verify

After first provision, normal code updates use:
    python scripts/deploy_all_lambdas.py wecare-checkout

Follows .kiro/steering/secret-handling.md: the Wix key is read by reference at runtime via a
SecretId name only; no credential is ever placed on a command line or in a log.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
FUNCTION_NAME = "wecare-checkout"
LIVE_ALIAS = "live"
ROLE_NAME = "wecare-checkout-role"

#: The account's single HTTP API ("wecare-digital-api") and its only stage, which auto-deploys.
#: There is no `$default` stage, so the raw execute-api host needs the `/prod` segment; the apex
#: `wecare.digital/api/*` rewrite supplies it.
API_ID = "zllr9lrg7j"
STAGE = "prod"

#: Exactly the two route keys this function's two consumers call — `src/pages/cart.tsx` POSTs
#: `/ecommerce/checkout` and `src/pages/checkout/status.tsx` POSTs `/ecommerce/checkout/status`.
#: Deliberately NOT a `{proxy+}`: the surface stays exactly as wide as its consumers, and
#: `handler._action` resolves `status` off the path suffix so both land on the right branch.
ROUTE_KEYS = (
    "POST /ecommerce/checkout",
    "POST /ecommerce/checkout/status",
)

#: One statement id, so re-running is idempotent rather than accumulating policy statements.
STATEMENT_ID = "apigateway-invoke-checkout"

ROOT = Path(__file__).resolve().parents[1]
FUNCTION_DIR = ROOT / "amplify/functions/ecommerce/checkout"
SHARED_DIR = ROOT / "amplify/functions/shared"

PAYMENT_ATTEMPTS_TABLE = "stack-wecare-digital-PaymentAttemptsTable"
COMMERCE_KEYS_TABLE = "stack-wecare-digital-WixOrderIds"
WIX_API_KEY_SECRET = "wecare/wix/headless-api-key"
WIX_SITE_ID = "fcd82f0c-9572-49c7-acfb-88fb05042ece"
SENDER_FUNCTION = "wecare-whatsapp-business-api"
PAYMENT_WABA_ID = "2094615664435155"

_account_id_cache = None


def account_id() -> str:
    global _account_id_cache
    if _account_id_cache is None:
        _account_id_cache = boto3.client(
            "sts", region_name=REGION).get_caller_identity()["Account"]
    return _account_id_cache


def iam():
    return boto3.client("iam")


def lam():
    return boto3.client("lambda", region_name=REGION)


def logs():
    return boto3.client("logs", region_name=REGION)


def api():
    return boto3.client("apigatewayv2", region_name=REGION)


def source_arn() -> str:
    """Any method, any stage on this API. Scoped to the one API, not to `*`."""
    return f"arn:aws:execute-api:{REGION}:{account_id()}:{API_ID}/*/*"


def function_arn(*, qualified: bool = True) -> str:
    arn = f"arn:aws:lambda:{REGION}:{account_id()}:function:{FUNCTION_NAME}"
    return f"{arn}:{LIVE_ALIAS}" if qualified else arn


def _not_found(exc: ClientError, *codes: str) -> bool:
    return exc.response.get("Error", {}).get("Code") in codes


def role_exists() -> bool:
    try:
        iam().get_role(RoleName=ROLE_NAME)
        return True
    except ClientError as exc:
        if _not_found(exc, "NoSuchEntity"):
            return False
        raise


def function_exists() -> bool:
    try:
        lam().get_function(FunctionName=FUNCTION_NAME)
        return True
    except ClientError as exc:
        if _not_found(exc, "ResourceNotFoundException"):
            return False
        raise


def _deploy_module(source_root: Path):
    """`scripts/deploy_all_lambdas.py` loaded by path, re-rooted at `source_root`.

    Loaded by path rather than imported, because `scripts/` is not a package. The four module
    globals are re-pointed BEFORE any `Spec` is constructed: `Spec.__init__` resolves
    `self.source` from the module-level `FUNCTIONS` at construction time, so a Spec built before
    the override would still read the working tree.
    """
    script = ROOT / "scripts" / "deploy_all_lambdas.py"
    loader = importlib.util.spec_from_file_location("deploy_all_lambdas", script)
    module = importlib.util.module_from_spec(loader)
    sys.modules["deploy_all_lambdas"] = module
    loader.loader.exec_module(module)

    functions = (source_root / "amplify" / "functions").resolve()
    if not (functions / "ecommerce" / "checkout" / "handler.py").is_file():
        raise FileNotFoundError(
            f"no checkout handler under {functions} — is --source-root a repo root?")
    module.FUNCTIONS = functions
    module.SHARED = functions / "shared"
    module.LAMBDA_UTILS = module.SHARED / "lambda_utils"
    module.STATIC_KB = module.SHARED / "static_knowledge_base.py"
    return module


def build_package(source_root: Path) -> tuple:
    """Return (zip_bytes, members, errors, warnings) for the checkout package.

    The validation is the point: an import the packaging step forgot is caught here, before
    `create_function`, instead of as a cold-start `Unable to import module` on a real request.
    `provided` is empty because this function has no layers — everything must resolve inside the
    package, or come from the python3.12 runtime / stdlib.
    """
    dal = _deploy_module(source_root)
    spec = dal.Spec(FUNCTION_NAME, "ecommerce/checkout",
                    provisioned_by="python scripts/provision_checkout.py")
    zip_bytes, members = dal.build_zip(spec)
    errors, warnings = dal.validate(spec, members, frozenset())
    errors += dal.validate_handler(members, "handler.handler")
    return zip_bytes, members, sorted(set(errors)), sorted(set(warnings))


def package_sha(zip_bytes: bytes) -> str:
    """base64(sha256(zip)) — the same value Lambda reports as `CodeSha256`."""
    return base64.b64encode(hashlib.sha256(zip_bytes).digest()).decode()


def report_package(zip_bytes: bytes, members: dict, errors: list, warnings: list) -> int:
    print(f"package: {len(members)} files, {len(zip_bytes)} bytes, "
          f"sha256 {package_sha(zip_bytes)}")
    for warning in warnings:
        print(f"  warning: {warning}")
    for error in errors:
        print(f"  ERROR: {error}")
    if errors:
        print(f"\nFAIL: {len(errors)} unresolved import(s) — refusing to create the function")
        return 1
    print(f"  imports: all resolve ({len(warnings)} guarded warning(s))")
    return 0


def ensure_role(dry_run: bool) -> str:
    if role_exists():
        return "exists"
    if dry_run:
        return "would create"

    assume = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }
    iam().create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(assume),
        Description="Customer checkout (headless WhatsApp/Razorpay) execution role",
        Tags=[{"Key": "Project", "Value": "WECARE.DIGITAL"},
              {"Key": "Purpose", "Value": "Checkout"}],
    )
    iam().attach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    acct = account_id()
    least_privilege = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ReadWixApiKey",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": [f"arn:aws:secretsmanager:{REGION}:{acct}:secret:{WIX_API_KEY_SECRET}-*"],
            },
            {
                "Sid": "PaymentAttemptAndCommerceKeys",
                "Effect": "Allow",
                # No DeleteItem: a checkout never deletes a payment attempt or a reservation — a
                # failed attempt is the evidence that no charge became an order.
                "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
                "Resource": [
                    f"arn:aws:dynamodb:{REGION}:{acct}:table/{PAYMENT_ATTEMPTS_TABLE}",
                    f"arn:aws:dynamodb:{REGION}:{acct}:table/{COMMERCE_KEYS_TABLE}",
                ],
            },
            {
                "Sid": "InvokeWhatsAppSender",
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": [
                    f"arn:aws:lambda:{REGION}:{acct}:function:{SENDER_FUNCTION}",
                    f"arn:aws:lambda:{REGION}:{acct}:function:{SENDER_FUNCTION}:{LIVE_ALIAS}",
                ],
            },
        ],
    }
    iam().put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="CheckoutLeastPrivilege",
        PolicyDocument=json.dumps(least_privilege),
    )
    return "created"


def ensure_log_group(dry_run: bool) -> str:
    name = f"/aws/lambda/{FUNCTION_NAME}"
    try:
        groups = logs().describe_log_groups(
            logGroupNamePrefix=name, limit=50).get("logGroups", [])
        exists = any(g.get("logGroupName") == name for g in groups)
    except ClientError:
        exists = False
    if not exists and dry_run:
        return "would create with 30-day retention"
    if not exists:
        logs().create_log_group(logGroupName=name, tags={
            "Project": "WECARE.DIGITAL", "Purpose": "Checkout"})
    if not dry_run:
        logs().put_retention_policy(logGroupName=name, retentionInDays=30)
    return "exists; retention verified" if exists else "created"


def expected_environment() -> dict:
    return {
        "PAYMENT_ATTEMPTS_TABLE": PAYMENT_ATTEMPTS_TABLE,
        "COMMERCE_KEYS_TABLE": COMMERCE_KEYS_TABLE,
        "WIX_API_KEY_SECRET": WIX_API_KEY_SECRET,
        "WIX_SITE_ID": WIX_SITE_ID,
        "SENDER_FUNCTION": f"{SENDER_FUNCTION}:{LIVE_ALIAS}",
        "PAYMENT_WABA_ID": PAYMENT_WABA_ID,
        # Deliberately empty: payment_readiness returns CONFIGURATION_UNVERIFIED until an owner sets
        # these from a live Meta/Razorpay read. No value here can enable a payment.
        "EXPECTED_CONFIGURATION_NAME": "",
        "EXPECTED_PROVIDER_MID": "",
        # CHECKOUT_INITIATION_ENABLED intentionally omitted -> initiation OFF.
    }


def ensure_function(dry_run: bool, zip_bytes: bytes) -> str:
    if function_exists():
        return "exists"
    if dry_run:
        return "would create"

    role_arn = iam().get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
    for attempt in range(8):
        try:
            lam().create_function(
                FunctionName=FUNCTION_NAME,
                Runtime="python3.12",
                Role=role_arn,
                Handler="handler.handler",
                Code={"ZipFile": zip_bytes},
                Description="Customer checkout: authoritative Wix total, readiness gate, "
                            "PaymentAttempt, in-chat handoff. Initiation off by default.",
                Timeout=20,
                MemorySize=256,
                Environment={"Variables": expected_environment()},
                Tags={"Project": "WECARE.DIGITAL", "Purpose": "Checkout"},
            )
            return "created"
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != \
                    "InvalidParameterValueException" or attempt == 7:
                raise
            time.sleep(2)
    raise RuntimeError("Lambda create retry exhausted")


def reconcile_environment(dry_run: bool) -> str:
    if not function_exists():
        return "function absent - nothing to reconcile"
    config = lam().get_function_configuration(FunctionName=FUNCTION_NAME)
    current = dict((config.get("Environment") or {}).get("Variables") or {})
    wanted = expected_environment()
    # Only ADD/repair the keys this script owns; never clobber an operator-set
    # CHECKOUT_INITIATION_ENABLED or a live-read EXPECTED_* value.
    drifted = {k: v for k, v in wanted.items()
               if k not in ("EXPECTED_CONFIGURATION_NAME", "EXPECTED_PROVIDER_MID")
               and current.get(k) != v}
    for k in ("EXPECTED_CONFIGURATION_NAME", "EXPECTED_PROVIDER_MID"):
        if k not in current:
            drifted[k] = wanted[k]
    if not drifted:
        return "env already correct"
    if dry_run:
        return f"would set {', '.join(sorted(drifted))}"
    current.update(drifted)
    lam().update_function_configuration(
        FunctionName=FUNCTION_NAME, Environment={"Variables": current})
    lam().get_waiter("function_updated_v2").wait(FunctionName=FUNCTION_NAME)
    return f"set {', '.join(sorted(drifted))}"


def ensure_live_alias(dry_run: bool) -> str:
    try:
        lam().get_alias(FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS)
        return "exists"
    except ClientError as exc:
        if not _not_found(exc, "ResourceNotFoundException"):
            raise
    if dry_run:
        return "would publish v1 and create live alias"
    published = lam().publish_version(
        FunctionName=FUNCTION_NAME, Description="initial checkout release (initiation off)")
    version = published["Version"]
    lam().get_waiter("function_active_v2").wait(
        FunctionName=FUNCTION_NAME, Qualifier=version)
    lam().create_alias(
        FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS, FunctionVersion=version,
        Description="Production checkout target")
    return f"created -> v{version}"


# ── HTTP API wiring ───────────────────────────────────────────────────────────

def ensure_invoke_permission(dry_run: bool) -> str:
    """Let API Gateway invoke the `live` alias. Qualified, which is the whole point.

    A function-level statement does NOT authorise an alias invoke. Getting this wrong produces a
    500 with no Lambda log line at all, because the function is never entered — see
    `scripts/provision_missing_ui_routes.ensure_permission`, which records the same trap costing a
    live route.
    """
    if dry_run:
        return f"would grant lambda:InvokeFunction on :{LIVE_ALIAS} to apigateway.amazonaws.com"
    try:
        lam().add_permission(
            FunctionName=FUNCTION_NAME,
            Qualifier=LIVE_ALIAS,
            StatementId=STATEMENT_ID,
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=source_arn(),
        )
        return f"granted on :{LIVE_ALIAS}"
    except ClientError as exc:
        if _not_found(exc, "ResourceConflictException"):
            return f"already granted on :{LIVE_ALIAS}"
        raise


def _all_items(method: str) -> list:
    client = api()
    paginate, items, token = getattr(client, method), [], None
    while True:
        kwargs = {"ApiId": API_ID, "MaxResults": "1000"}
        if token:
            kwargs["NextToken"] = token
        page = paginate(**kwargs)
        items.extend(page.get("Items", []))
        token = page.get("NextToken")
        if not token:
            return items


def find_integration(uri: str) -> str:
    for integration in _all_items("get_integrations"):
        if integration.get("IntegrationUri") == uri:
            return integration["IntegrationId"]
    return ""


def ensure_integration(dry_run: bool) -> tuple:
    """Reuse-or-create ONE AWS_PROXY integration pointing at the alias. Never modifies another."""
    uri = function_arn(qualified=True)
    existing = find_integration(uri)
    if existing:
        return existing, f"reusing {existing}"
    if dry_run:
        return "", f"would create AWS_PROXY -> {uri}"
    created = api().create_integration(
        ApiId=API_ID, IntegrationType="AWS_PROXY", IntegrationUri=uri,
        PayloadFormatVersion="2.0",
        Description="Customer checkout (initiation off by default)")
    return created["IntegrationId"], f"created {created['IntegrationId']} -> {uri}"


def ensure_routes(dry_run: bool, integration_id: str) -> str:
    """Create only missing route keys. Never deletes or retargets an existing route."""
    existing = {r["RouteKey"]: r["RouteId"] for r in _all_items("get_routes")}
    results = []
    for key in ROUTE_KEYS:
        if key in existing:
            results.append(f"{key} exists ({existing[key]})")
            continue
        if dry_run:
            results.append(f"would create {key}")
            continue
        made = api().create_route(
            ApiId=API_ID, RouteKey=key, Target=f"integrations/{integration_id}")
        results.append(f"created {key} ({made['RouteId']})")
    return "; ".join(results)


# ── IAM reachability report (never a grant) ───────────────────────────────────

#: DynamoDB actions the checkout path could plausibly need, and the verdict we expect.
_SIMULATED_ACTIONS = ("dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                      "dynamodb:ConditionCheckItem")


def import_closure(members: dict, entry: str = "handler.py") -> set:
    """Modules actually reachable from `entry` by following imports inside the package.

    Scoped to the closure rather than to the whole ZIP, and that distinction is the difference
    between a useful report and a false alarm. The package ships the ENTIRE `lambda_utils` tree —
    112 files — because `deploy_all_lambdas.build_zip` does not prune, so `crm/service.py` and
    `notifications/store.py` are present and both use `TransactWriteItems`. Neither is imported by
    the checkout handler. Scanning the ZIP therefore reports a `ConditionCheckItem` grant the
    function can never need, and a grant report that cries wolf is one nobody reads.
    """
    reachable, pending = set(), [entry]
    while pending:
        arcname = pending.pop()
        if arcname in reachable or arcname not in members:
            continue
        reachable.add(arcname)
        try:
            tree = ast.parse(members[arcname].decode("utf-8", "replace"), filename=arcname)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dotted = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    continue
                # `from lambda_utils.ecommerce import order_keys, payment_attempt` imports both the
                # package module and each named submodule; try every candidate and keep what exists.
                dotted = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            else:
                continue
            for name in dotted:
                stem = name.replace(".", "/")
                for candidate in (f"{stem}.py", f"{stem}/__init__.py"):
                    if candidate in members:
                        pending.append(candidate)
    return reachable


def _package_needs_transactions(members: dict) -> list:
    """Reachable call sites that would require `dynamodb:ConditionCheckItem`.

    `ConditionCheckItem` is only ever required inside `TransactWriteItems` / `TransactGetItems`;
    a plain `put_item`/`update_item` carrying a `ConditionExpression` needs `PutItem`/`UpdateItem`
    and nothing more. Conflating the two is what turns a working condition into a phantom
    permission gap.
    """
    needles = ("transact_write_items", "TransactWriteItems",
               "transact_get_items", "TransactGetItems", "ConditionCheckItem")
    hits = []
    for arcname in sorted(import_closure(members)):
        text = members[arcname].decode("utf-8", "replace")
        for needle in needles:
            if needle in text:
                hits.append(f"{arcname}: {needle}")
    return hits


def report_required_grants(members: dict | None) -> list:
    """Print a per-action verdict for the checkout role. REPORTS; never widens anything.

    Deliberately does not touch `wecare-digital-lambda-role`: that role is shared by the whole
    fleet, so a statement added for checkout would widen every other function too. Checkout has
    its own role, which is why a gap here is reportable rather than contagious.
    """
    acct = account_id()
    tables = [f"arn:aws:dynamodb:{REGION}:{acct}:table/{PAYMENT_ATTEMPTS_TABLE}",
              f"arn:aws:dynamodb:{REGION}:{acct}:table/{COMMERCE_KEYS_TABLE}"]
    try:
        role_arn = iam().get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
    except ClientError:
        print("iam: role absent — cannot simulate")
        return []

    verdicts, required = {}, []
    try:
        result = iam().simulate_principal_policy(
            PolicySourceArn=role_arn,
            ActionNames=list(_SIMULATED_ACTIONS),
            ResourceArns=tables,
        )
    except ClientError as exc:
        print(f"iam: simulate unavailable ({exc.response['Error']['Code']}) — "
              f"verdicts not measured")
        return []

    for item in result.get("EvaluationResults", []):
        verdicts.setdefault(item["EvalActionName"], set()).add(item["EvalDecision"])

    needed_by_code = _package_needs_transactions(members) if members else []
    for action in _SIMULATED_ACTIONS:
        decisions = verdicts.get(action, {"not evaluated"})
        decision = "allowed" if decisions == {"allowed"} else "/".join(sorted(decisions))
        note = ""
        if action == "dynamodb:ConditionCheckItem" and decision != "allowed":
            if needed_by_code:
                note = "  <-- REQUIRED GRANT"
                required.append(
                    f"dynamodb:ConditionCheckItem on {', '.join(tables)} — needed by "
                    + "; ".join(needed_by_code))
            else:
                note = ("  (not required: no TransactWriteItems/TransactGetItems anywhere in "
                        "the handler's import closure; a ConditionExpression on "
                        "put_item/update_item needs PutItem/UpdateItem only)")
        print(f"iam {action}: {decision}{note}")

    for line in required:
        print(f"REQUIRED GRANT: {line}")
    return required


def verify(members: dict | None = None) -> int:
    problems: list[str] = []
    if not function_exists():
        print("FAIL function missing")
        return 1
    try:
        alias = lam().get_alias(FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS)
    except ClientError:
        print("FAIL live alias missing")
        return 1

    live_config = lam().get_function_configuration(
        FunctionName=FUNCTION_NAME, Qualifier=alias["FunctionVersion"])
    live_env = (live_config.get("Environment") or {}).get("Variables") or {}
    for key in ("PAYMENT_ATTEMPTS_TABLE", "COMMERCE_KEYS_TABLE", "WIX_API_KEY_SECRET",
                "SENDER_FUNCTION", "PAYMENT_WABA_ID"):
        if live_env.get(key) != expected_environment()[key]:
            problems.append(f"env {key} mismatch on live (v{alias['FunctionVersion']})")

    initiation = str(live_env.get("CHECKOUT_INITIATION_ENABLED", "")).strip().lower()
    if initiation in ("1", "true", "yes", "on"):
        problems.append("CHECKOUT_INITIATION_ENABLED is ON — live payment initiation is enabled")

    # Readiness blocks independently of the gate. Both empty means `payment_readiness.evaluate`
    # returns CONFIGURATION_UNVERIFIED, so a flipped flag alone still cannot produce a payment.
    readiness_empty = not (live_env.get("EXPECTED_CONFIGURATION_NAME")
                           or live_env.get("EXPECTED_PROVIDER_MID"))

    print(f"function: present (live v{alias['FunctionVersion']})")
    print(f"initiation: {'ON' if initiation in ('1','true','yes','on') else 'OFF (expected)'}")
    print(f"readiness inputs: {'empty — blocks regardless of the gate' if readiness_empty else 'SET by an operator'}")
    print(f"sender: {SENDER_FUNCTION}:{LIVE_ALIAS}; WABA {PAYMENT_WABA_ID}")

    # Routes + integration: the half that turns a deployed function into a reachable endpoint.
    want_uri = function_arn(qualified=True)
    integrations = {i["IntegrationId"]: i.get("IntegrationUri", "")
                    for i in _all_items("get_integrations")}
    routes = {r["RouteKey"]: r for r in _all_items("get_routes")}
    for key in ROUTE_KEYS:
        route = routes.get(key)
        if not route:
            problems.append(f"route missing: {key}")
            continue
        target = str(route.get("Target") or "")
        uri = integrations.get(target.rsplit("/", 1)[-1], "")
        if uri != want_uri:
            problems.append(f"route {key} targets {uri or target!r}, not {want_uri}")
            continue
        print(f"route {key}: -> {want_uri}")
    print(f"routes on {API_ID}: {len(routes)} total, stage {STAGE}")

    report_required_grants(members)

    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\ncheckout provisioning verified (initiation disabled)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--source-root", default=str(ROOT), metavar="PATH",
        help="repo root to PACKAGE from (default: this checkout). Point it at a clean "
             "`git archive` export so a dirty shared tree cannot reach production.")
    args = parser.parse_args(argv)

    source_root = Path(args.source_root).expanduser().resolve()

    if args.verify:
        # Build the package too, so the grant report reasons about the shipped module set rather
        # than about the whole repo.
        try:
            _, members, _, _ = build_package(source_root)
        except Exception as exc:  # noqa: BLE001
            print(f"note: could not rebuild package for the grant report: {type(exc).__name__}")
            members = None
        return verify(members)

    print(f"region: {REGION}")
    print(f"source root: {source_root}")
    print(f"sender: {SENDER_FUNCTION}:{LIVE_ALIAS}; WABA {PAYMENT_WABA_ID}")
    print("initiation: OFF (CHECKOUT_INITIATION_ENABLED not set)")
    print(f"dry run: {args.dry_run}\n")

    zip_bytes, members, errors, warnings = build_package(source_root)
    if report_package(zip_bytes, members, errors, warnings):
        return 1
    print()

    print(f"role: {ensure_role(args.dry_run)}")
    print(f"log group: {ensure_log_group(args.dry_run)}")
    print(f"Lambda: {ensure_function(args.dry_run, zip_bytes)}")
    print(f"env: {reconcile_environment(args.dry_run)}")
    print(f"live alias: {ensure_live_alias(args.dry_run)}")
    print(f"invoke permission: {ensure_invoke_permission(args.dry_run)}")
    integration_id, integration_note = ensure_integration(args.dry_run)
    print(f"integration: {integration_note}")
    print(f"routes: {ensure_routes(args.dry_run, integration_id)}")

    if args.dry_run:
        print("\ndry run: nothing changed")
        return 0

    print("\nread-back verification:")
    return verify(members)


if __name__ == "__main__":
    raise SystemExit(main())
