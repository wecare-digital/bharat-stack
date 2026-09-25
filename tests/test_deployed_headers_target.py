"""Tests for scripts/verify_deployed_headers.py.

The bug these pin is not in the header logic - that was always right. It was the
TARGET: the script requested `app.wecare.digital`, a different CloudFront
distribution that Amplify's customHeaders never reach, so it reported RESULT: FAIL
against a host that was never meant to carry them. A gate that fails for a reason
unrelated to what it guards gets learned as noise, and then the real regression is
invisible. So the assertions here are mostly about *which host*.

No network access: the fetch is stubbed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "scripts" / "verify_deployed_headers.py"

_spec = importlib.util.spec_from_file_location("deployed_headers_under_test", _SCRIPT)
vdh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vdh)


GOOD_HEADERS = {
    "permissions-policy": "camera=(), microphone=(self), geolocation=()",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}


# ── the target ────────────────────────────────────────────────────────────────

def test_the_gate_targets_the_amplify_host_not_the_assets_distribution():
    """`amplify.yml` customHeaders are applied by Amplify Hosting. The Amplify app
    is served from the apex; `app.wecare.digital` is CloudFront ERCXSFDL0VM8X over
    S3 and can never carry them."""
    assert vdh.DEFAULT_URL == "https://wecare.digital/"
    assert "app.wecare.digital" not in vdh.DEFAULT_URL


def test_the_assets_distribution_is_still_named_but_kept_separate():
    """It is reported, because ignoring it is how its missing headers went unnoticed
    - but it must not be the gate, since fixing it is a CloudFront change."""
    assert vdh.ASSETS_URL == "https://app.wecare.digital/"
    assert vdh.ASSETS_URL != vdh.DEFAULT_URL


def test_the_assets_report_cannot_change_the_verdict(monkeypatch, capsys):
    """Reported, never gated. If the assets host has no headers at all - which is
    its real state - the Amplify origin still decides the exit code."""
    def fake(url):
        if url == vdh.ASSETS_URL:
            return 200, {"content-type": "text/html"}
        return 200, dict(GOOD_HEADERS)

    monkeypatch.setattr(vdh, "fetch_headers", fake)
    monkeypatch.setattr("sys.argv", ["verify_deployed_headers.py"])

    rc = vdh.main()
    out = capsys.readouterr().out

    assert rc == 0, "a bare assets distribution must not fail the gate"
    assert "reported, never gated" in out
    assert "RESULT: PASS" in out


def test_a_broken_assets_request_does_not_fail_the_gate(monkeypatch):
    def fake(url):
        if url == vdh.ASSETS_URL:
            raise OSError("boom")
        return 200, dict(GOOD_HEADERS)

    monkeypatch.setattr(vdh, "fetch_headers", fake)
    monkeypatch.setattr("sys.argv", ["verify_deployed_headers.py"])

    assert vdh.main() == 0


# ── the verdict still depends on the Amplify origin ───────────────────────────

def test_a_missing_permissions_policy_on_the_amplify_origin_fails(monkeypatch):
    monkeypatch.setattr(vdh, "fetch_headers",
                        lambda url: (200, {"x-content-type-options": "nosniff",
                                           "referrer-policy": "strict-origin-when-cross-origin"}))
    monkeypatch.setattr("sys.argv", ["verify_deployed_headers.py", "--no-assets"])

    assert vdh.main() == 1


def test_the_microphone_regression_this_script_was_written_for_still_fails(monkeypatch):
    """2026-09-19: config said microphone=(self), the deployed header said
    microphone=(). That is the exact case the script exists to catch."""
    bad = dict(GOOD_HEADERS)
    bad["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
    monkeypatch.setattr(vdh, "fetch_headers", lambda url: (200, bad))
    monkeypatch.setattr("sys.argv", ["verify_deployed_headers.py", "--no-assets"])

    assert vdh.main() == 1


def test_a_transport_failure_is_2_and_never_0(monkeypatch):
    """Exit 2, distinct from a header failure, and never a pass - an unreachable
    origin proves nothing about its headers."""
    def boom(url):
        raise OSError("dns")

    monkeypatch.setattr(vdh, "fetch_headers", boom)
    monkeypatch.setattr("sys.argv", ["verify_deployed_headers.py", "--no-assets"])

    assert vdh.main() == 2


# ── the parser, which was never the bug but is worth holding still ────────────

@pytest.mark.parametrize("value,expected", [
    ("camera=(), microphone=(self)", {"camera": "()", "microphone": "(self)"}),
    ("camera=()", {"camera": "()"}),
    ("", {}),
])
def test_permissions_policy_parsing(value, expected):
    assert vdh.parse_permissions_policy(value) == expected


def test_amplify_yml_is_the_configured_source_and_still_parses():
    """A narrow regex rather than a YAML parse, so the script keeps working in a
    bare CI shell with no third-party dependency."""
    assert vdh.amplify_yml_header() == "camera=(), microphone=(self), geolocation=()"
