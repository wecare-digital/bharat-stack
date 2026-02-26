"""
AWS SMS Lambda Function

Purpose: Send SMS messages via Amazon Pinpoint SMS (us-east-1)
Supports: Transactional SMS, Promotional SMS
Table: base-wecare-digital-SmsAwsTable (dedicated)

Endpoints:
  GET  /sms-aws/messages          - List SMS messages
  GET  /sms-aws/messages/{id}     - Get single message
  POST /sms-aws/send              - Send SMS
  DELETE /sms-aws/messages/{id}   - Delete message
  DELETE /sms-aws/clear-logs      - Clear all logs
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

logger = get_logger(__name__)

REGION = 'us-east-1'
dynamodb = boto3.resource('dynamodb', region_name=REGION)
pinpoint_sms = boto3.client('pinpoint-sms-voice-v2', region_name=REGION)

CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
SMS_TABLE = os.environ.get('SMS_AWS_TABLE', 'base-wecare-digital-SmsAwsTable')
ORIGINATION_IDENTITY = os.environ.get('ORIGINATION_IDENTITY', '')
SENDER_ID = os.environ.get('SENDER_ID', 'WECARE')
MESSAGE_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle AWS SMS operations."""
    from lambda_utils.middleware import require_auth
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('rawPath', event.get('path', ''))
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}

    logger.info(json.dumps({
        'event': 'sms_aws_handler', 'method': http_method,
        'path': path, 'requestId': request_id
    }))

    try:
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'}, origin)

        # Auth check
        auth_result = require_auth(event)
        if auth_result is not None:
            return auth_result

        # DELETE /sms-aws/clear-logs
        if http_method == 'DELETE' and 'clear-logs' in path:
            return _clear_logs(request_id)

        # DELETE /sms-aws/messages/{id}
        if http_method == 'DELETE' and path_params.get('messageId'):
            return _delete_message(path_params['messageId'], request_id)

        # GET /sms-aws/messages/{id}
        if http_method == 'GET' and path_params.get('messageId'):
            return _get_message(path_params['messageId'], request_id)

        # GET /sms-aws/messages
        if http_method == 'GET':
            return _list_messages(query_params, request_id)

        # POST /sms-aws/send
        if http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return _send_sms(body, request_id)

        return _response(405, {'error': 'Method not allowed'}, origin)

    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'}, origin)
    except Exception as e:
        logger.error(f"SMS AWS error: {str(e)}", exc_info=True)
        return _response(500, {'error': 'Internal server error'}, origin)


def _list_messages(params: Dict, request_id: str) -> Dict[str, Any]:
    """List SMS messages from dedicated table."""
    try:
        table = dynamodb.Table(SMS_TABLE)
        scan_kwargs = {'Limit': int(params.get('limit', 200))}

        from boto3.dynamodb.conditions import Attr

        filters = []
        if params.get('contactId'):
            filters.append(Attr('contactId').eq(params['contactId']))
        if params.get('status'):
            filters.append(Attr('status').eq(params['status']))
        if params.get('direction'):
            filters.append(Attr('direction').eq(params['direction']))

        if filters:
            combined = filters[0]
            for f in filters[1:]:
                combined = combined & f
            scan_kwargs['FilterExpression'] = combined

        result = table.scan(**scan_kwargs)
        messages = result.get('Items', [])
        messages.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)

        return _response(200, {
            'messages': [_normalize(m) for m in messages],
            'count': len(messages)
        })
    except Exception as e:
        logger.error(f"List messages error: {str(e)}")
        return _response(500, {'error': str(e)})


def _get_message(message_id: str, request_id: str) -> Dict[str, Any]:
    """Get a single SMS message."""
    try:
        table = dynamodb.Table(SMS_TABLE)
        result = table.get_item(Key={'messageId': message_id})
        item = result.get('Item')
        if item:
            return _response(200, {'message': _normalize(item)})
        return _response(404, {'error': 'Message not found'})
    except Exception as e:
        logger.error(f"Get message error: {str(e)}")
        return _response(500, {'error': str(e)})


def _delete_message(message_id: str, request_id: str) -> Dict[str, Any]:
    """Delete a single SMS message."""
    try:
        table = dynamodb.Table(SMS_TABLE)
        table.delete_item(Key={'messageId': message_id})
        return _response(200, {'success': True, 'deleted': message_id})
    except Exception as e:
        logger.error(f"Delete message error: {str(e)}")
        return _response(500, {'error': str(e)})


