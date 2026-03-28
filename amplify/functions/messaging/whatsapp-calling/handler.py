"""
WhatsApp Calling Webhook + Call Control Handler

Purpose: Handle WhatsApp Business Calling API webhooks + call signaling
- GET  /whatsapp-calling           → Webhook verification (hub.challenge)
- POST /whatsapp-calling           → Call events (connect, terminate, permission)
- GET  /whatsapp-calling/logs      → List call event logs
- GET  /whatsapp-calling/active    → Get active/pending calls (for frontend polling)
- POST /whatsapp-calling/accept    → Pre-accept + accept a call (send SDP answer to Meta)
- POST /whatsapp-calling/reject    → Reject/terminate a call
- POST /whatsapp-calling/hangup    → Hang up an active call
- POST /whatsapp-calling/outbound  → Request call permission or initiate outbound call
- DELETE /whatsapp-calling         → Clear call logs

Meta Webhook Fields: calls
Verify Token: wecare_calling_verify_2026
"""

import os
import json
import time
import logging
import uuid
import hmac
import hashlib
import boto3
import urllib.request
import urllib.error
from decimal import Decimal
from typing import Dict, Any, Optional

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.privacy import mask_phone, redact_pii

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)
secrets_client = boto3.client('secretsmanager', region_name=REGION)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '')
if not VERIFY_TOKEN:
    logging.getLogger(__name__).warning('VERIFY_TOKEN not set — webhook verification will reject all requests')
CALL_LOG_TABLE = os.environ.get('CALL_LOG_TABLE', 'stack-wecare-digital-WhatsAppCallingTable')
META_TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')
TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days

# Meta WhatsApp Calling error codes (from Meta Troubleshooting docs)
# Used for actionable error logging and frontend display
META_CALLING_ERRORS = {
    138000: {'msg': 'Calling not enabled', 'action': 'Enable calling on this phone number via POST /{phone_id}/settings'},
    138001: {'msg': 'Receiver uncallable', 'action': 'User not on WhatsApp, old ToS, or unsupported client'},
    138002: {'msg': 'Concurrent calls limit reached (max 1000)', 'action': 'Wait for active calls to end'},
    138005: {'msg': 'Call rate limit exceeded', 'action': 'Reduce call frequency'},
    138006: {'msg': 'No approved call permission', 'action': 'Send call_permission_request first'},
    138007: {'msg': 'Connect timeout (SDP not applied in time)', 'action': 'Check SDP answer generation speed'},
    138009: {'msg': 'Call permission request limit hit', 'action': 'Wait before sending more permission requests'},
    138012: {'msg': 'Business-initiated calls limit (100 connected/24h)', 'action': 'Daily outbound call limit reached'},
    138013: {'msg': 'Business-initiated calling not available', 'action': 'Feature not enabled for this WABA'},
    138014: {'msg': 'Calling temporarily disabled (low quality)', 'action': 'Improve call quality metrics'},
    138017: {'msg': 'Permanent permission already exists', 'action': 'User already granted permanent call permission'},
    138018: {'msg': 'Technical prerequisites not met', 'action': 'Configure SIP or subscribe to calls webhook field'},
    138019: {'msg': 'WhatsApp client failed to set up call', 'action': 'Retry — client-side issue'},
    138020: {'msg': 'Relay connection failed', 'action': 'Check network/firewall — media relay unreachable'},
    138021: {'msg': 'Media receive timeout', 'action': 'Check media pipeline — no audio received from caller'},
    138022: {'msg': 'Media transmit timeout', 'action': 'Check media pipeline — no audio sent to caller'},
    138023: {'msg': 'Call accepted but no media signals', 'action': 'SDP answer may be invalid or media path broken'},
}

# Dual WABA token support
WABA1_ID = '1912405516040025'
WABA2_ID = '2513394156072604'  # Migrated — now Direct API, uses token1 (WECARE.DIGITAL app)
PHONE1_META_ID = '960395407161423'
PHONE2_META_ID = '1055232054343117'  # New Meta phone ID after migration
# WABA2 now uses WECARE.DIGITAL app (token1), not Manish app
WABA2_IDS = set()  # No longer need separate token routing for WABA2

# WABA3 (Direct API) — +91 93309 94400 migrated here (pending registration)
WABA3_ID = '2094615664435155'
WABA3_PHONE_META_ID = '1016149501586345'  # New phone ID after migration

# Inbound handler Lambda for forwarding non-call webhook events (messages, statuses)
INBOUND_HANDLER_FUNCTION = os.environ.get('INBOUND_HANDLER_FUNCTION', 'wecare-inbound-whatsapp')
lambda_client = boto3.client('lambda', region_name=REGION)

# Cache Meta tokens (dual)
_token_cache = {}

# CORS headers provided by lambda_utils.response.cors_headers(origin)


def _get_meta_token(phone_number_id: str = None) -> str:
    """Get the Meta token for calling operations.
    
    WABA1/WABA3 use token1 (Meta App: WECARE.DIGITAL / 2238810740192680).
    WABA2 uses token2 (Meta App: Manish Agarwal / 1224334845952721).
    
    Note: For EUM-managed WABAs (WABA1, WABA2), direct Meta API calls return 403.
    Calling API (pre_accept/accept/terminate) only works on WABA3 (Direct API).
    """
    _load_meta_secrets()
    if phone_number_id and phone_number_id in WABA2_IDS:
        logger.info(f"Using token2 for WABA2 phone_number_id={phone_number_id}")
        return _token_cache.get('token2', '')
    token = _token_cache.get('token1', '')
    logger.info(f"Using token1 for calling (phone_number_id={phone_number_id})")
    return token


def _get_app_secret(phone_number_id: str = None) -> str:
    """Get the app secret for appsecret_proof. Routes to correct app secret."""
    _load_meta_secrets()
    if phone_number_id and phone_number_id in WABA2_IDS:
        return _token_cache.get('app_secret2', '')
    return _token_cache.get('app_secret1', '')


def _load_meta_secrets():
    """Load tokens + app secrets from Secrets Manager (cached)."""
    if 'loaded' in _token_cache:
        return
    try:
        resp = secrets_client.get_secret_value(SecretId=META_TOKEN_SECRET)
        secret = resp.get('SecretString', '')
        try:
            data = json.loads(secret)
            _token_cache['token1'] = (data.get('access_token') or '').strip()
            _token_cache['token2'] = (data.get('access_token_waba2') or data.get('access_token') or '').strip()
            _token_cache['app_secret1'] = (data.get('app_secret') or '').strip()
            _token_cache['app_secret2'] = (data.get('app_secret_waba2') or '').strip()
        except (json.JSONDecodeError, TypeError):
            _token_cache['token1'] = secret.strip()
            _token_cache['token2'] = secret.strip()
        _token_cache['loaded'] = True
        logger.info(f"Loaded dual tokens: token1={len(_token_cache.get('token1',''))}chars, token2={len(_token_cache.get('token2',''))}chars, has_app_secrets={bool(_token_cache.get('app_secret1'))}")
    except Exception as e:
        logger.error(f"Failed to get Meta token: {e}")
        raise


