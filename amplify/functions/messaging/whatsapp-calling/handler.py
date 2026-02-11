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
import boto3
import urllib.request
import urllib.error
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)
secrets_client = boto3.client('secretsmanager', region_name=REGION)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'wecare_calling_verify_2026')
CALL_LOG_TABLE = os.environ.get('CALL_LOG_TABLE', 'base-wecare-digital-WhatsAppCallingTable')
META_TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')
TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days

# Dual WABA token support
WABA1_ID = '1912405516040025'
WABA2_ID = '1633959101297902'
PHONE1_META_ID = '960395407161423'
PHONE2_META_ID = '997428863451102'
WABA2_IDS = {WABA2_ID, PHONE2_META_ID}

# Cache Meta tokens (dual)
_token_cache = {}

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
}


def _get_meta_token(phone_number_id: str = None) -> str:
    """Get the correct Meta token based on phone number ID (dual WABA support)."""
    use_waba2 = phone_number_id in WABA2_IDS if phone_number_id else False
    cache_key = 'token2' if use_waba2 else 'token1'

    if cache_key in _token_cache:
        return _token_cache[cache_key]

    # Load both tokens from secret
    if 'loaded' not in _token_cache:
        try:
            resp = secrets_client.get_secret_value(SecretId=META_TOKEN_SECRET)
            secret = resp.get('SecretString', '')
            try:
                data = json.loads(secret)
                _token_cache['token1'] = (data.get('access_token') or '').strip()
                _token_cache['token2'] = (data.get('access_token_waba2') or data.get('access_token') or '').strip()
            except (json.JSONDecodeError, TypeError):
                _token_cache['token1'] = secret.strip()
                _token_cache['token2'] = secret.strip()
            _token_cache['loaded'] = True
            logger.info(f"Loaded dual tokens: token1={len(_token_cache.get('token1',''))}chars, token2={len(_token_cache.get('token2',''))}chars")
        except Exception as e:
            logger.error(f"Failed to get Meta token: {e}")
            raise

    token = _token_cache.get(cache_key, _token_cache.get('token1', ''))
    logger.info(f"Using {cache_key} for phone_number_id={phone_number_id} (use_waba2={use_waba2})")
    return token


