#!/usr/bin/env python3
"""Repair the GitHub Actions OIDC trust policies broken by the repository rename.

WHY. The GitHub repo was renamed `bharat-stack` -> `wecare-digital` on 2026-09-27.
Both deploy workflows authenticate by OIDC and then failed with

    Not authorized to perform sts:AssumeRoleWithWebIdentity

which reads as a credentials problem and is not one. This repository was created
2026-08-22, i.e. after 2026-07-15, so it uses GitHub's **immutable** subject
format:

    repo:OWNER@OWNER-ID/REPO@REPO-ID:ref:refs/heads/BRANCH

The owner id and repo id survive a rename -- that is the point of the format --
but the *name* segments do not, and they are still present in `sub`. So the
trust policies, which pinned the whole string with `StringEquals`, went stale at
the name and nowhere else:

    before  repo:wecare-digital@319896805/bharat-stack@1342943014:ref:refs/heads/stack
    after   repo:wecare-digital@319896805/wecare-digital@1342943014:ref:refs/heads/stack

Evidence this is the cause and not a coincidence: `seo-tools-deploy` succeeded at
2026-09-27T03:58Z and failed at 06:46Z with no change to the role, the workflow
or its permissions in between. The rename happened in that window.

WHAT THIS WRITES, and why it is not simply the corrected literal. Pinning the new
name would break again on the next rename. Instead the name segments become
wildcards while the two immutable ids are pinned twice over -- inside `sub` and
again as their own condition keys:

    StringEquals  aud                  = sts.amazonaws.com
    StringEquals  repository_owner_id  = 319896805
    StringEquals  repository_id        = 1342943014
    StringLike    sub                  = repo:*@319896805/*@1342943014:ref:refs/heads/stack

The effective grant is unchanged: branch `stack` of repository 1342943014 owned
by 319896805, and nothing else. It is strictly tighter than the previous policy,
because ids cannot be recycled by a namespace grab whereas names can, and AWS
still sees a `sub` condition that is not solely a wildcard (IAM rejects the
policy outright if it is).

    python scripts/fix_github_oidc_trust.py --status
    python scripts/fix_github_oidc_trust.py --apply

`--apply` snapshots each existing trust policy to
docs/execution/snapshots/ before writing, and is idempotent: a role already
holding the target document is reported UNCHANGED and skipped.

ROLLBACK
    aws iam update-assume-role-policy --role-name <role> \
        --policy-document file://docs/execution/snapshots/<role>-trust-before-rename-repair.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "docs" / "execution" / "snapshots"

ACCOUNT_ID = "775261844268"
PROVIDER = "token.actions.githubusercontent.com"
PROVIDER_ARN = f"arn:aws:iam::{ACCOUNT_ID}:oidc-provider/{PROVIDER}"

# Immutable GitHub identifiers for wecare-digital/wecare-digital, confirmed from
# the REST API (`gh api repos/wecare-digital/wecare-digital`). These do not change
# on rename or transfer, which is why the policy keys on them.
OWNER_ID = "319896805"
REPO_ID = "1342943014"
BRANCH = "stack"

# The first two keep "bharat-stack" in their names on purpose: an IAM role name is
# not a repository reference and renaming it would invalidate every
# `role-to-assume` in .github/workflows. Only the trust policy was wrong.
#
# The third was created fresh on 2026-09-28 02:55 with the *correct* new repo name,
# so it was never broken - but it pinned that name with StringEquals, which is the
# same latent bug one rename away from repeating this outage. It is included so all
# three are rename-proof and auditable from one command.
ROLES = [
    "GitHubActions-bharat-stack-docs-scraper",
    "GitHubActions-bharat-stack-seo-tools",
    "GitHubActions-wecare-digital-route-auth",
]


def target_policy() -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Federated": PROVIDER_ARN},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        f"{PROVIDER}:aud": "sts.amazonaws.com",
                        f"{PROVIDER}:repository_owner_id": OWNER_ID,
                        f"{PROVIDER}:repository_id": REPO_ID,
                    },
                    "StringLike": {
                        f"{PROVIDER}:sub": (
                            f"repo:*@{OWNER_ID}/*@{REPO_ID}:ref:refs/heads/{BRANCH}"
                        )
                    },
                },
            }
        ],
    }


def _canonical(doc: dict) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def _current(iam, role: str) -> dict | None:
    try:
        return iam.get_role(RoleName=role)["Role"]["AssumeRolePolicyDocument"]
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        print(f"  {role}: cannot read trust policy ({code})")
        return None


def _subject(doc: dict) -> str:
    """Pull the sub condition out of a trust document, for reporting."""
    for statement in doc.get("Statement", []):
        condition = statement.get("Condition", {})
        for operator in ("StringEquals", "StringLike"):
            value = condition.get(operator, {}).get(f"{PROVIDER}:sub")
            if value:
                return f"{operator}: {value}"
    return "<no sub condition>"


def status(iam) -> int:
    want = target_policy()
    stale = 0
    print(f"target sub  StringLike: repo:*@{OWNER_ID}/*@{REPO_ID}:ref:refs/heads/{BRANCH}\n")
    for role in ROLES:
        doc = _current(iam, role)
        if doc is None:
            stale += 1
            continue
        matches = _canonical(doc) == _canonical(want)
        print(f"{'OK      ' if matches else 'STALE   '} {role}")
        print(f"         live  {_subject(doc)}")
        if not matches:
            stale += 1
    print(f"\n{len(ROLES) - stale}/{len(ROLES)} roles already correct")
    return 0 if stale == 0 else 1


def apply(iam) -> int:
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    want = target_policy()
    failures = 0

    for role in ROLES:
        doc = _current(iam, role)
        if doc is None:
            failures += 1
            continue

        if _canonical(doc) == _canonical(want):
            print(f"UNCHANGED {role} (already holds the target document)")
            continue

        snapshot = SNAPSHOTS / f"{role}-trust-before-rename-repair.json"
        if not snapshot.exists():
            snapshot.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            print(f"SNAPSHOT  {snapshot.relative_to(ROOT)}")
        else:
            print(f"SNAPSHOT  {snapshot.relative_to(ROOT)} (kept, already present)")

        try:
            iam.update_assume_role_policy(
                RoleName=role, PolicyDocument=json.dumps(want)
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "ClientError")
            print(f"FAILED    {role}: {code}")
            failures += 1
            continue

        after = _current(iam, role)
        if after is not None and _canonical(after) == _canonical(want):
            print(f"UPDATED   {role}")
            print(f"          now   {_subject(after)}")
        else:
            print(f"FAILED    {role}: write did not verify")
            failures += 1

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="report drift, change nothing")
    group.add_argument("--apply", action="store_true", help="snapshot then repair")
    args = parser.parse_args()

    iam = boto3.client("iam")
    return status(iam) if args.status else apply(iam)


if __name__ == "__main__":
    sys.exit(main())
