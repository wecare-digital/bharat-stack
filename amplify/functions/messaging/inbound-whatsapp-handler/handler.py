"""
Inbound WhatsApp Handler Lambda Function

Purpose: Process SNS notifications for WhatsApp messages
Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.12, 15.4, 15.7

Parses Meta webhook event format, stores messages, downloads media,
updates contact timestamps for 24-hour customer service window.
Tracks which WABA/phone number received the message.
Integrates with AI automation when enabled in SystemConfig.
"""

import os
import json
import uuid
import time
import logging
import hmac
import hashlib
import boto3
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from decimal import Decimal

# Configure logging
from lambda_utils.logging import get_logger
from lambda_utils.response import extract_origin
from lambda_utils.privacy import mask_phone, redact_pii
from lambda_utils.validation import normalize_phone
from lambda_utils.message_store import put_message  # unified MessagesTable dual-write
from lambda_utils.automation import evaluate_rules  # cross-channel auto-reply rules
try:
    from lambda_utils import partner_billing  # per-tenant prepaid metering (optional)
except Exception:  # noqa: BLE001
    partner_billing = None

# Sub-modules (monolith decomposition)
from modules.content import extract_content as _extract_content_v2
from modules.content import extract_unsupported_content as _extract_unsupported_content_v2

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sqs = boto3.client('sqs', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables - use actual table names
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'stack-wecare-digital-WhatsAppInboundTable')
# Canonical unified message table (status mirror target).
UNIFIED_MESSAGES_TABLE = os.environ.get('UNIFIED_MESSAGES_TABLE', 'stack-wecare-digital-MessagesTable')
MEDIA_FILES_TABLE = os.environ.get('MEDIA_FILES_TABLE', 'stack-wecare-digital-MediaFilesTable')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
FLOW_SUBMISSIONS_TABLE = os.environ.get('FLOW_SUBMISSIONS_TABLE', 'stack-wecare-digital-FlowSubmissionTable')
AI_INTERACTIONS_TABLE = os.environ.get('AI_INTERACTIONS_TABLE', 'stack-wecare-digital-AIInteractionsTable')
INVOICES_TABLE = os.environ.get('INVOICES_TABLE', 'stack-wecare-digital-InvoicesTable')
INBOUND_DLQ_URL = os.environ.get('INBOUND_DLQ_URL', '')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
MEDIA_PREFIX = os.environ.get('MEDIA_INBOUND_PREFIX', 'stack/whatsapp-media/incoming/')
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
SUBMIT_REQUESTS_TABLE = os.environ.get('SUBMIT_REQUESTS_TABLE', 'stack-wecare-digital-SubmitRequestsTable')

# AI Lambda function names
AI_QUERY_KB_FUNCTION = os.environ.get('AI_QUERY_KB_FUNCTION', 'wecare-ai-query-kb')
AI_GENERATE_RESPONSE_FUNCTION = os.environ.get('AI_GENERATE_RESPONSE_FUNCTION', 'wecare-ai-generate-response')

# Outbound WhatsApp Lambda function name
OUTBOUND_WHATSAPP_FUNCTION = os.environ.get('OUTBOUND_WHATSAPP_FUNCTION', 'wecare-outbound-whatsapp')

# WhatsApp Voice Lambda function name (TTS via Amazon Polly)
WHATSAPP_VOICE_FUNCTION = os.environ.get('WHATSAPP_VOICE_FUNCTION', 'wecare-whatsapp-voice')

# Fix #6: Circuit breaker for AI failures  -  skip AI if too many consecutive failures
_ai_fail_count = 0
_ai_fail_reset_time = 0
AI_CIRCUIT_BREAKER_THRESHOLD = 5   # failures before tripping
AI_CIRCUIT_BREAKER_COOLDOWN = 300  # seconds (5 min) before retrying

# WhatsApp Phone Number IDs - Map Meta phone number IDs to phone number IDs
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-waba1-direct-1016149501586345')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-waba-t-direct-1055232054343117')

# Map display phone numbers to phone number IDs for reference
PHONE_NUMBER_MAP = {
    '919330994400': PHONE_NUMBER_ID_1,  # +91 93309 94400 (WABA1, Direct API)
    '919903300044': PHONE_NUMBER_ID_2,  # +91 99033 00044 (WABA-T, Direct API)
}

# Meta phone number ID to phone number ID mapping
META_PHONE_ID_MAP = {
    '1016149501586345': PHONE_NUMBER_ID_1,  # +91 93309 94400 (Direct API)
    '1055232054343117': PHONE_NUMBER_ID_2,  # +91 99033 00044 (Direct API)
}

# All phones use Direct API
DIRECT_API_PHONE_IDS = {PHONE_NUMBER_ID_1, PHONE_NUMBER_ID_2}

# Platform-owned Meta WABA ids. Any OTHER WABA hitting our webhook is an
# Embedded-Signup partner tenant — tag its messages with partnerWabaId so the
# tenant-scoped customer inbox can query the partnerWabaId GSI.
PLATFORM_WABAS = {'2094615664435155', '2513394156072604'}


def _get_welcome_config_key(phone_number_id: str) -> str:
    """Return the SystemConfig key for welcome message based on phone number.
    Phone 1 uses 'welcome_message', Phone 2 uses 'welcome_message_2'."""
    if phone_number_id == PHONE_NUMBER_ID_2:
        return 'welcome_message_2'
    return 'welcome_message'


DEFAULT_FALLBACK_MESSAGE = "Thanks for your message! Type 'menu' to see available options, or 'subscribe' to get started."


# Deterministic-trigger keywords for the Meta Business Agent hybrid. When the AI
# holds control (standby), we take control + run OUR flow only for these; free-form
# text is left to the AI.
_DETERMINISTIC_KEYWORDS = {
    'hi', 'hello', 'hey', 'menu', 'main menu', 'show menu', 'browse menu', '/menu',
    'start', 'get started', 'need help!', 'subscribe', 'help',
}
_DETERMINISTIC_CONTAINS = (
    'get started', 'main menu', 'subscribe', 'track request', 'track', 'submit request',
    'amend request', 'appointment', 'rx slot', 'drop docs', 'enterprise', 'leave review',
    'catalog', 'catalogue', 'pay', 'payment', 'invoice', 'faq',
)


_routing_cache = {'v': None, 't': 0.0}


def _get_routing_config() -> Dict:
    """Load the AI hybrid routing config (which triggers the bot handles vs the AI)
    from SystemConfigTable id='ai_hybrid_routing'. Cached 60s. Falls back to the
    built-in defaults so behaviour is safe if unset."""
    import time as _t
    now = _t.time()
    if _routing_cache['v'] is not None and (now - _routing_cache['t']) < 60:
        return _routing_cache['v']
    cfg = {
        'enabled': True,
        'keywords': sorted(_DETERMINISTIC_KEYWORDS),
        'contains': list(_DETERMINISTIC_CONTAINS),
        'types': ['button', 'interactive', 'order'],
        'commandPrefix': '/',
    }
    try:
        item = dynamodb.Table(SYSTEM_CONFIG_TABLE).get_item(Key={'id': 'ai_hybrid_routing'}).get('Item')
        if item:
            raw = item.get('configValue')
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
            for k in ('enabled', 'keywords', 'contains', 'types', 'commandPrefix'):
                if k in data and data[k] is not None:
                    cfg[k] = data[k]
    except Exception:
        pass
    _routing_cache['v'] = cfg
    _routing_cache['t'] = now
    return cfg


def _is_deterministic_trigger(message: Dict) -> bool:
    """True if the message should be handled by OUR deterministic flows (menu,
    lists, flows, catalog/cart, commands) rather than the Meta AI agent. Driven by
    the configurable ai_hybrid_routing table (with safe built-in defaults)."""
    cfg = _get_routing_config()
    if not cfg.get('enabled', True):
        return False  # hybrid off → everything goes to the AI
    t = message.get('type')
    if t in set(cfg.get('types') or ['button', 'interactive', 'order']):
        return True  # ice-breaker taps, list/flow replies, catalog cart orders
    if t == 'text':
        body = ((message.get('text', {}) or {}).get('body', '') or '').strip().lower()
        if not body:
            return False
        prefix = cfg.get('commandPrefix', '/')
        if prefix and body.startswith(prefix):
            return True  # slash commands
        kws = {k.lower() for k in (cfg.get('keywords') or [])}
        if body in kws:
            return True
        return any(kw.lower() in body for kw in (cfg.get('contains') or []))
    return False


# ── Meta Business Agent hybrid: which standby messages our bot should take over ──
# When the Meta AI holds control, messages arrive on the `standby` field. For our
# deterministic experiences (menu/keywords/commands/flows/catalog) we TAKE control
# by processing them; free-form questions are left to the AI.
_STANDBY_TEXT_TRIGGERS = {
    'hi', 'hello', 'hey', 'menu', 'main menu', 'show menu', 'start', 'get started',
    'browse menu', '/menu', 'need help!', 'subscribe', 'pay', '/pay', 'catalog',
    'view catalog', 'submit request', 'track request', 'track', 'amend request',
    'appointment', 'rx slot', 'drop docs', 'enterprise', 'leave review', 'faq',
}


def _is_deterministic_trigger(message: dict) -> bool:
    """True if this message should be handled by our deterministic bot (menu/flow/
    catalog/command), rather than left to the Meta AI."""
    t = (message or {}).get('type', '')
    if t in ('interactive', 'order', 'button', 'nfm_reply'):
        return True
    if t == 'text':
        txt = ((message.get('text') or {}).get('body') or '').strip().lower()
        if not txt:
            return False
        if txt.startswith('/'):
            return True
        return txt in _STANDBY_TEXT_TRIGGERS
    return False


