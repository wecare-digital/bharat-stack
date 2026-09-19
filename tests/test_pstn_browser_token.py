"""Browser SDK access tokens, and the flagged <Dial><User> answer response.

Two things here were verified against Plivo's documentation and its official
Python SDK rather than assumed, because guessing either produces a failure that
only appears in the browser at login time:

  1. Plivo SIGNS the JWT. We mint it via the REST API; we do not sign it with the
     account auth token. A locally signed token fails with 10007.
  2. The permissions object nests grants under `voice`. The documentation page's
     field table implies they sit directly under `per`; the official SDK nests
     them, and flat grants fail with 10008 - accepted at mint, rejected at login.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.pstn import browser_token as bt  # noqa: E402

AUTH_ID = "MAMMI3YZIWYTETOTVJOC"
AUTH_TOKEN = "not-a-real-token"
ENDPOINT = "wecarewaivr203331794466262"
APP_ID = "12775976954213184"


class _Captured:
    def __init__(self, payload=None, status=200):
        self.requests = []
        self.payload = payload if payload is not None else {"token": "jwt.value.here"}
        self.status = status

    def __call__(self, request, timeout=None):
        body = json.loads(request.data.decode())
        self.requests.append({
            "url": request.full_url,
            "method": request.get_method(),
            "headers": {k.lower(): v for k, v in request.headers.items()},
            "body": body,
        })
        payload = json.dumps(self.payload).encode()

        class _Response:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return payload
        return _Response()


@pytest.fixture
def api(monkeypatch):
    captured = _Captured()
    monkeypatch.setattr(bt.urllib.request, "urlopen", captured)
    return captured


def _mint(**kwargs):
    params = dict(auth_id=AUTH_ID, auth_token=AUTH_TOKEN,
                  endpoint_username=ENDPOINT, app_id=APP_ID)
    params.update(kwargs)
    return bt.mint_token(**params)


# ==========================================================================
# Plivo signs the token, not us
# ==========================================================================
def test_the_token_is_minted_via_the_plivo_rest_api(api):
    _mint()
    assert len(api.requests) == 1
    assert api.requests[0]["url"] == \
        f"https://api.plivo.com/v1/Account/{AUTH_ID}/JWT/Token/"
    assert api.requests[0]["method"] == "POST"


def test_the_module_does_not_sign_anything_locally():
    """A locally signed token is rejected with 10007.

    Asserted on the source because the failure is silent here and loud in the
    browser: our auth token is the credential for MINTING, not the signing key.
    """
    source = (SHARED / "lambda_utils" / "pstn" / "browser_token.py").read_text()
    for signing in ("hmac.new", "jwt.encode", "hashlib.sha256(", "import hmac",
                    "import jwt"):
        assert signing not in source, f"local signing found: {signing}"


def test_credentials_are_sent_as_basic_auth_not_in_the_body(api):
    _mint()
    request = api.requests[0]
    assert request["headers"]["authorization"].startswith("Basic ")
    assert AUTH_TOKEN not in json.dumps(request["body"])


# ==========================================================================
# the permissions object shape
# ==========================================================================
def test_grants_are_nested_under_voice(api):
    """Flat grants are accepted at mint and rejected at login with 10008."""
    _mint(incoming_allow=True, outgoing_allow=True)
    per = api.requests[0]["body"]["per"]
    assert "voice" in per, "per must nest grants under 'voice'"
    assert per["voice"]["incoming_allow"] is True
    assert per["voice"]["outgoing_allow"] is True
    # and must NOT be flat
    assert "incoming_allow" not in per


def test_outbound_only_by_default(api):
    """Inbound requires a per-session endpoint; it is not granted casually."""
    _mint()
    per = api.requests[0]["body"]["per"]["voice"]
    assert per["outgoing_allow"] is True
    assert per["incoming_allow"] is False


def test_required_claims_are_present(api):
    _mint()
    body = api.requests[0]["body"]
    for claim in ("iss", "sub", "nbf", "exp", "per"):
        assert claim in body, f"missing required claim {claim}"
    assert body["iss"] == AUTH_ID
    assert body["sub"] == ENDPOINT


def test_nbf_and_exp_are_strings_matching_the_official_sdk(api):
    """plivo-python validates both as text, so this sends what Plivo's client sends."""
    body = api.requests[0]["body"] if api.requests else None
    _mint()
    body = api.requests[-1]["body"]
    assert isinstance(body["nbf"], str)
    assert isinstance(body["exp"], str)


def test_app_id_ties_the_session_to_our_application(api):
    """A mismatch between this and the endpoint's application misroutes calls."""
    _mint()
    assert api.requests[0]["body"]["app"] == APP_ID


