"""
Protected Plivo Browser SDK token route, softphone session state, and diagnostics.

Every route authenticates through `lambda_utils.middleware.require_auth` before any
dispatch, on the same API as the rest of the fleet. Minting a token grants the ability to
place real telephone calls, so it needs `Operator`, not merely a valid session.

Browser routing stays OFF, and the route says so
------------------------------------------------
`PSTN_BROWSER_ROUTING_ENABLED` is absent from every live function, so it is false. This
route therefore **refuses to mint** and returns 503 with the exact reason and the exact
unblock. That is deliberate rather than a stub:

* The route, its auth, its role gate, its contract and its tests are all complete and
  verifiable now.
* Enabling it later is a flag flip plus session-endpoint provisioning - no code change.
* Minting while the flag is off would hand a browser the ability to place live outbound
  calls, which is exactly the live-send path the standing instruction keeps closed.

A token is a bearer credential for telephony. It is returned to the caller, never logged,
and never written to a session row.

Inbound is refused while endpoints are shared
---------------------------------------------
`browser_token.plan_session_endpoint` reports `provisioned: False`: per-session Plivo
endpoints do not exist yet. Plivo supports multiple simultaneous registrations of one
endpoint for **outbound only** - for inbound, which tab rings is undefined, and past a few
registrations it fails with 10010. So `incomingAllow` is refused rather than silently
granted, and the response says why.

Routes
------
    POST /pstn/token                 mint a Browser SDK token (Operator)
    GET  /pstn/session               this actor's softphone session
    POST /pstn/session/events        apply an SDK event to the LOCAL leg (Operator)
    POST /pstn/session/presence      set presence (Operator)
    GET  /pstn/diagnostics           config posture and login-error reference
"""

import json
import os
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3

from lambda_utils.logging import get_logger, log_event
from lambda_utils.response import cors_response, extract_origin, options_response
from lambda_utils.middleware import require_auth
from lambda_utils.pstn import browser_token, softphone

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
secrets_client = boto3.client('secretsmanager',
                              region_name=os.environ.get('AWS_REGION', 'us-east-1'))

SESSIONS_TABLE = os.environ.get('PSTN_SESSIONS_TABLE',
                                'stack-wecare-digital-PstnSoftphoneSessions')

#: Plivo REST credential. Secrets Manager only - never an environment variable.
PLIVO_API_SECRET_ID = os.environ.get('PLIVO_API_SECRET_ID', 'wecare/plivo/api')

#: Non-secret identifiers. The application whose answer/hangup URLs we control, and the
#: base endpoint. Both are protected resources: never re-register or delete them.
PLIVO_APPLICATION_ID = os.environ.get('PLIVO_APPLICATION_ID', '')
PSTN_BASE_ENDPOINT = os.environ.get('PSTN_AGENT_ENDPOINT', '')

#: The gate. Absent means false, which is the current live state on every function.
BROWSER_ROUTING_ENABLED = os.environ.get(
    'PSTN_BROWSER_ROUTING_ENABLED', 'false').lower() == 'true'

#: Minting a token lets a browser place real calls, so it is an Operator action.
WRITE_ROLE = 'Operator'

_credentials_cache: Dict[str, str] = {}


def _plivo_credentials() -> Dict[str, str]:
    """Load the Plivo REST credential from Secrets Manager. Cached per sandbox.

    Lazily, never at import. A module-scope read is cached for the life of the execution
    environment, so a rotation would not take effect until every warm sandbox recycled -
    the defect already fixed across this fleet for razorpay-webhook and others.
    """
    if _credentials_cache.get('auth_id'):
        return _credentials_cache
    try:
        raw = secrets_client.get_secret_value(SecretId=PLIVO_API_SECRET_ID)
        data = json.loads(raw['SecretString'])
    except Exception as exc:  # noqa: BLE001
        log_event(logger, 'pstn_plivo_secret_unavailable', level='error',
                  secretId=PLIVO_API_SECRET_ID, error=str(exc)[:200])
        return {}
    missing = [f for f in ('auth_id', 'auth_token')
               if not str(data.get(f) or '').strip()]
    if missing:
        # Field names only, never values. Naming them turns an opaque failure into a
        # fixable one.
        log_event(logger, 'pstn_plivo_secret_incomplete', level='error',
                  secretId=PLIVO_API_SECRET_ID, missingFields=missing)
        return {}
    _credentials_cache.update({
        'auth_id': str(data['auth_id']).strip(),
        'auth_token': str(data['auth_token']).strip(),
    })
    return _credentials_cache


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get('body') or '{}'
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _actor(event: Dict[str, Any]) -> str:
    return str((event.get('_auth') or {}).get('username') or '')