def _meta_api_call(endpoint: str, method: str = 'POST', payload: Dict = None, phone_number_id: str = None) -> Dict:
    """Make a call to Meta Graph API with dual-token support."""
    url = f"https://graph.facebook.com/{META_API_VERSION}/{endpoint}"
    token = _get_meta_token(phone_number_id=phone_number_id)
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    data = json.dumps(payload).encode('utf-8') if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {'success': True}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Meta API error {e.code}: {error_body}")
        return {'error': True, 'status': e.code, 'detail': error_body}
    except Exception as e:
        logger.error(f"Meta API call failed: {e}")
        return {'error': True, 'detail': str(e)}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler — routes to appropriate function."""
    request_id = context.aws_request_id if context else 'local'
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
            if 'config' in path:
                return _get_config(request_id)
            if 'active' in path:
                return _get_active_calls(query_params, request_id)
            if 'logs' in path:
                return _list_logs(query_params, request_id)
            # Default GET = webhook verification
            return _verify_webhook(query_params, request_id)

        # POST routes
        if http_method == 'POST':
            if '/config' in path:
                return _update_config(event, request_id)
            if '/accept' in path:
                return _accept_call(event, request_id)
            if '/reject' in path or '/hangup' in path:
                return _terminate_call(event, request_id)
            if '/outbound' in path:
                return _outbound_call(event, request_id)
            # Default POST = webhook event from Meta
            body_str = event.get('body', '{}')
            if event.get('isBase64Encoded'):
                import base64
                body_str = base64.b64decode(body_str).decode('utf-8')
            return _handle_webhook_event(json.loads(body_str), request_id)

        # DELETE
        if http_method == 'DELETE':
            return _clear_logs(request_id)

        return _response(200, {'message': 'OK'})

    except Exception as e:
        logger.error(f"Handler error: {str(e)}", exc_info=True)
        return _response(200, {'error': str(e)})


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

def _handle_webhook_event(body: Dict, request_id: str) -> Dict[str, Any]:
    """Process incoming WhatsApp webhook events."""
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
                for call in calls:
                    _handle_call_event(waba_id, call, metadata, contacts, request_id)
            else:
                logger.info(f"Non-call field: {field}")

    return _response(200, {'status': 'processed', 'entries': len(entries)})


def _handle_call_event(waba_id: str, call: Dict, metadata: Dict, contacts: list, request_id: str) -> None:
    """Handle a single call event from webhook."""
    event_type = call.get('event', '')
    call_id = call.get('id', call.get('call_id', ''))
    from_number = call.get('from', '')
    to_number = call.get('to', '')
    direction = call.get('direction', 'USER_INITIATED')
    phone_number_id = metadata.get('phone_number_id', '')
    display_phone = metadata.get('display_phone_number', '')
    timestamp = call.get('timestamp', str(int(time.time())))

    # Extract caller name from contacts
    caller_name = ''
    if contacts:
        caller_name = contacts[0].get('profile', {}).get('name', '')

    now = int(time.time())

    logger.info(json.dumps({
        'event': 'call_event', 'type': event_type, 'call_id': call_id,
        'from': from_number, 'to': to_number, 'direction': direction,
        'phone_number_id': phone_number_id, 'caller_name': caller_name,
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
            'direction': direction,
            'eventType': 'connect',
            'status': 'ringing',
            'sdpOffer': sdp_offer,
            'sdpType': sdp_type,
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })
        logger.info(f"INBOUND CALL from {caller_name or from_number} — call_id: {call_id}, has_sdp: {bool(sdp_offer)}")

        # Auto-pickup: if enabled, answer immediately and play greeting
        if _is_auto_pickup_enabled() and phone_number_id:
            logger.info(f"AUTO-PICKUP enabled — answering call {call_id}")
            try:
                _auto_pickup_and_play(call_id, phone_number_id, from_number, sdp_offer)
            except Exception as e:
                logger.error(f"Auto-pickup failed: {e}", exc_info=True)

    elif event_type == 'terminate':
        reason = call.get('reason', 'unknown')
        duration = call.get('duration', 0)
        _store_call_log({
            'callId': call_id,
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number,
            'toNumber': to_number,
            'direction': direction,
            'eventType': 'terminate',
            'status': 'ended',
            'terminateReason': reason,
            'duration': duration,
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })

    elif event_type == 'call_permission_response':
        permission = call.get('permission', '')
        _store_call_log({
            'callId': call_id or str(uuid.uuid4()),
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number,
            'direction': direction,
            'eventType': 'permission_response',
            'status': f'permission_{permission}',
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })

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


# ─── Call Control (Accept / Reject / Hangup) ────────────────────────

def _accept_call(event: Dict, request_id: str) -> Dict[str, Any]:
    """
    Accept an incoming call: pre_accept → accept with SDP answer.
    Frontend sends: { callId, phoneNumberId, sdpAnswer }
    """
    body = json.loads(event.get('body', '{}'))
    call_id = body.get('callId', '')
    phone_number_id = body.get('phoneNumberId', '')
    sdp_answer = body.get('sdpAnswer', '')

    if not call_id or not phone_number_id:
        return _response(400, {'error': 'callId and phoneNumberId required'})

    logger.info(f"Accepting call {call_id} on {phone_number_id}, has_sdp_answer: {bool(sdp_answer)}")

    # Step 1: Pre-accept — tells Meta we're preparing to answer
    pre_accept_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'pre_accept',
    }, phone_number_id=phone_number_id)
    logger.info(f"Pre-accept result: {json.dumps(pre_accept_result)}")

    if pre_accept_result.get('error'):
        _update_call_status(call_id, 'pre_accept_failed', pre_accept_result)
        return _response(200, {
            'success': False, 'step': 'pre_accept',
            'error': pre_accept_result,
        })

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
    body = json.loads(event.get('body', '{}'))
    call_id = body.get('callId', '')
    phone_number_id = body.get('phoneNumberId', '')

    if not call_id or not phone_number_id:
        return _response(400, {'error': 'callId and phoneNumberId required'})

    logger.info(f"Terminating call {call_id} on {phone_number_id}")

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
    Body: { phoneNumberId, to, action: 'permission_request' | 'create', sdpOffer?, bodyText? }
    """
    body = json.loads(event.get('body', '{}'))
    phone_number_id = body.get('phoneNumberId', '')
    to_number = body.get('to', '')
    action = body.get('action', 'permission_request')

    if not phone_number_id or not to_number:
        return _response(400, {'error': 'phoneNumberId and to required'})

    if action == 'permission_request':
        # Send interactive call permission request message
        body_text = body.get('bodyText', 'Can we call you to discuss your query?')
        result = _meta_api_call(f"{phone_number_id}/messages", 'POST', {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'interactive',
            'interactive': {
                'type': 'call_permission_request',
                'body': {'text': body_text},
            },
        }, phone_number_id=phone_number_id)
        return _response(200, {'success': not result.get('error'), 'action': 'permission_request', 'result': result})

    elif action == 'create':
        # Initiate outbound call with SDP offer
        sdp_offer = body.get('sdpOffer', '')
        if not sdp_offer:
            return _response(400, {'error': 'sdpOffer required for outbound call'})
        result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
            'messaging_product': 'whatsapp',
            'action': 'create',
            'to': to_number,
            'sdp_offer': sdp_offer,
        }, phone_number_id=phone_number_id)
        return _response(200, {'success': not result.get('error'), 'action': 'create', 'result': result})

    return _response(400, {'error': f'Unknown action: {action}'})