def _load_fallback_message(phone_number_id: str) -> str:
    """Load configurable fallback message from SystemConfigTable."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'wa_auto_response'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            return config.get('fallbackMessage', DEFAULT_FALLBACK_MESSAGE)
        return DEFAULT_FALLBACK_MESSAGE
    except Exception:
        return DEFAULT_FALLBACK_MESSAGE


def _load_welcome_text(phone_number_id: str, default_text: str) -> str:
    """Load custom welcome text from SystemConfigTable for the given phone."""
    try:
        config_key = _get_welcome_config_key(phone_number_id)
        _wc = dynamodb.Table(SYSTEM_CONFIG_TABLE).get_item(Key={'id': config_key}).get('Item')
        if _wc:
            _wc_val = json.loads(_wc.get('configValue', '{}')) if isinstance(_wc.get('configValue'), str) else _wc.get('configValue', {})
            if _wc_val.get('textMessage'):
                return _wc_val['textMessage']
    except Exception:
        pass
    return default_text


def _is_direct_api_phone(phone_number_id: str) -> bool:
    """Check if a phone number ID belongs to a Direct API WABA."""
    return phone_number_id in DIRECT_API_PHONE_IDS


# ── Direct API support ──────────────────────────────────────────────
# All WABAs use Direct Meta Graph API for messaging.
# Token loaded from Secrets Manager (same secret as calling handler).
META_TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
META_API_VERSION = os.environ.get('META_API_VERSION', 'v25.0')
PHONE1_META_ID = '1016149501586345'  # +91 93309 94400 (WABA1, Direct API)
_direct_api_token_cache = {}
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))


def _load_direct_api_token() -> str:
    """Load Meta access token for Direct API calls (cached)."""
    if 'token' in _direct_api_token_cache:
        return _direct_api_token_cache['token']
    try:
        resp = secrets_client.get_secret_value(SecretId=META_TOKEN_SECRET)
        secret = resp.get('SecretString', '')
        try:
            data = json.loads(secret)
            _direct_api_token_cache['token'] = (data.get('access_token') or '').strip()
            _direct_api_token_cache['app_secret'] = (data.get('app_secret') or '').strip()
        except (json.JSONDecodeError, TypeError):
            _direct_api_token_cache['token'] = secret.strip()
            _direct_api_token_cache['app_secret'] = ''
        return _direct_api_token_cache.get('token', '')
    except Exception as e:
        logger.error(f"Failed to load Direct API token: {e}")
        return ''


def _get_meta_phone_id_for_direct_api(aws_phone_id: str) -> str:
    """Get the Meta phone ID for a Direct API phone number."""
    DIRECT_API_META_MAP = {
        PHONE_NUMBER_ID_1: '1016149501586345',  # +91 93309 94400 (WABA1)
        PHONE_NUMBER_ID_2: '1055232054343117',  # +91 99033 00044 (WABA-T)
    }
    meta_id = DIRECT_API_META_MAP.get(aws_phone_id)
    if meta_id:
        return meta_id
    # Fallback: extract from direct format phone-number-id-*-direct-{meta_id}
    if '-direct-' in aws_phone_id:
        return aws_phone_id.split('-direct-')[-1]
    # Last resort: use WABA-T phone (confirmed working)
    return '1055232054343117'


# Track current phone context for Direct API calls
_current_direct_api_phone = None

# Auto 👍 reaction toggle. Applies to outbound messages sent from THIS handler
# (AI auto-replies, IVR responses) and to inbound received-message reactions.
# Resolved at runtime from SystemConfig (id='whatsapp_auto_thumb', cached) with the
# env var as the default. Default ON.
AUTO_THUMB_REACTION_ENABLED = os.environ.get('AUTO_THUMB_REACTION_ENABLED', 'true').strip().lower() in ('true', '1', 'yes', 'on')
AUTO_THUMB_EMOJI = os.environ.get('AUTO_THUMB_EMOJI', '\U0001F44D')
_auto_thumb_cache = {'value': None, 'ts': 0.0}
_AUTO_THUMB_CACHE_TTL = 300  # seconds — admin toggles propagate within 5 min


def _auto_thumb_enabled() -> bool:
    """Runtime auto 👍 toggle. Reads SystemConfig 'whatsapp_auto_thumb' at most once
    per _AUTO_THUMB_CACHE_TTL seconds (cached); falls back to the env default."""
    now = time.time()
    if _auto_thumb_cache['value'] is not None and (now - _auto_thumb_cache['ts']) < _AUTO_THUMB_CACHE_TTL:
        return _auto_thumb_cache['value']
    val = AUTO_THUMB_REACTION_ENABLED
    try:
        item = dynamodb.Table(SYSTEM_CONFIG_TABLE).get_item(Key={'id': 'whatsapp_auto_thumb'}).get('Item')
        if item and 'configValue' in item:
            val = str(item.get('configValue')).lower() in ('true', '1', 'yes', 'on')
    except Exception as e:
        logger.warning(f"auto_thumb config read failed (using default {val}): {e}")
    _auto_thumb_cache['value'] = val
    _auto_thumb_cache['ts'] = now
    return val


def _send_direct_api_message(to_number: str, message_payload: Dict, meta_phone_id: str = None) -> Dict:
    """Send a WhatsApp message via Meta Graph API for Direct API phones."""
    token = _load_direct_api_token()
    if not token:
        return {'error': True, 'detail': 'No Direct API token available'}

    if not to_number.startswith('+'):
        to_number = f'+{to_number}'
    message_payload['to'] = to_number
    message_payload['messaging_product'] = 'whatsapp'

    phone_id = meta_phone_id or _current_direct_api_phone or PHONE1_META_ID
    url = f"https://graph.facebook.com/{META_API_VERSION}/{phone_id}/messages"
    app_secret = _direct_api_token_cache.get('app_secret', '')
    if app_secret:
        proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        url = f"{url}?appsecret_proof={proof}"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    data = json.dumps(message_payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode('utf-8')
            result = json.loads(body) if body else {}
            msg_id = ''
            messages = result.get('messages', [])
            if messages:
                msg_id = messages[0].get('id', '')
            # Auto 👍 on outbound messages sent from this handler (auto-replies, IVR).
            # Skip reaction-type payloads to prevent recursion. React from the SAME
            # phone (phone_id) that sent the message so the wamid resolves.
            if (msg_id and message_payload.get('type') != 'reaction'
                    and _auto_thumb_enabled()):
                try:
                    _send_direct_api_message(to_number, {
                        'type': 'reaction',
                        'reaction': {'message_id': msg_id, 'emoji': AUTO_THUMB_EMOJI},
                    }, meta_phone_id=phone_id)
                except Exception:
                    pass  # reaction is best-effort; never affect the primary send
            return {'success': True, 'messageId': msg_id}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Direct API send failed {e.code}: {error_body}")
        return {'error': True, 'status': e.code, 'detail': error_body}
    except Exception as e:
        logger.error(f"Direct API send failed: {e}")
        return {'error': True, 'detail': str(e)}


def _send_direct_api_reaction(to_number: str, whatsapp_message_id: str, emoji: str = '\U0001F44D') -> Dict:
    """Send a reaction via Meta Graph API via Direct API."""
    payload = {
        'type': 'reaction',
        'reaction': {
            'message_id': whatsapp_message_id,
            'emoji': emoji
        }
    }
    return _send_direct_api_message(to_number, payload)


def _send_direct_api_read_receipt(whatsapp_message_id: str, meta_phone_id: str = None, show_typing: bool = False) -> Dict:
    """Send a read receipt via Meta Graph API for Direct API phones.
    When show_typing=True, also displays the in-app typing indicator (auto-dismisses
    when you reply or after 25s) — per Meta's typing_indicator API. Only use when a
    reply will follow."""
    token = _load_direct_api_token()
    if not token:
        return {'error': True, 'detail': 'No Direct API token available'}
    payload = {
        'messaging_product': 'whatsapp',
        'status': 'read',
        'message_id': whatsapp_message_id
    }
    if show_typing:
        payload['typing_indicator'] = {'type': 'text'}
    phone_id = meta_phone_id or _current_direct_api_phone or PHONE1_META_ID
    url = f"https://graph.facebook.com/{META_API_VERSION}/{phone_id}/messages"
    app_secret = _direct_api_token_cache.get('app_secret', '')
    if app_secret:
        proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        url = f"{url}?appsecret_proof={proof}"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {'success': True}
    except Exception as e:
        logger.warning(f"Direct API read receipt failed: {e}")
        return {'error': True, 'detail': str(e)}


def _send_direct_api_typing(whatsapp_message_id: str, meta_phone_id: str = None) -> Dict:
    """Show the WhatsApp typing indicator via Meta's real typing_indicator API.
    Marks the message read and displays 'typing…' (auto-dismisses on reply or after 25s).
    Requires the inbound WhatsApp message_id."""
    if not whatsapp_message_id:
        return {'error': True, 'detail': 'whatsapp_message_id required for typing indicator'}
    return _send_direct_api_read_receipt(whatsapp_message_id, meta_phone_id=meta_phone_id, show_typing=True)


def _download_media_direct_api(whatsapp_media_id: str, message_id: str, media_type: str,
                                request_id: str, mime_type_hint: str = '') -> Optional[str]:
    """Download media via Meta Graph API via Direct API.
    
    Two-step process:
    1. GET /{media_id} to get the download URL
    2. GET the download URL to get the actual file bytes
    3. Upload to S3
    """
    token = _load_direct_api_token()
    if not token:
        logger.warning(f"No Direct API token for media download: {whatsapp_media_id}")
        return None
    
    try:
        app_secret = _direct_api_token_cache.get('app_secret', '')
        auth_headers = {'Authorization': f'Bearer {token}'}
        
        # Step 1: Get media URL
        media_url = f"https://graph.facebook.com/{META_API_VERSION}/{whatsapp_media_id}"
        if app_secret:
            proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
            media_url = f"{media_url}?appsecret_proof={proof}"
        
        req = urllib.request.Request(media_url, headers=auth_headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            media_info = json.loads(resp.read().decode('utf-8'))
        
        download_url = media_info.get('url', '')
        mime_type = media_info.get('mime_type', mime_type_hint)
        
        if not download_url:
            logger.warning(f"No download URL for media {whatsapp_media_id}")
            return None
        
        logger.info(json.dumps({
            'event': 'direct_api_media_url_fetched',
            'mediaId': whatsapp_media_id,
            'mimeType': mime_type,
            'requestId': request_id
        }))
        
        # Step 2: Download the actual file
        dl_req = urllib.request.Request(download_url, headers=auth_headers)
        with urllib.request.urlopen(dl_req, timeout=60) as dl_resp:
            file_bytes = dl_resp.read()
        
        # Step 3: Upload to S3
        ext = _get_extension_from_mime(mime_type) if mime_type else _get_extension_from_type(media_type)
        short_id = uuid.uuid4().hex[:8]
        s3_key = f"{MEDIA_PREFIX}wecare-digital-{short_id}{ext}"
        
        content_type = mime_type or 'application/octet-stream'
        s3.put_object(
            Bucket=MEDIA_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type
        )
        
        logger.info(json.dumps({
            'event': 'direct_api_media_downloaded',
            'mediaId': whatsapp_media_id,
            's3Key': s3_key,
            'fileSize': len(file_bytes),
            'mimeType': mime_type,
            'requestId': request_id
        }))
        
        return s3_key
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'direct_api_media_download_error',
            'mediaId': whatsapp_media_id,
            'error': str(e),
            'requestId': request_id
        }))
        return None


# TTL: 30 days in seconds
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60

# ── Payment flow messages (hardcoded, LLM-independent, edit here to change) ──
PAY_MSG = {
    'pulling':      '\U0001f440 Pulling your pending invoice...',
    'no_dues':      '\u2705 No pending dues!',
    'paid':         '\u2705 Paid successfully.',
    'pay_failed':   '\u274c Payment failed. Please try again.',
    'all_clear':    '\u2705 No pending dues!',
    'next_due':     '\u26a0\ufe0f You have unpaid invoice of \u20b9{total}.',
    'send_failed':  '\u274c Could not send payment link. Please try again.',
    'error':        '\u26a0\ufe0f Something went wrong. Please try again.',
    'wa_body':      'Your payment is ready \u2014 tap below to complete it \U0001f4b3',
    'redirect':     '\U0001f4b3 To make a payment, please send *pay* to +91 9330994400',
}

# Phone number ID that handles payments (Phone 1: +919330994400 / WECARE.DIGITAL)
PAYMENT_PHONE_NUMBER_ID = 'phone-number-id-waba1-direct-1016149501586345'

# WhatsApp Flow IDs
SUBMIT_REQUEST_FLOW_ID = os.environ.get('SUBMIT_REQUEST_FLOW_ID', '1235100738173254')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process inbound WhatsApp messages from SNS.
    
    Meta Webhook Event Format:
    {
        "context": { "MetaWabaIds": [...], "MetaPhoneNumberIds": [...] },
        "whatsAppWebhookEntry": "{...JSON STRING...}",
        "aws_account_id": "775261844268",
        "message_timestamp": "2026-01-17T12:00:00.000Z",
        "messageId": "uuid"
    }
    """
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    processed_count = 0
    error_count = 0
    
    # Timeout guard: reserve 15s for cleanup/response to avoid Lambda timeout
    _lambda_deadline_ms = (context.get_remaining_time_in_millis() if context else 120000)
    _start_time = time.time()

    # ── Direct invoke: create_invoice from dashboard ──
    if event.get('action') == 'create_invoice':
        return _handle_dashboard_invoice(event, request_id)
    
    logger.info(json.dumps({
        'event': 'inbound_processing_start',
        'recordCount': len(event.get('Records', [])),
        'requestId': request_id
    }))
    
    for record in event.get('Records', []):
        try:
            # Parse SNS message
            sns_message = json.loads(record.get('Sns', {}).get('Message', '{}'))
            
            # Extract WABA context - which WABA received this message
            context_data = sns_message.get('context', {})
            meta_waba_ids = context_data.get('MetaWabaIds', [])
            meta_phone_number_ids = context_data.get('MetaPhoneNumberIds', [])
            
            webhook_entry_str = sns_message.get('whatsAppWebhookEntry', '{}')
            aws_message_id = sns_message.get('messageId', str(uuid.uuid4()))
            
            # Decode whatsAppWebhookEntry JSON string
            webhook_entry = json.loads(webhook_entry_str)
            
            # Process each change in the webhook entry
            for change in webhook_entry.get('changes', []):
                value = change.get('value', {})
                metadata = value.get('metadata', {})

                # ── Meta Business Agent handover protocol ──
                # When the Meta AI agent is the primary responder it HOLDS control,
                # and the customer's messages arrive on the `standby` field (copies),
                # while `messaging_handovers` notifies of control changes. We must NOT
                # run our normal responder on standby traffic (that would hijack the
                # AI's thread by implicitly taking control). Capture the payload for
                # audit + to finalise command routing, then skip normal processing.
                _wh_field = change.get('field', '')
                if _wh_field == 'messaging_handovers':
                    # Control-change notification — audit only.
                    try:
                        _store_system_event(_wh_field, value, request_id)
                    except Exception:
                        pass
                    continue
                if _wh_field == 'standby':
                    # AI holds control. In the handover payload the message + contacts are
                    # nested under value["standby"] (not value["messages"]). Unwrap it, then
                    # take control + run OUR flow ONLY for deterministic triggers
                    # (menu/list/flow/catalog/commands); leave free-form to the AI.
                    try:
                        _sb = value.get('standby')
                        if isinstance(_sb, dict):
                            _msgs = _sb.get('messages', []) or value.get('messages', []) or []
                            _contacts = _sb.get('contacts')
                        elif isinstance(_sb, list):
                            _msgs = _sb; _contacts = None
                        else:
                            _msgs = value.get('messages', []) or []; _contacts = None
                        _det = [m for m in _msgs if _is_deterministic_trigger(m)]
                        logger.info(json.dumps({'event': 'standby_webhook', 'total': len(_msgs),
                                                'deterministic': len(_det), 'requestId': request_id}))
                        if not _det:
                            continue  # free-form → let the Meta AI agent respond
                        # Unwrap so normal processing (below) handles the deterministic
                        # triggers — sending a reply takes thread control from the AI.
                        value['messages'] = _det
                        if _contacts is not None:
                            value['contacts'] = _contacts
                        # fall through to normal message processing
                    except Exception as _he:
                        logger.warning(json.dumps({'event': 'standby_webhook_error',
                                                   'error': str(_he), 'requestId': request_id}))
                        continue

                # Extract receiving phone number info from metadata
                display_phone_number = metadata.get('display_phone_number', '')
                phone_number_id = metadata.get('phone_number_id', '')
                
                # Determine AWS phone number ID for this WABA
                aws_phone_number_id = _get_aws_phone_number_id(display_phone_number, phone_number_id)
                
                # Extract contacts info (contains profile names, BSUIDs, usernames)
                # WhatsApp webhook format: contacts array has wa_id, user_id, profile.name, profile.username
                contacts_info = value.get('contacts', [])
                contacts_map = {}
                for contact_info in contacts_info:
                    wa_id = contact_info.get('wa_id', '')
                    user_id = contact_info.get('user_id', '')  # BSUID
                    parent_user_id = contact_info.get('parent_user_id', '')
                    profile = contact_info.get('profile', {})
                    profile_name = profile.get('name', '')
                    username = profile.get('username', '')  # WhatsApp username (e.g. @pablomorales)
                    # Map by wa_id (phone) and user_id (BSUID) for flexible lookup
                    entry = {
                        'name': profile_name,
                        'bsuid': user_id,
                        'parent_bsuid': parent_user_id,
                        'username': username,
                        'contact_book_name': profile.get('contact_book_name', ''),
                        'wa_id': wa_id,
                    }
                    if wa_id:
                        contacts_map[wa_id] = entry
                    if user_id:
                        contacts_map[user_id] = entry
                
                # Process incoming messages
                for message in value.get('messages', []):
                    try:
                        # Timeout guard: skip remaining messages if <15s left
                        if context and context.get_remaining_time_in_millis() < 15000:
                            logger.warning(json.dumps({
                                'event': 'timeout_guard_triggered',
                                'remainingMs': context.get_remaining_time_in_millis(),
                                'processedCount': processed_count,
                                'requestId': request_id
                            }))
                            _send_to_dlq({'messages': value.get('messages', [])[processed_count:]}, 'timeout_guard', request_id)
                            break
                        
                        # Get sender info from contacts array (BSUID-aware)
                        sender_phone = message.get('from', '')
                        sender_bsuid = message.get('from_user_id', '')  # BSUID from message
                        sender_parent_bsuid = message.get('from_parent_user_id', '')  # Parent BSUID from message
                        # Lookup contact info by phone or BSUID
                        contact_entry = contacts_map.get(sender_phone) or contacts_map.get(sender_bsuid) or {}
                        sender_profile_name = contact_entry.get('name', '') if isinstance(contact_entry, dict) else contact_entry
                        sender_username = contact_entry.get('username', '') if isinstance(contact_entry, dict) else ''
                        sender_contact_book_name = contact_entry.get('contact_book_name', '') if isinstance(contact_entry, dict) else ''
                        # Use BSUID from contacts_map if not in message directly
                        if not sender_bsuid and isinstance(contact_entry, dict):
                            sender_bsuid = contact_entry.get('bsuid', '')
                        # Use parent BSUID from contacts_map if not in message directly
                        if not sender_parent_bsuid and isinstance(contact_entry, dict):
                            sender_parent_bsuid = contact_entry.get('parent_bsuid', '')
                        
                        _process_message(
                            message=message,
                            metadata=metadata,
                            request_id=request_id,
                            receiving_phone=display_phone_number,
                            aws_phone_number_id=aws_phone_number_id,
                            meta_waba_ids=meta_waba_ids,
                            sender_profile_name=sender_profile_name,
                            sender_bsuid=sender_bsuid,
                            sender_parent_bsuid=sender_parent_bsuid,
                            sender_username=sender_username,
                            sender_contact_book_name=sender_contact_book_name,
                        )
                        processed_count += 1
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'message_processing_error',
                            'messageId': message.get('id'),
                            'error': str(e),
                            'requestId': request_id
                        }))
                        error_count += 1
                
                # Process status updates
                _status_waba_id = (meta_waba_ids[0] if meta_waba_ids else '')
                for status in value.get('statuses', []):
                    try:
                        _process_status(status, request_id, contacts_map=contacts_map, waba_id=_status_waba_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'status_processing_error',
                            'statusId': status.get('id'),
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process template status updates (APPROVED, REJECTED, PAUSED, etc.)
                field = change.get('field', '')
                if field == 'message_template_status_update':
                    try:
                        _process_template_status(value, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'template_status_processing_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process phone number quality updates
                if field == 'phone_number_quality_update':
                    try:
                        _process_phone_quality_update(value, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'phone_quality_processing_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process account updates (messaging limits, etc.)
                if field == 'account_update':
                    try:
                        _process_account_update(value, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'account_update_processing_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process BSUID changes (user_id_update)  -  separate webhook field
                if field == 'user_id_update':
                    _store_system_event('user_id_update', value, request_id)  # audit trail
                    for uid_update in value.get('user_id_update', []):
                        try:
                            _process_user_id_update(uid_update, contacts_map, request_id)
                        except Exception as e:
                            logger.error(json.dumps({
                                'event': 'user_id_update_error',
                                'error': str(e),
                                'requestId': request_id
                            }))
                
                # Process business_username_updates webhook (Meta field is plural;
                # accept singular too for forward/backward compatibility)
                if field in ('business_username_updates', 'business_username_update'):
                    try:
                        _process_business_username_update(value, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'business_username_updates_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process user_preferences webhook (marketing message opt-in/out with BSUID)
                if field == 'user_preferences':
                    try:
                        _store_system_event('user_preferences', value, request_id)
                        # Also enrich contact BSUID from user_preferences contacts array
                        for pref in value.get('user_preferences', []):
                            pref_bsuid = pref.get('user_id', '')
                            pref_phone = pref.get('wa_id', '')
                            if pref_bsuid and pref_phone:
                                try:
                                    contact = _get_contact_by_phone(pref_phone)
                                    if contact:
                                        ct = dynamodb.Table(CONTACTS_TABLE)
                                        _update_contact_bsuid_fields(ct, contact, '', '', phone=pref_phone, bsuid=pref_bsuid)
                                except Exception as e:
                                    logger.warning(f'BSUID enrichment failed for {pref_phone[:6]}***: {e}')
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'user_preferences_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process group webhook events (group_participant_change, group_membership_approval_request)
                if field == 'group_participant_change':
                    try:
                        _store_system_event('group_participant_change', value, request_id)
                        _process_group_event(value, 'participant_change', request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'group_participant_change_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                if field == 'group_membership_approval_request':
                    try:
                        _store_system_event('group_membership_approval_request', value, request_id)
                        _process_group_event(value, 'membership_approval', request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'group_membership_approval_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                if field == 'group_lifecycle_update':
                    try:
                        _store_system_event('group_lifecycle_update', value, request_id)
                        _process_group_event(value, 'lifecycle', request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'group_lifecycle_update_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                if field == 'group_settings_update':
                    try:
                        _store_system_event('group_settings_update', value, request_id)
                        _process_group_event(value, 'settings_update', request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'group_settings_update_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # ── Additional Meta webhook fields (per official docs) ──
                # These are informational/system-level events that we log to SystemEvent
                # for audit trail and operational awareness.
                # Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components
                _SYSTEM_EVENT_FIELDS = {
                    'account_alerts', 'account_review_update',
                    'business_capability_update', 'history',
                    'message_template_components_update',
                    'message_template_quality_update',
                    'payment_configuration_update',
                    'phone_number_name_update', 'security',
                    'template_category_update',
                }
                if field in _SYSTEM_EVENT_FIELDS:
                    try:
                        _store_system_event(field, value, request_id)
                        logger.info(json.dumps({
                            'event': f'webhook_{field}_stored',
                            'field': field,
                            'requestId': request_id,
                        }))
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': f'webhook_{field}_error',
                            'error': str(e),
                            'requestId': request_id,
                        }))
                        
        except Exception as e:
            logger.error(json.dumps({
                'event': 'record_processing_error',
                'error': str(e),
                'requestId': request_id
            }))
            _send_to_dlq(record, str(e), request_id)
            error_count += 1
    
    logger.info(json.dumps({
        'event': 'inbound_processing_complete',
        'processedCount': processed_count,
        'errorCount': error_count,
        'requestId': request_id
    }))
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed_count,
            'errors': error_count
        })
    }


def _get_aws_phone_number_id(display_phone: str, meta_phone_id: str) -> str:
    """
    Map display phone number or Meta phone ID to phone number ID.
    Returns the appropriate AWS phone number ID for sending reactions.
    For Direct API phones, returns a synthetic ID for tracking purposes.
    """
    # Clean display phone number (remove + and spaces)
    clean_phone = display_phone.replace('+', '').replace(' ', '').replace('-', '')
    
    # Check if we have a mapping for this phone number
    if clean_phone in PHONE_NUMBER_MAP:
        return PHONE_NUMBER_MAP[clean_phone]
    
    # Check Meta phone number ID mapping (for Direct API WABAs)
    if meta_phone_id in META_PHONE_ID_MAP:
        return META_PHONE_ID_MAP[meta_phone_id]
    
    # Default to first phone number ID if no mapping found
    logger.warning(json.dumps({
        'event': 'phone_number_mapping_not_found',
        'displayPhone': display_phone,
        'metaPhoneId': meta_phone_id,
        'usingDefault': PHONE_NUMBER_ID_1
    }))
    return PHONE_NUMBER_ID_1


def _process_message(
    message: Dict,
    metadata: Dict,
    request_id: str,
    receiving_phone: str,
    aws_phone_number_id: str,
    meta_waba_ids: list,
    sender_profile_name: str = '',
    sender_bsuid: str = '',
    sender_parent_bsuid: str = '',
    sender_username: str = '',
    sender_contact_book_name: str = '',
) -> None:
    """
    Process a single inbound message.
    Stores which WABA/phone number received the message.
    Supports BSUID (Business-Scoped User ID), parent BSUID, and username from webhook.
    """
    whatsapp_message_id = message.get('id')
    sender_phone = message.get('from', '')
    # BSUID: from_user_id in message takes precedence over contacts array
    msg_bsuid = message.get('from_user_id', '') or sender_bsuid
    # Parent BSUID: from_parent_user_id in message takes precedence over contacts array
    msg_parent_bsuid = message.get('from_parent_user_id', '') or sender_parent_bsuid
    msg_type = message.get('type', 'text')
    timestamp = int(message.get('timestamp', time.time()))
    
    # ── Detect real content type for "unsupported" messages ──
    # Meta marks many messages as 'unsupported' but they still carry media/text
    # data. Detect the actual type so the inbox can render them properly.
    if msg_type == 'unsupported':
        for probe_type in ('image', 'video', 'audio', 'document', 'sticker', 'poll', 'location', 'contacts', 'reaction'):
            probe_data = message.get(probe_type)
            if isinstance(probe_data, dict) and probe_data.get('id'):
                # Has a media ID  -  this is a real media message wrapped as unsupported
                # (common for view-once, multi-image bundles)
                msg_type = probe_type
                logger.info(json.dumps({
                    'event': 'unsupported_type_recovered',
                    'recoveredType': probe_type,
                    'whatsappMessageId': whatsapp_message_id,
                    'requestId': request_id
                }))
                break
        # Check for text body in unsupported wrapper
        if msg_type == 'unsupported':
            text_data = message.get('text', {})
            if isinstance(text_data, dict) and text_data.get('body'):
                msg_type = 'text'
                logger.info(json.dumps({
                    'event': 'unsupported_type_recovered',
                    'recoveredType': 'text',
                    'whatsappMessageId': whatsapp_message_id,
                    'requestId': request_id
                }))
    
    # Log full message for unsupported or unrecognized types to help debug
    if msg_type in ('unsupported', 'unknown') or msg_type not in (
        'text', 'image', 'video', 'audio', 'document', 'sticker',
        'location', 'contacts', 'reaction', 'interactive', 'button',
        'order', 'system', 'request_welcome', 'ephemeral',
        'referral', 'ad_click', 'product', 'product_inquiry', 'poll',
        'edit', 'revoke',
    ):
        logger.warning(json.dumps({
            'event': 'unsupported_or_new_message_type',
            'senderPhone': sender_phone,
            'whatsappMessageId': whatsapp_message_id,
            'messageType': msg_type,
            'messageKeys': list(message.keys()),
            'fullMessage': message,
            'requestId': request_id
        }))
    
    # Use sender profile name from contacts array (passed in)
    # Fall back to checking message.profile if not provided
    sender_name = sender_profile_name
    if not sender_name and 'profile' in message:
        sender_name = message.get('profile', {}).get('name', '')
    
    # Deduplicate using whatsappMessageId
    if _message_exists(whatsapp_message_id):
        logger.info(json.dumps({
            'event': 'message_duplicate_skipped',
            'whatsappMessageId': whatsapp_message_id,
            'requestId': request_id
        }))
        return
    
    # Lookup or create contact with sender name, BSUID, parent BSUID, and username
    contact = _get_or_create_contact(sender_phone, sender_name, bsuid=msg_bsuid, username=sender_username, contact_book_name=sender_contact_book_name, parent_bsuid=msg_parent_bsuid)
    contact_id = contact.get('contactId') or contact.get('id')
    
    # Extract message content based on type
    content = _extract_content(message, msg_type)
    
    # Generate message ID and calculate TTL
    message_id = str(uuid.uuid4())
    now = int(time.time())
    expires_at = now + MESSAGE_TTL_SECONDS
    
    # Handle media messages (including stickers)
    # All phones use Direct API
    media_id = None
    s3_key = None
    if msg_type in ['image', 'video', 'audio', 'document', 'sticker']:
        media_data = message.get(msg_type, {})
        whatsapp_media_id = media_data.get('id')
        mime_type_hint = media_data.get('mime_type', '')
        if whatsapp_media_id:
            if _is_direct_api_phone(aws_phone_number_id):
                s3_key = _download_media_direct_api(whatsapp_media_id, message_id, msg_type, request_id, mime_type_hint)
            else:
                s3_key = _download_media(whatsapp_media_id, message_id, msg_type, aws_phone_number_id, request_id, mime_type_hint)
            if s3_key:
                media_id = _store_media_record(message_id, s3_key, media_data, whatsapp_media_id)
                # ── GAP 2 FIX: Auto-ingest WhatsApp documents into DocumentsTable ──
                if msg_type in ('document', 'image'):
                    _ingest_whatsapp_document(
                        sender_phone, sender_name, contact_id, message_id,
                        whatsapp_media_id, s3_key, msg_type,
                        media_data.get('mime_type', ''),
                        media_data.get('filename', ''),
                        media_data.get('file_size', 0),
                        request_id,
                    )
                # Attach media to the customer's OPEN service request (photos/files
                # sent after the flow are saved under the request's folder + linked).
                try:
                    _link_media_to_service_request(contact_id, s3_key, msg_type,
                                                   media_data.get('filename', ''),
                                                   media_data.get('mime_type', ''), request_id)
                except Exception as _le:
                    logger.warning(json.dumps({'event': 'attach_link_error', 'error': str(_le), 'requestId': request_id}))
    
    # Ephemeral messages may carry media nested inside  -  try to extract
    if msg_type == 'ephemeral' and not s3_key:
        ephemeral_data = message.get('ephemeral', {})
        if isinstance(ephemeral_data, dict):
            for etype in ('image', 'video', 'audio', 'document', 'sticker'):
                edata = ephemeral_data.get(etype, {})
                if isinstance(edata, dict) and edata.get('id'):
                    mime_hint = edata.get('mime_type', '')
                    if _is_direct_api_phone(aws_phone_number_id):
                        s3_key = _download_media_direct_api(edata['id'], message_id, etype, request_id, mime_hint)
                    else:
                        s3_key = _download_media(edata['id'], message_id, etype, aws_phone_number_id, request_id, mime_hint)
                    if s3_key:
                        media_id = _store_media_record(message_id, s3_key, edata, edata['id'])
                    break
    
    # Store message in DynamoDB with WABA info and sender name
    message_record = {
        'id': message_id,
        'messageId': message_id,
        'contactId': contact_id,
        'channel': 'whatsapp',
        'direction': 'inbound',
        'content': content,
        'messageType': msg_type,
        'timestamp': Decimal(str(timestamp)),
        'status': 'received',
        'whatsappMessageId': whatsapp_message_id,
        'mediaId': media_id,
        's3Key': s3_key,
        'senderPhone': sender_phone,
        'senderName': sender_name,  # Sender's WhatsApp profile name
        'senderBsuid': msg_bsuid or None,  # Sender's BSUID (Business-Scoped User ID)
        'senderParentBsuid': msg_parent_bsuid or None,  # Sender's parent BSUID (linked account)
        'senderUsername': sender_username or None,  # Sender's WhatsApp username
        # WABA tracking - which number received this message
        'receivingPhone': receiving_phone,
        'awsPhoneNumberId': aws_phone_number_id,
        'metaWabaIds': meta_waba_ids if meta_waba_ids else None,
        'createdAt': Decimal(str(now)),
        'expiresAt': Decimal(str(expires_at)),
    }
    
    # Capture referral context (click-to-WhatsApp ads, product catalogs, social posts)
    # Referral can be attached to ANY message type, not just 'referral' type
    referral = message.get('referral')
    if referral:
        message_record['referralSource'] = referral.get('source_type', '')
        message_record['referralSourceId'] = referral.get('source_id', '')
        message_record['referralSourceUrl'] = referral.get('source_url', '')
        message_record['referralHeadline'] = referral.get('headline', '')
        message_record['referralBody'] = referral.get('body', '')
        # Click-to-WhatsApp Click ID — required by the Conversions API to attribute
        # in-thread conversions (Purchase/Lead) back to the ad. Persist it against the
        # customer's phone so wecare-whatsapp-business-api can log events later.
        ctwa_clid = referral.get('ctwa_clid', '')
        if ctwa_clid:
            message_record['ctwaClid'] = ctwa_clid
            try:
                _digits = ''.join(ch for ch in sender_phone if ch.isdigit())
                _waba = meta_waba_ids[0] if meta_waba_ids else ''
                dynamodb.Table(SYSTEM_CONFIG_TABLE).put_item(Item={
                    'id': 'capi_clid_' + _digits,
                    'configValue': json.dumps({
                        'ctwaClid': ctwa_clid,
                        'phone': _digits,
                        'wabaId': _waba,
                        'sourceType': referral.get('source_type', ''),
                        'sourceId': referral.get('source_id', ''),
                        'headline': referral.get('headline', ''),
                        'ts': int(time.time()),
                    }),
                    'updatedAt': int(time.time()),
                })
            except Exception as _e:
                logger.warning(f'ctwa_clid capture failed (non-blocking): {_e}')
        logger.info(json.dumps({
            'event': 'referral_context',
            'senderPhone': mask_phone(sender_phone),
            'sourceType': referral.get('source_type', ''),
            'sourceUrl': referral.get('source_url', ''),
            'ctwaClid': bool(ctwa_clid),
            'requestId': request_id
        }))
        
        # Fire-and-forget: record ad attribution for analytics
        try:
            lambda_client.invoke(
                FunctionName=os.environ.get('AD_ATTRIBUTION_FUNCTION', 'wecare-ad-attribution'),
                InvocationType='Event',  # async
                Payload=json.dumps({
                    'requestContext': {'http': {'method': 'POST', 'path': '/ad-attribution'}},
                    'body': json.dumps({
                        'phone': sender_phone,
                        'contactId': contact_id,
                        'referral': referral,
                        'wabaId': meta_waba_ids[0] if meta_waba_ids else '',
                        'phoneNumberId': aws_phone_number_id,
                        'whatsappMessageId': whatsapp_message_id,
                    }),
                }),
            )
        except Exception as e:
            logger.warning(f'Ad attribution invoke failed (non-blocking): {e}')
    
    # Capture message context (reply-to, forwarded)
    msg_context = message.get('context')
    if msg_context:
        message_record['replyToMessageId'] = msg_context.get('id', '')
        if msg_context.get('forwarded'):
            message_record['isForwarded'] = True
        if msg_context.get('frequently_forwarded'):
            message_record['isFrequentlyForwarded'] = True
        if msg_context.get('referred_product'):
            message_record['referredProduct'] = msg_context['referred_product']
    
    messages_table = dynamodb.Table(MESSAGES_TABLE)
    messages_table.put_item(Item={k: v for k, v in message_record.items() if v is not None})
    
    # Unified Inbox dual-write — mirror inbound WhatsApp to the canonical MessagesTable
    # (Phase 1). Same messageId as the WhatsApp inbound row, so messages-read dedups by
    # messageId. Guarded inside put_message — can never break inbound processing.
    _partner_waba = next((str(w) for w in (meta_waba_ids or []) if str(w) not in PLATFORM_WABAS), None)
    put_message(
        channel='whatsapp',
        direction='inbound',
        contact_id=contact_id,
        content=content,
        status='received',
        message_id=message_id,
        message_type=msg_type,
        whatsapp_message_id=whatsapp_message_id,
        media_id=media_id,
        s3_key=s3_key,
        sender_phone=sender_phone,
        sender_name=sender_name,
        receiving_phone=receiving_phone,
        aws_phone_number_id=aws_phone_number_id,
        partner_waba_id=_partner_waba,
        timestamp=timestamp,
    )

    # Automation rules — auto-reply if an enabled rule matches (guarded, fire-and-forget
    # via async outbound invoke so it can never block/break inbound processing).
    try:
        if content and msg_type == 'text':
            _auto = evaluate_rules(content, 'whatsapp')
            if _auto:
                lambda_client.invoke(
                    FunctionName=os.environ.get('OUTBOUND_FUNCTION', 'wecare-outbound-whatsapp'),
                    InvocationType='Event',
                    Payload=json.dumps({
                        'requestContext': {'http': {'method': 'POST', 'path': '/whatsapp/send'}},
                        'body': json.dumps({'contactId': contact_id, 'content': _auto, 'phoneNumberId': aws_phone_number_id}),
                    }),
                )
                logger.info(json.dumps({'event': 'automation_auto_reply', 'contactId': contact_id, 'whatsappMessageId': whatsapp_message_id}))
    except Exception as _ae:
        logger.warning(f'automation auto-reply skipped: {_ae}')
    
    # call_permission_reply interactive messages are no longer processed.
    # Permission is auto-granted post-call in the whatsapp-calling handler.
    if msg_type == 'interactive':
        interactive = message.get('interactive', {})
        interactive_type = interactive.get('type', '')
        if interactive_type == 'call_permission_reply':
            logger.info(f"Ignoring call_permission_reply from {sender_phone} — permission auto-granted post-call")
            return  # Discard — no longer forwarded or stored
        # IVR button responses  -  route to appropriate department/action
        elif interactive_type == 'button_reply':
            button_id = interactive.get('button_reply', {}).get('id', '')
            if button_id.startswith('ivr_'):
                _handle_ivr_response(
                    sender_phone=sender_phone,
                    aws_phone_number_id=aws_phone_number_id,
                    button_id=button_id,
                    request_id=request_id,
                )
                return  # Stop processing  -  IVR button handled
            # Follow-up buttons: Explore More / Done for Now
            if button_id == 'followup_explore':
                _send_interactive_list(
                    contact_id=contact_id,
                    phone_number_id=aws_phone_number_id,
                    list_config=_get_welcome_config(),
                    request_id=request_id,
                )
                return
            if button_id == 'followup_done':
                _send_ai_auto_reply(contact_id,
                    "Awesome \u2014 you\u2019re all set for now \U0001f49b\n\nType *hi* anytime to come back.",
                    aws_phone_number_id, request_id)
                return
        # List reply  -  user tapped a row in an interactive list message
        elif interactive_type == 'list_reply':
            list_id = interactive.get('list_reply', {}).get('id', '')
            if list_id:
                _handle_list_reply(
                    list_id=list_id,
                    contact_id=contact_id,
                    phone_number_id=aws_phone_number_id,
                    sender_phone=sender_phone,
                    request_id=request_id,
                )
                return  # Stop processing  -  list reply handled
        # Native Flow Message reply — India Address Message submission arrives here
        # as nfm_reply with name='address_message' (also used by flow completions).
        elif interactive_type == 'nfm_reply':
            nfm = interactive.get('nfm_reply', {})
            if nfm.get('name') == 'address_message':
                _handle_address_submission(nfm, contact_id, sender_phone, aws_phone_number_id, request_id)
                return  # Stop processing — address submission handled
            # Post-payment (endpointless) flow completion: the DETAILS screen's
            # "complete" action returns a payload with reference_id + order details.
            try:
                _raw = nfm.get('response_json', '{}')
                _rj = json.loads(_raw) if isinstance(_raw, str) else (_raw or {})
                if isinstance(_rj, dict) and (_rj.get('reference_id') or _rj.get('request_id')) and (
                    'delivery_note' in _rj or 'preferred_time' in _rj or 'order_number' in _rj
                    or 'description' in _rj or 'request_id' in _rj):
                    _handle_postpay_submission(_rj, contact_id, sender_phone, aws_phone_number_id, request_id)
                    return  # Stop processing — post-payment submission handled
            except Exception as _pp_err:
                logger.warning(json.dumps({'event': 'postpay_nfm_parse_error', 'error': str(_pp_err), 'requestId': request_id}))

    # ── Cart order (native catalog checkout) ──
    # Customer sent a cart from the catalog (message.type='order'). Convert the
    # product_items into a native order_details (Review & Pay) with GST + convenience.
    if msg_type == 'order':
        _handle_cart_order(message, contact_id, sender_phone, aws_phone_number_id, request_id)
        return

    # Handle system status messages with user_changed_user_id
    # Per Meta BSUID docs: system messages can have type=user_changed_user_id
    # when a user changes their phone number, triggering a new BSUID
    if msg_type == 'system':
        system_data = message.get('system', {})
        system_type = system_data.get('type', '')
        if system_type == 'user_changed_user_id':
            new_bsuid = system_data.get('user_id', '')
            new_parent_bsuid = system_data.get('parent_user_id', '')
            new_wa_id = system_data.get('wa_id', '')
            logger.info(json.dumps({
                'event': 'system_user_changed_user_id',
                'senderPhone': sender_phone,
                'newBsuid': new_bsuid,
                'newParentBsuid': new_parent_bsuid,
                'newWaId': new_wa_id,
                'systemBody': system_data.get('body', ''),
                'requestId': request_id
            }))
            # Update contact with new BSUID and phone if available
            if new_bsuid and contact_id:
                try:
                    ct = dynamodb.Table(CONTACTS_TABLE)
                    update_expr = 'SET bsuid = :b'
                    expr_vals = {':b': new_bsuid}
                    if new_wa_id:
                        update_expr += ', phone = :p'
                        expr_vals[':p'] = new_wa_id
                    ct.update_item(
                        Key={'id': contact_id},
                        UpdateExpression=update_expr,
                        ExpressionAttributeValues=expr_vals
                    )
                except Exception as sys_err:
                    logger.warning(f'System user_changed_user_id update failed: {sys_err}')
            _store_system_event('user_changed_user_id', {
                'senderPhone': sender_phone,
                'contactId': contact_id,
                'newBsuid': new_bsuid,
                'newWaId': new_wa_id,
                'body': system_data.get('body', ''),
            }, request_id)
    
    # Handle REQUEST_CONTACT_INFO button response (contacts message with origin=contact_request)
    # Per Meta BSUID docs (May 2026): when user taps REQUEST_CONTACT_INFO button,
    # a contacts message is sent with origin "contact_request/other" containing vCard + phone
    if msg_type == 'contacts':
        msg_origin = message.get('origin', '')
        if 'contact_request' in msg_origin:
            msg_contacts = message.get('contacts', [])
            for mc in msg_contacts:
                phones = mc.get('phones', [])
                shared_phone = phones[0].get('phone', '') if phones else ''
                if shared_phone and contact_id:
                    try:
                        ct = dynamodb.Table(CONTACTS_TABLE)
                        ct.update_item(
                            Key={'id': contact_id},
                            UpdateExpression='SET phone = :p',
                            ExpressionAttributeValues={':p': shared_phone}
                        )
                        logger.info(json.dumps({
                            'event': 'contact_request_phone_captured',
                            'contactId': contact_id,
                            'sharedPhone': shared_phone,
                            'origin': msg_origin,
                            'requestId': request_id
                        }))
                    except Exception as cr_err:
                        logger.warning(f'Contact request phone update failed: {cr_err}')
    
    # Update Contact.lastInboundMessageAt for 24-hour window (+ WAMID for typing)
    _update_contact_timestamp(contact_id, now, wamid=whatsapp_message_id or '')
    
    logger.info(json.dumps({
        'event': 'message_stored',
        'messageId': message_id,
        'contactId': contact_id,
        'senderPhone': sender_phone,
        'senderName': sender_name,
        'whatsappMessageId': whatsapp_message_id,
        'type': msg_type,
        'hasMedia': bool(media_id),
        'receivingPhone': receiving_phone,
        'awsPhoneNumberId': aws_phone_number_id,
        'requestId': request_id
    }))
    
    # Auto-react with thumbs up (skip reactions to avoid loops)
    # Use the same phone number that received the message
    # Direct API for all phones
    if msg_type != 'reaction':
        # Set the current Direct API phone context for this message
        global _current_direct_api_phone
        _current_direct_api_phone = _get_meta_phone_id_for_direct_api(aws_phone_number_id)
        
        if _is_direct_api_phone(aws_phone_number_id):
            # Send reaction and read receipt via Meta Graph API
            try:
                if _auto_thumb_enabled():
                    _send_direct_api_reaction(sender_phone, whatsapp_message_id, emoji=AUTO_THUMB_EMOJI)
                logger.info(json.dumps({
                    'event': 'auto_reaction_triggered_direct_api',
                    'contactId': contact_id,
                    'whatsappMessageId': whatsapp_message_id,
                    'requestId': request_id
                }))
            except Exception as e:
                logger.warning(f"Direct API auto-reaction failed: {e}")
            try:
                _send_direct_api_read_receipt(whatsapp_message_id, show_typing=True)
                logger.info(json.dumps({
                    'event': 'read_receipt_sent_direct_api',
                    'whatsappMessageId': whatsapp_message_id,
                    'requestId': request_id
                }))
            except Exception as e:
                logger.warning(f"Direct API read receipt failed: {e}")
        else:
            _send_auto_reaction(
                contact_id=contact_id,
                whatsapp_message_id=whatsapp_message_id,
                phone_number_id=aws_phone_number_id,
                request_id=request_id
            )
            
            # Send read receipt to show message was received
            _send_read_receipt(
                whatsapp_message_id=whatsapp_message_id,
                phone_number_id=aws_phone_number_id,
                request_id=request_id
            )
    
    # ── request_welcome: user tapped "Start"  -  always send welcome + menu ──
    if msg_type == 'request_welcome':
        logger.info(json.dumps({
            'event': 'request_welcome_triggered',
            'contactId': contact_id,
            'senderPhone': sender_phone,
            'requestId': request_id,
        }))
        # Send ONLY the main menu (header/body already contains greeting)
        _send_interactive_list(
            contact_id=contact_id,
            phone_number_id=aws_phone_number_id,
            list_config=_get_welcome_config(),
            request_id=request_id
        )
        # Mark welcomeSent so brand-new contact path doesn't double-send
        try:
            dynamodb.Table(CONTACTS_TABLE).update_item(
                Key={'id': contact_id},
                UpdateExpression='SET welcomeSent = :t, welcomeSentAt = :ts',
                ExpressionAttributeValues={':t': True, ':ts': Decimal(str(now))}
            )
        except Exception:
            pass
        return  # Skip AI automation  -  welcome flow handled

    # ── Button type: "Get Started" quick reply or other button taps ──
    # WhatsApp "Get Started" ice-breaker sends msg_type='button' with text payload.
    # Treat button text as keyword input so it triggers the interactive menu.
    if msg_type == 'button' and content:
        button_text_lower = content.strip().lower()
        logger.info(json.dumps({
            'event': 'button_message_received',
            'buttonText': button_text_lower,
            'contactId': contact_id,
            'senderPhone': sender_phone,
            'requestId': request_id,
        }))
        # Map common button texts to menu trigger
        BUTTON_MENU_TRIGGERS = {'get started', 'start', 'menu', 'hi', 'hello', 'hey', 'main menu', 'need help!'}
        if button_text_lower in BUTTON_MENU_TRIGGERS or button_text_lower.startswith('get started'):
            _send_interactive_list(
                contact_id=contact_id,
                phone_number_id=aws_phone_number_id,
                list_config=_get_welcome_config(),
                request_id=request_id
            )
            logger.info(json.dumps({
                'event': 'button_triggered_menu_sent',
                'buttonText': button_text_lower,
                'contactId': contact_id,
                'requestId': request_id,
            }))
            return  # Skip AI automation — menu sent via button trigger

    # ── Keyword triggers (before AI automation) ──
    if msg_type == 'text' and content:
        content_lower = content.strip().lower()

        # ── Slash-command normalization (WhatsApp Conversational Components) ──
        # A configured command can be tapped OR typed with arguments/trailing
        # text, e.g. "/pay 500", "/menu ", "/imagine cars". Meta delivers the
        # FULL body. Collapse a KNOWN "/command [args]" to just the command
        # token so it reliably routes to the same handler as the bare command.
        # Unknown "/foo" is left intact so free-form input still reaches the AI.
        if content_lower.startswith('/'):
            _cmd_token = content_lower.split(None, 1)[0]
            _KNOWN_SLASH_COMMANDS = {
                '/menu', '/subscribe', '/bharatstack', '/selfservice',
                '/service', '/pay', '/help', '/commands',
            }
            if _cmd_token in _KNOWN_SLASH_COMMANDS:
                logger.info(json.dumps({
                    'event': 'slash_command_normalized',
                    'original': content_lower[:80], 'command': _cmd_token,
                    'contactId': contact_id, 'requestId': request_id,
                }))
                content_lower = _cmd_token

        # ── "Get my ID" / "my id" / "sub id" — fetch subscriber details ──
        MY_ID_KEYWORDS = {
            'my id', 'my sub id', 'sub id', 'subscriber id', 'my subscriber id',
            'get my id', 'get id', 'what is my id', 'whats my id',
            '/myid', '/id', 'show my id', 'my subscription', 'my subscription id',
            'find id', 'find my id', 'profile id', 'my profile id',
        }
        if content_lower in MY_ID_KEYWORDS:
            try:
                # Look up subscriber by phone
                fs_table = dynamodb.Table(os.environ.get('FLOW_SUBMISSIONS_TABLE', 'stack-wecare-digital-FlowSubmissionTable'))
                # Query by phone using GSI
                fs_resp = fs_table.scan(
                    FilterExpression='phone = :ph AND flowCode = :fc',
                    ExpressionAttributeValues={':ph': sender_phone, ':fc': 'WD_SUBSCRIBE'},
                    Limit=5,
                )
                subs = fs_resp.get('Items', [])
                if not subs:
                    # Try with normalized phone
                    norm = sender_phone.replace('+', '').replace(' ', '')
                    fs_resp = fs_table.scan(
                        FilterExpression='phone = :ph AND flowCode = :fc',
                        ExpressionAttributeValues={':ph': norm, ':fc': 'WD_SUBSCRIBE'},
                        Limit=5,
                    )
                    subs = fs_resp.get('Items', [])

                if subs:
                    # Get the latest subscription
                    latest = sorted(subs, key=lambda x: x.get('createdAt', 0), reverse=True)[0]
                    sub_id = latest.get('submissionId', 'N/A')
                    form_data = json.loads(latest.get('formData', '{}')) if latest.get('formData') else {}
                    name = form_data.get('full_name', '')
                    email = form_data.get('email_address', '')
                    org = form_data.get('company_name', '')
                    status = latest.get('status', 'active')

                    reply = (
                        f'🆔 *Your Subscriber Details*\n\n'
                        f'*Subscriber ID:* {sub_id}\n'
                        f'*Name:* {name}\n'
                        f'*Email:* {email}\n'
                        f'*Organization:* {org}\n'
                        f'*Status:* {status.title()}\n\n'
                        f'_Type "subscribe" to update your details._'
                    )
                else:
                    reply = (
                        '🔍 No subscription found for your number.\n\n'
                        'Type *subscribe* to register and get your subscriber ID.'
                    )

                _send_ai_auto_reply(contact_id, reply, aws_phone_number_id, request_id)
                return
            except Exception as e:
                logger.warning(f'My ID lookup failed: {e}')
                _send_ai_auto_reply(contact_id, '⚠️ Could not retrieve your details. Please try again.', aws_phone_number_id, request_id)
                return

        # Load flow triggers from SystemConfigTable (dashboard-configurable)
        flow_triggers = _get_flow_triggers_config()
        for flow_key, trigger in flow_triggers.items():
            if not trigger.get('enabled', True):
                continue
            keywords = [k.lower() for k in trigger.get('keywords', [])]
            if content_lower in keywords:
                flow_id = trigger.get('flowId', '')
                if not flow_id:
                    continue
                # All flow types use the same generic flow sender
                _send_generic_flow(
                    contact_id=contact_id,
                    phone_number_id=aws_phone_number_id,
                    sender_phone=sender_phone,
                    request_id=request_id,
                    flow_config=trigger,
                    flow_key=flow_key,
                )
                return  # Skip AI automation  -  flow handles the rest

        # ── Direct "Pay" keyword trigger (LLM-independent, hardcoded) ──
        # Exact matches (content_lower must be exactly one of these)
        PAY_KEYWORDS = {
            # English  -  core
            'pay', 'payment', 'pay now', 'pay bill', 'bill pay', '/pay',
            'pay due', 'pay dues', 'pay invoice', 'invoice',
            'pending payment', 'pending due', 'pending dues',
            'send payment', 'make payment', 'make a payment',
            'amount pay', 'pay amount',
            # English  -  conversational
            'i want to pay', 'i want pay', 'want to pay', 'wanna pay',
            'let me pay', 'ready to pay', 'how to pay', 'how do i pay',
            'what is my due', 'what are my dues', 'whats my due',
            'what is due', 'my due', 'my dues', 'my bill', 'my invoice',
            'show my bill', 'show my due', 'show my dues', 'show my invoice',
            'show invoice', 'show bill', 'show due', 'show dues',
            'check due', 'check dues', 'check bill', 'check invoice',
            'any due', 'any dues', 'any pending', 'any bill',
            'pending bill', 'pending bills', 'unpaid', 'unpaid bill',
            'outstanding', 'outstanding due', 'outstanding bill',
            'balance', 'balance due', 'due balance',
            'send bill', 'send invoice', 'resend invoice', 'resend bill',
            # Hindi / Hinglish
            'bhugtan', 'paisa', 'rupees', 'paise', 'kitna dena hai',
            'kitna baaki hai', 'baaki', 'baki', 'baaki hai', 'baki hai',
            'payment karo', 'payment kar do', 'pay karo', 'pay kar do',
            'bill bhejo', 'invoice bhejo', 'paisa dena hai', 'paise dene hai',
            'mera bill', 'mera due', 'mera invoice', 'mera baaki',
            'kितना बाकी है', 'भुगतान', 'बिल', 'पेमेंट',
        }
        # Fuzzy matches (content_lower contains any of these substrings)
        PAY_FUZZY = (
            'want to pay', 'wanna pay', 'make payment', 'pay my', 'pay the', 'pay for',
            'send me bill', 'send me invoice', 'send me due',
            'how much do i owe', 'how much i owe', 'what do i owe',
            'pending amount', 'due amount', 'total due',
            'kitna dena', 'kitna baaki', 'baaki kitna', 'payment bhej',
        )
        if content_lower in PAY_KEYWORDS or any(kw in content_lower for kw in PAY_FUZZY):
            logger.info(json.dumps({
                'event': 'pay_keyword_triggered',
                'content': content_lower,
                'contactId': contact_id,
                'senderPhone': sender_phone,
                'phoneNumberId': aws_phone_number_id,
                'requestId': request_id,
            }))
            # Phone 2: send CTA link to Phone 1 for payment
            if aws_phone_number_id == PHONE_NUMBER_ID_2:
                _send_cta_button(
                    contact_id=contact_id,
                    phone_number_id=aws_phone_number_id,
                    cta_text='Pay Now',
                    cta_url='https://r.wecare.digital/pay',
                    request_id=request_id,
                    body_text='\U0001f4b3 Make your payment quickly and securely online.',
                    footer_text='WECARE.DIGITAL',
                )
                _send_followup_buttons(contact_id, aws_phone_number_id, request_id)
                return
            # Phone 1: Step 1: Send "pulling" message immediately
            _send_ai_auto_reply(contact_id, PAY_MSG['pulling'], aws_phone_number_id, request_id)
            try:
                inv_payload = {
                    'rawPath': '/invoices/send-pending-by-phone',
                    'requestContext': {'http': {'method': 'POST'}},
                    'body': json.dumps({
                        'customerPhone': sender_phone,
                        'phoneNumberId': aws_phone_number_id,
                    }),
                }
                inv_response = lambda_client.invoke(
                    FunctionName='wecare-invoice-engine',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(inv_payload),
                )
                inv_result = json.loads(inv_response['Payload'].read())
                inv_body = json.loads(inv_result.get('body', '{}'))
                sent_count = inv_body.get('sent', 0)
                total_count = inv_body.get('total', 0)
                send_error = inv_body.get('error', '')

                if total_count == 0:
                    _send_ai_auto_reply(contact_id, PAY_MSG['no_dues'], aws_phone_number_id, request_id)
                elif sent_count == 0:
                    _send_ai_auto_reply(contact_id, PAY_MSG['send_failed'], aws_phone_number_id, request_id)
                    logger.warning(json.dumps({
                        'event': 'pay_keyword_send_failed',
                        'sent': 0, 'total': total_count,
                        'error': send_error, 'phone': sender_phone,
                        'requestId': request_id,
                    }))

                logger.info(json.dumps({
                    'event': 'pay_keyword_complete',
                    'sent': sent_count, 'total': total_count,
                    'phone': sender_phone, 'requestId': request_id,
                }))
            except Exception as pay_err:
                logger.error(json.dumps({
                    'event': 'pay_keyword_error',
                    'error': str(pay_err),
                    'phone': sender_phone,
                    'requestId': request_id,
                }))
                _send_ai_auto_reply(contact_id, PAY_MSG['error'], aws_phone_number_id, request_id)
            return  # Skip AI automation  -  payment flow handled

        # ── Direct "Hi" / greeting keyword trigger (LLM-independent) ──
        HI_KEYWORDS = {'hi', 'hello', 'hey', 'menu', 'main menu', 'show menu', 'start', 'browse menu', '/menu', 'need help!', 'get started'}
        if content_lower in HI_KEYWORDS:
            logger.info(json.dumps({
                'event': 'hi_keyword_triggered',
                'content': content_lower,
                'contactId': contact_id,
                'senderPhone': sender_phone,
                'requestId': request_id,
            }))
            # Send ONLY the main menu interactive list (no separate welcome text)
            # The menu header/body already contains the greeting
            _send_interactive_list(
                contact_id=contact_id,
                phone_number_id=aws_phone_number_id,
                list_config=_get_welcome_config(),
                request_id=request_id
            )
            logger.info(json.dumps({
                'event': 'hi_keyword_welcome_sent',
                'contactId': contact_id,
                'requestId': request_id,
            }))
            return  # Skip AI automation  -  welcome flow handled

        # ── Ice breaker: "Try Bharat Stack" / "/bharatstack" ──
        BHARAT_KEYWORDS = {'try bharat stack', 'bharat stack', '/bharatstack', 'bharat', 'aadhaar', 'upi', 'digilocker'}
        if content_lower in BHARAT_KEYWORDS:
            logger.info(json.dumps({
                'event': 'bharat_stack_triggered',
                'content': content_lower,
                'contactId': contact_id,
                'requestId': request_id,
            }))
            _send_cta_button(contact_id, aws_phone_number_id, 'Explore Bharat Stack', 'https://stack.wecare.digital', request_id,
                body_text="Explore Bharat Stack and discover services designed for everyday Bharat.",
                footer_text='WECARE.DIGITAL')
            _send_followup_buttons(contact_id, aws_phone_number_id, request_id)
            return

        # ── Ice breaker: "Self-service" / "/selfservice" ──
        SELFSERVICE_KEYWORDS = {'self-service', 'selfservice', 'self service', '/selfservice', '/service'}
        if content_lower in SELFSERVICE_KEYWORDS:
            logger.info(json.dumps({
                'event': 'selfservice_triggered',
                'content': content_lower,
                'contactId': contact_id,
                'requestId': request_id,
            }))
            _send_interactive_list(
                contact_id=contact_id,
                phone_number_id=aws_phone_number_id,
                list_config=_get_selfservice_menu(),
                request_id=request_id
            )
            return

        # ── Ice breaker: "Commands" / "/commands" / "/help" ──
        COMMANDS_KEYWORDS = {'commands', '/commands', '/help', 'help'}
        if content_lower in COMMANDS_KEYWORDS:
            commands_text = (
                "*Available Commands*\n\n"
                "/menu - Browse the main menu\n"
                "/subscribe - Register for updates and orders\n"
                "/bharatstack - Explore Bharat Stack services\n"
                "/selfservice - Self-service options\n"
                "/pay - Make a payment or check dues\n"
                "/help - Show this list"
            )
            _send_ai_auto_reply(contact_id, commands_text, aws_phone_number_id, request_id)
            return

        # ── Keyword: "store" / "shop" / "explore store" ──
        STORE_KEYWORDS = {'store', 'shop', 'explore store', 'brands', 'marketplace', '\U0001f6cd\ufe0f explore store'}
        if content_lower in STORE_KEYWORDS:
            _send_cta_button(contact_id, aws_phone_number_id, 'Explore Store', 'https://wecare.digital', request_id)
            return

        # ── Keyword: "gift card" / "gift" ──
        GIFT_KEYWORDS = {'gift card', 'gift cards', 'gift', 'buy gift card', '\U0001f381 gift cards'}
        if content_lower in GIFT_KEYWORDS:
            _send_cta_button(contact_id, aws_phone_number_id, 'Gift Cards', 'https://wecare.digital/gift-card', request_id)
            return

        # ── Keyword: "faq" / "faqs" / "help" / "questions" ──
        FAQ_KEYWORDS = {'faq', 'faqs', 'help', 'questions', 'common questions', '\u2753 faqs'}
        if content_lower in FAQ_KEYWORDS:
            _send_cta_button(contact_id, aws_phone_number_id, 'FAQs', 'https://wecare.digital/faq', request_id)
            return

        # ── Keyword: "about" / "about us" / "about wecare" ──
        ABOUT_KEYWORDS = {'about', 'about us', 'about wecare', 'about wecare.digital', '\U0001f49b about wecare.digital'}
        if content_lower in ABOUT_KEYWORDS:
            _send_cta_button(contact_id, aws_phone_number_id, 'About Us', 'https://wecare.digital', request_id)
            return

    # Process AI automation for supported message types
    # Now includes media types (image, audio, video, document) for multimodal AI
    ai_eligible_types = ['text', 'interactive', 'button', 'location', 'image', 'video', 'audio', 'document']

    # Auto-transcribe voice notes (audio messages) for English transcription display
    if msg_type == 'audio' and s3_key:
        _auto_transcribe_voice_note(message_id, s3_key, request_id)

    # ── Welcome message for brand-new contacts (independent of AI pipeline) ──
    # Check if welcome was already sent for this contact
    _welcome_already_sent = contact.get('welcomeSent') or contact.get('welcomeMessageSent')
    _is_brand_new_contact = not _welcome_already_sent
    if _is_brand_new_contact and msg_type in ('text', 'image', 'audio', 'video', 'document', 'request_welcome'):
        try:
            # Send ONLY the main menu (header/body already contains greeting)
            # No separate welcome text  -  the menu IS the welcome
            _send_interactive_list(
                contact_id=contact_id,
                phone_number_id=aws_phone_number_id,
                list_config=_get_welcome_config(),
                request_id=request_id
            )
            # Mark contact so welcome isn't sent again
            try:
                dynamodb.Table(CONTACTS_TABLE).update_item(
                    Key={'id': contact_id},
                    UpdateExpression='SET welcomeSent = :t, welcomeSentAt = :ts',
                    ExpressionAttributeValues={':t': True, ':ts': Decimal(str(now))}
                )
            except Exception:
                pass
            logger.info(json.dumps({
                'event': 'welcome_message_sent',
                'contactId': contact_id,
                'senderPhone': sender_phone,
                'requestId': request_id
            }))
        except Exception as _we:
            logger.warning(f"Welcome message failed (non-blocking): {_we}")

    if msg_type in ai_eligible_types and (content or s3_key) and not _is_brand_new_contact:
        # ── No auto-response for unmatched messages ──
        # Only keyword-triggered flows, welcome messages, and menu responses are sent.
        # Unmatched messages are stored but no reply is sent.
        # The admin can see all messages in the dashboard inbox and reply manually.
        pass


def _extract_content(message: Dict, msg_type: str) -> str:
    """Extract message content based on type. Delegates to modules.content."""
    return _extract_content_v2(message, msg_type)


def _extract_unsupported_content(message: Dict) -> str:
    """Extract info from unsupported message types. Delegates to modules.content."""
    return _extract_unsupported_content_v2(message)


def _message_exists(whatsapp_message_id: str) -> bool:
    """Check if message already exists (deduplication) using GSI query."""
    if not whatsapp_message_id:
        return False
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        response = messages_table.query(
            IndexName='whatsappMessageId-index',
            KeyConditionExpression='whatsappMessageId = :wmid',
            ExpressionAttributeValues={':wmid': whatsapp_message_id},
            Limit=1
        )
        return len(response.get('Items', [])) > 0
    except Exception as e:
        # Fallback to scan if GSI not ready yet
        logger.warning(f"GSI query failed, falling back to scan: {str(e)}")
        try:
            response = messages_table.scan(
                FilterExpression='whatsappMessageId = :wmid',
                ExpressionAttributeValues={':wmid': whatsapp_message_id},
                Limit=1
            )
            return len(response.get('Items', [])) > 0
        except Exception:
            return False


def _deterministic_contact_id(phone: str) -> str:
    """Stable, phone-derived contact id so ONE phone always maps to ONE contact
    (eliminates churn/duplicates from GSI eventual-consistency). Digits only."""
    digits = normalize_phone(phone) if phone else ''
    if not digits:
        digits = ''.join(c for c in (phone or '') if c.isdigit())
    return f'wa{digits}' if digits else ''


def _get_or_create_contact(phone: str, sender_name: str = '', bsuid: str = '', username: str = '', contact_book_name: str = '', parent_bsuid: str = '') -> Dict[str, Any]:
    """Get existing contact or create new one. Supports BSUID and parent BSUID lookup and storage.
    Uses a deterministic phone-derived id + strongly-consistent get_item so repeated
    inbound/outbound events never create duplicate (churned) contacts."""
    contacts_table = dynamodb.Table(CONTACTS_TABLE)

    # 0) Strongly-consistent lookup by deterministic phone id (no GSI lag / no churn)
    det_id = _deterministic_contact_id(phone)
    if det_id:
        try:
            r = contacts_table.get_item(Key={'id': det_id}, ConsistentRead=True)
            existing = r.get('Item')
            if existing and not existing.get('deletedAt'):
                _update_contact_bsuid_fields(contacts_table, existing, sender_name, username, phone, bsuid, contact_book_name, parent_bsuid)
                return existing
        except Exception as e:
            logger.warning(f"deterministic contact get failed for {det_id}: {e}")

    # Try BSUID lookup first (most reliable identifier going forward)
    if bsuid:
        try:
            response = contacts_table.query(
                IndexName='bsuid-index',
                KeyConditionExpression='bsuid = :bsuid',
                ExpressionAttributeValues={':bsuid': bsuid},
                Limit=10
            )
            bsuid_items = [i for i in response.get('Items', []) if not i.get('deletedAt')]
            if bsuid_items:
                contact = sorted(bsuid_items, key=lambda x: x.get('createdAt', 0))[0]
                # Update name/username/phone if available and contact doesn't have them
                _update_contact_bsuid_fields(contacts_table, contact, sender_name, username, phone, contact_book_name=contact_book_name, parent_bsuid=parent_bsuid)
                return contact
        except Exception as e:
            logger.warning(f"BSUID index query failed for {bsuid}: {str(e)}")
    
    # Clean phone for search - normalize to digits-only E.164
    clean_phone = normalize_phone(phone) if phone else ''
    if not clean_phone:
        clean_phone = phone.lstrip('+') if phone else ''
    phone_with_plus = f'+{clean_phone}' if clean_phone else ''
    
    # Use GSI query on phone-index for O(1) lookup (try both formats)
    items = []
    if clean_phone:
        for phone_variant in [phone_with_plus, clean_phone]:
            try:
                response = contacts_table.query(
                    IndexName='phone-index',
                    KeyConditionExpression='phone = :phone',
                    ExpressionAttributeValues={':phone': phone_variant},
                    Limit=10
                )
                variant_items = response.get('Items', [])
                # Filter out deleted contacts
                variant_items = [i for i in variant_items if not i.get('deletedAt')]
                items.extend(variant_items)
            except Exception as e:
                logger.warning(f"GSI phone-index query failed for {phone_variant}: {str(e)}")
    
    # Fallback to scan if GSI not ready
    if not items and clean_phone:
        try:
            response = contacts_table.scan(
                FilterExpression='(phone = :phone1 OR phone = :phone2) AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
                ExpressionAttributeValues={
                    ':phone1': clean_phone,
                    ':phone2': phone_with_plus,
                    ':null': None
                },
                Limit=100
            )
            items = response.get('Items', [])
        except Exception:
            items = []
    
    if items:
        # Deduplicate by id in case both phone formats matched the same contact
        seen_ids = set()
        unique_items = []
        for item in items:
            item_id = item.get('id', '')
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_items.append(item)
        items = unique_items
        
        # Return the first (oldest) contact to avoid duplicates
        contact = sorted(items, key=lambda x: x.get('createdAt', 0))[0]
        # Update name/BSUID/username if available
        _update_contact_bsuid_fields(contacts_table, contact, sender_name, username, phone, bsuid, contact_book_name, parent_bsuid)
        return contact
    
    # Create new contact with a DETERMINISTIC phone-derived id (idempotent).
    contact_id = det_id or str(uuid.uuid4())
    now = int(time.time())

    # Ensure phone has + prefix for international format (easier for SMS)
    formatted_phone = ''
    if phone:
        formatted_phone = phone if phone.startswith('+') else f'+{phone}'

    contact = {
        'id': contact_id,
        'contactId': contact_id,
        'name': sender_name or '',
        'phone': formatted_phone or None,
        'email': None,
        'bsuid': bsuid or None,  # Business-Scoped User ID
        'parentBsuid': parent_bsuid or None,  # Parent BSUID (linked account)
        'username': username or None,  # WhatsApp username
        'contactBookName': contact_book_name or None,  # Meta contact book name
        'optInWhatsApp': True,
        'optInSms': True,
        'optInEmail': True,
        'allowlistWhatsApp': True,
        'allowlistSms': True,
        'allowlistEmail': True,
        'lastInboundMessageAt': Decimal(str(now)),
        'createdAt': Decimal(str(now)),
        'updatedAt': Decimal(str(now)),
    }

    try:
        contacts_table.put_item(
            Item={k: v for k, v in contact.items() if v is not None},
            ConditionExpression='attribute_not_exists(id)',
        )
        logger.info(json.dumps({
            'event': 'contact_auto_created', 'contactId': contact_id,
            'phone': phone, 'name': sender_name, 'bsuid': bsuid, 'username': username,
        }))
        return contact
    except Exception as e:
        # Race: another invocation created it first — fetch and reuse (no duplicate).
        if 'ConditionalCheckFailedException' in str(e):
            try:
                r = contacts_table.get_item(Key={'id': contact_id}, ConsistentRead=True)
                existing = r.get('Item')
                if existing:
                    _update_contact_bsuid_fields(contacts_table, existing, sender_name, username, phone, bsuid, contact_book_name, parent_bsuid)
                    return existing
            except Exception:
                pass
        else:
            logger.warning(json.dumps({'event': 'contact_create_error', 'error': str(e), 'contactId': contact_id}))
        return contact


def _update_contact_bsuid_fields(contacts_table, contact: Dict, sender_name: str, username: str, phone: str = '', bsuid: str = '', contact_book_name: str = '', parent_bsuid: str = '') -> None:
    """Update contact with BSUID, parentBsuid, username, contactBookName, and name if they're new or changed."""
    updates = {}
    names = {}
    values = {}
    idx = 0
    
    current_name = contact.get('name', '')
    if sender_name and (not current_name or current_name in ['', '~', 'Unknown']):
        updates[f'#n{idx}'] = 'name'
        names[f'#n{idx}'] = 'name'
        values[f':v{idx}'] = sender_name
        contact['name'] = sender_name
        idx += 1
    
    if bsuid and not contact.get('bsuid'):
        names[f'#n{idx}'] = 'bsuid'
        values[f':v{idx}'] = bsuid
        contact['bsuid'] = bsuid
        idx += 1
    
    # Store parent BSUID if provided and different from current
    if parent_bsuid and contact.get('parentBsuid') != parent_bsuid:
        names[f'#n{idx}'] = 'parentBsuid'
        values[f':v{idx}'] = parent_bsuid
        contact['parentBsuid'] = parent_bsuid
        idx += 1
    
    if username and contact.get('username') != username:
        names[f'#n{idx}'] = 'username'
        values[f':v{idx}'] = username
        contact['username'] = username
        idx += 1
    
    # If contact has no phone but we have one now (BSUID-first contact getting phone)
    if phone and not contact.get('phone'):
        formatted = phone if phone.startswith('+') else f'+{phone.lstrip("+")}'
        names[f'#n{idx}'] = 'phone'
        values[f':v{idx}'] = formatted
        contact['phone'] = formatted
        idx += 1
    
    # Update contactBookName if provided and different
    if contact_book_name and contact.get('contactBookName') != contact_book_name:
        names[f'#n{idx}'] = 'contactBookName'
        values[f':v{idx}'] = contact_book_name
        contact['contactBookName'] = contact_book_name
        idx += 1
    
    if not names:
        return
    
    values[':now'] = Decimal(str(int(time.time())))
    names['#updatedAt'] = 'updatedAt'
    set_parts = [f'{k} = :v{i}' for i, k in enumerate(names.keys()) if k != '#updatedAt']
    set_parts.append('#updatedAt = :now')
    
    try:
        contacts_table.update_item(
            Key={'id': contact.get('id')},
            UpdateExpression='SET ' + ', '.join(set_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression='attribute_exists(id)',
        )
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'contact_bsuid_update_failed',
            'contactId': contact.get('id', ''),
            'error': str(e),
        }))


def _process_user_id_update(uid_update: Dict, contacts_map: Dict, request_id: str) -> None:
    """
    Handle user_id_update webhook  -  a user's BSUID has changed.
    Per Meta docs (field: user_id_update), the payload contains:
      user_id: { previous: "<OLD_BSUID>", current: "<NEW_BSUID>" }
      parent_user_id: { previous: "<OLD>", current: "<NEW>" }  (optional)
      wa_id: "<PHONE>" (optional)
    Updates the contact's BSUID and parentBsuid in DynamoDB.
    """
    user_id_obj = uid_update.get('user_id', {})
    old_user_id = user_id_obj.get('previous', '')
    new_user_id = user_id_obj.get('current', '')
    parent_id_obj = uid_update.get('parent_user_id', {})
    new_parent_id = parent_id_obj.get('current', '') if isinstance(parent_id_obj, dict) else ''
    wa_id = uid_update.get('wa_id', '')
    
    if not old_user_id or not new_user_id:
        logger.warning(json.dumps({
            'event': 'user_id_update_missing_ids',
            'old_user_id': old_user_id,
            'new_user_id': new_user_id,
            'requestId': request_id,
        }))
        return
    
    logger.info(json.dumps({
        'event': 'user_id_update_processing',
        'old_user_id': old_user_id,
        'new_user_id': new_user_id,
        'new_parent_id': new_parent_id,
        'requestId': request_id,
    }))
    
    contacts_table = dynamodb.Table(CONTACTS_TABLE)
    
    # Find contact by old BSUID
    try:
        response = contacts_table.query(
            IndexName='bsuid-index',
            KeyConditionExpression='bsuid = :bsuid',
            ExpressionAttributeValues={':bsuid': old_user_id},
            Limit=10
        )
        items = [i for i in response.get('Items', []) if not i.get('deletedAt')]
        
        if not items:
            logger.warning(json.dumps({
                'event': 'user_id_update_contact_not_found',
                'old_user_id': old_user_id,
                'requestId': request_id,
            }))
            return
        
        for contact in items:
            update_expr = 'SET bsuid = :new_bsuid, updatedAt = :now'
            expr_vals = {
                ':new_bsuid': new_user_id,
                ':now': Decimal(str(int(time.time()))),
            }
            # Also update parentBsuid if provided
            if new_parent_id:
                update_expr += ', parentBsuid = :new_parent'
                expr_vals[':new_parent'] = new_parent_id
            
            contacts_table.update_item(
                Key={'id': contact['id']},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_vals,
            )
            logger.info(json.dumps({
                'event': 'user_id_updated',
                'contactId': contact['id'],
                'old_bsuid': old_user_id,
                'new_bsuid': new_user_id,
                'new_parent_bsuid': new_parent_id,
                'requestId': request_id,
            }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'user_id_update_failed',
            'old_user_id': old_user_id,
            'new_user_id': new_user_id,
            'error': str(e),
            'requestId': request_id,
        }))


