"""The backend-owned customer session: the guard that makes "remembered login" safe (sections 15-16).

The properties under test are the ones section 16 is specific about and the ones a careless
implementation gets wrong:

  * a session is created, rotated and revoked, and a rotated/revoked id does not validate;
  * idle expiry and absolute expiry are enforced in CODE against the stored row, not left to the
    cookie - and a successful REFRESH slides idle but NEVER moves the absolute deadline;
  * refresh is single-flight: a second concurrent refresh is refused, not fired;
  * a DEFINITE refresh failure (spent token) revokes; a TRANSIENT one (offline/5xx) does NOT -
    a provider blip must not log a remembered customer out;
  * one customer's id never validates to another customer;
  * no token and no opaque id is ever placed in a URL or a log (asserted over the source).

The store is a small in-memory fake that evaluates the single-flight claim for real, in the spirit
of `crm_fake_dynamo`: a fake that accepted any claim would let a broken single-flight pass.
"""

import ast
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))

from lambda_utils import customer_session as cs  # noqa: E402
from lambda_utils import customer_session_config as cfg  # noqa: E402

CUSTOMER = "CUS_01J0000000000000000000000"
OTHER = "CUS_01J9999999999999999999999"
REF = "secretsmanager://wecare/customer-refresh/abc123"
NOW = 1_700_000_000


class FakeSessionStore:
    """In-memory session custody. The refresh claim is evaluated for real (single-flight)."""

    def __init__(self):
        self.rows = {}

    def put_session(self, row):
        self.rows[row["sidHash"]] = dict(row)

    def get_session(self, sid_hash):
        row = self.rows.get(sid_hash)
        return dict(row) if row else None

    def delete_session(self, sid_hash):
        self.rows.pop(sid_hash, None)

    def touch_session(self, sid_hash, *, last_seen_at, idle_expires_at):
        row = self.rows[sid_hash]
        row["lastSeenAt"] = last_seen_at
        row["idleExpiresAt"] = idle_expires_at

    def revoke_session(self, sid_hash, *, revoked_at):
        row = self.rows.get(sid_hash)
        if row:
            row["revokedAt"] = revoked_at

    def claim_refresh(self, sid_hash, *, now, lease_seconds):
        """Single-flight: succeed only if no live lease is held. Mirrors a conditional write."""
        row = self.rows[sid_hash]
        held = int(row.get("refreshInFlight") or 0)
        if held and now < held + lease_seconds:
            return False
        row["refreshInFlight"] = now
        return True

    def release_refresh(self, sid_hash):
        row = self.rows.get(sid_hash)
        if row:
            row["refreshInFlight"] = 0

    def record_refresh(self, sid_hash, *, refresh_ref, last_seen_at, idle_expires_at):
        row = self.rows[sid_hash]
        row["refreshRef"] = refresh_ref
        row["lastSeenAt"] = last_seen_at
        row["idleExpiresAt"] = idle_expires_at


@pytest.fixture
def store():
    return FakeSessionStore()


# ── create / validate ───────────────────────────────────────────────────────────

