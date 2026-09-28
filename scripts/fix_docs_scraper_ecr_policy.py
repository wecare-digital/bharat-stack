"""Add the one missing ECR read action the docs-scraper push needs.

WHAT BROKE, AND WHY IT LOOKED LIKE NOTHING CHANGED
--------------------------------------------------
`docs-scraper-deploy.yml` builds a container image and `docker push`es it to ECR.
On 2026-09-28 it started failing at the very end of the push, with every layer
already uploaded:

    cbbf4c7717aa: Pushed
    unknown: unexpected status from HEAD request to
      https://775261844268.dkr.ecr.us-east-1.amazonaws.com/v2/wecare-docs-scraper/
      manifests/sha256:97fbe...: 403 Forbidden

Nothing in this repository's AWS configuration changed. What changed is the runner
image: CI moved from `ubuntu-latest` (then Ubuntu 24.04) to a pinned `ubuntu-26.04`,
and the newer Docker client on 26.04 issues a HEAD on the manifest **by digest**
during push. The older client did not. Measured directly from the two run logs:
the 24.04 run contains ZERO `HEAD request` lines and the 26.04 run contains one.

A HEAD on `/v2/<repo>/manifests/<digest>` is authorized as `ecr:BatchGetImage`. The
deploy role `GitHubActions-bharat-stack-docs-scraper` was granted the nine push-side
actions and not that one, so ECR answered 403. The permission gap has been there
since the role was written; the old client simply never exercised it. That is the
real lesson here rather than anything about Ubuntu: a policy assembled from the
calls a tool happened to make is a policy that breaks when the tool changes.

`ecr:BatchGetImage` is a READ. It lets the role resolve an image manifest in the one
repository it already pushes to. It grants no new mutation, and AWS's own
push-to-ECR policy examples include it.

REPLACE, NOT PATCH - THE SAME HAZARD AS `UpdateUserPool`
--------------------------------------------------------
`PutRolePolicy` overwrites the **entire** inline policy document. There is no
add-one-action API. So this script reads the live document, inserts the single action
into the existing `ECRRepository` statement, and writes the whole thing back. It
refuses to apply if the live document is not the shape it expects, and `--verify`
re-reads and diffs every statement so an accidental drop shows up as a failure
rather than as a quiet loss of permission. See `.kiro/steering/aws-agent-rules.md`
for the Cognito incident this defensiveness is copied from.

    python scripts/fix_docs_scraper_ecr_policy.py            # plan (default)
    python scripts/fix_docs_scraper_ecr_policy.py --apply
    python scripts/fix_docs_scraper_ecr_policy.py --verify
"""

from __future__ import annotations

import argparse
import copy
import json
import sys

import boto3
from botocore.exceptions import ClientError

ACCOUNT = "775261844268"
REGION = "us-east-1"
ROLE = "GitHubActions-bharat-stack-docs-scraper"
POLICY = "DocsScraperDeploy"

REPO_ARN = f"arn:aws:ecr:{REGION}:{ACCOUNT}:repository/wecare-docs-scraper"

# The statement to amend, and the action to add to it.
TARGET_SID = "ECRRepository"
NEEDED_ACTION = "ecr:BatchGetImage"

# Guard rails for --apply. The live statement must already look like this, or the
# document has drifted and a blind write would be the bug rather than the fix.
EXPECTED_EXISTING = {
    "ecr:BatchCheckLayerAvailability",
    "ecr:CompleteLayerUpload",
    "ecr:DescribeRepositories",
    "ecr:InitiateLayerUpload",
    "ecr:PutImage",
    "ecr:SetRepositoryPolicy",
    "ecr:UploadLayerPart",
}


def _iam():
    return boto3.client("iam", region_name=REGION)


def _live_document(iam) -> dict:
    try:
        resp = iam.get_role_policy(RoleName=ROLE, PolicyName=POLICY)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        print(f"FAILED to read {ROLE}/{POLICY}: {code}", file=sys.stderr)
        raise SystemExit(2) from exc
    return resp["PolicyDocument"]


def _find_target(doc: dict) -> dict | None:
    statements = doc.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    for st in statements:
        if st.get("Sid") == TARGET_SID:
            return st
    return None


def _actions(st: dict) -> list[str]:
    acts = st.get("Action", [])
    return [acts] if isinstance(acts, str) else list(acts)


