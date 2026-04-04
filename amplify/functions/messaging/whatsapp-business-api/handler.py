"""
WhatsApp Business API Lambda
Handles: Business Profile, Flows, Webhooks, Groups, Payment Config
Uses Meta Graph API directly

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
  POST      /wa-business/groups/participants → Remove participants
  POST      /wa-business/groups/send   → Send group message
  GET       /wa-business/groups/invite-link → Get invite link
  POST      /wa-business/groups/invite-link → Reset invite link
  GET       /wa-business/groups/join-requests → List pending join requests
  POST      /wa-business/groups/join-requests → Approve join requests
  DELETE    /wa-business/groups/join-requests → Reject join requests
  GET       /wa-business/payment-config → Get payment configuration for phone
  GET       /wa-business/payment-config/check → Check payment gateway status via Meta API
  GET       /wa-business/payment-lookup → Meta Payment Lookup API (verify payment status)
  POST      /wa-business/payment-refund → Meta Refund API (initiate refund via WhatsApp)
  POST      /wa-business/flow-data     → WhatsApp Flow data_exchange endpoint
  POST      /wa-business/checkout-data → Checkout Button Template data_exchange (coupons + address)
"""
import os
import json
import logging
import hmac
import hashlib
import time
import uuid
import boto3
import urllib.request
import urllib.parse
from decimal import Decimal
from typing import Dict, Any

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

logger = get_logger(__name__)

secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

META_API_VERSION = os.environ.get('META_API_VERSION', 'v25.0')
META_TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
GRAPH_BASE = f'https://graph.facebook.com/{META_API_VERSION}'

# CORS headers provided by lambda_utils.response.cors_headers(origin)

_token_cache = {}

WABA1_ID = os.environ.get('WABA1_ID', '2094615664435155')  # WECARE.DIGITAL (Direct API)
WABA2_ID = os.environ.get('WABA2_ID', '2513394156072604')  # Manish Agarwal (Direct API)
PHONE1_META_ID = os.environ.get('PHONE1_META_ID', '1016149501586345')  # +919330994400 (Direct API)
PHONE2_META_ID = os.environ.get('PHONE2_META_ID', '1055232054343117')  # +919903300044 (Direct API)

# All IDs that belong to WABA2 — now uses WECARE.DIGITAL app (token1), no separate token needed
WABA2_IDS = set()

# DynamoDB tables for order lookups (flow-data endpoint)
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
ORDER_IDS_TABLE = os.environ.get('WIX_ORDER_IDS_TABLE', 'stack-wecare-digital-WixOrderIds')

# Lambda client for invoking outbound WhatsApp (payment after flow)
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
OUTBOUND_WHATSAPP_FUNCTION = os.environ.get('OUTBOUND_WHATSAPP_FUNCTION', 'wecare-outbound-whatsapp')
INVOICE_ENGINE_FUNCTION = os.environ.get('INVOICE_ENGINE_FUNCTION', 'wecare-invoice-engine')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
SUBMIT_REQUESTS_TABLE = os.environ.get('SUBMIT_REQUESTS_TABLE', 'stack-wecare-digital-SubmitRequestsTable')

# Flow management tables
FLOW_REGISTRY_TABLE = os.environ.get('FLOW_REGISTRY_TABLE', 'stack-wecare-digital-FlowRegistryTable')
FLOW_SUBMISSIONS_TABLE = os.environ.get('FLOW_SUBMISSIONS_TABLE', 'stack-wecare-digital-FlowSubmissionTable')
FLOW_LOGS_TABLE = os.environ.get('FLOW_LOGS_TABLE', 'stack-wecare-digital-FlowLogTable')

# Flow registry cache (in-memory, refreshed every 5 min)
_flow_registry_cache: Dict = {}
_flow_registry_cache_ts: float = 0
FLOW_REGISTRY_CACHE_TTL = 300  # 5 minutes

# Phone number IDs (for outbound Lambda)
PHONE1_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-waba1-direct-1016149501586345')


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
            _token_cache['app_secret'] = (secret.get('app_secret') or '').strip()
            _token_cache['app_secret_waba2'] = (secret.get('app_secret_waba2') or secret.get('app_secret') or '').strip()
        except json.JSONDecodeError:
            import re
            m = re.search(r'access_token\s*:\s*([^,}]+)', raw)
            token = m.group(1).strip() if m else raw.strip()
            _token_cache['token1'] = token
            _token_cache['token2'] = token
        _token_cache['loaded'] = True
    
    return _token_cache.get(cache_key, _token_cache.get('token1', ''))


def _get_app_secret(waba_id: str = None, phone_id: str = None) -> str:
    """Get the correct app secret based on WABA or phone ID."""
    use_waba2 = (waba_id in WABA2_IDS) or (phone_id in WABA2_IDS)
    cache_key = 'app_secret_waba2' if use_waba2 else 'app_secret'
    if cache_key in _token_cache:
        return _token_cache[cache_key]
    # Secrets are loaded in _get_meta_token — ensure loaded
    _get_meta_token(waba_id=waba_id, phone_id=phone_id)
    return _token_cache.get(cache_key, '')


def _graph_api(endpoint: str, method: str = 'GET', payload: Dict = None, params: Dict = None, waba_id: str = None, phone_id: str = None) -> Dict:
    token = _get_meta_token(waba_id=waba_id, phone_id=phone_id)
    app_secret = _get_app_secret(waba_id=waba_id, phone_id=phone_id)
    url = f'{GRAPH_BASE}/{endpoint}'
    # Compute appsecret_proof
    proof_params = {}
    if app_secret:
        proof = hmac.new(app_secret.encode('utf-8'), token.encode('utf-8'), hashlib.sha256).hexdigest()
        proof_params['appsecret_proof'] = proof
    if params:
        qs = {k: v for k, v in params.items() if v is not None}
        qs.update(proof_params)
        if qs:
            url += '?' + urllib.parse.urlencode(qs)
    elif proof_params:
        url += '?' + urllib.parse.urlencode(proof_params)
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
        except (json.JSONDecodeError, TypeError, ValueError):
            return {'error': {'message': error_body, 'code': e.code}}

def _resp(code: int, body: Dict, resp_origin: str = '') -> Dict:
    return {'statusCode': code, 'headers': cors_headers(resp_origin or origin), 'body': json.dumps(body, default=str)}

# ============================================================================
# BUSINESS PROFILE
# ============================================================================
def _get_business_profile(phone_id: str) -> Dict:
    fields = 'about,address,description,email,profile_picture_url,websites,vertical'
    result = _graph_api(f'{phone_id}/whatsapp_business_profile', params={'fields': fields}, phone_id=phone_id)
    if 'error' in result:
        # Retry once — Meta Graph API can be flaky
        logger.warning(f'Profile fetch failed for {phone_id}, retrying: {result}')
        time.sleep(1)
        result = _graph_api(f'{phone_id}/whatsapp_business_profile', params={'fields': fields}, phone_id=phone_id)
        if 'error' in result:
            logger.error(f'Profile fetch failed after retry for {phone_id}: {result}')
            # Return 200 with error info so frontend can display the error message
            error_msg = result.get('error', {})
            if isinstance(error_msg, dict):
                error_msg = error_msg.get('message', str(error_msg))
            return _resp(200, {'profile': None, 'error': str(error_msg), 'phoneId': phone_id})
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
    if not waba_id:
        return _resp(400, {'error': 'wabaId required'})
    result = _graph_api(f'{waba_id}/flows', params={'fields': 'id,name,status,categories,validation_errors'}, waba_id=waba_id)
    if 'error' in result:
        logger.error(f'List flows error for WABA {waba_id}: {result}')
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
    payload = {}
    if body.get('override_callback_uri'):
        payload['override_callback_uri'] = body['override_callback_uri']
    if body.get('verify_token'):
        payload['verify_token'] = body['verify_token']
    if body.get('subscribed_fields'):
        fields = body['subscribed_fields']
        # Meta expects subscribed_fields as comma-separated string
        if isinstance(fields, list):
            payload['subscribed_fields'] = ','.join(fields)
        else:
            payload['subscribed_fields'] = fields
    result = _graph_api(f'{waba_id}/subscribed_apps', method='POST', payload=payload or None, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'result': result})

def _unsubscribe_webhook(waba_id: str, body: Dict) -> Dict:
    result = _graph_api(f'{waba_id}/subscribed_apps', method='DELETE', waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

# ============================================================================
# ASSIGNED USERS
# ============================================================================
def _list_assigned_users(waba_id: str, params: Dict) -> Dict:
    """GET /{WABA-ID}/assigned_users — list users assigned to WABA."""
    business_id = params.get('business')
    if not business_id:
        return _resp(400, {'error': 'business parameter required'})
    query = {'business': business_id}
    if params.get('fields'):
        query['fields'] = params['fields']
    if params.get('limit'):
        query['limit'] = params['limit']
    if params.get('after'):
        query['after'] = params['after']
    if params.get('before'):
        query['before'] = params['before']
    result = _graph_api(f'{waba_id}/assigned_users', params=query, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {
        'users': result.get('data', []),
        'paging': result.get('paging', {}),
        'summary': result.get('summary', {}),
    })

def _add_assigned_user(waba_id: str, body: Dict) -> Dict:
    """POST /{WABA-ID}/assigned_users — add user with permission tasks."""
    user_id = body.get('user')
    tasks = body.get('tasks', [])
    if not user_id:
        return _resp(400, {'error': 'user (user ID) required'})
    if not tasks:
        return _resp(400, {'error': 'tasks array required'})
    result = _graph_api(
        f'{waba_id}/assigned_users', method='POST',
        payload={'user': user_id, 'tasks': tasks}, waba_id=waba_id,
    )
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

def _remove_assigned_user(waba_id: str, body: Dict) -> Dict:
    """DELETE /{WABA-ID}/assigned_users — revoke user access."""
    user_id = body.get('user')
    if not user_id:
        return _resp(400, {'error': 'user (user ID) required'})
    result = _graph_api(
        f'{waba_id}/assigned_users', method='DELETE',
        payload={'user': user_id}, waba_id=waba_id,
    )
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True})

# ============================================================================
# BOT DETAILS
# ============================================================================
def _get_bot_details(bot_id: str, params: Dict) -> Dict:
    """GET /{WABA-Bot-ID} — retrieve bot prompts, commands, welcome message config."""
    if not bot_id:
        return _resp(400, {'error': 'botId required'})
    fields = params.get('fields', 'id,prompts,commands,enable_welcome_message')
    result = _graph_api(bot_id, params={'fields': fields})
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'bot': result})

# ============================================================================
# GROUPS
# ============================================================================
def _list_groups(waba_id: str, phone_id: str = None) -> Dict:
    """List groups. Uses phone_id if provided, falls back to WABA phone mapping."""
    # Groups API uses phone_number_id, not waba_id
    if not phone_id:
        # Map WABA to its primary phone
        waba_phone_map = {
            WABA1_ID: PHONE1_META_ID,
            WABA2_ID: PHONE2_META_ID,
        }
        phone_id = waba_phone_map.get(waba_id, '')
    if not phone_id:
        return _resp(400, {'error': 'Could not resolve phone for WABA'})
    result = _graph_api(f'{phone_id}/groups', phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'groups': result.get('data', [])})

def _get_group(group_id: str) -> Dict:
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    result = _graph_api(group_id, params={
        'fields': 'id,subject,description,creation_timestamp,participants,total_participant_count,join_approval_mode,suspended,messaging_permission,member_visibility'
    })
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
    if body.get('join_approval_mode'):
        payload['join_approval_mode'] = body['join_approval_mode']
    result = _graph_api(f'{phone_id}/groups', method='POST', payload=payload, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'group': result})

def _update_group(group_id: str, body: Dict) -> Dict:
    """Update group settings: subject, description, join_approval_mode, messaging_permission, member_visibility."""
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    payload = {'messaging_product': 'whatsapp'}
    if body.get('subject'):
        payload['subject'] = body['subject']
    if body.get('description'):
        payload['description'] = body['description']
    # Privacy: who can send messages — 'all' (everyone) or 'admins' (admin-only)
    if body.get('messaging_permission'):
        payload['messaging_permission'] = body['messaging_permission']
    # Privacy: whether non-admin members can see other participants
    if body.get('member_visibility'):
        payload['member_visibility'] = body['member_visibility']
    # Join approval mode
    if body.get('join_approval_mode'):
        payload['join_approval_mode'] = body['join_approval_mode']
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
    """Send message to a group. Supports text, image, video, document, audio, template.
    Body: { content: str (for text), type: 'text'|'image'|'video'|'document'|'audio'|'template',
            mediaUrl/mediaId: str, caption: str, templateName: str, templateLanguage: str, templateComponents: [] }
    """
    if not phone_id or not group_id:
        return _resp(400, {'error': 'phoneId and groupId required'})

    msg_type = body.get('type', 'text')
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'group',
        'to': group_id,
        'type': msg_type,
    }

    if msg_type == 'text':
        content = body.get('content', '')
        if not content:
            return _resp(400, {'error': 'content required for text messages'})
        payload['text'] = {'body': content, 'preview_url': body.get('preview_url', True)}

    elif msg_type in ('image', 'video', 'document', 'audio'):
        media_obj = {}
        if body.get('mediaId'):
            media_obj['id'] = body['mediaId']
        elif body.get('mediaUrl'):
            media_obj['link'] = body['mediaUrl']
        else:
            return _resp(400, {'error': f'mediaId or mediaUrl required for {msg_type}'})
        if body.get('caption') and msg_type in ('image', 'video', 'document'):
            media_obj['caption'] = body['caption']
        if body.get('filename') and msg_type == 'document':
            media_obj['filename'] = body['filename']
        payload[msg_type] = media_obj

    elif msg_type == 'template':
        template_name = body.get('templateName', '')
        template_lang = body.get('templateLanguage', 'en')
        if not template_name:
            return _resp(400, {'error': 'templateName required for template messages'})
        template_obj = {'name': template_name, 'language': {'code': template_lang}}
        if body.get('templateComponents'):
            template_obj['components'] = body['templateComponents']
        payload['template'] = template_obj

    else:
        return _resp(400, {'error': f'Unsupported message type: {msg_type}. Use text, image, video, document, audio, or template.'})

    result = _graph_api(f'{phone_id}/messages', method='POST', payload=payload, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    msg_id = ''
    msgs = result.get('messages', [])
    if msgs:
        msg_id = msgs[0].get('id', '')
    return _resp(200, {'success': True, 'messageId': msg_id, 'type': msg_type})

def _set_group_image(group_id: str, image_url: str) -> Dict:
    """Set group profile picture from a URL. Downloads the image then uploads via multipart form."""
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    if not image_url:
        return _resp(400, {'error': 'imageUrl required'})
    # Download image
    try:
        img_req = urllib.request.Request(image_url)
        with urllib.request.urlopen(img_req, timeout=10) as img_resp:
            image_bytes = img_resp.read()
    except Exception as e:
        return _resp(400, {'error': f'Failed to download image: {str(e)}'})
    # Determine content type
    ct = 'image/png' if image_url.lower().endswith('.png') else 'image/jpeg'
    ext = 'png' if 'png' in ct else 'jpg'
    # Upload via multipart
    token = _get_meta_token()
    app_secret = _get_app_secret()
    proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest() if app_secret else ''
    url = f'{GRAPH_BASE}/{group_id}?appsecret_proof={proof}'
    boundary = '----WecareGroupImage'
    body = b''
    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="messaging_product"\r\n\r\n'
    body += b'whatsapp\r\n'
    body += f'--{boundary}\r\n'.encode()
    body += f'Content-Disposition: form-data; name="file"; filename="group.{ext}"\r\n'.encode()
    body += f'Content-Type: {ct}\r\n\r\n'.encode()
    body += image_bytes
    body += b'\r\n'
    body += f'--{boundary}--\r\n'.encode()
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        return _resp(200, {'success': True, 'result': result})
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else str(e)
        logger.error(f'Group image upload error: {err}')
        try:
            return _resp(400, json.loads(err))
        except:
            return _resp(400, {'error': err})

def _get_group_invite_link(group_id: str) -> Dict:
    """Get the current invite link for a group."""
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    result = _graph_api(f'{group_id}/invite_link')
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'invite_link': result.get('invite_link', '')})

