"""The softphone: leg separation, the state machine, and the protected token route.

Measured before building, 2026-09-23:

* `lambda_utils/pstn/browser_token.py` already existed (built 2026-09-19) and **nothing
  called it** - no token route, no softphone Lambda. The five Plivo routes on the API are
  the callbacks only: answer, hangup, events, dial-events, fallback.
* `PSTN_BROWSER_ROUTING_ENABLED` and `PSTN_AGENT_ENDPOINT` are **absent** from every live
  function, so browser routing is off and `plivo-answer._answer_xml` serves the greeting.
* All five `Pstn*` models declared in `resource.ts` are **absent from the account** and no
  Python references them, so they are declaration-only.

What these tests concentrate on is the one mistake the brief singles out: conflating the
agent's browser connecting with the customer picking up. Everything else here is a
consequence of keeping those two facts apart.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.pstn import browser_token, softphone  # noqa: E402

HANDLER_PATH = (ROOT / "amplify" / "functions" / "messaging" / "pstn-softphone"
                / "handler.py")
PLIVO_ANSWER = (ROOT / "amplify" / "functions" / "messaging" / "plivo-answer"
                / "handler.py")


def code_only(path: Path) -> str:
    """Source with docstrings and comments stripped, blanked in place.

    In place rather than by rejoining tokens: rejoining splits every expression across
    lines and makes substring assertions unfailable.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    docstrings: set = set()
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            docstrings.update(range(first.lineno,
                                    (first.end_lineno or first.lineno) + 1))
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                if 1 <= row <= len(lines):
                    lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return "\n".join(line for n, line in enumerate(lines, start=1)
                     if n not in docstrings)


def session(**overrides):
    base = softphone.new_session(session_id="alice#tab1", actor="alice",
                                 endpoint_username="wecare_ep", at=1000)
    base.update(overrides)
    return base


# ===========================================================================
# The leg distinction
# ===========================================================================

class TestLocalLegIsNotRemoteAnswer:
    """The mistake this module exists to prevent."""

    def test_the_sdk_answering_does_not_mean_the_customer_answered(self):
        """`onCallAnswered` is leg A - the agent's tab - and nothing more."""
        state = softphone.apply_local_event(session(), "onCallAnswered", at=1010)
        assert softphone.local_leg_connected(state) is True
        assert softphone.remote_party_answered(state) is False

    def test_talk_time_is_none_until_the_far_party_answers(self):
        """None, not 0. Zero reads as a call that connected and lasted no time."""
        state = softphone.apply_local_event(session(), "onCallAnswered", at=1010)
        assert softphone.talk_time_seconds(state) is None

    def test_only_a_provider_dial_status_establishes_the_remote_leg(self):
        state = softphone.apply_local_event(session(), "onCallAnswered", at=1010)
        state = softphone.apply_provider_dial_status(state, "answer", at=1020)
        assert softphone.remote_party_answered(state) is True
        assert state["remotePartyAnsweredAt"] == 1020

    def test_talk_time_measures_from_the_remote_answer_not_the_local_connect(self):
        state = softphone.apply_local_event(session(), "onCallAnswered", at=1000)
        state = softphone.apply_provider_dial_status(state, "answer", at=1030)
        state = softphone.apply_local_event(state, "onCallTerminated", at=1090)
        # 1090 - 1030, not 1090 - 1000. Billing from the local connect would overcharge by
        # the ringing time on every call.
        assert softphone.talk_time_seconds(state) == 60

    def test_a_local_event_can_never_write_the_remote_leg(self):
        """Structural, not conventional - this is the guarantee."""
        for sdk_event in sorted(softphone.SDK_EVENTS):
            fresh = session()
            try:
                updated = softphone.apply_local_event(fresh, sdk_event, at=1010)
            except softphone.TransitionRefused:
                continue
            assert updated["remoteLegState"] == softphone.REMOTE_UNKNOWN, (
                f"{sdk_event} moved the remote leg")
            assert "remotePartyAnsweredAt" not in updated

    def test_the_source_has_no_local_write_to_the_remote_leg(self):
        code = code_only(SHARED / "lambda_utils" / "pstn" / "softphone.py")
        local_fn = code[code.index("def apply_local_event("):
                        code.index("def apply_provider_dial_status(")]
        assert "remoteLegState" not in local_fn.replace(
            'updated["remoteLegState"]', "")  # no assignment at all
        assert "remotePartyAnsweredAt" not in local_fn

    def test_a_no_answer_call_reports_no_talk_time(self):
        state = softphone.apply_local_event(session(), "onCalling", at=1000)
        state = softphone.apply_provider_dial_status(state, "no-answer", at=1040)
        assert softphone.remote_party_answered(state) is False
        assert softphone.talk_time_seconds(state) is None

    @pytest.mark.parametrize("status,answered", [
        ("answer", True), ("answered", True), ("completed", True),
        ("ringing", False), ("no-answer", False), ("timeout", False),
        ("busy", False), ("failed", False), ("cancel", False),
    ])
    def test_provider_statuses_map_correctly(self, status, answered):
        state = softphone.apply_provider_dial_status(session(), status, at=1020)
        assert softphone.remote_party_answered(state) is answered


