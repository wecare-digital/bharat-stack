"""Two scripts write the GitHub OIDC trust policy. They must write the same one.

WHY THIS TEST EXISTS. On 2026-09-27 the repository was renamed `bharat-stack` ->
`wecare-digital` and two deploy workflows went dark for 22 hours with

    Not authorized to perform sts:AssumeRoleWithWebIdentity

which reads as a credentials fault and is not one. This repo was created after
2026-07-15, so it uses GitHub's immutable subject format:

    repo:OWNER@OWNER-ID/REPO@REPO-ID:ref:refs/heads/BRANCH

The ids survive a rename. The NAME segments are still in the string and do not.
Both trust policies pinned the whole string with `StringEquals`, so the rename
broke them.

THE REGRESSION THIS GUARDS, which is subtler than the original bug. After the
repair, `scripts/provision_ci_route_auth_role.py` still contained a name-pinned
`StringEquals` document *and* called `update_assume_role_policy` with it. Running
`--apply` for any unrelated reason would have silently reverted the hardening on
one of the three roles and re-armed the outage for the next rename. Nothing would
have failed at the time; the damage only appears on a rename, which is exactly the
kind of latent trap a test has to hold down.

So: both modules must emit a byte-identical document, and that document must not
pin a repository or owner NAME anywhere.

These assertions are pure data checks on module constants. No AWS call is made and
no credential is read, so this runs in CI with no permissions.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

OWNER_ID = "319896805"
REPO_ID = "1342943014"
BRANCH = "stack"
PROVIDER = "token.actions.githubusercontent.com"

# Names that must never appear in the matched subject. Both the old and the current
# repository name are listed: the current one is just as wrong to pin, because
# pinning it is what makes the next rename an outage.
FORBIDDEN_NAMES = ("bharat-stack", "wecare-digital@")


def _load(relpath: str, name: str):
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, relpath
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def provisioner():
    return _load("scripts/provision_ci_route_auth_role.py", "_oidc_provisioner")


@pytest.fixture(scope="module")
def fixer():
    return _load("scripts/fix_github_oidc_trust.py", "_oidc_fixer")


def _canonical(doc: dict) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def _conditions(doc: dict) -> tuple[dict, dict]:
    statements = doc["Statement"]
    assert len(statements) == 1, "expected exactly one trust statement"
    condition = statements[0]["Condition"]
    return condition.get("StringEquals", {}), condition.get("StringLike", {})


def test_both_scripts_write_the_same_document(provisioner, fixer):
    """Whichever runs last must not change the outcome."""
    assert _canonical(provisioner.TRUST) == _canonical(fixer.target_policy())


@pytest.mark.parametrize("which", ["provisioner", "fixer"])
def test_subject_is_matched_by_pattern_not_by_name(which, provisioner, fixer):
    doc = provisioner.TRUST if which == "provisioner" else fixer.target_policy()
    equals, like = _conditions(doc)

    # The subject must be a StringLike pattern. A StringEquals subject is the bug.
    assert f"{PROVIDER}:sub" not in equals, (
        "subject pinned with StringEquals; a rename will break this role"
    )
    subject = like.get(f"{PROVIDER}:sub")
    assert subject, "no StringLike subject condition"

    # IAM rejects a trust policy whose sub condition is only a wildcard.
    assert subject.strip() not in ("*", "?"), "IAM refuses a wholly wildcard subject"

    for name in FORBIDDEN_NAMES:
        assert name not in subject, f"subject pins the repository name via {name!r}"

    # The ids and the branch are what actually constrain it.
    assert f"@{OWNER_ID}/" in subject
    assert f"@{REPO_ID}:" in subject
    assert subject.endswith(f":ref:refs/heads/{BRANCH}")


@pytest.mark.parametrize("which", ["provisioner", "fixer"])
def test_immutable_ids_pinned_as_their_own_conditions(which, provisioner, fixer):
    """Belt and braces: the ids are also asserted outside the subject string."""
    doc = provisioner.TRUST if which == "provisioner" else fixer.target_policy()
    equals, _ = _conditions(doc)
    assert equals.get(f"{PROVIDER}:aud") == "sts.amazonaws.com"
    assert equals.get(f"{PROVIDER}:repository_owner_id") == OWNER_ID
    assert equals.get(f"{PROVIDER}:repository_id") == REPO_ID


def test_trust_grants_only_web_identity_assumption(provisioner):
    statement = provisioner.TRUST["Statement"][0]
    assert statement["Effect"] == "Allow"
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert statement["Principal"]["Federated"].endswith(f"oidc-provider/{PROVIDER}")


def test_fixer_covers_every_oidc_role(fixer):
    """A role left off the list is a role that silently keeps the old policy."""
    assert set(fixer.ROLES) == {
        "GitHubActions-bharat-stack-docs-scraper",
        "GitHubActions-bharat-stack-seo-tools",
        "GitHubActions-wecare-digital-route-auth",
    }


def test_route_auth_live_gate_does_not_run_on_pull_requests():
    """The branch-scoped subject cannot be produced by a pull_request event.

    A PR emits `...:pull_request` rather than `...:ref:refs/heads/stack`, so the job
    can never authenticate there; and a fork PR gets no OIDC token at all. Running
    it on PRs made the job red for a reason a contributor could not fix.
    """
    workflow = (ROOT / ".github/workflows/route-auth.yml").read_text(encoding="utf-8")
    assert "if: github.event_name != 'pull_request'" in workflow, (
        "route-auth live-gate must be excluded from pull_request events"
    )