def _reset_group_invite_link(group_id: str) -> Dict:
    """Reset (regenerate) the invite link for a group. Previous links become invalid."""
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    result = _graph_api(f'{group_id}/invite_link', method='POST', payload={'messaging_product': 'whatsapp'})
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'invite_link': result.get('invite_link', '')})

def _get_group_join_requests(group_id: str) -> Dict:
    """Get pending join requests for a group (when join_approval_mode=approval_required)."""
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    result = _graph_api(f'{group_id}/join_requests')
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'join_requests': result.get('data', [])})

def _approve_group_join_requests(group_id: str, body: Dict) -> Dict:
    """Approve pending join requests."""
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    join_requests = body.get('join_requests', [])
    if not join_requests:
        return _resp(400, {'error': 'join_requests (array of IDs) required'})
    payload = {'messaging_product': 'whatsapp', 'join_requests': join_requests}
    result = _graph_api(f'{group_id}/join_requests', method='POST', payload=payload)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, result)

def _reject_group_join_requests(group_id: str, body: Dict) -> Dict:
    """Reject pending join requests."""
    if not group_id:
        return _resp(400, {'error': 'groupId required'})
    join_requests = body.get('join_requests', [])
    if not join_requests:
        return _resp(400, {'error': 'join_requests (array of IDs) required'})
    payload = {'messaging_product': 'whatsapp', 'join_requests': join_requests}
    result = _graph_api(f'{group_id}/join_requests', method='DELETE', payload=payload)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, result)

# ============================================================================
# INTERACTIVE LIST MESSAGES
# ============================================================================
def _send_interactive_list(phone_id: str, body: Dict) -> Dict:
    """Send an interactive list message to a WhatsApp user."""
    to = body.get('to')
    if not to:
        return _resp(400, {'error': 'to (recipient phone number) required'})

    header_text = body.get('headerText', '')
    body_text = body.get('bodyText', '')
    footer_text = body.get('footerText', '')
    button_text = body.get('buttonText', 'Options')
    sections = body.get('sections', [])

    if not body_text:
        return _resp(400, {'error': 'bodyText required'})
    if not sections:
        return _resp(400, {'error': 'sections required (array of {title, rows})'})

    interactive = {
        'type': 'list',
        'body': {'text': body_text},
        'action': {
            'button': button_text,
            'sections': sections,
        },
    }
    if header_text:
        interactive['header'] = {'type': 'text', 'text': header_text}
    if footer_text:
        interactive['footer'] = {'text': footer_text}

    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': interactive,
    }

    result = _graph_api(f'{phone_id}/messages', method='POST', payload=payload, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    msg_id = ''
    msgs = result.get('messages', [])
    if msgs:
        msg_id = msgs[0].get('id', '')
    return _resp(200, {'success': True, 'messageId': msg_id})


# ============================================================================
# CALLING SETTINGS (Enable/Disable calling on a phone number)
# ============================================================================
def _get_calling_settings(phone_id: str) -> Dict:
    """Get current calling settings for a phone number, including SIP config and credentials."""
    # include_sip_credentials=true returns the Meta-generated SIP password
    result = _graph_api(f'{phone_id}/settings', params={
        'fields': 'calling',
        'include_sip_credentials': 'true',
    }, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'settings': result})


def _update_calling_settings(phone_id: str, body: Dict) -> Dict:
    """
    Enable or update calling settings on a phone number.
    Supports full Meta Calling API settings including SIP configuration.
    Body: {
      callIconVisibility: 'default' | 'disable_all',
      restrictToCountries: ['IN', 'AE'],
      callHours: { timezone, sun, mon, ... },
      callbackRequest: { enabled: bool, bodyText: str },
      sip: { status: 'ENABLED'|'DISABLED', servers: [{ hostname, port?, request_uri_user_params? }] },
      srtpKeyExchangeProtocol: 'DTLS' | 'SDES',
      status: 'ENABLED' | 'DISABLED',
      callbackPermissionStatus: 'ENABLED' | 'DISABLED',
    }
    """
    calling: Dict = {}

    # Basic calling settings
    visibility = body.get('callIconVisibility')
    if visibility:
        calling['call_icon_visibility'] = visibility

    status = body.get('status')
    if status:
        calling['status'] = status

    callback_perm = body.get('callbackPermissionStatus')
    if callback_perm:
        calling['callback_permission_status'] = callback_perm

    countries = body.get('restrictToCountries')
    if countries:
        calling['restrict_to_user_countries'] = countries

    call_hours = body.get('callHours')
    if call_hours:
        calling['call_hours'] = call_hours

    callback = body.get('callbackRequest')
    if callback:
        calling['callback_request'] = callback

    # SIP configuration (per Meta SIP Configuration Guide)
    sip = body.get('sip')
    if sip:
        sip_config: Dict = {}
        if 'status' in sip:
            sip_config['status'] = sip['status']  # ENABLED or DISABLED
        if 'servers' in sip:
            sip_config['servers'] = sip['servers']  # [{ hostname, port?, request_uri_user_params? }]
        if sip_config:
            calling['sip'] = sip_config

    # SRTP key exchange protocol (DTLS default, SDES for shorter call setup)
    srtp = body.get('srtpKeyExchangeProtocol')
    if srtp and srtp in ('DTLS', 'SDES'):
        calling['srtp_key_exchange_protocol'] = srtp

    if not calling:
        return _resp(400, {'error': 'No calling settings provided'})

    result = _graph_api(f'{phone_id}/settings', method='POST', payload={
        'calling': calling
    }, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'calling': calling})


# ============================================================================
# PHONE SETTINGS
# ============================================================================
def _get_phone_settings(phone_id: str) -> Dict:
    result = _graph_api(phone_id, params={'fields': 'display_phone_number,verified_name,quality_rating,messaging_limit_tier,is_official_business_account,name_status'}, phone_id=phone_id)
    if 'error' in result:
        # Retry once
        logger.warning(f'Phone settings fetch failed for {phone_id}, retrying: {result}')
        time.sleep(1)
        result = _graph_api(phone_id, params={'fields': 'display_phone_number,verified_name,quality_rating,messaging_limit_tier,is_official_business_account,name_status'}, phone_id=phone_id)
        if 'error' in result:
            logger.error(f'Phone settings fetch failed after retry for {phone_id}: {result}')
            return _resp(200, {'settings': None, 'error': str(result.get('error', '')), 'phoneId': phone_id})
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
# USERNAME MANAGEMENT
# Meta Graph API endpoints for WhatsApp Business usernames.
# GET /<phone_id>/username — current username + status
# GET /<phone_id>/username_suggestions — reserved suggestions
# POST /<phone_id>/username — claim a username
# DELETE /<phone_id>/username — delete current username
# ============================================================================

def _get_username(phone_id: str) -> Dict:
    """Get current business username for a phone number."""
    result = _graph_api(f'{phone_id}/username', phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, result)


def _get_username_suggestions(phone_id: str) -> Dict:
    """Get reserved username suggestions for a phone number."""
    result = _graph_api(f'{phone_id}/username_suggestions', phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    suggestions = []
    for item in result.get('data', []):
        suggestions.extend(item.get('username_suggestions', []))
    return _resp(200, {'suggestions': suggestions, 'raw': result})


def _claim_username(phone_id: str, body: Dict) -> Dict:
    """Claim/set a username for a phone number. Body: { "username": "desired_username" }"""
    username = body.get('username', '').strip()
    if not username:
        return _resp(400, {'error': 'username is required'})
    result = _graph_api(f'{phone_id}/username', method='POST',
                        payload={'username': username}, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'username': username, 'result': result})


def _delete_username(phone_id: str) -> Dict:
    """Delete the current username for a phone number."""
    result = _graph_api(f'{phone_id}/username', method='DELETE', phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'result': result})


# ============================================================================
# BLOCK USERS API
# Per Meta BSUID docs: block/unblock users by phone or user_id (BSUID)
# ============================================================================

def _block_users(waba_id: str, body: Dict) -> Dict:
    """Block users on a WABA. Accepts phone numbers and/or BSUIDs."""
    users = body.get('users', [])
    if not users:
        return _resp(400, {'error': 'users array required'})
    # Build payload per Meta API: POST /<WABA_ID>/block_users
    # Each user can have 'phone' and/or 'user_id' (BSUID)
    payload = {'messaging_product': 'whatsapp', 'block_users': users}
    result = _graph_api(f'{waba_id}/block_users', method='POST', payload=payload, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'result': result})


def _unblock_users(waba_id: str, body: Dict) -> Dict:
    """Unblock users on a WABA. Accepts phone numbers and/or BSUIDs."""
    users = body.get('users', [])
    if not users:
        return _resp(400, {'error': 'users array required'})
    payload = {'messaging_product': 'whatsapp', 'block_users': users}
    result = _graph_api(f'{waba_id}/unblock_users', method='POST', payload=payload, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'success': True, 'result': result})


def _get_blocked_users(waba_id: str) -> Dict:
    """Get list of blocked users for a WABA."""
    result = _graph_api(f'{waba_id}/block_users', method='GET', waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, result)


# ============================================================================
# PAYMENT CONFIGURATION
# Razorpay MID and UPI ID loaded from environment variables (not hardcoded).
# MCC: 4722 | Purpose Code: 03
# ============================================================================
_RAZORPAY_MID = os.environ.get('RAZORPAY_MID', 'acc_HDfub6wOfQybuH')
_RAZORPAY_UPI_ID = os.environ.get('RAZORPAY_UPI_ID', 'wecaredigital83.rzp@icici')
_PAYU_MID = os.environ.get('PAYU_MID', '8629516')
_PAYU_UPI_ID = os.environ.get('PAYU_UPI_ID', 'wecareqr.payu@indus')
_PAYMENT_WABA_ID = os.environ.get('PAYMENT_WABA_ID', '2094615664435155')

PAYMENT_CONFIGS = {
    PHONE1_META_ID: {
        'phone': '+91 9330994400',
        'wabaId': WABA1_ID,
        'configs': [
            {'name': 'Payu-UPIVPA', 'status': 'active', 'type': 'upi', 'gateway': 'payu', 'mid': _PAYU_MID, 'upiId': _PAYU_UPI_ID},
            {'name': 'WECARE-PAYU', 'status': 'active', 'type': 'payment_gateway', 'gateway': 'payu', 'mid': _PAYU_MID},
            {'name': 'WECARE-RAZORPAY-UPIVPA', 'status': 'active', 'type': 'upi', 'gateway': 'razorpay', 'mid': _RAZORPAY_MID, 'upiId': _RAZORPAY_UPI_ID},
            {'name': 'WECARE-RAZOR-PAY', 'status': 'active', 'type': 'payment_gateway', 'gateway': 'razorpay', 'mid': _RAZORPAY_MID, 'upiId': _RAZORPAY_UPI_ID},
        ],
        'mcc': '4722',
        'purposeCode': '03',
    },
    PHONE2_META_ID: {
        'phone': '+91 9903300044',
        'wabaId': WABA2_ID,
        'configs': [
            {'name': 'PayU_ManishAgarwal', 'status': 'active', 'type': 'payment_gateway', 'gateway': 'payu', 'mid': _PAYU_MID},
            {'name': 'PayU_UPI', 'status': 'active', 'type': 'upi', 'gateway': 'payu', 'mid': _PAYU_MID, 'upiId': _PAYU_UPI_ID},
            {'name': 'Razorpay_ManishAgarwal', 'status': 'active', 'type': 'payment_gateway', 'gateway': 'razorpay', 'mid': _RAZORPAY_MID, 'upiId': _RAZORPAY_UPI_ID},
            {'name': 'Razorpay_UPI', 'status': 'active', 'type': 'upi', 'gateway': 'razorpay', 'mid': _RAZORPAY_MID, 'upiId': _RAZORPAY_UPI_ID},
        ],
        'mcc': '4722',
        'purposeCode': '03',
    },
}

def _get_payment_config(phone_id: str) -> Dict:
    """Get payment configuration for a phone number."""
    config = PAYMENT_CONFIGS.get(phone_id)
    if config:
        return _resp(200, {'paymentConfig': config})
    # Try commerce settings from Meta Graph API
    result = _graph_api(f'{phone_id}/whatsapp_commerce_settings', phone_id=phone_id)
    if 'error' in result:
        return _resp(200, {'paymentConfig': None, 'note': 'No payment config found for this phone'})
    return _resp(200, {'paymentConfig': result})


def _check_payment_gateway(waba_id: str = None) -> Dict:
    """Check payment gateway configurations via Meta Graph API for all WABAs or a specific one."""
    results = []
    waba_ids = [waba_id] if waba_id else [WABA1_ID, WABA2_ID]
    waba_phone_map = {
        WABA1_ID: {'phone': '+91 9330994400', 'phoneId': PHONE1_META_ID},
        WABA2_ID: {'phone': '+91 9903300044', 'phoneId': PHONE2_META_ID},
    }

    for wid in waba_ids:
        phone_info = waba_phone_map.get(wid, {})
        local_config = PAYMENT_CONFIGS.get(phone_info.get('phoneId', ''), {})

        # Query Meta Graph API for payment configurations on this WABA
        api_result = _graph_api(
            f'{wid}/payment_configurations',
            params={'fields': 'configuration_name,status,payment_gateway,merchant_category_code,purpose_code'},
            waba_id=wid,
        )

        meta_configs = []
        if 'data' in api_result:
            meta_configs = api_result['data']
        elif 'error' not in api_result and isinstance(api_result, list):
            meta_configs = api_result

        # Build check result for each config
        config_checks = []
        for cfg in meta_configs:
            config_checks.append({
                'name': cfg.get('configuration_name', 'unknown'),
                'status': cfg.get('status', 'unknown'),
                'gateway': cfg.get('payment_gateway', {}).get('type', 'unknown') if isinstance(cfg.get('payment_gateway'), dict) else str(cfg.get('payment_gateway', 'unknown')),
                'mid': cfg.get('payment_gateway', {}).get('merchant_id', '') if isinstance(cfg.get('payment_gateway'), dict) else '',
                'mcc': cfg.get('merchant_category_code', ''),
                'purposeCode': cfg.get('purpose_code', ''),
                'canReceivePayments': cfg.get('status', '').lower() == 'active',
            })

        # Also include local configs not found in Meta API (for comparison)
        meta_names = {c['name'] for c in config_checks}
        for lc in local_config.get('configs', []):
            if lc['name'] not in meta_names:
                config_checks.append({
                    'name': lc['name'],
                    'status': 'local_only',
                    'gateway': lc.get('gateway', ''),
                    'mid': lc.get('mid', ''),
                    'mcc': local_config.get('mcc', ''),
                    'purposeCode': local_config.get('purposeCode', ''),
                    'canReceivePayments': False,
                    'note': 'Config exists locally but not found in Meta API',
                })

        results.append({
            'wabaId': wid,
            'phone': phone_info.get('phone', ''),
            'configurations': config_checks,
            'metaApiResponse': api_result if 'error' in api_result else None,
            'totalConfigs': len(config_checks),
            'activeConfigs': sum(1 for c in config_checks if c.get('canReceivePayments')),
        })

    return _resp(200, {'gatewayChecks': results})


def _payment_lookup(phone_number_id: str, config_name: str, reference_id: str) -> Dict:
    """Meta Payment Lookup API — verify payment status directly from WhatsApp.
    GET /<PHONE_NUMBER_ID>/payments/<PAYMENT_CONFIGURATION>/<REFERENCE_ID>
    SECURITY: Must not rely solely on webhooks. Always verify via this API."""
    if not phone_number_id or not config_name or not reference_id:
        return _resp(400, {'error': 'phone_number_id, config_name, and reference_id are required'})

    result = _graph_api(
        f'{phone_number_id}/payments/{config_name}/{reference_id}',
        phone_id=phone_number_id,
    )
    if 'error' in result:
        return _resp(result.get('error', {}).get('code', 500), {'error': result['error']})
    return _resp(200, {'paymentLookup': result})