def _meta_api_call(endpoint: str, method: str = 'POST', payload: Dict = None, phone_number_id: str = None) -> Dict:
    """Make a call to Meta Graph API with dual-token support and appsecret_proof."""
    token = _get_meta_token(phone_number_id=phone_number_id)
    app_secret = _get_app_secret(phone_number_id=phone_number_id)

    # Build URL with appsecret_proof if app secret is available
    url = f"https://graph.facebook.com/{META_API_VERSION}/{endpoint}"
    if app_secret:
        proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        separator = '&' if '?' in url else '?'
        url = f"{url}{separator}appsecret_proof={proof}"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    data = json.dumps(payload).encode('utf-8') if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {'success': True}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        # Parse Meta error code for actionable logging
        error_code = None
        error_msg = ''
        try:
            err_data = json.loads(error_body)
            error_obj = err_data.get('error', {})
            error_code = error_obj.get('code')
            error_msg = error_obj.get('message', '')
        except (json.JSONDecodeError, TypeError):
            pass
        if error_code and error_code in META_CALLING_ERRORS:
            meta_err = META_CALLING_ERRORS[error_code]
            logger.error(f"Meta API error {e.code} — Code {error_code}: {meta_err['msg']} | Action: {meta_err['action']} | Detail: {error_msg}")
        else:
            logger.error(f"Meta API error {e.code}: {error_body}")
        return {'error': True, 'status': e.code, 'detail': error_body, 'errorCode': error_code, 'errorMessage': error_msg}
    except Exception as e:
        logger.error(f"Meta API call failed: {e}")
        return {'error': True, 'detail': str(e)}


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler — routes to appropriate function."""
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)
    rc = event.get('requestContext', {})
    http_method = rc.get('http', {}).get('method', event.get('httpMethod', 'GET'))
    path = rc.get('http', {}).get('path', '') or event.get('rawPath', '') or event.get('path', '')
    query_params = event.get('queryStringParameters') or {}

    logger.info(json.dumps({
        'event': 'whatsapp_calling_request',
        'method': http_method, 'path': path, 'requestId': request_id,
    }))

    if http_method == 'OPTIONS':
        return _response(200, {'ok': True})

    try:
        # GET routes
        if http_method == 'GET':
            # Webhook verification (no auth needed — Meta sends this)
            if not any(x in path for x in ['config', 'active', 'logs']):
                return _verify_webhook(query_params, request_id)

            if 'config' in path:
                return _get_config(request_id)
            if 'active' in path:
                return _get_active_calls(query_params, request_id)
            if 'logs' in path:
                return _list_logs(query_params, request_id)

        # POST routes
        if http_method == 'POST':
            # Default POST with no sub-path = webhook event from Meta (no auth)
            if not any(x in path for x in ['/config', '/accept', '/reject', '/hangup', '/outbound', '/ai-respond']):
                # P0 Security: Verify X-Hub-Signature-256 before processing
                if not _verify_webhook_signature(event, request_id):
                    logger.warning(json.dumps({'event': 'webhook_signature_rejected', 'requestId': request_id}))
                    return _response(401, {'error': 'Invalid webhook signature'})
                body_str = event.get('body', '{}')
                if event.get('isBase64Encoded'):
                    import base64
                    body_str = base64.b64decode(body_str).decode('utf-8')
                try:
                    return _handle_webhook_event(json.loads(body_str), request_id)
                except (json.JSONDecodeError, TypeError, ValueError):
                    logger.warning(json.dumps({'event': 'webhook_invalid_json', 'requestId': request_id}))
                    return _response(400, {'error': 'Invalid JSON in webhook body'})

            if '/config' in path:
                return _update_config(event, request_id)
            if '/accept' in path:
                return _accept_call(event, request_id)
            if '/reject' in path or '/hangup' in path:
                return _terminate_call(event, request_id)
            if '/outbound' in path:
                return _outbound_call(event, request_id)
            if '/ai-respond' in path:
                return _ai_respond(event, request_id)

        # DELETE
        if http_method == 'DELETE':
            return _clear_logs(request_id)

        return _response(200, {'message': 'OK'})

    except Exception as e:
        logger.error(json.dumps({
            'event': 'handler_error',
            'error': str(e),
            'method': http_method,
            'path': path,
            'requestId': request_id,
        }), exc_info=True)
        return _response(500, {'error': 'Internal server error'})


# ─── Webhook Verification ───────────────────────────────────────────

def _verify_webhook(params: Dict, request_id: str) -> Dict[str, Any]:
    """Handle Meta webhook verification (GET with hub.challenge)."""
    mode = params.get('hub.mode', '')
    token = params.get('hub.verify_token', '')
    challenge = params.get('hub.challenge', '')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        logger.info(f"Webhook verified. Challenge: {challenge}")
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/plain', 'Access-Control-Allow-Origin': '*'},
            'body': challenge,
        }
    logger.warning(f"Webhook verification failed. Mode={mode}")
    return _response(403, {'error': 'Verification failed'})


# ─── Webhook Event Processing ───────────────────────────────────────

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

    # Load both app secrets (dual WABA support — webhook may be signed by either app)
    _load_meta_secrets()
    app_secret_1 = _token_cache.get('app_secret1', '')
    app_secret_2 = _token_cache.get('app_secret2', '')

    if not app_secret_1 and not app_secret_2:
        logger.error(json.dumps({'event': 'webhook_no_app_secret', 'requestId': request_id}))
        # P0 Security: Never fail open — reject if no secrets configured
        return False

    raw_body = event.get('body', '')
    if event.get('isBase64Encoded') and raw_body:
        import base64
        raw_body = base64.b64decode(raw_body).decode('utf-8')

    body_bytes = (raw_body or '').encode('utf-8')

    # Try both app secrets — webhook may come from either WABA's app
    for label, secret in [('app_secret1', app_secret_1), ('app_secret2', app_secret_2)]:
        if not secret:
            continue
        expected_sig = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(expected_sig, signature_header):
            return True

    # Neither secret matched — log for debugging
    # Compute expected with primary secret for the log
    primary_secret = app_secret_1 or app_secret_2
    expected_sig = 'sha256=' + hmac.new(
        primary_secret.encode('utf-8'),
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    logger.warning(json.dumps({
        'event': 'webhook_signature_mismatch',
        'expectedPrefix': expected_sig[:20],
        'receivedPrefix': signature_header[:20],
        'bodyLen': len(raw_body or ''),
        'isBase64': event.get('isBase64Encoded', False),
        'requestId': request_id,
    }))
    return False


# Maximum age for webhook events (replay protection)
WEBHOOK_MAX_AGE_SECONDS = 300  # 5 minutes


def _validate_webhook_timestamp(body: Dict, request_id: str) -> bool:
    """
    Reject webhook events older than 5 minutes (replay protection).
    Checks entry[].changes[].value.metadata.timestamp or entry[].time.
    Returns True if timestamp is valid (recent), False if stale.
    """
    try:
        now = int(time.time())
        entries = body.get('entry', [])
        for entry in entries:
            # Check entry-level timestamp
            entry_time = entry.get('time')
            if entry_time:
                age = now - int(entry_time)
                if age > WEBHOOK_MAX_AGE_SECONDS:
                    logger.warning(json.dumps({
                        'event': 'webhook_timestamp_stale',
                        'entryTime': entry_time,
                        'age': age,
                        'maxAge': WEBHOOK_MAX_AGE_SECONDS,
                        'requestId': request_id,
                    }))
                    return False
            # Check value-level timestamps
            for change in entry.get('changes', []):
                value = change.get('value', {})
                calls = value.get('calls', [value])
                for call in calls:
                    ts = call.get('timestamp')
                    if ts:
                        age = now - int(ts)
                        if age > WEBHOOK_MAX_AGE_SECONDS:
                            logger.warning(json.dumps({
                                'event': 'webhook_call_timestamp_stale',
                                'callTimestamp': ts,
                                'age': age,
                                'requestId': request_id,
                            }))
                            return False
    except (ValueError, TypeError) as e:
        logger.warning(f'Webhook timestamp validation error: {e}')
        # Fail open on parse errors — don't block legitimate events
    return True


def _handle_webhook_event(body: Dict, request_id: str) -> Dict[str, Any]:
    """Process incoming WhatsApp webhook events."""
    # Replay protection: reject events older than 5 minutes
    if not _validate_webhook_timestamp(body, request_id):
        logger.warning(json.dumps({'event': 'webhook_replay_rejected', 'requestId': request_id}))
        return _response(200, {'status': 'rejected', 'reason': 'stale_timestamp'})

    logger.info(json.dumps({
        'event': 'webhook_received', 'requestId': request_id,
        'body_preview': json.dumps(body)[:2000],
    }))

    obj = body.get('object', '')
    entries = body.get('entry', [])

    if obj != 'whatsapp_business_account':
        return _response(200, {'status': 'ignored', 'object': obj})

    for entry in entries:
        waba_id = entry.get('id', '')
        changes = entry.get('changes', [])
        for change in changes:
            field = change.get('field', '')
            value = change.get('value', {})

            if field == 'calls':
                # New Meta webhook format: calls is an array inside value
                calls = value.get('calls', [value])
                metadata = value.get('metadata', {})
                contacts = value.get('contacts', [])
                logger.info(f"Processing {len(calls)} call event(s) for waba_id={waba_id}, "
                            f"phone_number_id={metadata.get('phone_number_id', 'N/A')}, "
                            f"display_phone={metadata.get('display_phone_number', 'N/A')}")
                for call in calls:
                    _handle_call_event(waba_id, call, metadata, contacts, request_id)
            elif field == 'messages':
                # Forward message events to inbound handler (WABA3 Direct API)
                _forward_to_inbound_handler(entry, waba_id, request_id)
            else:
                logger.info(f"Non-call field: {field}")

    return _response(200, {'status': 'processed', 'entries': len(entries)})


def _forward_to_inbound_handler(entry: Dict, waba_id: str, request_id: str) -> None:
    """
    Forward non-call webhook events (messages, statuses) to the inbound handler.
    WABA3 uses Direct API with override_callback_uri, so messages arrive here
    instead of via AWS EUM → SNS. We wrap them in the SNS/EUM format the
    inbound handler expects and invoke it asynchronously.
    """
    try:
        # Extract metadata for context
        changes = entry.get('changes', [])
        meta_phone_ids = []
        for change in changes:
            value = change.get('value', {})
            metadata = value.get('metadata', {})
            pid = metadata.get('phone_number_id', '')
            if pid and pid not in meta_phone_ids:
                meta_phone_ids.append(pid)

        # Build the SNS/EUM format the inbound handler expects
        sns_message = {
            'context': {
                'MetaWabaIds': [waba_id],
                'MetaPhoneNumberIds': meta_phone_ids,
            },
            'whatsAppWebhookEntry': json.dumps(entry),
            'messageId': request_id,
        }

        # Wrap in SNS Records format
        inbound_event = {
            'Records': [{
                'Sns': {
                    'Message': json.dumps(sns_message),
                    'MessageId': request_id,
                }
            }]
        }

        result = lambda_client.invoke(
            FunctionName=INBOUND_HANDLER_FUNCTION,
            InvocationType='Event',  # async — don't wait
            Payload=json.dumps(inbound_event),
        )

        logger.info(json.dumps({
            'event': 'forwarded_to_inbound_handler',
            'wabaId': waba_id,
            'phoneNumberIds': meta_phone_ids,
            'statusCode': result.get('StatusCode'),
            'requestId': request_id,
        }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'forward_to_inbound_handler_failed',
            'wabaId': waba_id,
            'error': str(e),
            'requestId': request_id,
        }), exc_info=True)


def _handle_call_event(waba_id: str, call: Dict, metadata: Dict, contacts: list, request_id: str) -> None:
    """Handle a single call event from webhook. Extracts BSUID and username."""
    event_type = call.get('event', '')
    call_id = call.get('id', call.get('call_id', ''))
    from_number = call.get('from', '')
    to_number = call.get('to', '')
    direction = call.get('direction', 'USER_INITIATED')
    phone_number_id = metadata.get('phone_number_id', '')
    display_phone = metadata.get('display_phone_number', '')
    timestamp = call.get('timestamp', str(int(time.time())))

    # Extract BSUID from call event (from_user_id for user-initiated, to_user_id for biz-initiated)
    from_bsuid = call.get('from_user_id', '')
    to_bsuid = call.get('to_user_id', '')
    from_parent_bsuid = call.get('from_parent_user_id', '')
    to_parent_bsuid = call.get('to_parent_user_id', '')
    caller_bsuid = from_bsuid if direction == 'USER_INITIATED' else to_bsuid
    caller_parent_bsuid = from_parent_bsuid if direction == 'USER_INITIATED' else to_parent_bsuid

    # Extract caller name and username from contacts array
    caller_name = ''
    caller_username = ''
    if contacts:
        contact_info = contacts[0]
        caller_name = contact_info.get('profile', {}).get('name', '')
        caller_username = contact_info.get('profile', {}).get('username', '')
        # Also get BSUID from contacts if not in call event
        if not caller_bsuid:
            caller_bsuid = contact_info.get('user_id', '')

    now = int(time.time())

    logger.info(json.dumps({
        'event': 'call_event', 'type': event_type, 'call_id': call_id,
        'from': from_number, 'to': to_number, 'direction': direction,
        'phone_number_id': phone_number_id, 'caller_name': caller_name,
        'caller_bsuid': caller_bsuid, 'caller_username': caller_username,
    }))

    if event_type == 'connect':
        # Inbound call — extract SDP offer
        session = call.get('session', {})
        sdp_offer = session.get('sdp', call.get('sdp_offer', ''))
        sdp_type = session.get('sdp_type', 'offer')

        _store_call_log({
            'callId': call_id,
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'displayPhone': display_phone,
            'fromNumber': from_number,
            'toNumber': to_number,
            'callerName': caller_name,
            'fromBsuid': caller_bsuid or None,
            'fromParentBsuid': caller_parent_bsuid or None,
            'callerUsername': caller_username or None,
            'direction': direction,
            'eventType': 'connect',
            'status': 'ringing',
            'sdpOffer': sdp_offer,
            'sdpType': sdp_type,
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })
        logger.info(f"INBOUND CALL from {caller_name or from_number} (BSUID: {caller_bsuid or 'N/A'}) — call_id: {call_id}, has_sdp: {bool(sdp_offer)}, sdp_len: {len(sdp_offer) if sdp_offer else 0}, phone_number_id: {phone_number_id}")

        # Auto-pickup: behaviour depends on mode (manual / ivr)
        # - manual: pre_accept only, wait for frontend browser to answer via WebRTC
        # - ivr: pre_accept, send IVR audio message, terminate after delay
        if _is_auto_pickup_enabled() and phone_number_id:
            pickup_mode = _get_auto_pickup_mode()
            logger.info(f"AUTO-PICKUP mode={pickup_mode} — call {call_id} from {caller_name or from_number}")

            if pickup_mode == 'ivr':
                # IVR mode: pre_accept → send IVR menu → terminate
                _auto_pickup_and_play(call_id, phone_number_id, from_number, sdp_offer)
            elif pickup_mode == 'manual':
                # manual: pre_accept only, wait for frontend browser to answer via WebRTC
                # Skip pre_accept for EUM-managed phones (would 403)
                if phone_number_id in EUM_MANAGED_META_PHONE_IDS:
                    logger.info(f"AUTO-PICKUP manual mode: skipping pre_accept for EUM-managed phone {phone_number_id}")
                    _update_call_status(call_id, 'ringing_eum')
                else:
                    try:
                        pre_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
                            'messaging_product': 'whatsapp',
                            'call_id': call_id,
                            'action': 'pre_accept',
                        }, phone_number_id=phone_number_id)
                        logger.info(f"AUTO-PICKUP pre_accept result: {json.dumps(pre_result)}")
                        if pre_result.get('error'):
                            logger.error(f"AUTO-PICKUP pre_accept failed: {json.dumps(pre_result)}")
                            if pre_result.get('status') == 403:
                                logger.error(
                                    f"403 on pre_accept for phone_number_id={phone_number_id}. "
                                    f"Check: 1) System User token has whatsapp_business_messaging permission, "
                                    f"2) Calling is enabled on this phone number, "
                                    f"3) Token belongs to the correct WABA for this phone number."
                                )
                            _update_call_status(call_id, 'pre_accept_failed', pre_result)
                        else:
                            _update_call_status(call_id, 'pre_accepted')
                    except Exception as e:
                        logger.error(f"Auto pre_accept failed: {e}", exc_info=True)

    elif event_type == 'terminate':
        reason = call.get('reason', 'unknown')
        duration = call.get('duration', 0)
        # Extract Meta error code from terminate event if present
        error_code = call.get('error_code', call.get('code', ''))
        if error_code and int(error_code) in META_CALLING_ERRORS:
            meta_err = META_CALLING_ERRORS[int(error_code)]
            logger.warning(f"Call {call_id} terminated with Meta error {error_code}: "
                           f"{meta_err['msg']} | Action: {meta_err['action']}")
        _store_call_log({
            'callId': call_id,
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number,
            'toNumber': to_number,
            'fromBsuid': caller_bsuid or None,
            'fromParentBsuid': caller_parent_bsuid or None,
            'callerUsername': caller_username or None,
            'direction': direction,
            'eventType': 'terminate',
            'status': 'ended',
            'terminateReason': reason,
            'errorCode': str(error_code) if error_code else None,
            'duration': duration,
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })

        # Send post-call reaction to the caller via WhatsApp message
        # ✅ for completed calls (duration > 0), ❌ for missed/rejected
        _send_post_call_reaction(
            phone_number_id=phone_number_id,
            from_number=from_number,
            call_id=call_id,
            reason=reason,
            duration=duration,
            direction=direction,
        )

    elif event_type in ('call_permission_response', 'call_permission_status'):
        # Meta sends call_permission_status with status: GRANTED/REJECTED/REVOKED
        permission = call.get('status', call.get('permission', ''))
        recipient = call.get('recipient', call.get('to', to_number))
        _store_call_log({
            'callId': call_id or str(uuid.uuid4()),
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number or recipient,
            'toNumber': to_number,
            'fromBsuid': caller_bsuid or None,
            'fromParentBsuid': caller_parent_bsuid or None,
            'callerUsername': caller_username or None,
            'direction': direction,
            'eventType': 'permission_response',
            'status': f'permission_{permission.lower() if permission else "unknown"}',
            'permission': permission,
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })
        logger.info(f"Call permission {permission} from {from_number or recipient} on {phone_number_id}")

    else:
        _store_call_log({
            'callId': call_id or str(uuid.uuid4()),
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number,
            'eventType': event_type or 'unknown',
            'status': 'logged',
            'rawEvent': json.dumps(call)[:1000],
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })


def _redirect_call_to_voice_notes(call_id: str, phone_number_id: str,
                                   from_number: str, caller_name: str) -> None:
    """
    AI mode: Instead of establishing a real-time voice call (which requires
    WebRTC infrastructure), gracefully redirect the caller to send a voice note.

    The inbound WhatsApp handler already processes audio messages through the
    full multimodal AI pipeline (Bedrock Converse API → Nova Lite) and can
    reply with text + optional Polly TTS audio message. This gives the caller
    an AI voice conversation experience at zero additional infrastructure cost.

    Flow:
    1. Terminate the call immediately (no pre_accept needed)
    2. Send a friendly WhatsApp message explaining to send a voice note
    3. Caller sends voice note → inbound handler → AI pipeline → auto-reply
    """
    logger.info(json.dumps({
        'event': 'ai_redirect_to_voice_notes',
        'call_id': call_id,
        'from': from_number,
        'caller_name': caller_name,
        'phone_number_id': phone_number_id,
    }))

    # Step 1: Try to terminate the call (may fail with 403 if WABA is managed
    # by AWS EUM Social — that's OK, call will end naturally when caller hangs up)
    try:
        term_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
            'messaging_product': 'whatsapp',
            'call_id': call_id,
            'action': 'terminate',
        }, phone_number_id=phone_number_id)
        if term_result.get('error'):
            logger.info(f"AI-REDIRECT terminate skipped (expected with AWS EUM): status={term_result.get('status')}")
        else:
            logger.info(f"AI-REDIRECT terminate success: {json.dumps(term_result)}")
    except Exception as e:
        logger.info(f"AI-REDIRECT terminate skipped: {e}")

    _update_call_status(call_id, 'ai_redirected')

    # Step 2: Send a friendly redirect message via WhatsApp
    aws_phone_id = _get_aws_phone_id(phone_number_id)
    greeting = caller_name or 'there'

    redirect_text = (
        f"📞 Hey {greeting}! I noticed you tried to call.\n\n"
        f"🎙️ I'm an AI assistant — send me a *voice note* and I'll respond "
        f"instantly with a voice reply!\n\n"
        f"You can also just type your question. I'm here to help 😊"
    )

    result = _send_via_aws(aws_phone_id, from_number, {
        'type': 'text',
        'text': {'body': redirect_text},
    })

    if result.get('error'):
        error_detail = result.get('detail', '')
        if any(kw in error_detail.lower() for kw in ('outside', 'window', '131047')):
            # No 24h messaging window — try sending a template instead
            logger.warning(f"AI-REDIRECT: No 24h window for {from_number}, "
                           f"redirect message not sent. Caller will see missed call.")
        else:
            logger.error(f"AI-REDIRECT message failed: {json.dumps(result)}")
    else:
        logger.info(f"AI-REDIRECT message sent to {from_number}: messageId={result.get('messageId')}")


def _send_post_call_reaction(phone_number_id: str, from_number: str, call_id: str,
                              reason: str, duration: int, direction: str) -> None:
    """
    Send a post-call summary message to the caller/callee after a call ends.
    Uses AWS EUM Social Messaging to send a text message with call details.
    - Completed calls (duration > 0): ✅ with duration
    - Missed/rejected/no-answer: ❌ with reason
    - AI-redirected calls: skip (redirect message already sent)
    
    Note: Requires an open 24-hour messaging window. If the window is closed
    (e.g. caller never messaged this business number), the send will fail silently.
    """
    try:
        # Skip post-call reaction if the call was AI-redirected
        try:
            table = dynamodb.Table(CALL_LOG_TABLE)
            from boto3.dynamodb.conditions import Attr as DDBAttr
            result_check = table.scan(
                FilterExpression=DDBAttr('callId').eq(call_id),
                Limit=10,
            )
            ai_handled = any(
                i.get('status') in ('ai_redirected',)
                for i in result_check.get('Items', [])
            )
            if ai_handled:
                logger.info(f"Post-call reaction skipped: call {call_id} was AI-handled")
                return
        except Exception:
            pass  # If check fails, send the reaction anyway

        aws_phone_id = _get_aws_phone_id(phone_number_id)
        # Determine the recipient — for inbound calls, reply to the caller (from_number)
        to_number = from_number

        if not to_number:
            logger.warning(f"Post-call reaction skipped: no from_number for call {call_id}")
            return

        logger.info(f"Post-call reaction: phone_number_id={phone_number_id}, "
                     f"aws_phone_id={aws_phone_id}, to={to_number}, "
                     f"direction={direction}, reason={reason}, duration={duration}")

        if duration and int(duration) > 0:
            mins = int(duration) // 60
            secs = int(duration) % 60
            duration_str = f"{mins}m {secs}s" if mins else f"{secs}s"
            text = f"📞 ✅ Call completed — {duration_str}"
        else:
            reason_map = {
                'no_answer': 'No answer',
                'busy': 'Busy',
                'rejected': 'Rejected',
                'timeout': 'Timed out',
                'caller_hangup': 'Caller hung up',
                'callee_hangup': 'Call ended',
            }
            reason_text = reason_map.get(reason, reason.replace('_', ' ').title() if reason else 'Unknown')
            text = f"📞 ❌ Call ended — {reason_text}"

        result = _send_via_aws(aws_phone_id, to_number, {
            'type': 'text',
            'text': {'body': text},
        })

        if result.get('error'):
            error_detail = result.get('detail', '')
            # Check if it's a 24-hour window issue
            if 'outside' in error_detail.lower() or 'window' in error_detail.lower() or '131047' in error_detail:
                logger.warning(f"Post-call reaction skipped (no 24h window): "
                               f"to={to_number}, via={aws_phone_id}, call={call_id}")
            else:
                logger.error(f"Post-call reaction FAILED for {to_number} via {aws_phone_id}: "
                             f"{json.dumps(result)}")
        else:
            logger.info(f"Post-call reaction sent to {to_number}: {text} — "
                        f"messageId={result.get('messageId')}")
    except Exception as e:
        logger.error(f"Failed to send post-call reaction: {e}", exc_info=True)


# ─── Call Control (Accept / Reject / Hangup) ────────────────────────

def _accept_call(event: Dict, request_id: str) -> Dict[str, Any]:
    """
    Accept an incoming call: pre_accept → accept with SDP answer.
    Frontend sends: { callId, phoneNumberId, sdpAnswer }
    Skips pre_accept if the call was already pre_accepted by auto-pickup.
    """
    try:
        body = json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _response(400, {'error': 'Invalid JSON in request body'})
    call_id = body.get('callId', '')
    phone_number_id = body.get('phoneNumberId', '')
    sdp_answer = body.get('sdpAnswer', '')

    if not call_id or not phone_number_id:
        return _response(400, {'error': 'callId and phoneNumberId required'})

    logger.info(f"Accepting call {call_id} on {phone_number_id}, has_sdp_answer: {bool(sdp_answer)}")

    # EUM-managed phones cannot use direct Meta API for call control
    if phone_number_id in EUM_MANAGED_META_PHONE_IDS:
        logger.warning(f"Accept call on EUM-managed phone {phone_number_id} — "
                       f"direct Meta API not supported. Call control only works on Direct API phones.")
        return _response(200, {
            'success': False,
            'error': 'EUM-managed phone — direct call control not supported',
            'hint': 'This phone is linked to AWS Social Messaging which does not support calling API. '
                    'Call control (accept/reject/hangup) only works on Direct API phones (WABA3).',
        })

    # Check if call was already pre_accepted by auto-pickup webhook handler
    already_pre_accepted = False
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        from boto3.dynamodb.conditions import Attr as DDBAttr2
        result = table.scan(
            FilterExpression=DDBAttr2('callId').eq(call_id) & DDBAttr2('eventType').eq('connect'),
            Limit=10,
        )
        items = result.get('Items', [])
        if items and items[0].get('status') == 'pre_accepted':
            already_pre_accepted = True
            logger.info(f"Call {call_id} already pre_accepted by auto-pickup, skipping pre_accept")
    except Exception as e:
        logger.warning(f"Could not check pre_accept status: {e}")

    pre_accept_result = None
    if not already_pre_accepted:
        # Step 1: Pre-accept — tells Meta we're preparing to answer
        pre_accept_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
            'messaging_product': 'whatsapp',
            'call_id': call_id,
            'action': 'pre_accept',
        }, phone_number_id=phone_number_id)
        logger.info(f"Pre-accept result: {json.dumps(pre_accept_result)}")

        if pre_accept_result.get('error'):
            _update_call_status(call_id, 'pre_accept_failed', pre_accept_result)
            error_code = pre_accept_result.get('errorCode')
            hint = ''
            if error_code and error_code in META_CALLING_ERRORS:
                hint = f"Error {error_code}: {META_CALLING_ERRORS[error_code]['msg']} — {META_CALLING_ERRORS[error_code]['action']}"
            elif pre_accept_result.get('status') == 403:
                hint = ('Token lacks calling permission. Ensure the System User token '
                        'has whatsapp_business_messaging permission AND calling is '
                        'enabled on this phone number via POST /{phone_number_id}/settings '
                        'with the calling object. Also verify the token belongs to the '
                        'correct WABA for this phone number.')
            return _response(200, {
                'success': False, 'step': 'pre_accept',
                'error': pre_accept_result,
                'errorCode': error_code,
                'hint': hint,
                'phone_number_id_used': phone_number_id,
            })
    else:
        pre_accept_result = {'skipped': True, 'reason': 'already_pre_accepted'}

    # Step 2: Accept with SDP answer — establishes WebRTC media
    accept_payload = {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'accept',
    }
    if sdp_answer:
        accept_payload['sdp_answer'] = sdp_answer

    accept_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', accept_payload, phone_number_id=phone_number_id)
    logger.info(f"Accept result: {json.dumps(accept_result)}")

    if accept_result.get('error'):
        _update_call_status(call_id, 'accept_failed', accept_result)
        return _response(200, {
            'success': False, 'step': 'accept',
            'pre_accept': pre_accept_result,
            'error': accept_result,
        })

    _update_call_status(call_id, 'connected')

    return _response(200, {
        'success': True,
        'callId': call_id,
        'pre_accept': pre_accept_result,
        'accept': accept_result,
    })



def _terminate_call(event: Dict, request_id: str) -> Dict[str, Any]:
    """Reject or hang up a call."""
    try:
        body = json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _response(400, {'error': 'Invalid JSON in request body'})
    call_id = body.get('callId', '')
    phone_number_id = body.get('phoneNumberId', '')

    if not call_id or not phone_number_id:
        return _response(400, {'error': 'callId and phoneNumberId required'})

    logger.info(f"Terminating call {call_id} on {phone_number_id}")

    # EUM-managed phones cannot use direct Meta API for call control
    if phone_number_id in EUM_MANAGED_META_PHONE_IDS:
        logger.warning(f"Terminate call on EUM-managed phone {phone_number_id} — skipping API call")
        _update_call_status(call_id, 'terminated')
        return _response(200, {
            'success': True,
            'callId': call_id,
            'note': 'EUM-managed phone — terminate skipped (call will time out naturally)',
        })

    result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'terminate',
    }, phone_number_id=phone_number_id)

    _update_call_status(call_id, 'terminated')

    return _response(200, {
        'success': not result.get('error'),
        'callId': call_id,
        'result': result,
    })


def _outbound_call(event: Dict, request_id: str) -> Dict[str, Any]:
    """
    Initiate outbound call or send call permission request.
    Body: { phoneNumberId, to, action: 'permission_request' | 'create', sdpOffer?, bodyText?, recipientBsuid? }
    """
    try:
        body = json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _response(400, {'error': 'Invalid JSON in request body'})
    phone_number_id = body.get('phoneNumberId', '')
    to_number = body.get('to', '')
    action = body.get('action', 'permission_request')
    recipient_bsuid = body.get('recipientBsuid', '')

    if not phone_number_id or (not to_number and not recipient_bsuid):
        return _response(400, {'error': 'phoneNumberId and to (or recipientBsuid) required'})

    # EUM-managed phones cannot use direct Meta API for outbound calls
    if phone_number_id in EUM_MANAGED_META_PHONE_IDS:
        logger.warning(f"Outbound call on EUM-managed phone {phone_number_id} — not supported")
        return _response(200, {
            'success': False,
            'error': 'EUM-managed phone — outbound calling not supported via direct API',
            'hint': 'This phone is linked to AWS Social Messaging. Outbound calls only work on Direct API phones (WABA3).',
        })

    if action == 'permission_request':
        # Send interactive call permission request message
        body_text = body.get('bodyText', 'Can we call you to discuss your query?')
        payload = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'interactive',
            'interactive': {
                'type': 'call_permission_request',
                'body': {'text': body_text},
            },
        }
        # Add BSUID recipient if available (per Meta BSUID docs)
        if recipient_bsuid:
            payload['recipient'] = recipient_bsuid
        result = _meta_api_call(f"{phone_number_id}/messages", 'POST', payload, phone_number_id=phone_number_id)
        return _response(200, {'success': not result.get('error'), 'action': 'permission_request', 'result': result})

    elif action == 'create':
        # Initiate outbound call with SDP offer
        sdp_offer = body.get('sdpOffer', '')
        if not sdp_offer:
            return _response(400, {'error': 'sdpOffer required for outbound call'})
        payload = {
            'messaging_product': 'whatsapp',
            'action': 'create',
            'to': to_number,
            'sdp_offer': sdp_offer,
        }
        # Add BSUID recipient if available (per Meta Calling API BSUID docs)
        if recipient_bsuid:
            payload['recipient'] = recipient_bsuid
        result = _meta_api_call(f"{phone_number_id}/calls", 'POST', payload, phone_number_id=phone_number_id)
        return _response(200, {'success': not result.get('error'), 'action': 'create', 'result': result})

    return _response(400, {'error': f'Unknown action: {action}'})


# ─── Auto-Pickup Configuration ──────────────────────────────────────
# When enabled, incoming calls are automatically answered and a pre-recorded
# IVR greeting is sent as a WhatsApp audio message to the caller, then call disconnects.
# Default: ON — auto-pickup is enabled by default.
# Toggle via SystemConfig table or environment variable.

SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
DEFAULT_IVR_URL = os.environ.get('AUTO_PICKUP_IVR_URL', 'https://app.wecare.digital/stream/media/ivr/ivr.mp3')  # IVR audio greeting via CloudFront
AUTO_PICKUP_DEFAULT = os.environ.get('AUTO_PICKUP_ENABLED', 'true').lower() == 'true'

# AI Bot config
AI_AGENT_ID = os.environ.get('AI_AGENT_ID', '')
AI_AGENT_ALIAS = os.environ.get('AI_AGENT_ALIAS', '')
AI_KB_ID = os.environ.get('AI_KB_ID', '')
AI_VOICE_ID = os.environ.get('AI_VOICE_ID', 'Kajal')
AI_LANGUAGE = os.environ.get('AI_LANGUAGE', 'en-IN')
TRANSCRIBE_LANGUAGE = os.environ.get('TRANSCRIBE_LANGUAGE', 'en-IN')

s3 = boto3.client('s3', region_name=REGION)
social_messaging = boto3.client('socialmessaging', region_name=REGION)
polly_client = boto3.client('polly', region_name=REGION)
transcribe_client = boto3.client('transcribe', region_name=REGION)
bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=REGION)

# Phone number ID mapping for outbound audio via EUM
# Phone number ID mapping for outbound audio via Direct API
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-waba3-direct-1016149501586345')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-waba-t-direct-1055232054343117')
PHONE_NUMBER_ID_3 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_3', 'phone-number-id-waba3-direct-945798751960485')

# WABA3 uses Direct Meta API (no EUM) — track which phone IDs are Direct API
DIRECT_API_META_PHONE_IDS = {WABA3_PHONE_META_ID}

# EUM-managed phones: WABA1 and WABA2 are linked to AWS Social Messaging (EUM).
# Direct Meta Graph API calls (pre_accept, accept, terminate, messages) return 403
# for these phones. Messaging goes through AWS SDK; calling API is NOT supported by EUM.
# For these phones, IVR sends the menu via EUM SDK and skips pre_accept/terminate.
# Both phones are now on Direct API WABAs (no EUM). Full call control is supported.
# PHONE1 is pending registration on WABA3, PHONE2 is active on WABA-T.
EUM_MANAGED_META_PHONE_IDS = set()  # No EUM-managed phones anymore


def _is_auto_pickup_enabled() -> bool:
    """Check if auto-pickup is enabled via SystemConfig table."""
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        result = table.get_item(Key={'id': 'whatsapp_calling_auto_pickup'})
        item = result.get('Item')
        if item:
            return str(item.get('configValue', 'false')).lower() == 'true'
    except Exception as e:
        logger.warning(f"Failed to read auto-pickup config: {e}")
    return AUTO_PICKUP_DEFAULT


def _get_auto_pickup_audio_url() -> Optional[str]:
    """Get the IVR audio URL for auto-pickup greeting.
    Uses direct URL by default: https://app.wecare.digital/stream/media/ivr/ivr.mp3
    Can be overridden via SystemConfig table (key: whatsapp_calling_ivr_url).
    """
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        result = table.get_item(Key={'id': 'whatsapp_calling_ivr_url'})
        item = result.get('Item')
        if item and item.get('configValue'):
            return str(item['configValue']).strip()
    except Exception as e:
        logger.warning(f"Failed to read IVR URL config: {e}")
    return DEFAULT_IVR_URL


def _auto_pickup_and_play(call_id: str, phone_number_id: str, from_number: str, sdp_offer: str) -> None:
    """
    IVR mode: Pre-accept the call, send an interactive IVR menu via WhatsApp
    message, then terminate the call. The caller taps a button to route to
    the right department/action.

    For EUM-managed phones (WABA1, WABA2): Direct Meta API returns 403, so we
    skip pre_accept/terminate and just send the IVR menu via AWS EUM SDK.
    The call will ring and eventually time out on the caller's end, but they
    get the IVR menu as a WhatsApp message immediately.

    For Direct API phones (WABA3): Full flow — pre_accept → IVR menu → terminate.
    """
    is_eum = phone_number_id in EUM_MANAGED_META_PHONE_IDS

    logger.info(json.dumps({
        'event': 'ivr_start',
        'call_id': call_id,
        'from': from_number,
        'phone_number_id': phone_number_id,
        'is_eum_managed': is_eum,
    }))

    if is_eum:
        # EUM-managed: Skip pre_accept (would 403), just send IVR menu via EUM SDK
        logger.info(f"IVR EUM mode: skipping pre_accept for EUM-managed phone {phone_number_id}")
        _update_call_status(call_id, 'ivr_eum_mode')
        _send_ivr_menu(phone_number_id, from_number, call_id)
        _update_call_status(call_id, 'ivr_completed')
        return

    # Direct API (WABA3): Full pre_accept → IVR menu → terminate flow
    # Step 1: Pre-accept to stop ringing
    pre_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'pre_accept',
    }, phone_number_id=phone_number_id)
    logger.info(f"IVR pre_accept: {json.dumps(pre_result)}")

    if pre_result.get('error'):
        logger.error(f"IVR pre_accept failed: {json.dumps(pre_result)}")
        _update_call_status(call_id, 'ivr_failed', {'failStep': 'pre_accept'})
        # Still send IVR menu even if pre_accept fails
    else:
        _update_call_status(call_id, 'ivr_active')

    # Step 2: Send IVR menu via WhatsApp interactive message
    _send_ivr_menu(phone_number_id, from_number, call_id)

    # Step 3: Terminate the call after a short delay
    time.sleep(3)
    try:
        term_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
            'messaging_product': 'whatsapp',
            'call_id': call_id,
            'action': 'terminate',
        }, phone_number_id=phone_number_id)
        logger.info(f"IVR terminate: {json.dumps(term_result)}")
    except Exception as e:
        logger.info(f"IVR terminate skipped: {e}")

    _update_call_status(call_id, 'ivr_completed')


# ─── IVR Menu System ────────────────────────────────────────────────
# Configurable IVR menus per phone number (tenant).
# Each menu has a greeting text and interactive buttons.
# Button IDs are prefixed with 'ivr_' so the inbound handler can route them.

IVR_MENUS = {
    PHONE1_META_ID: {
        'greeting': (
            "📞 *WECARE.DIGITAL* — Thanks for calling!\n\n"
            "We're here to help. Please select an option below:"
        ),
        'buttons': [
            {'id': 'ivr_sales', 'title': '🛒 Sales & Orders'},
            {'id': 'ivr_support', 'title': '🔧 Support'},
            {'id': 'ivr_ai', 'title': '🤖 AI Assistant'},
        ],
        'footer': 'Reply anytime or send a voice note for instant AI help',
    },
    PHONE2_META_ID: {
        'greeting': (
            "📞 *Manish Agarwal* — Thanks for calling!\n\n"
            "How can I help you today?"
        ),
        'buttons': [
            {'id': 'ivr_callback', 'title': '📞 Request Callback'},
            {'id': 'ivr_support', 'title': '💬 Chat Support'},
            {'id': 'ivr_ai', 'title': '🤖 AI Assistant'},
        ],
        'footer': 'You can also send a voice note for instant AI help',
    },
    WABA3_PHONE_META_ID: {
        'greeting': (
            "📞 *WECARE.DIGITAL* — Thanks for calling!\n\n"
            "We're here to help. Please select an option below:"
        ),
        'buttons': [
            {'id': 'ivr_sales', 'title': '🛒 Sales & Orders'},
            {'id': 'ivr_support', 'title': '🔧 Support'},
            {'id': 'ivr_ai', 'title': '🤖 AI Assistant'},
        ],
        'footer': 'Reply anytime or send a voice note for instant AI help',
    },
}

# Default IVR menu for unknown phone numbers
IVR_DEFAULT_MENU = {
    'greeting': (
        "📞 Thanks for calling!\n\n"
        "Please select an option:"
    ),
    'buttons': [
        {'id': 'ivr_support', 'title': '💬 Support'},
        {'id': 'ivr_ai', 'title': '🤖 AI Assistant'},
        {'id': 'ivr_callback', 'title': '📞 Callback'},
    ],
    'footer': 'Send a voice note for instant AI help',
}

# IVR response handlers — what to send when user taps each button
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
        'notify_team': True,
        'department': 'sales',
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
        'notify_team': True,
        'department': 'support',
    },
    'ivr_ai': {
        'text': (
            "🤖 *AI Assistant*\n\n"
            "I'm ready to help! You can:\n\n"
            "• Type your question\n"
            "• Send a *voice note* — I'll listen and reply with voice\n"
            "• Send a *photo* — I can analyze images too\n\n"
            "Ask me anything about our products, services, or orders."
        ),
        'notify_team': False,
        'department': 'ai',
    },
    'ivr_callback': {
        'text': (
            "📞 *Callback Request*\n\n"
            "Got it! We'll call you back as soon as possible.\n\n"
            "If you'd like to specify a preferred time, just type it "
            "(e.g. \"Call me at 3 PM\" or \"Tomorrow morning\")."
        ),
        'notify_team': True,
        'department': 'callback',
    },
}


def _get_ivr_menu(phone_number_id: str) -> Dict:
    """Get the IVR menu config for a phone number. Falls back to default."""
    # Check SystemConfig for custom IVR menu (allows runtime updates)
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        result = table.get_item(Key={'id': f'ivr_menu_{phone_number_id}'})
        item = result.get('Item')
        if item and item.get('configValue'):
            custom = json.loads(str(item['configValue']))
            if custom.get('greeting') and custom.get('buttons'):
                return custom
    except Exception as e:
        logger.debug(f'IVR menu config lookup failed for {phone_number_id}: {e}')
    return IVR_MENUS.get(phone_number_id, IVR_DEFAULT_MENU)


def _send_ivr_menu(phone_number_id: str, to_number: str, call_id: str) -> None:
    """Send the IVR interactive button menu to the caller via WhatsApp."""
    menu = _get_ivr_menu(phone_number_id)
    aws_phone_id = _get_aws_phone_id(phone_number_id)

    # Send greeting audio first (if configured)
    audio_url = _get_auto_pickup_audio_url()
    if audio_url:
        _send_audio_to_caller(phone_number_id, to_number, audio_url, call_id)

    # Build interactive button message (max 3 buttons per Meta API)
    buttons = []
    for btn in menu.get('buttons', [])[:3]:
        buttons.append({
            'type': 'reply',
            'reply': {'id': btn['id'], 'title': btn['title'][:20]},  # 20 char limit
        })

    interactive_msg = {
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': menu.get('greeting', 'How can we help?')},
            'action': {'buttons': buttons},
        },
    }

    footer = menu.get('footer')
    if footer:
        interactive_msg['interactive']['footer'] = {'text': footer[:60]}  # 60 char limit

    result = _send_via_aws(aws_phone_id, to_number, interactive_msg)

    if result.get('error'):
        # Fallback: send as plain text if interactive fails (e.g. outside 24h window)
        logger.warning(f"IVR interactive failed, trying text fallback: {result}")
        fallback_text = menu.get('greeting', 'How can we help?')
        for btn in menu.get('buttons', []):
            fallback_text += f"\n\nReply *{btn['id'].replace('ivr_', '').upper()}* for {btn['title']}"
        _send_via_aws(aws_phone_id, to_number, {
            'type': 'text',
            'text': {'body': fallback_text},
        })
    else:
        logger.info(f"IVR menu sent to {to_number}: messageId={result.get('messageId')}")

    # Store IVR session in call log for tracking
    _update_call_status(call_id, 'ivr_menu_sent', {
        'ivrMenu': phone_number_id,
        'buttonsOffered': [b['id'] for b in menu.get('buttons', [])],
    })


def _get_aws_phone_id(meta_phone_number_id: str) -> str:
    """Map Meta phone_number_id to AWS EUM phone-number-id."""
    META_TO_AWS = {
        PHONE1_META_ID: PHONE_NUMBER_ID_1,
        PHONE2_META_ID: PHONE_NUMBER_ID_2,
        WABA3_PHONE_META_ID: PHONE_NUMBER_ID_3,
    }
    return META_TO_AWS.get(meta_phone_number_id, PHONE_NUMBER_ID_1)


def _send_via_aws(aws_phone_id: str, to_number: str, message_payload: Dict) -> Dict:
    """Send a WhatsApp message via AWS Social Messaging SDK or Direct Meta API for WABA3."""
    # AWS requires '+' prefix on phone numbers
    if not to_number.startswith('+'):
        to_number = f'+{to_number}'
    message_payload['to'] = to_number
    message_payload['messaging_product'] = 'whatsapp'

    # All phones are Direct API now — send via Meta Graph API
    DIRECT_API_PHONES = {
        PHONE_NUMBER_ID_1: PHONE1_META_ID,             # WABA3: +91 93309 94400 (pending registration)
        PHONE_NUMBER_ID_2: PHONE2_META_ID,             # WABA-T: +91 99033 00044
        PHONE_NUMBER_ID_3: WABA3_PHONE_META_ID,        # WABA3 (alias)
    }
    if aws_phone_id in DIRECT_API_PHONES:
        meta_phone_id = DIRECT_API_PHONES[aws_phone_id]
        try:
            result = _meta_api_call(
                f"{meta_phone_id}/messages", 'POST',
                message_payload, phone_number_id=meta_phone_id
            )
            if result.get('error'):
                logger.error(f"Direct API send failed for {meta_phone_id}: {result}")
                return result
            msg_id = ''
            messages = result.get('messages', [])
            if messages:
                msg_id = messages[0].get('id', '')
            logger.info(f"Direct API send success ({meta_phone_id}): messageId={msg_id}")
            return {'success': True, 'messageId': msg_id}
        except Exception as e:
            logger.error(f"Direct API send failed for {meta_phone_id}: {e}")
            return {'error': True, 'detail': str(e)}

    try:
        result = social_messaging.send_whatsapp_message(
            originationPhoneNumberId=aws_phone_id,
            message=json.dumps(message_payload).encode('utf-8'),
            metaApiVersion=META_API_VERSION,
        )
        logger.info(f"AWS send success: messageId={result.get('messageId')}")
        return {'success': True, 'messageId': result.get('messageId')}
    except Exception as e:
        logger.error(f"AWS send failed: {e}")
        return {'error': True, 'detail': str(e)}


def _send_audio_to_caller(phone_number_id: str, to_number: str, audio_url: str, call_id: str) -> None:
    """Send the greeting audio as a WhatsApp audio message via AWS Social Messaging."""
    try:
        aws_phone_id = _get_aws_phone_id(phone_number_id)
        result = _send_via_aws(aws_phone_id, to_number, {
            'type': 'audio',
            'audio': {'link': audio_url},
        })
        logger.info(f"AUTO-PICKUP audio sent to {to_number}: {json.dumps(result)}")
    except Exception as e:
        logger.error(f"Failed to send auto-pickup audio: {e}")


# ─── Active Calls (for frontend polling) ────────────────────────────

def _get_active_calls(params: Dict, request_id: str) -> Dict[str, Any]:
    """Get calls with status 'ringing', 'pre_accepted', or 'connected' for the frontend."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        result = table.scan(
            FilterExpression='#s IN (:r, :c, :a, :p)',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':r': 'ringing',
                ':c': 'connected',
                ':a': 'auto_answered',
                ':p': 'pre_accepted',
            },
        )
        items = result.get('Items', [])
        # Convert Decimal for JSON
        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = float(v)
        items.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        return _response(200, {'calls': items, 'count': len(items)})
    except Exception as e:
        logger.error(f"Get active calls error: {e}")
        return _response(200, {'calls': [], 'count': 0, 'error': str(e)})