def _session_id(actor: str, body: Dict[str, Any]) -> str:
    """The session key: the actor plus a client-supplied tab id.

    Scoped to the actor from the token, so a caller cannot address another agent's session
    by guessing an id. The tab component only distinguishes this user's own tabs.
    """
    tab = ''.join(c for c in str(body.get('sessionId') or 'default') if c.isalnum())[:24]
    return f'{actor}#{tab or "default"}'


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = getattr(context, 'aws_request_id', 'local')
    origin = extract_origin(event)
    rc = event.get('requestContext', {}) or {}
    method = (rc.get('http', {}).get('method') or event.get('httpMethod') or 'GET').upper()
    path = rc.get('http', {}).get('path') or event.get('rawPath') or ''

    if method == 'OPTIONS':
        return options_response(origin)

    auth_failure = require_auth(event)
    if auth_failure is not None:
        return auth_failure
    if method in ('POST', 'PATCH', 'PUT', 'DELETE'):
        role_failure = require_auth(event, required_role=WRITE_ROLE)
        if role_failure is not None:
            return role_failure

    actor = _actor(event)
    body = _body(event)

    log_event(logger, 'pstn_softphone_request', method=method, path=path,
              actor=actor, role=(event.get('_auth') or {}).get('role', ''),
              requestId=request_id)

    try:
        if '/pstn/diagnostics' in path:
            if method != 'GET':
                return cors_response(405, {'error': 'GET only'}, origin)
            return _diagnostics(body, origin)

        if '/pstn/token' in path:
            if method != 'POST':
                return cors_response(405, {'error': 'POST only'}, origin)
            return _mint(actor, body, origin, request_id)

        if '/pstn/session/events' in path:
            if method != 'POST':
                return cors_response(405, {'error': 'POST only'}, origin)
            return _sdk_event(actor, body, origin)

        if '/pstn/session/presence' in path:
            if method != 'POST':
                return cors_response(405, {'error': 'POST only'}, origin)
            return _presence(actor, body, origin)

        if '/pstn/session' in path:
            if method != 'GET':
                return cors_response(405, {'error': 'GET only'}, origin)
            return _session(actor, event.get('queryStringParameters') or {}, origin)

        return cors_response(404, {'error': f'Unknown PSTN path: {path}'}, origin)
    except softphone.TransitionRefused as exc:
        # 409: the request was well formed and the state does not permit it. A client
        # should re-read, which is a different action from fixing a payload.
        return cors_response(409, {'error': str(exc)}, origin)
    except browser_token.TokenError as exc:
        return cors_response(502, {'error': str(exc), 'code': exc.code}, origin)
    except ValueError as exc:
        return cors_response(400, {'error': str(exc)}, origin)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, 'pstn_softphone_error', level='error',
                  path=path, error=str(exc)[:300], requestId=request_id)
        return cors_response(500, {'error': 'Internal error'}, origin)


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