def _payment_refund(phone_number_id: str, reference_id: str, config_name: str,
                    amount_paise: int, speed: str = 'normal') -> Dict:
    """Meta Refund API — initiate refund via WhatsApp.
    POST /<PHONE_NUMBER_ID>/payments_refund"""
    if not phone_number_id or not reference_id or not config_name:
        return _resp(400, {'error': 'phone_number_id, reference_id, and config_name are required'})
    if amount_paise <= 0:
        return _resp(400, {'error': 'amount must be positive'})
    if speed not in ('normal', 'instant'):
        speed = 'normal'

    payload = {
        'reference_id': reference_id,
        'speed': speed,
        'payment_config_id': config_name,
        'amount': {
            'currency': 'INR',
            'value': str(amount_paise),
            'offset': '100',
        },
    }
    result = _graph_api(
        f'{phone_number_id}/payments_refund',
        method='POST',
        payload=payload,
        phone_id=phone_number_id,
    )
    if 'error' in result:
        return _resp(result.get('error', {}).get('code', 500), {'error': result['error']})
    return _resp(200, {'refund': result})


# ============================================================================
# FLOW ENCRYPTION / DECRYPTION (WhatsApp Flows require E2E encryption)
# ============================================================================
from base64 import b64decode, b64encode
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1
from cryptography.hazmat.primitives.asymmetric.padding import hashes as asym_hashes
from cryptography.hazmat.primitives.ciphers import Cipher as AESCipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key

FLOW_PRIVATE_KEY_SECRET = os.environ.get('FLOW_PRIVATE_KEY_SECRET', 'wecare/flow-private-key')
FLOW_PRIVATE_KEY_PASSPHRASE = os.environ.get('FLOW_PRIVATE_KEY_PASSPHRASE', '')
_flow_private_key = None


def _get_flow_private_key():
    """Load RSA private key from Secrets Manager (cached)."""
    global _flow_private_key
    if _flow_private_key:
        return _flow_private_key
    try:
        resp = secrets_client.get_secret_value(SecretId=FLOW_PRIVATE_KEY_SECRET)
        pem = resp['SecretString']
        passphrase = FLOW_PRIVATE_KEY_PASSPHRASE.encode('utf-8') if FLOW_PRIVATE_KEY_PASSPHRASE else None
        _flow_private_key = load_pem_private_key(pem.encode('utf-8'), password=passphrase)
        return _flow_private_key
    except Exception as e:
        logger.error(f'Failed to load flow private key: {e}')
        return None


def _decrypt_flow_request(encrypted_flow_data_b64: str, encrypted_aes_key_b64: str, initial_vector_b64: str):
    """Decrypt WhatsApp Flow data_exchange request."""
    private_key = _get_flow_private_key()
    if not private_key:
        raise ValueError('Flow private key not available')

    flow_data = b64decode(encrypted_flow_data_b64)
    iv = b64decode(initial_vector_b64)
    encrypted_aes_key = b64decode(encrypted_aes_key_b64)

    # Decrypt AES key with RSA private key
    aes_key = private_key.decrypt(
        encrypted_aes_key,
        OAEP(mgf=MGF1(algorithm=asym_hashes.SHA256()), algorithm=asym_hashes.SHA256(), label=None)
    )

    # Decrypt flow data with AES-GCM
    encrypted_body = flow_data[:-16]
    tag = flow_data[-16:]
    decryptor = AESCipher(algorithms.AES(aes_key), modes.GCM(iv, tag)).decryptor()
    decrypted = decryptor.update(encrypted_body) + decryptor.finalize()
    return json.loads(decrypted.decode('utf-8')), aes_key, iv


def _encrypt_flow_response(response_data: dict, aes_key: bytes, iv: bytes) -> str:
    """Encrypt WhatsApp Flow response. Returns base64 string."""
    # Flip IV
    flipped_iv = bytearray(b ^ 0xFF for b in iv)
    encryptor = AESCipher(algorithms.AES(aes_key), modes.GCM(bytes(flipped_iv))).encryptor()
    encrypted = encryptor.update(json.dumps(response_data).encode('utf-8')) + encryptor.finalize()
    return b64encode(encrypted + encryptor.tag).decode('utf-8')


# ============================================================================
# FLOW MANAGEMENT ENGINE
# ============================================================================

def _get_flow_registry(flow_id: str) -> Dict:
    """Get flow config from registry, with in-memory caching."""
    global _flow_registry_cache, _flow_registry_cache_ts
    now = time.time()
    if flow_id in _flow_registry_cache and (now - _flow_registry_cache_ts) < FLOW_REGISTRY_CACHE_TTL:
        return _flow_registry_cache[flow_id]
    try:
        table = dynamodb.Table(FLOW_REGISTRY_TABLE)
        resp = table.get_item(Key={'flowId': flow_id})
        item = resp.get('Item', {})
        if item:
            _flow_registry_cache[flow_id] = item
            _flow_registry_cache_ts = now
            return item
    except Exception as e:
        logger.warning(f'Flow registry lookup failed for {flow_id}: {e}')
    return {}


def _get_flow_registry_by_code(flow_code: str) -> Dict:
    """Look up flow config by flowCode (e.g. '01.WD_SR')."""
    try:
        table = dynamodb.Table(FLOW_REGISTRY_TABLE)
        resp = table.query(
            IndexName='flowCode',
            KeyConditionExpression='flowCode = :c',
            ExpressionAttributeValues={':c': flow_code},
            Limit=1,
        )
        items = resp.get('Items', [])
        return items[0] if items else {}
    except Exception as e:
        logger.warning(f'Flow registry code lookup failed for {flow_code}: {e}')
        return {}


def _save_flow_submission(flow_config: Dict, phone: str, contact_id: str,
                          sender_name: str, form_data: Dict, flow_token: str,
                          request_id: str) -> Dict:
    """Save a generic flow submission to FlowSubmissionsTable. Returns the saved item."""
    try:
        now = int(time.time())
        submission_id = str(uuid.uuid4())
        flow_code = flow_config.get('flowCode', '')
        prefix = flow_config.get('submissionPrefix', 'WD')
        submission_number = f'{prefix}-{uuid.uuid4().hex[:8].upper()}'

        requires_payment = flow_config.get('requiresPayment', False)
        payment_amount = int(flow_config.get('paymentAmount', 0)) if requires_payment else 0
        payment_ref_id = f'WD-PAY-{uuid.uuid4().hex[:8].upper()}' if requires_payment else ''

        item = {
            'submissionId': submission_id,
            'flowId': flow_config.get('flowId', ''),
            'flowCode': flow_code,
            'flowType': flow_config.get('flowType', ''),
            'flowVersion': flow_config.get('flowVersion', ''),
            'phone': phone,
            'contactId': contact_id,
            'senderName': sender_name,
            'formData': json.dumps(form_data, default=str),
            'orderId': form_data.get('order_id', ''),
            'requestType': form_data.get('request_type', ''),
            'subject': form_data.get('subject', ''),
            'description': form_data.get('description', ''),
            'submissionNumber': submission_number,
            'flowToken': flow_token,
            'paymentRequired': requires_payment,
            'paymentAmount': payment_amount,
            'paymentStatus': 'pending' if requires_payment else 'none',
            'paymentRefId': payment_ref_id,
            'status': 'open',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
        }

        table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
        table.put_item(Item={k: v for k, v in item.items() if v is not None and v != '' and v is not False})

        logger.info(json.dumps({
            'event': 'flow_submission_saved',
            'submissionId': submission_id,
            'flowCode': flow_code,
            'submissionNumber': submission_number,
            'phone': phone[:6] + '***' if phone else '',
            'paymentRequired': requires_payment,
            'requestId': request_id,
        }))
        return item
    except Exception as e:
        logger.error(json.dumps({
            'event': 'flow_submission_save_error',
            'error': str(e),
            'flowCode': flow_config.get('flowCode', ''),
            'requestId': request_id,
        }))
        return {}


def _enrich_contact_from_flow(contact_id: str, form_data: Dict, contact_mapping: Dict):
    """Update Contact record with data collected from a flow."""
    if not contact_id or not contact_mapping:
        return
    try:
        update_parts = []
        expr_values = {}
        expr_names = {}
        now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        for flow_field, contact_field in contact_mapping.items():
            val = form_data.get(flow_field, '')
            if val:
                safe_key = contact_field.replace('.', '_')
                update_parts.append(f'#{safe_key} = :{safe_key}')
                expr_values[f':{safe_key}'] = str(val)
                expr_names[f'#{safe_key}'] = contact_field

        # Always update lastFlowInteractionAt and updatedAt
        update_parts.append('#lfia = :lfia')
        expr_values[':lfia'] = now_iso
        expr_names['#lfia'] = 'lastFlowInteractionAt'
        update_parts.append('#ua = :ua')
        expr_values[':ua'] = now_iso
        expr_names['#ua'] = 'updatedAt'

        if update_parts:
            table = dynamodb.Table(CONTACTS_TABLE)
            table.update_item(
                Key={'contactId': contact_id},
                UpdateExpression='SET ' + ', '.join(update_parts),
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names,
            )
            logger.info(f'Contact {contact_id} enriched with {len(update_parts) - 2} flow fields')
    except Exception as e:
        logger.warning(f'Contact enrichment failed for {contact_id}: {e}')


def _log_flow_interaction(flow_config: Dict, flow_token: str, phone: str,
                          action: str, screen: str, data: Dict, request_id: str,
                          is_error: bool = False, error_type: str = '', error_message: str = ''):
    """Log a flow interaction to FlowLogsTable."""
    try:
        now = int(time.time())
        table = dynamodb.Table(FLOW_LOGS_TABLE)
        item = {
            'logId': f'flog-{uuid.uuid4().hex[:12]}',
            'flowId': flow_config.get('flowId', ''),
            'flowCode': flow_config.get('flowCode', ''),
            'flowToken': flow_token,
            'phone': phone,
            'action': action,
            'screen': screen,
            'requestId': request_id,
            'createdAt': Decimal(str(now)),
            'ttl': now + (90 * 86400),  # 90 days
        }
        if data:
            try:
                item['dataSnapshot'] = json.dumps(data, default=str)[:4000]  # Cap at 4KB
            except Exception:
                pass
        if is_error:
            item['isError'] = True
            item['errorType'] = error_type
            item['errorMessage'] = error_message
        table.put_item(Item={k: v for k, v in item.items() if v is not None and v != ''})
    except Exception as e:
        logger.warning(f'Flow log write failed: {e}')


def _list_flow_submissions(params: Dict) -> Dict:
    """List flow submissions with filtering."""
    try:
        table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
        limit = min(int(params.get('limit', '100')), 500)
        flow_code = params.get('flowCode', '')
        payment_status = params.get('paymentStatus', '')
        status_filter = params.get('status', '')
        phone_filter = params.get('phone', '')

        if flow_code:
            resp = table.query(
                IndexName='flowCode', KeyConditionExpression='flowCode = :c',
                ExpressionAttributeValues={':c': flow_code},
                ScanIndexForward=False, Limit=limit,
            )
        elif payment_status:
            resp = table.query(
                IndexName='paymentStatus', KeyConditionExpression='paymentStatus = :s',
                ExpressionAttributeValues={':s': payment_status},
                ScanIndexForward=False, Limit=limit,
            )
        elif status_filter:
            resp = table.query(
                IndexName='status', KeyConditionExpression='#st = :s',
                ExpressionAttributeNames={'#st': 'status'},
                ExpressionAttributeValues={':s': status_filter},
                ScanIndexForward=False, Limit=limit,
            )
        elif phone_filter:
            resp = table.query(
                IndexName='phone', KeyConditionExpression='phone = :p',
                ExpressionAttributeValues={':p': phone_filter},
                ScanIndexForward=False, Limit=limit,
            )
        else:
            resp = table.scan(Limit=limit)

        items = resp.get('Items', [])
        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = int(v) if v == int(v) else float(v)
        items.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        return _resp(200, {'submissions': items, 'count': len(items)})
    except Exception as e:
        logger.error(f'List flow submissions error: {e}')
        return _resp(500, {'error': str(e)})


def _list_flow_registry(params: Dict) -> Dict:
    """List all registered flows."""
    try:
        table = dynamodb.Table(FLOW_REGISTRY_TABLE)
        resp = table.scan()
        items = resp.get('Items', [])
        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = int(v) if v == int(v) else float(v)
        items.sort(key=lambda x: x.get('flowCode', ''))
        return _resp(200, {'flows': items, 'count': len(items)})
    except Exception as e:
        logger.error(f'List flow registry error: {e}')
        return _resp(500, {'error': str(e)})


def _upsert_flow_registry(body: Dict) -> Dict:
    """Create or update a flow registry entry."""
    try:
        flow_id = body.get('flowId', '')
        if not flow_id:
            return _resp(400, {'error': 'flowId required'})
        now = int(time.time())
        table = dynamodb.Table(FLOW_REGISTRY_TABLE)
        item = {
            'flowId': flow_id,
            'flowCode': body.get('flowCode', ''),
            'flowName': body.get('flowName', ''),
            'flowType': body.get('flowType', 'form_submit'),
            'flowVersion': body.get('flowVersion', '7.3'),
            'dataApiVersion': body.get('dataApiVersion', '4.0'),
            'wabaId': body.get('wabaId', ''),
            'status': body.get('status', 'DRAFT'),
            'category': body.get('category', ''),
            'requiresPayment': body.get('requiresPayment', False),
            'paymentAmount': int(body.get('paymentAmount', 0)),
            'paymentDescription': body.get('paymentDescription', ''),
            'screenConfig': body.get('screenConfig', '{}'),
            'contactMapping': body.get('contactMapping', '{}'),
            'dataFetchers': body.get('dataFetchers', '{}'),
            'submissionPrefix': body.get('submissionPrefix', 'WD'),
            'endpointUri': body.get('endpointUri', 'https://api.wecare.digital/wa-business/flow-data'),
            'createdAt': Decimal(str(body.get('createdAt', now))),
            'updatedAt': Decimal(str(now)),
        }
        if body.get('publishedAt'):
            item['publishedAt'] = Decimal(str(body['publishedAt']))
        table.put_item(Item={k: v for k, v in item.items() if v is not None and v != ''})
        # Invalidate cache
        global _flow_registry_cache_ts
        _flow_registry_cache_ts = 0
        return _resp(200, {'success': True, 'flowId': flow_id})
    except Exception as e:
        logger.error(f'Upsert flow registry error: {e}')
        return _resp(500, {'error': str(e)})


def _get_flow_submission_stats(params: Dict) -> Dict:
    """Get aggregated stats for flow submissions — payment totals, status counts."""
    try:
        table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
        flow_code = params.get('flowCode', '')
        if flow_code:
            resp = table.query(
                IndexName='flowCode', KeyConditionExpression='flowCode = :c',
                ExpressionAttributeValues={':c': flow_code},
                Limit=500,
            )
        else:
            resp = table.scan(Limit=500)
        items = resp.get('Items', [])
        stats = {
            'total': len(items),
            'byStatus': {}, 'byPaymentStatus': {},
            'totalPaymentAmount': 0, 'capturedAmount': 0, 'pendingAmount': 0,
        }
        for item in items:
            s = item.get('status', 'open')
            ps = item.get('paymentStatus', 'none')
            amt = int(item.get('paymentAmount', 0))
            stats['byStatus'][s] = stats['byStatus'].get(s, 0) + 1
            stats['byPaymentStatus'][ps] = stats['byPaymentStatus'].get(ps, 0) + 1
            if ps == 'captured':
                stats['capturedAmount'] += amt
            elif ps == 'pending':
                stats['pendingAmount'] += amt
            stats['totalPaymentAmount'] += amt
        return _resp(200, stats)
    except Exception as e:
        logger.error(f'Flow submission stats error: {e}')
        return _resp(500, {'error': str(e)})


# ============================================================================
# FLOW A/B TESTING
# ============================================================================

