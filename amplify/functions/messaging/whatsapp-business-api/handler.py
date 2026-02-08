"""
WhatsApp Business API Lambda
Handles: Business Profile, Flows, Webhooks, Groups
Uses Meta Graph API directly (not AWS EUM)
"""
import os
import json
import logging
import boto3
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')
META_TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
GRAPH_BASE = f'https://graph.facebook.com/{META_API_VERSION}'

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}

_token_cache = {}

def _get_meta_token() -> str:
    if 'token' in _token_cache:
        return _token_cache['token']
    resp = secrets_client.get_secret_value(SecretId=META_TOKEN_SECRET)
    secret = json.loads(resp['SecretString'])
    token = secret.get('access_token') or secret.get('token') or resp['SecretString']
    if isinstance(token, str) and token.startswith('{'):
        token = json.loads(token).get('access_token', token)
    _token_cache['token'] = token.strip()
    return _token_cache['token']

def _graph_api(endpoint: str, method: str = 'GET', payload: Dict = None, params: Dict = None) -> Dict:
    """Make a Meta Graph API call."""
    token = _get_meta_token()
    url = f'{GRAPH_BASE}/{endpoint}'
    if params:
        url += '?' + urllib.parse.urlencode(params)
    
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    data = json.dumps(payload).encode('utf-8') if payload else None
    
    if method == 'GET' and data is None:
        # GET requests shouldn't have body
        req = urllib.request.Request(url, headers=headers, method=method)
    elif method == 'DELETE':
        req = urllib.request.Request(url, headers=headers, method='DELETE')
    else:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        logger.error(f'Graph API error {e.code}: {error_body}')
        try:
            return {'error': json.loads(error_body)}
        except:
            return {'error': {'message': error_body, 'code': e.code}}

def _response(status_code: int, body: Dict) -> Dict:
    return {'statusCode': status_code, 'headers': CORS_HEADERS, 'body': json.dumps(body, default=str)}

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = context.aws_request_id if context else 'local'
    rc = event.get('requestContext', {})
    http = rc.get('http', {})
    method = http.get('method', event.get('httpMethod', 'GET'))
    path = http.get('path', '') or event.get('rawPath', '') or event.get('path', '')
    params = event.get('queryStringParameters') or {}
    
    if method == 'OPTIONS':
        return _response(200, {})
    
    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
    except:
        body = {}
    
    logger.info(f'[{request_id}] {method} {path}')
    
    try:
        # Business Profile endpoints
        if '/business-profile' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _response(400, {'error': 'phoneId required'})
            if method == 'GET':
                return _get_business_profile(phone_id)
            elif method in ('POST', 'PUT'):
                return _update_business_profile(phone_id, body)
        
        # Flows endpoints
        elif '/flows' in path:
            waba_id = params.get('wabaId') or body.get('wabaId')
            if not waba_id:
                return _response(400, {'error': 'wabaId required'})
            
            flow_id = params.get('flowId') or body.get('flowId')
            
            if method == 'GET':
                if flow_id:
                    return _get_flow(flow_id)
                return _list_flows(waba_id)
            elif method == 'POST':
                if '/flows/publish' in path:
                    return _publish_flow(flow_id)
                elif '/flows/deprecate' in path:
                    return _deprecate_flow(flow_id)
                elif '/flows/preview' in path:
                    return _get_flow_preview(flow_id)
                return _create_flow(waba_id, body)
            elif method == 'PUT':
                return _update_flow(flow_id, body)
            elif method == 'DELETE':
                return _delete_flow(flow_id)
        
        # Webhook endpoints
        elif '/webhooks' in path:
            waba_id = params.get('wabaId') or body.get('wabaId')
            if not waba_id:
                return _response(400, {'error': 'wabaId required'})
            if method == 'GET':
                return _get_webhook_subscriptions(waba_id)
            elif method == 'POST':
                return _subscribe_webhook(waba_id, body)
            elif method == 'DELETE':
                return _unsubscribe_webhook(waba_id, body)
        
        # Groups endpoints
        elif '/groups' in path:
            waba_id = params.get('wabaId') or body.get('wabaId')
            phone_id = params.get('phoneId') or body.get('phoneId')
            group_id = params.get('groupId') or body.get('groupId')
            
            if method == 'GET':
                if group_id:
                    return _get_group(group_id)
                return _list_groups(waba_id)
            elif method == 'POST':
                if '/groups/participants' in path:
                    return _manage_group_participants(group_id, body)
                elif '/groups/send' in path:
                    return _send_group_message(phone_id, group_id, body)
                return _create_group(phone_id, body)
            elif method == 'PUT':
                return _update_group(group_id, body)
            elif method == 'DELETE':
                return _delete_group(group_id)
        
        # Phone settings (calling config)
        elif '/phone-settings' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _response(400, {'error': 'phoneId required'})
            if method == 'GET':
                return _get_phone_settings(phone_id)
            elif method == 'POST':
                return _update_phone_settings(phone_id, body)
        
        return _response(404, {'error': f'Unknown path: {path}'})
    except Exception as e:
        logger.exception(f'[{request_id}] Error')
        return _response(500, {'error': str(e)})