def test_create_returns_an_opaque_id_and_stores_only_its_hash(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    assert opaque and view.customer_id == CUSTOMER
    # The raw id is NOT the key: the stored row is keyed by the hash, and the id is absent from it.
    assert view.sid_hash in store.rows
    assert view.sid_hash != opaque
    stored = store.rows[view.sid_hash]
    assert opaque not in str(stored)
    # Custody is a reference, never the token.
    assert stored["refreshRef"] == REF


def test_a_fresh_session_validates_and_slides_idle_but_not_absolute(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    absolute = view.absolute_expires_at
    later = NOW + 24 * 60 * 60
    v2 = cs.validate(store, opaque, now=later)
    assert v2.customer_id == CUSTOMER
    # Idle moved forward to now + 7 days; absolute is untouched.
    assert v2.idle_expires_at == later + cs.IDLE_LIFETIME_SECONDS
    assert v2.absolute_expires_at == absolute


def test_idle_expiry_is_enforced_in_code(store):
    opaque, _ = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    past_idle = NOW + cs.IDLE_LIFETIME_SECONDS + 1
    with pytest.raises(cs.SessionInvalid):
        cs.validate(store, opaque, now=past_idle)


def test_absolute_expiry_is_enforced_even_with_recent_activity(store):
    opaque, _ = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF,
                                  persistent=True, now=NOW)
    # Stay active right up to the absolute deadline: validate repeatedly within the idle window.
    t = NOW
    while t < NOW + cs.ABSOLUTE_LIFETIME_SECONDS - cs.IDLE_LIFETIME_SECONDS:
        t += cs.IDLE_LIFETIME_SECONDS - 1
        cs.validate(store, opaque, now=t)
    # Past the 30-day absolute cap, activity cannot save it.
    with pytest.raises(cs.SessionInvalid):
        cs.validate(store, opaque, now=NOW + cs.ABSOLUTE_LIFETIME_SECONDS + 1)


def test_idle_is_clamped_to_the_absolute_deadline(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF,
                                     persistent=False, now=NOW)
    # Shared-device absolute cap is short; a validate near it must not push idle past it.
    near = view.absolute_expires_at - 10
    v2 = cs.validate(store, opaque, now=near)
    assert v2.idle_expires_at <= view.absolute_expires_at


def test_a_shared_device_session_has_a_short_absolute_cap(store):
    _, shared = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF,
                                  persistent=False, now=NOW)
    _, remembered = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF,
                                      persistent=True, now=NOW)
    assert shared.absolute_expires_at - NOW == cs.SHARED_DEVICE_ABSOLUTE_SECONDS
    assert remembered.absolute_expires_at - NOW == cs.ABSOLUTE_LIFETIME_SECONDS
    assert shared.absolute_expires_at < remembered.absolute_expires_at


def test_an_unknown_id_does_not_validate(store):
    with pytest.raises(cs.SessionInvalid):
        cs.validate(store, "not-a-real-id", now=NOW)


# ── rotation ─────────────────────────────────────────────────────────────────────