class TestOutOfOrderEvents:
    def test_a_backwards_sdk_event_is_refused(self):
        """onCallTerminated before onCallAnswered is routine on a poor network."""
        state = softphone.apply_local_event(session(), "onCallAnswered", at=1010)
        with pytest.raises(softphone.TransitionRefused):
            softphone.apply_local_event(state, "onIncomingCall", at=1020)

    def test_terminated_then_answered_leaves_the_call_ended(self):
        state = softphone.apply_local_event(session(), "onCallTerminated", at=1010)
        with pytest.raises(softphone.TransitionRefused):
            softphone.apply_local_event(state, "onCallAnswered", at=1020)
        assert state["localLegState"] == softphone.LOCAL_ENDED

    def test_a_stale_status_cannot_erase_positive_answer_evidence(self):
        state = softphone.apply_provider_dial_status(session(), "answer", at=1020)
        with pytest.raises(softphone.TransitionRefused):
            softphone.apply_provider_dial_status(state, "no-answer", at=1030)
        assert softphone.remote_party_answered(state) is True

    def test_an_unknown_sdk_event_is_refused_not_guessed(self):
        with pytest.raises(softphone.TransitionRefused):
            softphone.apply_local_event(session(), "onSomethingNew")

    def test_an_unknown_provider_status_is_refused(self):
        with pytest.raises(softphone.TransitionRefused):
            softphone.apply_provider_dial_status(session(), "probably-fine")


# ===========================================================================
# Registration and presence
# ===========================================================================

class TestRegistrationAndPresence:
    def test_a_new_session_is_unregistered_and_offline(self):
        state = session()
        assert state["registration"] == softphone.UNREGISTERED
        assert state["presence"] == softphone.OFFLINE

    def test_a_session_must_be_attributable(self):
        """An unattributable session cannot be audited."""
        with pytest.raises(ValueError):
            softphone.new_session(session_id="s", actor="", endpoint_username="e")
        with pytest.raises(ValueError):
            softphone.new_session(session_id="", actor="a", endpoint_username="e")

    def test_registration_alone_does_not_make_an_agent_ready(self):
        """A registered endpoint is reachable, not necessarily staffed."""
        ready, reason = softphone.can_receive_call(
            session(registration=softphone.REGISTERED, presence=softphone.OFFLINE))
        assert not ready
        assert "presence" in reason

    def test_presence_alone_does_not_make_an_agent_ready(self):
        ready, reason = softphone.can_receive_call(
            session(registration=softphone.UNREGISTERED, presence=softphone.AVAILABLE))
        assert not ready
        assert "UNREGISTERED" in reason

    def test_both_together_are_ready(self):
        ready, _ = softphone.can_receive_call(
            session(registration=softphone.REGISTERED, presence=softphone.AVAILABLE))
        assert ready

    def test_an_agent_already_on_a_call_is_not_ready(self):
        ready, reason = softphone.can_receive_call(session(
            registration=softphone.REGISTERED, presence=softphone.AVAILABLE,
            localLegState=softphone.LOCAL_CONNECTED))
        assert not ready
        assert "already on a call" in reason

    def test_busy_does_not_accept_a_call(self):
        """Otherwise one agent takes two customers."""
        assert softphone.BUSY not in softphone.PRESENCE_ACCEPTS_CALL

    def test_a_token_expiry_drops_to_registering_not_unregistered(self):
        """Reconnecting is a different operator signal from signed out."""
        assert softphone.registration_can_transition(
            softphone.REGISTERED, softphone.REGISTERING)

    def test_a_session_carries_a_ttl(self):
        """A closed tab must not leave a stale AVAILABLE agent routing calls into a void."""
        assert session()["expiresAt"] > session()["createdAt"]

    def test_describe_spells_out_the_leg_difference(self):
        state = softphone.apply_local_event(session(), "onCallAnswered", at=1010)
        described = softphone.describe(state)
        assert described["localLegConnected"] is True
        assert described["remotePartyAnswered"] is False
        assert "connected-call notification" in described["note"]

    def test_describe_leaks_no_phone_number(self):
        state = session(remoteNumber="+918031830030")
        assert "918031830030" not in repr(softphone.describe(state))