# ─── Auto-Pickup Configuration ──────────────────────────────────────
# When enabled, incoming calls are automatically answered and a pre-recorded
# IVR greeting is sent as a WhatsApp audio message to the caller, then call disconnects.
# Default: ON — auto-pickup is enabled by default.
# Toggle via SystemConfig table or environment variable.

SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'base-wecare-digital-SystemConfigTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
DEFAULT_IVR_URL = os.environ.get('AUTO_PICKUP_IVR_URL', 'https://app.wecare.digital/stream/media/ivr/IVR+1.mp3')
AUTO_PICKUP_DEFAULT = os.environ.get('AUTO_PICKUP_ENABLED', 'true').lower() == 'true'

s3 = boto3.client('s3', region_name=REGION)
social_messaging = boto3.client('socialmessaging', region_name=REGION)

# Phone number ID mapping for outbound audio via EUM
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-5e020cecd221429996f6ae721cc42206')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c')


def _is_auto_pickup_enabled() -> bool:
    """Check if auto-pickup is enabled via SystemConfig table."""
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        result = table.get_item(Key={'configKey': 'whatsapp_calling_auto_pickup'})
        item = result.get('Item')
        if item:
            return str(item.get('configValue', 'false')).lower() == 'true'
    except Exception as e:
        logger.warning(f"Failed to read auto-pickup config: {e}")
    return AUTO_PICKUP_DEFAULT


def _get_auto_pickup_audio_url() -> Optional[str]:
    """Get the IVR audio URL for auto-pickup greeting.
    Uses direct URL by default: https://app.wecare.digital/stream/media/ivr/IVR+1.mp3
    Can be overridden via SystemConfig table (key: whatsapp_calling_ivr_url).
    """
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        result = table.get_item(Key={'configKey': 'whatsapp_calling_ivr_url'})
        item = result.get('Item')
        if item and item.get('configValue'):
            return str(item['configValue']).strip()
    except Exception as e:
        logger.warning(f"Failed to read IVR URL config: {e}")
    return DEFAULT_IVR_URL


