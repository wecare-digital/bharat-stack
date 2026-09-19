"""Drift detection on the Plivo control plane.

Drift is an out-of-band change to live provider state: someone used the console,
or another script, or a person clicked something. The check exists because the
repository's tooling is declared to be the source of truth, and that claim is only
meaningful if a departure from it is detected.

Two properties matter more than the individual comparisons:

  1. It NEVER converges. A check that silently fixed drift would erase the
     evidence of what moved and when, and would make an unreviewed change to
     production call routing.
  2. Severity is split. A callback URL moving is recoverable with a reviewed
     apply; the number-to-application binding moving means inbound calls are not
     arriving, and "fixing" it blind could be the second mistake.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import plivo_control_plane as cp  # noqa: E402

APP_ID = cp.APP_ID
NUMBER = cp.NUMBER
ENDPOINT_USERNAME = cp.ENDPOINT_USERNAME


def _healthy_app():
    return {
        "app_id": APP_ID,
        "app_name": cp.APP_NAME,
        "default_endpoint_app": True,
        "enabled": True,
        "public_uri": True,
        "sip_uri": cp.APPLICATION_SIP_URI,
        "sip_auth_type": "credential",
        "credential_uuid": "uuid-1",
        "ip_acl_uuid": "",
        "sub_account": None,
        "answer_url": f"{cp.TARGET_URLS['answer_url']}?token=secret",
        "fallback_answer_url": f"{cp.TARGET_URLS['fallback_answer_url']}?token=secret",
        "hangup_url": f"{cp.TARGET_URLS['hangup_url']}?token=secret",
        "answer_method": "POST",
        "fallback_method": "POST",
        "hangup_method": "POST",
    }


def _healthy_number():
    return {
        "number": NUMBER,
        "alias": "WECARE DIGITAL",
        "application": f"/v1/Account/AUTH/Application/{APP_ID}/",
        "number_type": "local",
        "voice_enabled": True,
        "sms_enabled": False,
    }


def _healthy_endpoint():
    return {
        "endpoint_id": "543585900967411",
        "username": ENDPOINT_USERNAME,
        "alias": cp.ENDPOINT_ALIAS,
        "sip_uri": cp.ENDPOINT_SIP_URI,
        "application": f"/v1/Account/AUTH/Application/{APP_ID}/",
        "sub_account": None,
    }


@pytest.fixture
def svc(monkeypatch):
    """A service whose provider reads are stubbed. No network, no credentials."""
    instance = cp.PlivoControlPlaneService.__new__(cp.PlivoControlPlaneService)
    instance._auth_id = "AUTHID"
    state = {
        "app": _healthy_app(),
        "number": _healthy_number(),
        "endpoint": _healthy_endpoint(),
    }
    monkeypatch.setattr(instance, "get_application", lambda *a, **k: state["app"],
                        raising=False)
    monkeypatch.setattr(instance, "get_number", lambda *a, **k: state["number"],
                        raising=False)
    monkeypatch.setattr(instance, "get_endpoint", lambda *a, **k: state["endpoint"],
                        raising=False)
    instance._state = state
    return instance


# --------------------------------------------------------------------------
# the clean case
# --------------------------------------------------------------------------
def test_healthy_state_reports_no_drift(svc):
    report = svc.check_drift()
    assert report["drifted"] is False
    assert report["critical"] == []
    assert report["warnings"] == []


def test_report_declares_itself_read_only(svc):
    """So no consumer can mistake a drift report for a converge."""
    assert svc.check_drift()["read_only"] is True


def test_report_never_mutates_provider_state(svc):
    before = dict(svc._state["app"])
    svc.check_drift()
    assert svc._state["app"] == before


def test_report_carries_no_secret(svc):
    """_assert_sanitized runs inside check_drift; prove a token cannot leak."""
    svc._state["app"]["answer_url"] = (
        f"{cp.TARGET_URLS['answer_url']}?token=super-secret-value")
    report = svc.check_drift()
    assert "super-secret-value" not in str(report)


# --------------------------------------------------------------------------
# CRITICAL: live routing or identity moved
# --------------------------------------------------------------------------
def test_default_endpoint_app_flipping_is_critical(svc):
    """The one invariant with a known regression history."""
    svc._state["app"]["default_endpoint_app"] = False
    report = svc.check_drift()
    assert report["critical_count"] == 1
    assert report["critical"][0]["field"] == "default_endpoint_app"
    assert report["critical"][0]["kind"] == "critical_invariant"


def test_number_unbound_from_the_application_is_critical(svc):
    """This is production call routing. Inbound calls stop arriving."""
    svc._state["number"]["application"] = "/v1/Account/AUTH/Application/999/"
    report = svc.check_drift()
    kinds = [c["kind"] for c in report["critical"]]
    assert "number_routing" in kinds
    detail = next(c for c in report["critical"] if c["kind"] == "number_routing")
    assert NUMBER in detail["detail"]


def test_sms_enabled_on_the_number_is_critical(svc):
    """Plivo SMS is prohibited. Enabling it at the provider is a policy breach."""
    svc._state["number"]["sms_enabled"] = True
    report = svc.check_drift()
    kinds = [c["kind"] for c in report["critical"]]
    assert "prohibited_capability" in kinds


def test_changed_application_identity_is_critical(svc):
    svc._state["app"]["app_id"] = "999"
    report = svc.check_drift()
    assert any(c["kind"] == "identity" for c in report["critical"])


def test_endpoint_reassigned_to_another_application_is_critical(svc):
    svc._state["endpoint"]["application"] = "/v1/Account/AUTH/Application/999/"
    report = svc.check_drift()
    assert any(c["kind"] == "endpoint_routing" for c in report["critical"])


def test_renamed_endpoint_is_critical(svc):
    svc._state["endpoint"]["username"] = "someone-else"
    report = svc.check_drift()
    assert any(c["field"] == "endpoint.username" for c in report["critical"])


# --------------------------------------------------------------------------
# WARN: recoverable
# --------------------------------------------------------------------------
def test_changed_callback_url_is_a_warning_not_critical(svc):
    svc._state["app"]["answer_url"] = "https://evil.example/plivo/answer?token=x"
    report = svc.check_drift()
    assert report["critical"] == []
    assert any(w["kind"] == "callback_url" for w in report["warnings"])


def test_method_downgraded_to_get_is_a_warning(svc):
    svc._state["app"]["hangup_method"] = "GET"
    report = svc.check_drift()
    assert any(w["field"] == "hangup_method" for w in report["warnings"])


def test_url_comparison_ignores_the_token_query(svc):
    """A token rotation must not read as a URL change."""
    svc._state["app"]["answer_url"] = (
        f"{cp.TARGET_URLS['answer_url']}?token=a-completely-different-token")
    report = svc.check_drift()
    assert not any(w["field"] == "answer_url" for w in report["warnings"])


def test_url_drift_reports_a_token_fingerprint_not_a_token(svc):
    svc._state["app"]["answer_url"] = "https://elsewhere.example/x?token=abc123"
    report = svc.check_drift()
    warning = next(w for w in report["warnings"] if w["field"] == "answer_url")
    assert "abc123" not in str(warning)
    if warning.get("token_fingerprint"):
        assert warning["token_fingerprint"].startswith("sha256:")


def test_missing_endpoint_is_a_warning_not_critical(svc):
    """The endpoint can be recreated; a misrouted number cannot be guessed at."""
    svc._state["endpoint"] = None
    monkey = svc.get_endpoint
    svc.get_endpoint = lambda *a, **k: None
    try:
        report = svc.check_drift()
    finally:
        svc.get_endpoint = monkey
    assert any(w["kind"] == "endpoint_missing" for w in report["warnings"])
    assert report["critical"] == []


# --------------------------------------------------------------------------
# severity is actionable
# --------------------------------------------------------------------------
def test_critical_and_warnings_are_counted_separately(svc):
    svc._state["app"]["default_endpoint_app"] = False
    svc._state["app"]["hangup_method"] = "GET"
    report = svc.check_drift()
    assert report["critical_count"] == 1
    assert report["warning_count"] == 1
    assert report["drifted"] is True


def test_what_was_checked_is_reported(svc):
    """A passing check must say what it covered, or it cannot be trusted."""
    checked = svc.check_drift()["checked"]
    assert checked["app_id"] == APP_ID
    assert checked["number"] == NUMBER
    assert checked["endpoint_username"] == ENDPOINT_USERNAME
    assert "default_endpoint_app" in checked["critical_invariants"]
    assert "sip_uri" in checked["protected_fields"]
