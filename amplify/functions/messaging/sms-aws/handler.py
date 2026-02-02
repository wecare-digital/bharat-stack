"""
AWS SMS Lambda Function

Purpose: Send SMS messages via AWS Pinpoint/SNS in us-east-1
Supports: Transactional SMS, Marketing SMS, Two-way SMS

AWS Services:
- Amazon Pinpoint: SMS campaigns and transactional
- Amazon SNS: Simple SMS delivery
"""

import os
import json
import uuid
import time
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients - us-east-1
REGION = 'us-east-1'
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)
pinpoint = boto3.client('pinpoint', region_name=REGION)

# Environment variables
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-MessagesTable')
PINPOINT_APP_ID = os.environ.get('PINPOINT_APP_ID', '')
ORIGINATION_NUMBER = os.environ.get('ORIGINATION_NUMBER', '')
SENDER_ID = os.environ.get('SENDER_ID', 'WECARE')
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle AWS SMS operations."""
    request_id = context.aws_request_id if context else 'local'
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({
        'event': 'aws_sms_handler',
        'method': http_method,
        'requestId': request_id
    }))
    
    try:
        # GET /sms-aws/messages - List messages
        if http_method == 'GET' and not path_params.get('messageId'):
            return _list_messages(query_params, request_id)
        
        # GET /sms-aws/messages/{messageId} - Get single message
        if http_method == 'GET' and path_params.get('messageId'):
            return _get_message(path_params['messageId'], request_id)
        
        # POST /sms-aws/send - Send SMS
        if http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return _send_sms(body, request_id)
        
        return _response(405, {'error': 'Method not allowed'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'})
    except Exception as e:
        logger.error(json.dumps({
            'event': 'aws_sms_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(500, {'error': 'Internal server error'})


def _list_messages(params: Dict, request_id: str) -> Dict[str, Any]:
    """List AWS SMS messages with optional filters."""
    try:
        table = dynamodb.Table(MESSAGES_TABLE)
        
        from boto3.dynamodb.conditions import Attr
        
        scan_kwargs = {'Limit': int(params.get('limit', 100))}
        filter_expressions = [
            Attr('channel').eq('SMS'),
            Attr('provider').eq('aws')
        ]
        
        if params.get('contactId'):
            filter_expressions.append(Attr('contactId').eq(params['contactId']))
        if params.get('status'):
            filter_expressions.append(Attr('status').eq(params['status']))
        
        combined = filter_expressions[0]
        for expr in filter_expressions[1:]:
            combined = combined & expr
        scan_kwargs['FilterExpression'] = combined
        
        result = table.scan(**scan_kwargs)
        messages = result.get('Items', [])
        
        # Sort by timestamp descending
        messages.sort(key=lambda x: float(x.get('timestamp', 0)), reverse=True)
        
        return _response(200, {
            'messages': [_normalize_message(m) for m in messages],
            'count': len(messages)
        })
        
    except Exception as e:
        logger.error(f"List messages error: {str(e)}")
        return _response(500, {'error': str(e)})


def _get_message(message_id: str, request_id: str) -> Dict[str, Any]:
    """Get a single SMS message."""
    try:
        table = dynamodb.Table(MESSAGES_TABLE)
        result = table.get_item(Key={'messageId': message_id})
        message = result.get('Item')
        
        if message and message.get('provider') == 'aws':
            return _response(200, {'message': _normalize_message(message)})
        return _response(404, {'error': 'Message not found'})
        
    except Exception as e:
        logger.error(f"Get message error: {str(e)}")
        return _response(500, {'error': str(e)})


def _send_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """Send SMS via AWS Pinpoint or SNS."""
    contact_id = body.get('contactId')
    phone_number = body.get('phoneNumber')
    content = body.get('content', '')
    message_type = body.get('messageType', 'TRANSACTIONAL')  # TRANSACTIONAL or PROMOTIONAL
    sender_id = body.get('senderId', SENDER_ID)
    
    if not contact_id and not phone_number:
        return _response(400, {'error': 'contactId or phoneNumber is required'})
    
    if not content:
        return _response(400, {'error': 'content is required'})
    
    # Get phone number
    phone = phone_number
    contact = None
    
    if contact_id:
        contact = _get_contact(contact_id)
        if not contact:
            return _response(404, {'error': 'Contact not found'})
        phone = contact.get('phone', '') or phone_number
    
    if not phone:
        return _response(400, {'error': 'No phone number available'})
    
    # Clean and validate phone
    phone_clean = _clean_phone_number(phone)
    if not phone_clean:
        return _response(400, {'error': 'Invalid phone number format'})
    
    # Format to E.164
    phone_e164 = _format_e164(phone_clean)
    
    # Generate message ID
    message_id = str(uuid.uuid4())
    
    # Send via Pinpoint if configured, else SNS
    if PINPOINT_APP_ID:
        result = _send_pinpoint_sms(
            phone=phone_e164,
            content=content,
            message_type=message_type,
            sender_id=sender_id,
            request_id=request_id
        )
    else:
        result = _send_sns_sms(
            phone=phone_e164,
            content=content,
            message_type=message_type,
            sender_id=sender_id,
            request_id=request_id
        )
    
    # Store message
    _store_message(
        message_id=message_id,
        contact_id=contact_id or '',
        phone=phone_e164,
        content=content,
        status='SENT' if result.get('success') else 'FAILED',
        error=result.get('error'),
        provider_message_id=result.get('providerMessageId'),
        extra_data={
            'messageType': message_type,
            'senderId': sender_id
        }
    )
    
    if not result.get('success'):
        return _response(500, {
            'error': result.get('error', 'Failed to send SMS'),
            'messageId': message_id
        })
    
    logger.info(json.dumps({
        'event': 'aws_sms_sent',
        'messageId': message_id,
        'contactId': contact_id,
        'messageType': message_type,
        'requestId': request_id
    }))
    
    return _response(200, {
        'messageId': message_id,
        'status': 'sent',
        'providerMessageId': result.get('providerMessageId')
    })


def _send_pinpoint_sms(phone: str, content: str, message_type: str,
                       sender_id: str, request_id: str) -> Dict[str, Any]:
    """Send SMS via Amazon Pinpoint."""
    try:
        message_config = {
            'SMSMessage': {
                'Body': content,
                'MessageType': message_type,
            }
        }
        
        if sender_id:
            message_config['SMSMessage']['SenderId'] = sender_id
        
        if ORIGINATION_NUMBER:
            message_config['SMSMessage']['OriginationNumber'] = ORIGINATION_NUMBER
        
        response = pinpoint.send_messages(
            ApplicationId=PINPOINT_APP_ID,
            MessageRequest={
                'Addresses': {
                    phone: {'ChannelType': 'SMS'}
                },
                'MessageConfiguration': message_config
            }
        )
        
        result = response.get('MessageResponse', {}).get('Result', {}).get(phone, {})
        
        if result.get('StatusCode') == 200:
            return {
                'success': True,
                'providerMessageId': result.get('MessageId')
            }
        
        return {
            'success': False,
            'error': result.get('StatusMessage', 'Pinpoint delivery failed')
        }
        
    except pinpoint.exceptions.BadRequestException as e:
        logger.error(f"Pinpoint bad request: {str(e)}")
        return {'success': False, 'error': f'Bad request: {str(e)}'}
    except Exception as e:
        logger.error(f"Pinpoint error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _send_sns_sms(phone: str, content: str, message_type: str,
                  sender_id: str, request_id: str) -> Dict[str, Any]:
    """Send SMS via Amazon SNS."""
    try:
        message_attributes = {
            'AWS.SNS.SMS.SMSType': {
                'DataType': 'String',
                'StringValue': message_type.capitalize()
            }
        }
        
        if sender_id:
            message_attributes['AWS.SNS.SMS.SenderID'] = {
                'DataType': 'String',
                'StringValue': sender_id
            }
        
        response = sns.publish(
            PhoneNumber=phone,
            Message=content,
            MessageAttributes=message_attributes
        )
        
        return {
            'success': True,
            'providerMessageId': response.get('MessageId')
        }
        
    except sns.exceptions.InvalidParameterException as e:
        logger.error(f"SNS invalid param: {str(e)}")
        return {'success': False, 'error': f'Invalid parameter: {str(e)}'}
    except Exception as e:
        logger.error(f"SNS error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _clean_phone_number(phone: str) -> str:
    """Clean phone number to digits only."""
    if not phone:
        return ''
    return ''.join(c for c in phone if c.isdigit())


def _format_e164(phone: str) -> str:
    """Format phone number to E.164 format."""
    digits = _clean_phone_number(phone)
    
    # If already has country code (11+ digits)
    if len(digits) >= 11:
        return f'+{digits}'
    
    # Assume US/Canada if 10 digits
    if len(digits) == 10:
        return f'+1{digits}'
    
    return f'+{digits}'


def _get_contact(contact_id: str) -> Dict[str, Any]:
    """Get contact from DynamoDB."""
    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        response = table.get_item(Key={'contactId': contact_id})
        return response.get('Item', {})
    except Exception as e:
        logger.error(f"Get contact error: {str(e)}")
        return {}


def _store_message(message_id: str, contact_id: str, phone: str, content: str,
                   status: str, error: str = None, provider_message_id: str = None,
                   extra_data: Dict = None) -> None:
    """Store message record in DynamoDB."""
    try:
        now = int(time.time())
        table = dynamodb.Table(MESSAGES_TABLE)
        
        item = {
            'messageId': message_id,
            'contactId': contact_id,
            'phoneNumber': phone,
            'channel': 'SMS',
            'provider': 'aws',
            'direction': 'OUTBOUND',
            'content': content,
            'status': status,
            'timestamp': Decimal(str(now)),
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + MESSAGE_TTL_SECONDS)),
        }
        
        if error:
            item['errorDetails'] = error
        if provider_message_id:
            item['providerMessageId'] = provider_message_id
        
        if extra_data:
            for key, value in extra_data.items():
                if value:
                    item[key] = value
        
        table.put_item(Item=item)
        
    except Exception as e:
        logger.error(f"Store message error: {str(e)}")


def _normalize_message(item: Dict) -> Dict:
    """Normalize message record for API response."""
    return {
        'messageId': item.get('messageId', ''),
        'contactId': item.get('contactId', ''),
        'phoneNumber': item.get('phoneNumber', ''),
        'channel': 'SMS',
        'provider': 'aws',
        'direction': item.get('direction', 'OUTBOUND'),
        'content': item.get('content', ''),
        'status': item.get('status', ''),
        'messageType': item.get('messageType', ''),
        'providerMessageId': item.get('providerMessageId', ''),
        'timestamp': int(float(item.get('timestamp', 0))),
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
