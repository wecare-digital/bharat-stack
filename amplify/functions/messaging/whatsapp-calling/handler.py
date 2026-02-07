"""
WhatsApp Calling Webhook Handler

Purpose: Handle WhatsApp Business Calling API webhooks
- GET  /whatsapp-calling  → Webhook verification (hub.challenge)
- POST /whatsapp-calling  → Call events (connect, terminate, permission responses)

Meta Webhook Fields: calls
Verify Token: wecare_calling_verify_2026
"""

import os
import json
import time
import logging
import uuid
import boto3
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'wecare_calling_verify_2026')
CALL_LOG_TABLE = os.environ.get('CALL_LOG_TABLE', 'base-wecare-digital-WhatsAppCallingTable')
TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle WhatsApp Calling webhook events."""
    request_id = context.aws_request_id if context else 'local'
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('rawPath', event.get('path', ''))
    query_params = event.get('queryStringParameters') or {}

    logger.info(json.dumps({
        'event': 'whatsapp_calling_webhook',
        'method': http_method,
        'path': path,
        'requestId': request_id,
        'queryParams': query_params,
    }))

    try:
        # GET — Webhook verification
        if http_method == 'GET':
            return _verify_webhook(query_params, request_id)

        # POST — Incoming webhook event
        if http_method == 'POST':
            body_str = event.get('body', '{}')
            # Handle base64 encoded body
            if event.get('isBase64Encoded'):
                import base64
                body_str = base64.b64decode(body_str).decode('utf-8')
            body = json.loads(body_str)
            return _handle_webhook_event(body, request_id)

        # DELETE — Clear call logs
        if http_method == 'DELETE':
            return _clear_logs(request_id)

        # GET logs endpoint
        if http_method == 'GET' and 'logs' in path:
            return _list_logs(query_params, request_id)

        return _response(200, {'message': 'OK'})

    except Exception as e:
        logger.error(f"Webhook handler error: {str(e)}", exc_info=True)
        # Always return 200 to Meta — otherwise they'll retry and eventually
        # disable the webhook
        return _response(200, {'error': str(e)})


def _verify_webhook(params: Dict, request_id: str) -> Dict[str, Any]:
    """Handle Meta webhook verification (GET with hub.challenge)."""
    mode = params.get('hub.mode', '')
    token = params.get('hub.verify_token', '')
    challenge = params.get('hub.challenge', '')

    logger.info(json.dumps({
        'event': 'webhook_verify',
        'mode': mode,
        'token_match': token == VERIFY_TOKEN,
        'has_challenge': bool(challenge),
        'requestId': request_id,
    }))

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        logger.info(f"Webhook verified successfully. Challenge: {challenge}")
        # Must return the challenge as plain text, not JSON
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/plain',
                'Access-Control-Allow-Origin': '*',
            },
            'body': challenge,
        }

    logger.warning(f"Webhook verification failed. Mode: {mode}, Token match: {token == VERIFY_TOKEN}")
    return _response(403, {'error': 'Verification failed'})


def _handle_webhook_event(body: Dict, request_id: str) -> Dict[str, Any]:
    """Process incoming WhatsApp webhook events."""
    logger.info(json.dumps({
        'event': 'webhook_received',
        'requestId': request_id,
        'body_keys': list(body.keys()),
        'full_body': json.dumps(body)[:2000],
    }))

    # Meta webhook structure:
    # { "object": "whatsapp_business_account", "entry": [...] }
    obj = body.get('object', '')
    entries = body.get('entry', [])

    if obj != 'whatsapp_business_account':
        logger.info(f"Ignoring non-WABA webhook: {obj}")
        return _response(200, {'status': 'ignored', 'object': obj})

    for entry in entries:
        entry_id = entry.get('id', '')  # WABA ID
        changes = entry.get('changes', [])

        for change in changes:
            field = change.get('field', '')
            value = change.get('value', {})

            logger.info(json.dumps({
                'event': 'webhook_change',
                'waba_id': entry_id,
                'field': field,
                'value_keys': list(value.keys()) if isinstance(value, dict) else str(type(value)),
            }))

            if field == 'calls':
                _handle_call_event(entry_id, value, request_id)
            elif field == 'messages':
                # Message events — log but don't process (EUM handles these)
                logger.info(f"Message event received (EUM handles): {json.dumps(value)[:500]}")
            elif field == 'account_update':
                logger.info(f"Account update: {json.dumps(value)[:500]}")
            else:
                logger.info(f"Unhandled field: {field}")

    return _response(200, {'status': 'processed', 'entries': len(entries)})


def _handle_call_event(waba_id: str, value: Dict, request_id: str) -> None:
    """Handle a call-related webhook event."""
    event_type = value.get('event', '')
    call_id = value.get('call_id', '')
    from_number = value.get('from', '')
    to_number = value.get('to', '')
    phone_number_id = value.get('metadata', {}).get('phone_number_id', '')
    timestamp = value.get('timestamp', str(int(time.time())))

    logger.info(json.dumps({
        'event': 'call_event',
        'call_event_type': event_type,
        'call_id': call_id,
        'from': from_number,
        'to': to_number,
        'phone_number_id': phone_number_id,
        'waba_id': waba_id,
        'requestId': request_id,
        'full_value': json.dumps(value)[:2000],
    }))

    now = int(time.time())

    if event_type == 'connect':
        # Inbound call — user is calling us
        sdp_offer = value.get('sdp_offer', '')
        logger.info(json.dumps({
            'event': 'inbound_call_connect',
            'call_id': call_id,
            'from': from_number,
            'has_sdp': bool(sdp_offer),
            'sdp_length': len(sdp_offer),
        }))

        # Store call record
        _store_call_log({
            'callId': call_id,
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number,
            'toNumber': to_number,
            'direction': 'INBOUND',
            'eventType': 'connect',
            'status': 'ringing',
            'hasSdpOffer': bool(sdp_offer),
            'sdpOffer': sdp_offer[:500] if sdp_offer else '',
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })

        # TODO: In production, you'd respond with pre_accept + accept here
        # For now, just log the event so we can confirm webhooks work
        logger.info(f"CALL RECEIVED from {from_number} — call_id: {call_id}")

    elif event_type == 'terminate':
        # Call ended
        reason = value.get('reason', 'unknown')
        duration = value.get('duration', 0)

        logger.info(json.dumps({
            'event': 'call_terminated',
            'call_id': call_id,
            'reason': reason,
            'duration': duration,
        }))

        _store_call_log({
            'callId': call_id,
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number,
            'toNumber': to_number,
            'direction': 'INBOUND',
            'eventType': 'terminate',
            'status': 'ended',
            'terminateReason': reason,
            'duration': duration,
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })

    elif event_type == 'call_permission_response':
        # User responded to call permission request
        permission = value.get('permission', '')
        logger.info(json.dumps({
            'event': 'call_permission_response',
            'call_id': call_id,
            'from': from_number,
            'permission': permission,
        }))

        _store_call_log({
            'callId': call_id or str(uuid.uuid4()),
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number,
            'direction': 'INBOUND',
            'eventType': 'permission_response',
            'status': f'permission_{permission}',
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })

    else:
        # Unknown call event — log everything
        logger.info(json.dumps({
            'event': 'unknown_call_event',
            'event_type': event_type,
            'full_value': json.dumps(value),
        }))

        _store_call_log({
            'callId': call_id or str(uuid.uuid4()),
            'wabaId': waba_id,
            'phoneNumberId': phone_number_id,
            'fromNumber': from_number,
            'toNumber': to_number,
            'eventType': event_type or 'unknown',
            'status': 'logged',
            'rawEvent': json.dumps(value)[:1000],
            'timestamp': timestamp,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + TTL_SECONDS)),
        })


def _store_call_log(item: Dict) -> None:
    """Store call event in DynamoDB."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        # Use callId + eventType as composite to avoid overwriting
        item['id'] = f"{item.get('callId', 'unknown')}_{item.get('eventType', 'unknown')}_{int(time.time())}"
        clean = {k: v for k, v in item.items() if v is not None and v != ''}
        table.put_item(Item=clean)
        logger.info(f"Stored call log: {item.get('id')}")
    except Exception as e:
        logger.error(f"Store call log error: {str(e)}")


def _list_logs(params: Dict, request_id: str) -> Dict[str, Any]:
    """List call event logs."""
    try:
        table = dynamodb.Table(CALL_LOG_TABLE)
        result = table.scan(Limit=int(params.get('limit', 100)))
        items = result.get('Items', [])
        items.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        return _response(200, {'logs': items, 'count': len(items)})
    except Exception as e:
        logger.error(f"List logs error: {str(e)}")
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
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
        },
        'body': json.dumps(body, default=str),
    }