def _mint(actor: str, body: Dict[str, Any], origin: str,
          request_id: str) -> Dict[str, Any]:
    """Mint a Browser SDK token, or explain precisely why not.

    The refusal path is the live one today. It returns everything an operator needs to act
    and nothing a browser could use.
    """
    if not BROWSER_ROUTING_ENABLED:
        # Not a stub and not an error: the deliberate current posture. Minting here would
        # hand a browser the ability to place live outbound calls.
        return cors_response(503, {
            'error': 'Browser softphone is disabled',
            'code': 'PSTN_BROWSER_ROUTING_DISABLED',
            'detail': ('PSTN_BROWSER_ROUTING_ENABLED is not true on this function. '
                       'Minting a token would allow a browser to place live outbound '
                       'calls, so the route refuses rather than issuing one.'),
            'unblock': [
                'provision per-session Plivo endpoints (see '
                'pstn.browser_token.plan_session_endpoint)',
                'set PSTN_AGENT_ENDPOINT',
                'set PSTN_BROWSER_ROUTING_ENABLED=true on wecare-pstn-softphone',
                'publish a version and move the live alias',
            ],
            'routeReady': True,
        }, origin)

    if not PSTN_BASE_ENDPOINT:
        return cors_response(503, {
            'error': 'No base endpoint configured',
            'code': 'PSTN_NO_AGENT_ENDPOINT',
            'detail': ('PSTN_BROWSER_ROUTING_ENABLED is true but PSTN_AGENT_ENDPOINT is '
                       'empty. A token with no sub cannot register.'),
        }, origin)

    credentials = _plivo_credentials()
    if not credentials:
        return cors_response(503, {
            'error': 'Plivo credentials unavailable',
            'code': 'NO_PROVIDER_CREDENTIALS',
            'detail': f'{PLIVO_API_SECRET_ID} could not be read or is incomplete',
        }, origin)

    session_id = _session_id(actor, body)
    plan = browser_token.plan_session_endpoint(PSTN_BASE_ENDPOINT, session_id)

    # Inbound needs a per-session endpoint. Until those exist, granting it would make
    # which tab rings undefined and eventually hit Plivo error 10010.
    wants_inbound = bool(body.get('incomingAllow'))
    if wants_inbound and not plan['inboundSafe']:
        return cors_response(409, {
            'error': 'Inbound is not available on a shared endpoint',
            'code': 'PSTN_INBOUND_NEEDS_SESSION_ENDPOINT',
            'detail': plan['reason'],
            'plan': plan,
        }, origin)

    endpoint_username = (plan['sessionEndpointUsername'] if plan['provisioned']
                         else PSTN_BASE_ENDPOINT)

    minted = browser_token.mint_token(
        auth_id=credentials['auth_id'],
        auth_token=credentials['auth_token'],
        endpoint_username=endpoint_username,
        app_id=PLIVO_APPLICATION_ID,
        ttl_seconds=body.get('ttlSeconds'),
        incoming_allow=False,
        outgoing_allow=True,
        request_id=request_id,
    )

    # Record the session, never the token. A token written to a row is a reusable
    # telephony credential sitting in a table with a different access policy.
    session = _load(session_id) or softphone.new_session(
        session_id=session_id, actor=actor, endpoint_username=endpoint_username)
    session['endpointUsername'] = endpoint_username
    session['registration'] = softphone.REGISTERING
    _save(session)

    return cors_response(200, _json_safe({**minted, 'sessionId': session_id}), origin)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def _load(session_id: str) -> Optional[Dict[str, Any]]:
    try:
        return dynamodb.Table(SESSIONS_TABLE).get_item(
            Key={'sessionId': session_id}).get('Item')
    except Exception as exc:  # noqa: BLE001
        log_event(logger, 'pstn_session_read_failed', level='warning',
                  error=str(exc)[:200])
        return None


def _save(session: Dict[str, Any]) -> None:
    try:
        dynamodb.Table(SESSIONS_TABLE).put_item(Item=session)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, 'pstn_session_write_failed', level='error',
                  error=str(exc)[:200])


def _session(actor: str, params: Dict[str, Any], origin: str) -> Dict[str, Any]:
    session_id = _session_id(actor, {'sessionId': params.get('sessionId')})
    session = _load(session_id)
    return cors_response(200, _json_safe({
        'sessionId': session_id,
        'session': softphone.describe(session),
    }), origin)