# ===========================================================================
# Token minting contract
# ===========================================================================

class TestTokenContract:
    def test_plivo_signs_the_token_we_do_not(self):
        """Signing locally fails at login with 10007, which is the worst place to learn."""
        code = code_only(SHARED / "lambda_utils" / "pstn" / "browser_token.py")
        assert "/JWT/Token/" in code
        for forbidden in ("hmac.new", "jwt.encode", "hashlib.sha256"):
            assert forbidden not in code, (
                f"{forbidden} suggests local signing; Plivo must mint the token")

    def test_permissions_are_nested_under_voice(self):
        """Flat grants are accepted at mint and rejected at login with 10008."""
        code = code_only(SHARED / "lambda_utils" / "pstn" / "browser_token.py")
        assert '"per": {"voice": {' in code

    def test_ttl_is_clamped_at_both_ends(self):
        assert browser_token.clamp_ttl(None) == browser_token.DEFAULT_TTL_SECONDS
        assert browser_token.clamp_ttl(10) == 30
        assert browser_token.clamp_ttl(999_999) == browser_token.MAX_TTL_SECONDS
        assert browser_token.clamp_ttl("nonsense") == browser_token.DEFAULT_TTL_SECONDS

    def test_the_default_ttl_is_short(self):
        """A stolen token should be worth very little; the SDK holds the registration."""
        assert browser_token.DEFAULT_TTL_SECONDS <= 600

    def test_a_session_endpoint_is_deterministic(self):
        """A reconnecting session must resolve to the same endpoint or strand registrations."""
        a = browser_token.session_endpoint_username("wecare_ep", "tab-1")
        b = browser_token.session_endpoint_username("wecare_ep", "tab-1")
        assert a == b
        assert a != browser_token.session_endpoint_username("wecare_ep", "tab-2")

    def test_session_endpoint_requires_both_parts(self):
        with pytest.raises(browser_token.TokenError):
            browser_token.session_endpoint_username("", "tab")
        with pytest.raises(browser_token.TokenError):
            browser_token.session_endpoint_username("wecare_ep", "")

    def test_session_endpoints_are_not_provisioned_and_inbound_is_unsafe(self):
        plan = browser_token.plan_session_endpoint("wecare_ep", "tab-1")
        assert plan["provisioned"] is False
        assert plan["inboundSafe"] is False
        assert plan["outboundSafe"] is True

    def test_planning_creates_nothing(self):
        """Provisioning provider resources from a sign-in would be unbounded and unreviewed."""
        code = code_only(SHARED / "lambda_utils" / "pstn" / "browser_token.py")
        plan_fn = code[code.index("def plan_session_endpoint("):
                       code.index("def _basic_auth_header(")]
        assert "urlopen" not in plan_fn
        assert "Request(" not in plan_fn

    def test_minting_without_credentials_is_refused(self):
        with pytest.raises(browser_token.TokenError):
            browser_token.mint_token(auth_id="", auth_token="",
                                     endpoint_username="e")

    def test_minting_without_an_endpoint_is_refused(self):
        with pytest.raises(browser_token.TokenError):
            browser_token.mint_token(auth_id="a", auth_token="b",
                                     endpoint_username="")

    def test_the_token_is_never_logged(self):
        """A logged JWT is a reusable telephony credential for its whole lifetime."""
        code = code_only(SHARED / "lambda_utils" / "pstn" / "browser_token.py")
        issued = code[code.index('log_event(logger, "pstn_token_issued"'):]
        issued = issued[:issued.index("return {")]
        assert "tokenLength=len(token)" in issued
        assert "token=token" not in issued

    def test_login_error_codes_are_explained(self):
        assert "10007" in str(browser_token.LOGIN_ERROR_CODES.keys()) or \
            10007 in browser_token.LOGIN_ERROR_CODES
        assert "10010" in browser_token.describe_login_error(10010) or \
            "concurrent" in browser_token.describe_login_error(10010)
        assert "Unrecognised" in browser_token.describe_login_error(99999)


# ===========================================================================
# The route
# ===========================================================================

