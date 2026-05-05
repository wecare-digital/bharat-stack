"""
Sinch RCS DLR (Delivery Report) Webhook Handler

Endpoint: POST /webhook/sinch-rcs
Receives delivery status callbacks from Sinch India Conversation API.

DLR Events:
- MESSAGE_DELIVERY: Message delivery status
- EVENT_DELIVERY: Event delivery status
- MESSAGE_INBOUND: Inbound message from user
- EVENT_INBOUND: Inbound event from user
- CONVERSATION_START / CONVERSATION_STOP
- CONTACT_CREATE / CONTACT_DELETE / CONTACT_MERGE / CONTACT_UPDATE
- OPT_IN / OPT_OUT
- CAPABILITY
- UNSUPPORTED
"""

import os
import json
import time
import logging
import boto3
from typing import Dict, Any

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_headers, extract_origin

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'stack-wecare-digital-WhatsAppOutboundTable')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Sinch RCS DLR webhook callbacks."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')

    # Health check
    if http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({'status': 'ok', 'service': 'sinch-rcs-webhook'}),
        }

    # Parse body
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            data = json.loads(body)
        else:
            data = body or {}
    except Exception as e:
        logger.error(f'Failed to parse RCS DLR body: {e}')
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({'success': False, 'error': 'parse_error'}),
        }

    # Log the callback
    event_type = _get_event_type(data)
    logger.info(json.dumps({
        'event': 'rcs_dlr_received',
        'type': event_type,
        'requestId': request_id,
        'data_keys': list(data.keys())[:10],
    }))

    # Process based on event type
    if event_type == 'MESSAGE_DELIVERY':
        _process_delivery(data, request_id)
    elif event_type == 'MESSAGE_INBOUND':
        _process_inbound(data, request_id)
    elif event_type in ('OPT_IN', 'OPT_OUT'):
        _process_opt(data, event_type, request_id)
    elif event_type == 'CAPABILITY':
        _process_capability(data, request_id)

    return {
        'statusCode': 200,
        'headers': cors_headers(origin),
        'body': json.dumps({'success': True, 'event': event_type}),
    }


def _get_event_type(data: Dict) -> str:
    """Extract event type from Sinch callback."""
    # Sinch sends different top-level keys for different events
    if 'message_delivery_report' in data:
        return 'MESSAGE_DELIVERY'
    elif 'message' in data and data.get('direction') == 'TO_APP':
        return 'MESSAGE_INBOUND'
    elif 'event_delivery_report' in data:
        return 'EVENT_DELIVERY'
    elif 'event' in data and data.get('direction') == 'TO_APP':
        return 'EVENT_INBOUND'
    elif 'conversation_start_notification' in data:
        return 'CONVERSATION_START'
    elif 'conversation_stop_notification' in data:
        return 'CONVERSATION_STOP'
    elif 'opt_in_notification' in data:
        return 'OPT_IN'
    elif 'opt_out_notification' in data:
        return 'OPT_OUT'
    elif 'capability_notification' in data:
        return 'CAPABILITY'
    elif 'contact_create_notification' in data:
        return 'CONTACT_CREATE'
    elif 'contact_delete_notification' in data:
        return 'CONTACT_DELETE'
    return data.get('event_type', 'UNKNOWN')


def _process_delivery(data: Dict, request_id: str):
    """Process message delivery report."""
    report = data.get('message_delivery_report', {})
    message_id = report.get('message_id', '')
    status = report.get('status', '')
    channel = report.get('channel_identity', {}).get('channel', 'RCS')

    logger.info(json.dumps({
        'event': 'rcs_delivery_report',
        'messageId': message_id,
        'status': status,
        'channel': channel,
        'requestId': request_id,
    }))


def _process_inbound(data: Dict, request_id: str):
    """Process inbound message from user."""
    message = data.get('message', {})
    contact_id = data.get('contact_id', '')
    conversation_id = data.get('conversation_id', '')

    logger.info(json.dumps({
        'event': 'rcs_inbound_message',
        'contactId': contact_id,
        'conversationId': conversation_id,
        'requestId': request_id,
    }))


def _process_opt(data: Dict, event_type: str, request_id: str):
    """Process opt-in/opt-out."""
    notification = data.get(f'{event_type.lower()}_notification', {})
    logger.info(json.dumps({
        'event': f'rcs_{event_type.lower()}',
        'notification': str(notification)[:200],
        'requestId': request_id,
    }))


def _process_capability(data: Dict, request_id: str):
    """Process capability check response."""
    notification = data.get('capability_notification', {})
    logger.info(json.dumps({
        'event': 'rcs_capability',
        'notification': str(notification)[:200],
        'requestId': request_id,
    }))
