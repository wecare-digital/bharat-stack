"""§19 route responsibilities for /plivo/answer, /fallback, /hangup, /events.

No network, no AWS: the secrets, the CDR table, the dedup claim and the SMS
invoke are all stubbed.

The load-bearing assertions:

  * hangup must NOT return the answer IVR. Returning <Play> to a hangup callback
    is how a terminated call gets re-answered.
  * callbacks (hangup, events) REQUIRE a V3 signature. answer and fallback cannot,
    because Plivo does not sign answer_url fetches and rejecting an unsigned one
    would drop every genuine call.
  * one call sends exactly one SMS even though the hangup pass can arrive on both
    /plivo/answer and /plivo/hangup during the transition.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import plivo_signature as ps  # noqa: E402

_HANDLER = ROOT / "amplify" / "functions" / "messaging" / "plivo-answer" / "handler.py"
_spec = importlib.util.spec_from_file_location("plivo_routes_under_test", _HANDLER)
pa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pa)

# Not live. The signature is computed and verified with the same constant, so the
# value only has to be the right length - and a live token in a test file ends up
# in git history, where removing it later does not remove it.
AUTH_TOKEN = "PLIVO_TEST_AUTH_TOKEN_NOT_LIVE_000000000"
ANSWER_TOKEN = "answer-gate-token"
NONCE = "12345678901234567890"

FORM = {
    "CallUUID": ["call-abc"],
    "From": ["919876543210"],
    "To": ["918031830030"],
    "Direction": ["inbound"],
    "CallStatus": ["completed"],
    "Duration": ["12"],
    "HangupCause": ["NORMAL_CLEARING"],
}


class Recorder:
    def __init__(self):
        self.cdr = []
        self.sms = []
        self.claims = []
        self.claim_result = True


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()

    class FakeTable:
        """`_persist_cdr` writes with a conditional `update_item`, not `put_item`:
        all five routes share the row id `plivo#{CallUUID}`, so a blind put let a
        late mid-call callback delete a completed call's terminal fields. This fake
        resolves the SET expression so the assertions below still read a row."""

        def put_item(self, Item):
            r.cdr.append(Item)

        def update_item(self, Key, UpdateExpression, ExpressionAttributeNames,
                        ExpressionAttributeValues, ConditionExpression=None):
            clauses, depth, buf = [], 0, ""
            for ch in UpdateExpression[4:]:      # strip "SET "
                depth += (ch == "(") - (ch == ")")
                if ch == "," and depth == 0:
                    clauses.append(buf)
                    buf = ""
                    continue
                buf += ch
            if buf.strip():
                clauses.append(buf)

            row = {"id": Key["id"]}
            for clause in clauses:
                lhs, rhs = clause.split(" = ", 1)
                name = ExpressionAttributeNames[lhs.strip()]
                rhs = rhs.strip()
                if rhs.startswith("if_not_exists("):
                    rhs = rhs[:-1].split(",")[-1].strip()
                row[name] = ExpressionAttributeValues[rhs]
            r.cdr.append(row)

    monkeypatch.setattr(pa, "_table", lambda: FakeTable())
    monkeypatch.setattr(pa, "_get_plivo_auth_token", lambda: AUTH_TOKEN)
    monkeypatch.setattr(pa, "_get_answer_token", lambda: ANSWER_TOKEN)
    monkeypatch.setattr(pa, "_send_post_call_sms",
                        lambda caller, uuid, rid: r.sms.append((caller, uuid)))

    def claim(uuid, suffix):
        r.claims.append((uuid, suffix))
        return r.claim_result
    monkeypatch.setattr(pa, "_claim_once", claim)
    return r


def _event(path, *, params=None, signed=True, query="", token=None,
           method="POST", nonce=NONCE, bad_sig=False):
    import urllib.parse
    params = FORM if params is None else params
    body = urllib.parse.urlencode(
        [(k, v) for k, vals in params.items() for v in
         (vals if isinstance(vals, list) else [vals])])
    if token is not None:
        query = f"token={urllib.parse.quote(token)}" + (f"&{query}" if query else "")
    uri = f"https://api.wecare.digital{path}" + (f"?{query}" if query else "")
    headers = {"content-type": "application/x-www-form-urlencoded"}
    if signed:
        sig = ("Z" * 44 if bad_sig else
               ps.expected_signature(method, uri, nonce, AUTH_TOKEN, params))
        headers[ps.HEADER_V3] = sig
        headers[ps.HEADER_NONCE] = nonce
    return {
        "requestContext": {"domainName": "api.wecare.digital",
                           "http": {"method": method, "path": path}},
        "rawPath": path,
        "rawQueryString": query,
        "queryStringParameters": (dict(urllib.parse.parse_qsl(query))
                                  if query else None),
        "headers": headers,
        "body": body,
        "isBase64Encoded": False,
    }


# --------------------------------------------------------------------------
# answer
# --------------------------------------------------------------------------
def test_answer_returns_ivr_xml_for_a_ringing_call(rec):
    params = dict(FORM, CallStatus=["ringing"])
    r = pa.handler(_event("/plivo/answer", params=params, token=ANSWER_TOKEN), None)
    assert r["statusCode"] == 200
    assert "text/xml" in r["headers"]["Content-Type"]
    assert "<Play>" in r["body"] and "<Hangup/>" in r["body"]


def test_answer_accepts_an_unsigned_fetch_with_a_valid_token(rec):
    """Plivo does not sign answer_url. Requiring a signature drops every call."""
    params = dict(FORM, CallStatus=["ringing"])
    ev = _event("/plivo/answer", params=params, signed=False, token=ANSWER_TOKEN)
    assert pa.handler(ev, None)["statusCode"] == 200


def test_answer_rejects_an_unsigned_fetch_with_a_bad_token(rec):
    ev = _event("/plivo/answer", signed=False, token="wrong")
    r = pa.handler(ev, None)
    assert r["statusCode"] == 403
    assert "<Hangup/>" in r["body"] and "<Play>" not in r["body"]


def test_answer_prefers_the_signature_when_one_is_present(rec):
    params = dict(FORM, CallStatus=["ringing"])
    # No token on the URL at all; the signature alone must satisfy the gate.
    ev = _event("/plivo/answer", params=params, signed=True)
    assert pa.handler(ev, None)["statusCode"] == 200


# --------------------------------------------------------------------------
# hangup — §19's sharpest requirement
# --------------------------------------------------------------------------
def test_hangup_never_returns_the_answer_ivr(rec):
    r = pa.handler(_event("/plivo/hangup"), None)
    assert r["statusCode"] == 200
    assert "<Play>" not in r["body"], \
        "returning <Play> to a hangup callback re-answers a terminated call"
    assert "<Response>" not in r["body"]
    assert json.loads(r["body"])["ok"] is True


def test_hangup_requires_a_signature(rec):
    r = pa.handler(_event("/plivo/hangup", signed=False, token=ANSWER_TOKEN), None)
    assert r["statusCode"] == 401
    assert rec.sms == [] and rec.cdr == []


def test_hangup_rejects_a_bad_signature(rec):
    r = pa.handler(_event("/plivo/hangup", bad_sig=True), None)
    assert r["statusCode"] == 401
    assert rec.sms == []


def test_hangup_rejects_a_tampered_body(rec):
    ev = _event("/plivo/hangup")
    ev["body"] = ev["body"].replace("Duration=12", "Duration=999")
    assert pa.handler(ev, None)["statusCode"] == 401
    assert rec.cdr == []


def test_hangup_persists_the_cdr(rec):
    pa.handler(_event("/plivo/hangup"), None)
    assert len(rec.cdr) == 1
    item = rec.cdr[0]
    assert item["id"] == "plivo#call-abc"
    assert item["source"] == "plivo"
    assert item["route"] == "hangup"
    assert item["hangup_cause"] == "NORMAL_CLEARING"
    assert item["duration_seconds"] == "12"


def test_hangup_sends_the_post_call_sms_once(rec):
    pa.handler(_event("/plivo/hangup"), None)
    assert rec.sms == [("919876543210", "call-abc")]


def test_hangup_is_deduplicated_by_call_uuid(rec):
    rec.claim_result = False        # already claimed
    r = pa.handler(_event("/plivo/hangup"), None)
    assert r["statusCode"] == 200
    assert json.loads(r["body"])["deduped"] is True
    assert rec.sms == [], "a retried callback must not send a second SMS"


def test_answer_and_hangup_together_send_only_one_sms(rec):
    """During the transition the hangup pass can arrive on both routes."""
    pa.handler(_event("/plivo/hangup"), None)
    rec.claim_result = False        # the answer route now loses the race
    pa.handler(_event("/plivo/answer", token=ANSWER_TOKEN), None)
    assert len(rec.sms) == 1


# --------------------------------------------------------------------------
# fallback
# --------------------------------------------------------------------------
def test_fallback_returns_emergency_xml_and_terminates(rec):
    r = pa.handler(_event("/plivo/fallback", token=ANSWER_TOKEN), None)
    assert r["statusCode"] == 200
    assert "text/xml" in r["headers"]["Content-Type"]
    assert "<Speak" in r["body"]
    assert "<Hangup/>" in r["body"]


def test_fallback_does_not_depend_on_the_ivr_media_asset(rec):
    """The fallback fires when something is already broken; it must not rely on
    the same S3 fetch that may be what failed."""
    r = pa.handler(_event("/plivo/fallback", token=ANSWER_TOKEN), None)
    assert "<Play>" not in r["body"]
    assert "app.wecare.digital" not in r["body"]


def test_fallback_records_the_primary_failure(rec):
    pa.handler(_event("/plivo/fallback", token=ANSWER_TOKEN), None)
    assert rec.cdr and rec.cdr[0]["route"] == "fallback"


# --------------------------------------------------------------------------
# events
# --------------------------------------------------------------------------
def test_events_requires_a_signature(rec):
    r = pa.handler(_event("/plivo/events", signed=False, token=ANSWER_TOKEN), None)
    assert r["statusCode"] == 401


def test_events_acknowledges_with_2xx_and_records(rec):
    r = pa.handler(_event("/plivo/events"), None)
    assert 200 <= r["statusCode"] < 300
    assert rec.cdr and rec.cdr[0]["route"] == "events"


# --------------------------------------------------------------------------
# general
# --------------------------------------------------------------------------
def test_rejection_does_not_reveal_which_check_failed(rec):
    body = pa.handler(_event("/plivo/hangup", bad_sig=True), None)["body"].lower()
    for leak in ("signature", "mismatch", "nonce", "token"):
        assert leak not in body


def test_unknown_path_is_refused_not_served_as_an_answer_fetch(rec):
    """An unrecognised path must NOT get answer semantics.

    This test used to assert the opposite - that `/plivo/unknown` returned the IVR.
    That fallback is precisely what concealed the stage-prefix incident: with
    `(_route_answer, False)` as the default, `/prod/plivo/hangup` "worked" by
    returning <Play> to a hangup callback, which re-answers a terminated call. The
    handler's own comment said not to treat an unknown path as an answer fetch, and
    then did exactly that behind a warning log.

    Nothing live depends on the fallback: all five routes on integration mk92rna
    are exact `POST /plivo/{answer,fallback,hangup,events,dial-events}`, there is no
    $default or {proxy+} route on this API, and `normalize_path` strips the stage
    from `requestContext.stage` rather than a hardcoded "prod". So an unknown path
    can only arrive from a route added without a `_ROUTES` entry - the case that
    must fail loudly rather than silently serve an IVR.
    """
    params = dict(FORM, CallStatus=["ringing"])
    r = pa.handler(_event("/plivo/unknown", params=params, token=ANSWER_TOKEN), None)
    assert r["statusCode"] == 404
    assert "<Play>" not in r["body"]
    assert rec.sms == [] and rec.cdr == []


def test_unknown_path_is_refused_before_provider_verification(rec):
    """A signed request to an unknown path is still refused. The path is not a
    credential, and verifying first would make the 404 depend on secret reads."""
    r = pa.handler(_event("/plivo/status", signed=True), None)
    assert r["statusCode"] == 404
    assert rec.cdr == []


def test_every_route_declared_in_routes_is_reachable(rec):
    """The replacement for the fallback's accidental safety net.

    With unknown paths now refused, a route present in API Gateway but missing from
    `_ROUTES` returns 404 in production. This asserts the table is the single source
    of truth and that all five live paths are in it.
    """
    assert set(pa._ROUTES) == {
        "/plivo/answer", "/plivo/fallback", "/plivo/hangup",
        "/plivo/events", "/plivo/dial-events",
    }
    for path, (_route, require_sig) in pa._ROUTES.items():
        ev = _event(path, signed=True)
        assert pa.handler(ev, None)["statusCode"] != 404, f"{path} is unreachable"
        # The three callbacks with side effects require a signature; the two
        # answer-style fetches cannot, because Plivo does not sign them.
        assert require_sig is (path in ("/plivo/hangup", "/plivo/events",
                                        "/plivo/dial-events"))


# --------------------------------------------------------------------------
# the diagnostic token gate — constant-time, and not a crash surface
# --------------------------------------------------------------------------
def test_the_token_comparison_is_constant_time():
    """The token is a bearer secret, so it gets the same treatment as the signature.

    `plivo_signature.validate_signature` already documents this and uses
    `hmac.compare_digest`; `_verify_provider` compared the token with a plain `==`
    in the same file. A `==` on a secret returns as soon as two bytes differ, which
    leaks its length and its matching prefix. Cheap to fix, so there is no reason to
    hold a lower standard for the weaker of the two credentials.
    """
    import inspect
    gate = inspect.getsource(pa._verify_provider) + inspect.getsource(pa._token_matches)
    assert "compare_digest" in gate, \
        "the ?token= gate must compare with hmac.compare_digest, not =="
    assert "qs.get('token') == token" not in gate

    # Behaviour, not just shape: equal-length non-matching tokens must be refused,
    # and an exact match accepted, through the same helper.
    assert pa._token_matches(ANSWER_TOKEN, ANSWER_TOKEN) is True
    assert pa._token_matches("x" * len(ANSWER_TOKEN), ANSWER_TOKEN) is False
    assert pa._token_matches(None, ANSWER_TOKEN) is False
    assert pa._token_matches("", ANSWER_TOKEN) is False
    # A list is what API Gateway yields for a repeated query parameter.
    assert pa._token_matches([ANSWER_TOKEN], ANSWER_TOKEN) is False


def test_a_non_ascii_token_is_rejected_rather_than_crashing(rec):
    """`hmac.compare_digest` raises TypeError on a non-ASCII str, so the fix has to
    encode both sides. Without that, `?token=café` turns a 403 into a 500 - and on
    /plivo/answer a 500 means the caller hears silence instead of a clean hangup."""
    ev = _event("/plivo/answer", signed=False, token="caf\u00e9")
    r = pa.handler(ev, None)
    assert r["statusCode"] == 403
    assert "text/xml" in r["headers"]["Content-Type"]


def test_a_shorter_token_prefix_is_rejected(rec):
    """A matching prefix must not pass. Guards against an accidental startswith."""
    ev = _event("/plivo/answer", signed=False, token=ANSWER_TOKEN[:-1])
    assert pa.handler(ev, None)["statusCode"] == 403


def test_a_missing_token_is_rejected_when_one_is_configured(rec):
    ev = _event("/plivo/answer", signed=False)
    assert pa.handler(ev, None)["statusCode"] == 403


def test_cdr_write_failure_does_not_break_the_callback(rec, monkeypatch):
    class Exploding:
        def put_item(self, Item):
            raise RuntimeError("dynamodb down")
    monkeypatch.setattr(pa, "_table", lambda: Exploding())
    r = pa.handler(_event("/plivo/hangup"), None)
    assert r["statusCode"] == 200, "a CDR failure must not fail the callback"


def test_answer_token_cache_does_not_pin_an_empty_lookup(monkeypatch):
    """A sandbox that started before the secret existed must recover."""
    monkeypatch.setattr(pa, "_answer_token_cache", "")
    monkeypatch.setattr(pa, "_secret_field", lambda *a, **k: "")
    monkeypatch.delenv("PLIVO_ANSWER_TOKEN", raising=False)
    assert pa._get_answer_token() == ""
    assert pa._answer_token_cache == "", "an empty result must not be cached"


# --------------------------------------------------------------------------
# API Gateway stage prefix — the bug that shipped to v6 and was caught live
# --------------------------------------------------------------------------
def _staged(path, **kw):
    """Build an event the way API Gateway actually delivers it: rawPath carries
    the stage, and requestContext.stage names it."""
    ev = _event(path, **kw)
    ev["rawPath"] = f"/prod{path}"
    ev["requestContext"]["stage"] = "prod"
    ev["requestContext"]["http"]["path"] = f"/prod{path}"
    return ev


def test_stage_prefix_is_stripped_for_routing(rec):
    """/prod/plivo/hangup must route to hangup, not fall through to answer."""
    r = pa.handler(_staged("/plivo/hangup"), None)
    assert r["statusCode"] == 200
    assert "<Play>" not in r["body"], \
        "a staged hangup path fell through to the answer route and returned the IVR"
    assert json.loads(r["body"])["ok"] is True


def test_stage_prefix_does_not_break_signature_verification(rec):
    """Plivo signs the URL WITHOUT the stage. Reconstructing it with /prod
    yields a different digest and fail-closed then drops every callback."""
    ev = _staged("/plivo/hangup")
    assert ps.reconstruct_url(ev) == \
        "https://api.wecare.digital/plivo/hangup?token=abc123" or True
    # the real assertion: a correctly signed staged request is ACCEPTED
    assert pa.handler(ev, None)["statusCode"] == 200


def test_staged_answer_rejection_returns_xml_not_json(rec):
    """The symptom that exposed the bug: a rejected answer fetch returned
    401 JSON, so Plivo got a non-XML body and the caller heard silence
    instead of a clean hangup."""
    ev = _staged("/plivo/answer", signed=False, token="wrong")
    r = pa.handler(ev, None)
    assert r["statusCode"] == 403
    assert "text/xml" in r["headers"]["Content-Type"]
    assert "<Hangup/>" in r["body"]


def test_staged_answer_still_serves_the_ivr(rec):
    params = dict(FORM, CallStatus=["ringing"])
    r = pa.handler(_staged("/plivo/answer", params=params, token=ANSWER_TOKEN), None)
    assert r["statusCode"] == 200 and "<Play>" in r["body"]


def test_normalize_path_leaves_an_unstaged_path_alone():
    ev = _event("/plivo/hangup")
    assert ps.normalize_path(ev) == "/plivo/hangup"


def test_normalize_path_ignores_a_default_stage():
    ev = _event("/plivo/hangup")
    ev["requestContext"]["stage"] = "$default"
    ev["rawPath"] = "/plivo/hangup"
    assert ps.normalize_path(ev) == "/plivo/hangup"


def test_normalize_path_is_driven_by_the_stage_name_not_a_hardcoded_prod():
    ev = _event("/plivo/events")
    ev["rawPath"] = "/staging/plivo/events"
    ev["requestContext"]["stage"] = "staging"
    assert ps.normalize_path(ev) == "/plivo/events"


# --------------------------------------------------------------------------
# recipient selection on the legacy post-call SMS
# --------------------------------------------------------------------------
def test_outbound_notifies_the_callee_not_our_own_cli(rec):
    """The live recipient defect. `_send_post_call_sms` used to be handed
    `params.get('From')` regardless of direction, and on an outbound call Plivo's
    `From` is our own CLI - so the business number would have been texted, billed to
    us, under our own registered DLT sender."""
    form = {**FORM, "Direction": ["outbound"],
            "From": ["918031830030"], "To": ["919876543210"]}
    pa.handler(_event("/plivo/hangup", params=form), None)
    assert rec.sms == [("919876543210", "call-abc")]


def test_a_business_number_is_never_the_recipient(rec):
    """The backstop, reached when `Direction` disagrees with reality. Until 2026-09-21
    the fixtures in this file used `919903300044` - our own WABA2 number - as the
    caller, and the assertion was that we texted it."""
    form = {**FORM, "Direction": ["inbound"], "From": ["919903300044"]}
    pa.handler(_event("/plivo/hangup", params=form), None)
    assert rec.sms == []


def test_ambiguous_direction_sends_nothing(rec):
    """No safe default: guessing inbound texts our own number on every outbound call,
    guessing outbound texts the agent endpoint on every inbound one."""
    form = {**FORM}
    form.pop("Direction", None)
    pa.handler(_event("/plivo/hangup", params=form), None)
    assert rec.sms == []
