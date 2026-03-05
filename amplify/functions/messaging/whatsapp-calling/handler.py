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

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)
secrets_client = boto3.client('secretsmanager', region_name=REGION)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', '')
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

# CORS headers provided by lambda_utils.response.cors_headers(origin)


def _get_meta_token(phone_number_id: str = None) -> str:
    """Get the correct Meta token based on phone number ID (dual WABA support)."""
    _load_meta_secrets()
    use_waba2 = phone_number_id in WABA2_IDS if phone_number_id else False
    cache_key = 'token2' if use_waba2 else 'token1'
    token = _token_cache.get(cache_key, _token_cache.get('token1', ''))
    logger.info(f"Using {cache_key} for phone_number_id={phone_number_id} (use_waba2={use_waba2})")
    return token


def _get_app_secret(phone_number_id: str = None) -> str:
    """Get the correct app secret for appsecret_proof."""
    _load_meta_secrets()
    use_waba2 = phone_number_id in WABA2_IDS if phone_number_id else False
    return _token_cache.get('app_secret2' if use_waba2 else 'app_secret1', '')


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
        logger.error(f"Meta API error {e.code}: {error_body}")
        return {'error': True, 'status': e.code, 'detail': error_body}
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
                body_str = event.get('body', '{}')
                if event.get('isBase64Encoded'):
                    import base64
                    body_str = base64.b64decode(body_str).decode('utf-8')
                return _handle_webhook_event(json.loads(body_str), request_id)

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
                logger.info(f"Processing {len(calls)} call event(s) for waba_id={waba_id}, "
                            f"phone_number_id={metadata.get('phone_number_id', 'N/A')}, "
                            f"display_phone={metadata.get('display_phone_number', 'N/A')}")
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
        logger.info(f"INBOUND CALL from {caller_name or from_number} — call_id: {call_id}, has_sdp: {bool(sdp_offer)}, sdp_len: {len(sdp_offer) if sdp_offer else 0}, phone_number_id: {phone_number_id}")

        # Auto-pickup: if enabled, send pre_accept to hold the call open
        # The actual accept with SDP answer is handled by the frontend (browser WebRTC).
        # Lambda sends pre_accept to tell Meta we intend to answer — this extends
        # the timeout window so the frontend has time to poll and generate SDP.
        if _is_auto_pickup_enabled() and phone_number_id:
            logger.info(f"AUTO-PICKUP pre_accept — holding call {call_id} for frontend pickup")
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