def _get_ab_test_flow_id(flow_code: str, phone: str) -> str:
    """For A/B testing: return flow ID based on deterministic phone hash split."""
    config = _get_flow_registry_by_code(flow_code)
    if not config:
        return ''
    ab_str = config.get('abTestConfig', '')
    if not ab_str:
        return config.get('flowId', '')
    try:
        ab = json.loads(ab_str)
        if not ab.get('enabled'):
            return config.get('flowId', '')
        split = ab.get('splitPercent', 50)
        phone_hash = int(hashlib.md5(phone.encode()).hexdigest()[:8], 16) % 100
        if phone_hash < split:
            return config.get('flowId', '')
        return ab.get('variantB_flowId', config.get('flowId', ''))
    except Exception:
        return config.get('flowId', '')


# ============================================================================
# SLA TRACKING & AUTO-ESCALATION
# ============================================================================

def _check_sla_and_escalate(params: Dict) -> Dict:
    """Check open submissions for SLA breaches. Auto-assign after 3d, escalate after 7d."""
    try:
        table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
        now = int(time.time())
        sla_days = int(params.get('slaDays', '7'))
        reminder_days = int(params.get('reminderDays', '3'))
        default_assignee = params.get('defaultAssignee', 'support@wecare.digital')
        resp = table.query(
            IndexName='status', KeyConditionExpression='#st = :s',
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={':s': 'open'}, Limit=500,
        )
        items = resp.get('Items', [])
        actions = {'reminded': 0, 'auto_assigned': 0, 'escalated': 0, 'overdue_payments': 0}
        for item in items:
            created = int(item.get('createdAt', 0))
            if not created:
                continue
            days_old = (now - created) // 86400
            sub_id = item.get('submissionId', '')
            if item.get('paymentStatus') == 'pending' and days_old > sla_days:
                actions['overdue_payments'] += 1
                try:
                    table.update_item(Key={'submissionId': sub_id},
                        UpdateExpression='SET notes = :n, updatedAt = :u',
                        ExpressionAttributeValues={':n': f'OVERDUE: Payment pending {days_old}d', ':u': Decimal(str(now))})
                except Exception:
                    pass
            if days_old >= reminder_days and not item.get('assignedTo'):
                actions['auto_assigned'] += 1
                try:
                    table.update_item(Key={'submissionId': sub_id},
                        UpdateExpression='SET assignedTo = :a, #st = :s, updatedAt = :u',
                        ExpressionAttributeNames={'#st': 'status'},
                        ExpressionAttributeValues={':a': default_assignee, ':s': 'in_progress', ':u': Decimal(str(now))})
                except Exception:
                    pass
            if days_old >= sla_days and item.get('assignedTo') and item.get('status') != 'escalated':
                actions['escalated'] += 1
                try:
                    table.update_item(Key={'submissionId': sub_id},
                        UpdateExpression='SET notes = :n, #st = :s, updatedAt = :u',
                        ExpressionAttributeNames={'#st': 'status'},
                        ExpressionAttributeValues={':n': f'ESCALATED: Open for {days_old}d', ':s': 'in_progress', ':u': Decimal(str(now))})
                except Exception:
                    pass
        return _resp(200, {'actions': actions, 'checked': len(items)})
    except Exception as e:
        return _resp(500, {'error': str(e)})


# ============================================================================
# CUSTOMER JOURNEY VIEW
# ============================================================================

def _get_customer_journey(params: Dict) -> Dict:
    """Get all flow submissions + logs for a phone number — full journey view."""
    phone = params.get('phone', '')
    if not phone:
        return _resp(400, {'error': 'phone required'})
    try:
        fs_table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
        fs_resp = fs_table.query(IndexName='phone', KeyConditionExpression='phone = :p',
            ExpressionAttributeValues={':p': phone}, Limit=100)
        submissions = fs_resp.get('Items', [])
        fl_table = dynamodb.Table(FLOW_LOGS_TABLE)
        fl_resp = fl_table.query(IndexName='phone', KeyConditionExpression='phone = :p',
            ExpressionAttributeValues={':p': phone}, Limit=200)
        logs = fl_resp.get('Items', [])
        contact_id = _find_contact_by_phone(phone)
        contact = {}
        if contact_id:
            try:
                ct = dynamodb.Table(CONTACTS_TABLE)
                cr = ct.get_item(Key={'contactId': contact_id})
                contact = cr.get('Item', {})
            except Exception:
                pass
        for lst in [submissions, logs]:
            for item in lst:
                for k, v in item.items():
                    if isinstance(v, Decimal):
                        item[k] = int(v) if v == int(v) else float(v)
        for k, v in contact.items():
            if isinstance(v, Decimal):
                contact[k] = int(v) if v == int(v) else float(v)
        submissions.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        logs.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        flows_completed = list(set(s.get('flowCode', '') for s in submissions))
        total_paid = sum(int(s.get('paymentAmount', 0)) for s in submissions if s.get('paymentStatus') == 'captured')
        return _resp(200, {
            'phone': phone, 'contactId': contact_id, 'contact': contact,
            'submissions': submissions, 'logs': logs,
            'summary': {'flowsCompleted': flows_completed, 'totalSubmissions': len(submissions),
                        'totalPaid': total_paid, 'totalInteractions': len(logs)},
        })
    except Exception as e:
        return _resp(500, {'error': str(e)})


# ============================================================================
# FLOW TEMPLATE CLONING BETWEEN WABAs
# ============================================================================

def _clone_flow_to_waba(body: Dict) -> Dict:
    """Clone a flow registry config to a different WABA with a new Meta flow ID."""
    source_flow_code = body.get('sourceFlowCode', '')
    target_waba_id = body.get('targetWabaId', '')
    target_flow_id = body.get('targetFlowId', '')
    if not source_flow_code or not target_waba_id or not target_flow_id:
        return _resp(400, {'error': 'sourceFlowCode, targetWabaId, targetFlowId required'})
    source = _get_flow_registry_by_code(source_flow_code)
    if not source:
        return _resp(404, {'error': f'Source flow {source_flow_code} not found'})
    now = int(time.time())
    clone = dict(source)
    clone['flowId'] = target_flow_id
    clone['wabaId'] = target_waba_id
    clone['status'] = 'DRAFT'
    clone['createdAt'] = Decimal(str(now))
    clone['updatedAt'] = Decimal(str(now))
    if 'publishedAt' in clone:
        del clone['publishedAt']
    try:
        table = dynamodb.Table(FLOW_REGISTRY_TABLE)
        table.put_item(Item={k: v for k, v in clone.items() if v is not None and v != ''})
        global _flow_registry_cache_ts
        _flow_registry_cache_ts = 0
        return _resp(200, {'success': True, 'clonedFlowId': target_flow_id, 'sourceFlowCode': source_flow_code})
    except Exception as e:
        return _resp(500, {'error': str(e)})


# ============================================================================
# WEBHOOK ALERTS (Slack/Email via SNS)
# ============================================================================

