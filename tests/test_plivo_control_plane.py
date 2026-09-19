"""§27 tests for the Plivo control plane. No network; the transport is stubbed.

The test that matters most is the `default_endpoint_app` one. On 2026-09-19 a
partial application update reset that field from true to false and it had to be
restored by hand. §5 makes it a protected invariant and requires automated tests,
so these pin three separate defences:

  1. a partial payload is never sent - every protected field is restated
  2. if the field comes back wrong anyway, read-back verification FAILS
  3. any unexpected field change is reported rather than ignored
"""
import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import plivo_control_plane as pcp  # noqa: E402

APP_BEFORE = {
    "app_id": pcp.APP_ID,
    "app_name": pcp.APP_NAME,
    "answer_url": "https://api.wecare.digital/plivo/answer?token=abc123secret",
    "answer_method": "POST",
    "fallback_answer_url": "https://api.wecare.digital/plivo/answer?token=abc123secret",
    "fallback_method": "POST",
    "hangup_url": "https://api.wecare.digital/plivo/answer?token=abc123secret",
    "hangup_method": "POST",
    "message_url": "",
    "message_method": "POST",
    "default_number_app": False,
    "default_endpoint_app": True,          # THE protected invariant
    "enabled": True,
    "public_uri": "",
    "sip_uri": pcp.APPLICATION_SIP_URI,
    "sip_auth_type": "credential",
    "credential_uuid": "30ad5c63-a41b-4b8c-b0f0-14693b6f4346",
    "ip_acl_uuid": None,
    "sub_account": None,
    "log_incoming_messages": True,
}

ENDPOINT = {
    "endpoint_id": "ep-1", "username": pcp.ENDPOINT_USERNAME,
    "alias": pcp.ENDPOINT_ALIAS, "sip_uri": pcp.ENDPOINT_SIP_URI,
    "application": f"/v1/Account/MAXXX/Application/{pcp.APP_ID}/",
    "sub_account": None,
    "password": "must-never-appear-in-a-snapshot",
}

NUMBER_OBJ = {
    "number": pcp.NUMBER, "alias": "WECARE DIGITAL",
    "application": f"/v1/Account/MAXXX/Application/{pcp.APP_ID}/",
    "number_type": "local", "voice_enabled": True, "sms_enabled": False,
    "sub_account": None,
}


class FakePlivo(pcp.PlivoControlPlaneService):
    """Records calls; serves a mutable in-memory application object."""

    read_back_delay = 0          # no real sleeping in tests

    def __init__(self, app=None):
        self._auth_id = "MAXXXXXXXXXXXXXXXXXX"
        self._auth = "ZmFrZQ=="
        self.app = copy.deepcopy(app or APP_BEFORE)
        self.posts = []
        self.apply_post_effect = None   # callable(app, payload) to simulate drift

    def _call(self, method, path, body=None, host=pcp.PLIVO_API):
        if method == "GET" and path.startswith(f"/Application/{pcp.APP_ID}"):
            return 200, copy.deepcopy(self.app)
        if method == "GET" and path == "/Application/":
            return 200, {"objects": [copy.deepcopy(self.app)]}
        if method == "GET" and path == "/Endpoint/":
            return 200, {"objects": [copy.deepcopy(ENDPOINT)]}
        if method == "GET" and path.startswith("/Number/"):
            return 200, copy.deepcopy(NUMBER_OBJ)
        if method == "GET":                      # trunk endpoints
            return 404, {"_error": "not found"}
        if method == "POST" and path.startswith(f"/Application/{pcp.APP_ID}"):
            self.posts.append(copy.deepcopy(body))
            self.app.update(body or {})
            if self.apply_post_effect:
                self.apply_post_effect(self.app, body or {})
            return 202, {"message": "changed"}
        if method == "POST" and path.startswith("/Number/"):
            self.posts.append({"_number": body})
            return 202, {"message": "changed"}
        return 400, {"_error": f"unexpected {method} {path}"}


@pytest.fixture
def svc():
    return FakePlivo()


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------
def test_application_read(svc):
    app = svc.get_application()
    assert app["app_id"] == pcp.APP_ID
    assert app["app_name"] == pcp.APP_NAME


def test_endpoint_located_by_username_not_position(svc):
    ep = svc.get_endpoint()
    assert ep["username"] == pcp.ENDPOINT_USERNAME
    assert ep["alias"] == pcp.ENDPOINT_ALIAS


