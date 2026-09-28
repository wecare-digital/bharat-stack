#!/usr/bin/env python3
"""Create the OIDC role that `plivo-drift.yml` needs, scoped to one secret.

WHY THIS WAS HELD BACK, AND WHAT CHANGED. `plivo-drift.yml` is guarded by
`if: vars.PLIVO_DRIFT_ROLE_ARN != ''` and that variable has never been set, so the drift
job has reported SKIPPED since it was written -- the same failure mode as
`route-auth.yml`'s live gate, where absence is indistinguishable from a pass in the
checks list.

Unlike route-auth, this job needs `secretsmanager:GetSecretValue`. Granting GitHub
Actions the ability to read a live provider credential genuinely widens who can read it,
so it sat outside the standing grant and was reported as an owner decision rather than
done quietly. It is created here under explicit authorisation.

WHAT KEEPS IT NARROW. Three things, all asserted by `--verify`:

1. **One secret, by ARN.** `wecare/plivo/api` only -- the id
   `scripts/plivo_control_plane.py` actually reads. Not `wecare/plivo`, not
   `wecare/plivo-answer`, not a wildcard. A `Deny` on every other secret ARN backs the
   allow, so a future widening of the allow statement still fails.
2. **Read only.** `GetSecretValue` and `DescribeSecret`. No `Put`, no `Update`, no
   `Delete`, no `List` -- the role cannot even discover what other secrets exist.
3. **Branch `stack` of this repository, by numeric ID.** `repo:*@319896805/*@1342943014:
   ref:refs/heads/stack` plus `repository_id` / `repository_owner_id` as their own
   condition keys. Names are excluded deliberately: the rename on 2026-09-27 broke every
   policy that pinned a name, and ids cannot be recycled by a namespace grab.

The drift job is read-only by construction -- it compares live Plivo configuration
against the committed expectation and reports -- so this grant cannot mutate either side.

    python scripts/provision_ci_plivo_drift_role.py --plan
    python scripts/provision_ci_plivo_drift_role.py --apply
    python scripts/provision_ci_plivo_drift_role.py --verify
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
ROLE = "GitHubActions-wecare-digital-plivo-drift"
POLICY = "PlivoSecretReadOnly"
OIDC_PROVIDER = f"arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"

OWNER_ID = "319896805"
REPO_ID = "1342943014"
BRANCH = "stack"

#: The exact secret `scripts/plivo_control_plane.py` reads (`SECRET_ID`). The trailing
#: `-??????` matches Secrets Manager's 6-character suffix without widening to a prefix
#: match, so `wecare/plivo/api-anything-else` cannot satisfy it.
SECRET_ARN = f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:wecare/plivo/api-??????"

TRUST = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "GitHubActionsStackBranchByRepositoryId",
            "Effect": "Allow",
            "Principal": {"Federated": OIDC_PROVIDER},
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:repository_id": REPO_ID,
                    "token.actions.githubusercontent.com:repository_owner_id": OWNER_ID,
                },
                "StringLike": {
                    "token.actions.githubusercontent.com:sub":
                        f"repo:*@{OWNER_ID}/*@{REPO_ID}:ref:refs/heads/{BRANCH}",
                },
            },
        }
    ],
}

PERMISSIONS = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ReadOnlyThePlivoApiSecret",
            "Effect": "Allow",
            "Action": ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
            "Resource": SECRET_ARN,
        },
        {
            # Belt and braces: even if the allow above is widened by accident, this keeps
            # the role to the one secret it was created for.
            "Sid": "DenyEveryOtherSecret",
            "Effect": "Deny",
            "Action": "secretsmanager:*",
            "NotResource": SECRET_ARN,
        },
    ],
}


def _iam():
    return boto3.client("iam", region_name=REGION)


def _exists(iam) -> bool:
    try:
        iam.get_role(RoleName=ROLE)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchEntity":
            return False
        raise


def plan() -> int:
    iam = _iam()
    print(f"role   {ROLE}: {'EXISTS' if _exists(iam) else 'ABSENT'}")
    print(f"secret {SECRET_ARN}")
    print("actions: secretsmanager:GetSecretValue, DescribeSecret (+ Deny on all others)")
    variables = subprocess.run(["gh", "variable", "list"], capture_output=True, text=True)
    print(f"repo variables now:\n{variables.stdout.strip() or '  (none)'}")
    return 0


def apply() -> int:
    iam = _iam()
    if _exists(iam):
        iam.update_assume_role_policy(RoleName=ROLE, PolicyDocument=json.dumps(TRUST))
        print(f"updated trust on {ROLE}")
    else:
        iam.create_role(
            RoleName=ROLE,
            AssumeRolePolicyDocument=json.dumps(TRUST),
            Description=("Read-only role for plivo-drift.yml. Scoped to "
                         "secretsmanager:GetSecretValue on wecare/plivo/api and nothing "
                         "else. Subject pinned by repository ID."),
            MaxSessionDuration=3600,
        )
        print(f"created {ROLE}")

    iam.put_role_policy(RoleName=ROLE, PolicyName=POLICY,
                        PolicyDocument=json.dumps(PERMISSIONS))
    print(f"attached inline policy {POLICY}")

    arn = f"arn:aws:iam::{ACCOUNT}:role/{ROLE}"
    result = subprocess.run(["gh", "variable", "set", "PLIVO_DRIFT_ROLE_ARN",
                             "--body", arn], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"gh variable set failed: {result.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"set repository variable PLIVO_DRIFT_ROLE_ARN = {arn}")
    return verify()


def verify() -> int:
    iam = _iam()
    problems = []
    try:
        role = iam.get_role(RoleName=ROLE)["Role"]
    except ClientError as exc:
        print(f"role missing: {exc.response['Error']['Code']}", file=sys.stderr)
        return 1

    statement = role["AssumeRolePolicyDocument"]["Statement"][0]
    equals = statement.get("Condition", {}).get("StringEquals", {})
    like = statement.get("Condition", {}).get("StringLike", {})
    document = iam.get_role_policy(RoleName=ROLE, PolicyName=POLICY)["PolicyDocument"]
    rendered = json.dumps(document)
    allow = [s for s in document["Statement"] if s["Effect"] == "Allow"]
    deny = [s for s in document["Statement"] if s["Effect"] == "Deny"]

    checks = {
        "trusts the GitHub OIDC provider":
            statement["Principal"].get("Federated") == OIDC_PROVIDER,
        "audience pinned":
            equals.get("token.actions.githubusercontent.com:aud") == "sts.amazonaws.com",
        "repository_id pinned":
            equals.get("token.actions.githubusercontent.com:repository_id") == REPO_ID,
        "repository_owner_id pinned":
            equals.get("token.actions.githubusercontent.com:repository_owner_id") == OWNER_ID,
        "subject restricted to refs/heads/stack":
            like.get("token.actions.githubusercontent.com:sub", "").endswith(
                f":ref:refs/heads/{BRANCH}"),
        "subject is not a bare wildcard":
            like.get("token.actions.githubusercontent.com:sub") != "*",
        "one inline policy only":
            iam.list_role_policies(RoleName=ROLE)["PolicyNames"] == [POLICY],
        "no managed policies attached":
            not iam.list_attached_role_policies(RoleName=ROLE)["AttachedPolicies"],
        "allow covers exactly the plivo api secret":
            len(allow) == 1 and allow[0]["Resource"] == SECRET_ARN,
        "allow is read-only":
            len(allow) == 1 and set(allow[0]["Action"]) == {
                "secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"},
        "a Deny backs it for every other secret":
            len(deny) == 1 and deny[0].get("NotResource") == SECRET_ARN,
        "no write verb anywhere":
            not any(v in rendered.lower()
                    for v in ("putsecret", "updatesecret", "deletesecret",
                              "createsecret", "rotatesecret", "tagresource")),
        "cannot list or discover other secrets":
            "listsecrets" not in rendered.lower(),
        "grants nothing outside secretsmanager":
            all(a.startswith("secretsmanager:")
                for s in document["Statement"]
                for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])),
    }

    variables = subprocess.run(["gh", "variable", "list"], capture_output=True, text=True)
    checks["PLIVO_DRIFT_ROLE_ARN is set"] = "PLIVO_DRIFT_ROLE_ARN" in variables.stdout

    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'}  {name}")
        if not ok:
            problems.append(name)

    if problems:
        print(f"\n{len(problems)} check(s) failed: {problems}", file=sys.stderr)
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
