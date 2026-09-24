"""
Auth enforcement middleware for Lambda handlers.

Usage:
    from lambda_utils.middleware import require_auth

    def handler(event, context):
        auth_result = require_auth(event)
        if auth_result is not None:
            return auth_result  # 401/403 response
        # ... proceed with handler logic
"""

import os
import json
import boto3
from typing import Any, Dict, Optional

from lambda_utils.response import cors_response, extract_origin
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

cognito = boto3.client('cognito-idp', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', 'us-east-1_cSx0RHCIR')

ROLE_HIERARCHY = {'Admin': 3, 'Operator': 2, 'Viewer': 1}

# Paths that skip auth. Only genuinely self-authenticating provider endpoints
# belong here - a Meta Flows data-exchange endpoint proves authenticity by RSA
# decryption, a provider webhook by HMAC signature. An endpoint that merely
# *sounds* like a callback does not qualify; see `path_is_exempt`.
AUTH_SKIP_PATHS = os.environ.get('AUTH_SKIP_PATHS', '').split(',')


def path_is_exempt(path: str, stage: str = '', skips=None) -> bool:
    """Exact path match, or a child segment of an exempt path. Never a substring.

    The original form was `skip.strip() in path`, a bare substring test, and that
    is wider than it looks once a catch-all route exists. `wecare-whatsapp-business-api`
    serves `ANY /wa-business/{proxy+}` alongside its explicit routes, so a request
    to `/wa-business/webhooks-anything` reached the same handler, matched the
    substring, and skipped authentication - then fell into the handler's
    `elif '/webhooks' in path` branch and executed the management action anyway.
    Two loose matchers in series, each individually defensible.

    Matching on segment boundaries removes the first one. `/wa-business/flow-data`
    still exempts itself and `/wa-business/flow-data/sub`; it no longer exempts
    `/wa-business/flow-dataX` or `/x/wa-business/flow-data`.
    """
    candidates = [s.strip() for s in (AUTH_SKIP_PATHS if skips is None else skips) if s and s.strip()]
    if not candidates:
        return False

    # Strip the API Gateway stage prefix, so `/prod/x` and `/x` behave alike. On
    # this HTTP API the custom-domain mapping puts the stage in the path, and that
    # difference has already caused two production incidents - see
    # `lambda_utils.http_path`. Without this, a stage-prefixed request to a
    # genuinely exempt endpoint would be sent to the auth gate instead.
    try:
        from lambda_utils.http_path import strip_stage
        normalized = strip_stage(path or '', stage or '')
    except Exception:  # pragma: no cover - the normalizer must never gate auth
        normalized = path or ''
    normalized = '/' + (normalized or '').strip('/')

    for skip in candidates:
        skip = '/' + skip.strip('/')
        if normalized == skip or normalized.startswith(skip + '/'):
            return True
    return False


def require_auth(
    event: Dict[str, Any],
    required_role: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Validate Cognito JWT token from the Authorization header.

    Returns None if auth succeeds (caller should proceed).
    Returns a cors_response dict if auth fails (caller should return it).

    Sets event['_auth'] with user info on success:
        event['_auth'] = {
            'username': str,
            'email': str,
            'role': str,
            'groups': list,
        }

    Skips auth for:
    - OPTIONS preflight requests
    - Paths listed in AUTH_SKIP_PATHS env var
    - Lambda-to-Lambda invocations (no requestContext.http and no httpMethod)
    """
    origin = extract_origin(event)

    # Skip auth for OPTIONS
    rc = event.get('requestContext', {})
    method = rc.get('http', {}).get('method', event.get('httpMethod', '')).upper()
    if method == 'OPTIONS':
        return None

    # Skip auth for internal Lambda-to-Lambda invocations.
    # Requests that arrive through API Gateway (the only externally reachable
    # path) always carry an API Gateway request context — apiId, domainName, and
    # http.sourceIp are injected by API Gateway HTTP APIs. Internal invokes built
    # by our own code (e.g. flow -> invoice-engine payment links, inbound -> pay)
    # do not have these, even though some include a minimal requestContext.http
    # for routing. The previous "no http context at all" check missed those and
    # returned 401 on legitimate internal calls. Treat any event lacking an API
    # Gateway context as internal. This does NOT create external exposure:
    # unauthenticated external callers can only reach the function via API Gateway
    # (apiId present -> auth enforced); direct Lambda invokes already require IAM.
    is_api_gateway = bool(
        rc.get('apiId') or rc.get('domainName')
        or rc.get('http', {}).get('sourceIp')
    )
    if not is_api_gateway:
        return None

    # Skip auth for configured self-authenticating provider endpoints.
    path = rc.get('http', {}).get('path', event.get('path', ''))
    if path_is_exempt(path, str(rc.get('stage') or '')):
        return None

    # Extract token
    headers = event.get('headers', {})
    auth_header = headers.get('authorization', headers.get('Authorization', ''))
    token = auth_header.replace('Bearer ', '') if auth_header else ''

    if not token:
        return cors_response(401, {'error': 'No authorization token provided'}, origin)

    # Validate with Cognito
    try:
        user_info = cognito.get_user(AccessToken=token)
    except cognito.exceptions.NotAuthorizedException:
        return cors_response(401, {'error': 'Invalid or expired token'}, origin)
    except Exception as e:
        logger.warning(json.dumps({'event': 'auth_validation_error', 'error': str(e)}))
        return cors_response(401, {'error': 'Token validation failed'}, origin)

    username = user_info.get('Username', '')
    attributes = {attr['Name']: attr['Value'] for attr in user_info.get('UserAttributes', [])}

    # Get groups
    groups = []
    try:
        groups_resp = cognito.admin_list_groups_for_user(
            Username=username, UserPoolId=USER_POOL_ID
        )
        groups = [g['GroupName'] for g in groups_resp.get('Groups', [])]
    except Exception as e:
        logger.warning(json.dumps({'event': 'groups_fetch_error', 'username': username, 'error': str(e)}))

    # Determine highest role
    role = 'Viewer'
    for group in groups:
        if ROLE_HIERARCHY.get(group, 0) > ROLE_HIERARCHY.get(role, 0):
            role = group

    # Check required role
    if required_role and ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(required_role, 0):
        return cors_response(403, {
            'error': 'Insufficient permissions',
            'requiredRole': required_role,
            'currentRole': role,
        }, origin)

    # --- Admin second factor -------------------------------------------------
    # Checked where the Admin privilege is USED, not at sign-in, because that is where
    # it is actually exercised - and only when Admin is required, so an Admin reading a
    # Viewer-level route does not pay an extra AdminGetUser per request.
    #
    # The role refusal above runs FIRST on purpose: a Viewer asking for Admin gets
    # "Insufficient permissions", not an MFA message, which would disclose that the
    # Admin role exists and what it requires.
    mfa_enrolled: Optional[bool] = None
    mfa_required = _admin_mfa_required()
    if required_role == 'Admin':
        mfa_enrolled = _has_enrolled_mfa(username)

        if mfa_enrolled is not True:
            log_level = 'error' if mfa_required else 'warning'
            logger.warning(json.dumps({
                'event': 'admin_without_mfa',
                'alert': 'ADMIN_MFA_MISSING',
                'level': log_level,
                'username': username,
                # None means the lookup failed; False means definitely not enrolled.
                # Collapsing the two would make a Cognito outage look like a policy
                # violation, and vice versa.
                'mfaEnrolled': mfa_enrolled,
                'enforcing': mfa_required,
            }))

        if mfa_required and mfa_enrolled is not True:
            # Fails CLOSED, deliberately the opposite of the audit sink's choice. An
            # audit write that fails open loses a record; an authorization check that
            # fails open grants administrator.
            return cors_response(403, {
                'error': 'MFA required',
                'detail': ('Administrator actions require a second factor. Enrol an '
                           'authenticator app in your account settings, sign in '
                           'again, and retry.'),
            }, origin)

    # Attach auth info to event for downstream use.
    # `attributes` includes any custom attributes (e.g. custom:partner_waba_id)
    # so handlers can scope data to a specific tenant for customer users.
    event['_auth'] = {
        'username': username,
        'email': attributes.get('email', ''),
        'role': role,
        'groups': groups,
        'attributes': attributes,
        # True / False / None, where None means the lookup could not answer.
        'mfaEnrolled': mfa_enrolled,
        'mfaRequired': mfa_required,
    }

    return None


def _admin_mfa_required() -> bool:
    """Whether a missing Admin second factor should refuse rather than warn.

    Read per call, not captured at import: this is a security posture switch and one
    that only takes effect after every warm sandbox recycles is not much of a switch.

    Defaults to warn. Measured 2026-09-23: the pool has one user, that user is in NO
    group, and all four groups are empty - so enforcing immediately would refuse the
    first Admin ever created until they enrolled, and whoever hit that would turn the
    check off rather than enrol. Warn first, with a findable alert, then flip.
    """
    return str(os.environ.get('ADMIN_MFA_REQUIRED', '')).strip().lower() in (
        '1', 'true', 'yes', 'on')


def _has_enrolled_mfa(username: str) -> Optional[bool]:
    """True / False / None for "does this user have a second factor registered".

    Deliberately ENROLMENT, not "did this session use MFA". `require_auth` validates an
    access token via `get_user`, and a Cognito access token carries no reliable `amr`
    claim, so the session question is not answerable here. Enrolment plus a pool
    `MfaConfiguration` of OPTIONAL or ON means Cognito will have issued a challenge;
    claiming to verify more than that would overstate the control.

    Any factor counts - TOTP, SMS or email OTP. The live account's sole user has
    SMS_MFA and EMAIL_OTP and no TOTP, so insisting on TOTP would refuse the one person
    who actually has a second factor.

    Returns None rather than False when the lookup fails, so a Cognito outage is
    distinguishable from a user who has enrolled nothing.
    """
    try:
        detail = cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
    except Exception as exc:  # noqa: BLE001
        logger.warning(json.dumps({
            'event': 'mfa_lookup_failed', 'username': username,
            'error': type(exc).__name__,
        }))
        return None

    factors = detail.get('UserMFASettingList') or []
    if detail.get('PreferredMfaSetting'):
        return True
    return bool(factors)


def health_check(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return a 200 health check response if the request path ends with /health.
    Returns None if not a health check request (caller should proceed).
    """
    rc = event.get('requestContext', {})
    path = rc.get('http', {}).get('path', event.get('path', ''))
    if path.rstrip('/').endswith('/health'):
        from lambda_utils.response import cors_response, extract_origin
        origin = extract_origin(event)
        return cors_response(200, {'status': 'healthy'}, origin)
    return None
