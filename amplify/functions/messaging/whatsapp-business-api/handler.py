"""
WhatsApp Business API Lambda
Handles: Business Profile, Flows, Webhooks, Groups
Uses Meta Graph API directly (not AWS EUM)

Routes:
  GET/POST  /wa-business/profile       → Business profile (read/update)
  GET       /wa-business/flows         → List flows
  POST      /wa-business/flows         → Create flow
  GET       /wa-business/flows?flowId= → Get flow details
  PUT       /wa-business/flows         → Update flow
  DELETE    /wa-business/flows         → Delete flow
  POST      /wa-business/flows/publish → Publish flow
  POST      /wa-business/flows/deprecate → Deprecate flow
  POST      /wa-business/flows/preview → Get flow preview URL
  GET       /wa-business/webhooks      → Get webhook subscriptions
  POST      /wa-business/webhooks      → Subscribe to webhook fields
  DELETE    /wa-business/webhooks      → Unsubscribe webhook fields
  GET       /wa-business/groups        → List groups
  POST      /wa-business/groups        → Create group
  GET       /wa-business/groups?groupId= → Get group details
  PUT       /wa-business/groups        → Update group
  DELETE    /wa-business/groups        → Delete group
  POST      /wa-business/groups/participants → Add/remove participants
  POST      /wa-business/groups/send   → Send group message
"""
import os
import json
import logging
import boto3
import urllib.request
import urllib.parse
from typing import Dict, Any

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

WABA1_ID = '1728153881476046'
WABA2_ID = '761651636983279'
PHONE1_META_ID = '1065003613352032'
PHONE2_META_ID = '1065809899939064'

# All IDs that belong to WABA2
WABA2_IDS = {WABA2_ID, PHONE2_META_ID}

def _get_meta_token(waba_id: str = None, phone_id: str = None) -> str:
    """Get the correct token based on WABA or phone ID."""
    use_waba2 = (waba_id in WABA2_IDS) or (phone_id in WABA2_IDS)
    
    cache_key = 'token2' if use_waba2 else 'token1'
    if cache_key in _token_cache:
        return _token_cache[cache_key]
    
    # Load both tokens from secret
    if 'loaded' not in _token_cache:
        resp = secrets_client.get_secret_value(SecretId=META_TOKEN_SECRET)
        raw = resp['SecretString']
        try:
            secret = json.loads(raw)
            _token_cache['token1'] = (secret.get('access_token') or '').strip()
            _token_cache['token2'] = (secret.get('access_token_waba2') or secret.get('access_token') or '').strip()
        except json.JSONDecodeError:
            import re
            m = re.search(r'access_token\s*:\s*([^,}]+)', raw)
            token = m.group(1).strip() if m else raw.strip()
            _token_cache['token1'] = token
            _token_cache['token2'] = token
        _token_cache['loaded'] = True
    
    return _token_cache.get(cache_key, _token_cache.get('token1', ''))


def _graph_api(endpoint: str, method: str = 'GET', payload: Dict = None, params: Dict = None, waba_id: str = None, phone_id: str = None) -> Dict:
    token = _get_meta_token(waba_id=waba_id, phone_id=phone_id)
    url = f'{GRAPH_BASE}/{endpoint}'
    if params:
        qs = {k: v for k, v in params.items() if v is not None}
        if qs:
            url += '?' + urllib.parse.urlencode(qs)
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    data = json.dumps(payload).encode('utf-8') if payload else None
    if method == 'GET':
        req = urllib.request.Request(url, headers=headers, method='GET')
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

def _resp(code: int, body: Dict) -> Dict:
    return {'statusCode': code, 'headers': CORS_HEADERS, 'body': json.dumps(body, default=str)}

# ============================================================================
# BUSINESS PROFILE
# ============================================================================
def _get_business_profile(phone_id: str) -> Dict:
    fields = 'about,address,description,email,profile_picture_url,websites,vertical'
    result = _graph_api(f'{phone_id}/whatsapp_business_profile', params={'fields': fields}, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    data = result.get('data', [{}])
    profile = data[0] if data else {}
    return _resp(200, {'profile': profile})

def _update_business_profile(phone_id: str, body: Dict) -> Dict:
    allowed = ['about', 'address', 'description', 'email', 'websites', 'vertical', 'profile_picture_url']
    payload = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not payload:
        return _resp(400, {'error': 'No valid fields to update'})
    payload['messaging_product'] = 'whatsapp'
    result = _graph_api(f'{phone_id}/whatsapp_business_profile', method='POST', payload=payload, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'updated': list(payload.keys())})

