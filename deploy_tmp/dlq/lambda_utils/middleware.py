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

# Paths that skip auth (webhooks, health checks, etc.)
AUTH_SKIP_PATHS = os.environ.get('AUTH_SKIP_PATHS', '').split(',')


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

    # Skip auth for Lambda-to-Lambda invocations (no HTTP context at all)
    if not rc.get('http') and not event.get('httpMethod'):
        return None

    # Skip auth for configured paths (webhooks, etc.)
    path = rc.get('http', {}).get('path', event.get('path', ''))
    for skip in AUTH_SKIP_PATHS:
        if skip and skip.strip() and skip.strip() in path:
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

    # Attach auth info to event for downstream use
    event['_auth'] = {
        'username': username,
        'email': attributes.get('email', ''),
        'role': role,
        'groups': groups,
    }

    return None


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