# ─── Auto-Pickup Config API ─────────────────────────────────────────
# GET  /whatsapp-calling/config  → Get auto-pickup config
# POST /whatsapp-calling/config  → Update auto-pickup config

def _get_config(request_id: str) -> Dict[str, Any]:
    """Get auto-pickup configuration including mode."""
    enabled = _is_auto_pickup_enabled()
    audio_url = _get_auto_pickup_audio_url()
    mode = _get_auto_pickup_mode()
    return _response(200, {
        'autoPickup': enabled,
        'ivrUrl': audio_url,
        'defaultIvrUrl': DEFAULT_IVR_URL,
        'autoPickupMode': mode,
    })


def _get_auto_pickup_mode() -> str:
    """Get auto-pickup mode from SystemConfig: 'manual' | 'ivr'.
    AI mode removed — IVR-only approach matching WABA3 config.
    """
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        result = table.get_item(Key={'id': 'whatsapp_calling_auto_pickup_mode'})
        item = result.get('Item')
        if item and item.get('configValue') in ('manual', 'ivr'):
            return str(item['configValue'])
    except Exception as e:
        logger.warning(f"Failed to read auto-pickup mode: {e}")
    return 'ivr'  # default — IVR-only like WABA3


def _update_config(event: Dict, request_id: str) -> Dict[str, Any]:
    """Update auto-pickup configuration (toggle + IVR URL + mode)."""
    try:
        body = json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _response(400, {'error': 'Invalid JSON in request body'})
    enabled = body.get('autoPickup')
    ivr_url = body.get('ivrUrl')
    mode = body.get('autoPickupMode')  # 'manual' | 'ivr'

    table = dynamodb.Table(SYSTEM_CONFIG_TABLE)

    if enabled is not None:
        try:
            table.put_item(Item={
                'id': 'whatsapp_calling_auto_pickup',
                'configValue': str(enabled).lower(),
                'updatedAt': Decimal(str(int(time.time()))),
            })
            logger.info(f"Auto-pickup set to: {enabled}")
        except Exception as e:
            logger.error(f"Failed to update auto-pickup config: {e}")
            return _response(500, {'error': str(e)})

    if ivr_url is not None:
        try:
            table.put_item(Item={
                'id': 'whatsapp_calling_ivr_url',
                'configValue': ivr_url.strip(),
                'updatedAt': Decimal(str(int(time.time()))),
            })
            logger.info(f"IVR URL set to: {ivr_url}")
        except Exception as e:
            logger.error(f"Failed to update IVR URL config: {e}")
            return _response(500, {'error': str(e)})

    if mode is not None and mode in ('manual', 'ivr'):
        try:
            table.put_item(Item={
                'id': 'whatsapp_calling_auto_pickup_mode',
                'configValue': mode,
                'updatedAt': Decimal(str(int(time.time()))),
            })
            logger.info(f"Auto-pickup mode set to: {mode}")
        except Exception as e:
            logger.error(f"Failed to update auto-pickup mode: {e}")
            return _response(500, {'error': str(e)})

    return _response(200, {'success': True, 'autoPickup': enabled, 'ivrUrl': ivr_url, 'autoPickupMode': mode})


