"""Every place the Meta Graph version is configured, enumerated and held to one invariant.

`tests/test_meta_version.py` proves no *handler* declares its own version. That left three gaps,
all of which turned out to be occupied:

1. `config/lambda-env-manifest.json` carries live `META_API_VERSION` / `META_GRAPH_BASE` values
   that no test read, so a malformed one could be committed.
2. `META_GRAPH_BASE` is a whole URL and was never shape-checked
   (`tests/testmeta_graph_version_base_is_validated.py` now covers the module side).
3. Scripts were outside the net entirely. `scripts/meta_webhook_control_plane.py` hard-coded
   `v23.0` -- two major versions behind the fleet -- and two more scripts carried `v25.0`.

The audit counted six sources of truth; the review that followed found a seventh. So these tests
assert the INVARIANT rather than a count, the way `test_meta_version.py` does: a count in a
document goes stale, and the next source to appear is the one nobody wrote down.

ON THE MANIFEST, AND WHY IT IS NOT ASSERTED EQUAL TO THE MODULE
---------------------------------------------------------------
`config/lambda-env-manifest.json` is a record of what is live, not a statement of what is
wanted. Its own `_comment` says so, and `scripts/env_manifest.py` diffs it against the running
Lambda configuration. The live functions pin `v25.0` today and will keep doing so until a
separately authorized deploy, so asserting the manifest equals the module default would be
asserting something false -- and would start failing the moment somebody correctly re-recorded
live state with `--export`.

What IS asserted: every recorded value is a *valid* version or base, every function carrying a
version key is one of the five known to do so, and any pin that differs from the current default
is accompanied by a comment explaining it. That makes a deliberate pin distinguishable from a
stale one, which is the thing the audit could not tell by looking.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))
sys.path.insert(0, str(ROOT / "scripts"))

MANIFEST = ROOT / "config/lambda-env-manifest.json"

#: The only functions that may carry a version key, from the audit's section 4.1. Four pin the
#: bare version; `wecare-marketing-ads` pins a whole base URL.
EXPECTED_VERSION_KEY_FUNCTIONS = {
    "wecare-partner-onboarding",
    "wecare-partner-token-refresh",
    "wecare-whatsapp-business-api",
    "wecare-whatsapp-calling",
    "wecare-marketing-ads",
}

#: The one function deliberately held away from the fleet default, and why.
#:
#: v26.0 defaults Shop Ads `destination_spec` on `adcreatives`/`ads`, `marketing-ads` sets none,
#: and WhatsApp-destination creative eligibility is undocumented. So this is an exception taken on
#: purpose, not an oversight -- and it is named here so nobody "finishes the job" by bumping it and
#: silently changes what an ad creative points at.
DELIBERATE_PIN = "wecare-marketing-ads"

#: Functions whose LIVE `META_API_VERSION` still trails the repo default, awaiting a deploy.
#:
#: Not a defect and not a pin: the repo constant moved to v26.0 on 2026-10-01 and the live
#: environments cannot change without `update-function-code` plus a version publish and an alias
#: move, which is the owner's action. This set is the deploy's checklist, written down so the
#: remaining work is enumerated instead of implied.
PENDING_ENV_DEPLOY = {
    "wecare-partner-onboarding",
    "wecare-partner-token-refresh",
    "wecare-whatsapp-business-api",
    "wecare-whatsapp-calling",
}


def _manifest_functions() -> dict:
    return json.loads(MANIFEST.read_text())["functions"]


def _version_keys() -> dict:
    out = {}
    for name, env in _manifest_functions().items():
        found = {k: v for k, v in env.items()
                 if k in ("META_API_VERSION", "META_GRAPH_BASE")}
        if found:
            out[name] = found
    return out


# ── the manifest cannot carry a malformed version ────────────────────────────────

def test_the_manifest_parses():
    assert isinstance(_manifest_functions(), dict)


def test_every_recorded_version_is_a_valid_graph_version():
    from lambda_utils.meta_version import is_valid_version

    bad = {f"{fn}.{key}": value
           for fn, keys in _version_keys().items() for key, value in keys.items()
           if key == "META_API_VERSION" and not is_valid_version(value)}
    assert not bad, f"malformed META_API_VERSION values in the manifest: {bad}"


def test_every_recorded_base_parses_under_the_module_regex():
    """A base may legitimately DIFFER from the default; it may not be malformed.

    This is the gap that let an unchecked URL be a configuration route: the module validated the
    bare version and never looked at the base.
    """
    from lambda_utils.meta_version import base_version

    bad = {f"{fn}.META_GRAPH_BASE": value
           for fn, keys in _version_keys().items()
           for key, value in keys.items()
           if key == "META_GRAPH_BASE" and not base_version(value)}
    assert not bad, f"malformed META_GRAPH_BASE values in the manifest: {bad}"


def test_only_the_known_five_functions_carry_a_version_key():
    """A newcomer is a new unvalidated version route, which is exactly the defect found.

    Named in the failure message rather than counted, so the fix is obvious: either the function
    should not pin a version, or it is a deliberate exception and belongs in this set with a
    reason.
    """
    actual = set(_version_keys())
    unexpected = actual - EXPECTED_VERSION_KEY_FUNCTIONS
    assert not unexpected, (
        "these functions carry a Meta version key and were not expected to. Either remove the "
        "key so they follow lambda_utils.meta_version, or add them here with the reason for the "
        f"pin: {sorted(unexpected)}"
    )


def test_a_base_pinned_away_from_the_default_is_explained():
    """A deliberate lag must be distinguishable from a forgotten one.

    The manifest records live state, so a value behind the default is expected while a deploy is
    pending. What must not happen is a pin with nothing saying why -- that is indistinguishable
    from nobody having looked, which is precisely how the false v26.0 blocker survived.
    """
    from lambda_utils.meta_version import META_API_VERSION, base_version

    functions = _manifest_functions()
    for name, keys in _version_keys().items():
        base = keys.get("META_GRAPH_BASE")
        if not base or base_version(base) == META_API_VERSION:
            continue
        env = functions[name]
        explained = any(
            key.startswith("_comment") or key.startswith("_note") for key in env)
        assert name == DELIBERATE_PIN or explained, (
            f"{name} pins META_GRAPH_BASE at {base_version(base)} while the module default is "
            f"{META_API_VERSION}, with nothing recording why. Add a `_comment` beside it, or "
            f"bring it to the default."
        )


def test_the_deliberate_pin_is_still_the_only_one_and_is_still_behind():
    """Guards the exception itself in both directions.

    If `wecare-marketing-ads` ever reaches the default this test fails, which is the prompt to
    delete the exception rather than leave a stale carve-out behind. If a second function joins
    it, that is a new decision nobody recorded.
    """
    from lambda_utils.meta_version import META_API_VERSION, base_version

    pinned_behind = {
        name for name, keys in _version_keys().items()
        if keys.get("META_GRAPH_BASE")
        and base_version(keys["META_GRAPH_BASE"]) != META_API_VERSION
    }
    assert pinned_behind == {DELIBERATE_PIN}, (
        "the set of functions pinned away from the default changed. If the Shop Ads "
        "destination_spec question is settled, remove the pin AND this expectation together; "
        f"got {sorted(pinned_behind)}"
    )


def test_the_pending_env_deploy_set_is_exactly_what_is_recorded():
    """The four live `META_API_VERSION` pins still trailing the repo default, enumerated.

    Editing `_DEFAULT` moves exactly ONE function -- `wecare-meta-business-agent`, the only one
    carrying neither key. The other five are configured in the environment and keep their old
    value until a deploy, which is what makes the repo-side bump low risk rather than a silent
    production flip.

    This test is the handover. When the deploy lands and `scripts/env_manifest.py --export`
    re-records live state, this fails and names what moved, so the set is updated deliberately
    rather than the drift going unnoticed in either direction.
    """
    from lambda_utils.meta_version import META_API_VERSION, is_valid_version

    trailing = set()
    for name, keys in _version_keys().items():
        recorded = keys.get("META_API_VERSION")
        if recorded and is_valid_version(recorded) and recorded != META_API_VERSION:
            trailing.add(name)
    assert trailing == PENDING_ENV_DEPLOY, (
        f"the set of functions whose live META_API_VERSION trails the repo default "
        f"({META_API_VERSION}) changed. If a deploy moved them, update PENDING_ENV_DEPLOY and "
        f"the audit document together; got {sorted(trailing)}"
    )


def test_the_deliberate_pin_is_not_in_the_pending_deploy_set():
    """The two kinds of lag must not be confused.

    One is waiting for a deploy and should close. The other is a decision and should not. Folding
    them together is how a deliberate exception gets "fixed" by someone tidying up.
    """
    assert DELIBERATE_PIN not in PENDING_ENV_DEPLOY


# ── the Python module and the generated JSON mirror still agree ──────────────────

def test_the_script_resolver_agrees_with_the_python_module():
    """Scripts resolve through `config/vendor-versions.json`; Lambdas use the Python constant.

    Two mechanisms, deliberately: a Lambda must not read a repo file to learn its own
    configuration, and a script cannot import from `amplify/functions/shared`. This asserts the
    two answers are the same, which is what makes having two mechanisms safe.
    """
    import meta_graph_version
    from lambda_utils.meta_version import GRAPH_BASE, META_API_VERSION

    assert meta_graph_version.graph_version() == META_API_VERSION
    assert meta_graph_version.graph_base() == GRAPH_BASE


def test_the_script_resolver_refuses_a_malformed_mirror(tmp_path, monkeypatch):
    """It validates on the way out, so a hand-edited mirror cannot reach a Graph URL."""
    import meta_graph_version

    bad = tmp_path / "vendor-versions.json"
    bad.write_text(json.dumps({"metaGraphApiVersion": "latest"}))
    monkeypatch.setattr(meta_graph_version, "_MIRROR", bad)
    with pytest.raises(RuntimeError) as caught:
        meta_graph_version.graph_version()
    assert type(caught.value).__name__ == "MetaGraphVersionUnavailable"


def test_a_missing_mirror_refuses_rather_than_defaulting(tmp_path, monkeypatch):
    import meta_graph_version

    monkeypatch.setattr(meta_graph_version, "_MIRROR", tmp_path / "absent.json")
    with pytest.raises(RuntimeError):
        meta_graph_version.graph_version()


# ── no script carries its own version literal any more ───────────────────────────

def test_no_script_hard_codes_a_graph_version():
    """The seventh source of truth, and the one the audit missed.

    `scripts/meta_webhook_control_plane.py` hard-coded `v23.0`. A literal here is invisible to
    both the module's validation and the version gate, so the script silently talks to a
    different API version than everything else. Comments are allowed to mention a version --
    recording what a line used to say is how the reason survives.
    """
    literal = re.compile(r"graph\.facebook\.com/v\d")
    offenders = []
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if not literal.search(line):
                continue
            if line.strip().startswith("#"):
                continue
            offenders.append(f"{path.relative_to(ROOT)}:{number}  {line.strip()[:90]}")
    assert not offenders, (
        "these scripts hard-code a Graph version instead of calling "
        "`meta_graph_version.graph_base()`:\n  " + "\n  ".join(offenders)
    )
