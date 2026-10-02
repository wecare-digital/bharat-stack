"""`META_GRAPH_BASE` is a configuration route, so it must be shape-checked like the other one.

The defect this covers, from `docs/execution/meta-graph-version-audit-20261001.md` section 4.1:
the Graph version had SIX sources of truth and two of them bypassed validation entirely. One is
`META_GRAPH_BASE`, a whole URL set on `wecare-marketing-ads`, which `marketing-ads/handler.py`
lets win over the shared module. `meta_version._VERSION_RE` never saw it, so a malformed or
unexpected version could reach Graph and answer 400 at request time about an unknown path --
which reads like an application bug rather than a configuration one.

The variable is deliberately KEPT rather than removed: pinning one function away from the fleet
default is a real need (the Shop Ads `destination_spec` question keeps `wecare-marketing-ads` on
v25.0 on purpose). Validating it is what makes that pin safe instead of a hole.

Why `pytest.raises(ValueError)` and not `mod.MetaVersionError`
-------------------------------------------------------------
`tests/test_meta_version.py:64-72` documents this and it applies identically here.
`pytest.raises` evaluates its argument BEFORE the reload, capturing the class object from the
OLD module namespace, while the reload re-executes the module body and defines a brand-new class
of the same name. `except OldClass` does not catch `NewClass`. `MetaVersionError` subclasses
`ValueError`, a builtin and therefore stable across reloads, so the assertion is made on
`ValueError` and the identity is checked by `type(exc).__name__`.
"""

from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))

HOST = "https://graph.facebook.com"


@pytest.fixture
def meta_version(monkeypatch):
    """The module, reloaded from a clean environment, and left in one afterwards.

    Both keys are cleared on the way in as well as out: another test in the session may have left
    one set, and this module's entire behaviour is a function of the environment at import time.
    The teardown undoes the monkeypatch FIRST and only then reloads, so the module every later
    test imports is the unconfigured one rather than whatever this test configured.
    """
    import lambda_utils.meta_version as mod

    monkeypatch.delenv("META_API_VERSION", raising=False)
    monkeypatch.delenv("META_GRAPH_BASE", raising=False)
    importlib.reload(mod)
    yield mod
    monkeypatch.undo()
    importlib.reload(mod)


def _reload_raises(monkeypatch, **env):
    import lambda_utils.meta_version as mod

    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError) as caught:
        importlib.reload(mod)
    assert type(caught.value).__name__ == "MetaVersionError"
    return caught.value


# ── absent behaves exactly as before ────────────────────────────────────────────

def test_with_no_base_set_the_module_behaves_as_it_always_did(meta_version):
    """The extension must not change the unconfigured path, which is 67 of 68 functions."""
    assert meta_version.META_API_VERSION == meta_version._DEFAULT
    assert meta_version.GRAPH_BASE == f"{HOST}/{meta_version.META_API_VERSION}"


# ── a well-formed base is accepted and becomes the version ──────────────────────

def test_a_well_formed_base_resolves_the_version_and_is_used_verbatim(meta_version, monkeypatch):
    """A deliberate per-function pin is reflected, not re-derived.

    `GRAPH_BASE` must equal what the operator configured. Rebuilding it from the extracted
    version would discard the actual setting and quietly make the two disagree again.
    """
    monkeypatch.setenv("META_GRAPH_BASE", f"{HOST}/v25.0")
    importlib.reload(meta_version)
    assert meta_version.META_API_VERSION == "v25.0"
    assert meta_version.GRAPH_BASE == f"{HOST}/v25.0"
    # And the helper that builds URLs follows it, so a pinned function really calls v25.0.
    assert meta_version.graph_url("123", "messages") == f"{HOST}/v25.0/123/messages"


