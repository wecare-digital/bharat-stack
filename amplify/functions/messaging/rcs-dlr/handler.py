"""
Sinch RCS DLR (Delivery Report) Webhook Handler

Endpoint: POST /webhook/sinch-rcs
Receives delivery status callbacks from Sinch India Conversation API.

DLR Events:
- MESSAGE_DELIVERY: Message delivery status (QUEUED, DELIVERED, FAILED, READ)
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
import boto3
import boto3.dynamodb.conditions
from typing import Dict, Any
from decimal import Decimal

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_headers, extract_origin

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
RCS_TABLE = os.environ.get('RCS_TABLE', 'stack-wecare-digital-RcsMessagesTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')

# Sinch RCS status mapping
RCS_STATUS_MAP = {
    'QUEUED': 'sent',
    'DELIVERED': 'delivered',
    'FAILED': 'failed',
    'READ': 'read',
    'DELETED': 'deleted',
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Sinch RCS DLR webhook callbacks."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')

    if http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({'status': 'ok', 'service': 'sinch-rcs-webhook'}),
        }

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

    event_type = _get_event_type(data)
    logger.info(json.dumps({
        'event': 'rcs_dlr_received',
        'type': event_type,
        'requestId': request_id,
    }))

    if event_type == 'MESSAGE_DELIVERY':
        _process_delivery(data, request_id)
    elif event_type == 'MESSAGE_INBOUND':
        _process_inbound(data, request_id)
    elif event_type in ('OPT_IN', 'OPT_OUT'):
        _process_opt(data, event_type, request_id)

    return {
        'statusCode': 200,
        'headers': cors_headers(origin),
        'body': json.dumps({'success': True, 'event': event_type}),
    }


def _get_event_type(data: Dict) -> str:
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
    """Process delivery report and UPDATE message status in DynamoDB."""
    report = data.get('message_delivery_report', {})
    message_id = report.get('message_id', '')
    sinch_status = report.get('status', '')
    channel = report.get('channel_identity', {}).get('channel', 'RCS')
    identity = report.get('channel_identity', {}).get('identity', '')
    reason = report.get('reason', {})
    metadata = data.get('message_metadata', '')

    status = RCS_STATUS_MAP.get(sinch_status, sinch_status.lower() if sinch_status else 'unknown')
    now = int(time.time())

    logger.info(json.dumps({
        'event': 'rcs_delivery_update',
        'messageId': message_id,
        'status': status,
        'sinchStatus': sinch_status,
        'channel': channel,
        'identity': identity[-4:] if identity else '',
        'reason': reason.get('description', ''),
        'requestId': request_id,
    }))

    if not message_id:
        return

    # Update RCS messages table (primary — always do this)
    try:
        table = dynamodb.Table(RCS_TABLE)
        table.update_item(
            Key={'messageId': message_id},
            UpdateExpression='SET #s = :status, dlrTime = :dlr, dlrRaw = :raw, updatedAt = :now',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': status,
                ':dlr': data.get('event_time', ''),
                ':raw': json.dumps({'sinchStatus': sinch_status, 'reason': reason})[:500],
                ':now': now,
            },
        )
    except Exception as e:
        logger.warning(f'RCS table update failed (may not exist yet): {e}')


def _process_inbound(data: Dict, request_id: str):
    """Process inbound RCS message and store in DB."""
    message = data.get('message', {})
    contact_id = data.get('contact_id', '')
    conversation_id = data.get('conversation_id', '')
    channel_identity = data.get('channel_identity', {})
    identity = channel_identity.get('identity', '')
    accepted_time = data.get('accepted_time', '')

    # Extract message content
    text_msg = message.get('text_message', {})
    content = text_msg.get('text', '')
    if not content:
        content = json.dumps(message)[:500]

    now = int(time.time())
    msg_id = data.get('message_id', f'rcs-in-{now}')

    # Look up contactId by phone number
    if not contact_id and identity:
        contact_id = _lookup_contact_by_phone(identity)

    logger.info(json.dumps({
        'event': 'rcs_inbound_stored',
        'messageId': msg_id,
        'identity': identity[-4:] if identity else '',
        'contactId': contact_id,
        'contentLen': len(content),
        'requestId': request_id,
    }))

    # Store inbound message
    try:
        table = dynamodb.Table(RCS_TABLE)
        item = {
            'messageId': msg_id,
            'direction': 'INBOUND',
            'channel': 'RCS',
            'phoneNumber': identity.replace('+', ''),
            'content': content,
            'status': 'received',
            'conversationId': conversation_id or 'none',
            'createdAt': now,
            'updatedAt': now,
        }
        # Only include GSI keys if non-empty (DynamoDB rejects empty string keys)
        if contact_id:
            item['contactId'] = contact_id
        table.put_item(Item=item)
        logger.info(f'Inbound RCS stored: {msg_id} from {identity[-4:] if identity else "?"}')
    except Exception as e:
        logger.warning(f'Failed to store inbound RCS: {e}')


def _process_opt(data: Dict, event_type: str, request_id: str):
    """Process opt-in/opt-out and log."""
    notification = data.get(f'{event_type.lower()}_notification', {})
    identity = notification.get('identity', '')
    logger.info(json.dumps({
        'event': f'rcs_{event_type.lower()}',
        'identity': identity[-4:] if identity else '',
        'requestId': request_id,
    }))


def _lookup_contact_by_phone(phone: str) -> str:
    """Look up contactId from Contacts table by phone number."""
    if not phone:
        return ''
    clean = phone.replace('+', '').replace(' ', '').replace('-', '')
    variants = [clean]
    if clean.startswith('91') and len(clean) == 12:
        variants.append(clean[2:])
        variants.append(f'+{clean}')
    elif len(clean) == 10:
        variants.append(f'91{clean}')
        variants.append(f'+91{clean}')

    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        for variant in variants:
            resp = table.query(
                IndexName='phone-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('phone').eq(variant),
                Limit=1,
            )
            items = resp.get('Items', [])
            if items:
                return items[0].get('contactId', '')
    except Exception as e:
        logger.debug(f"Contact lookup by phone failed: {e}")
    return ''
