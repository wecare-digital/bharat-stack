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

`ecr:DescribeImages` is granted alongside it, also a read, for the workflow's own
post-push assertion. The same 26.04 runner change made BuildKit attach a provenance
attestation by default, which turns the published artifact into an OCI image INDEX -
and Lambda cannot run an index. The workflow now reads back the manifest media type
and fails with that sentence instead of letting `update-function-code` reject the
image with one that names media types and not the cause.

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

# The statement to amend, and the actions to add to it. Both are reads on the one
# repository the role already pushes to.
#
#   ecr:BatchGetImage  the manifest HEAD that the newer Docker client issues on push
#   ecr:DescribeImages the workflow's own check that it did not publish an OCI index,
#                      which Lambda cannot run - see docs-scraper-deploy.yml
TARGET_SID = "ECRRepository"
NEEDED_ACTIONS = ("ecr:BatchGetImage", "ecr:DescribeImages")

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
    """Return a copy of doc with NEEDED_ACTIONS added to the target statement."""
    out = copy.deepcopy(doc)
    st = _find_target(out)
    if st is None:
        raise SystemExit(f"statement Sid={TARGET_SID!r} not found; refusing to guess")
    st["Action"] = sorted(set(_actions(st)) | set(NEEDED_ACTIONS))
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
    print("AFTER  :", ", ".join(sorted(acts | set(NEEDED_ACTIONS))))
    print()

    outstanding = sorted(set(NEEDED_ACTIONS) - acts)
    if not outstanding:
        print("already granted:", ", ".join(NEEDED_ACTIONS), "- nothing to do.")
        return 0

    # NEEDED_ACTIONS are excluded from the drift check because a partial earlier run
    # legitimately leaves one of them already present. Anything ELSE that appeared is
    # drift, and re-running --apply would write it back rather than question it.
    unexpected = acts - EXPECTED_EXISTING - set(NEEDED_ACTIONS)
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

    print(f"CHANGE : add {', '.join(outstanding)}")
    print("         scoped to that one repository. Both are reads.")
    print("Run with --apply.")
    return 0


def apply() -> int:
    rc = plan()
    if rc != 0:
        return rc

    iam = _iam()
    before = _live_document(iam)
    if set(NEEDED_ACTIONS) <= set(_actions(_find_target(before))):
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

    for need in NEEDED_ACTIONS:
        if need not in acts:
            print(f"FAIL: {need} not granted")
            ok = False
        else:
            print(f"ok  : {need} granted")

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
