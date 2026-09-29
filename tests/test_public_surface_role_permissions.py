"""The public-surface role's policy must be the calls the scripts make. No more, no less.

WHY THIS EXISTS. `scripts/iam-public-surface-README.md` claims every action in
`iam-public-surface-permissions.json` is a call one of the two deploy scripts actually
makes. That claim was written by reading the source, and reading the source is exactly the
step that does not survive the next edit. When it was checked mechanically, on 2026-09-29,
it was wrong in both directions at once:

  * MISSING `apigateway:DELETE`. `deploy_mcp_server.py` calls `delete_route_settings` to
    drop throttle entries left behind by deleted routes - it has to, because UpdateStage
    validates the merged map and a stale key makes it unwritable. Without the grant, an
    `apply` run fails with AccessDenied AFTER `provision_legacy_redirects.py` has already
    rewritten the live Amplify rules. A half-applied deploy is the worst outcome available
    to this workflow, and it was one retired route away.
  * GRANTED BUT NEVER CALLED: `lambda:GetPolicy` and `lambda:GetAlias`. The README
    explained GetPolicy as what makes re-running idempotent. It is not: `add_permission`
    is wrapped in `except ResourceConflictException`. The grant was unused and the
    documented reason for it was fiction.

Neither is catastrophic on its own. Together they are the reason a hand-checked permission
list is not evidence. This test derives the list from the boto3 calls in the two scripts,
so adding a call fails until the policy and the README catch up, and removing one fails
until the grant goes.

No AWS call is made and no credential is read.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_FILE = ROOT / "scripts" / "iam-public-surface-permissions.json"
WORKFLOW = ROOT / ".github" / "workflows" / "public-surface-deploy.yml"

#: Which boto3 client each local variable holds, per script. Declared rather than inferred:
#: an inference that silently fails to spot a client would make this test pass by seeing
#: nothing, which is the failure mode it is here to prevent.
CLIENT_VARS = {
    "scripts/deploy_mcp_server.py": {"lam": "lambda", "api": "apigatewayv2", "amp": "amplify"},
    "scripts/provision_legacy_redirects.py": {"client": "amplify"},
}

#: (service, boto3 method) -> the IAM action it authorises against.
#:
#: API Gateway is the one that surprises people: its control plane, v1 and v2 alike, is
#: authorised as `apigateway:` plus an HTTP VERB. There is no `apigatewayv2:` IAM prefix,
#: so a policy naming `apigatewayv2:GetRoutes` is not tighter, it is malformed.
CALL_TO_ACTION = {
    ("lambda", "get_function"): "lambda:GetFunction",
    ("lambda", "get_function_configuration"): "lambda:GetFunctionConfiguration",
    # Both waiters used here poll GetFunctionConfiguration.
    ("lambda", "get_waiter"): "lambda:GetFunctionConfiguration",
    ("lambda", "create_function"): "lambda:CreateFunction",
    ("lambda", "update_function_code"): "lambda:UpdateFunctionCode",
    ("lambda", "update_function_configuration"): "lambda:UpdateFunctionConfiguration",
    ("lambda", "publish_version"): "lambda:PublishVersion",
    ("lambda", "create_alias"): "lambda:CreateAlias",
    ("lambda", "update_alias"): "lambda:UpdateAlias",
    ("lambda", "add_permission"): "lambda:AddPermission",
    ("apigatewayv2", "get_integrations"): "apigateway:GET",
    ("apigatewayv2", "get_routes"): "apigateway:GET",
    ("apigatewayv2", "get_stage"): "apigateway:GET",
    ("apigatewayv2", "create_integration"): "apigateway:POST",
    ("apigatewayv2", "create_route"): "apigateway:POST",
    ("apigatewayv2", "update_route"): "apigateway:PATCH",
    ("apigatewayv2", "update_stage"): "apigateway:PATCH",
    ("apigatewayv2", "delete_route_settings"): "apigateway:DELETE",
    ("amplify", "get_app"): "amplify:GetApp",
    ("amplify", "update_app"): "amplify:UpdateApp",
}

#: Calls that pass an execution role to Lambda, and therefore need iam:PassRole. It is not
#: a boto3 method of its own, which is precisely why it is easy to forget.
PASS_ROLE_CALLS = {("lambda", "create_function"), ("lambda", "update_function_configuration")}

WRITE_VERBS = ("create", "update", "delete", "put", "post", "patch", "publish", "add", "tag")


def _calls() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    unknown: set[str] = set()
    for relpath, variables in CLIENT_VARS.items():
        source = (ROOT / relpath).read_text(encoding="utf-8")
        for variable, service in variables.items():
            for method in re.findall(rf"\b{variable}\.([a-z_][a-z0-9_]*)\(", source):
                if (service, method) in CALL_TO_ACTION:
                    found.add((service, method))
                else:
                    unknown.add(f"{relpath}: {variable}.{method}() [{service}]")
    assert not unknown, (
        "unrecognised AWS calls. Map each to the IAM action it needs in CALL_TO_ACTION and "
        "grant it in scripts/iam-public-surface-permissions.json, or the deploy fails with "
        "AccessDenied at exactly the wrong moment:\n  " + "\n  ".join(sorted(unknown))
    )
    return found


@pytest.fixture(scope="module")
def policy() -> dict:
    return json.loads(POLICY_FILE.read_text(encoding="utf-8"))


def _granted(policy: dict) -> set[str]:
    granted: set[str] = set()
    for statement in policy["Statement"]:
        assert statement["Effect"] == "Allow", "a Deny here would need its own reasoning"
        action = statement["Action"]
        granted |= {action} if isinstance(action, str) else set(action)
    return granted


def test_policy_grants_exactly_what_the_scripts_call(policy):
    calls = _calls()
    needed = {CALL_TO_ACTION[call] for call in calls}
    if calls & PASS_ROLE_CALLS:
        needed.add("iam:PassRole")

    granted = _granted(policy)

    missing = sorted(needed - granted)
    assert not missing, (
        "the scripts make these calls and the policy does not allow them: " + ", ".join(missing)
    )

    unused = sorted(granted - needed)
    assert not unused, (
        "granted but never called. Either the call went away and the grant should follow, or "
        "the README's account of why it is there is fiction: " + ", ".join(unused)
    )


def test_pass_role_is_confined_to_lambda(policy):
    statements = [s for s in policy["Statement"] if "iam:PassRole" in
                  ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])]
    assert len(statements) == 1
    statement = statements[0]
    assert statement["Resource"].endswith(":role/wecare-digital-lambda-role"), (
        "PassRole must name the one execution role"
    )
    condition = statement.get("Condition", {}).get("StringEquals", {})
    assert condition.get("iam:PassedToService") == "lambda.amazonaws.com", (
        "without this condition the role can hand the execution role to any service"
    )


def test_nothing_is_granted_on_every_resource(policy):
    for statement in policy["Statement"]:
        resources = statement["Resource"]
        for resource in [resources] if isinstance(resources, str) else resources:
            assert resource != "*", f'{statement["Sid"]} grants on every resource'
            assert resource.startswith("arn:aws:"), f'{statement["Sid"]}: {resource!r}'


def test_destructive_api_gateway_verb_reaches_route_settings_only(policy):
    """DELETE is needed, and it is one wildcard away from deleting the API.

    `delete_route_settings` is the only destructive call either script makes. Granting
    `apigateway:DELETE` on `/apis/zllr9lrg7j*` - the shape the rest of the policy uses -
    would also permit deleting every route, every integration and the API itself, which is
    the whole public surface of this project.
    """
    for statement in policy["Statement"]:
        actions = ([statement["Action"]] if isinstance(statement["Action"], str)
                   else statement["Action"])
        if "apigateway:DELETE" not in actions:
            continue
        resources = statement["Resource"]
        for resource in [resources] if isinstance(resources, str) else resources:
            assert resource.endswith("/routesettings/*"), (
                f"apigateway:DELETE is scoped to {resource!r}, which reaches more than the "
                "stale route settings it exists for"
            )


def test_verify_mode_assumes_the_role_with_a_read_only_session_policy():
    """The safe mode must be unable to write, not merely written not to.

    One role, two assumptions: `verify` adds an inline session policy, which STS
    INTERSECTS with the role's policy, so it can only subtract. This asserts the session
    policy is real, contains no write action, and grants nothing the role itself does not
    already have - a session policy naming an action outside the role is dead weight that
    reads as a grant.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"inline-session-policy:\s*'(\{.*?\})'\s*$", workflow, re.M | re.S)
    assert match, "verify mode must assume the role with an inline session policy"
    session = json.loads(match.group(1))

    session_actions = _granted(session)
    assert session_actions, "an empty session policy would deny everything, including reads"

    for action in sorted(session_actions):
        verb = action.split(":", 1)[1].lower()
        assert not verb.startswith(WRITE_VERBS), f"verify session grants a write: {action}"

    role_actions = _granted(json.loads(POLICY_FILE.read_text(encoding="utf-8")))
    extra = sorted(session_actions - role_actions)
    assert not extra, (
        "the session policy names actions the role does not have, so they grant nothing and "
        "only mislead a reader: " + ", ".join(extra)
    )

    # And the reads the verify path actually performs must survive the intersection.
    for required in ("amplify:GetApp", "lambda:GetFunction",
                     "lambda:GetFunctionConfiguration", "apigateway:GET"):
        assert required in session_actions, f"verify cannot run without {required}"
