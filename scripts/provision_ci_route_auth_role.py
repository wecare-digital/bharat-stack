#!/usr/bin/env python3
"""Create the read-only OIDC role that `route-auth.yml`'s live-AWS job needs.

WHY IT WAS NEVER RUNNING. `.github/workflows/route-auth.yml` has two jobs. The
source-scanning half runs on every push and blocks. The `live-gate` half is guarded
by `if: vars.ROUTE_AUTH_ROLE_ARN != ''`, and that repository variable has never been
set -- `gh variable list` returns nothing -- so the job has silently reported
"skipped" since the day it was written. The guard is the right design (a fork must
not go red for a reason a contributor cannot fix), but it means the absence looks
identical to a pass in the checks list. Only the console-drift half can catch a
route added straight in the console, which is exactly the class of change the
source scan is blind to.

THE SUBJECT CLAIM USES REPOSITORY IDS, NOT NAMES. The two existing roles --
`GitHubActions-bharat-stack-docs-scraper` and `-seo-tools` -- pin

    repo:wecare-digital@319896805/bharat-stack@1342943014:ref:refs/heads/stack

and that is deliberate, not a leftover. GitHub's ID-qualified subject survives a
rename: the repo became `wecare-digital/wecare-digital` on 2026-09-27 and both roles
kept working, while the Amplify app -- which pinned the NAME -- stopped deploying
entirely and took the production frontend 17 commits stale. So this role pins the
same numeric owner and repository ids.

PERMISSIONS. Exactly the four calls `audit_route_auth.py` makes --
`apigatewayv2:GET` on the API collection plus `lambda:ListFunctions` -- and nothing
else. No `secretsmanager`, no write verb anywhere. `apigatewayv2:GET` is the one
coarse action the service offers for reads; it cannot mutate.

    python scripts/provision_ci_route_auth_role.py --plan
    python scripts/provision_ci_route_auth_role.py --apply
    python scripts/provision_ci_route_auth_role.py --verify
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import boto3
from botocore.exceptions import ClientError

ACCOUNT = "775261844268"
REGION = "us-east-1"
ROLE = "GitHubActions-wecare-digital-route-auth"
POLICY = "RouteAuthReadOnly"
OIDC_PROVIDER = f"arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"

OWNER_ID = "319896805"
REPO_ID = "1342943014"
OWNER = "wecare-digital"
REPO = "wecare-digital"
BRANCH = "stack"

SUBJECT = f"repo:{OWNER}@{OWNER_ID}/{REPO}@{REPO_ID}:ref:refs/heads/{BRANCH}"

TRUST = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Federated": OIDC_PROVIDER},
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": SUBJECT,
                }
            },
        }
    ],
}

PERMISSIONS = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ReadHttpApiTopology",
            "Effect": "Allow",
            # apigatewayv2 exposes reads as the single coarse action `GET`. It covers
            # get_apis / get_routes / get_integrations and can mutate nothing.
            "Action": "apigateway:GET",
            "Resource": f"arn:aws:apigateway:{REGION}::/apis*",
        },
        {
            "Sid": "ListFunctionsOnly",
            "Effect": "Allow",
            "Action": "lambda:ListFunctions",
            "Resource": "*",
        },
    ],
}


def _iam():
    return boto3.client("iam", region_name=REGION)


def _role_exists(iam) -> bool:
    try:
        iam.get_role(RoleName=ROLE)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchEntity":
            return False
        raise


def plan() -> int:
    iam = _iam()
    print(f"role   {ROLE}: {'EXISTS' if _role_exists(iam) else 'ABSENT'}")
    print(f"subject: {SUBJECT}")
    print("permissions: apigateway:GET on /apis*, lambda:ListFunctions")
    existing = subprocess.run(["gh", "variable", "list"], capture_output=True, text=True)
    print(f"repo variables now: {existing.stdout.strip() or '(none)'}")
    return 0


def apply() -> int:
    iam = _iam()

    if _role_exists(iam):
        iam.update_assume_role_policy(RoleName=ROLE, PolicyDocument=json.dumps(TRUST))
        print(f"updated trust policy on {ROLE}")
    else:
        iam.create_role(
            RoleName=ROLE,
            AssumeRolePolicyDocument=json.dumps(TRUST),
            Description=("Read-only role for route-auth.yml's live-AWS drift job. "
                         "Subject is pinned by repository ID so a rename cannot break it."),
            MaxSessionDuration=3600,
        )
        print(f"created {ROLE}")

    iam.put_role_policy(RoleName=ROLE, PolicyName=POLICY,
                        PolicyDocument=json.dumps(PERMISSIONS))
    print(f"attached inline policy {POLICY}")

    arn = f"arn:aws:iam::{ACCOUNT}:role/{ROLE}"
    # A role ARN is not a secret -- it grants nothing without the OIDC trust -- so it
    # belongs in a repository VARIABLE rather than a secret, which is also what the
    # workflow's `vars.` reference expects.
    result = subprocess.run(["gh", "variable", "set", "ROUTE_AUTH_ROLE_ARN", "--body", arn],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"gh variable set failed: {result.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"set repository variable ROUTE_AUTH_ROLE_ARN = {arn}")
    return verify()


def verify() -> int:
    iam = _iam()
    problems = []

    try:
        role = iam.get_role(RoleName=ROLE)["Role"]
    except ClientError as exc:
        print(f"role missing: {exc.response['Error']['Code']}", file=sys.stderr)
        return 1

    trust = role["AssumeRolePolicyDocument"]
    condition = trust["Statement"][0].get("Condition", {}).get("StringEquals", {})
    checks = {
        "trusts the GitHub OIDC provider":
            trust["Statement"][0]["Principal"].get("Federated") == OIDC_PROVIDER,
        "audience pinned to sts.amazonaws.com":
            condition.get("token.actions.githubusercontent.com:aud") == "sts.amazonaws.com",
        "subject pinned by repository id":
            condition.get("token.actions.githubusercontent.com:sub") == SUBJECT,
        "subject carries the numeric ids":
            REPO_ID in str(condition.get("token.actions.githubusercontent.com:sub", "")),
    }

    inline = iam.list_role_policies(RoleName=ROLE)["PolicyNames"]
    checks["only the one inline policy"] = inline == [POLICY]
    checks["no attached managed policies"] = not iam.list_attached_role_policies(
        RoleName=ROLE)["AttachedPolicies"]

    document = iam.get_role_policy(RoleName=ROLE, PolicyName=POLICY)["PolicyDocument"]
    actions = {s["Action"] if isinstance(s["Action"], str) else tuple(s["Action"])
               for s in document["Statement"]}
    checks["grants exactly the two read actions"] = actions == {
        "apigateway:GET", "lambda:ListFunctions"}
    checks["no write verb anywhere"] = not any(
        verb in json.dumps(document).lower()
        for verb in ("put", "delete", "update", "create", "invoke"))
    checks["no secretsmanager grant"] = "secretsmanager" not in json.dumps(document).lower()

    variables = subprocess.run(["gh", "variable", "list"], capture_output=True, text=True)
    checks["ROUTE_AUTH_ROLE_ARN is set"] = "ROUTE_AUTH_ROLE_ARN" in variables.stdout

    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'}  {name}")
        if not ok:
            problems.append(name)

    if problems:
        print(f"\n{len(problems)} check(s) failed", file=sys.stderr)
        return 1
    print("\nall checks passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--plan", action="store_true")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.apply:
        return apply()
    if args.verify:
        return verify()
    return plan()


if __name__ == "__main__":
    raise SystemExit(main())
