"""Plivo V3 signature validation, cross-checked against the official SDK.

The point of this file is the cross-check. `lambda_utils/plivo_signature.py` is a
reimplementation, needed because the `plivo` package is dev-only and cannot be
imported from a Lambda. A reimplementation of a signing algorithm is worth
exactly as much as its agreement with the original, so every digest here is
compared against `plivo.utils.signature_v3` over a matrix of URL shapes,
parameter shapes and nonces.

If Plivo changes the algorithm, `test_matches_sdk_*` fails. Without that, this
module could drift into rejecting every genuine request - and in a fail-closed
handler that means silently dropping every call.
"""
import sys
from pathlib import Path

import pytest

SHARED = Path(__file__).resolve().parents[1] / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import plivo_signature as ps  # noqa: E402

sdk = pytest.importorskip(
    "plivo.utils.signature_v3",
    reason="official Plivo SDK (dev-only) required for the cross-check")

# Shape-realistic and genuinely not live. It used to say "not live" while holding
# the account's real auth token, which is how it reached the public history.
TOKEN = "PLIVO_TEST_AUTH_TOKEN_NOT_LIVE_000000000"
NONCE = "12345678901234567890"

ANSWER = "https://api.wecare.digital/plivo/answer"
HANGUP_TOKENED = "https://api.wecare.digital/plivo/hangup?token=abc123"

PLIVO_POST = {
    "CallUUID": ["abc-123"],
    "From": ["919903300044"],
    "To": ["918031830030"],
    "Direction": ["inbound"],
    "CallStatus": ["completed"],
}


def _sdk_ok(method, uri, nonce, token, signature, params):
    return sdk.validate_v3_signature(method, uri, nonce, token, signature, params)


# --------------------------------------------------------------------------
# Cross-check against the vendor implementation
# --------------------------------------------------------------------------
@pytest.mark.parametrize("uri", [
    ANSWER,
    HANGUP_TOKENED,
    "https://api.wecare.digital/plivo/fallback",
    "https://api.wecare.digital/plivo/events?token=xyz&extra=1",
    "https://api.wecare.digital/plivo/hangup?b=2&a=1",
])
@pytest.mark.parametrize("params", [
    {},
    {"CallUUID": ["x"]},
    PLIVO_POST,
    {"Dup": ["b", "a"]},                 # multi-valued, exercises the sort
    {"Zed": ["1"], "alpha": ["2"], "Beta": ["3"]},   # case-sensitive ordering
])
def test_matches_sdk_post(uri, params):
    """Our digest must equal the SDK's for every URL/param combination."""
    mine = ps.expected_signature("POST", uri, NONCE, TOKEN, params)
    assert _sdk_ok("POST", uri, NONCE, TOKEN, mine, dict(params)), (
        f"digest disagrees with the SDK for uri={uri} params={params}")


@pytest.mark.parametrize("uri", [ANSWER, HANGUP_TOKENED])
def test_matches_sdk_get(uri):
    mine = ps.expected_signature("GET", uri, NONCE, TOKEN, {})
    assert _sdk_ok("GET", uri, NONCE, TOKEN, mine, {})


@pytest.mark.parametrize("nonce", ["a", "0" * 64, "nonce-with-dashes-1"])
def test_matches_sdk_across_nonces(nonce):
    mine = ps.expected_signature("POST", HANGUP_TOKENED, nonce, TOKEN, PLIVO_POST)
    assert _sdk_ok("POST", HANGUP_TOKENED, nonce, TOKEN, mine, dict(PLIVO_POST))


def test_our_validator_accepts_an_sdk_generated_signature():
    """The other direction: sign the SDK's way, verify ours accepts it."""
    base = sdk.construct_post_url(HANGUP_TOKENED, dict(PLIVO_POST)).decode("utf-8")
    sig = sdk.get_signature_v3(TOKEN.encode(), base, NONCE.encode()).decode()
    assert ps.validate_signature("POST", HANGUP_TOKENED, NONCE, TOKEN, sig, PLIVO_POST)


# --------------------------------------------------------------------------
# The four details the public docs omit
# --------------------------------------------------------------------------
def test_nonce_is_joined_with_a_dot_not_bare_concatenation():
    right = ps.compute_signature(TOKEN, "https://x/y", NONCE)
    wrong_payload = f"https://x/y{NONCE}"
    import base64, hashlib, hmac
    wrong = base64.encodebytes(hmac.new(TOKEN.encode(), wrong_payload.encode(),
                                        hashlib.sha256).digest()).strip().decode()
    assert right != wrong


def test_post_with_query_string_gets_a_trailing_dot_before_params():
    base = ps._construct_post_url(HANGUP_TOKENED, {"A": ["1"]})
    assert "?token=abc123." in base


def test_post_without_query_string_gets_a_bare_question_mark():
    base = ps._construct_post_url(ANSWER, {"A": ["1"]})
    assert base.startswith(ANSWER + "?")
    assert "?." not in base


