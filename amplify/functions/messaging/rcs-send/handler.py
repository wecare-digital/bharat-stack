"""
RCS Send Lambda Function

Purpose: Send RCS messages via Sinch Conversation API
Supports: Text messages, Rich cards, Order notifications, IVR notifications

Endpoints:
  POST /rcs/send  — Send RCS message (text or card)

Config:
  - SINCH_RCS_ENABLED=true to activate
  - Secret: wecare/sinch/rcs (project_id, app_id, oauth_token, region)
"""

import os
import json
import uuid
import time
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.sinch_rcs import (
    is_rcs_enabled, send_rcs_text, send_rcs_card,
    send_rcs_ivr_notification, send_rcs_order_notification, send_rcs_wa_alert,
)

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'stack-wecare-digital-MessagesTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
MESSAGE_TTL_SECONDS = 90 * 24 * 60 * 60

origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle RCS send requests."""
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')

    if http_method == 'OPTIONS':
        return _response(200, {'message': 'OK'})

    if http_method != 'POST':
        return _response(405, {'error': 'Method not allowed'})

    try:
        body = json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError):
        return _response(400, {'error': 'Invalid JSON'})

    # Check if RCS is enabled
    if not is_rcs_enabled():
        return _response(200, {
            'success': False,
            'error': 'RCS not enabled',
            'message': 'Set SINCH_RCS_ENABLED=true and configure wecare/sinch/rcs secret to activate'
        })

    # Extract params
    contact_id = body.get('contactId', '')
    phone = body.get('phoneNumber', '')
    content = body.get('content', '')
    notification_type = body.get('notificationType', 'text')
    order_id = body.get('orderId', '')
    wd_order_id = body.get('wdOrderId', '')
    campaign_id = body.get('campaignId', '')
    campaign_name = body.get('campaignName', '')

    # Resolve phone from contact if needed
    if not phone and contact_id:
        try:
            table = dynamodb.Table(CONTACTS_TABLE)
            item = table.get_item(Key={'id': contact_id}).get('Item', {})
            phone = item.get('phone', '')
        except Exception:
            pass

    if not phone:
        return _response(400, {'error': 'phoneNumber or contactId with phone is required'})

    # Route to appropriate RCS message type
    if notification_type == 'order_confirmation':
        result = send_rcs_order_notification(phone, order_id, wd_order_id)
    elif notification_type == 'ivr_notification':
        result = send_rcs_ivr_notification(phone, request_id)
    elif notification_type == 'wa_alert':
        result = send_rcs_wa_alert(phone, request_id)
    elif notification_type == 'card' and body.get('card'):
        card = body['card']
        result = send_rcs_card(
            phone=phone,
            title=card.get('title', ''),
            description=card.get('description', ''),
            media_url=card.get('mediaUrl', ''),
            choices=card.get('choices', []),
            correlation_id=f'manual_{request_id}',
        )
    else:
        # Default: text message
        if not content:
            return _response(400, {'error': 'content is required for text messages'})
        result = send_rcs_text(phone, content, f'send_{request_id}')

    # Store message record
    if result.get('success'):
        message_id = str(uuid.uuid4())
        _store_message(message_id, contact_id, phone, content or notification_type,
                       result.get('message_id', ''), campaign_id, campaign_name)

    return _response(200, {
        'success': result.get('success', False),
        'messageId': result.get('message_id', ''),
        'error': result.get('error', ''),
    })


def _store_message(message_id, contact_id, phone, content, provider_id, campaign_id, campaign_name):
    """Store RCS message in MessagesTable."""
    try:
        now = Decimal(str(int(time.time())))
        table = dynamodb.Table(MESSAGES_TABLE)
        table.put_item(Item={
            'messageId': message_id,
            'contactId': contact_id or f'phone_{phone}',
            'channel': 'RCS',
            'direction': 'OUTBOUND',
            'content': content[:500] if content else '',
            'status': 'sent',
            'providerMessageId': provider_id,
            'campaignId': campaign_id,
            'campaignName': campaign_name,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'createdAt': now,
            'ttl': now + MESSAGE_TTL_SECONDS,
        })
    except Exception as e:
        logger.warning(f'Failed to store RCS message: {e}')


def _response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body),
    }