def _send_flow_alert(alert_type: str, flow_id: str, message: str, details: Dict = None):
    """Send alert via SNS topic (fans out to Slack/email subscriptions)."""
    try:
        sns = boto3.client('sns', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        topic_arn = os.environ.get('FLOW_ALERTS_SNS_TOPIC', '')
        if not topic_arn:
            logger.info(f'Flow alert (no SNS): {alert_type} - {message}')
            return
        sns.publish(TopicArn=topic_arn, Subject=f'Flow Alert: {alert_type}',
            Message=json.dumps({'alertType': alert_type, 'flowId': flow_id,
                'message': message, 'details': details or {}, 'timestamp': int(time.time())}, default=str))
    except Exception as e:
        logger.warning(f'Flow alert failed: {e}')


# ============================================================================
# CSV EXPORT FOR ACCOUNTING
# ============================================================================

def _export_submissions_csv(params: Dict) -> Dict:
    """Export flow submissions as CSV for accounting reconciliation."""
    try:
        table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
        flow_code = params.get('flowCode', '')
        payment_status = params.get('paymentStatus', '')
        if flow_code:
            resp = table.query(IndexName='flowCode', KeyConditionExpression='flowCode = :c',
                ExpressionAttributeValues={':c': flow_code}, Limit=1000)
        elif payment_status:
            resp = table.query(IndexName='paymentStatus', KeyConditionExpression='paymentStatus = :s',
                ExpressionAttributeValues={':s': payment_status}, Limit=1000)
        else:
            resp = table.scan(Limit=1000)
        items = resp.get('Items', [])
        items.sort(key=lambda x: int(x.get('createdAt', 0)), reverse=True)
        headers = ['submissionNumber', 'flowCode', 'phone', 'senderName', 'orderId',
                    'requestType', 'subject', 'paymentStatus', 'paymentAmount', 'paymentRefId',
                    'invoiceId', 'transactionId', 'status', 'assignedTo', 'createdAt', 'paidAt']
        lines = [','.join(headers)]
        for item in items:
            row = []
            for h in headers:
                val = item.get(h, '')
                if isinstance(val, Decimal):
                    val = int(val) if val == int(val) else float(val)
                if h == 'paymentAmount' and val:
                    val = f'{int(val) / 100:.2f}'
                if h in ('createdAt', 'paidAt') and val:
                    try:
                        val = time.strftime('%Y-%m-%d %H:%M', time.gmtime(int(val)))
                    except Exception:
                        pass
                s = str(val).replace('"', '""')
                row.append(f'"{s}"' if ',' in s or '"' in s else str(s))
            lines.append(','.join(row))
        return _resp(200, {'csv': '\n'.join(lines), 'count': len(items)})
    except Exception as e:
        return _resp(500, {'error': str(e)})


# ============================================================================
# FLOW VERSION FREEZE MONITORING
# ============================================================================

def _check_flow_version_health(params: Dict) -> Dict:
    """Check all registered flows for version freeze/expiry risks."""
    FROZEN = {'2.1', '3.0', '3.1', '4.0', '5.0'}
    RECOMMENDED = '7.3'
    SUPPORTED = {'5.1', '6.0', '6.1', '6.2', '6.3', '7.0', '7.1', '7.2', '7.3'}
    try:
        table = dynamodb.Table(FLOW_REGISTRY_TABLE)
        resp = table.scan()
        items = resp.get('Items', [])
        results = []
        for item in items:
            v = item.get('flowVersion', '')
            if v in FROZEN:
                st, msg = 'frozen', f'Version {v} is FROZEN. Upgrade to {RECOMMENDED} immediately.'
            elif v and v not in SUPPORTED:
                st, msg = 'unknown', f'Version {v} not in known supported list.'
            elif v != RECOMMENDED:
                st, msg = 'outdated', f'Version {v} supported but not recommended. Upgrade to {RECOMMENDED}.'
            else:
                st, msg = 'ok', ''
            results.append({'flowCode': item.get('flowCode', ''), 'flowName': item.get('flowName', ''),
                'flowId': item.get('flowId', ''), 'flowVersion': v,
                'dataApiVersion': item.get('dataApiVersion', ''), 'versionStatus': st, 'message': msg})
            if st == 'frozen':
                _send_flow_alert('VERSION_FROZEN', item.get('flowId', ''), msg, {'flowCode': item.get('flowCode', '')})
        return _resp(200, {'flows': results, 'recommendedVersion': RECOMMENDED})
    except Exception as e:
        return _resp(500, {'error': str(e)})


# ============================================================================
# FLOW DATA EXCHANGE (WhatsApp Flows)
# ============================================================================
def _handle_flow_data(body: Dict, request_id: str, origin: str = '') -> Dict:
    """
    Handle WhatsApp Flow data_exchange requests with E2E encryption.
    1. Decrypt incoming encrypted payload
    2. Process the action (INIT, data_exchange, ping)
    3. Encrypt the response and return as base64 string
    """
    # Step 1: Decrypt the incoming request
    encrypted_flow_data = body.get('encrypted_flow_data', '')
    encrypted_aes_key = body.get('encrypted_aes_key', '')
    initial_vector = body.get('initial_vector', '')

    if not encrypted_flow_data or not encrypted_aes_key or not initial_vector:
        return _resp(400, {'error': 'Missing encrypted flow data fields'})

    try:
        decrypted_data, aes_key, iv = _decrypt_flow_request(
            encrypted_flow_data, encrypted_aes_key, initial_vector)
    except Exception as e:
        logger.error(f'[{request_id}] Flow decryption failed: {e}')
        return _resp(421, {'error': 'Decryption failed'})

    action = decrypted_data.get('action', '')
    screen = decrypted_data.get('screen', '')
    data = decrypted_data.get('data', {})
    flow_token = decrypted_data.get('flow_token', '')

    logger.info(json.dumps({
        'flow_data': True, 'action': action, 'screen': screen,
        'data_keys': list(data.keys()), 'flow_token': flow_token,
        'requestId': request_id,
    }))

    response_payload = None

    # Extract phone from flow_token for logging
    _flow_phone = ''
    if flow_token and '-ph-' in flow_token:
        _flow_phone = flow_token.split('-ph-', 1)[1]

    # Log every flow interaction (non-ping) for audit trail
    if action != 'ping':
        try:
            _log_flow_event(
                flow_token=flow_token, phone=_flow_phone,
                action=action, screen=screen,
                data_keys=list(data.keys()), request_id=request_id,
                data=data,
            )
        except Exception as e:
            logger.warning(f'Flow log write failed: {e}')  # Never block flow for logging failures

        # Also log to new FlowLogsTable
        try:
            _flow_config_for_log = {}
            if flow_token:
                parts = flow_token.split('-')
                if len(parts) >= 2 and parts[0] not in ('sr',):
                    _flow_config_for_log = _get_flow_registry_by_code(parts[0])
            _log_flow_interaction(
                flow_config=_flow_config_for_log or {'flowId': '', 'flowCode': ''},
                flow_token=flow_token, phone=_flow_phone,
                action=action, screen=screen, data=data, request_id=request_id,
            )
        except Exception as e:
            logger.warning(f'New flow log write failed: {e}')

    # Step 2: Process the action
    # NOTE: Per Meta docs, encrypted responses must NOT include "version".
    # Ping → {"data": {"status": "active"}}
    # Data exchange → {"screen": "...", "data": {...}}
    # Final → {"screen": "SUCCESS", "data": {"extension_message_response": {...}}}

    if action == 'ping':
        response_payload = {'data': {'status': 'active'}}

    elif action == 'INIT':
        # Extract phone from flow_token (format: sr-{uuid}-ph-{phone})
        phone = data.get('phone', '') or data.get('wa_id', '')
        if not phone and flow_token and '-ph-' in flow_token:
            phone = flow_token.split('-ph-', 1)[1]
        email = data.get('email', '')
        orders = _fetch_orders_for_flow(phone, email)
        response_payload = {
            'screen': 'ORDER_SELECT',
            'data': {
                'orders': orders if orders else [{'id': 'none', 'title': 'No orders found'}],
            }
        }

    elif action == 'data_exchange':
        # ── Checkout Button Template sub_actions (coupons, address, shipping) ──
        # Meta Payments Checkout data_exchange has 'sub_action' + 'order_details' in data.
        # WhatsApp Flows data_exchange has 'screen' but no 'sub_action'.
        sub_action = decrypted_data.get('sub_action', '')
        if sub_action and data.get('order_details'):
            response_payload = _handle_checkout_data_exchange(
                sub_action=sub_action, data=data,
                version=decrypted_data.get('version', '1.0'),
                request_id=request_id,
            )
        # ── WhatsApp Flows data_exchange (form-based) ──
        # `screen` = current screen the user is on (top-level field from Meta).
        # Meta strips "screen" from payload data — so route by current screen ID.
        elif screen == 'ORDER_SELECT':
            # User selected an order → show REQUEST_FORM with request types
            selected_order = data.get('order_id', '')
            request_types = [
                {'id': 'return', 'title': '🔄 Return'},
                {'id': 'exchange', 'title': '🔁 Exchange'},
                {'id': 'refund', 'title': '💰 Refund'},
                {'id': 'complaint', 'title': '⚠️ Complaint'},
                {'id': 'support', 'title': '🛟 Support'},
                {'id': 'other', 'title': '📝 Other'},
            ]
            response_payload = {
                'screen': 'REQUEST_FORM',
                'data': {
                    'order_id': selected_order,
                    'request_types': request_types,
                }
            }

        elif screen == 'SUBMIT_REQUEST_FORM' or screen == 'REQUEST_FORM':
            # User filled subject + description → handled by navigate to REVIEW (client-side)
            # This path is only hit if the flow uses data_exchange instead of navigate
            order_id = data.get('order_id', '')
            subject = data.get('subject', '')
            description = data.get('description', '')
            request_type = data.get('request_type', '')
            response_payload = {
                'screen': 'REVIEW',
                'data': {
                    'order_id': order_id,
                    'request_type': request_type,
                    'subject': subject,
                    'description': description,
                }
            }

        elif screen == 'REVIEW' and not (flow_token and flow_token.startswith('sub-')):
            # User confirmed and tapped Submit Request ₹49 → save, pay, confirm, close flow
            order_id = data.get('order_id', '')
            subject = data.get('subject', '')
            description = data.get('description', '')
            request_type = data.get('request_type', '')

            # Generate dynamic request number + separate payment reference
            request_number = f'WD-SR-{uuid.uuid4().hex[:8].upper()}'
            payment_ref_id = f'WD-PAY-{uuid.uuid4().hex[:8].upper()}'

            logger.info(json.dumps({
                'flow_submit': True, 'order_id': order_id,
                'request_type': request_type,
                'subject': subject, 'description': description,
                'request_number': request_number,
                'payment_ref_id': payment_ref_id,
                'requestId': request_id,
            }))

            # Save submission to DynamoDB (legacy table)
            phone = ''
            if flow_token and '-ph-' in flow_token:
                phone = flow_token.split('-ph-', 1)[1]
            try:
                _save_submit_request(
                    phone=phone, order_id=order_id,
                    subject=subject, description=description,
                    flow_token=flow_token, request_id=request_id,
                    request_number=request_number,
                    payment_ref_id=payment_ref_id
                )
            except Exception as save_err:
                logger.error(json.dumps({
                    'event': 'flow_save_outer_error',
                    'error': str(save_err),
                    'requestId': request_id,
                }))

            # Save to new FlowSubmissionsTable (generic flow engine)
            try:
                # Try to look up flow config from registry (by flow_token prefix or fallback)
                flow_config = {}
                flow_code_from_token = ''
                if flow_token:
                    # Token format: {flowCode}-{uuid}-ph-{phone} or sr-{uuid}-ph-{phone}
                    parts = flow_token.split('-')
                    if len(parts) >= 2 and parts[0] not in ('sr',):
                        flow_code_from_token = parts[0]
                        flow_config = _get_flow_registry_by_code(flow_code_from_token)

                if not flow_config:
                    # Fallback: use default config for 01.WD_SR
                    flow_config = _get_flow_registry_by_code('01.WD_SR') or {
                        'flowId': '', 'flowCode': '01.WD_SR', 'flowName': 'Submit Request',
                        'flowType': 'form_submit', 'flowVersion': '7.3',
                        'requiresPayment': True, 'paymentAmount': 4900,
                        'submissionPrefix': 'WD-SR',
                    }

                contact_id = _find_contact_by_phone(phone)
                sender_name = ''
                if contact_id:
                    try:
                        ct = dynamodb.Table(CONTACTS_TABLE)
                        cr = ct.get_item(Key={'contactId': contact_id}, ProjectionExpression='#n', ExpressionAttributeNames={'#n': 'name'})
                        sender_name = cr.get('Item', {}).get('name', '')
                    except Exception:
                        pass

                submission = _save_flow_submission(
                    flow_config=flow_config, phone=phone, contact_id=contact_id,
                    sender_name=sender_name,
                    form_data={'order_id': order_id, 'subject': subject,
                               'description': description, 'request_type': request_type},
                    flow_token=flow_token, request_id=request_id,
                )
                # Override generated numbers with the ones we already created
                if submission and submission.get('submissionId'):
                    try:
                        fs_table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
                        fs_table.update_item(
                            Key={'submissionId': submission['submissionId']},
                            UpdateExpression='SET submissionNumber = :sn, paymentRefId = :pr, paymentStatus = :ps, paymentRequired = :preq, paymentAmount = :pa',
                            ExpressionAttributeValues={
                                ':sn': request_number, ':pr': payment_ref_id,
                                ':ps': 'pending', ':preq': True, ':pa': 4900,
                            },
                        )
                    except Exception:
                        pass

                # Enrich contact if flow has contactMapping
                contact_mapping_str = flow_config.get('contactMapping', '{}')
                try:
                    contact_mapping = json.loads(contact_mapping_str) if contact_mapping_str else {}
                except Exception:
                    contact_mapping = {}
                if contact_mapping and contact_id:
                    _enrich_contact_from_flow(contact_id, data, contact_mapping)

            except Exception as new_save_err:
                logger.warning(f'FlowSubmission save failed (non-blocking): {new_save_err}')

            # Send payment + confirmation ASYNC via a separate Lambda invocation
            # to avoid blocking the flow response (Meta has a timeout on data_exchange)
            try:
                # Read gateway config from flow registry
                _gw = flow_config.get('preferredGateway', '') if flow_config else ''
                _pg_config = flow_config.get('paymentConfigName', '') if flow_config else ''
                lambda_client.invoke(
                    FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'wecare-whatsapp-business-api'),
                    InvocationType='Event',
                    Payload=json.dumps({
                        '_async_action': 'flow_post_submit',
                        'phone': phone,
                        'order_id': order_id,
                        'subject': subject,
                        'request_id': request_id,
                        'request_number': request_number,
                        'payment_ref_id': payment_ref_id,
                        'preferred_gateway': _gw,
                        'payment_config_name': _pg_config,
                    })
                )
            except Exception as async_err:
                logger.error(json.dumps({
                    'event': 'flow_async_invoke_error',
                    'error': str(async_err),
                    'requestId': request_id,
                }))
                # Fallback: try synchronously (old behavior) if async invoke fails
                try:
                    _send_payment_after_flow(
                        phone=phone, order_id=order_id,
                        subject=subject, request_id=request_id,
                        request_number=request_number,
                        payment_ref_id=payment_ref_id
                    )
                    _send_flow_confirmation(
                        phone=phone, order_id=order_id, subject=subject,
                        request_id=request_id, request_number=request_number,
                        payment_ref_id=payment_ref_id
                    )
                except Exception as e:
                    logger.error(f'[{request_id}] Invoice/confirmation send failed for order {order_id}: {e}')

            # Navigate to SUCCESS screen with generated IDs
            # SUCCESS is terminal:true — it closes the flow when user taps "Done"
            response_payload = {
                'screen': 'SUCCESS',
                'data': {
                    'request_number': request_number,
                    'payment_ref_id': payment_ref_id,
                    'message': f'✅ Your request {request_number} has been submitted successfully! A payment link for ₹49 will be sent shortly.',
                }
            }

        # ── Subscribe Flow: REVIEW screen (data_exchange) ──
        elif screen == 'REVIEW' and flow_token and flow_token.startswith('sub-'):
            full_name = data.get('full_name', '')
            phone_number = data.get('phone_number', '')
            email_address = data.get('email_address', '')
            company_name = data.get('company_name', '')
            wa_username = data.get('wa_username', '')
            gstin = data.get('gstin', '')

            # Shipping address (primary — entered first)
            ship_name = data.get('ship_name', '')
            ship_phone = data.get('ship_phone', '')
            ship_house = data.get('ship_house', '')
            ship_building = data.get('ship_building', '')
            ship_street = data.get('ship_street', '')
            ship_landmark = data.get('ship_landmark', '')
            ship_city = data.get('ship_city', '')
            ship_state = data.get('ship_state', '')
            ship_pin = data.get('ship_pin', '')

            # Billing address (copy name/phone from shipping always, other fields if same_as_ship)
            same_as_ship = data.get('same_as_ship', False)
            bill_name = ship_name  # Always use shipping name for billing
            bill_phone = ship_phone  # Always use shipping phone for billing
            bill_house = data.get('bill_house', '')
            bill_building = data.get('bill_building', '')
            bill_street = data.get('bill_street', '')
            bill_landmark = data.get('bill_landmark', '')
            bill_city = data.get('bill_city', '')
            bill_state = data.get('bill_state', '')
            bill_pin = data.get('bill_pin', '')

            # Copy all billing address fields from shipping when same_as_ship or billing is empty
            if same_as_ship or not bill_street:
                bill_house = bill_house or ship_house
                bill_building = bill_building or ship_building
                bill_street = bill_street or ship_street
                bill_landmark = bill_landmark or ship_landmark
                bill_city = bill_city or ship_city
                bill_state = bill_state or ship_state
                bill_pin = bill_pin or ship_pin

            # Subscriber ID = short 4-digit ref, UUID for internal contact ID
            subscriber_uuid = str(uuid.uuid4())
            subscriber_id = f'WD-SUB-{uuid.uuid4().hex[:4].upper()}'

            # Extract phone from flow_token
            phone = ''
            if '-ph-' in flow_token:
                phone = flow_token.split('-ph-', 1)[1]

            # Build Meta shipping_info compatible address objects
            ship_addr_obj = {
                'name': ship_name, 'phone_number': ship_phone.replace('+', ''),
                'address': ship_street, 'city': ship_city,
                'state': ship_state, 'in_pin_code': ship_pin,
                'house_number': ship_house, 'building_name': ship_building,
                'landmark_area': ship_landmark,
            }
            bill_addr_obj = {
                'name': bill_name, 'phone_number': bill_phone.replace('+', ''),
                'address': bill_street, 'city': bill_city,
                'state': bill_state, 'in_pin_code': bill_pin,
                'house_number': bill_house, 'building_name': bill_building,
                'landmark_area': bill_landmark,
            }

            def _addr_str(a):
                parts = []
                if a.get('name'): parts.append(a['name'])
                if a.get('house_number'): parts.append(a['house_number'])
                if a.get('building_name'): parts.append(a['building_name'])
                if a.get('address'): parts.append(a['address'])
                if a.get('landmark_area'): parts.append(a['landmark_area'])
                if a.get('city'): parts.append(a['city'])
                if a.get('state'): parts.append(a['state'])
                if a.get('in_pin_code'): parts.append(a['in_pin_code'])
                return ', '.join(p for p in parts if p)

            # Find existing contact or create new one with subscriber UUID as contact ID
            contact_id = _find_contact_by_phone(phone)
            now_ts = int(time.time())

            if contact_id:
                # Update existing contact with subscription data + default opt-in
                # Save change log: read old values first
                old_contact = {}
                try:
                    ct = dynamodb.Table(CONTACTS_TABLE)
                    old_resp = ct.get_item(Key={'id': contact_id})
                    old_contact = old_resp.get('Item', {})
                except Exception:
                    pass

                try:
                    ct = dynamodb.Table(CONTACTS_TABLE)
                    ct.update_item(
                        Key={'id': contact_id},
                        UpdateExpression=(
                            'SET #nm = :nm, #em = :em, #ba = :ba, #sa = :sa, #ua = :ua, '
                            '#cbn = :cbn, #ow = :ow, #os = :os, #oe = :oe, '
                            '#aw = :aw, #as2 = :as2, #ae = :ae, '
                            '#baj = :baj, #saj = :saj, #un = :un, #gst = :gst'
                        ),
                        ExpressionAttributeNames={
                            '#nm': 'name', '#em': 'email', '#ba': 'billingAddress',
                            '#sa': 'shippingAddress', '#ua': 'updatedAt', '#cbn': 'contactBookName',
                            '#ow': 'optInWhatsApp', '#os': 'optInSms', '#oe': 'optInEmail',
                            '#aw': 'allowlistWhatsApp', '#as2': 'allowlistSms', '#ae': 'allowlistEmail',
                            '#baj': 'billingAddressJson', '#saj': 'shippingAddressJson',
                            '#un': 'username', '#gst': 'gstin',
                        },
                        ExpressionAttributeValues={
                            ':nm': full_name, ':em': email_address,
                            ':ba': _addr_str(bill_addr_obj), ':sa': _addr_str(ship_addr_obj),
                            ':ua': now_ts, ':cbn': company_name,
                            ':ow': True, ':os': True, ':oe': True,
                            ':aw': True, ':as2': True, ':ae': True,
                            ':baj': json.dumps(bill_addr_obj), ':saj': json.dumps(ship_addr_obj),
                            ':un': wa_username, ':gst': gstin,
                        },
                    )
                except Exception as e:
                    logger.warning(f'Subscribe contact update failed: {e}')

                # Save change log if contact was updated (not new)
                if old_contact:
                    try:
                        changes = {}
                        field_map = {
                            'name': full_name, 'email': email_address,
                            'contactBookName': company_name,
                            'username': wa_username, 'gstin': gstin,
                            'shippingAddress': _addr_str(ship_addr_obj),
                            'billingAddress': _addr_str(bill_addr_obj),
                        }
                        for field, new_val in field_map.items():
                            old_val = str(old_contact.get(field, '') or '')
                            if old_val != str(new_val):
                                changes[field] = {'old': old_val, 'new': str(new_val)}
                        if changes:
                            fs_table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
                            fs_table.put_item(Item={
                                'submissionId': f'WD-CHG-{uuid.uuid4().hex[:8].upper()}',
                                'flowCode': 'WD_SUBSCRIBE_UPDATE',
                                'flowType': 'change_log',
                                'phone': phone,
                                'contactId': contact_id,
                                'submissionNumber': subscriber_id,
                                'status': 'updated',
                                'formData': json.dumps({
                                    'changes': changes,
                                    'updated_by': 'subscribe_flow',
                                    'subscriber_id': subscriber_id,
                                }),
                                'flowToken': flow_token,
                                'createdAt': Decimal(str(now_ts)),
                                'updatedAt': Decimal(str(now_ts)),
                                'ttl': now_ts + (365 * 86400),
                            })
                            logger.info(json.dumps({
                                'event': 'subscribe_change_log_saved',
                                'contactId': contact_id,
                                'changedFields': list(changes.keys()),
                                'requestId': request_id,
                            }))
                    except Exception as cl_err:
                        logger.warning(f'Change log save failed: {cl_err}')
            else:
                # Create new contact with subscriber UUID as the contact ID
                contact_id = subscriber_uuid
                try:
                    ct = dynamodb.Table(CONTACTS_TABLE)
                    # Normalize phone
                    norm_phone = phone.replace('+', '').replace(' ', '')
                    if norm_phone and not norm_phone.startswith('+'):
                        norm_phone = f'+{norm_phone}'
                    ct.put_item(Item={
                        'id': contact_id, 'contactId': contact_id,
                        'name': full_name, 'phone': norm_phone, 'email': email_address,
                        'contactBookName': company_name,
                        'username': wa_username, 'gstin': gstin,
                        'billingAddress': _addr_str(bill_addr_obj),
                        'shippingAddress': _addr_str(ship_addr_obj),
                        'billingAddressJson': json.dumps(bill_addr_obj),
                        'shippingAddressJson': json.dumps(ship_addr_obj),
                        'optInWhatsApp': True, 'optInSms': True, 'optInEmail': True,
                        'allowlistWhatsApp': True, 'allowlistSms': True, 'allowlistEmail': True,
                        'tags': ['subscriber'],
                        'createdAt': now_ts, 'updatedAt': now_ts,
                    })
                except Exception as e:
                    logger.warning(f'Subscribe contact create failed: {e}')

            logger.info(json.dumps({
                'event': 'subscribe_contact_saved',
                'contactId': contact_id, 'subscriberId': subscriber_id,
                'isNew': contact_id == subscriber_uuid, 'requestId': request_id,
            }))

            # Save subscription to FlowSubmissionsTable
            try:
                fs_table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
                fs_table.put_item(Item={
                    'submissionId': subscriber_id,
                    'flowCode': 'WD_SUBSCRIBE',
                    'flowType': 'subscription',
                    'phone': phone,
                    'contactId': contact_id,
                    'submissionNumber': subscriber_id,
                    'status': 'completed',
                    'formData': json.dumps({
                        'full_name': full_name, 'phone_number': phone_number,
                        'email_address': email_address, 'company_name': company_name,
                        'wa_username': wa_username, 'gstin': gstin,
                        'shipping_address': ship_addr_obj, 'billing_address': bill_addr_obj,
                        'same_as_ship': same_as_ship,
                    }),
                    'flowToken': flow_token,
                    'createdAt': Decimal(str(now_ts)),
                    'updatedAt': Decimal(str(now_ts)),
                    'ttl': now_ts + (365 * 86400),
                })
            except Exception as e:
                logger.warning(f'Subscribe submission save failed: {e}')

            response_payload = {
                'screen': 'SUCCESS',
                'data': {
                    'subscriber_id': subscriber_id,
                    'contact_id': contact_id,
                    'message': f'Welcome to WECARE.DIGITAL! Your subscriber ID is {subscriber_id}.',
                }
            }

        elif screen == 'THANK_YOU' or screen == 'SUCCESS':
            # User tapped "Done" on the terminal screen → close flow
            response_payload = {
                'screen': 'SUCCESS',
                'data': {
                    'extension_message_response': {
                        'params': {
                            'flow_token': flow_token,
                            'status': 'completed',
                        }
                    }
                }
            }

    # Error notification acknowledgement
    if not response_payload and data.get('error'):
        response_payload = {'data': {'acknowledged': True}}

    if not response_payload:
        response_payload = {'data': {'error': f'Unknown action: {action}'}}

    # Step 3: Encrypt the response
    try:
        encrypted_response = _encrypt_flow_response(response_payload, aes_key, iv)
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': encrypted_response,
        }
    except Exception as e:
        logger.error(f'[{request_id}] Flow encryption failed: {e}')
        return _resp(500, {'error': 'Encryption failed'})