# ─── AI Bot Endpoint ─────────────────────────────────────────────────

def _ai_respond(event: Dict, request_id: str) -> Dict[str, Any]:
    """
    AI Bot endpoint: caller audio → transcribe → Bedrock → Polly TTS → audio URL.

    Frontend sends: { audioBase64, callerPhone, mimeType, text?, sessionId? }
    - audioBase64: base64-encoded webm/opus from browser MediaRecorder
    - text: direct text input (skip transcription if browser did speech-to-text)
    - callerPhone: caller's phone number
    - mimeType: 'audio/webm' (default)

    Returns: { audioUrl, transcribedText, aiResponse, sessionId }
    """
    import base64 as b64

    try:
        body = json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _response(400, {'error': 'Invalid JSON in request body'})
    audio_base64 = body.get('audioBase64', '')
    caller_phone = body.get('callerPhone', 'unknown')
    mime_type = body.get('mimeType', 'audio/webm')
    text_input = body.get('text', '')
    session_id = body.get('sessionId', str(uuid.uuid4()))

    logger.info(json.dumps({
        'event': 'ai_respond_start', 'callerPhone': caller_phone,
        'hasAudio': bool(audio_base64), 'hasText': bool(text_input),
        'sessionId': session_id, 'requestId': request_id,
    }))

    try:
        transcribed_text = text_input

        # Step 1-2: Transcribe audio if no direct text
        if not transcribed_text and audio_base64:
            transcribed_text = _transcribe_audio(audio_base64, mime_type, session_id, request_id)

        if not transcribed_text:
            return _response(200, {'error': 'No speech detected', 'audioUrl': None, 'noSpeech': True})

        logger.info(f"[AI-RESPOND] Transcribed: {transcribed_text[:200]}")

        # Step 3: Bedrock Agent response
        ai_response = _get_bedrock_response(transcribed_text, session_id, request_id)
        if not ai_response:
            ai_response = "Sorry, I couldn't process your request. Please call us at +91 9330994400 for assistance."

        logger.info(f"[AI-RESPOND] Bedrock: {ai_response[:200]}")

        # Step 4-5: Polly TTS → S3 presigned URL
        audio_url = _generate_tts_url(ai_response, session_id, request_id)

        return _response(200, {
            'audioUrl': audio_url,
            'transcribedText': transcribed_text,
            'aiResponse': ai_response,
            'sessionId': session_id,
        })

    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_respond_error',
            'error': str(e),
            'requestId': request_id,
        }), exc_info=True)
        return _response(500, {'error': 'AI response generation failed', 'audioUrl': None})