def _process_business_username_update(value: Dict, request_id: str) -> None:
    """Handle business_username_updates webhook — our business username status changed.

    Payload (per Meta BSUID doc): { display_phone_number, username, status }
    status: approved | reserved | deleted. Stores a SystemEvent and logs the
    status so the username claim lifecycle is observable end-to-end.
    """
    display_phone = value.get('display_phone_number', '')
    username = value.get('username', '')
    status = (value.get('status') or '').lower()

    # Audit trail (kept for the dashboard).
    _store_system_event('business_username_updates', value, request_id)

    logger.info(json.dumps({
        'event': 'business_username_update',
        'displayPhoneNumber': display_phone[:6] + '***' if display_phone else '',
        'username': username,
        'status': status,
        'requestId': request_id,
    }))

    # Best-effort: reflect the live username/status onto the FlowRegistry-adjacent
    # phone config if a WhatsAppPhone record exists (non-fatal if table absent).
    try:
        if status in ('approved', 'reserved', 'deleted') and display_phone:
            phones_table = dynamodb.Table(os.environ.get('WHATSAPP_PHONES_TABLE', 'stack-wecare-digital-WhatsAppPhonesTable'))
            phones_table.update_item(
                Key={'displayPhoneNumber': display_phone},
                UpdateExpression='SET businessUsername = :u, businessUsernameStatus = :s, updatedAt = :now',
                ExpressionAttributeValues={
                    ':u': '' if status == 'deleted' else username,
                    ':s': status,
                    ':now': Decimal(str(int(time.time()))),
                },
            )
    except Exception as e:
        # Table/record may not exist — the SystemEvent above is the source of truth.
        logger.info(json.dumps({
            'event': 'business_username_phone_update_skipped',
            'reason': str(e)[:160],
            'requestId': request_id,
        }))


