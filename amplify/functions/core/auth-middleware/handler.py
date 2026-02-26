"""
Auth Middleware Lambda Function
Purpose: Validate Cognito JWT tokens and check user roles/permissions
Used as a Lambda authorizer or direct auth check endpoint

Migrated to use shared lambda_utils for CORS, logging, and validation.
"""
import os
import json
import boto3
from typing import Dict, Any

from lambda_utils.response import cors_response, options_response
from lambda_utils.logging import get_logger, log_event
from lambda_utils.validation import validate_body

logger = get_logger(__name__)

cognito = boto3.client('cognito-idp', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', 'us-east-1_cSx0RHCIR')

ROLE_HIERARCHY = {'Admin': 3, 'Operator': 2, 'Viewer': 1}


def handler(event, context):
    """Validate auth token and return user info with role."""
    request_id = context.aws_request_id if context else 'local'
    origin = event.get('headers', {}).get('origin', '')

    # Handle OPTIONS
    if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return options_response(origin)

    try:
        # Extract token from Authorization header
        headers = event.get('headers', {})
        auth_header = headers.get('authorization', headers.get('Authorization', ''))
        token = auth_header.replace('Bearer ', '') if auth_header else ''

        if not token:
            return cors_response(401, {'error': 'No authorization token provided'}, origin)

        # Validate token with Cognito
        try:
            user_info = cognito.get_user(AccessToken=token)
        except cognito.exceptions.NotAuthorizedException:
            return cors_response(401, {'error': 'Invalid or expired token'}, origin)
        except Exception as e:
            log_event(logger, 'token_validation_error', level='error', request_id=request_id, error=str(e))
            return cors_response(401, {'error': 'Token validation failed'}, origin)

        username = user_info.get('Username', '')
        attributes = {attr['Name']: attr['Value'] for attr in user_info.get('UserAttributes', [])}
        email = attributes.get('email', '')

        # Get user groups (roles)
        try:
            groups_response = cognito.admin_list_groups_for_user(
                Username=username,
                UserPoolId=USER_POOL_ID
            )
            groups = [g['GroupName'] for g in groups_response.get('Groups', [])]
        except Exception as e:
            log_event(logger, 'groups_fetch_error', level='warning', request_id=request_id, username=username, error=str(e))
            groups = []

        # Determine highest role
        role = 'Viewer'
        for group in groups:
            if ROLE_HIERARCHY.get(group, 0) > ROLE_HIERARCHY.get(role, 0):
                role = group

        # Check required role if specified
        body = validate_body(event)
        required_role = body.get('requiredRole') or (event.get('queryStringParameters') or {}).get('requiredRole')

        if required_role and ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(required_role, 0):
            log_event(logger, 'insufficient_permissions', request_id=request_id, username=username, required=required_role, current=role)
            return cors_response(403, {
                'error': 'Insufficient permissions',
                'requiredRole': required_role,
                'currentRole': role
            }, origin)

        log_event(logger, 'auth_success', request_id=request_id, username=username, role=role)
        return cors_response(200, {
            'authenticated': True,
            'username': username,
            'email': email,
            'role': role,
            'groups': groups,
            'attributes': attributes
        }, origin)

    except Exception as e:
        log_event(logger, 'auth_error', level='error', request_id=request_id, error=str(e))
        return cors_response(500, {'error': 'Internal auth error'}, origin)