def test_nbf_is_backdated_for_client_clock_skew(api):
    """Without skew, a client a second ahead of us gets 10005 on a good token."""
    _mint()
    body = api.requests[0]["body"]
    assert int(body["exp"]) - int(body["nbf"]) > bt.DEFAULT_TTL_SECONDS


# ==========================================================================
# lifetime
# ==========================================================================
def test_default_ttl_is_five_minutes():
    assert bt.DEFAULT_TTL_SECONDS == 300


@pytest.mark.parametrize("requested,expected", [
    (None, 300),
    (0, 300),
    (60, 60),
    (10, 30),                 # floored
    (99999999, 24 * 60 * 60),  # clamped to Plivo's maximum
    ("nonsense", 300),
])
def test_ttl_is_clamped(requested, expected):
    assert bt.clamp_ttl(requested) == expected


def test_ttl_never_exceeds_twenty_four_hours():
    """Plivo rejects longer with 10009; clamping makes the error local and clear."""
    assert bt.clamp_ttl(10 ** 9) == bt.MAX_TTL_SECONDS
    assert bt.MAX_TTL_SECONDS == 24 * 60 * 60


def test_refresh_is_scheduled_before_expiry(api):
    """So a refresh happens proactively, not discovered mid-call."""
    result = _mint(ttl_seconds=300)
    assert result["refreshAfterSeconds"] < result["expiresInSeconds"]
    assert result["refreshAfterSeconds"] == 240


# ==========================================================================
# only minimal bootstrap reaches the browser
# ==========================================================================
def test_response_contains_the_token_and_nothing_sensitive(api):
    result = _mint()
    assert result["token"] == "jwt.value.here"
    blob = json.dumps(result)
    assert AUTH_TOKEN not in blob
    assert AUTH_ID not in blob, "the account auth id has no use in the browser"


def test_response_does_not_leak_an_endpoint_password(api):
    api.payload = {"token": "jwt.value.here", "password": "endpoint-secret"}
    result = _mint()
    assert "password" not in json.dumps(result)


def test_a_missing_token_in_the_response_is_an_error(api):
    api.payload = {"message": "ok"}
    with pytest.raises(bt.TokenError) as exc:
        _mint()
    assert exc.value.code == "NO_TOKEN_IN_RESPONSE"


# ==========================================================================
# failures are explicit
# ==========================================================================
def test_absent_credentials_are_refused_before_any_request(api):
    with pytest.raises(bt.TokenError) as exc:
        bt.mint_token(auth_id="", auth_token="", endpoint_username=ENDPOINT)
    assert exc.value.code == "NO_PROVIDER_CREDENTIALS"
    assert api.requests == []


def test_absent_endpoint_is_refused(api):
    with pytest.raises(bt.TokenError) as exc:
        bt.mint_token(auth_id=AUTH_ID, auth_token=AUTH_TOKEN, endpoint_username="")
    assert exc.value.code == "NO_ENDPOINT"


def test_provider_unreachable_is_reported_not_swallowed(monkeypatch):
    def boom(request, timeout=None):
        raise OSError("connection refused")
    monkeypatch.setattr(bt.urllib.request, "urlopen", boom)
    with pytest.raises(bt.TokenError) as exc:
        _mint()
    assert exc.value.code == "PROVIDER_UNREACHABLE"


def test_error_messages_carry_no_credential(monkeypatch):
    def boom(request, timeout=None):
        raise OSError("connection refused")
    monkeypatch.setattr(bt.urllib.request, "urlopen", boom)
    with pytest.raises(bt.TokenError) as exc:
        _mint()
    assert AUTH_TOKEN not in str(exc.value)


# ==========================================================================
# one endpoint per concurrent session
# ==========================================================================
def test_session_endpoint_is_deterministic():
    """A reconnecting session must resolve to the SAME endpoint.

    Otherwise registrations strand and the account eventually hits 10010
    MAX_ALLOWED_LOGIN_REACHED.
    """
    first = bt.session_endpoint_username(ENDPOINT, "session-abc")
    second = bt.session_endpoint_username(ENDPOINT, "session-abc")
    assert first == second


def test_different_sessions_get_different_endpoints():
    """Plivo: a unique endpoint per browser session is required for inbound."""
    a = bt.session_endpoint_username(ENDPOINT, "session-aaa")
    b = bt.session_endpoint_username(ENDPOINT, "session-bbb")
    assert a != b


def test_session_endpoint_rejects_missing_inputs():
    with pytest.raises(bt.TokenError):
        bt.session_endpoint_username("", "session-abc")
    with pytest.raises(bt.TokenError):
        bt.session_endpoint_username(ENDPOINT, "")