def _update_contact_timestamp(contact_id: str, timestamp: int, wamid: str = '') -> None:
    """Update contact's lastInboundMessageAt for 24-hour window tracking.
    Also stores the latest inbound WAMID so outbound can show a typing indicator
    (Meta's typing_indicator API requires the customer's last received message_id)."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        if wamid:
            contacts_table.update_item(
                Key={'id': contact_id},
                UpdateExpression='SET lastInboundMessageAt = :ts, updatedAt = :ts, lastInboundWamid = :w',
                ExpressionAttributeValues={':ts': Decimal(str(timestamp)), ':w': wamid}
            )
        else:
            contacts_table.update_item(
                Key={'id': contact_id},
                UpdateExpression='SET lastInboundMessageAt = :ts, updatedAt = :ts',
                ExpressionAttributeValues={':ts': Decimal(str(timestamp))}
            )
    except Exception as e:
        logger.error(f"Failed to update contact timestamp: {str(e)}")


def _download_media_direct_api(whatsapp_media_id: str, message_id: str, media_type: str,
                               phone_number_id: str, request_id: str,
                               mime_type_hint: str = '') -> Optional[str]:
    """Download media via Meta Graph API for Direct API phones."""
    token = _load_direct_api_token()
    if not token:
        logger.error("No Direct API token for media download")
        return None
    app_secret = _direct_api_token_cache.get('app_secret', '')
    
    try:
        # Step 1: Get media URL from Meta
        url = f"https://graph.facebook.com/{META_API_VERSION}/{whatsapp_media_id}"
        if app_secret:
            proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
            url = f"{url}?appsecret_proof={proof}"
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            media_info = json.loads(resp.read().decode())
        
        media_url = media_info.get('url', '')
        mime_type = media_info.get('mime_type', mime_type_hint)
        if not media_url:
            logger.error(f"No media URL returned for {whatsapp_media_id}")
            return None
        
        # Step 2: Download the actual media file
        req2 = urllib.request.Request(media_url, headers={'Authorization': f'Bearer {token}'})
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            media_bytes = resp2.read()
        
        # Step 3: Upload to S3
        ext = _get_media_extension_from_mime(mime_type)
        s3_key = f"{MEDIA_PREFIX}wecare-digital-{message_id}{ext}"
        s3.put_object(Bucket=MEDIA_BUCKET, Key=s3_key, Body=media_bytes, ContentType=mime_type)
        
        logger.info(json.dumps({
            'event': 'media_download_direct_api',
            'mediaId': whatsapp_media_id,
            's3Key': s3_key,
            'size': len(media_bytes),
            'mimeType': mime_type,
            'requestId': request_id
        }))
        return s3_key
    except Exception as e:
        logger.error(f"Direct API media download failed: {e}")
        return None


def _get_media_extension_from_mime(mime_type: str) -> str:
    """Get file extension from MIME type."""
    MIME_MAP = {
        'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
        'audio/ogg': '.ogg', 'audio/mpeg': '.mp3', 'audio/aac': '.aac',
        'video/mp4': '.mp4', 'video/3gpp': '.3gp',
        'application/pdf': '.pdf', 'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/msword': '.doc', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    }
    return MIME_MAP.get(mime_type, '.bin')


def _download_media(whatsapp_media_id: str, message_id: str, media_type: str, 
                    phone_number_id: str, request_id: str,
                    mime_type_hint: str = '') -> Optional[str]:
    """
    Download media file from WhatsApp.
    Routes to Direct API for all phones.
    
    Per AWS docs (S3File.key): The key is a PREFIX  -  AWS appends the WhatsApp
    mediaId to create the final file path. For example:
      key = "audio/"             → final = "audio/{mediaId}.ogg"
    
    Strategy: Use MEDIA_PREFIX directly (ending with "/") so files land flat
    under stack/whatsapp-media/incoming/{mediaId}.{ext}, then rename to
    wecare-digital-{uuid}.{ext} format.
    
    Returns the actual S3 key of the downloaded file.
    """
    # Route Direct API phones to Meta Graph API download
    if _is_direct_api_phone(phone_number_id):
        return _download_media_direct_api(whatsapp_media_id, message_id, media_type,
                                          phone_number_id, request_id, mime_type_hint)
    
    try:
        # Use MEDIA_PREFIX directly  -  files land flat, no subfolders
        s3_key_prefix = MEDIA_PREFIX  # e.g. "stack/whatsapp-media/incoming/"
        
        logger.info(json.dumps({
            'event': 'media_download_start',
            'mediaId': whatsapp_media_id,
            's3KeyPrefix': s3_key_prefix,
            'mediaType': media_type,
            'mimeTypeHint': mime_type_hint,
            'phoneNumberId': phone_number_id,
            'requestId': request_id
        }))
        
        # Download media via Meta Graph API: GET /{media_id} → get URL → download → upload to S3
        meta_pid = _get_meta_phone_id_for_direct_api(phone_number_id)
        token = _load_direct_api_token()
        app_secret = _direct_api_token_cache.get('app_secret', '')

        # Step 1: Get media URL from Meta
        media_url_endpoint = f"https://graph.facebook.com/{META_API_VERSION}/{whatsapp_media_id}"
        if app_secret:
            proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
            media_url_endpoint = f"{media_url_endpoint}?appsecret_proof={proof}"
        media_req = urllib.request.Request(media_url_endpoint, headers={
            'Authorization': f'Bearer {token}',
        })
        with urllib.request.urlopen(media_req, timeout=15) as media_resp:
            media_info = json.loads(media_resp.read().decode())
        media_download_url = media_info.get('url', '')
        mime_type = media_info.get('mime_type', mime_type_hint or '')
        file_size = media_info.get('file_size', 0)

        # Step 2: Download the actual media file
        dl_req = urllib.request.Request(media_download_url, headers={
            'Authorization': f'Bearer {token}',
        })
        with urllib.request.urlopen(dl_req, timeout=60) as dl_resp:
            media_bytes = dl_resp.read()

        # Step 3: Determine extension and upload to S3
        ext_map = {
            'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
            'video/mp4': '.mp4', 'audio/ogg': '.ogg', 'audio/mpeg': '.mp3',
            'audio/aac': '.aac', 'application/pdf': '.pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        }
        ext = ext_map.get(mime_type, '')
        actual_s3_key = f"{s3_key_prefix}{whatsapp_media_id}{ext}"
        s3.put_object(
            Bucket=MEDIA_BUCKET,
            Key=actual_s3_key,
            Body=media_bytes,
            ContentType=mime_type or 'application/octet-stream',
        )
        
        # Rename to wecare-digital-{uuid}.{ext} format (flat, no nesting)
        ext = _get_extension_from_mime(mime_type) if mime_type else _get_extension_from_type(media_type)
        short_id = uuid.uuid4().hex[:8]
        renamed_key = f"{MEDIA_PREFIX}wecare-digital-{short_id}{ext}"
        try:
            s3.copy_object(
                Bucket=MEDIA_BUCKET,
                CopySource={'Bucket': MEDIA_BUCKET, 'Key': actual_s3_key},
                Key=renamed_key
            )
            s3.delete_object(Bucket=MEDIA_BUCKET, Key=actual_s3_key)
            logger.info(json.dumps({
                'event': 'media_renamed',
                'originalKey': actual_s3_key,
                'renamedKey': renamed_key,
                'requestId': request_id
            }))
            actual_s3_key = renamed_key
        except Exception as rename_err:
            logger.warning(json.dumps({
                'event': 'media_rename_failed',
                'originalKey': actual_s3_key,
                'targetKey': renamed_key,
                'error': str(rename_err),
                'requestId': request_id
            }))
        
        logger.info(json.dumps({
            'event': 'media_downloaded',
            'mediaId': whatsapp_media_id,
            's3KeyPrefix': s3_key_prefix,
            'actualS3Key': actual_s3_key,
            'mimeType': mime_type,
            'fileSize': file_size,
            'phoneNumberId': phone_number_id,
            'requestId': request_id
        }))
        
        return actual_s3_key
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'media_download_error',
            'mediaId': whatsapp_media_id,
            'error': str(e),
            'requestId': request_id
        }))
        return None


def _get_extension_from_type(media_type: str) -> str:
    """
    Get file extension based on WhatsApp message type.
    Used as fallback when mime_type is not available.
    
    Supported types per WhatsApp Business Platform Cloud API:
    - image: JPEG (5MB), PNG (5MB)
    - video: MP4 (16MB), 3GPP (16MB)
    - audio: AAC (16MB), AMR (16MB), MP3 (16MB), M4A (16MB), OGG (16MB)
    - document: PDF, TXT, DOC/DOCX, XLS/XLSX, PPT/PPTX (100MB)
    - sticker: WEBP (500KB animated, 100KB static)
    """
    type_extensions = {
        'image': '.jpeg',
        'video': '.mp4',
        'audio': '.ogg',
        'document': '.pdf',
        'sticker': '.webp'
    }
    return type_extensions.get(media_type, '.bin')


def _get_extension_from_mime(mime_type: str) -> str:
    """
    Get file extension based on MIME type.
    Complete mapping per WhatsApp Business Platform supported media types.
    """
    mime_extensions = {
        # Image formats (max 5MB)
        'image/jpeg': '.jpeg',
        'image/png': '.png',
        
        # Sticker formats (max 500KB animated, 100KB static)
        'image/webp': '.webp',
        
        # Video formats (max 16MB)
        'video/mp4': '.mp4',
        'video/3gpp': '.3gp',
        
        # Audio formats (max 16MB)
        'audio/aac': '.aac',
        'audio/amr': '.amr',
        'audio/mpeg': '.mp3',
        'audio/mp4': '.m4a',
        'audio/ogg': '.ogg',
        'audio/opus': '.opus',
        
        # Document formats (max 100MB)
        'application/pdf': '.pdf',
        'text/plain': '.txt',
        'application/msword': '.doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.ms-powerpoint': '.ppt',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    }
    return mime_extensions.get(mime_type, '.bin')


def _store_media_record(message_id: str, s3_key: str, media_data: Dict, whatsapp_media_id: str) -> Optional[str]:
    """
    Store media file record in MediaFiles table.
    Returns file_id if successful, None if table doesn't exist or write fails.
    This is optional - the s3Key is stored directly in the message record.
    """
    try:
        file_id = str(uuid.uuid4())
        now = int(time.time())
        
        media_record = {
            'fileId': file_id,
            'messageId': message_id,
            's3Key': s3_key,
            'contentType': media_data.get('mime_type', ''),
            'size': Decimal(str(media_data.get('file_size', 0))) if media_data.get('file_size') else None,
            'whatsappMediaId': whatsapp_media_id,
            'uploadedAt': Decimal(str(now)),
        }
        
        media_table = dynamodb.Table(MEDIA_FILES_TABLE)
        media_table.put_item(Item={k: v for k, v in media_record.items() if v is not None})
        
        logger.info(json.dumps({
            'event': 'media_record_stored',
            'fileId': file_id,
            'messageId': message_id,
            's3Key': s3_key
        }))
        
        return file_id
    except Exception as e:
        # MediaFile table may not exist - this is OK, s3Key is stored in message record
        logger.warning(json.dumps({
            'event': 'media_record_store_skipped',
            'messageId': message_id,
            's3Key': s3_key,
            'error': str(e),
            'note': 'MediaFile table write failed, but s3Key is stored in message record'
        }))
        return None


def _ingest_whatsapp_document(
    sender_phone: str, sender_name: str, contact_id: str, message_id: str,
    whatsapp_media_id: str, s3_key: str, msg_type: str,
    mime_type: str, filename: str, file_size: int, request_id: str,
):
    """
    GAP 2 FIX: Auto-ingest WhatsApp-uploaded documents into the DocumentsTable.
    This ensures documents sent via WhatsApp automatically appear in the
    Drop Docs admin page for review/approval.
    """
    DOCUMENTS_TABLE_NAME = os.environ.get('DOCUMENTS_TABLE', 'stack-wecare-digital-DocumentTable')
    try:
        doc_table = dynamodb.Table(DOCUMENTS_TABLE_NAME)
        doc_id = f'WD-DOC-{uuid.uuid4().hex[:8].upper()}'
        now = int(time.time())

        # Infer document type from mime type
        doc_type = 'other'
        if mime_type:
            if 'pdf' in mime_type:
                doc_type = 'prescription'  # PDFs often prescriptions
            elif 'image' in mime_type:
                doc_type = 'photo'
            elif 'spreadsheet' in mime_type or 'excel' in mime_type:
                doc_type = 'invoice'

        item = {
            'documentId': doc_id,
            'customerPhone': sender_phone,
            'customerName': sender_name or '',
            'contactId': contact_id or '',
            'sourceType': 'whatsapp',
            'sourceReferenceId': whatsapp_media_id,
            'documentType': doc_type,
            'fileName': filename or f'{msg_type}_{message_id[:8]}',
            'storageKey': s3_key,
            'mimeType': mime_type,
            'fileSize': file_size or 0,
            'verificationStatus': 'uploaded',
            'uploadedAt': now,
            'createdAt': now,
            'updatedAt': now,
        }
        item = {k: v for k, v in item.items() if v is not None and v != '' and v != 0}
        # Ensure required fields are present even if empty
        item.setdefault('verificationStatus', 'uploaded')
        item.setdefault('sourceType', 'whatsapp')

        doc_table.put_item(Item=item)
        logger.info(json.dumps({
            'event': 'whatsapp_document_ingested',
            'documentId': doc_id,
            'phone': sender_phone[-4:] if sender_phone else '',
            'type': doc_type,
            's3Key': s3_key,
            'requestId': request_id,
        }))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'whatsapp_document_ingest_failed',
            'error': str(e),
            'requestId': request_id,
        }))


def _meter_partner_usage(status: Dict, waba_id: str, request_id: str) -> None:
    """Charge a partner (Embedded-Signup) tenant's prepaid wallet for a billable
    message. No-op for platform-owned numbers (no wallet). Never raises."""
    if not partner_billing or not waba_id:
        return
    try:
        pricing = status.get('pricing', {}) or {}
        billable = pricing.get('billable', False)
        # Charge once per message on the 'sent' status (which carries pricing).
        if status.get('status') != 'sent' or not billable:
            return
        category = pricing.get('category', '') or ''
        msg_id = status.get('id', '')
        # Idempotency: charge once per message even if the 'sent' webhook is redelivered.
        try:
            from lambda_utils.webhook_dedup import claim_event
            if msg_id and not claim_event(f'meter_{msg_id}', source='partner_meter'):
                return
        except Exception:  # noqa: BLE001 — dedup must never block real metering
            pass
        res = partner_billing.charge(waba_id, category=category, message_id=msg_id,
                                     note='wa message', to_number=status.get('recipient_id', ''))
        if res.get('charged'):
            logger.info(json.dumps({'event': 'partner_usage_charged', 'wabaId': waba_id,
                                    'category': category, 'amount': res.get('amount'),
                                    'balance': res.get('balance'), 'requestId': request_id}))
    except Exception as e:  # noqa: BLE001
        logger.warning(json.dumps({'event': 'partner_metering_error', 'wabaId': waba_id, 'error': str(e)}))


def _process_status(status: Dict, request_id: str, contacts_map: Dict = None, waba_id: str = '') -> None:
    """
    Process message status update (sent|delivered|read|failed|payment).
    Checks BOTH InboundTable and OutboundTable using GSI for O(1) lookup.
    Extracts BSUID (recipient_user_id) and parent_recipient_user_id from status webhooks.
    
    Per Meta BSUID docs (Mar 2026): status webhooks now include a contacts array
    with user_id, username, wa_id, parent_user_id for sent/delivered/read statuses.
    
    Payment status webhooks have type='payment' with payment object containing:
    - reference_id: Order/invoice reference
    - amount: {value, offset}
    - currency: INR
    - status: pending|captured|failed
    """
    whatsapp_message_id = status.get('id')
    status_value = status.get('status')
    status_type = status.get('type', '')  # 'payment' for payment webhooks
    timestamp = int(status.get('timestamp', time.time()))
    recipient_id = status.get('recipient_id', '')
    recipient_user_id = status.get('recipient_user_id', '')  # BSUID
    parent_recipient_user_id = status.get('parent_recipient_user_id', '')  # Parent BSUID
    
    # Log all status updates for debugging
    logger.info(json.dumps({
        'event': 'status_update_received',
        'statusType': status_type,
        'statusValue': status_value,
        'whatsappMessageId': whatsapp_message_id,
        'recipientId': recipient_id,
        'hasPaymentData': 'payment' in status,
        'fullStatus': status,
        'requestId': request_id
    }))
    
    # Handle payment status webhooks FIRST (before other checks)
    if status_type == 'payment' or 'payment' in status:
        _process_payment_status(status, request_id)
        return
    
    if not whatsapp_message_id or not status_value:
        return

    # Meter partner (Embedded-Signup) tenant usage against their prepaid wallet.
    # No-op for platform-owned numbers. Guarded — never breaks status processing.
    _meter_partner_usage(status, waba_id, request_id)
    
    # Search BOTH tables for the message using GSI
    OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'stack-wecare-digital-WhatsAppOutboundTable')
    tables_to_check = [
        ('inbound', MESSAGES_TABLE),
        ('outbound', OUTBOUND_TABLE),
    ]
    
    updated = False
    for direction, table_name in tables_to_check:
        try:
            table = dynamodb.Table(table_name)
            
            # Use GSI query for O(1) lookup
            try:
                response = table.query(
                    IndexName='whatsappMessageId-index',
                    KeyConditionExpression='whatsappMessageId = :wmid',
                    ExpressionAttributeValues={':wmid': whatsapp_message_id},
                    Limit=1
                )
            except Exception:
                # Fallback to scan if GSI not ready
                response = table.scan(
                    FilterExpression='whatsappMessageId = :wmid',
                    ExpressionAttributeValues={':wmid': whatsapp_message_id},
                    Limit=1
                )
            
            items = response.get('Items', [])
            if items:
                message_id = items[0].get('id') or items[0].get('messageId')
                # Build update expression  -  include recipientBsuid and parentRecipientBsuid if available
                update_expr = 'SET #status = :status, statusUpdatedAt = :ts'
                expr_values = {
                    ':status': status_value,
                    ':ts': Decimal(str(timestamp))
                }
                if recipient_user_id:
                    update_expr += ', recipientBsuid = :rbsuid'
                    expr_values[':rbsuid'] = recipient_user_id
                if parent_recipient_user_id:
                    update_expr += ', parentRecipientBsuid = :prbsuid'
                    expr_values[':prbsuid'] = parent_recipient_user_id

                # Delivery-time failure: capture Meta error code + reason so the
                # inbox can show a tooltip explaining why the message wasn't
                # delivered (e.g. 131026 undeliverable, 131047 re-engagement).
                if status_value == 'failed':
                    status_errors = status.get('errors', []) or []
                    if status_errors:
                        e0 = status_errors[0]
                        err_code = e0.get('code')
                        err_reason = (e0.get('title') or e0.get('message')
                                      or (e0.get('error_data', {}) or {}).get('details', '') or '')
                        if err_code is not None:
                            update_expr += ', errorCode = :ec'
                            expr_values[':ec'] = int(err_code)
                        if err_reason:
                            update_expr += ', errorDetails = :ed'
                            expr_values[':ed'] = json.dumps({'code': err_code, 'message': err_reason})

                table.update_item(
                    Key={'id': message_id},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues=expr_values
                )

                # Mirror the same status onto the canonical MessagesTable (same id,
                # written by the dual-write). Guarded — never breaks status processing.
                if table_name != UNIFIED_MESSAGES_TABLE:
                    try:
                        dynamodb.Table(UNIFIED_MESSAGES_TABLE).update_item(
                            Key={'id': message_id},
                            UpdateExpression=update_expr,
                            ConditionExpression='attribute_exists(id)',
                            ExpressionAttributeNames={'#status': 'status'},
                            ExpressionAttributeValues=expr_values
                        )
                    except Exception as _ue:
                        logger.debug(f'canonical status mirror skipped for {message_id}: {_ue}')
                
                logger.info(json.dumps({
                    'event': 'status_updated',
                    'messageId': message_id,
                    'whatsappMessageId': whatsapp_message_id,
                    'status': status_value,
                    'table': direction,
                    'requestId': request_id
                }))
                updated = True
                break  # Found and updated, no need to check other table
                
        except Exception as e:
            logger.error(json.dumps({
                'event': 'status_update_error',
                'whatsappMessageId': whatsapp_message_id,
                'table': direction,
                'error': str(e),
                'requestId': request_id
            }))
    
    if not updated:
        # Downgrade to debug  -  this is normal for auto-reaction/read-receipt messages
        # which are not stored in the outbound table
        logger.debug(json.dumps({
            'event': 'status_update_message_not_found',
            'whatsappMessageId': whatsapp_message_id,
            'status': status_value,
            'requestId': request_id
        }))
    
    # Enrich contact records from status webhook contacts array
    # Per Meta BSUID docs: sent/delivered/read status webhooks include a contacts
    # array with user_id (BSUID), username, wa_id, parent_user_id
    if contacts_map and status_value in ('sent', 'delivered', 'read'):
        for ckey, centry in contacts_map.items():
            if not isinstance(centry, dict):
                continue
            c_bsuid = centry.get('bsuid', '')
            c_username = centry.get('username', '')
            c_phone = centry.get('wa_id', '') if 'wa_id' in centry else ''
            c_parent_bsuid = centry.get('parent_bsuid', '')
            if not c_bsuid:
                continue
            try:
                # Try to find contact by BSUID and update username/phone if new
                contacts_table = dynamodb.Table(CONTACTS_TABLE)
                bsuid_resp = contacts_table.query(
                    IndexName='bsuid-index',
                    KeyConditionExpression='bsuid = :b',
                    ExpressionAttributeValues={':b': c_bsuid},
                    Limit=1
                )
                if bsuid_resp.get('Items'):
                    existing = bsuid_resp['Items'][0]
                    _update_contact_bsuid_fields(
                        contacts_table, existing,
                        sender_name=centry.get('name', ''),
                        username=c_username,
                        phone=c_phone,
                        bsuid=c_bsuid,
                        parent_bsuid=c_parent_bsuid,
                    )
            except Exception as enrich_err:
                logger.debug(f'Status contact enrichment skipped: {enrich_err}')


def _sanitize_reference_id(reference_id: str) -> str:
    """
    Sanitize reference_id - remove duplicate prefixes and underscores.
    
    WhatsApp/Razorpay may return reference_id with extra prefixes or underscores.
    This ensures clean WD-PAY-<ID> format for display.
    
    Examples:
    - "WD-PAY-ABC12345" -> "WD-PAY-ABC12345" (keep as-is)
    - "WD-PAY-WD-PAY-ABC" -> "WD-PAY-ABC" (remove duplicate prefix)
    - "WD_41BA3534" -> "WD-PAY-41BA3534" (upgrade old format)
    - "WDABC12345" -> "WD-PAY-ABC12345" (upgrade old format)
    - "WD+41BA3534" -> "WD-PAY-41BA3534" (remove plus sign)
    """
    import re
    
    if not reference_id:
        return reference_id
    
    stripped = reference_id.strip().upper()
    
    # Remove duplicate WD-PAY- prefixes
    while 'WD-PAY-WD-PAY-' in stripped:
        stripped = stripped.replace('WD-PAY-WD-PAY-', 'WD-PAY-')
    
    # Already in new format
    if stripped.startswith('WD-PAY-'):
        return stripped
    if stripped.startswith('WD-ORD-'):
        return stripped
    
    # Old format: strip non-alnum, remove legacy WD prefix(es), add WD-PAY-
    cleaned = re.sub(r'[^A-Za-z0-9]', '', stripped)
    while cleaned.startswith('WD'):
        cleaned = cleaned[2:]
    if not cleaned:
        return stripped  # Return original if nothing left
    
    return f'WD-PAY-{cleaned}'


def _process_payment_status(status: Dict, request_id: str) -> None:
    """
    Process payment status webhook from WhatsApp.
    
    Payment webhook format:
    {
        "id": "wamid.xxx",
        "recipient_id": "919876543210",
        "type": "payment",
        "status": "captured",  // pending, captured, failed
        "payment": {
            "reference_id": "ORDER_12345",
            "amount": {"value": 10000, "offset": 100},
            "currency": "INR",
            "transaction": {
                "id": "txn_xxx",
                "type": "upi",
                "status": "success"
            }
        },
        "timestamp": "1706140800"
    }
    """
    # Log full status for debugging
    logger.info(json.dumps({
        'event': 'payment_status_processing',
        'fullStatus': status,
        'requestId': request_id
    }))
    
    payment_data = status.get('payment', {})
    raw_reference_id = payment_data.get('reference_id', '')
    # Sanitize reference_id - remove duplicate WD prefix and underscores
    reference_id = _sanitize_reference_id(raw_reference_id)
    payment_status = status.get('status', '')
    recipient_id = status.get('recipient_id', '')
    timestamp = int(status.get('timestamp', time.time()))
    
    # Log payment data extraction
    logger.info(json.dumps({
        'event': 'payment_data_extracted',
        'paymentData': payment_data,
        'referenceId': reference_id,
        'paymentStatus': payment_status,
        'recipientId': recipient_id,
        'requestId': request_id
    }))
    
    amount = payment_data.get('amount', {})
    amount_value = amount.get('value', 0)
    amount_offset = amount.get('offset', 100)
    currency = payment_data.get('currency', 'INR')
    
    # Log amount extraction with full details
    logger.info(json.dumps({
        'event': 'payment_amount_extracted',
        'amountObject': amount,
        'amountValue': amount_value,
        'amountOffset': amount_offset,
        'paymentDataKeys': list(payment_data.keys()) if payment_data else [],
        'requestId': request_id
    }))
    
    # Calculate actual amount (value / offset)
    actual_amount = amount_value / amount_offset if amount_offset else amount_value
    
    # If amount is 0, try to look up from original payment request in DynamoDB
    if actual_amount == 0 and reference_id:
        logger.info(json.dumps({
            'event': 'payment_amount_zero_lookup',
            'referenceId': reference_id,
            'requestId': request_id
        }))
        actual_amount = _lookup_payment_amount(reference_id, request_id)
    
    transaction = payment_data.get('transaction', {})
    transaction_id = transaction.get('id', '')
    transaction_type = transaction.get('type', '')
    
    logger.info(json.dumps({
        'event': 'payment_status_received',
        'referenceId': reference_id,
        'paymentStatus': payment_status,
        'recipientId': recipient_id,
        'amount': actual_amount,
        'currency': currency,
        'transactionId': transaction_id,
        'transactionType': transaction_type,
        'requestId': request_id
    }))
    
    # Store payment record in DynamoDB
    _store_payment_record(
        reference_id=reference_id,
        recipient_id=recipient_id,
        payment_status=payment_status,
        amount_value=amount_value,
        amount_offset=amount_offset,
        currency=currency,
        transaction=transaction,
        timestamp=timestamp,
        request_id=request_id,
        full_payment_data=payment_data,
    )
    
    # Look up the phone_number_id from the original outbound payment request
    # so the confirmation goes back from the same business number
    originating_phone_id = None
    if reference_id:
        try:
            OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'stack-wecare-digital-WhatsAppOutboundTable')
            outbound_table = dynamodb.Table(OUTBOUND_TABLE)
            # Query GSI paymentReferenceId-index (falls back to scan if GSI missing)
            found = False
            try:
                resp = outbound_table.query(
                    IndexName='paymentReferenceId-index',
                    KeyConditionExpression='paymentReferenceId = :ref',
                    ExpressionAttributeValues={':ref': reference_id},
                    Limit=1,
                )
                items = resp.get('Items', [])
                if items:
                    originating_phone_id = items[0].get('awsPhoneNumberId') or items[0].get('phoneNumberId')
                    found = True
            except Exception:
                # Fallback to paginated scan if GSI not yet active
                scan_kwargs = {
                    'FilterExpression': 'paymentReferenceId = :ref',
                    'ExpressionAttributeValues': {':ref': reference_id},
                    'ProjectionExpression': 'awsPhoneNumberId, phoneNumberId',
                }
                while not found:
                    resp = outbound_table.scan(**scan_kwargs)
                    items = resp.get('Items', [])
                    if items:
                        originating_phone_id = items[0].get('awsPhoneNumberId') or items[0].get('phoneNumberId')
                        found = True
                    elif 'LastEvaluatedKey' in resp:
                        scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
                    else:
                        break
            
            logger.info(json.dumps({
                'event': 'payment_phone_id_resolved',
                'referenceId': reference_id,
                'phoneNumberId': originating_phone_id,
                'found': found,
                'requestId': request_id
            }))
        except Exception as e:
            logger.warning(json.dumps({
                'event': 'payment_phone_id_lookup_failed',
                'referenceId': reference_id,
                'error': str(e),
                'requestId': request_id
            }))

    # Detect effective failure: WhatsApp may send status="pending" but
    # transaction.status="failed" (e.g. insufficient funds / gateway error).
    transaction_status = transaction.get('status', '')
    effective_failed = (
        payment_status == 'failed'
        or (payment_status == 'pending' and transaction_status in ('failed', 'error'))
    )

    # Send order_status message based on payment status
    if payment_status == 'captured':
        # ── Security: Verify payment via Meta Payment Lookup API ──
        # Meta docs: "must not rely solely on the status of the transaction provided in the webhook"
        payment_verified = True  # Default to trust webhook, but log verification result
        if reference_id and originating_phone_id:
            try:
                # Look up payment config from the original outbound message
                OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'stack-wecare-digital-WhatsAppOutboundTable')
                outbound_table = dynamodb.Table(OUTBOUND_TABLE)
                config_name = ''
                try:
                    resp = outbound_table.query(
                        IndexName='paymentReferenceId-index',
                        KeyConditionExpression='paymentReferenceId = :ref',
                        ExpressionAttributeValues={':ref': reference_id},
                        Limit=1,
                    )
                    items = resp.get('Items', [])
                    if items:
                        config_name = items[0].get('paymentConfigName', '')
                except Exception:
                    pass

                if config_name:
                    import urllib.request, urllib.error
                    # Call Meta Payment Lookup API
                    meta_phone_id = originating_phone_id
                    # Extract Meta phone ID if in internal format
                    if '-direct-' in meta_phone_id:
                        meta_phone_id = meta_phone_id.split('-direct-')[-1]

                    token = _load_direct_api_token()
                    lookup_url = f"https://graph.facebook.com/v25.0/{meta_phone_id}/payments/{config_name}/{reference_id}"
                    req = urllib.request.Request(lookup_url, headers={
                        'Authorization': f'Bearer {token}',
                    }, method='GET')
                    try:
                        with urllib.request.urlopen(req, timeout=10) as r:
                            lookup_result = json.loads(r.read().decode())
                        payments = lookup_result.get('payments', [])
                        if payments:
                            lookup_status = payments[0].get('status', '')
                            if lookup_status != 'captured':
                                payment_verified = False
                                logger.warning(json.dumps({
                                    'event': 'payment_lookup_mismatch',
                                    'webhookStatus': 'captured',
                                    'lookupStatus': lookup_status,
                                    'referenceId': reference_id,
                                    'requestId': request_id,
                                }))
                            else:
                                logger.info(json.dumps({
                                    'event': 'payment_lookup_verified',
                                    'referenceId': reference_id,
                                    'requestId': request_id,
                                }))
                    except Exception as lookup_err:
                        # Don't block payment on lookup failure  -  log and proceed
                        logger.warning(json.dumps({
                            'event': 'payment_lookup_failed',
                            'error': str(lookup_err)[:200],
                            'referenceId': reference_id,
                            'requestId': request_id,
                        }))
            except Exception as e:
                logger.warning(json.dumps({
                    'event': 'payment_verification_error',
                    'error': str(e)[:200],
                    'requestId': request_id,
                }))

        if not payment_verified:
            logger.error(json.dumps({
                'event': 'payment_capture_unverified_skipping',
                'referenceId': reference_id,
                'requestId': request_id,
            }))
            return

        # ── Direct invoice status update in InvoicesTable ──
        # Ensures the invoice is marked paid even if the dedup path in
        # create_invoice is skipped (e.g. invoice was created from dashboard).
        _mark_invoice_paid_by_reference(reference_id, request_id)

        _send_order_status_message(
            recipient_id=recipient_id,
            reference_id=reference_id,
            order_status='completed',
            amount=actual_amount,
            description=PAY_MSG['paid'],
            request_id=request_id,
            phone_number_id=originating_phone_id
        )
        # Generate and send invoice after successful payment
        _generate_invoice_for_captured_payment(
            reference_id=reference_id,
            recipient_id=recipient_id,
            actual_amount=actual_amount,
            phone_number_id=originating_phone_id,
            request_id=request_id,
        )
        # Check for remaining pending dues and notify
        _check_and_notify_balance_due(
            recipient_id=recipient_id,
            paid_reference_id=reference_id,
            phone_number_id=originating_phone_id,
            request_id=request_id,
        )
    elif effective_failed:
        logger.info(json.dumps({
            'event': 'payment_effective_failure',
            'paymentStatus': payment_status,
            'transactionStatus': transaction_status,
            'referenceId': reference_id,
            'requestId': request_id,
        }))
        _send_order_status_message(
            recipient_id=recipient_id,
            reference_id=reference_id,
            order_status='canceled',
            amount=0,
            description=PAY_MSG['pay_failed'],
            request_id=request_id,
            phone_number_id=originating_phone_id
        )
    elif payment_status == 'pending':
        # Genuine pending (transaction still in progress)  -  log and wait
        logger.info(json.dumps({
            'event': 'payment_pending_waiting',
            'referenceId': reference_id,
            'transactionStatus': transaction_status,
            'requestId': request_id,
        }))


def _mark_invoice_paid_by_reference(reference_id: str, request_id: str) -> None:
    """Directly update InvoicesTable: set status=paid for the given referenceId.
    This is a safety net so the invoice is always marked paid on capture,
    regardless of whether the dedup path in create_invoice runs later."""
    if not reference_id:
        return
    try:
        import datetime
        table = dynamodb.Table(INVOICES_TABLE)
        now = int(time.time())
        now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        paid_at_ts = int(now_ist.timestamp())

        # Use referenceId GSI instead of table scan
        found = []
        query_kwargs = {
            'IndexName': 'referenceId-index',
            'KeyConditionExpression': 'referenceId = :ref',
            'ExpressionAttributeValues': {':ref': reference_id},
        }
        resp = table.query(**query_kwargs)
        found.extend(resp.get('Items', []))
        while 'LastEvaluatedKey' in resp:
            query_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            resp = table.query(**query_kwargs)
            found.extend(resp.get('Items', []))

        for inv in found:
            if inv.get('status') != 'paid':
                table.update_item(
                    Key={'invoiceId': inv['invoiceId']},
                    UpdateExpression='SET #st = :st, #ps = :ps, #pa = :pa, #ua = :now',
                    ExpressionAttributeNames={
                        '#st': 'status', '#ps': 'paymentStatus',
                        '#pa': 'paidAt', '#ua': 'updatedAt',
                    },
                    ExpressionAttributeValues={
                        ':st': 'paid', ':ps': 'captured',
                        ':pa': paid_at_ts, ':now': now,
                    },
                )
                logger.info(json.dumps({
                    'event': 'invoice_marked_paid_direct',
                    'invoiceId': inv['invoiceId'],
                    'referenceId': reference_id,
                    'requestId': request_id,
                }))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'mark_invoice_paid_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id,
        }))


def _generate_invoice_for_captured_payment(reference_id: str, recipient_id: str,
                                           actual_amount: float, phone_number_id: str,
                                           request_id: str) -> None:
    """
    After WhatsApp payment captured: create invoice via unified invoice engine.
    Uses wecare-invoice-engine Lambda for proper GST sequencing (WD/FY/NNNNN).
    Also sends the invoice image on WhatsApp automatically.
    """
    import datetime
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        items = []

        # Try GSI query first, fall back to scan if index doesn't exist
        try:
            resp = messages_table.query(
                IndexName='messageId-index',
                KeyConditionExpression='messageId = :mid',
                ExpressionAttributeValues={':mid': reference_id},
                Limit=1,
            )
            items = resp.get('Items', [])
        except Exception as gsi_err:
            logger.info(json.dumps({
                'event': 'invoice_gsi_fallback',
                'referenceId': reference_id,
                'gsiError': str(gsi_err)[:100],
                'requestId': request_id,
            }))

        # Fallback: scan for paymentReferenceId (paginate to find it)
        if not items:
            scan_kwargs = {
                'FilterExpression': 'paymentReferenceId = :ref AND messageType = :mt',
                'ExpressionAttributeValues': {':ref': reference_id, ':mt': 'payment_request'},
            }
            while not items:
                resp = messages_table.scan(**scan_kwargs)
                items = resp.get('Items', [])
                if items:
                    break
                if 'LastEvaluatedKey' in resp:
                    scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
                else:
                    break

        if not items:
            logger.warning(json.dumps({
                'event': 'invoice_no_payment_request_found',
                'referenceId': reference_id,
                'requestId': request_id,
            }))
            return

        pr = items[0]
        contact_id = pr.get('contactId', '')
        sender_phone = pr.get('senderPhone', recipient_id)

        # Extract fields from payment_request record
        unit_price = float(pr.get('paymentAmount', 0)) / 100  # stored in paise
        quantity = int(pr.get('paymentQuantity', 1))
        item_name = pr.get('paymentItemName', 'Services/Goods')
        gst_rate = float(pr.get('paymentGstRate', 18))
        shipping = float(pr.get('paymentShipping', 0)) / 100  # stored in paise
        handling = float(pr.get('paymentHandling', 0)) / 100  # stored in paise
        discount = float(pr.get('paymentDiscount', 0)) / 100  # stored in paise
        purpose = pr.get('paymentPurpose', '')
        order_id = pr.get('paymentOrderId', 'Offline')
        customer_name = pr.get('paymentCustomerName', '')
        customer_phone = pr.get('paymentCustomerPhone', sender_phone)
        customer_email = pr.get('paymentCustomerEmail', '')
        shipping_address = pr.get('paymentShippingAddress', '')
        billing_address = pr.get('paymentBillingAddress', '')

        now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        paid_at_ts = int(now_ist.timestamp())

        # ── Step 1: Create invoice via unified invoice engine ──
        invoice_payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'customerName': customer_name,
                'customerPhone': customer_phone,
                'paidByPhone': customer_phone,
                'customerEmail': customer_email,
                'shippingAddress': shipping_address,
                'billingAddress': billing_address,
                'catalogRetailerId': pr.get('catalogRetailerId', ''),
                'items': [{'name': item_name, 'amount': unit_price, 'quantity': quantity}],
                'gstRate': gst_rate,
                'shipping': shipping,
                'handling': handling,
                'discount': discount,
                'purpose': purpose,
                'orderId': order_id,
                'referenceId': reference_id,
                'entryPoint': 'whatsapp_payment',
                'status': 'paid',
                'paymentStatus': 'captured',
                'paidAt': paid_at_ts,
            }),
            'rawPath': '/invoices',
            'requestContext': {'http': {'method': 'POST'}},
        }

        inv_response = lambda_client.invoke(
            FunctionName='wecare-invoice-engine',
            InvocationType='RequestResponse',
            Payload=json.dumps(invoice_payload),
        )
        inv_result = json.loads(inv_response['Payload'].read())
        inv_body = json.loads(inv_result.get('body', '{}'))
        invoice_id = inv_body.get('invoiceId', '')
        invoice_number = inv_body.get('invoiceNumber', '')

        logger.info(json.dumps({
            'event': 'invoice_created_via_engine',
            'invoiceId': invoice_id,
            'invoiceNumber': invoice_number,
            'referenceId': reference_id,
            'entryPoint': 'whatsapp_payment',
            'requestId': request_id,
        }))

        if not invoice_id:
            logger.error(json.dumps({
                'event': 'invoice_engine_empty_response',
                'referenceId': reference_id,
                'response': str(inv_body),
                'requestId': request_id,
            }))
            return

        # ── Step 2: Generate invoice image ──
        try:
            img_payload = {
                'rawPath': f'/invoices/{invoice_id}/generate-image',
                'requestContext': {'http': {'method': 'POST'}},
                'pathParameters': {'invoiceId': invoice_id},
                'body': json.dumps({'invoiceId': invoice_id}),
            }
            img_response = lambda_client.invoke(
                FunctionName='wecare-invoice-engine',
                InvocationType='RequestResponse',
                Payload=json.dumps(img_payload),
            )
            img_result = json.loads(img_response['Payload'].read())
            img_body = json.loads(img_result.get('body', '{}'))
            image_url = img_body.get('imageUrl', '')
            logger.info(json.dumps({
                'event': 'invoice_image_generated',
                'invoiceId': invoice_id,
                'imageUrl': image_url,
                'requestId': request_id,
            }))
        except Exception as img_err:
            logger.error(json.dumps({
                'event': 'invoice_image_error',
                'invoiceId': invoice_id,
                'error': str(img_err),
                'requestId': request_id,
            }))

        # ── Step 3: Send invoice on WhatsApp ──
        if invoice_id and customer_phone:
            try:
                send_phone_id = phone_number_id or PHONE_NUMBER_ID_1
                send_payload = {
                    'rawPath': f'/invoices/{invoice_id}/send-whatsapp',
                    'requestContext': {'http': {'method': 'POST'}},
                    'pathParameters': {'invoiceId': invoice_id},
                    'body': json.dumps({
                        'invoiceId': invoice_id,
                        'toWhatsAppNumber': customer_phone,
                        'phoneNumberId': send_phone_id,
                    }),
                }
                lambda_client.invoke(
                    FunctionName='wecare-invoice-engine',
                    InvocationType='Event',  # Async
                    Payload=json.dumps(send_payload),
                )
                logger.info(json.dumps({
                    'event': 'invoice_whatsapp_triggered',
                    'invoiceId': invoice_id,
                    'toPhone': customer_phone,
                    'requestId': request_id,
                }))
            except Exception as send_err:
                logger.error(json.dumps({
                    'event': 'invoice_whatsapp_error',
                    'invoiceId': invoice_id,
                    'error': str(send_err),
                    'requestId': request_id,
                }))

        # ── Step 4: Generate PDF (async) ──
        try:
            pdf_payload = {
                'rawPath': f'/invoices/{invoice_id}/generate-pdf',
                'requestContext': {'http': {'method': 'POST'}},
                'pathParameters': {'invoiceId': invoice_id},
                'body': json.dumps({'invoiceId': invoice_id}),
            }
            lambda_client.invoke(
                FunctionName='wecare-invoice-engine',
                InvocationType='Event',
                Payload=json.dumps(pdf_payload),
            )
        except Exception as pdf_err:
            logger.error(json.dumps({
                'event': 'invoice_pdf_error',
                'invoiceId': invoice_id,
                'error': str(pdf_err),
                'requestId': request_id,
            }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'invoice_for_captured_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id,
        }))


def _auto_next_due_enabled() -> bool:
    """Config toggle for the post-payment 'next due' auto-push. Default OFF —
    auto-sending the next pending invoice + a balance-due nag right after a
    customer pays is spammy (a payment produced 5-6 messages). Businesses that
    want sequential bill collection can enable SystemConfig id='whatsapp_auto_next_due'."""
    try:
        item = dynamodb.Table(SYSTEM_CONFIG_TABLE).get_item(Key={'id': 'whatsapp_auto_next_due'}).get('Item')
        if item and 'configValue' in item:
            return str(item.get('configValue')).lower() in ('true', '1', 'yes', 'on')
    except Exception:
        pass
    return False


def _check_and_notify_balance_due(recipient_id: str, paid_reference_id: str,
                                  phone_number_id: str, request_id: str) -> None:
    """After a payment is captured, check InvoicesTable for remaining pending dues.
    If found, auto-send the next payment link (sequential pay) and notify user.
    Gated behind whatsapp_auto_next_due (default OFF) to avoid post-payment spam.
    """
    if not _auto_next_due_enabled():
        logger.info(json.dumps({'event': 'balance_due_followup_skipped',
                                'reason': 'auto_next_due disabled', 'requestId': request_id}))
        return
    try:
        clean_phone = recipient_id.replace('+', '').replace(' ', '').replace('-', '')
        # Normalize to 10-digit local number for strict matching
        if clean_phone.startswith('91') and len(clean_phone) == 12:
            local10 = clean_phone[2:]
        elif clean_phone.startswith('0') and len(clean_phone) == 11:
            local10 = clean_phone[1:]
        elif len(clean_phone) == 10:
            local10 = clean_phone
        else:
            local10 = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone

        # Query InvoicesTable for remaining pending invoices (source of truth)
        invoices_table = dynamodb.Table(INVOICES_TABLE)
        pending_statuses = ['created', 'pending_payment', 'sent']
        remaining = []

        scan_kwargs = {
            'FilterExpression': boto3.dynamodb.conditions.Attr('status').is_in(pending_statuses),
            'ConsistentRead': True,
        }
        while True:
            resp = invoices_table.scan(**scan_kwargs)
            for item in resp.get('Items', []):
                inv_phone_raw = (item.get('customerPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                # Normalize invoice phone to 10-digit local
                if inv_phone_raw.startswith('91') and len(inv_phone_raw) == 12:
                    inv_local10 = inv_phone_raw[2:]
                elif inv_phone_raw.startswith('0') and len(inv_phone_raw) == 11:
                    inv_local10 = inv_phone_raw[1:]
                elif len(inv_phone_raw) == 10:
                    inv_local10 = inv_phone_raw
                else:
                    inv_local10 = inv_phone_raw[-10:] if len(inv_phone_raw) >= 10 else inv_phone_raw
                inv_ref = item.get('referenceId', '')
                inv_ps = item.get('paymentStatus', '')
                # STRICT match: full 10-digit local number must match exactly
                if inv_local10 == local10 and len(local10) == 10 and inv_ref != paid_reference_id and inv_ps not in ('captured', 'paid', 'refunded'):
                    remaining.append(item)
            if 'LastEvaluatedKey' in resp:
                scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            else:
                break

        if not remaining:
            # All clear  -  send congratulations
            contact = _get_contact_by_phone(recipient_id)
            contact_id = contact.get('id', '') if contact else ''
            contact_phone = contact.get('phone', f'+{clean_phone}') if contact else f'+{clean_phone}'
            payload = {
                'body': json.dumps({
                    'contactId': contact_id if contact_id else None,
                    'recipientPhone': contact_phone,
                    'content': PAY_MSG['all_clear'],
                    'phoneNumberId': phone_number_id or PHONE_NUMBER_ID_1,
                })
            }
            lambda_client.invoke(
                FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
                InvocationType='Event',
                Payload=json.dumps(payload)
            )
            return

        # Sort oldest first
        remaining.sort(key=lambda x: int(x.get('createdAt', 0)))

        # Build summary
        total_bal = sum(float(inv.get('total', 0)) for inv in remaining)
        summary_msg = PAY_MSG['next_due'].format(total=f'{total_bal:,.2f}')

        # Send summary text
        contact = _get_contact_by_phone(recipient_id)
        contact_id = contact.get('id', '') if contact else ''
        contact_phone = contact.get('phone', f'+{clean_phone}') if contact else f'+{clean_phone}'
        sending_phone_id = phone_number_id or PHONE_NUMBER_ID_1

        payload = {
            'body': json.dumps({
                'contactId': contact_id if contact_id else None,
                'recipientPhone': contact_phone,
                'content': summary_msg,
                'phoneNumberId': sending_phone_id,
            })
        }
        lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        # Auto-send payment link for the next (oldest) pending invoice
        next_inv = remaining[0]
        next_id = next_inv.get('invoiceId', '')
        next_pg_config = next_inv.get('paymentConfiguration', '')
        try:
            inv_payload = {
                'rawPath': f'/invoices/{next_id}/send-payment-link',
                'requestContext': {'http': {'method': 'POST'}},
                'pathParameters': {'invoiceId': next_id},
                'body': json.dumps({
                    'invoiceId': next_id,
                    'phoneNumberId': sending_phone_id,
                    'paymentConfiguration': next_pg_config,
                }),
            }
            lambda_client.invoke(
                FunctionName='wecare-invoice-engine',
                InvocationType='Event',
                Payload=json.dumps(inv_payload),
            )
            logger.info(json.dumps({
                'event': 'next_payment_auto_sent',
                'invoiceId': next_id,
                'remainingCount': len(remaining),
                'requestId': request_id,
            }))
        except Exception as link_err:
            logger.warning(json.dumps({
                'event': 'next_payment_auto_send_error',
                'invoiceId': next_id,
                'error': str(link_err),
                'requestId': request_id,
            }))

        logger.info(json.dumps({
            'event': 'balance_due_notification_sent',
            'recipientId': recipient_id,
            'remainingDues': len(remaining),
            'totalBalance': total_bal,
            'requestId': request_id,
        }))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'balance_due_check_error',
            'error': str(e),
            'requestId': request_id,
        }))


def _store_payment_record(reference_id: str, recipient_id: str, payment_status: str,
                          amount_value: int, amount_offset: int, currency: str,
                          transaction: Dict = None, timestamp: int = 0,
                          request_id: str = '', full_payment_data: Dict = None) -> None:
    """Store payment record in Messages table for tracking.
    Stores full transaction object: pg_transaction_id, method.type, error.code/reason.
    Also parses and stores refund data from Meta payment webhooks."""
    if transaction is None:
        transaction = {}
    if full_payment_data is None:
        full_payment_data = {}
    try:
        # Find contact by phone number
        contact = _get_contact_by_phone(recipient_id)
        contact_id = contact.get('id', '') if contact else ''
        
        payment_id = str(uuid.uuid4())
        now = int(time.time())
        expires_at = now + MESSAGE_TTL_SECONDS
        
        # Calculate actual amount
        actual_amount = amount_value / amount_offset if amount_offset else amount_value

        # Extract full transaction fields (Gap 5)
        transaction_id = transaction.get('id', '')
        transaction_type = transaction.get('type', '')
        pg_transaction_id = transaction.get('pg_transaction_id', '')
        transaction_status = transaction.get('status', '')
        txn_method = transaction.get('method', {})
        txn_method_type = txn_method.get('type', '') if isinstance(txn_method, dict) else str(txn_method)
        txn_error = transaction.get('error', {})
        txn_error_code = txn_error.get('code', '') if isinstance(txn_error, dict) else ''
        txn_error_reason = txn_error.get('reason', '') if isinstance(txn_error, dict) else ''
        txn_created = transaction.get('created_timestamp', 0)
        txn_updated = transaction.get('updated_timestamp', 0)

        # Parse refund data from Meta payment webhooks (Gap 6)
        refunds_raw = full_payment_data.get('refunds', [])
        refunds_json = ''
        if refunds_raw:
            refunds_json = json.dumps(refunds_raw, default=str)[:4000]

        # Parse PG-specific UDF/notes echoed back in webhook
        webhook_notes = full_payment_data.get('notes', {})
        webhook_receipt = full_payment_data.get('receipt', '')
        webhook_udf1 = full_payment_data.get('udf1', '')
        webhook_udf2 = full_payment_data.get('udf2', '')
        webhook_udf3 = full_payment_data.get('udf3', '')
        webhook_udf4 = full_payment_data.get('udf4', '')
        
        payment_record = {
            'id': payment_id,
            'messageId': payment_id,
            'contactId': contact_id,
            'channel': 'whatsapp',
            'direction': 'inbound',
            'messageType': 'payment',
            'content': f'Payment {payment_status}: ₹{actual_amount:.2f} ({currency})',
            'status': payment_status,
            'senderPhone': recipient_id,
            # Payment-specific fields
            'paymentReferenceId': reference_id,
            'paymentStatus': payment_status,
            'paymentAmount': Decimal(str(amount_value)),
            'paymentOffset': Decimal(str(amount_offset)),
            'paymentCurrency': currency,
            # Full transaction object (Gap 5)
            'transactionId': transaction_id,
            'transactionType': transaction_type,
            'pgTransactionId': pg_transaction_id,
            'transactionStatus': transaction_status,
            'paymentMethodType': txn_method_type,
            'errorCode': txn_error_code,
            'errorReason': txn_error_reason,
            'txnCreatedAt': Decimal(str(txn_created)) if txn_created else None,
            'txnUpdatedAt': Decimal(str(txn_updated)) if txn_updated else None,
            # Refund data (Gap 6)
            'refundsJson': refunds_json if refunds_json else None,
            # PG-specific fields echoed back
            'webhookNotes': json.dumps(webhook_notes, default=str)[:2000] if webhook_notes else None,
            'webhookReceipt': webhook_receipt if webhook_receipt else None,
            'webhookUdf1': webhook_udf1 if webhook_udf1 else None,
            'webhookUdf2': webhook_udf2 if webhook_udf2 else None,
            'webhookUdf3': webhook_udf3 if webhook_udf3 else None,
            'webhookUdf4': webhook_udf4 if webhook_udf4 else None,
            'timestamp': Decimal(str(timestamp)),
            'createdAt': Decimal(str(now)),
            'expiresAt': Decimal(str(expires_at)),
        }
        
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        messages_table.put_item(Item={k: v for k, v in payment_record.items() if v is not None and v != ''})

        # Unified Inbox dual-write — mirror payment record to canonical MessagesTable so
        # the dashboard (reads canonical) shows payments. Guarded; sparse contactId.
        if MESSAGES_TABLE != UNIFIED_MESSAGES_TABLE:
            try:
                dynamodb.Table(UNIFIED_MESSAGES_TABLE).put_item(
                    Item={k: v for k, v in payment_record.items() if v is not None and v != ''}
                )
            except Exception as _ce:
                logger.warning(f'payment record canonical mirror skipped: {_ce}')
        
        # Link payment to SubmitRequest if reference_id starts with WD-PAY- or SR- (legacy)
        if reference_id and (reference_id.startswith('WD-PAY-') or reference_id.startswith('SR-')):
            _update_submit_request_payment(reference_id, payment_status, transaction_id, request_id)
        
        logger.info(json.dumps({
            'event': 'payment_record_stored',
            'paymentId': payment_id,
            'referenceId': reference_id,
            'contactId': contact_id,
            'paymentStatus': payment_status,
            'amount': actual_amount,
            'pgTransactionId': pg_transaction_id,
            'methodType': txn_method_type,
            'hasRefunds': bool(refunds_raw),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'payment_record_store_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id
        }))


def _update_submit_request_payment(reference_id: str, payment_status: str,
                                    transaction_id: str, request_id: str) -> None:
    """Update SubmitRequest record with payment status when payment webhook arrives."""
    try:
        table = dynamodb.Table(SUBMIT_REQUESTS_TABLE)
        now = int(time.time())
        # Query by paymentReferenceId GSI
        resp = table.query(
            IndexName='paymentReferenceId',
            KeyConditionExpression='paymentReferenceId = :ref',
            ExpressionAttributeValues={':ref': reference_id},
            Limit=1,
        )
        items = resp.get('Items', [])
        if items:
            submission_id = items[0]['id']
            table.update_item(
                Key={'id': submission_id},
                UpdateExpression='SET paymentStatus = :s, transactionId = :t, updatedAt = :u',
                ExpressionAttributeValues={
                    ':s': payment_status,
                    ':t': transaction_id,
                    ':u': Decimal(str(now)),
                },
            )
            logger.info(json.dumps({
                'event': 'submit_request_payment_linked',
                'submissionId': submission_id,
                'referenceId': reference_id,
                'paymentStatus': payment_status,
                'requestId': request_id,
            }))
        else:
            logger.warning(json.dumps({
                'event': 'submit_request_not_found_for_payment',
                'referenceId': reference_id,
                'requestId': request_id,
            }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'submit_request_payment_link_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id,
        }))


def _get_contact_by_phone(phone: str) -> Optional[Dict]:
    """Get contact by phone number using GSI for O(1) lookup."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        # Clean phone number - handle various formats
        clean_phone = phone.lstrip('+')
        phone_with_plus = f'+{clean_phone}'
        
        logger.info(json.dumps({
            'event': 'contact_lookup_by_phone',
            'originalPhone': phone,
            'cleanPhone': clean_phone,
            'phoneWithPlus': phone_with_plus
        }))
        
        # Use GSI query on phone-index for O(1) lookup
        for phone_variant in [phone_with_plus, clean_phone, phone]:
            try:
                response = contacts_table.query(
                    IndexName='phone-index',
                    KeyConditionExpression='phone = :phone',
                    ExpressionAttributeValues={':phone': phone_variant},
                    Limit=5
                )
                items = response.get('Items', [])
                # Filter out deleted contacts
                items = [i for i in items if not i.get('deletedAt')]
                if items:
                    logger.info(json.dumps({
                        'event': 'contact_lookup_result',
                        'phone': phone,
                        'foundCount': len(items),
                        'contactId': items[0].get('id', ''),
                        'method': 'gsi'
                    }))
                    return items[0]
            except Exception:
                pass  # GSI not ready, will fallback below
        
        # Fallback to scan if GSI not ready
        response = contacts_table.scan(
            FilterExpression='(phone = :phone1 OR phone = :phone2 OR phone = :phone3) AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={
                ':phone1': clean_phone,
                ':phone2': phone_with_plus,
                ':phone3': phone,
                ':null': None
            },
            Limit=10
        )
        
        items = response.get('Items', [])
        
        logger.info(json.dumps({
            'event': 'contact_lookup_result',
            'phone': phone,
            'foundCount': len(items),
            'contactId': items[0].get('id', '') if items else None,
            'method': 'scan_fallback'
        }))
        
        return items[0] if items else None
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'contact_lookup_error',
            'phone': phone,
            'error': str(e)
        }))
        return None