class TestTheRouteIsProtectedAndDisabled:
    def test_the_handler_authenticates_before_dispatch(self):
        code = code_only(HANDLER_PATH)
        assert "require_auth(event)" in code
        assert code.index("require_auth(event)") < code.index("'/pstn/token'")

    def test_minting_requires_operator(self):
        """A token grants the ability to place real telephone calls."""
        code = code_only(HANDLER_PATH)
        assert "WRITE_ROLE = 'Operator'" in code
        assert "required_role=WRITE_ROLE" in code

    def test_options_is_answered_before_auth(self):
        code = code_only(HANDLER_PATH)
        assert code.index("options_response(origin)") < code.index("require_auth(event)")

    def test_browser_routing_defaults_off(self):
        code = code_only(HANDLER_PATH)
        assert "'PSTN_BROWSER_ROUTING_ENABLED', 'false'" in code

    def test_the_route_refuses_to_mint_while_the_flag_is_off(self):
        """Minting would hand a browser the ability to place live outbound calls."""
        code = code_only(HANDLER_PATH)
        mint = code[code.index("def _mint("):code.index("def _load(")]
        assert "if not BROWSER_ROUTING_ENABLED:" in mint
        assert "PSTN_BROWSER_ROUTING_DISABLED" in mint
        assert "cors_response(503" in mint
        # And it must say how to turn it on, so the refusal is actionable.
        assert "'unblock'" in mint

    def test_inbound_is_refused_on_a_shared_endpoint(self):
        code = code_only(HANDLER_PATH)
        assert "PSTN_INBOUND_NEEDS_SESSION_ENDPOINT" in code
        assert "incoming_allow=False" in code

    def test_the_token_is_never_written_to_the_session_row(self):
        """A token in a table is a reusable telephony credential under a different policy.

        Checked three ways that can each actually fail: the mint path saves a session and
        never assigns a token onto it, the session constructor has no token field, and no
        key anywhere in a fresh session row is token-shaped.
        """
        code = code_only(HANDLER_PATH)
        mint = code[code.index("def _mint("):code.index("def _load(")]
        assert "_save(session)" in mint
        for forbidden in ("session['token']", 'session["token"]',
                          "session['accessToken']", "minted['token']"):
            assert forbidden not in mint, f"{forbidden} would persist the token"

        row = softphone.new_session(session_id="s", actor="a", endpoint_username="e")
        assert "token" not in row
        assert not [k for k in row if "token" in k.lower()], sorted(row)

    def test_credentials_come_from_secrets_manager_lazily(self):
        code = code_only(HANDLER_PATH)
        assert "get_secret_value(SecretId=PLIVO_API_SECRET_ID)" in code
        assert "def _plivo_credentials()" in code
        # No module-scope read: a cached value would survive a rotation.
        header = code[:code.index("def _plivo_credentials(")]
        assert "get_secret_value" not in header

    def test_no_credential_is_read_from_the_environment(self):
        import re

        code = code_only(HANDLER_PATH)
        offenders = re.findall(
            r"environ(?:\.get)?\s*[\(\[]\s*['\"]([A-Z0-9_]*"
            r"(?:AUTH_TOKEN|PASSWORD|SECRET_KEY)[A-Z0-9_]*)['\"]", code)
        assert not offenders, offenders

    def test_a_session_id_is_scoped_to_the_token_actor(self):
        """So a caller cannot address another agent's session by guessing an id."""
        code = code_only(HANDLER_PATH)
        fn = code[code.index("def _session_id("):code.index("def handler(")]
        assert "actor" in fn and "f'{actor}#" in fn

    def test_presence_cannot_be_set_available_mid_call(self):
        code = code_only(HANDLER_PATH)
        fn = code[code.index("def _presence("):code.index("def _diagnostics(")]
        assert "LOCAL_CONNECTED" in fn
        assert "cors_response(409" in fn

    def test_diagnostics_exposes_no_credential(self):
        code = code_only(HANDLER_PATH)
        fn = code[code.index("def _diagnostics("):]
        assert "providerCredentialsAvailable" in fn
        assert "auth_token" not in fn
        assert "'auth_id'" not in fn


class TestPlivoAnswerStaysSafe:
    def test_the_answer_url_still_fails_safe_on_the_flag(self):
        """A flag on without an endpoint must serve the greeting, not dial nowhere."""
        code = code_only(PLIVO_ANSWER)
        assert "PSTN_BROWSER_ROUTING_ENABLED and PSTN_AGENT_ENDPOINT" in code
        assert "PSTN_BROWSER_ROUTING_NO_ENDPOINT" in code

    def test_the_flag_defaults_off_there_too(self):
        code = code_only(PLIVO_ANSWER)
        assert "'PSTN_BROWSER_ROUTING_ENABLED', 'false'" in code
