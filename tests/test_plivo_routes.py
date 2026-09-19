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

AUTH_TOKEN = "YWQ5NmY4ZmYtZWZlOC00ZGY2LTVmMTItYjU5MzUz"
ANSWER_TOKEN = "answer-gate-token"
NONCE = "12345678901234567890"

FORM = {
    "CallUUID": ["call-abc"],
    "From": ["919903300044"],
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
        def put_item(self, Item):
            r.cdr.append(Item)

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
    assert rec.sms == [("919903300044", "call-abc")]


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


def test_unknown_path_falls_back_to_answer_behaviour(rec):
    params = dict(FORM, CallStatus=["ringing"])
    r = pa.handler(_event("/plivo/unknown", params=params, token=ANSWER_TOKEN), None)
    assert r["statusCode"] == 200
    assert "<Play>" in r["body"]


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