def _clear_logs(request_id: str) -> Dict[str, Any]:
    """Clear all SMS logs."""
    try:
        table = dynamodb.Table(SMS_TABLE)
        result = table.scan(ProjectionExpression='messageId')
        items = result.get('Items', [])
        deleted = 0
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={'messageId': item['messageId']})
                deleted += 1
        return _response(200, {'success': True, 'deletedCount': deleted})
    except Exception as e:
        logger.error(f"Clear logs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _send_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """Send SMS via Amazon Pinpoint SMS v2."""
    contact_id = body.get('contactId', '')
    phone_number = body.get('phoneNumber') or body.get('phone')
    content = body.get('content', '')
    message_type = body.get('messageType', 'TRANSACTIONAL')
    campaign_id = body.get('campaignId', '')
    campaign_name = body.get('campaignName', '')

    if not phone_number and contact_id:
        contact = _get_contact(contact_id)
        phone_number = contact.get('phone') if contact else None

    if not phone_number:
        return _response(400, {'error': 'phoneNumber is required'})
    if not content:
        return _response(400, {'error': 'content is required'})

    phone_e164 = _format_e164(phone_number)
    if not phone_e164:
        return _response(400, {'error': 'Invalid phone number format'})

    message_id = str(uuid.uuid4())

    # Send via Pinpoint SMS v2
    result = _send_pinpoint_sms(phone_e164, content, message_type, request_id)

    now = int(time.time())
    _store_message({
        'messageId': message_id,
        'contactId': contact_id,
        'phoneNumber': phone_e164,
        'content': content,
        'direction': 'OUTBOUND',
        'status': 'SENT' if result.get('success') else 'FAILED',
        'messageType': message_type,
        'senderId': SENDER_ID,
        'providerMessageId': result.get('providerMessageId', ''),
        'campaignId': campaign_id,
        'campaignName': campaign_name,
        'errorDetails': result.get('error', ''),
        'createdAt': Decimal(str(now)),
        'ttl': Decimal(str(now + MESSAGE_TTL_SECONDS)),
    })

    if not result.get('success'):
        return _response(500, {
            'error': result.get('error', 'Failed to send SMS'),
            'messageId': message_id
        })

    return _response(200, {
        'success': True,
        'messageId': message_id,
        'status': 'sent',
        'providerMessageId': result.get('providerMessageId')
    })


def _send_pinpoint_sms(phone: str, content: str, message_type: str,
                       request_id: str) -> Dict[str, Any]:
    """Send SMS via Pinpoint SMS Voice v2 API.
    
    Note: ORIGINATION_IDENTITY is only set if an SMS-capable pool/number exists.
    If not set, Pinpoint uses the default configuration for the account.
    The toll-free +18444891209 is PENDING registration, so SMS uses account default.
    """
    try:
        params: Dict[str, Any] = {
            'DestinationPhoneNumber': phone,
            'MessageBody': content,
            'MessageType': message_type,
        }

        # Only set origination identity if it's an SMS-capable resource
        if ORIGINATION_IDENTITY:
            params['OriginationIdentity'] = ORIGINATION_IDENTITY

        response = pinpoint_sms.send_text_message(**params)

        return {
            'success': True,
            'providerMessageId': response.get('MessageId', '')
        }

    except pinpoint_sms.exceptions.ConflictException as e:
        logger.error(f"Pinpoint conflict: {str(e)}")
        return {'success': False, 'error': f'Conflict: {str(e)}'}
    except pinpoint_sms.exceptions.ValidationException as e:
        logger.error(f"Pinpoint validation: {str(e)}")
        return {'success': False, 'error': f'Validation: {str(e)}'}
    except pinpoint_sms.exceptions.ThrottlingException as e:
        logger.error(f"Pinpoint throttled: {str(e)}")
        return {'success': False, 'error': 'Rate limited, try again'}
    except Exception as e:
        logger.error(f"Pinpoint SMS error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _format_e164(phone: str) -> str:
    """Format phone number to E.164."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if len(digits) == 10:
        return f'+91{digits}'  # India default
    if len(digits) >= 11 and not phone.startswith('+'):
        return f'+{digits}'
    if phone.startswith('+'):
        return phone
    return f'+{digits}' if digits else ''


def _get_contact(contact_id: str) -> Dict[str, Any]:
    """Get contact from DynamoDB."""
    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        response = table.get_item(Key={'contactId': contact_id})
        return response.get('Item', {})
    except Exception as e:
        logger.error(f"Get contact error: {str(e)}")
        return {}


def _store_message(item: Dict) -> None:
    """Store message in dedicated SMS table."""
    try:
        table = dynamodb.Table(SMS_TABLE)
        # Remove empty string values (DynamoDB doesn't allow them)
        clean = {k: v for k, v in item.items() if v is not None and v != ''}
        table.put_item(Item=clean)
    except Exception as e:
        logger.error(f"Store message error: {str(e)}")


def _normalize(item: Dict) -> Dict:
    """Normalize message for API response."""
    return {
        'messageId': item.get('messageId', ''),
        'contactId': item.get('contactId', ''),
        'phoneNumber': item.get('phoneNumber', ''),
        'content': item.get('content', ''),
        'direction': item.get('direction', 'OUTBOUND'),
        'status': item.get('status', ''),
        'messageType': item.get('messageType', ''),
        'senderId': item.get('senderId', ''),
        'providerMessageId': item.get('providerMessageId', ''),
        'campaignId': item.get('campaignId', ''),
        'campaignName': item.get('campaignName', ''),
        'channel': 'SMS',
        'provider': 'aws',
        'timestamp': int(float(item.get('createdAt', 0))),
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _response(status_code: int, body: Dict, origin: str = '') -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body, default=str)
    }