def _transcribe_audio(audio_base64: str, mime_type: str, session_id: str, request_id: str) -> str:
    """Decode base64 audio, upload to S3, run Transcribe batch job, return text."""
    import base64 as b64

    ext = 'webm' if 'webm' in mime_type else 'ogg' if 'ogg' in mime_type else 'mp3'
    media_format = 'webm' if ext == 'webm' else 'ogg' if ext == 'ogg' else 'mp3'

    audio_bytes = b64.b64decode(audio_base64)
    s3_key = f"stack/whatsapp-media/calling-ai/wecare-digital-{session_id[:8]}_{int(time.time())}.{ext}"

    s3.put_object(Bucket=MEDIA_BUCKET, Key=s3_key, Body=audio_bytes, ContentType=mime_type)
    logger.info(f"[TRANSCRIBE] Uploaded {len(audio_bytes)} bytes to s3://{MEDIA_BUCKET}/{s3_key}")

    job_name = f"wa-call-{session_id[:8]}-{int(time.time())}"
    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': f"s3://{MEDIA_BUCKET}/{s3_key}"},
        MediaFormat=media_format,
        LanguageCode=TRANSCRIBE_LANGUAGE,
        OutputBucketName=MEDIA_BUCKET,
        OutputKey=f"stack/whatsapp-media/calling-ai/wecare-digital-transcript-{job_name}.json",
    )

    # Poll for completion (max 30s)
    for _ in range(30):
        time.sleep(1)
        status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        job_status = status['TranscriptionJob']['TranscriptionJobStatus']
        if job_status == 'COMPLETED':
            transcript_key = f"stack/whatsapp-media/calling-ai/wecare-digital-transcript-{job_name}.json"
            obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=transcript_key)
            transcript_data = json.loads(obj['Body'].read().decode('utf-8'))
            text = transcript_data.get('results', {}).get('transcripts', [{}])[0].get('transcript', '')
            logger.info(f"[TRANSCRIBE] Done: {text[:200]}")
            try:
                s3.delete_object(Bucket=MEDIA_BUCKET, Key=s3_key)
                s3.delete_object(Bucket=MEDIA_BUCKET, Key=transcript_key)
            except Exception as e:
                logger.debug(f'Transcription S3 cleanup failed: {e}')
            return text.strip()
        elif job_status == 'FAILED':
            reason = status['TranscriptionJob'].get('FailureReason', 'unknown')
            logger.error(f"[TRANSCRIBE] Failed: {reason}")
            return ''

    logger.warning(f"[TRANSCRIBE] Timed out after 30s")
    return ''