def _save_submit_request(phone: str, order_id: str, subject: str, description: str,
                         flow_token: str, request_id: str, request_number: str = '',
                         payment_ref_id: str = '') -> str:
    """Save flow submission to SubmitRequests DynamoDB table."""
    try:
        now = int(time.time())
        submission_id = str(uuid.uuid4())
        ref_id = payment_ref_id or f'WD-PAY-{uuid.uuid4().hex[:8].upper()}'

        # Look up contact info
        contact_id = _find_contact_by_phone(phone)
        sender_name = ''
        if contact_id:
            try:
                table = dynamodb.Table(CONTACTS_TABLE)
                resp = table.get_item(Key={'id': contact_id}, ProjectionExpression='#n', ExpressionAttributeNames={'#n': 'name'})
                sender_name = resp.get('Item', {}).get('name', '')
            except Exception as e:
                logger.warning(f'Contact name lookup failed for {contact_id}: {e}')

        item = {
            'id': submission_id,
            'requestId': request_id,
            'requestNumber': request_number or ref_id,
            'flowToken': flow_token,
            'phone': phone,
            'senderName': sender_name,
            'contactId': contact_id,
            'orderId': order_id,
            'subject': subject,
            'description': description,
            'paymentStatus': 'pending',
            'paymentReferenceId': ref_id,
            'paymentAmount': 4900,
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
        }

        table = dynamodb.Table(SUBMIT_REQUESTS_TABLE)
        table.put_item(Item={k: v for k, v in item.items() if v is not None and v != ''})

        logger.info(json.dumps({
            'event': 'submit_request_saved',
            'submissionId': submission_id,
            'orderId': order_id,
            'phone': phone[:6] + '***' if phone else '',
            'referenceId': ref_id,
            'requestId': request_id,
        }))
        return submission_id
    except Exception as e:
        logger.error(json.dumps({
            'event': 'submit_request_save_error',
            'error': str(e),
            'orderId': order_id,
            'requestId': request_id,
        }))
        return ''


# ═══════════════════════════════════════════════════════════════════════════
# CHECKOUT BUTTON TEMPLATE — data_exchange sub-action handlers
# Per Meta docs: https://developers.facebook.com/docs/whatsapp/cloud-api/
#   payments-api/payments-in/checkout-button-templates
# Handles: get_coupons, apply_coupon, remove_coupon, apply_shipping
# Uses same E2E encryption as WhatsApp Flows (shared /flow-data endpoint).
# ═══════════════════════════════════════════════════════════════════════════

# ── Coupon Configuration ──
# In-memory coupon store. Migrate to DynamoDB CouponsTable for dynamic management.
# Each coupon: code, id, description, discount_type (percent|flat), discount_value (paise for flat, % for percent),
#              min_order_paise, max_discount_paise, active, valid_until (epoch), usage_limit
CHECKOUT_COUPONS = [
    {
        'code': 'WELCOME10', 'id': 'welcome_10',
        'description': 'Save ₹10 on your first order',
        'discount_type': 'percent', 'discount_value': 10,
        'min_order_paise': 10000, 'max_discount_paise': 50000,
        'active': True, 'valid_until': 0, 'usage_limit': 0,
    },
    {
        'code': 'FLAT50', 'id': 'flat_50',
        'description': 'Flat ₹50 off on orders above ₹200',
        'discount_type': 'flat', 'discount_value': 5000,
        'min_order_paise': 20000, 'max_discount_paise': 5000,
        'active': True, 'valid_until': 0, 'usage_limit': 0,
    },
    {
        'code': 'SAVE20', 'id': 'save_20',
        'description': 'Save 20% up to ₹100',
        'discount_type': 'percent', 'discount_value': 20,
        'min_order_paise': 15000, 'max_discount_paise': 10000,
        'active': True, 'valid_until': 0, 'usage_limit': 0,
    },
    {
        'code': 'FREESHIP', 'id': 'free_ship',
        'description': 'Free shipping on this order',
        'discount_type': 'flat', 'discount_value': 0,  # Special: zeroes shipping
        'min_order_paise': 0, 'max_discount_paise': 0,
        'active': True, 'valid_until': 0, 'usage_limit': 0,
        '_free_shipping': True,
    },
]

# ── Pin-code based shipping rates (paise) ──
# Zone → base rate. Kolkata (700xxx) is local, rest of WB is regional, others are national.
# Override per pin prefix for granular control.
SHIPPING_RATES_PAISE = {
    'local': 4900,       # ₹49 — Kolkata (700xxx)
    'regional': 7900,    # ₹79 — West Bengal (71x-74x)
    'metro': 9900,       # ₹99 — Delhi, Mumbai, Bangalore, Chennai, Hyderabad
    'national': 14900,   # ₹149 — Rest of India
    'remote': 24900,     # ₹249 — NE states, J&K, Ladakh, A&N
}

# Pin prefix → zone mapping
_PIN_ZONE_MAP = {
    '700': 'local', '711': 'regional', '712': 'regional', '713': 'regional',
    '721': 'regional', '722': 'regional', '723': 'regional', '731': 'regional',
    '732': 'regional', '733': 'regional', '734': 'regional', '735': 'regional',
    '736': 'regional', '741': 'regional', '742': 'regional', '743': 'regional',
    # Metros
    '110': 'metro', '400': 'metro', '560': 'metro', '600': 'metro', '500': 'metro',
    # Remote / NE
    '781': 'remote', '782': 'remote', '783': 'remote', '784': 'remote', '785': 'remote',
    '786': 'remote', '787': 'remote', '788': 'remote', '790': 'remote', '791': 'remote',
    '792': 'remote', '793': 'remote', '794': 'remote', '795': 'remote', '796': 'remote',
    '797': 'remote', '798': 'remote', '799': 'remote',
    '180': 'remote', '181': 'remote', '190': 'remote', '191': 'remote', '192': 'remote',
    '193': 'remote', '194': 'remote', '744': 'remote',
}


def _get_shipping_zone(pin_code: str) -> str:
    """Determine shipping zone from 6-digit Indian pin code."""
    pin = (pin_code or '').strip()[:6]
    if len(pin) < 3:
        return 'national'
    prefix3 = pin[:3]
    if prefix3 in _PIN_ZONE_MAP:
        return _PIN_ZONE_MAP[prefix3]
    # Fallback: check 2-digit prefix for broad state mapping
    prefix2 = pin[:2]
    if prefix2 in ('70', '71', '72', '73', '74'):
        return 'regional'  # West Bengal
    return 'national'


def _calculate_shipping_paise(pin_code: str) -> int:
    """Calculate shipping cost in paise based on pin code zone."""
    zone = _get_shipping_zone(pin_code)
    return SHIPPING_RATES_PAISE.get(zone, SHIPPING_RATES_PAISE['national'])


def _find_coupon(code: str) -> dict:
    """Look up coupon by code (case-insensitive). Returns coupon dict or empty."""
    code_upper = (code or '').strip().upper()
    for c in CHECKOUT_COUPONS:
        if c.get('code', '').upper() == code_upper and c.get('active', False):
            return c
    return {}


def _calculate_coupon_discount_paise(coupon: dict, subtotal_paise: int) -> int:
    """Calculate coupon discount in paise. Respects min_order and max_discount."""
    if not coupon:
        return 0
    min_order = coupon.get('min_order_paise', 0)
    if subtotal_paise < min_order:
        return 0
    dtype = coupon.get('discount_type', 'percent')
    if dtype == 'flat':
        discount = coupon.get('discount_value', 0)
    else:
        pct = coupon.get('discount_value', 0)
        discount = int(subtotal_paise * pct / 100)
    max_disc = coupon.get('max_discount_paise', 0)
    if max_disc > 0 and discount > max_disc:
        discount = max_disc
    return discount


def _recalculate_order_total(order_details: dict, coupon_discount_paise: int = 0) -> int:
    """Recalculate total_amount from order components + optional coupon discount.
    total = subtotal + shipping + tax - discount - coupon_discount
    All values in paise."""
    order = order_details.get('order', {})
    subtotal = order.get('subtotal', {}).get('value', 0)
    shipping = order.get('shipping', {}).get('value', 0)
    tax = order.get('tax', {}).get('value', 0)
    discount = order.get('discount', {}).get('value', 0)
    total = subtotal + shipping + tax - discount - coupon_discount_paise
    return max(total, 0)


def _handle_checkout_data_exchange(sub_action: str, data: dict,
                                   version: str, request_id: str) -> dict:
    """Route checkout button template data_exchange sub-actions.
    Per Meta Payments API: the decrypted payload has sub_action + data.order_details.
    Response must match Meta's expected schema per sub_action."""

    order_details = data.get('order_details', {})
    input_data = data.get('input', {})
    user_id = input_data.get('user_id', '')

    logger.info(json.dumps({
        'event': 'checkout_data_exchange',
        'sub_action': sub_action,
        'reference_id': order_details.get('reference_id', ''),
        'user_id': user_id,
        'version': version,
        'requestId': request_id,
    }))

    if sub_action == 'get_coupons':
        return _checkout_get_coupons(order_details, input_data, version, request_id)
    elif sub_action == 'apply_coupon':
        return _checkout_apply_coupon(order_details, input_data, version, request_id)
    elif sub_action == 'remove_coupon':
        return _checkout_remove_coupon(order_details, input_data, version, request_id)
    elif sub_action == 'apply_shipping':
        return _checkout_apply_shipping(order_details, input_data, version, request_id)
    else:
        logger.warning(json.dumps({
            'event': 'checkout_unknown_sub_action',
            'sub_action': sub_action, 'requestId': request_id,
        }))
        return {'data': {'error': f'Unknown sub_action: {sub_action}'}}


def _checkout_get_coupons(order_details: dict, input_data: dict,
                          version: str, request_id: str) -> dict:
    """Return available coupons for the order. Meta shows these in the savings offer UI."""
    subtotal_paise = order_details.get('order', {}).get('subtotal', {}).get('value', 0)
    user_id = input_data.get('user_id', '')

    # Filter coupons: only return those where min_order is met
    import time as _time
    now = int(_time.time())
    available = []
    for c in CHECKOUT_COUPONS:
        if not c.get('active', False):
            continue
        valid_until = c.get('valid_until', 0)
        if valid_until > 0 and now > valid_until:
            continue
        if subtotal_paise < c.get('min_order_paise', 0):
            continue
        available.append({
            'code': c['code'],
            'id': c['id'],
            'description': c['description'],
        })

    logger.info(json.dumps({
        'event': 'checkout_get_coupons',
        'user_id': user_id,
        'subtotal_paise': subtotal_paise,
        'coupons_returned': len(available),
        'requestId': request_id,
    }))

    return {
        'version': version,
        'sub_action': 'get_coupons',
        'data': {
            'coupons': available,
        },
    }


def _checkout_apply_coupon(order_details: dict, input_data: dict,
                           version: str, request_id: str) -> dict:
    """Apply a coupon to the order. Recalculate totals and return updated order_details."""
    coupon_input = input_data.get('coupon', {})
    coupon_code = coupon_input.get('code', '')
    coupon = _find_coupon(coupon_code)

    subtotal_paise = order_details.get('order', {}).get('subtotal', {}).get('value', 0)

    if not coupon:
        logger.warning(json.dumps({
            'event': 'checkout_coupon_not_found',
            'code': coupon_code, 'requestId': request_id,
        }))
        # Return order unchanged — Meta will show "coupon not valid"
        total = _recalculate_order_total(order_details, 0)
        order_details['total_amount'] = {'offset': 100, 'value': total}
        return {
            'version': version,
            'sub_action': 'apply_coupon',
            'data': {'order_details': order_details},
        }

    # Special: free shipping coupon
    if coupon.get('_free_shipping'):
        order_details['order']['shipping'] = {'offset': 100, 'value': 0}
        coupon_discount_paise = 0
    else:
        coupon_discount_paise = _calculate_coupon_discount_paise(coupon, subtotal_paise)

    total = _recalculate_order_total(order_details, coupon_discount_paise)
    order_details['total_amount'] = {'offset': 100, 'value': total}

    # Attach coupon to order_details (Meta expects this in response)
    order_details['coupon'] = {
        'code': coupon['code'],
        'discount': {
            'value': coupon_discount_paise,
            'offset': 100,
        },
    }

    logger.info(json.dumps({
        'event': 'checkout_coupon_applied',
        'code': coupon_code,
        'discount_paise': coupon_discount_paise,
        'new_total_paise': total,
        'requestId': request_id,
    }))

    return {
        'version': version,
        'sub_action': 'apply_coupon',
        'data': {'order_details': order_details},
    }


def _checkout_remove_coupon(order_details: dict, input_data: dict,
                            version: str, request_id: str) -> dict:
    """Remove coupon from order. Recalculate totals and return order_details without coupon."""
    removed_code = order_details.get('coupon', {}).get('code', '')

    # If the removed coupon was a free-shipping coupon, restore default shipping
    removed_coupon = _find_coupon(removed_code)
    if removed_coupon and removed_coupon.get('_free_shipping'):
        # Restore shipping based on address if available
        addresses = order_details.get('shipping_info', {}).get('addresses', [])
        if addresses:
            pin = addresses[0].get('in_pin_code', '')
            order_details['order']['shipping'] = {
                'offset': 100, 'value': _calculate_shipping_paise(pin),
            }

    # Remove coupon from order_details
    order_details.pop('coupon', None)

    total = _recalculate_order_total(order_details, 0)
    order_details['total_amount'] = {'offset': 100, 'value': total}

    logger.info(json.dumps({
        'event': 'checkout_coupon_removed',
        'removed_code': removed_code,
        'new_total_paise': total,
        'requestId': request_id,
    }))

    return {
        'version': version,
        'sub_action': 'remove_coupon',
        'data': {'order_details': order_details},
    }