def _lookup_payment_amount(reference_id: str, request_id: str) -> float:
    """
    Look up payment amount from original payment request in Messages table.
    This is a fallback when WhatsApp webhook doesn't include the amount.
    
    The original payment request message stores the amount in the content field
    or in a dedicated paymentAmount field.
    """
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        
        # Sanitize reference_id for lookup
        sanitized_ref = _sanitize_reference_id(reference_id)
        
        # Extract just the ID part (without WD-PAY- or legacy WD prefix) for broader search
        id_part = sanitized_ref
        for pfx in ('WD-PAY-', 'WD-ORD-', 'WD'):
            if id_part.startswith(pfx):
                id_part = id_part[len(pfx):]
                break
        
        # Look for the original payment request message by reference_id
        # Search with multiple variations to handle format differences
        response = messages_table.scan(
            FilterExpression='paymentReferenceId = :ref1 OR paymentReferenceId = :ref2 OR contains(content, :id_part)',
            ExpressionAttributeValues={
                ':ref1': sanitized_ref,
                ':ref2': reference_id,  # Also try original format
                ':id_part': id_part
            },
            Limit=10
        )
        
        items = response.get('Items', [])
        
        logger.info(json.dumps({
            'event': 'payment_amount_lookup_result',
            'referenceId': reference_id,
            'sanitizedRef': sanitized_ref,
            'idPart': id_part,
            'foundCount': len(items),
            'requestId': request_id
        }))
        
        # Look for amount in the found records
        for item in items:
            # Check for paymentAmount field (stored in paise)
            payment_amount = item.get('paymentAmount')
            if payment_amount:
                offset = item.get('paymentOffset', 100)
                amount = float(payment_amount) / float(offset)
                logger.info(json.dumps({
                    'event': 'payment_amount_found_in_record',
                    'referenceId': reference_id,
                    'amount': amount,
                    'requestId': request_id
                }))
                return amount
            
            # Try to extract from content (e.g., "Payment request: ₹500.00")
            content = item.get('content', '')
            if '₹' in content:
                import re
                match = re.search(r'₹([\d,]+\.?\d*)', content)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    logger.info(json.dumps({
                        'event': 'payment_amount_extracted_from_content',
                        'referenceId': reference_id,
                        'amount': amount,
                        'content': content[:100],
                        'requestId': request_id
                    }))
                    return amount
        
        logger.warning(json.dumps({
            'event': 'payment_amount_not_found',
            'referenceId': reference_id,
            'requestId': request_id
        }))
        return 0.0
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'payment_amount_lookup_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id
        }))
        return 0.0


def _inbound_order_status_enabled() -> bool:
    """The razorpay-webhook is the authoritative payment path and already sends the
    order-status confirmation on payment.captured. This inbound (Meta payment webhook)
    path would send a SECOND, duplicate confirmation. Gated OFF by default to avoid
    the duplicate; enable SystemConfig id='whatsapp_inbound_order_status' to restore."""
    try:
        item = dynamodb.Table(SYSTEM_CONFIG_TABLE).get_item(Key={'id': 'whatsapp_inbound_order_status'}).get('Item')
        if item and 'configValue' in item:
            return str(item.get('configValue')).lower() in ('true', '1', 'yes', 'on')
    except Exception:
        pass
    return False