def _get_bedrock_response(user_text: str, session_id: str, request_id: str) -> str:
    """Send text to Bedrock Agent (external/customer-facing) and get response."""
    agent_id = AI_AGENT_ID or 'Z4YAK0ZLBO'
    agent_alias = AI_AGENT_ALIAS or 'WANPKHQGIB'

    try:
        response = bedrock_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias,
            sessionId=session_id,
            inputText=user_text,
            enableTrace=False,
        )

        completion = ""
        for evt in response.get('completion', []):
            if 'chunk' in evt:
                chunk_data = evt['chunk']
                if 'bytes' in chunk_data:
                    completion += chunk_data['bytes'].decode('utf-8')

        if completion:
            return completion.strip()

        # Fallback to KB
        kb_id = AI_KB_ID or 'static-faq'
        if kb_id:
            return _query_kb_direct(user_text, kb_id, request_id)
        return ''

    except Exception as e:
        logger.error(f"[BEDROCK] Error: {e}", exc_info=True)
        kb_id = AI_KB_ID or 'static-faq'
        if kb_id:
            return _query_kb_direct(user_text, kb_id, request_id)
        return ''


def _query_kb_direct(user_text: str, kb_id: str, request_id: str) -> str:
    """Query static knowledge base as fallback (FREE — no OpenSearch/Bedrock KB)."""
    try:
        from static_knowledge_base import search_knowledge_base as static_kb_search
        result = static_kb_search(user_text, max_results=2)
        if result:
            logger.info(f"[KB] Static FAQ match ({len(result)} chars)")
            return result
        return ''
    except ImportError:
        logger.warning("[KB] static_knowledge_base not available")
        return ''
    except Exception as e:
        logger.error(f"[KB] Error: {e}")
        return ''