def _send_post_call_reaction(phone_number_id: str, from_number: str, call_id: str,
                              reason: str, duration: int, direction: str) -> None:
    """
    Send a post-call summary message to the caller/callee after a call ends.
    Uses AWS EUM Social Messaging to send a text message with call details.
    - Completed calls (duration > 0): ✅ with duration
    - Missed/rejected/no-answer: ❌ with reason
    
    Note: Requires an open 24-hour messaging window. If the window is closed
    (e.g. caller never messaged this business number), the send will fail silently.
    """
    try:
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
    body = json.loads(event.get('body', '{}'))
    call_id = body.get('callId', '')
    phone_number_id = body.get('phoneNumberId', '')
    sdp_answer = body.get('sdpAnswer', '')

    if not call_id or not phone_number_id:
        return _response(400, {'error': 'callId and phoneNumberId required'})

    logger.info(f"Accepting call {call_id} on {phone_number_id}, has_sdp_answer: {bool(sdp_answer)}")

    # Check if call was already pre_accepted by auto-pickup webhook handler
    already_pre_accepted = False
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        result = table.scan(
            FilterExpression='#cid = :cid AND #et = :et',
            ExpressionAttributeNames={'#cid': 'callId', '#et': 'eventType'},
            ExpressionAttributeValues={':cid': call_id, ':et': 'connect'},
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
            hint = ''
            if pre_accept_result.get('status') == 403:
                hint = ('Token lacks calling permission. Ensure the System User token '
                        'has whatsapp_business_messaging permission AND calling is '
                        'enabled on this phone number via POST /{phone_number_id}/settings '
                        'with the calling object. Also verify the token belongs to the '
                        'correct WABA for this phone number.')
            return _response(200, {
                'success': False, 'step': 'pre_accept',
                'error': pre_accept_result,
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
DEFAULT_IVR_URL = os.environ.get('AUTO_PICKUP_IVR_URL', 'https://app.wecare.digital/stream/media/ivr/ivr-greeting.mp3')
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
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-5e020cecd221429996f6ae721cc42206')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c')


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
    Uses direct URL by default: https://app.wecare.digital/stream/media/ivr/IVR+1.mp3
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
    Auto-pickup: pre_accept → accept the call, then send the greeting audio
    as a WhatsApp audio message to the caller.

    IMPORTANT: Meta's Calling API requires an SDP answer for the accept action
    to establish WebRTC media. Without a valid SDP answer, the call will NOT
    connect and will timeout with a "terminate" webhook.

    Current limitation: Server-side Lambda cannot generate a WebRTC SDP answer
    without a WebRTC stack (e.g., GStreamer, Opal, Opal, or a headless browser).
    As a workaround, we send pre_accept (to stop ringing) and then send an
    audio message to the caller via WhatsApp messaging API. The actual voice
    call will NOT connect — the caller hears ringing then disconnect.

    For true auto-pickup, you need either:
    1. A browser-based WebRTC client (frontend) to generate SDP answer
    2. A server-side WebRTC stack (e.g., Opal/GStreamer/Opal) to generate SDP
    3. SIP integration (if enabled on the WABA) with a SIP server like Opal/FreeSWITCH
    """
    logger.info(json.dumps({
        'event': 'auto_pickup_start',
        'call_id': call_id,
        'from': from_number,
        'phone_number_id': phone_number_id,
        'has_sdp_offer': bool(sdp_offer),
        'sdp_offer_length': len(sdp_offer) if sdp_offer else 0,
    }))

    # Step 1: Pre-accept — tells Meta we intend to answer (stops ringing on user's end)
    pre_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'pre_accept',
    }, phone_number_id=phone_number_id)
    logger.info(f"AUTO-PICKUP pre_accept: {json.dumps(pre_result)}")

    if pre_result.get('error'):
        logger.error(json.dumps({
            'event': 'auto_pickup_pre_accept_failed',
            'call_id': call_id,
            'error': pre_result,
            'phone_number_id': phone_number_id,
        }))
        _update_call_status(call_id, 'auto_pickup_failed', {
            'failStep': 'pre_accept',
            'error': json.dumps(pre_result)[:500],
        })
        return

    # Step 2: Accept — requires SDP answer for WebRTC media establishment
    # Without SDP answer, Meta will NOT connect the call audio.
    # We still send accept to complete the signaling, but the call won't have audio.
    accept_payload = {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'accept',
    }
    # NOTE: sdp_answer is NOT included because Lambda cannot generate one.
    # This means the call will likely terminate with "no_answer" or "timeout".

    accept_result = _meta_api_call(f"{phone_number_id}/calls", 'POST',
                                    accept_payload, phone_number_id=phone_number_id)
    logger.info(f"AUTO-PICKUP accept: {json.dumps(accept_result)}")

    if accept_result.get('error'):
        logger.error(json.dumps({
            'event': 'auto_pickup_accept_failed',
            'call_id': call_id,
            'error': accept_result,
            'phone_number_id': phone_number_id,
            'note': 'Accept without SDP answer — call audio will NOT connect',
        }))
        _update_call_status(call_id, 'auto_pickup_failed', {
            'failStep': 'accept',
            'error': json.dumps(accept_result)[:500],
        })
        return

    _update_call_status(call_id, 'auto_answered')

    # Step 3: Send greeting audio message to the caller via WhatsApp messaging API
    # This is a regular WhatsApp audio message, NOT in-call audio.
    audio_url = _get_auto_pickup_audio_url()
    if audio_url:
        _send_audio_to_caller(phone_number_id, from_number, audio_url, call_id)
    else:
        logger.warning("AUTO-PICKUP: No greeting audio configured, call answered silently")

    # Step 4: Terminate after a delay (let audio message send)
    # Use synchronous sleep — daemon threads get killed when Lambda freezes
    # the execution context after handler returns.
    time.sleep(15)
    logger.info(f"AUTO-PICKUP: Hanging up call {call_id}")
    hangup_result = _meta_api_call(f"{phone_number_id}/calls", 'POST', {
        'messaging_product': 'whatsapp',
        'call_id': call_id,
        'action': 'terminate',
    }, phone_number_id=phone_number_id)
    logger.info(f"AUTO-PICKUP hangup result: {json.dumps(hangup_result)}")
    _update_call_status(call_id, 'auto_completed')


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
    """Get auto-pickup mode from SystemConfig: 'manual' | 'ivr' | 'ai'."""
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        result = table.get_item(Key={'id': 'whatsapp_calling_auto_pickup_mode'})
        item = result.get('Item')
        if item and item.get('configValue') in ('manual', 'ivr', 'ai'):
            return str(item['configValue'])
    except Exception as e:
        logger.warning(f"Failed to read auto-pickup mode: {e}")
    return 'ivr'  # default


def _update_config(event: Dict, request_id: str) -> Dict[str, Any]:
    """Update auto-pickup configuration (toggle + IVR URL + mode)."""
    body = json.loads(event.get('body', '{}'))
    enabled = body.get('autoPickup')
    ivr_url = body.get('ivrUrl')
    mode = body.get('autoPickupMode')  # 'manual' | 'ivr' | 'ai'

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

    if mode is not None and mode in ('manual', 'ivr', 'ai'):
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

    body = json.loads(event.get('body', '{}'))
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
            return _response(200, {'error': 'No speech detected', 'audioUrl': None})

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
        logger.error(f"[AI-RESPOND] Error: {e}", exc_info=True)
        return _response(200, {'error': str(e), 'audioUrl': None})


def _transcribe_audio(audio_base64: str, mime_type: str, session_id: str, request_id: str) -> str:
    """Decode base64 audio, upload to S3, run Transcribe batch job, return text."""
    import base64 as b64

    ext = 'webm' if 'webm' in mime_type else 'ogg' if 'ogg' in mime_type else 'mp3'
    media_format = 'webm' if ext == 'webm' else 'ogg' if ext == 'ogg' else 'mp3'

    audio_bytes = b64.b64decode(audio_base64)
    s3_key = f"base/whatsapp-media/calling-ai/wecare-digital-{session_id[:8]}_{int(time.time())}.{ext}"

    s3.put_object(Bucket=MEDIA_BUCKET, Key=s3_key, Body=audio_bytes, ContentType=mime_type)
    logger.info(f"[TRANSCRIBE] Uploaded {len(audio_bytes)} bytes to s3://{MEDIA_BUCKET}/{s3_key}")

    job_name = f"wa-call-{session_id[:8]}-{int(time.time())}"
    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': f"s3://{MEDIA_BUCKET}/{s3_key}"},
        MediaFormat=media_format,
        LanguageCode=TRANSCRIBE_LANGUAGE,
        OutputBucketName=MEDIA_BUCKET,
        OutputKey=f"base/whatsapp-media/calling-ai/wecare-digital-transcript-{job_name}.json",
    )

    # Poll for completion (max 30s)
    for _ in range(30):
        time.sleep(1)
        status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        job_status = status['TranscriptionJob']['TranscriptionJobStatus']
        if job_status == 'COMPLETED':
            transcript_key = f"base/whatsapp-media/calling-ai/wecare-digital-transcript-{job_name}.json"
            obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=transcript_key)
            transcript_data = json.loads(obj['Body'].read().decode('utf-8'))
            text = transcript_data.get('results', {}).get('transcripts', [{}])[0].get('transcript', '')
            logger.info(f"[TRANSCRIBE] Done: {text[:200]}")
            try:
                s3.delete_object(Bucket=MEDIA_BUCKET, Key=s3_key)
                s3.delete_object(Bucket=MEDIA_BUCKET, Key=transcript_key)
            except Exception:
                pass
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
        s3_key = f"base/whatsapp-media/calling-ai/wecare-digital-tts-{session_id[:8]}_{int(time.time())}.mp3"
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
            s3_key = f"base/whatsapp-media/calling-ai/wecare-digital-tts-{session_id[:8]}_{int(time.time())}.mp3"
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


def _response(status_code: int, body: Dict, origin: str = '') -> Dict[str, Any]:
    """HTTP response with CORS."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body, default=str),
    }