def test_params_are_key_value_concatenated_with_no_separator():
    assert ps._sorted_params_string({"b": "2", "a": "1"}) == "a1b2"


def test_multiple_comma_separated_signatures_any_match_wins():
    good = ps.expected_signature("POST", ANSWER, NONCE, TOKEN, PLIVO_POST)
    header = f"{'A' * 44},{good},{'B' * 44}"
    assert ps.validate_signature("POST", ANSWER, NONCE, TOKEN, header, PLIVO_POST)


# --------------------------------------------------------------------------
# §18 required behaviours
# --------------------------------------------------------------------------
def _event(uri_path="/plivo/hangup", query="token=abc123", params=None,
           nonce=NONCE, sig=None, token=TOKEN, header=ps.HEADER_V3,
           method="POST"):
    import urllib.parse
    params = PLIVO_POST if params is None else params
    body = urllib.parse.urlencode(
        [(k, v) for k, vals in params.items() for v in
         (vals if isinstance(vals, list) else [vals])])
    uri = f"https://api.wecare.digital{uri_path}" + (f"?{query}" if query else "")
    if sig is None:
        sig = ps.expected_signature(method, uri, nonce, token, params)
    return {
        "requestContext": {"domainName": "api.wecare.digital",
                           "http": {"method": method, "path": uri_path}},
        "rawPath": uri_path,
        "rawQueryString": query,
        "headers": {header: sig, ps.HEADER_NONCE: nonce,
                    "content-type": "application/x-www-form-urlencoded"},
        "body": body,
        "isBase64Encoded": False,
    }


def test_valid_plivo_signature_is_accepted():
    ok, reason = ps.verify_request(_event(), TOKEN)
    assert ok and reason == "v3"


def test_ma_v3_header_is_also_accepted():
    ok, reason = ps.verify_request(_event(header=ps.HEADER_MA_V3), TOKEN)
    assert ok and reason == "ma_v3"


def test_invalid_signature_is_rejected():
    ok, reason = ps.verify_request(_event(sig="Z" * 44), TOKEN)
    assert not ok and reason == "signature_mismatch"


def test_tampered_body_is_rejected():
    """Sign one payload, deliver another - the classic replay-with-edit."""
    ev = _event()
    ev["body"] = ev["body"].replace("CallStatus=completed", "CallStatus=ringing")
    ok, reason = ps.verify_request(ev, TOKEN)
    assert not ok and reason == "signature_mismatch"


def test_tampered_query_string_is_rejected():
    ev = _event()
    ev["rawQueryString"] = "token=wrong"
    ok, _ = ps.verify_request(ev, TOKEN)
    assert not ok


def test_unsigned_request_is_rejected():
    ev = _event()
    del ev["headers"][ps.HEADER_V3]
    ok, reason = ps.verify_request(ev, TOKEN)
    assert not ok and reason == "missing_signature_header"


def test_missing_nonce_is_rejected():
    ev = _event()
    del ev["headers"][ps.HEADER_NONCE]
    ok, reason = ps.verify_request(ev, TOKEN)
    assert not ok and reason == "missing_nonce_header"


def test_unconfigured_auth_token_fails_closed():
    ok, reason = ps.verify_request(_event(), "")
    assert not ok and reason == "auth_token_not_configured"


def test_wrong_auth_token_is_rejected():
    ok, _ = ps.verify_request(_event(), "a-different-token")
    assert not ok


def test_base64_encoded_body_verifies():
    import base64 as b64
    ev = _event()
    ev["body"] = b64.b64encode(ev["body"].encode()).decode()
    ev["isBase64Encoded"] = True
    ok, _ = ps.verify_request(ev, TOKEN)
    assert ok


# --------------------------------------------------------------------------
# URL reconstruction — the digest depends on getting this byte-exact
# --------------------------------------------------------------------------
def test_reconstruct_url_uses_the_custom_domain_and_raw_query():
    ev = _event()
    assert ps.reconstruct_url(ev) == \
        "https://api.wecare.digital/plivo/hangup?token=abc123"


def test_reconstruct_url_omits_the_question_mark_when_there_is_no_query():
    ev = _event(query="")
    assert ps.reconstruct_url(ev) == "https://api.wecare.digital/plivo/hangup"


def test_reconstruct_url_can_be_overridden_for_a_proxy_host():
    ev = _event()
    ev["requestContext"]["domainName"] = "abc.execute-api.us-east-1.amazonaws.com"
    assert ps.reconstruct_url(ev, force_host="api.wecare.digital").startswith(
        "https://api.wecare.digital/")


def test_form_params_keep_list_values():
    """Collapsing single-element lists would change the digest for repeats."""
    ev = _event(params={"Dup": ["a", "b"]})
    parsed = ps.parse_form_params(ev)
    assert parsed["Dup"] == ["a", "b"]
