"""
Auth Middleware Lambda Function
Purpose: Validate Cognito JWT tokens and check user roles/permissions
Used as a Lambda authorizer or direct auth check endpoint
"""
import os
import json
import logging
import boto3
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

cognito = boto3.client('cognito-idp', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', 'us-east-1_cSx0RHCIR')

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}

ROLE_HIERARCHY = {'Admin': 3, 'Operator': 2, 'Viewer': 1}

def handler(event, context):
    """Validate auth token and return user info with role."""
    request_id = context.aws_request_id if context else 'local'

    # Handle OPTIONS
    if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return _response(200, {})

    try:
        # Extract token from Authorization header
        headers = event.get('headers', {})
        auth_header = headers.get('authorization', headers.get('Authorization', ''))
        token = auth_header.replace('Bearer ', '') if auth_header else ''

        if not token:
            return _response(401, {'error': 'No authorization token provided'})

        # Validate token with Cognito
        try:
            user_info = cognito.get_user(AccessToken=token)
        except cognito.exceptions.NotAuthorizedException:
            return _response(401, {'error': 'Invalid or expired token'})
        except Exception as e:
            logger.error(f'[{request_id}] Token validation error: {e}')
            return _response(401, {'error': 'Token validation failed'})

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
            logger.warning(f'[{request_id}] Could not fetch groups for {username}: {e}')
            groups = []

        # Determine highest role
        role = 'Viewer'
        for group in groups:
            if ROLE_HIERARCHY.get(group, 0) > ROLE_HIERARCHY.get(role, 0):
                role = group

        # Check required role if specified
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        required_role = body.get('requiredRole') or event.get('queryStringParameters', {}).get('requiredRole')

        if required_role and ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(required_role, 0):
            return _response(403, {
                'error': 'Insufficient permissions',
                'requiredRole': required_role,
                'currentRole': role
            })

        return _response(200, {
            'authenticated': True,
            'username': username,
            'email': email,
            'role': role,
            'groups': groups,
            'attributes': attributes
        })

    except Exception as e:
        logger.error(f'[{request_id}] Auth error: {e}')
        return _response(500, {'error': 'Internal auth error'})


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    return {'statusCode': status_code, 'headers': CORS_HEADERS, 'body': json.dumps(body, default=str)}