def _generate_tts_url(text: str, session_id: str, request_id: str) -> Optional[str]:
    """Generate Polly TTS audio, upload to S3, return presigned URL."""
    try:
        ssml_text = f'<speak><prosody rate="medium">{text[:2900]}</prosody></speak>'
        polly_response = polly_client.synthesize_speech(
            Text=ssml_text, TextType='ssml', OutputFormat='mp3',
            VoiceId=AI_VOICE_ID or 'Kajal', Engine='neural',
            LanguageCode=AI_LANGUAGE or 'en-IN',
        )
        audio_stream = polly_response['AudioStream'].read()
        s3_key = f"stack/whatsapp-media/calling-ai/wecare-digital-tts-{session_id[:8]}_{int(time.time())}.mp3"
        s3.put_object(Bucket=MEDIA_BUCKET, Key=s3_key, Body=audio_stream, ContentType='audio/mpeg')
        url = s3.generate_presigned_url('get_object', Params={'Bucket': MEDIA_BUCKET, 'Key': s3_key}, ExpiresIn=3600)
        logger.info(f"[TTS] Generated {len(audio_stream)} bytes → {s3_key}")
        return url
    except Exception as e:
        logger.error(f"[TTS] SSML failed, retrying plain: {e}")
        try:
            polly_response = polly_client.synthesize_speech(
                Text=text[:2900], TextType='text', OutputFormat='mp3',
                VoiceId=AI_VOICE_ID or 'Kajal', Engine='neural',
                LanguageCode=AI_LANGUAGE or 'en-IN',
            )
            audio_stream = polly_response['AudioStream'].read()
            s3_key = f"stack/whatsapp-media/calling-ai/wecare-digital-tts-{session_id[:8]}_{int(time.time())}.mp3"
            s3.put_object(Bucket=MEDIA_BUCKET, Key=s3_key, Body=audio_stream, ContentType='audio/mpeg')
            return s3.generate_presigned_url('get_object', Params={'Bucket': MEDIA_BUCKET, 'Key': s3_key}, ExpiresIn=3600)
        except Exception as e2:
            logger.error(f"[TTS] Plain text also failed: {e2}")
            return None