def test_the_marketing_ads_pin_is_expressible_and_differs_from_the_fleet_default(
        meta_version, monkeypatch):
    """The concrete case this validation exists to make safe.

    `wecare-marketing-ads` stays on v25.0 while the fleet default moves to v26.0, because v26.0
    defaults Shop Ads `destination_spec` and WhatsApp-destination creative eligibility is
    undocumented. The point of the test is that the pin is a VALIDATED override rather than an
    unchecked string, and that it genuinely differs from the default.
    """
    monkeypatch.setenv("META_GRAPH_BASE", f"{HOST}/v25.0")
    importlib.reload(meta_version)
    assert meta_version.META_API_VERSION == "v25.0"
    assert meta_version._DEFAULT == "v26.0"
    assert meta_version.META_API_VERSION != meta_version._DEFAULT


# ── malformed bases are refused at import ───────────────────────────────────────

@pytest.mark.parametrize("bad", [
    f"{HOST}/v26.0.1",          # three components: not a Graph version
    f"{HOST}/v26",              # no minor
    HOST,                       # no version segment at all
    "http://graph.facebook.com/v26.0",   # not https
    f"{HOST}/v26.0/",           # trailing slash; graph_url joins with / itself
    f"{HOST}/v26.0/extra",      # extra path segment
    "https://evil.example.com/v26.0",    # right shape, wrong host
    "https://graph.facebook.com.evil.test/v26.0",  # host-prefix lookalike
    "",                         # configured and got it wrong
    "   ",
    "v26.0",                    # a version where a base was expected
])
def test_a_malformed_base_refuses_to_start(meta_version, monkeypatch, bad):
    error = _reload_raises(monkeypatch, META_GRAPH_BASE=bad)
    assert "META_GRAPH_BASE" in str(error)


def test_the_refusal_names_the_expected_form_rather_than_only_rejecting(
        meta_version, monkeypatch):
    """A configuration error should be fixable from the message alone."""
    error = str(_reload_raises(monkeypatch, META_GRAPH_BASE="https://graph.facebook.com/v26"))
    assert HOST in error
    assert "trailing slash" in error


# ── two sources that disagree raise rather than one silently winning ─────────────

def test_disagreeing_version_and_base_raise_instead_of_picking_a_winner(
        meta_version, monkeypatch):
    """No precedence rule, deliberately.

    A silent winner is exactly how one function ended up running on a version nothing had
    validated while the fleet read a different variable. The error names both values so whoever
    set the second one can see the conflict.
    """
    error = str(_reload_raises(monkeypatch, META_API_VERSION="v26.0",
                               META_GRAPH_BASE=f"{HOST}/v25.0"))
    assert "v26.0" in error and "v25.0" in error


def test_agreeing_version_and_base_are_accepted(meta_version, monkeypatch):
    monkeypatch.setenv("META_API_VERSION", "v25.0")
    monkeypatch.setenv("META_GRAPH_BASE", f"{HOST}/v25.0")
    importlib.reload(meta_version)
    assert meta_version.META_API_VERSION == "v25.0"
    assert meta_version.GRAPH_BASE == f"{HOST}/v25.0"


def test_a_malformed_version_still_raises_even_with_a_valid_base(meta_version, monkeypatch):
    """The original validation is not weakened by the new one.

    Order matters here: if the base were parsed first and allowed to supply the version, a
    nonsense `META_API_VERSION` beside a good base would stop being an error. It must not.
    """
    error = str(_reload_raises(monkeypatch, META_API_VERSION="latest",
                               META_GRAPH_BASE=f"{HOST}/v26.0"))
    assert "META_API_VERSION" in error


# ── the shared parse is exposed, so nothing re-derives it ───────────────────────

@pytest.mark.parametrize("value,expected", [
    (f"{HOST}/v26.0", "v26.0"),
    (f"{HOST}/v9.0", "v9.0"),
    (f"{HOST}/v100.0", "v100.0"),
    (f"  {HOST}/v26.0  ", "v26.0"),
    (f"{HOST}/v26", ""),
    (HOST, ""),
    ("", ""),
    (None, ""),
    ("https://evil.example.com/v26.0", ""),
])
def test_base_version_parses_the_same_way_the_module_does(meta_version, value, expected):
    assert meta_version.base_version(value) == expected