def test_number_read(svc):
    assert svc.get_number()["number"] == pcp.NUMBER


def test_trunk_discovery_reports_status_instead_of_raising(svc):
    """A non-200 on one Zentrunk collection is information, not a failure."""
    trunks = svc.list_trunks()
    assert set(trunks) == {"trunks", "credentials", "ip_access_control_lists"}
    assert all(t["status"] == 404 for t in trunks.values())


def test_trunk_discovery_uses_the_zentrunk_path_prefix(svc):
    """Regression guard on paths that were wrong twice.

    Top-level /Trunk/ 404s and zentrunk.plivo.com resets the TLS connection;
    only the /Zentrunk/ prefix on api.plivo.com works.
    """
    paths = [p for _, p in pcp.PlivoControlPlaneService.ZENTRUNK_PATHS]
    assert all(p.startswith("/Zentrunk/") for p in paths), paths


def test_trunk_discovery_projects_the_real_field_names(svc):
    """The obvious guesses - direction, status, primary_uri - are all wrong."""
    fields = pcp.PlivoControlPlaneService.TRUNK_FIELDS
    for real in ("trunk_direction", "trunk_status", "trunk_domain"):
        assert real in fields
    for wrong in ("direction", "status", "primary_uri"):
        assert wrong not in fields


def test_trunk_credentials_never_echo_a_secret():
    class WithCreds(FakePlivo):
        def _call(self, method, path, body=None, host=pcp.PLIVO_API):
            if path == "/Zentrunk/Credential/":
                return 200, {"objects": [{"username": "wecare",
                                          "password": "leaked-secret"}]}
            if path.startswith("/Zentrunk/"):
                return 200, {"objects": []}
            return super()._call(method, path, body, host)

    out = WithCreds().list_trunks()
    assert "leaked-secret" not in json.dumps(out)
    assert out["credentials"]["objects"][0]["username"] == "wecare"


# --------------------------------------------------------------------------
# §14 the two SIP objects are different resources
# --------------------------------------------------------------------------
def test_application_sip_and_endpoint_sip_are_never_conflated(svc):
    info = svc.verify_application_sip()
    assert info["expected_application_sip"] == f"sip:{pcp.APP_ID}@app.plivo.com"
    assert info["endpoint_sip_uri_is_a_different_resource"] \
        == f"sip:{pcp.ENDPOINT_USERNAME}@phone.plivo.com"
    assert info["expected_application_sip"] != \
        info["endpoint_sip_uri_is_a_different_resource"]


def test_application_sip_is_verified_not_assumed(svc):
    svc.app["sip_uri"] = ""
    info = svc.verify_application_sip()
    assert info["observed_sip_uri"] == ""
    assert info["matches_expected"] is False, \
        "a predictable URI format must not be treated as proof it is enabled"


# --------------------------------------------------------------------------
# §7 planning
# --------------------------------------------------------------------------
def test_plan_identifies_exactly_the_two_url_changes(svc):
    rows = svc.plan_application_update()
    changed = {r["field"] for r in rows if r["change"]}
    assert changed == {"fallback_answer_url", "hangup_url"}


def test_plan_marks_answer_url_as_unchanged(svc):
    rows = svc.plan_application_update()
    answer = next(r for r in rows if r["field"] == "answer_url")
    assert answer["change"] is False


def test_plan_reports_protected_fields_with_critical_flag(svc):
    rows = svc.plan_application_update()
    dea = [r for r in rows if r["field"] == "default_endpoint_app"]
    assert dea, "protected fields must appear in the plan table"
    assert dea[0]["protected"] is True
    assert dea[0]["critical"] is True
    assert dea[0]["change"] is False


def test_plan_never_mutates(svc):
    before = copy.deepcopy(svc.app)
    svc.plan_application_update()
    assert svc.app == before
    assert svc.posts == []


def test_plan_compares_urls_without_the_token(svc):
    """The ?token= must not make an otherwise-identical URL look changed."""
    rows = svc.plan_application_update()
    answer = next(r for r in rows if r["field"] == "answer_url")
    assert "token" not in str(answer["current"])
    assert answer["current_token"].startswith("sha256:")


