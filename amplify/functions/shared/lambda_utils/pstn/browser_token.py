"""Short-lived Plivo Browser SDK access tokens, minted server-side.

Plivo signs the JWT, we do not
------------------------------
This was worth checking rather than assuming. The token is produced by a Plivo
REST call:

    POST https://api.plivo.com/v1/Account/{auth_id}/JWT/Token/

and the returned JWT's signature is "HMAC-SHA256, signed by Plivo (not your
auth_token)". Signing one locally with the account auth token therefore does NOT
work - the SDK rejects it with error 10007 INVALID_ACCESS_TOKEN_SIGNATURE. Our
auth token is the API credential for minting, not the signing key.

Verified 2026-09-19 against docs.plivo.com/docs/voice/sdk/browser/jwt-authentication
and the official plivo-python 4.x `plivo/resources/token.py`.

The permissions object is NESTED
--------------------------------
    {"per": {"voice": {"incoming_allow": true, "outgoing_allow": true}}}

The documentation page's field table lists `incoming_allow` and `outgoing_allow`
as if they sat directly under `per`. The official SDK nests them under `voice`,
and the SDK is what Plivo's own examples run. Flat grants produce error 10008
INVALID_ACCESS_TOKEN_GRANTS - accepted by the mint call, rejected at login, which
is the worst place to discover it.

`nbf` and `exp` are sent as STRINGS, matching the SDK's own validators
(`optional(of_type(six.text_type))`), so this sends exactly what Plivo's official
client sends.

One endpoint per concurrent session
-----------------------------------
Plivo's own guidance: multiple simultaneous registrations of the SAME endpoint are
only reliable for outbound-only use. For inbound routing a unique endpoint per
browser session is required, otherwise which tab rings is undefined.

So `session_endpoint_username` derives a per-session identity. Provisioning those
endpoints is a control-plane operation and is deliberately NOT done here - see
`plan_session_endpoint`.

Why the SDK is not imported
---------------------------
`plivo` is a dev-only dependency and is not bundled into the Lambda packages, so
this issues the HTTP request directly with the same contract.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from lambda_utils.logging import get_logger, log_event

logger = get_logger(__name__)

PLIVO_API_BASE = os.environ.get("PLIVO_API_BASE", "https://api.plivo.com")

# 5 minutes. Plivo's own recommendation, and the brief's default. The SDK holds
# the SIP registration after login, so a short token does not mean frequent
# re-auth - it means a stolen token is worth very little.
DEFAULT_TTL_SECONDS = int(os.environ.get("PSTN_TOKEN_TTL_SECONDS", "300"))

# Plivo rejects anything longer with error 10009. Clamped locally so the failure
# is a clear local error rather than a confusing login failure in the browser.
MAX_TTL_SECONDS = 24 * 60 * 60

# Small backdate on nbf. Without it, a client whose clock is a second or two ahead
# of ours gets error 10005 ACCESS_TOKEN_NOT_VALID_YET on a perfectly good token.
NBF_SKEW_SECONDS = int(os.environ.get("PSTN_TOKEN_NBF_SKEW_SECONDS", "10"))

# Documented login failure codes, mapped to something an operator can act on.
# Surfaced to authorised diagnostics only - never to an end user.
LOGIN_ERROR_CODES = {
    10001: "INVALID_ACCESS_TOKEN: the token is malformed.",
    10002: "INVALID_ACCESS_TOKEN_HEADER: the token header is invalid.",
    10003: "INVALID_ACCESS_TOKEN_ISSUER: iss does not match the account auth id.",
    10004: "INVALID_ACCESS_TOKEN_SUBJECT: sub is not a valid endpoint username.",
    10005: ("ACCESS_TOKEN_NOT_VALID_YET: client clock is behind nbf. "
            "Increase PSTN_TOKEN_NBF_SKEW_SECONDS."),
    10006: "ACCESS_TOKEN_EXPIRED: fetch a new token and log in again.",
    10007: ("INVALID_ACCESS_TOKEN_SIGNATURE: the token was not minted by the "
            "Plivo REST API. Do not sign tokens locally."),
    10008: ("INVALID_ACCESS_TOKEN_GRANTS: the per object is missing or the wrong "
            "shape. It must be {'voice': {...}}, not flat."),
    10009: ("EXPIRATION_EXCEEDS_MAX_ALLOWED_TIME: exp is more than 24h ahead."),
    10010: ("MAX_ALLOWED_LOGIN_REACHED: too many concurrent registrations for "
            "this endpoint. Use a unique endpoint per browser session."),
}


class TokenError(RuntimeError):
    """Minting failed. The message is safe to log; it carries no credential."""

    def __init__(self, message: str, *, code: str = "TOKEN_MINT_FAILED") -> None:
        super().__init__(message)
        self.code = code


def clamp_ttl(requested_seconds: Optional[int]) -> int:
    """Bound the requested lifetime. Never exceeds 24h; never below 30s.

    A floor exists because a token that expires before the browser finishes
    registering is indistinguishable, from the user's side, from a broken login.
    """
    if not requested_seconds:
        return DEFAULT_TTL_SECONDS
    try:
        seconds = int(requested_seconds)
    except (TypeError, ValueError):
        return DEFAULT_TTL_SECONDS
    return max(30, min(seconds, MAX_TTL_SECONDS))


def session_endpoint_username(base_username: str, session_id: str) -> str:
    """The per-session endpoint identity.

    Plivo endpoint usernames are provider-side resources, so this does not invent
    an arbitrary string - it derives a deterministic candidate from the base
    endpoint and the session, which `plan_session_endpoint` then reconciles.

    Deterministic on purpose: a reconnecting session must resolve to the SAME
    endpoint, or it would strand registrations and eventually hit error 10010.
    """
    base = str(base_username or "").strip()
    session = "".join(c for c in str(session_id or "") if c.isalnum())[:16]
    if not base:
        raise TokenError("base endpoint username is required",
                         code="NO_BASE_ENDPOINT")
    if not session:
        raise TokenError("session id is required to derive an endpoint identity",
                         code="NO_SESSION_ID")
    return f"{base}{session}"


def plan_session_endpoint(base_username: str, session_id: str) -> Dict[str, Any]:
    """What WOULD be provisioned for this session. Does not create anything.

    Creating a Plivo endpoint is a control-plane write, and this module is on the
    request path for every softphone sign-in. Provisioning here would mean an
    unbounded number of provider resources created by ordinary user traffic, with
    no plan, no approval and no drift record.

    So this returns the plan and the caller decides. Until session endpoints are
    provisioned, token issuance falls back to the base endpoint, which Plivo
    supports for OUTBOUND-ONLY use - and `incoming_allow` is refused in that case
    rather than silently granted, because inbound routing to a shared endpoint is
    undefined.
    """
    return {
        "baseEndpointUsername": base_username,
        "sessionEndpointUsername": session_endpoint_username(base_username, session_id),
        "provisioned": False,
        "reason": ("Per-session Plivo endpoints are not provisioned yet. Creating "
                   "them is a control-plane operation requiring a reviewed plan, "
                   "not a side effect of a user signing in."),
        "inboundSafe": False,
        "outboundSafe": True,
    }


def _basic_auth_header(auth_id: str, auth_token: str) -> str:
    raw = f"{auth_id}:{auth_token}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def mint_token(*, auth_id: str, auth_token: str, endpoint_username: str,
               app_id: str = "", ttl_seconds: Optional[int] = None,
               incoming_allow: bool = False, outgoing_allow: bool = True,
               request_id: str = "") -> Dict[str, Any]:
    """Mint a JWT via the Plivo REST API.

    Returns the minimal client bootstrap - the token and its expiry - and nothing
    else. The browser has no need for the auth id, the endpoint password, the app
    id or the account structure, and anything returned here ends up in a
    JavaScript variable.

    Raises TokenError on failure. The message never contains a credential.
    """
    if not auth_id or not auth_token:
        raise TokenError("Plivo credentials are not available",
                         code="NO_PROVIDER_CREDENTIALS")
    if not endpoint_username:
        raise TokenError("endpoint username is required", code="NO_ENDPOINT")
    if incoming_allow and not endpoint_username:
        # Plivo enforces this too; failing here gives a clearer message.
        raise TokenError("sub is required when incoming_allow is true",
                         code="NO_ENDPOINT_FOR_INBOUND")

    ttl = clamp_ttl(ttl_seconds)
    now = int(time.time())
    not_before = now - NBF_SKEW_SECONDS
    expires_at = now + ttl

    # Strings, matching the official SDK's own validators.
    payload: Dict[str, Any] = {
        "iss": auth_id,
        "sub": endpoint_username,
        "nbf": str(not_before),
        "exp": str(expires_at),
        # NESTED under `voice`. Flat grants are accepted at mint time and rejected
        # at login with 10008, which is the worst place to find out.
        "per": {"voice": {
            "incoming_allow": bool(incoming_allow),
            "outgoing_allow": bool(outgoing_allow),
        }},
    }
    if app_id:
        # Ties the session to the application whose answer/hangup URLs we control.
        # Plivo warns that a mismatch between this and the endpoint's application
        # makes call routing behave unexpectedly.
        payload["app"] = app_id

    url = f"{PLIVO_API_BASE}/v1/Account/{auth_id}/JWT/Token/"
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": _basic_auth_header(auth_id, auth_token),
        })

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            parsed = json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = (exc.read().decode() or "")[:200]
        except Exception:  # noqa: BLE001
            detail = ""
        log_event(logger, "pstn_token_mint_http_error", level="error",
                  status=exc.code, requestId=request_id)
        raise TokenError(f"Plivo rejected the token request (HTTP {exc.code}): "
                         f"{detail}", code=f"PLIVO_HTTP_{exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "pstn_token_mint_failed", level="error",
                  errorType=type(exc).__name__, requestId=request_id)
        raise TokenError("could not reach the Plivo token API",
                         code="PROVIDER_UNREACHABLE") from exc

    token = (parsed.get("token") or parsed.get("jwt")
             or parsed.get("access_token") or "")
    if not token:
        raise TokenError("Plivo returned no token in the response",
                         code="NO_TOKEN_IN_RESPONSE")

    # Audit the ISSUANCE, never the token. A logged JWT is a reusable credential
    # for its whole lifetime.
    log_event(logger, "pstn_token_issued",
              endpointUsername=endpoint_username, appId=app_id or None,
              ttlSeconds=ttl, incomingAllow=bool(incoming_allow),
              outgoingAllow=bool(outgoing_allow),
              tokenLength=len(token), requestId=request_id)

    return {
        "token": token,
        "expiresAt": expires_at,
        "expiresInSeconds": ttl,
        # So the client can schedule a refresh BEFORE expiry rather than
        # discovering it mid-call. 80% of the lifetime, floor 20s.
        "refreshAfterSeconds": max(20, int(ttl * 0.8)),
        "endpointUsername": endpoint_username,
        "incomingAllow": bool(incoming_allow),
        "outgoingAllow": bool(outgoing_allow),
    }


def describe_login_error(code: Any) -> str:
    """Explain a Browser SDK onLoginFailed code for an authorised diagnostic."""
    try:
        numeric = int(code)
    except (TypeError, ValueError):
        return f"Unrecognised login error: {code!r}"
    return LOGIN_ERROR_CODES.get(
        numeric, f"Unrecognised Plivo login error code {numeric}")