def test_rotate_issues_a_new_id_and_retires_the_old_one(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    original_absolute = view.absolute_expires_at
    new_opaque, new_view = cs.rotate(store, opaque, now=NOW + 5)

    assert new_opaque != opaque
    # The old id no longer validates; the new one does.
    with pytest.raises(cs.SessionInvalid):
        cs.validate(store, opaque, now=NOW + 10)
    assert cs.validate(store, new_opaque, now=NOW + 10).customer_id == CUSTOMER
    # Rotation is an id swap, not a new session: the absolute anchor carries over unchanged.
    assert new_view.absolute_expires_at == original_absolute
    # The CSRF token is fresh after rotation.
    assert new_view.csrf_token != view.csrf_token


# ── CSRF ─────────────────────────────────────────────────────────────────────────

def test_csrf_matches_the_session_token(store):
    _, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    cs.assert_csrf(view, view.csrf_token)  # no raise


@pytest.mark.parametrize("presented", ["", "wrong", "x"])
def test_csrf_mismatch_is_refused(store, presented):
    _, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    with pytest.raises(cs.CsrfInvalid):
        cs.assert_csrf(view, presented)


# ── revoke / sign-out ──────────────────────────────────────────────────────────────

def test_revoke_makes_a_replayed_cookie_validate_to_nothing(store):
    opaque, _ = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    cs.revoke(store, opaque, now=NOW + 1)
    with pytest.raises(cs.SessionInvalid):
        cs.validate(store, opaque, now=NOW + 2)


def test_revoke_is_idempotent(store):
    opaque, _ = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    cs.revoke(store, opaque, now=NOW + 1)
    cs.revoke(store, opaque, now=NOW + 2)  # no raise
    cs.revoke(store, "unknown-id", now=NOW + 3)  # no raise


# ── cross-customer denial ──────────────────────────────────────────────────────────

def test_one_customers_session_never_resolves_to_another(store):
    opaque_a, _ = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    opaque_b, _ = cs.create_session(store, customer_id=OTHER, refresh_ref=REF, now=NOW)
    assert cs.validate(store, opaque_a, now=NOW + 1).customer_id == CUSTOMER
    assert cs.validate(store, opaque_b, now=NOW + 1).customer_id == OTHER
    # The two sessions are distinct rows; neither id reaches the other's customer.
    assert cs.validate(store, opaque_a, now=NOW + 1).customer_id != OTHER


# ── single-flight refresh ──────────────────────────────────────────────────────────

def _ok_refresh(new_ref="secretsmanager://wecare/customer-refresh/rotated"):
    def _refresh(ref, rotation_enabled):
        # A rotation client returns a NEW refresh reference; a non-rotation client reuses it.
        return {
            "accessToken": "new-access-token",
            "expiresIn": 3600,
            "refreshRef": new_ref if rotation_enabled else ref,
        }
    return _refresh


def test_refresh_renews_the_access_token_without_moving_the_absolute_deadline(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF,
                                     rotation_enabled=True, now=NOW)
    absolute = view.absolute_expires_at
    later = NOW + 3600
    result = cs.refresh_access_token(store, opaque, cognito_refresh=_ok_refresh(), now=later)
    assert result["accessToken"] == "new-access-token"
    # Section 16: a successful refresh must NOT extend the absolute deadline.
    assert store.rows[view.sid_hash]["absoluteExpiresAt"] == absolute
    # Idle slid forward; the rotated refresh reference replaced the old one.
    assert store.rows[view.sid_hash]["idleExpiresAt"] == later + cs.IDLE_LIFETIME_SECONDS
    assert store.rows[view.sid_hash]["refreshRef"].endswith("rotated")


def test_a_non_rotation_client_reuses_its_refresh_reference(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF,
                                     rotation_enabled=False, now=NOW)
    cs.refresh_access_token(store, opaque, cognito_refresh=_ok_refresh(), now=NOW + 1)
    assert store.rows[view.sid_hash]["refreshRef"] == REF


def test_refresh_is_single_flight(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)
    # Simulate a concurrent refresh already in flight by pre-claiming the lease.
    assert store.claim_refresh(view.sid_hash, now=NOW, lease_seconds=cs.REFRESH_LEASE_SECONDS)
    with pytest.raises(cs.RefreshUnavailable):
        cs.refresh_access_token(store, opaque, cognito_refresh=_ok_refresh(), now=NOW + 1)


def test_a_spent_refresh_token_logs_out(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)

    def _dead(ref, rotation_enabled):
        raise cs.RefreshFailed("refresh token revoked")

    with pytest.raises(cs.RefreshFailed):
        cs.refresh_access_token(store, opaque, cognito_refresh=_dead, now=NOW + 1)
    # A definite failure revokes; the session is now gone.
    assert store.rows[view.sid_hash].get("revokedAt")
    with pytest.raises(cs.SessionInvalid):
        cs.validate(store, opaque, now=NOW + 2)


def test_a_transient_provider_error_is_not_a_logout(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF, now=NOW)

    calls = {"n": 0}

    def _flaky(ref, rotation_enabled):
        calls["n"] += 1
        raise ConnectionError("EndpointConnectionError")  # a 5xx/offline, NOT a spent token

    with pytest.raises(cs.RefreshUnavailable):
        cs.refresh_access_token(store, opaque, cognito_refresh=_flaky, now=NOW + 1)
    # Bounded retry: attempted, capped, and NOT infinite.
    assert calls["n"] == cs.MAX_REFRESH_ATTEMPTS
    # The session is still valid - a provider blip must not evict a remembered session.
    assert not store.rows[view.sid_hash].get("revokedAt")
    assert cs.validate(store, opaque, now=NOW + 2).customer_id == CUSTOMER
    # The lease was released, so a later refresh can proceed.
    ok = cs.refresh_access_token(store, opaque, cognito_refresh=_ok_refresh(), now=NOW + 3)
    assert ok["accessToken"] == "new-access-token"


# ── cookie assembly ────────────────────────────────────────────────────────────────

def test_the_cookie_is_secure_httponly_host_only_lax(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF,
                                     persistent=True, now=NOW)
    cookie = cs.build_set_cookie(opaque, persistent=True,
                                 absolute_expires_at=view.absolute_expires_at, now=NOW)
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=Lax" in cookie
    # Host-only: no Domain= attribute, so it is not shared with sibling subdomains.
    assert "Domain=" not in cookie
    assert "Max-Age=" in cookie


def test_a_shared_device_cookie_is_a_session_cookie(store):
    opaque, view = cs.create_session(store, customer_id=CUSTOMER, refresh_ref=REF,
                                     persistent=False, now=NOW)
    cookie = cs.build_set_cookie(opaque, persistent=False,
                                 absolute_expires_at=view.absolute_expires_at, now=NOW)
    # No Max-Age => the browser drops it when it closes. The server still enforces both deadlines.
    assert "Max-Age=" not in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie


def test_the_clear_cookie_expires_immediately():
    assert "Max-Age=0" in cs.build_clear_cookie()


def test_read_cookie_extracts_the_opaque_id():
    headers = {"Cookie": f"foo=bar; {cs.COOKIE_NAME}=the-opaque-id; baz=qux"}
    assert cs.read_cookie(headers) == "the-opaque-id"
    assert cs.read_cookie({}) == ""
    assert cs.read_cookie(None) == ""


# ── the token/id never leaks to a URL or a log ─────────────────────────────────────

def test_no_token_or_opaque_id_is_ever_logged():
    """A log call must not pass a token, a raw session id or a refresh value as an ARGUMENT.

    The static event names (e.g. a `customer_session_csrf_rejected` literal) are fine - they carry
    no secret. What must never appear is a variable holding the opaque id, a token or the refresh
    reference being interpolated into the message, so this inspects the call's ARGUMENTS, not the
    whole rendered call.
    """
    tree = ast.parse(inspect.getsource(cs))
    forbidden_names = {"opaque", "session_id", "refresh_ref", "new_ref", "new_opaque",
                       "sid", "token", "access_token"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not ast.unparse(node.func).startswith("logger."):
            continue
        for arg in node.args:
            rendered = ast.unparse(arg)
            # The first arg is the format literal; the rest are the interpolated values.
            for name in forbidden_names:
                assert name not in rendered.lower(), \
                    f"log call interpolates {name!r}: {ast.unparse(node)}"


def test_the_module_never_builds_a_url_from_a_token():
    """No http(s) URL is assembled in this module at all - a session id or token in a URL is the
    exact leak the opaque-cookie design exists to avoid. The signed receipt URL is built in
    `receipt_links`, not here."""
    source = inspect.getsource(cs)
    assert "http://" not in source
    assert "https://" not in source


# ── config / IaC (BLOCKED-on-environment, authored not deployed) ───────────────────

def test_the_refresh_flow_is_decided_by_rotation():
    assert cfg.refresh_flow_for(True) == "GetTokensFromRefreshToken"
    assert cfg.refresh_flow_for(False) == "REFRESH_TOKEN_AUTH"


def test_the_config_preserves_custom_auth_and_does_not_update_the_pool():
    flows = cfg.REQUIRED_APP_CLIENT_SETTINGS["ExplicitAuthFlows"]
    assert "ALLOW_CUSTOM_AUTH" in flows  # WhatsApp OTP must survive
    assert "ALLOW_REFRESH_TOKEN_AUTH" in flows
    # The unblock step uses update-user-pool-client, never update-user-pool (the full-replace trap).
    assert "update-user-pool-client" in cfg.UNBLOCK_COMMANDS["update_app_client"]
    assert "update-user-pool " not in cfg.UNBLOCK_COMMANDS["update_app_client"]


def test_the_session_table_is_keyed_on_the_hash_and_private():
    tbl = cfg.REQUIRED_SESSION_TABLE
    assert tbl["KeySchema"][0]["AttributeName"] == "sidHash"
    assert tbl["SSESpecification"]["Enabled"] is True
    assert cfg.UNBLOCK_COMMANDS["inspect_rotation"].startswith("aws cognito-idp describe-user-pool-client")


def test_the_blocked_note_names_the_unblock_path():
    assert "No AWS credentials" in cfg.BLOCKED_ON_ENVIRONMENT
    assert "UpdateUserPool" in cfg.BLOCKED_ON_ENVIRONMENT