def test_session_endpoint_provisioning_is_planned_not_performed():
    """Creating provider resources from ordinary user traffic would be unbounded."""
    plan = bt.plan_session_endpoint(ENDPOINT, "session-abc")
    assert plan["provisioned"] is False
    assert plan["inboundSafe"] is False
    assert plan["outboundSafe"] is True
    assert "control-plane" in plan["reason"]


# ==========================================================================
# login error mapping
# ==========================================================================
@pytest.mark.parametrize("code,fragment", [
    (10005, "clock"),
    (10006, "new token"),
    (10007, "not minted by the"),
    (10008, "per object"),
    (10009, "24h"),
    (10010, "unique endpoint"),
])
def test_documented_login_errors_are_actionable(code, fragment):
    assert fragment in bt.describe_login_error(code)


def test_unknown_login_error_is_not_invented():
    assert "Unrecognised" in bt.describe_login_error(99999)


# ==========================================================================
# the flagged <Dial><User> answer response
# ==========================================================================
def _load_plivo_handler(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    path = (ROOT / "amplify" / "functions" / "messaging" / "plivo-answer"
            / "handler.py")
    spec = importlib.util.spec_from_file_location(
        f"plivo_dialuser_{abs(hash(frozenset(env.items())))}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_browser_routing_is_off_by_default(monkeypatch):
    """The current greeting-and-hangup behaviour stays the production default."""
    module = _load_plivo_handler(monkeypatch)
    assert module.PSTN_BROWSER_ROUTING_ENABLED is False
    assert "<Dial" not in module._answer_xml()
    assert "<Play>" in module._answer_xml()


def test_enabling_the_flag_dials_the_agent_endpoint(monkeypatch):
    module = _load_plivo_handler(
        monkeypatch, PSTN_BROWSER_ROUTING_ENABLED="true",
        PSTN_AGENT_ENDPOINT="agent-endpoint-1")
    xml = module._answer_xml()
    assert "<Dial" in xml
    assert "<User>sip:agent-endpoint-1@phone.plivo.com</User>" in xml


def test_the_flag_without_an_endpoint_falls_back_rather_than_dropping_the_call(
        monkeypatch):
    """A <Dial> to an empty destination drops the call.

    Missing configuration is treated as "not enabled" and alerted, not trusted.
    """
    module = _load_plivo_handler(
        monkeypatch, PSTN_BROWSER_ROUTING_ENABLED="true", PSTN_AGENT_ENDPOINT="")
    xml = module._answer_xml()
    assert "<Dial" not in xml
    assert "<Play>" in xml


def test_the_dial_carries_the_authoritative_callback(monkeypatch):
    module = _load_plivo_handler(
        monkeypatch, PSTN_BROWSER_ROUTING_ENABLED="true",
        PSTN_AGENT_ENDPOINT="agent-endpoint-1")
    xml = module._answer_xml()
    assert "/plivo/dial-events" in xml
    assert 'callbackMethod="POST"' in xml


def test_the_greeting_follows_the_dial_so_no_answer_is_not_silence(monkeypatch):
    module = _load_plivo_handler(
        monkeypatch, PSTN_BROWSER_ROUTING_ENABLED="true",
        PSTN_AGENT_ENDPOINT="agent-endpoint-1")
    xml = module._answer_xml()
    assert xml.index("</Dial>") < xml.index("<Play>")


def test_the_endpoint_is_escaped_into_the_xml(monkeypatch):
    """Server configuration, but XML-escaped regardless.

    A configuration value reaching an XML document unescaped is how a routing
    template becomes an injection point.
    """
    module = _load_plivo_handler(
        monkeypatch, PSTN_BROWSER_ROUTING_ENABLED="true",
        PSTN_AGENT_ENDPOINT='bad&"<value>')
    xml = module._answer_xml()
    assert "&amp;" in xml
    assert "<value>" not in xml


def test_no_sip_target_is_accepted_from_a_request(monkeypatch):
    """The dial destination comes only from server configuration."""
    module = _load_plivo_handler(
        monkeypatch, PSTN_BROWSER_ROUTING_ENABLED="true",
        PSTN_AGENT_ENDPOINT="agent-endpoint-1")
    source = (ROOT / "amplify" / "functions" / "messaging" / "plivo-answer"
              / "handler.py").read_text()
    dial_fn = source[source.index("def _dial_user_xml"):source.index("def _answer_xml")]
    for request_field in ("params.get", "body.get", "queryStringParameters"):
        assert request_field not in dial_fn, \
            "the dial destination must not come from a request"