def _auto_pickup_and_play(call_id: str, phone_number_id: str, from_number: str, sdp_offer: str) -> None:
    """
    Auto-pickup: pre_accept → accept the call, then send the greeting audio
    as a WhatsApp audio message to the caller.

    Flow:
    1. pre_accept → accept (no SDP answer needed for server-side auto-pickup,
       Meta will handle media if we just accept)
    2. Send audio message to caller via WhatsApp messaging API
    3. After audio plays, terminate the call (or let caller hang up)
    """
    logger.info(f"AUTO-PICKUP: Answering call {call_id} from {from_number}")

    # Step 1: Pre-accept
    pre_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'pre_accept',
    }, phone_number_id=phone_number_id)
    logger.info(f"AUTO-PICKUP pre_accept: {json.dumps(pre_result)}")

    if pre_result.get('error'):
        logger.error(f"AUTO-PICKUP pre_accept failed: {json.dumps(pre_result)}")
        _update_call_status(call_id, 'auto_pickup_failed')
        return

    # Step 2: Accept (server-side, no browser SDP answer)
    accept_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'accept',
    }, phone_number_id=phone_number_id)
    logger.info(f"AUTO-PICKUP accept: {json.dumps(accept_result)}")

    if accept_result.get('error'):
        logger.error(f"AUTO-PICKUP accept failed: {json.dumps(accept_result)}")
        _update_call_status(call_id, 'auto_pickup_failed')
        return

    _update_call_status(call_id, 'auto_answered')

    # Step 3: Send greeting audio message to the caller
    audio_url = _get_auto_pickup_audio_url()
    if audio_url:
        _send_audio_to_caller(phone_number_id, from_number, audio_url, call_id)
    else:
        logger.warning("AUTO-PICKUP: No greeting audio configured, call answered silently")

    # Step 4: Terminate after a delay (let audio play ~15s)
    # Note: In production you might use Step Functions or a delayed SQS message.
    # For now, we terminate after sending the audio — the caller hears the
    # audio message in their chat and the call ends.
    import threading

    def _delayed_hangup():
        time.sleep(15)
        logger.info(f"AUTO-PICKUP: Hanging up call {call_id}")
        _meta_api_call(f"{phone_number_id}/calls", 'POST', {
            'messaging_product': 'whatsapp',
            'call_id': call_id,
            'action': 'terminate',
        }, phone_number_id=phone_number_id)
        _update_call_status(call_id, 'auto_completed')

    t = threading.Thread(target=_delayed_hangup, daemon=True)
    t.start()


def _get_aws_phone_id(meta_phone_number_id: str) -> str:
    """Map Meta phone_number_id to AWS EUM phone-number-id."""
    META_TO_AWS = {
        PHONE1_META_ID: PHONE_NUMBER_ID_1,
        PHONE2_META_ID: PHONE_NUMBER_ID_2,
    }
    return META_TO_AWS.get(meta_phone_number_id, PHONE_NUMBER_ID_1)


def _send_via_aws(aws_phone_id: str, to_number: str, message_payload: Dict) -> Dict:
    """Send a WhatsApp message via AWS Social Messaging SDK."""
    # AWS requires '+' prefix on phone numbers
    if not to_number.startswith('+'):
        to_number = f'+{to_number}'
    message_payload['to'] = to_number
    message_payload['messaging_product'] = 'whatsapp'
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
    """Get calls with status 'ringing' or 'connected' for the frontend."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        result = table.scan(
            FilterExpression='#s IN (:r, :c, :a)',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':r': 'ringing',
                ':c': 'connected',
                ':a': 'auto_answered',
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
    """Get auto-pickup configuration."""
    enabled = _is_auto_pickup_enabled()
    audio_url = _get_auto_pickup_audio_url()
    return _response(200, {
        'autoPickup': enabled,
        'ivrUrl': audio_url,
        'defaultIvrUrl': DEFAULT_IVR_URL,
    })


def _update_config(event: Dict, request_id: str) -> Dict[str, Any]:
    """Update auto-pickup configuration (toggle + IVR URL)."""
    body = json.loads(event.get('body', '{}'))
    enabled = body.get('autoPickup')
    ivr_url = body.get('ivrUrl')

    table = dynamodb.Table(SYSTEM_CONFIG_TABLE)

    if enabled is not None:
        try:
            table.put_item(Item={
                'configKey': 'whatsapp_calling_auto_pickup',
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
                'configKey': 'whatsapp_calling_ivr_url',
                'configValue': ivr_url.strip(),
                'updatedAt': Decimal(str(int(time.time()))),
            })
            logger.info(f"IVR URL set to: {ivr_url}")
        except Exception as e:
            logger.error(f"Failed to update IVR URL config: {e}")
            return _response(500, {'error': str(e)})

    return _response(200, {'success': True, 'autoPickup': enabled, 'ivrUrl': ivr_url})


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
        # Find the connect record for this call
        result = table.scan(
            FilterExpression='#cid = :cid AND #et = :et',
            ExpressionAttributeNames={'#cid': 'callId', '#et': 'eventType'},
            ExpressionAttributeValues={':cid': call_id, ':et': 'connect'},
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
    """Clear all call logs."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        result = table.scan(ProjectionExpression='id')
        items = result.get('Items', [])
        deleted = 0
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={'id': item['id']})
                deleted += 1
        return _response(200, {'success': True, 'deletedCount': deleted})
    except Exception as e:
        return _response(200, {'success': False, 'error': str(e)})


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """HTTP response with CORS."""
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, default=str),
    }