def _send_order_status_message(recipient_id: str, reference_id: str, 
                                order_status: str, amount: float, description: str,
                                request_id: str, phone_number_id: str = None) -> None:
    """
    Send order_status interactive message to confirm payment status.
    Uses the phone_number_id that received the original payment if available,
    otherwise falls back to PHONE_NUMBER_ID_1.
    """
    if not _inbound_order_status_enabled():
        logger.info(json.dumps({'event': 'order_status_skipped_dedup',
                                'reason': 'razorpay-webhook is sole sender',
                                'referenceId': reference_id, 'requestId': request_id}))
        return
    try:
        # Find contact by phone number
        contact = _get_contact_by_phone(recipient_id)
        
        if not contact:
            logger.warning(json.dumps({
                'event': 'order_status_no_contact',
                'recipientId': recipient_id,
                'referenceId': reference_id,
                'requestId': request_id,
                'note': 'Will try to send using phone number directly'
            }))
            # Create a minimal contact object with phone number
            # Format phone for WhatsApp: +91XXXXXXXXXX
            formatted_phone = f'+{recipient_id}' if not recipient_id.startswith('+') else recipient_id
            contact = {'id': '', 'phone': formatted_phone}
        
        contact_id = contact.get('id', '')
        contact_phone = contact.get('phone', f'+{recipient_id}')
        
        # Build order_status payload - send directly to outbound Lambda
        # Use the phone number that received the original message, or fall back to default
        sending_phone_id = phone_number_id or PHONE_NUMBER_ID_1
        order_status_payload = {
            'body': json.dumps({
                'contactId': contact_id if contact_id else None,
                'recipientPhone': contact_phone,  # Fallback to phone if no contactId
                'phoneNumberId': sending_phone_id,
                'isOrderStatus': True,
                'orderStatusDetails': {
                    'reference_id': reference_id,
                    'order_status': order_status,
                    'amount': amount,  # Amount in rupees for display
                    'description': description
                }
            })
        }
        
        logger.info(json.dumps({
            'event': 'order_status_message_sending',
            'contactId': contact_id,
            'contactPhone': contact_phone,
            'referenceId': reference_id,
            'orderStatus': order_status,
            'amount': amount,
            'sendingPhoneId': sending_phone_id,
            'requestId': request_id
        }))
        
        # Invoke outbound Lambda to send order_status message
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',  # Async
            Payload=json.dumps(order_status_payload)
        )
        
        logger.info(json.dumps({
            'event': 'order_status_message_triggered',
            'contactId': contact_id,
            'contactPhone': contact_phone,
            'referenceId': reference_id,
            'orderStatus': order_status,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'order_status_message_error',
            'recipientId': recipient_id,
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_to_dlq(record: Dict, error: str, request_id: str) -> None:
    """Send failed message to inbound-dlq."""
    if not INBOUND_DLQ_URL:
        return
    
    try:
        sqs.send_message(
            QueueUrl=INBOUND_DLQ_URL,
            MessageBody=json.dumps({
                'originalRecord': record,
                'error': error,
                'timestamp': int(time.time()),
                'requestId': request_id
            }, default=str)
        )
    except Exception as e:
        logger.error(json.dumps({
            'event': 'dlq_send_error',
            'error': str(e),
            'requestId': request_id
        }))


CALLING_TABLE = os.environ.get('CALL_LOG_TABLE', 'stack-wecare-digital-WhatsAppCallingTable')


def _forward_call_permission_to_calling_table(sender_phone: str, receiving_phone: str,
                                               aws_phone_number_id: str,
                                               interactive: Dict) -> None:
    """
    DEPRECATED: No longer called. Permission is auto-granted pre/post call.
    Kept for reference only — will be removed in next cleanup.
    """
    pass


def _handle_ivr_response(sender_phone: str, aws_phone_number_id: str,
                          button_id: str, request_id: str) -> None:
    """
    Handle IVR button responses from the calling IVR menu.
    Button IDs are prefixed with 'ivr_' (e.g. ivr_sales, ivr_support, ivr_ai, ivr_callback).
    Sends the appropriate follow-up message and optionally notifies the team.
    """
    # IVR response definitions
    IVR_RESPONSES = {
        'ivr_sales': {
            'text': (
                "🛒 *Sales & Orders*\n\n"
                "How can we help?\n\n"
                "• Send your *order number* to check status\n"
                "• Send a *product name* to browse our catalog\n"
                "• Type *\"new order\"* to place an order\n\n"
                "A team member will also be notified to assist you."
            ),
            'notify': True,
            'dept': 'sales',
        },
        'ivr_support': {
            'text': (
                "🔧 *Support*\n\n"
                "Please describe your issue and we'll get back to you shortly.\n\n"
                "You can:\n"
                "• Type your question\n"
                "• Send a screenshot\n"
                "• Send a voice note\n\n"
                "Our AI assistant will try to help immediately, "
                "and a human agent will follow up if needed."
            ),
            'notify': True,
            'dept': 'support',
        },
        'ivr_ai': {
            'text': (
                "🤖 *AI Assistant*\n\n"
                "I'm ready to help! You can:\n\n"
                "• Type your question\n"
                "• Send a *voice note*  -  I'll listen and reply with voice\n"
                "• Send a *photo*  -  I can analyze images too\n\n"
                "Ask me anything about our products, services, or orders."
            ),
            'notify': False,
            'dept': 'ai',
        },
        'ivr_callback': {
            'text': (
                "📞 *Callback Request*\n\n"
                "Got it! We'll call you back as soon as possible.\n\n"
                "If you'd like to specify a preferred time, just type it "
                "(e.g. \"Call me at 3 PM\" or \"Tomorrow morning\")."
            ),
            'notify': True,
            'dept': 'callback',
        },
    }

    response_config = IVR_RESPONSES.get(button_id)
    if not response_config:
        logger.warning(f"Unknown IVR button: {button_id}")
        return

    logger.info(json.dumps({
        'event': 'ivr_response',
        'senderPhone': sender_phone,
        'buttonId': button_id,
        'department': response_config['dept'],
        'requestId': request_id,
    }))

    try:
        # Send the follow-up message
        if not sender_phone.startswith('+'):
            to_number = f'+{sender_phone}'
        else:
            to_number = sender_phone

        msg_payload = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'text',
            'text': {'body': response_config['text']},
        }

        # All phones use Direct API
        if _is_direct_api_phone(aws_phone_number_id):
            result = _send_direct_api_message(to_number, msg_payload)
            if result.get('error'):
                logger.error(f"IVR Direct API send failed for {button_id}: {result}")
            else:
                logger.info(f"IVR response sent via Direct API to {sender_phone} for {button_id}")
        else:
            meta_pid = _get_meta_phone_id_for_direct_api(aws_phone_number_id)
            _send_direct_api_message(sender_phone, msg_payload, meta_phone_id=meta_pid)
            logger.info(f"IVR response sent to {sender_phone} for {button_id}")

        # Store IVR selection in SystemEvent table for tracking/analytics
        try:
            now = int(time.time())
            system_events_table = dynamodb.Table(
                os.environ.get('SYSTEM_EVENTS_TABLE', 'stack-wecare-digital-SystemEventTable')
            )
            system_events_table.put_item(Item={
                'id': f"ivr_{sender_phone}_{now}",
                'eventType': 'ivr_selection',
                'phoneNumber': sender_phone,
                'phoneNumberId': aws_phone_number_id,
                'buttonId': button_id,
                'department': response_config['dept'],
                'notifyTeam': response_config['notify'],
                'createdAt': Decimal(str(now)),
                'ttl': Decimal(str(now + 90 * 24 * 60 * 60)),
            })
        except Exception as e:
            logger.warning(f"Failed to store IVR event: {e}")

    except Exception as e:
        logger.error(f"Failed to send IVR response for {button_id}: {e}")


def _send_auto_reaction(contact_id: str, whatsapp_message_id: str, 
                        phone_number_id: str, request_id: str) -> None:
    """
    Send automatic thumbs up reaction to inbound message.
    Uses the same phone number that received the message.
    """
    if not whatsapp_message_id:
        return
    
    try:
        reaction_payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'isReaction': True,
                'reactionMessageId': whatsapp_message_id,
                'reactionEmoji': '\U0001F44D',  # Thumbs up
                'phoneNumberId': phone_number_id  # Use same phone that received
            })
        }
        
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(reaction_payload)
        )
        
        logger.info(json.dumps({
            'event': 'auto_reaction_triggered',
            'contactId': contact_id,
            'whatsappMessageId': whatsapp_message_id,
            'phoneNumberId': phone_number_id,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'auto_reaction_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_ai_auto_reply(contact_id: str, content: str, phone_number_id: str, request_id: str) -> None:
    """
    Send AI-generated auto-reply to WhatsApp.
    Uses the same phone number that received the message.
    """
    if not content or not content.strip() or not contact_id:
        return
    
    try:
        reply_payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'content': content,
                'phoneNumberId': phone_number_id
            })
        }
        
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',  # Async - don't wait for response
            Payload=json.dumps(reply_payload)
        )
        
        logger.info(json.dumps({
            'event': 'ai_auto_reply_triggered',
            'contactId': contact_id,
            'contentLength': len(content),
            'phoneNumberId': phone_number_id,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_auto_reply_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_submit_request_flow(contact_id: str, phone_number_id: str, sender_phone: str, request_id: str, flow_config: Dict = None) -> None:
    """
    Send the Submit Request WhatsApp Flow to the user.
    Passes sender's phone number so the endpoint can fetch their orders.
    Message content is configurable via flow_config (from SystemConfigTable).
    """
    try:
        # Resolve flow ID: config override > env var
        flow_id = (flow_config or {}).get('flowId', '') or SUBMIT_REQUEST_FLOW_ID
        msg = (flow_config or {}).get('message', {})

        # Encode phone in flow_token so the flow-data endpoint can extract it
        # during INIT (data_exchange mode doesn't pass custom data in the message)
        # Format: {prefix}-{uuid}-waba-{phone_number_id_suffix}-ph-{sender_phone}
        # The waba segment tells the flow-data endpoint which WABA phone sent this flow
        _waba_suffix = '1' if phone_number_id == PHONE_NUMBER_ID_1 else '2'
        flow_token = f'sr-{uuid.uuid4()}-waba-{_waba_suffix}-ph-{sender_phone}'
        interactive_data = {
            'body': msg.get('body', '\U0001f447Please use the self-service option below. Once we receive it, we\u2019ll review it and follow up if needed.'),
            'footer': msg.get('footer', 'WECARE.DIGITAL'),
            'flowId': flow_id,
            'flowCta': msg.get('flowCta', 'Submit Request'),
            'flowAction': 'data_exchange',
            'flowToken': flow_token,
        }
        # Only include header if explicitly set in config
        header_val = msg.get('header', '')
        if header_val:
            interactive_data['header'] = header_val

        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'flow',
                'interactiveData': interactive_data,
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'submit_request_flow_sent',
            'contactId': contact_id,
            'senderPhone': sender_phone,
            'flowId': flow_id,
            'flowToken': flow_token,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'submit_request_flow_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_subscribe_flow(contact_id: str, phone_number_id: str, sender_phone: str, request_id: str, flow_config: Dict = None) -> None:
    """
    Send the Subscribe WhatsApp Flow to the user.
    Collects: name, phone, email, company, billing + shipping address.
    On completion, updates the contact book via _enrich_contact_from_flow.
    """
    try:
        flow_id = (flow_config or {}).get('flowId', '')
        if not flow_id:
            logger.warning(json.dumps({
                'event': 'subscribe_flow_no_id',
                'contactId': contact_id,
                'requestId': request_id,
            }))
            return
        msg = (flow_config or {}).get('message', {})

        _waba_suffix = '1' if phone_number_id == PHONE_NUMBER_ID_1 else '2'
        flow_token = f'subscribe-{uuid.uuid4()}-waba-{_waba_suffix}-ph-{sender_phone}'
        interactive_data = {
            'body': msg.get('body', '\U0001f4cb Subscribe to WECARE.DIGITAL \u2014 fill in your details to get started with orders, payments, and updates.'),
            'footer': msg.get('footer', 'WECARE.DIGITAL'),
            'flowId': flow_id,
            'flowCta': msg.get('flowCta', 'Subscribe Now'),
            'flowAction': 'data_exchange',
            'flowToken': flow_token,
        }
        header_val = msg.get('header', '')
        if header_val:
            interactive_data['header'] = header_val

        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'flow',
                'interactiveData': interactive_data,
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'subscribe_flow_sent',
            'contactId': contact_id,
            'senderPhone': sender_phone,
            'flowId': flow_id,
            'flowToken': flow_token,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'subscribe_flow_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_generic_flow(contact_id: str, phone_number_id: str, sender_phone: str,
                       request_id: str, flow_config: Dict = None, flow_key: str = '') -> None:
    """
    Generic flow sender  -  works for all flow types.
    
    Phone 1 (WABA 1): Sends WhatsApp Flow interactive message (flows exist on WABA 1).
    Phone 2 (WABA 2): Sends CTA URL button with short link → wa.me message link on Phone 1.
    Flows are WABA-specific  -  they only exist on the WABA where they were created.
    """
    try:
        flow_id = (flow_config or {}).get('flowId', '')
        if not flow_id:
            logger.warning(json.dumps({
                'event': 'generic_flow_no_id',
                'flowKey': flow_key,
                'contactId': contact_id,
                'requestId': request_id,
            }))
            return
        msg = (flow_config or {}).get('message', {})

        # ── Phone 2: check if WABA 2 has its own flow, otherwise CTA fallback ──
        if phone_number_id == PHONE_NUMBER_ID_2:
            flow_id_2 = (flow_config or {}).get('flowId2', '')
            if flow_id_2:
                # WABA 2 has its own flow  -  use it instead of WABA 1 flow
                flow_id = flow_id_2
                logger.info(json.dumps({
                    'event': 'generic_flow_using_waba2_flow',
                    'flowKey': flow_key, 'flowId2': flow_id_2, 'requestId': request_id,
                }))
                # Fall through to flow sending logic below
            else:
                # No WABA 2 flow  -  send CTA URL fallback
                SHORT_URLS = {
                    'submit_request': 'https://r.wecare.digital/sr',
                    'track_request': 'https://r.wecare.digital/tr',
                    'amend_request': 'https://r.wecare.digital/ar',
                    'schedule_appointment': 'https://r.wecare.digital/sa',
                    'rx_slot': 'https://r.wecare.digital/rx',
                    'drop_docs': 'https://r.wecare.digital/dd',
                    'enterprise_assist': 'https://r.wecare.digital/ea',
                    'leave_review': 'https://r.wecare.digital/lr',
                    'subscribe': 'https://r.wecare.digital/sub',
                    'order_notes': 'https://r.wecare.digital/on',
                }
                PHONE2_BODY = {
                    'submit_request': '\U0001f4cb Start a new support request. Share the details and our team will follow up with you.',
                    'track_request': '\U0001f50d Check the status of your request anytime. Enter your reference ID below.',
                    'amend_request': '\u270f\ufe0f Need to make a change? Edit or correct your submitted request.',
                    'schedule_appointment': '\U0001f4c5 Schedule a consultation or service visit at a time that works best for you.',
                    'rx_slot': '\U0001fa7a Schedule a medical tourism or prescription-related visit.',
                    'drop_docs': '\U0001f4c4 Send supporting documents for your request.',
                    'enterprise_assist': '\U0001f3e2 Corporate, B2B, and bulk enquiries. Tell us what you need.',
                    'leave_review': '\u2b50 Share your experience with our service.',
                    'subscribe': '\U0001f514 Get updates, offers, and service news. Fill in your details to stay connected.',
                    'order_notes': '\U0001f4dd Add notes to your order with any special instructions.',
                }
                short_url = SHORT_URLS.get(flow_key, 'https://r.wecare.digital/sr')
                cta_text = msg.get('flowCta', flow_key.replace('_', ' ').title())
                body_text = PHONE2_BODY.get(flow_key, msg.get('body', 'Tap below to continue.'))
                _send_cta_button(contact_id, phone_number_id, cta_text, short_url, request_id,
                    body_text=body_text, footer_text='WECARE.DIGITAL')
                _send_followup_buttons(contact_id, phone_number_id, request_id)
                logger.info(json.dumps({
                    'event': 'generic_flow_phone2_cta_sent',
                    'flowKey': flow_key, 'contactId': contact_id, 'shortUrl': short_url,
                    'phoneNumberId': phone_number_id, 'requestId': request_id,
                }))
                return

        # ── Phone 1: send WhatsApp Flow interactive message ──
        _waba_suffix = '1' if phone_number_id == PHONE_NUMBER_ID_1 else '2'
        flow_token = f'{flow_key[:10]}-{uuid.uuid4()}-waba-{_waba_suffix}-ph-{sender_phone}'

        # Flows whose FIRST screen is STATIC (needs no endpoint data at open) must
        # open with NAVIGATE, not data_exchange. NAVIGATE renders the first screen
        # client-side and SKIPS the endpoint INIT round-trip — removing the "stuck
        # on loading" latency (per Meta Flows performance guidance). The endpoint is
        # still called later on data_exchange screens (e.g. REVIEW), so no data is
        # lost. Only order-fetching flows (submit_request, etc.) need data_exchange
        # at open to populate their first screen.
        STATIC_ENTRY_SCREENS = {'subscribe': 'PERSONAL_INFO'}
        _entry_screen = STATIC_ENTRY_SCREENS.get(flow_key, '')
        flow_action = 'navigate' if _entry_screen else 'data_exchange'

        interactive_data = {
            'body': msg.get('body', 'Please fill in the details below.'),
            'footer': msg.get('footer', 'WECARE.DIGITAL'),
            'flowId': flow_id,
            'flowCta': msg.get('flowCta', flow_key.replace('_', ' ').title()),
            'flowAction': flow_action,
            'flowToken': flow_token,
        }
        if _entry_screen:
            interactive_data['screenId'] = _entry_screen

        header_val = msg.get('header', '')
        if header_val:
            interactive_data['header'] = header_val

        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'flow',
                'interactiveData': interactive_data,
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'generic_flow_sent',
            'flowKey': flow_key,
            'contactId': contact_id,
            'senderPhone': sender_phone,
            'flowId': flow_id,
            'flowToken': flow_token,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'generic_flow_error',
            'flowKey': flow_key,
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_interactive_list(contact_id: str, phone_number_id: str, list_config: Dict, request_id: str) -> None:
    """
    Send a WhatsApp interactive list message.
    list_config should have: header, body, footer, buttonText, sections.
    """
    if not contact_id or not list_config.get('sections'):
        return

    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'list',
                'interactiveData': {
                    'header': list_config.get('header', ''),
                    'body': list_config.get('body', 'Please select an option'),
                    'footer': list_config.get('footer', ''),
                    'buttonText': list_config.get('buttonText', 'Menu'),
                    'sections': list_config.get('sections', []),
                }
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'interactive_list_sent',
            'contactId': contact_id,
            'buttonText': list_config.get('buttonText', 'Menu'),
            'sectionsCount': len(list_config.get('sections', [])),
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'interactive_list_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_cta_button(contact_id: str, phone_number_id: str, cta_text: str, cta_url: str, request_id: str,
                     body_text: str = '', header_text: str = '', footer_text: str = '') -> None:
    """Send a WhatsApp CTA URL button message with body text.
    Sends ONE interactive message with body text + CTA button."""
    if not contact_id or not cta_url:
        return

    try:
        interactive_data: Dict[str, Any] = {
            'body': body_text or cta_text,
            'buttonText': cta_text[:20],  # Max 20 chars for CTA display text
            'url': cta_url,
        }
        if header_text:
            interactive_data['header'] = header_text
        if footer_text:
            interactive_data['footer'] = footer_text

        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'cta_url',
                'interactiveData': interactive_data,
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'cta_button_sent',
            'contactId': contact_id,
            'ctaText': cta_text,
            'ctaUrl': cta_url,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'cta_button_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_reply_buttons(contact_id: str, phone_number_id: str, button_config: Dict, request_id: str) -> None:
    """
    Send WhatsApp interactive reply buttons (max 3 buttons).
    button_config: {header, body, footer, buttons: [{id, title}]}
    """
    if not contact_id or not button_config.get('buttons'):
        return

    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'button',
                'interactiveData': {
                    'header': button_config.get('header', ''),
                    'body': button_config.get('body', 'Please select an option'),
                    'footer': button_config.get('footer', ''),
                    'buttons': button_config.get('buttons', []),
                }
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'reply_buttons_sent',
            'contactId': contact_id,
            'buttonCount': len(button_config.get('buttons', [])),
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'reply_buttons_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_followup_buttons(contact_id: str, phone_number_id: str, request_id: str) -> None:
    """Send 'Explore More / All Set' reply buttons after any CTA response."""
    _send_reply_buttons(
        contact_id=contact_id,
        phone_number_id=phone_number_id,
        button_config={
            'body': "What next? \U0001f447",
            'footer': 'WECARE.DIGITAL',
            'buttons': [
                {'id': 'followup_explore', 'title': '\U0001f9ed Explore More'},
                {'id': 'followup_done', 'title': '\U0001faf6 All Set'},
            ],
        },
        request_id=request_id,
    )


def _send_audio_response(contact_id: str, phone_number_id: str, text: str, language: str, request_id: str,
                         sender_phone: str = '', sender_bsuid: str = '') -> None:
    """
    Invoke the whatsapp-voice Lambda to generate TTS audio and send it.
    Called when user has audioEnabled=True.
    """
    if not contact_id or not text or len(text.strip()) < 5:
        return

    # Map language preference to Polly voice/language code
    # Languages with native Polly voices use them; others use best fallback
    LANG_TO_POLLY = {
        # ── Popular (Indian + English) ──
        'english': ('Kajal', 'en-IN'),
        'hindi': ('Kajal', 'hi-IN'),
        'hinglish': ('Kajal', 'hi-IN'),
        'bengali': ('Kajal', 'hi-IN'),       # No native voice → Hindi fallback
        'tamil': ('Kajal', 'en-IN'),         # No native voice → English fallback
        'telugu': ('Kajal', 'en-IN'),        # No native voice
        'gujarati': ('Kajal', 'hi-IN'),      # No native voice → Hindi fallback
        'marathi': ('Kajal', 'hi-IN'),       # No native voice → Hindi fallback
        'kannada': ('Kajal', 'en-IN'),       # No native voice
        'malayalam': ('Kajal', 'en-IN'),     # No native voice
        # ── Asian ──
        'chinese': ('Zhiyu', 'cmn-CN'),
        'japanese': ('Kazuha', 'ja-JP'),
        'korean': ('Seoyeon', 'ko-KR'),
        'thai': ('Kajal', 'en-IN'),          # No native voice
        'vietnamese': ('Kajal', 'en-IN'),    # No native voice
        'indonesian': ('Kajal', 'en-IN'),    # No native voice
        'malay': ('Kajal', 'en-IN'),         # No native voice
        'sinhala': ('Kajal', 'en-IN'),       # No native voice
        # ── Middle East ──
        'arabic': ('Hala', 'arb'),
        'turkish': ('Burcu', 'tr-TR'),
        'russian': ('Tatyana', 'ru-RU'),
        'urdu': ('Kajal', 'hi-IN'),          # No native voice → Hindi fallback
        'punjabi': ('Kajal', 'hi-IN'),       # No native voice → Hindi fallback
        # ── European ──
        'french': ('Lea', 'fr-FR'),
        'spanish': ('Lupe', 'es-US'),
        'portuguese': ('Camila', 'pt-BR'),
        'italian': ('Bianca', 'it-IT'),
        'german': ('Vicki', 'de-DE'),
        'dutch': ('Laura', 'nl-NL'),
        'polish': ('Ola', 'pl-PL'),
        'swedish': ('Elin', 'sv-SE'),
        'danish': ('Sofie', 'da-DK'),
        'norwegian': ('Ida', 'nb-NO'),
        'finnish': ('Suvi', 'fi-FI'),
        'catalan': ('Arlet', 'ca-ES'),
        'romanian': ('Carmen', 'ro-RO'),
        'welsh': ('Gwyneth', 'cy-GB'),
    }
    voice_id, lang_code = LANG_TO_POLLY.get(language.lower(), ('Kajal', 'en-IN'))

    try:
        # The voice Lambda expects an HTTP-style event with POST /whatsapp-voice/tts
        tts_payload = {
            'requestContext': {'http': {'method': 'POST'}},
            'rawPath': '/whatsapp-voice/tts',
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumber': sender_phone,
                'messageText': text[:500],  # Polly limit
                'voiceId': voice_id,
                'languageCode': lang_code,
                'engine': 'neural',
                'phoneNumberId': phone_number_id,
                'recipientBsuid': sender_bsuid,
            })
        }

        response = lambda_client.invoke(
            FunctionName=WHATSAPP_VOICE_FUNCTION,
            InvocationType='Event',  # Async  -  don't block
            Payload=json.dumps(tts_payload)
        )

        logger.info(json.dumps({
            'event': 'audio_response_triggered',
            'contactId': contact_id,
            'voiceId': voice_id,
            'langCode': lang_code,
            'textLength': len(text),
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'audio_response_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _auto_transcribe_voice_note(message_id: str, s3_key: str, request_id: str) -> None:
    """
    Async-invoke the whatsapp-voice Lambda to transcribe a voice note.
    The transcription result is stored back in the message record.
    Non-blocking (InvocationType='Event').
    """
    try:
        # Check if auto-transcribe is enabled in system config
        config_table = dynamodb.Table(
            os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
        )
        try:
            cfg_result = config_table.get_item(Key={'id': 'voice_language_config'})
            cfg_value = cfg_result.get('Item', {}).get('configValue', '{}')
            voice_config = json.loads(cfg_value) if isinstance(cfg_value, str) else cfg_value
            if not voice_config.get('autoTranscribe', True):
                return  # Auto-transcribe disabled
        except Exception:
            pass  # Default: auto-transcribe enabled

        transcribe_payload = {
            'requestContext': {'http': {'method': 'POST'}},
            'rawPath': '/whatsapp-voice/transcribe',
            'body': json.dumps({
                'messageId': message_id,
                's3Key': s3_key,
                'direction': 'INBOUND',
            })
        }

        response = lambda_client.invoke(
            FunctionName=WHATSAPP_VOICE_FUNCTION,
            InvocationType='Event',  # Async  -  don't block inbound processing
            Payload=json.dumps(transcribe_payload)
        )

        logger.info(json.dumps({
            'event': 'auto_transcribe_triggered',
            'messageId': message_id,
            's3Key': s3_key,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id,
        }))

    except Exception as e:
        logger.warning(json.dumps({
            'event': 'auto_transcribe_error',
            'messageId': message_id,
            'error': str(e),
            'requestId': request_id,
        }))


def _fetch_catalog_product_names(catalog_id: str, retailer_ids: list) -> dict:
    """Fetch real product display names from a Meta catalog by retailer_id, so the
    order/invoice shows 'WECARE Test Product' instead of a raw SKU like 'htlu35lrs1'.
    Returns {retailer_id: name}; best-effort (empty on failure)."""
    names = {}
    rids = [r for r in {str(x) for x in (retailer_ids or [])} if r]
    if not catalog_id or not rids:
        return names
    try:
        import urllib.parse as _up
        token = _load_direct_api_token()
        app_secret = _direct_api_token_cache.get('app_secret', '')
        flt = json.dumps({'retailer_id': {'is_any': rids}})
        url = (f"https://graph.facebook.com/{META_API_VERSION}/{catalog_id}/products"
               f"?fields=name,retailer_id&limit=100&filter={_up.quote(flt)}&access_token={token}")
        if app_secret:
            url += '&appsecret_proof=' + hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as r:
            data = json.loads(r.read().decode())
        for it in data.get('data', []):
            rid = it.get('retailer_id', '')
            if rid:
                names[rid] = it.get('name', rid)
    except Exception as e:
        logger.warning(json.dumps({'event': 'catalog_name_fetch_error', 'error': str(e)}))
    return names


def _handle_cart_order(message: Dict, contact_id: str, sender_phone: str,
                       phone_number_id: str, request_id: str) -> None:
    """Native catalog checkout. A customer sent a cart (message.type='order').
    Convert product_items into a native PHYSICAL-GOODS order_details (Review & Pay)
    carrying the business's standard 18% GST + 2% convenience fee, with real product
    names and the saved shipping address as beneficiaries; collect the address via
    an Address Message if none is on file. Invoice is generated on payment capture."""
    try:
        order = message.get('order', {}) or {}
        product_items = order.get('product_items', []) or []
        catalog_id = order.get('catalog_id', '')

        # Resolve real product names from the catalog (fixes vague SKU display).
        rids = [str(pi.get('product_retailer_id') or '') for pi in product_items if pi.get('product_retailer_id')]
        name_map = _fetch_catalog_product_names(catalog_id, rids)

        items = []
        subtotal = 0.0
        for pi in product_items:
            qty = int(pi.get('quantity', 1) or 1)
            price = float(pi.get('item_price', 0) or 0)  # currency units (rupees)
            if price <= 0 or qty <= 0:
                continue
            subtotal += price * qty
            rid = str(pi.get('product_retailer_id') or '')
            items.append({
                'name': (name_map.get(rid) or rid or 'Item')[:60],
                'amount_paise': int(round(price * 100)),
                'quantity': qty,
                'gst_rate': 18.0,
            })
        if not items:
            logger.warning(json.dumps({'event': 'cart_order_no_items', 'requestId': request_id}))
            return

        # Load contact + structured shipping address (captured via Address Message).
        ship_addr = ''
        cust_name = ''
        ship_info = None
        try:
            if contact_id:
                c = dynamodb.Table(CONTACTS_TABLE).get_item(Key={'id': contact_id}).get('Item', {})
                ship_addr = c.get('shippingAddress', '') or ''
                cust_name = c.get('contactBookName', '') or c.get('name', '') or ''
                if ship_addr or c.get('addressLine1'):
                    ship_info = {'addresses': [{
                        'name': cust_name or 'Customer',
                        'address': (c.get('addressLine1') or ship_addr or '')[:100],
                        'landmark_area': c.get('landmark', '') or '',
                        'city': c.get('city', '') or '',
                        'state': c.get('state', '') or '',
                        'in_pin_code': (c.get('postalCode', '') or '')[:6],
                    }]}
        except Exception:
            pass

        logger.info(json.dumps({
            'event': 'cart_order_received', 'itemCount': len(items),
            'subtotal': round(subtotal, 2), 'catalogId': catalog_id,
            'namesResolved': len(name_map), 'hasAddress': bool(ship_addr),
            'phone_suffix': sender_phone[-4:] if sender_phone else '', 'requestId': request_id,
        }))

        # Native Review & Pay (physical-goods order_details) with GST + convenience.
        _first_retailer_id = str((product_items[0] or {}).get('product_retailer_id') or '') if product_items else ''
        _send_payment_request(
            contact_id=contact_id, phone_number_id=phone_number_id, amount=subtotal,
            request_id=request_id, gst_rate=18, shipping=0, sender_phone=sender_phone,
            items=items, payment_purpose='Catalog order',
            order_id=catalog_id or 'Catalog',
            customer_name=cust_name, customer_phone=sender_phone,
            shipping_address=ship_addr, goods_type='physical-goods', shipping_info=ship_info,
            catalog_retailer_id=_first_retailer_id,
        )

        # Physical goods: collect a shipping address if we don't have one on file.
        if not ship_addr:
            try:
                _vals = {'phone_number': f'+{sender_phone}'}
                if cust_name:
                    _vals['name'] = cust_name
                addr_payload = {'body': json.dumps({
                    'contactId': contact_id, 'phoneNumberId': phone_number_id,
                    'isInteractive': True, 'interactiveType': 'address_message',
                    'interactiveData': {
                        'body': 'To deliver your order, please share your delivery address.',
                        'country': 'IN', 'values': _vals,
                    },
                })}
                lambda_client.invoke(FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
                                     InvocationType='Event', Payload=json.dumps(addr_payload))
            except Exception as _ae:
                logger.warning(json.dumps({'event': 'cart_address_request_error', 'error': str(_ae), 'requestId': request_id}))
    except Exception as e:
        logger.error(json.dumps({'event': 'cart_order_error', 'error': str(e), 'requestId': request_id}))


def _send_payment_request(contact_id: str, phone_number_id: str, amount: float, request_id: str,
                          item_name: str = 'Services/Goods', gst_rate: float = 18,
                          shipping: float = 49, sender_phone: str = '',
                          quantity: int = 1, discount: float = 0,
                          handling: float = 0,
                          items: list = None,
                          payment_purpose: str = '', due_ref: str = '',
                          order_id: str = 'Offline', customer_name: str = '',
                          customer_phone: str = '', customer_email: str = '',
                          shipping_address: str = '', billing_address: str = '',
                          pay_for: str = 'self',
                          goods_type: str = 'digital-goods', shipping_info: dict = None,
                          catalog_retailer_id: str = '') -> None:
    """Send WhatsApp Pay order_details message with per-item GST and payment log.
    
    Supports multi-item via `items` list of dicts:
      [{'name': str, 'amount_paise': int, 'quantity': int, 'gst_rate': float}]
    Falls back to single item_name/amount/quantity/gst_rate if items not provided.
    """
    if not contact_id or amount <= 0:
        return
    # Validate amount upper bound (₹10,00,000 = 10 lakh INR)
    if amount > 1000000:
        logger.warning(json.dumps({
            'event': 'payment_amount_exceeds_limit',
            'contactId': contact_id,
            'amount': amount,
            'requestId': request_id,
        }))
        return

    try:
        reference_id = f"WD-PAY-{uuid.uuid4().hex[:8].upper()}"
        qty = max(1, int(quantity))
        
        # Build items array for order_details with per-item GST
        if items and len(items) > 0:
            order_items = []
            subtotal_paise = 0
            gst_paise = 0
            for i, item in enumerate(items):
                i_amount = int(item.get('amount_paise', int(amount * 100)))
                i_qty = int(item.get('quantity', 1))
                i_name = item.get('name', item_name)
                i_gst_rate = float(item.get('gst_rate', gst_rate))
                i_line_total = i_amount * i_qty
                subtotal_paise += i_line_total
                gst_paise += int(round(i_line_total * i_gst_rate / 100 / 100, 2) * 100)
                order_items.append({
                    'retailer_id': f'ITEM_{i+1}',
                    'name': i_name,
                    'amount': {'value': i_amount, 'offset': 100},
                    'quantity': i_qty,
                    'gstRate': i_gst_rate,
                })
        else:
            amount_in_paise = int(amount * 100)
            subtotal_paise = amount_in_paise * qty
            gst_paise = int(round(subtotal_paise * gst_rate / 100 / 100, 2) * 100)
            order_items = [{
                'retailer_id': 'ITEM_MAIN',
                'name': item_name,
                'amount': {'value': amount_in_paise, 'offset': 100},
                'quantity': qty,
                'gstRate': gst_rate,
            }]
        
        discount_paise = int(discount * 100)
        shipping_paise = int(shipping * 100)
        handling_paise = int(handling * 100)

        # Build payload matching outbound handler's isInteractivePayment format
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractivePayment': True,
                'orderDetails': {
                    'reference_id': reference_id,
                    'type': goods_type or 'digital-goods',
                    'shipping_info': shipping_info or {},
                    'currency': 'INR',
                    'itemName': order_items[0]['name'] if order_items else item_name,
                    'quantity': qty,
                    'gstRate': gst_rate,
                    'gstin': '19AADFW7431N1ZK',
                    'orderId': order_id or 'Offline',
                    'order': {
                        'status': 'pending',
                        'items': order_items,
                        'subtotal': {'value': subtotal_paise, 'offset': 100},
                        'discount': {'value': discount_paise, 'offset': 100, 'description': 'Promo'},
                        'shipping': {'value': shipping_paise, 'offset': 100, 'description': 'Express'},
                        'handling': {'value': handling_paise, 'offset': 100, 'description': 'Handling'},
                        'tax': {'value': gst_paise, 'offset': 100, 'description': f'GSTIN: 19AADFW7431N1ZK'},
                    },
                }
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        # Calculate totals for logging
        conv_base_paise = int(round(subtotal_paise * 0.02 / 100, 2) * 100)
        conv_gst_paise = int(round(conv_base_paise * 0.18 / 100, 2) * 100)
        conv_total_paise = conv_base_paise + conv_gst_paise
        total_paise = subtotal_paise - discount_paise + gst_paise + shipping_paise + handling_paise + conv_total_paise

        # Store payment request with full GST breakdown for accounting
        try:
            messages_table = dynamodb.Table(MESSAGES_TABLE)
            now = int(time.time())
            # Build item summary for content field
            item_summary = ' | '.join([f"{it['name']} x{it['quantity']} @₹{it['amount']['value']/100:.2f}" for it in order_items])
            messages_table.put_item(Item={k: v for k, v in {
                'id': str(uuid.uuid4()),
                'messageId': reference_id,
                'contactId': contact_id,
                'channel': 'whatsapp',
                'direction': 'outbound',
                'messageType': 'payment_request',
                'content': f'Payment: {item_summary} | GST {gst_rate}%: ₹{gst_paise/100:.2f} | Promo: -₹{discount:.2f} | Ship: ₹{shipping:.2f} | Handling: ₹{handling:.2f} | Total: ₹{total_paise/100:.2f}',
                'paymentReferenceId': reference_id,
                'paymentAmount': Decimal(str(subtotal_paise)),
                'paymentOffset': Decimal('100'),
                'paymentCurrency': 'INR',
                'paymentItemName': order_items[0]['name'] if order_items else item_name,
                'paymentItemCount': len(order_items),
                'paymentQuantity': qty,
                'paymentSubtotal': Decimal(str(subtotal_paise)),
                'paymentDiscount': Decimal(str(discount_paise)),
                'paymentGstRate': Decimal(str(gst_rate)),
                'paymentGstAmount': Decimal(str(gst_paise)),
                'paymentShipping': Decimal(str(shipping_paise)),
                'paymentHandling': Decimal(str(handling_paise)),
                'paymentConvFee': Decimal(str(conv_total_paise)),
                'paymentTotal': Decimal(str(total_paise)),
                'paymentGstin': '19AADFW7431N1ZK',
                'paymentSource': 'whatsapp_bot',
                'paymentPurpose': payment_purpose or '',
                'paymentDueRef': due_ref or '',
                'paymentOrderId': order_id or 'Offline',
                'paymentCustomerName': customer_name or '',
                'paymentCustomerPhone': customer_phone or sender_phone,
                'paymentCustomerEmail': customer_email or '',
                'paymentShippingAddress': shipping_address or '',
                'paymentBillingAddress': billing_address or '',
                'paymentPayFor': pay_for or 'self',
                'catalogRetailerId': catalog_retailer_id or '',
                'status': 'pending',
                'senderPhone': sender_phone,
                'createdAt': Decimal(str(now)),
                'expiresAt': Decimal(str(now + 86400 * 30)),
            }.items() if v is not None and v != ''})
        except Exception as store_err:
            logger.warning(json.dumps({
                'event': 'payment_request_store_error',
                'error': str(store_err),
                'referenceId': reference_id,
                'requestId': request_id
            }))

        # Save pending payment ref to ConversationHistoryTable for due check
        if sender_phone:
            try:
                from hashlib import sha256
                clean_phone = sender_phone.replace('+', '').replace(' ', '').replace('-', '')
                ph = sha256(clean_phone.encode()).hexdigest()[:32]
                conv_table = dynamodb.Table(os.environ.get('CONVERSATION_HISTORY_TABLE', 'stack-wecare-digital-ConversationHistoryTable'))
                conv_table.update_item(
                    Key={'phoneHash': ph},
                    UpdateExpression='SET lastPaymentRef = :ref, lastPaymentAmount = :amt, lastPaymentStatus = :s, lastPaymentAt = :t',
                    ExpressionAttributeValues={
                        ':ref': reference_id,
                        ':amt': Decimal(str(subtotal_paise / 100)),
                        ':s': 'pending',
                        ':t': Decimal(str(int(time.time()))),
                    }
                )
            except Exception as conv_err:
                logger.warning(json.dumps({
                    'event': 'payment_conv_update_error',
                    'error': str(conv_err),
                    'requestId': request_id
                }))

        logger.info(json.dumps({
            'event': 'payment_request_sent',
            'contactId': contact_id,
            'referenceId': reference_id,
            'itemCount': len(order_items),
            'subtotal': subtotal_paise / 100,
            'discount': discount,
            'gstRate': gst_rate,
            'gstAmount': gst_paise / 100,
            'shipping': shipping,
            'handling': handling,
            'convFee': conv_total_paise / 100,
            'total': total_paise / 100,
            'orderId': order_id or 'Offline',
            'source': 'whatsapp_bot',
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'payment_request_error',
            'contactId': contact_id,
            'amount': amount,
            'error': str(e),
            'requestId': request_id
        }))


# ============================================================================
# POS INVOICE IMAGE GENERATOR (pure Python PNG  -  zero external dependencies)
# ============================================================================

# Minimal 5x7 bitmap font for ASCII 32-126 (space to ~)
# Each char is 5 pixels wide, 7 pixels tall, stored as 7 bytes (each byte = 5-bit row)
_FONT_5x7 = {
    32: [0,0,0,0,0,0,0], 33: [4,4,4,4,0,0,4], 34: [10,10,0,0,0,0,0],
    35: [10,31,10,10,31,10,0], 36: [4,15,20,14,5,30,4], 37: [24,25,2,4,8,19,3],
    38: [8,20,20,8,21,18,13], 39: [4,4,0,0,0,0,0], 40: [2,4,8,8,8,4,2],
    41: [8,4,2,2,2,4,8], 42: [0,4,21,14,21,4,0], 43: [0,4,4,31,4,4,0],
    44: [0,0,0,0,0,4,8], 45: [0,0,0,31,0,0,0], 46: [0,0,0,0,0,0,4],
    47: [0,1,2,4,8,16,0], 48: [14,17,19,21,25,17,14], 49: [4,12,4,4,4,4,14],
    50: [14,17,1,2,4,8,31], 51: [14,17,1,6,1,17,14], 52: [2,6,10,18,31,2,2],
    53: [31,16,30,1,1,17,14], 54: [6,8,16,30,17,17,14], 55: [31,1,2,4,8,8,8],
    56: [14,17,17,14,17,17,14], 57: [14,17,17,15,1,2,12], 58: [0,0,4,0,0,4,0],
    59: [0,0,4,0,0,4,8], 60: [1,2,4,8,4,2,1], 61: [0,0,31,0,31,0,0],
    62: [16,8,4,2,4,8,16], 63: [14,17,1,2,4,0,4], 64: [14,17,23,21,23,16,14],
    65: [14,17,17,31,17,17,17], 66: [30,17,17,30,17,17,30], 67: [14,17,16,16,16,17,14],
    68: [30,17,17,17,17,17,30], 69: [31,16,16,30,16,16,31], 70: [31,16,16,30,16,16,16],
    71: [14,17,16,23,17,17,14], 72: [17,17,17,31,17,17,17], 73: [14,4,4,4,4,4,14],
    74: [7,2,2,2,2,18,12], 75: [17,18,20,24,20,18,17], 76: [16,16,16,16,16,16,31],
    77: [17,27,21,21,17,17,17], 78: [17,25,21,21,21,19,17], 79: [14,17,17,17,17,17,14],
    80: [30,17,17,30,16,16,16], 81: [14,17,17,17,21,18,13], 82: [30,17,17,30,20,18,17],
    83: [14,17,16,14,1,17,14], 84: [31,4,4,4,4,4,4], 85: [17,17,17,17,17,17,14],
    86: [17,17,17,17,10,10,4], 87: [17,17,17,21,21,21,10], 88: [17,17,10,4,10,17,17],
    89: [17,17,10,4,4,4,4], 90: [31,1,2,4,8,16,31],
    91: [14,8,8,8,8,8,14], 92: [0,16,8,4,2,1,0], 93: [14,2,2,2,2,2,14],
    94: [4,10,17,0,0,0,0], 95: [0,0,0,0,0,0,31], 96: [8,4,0,0,0,0,0],
    97: [0,0,14,1,15,17,15], 98: [16,16,30,17,17,17,30], 99: [0,0,14,17,16,17,14],
    100: [1,1,15,17,17,17,15], 101: [0,0,14,17,31,16,14], 102: [6,9,8,28,8,8,8],
    103: [0,0,15,17,15,1,14], 104: [16,16,30,17,17,17,17], 105: [4,0,12,4,4,4,14],
    106: [2,0,6,2,2,18,12], 107: [16,16,18,20,24,20,18], 108: [12,4,4,4,4,4,14],
    109: [0,0,26,21,21,21,17], 110: [0,0,30,17,17,17,17], 111: [0,0,14,17,17,17,14],
    112: [0,0,30,17,30,16,16], 113: [0,0,15,17,15,1,1], 114: [0,0,22,25,16,16,16],
    115: [0,0,15,16,14,1,30], 116: [8,8,28,8,8,9,6], 117: [0,0,17,17,17,17,15],
    118: [0,0,17,17,17,10,4], 119: [0,0,17,17,21,21,10], 120: [0,0,17,10,4,10,17],
    121: [0,0,17,17,15,1,14], 122: [0,0,31,2,4,8,31],
    123: [3,4,4,8,4,4,3], 124: [4,4,4,4,4,4,4], 125: [24,4,4,2,4,4,24],
    126: [0,0,8,21,2,0,0],
}
# Special chars mapped to ASCII equivalents
_CHAR_MAP = {0x20B9: ord('R'), 0x2500: ord('-'), 0x2502: ord('|'), 0x2714: ord('*'),
             0x274C: ord('x'), 0x2705: ord('*')}


def _decode_png_pixels(png_bytes: bytes):
    """Minimal pure-Python PNG decoder. Returns (width, height, rows) where rows is list of lists of (R,G,B,A)."""
    import struct as _struct
    import zlib as _zlib

    if png_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        return None, None, None

    pos = 8
    width = height = bit_depth = color_type = 0
    idat_chunks = []
    palette = []

    while pos < len(png_bytes):
        length = _struct.unpack('>I', png_bytes[pos:pos+4])[0]
        chunk_type = png_bytes[pos+4:pos+8]
        chunk_data = png_bytes[pos+8:pos+8+length]
        pos += 12 + length

        if chunk_type == b'IHDR':
            width, height, bit_depth, color_type = _struct.unpack('>IIBB', chunk_data[:10])
        elif chunk_type == b'PLTE':
            for i in range(0, len(chunk_data), 3):
                palette.append((chunk_data[i], chunk_data[i+1], chunk_data[i+2]))
        elif chunk_type == b'IDAT':
            idat_chunks.append(chunk_data)
        elif chunk_type == b'IEND':
            break

    raw = _zlib.decompress(b''.join(idat_chunks))

    # Determine bytes per pixel
    if color_type == 0:
        bpp = 1  # grayscale
    elif color_type == 2:
        bpp = 3  # RGB
    elif color_type == 3:
        bpp = 1  # indexed
    elif color_type == 4:
        bpp = 2  # grayscale + alpha
    elif color_type == 6:
        bpp = 4  # RGBA
    else:
        return None, None, None

    stride = width * bpp
    rows = []
    prev_row = bytearray(stride)

    offset = 0
    for y in range(height):
        filter_type = raw[offset]
        offset += 1
        cur_row = bytearray(raw[offset:offset + stride])
        offset += stride

        # Reconstruct filtered row
        for i in range(stride):
            a = cur_row[i - bpp] if i >= bpp else 0
            b = prev_row[i]
            c = prev_row[i - bpp] if i >= bpp else 0
            if filter_type == 1:
                cur_row[i] = (cur_row[i] + a) & 0xFF
            elif filter_type == 2:
                cur_row[i] = (cur_row[i] + b) & 0xFF
            elif filter_type == 3:
                cur_row[i] = (cur_row[i] + (a + b) // 2) & 0xFF
            elif filter_type == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                cur_row[i] = (cur_row[i] + pr) & 0xFF

        # Convert to RGBA tuples
        pixel_row = []
        for x in range(width):
            idx = x * bpp
            if color_type == 0:
                v = cur_row[idx]
                pixel_row.append((v, v, v, 255))
            elif color_type == 2:
                pixel_row.append((cur_row[idx], cur_row[idx+1], cur_row[idx+2], 255))
            elif color_type == 3:
                ci = cur_row[idx]
                if ci < len(palette):
                    r, g, b = palette[ci]
                    pixel_row.append((r, g, b, 255))
                else:
                    pixel_row.append((0, 0, 0, 255))
            elif color_type == 4:
                v, a = cur_row[idx], cur_row[idx+1]
                pixel_row.append((v, v, v, a))
            elif color_type == 6:
                pixel_row.append((cur_row[idx], cur_row[idx+1], cur_row[idx+2], cur_row[idx+3]))

        rows.append(pixel_row)
        prev_row = cur_row

    return width, height, rows


def _render_text_to_png(lines: list, scale: int = 2, logo_pixels=None, logo_w: int = 0, logo_h: int = 0) -> bytes:
    """Render lines of text to a PNG image using a 5x7 bitmap font. Optionally composites a logo at top center. Returns PNG bytes."""
    import struct as _struct
    import zlib as _zlib
    import io as _io

    char_w, char_h = 6 * scale, 9 * scale
    pad_x, pad_y = 12 * scale, 8 * scale
    max_cols = max((len(l) for l in lines), default=1)
    img_w = max_cols * char_w + pad_x * 2
    img_h = len(lines) * char_h + pad_y * 2

    # If logo, add space at top
    logo_offset_y = 0
    if logo_pixels and logo_h > 0:
        # Scale logo to fit ~60% of receipt width, max 80px tall
        target_w = int(img_w * 0.4)
        logo_scale = min(target_w / max(logo_w, 1), 80 / max(logo_h, 1), 1.0)
        scaled_lw = int(logo_w * logo_scale)
        scaled_lh = int(logo_h * logo_scale)
        logo_offset_y = scaled_lh + pad_y
        img_h += logo_offset_y

    # Create RGBA pixel buffer (white background)
    pixels = bytearray([255, 255, 255, 255] * (img_w * img_h))

    # Composite logo at top center
    if logo_pixels and logo_h > 0 and logo_offset_y > 0:
        logo_x_start = (img_w - scaled_lw) // 2
        for ly in range(scaled_lh):
            src_y = int(ly / logo_scale)
            if src_y >= logo_h:
                src_y = logo_h - 1
            for lx in range(scaled_lw):
                src_x = int(lx / logo_scale)
                if src_x >= logo_w:
                    src_x = logo_w - 1
                r, g, b, a = logo_pixels[src_y][src_x]
                px = logo_x_start + lx
                py = pad_y + ly
                if 0 <= px < img_w and 0 <= py < img_h and a > 0:
                    idx = (py * img_w + px) * 4
                    if a == 255:
                        pixels[idx] = r
                        pixels[idx+1] = g
                        pixels[idx+2] = b
                        pixels[idx+3] = 255
                    else:
                        # Alpha blend
                        af = a / 255.0
                        pixels[idx] = int(r * af + pixels[idx] * (1 - af))
                        pixels[idx+1] = int(g * af + pixels[idx+1] * (1 - af))
                        pixels[idx+2] = int(b * af + pixels[idx+2] * (1 - af))
                        pixels[idx+3] = 255

    # Render text
    for row_idx, line in enumerate(lines):
        for col_idx, ch in enumerate(line):
            code = ord(ch)
            code = _CHAR_MAP.get(code, code)
            glyph = _FONT_5x7.get(code, _FONT_5x7.get(63))
            if not glyph:
                continue
            bx = pad_x + col_idx * char_w
            by = pad_y + logo_offset_y + row_idx * char_h
            for gy, row_bits in enumerate(glyph):
                for gx in range(5):
                    if row_bits & (1 << (4 - gx)):
                        for sy in range(scale):
                            for sx in range(scale):
                                px = bx + gx * scale + sx
                                py = by + gy * scale + sy
                                if 0 <= px < img_w and 0 <= py < img_h:
                                    idx = (py * img_w + px) * 4
                                    pixels[idx] = 0
                                    pixels[idx+1] = 0
                                    pixels[idx+2] = 0
                                    pixels[idx+3] = 255

    # Encode as PNG (RGBA, 8-bit)
    def _png_chunk(chunk_type, data):
        c = chunk_type + data
        return _struct.pack('>I', len(data)) + c + _struct.pack('>I', _zlib.crc32(c) & 0xFFFFFFFF)

    raw_rows = b''
    for y in range(img_h):
        raw_rows += b'\x00' + bytes(pixels[y * img_w * 4:(y + 1) * img_w * 4])

    buf = _io.BytesIO()
    buf.write(b'\x89PNG\r\n\x1a\n')
    # color_type=6 = RGBA
    buf.write(_png_chunk(b'IHDR', _struct.pack('>IIBBBBB', img_w, img_h, 8, 6, 0, 0, 0)))
    buf.write(_png_chunk(b'IDAT', _zlib.compress(raw_rows, 9)))
    buf.write(_png_chunk(b'IEND', b''))
    return buf.getvalue()


def _build_invoice_lines(ref_id: str, pay_ref: str, item_name: str, unit_price: float, qty: int,
                         gst_rate: float, shipping: float, discount: float,
                         sender_phone: str, purpose: str, due_ref: str,
                         paid_at: str = '', order_id: str = 'Offline',
                         customer_name: str = '', customer_phone: str = '',
                         customer_email: str = '', shipping_address: str = '',
                         billing_address: str = '', pay_for: str = 'self') -> list:
    """Build POS receipt text lines for the invoice."""
    import datetime
    if paid_at:
        date_str = paid_at.split(' ')[0] if ' ' in paid_at else paid_at
        time_str = paid_at.split(' ')[1] if ' ' in paid_at else ''
    else:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        date_str = now.strftime('%d-%m-%Y')
        time_str = now.strftime('%H:%M:%S')

    subtotal = unit_price * qty
    after_promo = subtotal - discount
    gst_amt = round(after_promo * gst_rate / 100, 2)
    half_rate = gst_rate / 2
    cgst = round(gst_amt / 2, 2)
    sgst = round(gst_amt / 2, 2)
    conv_base = round(after_promo * 0.02, 2)
    conv_gst = round(conv_base * 0.18, 2)
    conv_fee = round(conv_base + conv_gst, 2)
    total = round(after_promo + gst_amt + shipping + conv_fee, 2)

    W = 42  # receipt width in chars
    sep = '-' * W
    dsep = '=' * W

    def center(t):
        return t.center(W)

    def lr(left, right):
        space = W - len(left) - len(right)
        return left + ' ' * max(space, 1) + right

    def fmt(v):
        return f'{v:,.2f}'

    lines = []
    # Header  -  logo will be composited above this
    lines.append('')
    lines.append('')
    lines.append('')  # space for logo
    lines.append(center('WECARE.DIGITAL'))
    lines.append(center('GSTIN: 19AADFW7431N1ZK'))
    lines.append(center('The W.B.S.I.D.C. Building'))
    lines.append(center('Unit 1/20, 81/2/7 Phears Ln'))
    lines.append(center('Kolkata, WB 700012'))
    lines.append(center('Email: one@wecare.digital'))
    lines.append(center('Phone: +919330994400'))
    lines.append(dsep)
    lines.append(center('TAX INVOICE'))
    lines.append(sep)
    lines.append(lr(f'Inv: {ref_id}', f'Date: {date_str}'))
    lines.append(lr(f'Pay Ref: {pay_ref}', f'Time: {time_str}'))
    lines.append(f'Order: {order_id}')
    lines.append(sep)
    # Customer details
    lines.append(center('BILL TO'))
    if customer_name:
        lines.append(f'Name: {customer_name[:30]}')
    cust_ph = customer_phone or sender_phone
    cust_ph_display = cust_ph[-10:] if len(cust_ph) > 10 else cust_ph
    lines.append(f'Phone: {cust_ph_display}')
    if customer_email:
        lines.append(f'Email: {customer_email[:30]}')
    if billing_address:
        # Wrap long address
        addr = billing_address[:60]
        lines.append(f'Addr: {addr}')
    if pay_for == 'other':
        paid_by = sender_phone[-10:] if len(sender_phone) > 10 else sender_phone
        lines.append(f'Paid By: {paid_by}')
    lines.append(sep)
    lines.append(center('SHIP TO'))
    if shipping_address:
        lines.append(f'{shipping_address[:42]}')
    else:
        lines.append('Same as billing')
    if purpose:
        lines.append(f'Purpose: {purpose[:30]}')
    if due_ref:
        lines.append(f'Due Ref: {due_ref}')
    lines.append(sep)
    lines.append(lr('ITEM', 'AMOUNT'))
    lines.append(sep)
    item_display = item_name[:24]
    lines.append(f'{item_display}')
    lines.append(lr(f'  Rs.{fmt(unit_price)} x {qty}', f'Rs.{fmt(subtotal)}'))
    lines.append(sep)
    lines.append(lr('Subtotal:', f'Rs.{fmt(subtotal)}'))
    if discount > 0:
        lines.append(lr('Promo Discount:', f'-Rs.{fmt(discount)}'))
    lines.append(lr(f'CGST @{half_rate:.1f}%:', f'Rs.{fmt(cgst)}'))
    lines.append(lr(f'SGST @{half_rate:.1f}%:', f'Rs.{fmt(sgst)}'))
    lines.append(lr('Shipping:', f'Rs.{fmt(shipping)}'))
    lines.append(lr('Conv. Fee (2%+GST):', f'Rs.{fmt(conv_fee)}'))
    lines.append(dsep)
    lines.append(lr('TOTAL PAID:', f'Rs.{fmt(total)}'))
    lines.append(dsep)
    lines.append(center('GST SUMMARY'))
    lines.append(sep)
    lines.append(lr('Tax', 'Taxable    Amount'))
    lines.append(lr(f'CGST @{half_rate:.1f}%', f'{fmt(after_promo)}  {fmt(cgst)}'))
    lines.append(lr(f'SGST @{half_rate:.1f}%', f'{fmt(after_promo)}  {fmt(sgst)}'))
    lines.append(lr('Total Tax:', f'Rs.{fmt(gst_amt)}'))
    lines.append(sep)
    lines.append('')
    lines.append(center('** PAID **'))
    lines.append(center(f'{date_str} {time_str} IST'))
    lines.append('')
    lines.append(center('Thank You for your payment!'))
    lines.append(center('wecare.digital'))
    lines.append(dsep)

    return lines


def _handle_dashboard_invoice(event, request_id):
    """Handle direct invoke from dashboard to create and send an invoice."""
    try:
        contact_id = event['contactId']
        phone_number_id = event.get('phoneNumberId', '919330994400')
        item_name = event['itemName']
        unit_price = float(event['unitPrice'])
        quantity = int(event.get('quantity', 1))
        gst_rate = float(event.get('gstRate', 18))
        shipping = float(event.get('shipping', 49))
        discount = float(event.get('discount', 15))
        purpose = event.get('purpose', '')
        order_id = event.get('orderId', 'Offline')
        customer_name = event.get('customerName', '')
        customer_phone = event.get('customerPhone', '')
        customer_email = event.get('customerEmail', '')
        shipping_address = event.get('shippingAddress', '')
        billing_address = event.get('billingAddress', '')
        sender_phone = event.get('senderPhone', customer_phone or contact_id)

        # Cap promo so it never exceeds subtotal
        subtotal = unit_price * quantity
        discount = min(discount, subtotal)

        _generate_and_send_invoice(
            contact_id=contact_id,
            phone_number_id=phone_number_id,
            amount=unit_price,
            quantity=quantity,
            item_name=item_name,
            gst_rate=gst_rate,
            shipping=shipping,
            discount=discount,
            purpose=purpose,
            due_ref='',
            sender_phone=sender_phone,
            request_id=request_id,
            order_id=order_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            shipping_address=shipping_address,
            billing_address=billing_address,
            pay_for='self',
        )

        return {'statusCode': 200, 'success': True, 'message': 'Invoice created and sent'}
    except Exception as e:
        logger.error(json.dumps({'event': 'dashboard_invoice_error', 'error': str(e), 'requestId': request_id}))
        return {'statusCode': 500, 'success': False, 'error': str(e)}


def _generate_and_send_invoice(contact_id: str, phone_number_id: str, amount: float,
                               quantity: int, item_name: str, gst_rate: float,
                               shipping: float, discount: float, purpose: str,
                               due_ref: str, sender_phone: str, request_id: str,
                               pay_ref: str = '', paid_at: str = '',
                               order_id: str = 'Offline', customer_name: str = '',
                               customer_phone: str = '', customer_email: str = '',
                               shipping_address: str = '', billing_address: str = '',
                               pay_for: str = 'self') -> None:
    """Generate POS invoice image with logo, upload to S3, send via WhatsApp."""
    try:
        inv_ref = f"WD-PAY-{uuid.uuid4().hex[:8].upper()}"

        if not paid_at:
            import datetime
            now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
            paid_at = now_ist.strftime('%d-%m-%Y %H:%M:%S')

        # Load logo from S3
        logo_pixels = None
        logo_w = logo_h = 0
        try:
            logo_obj = s3.get_object(Bucket=MEDIA_BUCKET, Key='stream/media/m/wecare-digital.png')
            logo_bytes = logo_obj['Body'].read()
            logo_w, logo_h, logo_pixels = _decode_png_pixels(logo_bytes)
            if logo_w is None:
                logo_pixels = None
                logo_w = logo_h = 0
            logger.info(json.dumps({'event': 'logo_loaded', 'width': logo_w, 'height': logo_h}))
        except Exception as logo_err:
            logger.warning(json.dumps({'event': 'logo_load_error', 'error': str(logo_err)}))

        lines = _build_invoice_lines(
            ref_id=inv_ref, pay_ref=pay_ref or '-', item_name=item_name,
            unit_price=amount, qty=quantity, gst_rate=gst_rate,
            shipping=shipping, discount=discount, sender_phone=sender_phone,
            purpose=purpose, due_ref=due_ref, paid_at=paid_at,
            order_id=order_id, customer_name=customer_name,
            customer_phone=customer_phone, customer_email=customer_email,
            shipping_address=shipping_address, billing_address=billing_address,
            pay_for=pay_for,
        )

        png_bytes = _render_text_to_png(lines, scale=3, logo_pixels=logo_pixels, logo_w=logo_w, logo_h=logo_h)

        s3_key = f'stack/invoices/wecare-digital-{inv_ref}.png'
        s3.put_object(
            Bucket=MEDIA_BUCKET,
            Key=s3_key,
            Body=png_bytes,
            ContentType='image/png',
            CacheControl='public, max-age=31536000',
        )

        logger.info(json.dumps({
            'event': 'invoice_uploaded',
            'invoiceRef': inv_ref,
            'payRef': pay_ref,
            's3Key': s3_key,
            'sizeBytes': len(png_bytes),
            'requestId': request_id,
        }))

        invoice_payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'content': f'Here is your invoice {inv_ref}',
                'mediaFile': f's3://{MEDIA_BUCKET}/{s3_key}',
                'mediaType': 'image',
                'mediaFileName': f'{inv_ref}.png',
            })
        }
        lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(invoice_payload),
        )

        # Store invoice record in Messages table
        try:
            messages_table = dynamodb.Table(MESSAGES_TABLE)
            now = int(time.time())
            subtotal = amount * quantity
            after_promo = subtotal - discount
            gst_amt = round(after_promo * gst_rate / 100, 2)
            cgst = round(gst_amt / 2, 2)
            sgst = round(gst_amt / 2, 2)
            conv_base = round(after_promo * 0.02, 2)
            conv_gst = round(conv_base * 0.18, 2)
            conv_fee = round(conv_base + conv_gst, 2)
            total = round(after_promo + gst_amt + shipping + conv_fee, 2)

            messages_table.put_item(Item={
                'id': str(uuid.uuid4()),
                'messageId': inv_ref,
                'contactId': contact_id,
                'channel': 'whatsapp',
                'direction': 'outbound',
                'messageType': 'invoice',
                'content': f'Invoice {inv_ref} (Paid)',
                'invoiceRef': inv_ref,
                'invoiceS3Key': s3_key,
                'paymentReferenceId': pay_ref or '',
                'paymentItemName': item_name,
                'paymentQuantity': quantity,
                'paymentAmount': Decimal(str(int(amount * 100))),
                'paymentSubtotal': Decimal(str(int(subtotal * 100))),
                'paymentDiscount': Decimal(str(int(discount * 100))),
                'paymentGstRate': Decimal(str(gst_rate)),
                'paymentGstAmount': Decimal(str(int(gst_amt * 100))),
                'paymentCgst': Decimal(str(int(cgst * 100))),
                'paymentSgst': Decimal(str(int(sgst * 100))),
                'paymentShipping': Decimal(str(int(shipping * 100))),
                'paymentConvFee': Decimal(str(int(conv_fee * 100))),
                'paymentTotal': Decimal(str(int(total * 100))),
                'paymentPurpose': purpose or '',
                'paymentDueRef': due_ref or '',
                'senderPhone': sender_phone,
                'paidAt': paid_at,
                'status': 'paid',
                'createdAt': Decimal(str(now)),
                'expiresAt': Decimal(str(now + 86400 * 365)),
            })
        except Exception as store_err:
            logger.warning(json.dumps({
                'event': 'invoice_store_error',
                'error': str(store_err),
                'invoiceRef': inv_ref,
                'requestId': request_id,
            }))

        logger.info(json.dumps({
            'event': 'invoice_sent',
            'invoiceRef': inv_ref,
            'payRef': pay_ref,
            'contactId': contact_id,
            'requestId': request_id,
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'invoice_generation_error',
            'error': str(e),
            'contactId': contact_id,
            'requestId': request_id,
        }))


# ============================================================================
# BOT FLOW CONFIGS (loaded from SystemConfigTable, dashboard-manageable)
# ============================================================================