def _checkout_apply_shipping(order_details: dict, input_data: dict,
                             version: str, request_id: str) -> dict:
    """Apply shipping address. Calculate shipping cost by pin code and update order."""
    selected_address = input_data.get('selected_address', {})
    pin_code = selected_address.get('in_pin_code', '')

    # Calculate shipping based on pin code zone
    shipping_paise = _calculate_shipping_paise(pin_code)

    # Check if a free-shipping coupon is active
    existing_coupon = order_details.get('coupon', {})
    coupon_code = existing_coupon.get('code', '')
    coupon = _find_coupon(coupon_code) if coupon_code else {}
    if coupon.get('_free_shipping'):
        shipping_paise = 0

    # Update shipping in order
    order_details['order']['shipping'] = {'offset': 100, 'value': shipping_paise}

    # Update shipping_info with selected_address
    if 'shipping_info' not in order_details:
        order_details['shipping_info'] = {'country': 'IN', 'addresses': []}
    order_details['shipping_info']['selected_address'] = selected_address

    # Recalculate total (with coupon discount if present)
    coupon_discount_paise = existing_coupon.get('discount', {}).get('value', 0)
    total = _recalculate_order_total(order_details, coupon_discount_paise)
    order_details['total_amount'] = {'offset': 100, 'value': total}

    zone = _get_shipping_zone(pin_code)
    logger.info(json.dumps({
        'event': 'checkout_shipping_applied',
        'pin_code': pin_code,
        'zone': zone,
        'shipping_paise': shipping_paise,
        'new_total_paise': total,
        'has_coupon': bool(coupon_code),
        'requestId': request_id,
    }))

    return {
        'version': version,
        'sub_action': 'apply_shipping',
        'data': {'order_details': order_details},
    }


# ═══════════════════════════════════════════════════════════════════════════
# END CHECKOUT BUTTON TEMPLATE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════


def _send_payment_after_flow(phone: str, order_id: str, subject: str, request_id: str,
                             request_number: str = '', payment_ref_id: str = '',
                             preferred_gateway: str = '', payment_config_name: str = '') -> str:
    """
    Create an invoice via invoice-engine, then send payment link through that invoice.
    This integrates Submit Request payments into the common invoice infrastructure
    so they appear in the Pay Flow / Invoices tab alongside all other invoices.
    
    preferred_gateway: 'razorpay' or 'payu' — passed to invoice-engine
    payment_config_name: specific Meta PG config name (e.g. 'WECARE-RAZOR-PAY')
    
    Returns the invoice number (or empty string on failure).
    """
    logger.info(json.dumps({
        'event': 'flow_payment_start',
        'phone': phone[:6] + '***' if phone else 'none',
        'orderId': order_id,
        'subject': subject,
        'requestNumber': request_number,
        'paymentRefId': payment_ref_id,
        'requestId': request_id,
    }))

    if not phone:
        logger.warning(f'[{request_id}] No phone for payment — skipping')
        return ''

    ref_id = payment_ref_id or f'WD-PAY-{uuid.uuid4().hex[:8].upper()}'

    # Look up contactId from DynamoDB
    contact_id = _find_contact_by_phone(phone)
    sender_name = ''
    if contact_id:
        try:
            table = dynamodb.Table(CONTACTS_TABLE)
            resp = table.get_item(Key={'id': contact_id}, ProjectionExpression='#n', ExpressionAttributeNames={'#n': 'name'})
            sender_name = resp.get('Item', {}).get('name', '')
        except Exception as e:
            logger.warning(f'Contact name lookup failed for {contact_id}: {e}')

    # Step 1: Create invoice via invoice-engine Lambda
    invoice_body = {
        'referenceId': ref_id,
        'customerPhone': phone,
        'customerName': sender_name,
        'contactId': contact_id or '',
        'orderId': order_id,
        'entryPoint': 'submit_request_flow',
        'purpose': f'Service Request: {subject}' if subject else 'Service Request',
        'notes': f'Request #{request_number}' if request_number else '',
        'gstin': '19AADFW7431N1ZK',
        'gstRate': 18,
        'items': [{
            'name': 'Service Request',
            'amount': 49,
            'quantity': 1,
            'gstRate': 18,
        }],
    }
    # Add gateway preference from flow registry config
    if preferred_gateway:
        invoice_body['preferredGateway'] = preferred_gateway
    if payment_config_name:
        invoice_body['paymentConfiguration'] = payment_config_name

    try:
        create_resp = lambda_client.invoke(
            FunctionName=INVOICE_ENGINE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'requestContext': {'http': {'method': 'POST'}},
                'rawPath': '/invoices',
                'body': json.dumps(invoice_body),
            })
        )
        create_result = json.loads(create_resp['Payload'].read())
        create_body = json.loads(create_result.get('body', '{}'))
        invoice_id = create_body.get('invoiceId', '')
        invoice_number = create_body.get('invoiceNumber', '')
        is_dedup = create_body.get('deduplicated', False)

        logger.info(json.dumps({
            'event': 'flow_invoice_created',
            'invoiceId': invoice_id,
            'invoiceNumber': invoice_number,
            'referenceId': ref_id,
            'deduplicated': is_dedup,
            'phone': phone[:6] + '***',
            'requestId': request_id,
        }))

        if not invoice_id:
            logger.error(json.dumps({
                'event': 'flow_invoice_create_failed',
                'response': create_body,
                'requestId': request_id,
            }))
            # Fallback: send payment directly via outbound (old behavior)
            _send_payment_direct_fallback(phone, order_id, subject, ref_id, contact_id, request_id)
            return ''

        # Store invoiceId on the SubmitRequest record
        try:
            sr_table = dynamodb.Table(SUBMIT_REQUESTS_TABLE)
            sr_resp = sr_table.query(
                IndexName='paymentReferenceId',
                KeyConditionExpression='paymentReferenceId = :ref',
                ExpressionAttributeValues={':ref': ref_id},
                Limit=1,
            )
            sr_items = sr_resp.get('Items', [])
            if sr_items:
                sr_table.update_item(
                    Key={'id': sr_items[0]['id']},
                    UpdateExpression='SET invoiceId = :inv, invoiceNumber = :inum, updatedAt = :u',
                    ExpressionAttributeValues={
                        ':inv': invoice_id,
                        ':inum': invoice_number,
                        ':u': Decimal(str(int(time.time()))),
                    },
                )
        except Exception as link_err:
            logger.warning(json.dumps({
                'event': 'flow_invoice_link_error',
                'error': str(link_err),
                'requestId': request_id,
            }))

        # Step 2: Send payment link via invoice-engine (uses common infrastructure)
        send_resp = lambda_client.invoke(
            FunctionName=INVOICE_ENGINE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'requestContext': {'http': {'method': 'POST'}},
                'rawPath': '/invoices/send-payment-link',
                'body': json.dumps({
                    'invoiceId': invoice_id,
                    'phoneNumberId': PHONE1_ID,
                }),
            })
        )
        send_result = json.loads(send_resp['Payload'].read())
        send_status = send_result.get('statusCode', 0)

        logger.info(json.dumps({
            'event': 'flow_payment_link_sent',
            'invoiceId': invoice_id,
            'invoiceNumber': invoice_number,
            'referenceId': ref_id,
            'phone': phone[:6] + '***',
            'statusCode': send_status,
            'requestId': request_id,
        }))

        return invoice_number

    except Exception as e:
        logger.error(json.dumps({
            'event': 'flow_invoice_payment_error',
            'phone': phone[:6] + '***',
            'error': str(e),
            'requestId': request_id,
        }))
        # Fallback: send payment directly via outbound (old behavior)
        try:
            _send_payment_direct_fallback(phone, order_id, subject, ref_id, contact_id, request_id)
        except Exception as fb_err:
            logger.error(json.dumps({
                'event': 'flow_payment_fallback_error',
                'error': str(fb_err),
                'requestId': request_id,
            }))
        return ''


def _send_payment_direct_fallback(phone: str, order_id: str, subject: str,
                                   ref_id: str, contact_id: str, request_id: str):
    """Fallback: send payment directly via outbound-whatsapp if invoice-engine fails."""
    amount_paise = 4900
    gst_rate = 18
    gst_paise = round(amount_paise * gst_rate / 100)

    payload = {
        'body': json.dumps({
            'contactId': contact_id or '',
            'recipientPhone': phone if not contact_id else '',
            'phoneNumberId': PHONE1_ID,
            'isInteractivePayment': True,
            'orderDetails': {
                'reference_id': ref_id,
                'type': 'digital-goods',
                'currency': 'INR',
                'itemName': 'Service Request',
                'quantity': 1,
                'gstRate': gst_rate,
                'gstin': '19AADFW7431N1ZK',
                'orderId': order_id,
                'order': {
                    'status': 'pending',
                    'items': [{
                        'retailer_id': 'SR-REQUEST',
                        'name': 'Service Request',
                        'amount': {'value': amount_paise, 'offset': 100},
                        'quantity': 1,
                        'gstRate': gst_rate,
                    }],
                    'subtotal': {'value': amount_paise, 'offset': 100},
                    'discount': {'value': 0, 'offset': 100, 'description': 'None'},
                    'shipping': {'value': 0, 'offset': 100, 'description': 'N/A'},
                    'tax': {'value': gst_paise, 'offset': 100, 'description': f'GST {gst_rate}%'},
                },
            }
        })
    }

    response = lambda_client.invoke(
        FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
        InvocationType='Event',
        Payload=json.dumps(payload)
    )

    logger.info(json.dumps({
        'event': 'flow_payment_fallback_sent',
        'phone': phone[:6] + '***',
        'referenceId': ref_id,
        'lambdaStatus': response.get('StatusCode'),
        'requestId': request_id,
    }))


def _send_flow_confirmation(phone: str, order_id: str, subject: str, request_id: str,
                            request_number: str = '', payment_ref_id: str = '',
                            invoice_number: str = ''):
    """Send a WhatsApp text confirmation after the Submit Request flow completes."""
    if not phone:
        return
    try:
        inv_line = f'*Invoice:* {invoice_number}\n' if invoice_number else ''
        msg = (
            '\u2705 *Request Submitted Successfully*\n\n'
            f'*Request No:* {request_number}\n'
            f'{inv_line}'
            f'*Payment Ref:* {payment_ref_id}\n'
            f'*Order:* {order_id}\n'
            f'*Subject:* {subject}\n\n'
            'Please complete the payment using the payment card sent above \u2b06\ufe0f\n'
            'Our team will review your request within 24 hours.\n\n'
            '_Thank you for choosing WECARE.DIGITAL_'
        )
        payload = {
            'body': json.dumps({
                'recipientPhone': phone,
                'phoneNumberId': PHONE1_ID,
                'content': msg,
            })
        }
        lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        logger.info(json.dumps({
            'event': 'flow_confirmation_sent',
            'phone': phone[:6] + '***',
            'requestId': request_id,
        }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'flow_confirmation_error',
            'error': str(e),
            'requestId': request_id,
        }))


def _find_contact_by_phone(phone: str) -> str:
    """Look up contactId from DynamoDB Contacts table by phone number using GSI."""
    if not phone:
        return ''
    try:
        # Normalize: strip + and spaces
        clean = phone.replace('+', '').replace(' ', '').replace('-', '')
        with_plus = f'+{clean}'
        table = dynamodb.Table(CONTACTS_TABLE)
        # Try with + prefix first (contacts are stored as +91XXXXXXXXXX), then without
        for variant in [with_plus, clean]:
            try:
                resp = table.query(
                    IndexName='phone-index',
                    KeyConditionExpression='phone = :p',
                    ExpressionAttributeValues={':p': variant},
                    Limit=1,
                    ProjectionExpression='id'
                )
                items = resp.get('Items', [])
                if items:
                    return items[0].get('id', '')
            except Exception as e:
                logger.debug(f'Contact query variant failed: {e}')
    except Exception as e:
        logger.warning(f'Contact lookup failed for {phone[:6]}***: {e}')
    return ''