# ============================================================================
# FLOWS
# ============================================================================
def _list_flows(waba_id: str) -> Dict:
    result = _graph_api(f'{waba_id}/flows', waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'flows': result.get('data', [])})

def _get_flow(flow_id: str) -> Dict:
    if not flow_id:
        return _resp(400, {'error': 'flowId required'})
    result = _graph_api(flow_id, params={'fields': 'id,name,status,categories,validation_errors,json_version,data_api_version,endpoint_uri,preview'})
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'flow': result})

def _create_flow(waba_id: str, body: Dict) -> Dict:
    name = body.get('name')
    if not name:
        return _resp(400, {'error': 'name required'})
    payload = {'name': name}
    if body.get('categories'):
        payload['categories'] = body['categories']
    if body.get('clone_flow_id'):
        payload['clone_flow_id'] = body['clone_flow_id']
    result = _graph_api(f'{waba_id}/flows', method='POST', payload=payload, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'flow': result})

def _update_flow(flow_id: str, body: Dict) -> Dict:
    if not flow_id:
        return _resp(400, {'error': 'flowId required'})
    payload = {}
    if body.get('name'):
        payload['name'] = body['name']
    if body.get('categories'):
        payload['categories'] = body['categories']
    if body.get('endpoint_uri'):
        payload['endpoint_uri'] = body['endpoint_uri']
    if body.get('json'):
        payload['json'] = body['json']
    result = _graph_api(flow_id, method='POST', payload=payload)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

def _delete_flow(flow_id: str) -> Dict:
    if not flow_id:
        return _resp(400, {'error': 'flowId required'})
    result = _graph_api(flow_id, method='DELETE')
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

def _publish_flow(flow_id: str) -> Dict:
    if not flow_id:
        return _resp(400, {'error': 'flowId required'})
    result = _graph_api(f'{flow_id}/publish', method='POST')
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

def _deprecate_flow(flow_id: str) -> Dict:
    if not flow_id:
        return _resp(400, {'error': 'flowId required'})
    result = _graph_api(flow_id, method='POST', payload={'status': 'DEPRECATED'})
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

def _get_flow_preview(flow_id: str) -> Dict:
    if not flow_id:
        return _resp(400, {'error': 'flowId required'})
    result = _graph_api(flow_id, params={'fields': 'preview.invalidate(false)'})
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'preview': result.get('preview', {})})


# ============================================================================
# WEBHOOKS
# ============================================================================
def _get_webhook_subscriptions(waba_id: str) -> Dict:
    result = _graph_api(f'{waba_id}/subscribed_apps', waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'subscriptions': result.get('data', [])})

def _subscribe_webhook(waba_id: str, body: Dict) -> Dict:
    result = _graph_api(f'{waba_id}/subscribed_apps', method='POST', waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'result': result})

def _unsubscribe_webhook(waba_id: str, body: Dict) -> Dict:
    result = _graph_api(f'{waba_id}/subscribed_apps', method='DELETE', waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

# ============================================================================
# GROUPS
# ============================================================================
def _list_groups(waba_id: str) -> Dict:
    result = _graph_api(f'{waba_id}/groups', waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'groups': result.get('data', [])})

def _get_group(group_id: str) -> Dict:
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    result = _graph_api(group_id, params={'fields': 'id,subject,description,owner,creation_timestamp,participants'})
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'group': result})

def _create_group(phone_id: str, body: Dict) -> Dict:
    if not phone_id:
        return _resp(400, {'error': 'phoneId required'})
    subject = body.get('subject')
    if not subject:
        return _resp(400, {'error': 'subject required'})
    payload = {'subject': subject, 'messaging_product': 'whatsapp'}
    if body.get('description'):
        payload['description'] = body['description']
    if body.get('participants'):
        payload['participants'] = body['participants']
    result = _graph_api(f'{phone_id}/groups', method='POST', payload=payload, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'group': result})

def _update_group(group_id: str, body: Dict) -> Dict:
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    payload = {}
    if body.get('subject'):
        payload['subject'] = body['subject']
    if body.get('description'):
        payload['description'] = body['description']
    result = _graph_api(group_id, method='POST', payload=payload)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

def _delete_group(group_id: str) -> Dict:
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    result = _graph_api(group_id, method='DELETE')
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

