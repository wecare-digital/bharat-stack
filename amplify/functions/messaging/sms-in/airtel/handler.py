"""
Airtel IQ SMS Lambda Function

Purpose: Send SMS messages via Airtel IQ Messaging API
Features:
- Basic Authentication
- DLT compliance (entityId, dltTemplateId)
- Message types: PROMOTIONAL, TRANSACTIONAL, SERVICE_IMPLICIT, SERVICE_EXPLICIT

API Endpoints:
- Single/Multiple: https://iqmessaging.airtel.in/api/v4/send-sms
- Bulk: https://iqmessaging.airtel.in/conduit/api/v1/send-sms-bulk

Secrets: wecare/airtel/sms
"""

import os
import json
import uuid
import time
import logging
import boto3
import base64
import urllib.request
import urllib.error
from typing import Dict, Any, List
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)

# Environment variables
AIRTEL_SMS_TABLE = os.environ.get('AIRTEL_SMS_TABLE', 'base-wecare-digital-AirtelSMSTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
AIRTEL_SMS_SECRET_NAME = os.environ.get('AIRTEL_SMS_SECRET_NAME', 'wecare/airtel/sms')
AIRTEL_SMS_HOST = os.environ.get('AIRTEL_SMS_HOST', 'iqmessaging.airtel.in')
MESSAGE_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days

# Cached secrets
_secrets_cache = None


def _get_secrets() -> Dict[str, str]:
    """Fetch Airtel SMS credentials from Secrets Manager (cached)."""
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache
    
    try:
        response = secrets_client.get_secret_value(SecretId=AIRTEL_SMS_SECRET_NAME)
        _secrets_cache = json.loads(response['SecretString'])
        logger.info(f"Loaded secrets from {AIRTEL_SMS_SECRET_NAME}")
        return _secrets_cache
    except Exception as e:
        logger.error(f"Failed to load secrets: {str(e)}")
        return {}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Airtel SMS operations."""
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({
        'event': 'airtel_sms_handler',
        'method': http_method,
        'requestId': request_id
    }))
    
    try:
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        # GET - List messages
        if http_method == 'GET' and not path_params.get('messageId'):
            return _list_messages(query_params, request_id)
        
        # GET - Get single message
        if http_method == 'GET' and path_params.get('messageId'):
            return _get_message(path_params['messageId'], request_id)
        
        # POST - Send SMS
        if http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            action = body.get('action', 'send')
            
            if action == 'send':
                return _send_sms(body, request_id)
            elif action == 'send_bulk':
                return _send_bulk_sms(body, request_id)
            else:
                return _response(400, {'error': f'Unknown action: {action}'})
        
        return _response(405, {'error': 'Method not allowed'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'})
    except Exception as e:
        logger.error(json.dumps({
            'event': 'airtel_sms_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(500, {'error': 'Internal server error'})


def _send_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """Send single/multiple SMS via Airtel IQ API v4."""
    phone_numbers = body.get('phoneNumbers', [])
    phone_number = body.get('phoneNumber')
    contact_id = body.get('contactId')
    content = body.get('content', '')
    message_type = body.get('messageType', 'SERVICE_EXPLICIT')
    sender_id = body.get('senderId')
    entity_id = body.get('entityId')
    dlt_template_id = body.get('dltTemplateId')
    
    # Build destination list
    destinations = []
    if phone_number:
        destinations.append(phone_number)
    if phone_numbers:
        destinations.extend(phone_numbers)
    
    # Get from contact if needed
    if contact_id and not destinations:
        contact = _get_contact(contact_id)
        if not contact:
            return _response(404, {'error': 'Contact not found'})
        phone = contact.get('phone', '')
        if phone:
            destinations.append(phone)
    
    if not destinations:
        return _response(400, {'error': 'phoneNumber, phoneNumbers, or contactId is required'})
    
    if not content:
        return _response(400, {'error': 'content is required'})
    
    # Clean phone numbers
    clean_destinations = [_clean_phone_number(p) for p in destinations]
    clean_destinations = [p for p in clean_destinations if p]
    
    if not clean_destinations:
        return _response(400, {'error': 'No valid phone numbers'})
    
    message_id = str(uuid.uuid4())
    
    result = _call_airtel_v4_api(
        destinations=clean_destinations,
        content=content,
        message_type=message_type,
        sender_id=sender_id,
        entity_id=entity_id,
        dlt_template_id=dlt_template_id,
        request_id=request_id
    )
    
    # Store message
    _store_message(
        message_id=message_id,
        contact_id=contact_id or '',
        phone=','.join(clean_destinations),
        content=content,
        status='SENT' if result.get('success') else 'FAILED',
        error=result.get('error'),
        provider_message_id=result.get('providerMessageId'),
        extra_data={
            'messageType': message_type,
            'senderId': sender_id,
            'entityId': entity_id,
            'dltTemplateId': dlt_template_id,
            'recipientCount': len(clean_destinations)
        }
    )
    
    if not result.get('success'):
        return _response(500, {
            'error': result.get('error', 'Failed to send SMS'),
            'messageId': message_id
        })
    
    logger.info(json.dumps({
        'event': 'airtel_sms_sent',
        'messageId': message_id,
        'recipientCount': len(clean_destinations),
        'messageType': message_type,
        'requestId': request_id
    }))
    
    return _response(200, {
        'messageId': message_id,
        'status': 'sent',
        'recipientCount': len(clean_destinations),
        'providerResponse': result.get('providerResponse')
    })


def _send_bulk_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """Send bulk SMS via Airtel Conduit API (individual messages per recipient)."""
    messages = body.get('messages', [])
    
    if not messages:
        return _response(400, {'error': 'messages array is required'})
    
    secrets = _get_secrets()
    auth_token = secrets.get('auth_token')
    default_sender_id = secrets.get('sender_id', 'WDBEEP')
    default_entity_id = secrets.get('entity_id')
    
    if not auth_token:
        return _response(500, {'error': 'Airtel SMS credentials not configured'})
    
    # Build bulk payload
    bulk_payload = []
    for msg in messages:
        phone = _clean_phone_number(msg.get('phoneNumber', ''))
        if not phone:
            continue
        
        bulk_payload.append({
            "msisdn": phone,
            "content": msg.get('content', ''),
            "header": msg.get('senderId') or default_sender_id,
            "messageType": msg.get('messageType', 'SERVICE_EXPLICIT'),
            "templateId": msg.get('dltTemplateId', ''),
            "peId": msg.get('entityId') or default_entity_id,
            "category": "SMS_NCM"
        })
    
    if not bulk_payload:
        return _response(400, {'error': 'No valid messages in payload'})
    
    result = _call_airtel_bulk_api(bulk_payload, auth_token, request_id)
    
    if not result.get('success'):
        return _response(500, {
            'error': result.get('error', 'Failed to send bulk SMS')
        })
    
    return _response(200, {
        'status': 'sent',
        'messageCount': len(bulk_payload),
        'providerResponse': result.get('providerResponse')
    })


def _call_airtel_v4_api(destinations: List[str], content: str, message_type: str,
                        sender_id: str, entity_id: str, dlt_template_id: str,
                        request_id: str) -> Dict[str, Any]:
    """Call Airtel IQ SMS API v4 with Basic Authentication."""
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        auth_token = secrets.get('auth_token')
        default_sender_id = secrets.get('sender_id', 'WDBEEP')
        default_entity_id = secrets.get('entity_id')
        default_template_id = secrets.get('dlt_template_id')
        
        if not customer_id or not auth_token:
            return {'success': False, 'error': 'Airtel SMS credentials not configured'}
        
        # Use defaults from secrets if not provided
        sender_id = sender_id or default_sender_id
        entity_id = entity_id or default_entity_id
        dlt_template_id = dlt_template_id or default_template_id
        
        # Build payload for v4 API
        payload = {
            "customerId": customer_id,
            "destinationAddress": destinations,
            "message": content,
            "sourceAddress": sender_id,
            "messageType": message_type
        }
        
        # Add DLT fields (required for India)
        if dlt_template_id:
            payload["dltTemplateId"] = dlt_template_id
        if entity_id:
            payload["entityId"] = entity_id
        
        body_str = json.dumps(payload)
        url = f"https://{AIRTEL_SMS_HOST}/api/v4/send-sms"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_token}',
            'customerId': customer_id
        }
        
        req = urllib.request.Request(url, data=body_str.encode('utf-8'), headers=headers, method='POST')
        
        logger.info(json.dumps({
            'event': 'airtel_sms_v4_request',
            'url': url,
            'destinationCount': len(destinations),
            'messageType': message_type,
            'requestId': request_id
        }))
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            # Check for success
            if result.get('status') == 'success' or result.get('messageId') or result.get('requestId'):
                return {
                    'success': True,
                    'providerMessageId': result.get('messageId') or result.get('requestId'),
                    'providerResponse': result
                }
            
            return {
                'success': False,
                'error': result.get('message') or result.get('errorMessage', 'API error'),
                'providerResponse': result
            }
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Airtel SMS HTTP error: {e.code} - {error_body}")
        return {'success': False, 'error': f'HTTP {e.code}: {error_body[:200]}'}
    except Exception as e:
        logger.error(f"Airtel SMS error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _call_airtel_bulk_api(messages: List[Dict], auth_token: str, 
                          request_id: str) -> Dict[str, Any]:
    """Call Airtel Conduit Bulk SMS API."""
    try:
        body_str = json.dumps(messages)
        url = f"https://{AIRTEL_SMS_HOST}/conduit/api/v1/send-sms-bulk"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_token}'
        }
        
        req = urllib.request.Request(url, data=body_str.encode('utf-8'), headers=headers, method='POST')
        
        logger.info(json.dumps({
            'event': 'airtel_bulk_sms_request',
            'url': url,
            'messageCount': len(messages),
            'requestId': request_id
        }))
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            # Bulk API typically returns array or success status
            if isinstance(result, list) or result.get('status') == 'success':
                return {
                    'success': True,
                    'providerResponse': result
                }
            
            return {
                'success': False,
                'error': result.get('message') or result.get('errorMessage', 'API error'),
                'providerResponse': result
            }
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Airtel bulk SMS HTTP error: {e.code} - {error_body}")
        return {'success': False, 'error': f'HTTP {e.code}: {error_body[:200]}'}
    except Exception as e:
        logger.error(f"Airtel bulk SMS error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _list_messages(params: Dict, request_id: str) -> Dict[str, Any]:
    """List Airtel SMS messages with optional filters."""
    try:
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        from boto3.dynamodb.conditions import Attr
        
        scan_kwargs = {'Limit': int(params.get('limit', 100))}
        filter_expressions = []
        
        if params.get('contactId'):
            filter_expressions.append(Attr('contactId').eq(params['contactId']))
        if params.get('status'):
            filter_expressions.append(Attr('status').eq(params['status']))
        if params.get('direction'):
            filter_expressions.append(Attr('direction').eq(params['direction']))
        if params.get('phoneNumber'):
            filter_expressions.append(Attr('phoneNumber').contains(params['phoneNumber']))
        
        if filter_expressions:
            combined = filter_expressions[0]
            for expr in filter_expressions[1:]:
                combined = combined & expr
            scan_kwargs['FilterExpression'] = combined
        
        result = table.scan(**scan_kwargs)
        messages = result.get('Items', [])
        messages.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        
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
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        result = table.get_item(Key={'messageId': message_id})
        message = result.get('Item')
        
        if message:
            return _response(200, {'message': _normalize_message(message)})
        return _response(404, {'error': 'Message not found'})
        
    except Exception as e:
        logger.error(f"Get message error: {str(e)}")
        return _response(500, {'error': str(e)})


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
    """Store message record in AirtelSMS DynamoDB table."""
    try:
        now = int(time.time())
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        
        item = {
            'messageId': message_id,
            'contactId': contact_id,
            'phoneNumber': phone,
            'content': content,
            'direction': 'OUTBOUND',
            'status': status,
            'createdAt': Decimal(str(now)),
            'expiresAt': Decimal(str(now + MESSAGE_TTL_SECONDS)),
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
        'provider': 'airtel',
        'direction': item.get('direction', 'OUTBOUND'),
        'content': item.get('content', ''),
        'status': item.get('status', ''),
        'messageType': item.get('messageType', ''),
        'senderId': item.get('senderId', ''),
        'entityId': item.get('entityId', ''),
        'dltTemplateId': item.get('dltTemplateId', ''),
        'providerMessageId': item.get('providerMessageId', ''),
        'recipientCount': item.get('recipientCount', 1),
        'timestamp': int(float(item.get('timestamp', 0))),
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _clean_phone_number(phone: str) -> str:
    """Clean phone number to 10 digits (India format)."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    # Remove country code if present
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) == 10 else ''


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