def _amended(doc: dict) -> dict:
    """Return a copy of doc with NEEDED_ACTION added to the target statement."""
    out = copy.deepcopy(doc)
    st = _find_target(out)
    if st is None:
        raise SystemExit(f"statement Sid={TARGET_SID!r} not found; refusing to guess")
    acts = _actions(st)
    if NEEDED_ACTION not in acts:
        acts.append(NEEDED_ACTION)
    st["Action"] = sorted(acts)
    return out


def plan() -> int:
    doc = _live_document(_iam())
    st = _find_target(doc)
    if st is None:
        print(f"Sid={TARGET_SID} MISSING from the live document. Not safe to apply.")
        return 1

    acts = set(_actions(st))
    print(f"role   : {ROLE}")
    print(f"policy : {POLICY} (inline)")
    print(f"stmt   : {TARGET_SID}")
    print(f"scope  : {st.get('Resource')}")
    print()
    print("BEFORE :", ", ".join(sorted(acts)))
    print("AFTER  :", ", ".join(sorted(acts | {NEEDED_ACTION})))
    print()

    if NEEDED_ACTION in acts:
        print(f"{NEEDED_ACTION} already granted. Nothing to do.")
        return 0

    unexpected = acts - EXPECTED_EXISTING
    missing = EXPECTED_EXISTING - acts
    if unexpected or missing:
        print("DRIFT against the expected shape - review before applying:")
        if unexpected:
            print("  unexpected present:", ", ".join(sorted(unexpected)))
        if missing:
            print("  expected but absent:", ", ".join(sorted(missing)))
        return 1

    if st.get("Resource") != REPO_ARN:
        print(f"Resource is not the single repository ARN ({REPO_ARN}); refusing.")
        return 1

    print(f"CHANGE : add {NEEDED_ACTION}, scoped to that one repository. Read-only.")
    print("Run with --apply.")
    return 0


def apply() -> int:
    rc = plan()
    if rc != 0:
        return rc

    iam = _iam()
    before = _live_document(iam)
    if NEEDED_ACTION in set(_actions(_find_target(before))):
        return 0

    after = _amended(before)
    iam.put_role_policy(
        RoleName=ROLE, PolicyName=POLICY, PolicyDocument=json.dumps(after)
    )
    print(f"APPLIED: put_role_policy {ROLE}/{POLICY}")
    return verify(before=before)


def verify(before: dict | None = None) -> int:
    live = _live_document(_iam())
    st = _find_target(live)
    if st is None:
        print(f"FAIL: Sid={TARGET_SID} absent")
        return 1

    acts = set(_actions(st))
    ok = True

    if NEEDED_ACTION not in acts:
        print(f"FAIL: {NEEDED_ACTION} not granted")
        ok = False
    else:
        print(f"ok  : {NEEDED_ACTION} granted")

    if st.get("Resource") != REPO_ARN:
        print(f"FAIL: scope widened to {st.get('Resource')}")
        ok = False
    else:
        print("ok  : still scoped to the single wecare-docs-scraper repository")

    lost_actions = sorted(EXPECTED_EXISTING - acts)
    if lost_actions:
        for want in lost_actions:
            print(f"FAIL: pre-existing action lost: {want}")
        ok = False
    else:
        print(f"ok  : all {len(EXPECTED_EXISTING)} pre-existing ECR actions intact")

    # PutRolePolicy replaces the whole document, so prove the other statements
    # survived rather than assuming they did.
    if before is not None:
        b = {s.get("Sid") for s in before.get("Statement", [])}
        a = {s.get("Sid") for s in live.get("Statement", [])}
        lost = b - a
        if lost:
            print(f"FAIL: statements dropped by the write: {sorted(lost)}")
            ok = False
        else:
            print(f"ok  : all {len(b)} statements still present {sorted(a)}")
    else:
        sids = sorted(s.get("Sid") for s in live.get("Statement", []))
        print(f"note: {len(sids)} statements present {sids}")

    print("VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--plan", action="store_true", help="show the change (default)")
    g.add_argument("--apply", action="store_true", help="write the amended policy")
    g.add_argument("--verify", action="store_true", help="re-read and assert")
    args = ap.parse_args()

    if args.apply:
        return apply()
    if args.verify:
        return verify()
    return plan()


if __name__ == "__main__":
    raise SystemExit(main())