# Default flow triggers config  -  keyword-to-flow mapping
# Keywords MUST include: exact keyword, selfservice menu row title (without emoji),
# natural variations, and the list_reply action keyword from MENU_TO_KEYWORD.
DEFAULT_FLOW_TRIGGERS = {
    'submit_request': {
        'keywords': [
            'submit request', 'sr', 'raise request', 'submit', 'request',
            'new request', 'start a new support request', 'support request',
            '\U0001f4cb submit request',
        ],
        # Flow ID: 1469093721293830 = v3 (PUBLISHED on WABA 1)
        # Phone 2 (WABA 2) cannot send WABA 1 flows — it uses CTA URL fallback automatically
        'flowId': '1469093721293830',
        'message': {
            'body': '\U0001f4cb Start a new support request. Share the details and our team will follow up with you.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Submit Request',
        },
        'enabled': True,
    },
    'track_request': {
        'keywords': [
            'track request', 'track', 'status', 'where is my request', 'check status',
            'request status', 'track order', 'check the status',
            '\U0001f50d track request',
        ],
        # DRAFT on WABA 1 — publish before enabling
        'flowId': '1486454129852338',
        'message': {
            'body': '\U0001f50d Check the status of your request anytime. Enter your reference ID below.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Track Request',
        },
        'enabled': True,
    },
    'amend_request': {
        'keywords': [
            'amend request', 'amend', 'change request', 'modify request',
            'update request', 'edit request', 'correct request',
            'edit or correct', 'existing request',
            '\u270f\ufe0f amend request',
        ],
        'flowId': '3678132465672138',
        'message': {
            'body': '\u270f\ufe0f Need to make a change? Edit or correct your submitted request.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Amend Request',
        },
        'enabled': True,
    },
    'schedule_appointment': {
        'keywords': [
            'schedule appointment', 'appointment', 'book appointment', 'schedule',
            'meeting', 'book meeting', 'schedule meeting', 'consultation',
            'schedule a consultation', 'service visit',
            '\U0001f4c5 appointment',
        ],
        'flowId': '26575380852083467',
        'message': {
            'body': '\U0001f4c5 Schedule a consultation or service visit at a time that works best for you.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Appointment',
        },
        'enabled': True,
    },
    'rx_slot': {
        'keywords': [
            'rx slot', 'rx', 'prescription', 'book rx', 'medicine', 'pharmacy',
            'chemist', 'book medical visit', 'medical visit', 'medical tourism',
            '\U0001fa7a rx slot',
        ],
        'flowId': '895208030185211',
        'message': {
            'body': '\U0001fa7a Schedule a medical tourism or prescription-related visit.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'RX Slot',
        },
        'enabled': True,
    },
    'drop_docs': {
        'keywords': [
            'drop docs', 'drop documents', 'upload docs', 'send docs', 'documents',
            'upload documents', 'share docs', 'supporting documents',
            '\U0001f4c4 drop docs',
        ],
        'flowId': '1211063631104445',
        'message': {
            'body': '\U0001f4c4 Send supporting documents for your request.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Drop Docs',
        },
        'enabled': True,
    },
    'enterprise_assist': {
        'keywords': [
            'enterprise assist', 'enterprise', 'business assist', 'corporate',
            'b2b', 'enterprise help', 'enterprise support', 'business support',
            'bulk enquiries', 'bulk',
            '\U0001f3e2 enterprise assist',
        ],
        'flowId': '1707170524029465',
        'message': {
            'body': '\U0001f3e2 Corporate, B2B, and bulk enquiries. Tell us what you need.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Enterprise Assist',
        },
        'enabled': True,
    },
    'leave_review': {
        'keywords': [
            'leave review', 'review', 'feedback', 'rate', 'rating', 'testimonial',
            'leave feedback', 'share your experience',
            '\u2b50 leave review',
        ],
        'flowId': '4423166114671543',
        'message': {
            'body': '\u2b50 Share your experience with our service.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Leave Review',
        },
        'enabled': True,
    },
    'subscribe': {
        'keywords': [
            'subscribe', 'signup', 'sign up', 'register', 'join', 'membership',
            'enroll', 'enrol', 'subscribe for updates', 'updates', '/subscribe',
            '\U0001f514 subscribe for updates',
        ],
        'flowId': '1262971692700761',
        'flowId2': '951987930811295',
        'message': {
            'body': '\U0001f514 Get updates, offers, and service news. Fill in your details to stay connected.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Subscribe for Updates',
        },
        'enabled': True,
    },
    'order_notes': {
        'keywords': ['order notes', 'order note', 'special instructions', 'delivery notes', 'order instructions'],
        'flowId': '1434731571172691',
        'message': {
            'body': '\U0001f4dd Add notes to your order \u2014 share any special instructions.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Order Notes',
        },
        'enabled': True,
    },
}


def _link_media_to_service_request(contact_id: str, s3_key: str, media_type: str,
                                   filename: str, mime: str, request_id: str) -> None:
    """If the contact has a recent OPEN service request, copy the media into the
    request's folder (stack/service-requests/{req}/) under the app bucket and append
    it to the request's attachments list so the team can service it from the dashboard."""
    if not contact_id or not s3_key:
        return
    try:
        c = dynamodb.Table(CONTACTS_TABLE).get_item(Key={'id': contact_id}).get('Item') or {}
        req = c.get('openServiceRequestId') or ''
        opened_at = int(c.get('openServiceRequestAt') or 0)
        # Only link within 14 days of the request being opened.
        if not req or (int(time.time()) - opened_at) > 14 * 86400:
            return
        base = s3_key.split('/')[-1]
        dest_key = f"stack/service-requests/{req}/{int(time.time())}-{base}"
        try:
            s3.copy_object(Bucket=MEDIA_BUCKET, CopySource={'Bucket': MEDIA_BUCKET, 'Key': s3_key}, Key=dest_key)
        except Exception:
            dest_key = s3_key  # fall back to the original key if copy fails
        attachment = {
            'key': dest_key,
            'url': f'https://{MEDIA_BUCKET}/{dest_key}',
            'type': media_type,
            'filename': filename or base,
            'mime': mime or '',
            'ts': int(time.time()),
        }
        try:
            dynamodb.Table(FLOW_SUBMISSIONS_TABLE).update_item(
                Key={'submissionId': req},
                UpdateExpression='SET attachments = list_append(if_not_exists(attachments, :empty), :a), updatedAt = :u',
                ExpressionAttributeValues={':a': [attachment], ':empty': [], ':u': int(time.time())},
            )
            logger.info(json.dumps({'event': 'service_request_attachment_added', 'submissionId': req,
                                    'key': dest_key, 'requestId': request_id}))
        except Exception as e:
            logger.warning(json.dumps({'event': 'service_request_attachment_error', 'error': str(e),
                                       'requestId': request_id}))
    except Exception as e:
        logger.warning(json.dumps({'event': 'link_media_error', 'error': str(e), 'requestId': request_id}))


def _handle_postpay_submission(data: Dict, contact_id: str, sender_phone: str,
                               phone_number_id: str, request_id: str) -> None:
    """Handle a post-payment (endpointless) flow completion. The flow's 'complete'
    action returns reference_id + order/payment ids + the customer's details.
    Saves ONE submission per payment (idempotent, keyed on reference_id) and sends
    a confirmation message."""
    try:
        # New multi-screen flow uses request_id + order_number (+ full address/details).
        # Stay backward-compatible with the old payload (reference_id/delivery_note).
        request_sr_id = str(data.get('request_id', '')).strip()
        reference_id = str(data.get('reference_id') or data.get('order_number') or '').strip()
        if not request_sr_id and not reference_id:
            return
        now = int(time.time())
        # Key on the unique Request ID (falls back to reference for old payloads).
        sub_id = request_sr_id or f'postpay-{reference_id}'
        # Compose a human-readable shipping address from the flow's address fields.
        addr_parts = [data.get('address', ''), data.get('landmark', ''), data.get('city', ''),
                      data.get('state', ''), data.get('pin', '')]
        address_str = ', '.join(str(p).strip() for p in addr_parts if str(p).strip())
        form = {k: v for k, v in data.items() if k not in ('flow_token',)}
        item = {
            'submissionId': sub_id,
            'flowCode': '03.WD_POSTPAY_REQUEST',
            'flowType': 'service_request',
            'phone': sender_phone,
            'contactId': contact_id or '',
            'formData': json.dumps(form),
            'submissionNumber': sub_id,
            'requestId': request_sr_id,
            'orderId': reference_id,
            'referenceId': reference_id,
            'orderNumber': str(data.get('order_number', '')),
            'product': str(data.get('product', '')),
            'amount': str(data.get('amount', '')),
            'customerName': str(data.get('name', '')),
            'shippingAddress': address_str,
            'addressLine1': str(data.get('address', '')),
            'city': str(data.get('city', '')),
            'state': str(data.get('state', '')),
            'postalCode': str(data.get('pin', '')),
            'landmark': str(data.get('landmark', '')),
            'description': str(data.get('description', '')),
            'deliveryNote': str(data.get('delivery_note', '')),
            'preferredTime': str(data.get('preferred_time', '')),
            'status': 'open',
            'paymentStatus': 'paid',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
            'ttl': now + (365 * 86400),
        }
        try:
            dynamodb.Table(FLOW_SUBMISSIONS_TABLE).put_item(
                Item={k: v for k, v in item.items() if v is not None and v != ''},
                ConditionExpression='attribute_not_exists(submissionId)',
            )
            logger.info(json.dumps({'event': 'postpay_submission_saved', 'submissionId': sub_id,
                                    'requestId2': request_sr_id, 'referenceId': reference_id,
                                    'requestId': request_id}))
        except Exception as e:
            if 'ConditionalCheckFailedException' in str(e):
                logger.info(json.dumps({'event': 'postpay_submission_duplicate', 'submissionId': sub_id,
                                        'requestId': request_id}))
                return  # already recorded — do not send a second confirmation
            raise
        # Update the customer's saved address from the flow so future orders pre-fill.
        try:
            if contact_id:
                # Tag the contact with the open request so any media they send next
                # gets attached to THIS request. Also save the address for reuse.
                _uexpr = 'SET openServiceRequestId=:rid, openServiceRequestAt=:ua, updatedAt=:ua'
                _names = {}
                _vals = {':rid': sub_id, ':ua': now}
                if address_str:
                    _uexpr += (', shippingAddress=:sa, addressLine1=:al, city=:cy, '
                               '#st=:st, postalCode=:pc, landmark=:lm')
                    _names['#st'] = 'state'
                    _vals.update({':sa': address_str, ':al': str(data.get('address', '')),
                                  ':cy': str(data.get('city', '')), ':st': str(data.get('state', '')),
                                  ':pc': str(data.get('pin', '')), ':lm': str(data.get('landmark', ''))})
                _kwargs = {'Key': {'id': contact_id}, 'UpdateExpression': _uexpr,
                           'ExpressionAttributeValues': _vals}
                if _names:
                    _kwargs['ExpressionAttributeNames'] = _names
                dynamodb.Table(CONTACTS_TABLE).update_item(**_kwargs)
        except Exception:
            pass
        # Confirmation message showing the Request ID.
        try:
            rid = request_sr_id or sub_id
            msg = (f'\u2705 *Request confirmed*\n\nRequest ID: *{rid}*\n'
                   'Our team will process it within 24-48 hours. You can send any photos '
                   'or documents here and we\u2019ll attach them to your request.\n\n'
                   '_Thank you for choosing WECARE.DIGITAL_')
            meta_pid = _get_meta_phone_id_for_direct_api(phone_number_id)
            _send_direct_api_message(sender_phone, {'type': 'text', 'text': {'body': msg}}, meta_pid)
        except Exception:
            pass
    except Exception as e:
        logger.error(json.dumps({'event': 'postpay_submission_error', 'error': str(e), 'requestId': request_id}))


def _handle_address_submission(nfm: Dict, contact_id: str, sender_phone: str,
                               phone_number_id: str, request_id: str) -> None:
    """Handle a native India Address Message submission (nfm_reply,
    name='address_message'). Parses response_json and saves the structured
    shipping address to the contact so checkout / order_details can reuse it."""
    try:
        raw = nfm.get('response_json', '{}')
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        vals = data.get('values', data) or {}
        house = vals.get('house_number', '')
        floor = vals.get('floor_number', '')
        tower = vals.get('tower_number', '')
        building = vals.get('building_name', '')
        addr = vals.get('address', '')
        landmark = vals.get('landmark_area', '')
        city = vals.get('city', '')
        state = vals.get('state', '')
        pin = vals.get('in_pin_code', '')
        name = vals.get('name', '')
        parts = [house, (f'Floor {floor}' if floor else ''), tower, building, addr, landmark, city, state, pin]
        address_str = ', '.join(p for p in parts if p)
        logger.info(json.dumps({
            'event': 'address_submission', 'phone_suffix': sender_phone[-4:] if sender_phone else '',
            'savedAddressId': data.get('saved_address_id', ''), 'pin': pin, 'city': city,
            'requestId': request_id,
        }))
        if not contact_id:
            return
        ct = dynamodb.Table(CONTACTS_TABLE)
        expr_names = {'#st': 'state'}
        expr_vals = {
            ':sa': address_str, ':hn': house, ':fl': floor, ':tw': tower, ':bn': building,
            ':al': addr, ':lm': landmark, ':cy': city, ':st': state, ':pc': pin,
            ':co': 'India', ':ua': int(time.time()),
        }
        update_expr = ('SET shippingAddress=:sa, houseNumber=:hn, floorNumber=:fl, towerNumber=:tw, '
                       'buildingName=:bn, addressLine1=:al, landmark=:lm, city=:cy, #st=:st, '
                       'postalCode=:pc, country=:co, updatedAt=:ua')
        if name:
            update_expr += ', contactBookName=:nm'
            expr_vals[':nm'] = name
        ct.update_item(Key={'id': contact_id}, UpdateExpression=update_expr,
                       ExpressionAttributeNames=expr_names, ExpressionAttributeValues=expr_vals)
        logger.info(json.dumps({'event': 'address_saved', 'contactId': contact_id, 'requestId': request_id}))
    except Exception as e:
        logger.error(json.dumps({'event': 'address_submission_error', 'error': str(e), 'requestId': request_id}))


def _handle_list_reply(list_id: str, contact_id: str, phone_number_id: str,
                      sender_phone: str, request_id: str) -> None:
    """
    Handle interactive list_reply selections from main menu and self-service menu.
    Maps row IDs to keyword triggers or sub-menus.
    """
    logger.info(json.dumps({
        'event': 'list_reply_received',
        'listId': list_id,
        'contactId': contact_id,
        'requestId': request_id,
    }))

    # ── Main menu row IDs → actions ──
    MENU_TO_KEYWORD = {
        # Main menu  -  Start Here
        'menu_selfservice': '_selfservice_menu',
        'menu_self_service': '_selfservice_menu',  # legacy
        'menu_subscribe': 'subscribe',
        'menu_find_id': 'find id',
        'menu_pay': 'pay',
        # Main menu  -  Explore WECARE
        'menu_store': '_cta_store',
        'menu_gift_card': '_cta_gift_card',
        'menu_bharat_stack': '_cta_bharat_stack',
        # Main menu  -  Help & Answers
        'menu_faq': '_cta_faq',
        'menu_about': '_cta_about',
        # Legacy main menu IDs (old menu, may be cached)
        'menu_app': '_cta_about',
        'menu_audio': None,
        'menu_language': '_language_menu',
        'menu_notifications': None,
        'menu_human': None,
        # Self-service menu
        'ss_submit_request': 'submit request',
        'ss_amend_request': 'amend request',
        'ss_track_request': 'track request',
        'ss_order_notes': 'order notes',
        'ss_subscribe': 'subscribe',
        'ss_rx_slot': 'rx slot',
        'ss_drop_docs': 'drop docs',
        'ss_schedule_appointment': 'schedule appointment',
        'ss_enterprise_assist': 'enterprise assist',
        'ss_leave_review': 'leave review',
        'ss_faq': '_cta_faq',
        'ss_main_menu': '_main_menu',
        # Legacy self-service IDs
        'ss_orders': 'track request',
        'ss_payments': 'pay',
        'ss_support': 'submit request',
        # Bharat Stack
        'bs_aadhaar': None,
        'bs_upi': None,
        'bs_digilocker': None,
        'bs_esign': None,
        'bs_ondc': None,
        'bs_account_aggregator': None,
    }

    action = MENU_TO_KEYWORD.get(list_id)

    # Sub-menu triggers
    if action == '_selfservice_menu':
        _send_interactive_list(
            contact_id=contact_id,
            phone_number_id=phone_number_id,
            list_config=_get_selfservice_menu(),
            request_id=request_id,
        )
        return

    if action == '_bharat_stack_menu':
        _send_interactive_list(
            contact_id=contact_id,
            phone_number_id=phone_number_id,
            list_config=_get_bharat_stack_menu(),
            request_id=request_id,
        )
        return

    if action == '_main_menu':
        _send_interactive_list(
            contact_id=contact_id,
            phone_number_id=phone_number_id,
            list_config=_get_welcome_config(),
            request_id=request_id,
        )
        return

    if action == '_language_menu':
        _send_interactive_list(
            contact_id=contact_id,
            phone_number_id=phone_number_id,
            list_config=_get_language_picker_config(),
            request_id=request_id,
        )
        return

    # ── CTA URL buttons (Store, Gift Card, FAQ, Bharat Stack) ──
    # Each sends ONE interactive CTA message with body + button + footer
    # Then followup reply buttons as second message
    if action == '_cta_faq':
        _send_cta_button(contact_id, phone_number_id, 'Open FAQs', 'https://wecare.digital/faq', request_id,
            body_text="Find quick answers about requests, payments, appointments, business hours, the app, and more.\n\nTap below to open the FAQ page. \U0001f447",
            footer_text='WECARE.DIGITAL')
        _send_followup_buttons(contact_id, phone_number_id, request_id)
        return

    if action == '_cta_gift_card':
        _send_cta_button(contact_id, phone_number_id, 'View Gift Cards', 'https://wecare.digital/gift-card', request_id,
            body_text="Send a digital gift card in just a few taps \u2014 quick, easy, and thoughtful.\n\nTap below to continue. \U0001f447",
            footer_text='WECARE.DIGITAL')
        _send_followup_buttons(contact_id, phone_number_id, request_id)
        return

    if action == '_cta_store':
        _send_cta_button(contact_id, phone_number_id, 'Visit Store', 'https://wecare.digital', request_id,
            body_text="Browse WECARE.DIGITAL services, brands, and offers \u2014 all in one place.\n\nTap below to explore. \U0001f447",
            footer_text='WECARE.DIGITAL')
        _send_followup_buttons(contact_id, phone_number_id, request_id)
        return

    if action == '_cta_bharat_stack':
        _send_cta_button(contact_id, phone_number_id, 'Explore Bharat Stack', 'https://stack.wecare.digital', request_id,
            body_text="Explore Bharat Stack and discover services designed for everyday Bharat.",
            footer_text='WECARE.DIGITAL')
        _send_followup_buttons(contact_id, phone_number_id, request_id)
        return

    # About WECARE.DIGITAL  -  text only, no CTA + follow-up buttons
    if action == '_cta_about':
        about_text = (
            "*Building digital railroads for everyday Bharat*\n\n"
            "WECARE.DIGITAL is a network of microservice brands serving everyday Bharat\u2014"
            "across travel, paperwork, disputes, rituals, and reflection.\n\n"
            "We focus on simple access, transparent pricing, and reliable service through "
            "Bnb Club, Expo Week, Legal Champ, No Fault, Ritual Guru, Swdhya, and Bharat Stack.\n\n"
            "Made to serve what matters most."
        )
        _send_ai_auto_reply(contact_id, about_text, phone_number_id, request_id)
        _send_followup_buttons(contact_id, phone_number_id, request_id)
        return

    # Keyword-triggered flows
    if action and action != 'pay':
        flow_triggers = _get_flow_triggers_config()
        for flow_key, trigger in flow_triggers.items():
            if not trigger.get('enabled', True):
                continue
            keywords = [k.lower() for k in trigger.get('keywords', [])]
            if action.lower() in keywords:
                flow_id = trigger.get('flowId', '')
                if flow_id:
                    _send_generic_flow(
                        contact_id=contact_id,
                        phone_number_id=phone_number_id,
                        sender_phone=sender_phone,
                        request_id=request_id,
                        flow_config=trigger,
                        flow_key=flow_key,
                    )
                    return
        # Fallback: send the keyword as text so it gets picked up by keyword matching
        _send_ai_auto_reply(contact_id, f"You selected: {action.title()}. Processing...", phone_number_id, request_id)
        return

    # Pay keyword
    if action == 'pay':
        # Phone 2: send CTA link to Phone 1 for payment
        if phone_number_id == PHONE_NUMBER_ID_2:
            _send_cta_button(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                cta_text='Pay Now',
                cta_url='https://r.wecare.digital/pay',
                request_id=request_id,
                body_text='\U0001f4b3 Make your payment quickly and securely online.',
                footer_text='WECARE.DIGITAL',
            )
            _send_followup_buttons(contact_id, phone_number_id, request_id)
            return
        # Phone 1: trigger pay flow directly
        _send_ai_auto_reply(contact_id, PAY_MSG['pulling'], phone_number_id, request_id)
        try:
            inv_payload = {
                'rawPath': '/invoices/send-pending-by-phone',
                'requestContext': {'http': {'method': 'POST'}},
                'body': json.dumps({
                    'customerPhone': sender_phone,
                    'phoneNumberId': phone_number_id,
                }),
            }
            inv_response = lambda_client.invoke(
                FunctionName='wecare-invoice-engine',
                InvocationType='RequestResponse',
                Payload=json.dumps(inv_payload),
            )
            inv_result = json.loads(inv_response['Payload'].read())
            inv_body = json.loads(inv_result.get('body', '{}'))
            if inv_body.get('total', 0) == 0:
                _send_ai_auto_reply(contact_id, PAY_MSG['no_dues'], phone_number_id, request_id)
        except Exception as e:
            logger.warning(f"List reply pay flow error: {e}")
            _send_ai_auto_reply(contact_id, PAY_MSG['error'], phone_number_id, request_id)
        return

    # Unhandled list ID  -  log it
    if not action:
        logger.info(json.dumps({
            'event': 'list_reply_unhandled',
            'listId': list_id,
            'contactId': contact_id,
            'requestId': request_id,
        }))


def _get_flow_triggers_config() -> Dict:
    """Load flow triggers config from SystemConfigTable (id: 'flow_triggers_config')."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'flow_triggers_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            # Merge with defaults  -  config overrides per flow key
            merged = {}
            for key, default in DEFAULT_FLOW_TRIGGERS.items():
                if key in config:
                    entry = default.copy()
                    entry.update(config[key])
                    if 'message' in config[key]:
                        entry['message'] = {**default.get('message', {}), **config[key]['message']}
                    merged[key] = entry
                else:
                    merged[key] = default.copy()
            # Also include any new flows defined in config but not in defaults
            for key, val in config.items():
                if key not in merged:
                    merged[key] = val
            return merged
        return {k: v.copy() for k, v in DEFAULT_FLOW_TRIGGERS.items()}
    except Exception:
        return {k: v.copy() for k, v in DEFAULT_FLOW_TRIGGERS.items()}

DEFAULT_MAIN_MENU = {
    'header': 'Welcome to WECARE.DIGITAL',
    'body': "Choose what you\u2019d like to do \u2014 get started, explore our services, or find quick answers.",
    'footer': 'Tap an option to continue.',
    'buttonText': 'Get Started',
    'sections': [
        {
            'title': 'Start Here',
            'rows': [
                {'id': 'menu_selfservice', 'title': '\U0001f680 Selfservice', 'description': 'Requests, appointments, documents, and support'},
                {'id': 'menu_subscribe', 'title': '\U0001f514 Subscribe for Updates', 'description': 'Get updates, offers, and service news'},
                {'id': 'menu_find_id', 'title': '\U0001f194 Find Profile ID', 'description': 'Locate your subscription or profile ID'},
                {'id': 'menu_pay', 'title': '\U0001f4b3 Make a Payment', 'description': 'Pay an invoice or complete a pending payment'},
            ]
        },
        {
            'title': 'Explore WECARE',
            'rows': [
                {'id': 'menu_store', 'title': '\U0001f6cd\ufe0f Explore Store', 'description': 'Browse services, brands, and offers'},
                {'id': 'menu_gift_card', 'title': '\U0001f381 Gift Cards', 'description': 'Send a digital gift card'},
                {'id': 'menu_bharat_stack', 'title': '\U0001f1ee\U0001f1f3 Bharat Stack', 'description': 'Discover Bharat Stack and services'},
            ]
        },
        {
            'title': 'Help & Answers',
            'rows': [
                {'id': 'menu_faq', 'title': '\u2753 FAQs', 'description': 'Find answers to common questions'},
                {'id': 'menu_about', 'title': '\U0001f49b About WECARE.DIGITAL', 'description': 'Learn more about WECARE.DIGITAL'},
            ]
        },
    ]
}

DEFAULT_LANGUAGE_PICKER = {
    'header': '\U0001f310 Choose Region',
    'body': 'Please select a language group.\n\n\u0915\u0943\u092a\u092f\u093e \u092d\u093e\u0937\u093e \u0938\u092e\u0942\u0939 \u091a\u0941\u0928\u0947\u0902\u0964',
    'footer': 'You can change anytime by typing "language <name>"',
    'buttonText': 'Regions',
    'sections': [
        {
            'title': 'Select Region',
            'rows': [
                {'id': 'region_popular', 'title': '\u2b50 Popular', 'description': 'English, Hindi, Bengali, Tamil & more'},
                {'id': 'region_asian', 'title': '\U0001f30f Asian', 'description': '\u4e2d\u6587, \u65e5\u672c\u8a9e, \ud55c\uad6d\uc5b4, \u0e44\u0e17\u0e22 & more'},
                {'id': 'region_middle_east', 'title': '\U0001f30d Middle East', 'description': '\u0627\u0644\u0639\u0631\u0628\u064a\u0629, T\u00fcrk\u00e7e, \u0420\u0443\u0441\u0441\u043a\u0438\u0439, \u0627\u0631\u062f\u0648'},
                {'id': 'region_european', 'title': '\U0001f1ea\U0001f1fa European', 'description': 'Fran\u00e7ais, Espa\u00f1ol, Portugu\u00eas'},
            ]
        }
    ]
}

# Step 2: Language lists per region (used when ai-generate-response returns regionLanguages)
REGION_LANGUAGE_LISTS = {
    'region_popular': {
        'header': '\u2b50 Popular Languages',
        'body': 'Choose your language \U0001f447',
        'footer': 'wecare.digital',
        'buttonText': 'Languages',
        'sections': [{'title': 'Languages', 'rows': [
            {'id': 'lang_english', 'title': 'English', 'description': 'Respond in English'},
            {'id': 'lang_hindi', 'title': '\u0939\u093f\u0928\u094d\u0926\u0940 / Hindi', 'description': '\u0939\u093f\u0902\u0926\u0940 \u092e\u0947\u0902 \u091c\u0935\u093e\u092c \u0926\u0947\u0902'},
            {'id': 'lang_hinglish', 'title': 'Hinglish', 'description': 'Hindi + English mix'},
            {'id': 'lang_bengali', 'title': '\u09ac\u09be\u0982\u09b2\u09be / Bengali', 'description': '\u09ac\u09be\u0982\u09b2\u09be\u09af\u09bc \u0989\u09a4\u09cd\u09a4\u09b0 \u09a6\u09bf\u09a8'},
            {'id': 'lang_tamil', 'title': '\u0ba4\u0bae\u0bbf\u0bb4\u0bcd / Tamil', 'description': '\u0ba4\u0bae\u0bbf\u0bb4\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0bbf\u0bb2\u0bb3\u0bbf\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd'},
            {'id': 'lang_telugu', 'title': '\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41 / Telugu', 'description': '\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41\u0c32\u0c4b \u0c38\u0c2e\u0c3e\u0c27\u0c3e\u0c28\u0c02'},
            {'id': 'lang_gujarati', 'title': '\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0 / Gujarati', 'description': '\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0\u0aae\u0abe\u0a82 \u0a9c\u0ab5\u0abe\u0aac'},
            {'id': 'lang_marathi', 'title': '\u092e\u0930\u093e\u0920\u0940 / Marathi', 'description': '\u092e\u0930\u093e\u0920\u0940\u0924 \u0909\u0924\u094d\u0924\u0930 \u0926\u094d\u092f\u093e'},
            {'id': 'lang_kannada', 'title': '\u0c95\u0ca8\u0ccd\u0ca8\u0ca1 / Kannada', 'description': '\u0c95\u0ca8\u0ccd\u0ca8\u0ca1\u0ca6\u0cb2\u0ccd\u0cb2\u0cbf \u0c89\u0ca4\u0ccd\u0ca4\u0cb0'},
            {'id': 'lang_malayalam', 'title': '\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02 / Malayalam', 'description': '\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d24\u0d4d\u0d24\u0d3f\u0d7d \u0d2e\u0d31\u0d41\u0d2a\u0d1f\u0d3f'},
        ]}]
    },
    'region_asian': {
        'header': '\U0001f30f Asian Languages',
        'body': 'Choose your language \U0001f447',
        'footer': 'wecare.digital',
        'buttonText': 'Languages',
        'sections': [{'title': 'Languages', 'rows': [
            {'id': 'lang_chinese', 'title': '\u7b80\u4f53\u4e2d\u6587 / Chinese', 'description': '\u7528\u4e2d\u6587\u56de\u590d'},
            {'id': 'lang_japanese', 'title': '\u65e5\u672c\u8a9e / Japanese', 'description': '\u65e5\u672c\u8a9e\u3067\u5fdc\u7b54'},
            {'id': 'lang_korean', 'title': '\ud55c\uad6d\uc5b4 / Korean', 'description': '\ud55c\uad6d\uc5b4\ub85c \ub2f5\ubcc0'},
            {'id': 'lang_thai', 'title': '\u0e44\u0e17\u0e22 / Thai', 'description': '\u0e15\u0e2d\u0e1a\u0e40\u0e1b\u0e47\u0e19\u0e20\u0e32\u0e29\u0e32\u0e44\u0e17\u0e22'},
            {'id': 'lang_vietnamese', 'title': 'Ti\u1ebfng Vi\u1ec7t / Vietnamese', 'description': 'Tr\u1ea3 l\u1eddi b\u1eb1ng ti\u1ebfng Vi\u1ec7t'},
            {'id': 'lang_indonesian', 'title': 'Indonesia / Indonesian', 'description': 'Balas dalam Bahasa Indonesia'},
            {'id': 'lang_sinhala', 'title': '\u0dc3\u0dd2\u0d82\u0dc4\u0dbd / Sinhala', 'description': '\u0dc3\u0dd2\u0d82\u0dc4\u0dbd\u0dd9\u0db1\u0dca \u0db4\u0dd2\u0dc5\u0dd2\u0dad\u0dd4\u0dbb\u0dd4'},
        ]}]
    },
    'region_middle_east': {
        'header': '\U0001f30d Middle East Languages',
        'body': 'Choose your language \U0001f447',
        'footer': 'wecare.digital',
        'buttonText': 'Languages',
        'sections': [{'title': 'Languages', 'rows': [
            {'id': 'lang_arabic', 'title': '\u0627\u0644\u0639\u0631\u0628\u064a\u0629 / Arabic', 'description': '\u0627\u0644\u0631\u062f \u0628\u0627\u0644\u0639\u0631\u0628\u064a\u0629'},
            {'id': 'lang_turkish', 'title': 'T\u00fcrk\u00e7e / Turkish', 'description': 'T\u00fcrk\u00e7e yan\u0131t verin'},
            {'id': 'lang_russian', 'title': '\u0420\u0443\u0441\u0441\u043a\u0438\u0439 / Russian', 'description': '\u041e\u0442\u0432\u0435\u0442 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c'},
            {'id': 'lang_urdu', 'title': '\u0627\u0631\u062f\u0648 / Urdu', 'description': '\u0627\u0631\u062f\u0648 \u0645\u06cc\u06ba \u062c\u0648\u0627\u0628 \u062f\u06cc\u06ba'},
            {'id': 'lang_punjabi', 'title': '\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40 / Punjabi', 'description': '\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40 \u0a35\u0a3f\u0a71\u0a1a \u0a1c\u0a35\u0a3e\u0a2c'},
        ]}]
    },
    'region_european': {
        'header': '\U0001f1ea\U0001f1fa European Languages',
        'body': 'Choose your language \U0001f447',
        'footer': 'wecare.digital',
        'buttonText': 'Languages',
        'sections': [{'title': 'Languages', 'rows': [
            {'id': 'lang_french', 'title': 'Fran\u00e7ais / French', 'description': 'R\u00e9pondre en fran\u00e7ais'},
            {'id': 'lang_spanish', 'title': 'Espa\u00f1ol / Spanish', 'description': 'Responder en espa\u00f1ol'},
            {'id': 'lang_portuguese', 'title': 'Portugu\u00eas / Portuguese', 'description': 'Responder em portugu\u00eas'},
        ]}]
    },
}


def _get_welcome_config() -> Dict:
    """Load main menu config from SystemConfigTable (id: 'welcome_message_config')."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'welcome_message_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            merged = DEFAULT_MAIN_MENU.copy()
            merged.update(config)
            return merged
        return DEFAULT_MAIN_MENU.copy()
    except Exception:
        return DEFAULT_MAIN_MENU.copy()


# ── Bharat Stack sub-menu ──
DEFAULT_BHARAT_STACK_MENU = {
    'header': 'Bharat Stack',
    'body': 'Explore India\u2019s digital public infrastructure \U0001f1ee\U0001f1f3',
    'footer': 'wecare.digital',
    'buttonText': 'Explore',
    'sections': [
        {
            'title': 'Bharat Stack Services',
            'rows': [
                {'id': 'bs_aadhaar', 'title': 'Aadhaar Services', 'description': 'Verify, link, update Aadhaar'},
                {'id': 'bs_upi', 'title': 'UPI Payments', 'description': 'Send, receive, check balance'},
                {'id': 'bs_digilocker', 'title': 'DigiLocker', 'description': 'Access digital documents'},
                {'id': 'bs_esign', 'title': 'eSign', 'description': 'Digital signature services'},
                {'id': 'bs_ondc', 'title': 'ONDC', 'description': 'Open Network for Digital Commerce'},
                {'id': 'bs_account_aggregator', 'title': 'Account Aggregator', 'description': 'Consent-based financial data'},
            ]
        }
    ]
}


def _get_bharat_stack_menu() -> Dict:
    """Load Bharat Stack menu config from SystemConfigTable."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'bharat_stack_menu_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            merged = DEFAULT_BHARAT_STACK_MENU.copy()
            merged.update(config)
            return merged
        return DEFAULT_BHARAT_STACK_MENU.copy()
    except Exception:
        return DEFAULT_BHARAT_STACK_MENU.copy()


# ── Self-service sub-menu ──
DEFAULT_SELFSERVICE_MENU = {
    'header': 'Selfservice',
    'body': "Choose what you'd like to do. You can submit or track a request, book a visit, upload documents, or get business support.",
    'footer': 'Tap an option to continue.',
    'buttonText': 'Browse Services',
    'sections': [
        {
            'title': 'New Request',
            'rows': [
                {'id': 'ss_submit_request', 'title': '\U0001f4cb Submit Request', 'description': 'Start a new support request'},
            ]
        },
        {
            'title': 'Request Status',
            'rows': [
                {'id': 'ss_track_request', 'title': '\U0001f50d Track Request', 'description': 'Check the status of your request'},
            ]
        },
        {
            'title': 'Existing Request',
            'rows': [
                {'id': 'ss_amend_request', 'title': '\u270f\ufe0f Amend Request', 'description': 'Edit or correct a submitted request'},
            ]
        },
        {
            'title': 'Schedule Appointments',
            'rows': [
                {'id': 'ss_schedule_appointment', 'title': '\U0001f4c5 Appointment', 'description': 'Schedule a consultation or service visit'},
            ]
        },
        {
            'title': 'Medical Tourism',
            'rows': [
                {'id': 'ss_rx_slot', 'title': '\U0001fa7a RX Slot', 'description': 'Schedule a medical tourism or prescription-related visit'},
            ]
        },
        {
            'title': 'Documents',
            'rows': [
                {'id': 'ss_drop_docs', 'title': '\U0001f4c4 Drop Docs', 'description': 'Send supporting documents for your request'},
            ]
        },
        {
            'title': 'Business Support',
            'rows': [
                {'id': 'ss_enterprise_assist', 'title': '\U0001f3e2 Enterprise Assist', 'description': 'Corporate, B2B, and bulk enquiries'},
            ]
        },
        {
            'title': 'Feedback',
            'rows': [
                {'id': 'ss_leave_review', 'title': '\u2b50 Leave Review', 'description': 'Share your experience with our service'},
            ]
        },
        {
            'title': 'Help',
            'rows': [
                {'id': 'ss_faq', 'title': '\u2753 FAQ', 'description': 'View frequently asked questions'},
            ]
        },
    ]
}


def _get_selfservice_menu() -> Dict:
    """Load self-service menu config from SystemConfigTable."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'selfservice_menu_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            merged = DEFAULT_SELFSERVICE_MENU.copy()
            merged.update(config)
            return merged
        return DEFAULT_SELFSERVICE_MENU.copy()
    except Exception:
        return DEFAULT_SELFSERVICE_MENU.copy()


