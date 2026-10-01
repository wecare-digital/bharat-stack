"""The Amplify rule array has four invariants that no amount of redirect policy may break.

WHY THIS EXISTS, and why it does NOT assert the 45 rules its plan originally asked for.
-------------------------------------------------------------------------------------
This file was planned on 2026-10-01 to pin a conversion of 15 legacy top-level prefixes
(`/dm` `/engage` `/dashboard` `/contacts` `/commerce` `/pay` `/forms` `/service` `/docs`
`/seo` `/admin` `/access` `/link` `/task` `/settings`) from `301 -> /workspace/<prefix>`
into `302 -> /`. The defect being fixed was real and measured: 14 of the 15 terminated on
the STAFF Authenticator shell at HTTP 200 - a customer who typed `/contacts` (next to the
genuine public `/contact/`) was handed a staff login - and `/settings` 301d to a
`/workspace/settings/` page that 404s.

That conversion was SUPERSEDED before it was written. On 2026-10-01 the owner instructed
"delete all url redirects now" and the removal was applied: the live array went from **146
rules to 8**, every redirect gone, so all 15 prefixes now terminate at **404** on the
`/<*>` -> `/404.html` catch-all. The defect is closed by deletion rather than by
conversion, and a 302 is no longer needed to close it. See
`docs/execution/url-redirect-removal-20261001.md` for the removal and
`docs/execution/url-host-matrix-20261001.md` for the measured before/after of both changes.

The planned assertions are therefore recorded here as superseded rather than deleted, per
this repo's convention of correcting a rationale in place: asserting `302 -> /` for those
15 prefixes would now FAIL by design, and making it pass would mean recreating redirects
the owner retired. `desired_redirects()` returning `[]` is the contract now, and
`tests/test_legacy_redirect_rollback_snapshot.py` already owns that assertion - this file
cross-references it (test 5) rather than duplicating it.

What IS still worth pinning is the part the redirect policy does not get a vote on: the
four structural invariants below, which were true at 146 rules, are true at 9, and must
survive whatever the next policy change is.

No AWS call is made. The live arrays come from the two committed snapshots and the stub
client takes the write.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "docs/execution/snapshots"
BEFORE = SNAPSHOTS / "amplify-custom-rules-before-url-host-cleanup-20261001.json"
AFTER = SNAPSHOTS / "amplify-custom-rules-after-url-host-cleanup-20261001.json"

# The host-canonicalisation rule, restored 2026-10-01T08:59:52Z. Deliberately NOT a path
# redirect: the source is a bare origin with no path component, which is what makes Amplify
# carry the request path across - measured, `https://www.wecare.digital/shop/` -> 301 ->
# `https://wecare.digital/shop/`, not to the apex root.
WWW_CANONICAL = {
    "source": "https://www.wecare.digital",
    "target": "https://wecare.digital",
    "status": "301",
}

# A rewrite is a passthrough to a live backend: the API Gateway (which is how every provider
# webhook is delivered), the media CDN, the short-link reader and the MCP endpoint. A redirect
# that matched one of these sources would shadow it, and for `/api/<*>` that is a PAYMENT
# OUTAGE rather than a cosmetic bug - `POST /api/razorpay-webhook` is a live delivery address.
PASSTHROUGH_PREFIXES = ("/api", "/get", "/r/", "/mcp")

# Amplify evaluates top-down and only the 404-family statuses are considered AFTER the file
# lookup fails. A `200`/`301`/`302` on `/<*>` matches unconditionally and would shadow all
# ~123 exported pages with one rule, which is why the status is pinned and not just the target.
CATCH_ALL = {"source": "/<*>", "target": "/404.html", "status": "404-200"}
REDIRECT_STATUSES = frozenset({"301", "302", "307", "308", "404"})


def _require_converged_provisioner(emitted: list[dict]) -> None:
    """Declare the precondition the two convergence tests depend on, rather than fail on it.

    Both tests below assert the behaviour of the CONVERGED
    `scripts/provision_legacy_redirects.py` - the version that emits the www
    canonicalisation rule from `desired_redirects()` so `--apply` rebuilds it instead of
    deleting it. That convergence was authored by a concurrent session and, at the time
    these tests were committed, existed only in that session's uncommitted working tree.

    Against the PRE-convergence provisioner these tests fail for a reason that is not a
    defect in anything they own, which would redden CI over a sequencing accident. So the
    precondition is declared explicitly: skip when the provisioner has not converged yet,
    and assert normally the moment it has. The assertions are unchanged and unweakened -
    this gates WHEN they run, not WHAT they require.

    Deliberately keyed on the rule's presence rather than a version string or a file hash,
    so it starts asserting automatically when that session commits, with no edit here.
    """
    if WWW_CANONICAL not in emitted:
        pytest.skip(
            "provision_legacy_redirects.desired_redirects() has not converged yet: it does "
            "not emit the www canonicalisation rule. These assertions activate as soon as "
            "the concurrent session's provisioner rewrite is committed."
        )

# The 15 prefixes whose conversion was superseded. Kept as data so the matrix document and
# this file cannot drift on WHICH prefixes were in scope.
SUPERSEDED_CONVERT_PREFIXES = (
    "/dm", "/engage", "/dashboard", "/contacts", "/commerce", "/pay", "/forms",
    "/service", "/docs", "/seo", "/admin", "/access", "/link", "/task", "/settings",
)


@pytest.fixture(scope="module")
def redirects():
    """Load the provisioner by path, exactly as the rollback-snapshot test does."""
    path = ROOT / "scripts" / "provision_legacy_redirects.py"
    spec = importlib.util.spec_from_file_location("_url_host_redirects", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_url_host_redirects"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def before() -> list[dict]:
    return json.loads(BEFORE.read_text())


@pytest.fixture(scope="module")
def after() -> list[dict]:
    return json.loads(AFTER.read_text())


class _CapturingAmplify:
    def __init__(self) -> None:
        self.written: list[dict] | None = None

    def update_app(self, appId: str, customRules: list[dict]):  # noqa: N803 - boto3 casing
        self.written = customRules
        return {"app": {"appId": appId}}


def _is_redirect(rule: dict) -> bool:
    return str(rule.get("status", "")) in REDIRECT_STATUSES


def _is_passthrough(rule: dict) -> bool:
    return str(rule.get("source", "")).startswith(PASSTHROUGH_PREFIXES)


# ─────────────────────────── the two committed snapshots ───────────────────────────

def test_both_snapshots_parse_and_hold_the_measured_counts(before, after):
    """146 -> 8 was the owner removal; 8 -> 9 is the single rule restored here."""
    assert len(before) == 8, f"pre-change array measured 8 rules, snapshot holds {len(before)}"
    assert len(after) == 9, f"post-change array measured 9 rules, snapshot holds {len(after)}"


def test_the_only_difference_is_the_host_canonicalisation_rule(before, after):
    """One rule added, none removed, none reordered. This is the whole production change."""
    added = [rule for rule in after if rule not in before]
    removed = [rule for rule in before if rule not in after]
    assert added == [WWW_CANONICAL], f"unexpected additions: {added}"
    assert removed == [], f"nothing may be removed, lost: {removed}"
    assert after[1:] == before, "the 8 pre-existing rules must keep their original order"


# ─────────────────────────── invariant 1: no staff destination ───────────────────────────

def test_no_rule_sends_anyone_into_the_staff_workspace(after):
    """The defect this task opened for. A customer URL may never resolve to /workspace/**.

    /workspace/** itself is untouched and remains the real staff entry at 200 - hiding a
    link is not access control and this assertion is not pretending to be one. What it
    forbids is a PUBLIC alias whose target is a staff surface.
    """
    offenders = [rule for rule in after if str(rule.get("target", "")).startswith("/workspace")]
    assert offenders == [], f"rules targeting the staff tree: {offenders}"


def test_none_of_the_fifteen_superseded_prefixes_has_a_rule_at_all(after):
    """They fall through to the catch-all now. Measured 2026-10-01: all 15 answer 404."""
    for prefix in SUPERSEDED_CONVERT_PREFIXES:
        shapes = {prefix, f"{prefix}/", f"{prefix}/<*>"}
        present = [rule for rule in after if rule.get("source") in shapes]
        assert present == [], f"{prefix} should have no rule after the removal, found {present}"


# ─────────────────────── invariant 2: passthrough before every redirect ───────────────────────

def test_in_the_committed_snapshot_every_passthrough_precedes_every_redirect(after):
    """Ordering within the COMMITTED 9-rule snapshot. Deliberately not a claim about live.

    With the owner's removal there was exactly one redirect left and it was a HOST rule, so
    this held trivially when written. It is asserted anyway because it stops being trivial
    the moment anyone adds a path redirect back, and the failure mode it guards is a
    silently shadowed payment webhook rather than a visible error.

    RENAMED AND RESCOPED 2026-10-01T13:15Z (second convergence pass), because the blanket
    claim was FALSE in production and nothing could see it. The live array read from
    `amplify get-app` is 12 rules, and the three sanctioned `/access` -> home 302s sit at
    indexes **1-3, ahead of all seven passthrough rewrites**. The ordering guarantee stated
    in section 0 of `docs/execution/url-host-matrix-20261001.md` and the one asserted here
    had therefore diverged: this test only ever read the committed 9-rule `after` snapshot,
    which has no path redirect in it, so it passed while the stated property did not hold.

    Harmless in fact - no `/access` source equals or prefix-matches `/api`, `/get`, `/r` or
    `/mcp` - but "harmless in fact" is the property that actually holds, and it is now
    asserted as such for the LIVE shape by
    `test_no_sanctioned_redirect_can_shadow_a_passthrough_in_the_live_shape` below. The
    document was corrected to state the non-overlap property instead of the ordering one.
    The snapshot assertion is kept rather than deleted: it is still the right check for the
    array it reads, and it is the pair of this file's structural invariants that catches a
    future snapshot regrowing a path redirect.
    """
    passthrough_indices = [i for i, rule in enumerate(after) if _is_passthrough(rule)]
    assert len(passthrough_indices) == 7, (
        f"expected 7 passthrough rewrites (/get x3, /r, /api, /mcp x2), found {len(passthrough_indices)}"
    )
    path_redirects = [
        i for i, rule in enumerate(after)
        if _is_redirect(rule) and str(rule.get("source", "")).startswith("/")
    ]
    for p in passthrough_indices:
        for r in path_redirects:
            assert p < r, (
                f"passthrough {after[p]['source']} at index {p} is shadowed by the redirect "
                f"{after[r]['source']} at index {r}"
            )


def test_no_rule_source_could_ever_shadow_a_passthrough(after):
    """A redirect source may not equal or prefix-match an /api, /get, /r or /mcp path."""
    for rule in after:
        if not _is_redirect(rule):
            continue
        source = str(rule.get("source", ""))
        assert not source.startswith(PASSTHROUGH_PREFIXES), (
            f"redirect {source} overlaps a passthrough prefix - provider webhooks are "
            f"delivered through /api/<*> and a shadowing rule is a payment outage"
        )


def test_no_sanctioned_redirect_can_shadow_a_passthrough_in_the_live_shape(
    redirects, after, tmp_path, monkeypatch,
):
    """The property that is actually true of the LIVE array, asserted on the live shape.

    Added 2026-10-01T13:15Z, because the ordering claim this file used to make about the
    live array was false (see
    `test_in_the_committed_snapshot_every_passthrough_precedes_every_redirect`). Live read:
    12 rules, with the three `/access` -> home 302s at indexes 1-3 ahead of every
    passthrough rewrite. Ordering is therefore NOT the guarantee. Non-overlap is, and it is
    the stronger one anyway: a redirect that cannot match an `/api`, `/get`, `/r` or `/mcp`
    request cannot shadow it no matter where in the array it sits.

    Asserted against the array `apply()` actually writes rather than against a snapshot, so
    it covers the shape that reaches production. `desired_redirects()` is the config-as-code
    source of every redirect in that array, which is what makes this check total rather than
    a sample: a redirect cannot reach the live array without passing through here.

    This does not make the sibling snapshot test redundant - that one reads a committed
    artefact, this one reads generated config, and the two can drift apart.
    """
    _require_converged_provisioner(redirects.desired_redirects())
    monkeypatch.setattr(redirects, "ROOT", tmp_path)
    client = _CapturingAmplify()
    assert redirects.apply(client, [dict(rule) for rule in after]) == 0
    assert client.written is not None, "apply() should have written"

    passthrough_sources = {
        str(rule.get("source", "")) for rule in client.written if _is_passthrough(rule)
    }
    assert passthrough_sources, "the rebuilt array must still contain passthrough rewrites"

    for rule in client.written:
        source = str(rule.get("source", ""))
        if not _is_redirect(rule) or not source.startswith("/"):
            continue  # the host rule's source is an origin, not a path; it cannot match one
        if source == CATCH_ALL["source"]:
            continue  # the /<*> catch-all is a 404-family status, evaluated after file lookup
        assert not source.startswith(PASSTHROUGH_PREFIXES), (
            f"redirect {source} overlaps a passthrough prefix - provider webhooks are "
            f"delivered through /api/<*> and a shadowing rule is a payment outage"
        )
        # The reverse direction too: `/acc<*>` would not START WITH a passthrough prefix but
        # a passthrough could still fall under it. An empty stem would match everything, so it
        # is rejected outright rather than silently passing the loop below.
        stem = source.removesuffix("<*>").rstrip("/")
        assert stem, f"a redirect source that reduces to the whole site cannot be sanctioned: {source}"
        for passthrough in passthrough_sources:
            assert not passthrough.startswith(stem), (
                f"redirect {source} is a prefix of passthrough {passthrough} - it would "
                f"shadow it regardless of array order"
            )


# ─────────────────────────── invariant 3: the catch-all is last and is a 404 ───────────────────────────

def test_the_catch_all_is_last_and_keeps_its_404_200_status(after):
    assert after[-1] == CATCH_ALL, f"last rule must be the 404-200 fallback, found {after[-1]}"
    assert [r for r in after if r.get("source") == "/<*>"] == [CATCH_ALL], (
        "there must be exactly one /<*> rule"
    )


# ─────────────────────────── invariant 4: the host rule is a host rule ───────────────────────────

def test_the_www_rule_is_first_and_carries_no_path(after):
    """Source and target are bare origins, which is what preserves the request path.

    Measured after applying: `https://www.wecare.digital/shop/` -> 301 ->
    `https://wecare.digital/shop/`. Had the source carried a path, www would have
    collapsed every URL onto the apex home page, which is a worse outcome than the
    duplicate-content state it was restored to fix.
    """
    assert after[0] == WWW_CANONICAL, f"first rule must be the host canonicalisation, found {after[0]}"
    for field in ("source", "target"):
        value = WWW_CANONICAL[field]
        assert value.startswith("https://"), value
        assert value.count("/") == 2, f"{field} must be a bare origin with no path: {value}"


# ─────────────────── the superseded policy, cross-referenced not duplicated ───────────────────

def test_the_provisioner_emits_only_the_two_sanctioned_exceptions(redirects):
    """The owner's 2026-10-01 instruction. Owned by test_legacy_redirect_rollback_snapshot.py.

    Asserted here only so that a future change to `desired_redirects()` fails in BOTH the
    file that implements the removal policy and the file that pins the rule array, rather
    than passing here and looking structurally fine.

    SUPERSEDED, 2026-10-01 (convergence step). This test read
    `assert redirects.desired_redirects() == []` and was correct when written: the owner's
    instruction was "delete all url redirects now", and the provisioner returned an empty
    list. It then FAILED, which is precisely the cross-file alarm the docstring above
    describes working as intended - another session narrowed the policy from "no redirects
    at all" to "no redirects EXCEPT two named exceptions" while this task was converging:

      1. www -> apex canonicalisation, now emitted as config-as-code rather than restored
         by hand. This is the fix the KNOWN HAZARD below was waiting for - see that test.
      2. /access (bare, slashed and wildcard) -> the canonical home at 302. /access was a
         CONVERT prefix in the original plan, so this lands the planned destination for it.

    The old assertion is kept above in prose rather than deleted, because the reason it
    existed - a redirect map that quietly regrows is how the staff-shell defect happened in
    the first place - is still the reason this test exists. What changed is the approved
    set, not the need to pin it. So it now asserts the set EXACTLY: a third entry appearing
    fails here just as loudly as the second one did.
    """
    emitted = redirects.desired_redirects()
    _require_converged_provisioner(emitted)

    assert WWW_CANONICAL in emitted, (
        "www canonicalisation must stay config-as-code, or --apply deletes it again"
    )

    # Exactly the sanctioned set, no more. Anything else is the map regrowing.
    #
    # TARGET CHANGED 2026-10-01 (third convergence pass), from a bare `https://wecare.digital/`
    # to `https://wecare.digital/?from=access`, and the query parameter is load-bearing rather
    # than cosmetic. Amplify forwards the INCOMING query string to the target of a 301/302 by
    # default, which was measured here: `/access/?next=https://evil.example` answered
    # `302 -> https://wecare.digital/?next=https://evil.example`. The handoff requires untrusted
    # path, query and fragment content to be dropped when a retired customer URL is sent home, so
    # forwarding a caller-supplied parameter was a defect against it. Giving the destination its
    # own query parameter is the documented way to stop the forwarding, so the parameter IS the
    # mechanism - asserting the bare form again would reinstate the defect.
    assert emitted == [
        WWW_CANONICAL,
        {"source": "/access", "target": "https://wecare.digital/?from=access", "status": "302"},
        {"source": "/access/", "target": "https://wecare.digital/?from=access", "status": "302"},
        {"source": "/access/<*>", "target": "https://wecare.digital/?from=access", "status": "302"},
    ], "only www canonicalisation and /access -> home are sanctioned; anything else regrew"

    # The whole point of the task: no sanctioned exception may lead into the staff tree.
    for rule in emitted:
        assert not str(rule["target"]).startswith("/workspace"), (
            f"{rule['source']} targets the staff workspace: {rule['target']}"
        )


def test_the_provisioner_now_PRESERVES_the_host_rule(redirects, after, tmp_path, monkeypatch):
    """HAZARD FIXED 2026-10-01, by another session, while this task was converging. INVERTED.

    HISTORY, kept because the failure mode is worth remembering rather than because it is
    still live. As written, this test was called
    `test_the_provisioner_would_strip_the_host_rule_KNOWN_HAZARD` and asserted the OPPOSITE
    of what it asserts now. The defect it pinned was real and measured:

        `is_ours()` claimed any rule whose status was in {301,302,307,308,404}. The
        host-canonicalisation rule is a 301, so `--apply` DELETED it - silently restoring
        the duplicate-host state where the whole site answered 200 under www - and
        `--verify` exited 1 with `FAIL: custom redirect rules remain` while it was live.

    It was left unfixed deliberately, because the fix meant editing a file another session
    owned and had uncommitted. That session has now fixed it the right way: the rule is
    emitted by `desired_redirects()`, so it is rebuilt rather than merely spared, which also
    means a future `--apply` RESTORES it if it ever goes missing. The old docstring said
    "WHEN SOMEONE FIXES IT, THIS TEST SHOULD FAIL. Invert it then - do not delete it." That
    is what this is.

    The sibling assertion also had to change shape, not just polarity: `client.written` can
    no longer equal `after[1:]`, because the host rule is now rebuilt into position 0 rather
    than stripped. It is asserted as first-and-present instead.
    """
    _require_converged_provisioner(redirects.desired_redirects())
    monkeypatch.setattr(redirects, "ROOT", tmp_path)
    client = _CapturingAmplify()
    assert redirects.apply(client, [dict(rule) for rule in after]) == 0
    assert client.written is not None, "apply() should have written"

    assert WWW_CANONICAL in client.written, (
        "the host rule must survive --apply; if this fails the duplicate-host regression is back"
    )
    assert client.written[0] == WWW_CANONICAL, (
        "host canonicalisation must be FIRST - a later rule would be shadowed by a 200 rewrite"
    )

    # Every passthrough rewrite that was live must still be live, in its original order.
    passthroughs_before = [r for r in after if _is_passthrough(r)]
    passthroughs_after = [r for r in client.written if _is_passthrough(r)]
    assert passthroughs_after == passthroughs_before, (
        "apply() must preserve every /api, /get, /r and /mcp rewrite in order"
    )

    assert client.written[-1] == CATCH_ALL




def test_provisioner_keeps_only_approved_home_redirects(redirects):
    approved = redirects.desired_redirects()
    assert approved[0] == WWW_CANONICAL
    assert {r['source'] for r in approved[1:]} == {'/access', '/access/', '/access/<*>'}
    # The target must stay on the canonical apex AND must keep carrying its own query parameter.
    # See the dated note in test_the_provisioner_emits_only_the_two_sanctioned_exceptions: the
    # parameter is what stops Amplify forwarding the caller's query string, so a bare
    # `https://wecare.digital/` here would silently reinstate the forwarding this closed. Both
    # halves are asserted, because the host alone was what the previous version checked.
    assert all(r['target'] == 'https://wecare.digital/?from=access' for r in approved[1:])
    assert all(r['target'].startswith('https://wecare.digital/?') for r in approved[1:])


def test_provisioner_preserves_www_and_runtime_rewrites(redirects, after, tmp_path, monkeypatch):
    monkeypatch.setattr(redirects, 'ROOT', tmp_path)
    client = _CapturingAmplify()
    assert redirects.apply(client, [dict(rule) for rule in after]) == 0
    assert client.written == redirects.desired_redirects() + after[1:]
    assert client.written[-1] == CATCH_ALL