# ─── Storage Helpers ─────────────────────────────────────────────────

def _store_call_log(item: Dict) -> None:
    """Store call event in DynamoDB."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        item['id'] = f"{item.get('callId', 'unknown')}_{item.get('eventType', 'unknown')}_{int(time.time())}"
        clean = {k: v for k, v in item.items() if v is not None and v != ''}
        table.put_item(Item=clean)
        logger.info(f"Stored call log: {item.get('id')}")
    except Exception as e:
        logger.error(f"Store call log error: {e}")


def _update_call_status(call_id: str, new_status: str, extra: Dict = None) -> None:
    """Update the status of the most recent log entry for a call."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        # Scan with filter — no GSI on callId
        from boto3.dynamodb.conditions import Attr
        result = table.scan(
            FilterExpression=Attr('callId').eq(call_id) & Attr('eventType').eq('connect'),
            Limit=10,
        )
        items = result.get('Items', [])
        if items:
            item = items[0]
            update_expr = 'SET #s = :s, #ua = :ua'
            expr_names = {'#s': 'status', '#ua': 'updatedAt'}
            expr_values = {':s': new_status, ':ua': Decimal(str(int(time.time())))}
            if extra:
                update_expr += ', #ex = :ex'
                expr_names['#ex'] = 'apiResponse'
                expr_values[':ex'] = json.dumps(extra, default=str)[:500]
            table.update_item(
                Key={'id': item['id']},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
            logger.info(f"Updated call {call_id} status to {new_status}")
    except Exception as e:
        logger.error(f"Update call status error: {e}")


def _list_logs(params: Dict, request_id: str) -> Dict[str, Any]:
    """List call event logs."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        result = table.scan(Limit=int(params.get('limit', 100)))
        items = result.get('Items', [])
        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = float(v)
        items.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        return _response(200, {'logs': items, 'count': len(items)})
    except Exception as e:
        logger.error(f"List logs error: {e}")
        return _response(200, {'logs': [], 'count': 0, 'error': str(e)})


def _clear_logs(request_id: str) -> Dict[str, Any]:
    """Clear all call logs (paginated to handle large tables)."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        deleted = 0
        scan_kwargs = {'ProjectionExpression': 'id'}
        while True:
            result = table.scan(**scan_kwargs)
            items = result.get('Items', [])
            if not items:
                break
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'id': item['id']})
                    deleted += 1
            if 'LastEvaluatedKey' not in result:
                break
            scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']
        return _response(200, {'success': True, 'deletedCount': deleted})
    except Exception as e:
        return _response(200, {'success': False, 'error': str(e)})


def _response(status_code: int, body: Dict, resp_origin: str = '') -> Dict[str, Any]:
    """HTTP response with CORS."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(resp_origin or origin),
        'body': json.dumps(body, default=str),
    }
