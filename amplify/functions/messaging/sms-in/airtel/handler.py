"""
Airtel IQ SMS Lambda Function

Purpose: Send SMS messages via Airtel IQ Messaging API
Features:
- Basic Authentication
- DLT compliance (entityId, dltTemplateId)
- Message types: PROMOTIONAL, TRANSACTIONAL, SERVICE_IMPLICIT, SERVICE_EXPLICIT
- DLT Template management

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
import urllib.request
import urllib.error
from typing import Dict, Any, List
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)

AIRTEL_SMS_TABLE = os.environ.get('AIRTEL_SMS_TABLE', 'base-wecare-digital-AirtelSMSTable')
DLT_TEMPLATES_TABLE = os.environ.get('DLT_TEMPLATES_TABLE', 'base-wecare-digital-DLTTemplates')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
AIRTEL_SMS_SECRET_NAME = os.environ.get('AIRTEL_SMS_SECRET_NAME', 'wecare/airtel/sms')
AIRTEL_SMS_HOST = 'iqmessaging.airtel.in'
MESSAGE_TTL_SECONDS = 90 * 24 * 60 * 60

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
    path = event.get('rawPath', event.get('path', ''))
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({'event': 'airtel_sms_handler', 'method': http_method, 'path': path, 'requestId': request_id}))
    
    try:
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        # Template management endpoints
        if '/templates' in path:
            if http_method == 'GET':
                return _list_templates(query_params, request_id)
            elif http_method == 'POST':
                body = json.loads(event.get('body', '{}'))
                return _create_template(body, request_id)
            elif http_method == 'DELETE':
                template_id = path_params.get('templateId') or query_params.get('templateId')
                return _delete_template(template_id, request_id)
        
        # GET - List messages
        if http_method == 'GET' and not path_params.get('messageId'):
            return _list_messages(query_params, request_id)
        
        # GET - Get single message
        if http_method == 'GET' and path_params.get('messageId'):
            return _get_message(path_params['messageId'], request_id)
        
        # POST - Send SMS
        if http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            if body.get('bulk') or body.get('phoneNumbers'):
                return _send_bulk_sms(body, request_id)
            return _send_sms(body, request_id)
        
        return _response(405, {'error': 'Method not allowed'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'})
    except Exception as e:
        logger.error(json.dumps({'event': 'airtel_sms_error', 'error': str(e), 'requestId': request_id}))
        return _response(500, {'error': 'Internal server error'})


def _send_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """Send single SMS via Airtel IQ API v4."""
    phone_number = body.get('phoneNumber')
    content = body.get('content', '')
    message_type = body.get('messageType', 'SERVICE_EXPLICIT')
    dlt_template_id = body.get('dltTemplateId')
    
    if not phone_number:
        return _response(400, {'error': 'phoneNumber is required'})
    if not content:
        return _response(400, {'error': 'content is required'})
    
    clean_phone = _clean_phone_number(phone_number)
    if not clean_phone:
        return _response(400, {'error': 'Invalid phone number'})
    
    secrets = _get_secrets()
    customer_id = secrets.get('customer_id')
    auth_token = secrets.get('auth_token')
    sender_id = secrets.get('sender_id', 'WDBEEP')
    entity_id = secrets.get('entity_id', '1201161991108627443')
    default_template_id = secrets.get('dlt_template_id', '1007974344269130859')
    
    if not customer_id or not auth_token:
        return _response(500, {'error': 'Airtel SMS credentials not configured'})
    
    dlt_template_id = dlt_template_id or default_template_id
    
    payload = {
        "customerId": customer_id,
        "destinationAddress": [clean_phone],
        "message": content,
        "sourceAddress": sender_id,
        "messageType": message_type,
        "dltTemplateId": dlt_template_id,
        "entityId": entity_id
    }
    
    # Add OTP flag for SERVICE_IMPLICIT if needed
    if message_type == 'SERVICE_IMPLICIT' and body.get('otp'):
        payload["otp"] = True
    
    url = f"https://{AIRTEL_SMS_HOST}/api/v4/send-sms"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {auth_token}',
        'customerId': customer_id
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            message_id = str(uuid.uuid4())
            provider_msg_id = result.get('messageRequestId') or result.get('messageId')
            
            _store_message(message_id, clean_phone, content, 'SENT', message_type, sender_id, entity_id, dlt_template_id, provider_msg_id)
            
            return _response(200, {
                'success': True,
                'messageId': message_id,
                'providerMessageId': provider_msg_id,
                'status': 'sent'
            })
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Airtel SMS error: {e.code} - {error_body}")
        return _response(e.code, {'error': f'Airtel API error: {error_body[:200]}'})
    except Exception as e:
        logger.error(f"SMS send error: {str(e)}")
        return _response(500, {'error': str(e)})


def _send_bulk_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """Send bulk SMS via Airtel Conduit API."""
    phone_numbers = body.get('phoneNumbers', [])
    content = body.get('content', '')
    message_type = body.get('messageType', 'SERVICE_EXPLICIT')
    dlt_template_id = body.get('dltTemplateId')
    
    if not phone_numbers:
        return _response(400, {'error': 'phoneNumbers array is required'})
    if not content:
        return _response(400, {'error': 'content is required'})
    
    secrets = _get_secrets()
    auth_token = secrets.get('auth_token')
    sender_id = secrets.get('sender_id', 'WDBEEP')
    entity_id = secrets.get('entity_id', '1201161991108627443')
    default_template_id = secrets.get('dlt_template_id', '1007974344269130859')
    
    if not auth_token:
        return _response(500, {'error': 'Airtel SMS credentials not configured'})
    
    dlt_template_id = dlt_template_id or default_template_id
    
    # Build bulk payload per Airtel Conduit API spec
    bulk_payload = []
    for phone in phone_numbers:
        clean_phone = _clean_phone_number(phone)
        if not clean_phone:
            continue
        bulk_payload.append({
            "msisdn": clean_phone,
            "content": content,
            "header": sender_id,
            "messageType": message_type,
            "templateId": dlt_template_id,
            "peId": entity_id,
            "category": "SMS_NCM"
        })
    
    if not bulk_payload:
        return _response(400, {'error': 'No valid phone numbers'})
    
    url = f"https://{AIRTEL_SMS_HOST}/conduit/api/v1/send-sms-bulk"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {auth_token}'
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(bulk_payload).encode('utf-8'), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            # Store bulk message record
            message_id = str(uuid.uuid4())
            _store_message(message_id, ','.join([p['msisdn'] for p in bulk_payload]), content, 'SENT', message_type, sender_id, entity_id, dlt_template_id, None, len(bulk_payload))
            
            return _response(200, {
                'success': True,
                'messageId': message_id,
                'recipientCount': len(bulk_payload),
                'status': 'sent'
            })
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Airtel bulk SMS error: {e.code} - {error_body}")
        return _response(e.code, {'error': f'Airtel API error: {error_body[:200]}'})
    except Exception as e:
        logger.error(f"Bulk SMS error: {str(e)}")
        return _response(500, {'error': str(e)})


# DLT Template Management
def _list_templates(params: Dict, request_id: str) -> Dict[str, Any]:
    """List DLT templates."""
    try:
        table = dynamodb.Table(DLT_TEMPLATES_TABLE)
        result = table.scan(Limit=int(params.get('limit', 100)))
        templates = result.get('Items', [])
        templates.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        
        return _response(200, {
            'templates': [_normalize_template(t) for t in templates],
            'count': len(templates)
        })
    except Exception as e:
        logger.error(f"List templates error: {str(e)}")
        return _response(500, {'error': str(e)})


def _create_template(body: Dict, request_id: str) -> Dict[str, Any]:
    """Create/save a DLT template locally."""
    template_id = body.get('templateId') or body.get('dltTemplateId')
    name = body.get('name', '')
    content = body.get('content', '')
    message_type = body.get('messageType', 'SERVICE_EXPLICIT')
    
    if not template_id:
        return _response(400, {'error': 'templateId is required'})
    if not content:
        return _response(400, {'error': 'content is required'})
    
    try:
        now = int(time.time())
        table = dynamodb.Table(DLT_TEMPLATES_TABLE)
        
        # Extract variables from content
        import re
        vars_match = re.findall(r'\{#(\w+)#\}', content)
        variables = body.get('variables', list(set(vars_match)))
        
        item = {
            'templateId': template_id,
            'name': name or f'Template {template_id[:8]}',
            'content': content,
            'messageType': message_type,
            'senderId': body.get('senderId', 'WDBEEP'),
            'entityId': body.get('entityId', '1201161991108627443'),
            'variables': variables,
            'status': 'active',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now))
        }
        
        table.put_item(Item=item)
        
        return _response(200, {
            'success': True,
            'template': _normalize_template(item)
        })
    except Exception as e:
        logger.error(f"Create template error: {str(e)}")
        return _response(500, {'error': str(e)})


def _delete_template(template_id: str, request_id: str) -> Dict[str, Any]:
    """Delete a DLT template."""
    if not template_id:
        return _response(400, {'error': 'templateId is required'})
    
    try:
        table = dynamodb.Table(DLT_TEMPLATES_TABLE)
        table.delete_item(Key={'templateId': template_id})
        return _response(200, {'success': True, 'deleted': template_id})
    except Exception as e:
        logger.error(f"Delete template error: {str(e)}")
        return _response(500, {'error': str(e)})


def _normalize_template(item: Dict) -> Dict:
    """Normalize template for response."""
    # Extract variables from content if not stored
    content = item.get('content', '')
    stored_vars = item.get('variables', [])
    if not stored_vars and content:
        import re
        vars_match = re.findall(r'\{#(\w+)#\}', content)
        stored_vars = list(set(vars_match))
    
    return {
        'templateId': item.get('templateId', ''),
        'name': item.get('name', ''),
        'content': content,
        'messageType': item.get('messageType', ''),
        'senderId': item.get('senderId', ''),
        'entityId': item.get('entityId', ''),
        'variables': stored_vars,
        'status': item.get('status', 'active'),
        'createdAt': int(float(item.get('createdAt', 0)))
    }


# Message storage and retrieval
def _list_messages(params: Dict, request_id: str) -> Dict[str, Any]:
    """List SMS messages."""
    try:
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        result = table.scan(Limit=int(params.get('limit', 100)))
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


def _store_message(message_id: str, phone: str, content: str, status: str, 
                   message_type: str, sender_id: str, entity_id: str, 
                   dlt_template_id: str, provider_msg_id: str = None, 
                   recipient_count: int = 1) -> None:
    """Store message record."""
    try:
        now = int(time.time())
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        
        item = {
            'messageId': message_id,
            'phoneNumber': phone,
            'content': content,
            'status': status,
            'messageType': message_type,
            'senderId': sender_id,
            'entityId': entity_id,
            'dltTemplateId': dlt_template_id,
            'recipientCount': recipient_count,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + MESSAGE_TTL_SECONDS))
        }
        
        if provider_msg_id:
            item['providerMessageId'] = provider_msg_id
        
        table.put_item(Item=item)
    except Exception as e:
        logger.error(f"Store message error: {str(e)}")


def _normalize_message(item: Dict) -> Dict:
    """Normalize message for response."""
    return {
        'messageId': item.get('messageId', ''),
        'phoneNumber': item.get('phoneNumber', ''),
        'content': item.get('content', ''),
        'status': item.get('status', ''),
        'messageType': item.get('messageType', ''),
        'senderId': item.get('senderId', ''),
        'dltTemplateId': item.get('dltTemplateId', ''),
        'recipientCount': int(item.get('recipientCount', 1)),
        'providerMessageId': item.get('providerMessageId', ''),
        'createdAt': int(float(item.get('createdAt', 0)))
    }


def _clean_phone_number(phone: str) -> str:
    """Clean phone number to 10 digits (India format)."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
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
            'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }