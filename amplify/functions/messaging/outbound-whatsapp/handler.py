"""
Outbound WhatsApp Lambda Function

Purpose: Send WhatsApp text/media messages
Requirements: 3.1, 3.2, 5.2-5.11, 14.4, 16.2-16.6

Validates opt-in and allowlist, checks customer service window,
calls Meta Graph API (Direct API) for all phones.
Emits CloudWatch metrics for delivery success/failure.
"""

import os
import json
import uuid
import time
import logging
import boto3
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal

# Configure logging
from lambda_utils.logging import get_logger
from lambda_utils.response import cors_headers, extract_origin
from lambda_utils.privacy import mask_phone, redact_pii
from lambda_utils.middleware import require_auth
from lambda_utils.message_store import put_message  # unified MessagesTable dual-write

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
cloudwatch = boto3.client('cloudwatch', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'stack-wecare-digital-WhatsAppOutboundTable')
MEDIA_FILES_TABLE = os.environ.get('MEDIA_FILES_TABLE', 'stack-wecare-digital-MediaFilesTable')
RATE_LIMIT_TABLE = os.environ.get('RATE_LIMIT_TABLE', 'stack-wecare-digital-RateLimitTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
MEDIA_PREFIX = os.environ.get('MEDIA_OUTBOUND_PREFIX', 'stack/whatsapp-media/outgoing/')
# Public, reusable template-attachment folder (same bucket). Files here are served
# via CloudFront so WhatsApp can fetch them by URL and the same attachment can be
# re-sent across many template messages without re-uploading to Meta each time.
PUBLIC_MEDIA_PREFIX = os.environ.get('PUBLIC_MEDIA_PREFIX', 'public/wa-tpl/')
CDN_DOMAIN = os.environ.get('CDN_DOMAIN', 'app.wecare.digital')

# WhatsApp Phone Number IDs (Allowlist) - Requirement 3.2
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-waba1-direct-1016149501586345')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-waba-t-direct-1055232054343117')
ALLOWLIST = {PHONE_NUMBER_ID_1, PHONE_NUMBER_ID_2}

# All phones use Direct Meta Graph API
DIRECT_API_PHONE_IDS = {PHONE_NUMBER_ID_1, PHONE_NUMBER_ID_2}
# Meta phone ID for Direct API sending
DIRECT_API_META_PHONE_MAP = {
    'phone-number-id-waba1-direct-1016149501586345': '1016149501586345',  # +91 93309 94400 (WABA1)
    'phone-number-id-waba-t-direct-1055232054343117': '1055232054343117',  # +91 99033 00044 (WABA-T)
}

# Secrets Manager for Direct API tokens
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
_direct_api_cache = {}

def _is_direct_api_phone(phone_number_id: str) -> bool:
    """Check if phone uses Direct API. All phones are now Direct API."""
    return phone_number_id in DIRECT_API_PHONE_IDS

def _send_direct_api(phone_number_id: str, message_json: str) -> Dict:
    """Send message via Meta Graph API for Direct API phones."""
    import hmac as _hmac, hashlib as _hashlib
    if 'token' not in _direct_api_cache:
        resp = secrets_client.get_secret_value(SecretId='wecare/meta-system-user-token')
        data = json.loads(resp['SecretString'])
        _direct_api_cache['token'] = (data.get('access_token') or '').strip()
        _direct_api_cache['app_secret'] = (data.get('app_secret') or '').strip()
    
    token = _direct_api_cache['token']
    app_secret = _direct_api_cache['app_secret']
    meta_phone_id = DIRECT_API_META_PHONE_MAP.get(phone_number_id, '')
    
    # Fallback: extract Meta phone ID from Direct API format phone-number-id-waba1-direct-{meta_id}
    if not meta_phone_id and '-direct-' in phone_number_id:
        meta_phone_id = phone_number_id.split('-direct-')[-1]
    # Last resort: default to WABA-T phone (the working one)
    if not meta_phone_id:
        meta_phone_id = '1055232054343117'
        logger.warning(f"No Meta phone ID mapping for {phone_number_id}, defaulting to {meta_phone_id}")
    
    url = f"https://graph.facebook.com/{META_API_VERSION}/{meta_phone_id}/messages"
    if app_secret:
        proof = _hmac.new(app_secret.encode(), token.encode(), _hashlib.sha256).hexdigest()
        url = f"{url}?appsecret_proof={proof}"
    
    import urllib.request, urllib.error
    req = urllib.request.Request(url, data=message_json.encode() if isinstance(message_json, str) else message_json, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read().decode())
        msg_id = result.get('messages', [{}])[0].get('id', '')
        return {'messageId': msg_id}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Direct API send failed {e.code} for phone {meta_phone_id}: {error_body[:500]}")
        raise


def _send_message(phone_number_id: str, payload, as_bytes=False) -> Dict:
    """Universal send — all phones use Direct Meta API."""
    msg = json.dumps(payload) if not isinstance(payload, str) else payload
    return _send_direct_api(phone_number_id, msg)

def _resolve_meta_phone_id(phone_number_id: str) -> str:
    """Resolve our phone id to the Meta phone-number id used in Graph URLs."""
    meta_phone_id = DIRECT_API_META_PHONE_MAP.get(phone_number_id, '')
    if not meta_phone_id and '-direct-' in phone_number_id:
        meta_phone_id = phone_number_id.split('-direct-')[-1]
    if not meta_phone_id:
        meta_phone_id = '1055232054343117'
    return meta_phone_id

def _block_users_api(phone_number_id: str, users: list, action: str) -> Dict:
    """Block / unblock / list blocked users via the Meta block_users endpoint.

    action: 'block' (POST), 'unblock' (DELETE), 'list' (GET).
    Note (Meta): you can only block a user who messaged the business in the last 24h.
    """
    import hmac as _hmac, hashlib as _hashlib
    import urllib.request, urllib.error
    if 'token' not in _direct_api_cache:
        resp = secrets_client.get_secret_value(SecretId='wecare/meta-system-user-token')
        data = json.loads(resp['SecretString'])
        _direct_api_cache['token'] = (data.get('access_token') or '').strip()
        _direct_api_cache['app_secret'] = (data.get('app_secret') or '').strip()
    token = _direct_api_cache['token']
    app_secret = _direct_api_cache['app_secret']
    meta_phone_id = _resolve_meta_phone_id(phone_number_id)
    url = f"https://graph.facebook.com/{META_API_VERSION}/{meta_phone_id}/block_users"
    if app_secret:
        proof = _hmac.new(app_secret.encode(), token.encode(), _hashlib.sha256).hexdigest()
        url = f"{url}?appsecret_proof={proof}"
    method = 'GET' if action == 'list' else ('DELETE' if action == 'unblock' else 'POST')
    body = None
    if action in ('block', 'unblock'):
        body = json.dumps({
            'messaging_product': 'whatsapp',
            'block_users': [{'user': _normalize_phone_number(u)} for u in users if u],
        }).encode()
    req = urllib.request.Request(url, data=body, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"block_users {action} failed {e.code}: {error_body[:500]}")
        raise Exception(f"HTTP {e.code}: {error_body[:300]}")

# Constants
META_API_VERSION = 'v25.0'  # Latest WhatsApp Cloud API with full payment support
MAX_TEXT_LENGTH = 4096  # Requirement 5.4
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
CUSTOMER_SERVICE_WINDOW_HOURS = 24  # Requirement 16.2
RATE_LIMIT_PER_SECOND = 80  # Requirement 5.9

# WhatsApp Payment Configurations
# +919330994400 (WECARE.DIGITAL) WABA: 2094615664435155 — Active, Direct API
# +919903300044 (Manish Agarwal) WABA: 2513394156072604 — active, Direct API
# Both use same Razorpay MID (from env RAZORPAY_MID) | MCC: 4722 | Purpose: 03
# Config names MUST match exactly what's in Meta Business Manager
VALID_PAYMENT_CONFIGS = {
    'WECARE-RAZOR-PAY', 'WECARE-RAZOR-UPI', 'WECARE-PAYU',
    'WECARE-RAZORPAY-UPIVPA', 'WECARE-RAZOR-UPIVPA', 'Payu-UPIVPA',
    'Razorpay_ManishAgarwal', 'Razorpay_UPI', 'PayU_ManishAgarwal', 'PayU_UPI',
}
DEFAULT_PAYMENT_CONFIG = 'Razorpay_ManishAgarwal'
# Map phone number ID to its default payment config name
PHONE_PAYMENT_CONFIG = {
    PHONE_NUMBER_ID_1: 'WECARE-RAZOR-PAY',              # +919330994400
    PHONE_NUMBER_ID_2: 'Razorpay_ManishAgarwal',         # +919903300044
}

# Per-phone payment gateway configs (Razorpay + PayU)
# Each phone's WABA has different config names registered on Meta
PHONE_PAYMENT_GATEWAYS = {
    PHONE_NUMBER_ID_1: {                                  # +919330994400
        'razorpay': 'WECARE-RAZOR-PAY',
        'payu': 'WECARE-PAYU',
    },
    PHONE_NUMBER_ID_2: {                                  # +919903300044
        'razorpay': 'Razorpay_ManishAgarwal',
        'payu': 'PayU_ManishAgarwal',
    },
}


def _build_payment_settings(phone_number_id: str, order_details: dict) -> list:
    """Build payment_settings array per Meta's latest PG deep integration spec (v25.0).

    Supports 3 modes:
    1. PG Deep Integration (default) — razorpay/payu with configuration_name
    2. Enhanced Payment Links — payment_link with PG-generated URL
    3. UPI Intent — upi_intent_link with raw UPI deep link

    Also supports TPV (Third Party Validation) for Razorpay/PayU.
    Meta allows ONE payment_setting per review_and_pay message."""
    explicit_config = order_details.get('payment_configuration', '')
    ref_id = order_details.get('reference_id', '')

    # ── Mode 1: Enhanced Payment Links (Gap 9) ──
    payment_link_uri = order_details.get('payment_link_uri', '')
    if payment_link_uri:
        link_obj = {'uri': payment_link_uri}
        success_url = order_details.get('payment_link_success_url', '')
        cancel_url = order_details.get('payment_link_cancel_url', '')
        if success_url:
            link_obj['success_url'] = success_url
        if cancel_url:
            link_obj['cancel_url'] = cancel_url
        return [{'type': 'payment_link', 'payment_link': link_obj}]

    # ── Mode 2: UPI Intent Link ──
    upi_intent = order_details.get('upi_intent_link', '')
    if upi_intent:
        return [{'type': 'upi_intent_link', 'upi_intent_link': {'link': upi_intent}}]

    # ── Mode 3: PG Deep Integration (default) ──
    # Determine which gateway and config name to use
    # CRITICAL: Never cross-WABA — each phone's configs only work on its own WABA
    if explicit_config and explicit_config in VALID_PAYMENT_CONFIGS:
        gw_type = 'payu' if 'PAYU' in explicit_config.upper() else 'razorpay'
        config_name = explicit_config
    else:
        gw_type = 'razorpay'
        # Use THIS phone's gateway map — never fall back to a different phone's configs
        gateways = PHONE_PAYMENT_GATEWAYS.get(phone_number_id)
        if not gateways:
            # Unknown phone ID — try to infer from the ID string
            if '1016149501586345' in str(phone_number_id):
                gateways = PHONE_PAYMENT_GATEWAYS.get(PHONE_NUMBER_ID_1)
            else:
                gateways = PHONE_PAYMENT_GATEWAYS.get(PHONE_NUMBER_ID_2)
        config_name = gateways.get('razorpay', DEFAULT_PAYMENT_CONFIG) if gateways else DEFAULT_PAYMENT_CONFIG

    pg_obj = {
        'type': gw_type,
        'configuration_name': config_name,
    }

    # Cross-WABA validation: ensure config belongs to the sending phone's WABA
    # WABA 1 configs: WECARE-RAZOR-PAY, WECARE-PAYU, WECARE-RAZORPAY-UPIVPA, Payu-UPIVPA, etc.
    # WABA 2 configs: Razorpay_ManishAgarwal, PayU_ManishAgarwal, Razorpay_UPI, PayU_UPI
    is_phone1 = '1016149501586345' in str(phone_number_id)
    is_waba1_config = 'WECARE-' in config_name.upper() or 'UPIVPA' in config_name.upper()
    is_waba2_config = 'ManishAgarwal' in config_name or config_name in ('Razorpay_UPI', 'PayU_UPI')

    if is_phone1 and is_waba2_config:
        # Wrong config for this phone — override to Phone 1's config
        logger.warning(json.dumps({
            'event': 'cross_waba_config_corrected',
            'phone': 'phone1', 'wrongConfig': config_name,
            'correctedTo': 'WECARE-RAZOR-PAY' if gw_type == 'razorpay' else 'WECARE-PAYU',
        }))
        config_name = 'WECARE-RAZOR-PAY' if gw_type == 'razorpay' else 'WECARE-PAYU'
        pg_obj['configuration_name'] = config_name
    elif not is_phone1 and is_waba1_config:
        # Wrong config for this phone — override to Phone 2's config
        logger.warning(json.dumps({
            'event': 'cross_waba_config_corrected',
            'phone': 'phone2', 'wrongConfig': config_name,
            'correctedTo': 'Razorpay_ManishAgarwal' if gw_type == 'razorpay' else 'PayU_ManishAgarwal',
        }))
        config_name = 'Razorpay_ManishAgarwal' if gw_type == 'razorpay' else 'PayU_ManishAgarwal'
        pg_obj['configuration_name'] = config_name

    # Add PG-specific fields per Meta docs
    if gw_type == 'razorpay':
        pg_obj['razorpay'] = {
            'receipt': ref_id[:40] if ref_id else '',
            'notes': {
                'referenceId': ref_id,
                'source': 'wecare_invoice_engine',
            },
        }
        # TPV support for Razorpay (Gap 11) — encrypted bank account validation
        encrypted_tpv = order_details.get('encrypted_payment_gateway_data', '')
        if encrypted_tpv:
            pg_obj['razorpay']['encrypted_payment_gateway_data'] = encrypted_tpv
    elif gw_type == 'payu':
        pg_obj['payu'] = {
            'udf1': ref_id,
            'udf2': order_details.get('orderId', 'Offline'),
            'udf3': order_details.get('gstin', '19AADFW7431N1ZK'),
            'udf4': 'wecare_invoice_engine',
        }
        # TPV support for PayU (Gap 11) — encrypted beneficiary validation
        encrypted_tpv = order_details.get('encrypted_payment_gateway_data', '')
        if encrypted_tpv:
            pg_obj['payu']['encrypted_payment_gateway_data'] = encrypted_tpv

    return [{'type': 'payment_gateway', 'payment_gateway': pg_obj}]
METRICS_NAMESPACE = 'WECARE.DIGITAL'

# Meta WhatsApp Cloud API error codes (from official error reference docs)
# Used for actionable error handling, retry logic, and frontend display
META_MESSAGE_ERRORS = {
    # Rate limiting
    130429: {'msg': 'Rate limit hit', 'action': 'Implement exponential backoff', 'retry': True},
    131045: {'msg': 'Message rate limit hit', 'action': 'Slow down message sending', 'retry': True},
    131056: {'msg': 'Pair rate limit hit (1 msg/6s per user)', 'action': 'Wait 4^X seconds before retry', 'retry': True},
    # Messaging window
    131047: {'msg': 'Re-engagement message outside 24h window', 'action': 'Send template message instead', 'retry': False},
    131051: {'msg': 'Unsupported message type', 'action': 'Check message type compatibility', 'retry': False},
    # Template errors
    132000: {'msg': 'Template param count mismatch', 'action': 'Verify template parameter count', 'retry': False},
    132001: {'msg': 'Template does not exist', 'action': 'Check template name and language', 'retry': False},
    132005: {'msg': 'Template hydrated text too long', 'action': 'Shorten parameter values', 'retry': False},
    132007: {'msg': 'Template format mismatch', 'action': 'Check component types match template', 'retry': False},
    132012: {'msg': 'Template paused', 'action': 'Template quality too low — fix or use another', 'retry': False},
    132015: {'msg': 'Template disabled', 'action': 'Template was disabled — create new one', 'retry': False},
    # Media errors
    131052: {'msg': 'Media download error', 'action': 'Check media URL accessibility', 'retry': True},
    131053: {'msg': 'Media upload error', 'action': 'Retry media upload', 'retry': True},
    # Account errors
    131031: {'msg': 'Account locked', 'action': 'Contact Meta support', 'retry': False},
    131048: {'msg': 'Spam rate limit', 'action': 'Improve message quality', 'retry': False},
    131049: {'msg': 'Message not sent — user not on WhatsApp', 'action': 'Verify recipient number', 'retry': False},
    # Generic
    100: {'msg': 'Invalid parameter', 'action': 'Check request payload', 'retry': False},
    131009: {'msg': 'Parameter missing or invalid', 'action': 'Check required fields', 'retry': False},
    131026: {'msg': 'Message undeliverable', 'action': 'Recipient may have blocked you', 'retry': False},
    131042: {'msg': 'Business eligibility payment issue', 'action': 'Check payment method on WABA', 'retry': False},
    # Additional codes from official Meta error reference (2025-2026)
    130472: {'msg': 'User part of experiment', 'action': 'User number is in a Meta experiment — retry later', 'retry': True},
    131000: {'msg': 'Something went wrong', 'action': 'Retry; if persists, open Direct Support ticket', 'retry': True},
    131008: {'msg': 'Required parameter missing', 'action': 'Check endpoint reference for required params', 'retry': False},
    131016: {'msg': 'Service unavailable', 'action': 'Service temporarily unavailable — retry', 'retry': True},
    131021: {'msg': 'Recipient cannot be sender', 'action': 'Cannot send message to yourself', 'retry': False},
    131037: {'msg': 'Display name approval needed', 'action': 'Approve display name before sending', 'retry': False},
    131050: {'msg': 'User stopped marketing messages', 'action': 'Do not retry — user opted out of marketing', 'retry': False},
}

# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Send WhatsApp message or reaction.
    Requirements: 3.1, 3.2, 5.2-5.11, 16.2-16.6
    Supports: text, media, template, and reaction messages
    """
    global origin
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)

    logger.info(json.dumps({
        'event': 'outbound_whatsapp_start',
        'sendMode': SEND_MODE,
        'requestId': request_id
    }))

    # Enforce auth for HTTP-invoked requests. Lambda-to-Lambda invokes (inbound
    # handler auto-replies, CDR/IVR notifications, scheduled sends) carry no HTTP
    # context and are auto-exempt by require_auth, so internal callers keep working.
    auth_result = require_auth(event)
    if auth_result is not None:
        return auth_result

    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))

        # ── Presigned media upload (Issue 2 fix): large media must NOT be sent as base64
        # through API Gateway/Lambda (10MB GW / 6MB Lambda limits). Frontend requests a
        # presigned PUT URL, uploads the file directly to S3, then sends the S3 key. ──
        if body.get('action') == 'getUploadUrl':
            return _get_media_upload_url(body, request_id)

        contact_id = body.get('contactId')
        content = body.get('content', '')
        phone_number_id = body.get('phoneNumberId', PHONE_NUMBER_ID_1)
        media_file = body.get('mediaFile')  # S3 key or base64
        media_type = body.get('mediaType')  # image, video, audio, document
        media_filename = body.get('mediaFileName')  # Original filename for documents
        is_template = body.get('isTemplate', False)
        template_name = body.get('templateName')
        template_params = body.get('templateParams', [])
        
        # Payment template support (order_details)
        is_payment_template = body.get('isPaymentTemplate', False)
        order_details = body.get('orderDetails')
        header_image_url = body.get('headerImageUrl')
        
        # OTP / Authentication template support
        is_otp_template = body.get('isOtpTemplate', False) or body.get('isAuthenticationTemplate', False)
        otp_code = body.get('otpCode', '')
        otp_button_type = body.get('otpButtonType', 'copy_code')  # 'url' or 'copy_code'

        # Standard template media header support (IMAGE / VIDEO / DOCUMENT headers).
        # Templates like wecare_pdf (DOCUMENT), wd_order/wd_menu (VIDEO) require a
        # header parameter at SEND time — the approval-time example handle is not
        # reusable. The inbox TemplateSender supplies a public link here.
        template_header_media = body.get('headerMedia') or body.get('templateHeaderMedia')
        template_header_type = (body.get('headerType') or body.get('templateHeaderType') or '').lower()
        template_header_filename = body.get('headerFilename') or body.get('templateHeaderFilename')
        # Location header support (headerType == 'location').
        # Expects {latitude, longitude, name, address} supplied at send time.
        template_header_location = body.get('headerLocation') or body.get('templateHeaderLocation')
        # Flow button support: templates with a FLOW button require a button
        # component (sub_type 'flow') at send time, else Meta rejects with
        # error 131008/131009. The frontend detects the flow button from the
        # template definition and passes {index, flowToken?, flowActionData?}.
        template_flow_button = body.get('flowButton') or body.get('templateFlowButton')

        # Interactive payment support (for within 24h window - uses payment_settings)
        is_interactive_payment = body.get('isInteractivePayment', False)
        
        # Checkout button template support (order_details button with sale_amount + shipping_info)
        is_checkout_template = body.get('isCheckoutTemplate', False)
        checkout_order_details = body.get('checkoutOrderDetails')  # Full Meta order_details object
        
        # Interactive message support (list, buttons, location request)
        is_interactive = body.get('isInteractive', False)
        interactive_type = body.get('interactiveType')  # 'list', 'button', 'location_request'
        interactive_data = body.get('interactiveData', {})
        
        # Order status support (for payment confirmation messages)
        is_order_status = body.get('isOrderStatus', False)
        order_status_details = body.get('orderStatusDetails')
        
        # Direct phone number (fallback when contactId not available)
        recipient_phone_direct = body.get('recipientPhone')
        
        # BSUID recipient (for sending to users without phone numbers)
        recipient_bsuid = body.get('recipientBsuid', '')
        
        # Reaction support
        is_reaction = body.get('isReaction', False)
        reaction_message_id = body.get('reactionMessageId')  # WhatsApp message ID to react to
        reaction_emoji = body.get('reactionEmoji', '\U0001F44D')  # Default: thumbs up
        
        # Native reply support — quote the WhatsApp message id being replied to.
        context_message_id = body.get('contextMessageId') or body.get('replyToMessageId')
        
        # Allow sending without contactId if recipientPhone is provided (for order_status)
        if not contact_id and not recipient_phone_direct:
            return _error_response(400, 'contactId or recipientPhone is required')
        
        # If we have recipientPhone but no contactId, auto-create contact so message shows in inbox
        if not contact_id and recipient_phone_direct:
            contact = _get_or_create_contact_by_phone(recipient_phone_direct)
            contact_id = contact.get('contactId') or contact.get('id', '')
            recipient_phone = recipient_phone_direct
        else:
            # Retrieve contact
            contact = _get_contact(contact_id)
            if not contact:
                return _error_response(404, 'Contact not found')
            recipient_phone = contact.get('phone')
            # Auto-resolve BSUID from contact if not explicitly provided
            if not recipient_bsuid and contact.get('bsuid'):
                recipient_bsuid = contact.get('bsuid', '')
        
        # Validate reaction request
        if is_reaction and not reaction_message_id:
            return _error_response(400, 'reactionMessageId is required for reactions')
        
        # Handle typing indicator request (fire and forget)
        is_typing_indicator = body.get('isTypingIndicator', False)
        if is_typing_indicator:
            try:
                typing_msg_id = body.get('messageId') or body.get('typingMessageId') or ''
                _send_typing_indicator(phone_number_id, typing_msg_id)
                return {
                    'statusCode': 200,
                    'headers': cors_headers(origin),
                    'body': json.dumps({'success': True, 'action': 'typing_indicator'})
                }
            except Exception as e:
                logger.warning(f'Typing indicator failed: {e}')
                return {
                    'statusCode': 200,
                    'headers': cors_headers(origin),
                    'body': json.dumps({'success': False, 'action': 'typing_indicator', 'error': str(e)})
                }
        
        # Block / unblock / list blocked users (Meta block_users API).
        # Only users who messaged in the last 24h can be blocked (Meta rule).
        block_action = body.get('blockAction')  # 'block' | 'unblock' | 'list'
        if block_action:
            try:
                if block_action == 'list':
                    result = _block_users_api(phone_number_id, [], 'list')
                    return {'statusCode': 200, 'headers': cors_headers(origin), 'body': json.dumps({'success': True, 'action': 'list', 'result': result})}
                users = body.get('blockUsers') or []
                if not users and recipient_phone:
                    users = [recipient_phone]
                if not users:
                    return _error_response(400, 'No user phone provided to block/unblock')
                result = _block_users_api(phone_number_id, users, block_action)
                return {'statusCode': 200, 'headers': cors_headers(origin), 'body': json.dumps({'success': True, 'action': block_action, 'users': users, 'result': result})}
            except Exception as e:
                return _error_response(502, f'Block API error ({block_action}): {e}')
        
        # Opt-in enforcement: all contacts allowed by default (permissive)
        # Service window check: outside 24h window, only templates are allowed (WhatsApp policy)
        within_window = True
        if contact and contact.get('id'):
            within_window = _is_within_service_window(contact)
        if not within_window and not is_template:
            return _error_response(403, 'Outside 24h service window — only template messages allowed')
        
        # Requirement 5.4: Validate text length (skip for reactions)
        if not is_reaction and content and len(content) > MAX_TEXT_LENGTH:
            return _error_response(400, f'Content exceeds {MAX_TEXT_LENGTH} characters')
        
        # Requirement 5.9: Check rate limit
        if not _check_rate_limit(phone_number_id):
            return _error_response(429, 'Rate limit exceeded. Try again later.')
        
        # Generate message ID
        message_id = str(uuid.uuid4())
        
        # Requirement 5.3: DRY_RUN mode - log without API call
        if SEND_MODE == 'DRY_RUN':
            if is_reaction:
                return _handle_dry_run_reaction(message_id, contact_id, recipient_phone, reaction_message_id, reaction_emoji, request_id)
            return _handle_dry_run(message_id, contact_id, recipient_phone, content, is_template, request_id)
        
        # Handle reaction messages
        if is_reaction:
            return _handle_reaction_send(
                message_id, contact_id, recipient_phone, phone_number_id,
                reaction_message_id, reaction_emoji, request_id,
                recipient_bsuid=recipient_bsuid
            )
        
        # Handle order_status messages (payment confirmation)
        if is_order_status and order_status_details:
            return _handle_order_status_send(
                message_id, contact_id, recipient_phone, phone_number_id,
                order_status_details, request_id,
                recipient_bsuid=recipient_bsuid
            )
        
        # Handle interactive messages (list, buttons, location request)
        if is_interactive and interactive_type:
            return _handle_interactive_send(
                message_id, contact_id, recipient_phone, phone_number_id,
                interactive_type, interactive_data, request_id,
                recipient_bsuid=recipient_bsuid
            )
        
        # Handle checkout button template (order_details button with sale_amount + shipping_info)
        if is_checkout_template and checkout_order_details:
            return _handle_checkout_template_send(
                message_id, contact_id, recipient_phone, phone_number_id,
                is_template, template_name, template_params,
                checkout_order_details, header_image_url,
                request_id, recipient_bsuid=recipient_bsuid
            )
        
        # Requirement 5.2: LIVE mode - call API
        return _handle_live_send(
            message_id, contact_id, recipient_phone, phone_number_id,
            content, media_file, media_type, media_filename, is_template, template_name,
            template_params, within_window, request_id, is_payment_template, order_details, 
            header_image_url, is_interactive_payment, is_otp_template, otp_code, otp_button_type,
            recipient_bsuid=recipient_bsuid,
            template_header_media=template_header_media,
            template_header_type=template_header_type,
            template_header_filename=template_header_filename,
            template_header_location=template_header_location,
            template_flow_button=template_flow_button,
            context_message_id=context_message_id
        )
        
    except json.JSONDecodeError:
        return _error_response(400, 'Invalid JSON in request body')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'outbound_whatsapp_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, 'Internal server error')


def _handle_dry_run(message_id: str, contact_id: str, recipient_phone: str, 
                    content: str, is_template: bool, request_id: str) -> Dict[str, Any]:
    """Handle DRY_RUN mode - log without actual API call."""
    now = int(time.time())
    
    # Store message record with DRY_RUN status
    _store_message_record(
        message_id=message_id,
        contact_id=contact_id,
        content=content,
        status='dry_run',
        is_template=is_template,
        whatsapp_message_id=f'dry-run-{message_id}'
    )
    
    logger.info(json.dumps({
        'event': 'dry_run_message',
        'messageId': message_id,
        'contactId': contact_id,
        'recipientPhone': recipient_phone,
        'contentLength': len(content) if content else 0,
        'isTemplate': is_template,
        'requestId': request_id
    }))
    
    return {
        'statusCode': 200,
        'headers': cors_headers(origin),
        'body': json.dumps({
            'messageId': message_id,
            'status': 'dry_run',
            'mode': 'DRY_RUN',
            'message': 'Message logged but not sent (DRY_RUN mode)'
        })
    }


def _handle_dry_run_reaction(message_id: str, contact_id: str, recipient_phone: str,
                              reaction_message_id: str, reaction_emoji: str, request_id: str) -> Dict[str, Any]:
    """Handle DRY_RUN mode for reactions - log without actual API call."""
    logger.info(json.dumps({
        'event': 'dry_run_reaction',
        'messageId': message_id,
        'contactId': contact_id,
        'recipientPhone': recipient_phone,
        'reactionMessageId': reaction_message_id,
        'emoji': reaction_emoji,
        'requestId': request_id
    }))
    
    return {
        'statusCode': 200,
        'headers': cors_headers(origin),
        'body': json.dumps({
            'messageId': message_id,
            'status': 'dry_run',
            'mode': 'DRY_RUN',
            'type': 'reaction',
            'reactionMessageId': reaction_message_id,
            'emoji': reaction_emoji,
            'message': 'Reaction logged but not sent (DRY_RUN mode)'
        })
    }


def _handle_reaction_send(message_id: str, contact_id: str, recipient_phone: str,
                          phone_number_id: str, reaction_message_id: str, 
                          reaction_emoji: str, request_id: str,
                          recipient_bsuid: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a reaction to a WhatsApp message.
    Uses Meta Graph API (Direct API) with reaction type.
    Per Meta docs: reaction payload requires message_id from the original message.
    """
    try:
        # Normalize phone number and add + prefix for reactions
        # AWS docs example: "to":"'{PHONE_NUMBER}'" - try with + prefix
        digits_only = _normalize_phone_number(recipient_phone)
        formatted_phone = f"+{digits_only}" if not digits_only.startswith('+') else digits_only
        
        # Build reaction payload per Meta WhatsApp Cloud API docs
        reaction_payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': formatted_phone,
            'type': 'reaction',
            'reaction': {
                'message_id': reaction_message_id,
                'emoji': reaction_emoji
            }
        }
        # Add BSUID recipient if available (per Meta BSUID docs)
        if recipient_bsuid:
            reaction_payload['recipient'] = recipient_bsuid
        
        logger.info(json.dumps({
            'event': 'reaction_payload',
            'to': formatted_phone,
            'reactionMessageId': reaction_message_id,
            'emoji': reaction_emoji,
            'payload': reaction_payload,
            'requestId': request_id
        }))
        
        # Call SendWhatsAppMessage API (Direct API)
        response = _send_message(phone_number_id, reaction_payload)
        
        whatsapp_message_id = response.get('messageId', '')
        
        logger.info(json.dumps({
            'event': 'reaction_sent',
            'messageId': message_id,
            'whatsappMessageId': whatsapp_message_id,
            'contactId': contact_id,
            'reactionMessageId': reaction_message_id,
            'emoji': reaction_emoji,
            'requestId': request_id
        }))
        
        # Emit success metric
        _emit_delivery_metric('success', is_template=False)
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE',
                'type': 'reaction',
                'reactionMessageId': reaction_message_id,
                'emoji': reaction_emoji
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        # Log detailed error for debugging
        logger.error(json.dumps({
            'event': 'reaction_send_error',
            'messageId': message_id,
            'reactionMessageId': reaction_message_id,
            'recipientPhone': recipient_phone,
            'formattedPhone': _normalize_phone_number(recipient_phone),
            'phoneNumberId': phone_number_id,
            'error': error_msg,
            'requestId': request_id
        }))
        _emit_delivery_metric('failed', is_template=False)
        return _error_response(500, f'Failed to send reaction: {error_msg}')


def _handle_order_status_send(message_id: str, contact_id: str, recipient_phone: str,
                               phone_number_id: str, order_status_details: Dict,
                               request_id: str,
                               recipient_bsuid: Optional[str] = None) -> Dict[str, Any]:
    """
    Send order_status interactive message to confirm payment status.
    
    Messages:
    - Payment Success (captured): Payment of ₹{amount} received successfully! Thank you ✅
    - Payment Failed: Payment failed. Please try again ❌
    """
    try:
        raw_reference_id = order_status_details.get('reference_id', '')
        # Sanitize reference_id to remove duplicate WD prefixes
        reference_id = _sanitize_reference_id(raw_reference_id)
        order_status = order_status_details.get('order_status', 'completed')
        amount = order_status_details.get('amount', 0)  # Amount in rupees
        
        # Log the received order_status_details for debugging
        logger.info(json.dumps({
            'event': 'order_status_details_received',
            'orderStatusDetails': order_status_details,
            'rawReferenceId': raw_reference_id,
            'sanitizedReferenceId': reference_id,
            'amount': amount,
            'amountType': type(amount).__name__,
            'requestId': request_id
        }))
        
        # Ensure amount is a float
        try:
            amount = float(amount) if amount else 0.0
        except (ValueError, TypeError):
            amount = 0.0
        
        # Generate appropriate message based on status
        if order_status == 'completed' or order_status == 'captured':
            # Use description from inbound handler if amount is 0 (fallback)
            if amount > 0:
                body_text = f"Payment of ₹{amount:.2f} received successfully! Thank you ✅"
            else:
                # Use the description passed from inbound handler which may have the amount
                body_text = order_status_details.get('description', 'Payment received successfully! Thank you ✅')
            description = "Payment received. Thank you!"
            order_status = 'completed'
        elif order_status == 'failed':
            body_text = "Payment failed. Please try again ❌"
            description = "Payment failed"
        else:
            body_text = order_status_details.get('description', 'Order status updated')
            description = body_text
        
        # Normalize phone number
        formatted_phone = _normalize_phone_number(recipient_phone)
        whatsapp_phone = f"+{formatted_phone}"
        
        # Build order_status payload
        order_status_payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': whatsapp_phone,
            'type': 'interactive',
            'interactive': {
                'type': 'order_status',
                'body': {
                    'text': body_text
                },
                'action': {
                    'name': 'review_order',
                    'parameters': {
                        'reference_id': reference_id,
                        'order': {
                            'status': order_status,
                            'description': description
                        }
                    }
                }
            }
        }
        # Add BSUID recipient if available (per Meta BSUID docs)
        if recipient_bsuid:
            order_status_payload['recipient'] = recipient_bsuid
        
        logger.info(json.dumps({
            'event': 'order_status_payload',
            'to': whatsapp_phone,
            'referenceId': reference_id,
            'orderStatus': order_status,
            'payload': order_status_payload,
            'requestId': request_id
        }))
        
        # Call SendWhatsAppMessage API (Direct API)
        response = _send_message(phone_number_id, order_status_payload)
        
        whatsapp_message_id = response.get('messageId', '')
        
        # Store message record
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=f'Order Status: {order_status} - {description}',
            status='sent',
            is_template=False,
            whatsapp_message_id=whatsapp_message_id,
            phone_number_id=phone_number_id,
            recipient_bsuid=recipient_bsuid,
        )
        
        logger.info(json.dumps({
            'event': 'order_status_sent',
            'messageId': message_id,
            'whatsappMessageId': whatsapp_message_id,
            'contactId': contact_id,
            'referenceId': reference_id,
            'orderStatus': order_status,
            'requestId': request_id
        }))
        
        # Emit success metric
        _emit_delivery_metric('success', is_template=False)
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE',
                'type': 'order_status',
                'referenceId': reference_id,
                'orderStatus': order_status
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(json.dumps({
            'event': 'order_status_send_error',
            'messageId': message_id,
            'referenceId': order_status_details.get('reference_id', ''),
            'error': error_msg,
            'requestId': request_id
        }))
        _emit_delivery_metric('failed', is_template=False)
        return _error_response(500, f'Failed to send order status: {error_msg}')


# ═══════════════════════════════════════════════════════════════════════════
# CHECKOUT BUTTON TEMPLATE — Send handler
# Per Meta docs: Checkout button templates use order_details button with
# sale_amount, shipping_info, importer_address, and payment_settings.
# https://developers.facebook.com/docs/whatsapp/cloud-api/payments-api/
#   payments-in/checkout-button-templates
# ═══════════════════════════════════════════════════════════════════════════

def _handle_checkout_template_send(
        message_id: str, contact_id: str, recipient_phone: str,
        phone_number_id: str, is_template: bool, template_name: str,
        template_params: list, checkout_order_details: Dict,
        header_image_url: Optional[str], request_id: str,
        recipient_bsuid: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a checkout button template message with order_details action.
    
    The checkout_order_details dict is the FULL Meta order_details object including:
    - reference_id, type (physical-goods/digital-goods), currency
    - payment_settings (payment_gateway config)
    - shipping_info (country, addresses with name/phone/address/city/state/pin)
    - order (items with amount/sale_amount, subtotal, shipping, tax, discount, expiration)
    - total_amount
    
    This builds the exact payload Meta expects for checkout button templates.
    """
    try:
        formatted_phone = _normalize_phone_number(recipient_phone)
        whatsapp_phone = f"+{formatted_phone}"

        # Determine template language from params or auto-detect per WABA
        # wecare_pay: WABA1 uses 'en', WABA-T uses 'en_US'
        template_language = 'en_US'  # default
        actual_params = list(template_params) if template_params else []
        if actual_params and isinstance(actual_params[0], str) and (
                len(actual_params[0]) == 2 or '_' in actual_params[0]):
            template_language = actual_params[0]
            actual_params = actual_params[1:]
        elif '1016149501586345' in str(phone_number_id):
            template_language = 'en'  # WABA1
        else:
            template_language = 'en_US'  # WABA-T

        # Build payment_settings from checkout_order_details or infer from phone
        payment_settings = checkout_order_details.get('payment_settings')
        if not payment_settings:
            # Auto-build from phone's configured gateway
            payment_settings = _build_payment_settings(phone_number_id, checkout_order_details)

        # Ensure reference_id is sanitized
        ref_id = _sanitize_reference_id(checkout_order_details.get('reference_id', ''))
        checkout_order_details['reference_id'] = ref_id

        # Build the order_details action object (strip payment_settings — they go at top level)
        order_obj = checkout_order_details.get('order', {})

        # Ensure expiration has description (Meta requires it for templates)
        if 'expiration' not in order_obj:
            import time as _time
            order_obj['expiration'] = {
                'timestamp': str(int(_time.time()) + 86400),
                'description': 'Order expires in 24 hours',
            }
        elif not order_obj.get('expiration', {}).get('description'):
            order_obj['expiration']['description'] = 'Order expires in 24 hours'

        # Ensure discount has description (Meta requires it)
        if 'discount' in order_obj and not order_obj['discount'].get('description'):
            order_obj['discount']['description'] = 'Discount'

        # Calculate total_amount if not provided
        total_amount = checkout_order_details.get('total_amount', {})
        if not total_amount.get('value'):
            subtotal = order_obj.get('subtotal', {}).get('value', 0)
            shipping = order_obj.get('shipping', {}).get('value', 0)
            tax = order_obj.get('tax', {}).get('value', 0)
            discount = order_obj.get('discount', {}).get('value', 0)
            total_amount = {'offset': 100, 'value': subtotal + shipping + tax - discount}

        order_details_action = {
            'reference_id': ref_id,
            'type': checkout_order_details.get('type', 'physical-goods'),
            'currency': checkout_order_details.get('currency', 'INR'),
            'payment_settings': payment_settings,
            'order': order_obj,
            'total_amount': total_amount,
        }

        # Add shipping_info for physical-goods
        if checkout_order_details.get('type', '') == 'physical-goods':
            shipping_info = checkout_order_details.get('shipping_info')
            if shipping_info:
                order_details_action['shipping_info'] = shipping_info
            else:
                # Default: empty addresses array — WhatsApp will ask user to add address
                order_details_action['shipping_info'] = {'country': 'IN', 'addresses': []}

        # Ensure all items have required India compliance fields
        WECARE_IMPORTER = {
            'country_of_origin': 'India',
            'importer_name': 'WECARE.DIGITAL',
            'importer_address': {
                'address_line1': '81/2/7 Phears Ln',
                'city': 'Kolkata',
                'zone_code': 'WB',
                'postal_code': '700012',
                'country_code': 'IN',
            },
        }
        for item in order_obj.get('items', []):
            if not item.get('importer_name'):
                item.update(WECARE_IMPORTER)
            if not item.get('country_of_origin'):
                item['country_of_origin'] = 'India'

        # Build template components
        components = []

        # Header (image or video) — wecare_pay template REQUIRES image header
        DEFAULT_CHECKOUT_HEADER = 'https://app.wecare.digital/stream/media/m/wecare-digital.png'
        checkout_header = header_image_url or DEFAULT_CHECKOUT_HEADER
        if checkout_order_details.get('header_image_id'):
            components.append({
                'type': 'header',
                'parameters': [{
                    'type': 'image',
                    'image': {'id': checkout_order_details['header_image_id']},
                }],
            })
        else:
            components.append({
                'type': 'header',
                'parameters': [{
                    'type': 'image',
                    'image': {'link': checkout_header},
                }],
            })

        # Body parameters
        if actual_params:
            components.append({
                'type': 'body',
                'parameters': [{'type': 'text', 'text': str(p)} for p in actual_params],
            })

        # Checkout button (order_details) — always index 0
        components.append({
            'type': 'button',
            'sub_type': 'order_details',
            'index': 0,
            'parameters': [{
                'type': 'action',
                'action': {
                    'order_details': order_details_action,
                },
            }],
        })

        # Build full payload
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': whatsapp_phone,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {
                    'policy': 'deterministic',
                    'code': template_language,
                },
                'components': components,
            },
        }

        if recipient_bsuid:
            payload['recipient'] = recipient_bsuid

        logger.info(json.dumps({
            'event': 'checkout_template_payload_built',
            'templateName': template_name,
            'language': template_language,
            'referenceId': ref_id,
            'goodsType': order_details_action.get('type'),
            'itemCount': len(order_details_action.get('order', {}).get('items', [])),
            'totalAmount': order_details_action.get('total_amount', {}).get('value', 0),
            'hasShippingInfo': 'shipping_info' in order_details_action,
            'hasHeaderImage': bool(header_image_url or checkout_order_details.get('header_image_id')),
            'bodyParamCount': len(actual_params),
            'requestId': request_id,
        }))

        # Send via Meta API
        response = _send_message(phone_number_id, payload)
        whatsapp_message_id = response.get('messageId', '')

        # Store message record
        item_names = ', '.join(
            i.get('name', '') for i in order_details_action.get('order', {}).get('items', [])
        )
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=f'[Checkout: {template_name}] {item_names} — Ref: {ref_id}',
            status='sent',
            is_template=True,
            whatsapp_message_id=whatsapp_message_id,
            phone_number_id=phone_number_id,
            recipient_bsuid=recipient_bsuid,
        )

        _emit_delivery_metric('success', is_template=True)

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE',
                'type': 'checkout_template',
                'templateName': template_name,
                'referenceId': ref_id,
            }),
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(json.dumps({
            'event': 'checkout_template_send_error',
            'messageId': message_id,
            'templateName': template_name,
            'error': error_msg,
            'requestId': request_id,
        }))
        _emit_delivery_metric('failed', is_template=True)
        return _error_response(500, f'Failed to send checkout template: {error_msg}')


def _handle_interactive_send(message_id: str, contact_id: str, recipient_phone: str,
                              phone_number_id: str, interactive_type: str,
                              interactive_data: Dict, request_id: str,
                              recipient_bsuid: Optional[str] = None) -> Dict[str, Any]:
    """
    Send interactive messages (list, buttons, location request, CTA URL).
    
    Interactive Types:
    - list: Up to 10 sections with rows (max 10 rows total)
    - button: Up to 3 quick reply buttons
    - location_request: Request user's location
    - cta_url: Call-to-action URL button
    - flow: WhatsApp Flow trigger (if supported)
    
    Per WhatsApp Business API docs:
    https://developers.facebook.com/docs/whatsapp/guides/interactive-messages/
    https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-cta-url-messages/
    """
    try:
        # Normalize phone number
        formatted_phone = _normalize_phone_number(recipient_phone)
        whatsapp_phone = f"+{formatted_phone}"
        
        # Base payload
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': whatsapp_phone,
            'type': 'interactive'
        }
        # Add BSUID recipient if available (per Meta BSUID docs)
        if recipient_bsuid:
            payload['recipient'] = recipient_bsuid
        
        # Build interactive payload based on type
        if interactive_type == 'list':
            # List message with sections and rows
            header_text = interactive_data.get('header', '')
            body_text = interactive_data.get('body', 'Please select an option')
            footer_text = interactive_data.get('footer', '')
            button_text = interactive_data.get('buttonText', 'View Options')
            sections = interactive_data.get('sections', [])
            
            interactive_payload = {
                'type': 'list',
                'body': {'text': body_text},
                'action': {
                    'button': button_text,
                    'sections': []
                }
            }
            
            # Add header if provided
            if header_text:
                interactive_payload['header'] = {'type': 'text', 'text': header_text}
            
            # Add footer if provided
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            
            # Build sections (max 10 sections, max 10 rows total)
            for section in sections[:10]:
                section_obj = {
                    'title': section.get('title', 'Options'),
                    'rows': []
                }
                for row in section.get('rows', [])[:10]:
                    section_obj['rows'].append({
                        'id': row.get('id', str(len(section_obj['rows']))),
                        'title': row.get('title', 'Option')[:24],  # Max 24 chars
                        'description': row.get('description', '')[:72]  # Max 72 chars
                    })
                if section_obj['rows']:
                    interactive_payload['action']['sections'].append(section_obj)
            
            payload['interactive'] = interactive_payload
            
        elif interactive_type == 'button':
            # Reply buttons (max 3)
            header_text = interactive_data.get('header', '')
            header_type = interactive_data.get('headerType', 'text')  # text, image, video, document
            body_text = interactive_data.get('body', 'Please select an option')
            footer_text = interactive_data.get('footer', '')
            buttons = interactive_data.get('buttons', [])
            
            interactive_payload = {
                'type': 'button',
                'body': {'text': body_text},
                'action': {'buttons': []}
            }
            
            # Add header if provided
            if header_text or header_type != 'text':
                if header_type == 'text':
                    interactive_payload['header'] = {'type': 'text', 'text': header_text}
                elif header_type == 'image':
                    interactive_payload['header'] = {
                        'type': 'image',
                        'image': {'link': interactive_data.get('headerMedia', '')}
                    }
                elif header_type == 'video':
                    interactive_payload['header'] = {
                        'type': 'video',
                        'video': {'link': interactive_data.get('headerMedia', '')}
                    }
                elif header_type == 'document':
                    interactive_payload['header'] = {
                        'type': 'document',
                        'document': {
                            'link': interactive_data.get('headerMedia', ''),
                            'filename': interactive_data.get('headerFilename', 'document.pdf')
                        }
                    }
            
            # Add footer if provided
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            
            # Build buttons (max 3)
            for i, btn in enumerate(buttons[:3]):
                interactive_payload['action']['buttons'].append({
                    'type': 'reply',
                    'reply': {
                        'id': btn.get('id', f'btn_{i}'),
                        'title': btn.get('title', 'Button')[:20]  # Max 20 chars
                    }
                })
            
            payload['interactive'] = interactive_payload
            
        elif interactive_type == 'location_request':
            # Location request message
            body_text = interactive_data.get('body', 'Please share your location')
            
            interactive_payload = {
                'type': 'location_request_message',
                'body': {'text': body_text},
                'action': {'name': 'send_location'}
            }
            
            payload['interactive'] = interactive_payload
        
        elif interactive_type == 'cta_url':
            # Call-to-action URL button message
            # Per Meta docs: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-cta-url-messages/
            header_text = interactive_data.get('header', '')
            header_type = interactive_data.get('headerType', 'text')
            body_text = interactive_data.get('body', 'Click the button below')
            footer_text = interactive_data.get('footer', '')
            button_text = interactive_data.get('buttonText', 'Visit')[:20]  # Max 20 chars
            url = interactive_data.get('url', '')
            
            if not url:
                return _error_response(400, 'url is required for cta_url type')
            
            interactive_payload = {
                'type': 'cta_url',
                'body': {'text': body_text},
                'action': {
                    'name': 'cta_url',
                    'parameters': {
                        'display_text': button_text,
                        'url': url
                    }
                }
            }
            
            # Add header if provided
            if header_text:
                if header_type == 'text':
                    interactive_payload['header'] = {'type': 'text', 'text': header_text}
                elif header_type == 'image':
                    interactive_payload['header'] = {
                        'type': 'image',
                        'image': {'link': interactive_data.get('headerMedia', '')}
                    }
                elif header_type == 'video':
                    interactive_payload['header'] = {
                        'type': 'video',
                        'video': {'link': interactive_data.get('headerMedia', '')}
                    }
            
            # Add footer if provided
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            
            payload['interactive'] = interactive_payload
        
        elif interactive_type == 'flow':
            # WhatsApp Flow trigger message
            # Per Meta docs: https://developers.facebook.com/docs/whatsapp/flows/
            header_text = interactive_data.get('header', '')
            body_text = interactive_data.get('body', 'Start the flow')
            footer_text = interactive_data.get('footer', '')
            flow_id = interactive_data.get('flowId', '')
            flow_cta = interactive_data.get('flowCta', 'Start')[:20]
            flow_action = interactive_data.get('flowAction', 'navigate')  # navigate or data_exchange
            flow_token = interactive_data.get('flowToken', str(uuid.uuid4()))
            screen_id = interactive_data.get('screenId', '')  # First screen to show
            flow_data = interactive_data.get('flowData', {})  # Data to pass to flow
            
            if not flow_id:
                return _error_response(400, 'flowId is required for flow type')
            
            interactive_payload = {
                'type': 'flow',
                'body': {'text': body_text},
                'action': {
                    'name': 'flow',
                    'parameters': {
                        'flow_message_version': '3',
                        'flow_token': flow_token,
                        'flow_id': flow_id,
                        'flow_cta': flow_cta,
                        'flow_action': flow_action
                    }
                }
            }
            
            # flow_action_payload is ONLY valid for "navigate" mode.
            # For "data_exchange", Meta sends INIT to the endpoint automatically —
            # do NOT include flow_action_payload or Meta returns error 131009.
            if flow_action == 'navigate' and screen_id:
                interactive_payload['action']['parameters']['flow_action_payload'] = {
                    'screen': screen_id
                }
                if flow_data:
                    interactive_payload['action']['parameters']['flow_action_payload']['data'] = flow_data
            
            # Add header if provided
            if header_text:
                interactive_payload['header'] = {'type': 'text', 'text': header_text}
            
            # Add footer if provided
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            
            payload['interactive'] = interactive_payload
            
        elif interactive_type == 'product':
            # Single Product Message — requires a catalog_id + product_retailer_id.
            catalog_id = interactive_data.get('catalogId') or interactive_data.get('catalog_id')
            product_retailer_id = interactive_data.get('productRetailerId') or interactive_data.get('product_retailer_id')
            if not catalog_id or not product_retailer_id:
                return _error_response(400, 'product message requires catalogId and productRetailerId')
            interactive_payload = {
                'type': 'product',
                'action': {
                    'catalog_id': str(catalog_id),
                    'product_retailer_id': str(product_retailer_id),
                }
            }
            if interactive_data.get('body'):
                interactive_payload['body'] = {'text': interactive_data['body']}
            if interactive_data.get('footer'):
                interactive_payload['footer'] = {'text': interactive_data['footer']}
            payload['interactive'] = interactive_payload
            
        elif interactive_type == 'product_list':
            # Multi-Product Message — catalog_id + sections of product_items.
            catalog_id = interactive_data.get('catalogId') or interactive_data.get('catalog_id')
            sections_in = interactive_data.get('sections', [])
            if not catalog_id or not sections_in:
                return _error_response(400, 'product_list requires catalogId and sections')
            header_text = interactive_data.get('header', 'Our products')
            body_text = interactive_data.get('body', 'Browse our catalog')
            footer_text = interactive_data.get('footer', '')
            sections_out = []
            for section in sections_in[:10]:
                items = section.get('productItems') or section.get('product_items') or []
                product_items = []
                for it in items[:30]:
                    rid = it.get('productRetailerId') or it.get('product_retailer_id') or (it if isinstance(it, str) else None)
                    if rid:
                        product_items.append({'product_retailer_id': str(rid)})
                if product_items:
                    sections_out.append({'title': section.get('title', 'Products')[:24], 'product_items': product_items})
            if not sections_out:
                return _error_response(400, 'product_list has no valid product items')
            interactive_payload = {
                'type': 'product_list',
                'header': {'type': 'text', 'text': header_text},
                'body': {'text': body_text},
                'action': {
                    'catalog_id': str(catalog_id),
                    'sections': sections_out,
                }
            }
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            payload['interactive'] = interactive_payload
            
        else:
            return _error_response(400, f'Invalid interactive type: {interactive_type}')
        
        logger.info(json.dumps({
            'event': 'interactive_payload',
            'to': whatsapp_phone,
            'interactiveType': interactive_type,
            'payload': payload,
            'requestId': request_id
        }))
        
        # Call SendWhatsAppMessage API (Direct API)
        response = _send_message(phone_number_id, payload)
        
        whatsapp_message_id = response.get('messageId', '')
        
        # Store message record
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=f'[Interactive: {interactive_type}] {interactive_data.get("body", "")}',
            status='sent',
            is_template=False,
            whatsapp_message_id=whatsapp_message_id,
            phone_number_id=phone_number_id,
            recipient_bsuid=recipient_bsuid,
        )
        
        logger.info(json.dumps({
            'event': 'interactive_sent',
            'messageId': message_id,
            'whatsappMessageId': whatsapp_message_id,
            'contactId': contact_id,
            'interactiveType': interactive_type,
            'requestId': request_id
        }))
        
        # Emit success metric
        _emit_delivery_metric('success', is_template=False)
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE',
                'type': 'interactive',
                'interactiveType': interactive_type
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(json.dumps({
            'event': 'interactive_send_error',
            'messageId': message_id,
            'interactiveType': interactive_type,
            'error': error_msg,
            'requestId': request_id
        }))
        _emit_delivery_metric('failed', is_template=False)
        return _error_response(500, f'Failed to send interactive message: {error_msg}')


def _handle_live_send(message_id: str, contact_id: str, recipient_phone: str,
                      phone_number_id: str, content: str, media_file: Optional[str],
                      media_type: Optional[str], media_filename: Optional[str], is_template: bool, template_name: Optional[str],
                      template_params: list, within_window: bool, request_id: str,
                      is_payment_template: bool = False, order_details: Optional[Dict] = None,
                      header_image_url: Optional[str] = None, is_interactive_payment: bool = False,
                      is_otp_template: bool = False, otp_code: Optional[str] = None,
                      otp_button_type: Optional[str] = None,
                      recipient_bsuid: Optional[str] = None,
                      template_header_media: Optional[str] = None,
                      template_header_type: Optional[str] = None,
                      template_header_filename: Optional[str] = None,
                      template_header_location: Optional[Dict] = None,
                      template_flow_button: Optional[Dict] = None,
                      context_message_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Handle LIVE mode - call Meta Graph API (Direct API).
    Requirements: 5.2, 5.5, 5.6, 5.7, 5.8, 5.10, 5.11
    """
    try:
        whatsapp_media_id = None
        s3_key = None
        stored_filename = None
        
        # Requirements 5.5, 5.6, 5.7: Handle media upload
        if media_file and media_type:
            # Use provided filename from frontend, or extract from path
            filename = media_filename
            if not filename and isinstance(media_file, str) and '/' in media_file:
                filename = media_file.split('/')[-1]
            
            s3_key, whatsapp_media_id, stored_filename = _upload_media(media_file, media_type, message_id, phone_number_id, request_id, filename)
            if not whatsapp_media_id:
                return _error_response(500, 'Failed to upload media')

        # Resolve a template media header (IMAGE/VIDEO/DOCUMENT) into a sendable
        # reference. A public https link is passed through as-is; an S3 key is
        # uploaded to the WhatsApp media API and replaced with its media id so
        # private-bucket files work without exposing a public URL.
        resolved_header_media = template_header_media
        if (is_template and template_header_media and template_header_type
                and not str(template_header_media).startswith('http')):
            try:
                _, _hdr_media_id, _ = _upload_media(
                    template_header_media, template_header_type, message_id,
                    phone_number_id, request_id, template_header_filename
                )
                if _hdr_media_id:
                    resolved_header_media = _hdr_media_id
                else:
                    logger.warning(json.dumps({
                        'event': 'template_header_media_resolve_failed',
                        'templateName': template_name, 'requestId': request_id
                    }))
            except Exception as _he:
                logger.warning(json.dumps({
                    'event': 'template_header_media_resolve_error',
                    'error': str(_he), 'requestId': request_id
                }))

        # Build WhatsApp message payload
        message_payload = _build_message_payload(
            recipient_phone, content, media_type, whatsapp_media_id,
            is_template, template_name, template_params, stored_filename,
            is_payment_template, order_details, header_image_url, is_interactive_payment,
            is_otp_template, otp_code, otp_button_type,
            phone_number_id=phone_number_id,
            recipient_bsuid=recipient_bsuid,
            template_header_media=resolved_header_media,
            template_header_type=template_header_type,
            template_header_filename=template_header_filename,
            template_header_location=template_header_location,
            template_flow_button=template_flow_button,
            context_message_id=context_message_id
        )
        
        logger.info(json.dumps({
            'event': 'message_payload_built',
            'messageId': message_id,
            'contactId': contact_id,
            'recipientPhone': recipient_phone,
            'normalizedPhone': message_payload.get('to'),
            'payloadType': message_payload.get('type'),
            'hasMedia': bool(whatsapp_media_id),
            'mediaId': whatsapp_media_id,
            'payload': message_payload,
            'requestId': request_id
        }))
        
        # Requirement 5.8: Call SendWhatsAppMessage API
        # Note: message parameter should be a string, not bytes
        message_json = json.dumps(message_payload)
        
        logger.info(json.dumps({
            'event': 'calling_send_whatsapp_message_api',
            'messageId': message_id,
            'phoneNumberId': phone_number_id,
            'messageJson': message_json,
            'requestId': request_id
        }))
        
        # Idempotency: check if this message_id was already sent (prevents duplicates on retry)
        try:
            messages_table = dynamodb.Table(MESSAGES_TABLE)
            existing = messages_table.get_item(Key={'id': message_id}, ProjectionExpression='id,whatsappMessageId,#s', ExpressionAttributeNames={'#s': 'status'})
            if existing.get('Item') and existing['Item'].get('whatsappMessageId'):
                logger.info(json.dumps({'event': 'idempotent_skip', 'messageId': message_id, 'requestId': request_id}))
                return {
                    'statusCode': 200,
                    'headers': cors_headers(''),
                    'body': json.dumps({'success': True, 'messageId': message_id, 'whatsappMessageId': existing['Item']['whatsappMessageId'], 'idempotent': True})
                }
        except Exception as e:
            logger.warning(f'Idempotency check failed (proceeding): {e}')

        # Retry with exponential backoff for transient failures
        max_retries = 3
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                # Direct API — send via Meta Graph API
                response = _send_direct_api(phone_number_id, message_json)
                last_error = None
                break
            except Exception as e:
                error_str = str(e).lower()
                is_transient = any(kw in error_str for kw in ['timeout', 'service unavailable', '503', '429', 'throttl'])
                if is_transient and attempt < max_retries:
                    wait_time = min(2 ** attempt, 8)
                    logger.warning(json.dumps({
                        'event': 'send_transient_retry',
                        'attempt': attempt + 1,
                        'waitSeconds': wait_time,
                        'error': str(e)[:200],
                        'messageId': message_id,
                        'requestId': request_id
                    }))
                    time.sleep(wait_time)
                    last_error = e
                else:
                    raise
        
        if last_error:
            raise last_error
        
        whatsapp_message_id = response.get('messageId', '')
        
        # Extract payment info for storage (for amount lookup on confirmation)
        payment_ref_id = None
        payment_amount = None
        stored_content = content
        # Templates: guarantee a displayable content string so the sent template
        # shows in the conversation thread (the empty-content guard below would
        # otherwise skip template sends, which carry no free-form `content`).
        if is_template and not stored_content:
            stored_content = f'[Template] {template_name}' if template_name else '[Template message]'
        if is_interactive_payment and order_details:
            payment_ref_id = _sanitize_reference_id(order_details.get('reference_id', ''))
            # Calculate total amount in rupees from order_details
            order_data = order_details.get('order', {})
            total_amt = order_data.get('total_amount', {})
            if not total_amt:
                # total_amount may be at parameters level in built payload
                subtotal_val = order_data.get('subtotal', {}).get('value', 0)
                discount_val = order_data.get('discount', {}).get('value', 0)
                shipping_val = order_data.get('shipping', {}).get('value', 0)
                tax_val = order_data.get('tax', {}).get('value', 0)
                total_paise = subtotal_val - discount_val + shipping_val + tax_val
                payment_amount = total_paise / 100
            else:
                payment_amount = total_amt.get('value', 0) / total_amt.get('offset', 100)
            # Build rich content for inbox display
            item_name = order_details.get('itemName', 'Payment')
            stored_content = f'[Payment: ₹{payment_amount:.2f} | {item_name} | Ref: {payment_ref_id}]'
        
        # Requirement 5.11: Store message record
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=stored_content,
            status='sent',
            is_template=is_template,
            whatsapp_message_id=whatsapp_message_id,
            media_id=whatsapp_media_id,
            s3_key=s3_key,
            phone_number_id=phone_number_id,
            payment_reference_id=payment_ref_id,
            payment_amount=payment_amount,
            recipient_bsuid=recipient_bsuid,
            # Template header media (public link) → shows the attachment in the inbox
            media_url=(resolved_header_media if (is_template and template_header_media
                       and str(resolved_header_media or '').startswith('http')) else None),
        )
        
        # Store payment_request record for invoice generator lookup
        # The invoice engine scans for messageType='payment_request' + paymentReferenceId
        if is_interactive_payment and order_details and payment_ref_id:
            try:
                order_data = order_details.get('order', {})
                items_list = order_data.get('items', [])
                first_item_name = items_list[0].get('name', 'Service Fee') if items_list else order_details.get('itemName', 'Service Fee')
                subtotal_val = order_data.get('subtotal', {}).get('value', 0)
                discount_val = order_data.get('discount', {}).get('value', 0)
                shipping_val = order_data.get('shipping', {}).get('value', 0)
                tax_val = order_data.get('tax', {}).get('value', 0)
                
                # Calculate per-item GST total for gstRate field
                total_gst_rate = 0
                if items_list:
                    weighted_sum = 0
                    total_value = 0
                    for it in items_list:
                        it_val = int(it.get('amount', {}).get('value', 0)) * int(it.get('quantity', 1))
                        it_rate = float(it.get('gstRate', 0))
                        weighted_sum += it_val * it_rate
                        total_value += it_val
                    if total_value > 0:
                        total_gst_rate = weighted_sum / total_value  # Weighted average GST rate
                
                # Look up contact for customer details
                contact_info = _get_contact(contact_id) if contact_id else None
                c_name = (contact_info or {}).get('name', '')
                c_phone = (contact_info or {}).get('phone', recipient_phone or '')
                c_email = (contact_info or {}).get('email', '')
                c_ship = (contact_info or {}).get('shippingAddress', '')
                c_bill = (contact_info or {}).get('billingAddress', '')
                
                pay_req_record = {
                    'id': str(uuid.uuid4()),
                    'messageId': payment_ref_id,
                    'contactId': contact_id,
                    'channel': 'whatsapp',
                    'direction': 'outbound',
                    'messageType': 'payment_request',
                    'content': stored_content,
                    'paymentReferenceId': payment_ref_id,
                    'paymentAmount': Decimal(str(subtotal_val)),
                    'paymentOffset': Decimal('100'),
                    'paymentCurrency': 'INR',
                    'paymentItemName': first_item_name,
                    'paymentItemCount': len(items_list),
                    'paymentQuantity': int(items_list[0].get('quantity', 1)) if items_list else 1,
                    'paymentSubtotal': Decimal(str(subtotal_val)),
                    'paymentDiscount': Decimal(str(discount_val)),
                    'paymentGstRate': Decimal(str(total_gst_rate)),
                    'paymentGstAmount': Decimal(str(tax_val)),
                    'paymentShipping': Decimal(str(shipping_val)),
                    'paymentTotal': Decimal(str(int((payment_amount or 0) * 100))),
                    'paymentGstin': order_details.get('gstin', '19AADFW7431N1ZK'),
                    'paymentSource': 'inbox_ui',
                    'paymentOrderId': order_details.get('orderId', 'Offline'),
                    'paymentCustomerName': c_name,
                    'paymentCustomerPhone': c_phone,
                    'paymentCustomerEmail': c_email,
                    'paymentShippingAddress': c_ship,
                    'paymentBillingAddress': c_bill,
                    'paymentConfigName': order_details.get('payment_configuration', PHONE_PAYMENT_CONFIG.get(phone_number_id, DEFAULT_PAYMENT_CONFIG)),
                    'awsPhoneNumberId': phone_number_id or '',
                    'status': 'pending',
                    'senderPhone': recipient_phone or '',
                    'createdAt': Decimal(str(int(time.time()))),
                    'expiresAt': Decimal(str(int(time.time()) + 86400 * 30)),
                }
                # Store in INBOUND table — invoice generator scans WhatsAppInboundTable
                inbound_table_name = os.environ.get('INBOUND_TABLE', 'stack-wecare-digital-WhatsAppInboundTable')
                inbound_table = dynamodb.Table(inbound_table_name)
                inbound_table.put_item(Item={k: v for k, v in pay_req_record.items() if v is not None and v != '' and v != Decimal('0') or k in ('paymentDiscount', 'paymentShipping')})
                # Unified Inbox dual-write — mirror the payment_request to the canonical
                # MessagesTable so the dashboard (which reads canonical) shows payments.
                # Add `timestamp` (GSI sort key) so it's queryable via channel/contactId index.
                try:
                    _canon = dict(pay_req_record)
                    _canon['timestamp'] = _canon.get('createdAt') or Decimal(str(int(time.time())))
                    dynamodb.Table(
                        os.environ.get('UNIFIED_MESSAGES_TABLE', 'stack-wecare-digital-MessagesTable')
                    ).put_item(Item={k: v for k, v in _canon.items() if v is not None and v != '' and v != Decimal('0') or k in ('paymentDiscount', 'paymentShipping')})
                except Exception as _ce:
                    logger.warning(f'payment_request canonical mirror skipped: {_ce}')
                logger.info(json.dumps({
                    'event': 'payment_request_record_stored',
                    'referenceId': payment_ref_id,
                    'contactId': contact_id,
                    'requestId': request_id,
                }))
            except Exception as pr_err:
                logger.warning(json.dumps({
                    'event': 'payment_request_record_error',
                    'referenceId': payment_ref_id,
                    'error': str(pr_err),
                    'requestId': request_id,
                }))
        
        logger.info(json.dumps({
            'event': 'message_sent',
            'messageId': message_id,
            'whatsappMessageId': whatsapp_message_id,
            'contactId': contact_id,
            'isTemplate': is_template,
            'hasMedia': bool(whatsapp_media_id),
            'requestId': request_id
        }))
        
        # Requirement 14.4: Emit success metric
        _emit_delivery_metric('success', is_template)
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE'
            })
        }
        
    except urllib.error.HTTPError as e:
        # Handle Meta API HTTP errors. Parse the Meta error envelope so we capture
        # the specific error CODE (e.g. 131047, 131026, 131009) + message and store
        # them on the failed message for a UI tooltip explaining the reason.
        error_body = e.read().decode('utf-8') if e.fp else ''
        http_code = e.code
        meta_code = None
        meta_message = ''
        meta_details = ''
        try:
            parsed = json.loads(error_body) if error_body else {}
            err_obj = parsed.get('error', {}) if isinstance(parsed, dict) else {}
            meta_code = err_obj.get('code')
            meta_message = err_obj.get('message', '') or ''
            meta_details = (err_obj.get('error_data', {}) or {}).get('details', '') or ''
        except (json.JSONDecodeError, AttributeError):
            pass

        is_throttled = http_code == 429 or meta_code in (4, 80007, 130429, 131056) or 'throttl' in error_body.lower()

        logger.error(json.dumps({
            'event': 'send_meta_error',
            'messageId': message_id,
            'httpCode': http_code,
            'metaCode': meta_code,
            'metaMessage': meta_message,
            'metaDetails': meta_details,
            'requestId': request_id,
        }))

        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=content,
            status='failed',
            is_template=is_template,
            error_details={
                'type': 'throttling' if is_throttled else 'meta_error',
                'code': meta_code,
                'message': meta_message or error_body[:500],
                'details': meta_details,
            },
            error_code=meta_code,
            phone_number_id=phone_number_id,
            recipient_bsuid=recipient_bsuid,
        )
        _emit_delivery_metric('failed', is_template)
        if is_throttled:
            return _error_response(429, 'API rate limit exceeded')
        return _error_response(
            400,
            f'WhatsApp error {meta_code}: {meta_message}' if meta_code else f'Failed to send message: HTTP {http_code}',
            message=meta_details or None,
        )
        
    except Exception as e:
        # Requirement 5.10: Store error details
        error_msg = str(e)
        error_type = type(e).__name__
        
        logger.error(json.dumps({
            'event': 'send_api_error',
            'messageId': message_id,
            'error': error_msg,
            'errorType': error_type,
            'recipientPhone': recipient_phone,
            'normalizedPhone': message_payload.get('to') if 'message_payload' in locals() else 'unknown',
            'requestId': request_id
        }))
        
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=content,
            status='failed',
            error_details={'type': error_type, 'message': error_msg},
            phone_number_id=phone_number_id
        )
        # Emit failure metric
        _emit_delivery_metric('failed', is_template)
        return _error_response(500, f'Failed to send message: {error_msg}')


def _public_media_folder(media_type: str) -> str:
    """Map a media type/category to its public wa-tpl/ subfolder.

    Accepts either a generic category ('image'/'video'/'document'/'audio'/
    'sticker') or a full MIME ('application/pdf', 'image/png', ...).
    """
    folders = {
        'image': 'img', 'video': 'vid', 'document': 'docs',
        'audio': 'aud', 'sticker': 'stk',
    }
    mt = (media_type or '').lower()
    if mt in folders:
        return folders[mt]
    if mt == 'image/webp':
        return 'stk'
    prefix = mt.split('/')[0] if '/' in mt else mt
    return folders.get(prefix, 'docs')


# Meta WhatsApp Cloud API media size limits, by public folder (bytes).
# Source: WhatsApp Business Platform "Supported Media Types".
_WA_MEDIA_MAX_SIZES = {
    'docs': 100 * 1024 * 1024,  # 100 MB
    'img': 5 * 1024 * 1024,     # 5 MB
    'vid': 16 * 1024 * 1024,    # 16 MB
    'aud': 16 * 1024 * 1024,    # 16 MB
    'stk': 500 * 1024,          # 500 KB
}


def _wa_media_max_size(media_type: str) -> int:
    """Return Meta's max upload size (bytes) for the given media type/category."""
    return _WA_MEDIA_MAX_SIZES.get(_public_media_folder(media_type), 100 * 1024 * 1024)


def _get_media_upload_url(body: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """
    Generate a presigned S3 PUT URL so the browser can upload media directly to S3,
    bypassing the API Gateway (10MB) and Lambda (6MB) request-payload limits.

    Request body: { "action": "getUploadUrl", "mediaType": "<mime>", "filename": "<name>", "reuse": <bool> }
    Response:     { "uploadUrl": "<presigned PUT>", "s3Key": "<key>", "contentType": "<mime>", "publicUrl": "<cdn url>", "expiresIn": 300 }

    By default the s3Key is placed under MEDIA_PREFIX (private) so that _upload_media's
    is_s3_key detection picks it up when /whatsapp/send is subsequently called with
    mediaFile=s3Key.

    When reuse=True (or target="public"), the file is placed in the public, reusable
    template-attachment folder (PUBLIC_MEDIA_PREFIX/{folder}/) and a stable CloudFront
    URL is returned as publicUrl. Passing that URL as a template header link lets
    WhatsApp fetch the file directly (correct content type for every attachment type)
    and lets the same attachment be re-sent across many templates without re-uploading.
    """
    try:
        media_type = (body.get('mediaType') or '').strip()
        filename = (body.get('filename') or body.get('mediaFileName') or '').strip()
        reuse = bool(body.get('reuse')) or (body.get('target') == 'public')

        # Resolve a sane content type + extension
        content_type = _get_content_type(media_type) if media_type else 'application/octet-stream'
        extension = _get_media_extension(media_type) if media_type else ''
        if not extension and '.' in filename:
            extension = '.' + filename.rsplit('.', 1)[-1].lower()

        short_id = uuid.uuid4().hex[:8]
        if reuse:
            # Public reusable folder, keeping the original filename so document
            # headers show a meaningful name to the recipient.
            folder = _public_media_folder(media_type)
            safe_filename = ''.join(
                c if c.isalnum() or c in '._-' else '_' for c in filename
            ) if filename else ''
            if safe_filename:
                s3_key = f"{PUBLIC_MEDIA_PREFIX}{folder}/wecare-digital-{short_id}_{safe_filename}"
            else:
                s3_key = f"{PUBLIC_MEDIA_PREFIX}{folder}/wecare-digital-{short_id}{extension or '.bin'}"

            # Hard server-side size guard: a presigned POST with a
            # content-length-range condition makes S3 ITSELF reject any upload
            # over Meta's per-type limit (the browser uploads directly, so this
            # is the only place the size can be enforced server-side).
            max_size = _wa_media_max_size(media_type)
            presigned_post = s3.generate_presigned_post(
                Bucket=MEDIA_BUCKET,
                Key=s3_key,
                Fields={
                    'Content-Type': content_type,
                    'Cache-Control': 'public, max-age=31536000',
                },
                Conditions=[
                    {'Content-Type': content_type},
                    {'Cache-Control': 'public, max-age=31536000'},
                    ['content-length-range', 1, max_size],
                ],
                ExpiresIn=300,  # 5 minutes
            )

            logger.info(json.dumps({
                'event': 'media_upload_post_generated',
                's3Key': s3_key,
                'mediaType': media_type,
                'contentType': content_type,
                'maxSize': max_size,
                'requestId': request_id,
            }))

            return {
                'statusCode': 200,
                'headers': cors_headers(origin),
                'body': json.dumps({
                    'uploadMethod': 'POST',
                    'uploadUrl': presigned_post['url'],
                    'fields': presigned_post['fields'],
                    's3Key': s3_key,
                    'contentType': content_type,
                    # Stable public CDN URL — pass as a template header link to
                    # send without re-uploading to Meta, and reuse across sends.
                    'publicUrl': f"https://{CDN_DOMAIN}/{s3_key}",
                    'maxSize': max_size,
                    'expiresIn': 300,
                })
            }

        # Private path (default): presigned PUT into MEDIA_PREFIX.
        s3_key = f"{MEDIA_PREFIX}wecare-digital-{short_id}{extension or '.bin'}"

        upload_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': MEDIA_BUCKET,
                'Key': s3_key,
                'ContentType': content_type,
            },
            ExpiresIn=300,  # 5 minutes
        )

        logger.info(json.dumps({
            'event': 'media_upload_url_generated',
            's3Key': s3_key,
            'mediaType': media_type,
            'contentType': content_type,
            'requestId': request_id,
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'uploadMethod': 'PUT',
                'uploadUrl': upload_url,
                's3Key': s3_key,
                'contentType': content_type,
                'publicUrl': None,
                'expiresIn': 300,
            })
        }
    except Exception as e:
        logger.error(json.dumps({
            'event': 'media_upload_url_error',
            'error': str(e),
            'errorType': type(e).__name__,
            'requestId': request_id,
        }))
        return _error_response(500, f'Failed to generate upload URL: {str(e)}')


# Warm-instance cache: input S3 key + phone → WhatsApp media id, so a bulk run
# re-uses a single upload instead of re-uploading the same file per recipient.
_media_id_cache: Dict[str, Tuple[str, str, str, float]] = {}
MEDIA_ID_CACHE_TTL = 600  # 10 minutes