def _fetch_orders_for_flow(phone: str, email: str) -> list:
    """
    Fetch WD-ORD numbers for a user by phone or email.
    Uses the wix-store Lambda (eCommerce Orders API) for rich order data.
    Falls back to Wix Velo /_functions/orders if Lambda call fails.
    Returns list of {id, title} for WhatsApp Flow dropdown.
    """
    order_ids = []

    # ── Method 1: Use wix-store Lambda (rich data) ──
    try:
        search_params = {'limit': '20'}
        if email:
            search_params['email'] = email

        wix_resp = lambda_client.invoke(
            FunctionName=os.environ.get('WIX_STORE_FUNCTION', 'wecare-wix-store'),
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'requestContext': {'http': {'method': 'GET'}},
                'rawPath': '/wix-store/orders',
                'queryStringParameters': search_params,
                'headers': {'origin': 'https://admin.wecare.digital'},
            })
        )
        wix_result = json.loads(wix_resp['Payload'].read())
        wix_body = json.loads(wix_result.get('body', '{}'))
        orders = wix_body.get('orders', [])

        # Normalize phone for matching
        clean_phone = ''
        clean_phone_short = ''
        if phone:
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
            clean_phone_short = clean_phone[2:] if len(clean_phone) > 10 and clean_phone.startswith('91') else clean_phone

        for order in orders:
            summary = order.get('_summary', {})
            wd_id = order.get('customOrderNumber', '') or summary.get('customOrderNumber', '')
            if not wd_id or not wd_id.startswith('WD-ORD'):
                continue

            # Match by phone if no email filter
            if not email and clean_phone:
                billing_phone = (summary.get('billingPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                buyer_email = summary.get('buyerEmail', '')
                if clean_phone_short not in billing_phone and clean_phone not in billing_phone:
                    continue

            # Build rich title: "WD-ORD-A1B2C3D4 — ₹499 — 2 items — 22 Mar"
            total = summary.get('totalAmount', '0')
            item_count = summary.get('lineItemCount', 0)
            created = summary.get('createdDate', '')
            date_str = ''
            if created:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    date_str = dt.strftime('%d %b %Y')
                except Exception:
                    date_str = created[:10]

            # First item name for context
            items = summary.get('lineItems', [])
            first_item = items[0].get('name', '') if items else ''
            title_parts = [wd_id]
            if total and total != '0':
                title_parts.append(f'₹{float(total):.0f}')
            if first_item:
                title_parts.append(first_item[:25])
            if date_str:
                title_parts.append(date_str)

            order_ids.append({
                'id': wd_id,
                'title': ' — '.join(title_parts),
            })

        if order_ids:
            logger.info(json.dumps({
                'action': 'fetch_orders_for_flow', 'source': 'wix_store_lambda',
                'count': len(order_ids), 'phone': (phone or '')[:6] + '***',
            }))
            return order_ids

    except Exception as e:
        logger.warning(json.dumps({'action': 'fetch_orders_wix_lambda_failed', 'error': str(e)}))

    # ── Method 2: Fallback to Wix Velo /_functions/orders ──
    try:
        wix_site_url = os.environ.get('WIX_SITE_URL', 'https://www.wecare.digital')
        api_key = os.environ.get('WIX_API_KEY', '')
        if not api_key:
            try:
                resp = secrets_client.get_secret_value(SecretId='wecare/wix-api-key')
                api_key = resp.get('SecretString', '').strip()
            except Exception:
                pass

        clean_phone = ''
        clean_phone_short = ''
        if phone:
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
            clean_phone_short = clean_phone[2:] if len(clean_phone) > 10 and clean_phone.startswith('91') else clean_phone

        query_param = f'email={urllib.parse.quote(email)}' if email else ''
        url = f'{wix_site_url}/_functions/orders?limit=50&{query_param}'
        headers = {}
        if api_key:
            headers['x-api-key'] = api_key
        req = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(req, timeout=12) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            for order in result.get('orders', []):
                wd_id = order.get('customOrderNumber', '') or (order.get('customField', {}) or {}).get('value', '')
                if not wd_id or not wd_id.startswith('WD-ORD'):
                    continue
                if not email and clean_phone:
                    order_phone = (order.get('buyerPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                    if clean_phone_short not in order_phone and clean_phone not in order_phone:
                        continue
                order_ids.append({'id': wd_id, 'title': wd_id})

        logger.info(json.dumps({
            'action': 'fetch_orders_for_flow', 'source': 'wix_velo_fallback',
            'count': len(order_ids), 'phone': (phone or '')[:6] + '***',
        }))
    except Exception as e:
        logger.error(json.dumps({'action': 'fetch_orders_for_flow', 'error': str(e)}))

    return order_ids


def _list_submit_requests(params: Dict) -> Dict:
    """List submit request submissions from DynamoDB."""
    try:
        table = dynamodb.Table(SUBMIT_REQUESTS_TABLE)
        limit = min(int(params.get('limit', '100')), 500)
        payment_status = params.get('paymentStatus', '')

        if payment_status:
            resp = table.query(
                IndexName='paymentStatus',
                KeyConditionExpression='paymentStatus = :s',
                ExpressionAttributeValues={':s': payment_status},
                ScanIndexForward=False,
                Limit=limit,
            )
        else:
            resp = table.scan(Limit=limit)

        items = resp.get('Items', [])
        now = int(time.time())
        # Convert Decimal to int/float for JSON + add computed fields
        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = int(v) if v == int(v) else float(v)
            # Add days old + expiry flag for pending payments
            created = item.get('createdAt', 0)
            if created:
                days_old = (now - created) // 86400
                item['daysOld'] = days_old
                # Mark as expired if pending for more than 7 days
                if item.get('paymentStatus') == 'pending' and days_old > 7:
                    item['isExpired'] = True

        # Sort by createdAt descending
        items.sort(key=lambda x: x.get('createdAt', 0), reverse=True)

        return _resp(200, {'requests': items, 'count': len(items)})
    except Exception as e:
        logger.error(f'List submit requests error: {e}')
        return _resp(500, {'error': str(e)})


def _log_flow_event(flow_token: str, phone: str, action: str, screen: str,
                    data_keys: list, request_id: str, data: dict = None):
    """
    Log a flow interaction event to SubmitRequestsTable for audit trail.
    Uses type='flow_log' to distinguish from actual submissions.
    Captures full submitted data for comprehensive logging.
    """
    try:
        now = int(time.time())
        table = dynamodb.Table(SUBMIT_REQUESTS_TABLE)
        item = {
            'id': f'flog-{uuid.uuid4().hex[:12]}',
            'type': 'flow_log',
            'flowToken': flow_token,
            'phone': phone,
            'action': action,
            'screen': screen,
            'dataKeys': data_keys,
            'requestId': request_id,
            'createdAt': Decimal(str(now)),
        }

        # Capture full submitted data for comprehensive flow logs
        if data and isinstance(data, dict):
            # Store individual known fields for easy querying
            for field in ('order_id', 'subject', 'description', 'email'):
                if data.get(field):
                    item[field] = str(data[field])
            # Store full data snapshot as JSON string (for any extra fields)
            try:
                item['flowData'] = json.dumps(data, default=str)
            except Exception as e:
                logger.debug(f'Flow data serialization failed: {e}')

        table.put_item(Item={k: v for k, v in item.items() if v is not None and v != ''})
    except Exception as e:
        logger.warning(f'Flow log write failed: {e}')


def _list_flow_logs(params: Dict) -> Dict:
    """List flow interaction logs from SubmitRequestsTable (type=flow_log)."""
    try:
        table = dynamodb.Table(SUBMIT_REQUESTS_TABLE)
        limit = min(int(params.get('limit', '200')), 500)
        phone_filter = params.get('phone', '')

        # Scan for flow_log type records with full pagination
        filter_expr = '#t = :t'
        expr_names = {'#t': 'type'}
        expr_values = {':t': 'flow_log'}

        if phone_filter:
            filter_expr += ' AND contains(phone, :ph)'
            expr_values[':ph'] = phone_filter.replace('+', '').replace(' ', '')

        items = []
        scan_kwargs = {
            'FilterExpression': filter_expr,
            'ExpressionAttributeNames': expr_names,
            'ExpressionAttributeValues': expr_values,
        }
        while len(items) < limit:
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get('Items', []))
            if 'LastEvaluatedKey' not in resp:
                break
            scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

        # Trim to limit
        items = items[:limit]

        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = int(v) if v == int(v) else float(v)

        items.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        return _resp(200, {'logs': items, 'count': len(items)})
    except Exception as e:
        logger.error(f'List flow logs error: {e}')
        return _resp(500, {'error': str(e)})


def _handle_async_post_submit(event: Dict, request_id: str) -> Dict:
    """
    Handle async post-submit actions: create invoice, send payment link, send confirmation.
    Called via async Lambda invocation from the REVIEW screen handler to avoid blocking
    the flow data_exchange response (Meta has a timeout).
    """
    phone = event.get('phone', '')
    order_id = event.get('order_id', '')
    subject = event.get('subject', '')
    request_number = event.get('request_number', '')
    payment_ref_id = event.get('payment_ref_id', '')
    preferred_gateway = event.get('preferred_gateway', '')
    payment_config_name = event.get('payment_config_name', '')

    logger.info(json.dumps({
        'event': 'async_post_submit_start',
        'phone': phone[:6] + '***' if phone else '',
        'requestNumber': request_number,
        'requestId': request_id,
    }))

    # Step 1: Create invoice + send payment link
    invoice_number = ''
    try:
        invoice_number = _send_payment_after_flow(
            phone=phone, order_id=order_id,
            subject=subject, request_id=request_id,
            request_number=request_number,
            payment_ref_id=payment_ref_id,
            preferred_gateway=preferred_gateway,
            payment_config_name=payment_config_name
        ) or ''
    except Exception as pay_err:
        logger.error(json.dumps({
            'event': 'async_payment_error',
            'error': str(pay_err),
            'requestId': request_id,
        }))

    # Step 2: Send confirmation text
    try:
        _send_flow_confirmation(
            phone=phone, order_id=order_id, subject=subject,
            request_id=request_id, request_number=request_number,
            payment_ref_id=payment_ref_id,
            invoice_number=invoice_number
        )
    except Exception as conf_err:
        logger.error(json.dumps({
            'event': 'async_confirmation_error',
            'error': str(conf_err),
            'requestId': request_id,
        }))

    # Step 3: Update FlowSubmissionsTable with invoiceId (if invoice was created)
    if invoice_number and payment_ref_id:
        try:
            fs_table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
            fs_resp = fs_table.query(
                IndexName='paymentRefId',
                KeyConditionExpression='paymentRefId = :ref',
                ExpressionAttributeValues={':ref': payment_ref_id},
                Limit=1,
            )
            fs_items = fs_resp.get('Items', [])
            if fs_items:
                fs_table.update_item(
                    Key={'submissionId': fs_items[0]['submissionId']},
                    UpdateExpression='SET invoiceId = :inv, updatedAt = :u',
                    ExpressionAttributeValues={
                        ':inv': invoice_number,
                        ':u': Decimal(str(int(time.time()))),
                    },
                )
                logger.info(f'FlowSubmission updated with invoiceId for paymentRefId={payment_ref_id}')
        except Exception as fs_err:
            logger.warning(f'FlowSubmission invoice link failed: {fs_err}')

    return {'statusCode': 200, 'headers': cors_headers(origin), 'body': json.dumps({'status': 'ok'})}


# ============================================================================
# HANDLER
# ============================================================================
# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def _verify_webhook_signature(event: Dict[str, Any], request_id: str) -> bool:
    """
    Verify X-Hub-Signature-256 header on incoming Meta webhooks.
    Meta signs every webhook POST with HMAC-SHA256 using the app secret.
    Returns True if valid, False if invalid.
    Fails open (returns True) only if app_secret is not configured.
    """
    headers = event.get('headers', {})
    signature_header = (
        headers.get('x-hub-signature-256')
        or headers.get('X-Hub-Signature-256')
        or ''
    )
    if not signature_header:
        logger.warning(json.dumps({'event': 'webhook_no_signature', 'requestId': request_id}))
        return False

    app_secret = _get_app_secret()
    if not app_secret:
        logger.error(json.dumps({'event': 'webhook_no_app_secret', 'requestId': request_id}))
        return True  # Fail open only if secret not configured (dev/test)

    raw_body = event.get('body', '')
    if event.get('isBase64Encoded') and raw_body:
        import base64
        raw_body = base64.b64decode(raw_body).decode('utf-8')

    expected_sig = 'sha256=' + hmac.new(
        app_secret.encode('utf-8'),
        (raw_body or '').encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    is_valid = hmac.compare_digest(expected_sig, signature_header)
    if not is_valid:
        logger.warning(json.dumps({
            'event': 'webhook_signature_mismatch',
            'expectedPrefix': expected_sig[:20],
            'receivedPrefix': signature_header[:20],
            'requestId': request_id,
        }))
    return is_valid


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)

    # Handle async post-submit actions (invoked by REVIEW screen handler)
    if event.get('_async_action') == 'flow_post_submit':
        return _handle_async_post_submit(event, request_id)

    rc = event.get('requestContext', {})
    http = rc.get('http', {})
    method = http.get('method', event.get('httpMethod', 'GET'))
    path = http.get('path', '') or event.get('rawPath', '') or event.get('path', '')
    params = event.get('queryStringParameters') or {}

    if method == 'OPTIONS':
        return _resp(200, {})

    # P0 Security: Verify X-Hub-Signature-256 on flow-data and checkout-data webhook POSTs from Meta
    if method == 'POST' and ('/flow-data' in path or '/checkout-data' in path):
        if not _verify_webhook_signature(event, request_id):
            logger.warning(json.dumps({'event': 'flow_data_signature_rejected', 'requestId': request_id}))
            return _resp(401, {'error': 'Invalid webhook signature'})

    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
    except (json.JSONDecodeError, TypeError, ValueError):
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

        elif '/assigned-users' in path:
            waba_id = params.get('wabaId') or body.get('wabaId')
            if not waba_id:
                return _resp(400, {'error': 'wabaId required'})
            if method == 'GET':
                return _list_assigned_users(waba_id, params)
            elif method == 'POST':
                return _add_assigned_user(waba_id, body)
            elif method == 'DELETE':
                return _remove_assigned_user(waba_id, body)

        elif '/bot' in path:
            bot_id = params.get('botId') or body.get('botId')
            if not bot_id:
                return _resp(400, {'error': 'botId required'})
            if method == 'GET':
                return _get_bot_details(bot_id, params)

        elif '/groups/participants' in path:
            return _manage_group_participants(params.get('groupId') or body.get('groupId') or '', body)
        elif '/groups/send' in path:
            return _send_group_message(
                params.get('phoneId') or body.get('phoneId') or '',
                params.get('groupId') or body.get('groupId') or '', body)
        elif '/groups/image' in path:
            group_id = params.get('groupId') or body.get('groupId') or ''
            image_url = body.get('imageUrl', '')
            return _set_group_image(group_id, image_url)
        elif '/groups/invite-link' in path:
            group_id = params.get('groupId') or body.get('groupId') or ''
            if method == 'GET':
                return _get_group_invite_link(group_id)
            elif method == 'POST':
                return _reset_group_invite_link(group_id)
        elif '/groups/join-requests' in path:
            group_id = params.get('groupId') or body.get('groupId') or ''
            if method == 'GET':
                return _get_group_join_requests(group_id)
            elif method == 'POST':
                return _approve_group_join_requests(group_id, body)
            elif method == 'DELETE':
                return _reject_group_join_requests(group_id, body)
        elif '/groups' in path:
            waba_id = params.get('wabaId') or body.get('wabaId') or ''
            group_id = params.get('groupId') or body.get('groupId')
            phone_id = params.get('phoneId') or body.get('phoneId')
            if method == 'GET':
                return _get_group(group_id) if group_id else _list_groups(waba_id, phone_id)
            elif method == 'POST':
                return _create_group(phone_id or '', body)
            elif method == 'PUT':
                return _update_group(group_id or '', body)
            elif method == 'DELETE':
                return _delete_group(group_id or '')

        elif '/interactive-list' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
            return _send_interactive_list(phone_id, body)

        elif '/calling-settings' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
            if method == 'GET':
                return _get_calling_settings(phone_id)
            return _update_calling_settings(phone_id, body)

        elif '/payment-config/check' in path:
            waba_id = params.get('wabaId') or body.get('wabaId')
            return _check_payment_gateway(waba_id)

        elif '/payment-lookup' in path:
            phone_id = params.get('phoneId') or body.get('phoneId', '')
            config_name = params.get('configName') or body.get('configName', '')
            reference_id = params.get('referenceId') or body.get('referenceId', '')
            return _payment_lookup(phone_id, config_name, reference_id)

        elif '/payment-refund' in path:
            phone_id = body.get('phoneId', '')
            reference_id = body.get('referenceId', '')
            config_name = body.get('configName', '')
            amount_paise = int(body.get('amountPaise', 0))
            speed = body.get('speed', 'normal')
            return _payment_refund(phone_id, reference_id, config_name, amount_paise, speed)

        elif '/payment-config' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
            if method == 'GET':
                return _get_payment_config(phone_id)

        elif '/phone-settings' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
            if method == 'GET':
                return _get_phone_settings(phone_id)
            return _update_phone_settings(phone_id, body)

        elif '/username/suggestions' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
            return _get_username_suggestions(phone_id)

        elif '/username' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
            if method == 'GET':
                return _get_username(phone_id)
            elif method == 'POST':
                return _claim_username(phone_id, body)
            elif method == 'DELETE':
                return _delete_username(phone_id)

        elif '/block-users' in path:
            waba_id = params.get('wabaId') or body.get('wabaId') or ''
            if not waba_id:
                return _resp(400, {'error': 'wabaId required'})
            if method == 'GET':
                return _get_blocked_users(waba_id)
            elif method == 'POST':
                return _block_users(waba_id, body)

        elif '/unblock-users' in path:
            waba_id = params.get('wabaId') or body.get('wabaId') or ''
            if not waba_id:
                return _resp(400, {'error': 'wabaId required'})
            if method == 'POST':
                return _unblock_users(waba_id, body)

        elif '/flow-data' in path:
            if method == 'POST':
                return _handle_flow_data(body, request_id, origin)
            return _resp(405, {'error': 'POST only'})

        # Dedicated checkout endpoint (same handler, separate URL for Meta linking)
        # Link this URL with payment configuration via Meta support:
        # https://api.wecare.digital/wa-business/checkout-data
        elif '/checkout-data' in path:
            if method == 'POST':
                return _handle_flow_data(body, request_id, origin)
            return _resp(405, {'error': 'POST only'})

        # Flow Management Engine routes
        elif '/flow-registry' in path:
            if method == 'GET':
                return _list_flow_registry(params)
            elif method == 'POST' or method == 'PUT':
                return _upsert_flow_registry(body)
            return _resp(405, {'error': 'GET/POST/PUT only'})

        elif '/flow-submissions/stats' in path:
            if method == 'GET':
                return _get_flow_submission_stats(params)
            return _resp(405, {'error': 'GET only'})

        elif '/flow-submissions/export' in path:
            if method == 'GET':
                return _export_submissions_csv(params)
            return _resp(405, {'error': 'GET only'})

        elif '/flow-submissions' in path:
            if method == 'GET':
                return _list_flow_submissions(params)
            return _resp(405, {'error': 'GET only'})

        elif '/flow-sla-check' in path:
            if method == 'POST':
                return _check_sla_and_escalate(body)
            return _resp(405, {'error': 'POST only'})

        elif '/flow-customer-journey' in path:
            if method == 'GET':
                return _get_customer_journey(params)
            return _resp(405, {'error': 'GET only'})

        elif '/flow-clone' in path:
            if method == 'POST':
                return _clone_flow_to_waba(body)
            return _resp(405, {'error': 'POST only'})

        elif '/flow-version-health' in path:
            if method == 'GET':
                return _check_flow_version_health(params)
            return _resp(405, {'error': 'GET only'})

        elif '/submit-requests' in path:
            if method == 'GET':
                return _list_submit_requests(params)
            return _resp(405, {'error': 'GET only'})

        elif '/flow-logs' in path:
            if method == 'GET':
                return _list_flow_logs(params)
            return _resp(405, {'error': 'GET only'})

        return _resp(404, {'error': f'Unknown path: {path}'})
    except Exception as e:
        logger.exception(f'[{request_id}] Error')
        return _resp(500, {'error': str(e)})