def _manage_group_participants(group_id: str, body: Dict) -> Dict:
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    action = body.get('action', 'add')  # add or remove
    participants = body.get('participants', [])
    if not participants:
        return _resp(400, {'error': 'participants required'})
    payload = {'messaging_product': 'whatsapp', 'participants': participants}
    endpoint = f'{group_id}/participants'
    method = 'POST' if action == 'add' else 'DELETE'
    result = _graph_api(endpoint, method=method, payload=payload)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'action': action, 'count': len(participants)})

def _send_group_message(phone_id: str, group_id: str, body: Dict) -> Dict:
    if not phone_id or not group_id:
        return _resp(400, {'error': 'phoneId and groupId required'})
    content = body.get('content', '')
    if not content:
        return _resp(400, {'error': 'content required'})
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'group',
        'to': group_id,
        'type': 'text',
        'text': {'body': content}
    }
    result = _graph_api(f'{phone_id}/messages', method='POST', payload=payload, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'messageId': result.get('messages', [{}])[0].get('id')})

# ============================================================================
# PHONE SETTINGS
# ============================================================================
def _get_phone_settings(phone_id: str) -> Dict:
    result = _graph_api(phone_id, params={'fields': 'display_phone_number,verified_name,quality_rating,messaging_limit_tier,is_official_business_account,name_status'}, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'settings': result})

def _update_phone_settings(phone_id: str, body: Dict) -> Dict:
    payload = {}
    if 'calling' in body:
        payload['calling'] = body['calling']
    if not payload:
        return _resp(400, {'error': 'No settings to update'})
    result = _graph_api(f'{phone_id}/settings', method='POST', payload=payload, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

# ============================================================================
# HANDLER
# ============================================================================
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = context.aws_request_id if context else 'local'
    rc = event.get('requestContext', {})
    http = rc.get('http', {})
    method = http.get('method', event.get('httpMethod', 'GET'))
    path = http.get('path', '') or event.get('rawPath', '') or event.get('path', '')
    params = event.get('queryStringParameters') or {}

    if method == 'OPTIONS':
        return _resp(200, {})

    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
    except:
        body = {}

    logger.info(f'[{request_id}] {method} {path}')

    try:
        if '/profile' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
            if method == 'GET':
                return _get_business_profile(phone_id)
            return _update_business_profile(phone_id, body)

        elif '/flows/publish' in path:
            return _publish_flow(params.get('flowId') or body.get('flowId'))
        elif '/flows/deprecate' in path:
            return _deprecate_flow(params.get('flowId') or body.get('flowId'))
        elif '/flows/preview' in path:
            return _get_flow_preview(params.get('flowId') or body.get('flowId'))
        elif '/flows' in path:
            waba_id = params.get('wabaId') or body.get('wabaId')
            flow_id = params.get('flowId') or body.get('flowId')
            if method == 'GET':
                return _get_flow(flow_id) if flow_id else _list_flows(waba_id or '')
            elif method == 'POST':
                return _create_flow(waba_id or '', body)
            elif method == 'PUT':
                return _update_flow(flow_id or '', body)
            elif method == 'DELETE':
                return _delete_flow(flow_id or '')

        elif '/webhooks' in path:
            waba_id = params.get('wabaId') or body.get('wabaId')
            if not waba_id:
                return _resp(400, {'error': 'wabaId required'})
            if method == 'GET':
                return _get_webhook_subscriptions(waba_id)
            elif method == 'POST':
                return _subscribe_webhook(waba_id, body)
            elif method == 'DELETE':
                return _unsubscribe_webhook(waba_id, body)

        elif '/groups/participants' in path:
            return _manage_group_participants(params.get('groupId') or body.get('groupId') or '', body)
        elif '/groups/send' in path:
            return _send_group_message(
                params.get('phoneId') or body.get('phoneId') or '',
                params.get('groupId') or body.get('groupId') or '', body)
        elif '/groups' in path:
            waba_id = params.get('wabaId') or body.get('wabaId') or ''
            group_id = params.get('groupId') or body.get('groupId')
            phone_id = params.get('phoneId') or body.get('phoneId')
            if method == 'GET':
                return _get_group(group_id) if group_id else _list_groups(waba_id)
            elif method == 'POST':
                return _create_group(phone_id or '', body)
            elif method == 'PUT':
                return _update_group(group_id or '', body)
            elif method == 'DELETE':
                return _delete_group(group_id or '')

        elif '/phone-settings' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
            if method == 'GET':
                return _get_phone_settings(phone_id)
            return _update_phone_settings(phone_id, body)

        return _resp(404, {'error': f'Unknown path: {path}'})
    except Exception as e:
        logger.exception(f'[{request_id}] Error')
        return _resp(500, {'error': str(e)})