# --------------------------------------------------------------------------
# §5 the regression that already happened once
# --------------------------------------------------------------------------
def test_apply_restates_default_endpoint_app_in_the_payload(svc):
    """The actual defence: never send a partial update.

    Plivo replaces the fields it receives and the SDK defaults
    default_endpoint_app to False, so omitting it clears it.
    """
    rows = svc.plan_application_update()
    svc.apply_application_update(rows)
    assert len(svc.posts) == 1
    payload = svc.posts[0]
    assert "default_endpoint_app" in payload, \
        "omitting this field is what caused the 2026-09-19 regression"
    assert payload["default_endpoint_app"] is True
    assert payload["default_number_app"] is False
    assert payload["log_incoming_messages"] is True


def test_apply_preserves_default_endpoint_app_true(svc):
    svc.apply_application_update(svc.plan_application_update())
    assert svc.app["default_endpoint_app"] is True


def test_read_back_fails_when_default_endpoint_app_is_clobbered(svc):
    """Defence in depth: if the provider clears it anyway, we must notice."""
    def clobber(app, payload):
        app["default_endpoint_app"] = False
    svc.apply_post_effect = clobber
    result = svc.apply_application_update(svc.plan_application_update())
    v = result["verification"]
    assert v["ok"] is False
    assert any("CRITICAL INVARIANT default_endpoint_app" in f for f in v["failures"])


def test_read_back_detects_an_unexpected_protected_change(svc):
    def clobber(app, payload):
        app["credential_uuid"] = "something-else"
    svc.apply_post_effect = clobber
    v = svc.apply_application_update(svc.plan_application_update())["verification"]
    assert v["ok"] is False
    assert any("PROTECTED credential_uuid changed" in f for f in v["failures"])


def test_read_back_detects_application_being_disabled(svc):
    def clobber(app, payload):
        app["enabled"] = False
    svc.apply_post_effect = clobber
    v = svc.apply_application_update(svc.plan_application_update())["verification"]
    assert v["ok"] is False
    assert any("PROTECTED enabled changed" in f for f in v["failures"])


# --------------------------------------------------------------------------
# §8 read-back verification
# --------------------------------------------------------------------------
def test_successful_apply_verifies_all_three_urls_and_methods(svc):
    v = svc.apply_application_update(svc.plan_application_update())["verification"]
    assert v["ok"] is True, v["failures"]
    checked = {c["check"] for c in v["checks"]}
    for field in ("answer_url", "fallback_answer_url", "hangup_url",
                  "answer_method", "fallback_method", "hangup_method"):
        assert field in checked


def test_http_202_alone_is_not_treated_as_success(svc):
    """The provider returns 202 and applies asynchronously; only the persisted
    object counts."""
    def lie(app, payload):
        app["hangup_url"] = "https://api.wecare.digital/plivo/answer"
    svc.apply_post_effect = lie
    result = svc.apply_application_update(svc.plan_application_update())
    assert result["http_status"] == 202
    assert result["verification"]["ok"] is False


def test_apply_preserves_the_token_query_string(svc):
    """A reconcile must not silently disarm the ?token= gate."""
    svc.apply_application_update(svc.plan_application_update())
    assert "token=abc123secret" in svc.app["hangup_url"]
    assert "token=abc123secret" in svc.app["fallback_answer_url"]


def test_apply_is_a_noop_when_already_converged(svc):
    svc.apply_application_update(svc.plan_application_update())
    svc.posts.clear()
    result = svc.apply_application_update(svc.plan_application_update())
    assert result["applied"] is False
    assert svc.posts == []


def test_rollback_restores_the_before_state(svc):
    before = copy.deepcopy(svc.app)
    svc.apply_application_update(svc.plan_application_update())
    assert svc.app["hangup_url"] != before["hangup_url"]
    rb = svc.rollback_application_update(before)
    assert rb["restored"] is True
    assert svc.app["default_endpoint_app"] is True


# --------------------------------------------------------------------------
# §10/§11 number routing guard
# --------------------------------------------------------------------------
def test_number_plan_defaults_to_no_change_and_is_compliant(svc):
    plan = svc.plan_number_routing_change()
    assert plan["change"] is False
    assert plan["compliant"] is True
    assert plan["current_application"] == pcp.APP_ID


def test_number_plan_never_mutates(svc):
    svc.plan_number_routing_change(target_trunk_id="trunk-123")
    assert svc.posts == []


