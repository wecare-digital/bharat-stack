"""
WhatsApp Business API Lambda
Handles: Business Profile, Flows, Webhooks, Groups, Payment Config
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
  GET       /wa-business/payment-config → Get payment configuration for phone
  POST      /wa-business/flow-data     → WhatsApp Flow data_exchange endpoint
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

WABA1_ID = '1912405516040025'
WABA2_ID = '1633959101297902'
PHONE1_META_ID = '960395407161423'
PHONE2_META_ID = '997428863451102'

# All IDs that belong to WABA2
WABA2_IDS = {WABA2_ID, PHONE2_META_ID}

# DynamoDB tables for order lookups (flow-data endpoint)
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
ORDER_IDS_TABLE = os.environ.get('WIX_ORDER_IDS_TABLE', 'base-wecare-digital-WixOrderIds')

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
    """Get current calling settings for a phone number."""
    result = _graph_api(f'{phone_id}/settings', params={
        'fields': 'calling'
    }, phone_id=phone_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'settings': result})


def _update_calling_settings(phone_id: str, body: Dict) -> Dict:
    """
    Enable or update calling settings on a phone number.
    Body: {
      callIconVisibility: 'default' | 'disable_all',
      restrictToCountries: ['IN', 'AE'],  // optional
      callHours: { timezone, sun, mon, ... },  // optional
      callbackRequest: { enabled: bool, bodyText: str }  // optional
    }
    """
    calling: Dict = {}

    visibility = body.get('callIconVisibility', 'default')
    calling['call_icon_visibility'] = visibility

    countries = body.get('restrictToCountries')
    if countries:
        calling['restrict_to_user_countries'] = countries

    call_hours = body.get('callHours')
    if call_hours:
        calling['call_hours'] = call_hours

    callback = body.get('callbackRequest')
    if callback:
        calling['callback_request'] = callback

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
# PAYMENT CONFIGURATION
# +91 9330994400 (WABA 1912405516040025): WECARE-DIGITAL (Razorpay Gateway + UPI)
# +91 9903300044 (WABA 1633959101297902): ManishAgarwal_Pay (Razorpay Gateway + UPI)
# MCC: 4722 | Purpose Code: 03 | Razorpay MID: acc_HDfub6wOfQybuH
# UPI ID: wecaredigital83.rzp@icici
# ============================================================================
PAYMENT_CONFIGS = {
    PHONE1_META_ID: {
        'phone': '+91 9330994400',
        'wabaId': '1728153881476046',
        'configs': [
            {'name': 'WECARE_PAY', 'status': 'active', 'type': 'payment_gateway', 'gateway': 'razorpay', 'mid': 'acc_HDfub6wOfQybuH', 'upiId': 'wecaredigital83.rzp@icici'},
            {'name': 'WECARE_UPI', 'status': 'active', 'type': 'upi', 'gateway': 'razorpay', 'mid': 'acc_HDfub6wOfQybuH', 'upiId': 'wecaredigital83.rzp@icici'},
        ],
        'mcc': '4722',
        'purposeCode': '03',
    },
    PHONE2_META_ID: {
        'phone': '+91 9903300044',
        'wabaId': '1728153881476046',
        'configs': [
            {'name': 'WECARE_PAY', 'status': 'active', 'type': 'payment_gateway', 'gateway': 'razorpay', 'mid': 'acc_HDfub6wOfQybuH', 'upiId': 'wecaredigital83.rzp@icici'},
            {'name': 'WECARE_UPI', 'status': 'active', 'type': 'upi', 'gateway': 'razorpay', 'mid': 'acc_HDfub6wOfQybuH', 'upiId': 'wecaredigital83.rzp@icici'},
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
# FLOW DATA EXCHANGE (WhatsApp Flows)
# ============================================================================
def _handle_flow_data(body: Dict, request_id: str) -> Dict:
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
        # `screen` = current screen the user is on (top-level field from Meta).
        # Meta strips "screen" from payload data — so route by current screen ID.

        if screen == 'ORDER_SELECT':
            # User selected an order and tapped Continue → show REQUEST_FORM
            selected_order = data.get('order_id', '')
            response_payload = {
                'screen': 'REQUEST_FORM',
                'data': {
                    'order_id': selected_order,
                    'request_types': [
                        {'id': 'return', 'title': 'Return'},
                        {'id': 'exchange', 'title': 'Exchange'},
                        {'id': 'support', 'title': 'Support'},
                        {'id': 'other', 'title': 'Other'},
                    ],
                }
            }

        elif screen == 'REQUEST_FORM':
            # User filled the form and tapped Submit → show SUCCESS
            order_id = data.get('order_id', '')
            request_type = data.get('request_type', '')
            subject = data.get('subject', '')
            description = data.get('description', '')
            logger.info(json.dumps({
                'flow_submit': True, 'order_id': order_id,
                'request_type': request_type, 'subject': subject,
                'requestId': request_id,
            }))
            response_payload = {
                'screen': 'SUCCESS',
                'data': {
                    'message': f'Request submitted for {order_id}. We will get back to you shortly.',
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
            'headers': CORS_HEADERS,
            'body': encrypted_response,
        }
    except Exception as e:
        logger.error(f'[{request_id}] Flow encryption failed: {e}')
        return _resp(500, {'error': 'Encryption failed'})



def _fetch_orders_for_flow(phone: str, email: str) -> list:
    """
    Fetch WD-ORD numbers for a user by phone or email.
    Queries the Wix /_functions/orders endpoint which returns orders with
    customOrderNumber (WD-ORD) and buyerPhone/buyerEmail for matching.
    Returns list of {id, title} for WhatsApp Flow dropdown.
    """
    order_ids = []

    try:
        wix_site_url = os.environ.get('WIX_SITE_URL', 'https://www.wecare.digital')

        # Get API key from env or Secrets Manager for Wix auth
        api_key = os.environ.get('WIX_API_KEY', '')
        if not api_key:
            try:
                resp = secrets_client.get_secret_value(SecretId='wecare/wix-api-key')
                api_key = resp.get('SecretString', '').strip()
            except Exception:
                pass

        # Normalize phone for matching
        clean_phone = ''
        if phone:
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
            # Strip country code if present (91XXXXXXXXXX → XXXXXXXXXX)
            if len(clean_phone) > 10 and clean_phone.startswith('91'):
                clean_phone_short = clean_phone[2:]
            else:
                clean_phone_short = clean_phone

        # Query by email first (more reliable), then by phone
        query_param = ''
        if email:
            query_param = f'email={urllib.parse.quote(email)}'
        # Always fetch a reasonable batch
        url = f'{wix_site_url}/_functions/orders?limit=50&{query_param}'

        headers = {}
        if api_key:
            headers['x-api-key'] = api_key

        req = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(req, timeout=12) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            orders = result.get('orders', [])

            for order in orders:
                wd_id = order.get('customOrderNumber', '') or (order.get('customField', {}) or {}).get('value', '')
                if not wd_id or not wd_id.startswith('WD-ORD'):
                    continue

                # Match by phone if no email filter was used
                if not email and clean_phone:
                    order_phone = (order.get('buyerPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                    if clean_phone_short not in order_phone and clean_phone not in order_phone:
                        continue

                order_ids.append({'id': wd_id, 'title': wd_id})

        logger.info(json.dumps({
            'action': 'fetch_orders_for_flow', 'source': 'wix',
            'count': len(order_ids), 'phone': (phone or '')[:6] + '***',
            'email': (email or '')[:3] + '***',
        }))

    except Exception as e:
        logger.error(json.dumps({'action': 'fetch_orders_for_flow', 'error': str(e)}))

    return order_ids


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

        elif '/flow-data' in path:
            if method == 'POST':
                return _handle_flow_data(body, request_id)
            return _resp(405, {'error': 'POST only'})

        return _resp(404, {'error': f'Unknown path: {path}'})
    except Exception as e:
        logger.exception(f'[{request_id}] Error')
        return _resp(500, {'error': str(e)})