def _upload_media(media_file: str, media_type: str, message_id: str, phone_number_id: str, request_id: str, filename: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Upload media to S3 and register with WhatsApp.
    Supports all WhatsApp media types per Meta documentation.
    Requirements 5.5, 5.6, 5.7
    
    Returns: (s3_key, whatsapp_media_id, display_filename)
    """
    import base64
    
    try:
        # Bulk optimization: reuse a previously-uploaded media id for the same
        # S3 key + phone within the TTL (skips re-download + re-upload per send).
        if media_file and len(media_file) < 512:
            _ck = f"{media_file}|{phone_number_id}"
            _hit = _media_id_cache.get(_ck)
            if _hit and (time.time() - _hit[3]) < MEDIA_ID_CACHE_TTL:
                logger.info(json.dumps({'event': 'media_id_cache_hit', 'requestId': request_id}))
                return _hit[0], _hit[1], _hit[2]
        # Generate S3 key with proper extension
        extension = _get_media_extension(media_type)
        
        # S3 key: short format wecare-digital-{8char_uuid}{ext}
        short_id = message_id[:8]
        s3_key = f"{MEDIA_PREFIX}wecare-digital-{short_id}{extension}"
        
        # Display filename for WhatsApp (max 240 chars) - use original name if valid
        display_filename = None
        if filename and filename.strip() and filename not in ['undefined', 'null', 'File', 'Blob']:
            display_filename = _sanitize_filename(filename, max_length=240)
        
        # If no valid filename, generate one
        if not display_filename or display_filename == 'document':
            display_filename = f"wecare-digital-{short_id}{extension}"
        
        logger.info(json.dumps({
            'event': 'media_upload_start',
            'messageId': message_id,
            'mediaType': media_type,
            'providedFilename': filename,
            'displayFilename': display_filename,
            's3Key': s3_key,
            'requestId': request_id
        }))
        
        # If media_file is already an S3 key, use it directly
        # Detect S3 keys: s3:// prefix, media prefix, invoices/ prefix, or any path with / that isn't base64
        is_s3_key = (
            media_file.startswith('s3://') or
            media_file.startswith(MEDIA_PREFIX) or
            media_file.startswith('stack/') or
            media_file.startswith('stream/') or
            (('/' in media_file) and media_file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.pdf', '.ogg', '.mp3')))
        )
        if is_s3_key:
            s3_key = media_file.replace('s3://', '').replace(f'{MEDIA_BUCKET}/', '')
            
            # Get file size from S3 for validation
            try:
                head_response = s3.head_object(Bucket=MEDIA_BUCKET, Key=s3_key)
                file_size = head_response.get('ContentLength', 0)
                is_valid, error_msg = _validate_media_size(file_size, media_type)
                if not is_valid:
                    logger.error(json.dumps({
                        'event': 'media_size_validation_failed',
                        's3Key': s3_key,
                        'fileSize': file_size,
                        'error': error_msg,
                        'requestId': request_id
                    }))
                    return None, None, None
            except Exception as e:
                logger.warning(f"Could not validate S3 file size: {str(e)}")
        else:
            # Assume base64 encoded - decode and upload
            try:
                file_content = base64.b64decode(media_file)
            except Exception as e:
                logger.error(json.dumps({
                    'event': 'media_decode_error',
                    'error': str(e),
                    'mediaType': media_type,
                    'requestId': request_id
                }))
                return None, None, None
            
            # Validate file size
            file_size = len(file_content)
            is_valid, error_msg = _validate_media_size(file_size, media_type)
            if not is_valid:
                logger.error(json.dumps({
                    'event': 'media_size_validation_failed',
                    'fileSize': file_size,
                    'error': error_msg,
                    'requestId': request_id
                }))
                return None, None, None
            
            logger.info(json.dumps({
                'event': 'media_uploading_to_s3',
                's3Key': s3_key,
                'fileSize': file_size,
                'mediaType': media_type,
                'requestId': request_id
            }))
            
            # Upload to S3 using streaming for large files
            s3.put_object(
                Bucket=MEDIA_BUCKET,
                Key=s3_key,
                Body=file_content,
                ContentType=_get_content_type(media_type)
            )
        
        logger.info(json.dumps({
            'event': 'media_uploaded_to_s3',
            's3Key': s3_key,
            'mediaType': media_type,
            'displayFilename': display_filename,
            'requestId': request_id
        }))
        
        # Requirement 5.6: Call PostWhatsAppMessageMedia to get mediaId
        # All phones use Direct Meta API
        try:
            import hmac as _hmac, hashlib as _hashlib
            obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=s3_key)
            media_bytes = obj['Body'].read()
            # Resolve the MIME type Meta will see. Prefer the validated mapping derived
            # from media_type (prevents error 131053 "mismatched media type"); fall back to
            # the S3 object's stored ContentType, then to extension-based guess.
            validated_ct = _get_content_type(media_type)
            s3_ct = (obj.get('ContentType') or '').strip()
            # media_type may be a generic category ('document'/'image'/'video'/
            # 'audio') OR a full MIME ('application/pdf'). For a generic category
            # _get_content_type only yields a *default* (document→application/pdf,
            # image→image/jpeg, video→video/mp4), which is WRONG for non-default
            # files (DOCX/XLSX/PPTX/TXT documents, PNG images, 3GP videos) and
            # makes Meta reject the upload with error 131053 (mismatched media
            # type). In that case trust the file's real stored S3 ContentType,
            # which was set correctly when the file was uploaded.
            is_generic_type = '/' not in (media_type or '')
            if is_generic_type and s3_ct and s3_ct != 'application/octet-stream':
                content_type = s3_ct
            elif validated_ct and validated_ct != 'application/octet-stream':
                content_type = validated_ct
            elif s3_ct and s3_ct != 'application/octet-stream':
                content_type = s3_ct
            else:
                # Last resort: infer from the S3 key extension
                ext_ct = _get_content_type('image' if s3_key.lower().endswith(('.jpg', '.jpeg', '.png'))
                                           else s3_key.rsplit('.', 1)[-1] if '.' in s3_key else '')
                content_type = ext_ct if ext_ct != 'application/octet-stream' else (s3_ct or 'application/octet-stream')
            
            if 'token' not in _direct_api_cache:
                resp = secrets_client.get_secret_value(SecretId='wecare/meta-system-user-token')
                data = json.loads(resp['SecretString'])
                _direct_api_cache['token'] = (data.get('access_token') or '').strip()
                _direct_api_cache['app_secret'] = (data.get('app_secret') or '').strip()
            
            token = _direct_api_cache['token']
            app_secret = _direct_api_cache['app_secret']
            meta_phone_id = DIRECT_API_META_PHONE_MAP.get(phone_number_id, '')
            url = f"https://graph.facebook.com/{META_API_VERSION}/{meta_phone_id}/media"
            if app_secret:
                proof = _hmac.new(app_secret.encode(), token.encode(), _hashlib.sha256).hexdigest()
                url = f"{url}?appsecret_proof={proof}"
            
            boundary = 'wecareupload'
            body = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="messaging_product"\r\n\r\nwhatsapp\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\n{content_type}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{display_filename or "file"}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n'
            ).encode() + media_bytes + f'\r\n--{boundary}--\r\n'.encode()
            
            import urllib.request as _ur
            req = _ur.Request(url, data=body, headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': f'multipart/form-data; boundary={boundary}'
            }, method='POST')
            with _ur.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
            whatsapp_media_id = result.get('id', '')
            
            if not whatsapp_media_id:
                logger.error(json.dumps({
                    'event': 'media_registration_no_id',
                    's3Key': s3_key,
                    'response': str(result),
                    'requestId': request_id
                }))
                return None, None, None

            # Cache for bulk reuse (same S3 key + phone within TTL).
            if media_file and len(media_file) < 512:
                _media_id_cache[f"{media_file}|{phone_number_id}"] = (
                    s3_key, whatsapp_media_id, display_filename, time.time()
                )
            
            logger.info(json.dumps({
                'event': 'media_registered_with_whatsapp',
                's3Key': s3_key,
                'mediaId': whatsapp_media_id,
                'mediaType': media_type,
                'displayFilename': display_filename,
                'phoneNumberId': phone_number_id,
                'requestId': request_id
            }))
            
        except Exception as e:
            logger.error(json.dumps({
                'event': 'media_registration_failed',
                'error': str(e),
                'errorType': type(e).__name__,
                's3Key': s3_key,
                'phoneNumberId': phone_number_id,
                'requestId': request_id
            }))
            # Media registration failed - cannot send media without mediaId
            return None, None, None
        
        logger.info(json.dumps({
            'event': 'media_upload_complete',
            's3Key': s3_key,
            'mediaId': whatsapp_media_id,
            'mediaType': media_type,
            'displayFilename': display_filename,
            'requestId': request_id
        }))
        
        return s3_key, whatsapp_media_id, display_filename
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'media_upload_error',
            'error': str(e),
            'errorType': type(e).__name__,
            'mediaType': media_type,
            'requestId': request_id
        }))
        return None, None, None


def _sanitize_filename(filename: str, max_length: int = 240) -> str:
    """
    Sanitize filename for WhatsApp document messages.
    
    WhatsApp filename requirements:
    - Maximum 240 characters
    - Remove invalid characters but preserve common ones
    - Preserve file extension
    
    Args:
        filename: Original filename
        max_length: Maximum allowed length (default 240 for WhatsApp)
    
    Returns:
        Sanitized filename
    """
    if not filename or not isinstance(filename, str):
        return 'document'
    
    # Handle placeholder values
    if filename.strip() in ['undefined', 'null', 'File', 'Blob', '']:
        return 'document'
    
    # Remove path separators if present
    filename = filename.split('/')[-1].split('\\')[-1]
    
    # Remove only truly invalid characters for WhatsApp
    # Keep: alphanumeric, dots, hyphens, underscores, spaces, parentheses
    import re
    sanitized = re.sub(r'[^\w\s.\-()]+', '', filename, flags=re.UNICODE)
    
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # Strip leading/trailing spaces
    sanitized = sanitized.strip()
    
    # If filename is too long, truncate while preserving extension
    if len(sanitized) > max_length:
        # Split filename and extension
        if '.' in sanitized:
            name_parts = sanitized.rsplit('.', 1)
            name = name_parts[0]
            ext = '.' + name_parts[1]
        else:
            name = sanitized
            ext = ''
        
        # Calculate how much space we have for the name
        available_length = max_length - len(ext)
        
        # Truncate name and reconstruct
        sanitized = name[:available_length] + ext
    
    # Ensure we have a valid filename
    if not sanitized or sanitized.isspace():
        sanitized = 'document'
    
    logger.info(json.dumps({
        'event': 'filename_sanitized',
        'original': filename,
        'sanitized': sanitized,
        'length': len(sanitized),
        'maxLength': max_length,
        'changed': filename != sanitized
    }))
    
    return sanitized


def _normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number to WhatsApp-compatible E.164 format.
    WhatsApp requires: digits only, no + prefix, with country code.
    
    Examples:
    - "+919876543210" -> "919876543210"
    - "919876543210" -> "919876543210"
    - "+91 98765 43210" -> "919876543210"
    - "9876543210" -> "919876543210" (assumes India)
    - "447447840003" -> "447447840003"
    - "+44 7447 840003" -> "447447840003"
    """
    if not phone:
        return phone
    
    # Remove all non-digit characters (spaces, dashes, +, etc.)
    digits_only = ''.join(c for c in phone if c.isdigit())
    
    # If empty after removing non-digits, return original
    if not digits_only:
        return phone
    
    # If 10 digits and starts with 6-9, assume Indian number
    if len(digits_only) == 10 and digits_only[0] in '6789':
        digits_only = '91' + digits_only
    
    # If 11 digits starting with 0, remove leading 0 and add country code
    if len(digits_only) == 11 and digits_only[0] == '0':
        digits_only = '91' + digits_only[1:]
    
    # If 12 digits starting with 0091, remove leading 00
    if len(digits_only) == 12 and digits_only.startswith('0091'):
        digits_only = digits_only[2:]
    
    # Validate final format: should be 10-15 digits (E.164 format)
    if not digits_only.isdigit() or len(digits_only) < 10 or len(digits_only) > 15:
        logger.warning(f"Phone number after normalization is invalid: {phone} -> {digits_only} (length: {len(digits_only)})")
    
    return digits_only


def _sanitize_reference_id(reference_id: str) -> str:
    """
    Sanitize reference_id for UPI compatibility.
    UPI requires: only A-Z, a-z, 0-9, _, - (max 35 chars)
    Must be unique for each transaction.
    
    Format: WD-PAY-<ID> (dash-separated, type-prefixed)
    
    Examples:
    - "WD-PAY-ABC12345" -> "WD-PAY-ABC12345" (keep as-is)
    - "WD_ABC12345" -> "WD-PAY-ABC12345" (upgrade old format)
    - "WDABC12345" -> "WD-PAY-ABC12345" (upgrade old format)
    - "WD-PAY-WD-PAY-ABC" -> "WD-PAY-ABC" (remove duplicate prefix)
    - "" -> "WD-PAY-XXXXXXXX" (auto-generated)
    """
    import re
    
    if not reference_id or not reference_id.strip():
        # Generate unique reference if empty
        unique_id = str(uuid.uuid4()).replace('-', '')[:8].upper()
        return f"WD-PAY-{unique_id}"
    
    stripped = reference_id.strip().upper()
    
    # Remove duplicate WD-PAY- prefixes
    while 'WD-PAY-WD-PAY-' in stripped:
        stripped = stripped.replace('WD-PAY-WD-PAY-', 'WD-PAY-')
    
    # Already in new format
    if stripped.startswith('WD-PAY-'):
        result = stripped
    elif stripped.startswith('WD-ORD-'):
        # Order prefix — leave as-is
        result = stripped
    else:
        # Old format: strip old WD prefix and non-alnum, then add WD-PAY-
        cleaned = re.sub(r'[^A-Za-z0-9]', '', stripped)
        # Remove legacy WD prefix(es)
        while cleaned.startswith('WD'):
            cleaned = cleaned[2:]
        if not cleaned:
            unique_id = str(uuid.uuid4()).replace('-', '')[:8].upper()
            cleaned = unique_id
        result = f"WD-PAY-{cleaned}"
    
    # Truncate to max 35 chars (UPI limit)
    if len(result) > 35:
        result = result[:35]
    
    return result


def _build_message_payload(recipient_phone: str, content: str, media_type: Optional[str],
                           media_id: Optional[str], is_template: bool, template_name: Optional[str],
                           template_params: list, filename: Optional[str] = None,
                           is_payment_template: bool = False, order_details: Optional[Dict] = None,
                           header_image_url: Optional[str] = None,
                           is_interactive_payment: bool = False,
                           is_otp_template: bool = False, otp_code: Optional[str] = None,
                           otp_button_type: Optional[str] = None,
                           phone_number_id: Optional[str] = None,
                           recipient_bsuid: Optional[str] = None,
                           template_header_media: Optional[str] = None,
                           template_header_type: Optional[str] = None,
                           template_header_filename: Optional[str] = None,
                           template_header_location: Optional[Dict] = None,
                           template_flow_button: Optional[Dict] = None,
                           context_message_id: Optional[str] = None) -> Dict[str, Any]:
    """Build WhatsApp Cloud API message payload. Supports BSUID recipient."""
    # Normalize phone number - WhatsApp API expects digits only without + prefix
    formatted_phone = _normalize_phone_number(recipient_phone) if recipient_phone else ''
    
    # Validate phone number format (skip if sending to BSUID only)
    if formatted_phone and (not formatted_phone.isdigit() or len(formatted_phone) < 10):
        logger.warning(f"Invalid phone number after normalization: {recipient_phone} -> {formatted_phone}")
    
    # WhatsApp requires + prefix with country code in the message payload
    whatsapp_phone = f"+{formatted_phone}" if formatted_phone else ''
    
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
    }
    
    # Support both phone number and BSUID recipients (per Meta BSUID docs)
    # If both provided, 'to' (phone) takes precedence
    if whatsapp_phone:
        payload['to'] = whatsapp_phone
    if recipient_bsuid:
        payload['recipient'] = recipient_bsuid
    # Fallback: at least one must be set
    if not whatsapp_phone and not recipient_bsuid:
        payload['to'] = whatsapp_phone  # Will fail at API level with clear error
    
    # Default header image for interactive payments
    DEFAULT_PAYMENT_HEADER_IMAGE = 'https://app.wecare.digital/stream/media/m/wecare-digital.png'
    
    # Handle INTERACTIVE order_details message (for within 24h window)
    # Structure:
    # BODY: Your payment is overdue—please tap below to complete it 💳🤝
    # CART ITEMS: from input items array
    # BREAKDOWN: Subtotal, Discount, Shipping, Tax (with GSTIN)
    # TOTAL: auto-calculated
    if is_interactive_payment and order_details:
        from decimal import Decimal, ROUND_HALF_UP
        
        def round_paise(x: Decimal) -> int:
            """Round to nearest paise"""
            return int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        
        payload['type'] = 'interactive'
        
        # Use provided header image or default
        payment_header_image = header_image_url or DEFAULT_PAYMENT_HEADER_IMAGE
        
        # Get order components from frontend
        order_data = order_details.get('order', {})
        
        # GSTIN
        gstin = order_details.get('gstin', '19AADFW7431N1ZK')
        
        # Discount, Delivery (user input, mandatory - show even if 0)
        discount_paise = int(order_data.get('discount', {}).get('value', 0))
        delivery_paise = int(order_data.get('shipping', {}).get('value', 0))
        
        # Build items from input array (multi-item support with per-item GST)
        items_list = order_data.get('items', [])
        items_for_whatsapp = []
        item_total_paise = 0
        gst_paise = 0  # Total GST across all items
        
        for i, item in enumerate(items_list):
            item_amount = int(item.get('amount', {}).get('value', 100))
            item_qty = int(item.get('quantity', 1))
            item_name = item.get('name', 'Service Fee')
            item_line_total = item_amount * item_qty
            item_total_paise += item_line_total
            
            # Per-item GST rate
            item_gst_rate = float(item.get('gstRate', 0))
            if item_gst_rate > 0:
                gst_paise += round_paise(Decimal(item_line_total) * Decimal(str(item_gst_rate)) / Decimal("100"))
            
            items_for_whatsapp.append({
                'retailer_id': item.get('retailer_id', f'ITEM_{i+1}'),
                'name': item_name,
                'amount': {'value': item_amount, 'offset': 100},
                'quantity': item_qty,
                'country_of_origin': 'India',
                'importer_name': 'WECARE.DIGITAL',
                'importer_address': {
                    'address_line1': '81/2/7 Phears Ln',
                    'city': 'Kolkata',
                    'zone_code': 'WB',
                    'postal_code': '700012',
                    'country_code': 'IN',
                },
            })
        
        # Fallback if no items
        if not items_for_whatsapp:
            item_name = order_details.get('itemName', 'Service Fee')
            item_quantity = int(order_details.get('quantity', 1))
            fallback_amount = int(order_data.get('subtotal', {}).get('value', 100))
            item_total_paise = fallback_amount
            items_for_whatsapp.append({
                'retailer_id': 'ITEM_MAIN',
                'name': item_name,
                'amount': {'value': fallback_amount // max(item_quantity, 1), 'offset': 100},
                'quantity': item_quantity,
                'country_of_origin': 'India',
                'importer_name': 'WECARE.DIGITAL',
                'importer_address': {'address_line1': '81/2/7 Phears Ln', 'city': 'Kolkata', 'zone_code': 'WB', 'postal_code': '700012', 'country_code': 'IN'},
            })
            # Use tax value from order_data as fallback
            gst_paise = int(order_data.get('tax', {}).get('value', 0))
        
        # Convenience Fee: configurable rate (default 2%) + GST on that rate (default 18%)
        # Can be overridden per-order via convenienceFeeRate and convenienceFeeGstRate
        conv_fee_rate = Decimal(str(order_details.get('convenienceFeeRate', '0.02')))
        conv_fee_gst_rate = Decimal(str(order_details.get('convenienceFeeGstRate', '0.18')))
        skip_conv_fee = order_details.get('skipConvenienceFee', False)

        if not skip_conv_fee and conv_fee_rate > 0:
            collection_paise = item_total_paise + gst_paise
            conv_base = round_paise(Decimal(collection_paise) * conv_fee_rate)
            conv_gst = round_paise(Decimal(conv_base) * conv_fee_gst_rate)
            conv_total = conv_base + conv_gst
        else:
            conv_total = 0
        
        # Add convenience fee as a line item (only if > 0)
        if conv_total > 0:
            items_for_whatsapp.append({
                'retailer_id': 'ITEM_CONV',
                'name': 'Convenience Fee (Collected by Bank)',
                'amount': {'value': conv_total, 'offset': 100},
                'quantity': 1,
                'country_of_origin': 'India',
                'importer_name': 'WECARE.DIGITAL',
                'importer_address': {'address_line1': '81/2/7 Phears Ln', 'city': 'Kolkata', 'zone_code': 'WB', 'postal_code': '700012', 'country_code': 'IN'},
            })
        
        # Build reference ID
        ref_id = _sanitize_reference_id(order_details.get('reference_id', ''))
        
        # WhatsApp subtotal = sum of (item.amount * item.quantity) for all items
        whatsapp_subtotal = item_total_paise + conv_total
        
        total_paise = whatsapp_subtotal - discount_paise + delivery_paise + gst_paise
        
        # Build order object - ALL fields mandatory (show even if 0)
        # WhatsApp only supports: subtotal, discount, shipping, tax
        order_obj = {
            'status': 'pending',
            'items': items_for_whatsapp,
            'subtotal': {'value': whatsapp_subtotal, 'offset': 100},
            'discount': {
                'value': discount_paise,
                'offset': 100,
                'description': order_data.get('discount', {}).get('description', 'Promo')
            },
            'shipping': {
                'value': delivery_paise,
                'offset': 100,
                'description': order_data.get('shipping', {}).get('description', 'Express')
            },
            'tax': {
                'value': gst_paise,
                'offset': 100,
                'description': f'GSTIN: {gstin}'
            }
        }

        # Gap 8: quick_pay — hides "Review and Pay", shows only "Pay Now" button
        if order_details.get('quick_pay', False):
            order_obj['type'] = 'quick_pay'
        
        # Build interactive order_details payload
        goods_type = order_details.get('type', 'digital-goods')
        
        # Order expiration: default 24h from now (Meta minimum: 300 seconds)
        import time as _time
        expiration_seconds = int(order_details.get('expiration_seconds', 86400))  # default 24h
        if expiration_seconds < 300:
            expiration_seconds = 300  # Meta minimum threshold
        expiration_ts = str(int(_time.time()) + expiration_seconds)
        expiration_desc = order_details.get('expiration_description', 'This payment link will expire in 24 hours')
        
        order_obj['expiration'] = {
            'timestamp': expiration_ts,
            'description': expiration_desc[:120],  # Meta max 120 chars
        }
        
        action_params = {
            'reference_id': ref_id,
            'type': goods_type,
            'payment_settings': _build_payment_settings(phone_number_id, order_details),
            'currency': order_details.get('currency', 'INR'),
            'total_amount': {'value': total_paise, 'offset': 100},
            'order': order_obj
        }
        
        # Merchant preferred UPI app + payment options (only for PG deep integration mode)
        ps = action_params['payment_settings'][0]
        if 'payment_gateway' in ps:
            preferred_upi_app = order_details.get('preferred_upi_app', '')
            if preferred_upi_app:
                ps['payment_gateway']['preferred_payment_methods'] = [
                    {'method': preferred_upi_app}
                ]
            
            # Restrict payment options: "upi" or "web" (optional)
            # UPI transactions limited to ₹5,00,000 — auto-switch to web for higher amounts
            enabled_options = order_details.get('enabled_payment_options', '')
            if total_paise > 50000000:  # > ₹5,00,000 in paise
                enabled_options = 'web'
            if enabled_options:
                ps['payment_gateway']['enabled_payment_options'] = [enabled_options]

        # For payment_link mode: add payment_type: "upi" (required by Meta)
        if 'payment_link' in ps:
            action_params['payment_type'] = 'upi'
        
        # For physical-goods: beneficiaries is REQUIRED by Meta (legal/compliance).
        # Per Meta PG docs: "Required for shipped physical-goods."
        # NOTE: shipping_info + address collection is a CHECKOUT BUTTON TEMPLATE feature
        # (requires checkout endpoint / data_exchange beta). It does NOT work with
        # interactive order_details messages. For PG deep integration, we MUST always
        # provide beneficiaries. If address is unknown, use business address as fallback.
        if goods_type == 'physical-goods':
            shipping_info = order_details.get('shipping_info', {})
            beneficiary_addr = shipping_info.get('addresses', [])

            # Try to build beneficiary from provided address
            b_name = 'Customer'
            b_addr1 = ''
            b_city = ''
            b_state = ''
            b_postal = ''

            if beneficiary_addr:
                addr = beneficiary_addr[0]
                b_name = (addr.get('name', 'Customer') or 'Customer')[:200]
                b_addr1 = addr.get('address', addr.get('address_line1', '')) or ''
                b_city = addr.get('city', '') or ''
                b_state = addr.get('state', '') or ''
                b_postal = addr.get('in_pin_code', addr.get('postal_code', '')) or ''

            if b_addr1 and b_city and b_postal:
                # Complete customer address — use it
                action_params['beneficiaries'] = [{
                    'name': b_name,
                    'address_line1': b_addr1[:100],
                    'address_line2': (beneficiary_addr[0].get('landmark_area', beneficiary_addr[0].get('address_line2', '')) if beneficiary_addr else '')[:100],
                    'city': b_city,
                    'state': b_state or b_city,
                    'country': 'India',
                    'postal_code': b_postal[:6],
                }]
            else:
                # Address unknown/incomplete — use BUSINESS address as beneficiary fallback.
                # Meta requires beneficiaries for physical-goods but says "Beneficiary
                # information isn't shown to users but is needed for legal and compliance."
                # So using business address is valid — the actual shipping address can be
                # collected separately (via chat, form, or checkout endpoint beta).
                logger.info(json.dumps({
                    'event': 'beneficiary_fallback_to_business_address',
                    'reason': 'Customer address incomplete for physical-goods',
                    'missingFields': {'address_line1': not b_addr1, 'city': not b_city, 'postal_code': not b_postal},
                    'referenceId': ref_id,
                }))
                action_params['beneficiaries'] = [{
                    'name': 'WECARE.DIGITAL',
                    'address_line1': '81/2/7 Phears Ln',
                    'address_line2': 'The W.B.S.I.D.C. Building, Unit 1/20',
                    'city': 'Kolkata',
                    'state': 'West Bengal',
                    'country': 'India',
                    'postal_code': '700012',
                }]
        
        interactive_payload = {
            'type': 'order_details',
            'header': {
                'type': 'image',
                'image': {'link': payment_header_image}
            },
            'body': {
                'text': 'Your payment is ready \u2014 tap below to complete it \U0001f4b3'
            },
            'footer': {
                'text': order_details.get('footer_text', 'WECARE.DIGITAL')
            },
            'action': {
                'name': 'review_and_pay',
                'parameters': action_params
            }
        }
        
        payload['interactive'] = interactive_payload
        
        logger.info(json.dumps({
            'event': 'interactive_payment_payload_built',
            'referenceId': ref_id,
            'goodsType': goods_type,
            'hasBeneficiaries': 'beneficiaries' in action_params,
            'itemCount': len(items_list),
            'itemTotal': item_total_paise / 100,
            'gstTotal': gst_paise / 100,
            'discount': discount_paise / 100,
            'shipping': delivery_paise / 100,
            'convFee': conv_total / 100,
            'whatsappSubtotal': whatsapp_subtotal / 100,
            'total': total_paise / 100,
            'gstin': gstin,
            'orderId': order_details.get('orderId', 'Offline'),
            'paymentConfig': order_details.get('payment_configuration', PHONE_PAYMENT_CONFIG.get(phone_number_id, DEFAULT_PAYMENT_CONFIG))
        }))
        
        return payload
    
    if is_template and template_name:
        # Template message
        # Get language from template_params if provided, otherwise default to 'en'
        template_language = 'en'
        actual_params = list(template_params) if template_params else []
        
        if actual_params and len(actual_params) > 0:
            # Check if first param is a language code (2-5 chars like 'en', 'en_US')
            first_param = actual_params[0] if actual_params else ''
            if isinstance(first_param, str) and (len(first_param) == 2 or (2 <= len(first_param) <= 5 and '_' in first_param)):
                # Looks like a language code, use it
                template_language = first_param
                actual_params = actual_params[1:]  # Remove language from params
        
        payload['type'] = 'template'
        payload['template'] = {
            'name': template_name,
            'language': {'code': template_language},
            'components': []
        }

        # Media header for standard (non-payment) templates. Must be appended
        # first so the component order is header → body → button per Meta spec.
        # Accepts a public https link OR a pre-resolved WhatsApp media id.
        if (template_header_media and not is_payment_template
                and template_header_type in ('image', 'video', 'document')):
            _is_link = str(template_header_media).startswith('http')
            _ref = {'link': template_header_media} if _is_link else {'id': template_header_media}
            if template_header_type == 'document':
                if template_header_filename:
                    _ref['filename'] = template_header_filename
                _hp = {'type': 'document', 'document': _ref}
            elif template_header_type == 'video':
                _hp = {'type': 'video', 'video': _ref}
            else:
                _hp = {'type': 'image', 'image': _ref}
            payload['template']['components'].append({'type': 'header', 'parameters': [_hp]})
            logger.info(json.dumps({
                'event': 'template_media_header_added',
                'templateName': template_name,
                'headerType': template_header_type,
                'ref': 'link' if _is_link else 'id',
                'hasFilename': bool(template_header_filename),
            }))

        # Location header for standard (non-payment) templates. Coordinates are
        # supplied at send time (latitude/longitude required; name/address optional).
        if (template_header_type == 'location' and template_header_location
                and not is_payment_template):
            _loc = {}
            for _k in ('latitude', 'longitude', 'name', 'address'):
                _v = template_header_location.get(_k)
                if _v not in (None, ''):
                    _loc[_k] = str(_v)
            if _loc.get('latitude') and _loc.get('longitude'):
                payload['template']['components'].append({
                    'type': 'header',
                    'parameters': [{'type': 'location', 'location': _loc}]
                })
                logger.info(json.dumps({
                    'event': 'template_location_header_added',
                    'templateName': template_name,
                    'hasName': bool(_loc.get('name')),
                }))
        # Handle payment template with order_details button
        if is_payment_template and order_details:
            # Add header image if provided
            if header_image_url:
                payload['template']['components'].append({
                    'type': 'header',
                    'parameters': [{
                        'type': 'image',
                        'image': {'link': header_image_url}
                    }]
                })
            
            # Add body parameters if provided (for templates with variables like {{1}})
            if actual_params and len(actual_params) > 0:
                payload['template']['components'].append({
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': str(p)} for p in actual_params]
                })
            
            # Add order_details button component
            payload['template']['components'].append({
                'type': 'button',
                'sub_type': 'order_details',
                'index': 0,
                'parameters': [{
                    'type': 'action',
                    'action': {'order_details': order_details}
                }]
            })
            
            logger.info(json.dumps({
                'event': 'payment_template_payload_built',
                'templateName': template_name,
                'language': template_language,
                'referenceId': order_details.get('reference_id'),
                'totalAmount': order_details.get('total_amount', {}).get('value'),
                'currency': order_details.get('currency'),
                'hasHeaderImage': bool(header_image_url),
                'bodyParamCount': len(actual_params)
            }))
        # OTP / Authentication template support
        # WhatsApp authentication templates use a button component with:
        # - sub_type 'url' with {{1}} OTP code parameter (URL button with OTP appended)
        # - sub_type 'copy_code' with coupon_code parameter (one-tap copy button)
        elif is_otp_template and otp_code:
            # Body params (e.g. {{1}} = OTP code for display in message body)
            if actual_params:
                payload['template']['components'].append({
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': str(p)} for p in actual_params]
                })
            
            btn_type = (otp_button_type or 'copy_code').lower()
            if btn_type == 'url':
                # URL button: OTP code appended to the template URL as {{1}}
                payload['template']['components'].append({
                    'type': 'button',
                    'sub_type': 'url',
                    'index': 0,
                    'parameters': [{'type': 'text', 'text': str(otp_code)}]
                })
            else:
                # One-tap / copy_code button: user taps to auto-fill OTP
                payload['template']['components'].append({
                    'type': 'button',
                    'sub_type': 'copy_code',
                    'index': 0,
                    'parameters': [{'type': 'coupon_code', 'coupon_code': str(otp_code)}]
                })
            
            logger.info(json.dumps({
                'event': 'otp_template_payload_built',
                'templateName': template_name,
                'language': template_language,
                'otpButtonType': btn_type,
                'bodyParamCount': len(actual_params)
            }))
        # Add body parameters if provided (for templates with variables like {{1}}, {{2}})
        # Supports both positional params (list of values) and named params (dict of name:value)
        elif actual_params and len(actual_params) > 0:
            # Check if params are named (dict) or positional (list of strings)
            if len(actual_params) == 1 and isinstance(actual_params[0], dict):
                # Named parameters: {"name": "John", "order_id": "WD-123"}
                # Convert to positional per Meta API (named params are for readability only)
                named = actual_params[0]
                payload['template']['components'].append({
                    'type': 'body',
                    'parameters': [
                        {'type': 'text', 'text': str(v), 'parameter_name': str(k)}
                        for k, v in named.items()
                    ]
                })
            else:
                payload['template']['components'].append({
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': str(p)} for p in actual_params]
                })
        
        # Flow button component — REQUIRED by Meta when the template contains a
        # FLOW button, otherwise Meta rejects the send with error 131008/131009
        # ("specify a flow button component" / "Components sub_type invalid").
        # The frontend detects the flow button in the template definition and
        # passes {index, flowToken?, flowActionData?}. NAVIGATE flows default the
        # token to "unused"; flowActionData is only needed when the target screen
        # requires input data.
        if template_flow_button and not is_payment_template and not is_otp_template:
            try:
                _fb_index = template_flow_button.get('index', 0)
                _fb_token = (template_flow_button.get('flowToken')
                             or template_flow_button.get('flow_token') or 'unused')
                _fb_action = {'flow_token': str(_fb_token)}
                _fb_data = (template_flow_button.get('flowActionData')
                            or template_flow_button.get('flow_action_data'))
                if _fb_data:
                    _fb_action['flow_action_data'] = _fb_data
                payload['template']['components'].append({
                    'type': 'button',
                    'sub_type': 'flow',
                    'index': str(_fb_index),
                    'parameters': [{'type': 'action', 'action': _fb_action}]
                })
                logger.info(json.dumps({
                    'event': 'template_flow_button_added',
                    'templateName': template_name,
                    'index': _fb_index,
                    'hasActionData': bool(_fb_data),
                }))
            except Exception as _fbe:
                logger.warning(json.dumps({
                    'event': 'template_flow_button_error',
                    'error': str(_fbe), 'templateName': template_name,
                }))

        logger.info(json.dumps({
            'event': 'template_payload_built',
            'templateName': template_name,
            'language': template_language,
            'paramCount': len(actual_params),
            'params': actual_params,
            'isPaymentTemplate': is_payment_template
        }))
    elif media_id and media_type:
        # Media message - derive WhatsApp message type from the media MIME type.
        # media_type is like 'image/jpeg', 'video/mp4', 'audio/ogg', 'application/pdf', 'image/webp'.
        mt = (media_type or '').lower().strip()

        # WebP can ONLY be sent as a sticker — Meta rejects WebP sent as an image.
        if mt in ('sticker', 'image/webp', 'application/webp') or mt.endswith('/webp'):
            msg_type = 'sticker'
        elif '/' in mt:
            prefix = mt.split('/')[0]
            # Documents have many MIME prefixes (application/, text/) → map to 'document'.
            msg_type = prefix if prefix in ('image', 'video', 'audio') else 'document'
        else:
            msg_type = mt

        # Validate media type
        valid_types = ['image', 'video', 'audio', 'document', 'sticker']
        if msg_type not in valid_types:
            logger.warning(f"Invalid media type: {media_type} -> {msg_type}, using 'document' as fallback")
            msg_type = 'document'
        
        payload['type'] = msg_type
        payload[msg_type] = {'id': media_id}
        
        # Add caption if provided. Stickers and audio do NOT support captions (Meta rejects them).
        if content and msg_type in ('image', 'video', 'document'):
            payload[msg_type]['caption'] = content
        
        # For documents, add filename if available
        # WhatsApp filename limit: 240 characters
        if msg_type == 'document' and filename:
            # Sanitize and truncate filename to 240 characters
            sanitized_filename = _sanitize_filename(filename, max_length=240)
            payload[msg_type]['filename'] = sanitized_filename
            logger.info(json.dumps({
                'event': 'document_filename_added',
                'originalFilename': filename,
                'sanitizedFilename': sanitized_filename,
                'length': len(sanitized_filename)
            }))
    else:
        # Check for special message types passed via content JSON
        try:
            content_data = json.loads(content) if content and content.startswith('{') else None
        except (json.JSONDecodeError, TypeError):
            content_data = None

        if content_data and content_data.get('_type') == 'contacts':
            # Contact card message — per WhatsApp Cloud API contacts spec
            payload['type'] = 'contacts'
            payload['contacts'] = content_data.get('contacts', [])
        elif content_data and content_data.get('_type') == 'location':
            # Location message — per WhatsApp Cloud API location spec
            payload['type'] = 'location'
            payload['location'] = {
                'latitude': str(content_data.get('latitude', 0)),
                'longitude': str(content_data.get('longitude', 0)),
            }
            if content_data.get('name'):
                payload['location']['name'] = content_data['name']
            if content_data.get('address'):
                payload['location']['address'] = content_data['address']
        elif content_data and content_data.get('_type') == 'location_request':
            # Location request message — interactive type
            payload['type'] = 'interactive'
            payload['interactive'] = {
                'type': 'location_request_message',
                'body': {'text': content_data.get('body', 'Please share your location')},
                'action': {'name': 'send_location'},
            }
        elif content_data and content_data.get('_type') == 'address':
            # Address message — interactive type
            payload['type'] = 'interactive'
            payload['interactive'] = {
                'type': 'address_message',
                'body': {'text': content_data.get('body', 'Please provide your delivery address')},
                'action': {
                    'name': 'address_message',
                    'parameters': content_data.get('parameters', {}),
                },
            }
        else:
            # Text message — enable link preview when content contains a URL
            has_url = 'http://' in content or 'https://' in content
            payload['type'] = 'text'
            payload['text'] = {'body': content, 'preview_url': has_url}
    
    # Native reply: quote the message being replied to (Meta "context" object).
    # Applies to text/media/interactive/contacts/location — set last so it covers all.
    if context_message_id:
        payload['context'] = {'message_id': context_message_id}
    
    return payload


def _get_contact(contact_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve contact from DynamoDB."""
    contacts_table = dynamodb.Table(CONTACTS_TABLE)
    
    # First try direct lookup by 'id' (primary key)
    try:
        response = contacts_table.get_item(Key={'id': contact_id})
        item = response.get('Item')
        if item and item.get('deletedAt') is None:
            return item
    except Exception as e:
        logger.warning(f"Direct lookup failed: {str(e)}")
    
    # Fallback: scan by contactId field
    try:
        response = contacts_table.scan(
            FilterExpression='contactId = :cid AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={':cid': contact_id, ':null': None},
            Limit=1
        )
        items = response.get('Items', [])
        if items:
            return items[0]
    except Exception as e:
        logger.warning(f"Scan by contactId failed: {str(e)}")
    
    return None


def _get_or_create_contact_by_phone(phone: str) -> Dict[str, Any]:
    """Look up contact by phone number, or auto-create if not found.
    Ensures outbound messages always have a valid contactId for inbox display."""
    contacts_table = dynamodb.Table(CONTACTS_TABLE)
    clean = phone.lstrip('+')
    with_plus = f'+{clean}'

    # Try GSI phone-index lookup (both formats)
    for variant in [with_plus, clean]:
        try:
            resp = contacts_table.query(
                IndexName='phone-index',
                KeyConditionExpression='phone = :p',
                ExpressionAttributeValues={':p': variant},
                Limit=5,
            )
            items = [i for i in resp.get('Items', []) if not i.get('deletedAt')]
            if items:
                contact = sorted(items, key=lambda x: x.get('createdAt', 0))[0]
                logger.info(json.dumps({
                    'event': 'contact_found_by_phone',
                    'contactId': contact.get('contactId', contact.get('id', '')),
                    'phone': phone,
                }))
                return contact
        except Exception as e:
            logger.warning(f"Phone GSI lookup failed for {variant}: {e}")

    # Fallback scan
    try:
        resp = contacts_table.scan(
            FilterExpression='(phone = :p1 OR phone = :p2) AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={':p1': clean, ':p2': with_plus, ':null': None},
            Limit=10,
        )
        items = resp.get('Items', [])
        if items:
            return sorted(items, key=lambda x: x.get('createdAt', 0))[0]
    except Exception:
        pass

    # Not found — create new contact
    contact_id = str(uuid.uuid4())
    now = int(time.time())
    contact = {
        'id': contact_id,
        'contactId': contact_id,
        'name': '',
        'phone': with_plus,
        'optInWhatsApp': True,
        'optInSms': True,
        'optInEmail': True,
        'allowlistWhatsApp': True,
        'allowlistSms': True,
        'allowlistEmail': True,
        'createdAt': Decimal(str(now)),
        'updatedAt': Decimal(str(now)),
    }
    contacts_table.put_item(Item=contact)
    logger.info(json.dumps({
        'event': 'contact_auto_created_outbound',
        'contactId': contact_id,
        'phone': with_plus,
    }))
    return contact


def _is_within_service_window(contact: Dict[str, Any]) -> bool:
    """
    Check if within 24-hour customer service window.
    Requirement 16.2: Calculate window as 24 hours from lastInboundMessageAt
    """
    last_inbound = contact.get('lastInboundMessageAt')
    if not last_inbound:
        return False
    
    # Convert to int if Decimal
    if isinstance(last_inbound, Decimal):
        last_inbound = int(last_inbound)
    elif isinstance(last_inbound, str):
        # Handle ISO format
        from datetime import datetime
        last_inbound = int(datetime.fromisoformat(last_inbound.replace('Z', '+00:00')).timestamp())
    
    window_end = last_inbound + (CUSTOMER_SERVICE_WINDOW_HOURS * 60 * 60)
    return int(time.time()) < window_end


def _check_rate_limit(phone_number_id: str) -> bool:
    """
    Check rate limit for phone number.
    Requirement 5.9: 80 messages per second per phone number
    """
    try:
        rate_table = dynamodb.Table(RATE_LIMIT_TABLE)
        now = int(time.time())
        window_key = f"whatsapp:{phone_number_id}"
        rate_id = f"{window_key}:{now}"
        
        # Atomic increment
        response = rate_table.update_item(
            Key={'id': rate_id},
            UpdateExpression='SET messageCount = if_not_exists(messageCount, :zero) + :inc, channel = :ch, windowStart = :ws, lastUpdatedAt = :now',
            ExpressionAttributeValues={
                ':zero': Decimal('0'),
                ':inc': Decimal('1'),
                ':ch': window_key,
                ':ws': str(now),
                ':now': Decimal(str(now + 86400))  # TTL: 24 hours
            },
            ReturnValues='UPDATED_NEW'
        )
        
        count = int(response.get('Attributes', {}).get('messageCount', 0))
        return count <= RATE_LIMIT_PER_SECOND
        
    except Exception:
        # Allow on error (fail open for rate limiting)
        return True


def _check_pair_rate_limit(phone_number_id: str, recipient_phone: str) -> Tuple[bool, int]:
    """
    Check per-recipient pair rate limit (Meta error 131056).
    Meta allows 1 message per 6 seconds per (sender, recipient) pair.
    Uses 4^X exponential backoff on repeated violations.
    
    Returns (allowed: bool, retry_after_seconds: int).
    """
    try:
        rate_table = dynamodb.Table(RATE_LIMIT_TABLE)
        now = int(time.time())
        pair_key = f"pair:{phone_number_id}:{recipient_phone}"
        
        response = rate_table.get_item(Key={'id': pair_key})
        item = response.get('Item')
        
        if item:
            last_sent = int(item.get('messageCount', 0))  # reuse field as last-sent timestamp
            violations = int(item.get('violations', 0))
            # Base cooldown: 6 seconds, exponential: 4^violations (capped at 4^4 = 256s)
            backoff = min(6 * (4 ** violations), 256)
            elapsed = now - last_sent
            
            if elapsed < backoff:
                retry_after = backoff - elapsed
                logger.warning(json.dumps({
                    'event': 'pair_rate_limit_hit',
                    'pair': pair_key,
                    'elapsed': elapsed,
                    'backoff': backoff,
                    'violations': violations,
                    'retryAfter': retry_after,
                }))
                return False, retry_after
        
        # Update last-sent timestamp, reset violations on success
        rate_table.put_item(Item={
            'id': pair_key,
            'channel': pair_key,
            'windowStart': 'pair',
            'messageCount': Decimal(str(now)),
            'violations': Decimal('0'),
            'lastUpdatedAt': Decimal(str(now + 86400)),
        })
        return True, 0
        
    except Exception as e:
        logger.warning(f'Pair rate limit check failed: {e}')
        return True, 0  # Fail open


def _record_pair_rate_violation(phone_number_id: str, recipient_phone: str) -> None:
    """Record a pair rate limit violation (called when Meta returns 131056)."""
    try:
        rate_table = dynamodb.Table(RATE_LIMIT_TABLE)
        now = int(time.time())
        pair_key = f"pair:{phone_number_id}:{recipient_phone}"
        
        rate_table.update_item(
            Key={'id': pair_key},
            UpdateExpression='SET violations = if_not_exists(violations, :zero) + :inc, messageCount = :now, channel = :ch, windowStart = :ws, lastUpdatedAt = :ttl',
            ExpressionAttributeValues={
                ':zero': Decimal('0'),
                ':inc': Decimal('1'),
                ':now': Decimal(str(now)),
                ':ch': pair_key,
                ':ws': 'pair',
                ':ttl': Decimal(str(now + 86400)),
            },
        )
    except Exception as e:
        logger.warning(f'Pair rate violation record failed: {e}')


def _store_message_record(message_id: str, contact_id: str, content: str, status: str,
                          is_template: bool = False, whatsapp_message_id: str = None,
                          media_id: str = None, s3_key: str = None,
                          error_details: Dict = None, phone_number_id: str = None,
                          payment_reference_id: str = None, payment_amount: float = None,
                          recipient_bsuid: str = None, media_url: str = None,
                          error_code: int = None) -> None:
    """Store message record in DynamoDB with WABA tracking."""
    now = int(time.time())
    expires_at = now + MESSAGE_TTL_SECONDS
    
    # Guard: don't store messages with empty content (prevents blank inbox entries).
    # Templates are exempt — they carry no free-form content but must still appear
    # in the conversation thread.
    if not content and not media_id and not s3_key and not media_url and status != 'failed' and not is_template:
        logger.warning(json.dumps({
            'event': 'empty_content_skipped',
            'messageId': message_id,
            'contactId': contact_id,
            'status': status,
        }))
        return

    # Templates with no preview content fall back to a readable label.
    if is_template and not content:
        content = '[Template message]'
    
    # Determine messageType: image/video/audio/document if media present, else template/text.
    # media_url covers template header media (a public link) so sent attachments
    # render in the inbox thread, not just a generic "template" label.
    _media_ref = s3_key or media_url or ''
    if media_id or s3_key or media_url:
        ext = _media_ref.rsplit('.', 1)[-1].lower().split('?')[0] if '.' in _media_ref else ''
        if ext in ('jpg', 'jpeg', 'png', 'gif', 'bmp'):
            msg_type = 'image'
        elif ext in ('mp4', '3gp', '3gpp', 'mov'):
            msg_type = 'video'
        elif ext in ('ogg', 'opus', 'mp3', 'aac', 'amr', 'm4a'):
            msg_type = 'audio'
        elif ext == 'webp':
            msg_type = 'sticker'
        elif ext in ('pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'):
            msg_type = 'document'
        elif is_template:
            msg_type = 'template'
        else:
            msg_type = 'document'
    elif is_template:
        msg_type = 'template'
    else:
        msg_type = 'text'
    
    record = {
        'id': message_id,
        'messageId': message_id,
        'contactId': contact_id,
        'channel': 'whatsapp',
        'direction': 'outbound',
        'content': content,
        'messageType': msg_type,
        'timestamp': Decimal(str(now)),
        'status': status,
        'whatsappMessageId': whatsapp_message_id,
        'mediaId': media_id,
        's3Key': s3_key,
        'mediaUrl': media_url,
        'errorDetails': json.dumps(error_details) if error_details else None,
        # Meta error code (e.g. 131047) for failed messages → UI tooltip reason
        'errorCode': error_code if error_code else None,
        # WABA tracking - which phone number sent this message
        'awsPhoneNumberId': phone_number_id,
        'createdAt': Decimal(str(now)),
        'expiresAt': Decimal(str(expires_at)),
        # Payment tracking fields (for amount lookup on confirmation)
        'paymentReferenceId': payment_reference_id,
        'paymentAmount': Decimal(str(payment_amount * 100)) if payment_amount else None,  # Store in paise
        'paymentOffset': Decimal('100') if payment_amount else None,
        # BSUID recipient tracking (for BSUID-only sends)
        'recipientBsuid': recipient_bsuid or None,
    }
    
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        messages_table.put_item(Item={k: v for k, v in record.items() if v is not None})
    except Exception as e:
        logger.error(f"Failed to store message record: {str(e)}")

    # Unified Inbox dual-write — mirror to the canonical MessagesTable (Phase 1).
    # Same messageId as the WhatsApp table row, so messages-read dedups by messageId.
    # Guarded inside put_message, so it can never break the WhatsApp store/send above.
    put_message(
        channel='whatsapp',
        direction='outbound',
        contact_id=contact_id,
        content=content,
        status=status,
        message_id=message_id,
        message_type=msg_type,
        whatsapp_message_id=whatsapp_message_id,
        media_id=media_id,
        s3_key=s3_key,
        media_url=media_url,
        error_code=error_code or None,
        aws_phone_number_id=phone_number_id,
        timestamp=now,
    )


def _log_validation_failure(contact_id: str, channel: str, reason: str, request_id: str) -> None:
    """Log validation failure - Requirement 3.6"""
    logger.warning(json.dumps({
        'event': 'validation_failure',
        'contactId': contact_id,
        'channel': channel,
        'reason': reason,
        'requestId': request_id,
        'timestamp': int(time.time())
    }))


def _get_media_extension(media_type: str) -> str:
    """
    Get file extension based on media type.
    Complete mapping per WhatsApp Business Platform supported media types.
    
    Supported types:
    - Audio: AAC, AMR, MP3, M4A, OGG (max 16MB)
    - Document: PDF, TXT, DOC/DOCX, XLS/XLSX, PPT/PPTX (max 100MB)
    - Image: JPEG, PNG (max 5MB)
    - Sticker: WEBP (max 500KB animated, 100KB static)
    - Video: MP4, 3GPP (max 16MB)
    """
    extensions = {
        # Image formats (max 5MB)
        'image/jpeg': '.jpeg',
        'image/png': '.png',
        'image': '.jpeg',  # Default image

        # Sticker formats (max 500KB animated, 100KB static)
        'image/webp': '.webp',
        'sticker': '.webp',

        # Video formats (max 16MB)
        'video/mp4': '.mp4',
        'video/3gpp': '.3gp',
        'video': '.mp4',  # Default video

        # Audio formats (max 16MB)
        'audio/aac': '.aac',
        'audio/amr': '.amr',
        'audio/mpeg': '.mp3',
        'audio/mp4': '.m4a',
        'audio/ogg': '.ogg',
        'audio/opus': '.opus',
        'audio': '.ogg',  # Default audio

        # Document formats (max 100MB)
        'application/pdf': '.pdf',
        'text/plain': '.txt',
        'application/msword': '.doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.ms-powerpoint': '.ppt',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
        'document': '.pdf',  # Default document
    }
    
    # Try exact match first
    if media_type in extensions:
        return extensions[media_type]
    
    # Try prefix match (e.g., 'image' from 'image/jpeg')
    prefix = media_type.split('/')[0] if '/' in media_type else media_type
    return extensions.get(prefix, '.bin')


def _get_content_type(media_type: str) -> str:
    """
    Get MIME content type based on media type.
    Complete mapping per WhatsApp Business Platform supported media types.
    """
    content_types = {
        # Image formats (max 5MB)
        'image/jpeg': 'image/jpeg',
        'image/png': 'image/png',
        'image': 'image/jpeg',

        # Sticker formats (max 500KB animated, 100KB static)
        'image/webp': 'image/webp',
        'sticker': 'image/webp',

        # Video formats (max 16MB)
        'video/mp4': 'video/mp4',
        'video/3gpp': 'video/3gpp',
        'video': 'video/mp4',

        # Audio formats (max 16MB)
        'audio/aac': 'audio/aac',
        'audio/amr': 'audio/amr',
        'audio/mpeg': 'audio/mpeg',
        'audio/mp4': 'audio/mp4',
        'audio/ogg': 'audio/ogg',
        'audio/opus': 'audio/ogg',  # Opus → OGG container for WhatsApp
        'audio': 'audio/ogg',

        # Document formats (max 100MB)
        'application/pdf': 'application/pdf',
        'text/plain': 'text/plain',
        'application/msword': 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel': 'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint': 'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'document': 'application/pdf',
    }
    
    # Try exact match first
    if media_type in content_types:
        return content_types[media_type]
    
    # Try prefix match
    prefix = media_type.split('/')[0] if '/' in media_type else media_type
    if prefix in content_types:
        return content_types[prefix]
    
    return 'application/octet-stream'


def _validate_media_size(file_size: int, media_type: str) -> Tuple[bool, str]:
    """
    Validate media file size per WhatsApp Business Platform supported media types.
    
    Limits:
    - Audio (AAC, AMR, MP3, M4A, OGG): 16 MB
    - Document (PDF, TXT, DOC/DOCX, XLS/XLSX, PPT/PPTX): 100 MB
    - Image (JPEG, PNG): 5 MB
    - Sticker animated (WEBP): 500 KB
    - Sticker static (WEBP): 100 KB
    - Video (MP4, 3GPP): 16 MB
    
    Returns (is_valid, error_message)
    """
    if media_type.startswith('audio/') or media_type == 'audio':
        max_size = 16 * 1024 * 1024  # 16 MB
        category = 'Audio'
    elif media_type.startswith('video/') or media_type == 'video':
        max_size = 16 * 1024 * 1024  # 16 MB
        category = 'Video'
    elif media_type == 'sticker' or media_type == 'image/webp':
        max_size = 500 * 1024  # 500 KB (animated max; static is 100KB but we allow up to 500KB)
        category = 'Sticker'
    elif media_type.startswith('image/') or media_type == 'image':
        max_size = 5 * 1024 * 1024  # 5 MB
        category = 'Image'
    else:
        # Documents: PDF, TXT, DOC/DOCX, XLS/XLSX, PPT/PPTX
        max_size = 100 * 1024 * 1024  # 100 MB
        category = 'Document'
    
    if file_size > max_size:
        max_display = f'{max_size / 1024:.0f}KB' if max_size < 1024 * 1024 else f'{max_size / (1024*1024):.0f}MB'
        return False, f'{category} file exceeds maximum size of {max_display}'
    
    return True, ''


def _error_response(status_code: int, error: str, message: str = None) -> Dict[str, Any]:
    """Return error response with CORS headers."""
    body = {'error': error}
    if message:
        body['message'] = message
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body)
    }


def _send_typing_indicator(phone_number_id: str, message_id: str) -> None:
    """Send a native WhatsApp typing indicator.

    Per Meta Cloud API (2025+): POST /{PHONE_NUMBER_ID}/messages with
    status='read' + the inbound message_id + a typing_indicator object.
    This marks the customer's last message as read (blue ticks) AND shows a
    typing bubble for up to 25 seconds (or until the business sends a message).

    Requires the WAMID of the customer's most recent inbound message.
    """
    try:
        if not message_id:
            logger.info(json.dumps({
                'event': 'typing_indicator_skipped',
                'reason': 'no inbound message_id available',
                'phoneNumberId': phone_number_id,
            }))
            return

        payload = {
            'messaging_product': 'whatsapp',
            'status': 'read',
            'message_id': message_id,
            'typing_indicator': {'type': 'text'},
        }

        _send_message(phone_number_id, payload)

        logger.info(json.dumps({
            'event': 'typing_indicator_sent',
            'messageId': message_id,
            'phoneNumberId': phone_number_id,
        }))
    except Exception as e:
        # Non-critical — log and swallow so the caller can proceed
        logger.warning(json.dumps({
            'event': 'typing_indicator_error',
            'error': str(e),
            'messageId': message_id,
        }))


def _emit_delivery_metric(status: str, is_template: bool = False) -> None:
    """
    Emit message delivery metric to CloudWatch.
    Requirement 14.4: Emit CloudWatch metrics for message delivery success/failure
    """
    try:
        cloudwatch.put_metric_data(
            Namespace=METRICS_NAMESPACE,
            MetricData=[
                {
                    'MetricName': f'Messages{status.capitalize()}',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Channel', 'Value': 'WHATSAPP'},
                        {'Name': 'Status', 'Value': status.upper()},
                        {'Name': 'MessageType', 'Value': 'TEMPLATE' if is_template else 'FREEFORM'}
                    ]
                },
                {
                    'MetricName': 'MessagesTotal',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Channel', 'Value': 'WHATSAPP'}
                    ]
                }
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to emit metric: {str(e)}")