def test_number_plan_for_a_trunk_is_flagged_as_a_production_cutover(svc):
    plan = svc.plan_number_routing_change(target_trunk_id="trunk-123")
    assert plan["change"] is True
    assert "PRODUCTION ROUTING CUTOVER" in plan["risk"]
    assert "explicit production approval" in plan["requires"]
    assert "does NOT prove the SIP route works" in plan["warning"]


def test_number_routing_apply_refuses_without_explicit_approval(svc):
    with pytest.raises(pcp.PlivoError) as exc:
        svc.apply_number_routing_change(target_app_id="999")
    assert "approved=True" in str(exc.value)
    assert svc.posts == [], "a refused cutover must not have mutated anything"


def test_number_routing_apply_proceeds_when_approved(svc):
    svc.apply_number_routing_change(target_app_id="999", approved=True)
    assert svc.posts and "_number" in svc.posts[0]


# --------------------------------------------------------------------------
# §26 snapshots must never carry credential material
# --------------------------------------------------------------------------
def test_snapshot_excludes_the_endpoint_password(svc):
    snap = svc.snapshot_current_state(write=False)
    assert "must-never-appear-in-a-snapshot" not in json.dumps(snap)
    assert "password" not in json.dumps(snap).lower()


def test_snapshot_excludes_the_url_token_but_keeps_a_fingerprint(svc):
    snap = svc.snapshot_current_state(write=False)
    blob = json.dumps(snap)
    assert "abc123secret" not in blob
    assert snap["application"]["answer_url_token"].startswith("sha256:")


def test_snapshot_captures_every_required_field(svc):
    snap = svc.snapshot_current_state(write=False)
    for field in pcp.CAPTURED_FIELDS:
        assert field in snap["application"], f"§4 requires {field}"


def test_snapshot_records_provenance(svc):
    snap = svc.snapshot_current_state(write=False)
    for key in ("timestamp", "resource_type", "git_commit", "environment"):
        assert snap.get(key), f"§26 requires {key}"


def test_sanitizer_rejects_credential_material():
    with pytest.raises(pcp.PlivoError):
        pcp._assert_sanitized({"auth_token": "leaked"})


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url,expected", [
    ("https://a.example/p?token=x", "https://a.example/p"),
    ("https://a.example/p", "https://a.example/p"),
    ("", ""),
    (None, ""),
])
def test_strip_query(url, expected):
    assert pcp._strip_query(url) == expected


def test_token_fingerprint_is_stable_and_does_not_reveal_the_token():
    a = pcp._token_fingerprint("https://x/y?token=supersecret")
    b = pcp._token_fingerprint("https://other/z?token=supersecret")
    assert a == b
    assert "supersecret" not in a
    assert pcp._token_fingerprint("https://x/y") == ""


# --------------------------------------------------------------------------
# Unset-value equivalence — the false positive that rolled back a good apply
# --------------------------------------------------------------------------
@pytest.mark.parametrize("a,b", [
    (None, ""), ("", None), (None, None), ("", ""), ([], None), ({}, ""),
])
def test_unset_forms_compare_as_equal(a, b):
    assert pcp._same(a, b) is True


@pytest.mark.parametrize("a,b", [
    ("x", None), (None, "x"), ("x", "y"), (True, False), (True, None),
])
def test_real_differences_still_compare_as_different(a, b):
    assert pcp._same(a, b) is False


def test_ip_acl_uuid_empty_to_none_is_not_a_protected_change(svc):
    """The exact false positive seen on the first live --apply.

    Plivo returns an unset field as '' on the GET and None on the POST response.
    A naive == flagged ip_acl_uuid: '' -> None as a protected-field change, and
    rolled back an apply whose URLs and critical invariant had all passed.
    """
    svc.app["ip_acl_uuid"] = ""

    def to_none(app, payload):
        app["ip_acl_uuid"] = None       # what Plivo actually does

    svc.apply_post_effect = to_none
    v = svc.apply_application_update(svc.plan_application_update())["verification"]
    assert v["ok"] is True, v["failures"]


def test_a_genuine_ip_acl_change_is_still_caught(svc):
    """The loosening must not blind the check to a real assignment."""
    def assign(app, payload):
        app["ip_acl_uuid"] = "acl-abc-123"

    svc.apply_post_effect = assign
    v = svc.apply_application_update(svc.plan_application_update())["verification"]
    assert v["ok"] is False
    assert any("ip_acl_uuid" in f for f in v["failures"])