def _sdk_event(actor: str, body: Dict[str, Any], origin: str) -> Dict[str, Any]:
    """Apply a Browser SDK event to the LOCAL leg.

    This route cannot touch the remote leg: `apply_local_event` has no path that writes
    `remoteLegState`. That is what stops a browser claiming the customer answered - the
    only input trusted for that is a provider Dial callback.
    """
    sdk_event = str(body.get('event') or '').strip()
    if not sdk_event:
        return cors_response(400, {
            'error': 'event is required',
            'knownEvents': sorted(softphone.SDK_EVENTS),
        }, origin)

    session_id = _session_id(actor, body)
    session = _load(session_id)
    if not session:
        return cors_response(404, {'error': 'No softphone session; mint a token first'},
                             origin)

    updated = softphone.apply_local_event(session, sdk_event)
    # A local leg that ended frees the agent, but only presence says they are available
    # again - the tab may have been closed.
    if updated['localLegState'] in (softphone.LOCAL_ENDED, softphone.LOCAL_FAILED) \
            and updated.get('presence') == softphone.BUSY:
        updated['presence'] = softphone.AVAILABLE
    elif updated['localLegState'] == softphone.LOCAL_CONNECTED:
        updated['presence'] = softphone.BUSY
    _save(updated)

    return cors_response(200, _json_safe({
        'sessionId': session_id,
        'session': softphone.describe(updated),
    }), origin)


def _presence(actor: str, body: Dict[str, Any], origin: str) -> Dict[str, Any]:
    presence = str(body.get('presence') or '').strip().upper()
    if presence not in softphone.PRESENCE_STATES:
        return cors_response(400, {
            'error': f'unknown presence {presence or "(missing)"}',
            'presenceStates': list(softphone.PRESENCE_STATES),
        }, origin)

    session_id = _session_id(actor, body)
    session = _load(session_id)
    if not session:
        return cors_response(404, {'error': 'No softphone session; mint a token first'},
                             origin)
    if presence == softphone.AVAILABLE and str(
            session.get('localLegState')) == softphone.LOCAL_CONNECTED:
        # Claiming availability mid-call would route a second customer into an occupied
        # browser.
        return cors_response(409, {
            'error': 'Cannot become AVAILABLE while the local leg is connected',
            'session': softphone.describe(session),
        }, origin)

    session['presence'] = presence
    _save(session)
    return cors_response(200, _json_safe({
        'sessionId': session_id,
        'session': softphone.describe(session),
    }), origin)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def _diagnostics(body: Dict[str, Any], origin: str) -> Dict[str, Any]:
    """Configuration posture for an authorised operator. No credential, no token.

    Reports presence of each identifier rather than its value where the value is a
    provider resource id, and never touches the Plivo auth token.
    """
    credentials = _plivo_credentials()
    return cors_response(200, {
        'browserRoutingEnabled': BROWSER_ROUTING_ENABLED,
        'baseEndpointConfigured': bool(PSTN_BASE_ENDPOINT),
        'applicationConfigured': bool(PLIVO_APPLICATION_ID),
        'providerCredentialsAvailable': bool(credentials),
        'secretId': PLIVO_API_SECRET_ID,
        'sessionsTable': SESSIONS_TABLE,
        'tokenTtlSecondsDefault': browser_token.DEFAULT_TTL_SECONDS,
        'tokenTtlSecondsMax': browser_token.MAX_TTL_SECONDS,
        'inboundSupported': False,
        'inboundReason': ('per-session Plivo endpoints are not provisioned; a shared '
                          'endpoint is reliable for outbound only'),
        'registrationStates': list(softphone.REGISTRATION_STATES),
        'presenceStates': list(softphone.PRESENCE_STATES),
        'localLegStates': list(softphone.LOCAL_STATES),
        'remoteLegStates': list(softphone.REMOTE_STATES),
        'sdkEvents': sorted(softphone.SDK_EVENTS),
        'loginErrorCodes': {str(k): v
                            for k, v in browser_token.LOGIN_ERROR_CODES.items()},
        'legNote': ('localLegState is the agent browser. remoteLegState is the other '
                    'party. Only remotePartyAnswered may start billing or fire a '
                    'connected-call notification.'),
    }, origin)