def _get_language_picker_config() -> Dict:
    """Load language picker config from SystemConfigTable (id: 'bot_language_picker_config')."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'bot_language_picker_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            # Region picker (Step 1)  -  override rows if provided
            if 'regionPicker' in config:
                region_rows = config['regionPicker']
                return {
                    'header': config.get('regionHeader', DEFAULT_LANGUAGE_PICKER['header']),
                    'body': config.get('regionBody', DEFAULT_LANGUAGE_PICKER['body']),
                    'footer': config.get('regionFooter', DEFAULT_LANGUAGE_PICKER['footer']),
                    'buttonText': config.get('regionButtonText', DEFAULT_LANGUAGE_PICKER['buttonText']),
                    'sections': [{'title': 'Select Region', 'rows': region_rows}]
                }
            merged = DEFAULT_LANGUAGE_PICKER.copy()
            merged.update(config)
            return merged
        return DEFAULT_LANGUAGE_PICKER.copy()
    except Exception:
        return DEFAULT_LANGUAGE_PICKER.copy()


def _get_region_language_list(region_id: str) -> Optional[Dict]:
    """
    Get the language list for a specific region.
    Checks SystemConfigTable first (dashboard-manageable), falls back to REGION_LANGUAGE_LISTS.
    """
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'bot_language_picker_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            db_region_lists = config.get('regionLanguageLists', {})
            if region_id in db_region_lists:
                return db_region_lists[region_id]
    except Exception as e:
        logger.debug(f'Region language config lookup failed: {e}')
    return REGION_LANGUAGE_LISTS.get(region_id)


def _send_read_receipt(whatsapp_message_id: str, phone_number_id: str, request_id: str) -> None:
    """
    Send read receipt to WhatsApp per AWS docs.
    Per AWS: send-whatsapp-message with status='read' shows two blue check marks.
    """
    if not whatsapp_message_id:
        return
    
    try:
        # Build read receipt payload per Meta WhatsApp API
        read_receipt_payload = {
            'messaging_product': 'whatsapp',
            'message_id': whatsapp_message_id,
            'status': 'read'
        }
        
        logger.info(json.dumps({
            'event': 'read_receipt_payload',
            'messageId': whatsapp_message_id,
            'status': 'read',
            'requestId': request_id
        }))
        
        # Send read receipt via Direct API
        if _is_direct_api_phone(phone_number_id):
            meta_pid = _get_meta_phone_id_for_direct_api(phone_number_id)
            _send_direct_api_read_receipt(whatsapp_message_id, meta_phone_id=meta_pid)
            response = {'StatusCode': 200}
        else:
            # Fallback: try Direct API with default phone
            _send_direct_api_read_receipt(whatsapp_message_id)
            response = {'StatusCode': 200}
        
        logger.info(json.dumps({
            'event': 'read_receipt_sent',
            'messageId': whatsapp_message_id,
            'phoneNumberId': phone_number_id,
            'statusCode': response.get('StatusCode', 200),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'read_receipt_error',
            'messageId': whatsapp_message_id,
            'error': str(e),
            'requestId': request_id
        }))


# ============================================================================
# AI AUTOMATION INTEGRATION
# ============================================================================

# Default AI configuration
DEFAULT_AI_CONFIG = {
    'enabled': False,
    'autoReplyEnabled': False,
    'respondToInteractive': True,
    'respondToText': True,
    'respondToMedia': True,  # Now enabled  -  multimodal AI via Converse API
    'respondToLocation': True,
    'maxResponseLength': 500,
    'responseDelay': 0,
    'supportedLanguages': ['en', 'hi', 'hi-Latn', 'bn', 'ta', 'te', 'gu', 'mr'],
    'defaultLanguage': 'en',
    'agentId': '4UUQYFWX64',
    'agentAlias': 'TSTALIASID',
    'knowledgeBaseId': 'static-faq',
    'modelId': 'amazon.nova-pro-v1:0',
}


def _get_ai_config() -> Dict[str, Any]:
    """
    Get AI configuration from SystemConfig table.
    Returns default config if not found or on error.
    """
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        # SystemConfigTable PK is 'id', we use id=configKey for compatibility
        response = config_table.get_item(Key={'id': 'ai_config'})
        
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            # Merge with defaults to ensure all keys exist
            merged = DEFAULT_AI_CONFIG.copy()
            merged.update(config)
            return merged
        
        return DEFAULT_AI_CONFIG.copy()
    except Exception as e:
        logger.warning(f"Failed to get AI config: {str(e)}")
        return DEFAULT_AI_CONFIG.copy()


def _is_ai_enabled() -> bool:
    """
    Check if AI automation is enabled in SystemConfig.
    Returns False — AI auto-reply permanently removed.
    """
    return False


def _process_ai_automation(message_id: str, contact_id: str, content: str, message_type: str, phone_number_id: str, sender_phone: str, s3_key: str, mime_type: str, request_id: str, sender_bsuid: str = '') -> Optional[Dict]:
    """
    WhatsApp AI auto-reply — PERMANENTLY REMOVED.
    This function is kept as a no-op stub so callers don't break.
    """
    return None
    # Get AI config from SystemConfig table
    ai_config = _get_ai_config()
    ai_enabled = ai_config.get('enabled', False) and ai_config.get('autoReplyEnabled', False)
    
    # Check if this message type should trigger AI
    type_config_map = {
        'text': 'respondToText',
        'interactive': 'respondToInteractive',
        'button': 'respondToInteractive',
        'location': 'respondToLocation',
        'image': 'respondToMedia',
        'audio': 'respondToMedia',
        'video': 'respondToMedia',
        'document': 'respondToMedia',
    }
    config_key = type_config_map.get(message_type, 'respondToText')
    should_respond = ai_config.get(config_key, True)
    
    logger.info(json.dumps({
        'event': 'ai_automation_check',
        'aiEnabled': ai_enabled,
        'messageType': message_type,
        'shouldRespond': should_respond,
        'hasMedia': bool(s3_key),
        'messageId': message_id,
        'contentLength': len(content) if content else 0,
        'requestId': request_id
    }))
    
    if not ai_enabled or not should_respond:
        return None

    # Fix #6: Circuit breaker  -  skip AI if too many recent failures
    global _ai_fail_count, _ai_fail_reset_time
    if _ai_fail_count >= AI_CIRCUIT_BREAKER_THRESHOLD:
        if time.time() < _ai_fail_reset_time:
            logger.warning(json.dumps({
                'event': 'ai_circuit_breaker_open',
                'failCount': _ai_fail_count,
                'resetAt': _ai_fail_reset_time,
                'requestId': request_id
            }))
            return None
        # Cooldown expired  -  reset and retry
        _ai_fail_count = 0
    
    try:
        # Send typing indicator before AI processing
        _send_typing_indicator(
            sender_phone=sender_phone,
            phone_number_id=phone_number_id,
            request_id=request_id
        )
        
        # Skip separate KB query  -  the ai-generate-response function now handles
        # KB retrieval internally via the Converse API path
        
        # Invoke AI generate response with multimodal payload
        ai_response = _invoke_ai_generate_response_v2(
            content=content,
            message_id=message_id,
            contact_id=contact_id,
            sender_phone=sender_phone,
            message_type=message_type,
            s3_key=s3_key,
            mime_type=mime_type,
            request_id=request_id,
            phone_number_id=phone_number_id,
        )
        
        # Check if processing was locked (another message being processed)
        # Fix #6: Reset circuit breaker on success
        if ai_response and not ai_response.get('locked'):
            _ai_fail_count = 0
        if ai_response and ai_response.get('locked'):
            _send_ai_auto_reply(
                contact_id=contact_id,
                content="I'm still working on your previous message, one moment... ⏳",
                phone_number_id=phone_number_id,
                request_id=request_id
            )
            return ai_response
        
        # Check if AI flagged for human escalation (from intent classification, NOT from menu handoff)
        if ai_response and ai_response.get('escalate') and not ai_response.get('humanHandoff'):
            escalation_text = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            if escalation_text and len(escalation_text) > 5:
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=escalation_text,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )
            logger.info(json.dumps({
                'event': 'ai_escalation_triggered',
                'intent': ai_response.get('intent', 'unknown'),
                'confidence': ai_response.get('confidence', 0),
                'messageId': message_id,
                'contactId': contact_id,
                'escalationTextSent': bool(escalation_text),
                'requestId': request_id
            }))
            return ai_response
        
        # ── Bot flow handling ──
        flow_action = ai_response.get('flowAction', '') if ai_response else ''
        flow_config = ai_response.get('flowConfig', {}) if ai_response else {}

        # Welcome: send welcome text + main menu
        if ai_response and ai_response.get('sendWelcomeMenu'):
            welcome_text = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            if welcome_text:
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=welcome_text,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )
            # Send the main menu interactive list
            main_menu = flow_config.get('mainMenu') or _get_welcome_config()
            _send_interactive_list(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                list_config=main_menu,
                request_id=request_id
            )
            return ai_response

        # Language picker requested (two-step: region → languages)
        if ai_response and ai_response.get('showLanguagePicker'):
            picker_step = ai_response.get('languagePickerStep', 'region')

            if picker_step == 'languages':
                # Step 2: Show languages for the selected region
                region_id = ai_response.get('regionId', '')
                region_list = _get_region_language_list(region_id)
                if region_list:
                    _send_interactive_list(
                        contact_id=contact_id,
                        phone_number_id=phone_number_id,
                        list_config=region_list,
                        request_id=request_id
                    )
                else:
                    # Fallback: show region picker again
                    _send_interactive_list(
                        contact_id=contact_id,
                        phone_number_id=phone_number_id,
                        list_config=_get_language_picker_config(),
                        request_id=request_id
                    )
            else:
                # Step 1: Show region picker
                _send_interactive_list(
                    contact_id=contact_id,
                    phone_number_id=phone_number_id,
                    list_config=_get_language_picker_config(),
                    request_id=request_id
                )
            return ai_response

        # Send text response first (menu item response, language confirmation, etc.)
        if ai_response and (ai_response.get('suggestion') or ai_response.get('suggestedResponse')):
            suggestion = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            max_length = ai_config.get('maxResponseLength', 1000)
            if suggestion and len(suggestion) > 5:
                if len(suggestion) > max_length:
                    suggestion = suggestion[:max_length] + '...'
                
                response_delay = ai_config.get('responseDelay', 0)
                if response_delay > 0:
                    time.sleep(min(response_delay, 5))
                
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=suggestion,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )

        # Send CTA button if present
        if ai_response and ai_response.get('cta'):
            cta = ai_response['cta']
            _send_cta_button(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                cta_text=cta.get('text', 'Start Now'),
                cta_url=cta.get('url', 'https://wecare.digital/selfservice'),
                request_id=request_id
            )

        # Follow-up flow actions
        if flow_action == 'showOptions':
            _send_reply_buttons(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                button_config={
                    'body': "What\u2019s next?",
                    'footer': 'wecare.digital',
                    'buttons': [
                        {'id': 'opt_do_more', 'title': '\U0001f9ed Do more'},
                        {'id': 'opt_done', 'title': '\u270c\ufe0f Done here'},
                    ],
                },
                request_id=request_id
            )
        elif flow_action == 'showMainMenu':
            main_menu = _get_welcome_config()
            _send_interactive_list(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                list_config=main_menu,
                request_id=request_id
            )
        elif flow_action == 'showSubMenu':
            sub_menu_config = ai_response.get('subMenuConfig', {}) if ai_response else {}
            if sub_menu_config:
                _send_interactive_list(
                    contact_id=contact_id,
                    phone_number_id=phone_number_id,
                    list_config=sub_menu_config,
                    request_id=request_id
                )
        elif flow_action == 'showRating':
            _send_reply_buttons(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                button_config={
                    'body': "How was your experience? \U0001faf6",
                    'footer': 'wecare.digital',
                    'buttons': [
                        {'id': 'rate_good', 'title': '\U0001f64c Great'},
                        {'id': 'rate_ok', 'title': '\U0001f610 Just okay'},
                        {'id': 'rate_mid', 'title': '\U0001fae4 Could be better'},
                    ],
                },
                request_id=request_id
            )
        elif flow_action == 'sendPayment':
            # Send WhatsApp Pay order_details message with GST breakdown
            payment_amount = ai_response.get('paymentAmount', 0) if ai_response else 0
            if payment_amount > 0:
                _send_payment_request(
                    contact_id=contact_id,
                    phone_number_id=phone_number_id,
                    amount=payment_amount,
                    request_id=request_id,
                    item_name=ai_response.get('paymentItemName', 'Services/Goods'),
                    gst_rate=ai_response.get('paymentGstRate', 18),
                    shipping=ai_response.get('paymentShipping', 49),
                    sender_phone=sender_phone,
                    quantity=ai_response.get('paymentQuantity', 1),
                    discount=ai_response.get('paymentDiscount', 0),
                    payment_purpose=ai_response.get('paymentPurpose', ''),
                    due_ref=ai_response.get('paymentDueRef', ''),
                    order_id=ai_response.get('paymentOrderId', 'Offline'),
                    customer_name=ai_response.get('paymentCustomerName', ''),
                    customer_phone=ai_response.get('paymentCustomerPhone', sender_phone),
                    customer_email=ai_response.get('paymentCustomerEmail', ''),
                    shipping_address=ai_response.get('paymentShippingAddress', ''),
                    billing_address=ai_response.get('paymentBillingAddress', ''),
                    pay_for=ai_response.get('paymentPayFor', 'self'),
                )
        elif flow_action == 'sendPendingPayments':
            # ── Payment flow (hardcoded, LLM-independent  -  edit PAY_MSG at top of file) ──
            customer_phone = ai_response.get('paymentCustomerPhone', sender_phone) if ai_response else sender_phone

            # Handle payments on whichever phone received the message
            # (Phone 1 is disconnected, so no redirect  -  all phones handle payments directly)
            if False:  # Redirect disabled  -  Phone 1 (+919330994400) is DISCONNECTED
                _send_ai_auto_reply(contact_id, PAY_MSG['redirect'], phone_number_id, request_id)
                logger.info(json.dumps({
                    'event': 'payment_redirected_to_phone1',
                    'phone': customer_phone,
                    'fromPhoneId': phone_number_id,
                    'requestId': request_id,
                }))
            else:
                # Step 1: Send "pulling" message immediately
                _send_ai_auto_reply(contact_id, PAY_MSG['pulling'], phone_number_id, request_id)

                try:
                    inv_payload = {
                        'rawPath': '/invoices/send-pending-by-phone',
                        'requestContext': {'http': {'method': 'POST'}},
                        'body': json.dumps({
                            'customerPhone': customer_phone,
                            'phoneNumberId': phone_number_id,
                        }),
                    }
                    inv_response = lambda_client.invoke(
                        FunctionName='wecare-invoice-engine',
                        InvocationType='RequestResponse',
                        Payload=json.dumps(inv_payload),
                    )
                    inv_result = json.loads(inv_response['Payload'].read())
                    inv_body = json.loads(inv_result.get('body', '{}'))
                    sent_count = inv_body.get('sent', 0)
                    total_count = inv_body.get('total', 0)
                    invoices_sent = inv_body.get('invoices', [])
                    send_error = inv_body.get('error', '')

                    if total_count == 0:
                        _send_ai_auto_reply(contact_id, PAY_MSG['no_dues'], phone_number_id, request_id)
                    elif sent_count == 0:
                        _send_ai_auto_reply(contact_id, PAY_MSG['send_failed'], phone_number_id, request_id)
                        logger.warning(json.dumps({
                            'event': 'send_pending_payment_link_failed',
                            'sent': 0, 'total': total_count,
                            'error': send_error, 'phone': customer_phone,
                            'requestId': request_id,
                        }))

                    logger.info(json.dumps({
                        'event': 'send_pending_payments_complete',
                        'sent': sent_count, 'total': total_count,
                        'phone': customer_phone, 'requestId': request_id,
                    }))
                except Exception as e:
                    logger.error(json.dumps({
                        'event': 'send_pending_payments_error',
                        'error': str(e), 'requestId': request_id,
                    }))
                    _send_ai_auto_reply(contact_id, PAY_MSG['error'], phone_number_id, request_id)

        elif flow_action == 'humanHandoff':
            # Flag conversation for human agent in CRM
            try:
                contacts_table = dynamodb.Table(CONTACTS_TABLE)
                contacts_table.update_item(
                    Key={'id': contact_id},
                    UpdateExpression='SET humanHandoff = :h, handoffAt = :t',
                    ExpressionAttributeValues={
                        ':h': True,
                        ':t': Decimal(str(int(time.time()))),
                    }
                )
            except Exception as hh_err:
                logger.warning(json.dumps({
                    'event': 'human_handoff_flag_error',
                    'contactId': contact_id,
                    'error': str(hh_err),
                    'requestId': request_id
                }))
            logger.info(json.dumps({
                'event': 'human_handoff_requested',
                'contactId': contact_id,
                'requestId': request_id
            }))
        elif flow_action == 'end':
            # Rating submitted  -  nothing more to do, message already sent
            pass

        # ── Safety net: if AI returned but nothing was sent to user, send fallback ──
        if ai_response and not ai_response.get('locked') and not ai_response.get('showLanguagePicker'):
            suggestion_sent = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            has_flow_action = flow_action in ('showMainMenu', 'showSubMenu', 'showOptions', 'showRating', 'sendPayment', 'sendPendingPayments', 'humanHandoff', 'end')
            if not suggestion_sent and not has_flow_action and not ai_response.get('sendWelcomeMenu'):
                fallback_msg = "Hi! 👋 I'm here to help. Type *menu* to see options, or just ask me anything. 😊"
                logger.warning(json.dumps({
                    'event': 'ai_blank_response_fallback',
                    'contactId': contact_id,
                    'messageId': message_id,
                    'aiResponseKeys': list(ai_response.keys()) if ai_response else [],
                    'requestId': request_id
                }))
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=fallback_msg,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )

        # ── Audio response: if user has audioEnabled, send TTS version ──
        if ai_response and not ai_response.get('locked') and not ai_response.get('escalate'):
            suggestion_text = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            if suggestion_text and len(suggestion_text) > 10:
                try:
                    # Load user preferences to check audioEnabled
                    # Fix #2: Use same hash as AI handler  -  sha256(clean_phone)[:32]
                    from hashlib import sha256
                    clean_phone = sender_phone.replace('+', '').replace(' ', '').replace('-', '') if sender_phone else ''
                    ph = sha256(clean_phone.encode()).hexdigest()[:32] if clean_phone else ''
                    if ph:
                        conv_table = dynamodb.Table(os.environ.get('CONVERSATION_HISTORY_TABLE', 'stack-wecare-digital-ConversationHistoryTable'))
                        pref_resp = conv_table.get_item(Key={'phoneHash': ph})
                        pref_item = pref_resp.get('Item', {})
                        audio_enabled = pref_item.get('audioEnabled', False)
                        user_lang = pref_item.get('preferredLanguage', 'English')
                        if audio_enabled:
                            _send_audio_response(
                                contact_id=contact_id,
                                phone_number_id=phone_number_id,
                                text=suggestion_text,
                                language=user_lang,
                                request_id=request_id,
                                sender_phone=sender_phone,
                                sender_bsuid=sender_bsuid,
                            )
                except Exception as audio_err:
                    logger.warning(json.dumps({
                        'event': 'audio_check_error',
                        'contactId': contact_id,
                        'error': str(audio_err),
                        'requestId': request_id
                    }))
        
        return ai_response
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_automation_error',
            'messageId': message_id,
            'messageType': message_type,
            'error': str(e),
            'requestId': request_id
        }))
        # Fix #5: Send fallback message so customer doesn't get silence
        # Fix #6: Increment circuit breaker
        _ai_fail_count += 1
        _ai_fail_reset_time = time.time() + AI_CIRCUIT_BREAKER_COOLDOWN
        try:
            _send_ai_auto_reply(
                contact_id=contact_id,
                content="Thanks for your message! 🙏 We're experiencing a brief delay. Please try again in a moment, or call us at +91 9330994400.",
                phone_number_id=phone_number_id,
                request_id=request_id
            )
        except Exception as e:
            logger.warning(f'AI fallback auto-reply send failed: {e}')
        return None


def _invoke_ai_query_kb(query: str, message_id: str, request_id: str) -> Optional[Dict]:
    """Invoke ai-query-kb Lambda function."""
    try:
        logger.info(json.dumps({
            'event': 'invoking_ai_query_kb',
            'functionName': AI_QUERY_KB_FUNCTION,
            'messageId': message_id,
            'requestId': request_id
        }))
        response = lambda_client.invoke(
            FunctionName=AI_QUERY_KB_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({'query': query, 'messageId': message_id, 'requestId': request_id})
        )
        status_code = response.get('StatusCode')
        logger.info(json.dumps({
            'event': 'ai_query_kb_response',
            'statusCode': status_code,
            'messageId': message_id,
            'requestId': request_id
        }))
        if status_code == 200:
            payload = response['Payload'].read().decode('utf-8')
            return json.loads(json.loads(payload).get('body', '{}'))
        return None
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_query_kb_error',
            'error': str(e),
            'messageId': message_id,
            'requestId': request_id
        }))
        return None


def _invoke_ai_generate_response(content: str, kb_context: Optional[Dict], 
                                  message_id: str, contact_id: str, request_id: str) -> Optional[Dict]:
    """Invoke ai-generate-response Lambda function (legacy, used for internal)."""
    try:
        response = lambda_client.invoke(
            FunctionName=AI_GENERATE_RESPONSE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'messageContent': content,
                'kbContext': kb_context,
                'messageId': message_id,
                'contactId': contact_id,
                'requestId': request_id
            })
        )
        if response.get('StatusCode') == 200:
            body = json.loads(json.loads(response['Payload'].read().decode('utf-8')).get('body', '{}'))
            _store_ai_interaction(message_id, content, body.get('suggestion', '') or body.get('suggestedResponse', ''), request_id)
            return body
        return None
    except Exception:
        return None


def _invoke_ai_generate_response_v2(
    content: str, message_id: str, contact_id: str, sender_phone: str,
    message_type: str, s3_key: str, mime_type: str, request_id: str,
    phone_number_id: str = '',
) -> Optional[Dict]:
    """
    Invoke ai-generate-response Lambda with multimodal payload.
    Passes sender phone, message type, S3 key, and mime type for
    the Converse API path to handle images, audio, video, documents.
    Passes phoneNumberId so AI sessions are separated per WABA.
    """
    try:
        payload = {
            'messageContent': content,
            'messageId': message_id,
            'contactId': contact_id,
            'senderPhone': sender_phone,
            'context': 'external',
            'messageType': message_type,
            's3Key': s3_key,
            'mediaType': message_type if message_type in ('image', 'audio', 'video', 'document') else '',
            'mimeType': mime_type,
            'requestId': request_id,
            'phoneNumberId': phone_number_id,
        }

        logger.info(json.dumps({
            'event': 'ai_generate_v2_invoke',
            'messageType': message_type,
            'hasMedia': bool(s3_key),
            'messageId': message_id,
            'requestId': request_id
        }))

        # Use a shorter boto3 read timeout for AI invocation to prevent
        # this Lambda from timing out waiting for the AI Lambda.
        # Default boto3 read_timeout is 60s; we cap at 45s here.
        import botocore.config
        _ai_lambda_config = botocore.config.Config(read_timeout=45, retries={'max_attempts': 0})
        _ai_lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'), config=_ai_lambda_config)
        
        response = _ai_lambda_client.invoke(
            FunctionName=AI_GENERATE_RESPONSE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        if response.get('StatusCode') == 200:
            raw = response['Payload'].read().decode('utf-8')
            parsed = json.loads(raw)
            body = json.loads(parsed.get('body', '{}'))

            # Store AI interaction for audit
            suggestion = body.get('suggestion', '') or body.get('suggestedResponse', '')
            if suggestion and not body.get('locked'):
                _store_ai_interaction(message_id, content or f'[{message_type}]', suggestion, request_id)

            return body
        return None
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_generate_v2_error',
            'error': str(e),
            'messageId': message_id,
            'requestId': request_id
        }))
        return None


def _send_typing_indicator(sender_phone: str, phone_number_id: str, request_id: str) -> None:
    """
    Send WhatsApp typing indicator so the customer sees engagement while AI processes.
    
    Meta Graph API does not expose a native typing indicator endpoint.
    We send a read receipt (blue ticks) as the closest proxy  -  this signals
    to the customer that their message was seen and a response is coming.
    """
    if not sender_phone or not phone_number_id:
        return

    # Use Direct API read receipt as typing proxy
    if _is_direct_api_phone(phone_number_id):
        try:
            # For Direct API phones, we already sent read receipt in the auto-reaction block.
            # Send another read receipt as typing proxy if we have a message ID.
            logger.info(json.dumps({
                'event': 'typing_indicator_direct_api',
                'senderPhone': sender_phone,
                'phoneNumberId': phone_number_id,
                'note': 'Using read receipt as typing proxy for Direct API phone',
                'requestId': request_id
            }))
        except Exception as e:
            logger.warning(f"Direct API typing indicator failed: {e}")
        return

    try:
        # Clean phone number  -  ensure + prefix for WhatsApp recipient
        clean_phone = sender_phone.lstrip('+')
        formatted_phone = f'+{clean_phone}'

        # Send read receipt as typing proxy
        read_payload = {
            'messaging_product': 'whatsapp',
            'status': 'read',
            'recipient_type': 'individual',
            'to': formatted_phone,
        }

        if _is_direct_api_phone(phone_number_id):
            meta_pid = _get_meta_phone_id_for_direct_api(phone_number_id)
            _send_direct_api_read_receipt(whatsapp_message_id if 'whatsapp_message_id' in dir() else '', meta_phone_id=meta_pid)
        else:
            # Fallback: try Direct API with default phone
            _send_direct_api_read_receipt('', meta_phone_id=_current_direct_api_phone or PHONE1_META_ID)

        logger.info(json.dumps({
            'event': 'typing_indicator_sent',
            'senderPhone': sender_phone,
            'phoneNumberId': phone_number_id,
            'note': 'Sent read receipt as typing proxy',
            'requestId': request_id
        }))

    except Exception as e:
        # Non-critical  -  don't fail the AI flow for typing indicator
        logger.warning(json.dumps({
            'event': 'typing_indicator_error',
            'error': str(e),
            'requestId': request_id
        }))


def _store_ai_interaction(message_id: str, query: str, response: str, request_id: str) -> None:
    """Store AI interaction record."""
    try:
        ai_table = dynamodb.Table(AI_INTERACTIONS_TABLE)
        ai_table.put_item(Item={
            'id': str(uuid.uuid4()),
            'interactionId': str(uuid.uuid4()),
            'messageId': message_id,
            'query': query,
            'response': response,
            'approved': False,
            'timestamp': Decimal(str(int(time.time()))),
        })
    except Exception as e:
        logger.error(f"Failed to store AI interaction: {str(e)}")


# ============================================================================
# WHATSAPP BUSINESS ACCOUNT WEBHOOKS
# Template Status, Phone Quality, Messaging Limits
# ============================================================================

def _process_template_status(value: Dict, request_id: str) -> None:
    """
    Process template status update webhook.
    
    Webhook format:
    {
        "event": "APPROVED" | "REJECTED" | "PENDING" | "PAUSED" | "DISABLED" | "FLAGGED",
        "message_template_id": 123456789,
        "message_template_name": "template_name",
        "message_template_language": "en_US",
        "reason": "NONE" | "ABUSIVE_CONTENT" | "INVALID_FORMAT" | ...
    }
    
    Events:
    - APPROVED: Template approved and ready to use
    - REJECTED: Template rejected (check reason)
    - PENDING: Template submitted for review
    - PAUSED: Template paused due to quality issues
    - DISABLED: Template disabled
    - FLAGGED: Template flagged for review
    """
    event = value.get('event', '')
    template_id = value.get('message_template_id', '')
    template_name = value.get('message_template_name', '')
    template_language = value.get('message_template_language', '')
    reason = value.get('reason', 'NONE')
    
    logger.info(json.dumps({
        'event': 'template_status_update',
        'templateEvent': event,
        'templateId': template_id,
        'templateName': template_name,
        'templateLanguage': template_language,
        'reason': reason,
        'requestId': request_id
    }))
    
    # Store template status in SystemConfig table for dashboard display
    _store_system_event(
        event_type='template_status',
        event_data={
            'event': event,
            'templateId': str(template_id),
            'templateName': template_name,
            'templateLanguage': template_language,
            'reason': reason
        },
        request_id=request_id
    )
    
    # Log warning for rejected/paused templates
    if event in ['REJECTED', 'PAUSED', 'DISABLED', 'FLAGGED']:
        logger.warning(json.dumps({
            'event': 'template_status_alert',
            'templateEvent': event,
            'templateName': template_name,
            'reason': reason,
            'action': 'Review template in Meta Business Manager',
            'requestId': request_id
        }))


def _process_phone_quality_update(value: Dict, request_id: str) -> None:
    """
    Process phone number quality update webhook.
    
    Webhook format:
    {
        "display_phone_number": "+1234567890",
        "current_limit": "TIER_1K" | "TIER_10K" | "TIER_100K" | "TIER_UNLIMITED",
        "event": "FLAGGED" | "UNFLAGGED",
        "quality_score": "GREEN" | "YELLOW" | "RED"
    }
    
    Quality scores:
    - GREEN: High quality, no issues
    - YELLOW: Medium quality, some issues
    - RED: Low quality, at risk of being blocked
    
    Events:
    - FLAGGED: Phone number flagged due to quality issues
    - UNFLAGGED: Phone number quality restored
    """
    display_phone = value.get('display_phone_number', '')
    current_limit = value.get('current_limit', '')
    event = value.get('event', '')
    quality_score = value.get('quality_score', '')
    
    logger.info(json.dumps({
        'event': 'phone_quality_update',
        'displayPhone': display_phone,
        'currentLimit': current_limit,
        'qualityEvent': event,
        'qualityScore': quality_score,
        'requestId': request_id
    }))
    
    # Store phone quality in SystemConfig table
    _store_system_event(
        event_type='phone_quality',
        event_data={
            'displayPhone': display_phone,
            'currentLimit': current_limit,
            'event': event,
            'qualityScore': quality_score
        },
        request_id=request_id
    )
    
    # Log warning for quality issues
    if quality_score in ['YELLOW', 'RED'] or event == 'FLAGGED':
        logger.warning(json.dumps({
            'event': 'phone_quality_alert',
            'displayPhone': display_phone,
            'qualityScore': quality_score,
            'qualityEvent': event,
            'action': 'Review message quality and reduce spam complaints',
            'requestId': request_id
        }))


def _process_account_update(value: Dict, request_id: str) -> None:
    """
    Process account update webhook (messaging limits, restrictions, etc.).
    
    Webhook format for messaging limit changes:
    {
        "phone_number": "+1234567890",
        "event": "PHONE_NUMBER_MESSAGING_LIMIT_CHANGED",
        "current_limit": "TIER_1K" | "TIER_10K" | "TIER_100K" | "TIER_UNLIMITED"
    }
    
    Webhook format for account restrictions:
    {
        "event": "ACCOUNT_RESTRICTION",
        "restriction_type": "RESTRICTED_ADD_PHONE_NUMBER_ACTION" | ...
    }
    
    Messaging limit tiers:
    - TIER_1K: 1,000 business-initiated conversations per 24 hours
    - TIER_10K: 10,000 business-initiated conversations per 24 hours
    - TIER_100K: 100,000 business-initiated conversations per 24 hours
    - TIER_UNLIMITED: Unlimited business-initiated conversations
    """
    event = value.get('event', '')
    phone_number = value.get('phone_number', '')
    current_limit = value.get('current_limit', '')
    restriction_type = value.get('restriction_type', '')
    ban_info = value.get('ban_info', {})
    
    logger.info(json.dumps({
        'event': 'account_update',
        'accountEvent': event,
        'phoneNumber': phone_number,
        'currentLimit': current_limit,
        'restrictionType': restriction_type,
        'banInfo': ban_info,
        'requestId': request_id
    }))
    
    # Store account update in SystemConfig table
    _store_system_event(
        event_type='account_update',
        event_data={
            'event': event,
            'phoneNumber': phone_number,
            'currentLimit': current_limit,
            'restrictionType': restriction_type,
            'banInfo': ban_info
        },
        request_id=request_id
    )
    
    # Log messaging limit changes
    if event == 'PHONE_NUMBER_MESSAGING_LIMIT_CHANGED':
        logger.info(json.dumps({
            'event': 'messaging_limit_changed',
            'phoneNumber': phone_number,
            'newLimit': current_limit,
            'requestId': request_id
        }))
    
    # Log warnings for restrictions
    if event == 'ACCOUNT_RESTRICTION' or restriction_type:
        logger.warning(json.dumps({
            'event': 'account_restriction_alert',
            'restrictionType': restriction_type,
            'action': 'Review account in Meta Business Manager',
            'requestId': request_id
        }))
    
    # Log ban info if present
    if ban_info:
        logger.error(json.dumps({
            'event': 'account_ban_alert',
            'banInfo': ban_info,
            'action': 'Contact Meta support immediately',
            'requestId': request_id
        }))


def _store_system_event(event_type: str, event_data: Dict, request_id: str) -> None:
    """
    Store system event in SystemConfig table for dashboard display.
    Uses a composite key: whatsapp_events_{event_type}
    Stores last 10 events of each type.
    
    Note: SystemConfigTable PK is 'id', we use id=configKey for compatibility.
    """
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        config_key = f'whatsapp_events_{event_type}'
        now = int(time.time())
        
        # Get existing events (PK is 'id')
        try:
            response = config_table.get_item(Key={'id': config_key})
            existing = response.get('Item', {})
            events_list = json.loads(existing.get('configValue', '[]'))
        except Exception:
            events_list = []
        
        # Add new event with timestamp
        new_event = {
            'timestamp': now,
            'data': event_data
        }
        events_list.insert(0, new_event)
        
        # Keep only last 10 events
        events_list = events_list[:10]
        
        # Store updated events (PK is 'id')
        config_table.put_item(Item={
            'id': config_key,
            'configKey': config_key,
            'configValue': json.dumps(events_list),
            'updatedAt': Decimal(str(now))
        })
        
        logger.info(json.dumps({
            'event': 'system_event_stored',
            'eventType': event_type,
            'configKey': config_key,
            'eventsCount': len(events_list),
            'requestId': request_id
        }))
        
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        # SystemConfig table doesn't exist - skip silently
        logger.warning(json.dumps({
            'event': 'system_event_store_skipped',
            'eventType': event_type,
            'reason': 'SystemConfig table not found',
            'requestId': request_id
        }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'system_event_store_error',
            'eventType': event_type,
            'error': str(e),
            'requestId': request_id
        }))


def _process_group_event(value: Dict, event_subtype: str, request_id: str) -> None:
    """
    Process group webhook events and update WhatsAppGroup table.
    Handles: group_participant_change, group_membership_approval_request.
    Per Meta Groups API docs.
    """
    try:
        GROUP_TABLE = os.environ.get('GROUP_TABLE', 'stack-wecare-digital-WhatsAppGroupTable')
        group_table = dynamodb.Table(GROUP_TABLE)
        now = int(time.time())

        # Extract group info from webhook value
        groups = value.get('groups', [value]) if isinstance(value.get('groups'), list) else [value]
        for group_data in groups:
            group_id = group_data.get('group_id', group_data.get('id', ''))
            if not group_id:
                continue

            subject = group_data.get('subject', '')
            participants = group_data.get('participants', [])
            action = group_data.get('action', event_subtype)

            # Upsert group record
            update_expr = 'SET updatedAt = :now'
            expr_vals: Dict[str, Any] = {':now': Decimal(str(now))}

            if subject:
                update_expr += ', subject = :subj'
                expr_vals[':subj'] = subject
            if participants:
                update_expr += ', lastParticipantEvent = :pe'
                expr_vals[':pe'] = json.dumps({
                    'action': action,
                    'participants': participants[:20],  # Limit stored participants
                    'timestamp': now,
                })

            try:
                group_table.update_item(
                    Key={'id': group_id},
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_vals,
                )
            except Exception:
                # Table may not exist yet  -  create item instead
                group_table.put_item(Item={
                    'id': group_id,
                    'groupId': group_id,
                    'subject': subject,
                    'lastParticipantEvent': json.dumps({
                        'action': action,
                        'participants': participants[:20],
                        'timestamp': now,
                    }),
                    'createdAt': Decimal(str(now)),
                    'updatedAt': Decimal(str(now)),
                })

            logger.info(json.dumps({
                'event': 'group_event_processed',
                'groupId': group_id,
                'action': action,
                'participantCount': len(participants),
                'requestId': request_id,
            }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'group_event_processing_error',
            'error': str(e),
            'requestId': request_id,
        }))
