"""
Airtel IQ SMS Lambda Function

Purpose: Send SMS messages via Airtel IQ Messaging API
Features:
- Basic Authentication (base64 encoded username:password)
- DLT compliance (entityId, dltTemplateId) per TRAI TCCCPR 2019
- Message types: PROMOTIONAL, TRANSACTIONAL, SERVICE_IMPLICIT, SERVICE_EXPLICIT
- DLT Template management
- metaData support (flows end-to-end to IQ reporting and callbacks)
- OTP flag for SERVICE_IMPLICIT (otp: true → OTP traffic type)

API Endpoints (Airtel IQ):
- v4 Single/Multiple SMS: POST https://iqmessaging.airtel.in/api/v4/send-sms
- v5 Content Moderation:  POST https://iqmessaging.airtel.in/api/v5/send-sms-cm
- v6 Enhanced Response:   POST https://iqmessaging.airtel.in/api/v6/send-sms
- Bulk (Conduit):         POST https://iqmessaging.airtel.in/conduit/api/v1/send-sms-bulk

Auth: Basic (base64 of username:password)
  Kong Username: WECAREDIG_v6J1SyLLI2auy7Lw9JrW
  Kong Password: sN$~|(I@112
  Base64 Token:  V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy

Headers (v4/v5/v6): Authorization, Content-Type: application/json, customerId
Headers (Bulk/Conduit): Authorization, Content-Type: application/json (NO customerId)

DLT Requirements:
- PE ID (entityId): 1201161991108627443
- Sender ID (sourceAddress/header): WDBEEP
- Content Template ID (dltTemplateId): registered on DLT portal
- MSISDN: 10 or 12 digits

Secrets: wecare/airtel/sms
Expected secret keys:
- customer_id: WECAREDIG_v6J1SyLLI2auy7Lw9JrW
- auth_token: V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy
- sender_id: WDBEEP (DLT registered header)
- entity_id: 1201161991108627443 (PE ID from DLT)
- dlt_template_id: 1007974344269130859 (default)

Notes (from Airtel spec):
- v4 destinationAddress is an array — supports single AND multiple recipients in one call
- Bulk (Conduit) is a different format: array of objects with msisdn, content, header, etc.
- Promotional messages: No DLR sent back (except NACK from DLT)
- If content is wrong per DLT, CP still gets success
- If DND scrubbing fails at DLT, CP still gets submit success
- Optional parameters are mandatory else packet rejected
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

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

logger = get_logger(__name__)

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)

AIRTEL_SMS_TABLE = os.environ.get('AIRTEL_SMS_TABLE', 'stack-wecare-digital-AirtelSMSTable')
DLT_TEMPLATES_TABLE = os.environ.get('DLT_TEMPLATES_TABLE', 'stack-wecare-digital-DLTTemplates')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
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


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Airtel SMS operations."""
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    global origin
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('rawPath', event.get('path', ''))
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({'event': 'airtel_sms_handler', 'method': http_method, 'path': path, 'requestId': request_id}))
    
    try:
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'}, origin)
        
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
            # bulk=true → Conduit bulk API (different payload format per recipient)
            if body.get('bulk'):
                return _send_bulk_sms(body, request_id)
            # phoneNumbers array OR single phoneNumber → v4/v5/v6 (destinationAddress supports multiple)
            return _send_sms(body, request_id)
        
        # DELETE - Delete message or clear logs
        if http_method == 'DELETE':
            if '/clear-logs' in path:
                return _clear_logs(request_id)
            message_id = path_params.get('messageId') or query_params.get('messageId')
            if message_id:
                return _delete_message(message_id, request_id)
            return _response(400, {'error': 'messageId is required'})
        
        return _response(405, {'error': 'Method not allowed'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'})
    except Exception as e:
        logger.error(json.dumps({'event': 'airtel_sms_error', 'error': str(e), 'requestId': request_id}))
        return _response(500, {'error': 'Internal server error'})


def _send_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Send SMS via Airtel IQ API (single or multiple recipients).

    Airtel v4/v5/v6 natively support multiple destinationAddress in one call.
    - v4 (default): POST /api/v4/send-sms
    - v5: POST /api/v5/send-sms-cm — content moderation (auto DLT)
    - v6: POST /api/v6/send-sms — enhanced response with echo-back

    Body params:
    - phoneNumber (string): single destination (10-digit mobile)
    - phoneNumbers (array): multiple destinations — same v4/v5/v6 endpoint
    - content (required): message text
    - messageType: PROMOTIONAL | TRANSACTIONAL | SERVICE_IMPLICIT | SERVICE_EXPLICIT
    - dltTemplateId: DLT content template ID
    - otp: true/false (for SERVICE_IMPLICIT, sets traffic type to OTP)
    - metaData: optional key-value map (flows to IQ reporting and callbacks)
    - apiVersion: "v4" | "v5" | "v6" (default: v4)
    """
    # Accept both single phoneNumber and phoneNumbers array
    phone_numbers = body.get('phoneNumbers', [])
    if body.get('phoneNumber'):
        phone_numbers = [body['phoneNumber']] + phone_numbers
    
    content = body.get('content', '')
    message_type = body.get('messageType', 'SERVICE_EXPLICIT')
    dlt_template_id = body.get('dltTemplateId')
    api_version = body.get('apiVersion', 'v4')
    meta_data = body.get('metaData')
    
    if not phone_numbers:
        return _response(400, {'error': 'phoneNumber or phoneNumbers is required'})
    if not content:
        return _response(400, {'error': 'content is required'})
    
    # Clean and validate all phone numbers
    clean_phones = []
    for p in phone_numbers:
        cleaned = _clean_phone_number(p)
        if cleaned:
            clean_phones.append(cleaned)
    
    if not clean_phones:
        return _response(400, {'error': 'No valid phone numbers'})
    
    secrets = _get_secrets()
    customer_id = secrets.get('customer_id')
    auth_token = secrets.get('auth_token')
    sender_id = secrets.get('sender_id', 'WDBEEP')
    entity_id = secrets.get('entity_id', '1201161991108627443')
    default_template_id = secrets.get('dlt_template_id', '1007974344269130859')
    
    if not customer_id or not auth_token:
        return _response(500, {'error': 'Airtel SMS credentials not configured'})
    
    dlt_template_id = dlt_template_id or default_template_id
    
    # Build payload based on API version
    # destinationAddress is always an array (works for single and multiple)
    if api_version == 'v5':
        # v5 Content Moderation — no DLT fields needed
        payload = {
            "customerId": customer_id,
            "destinationAddress": clean_phones,
            "message": content,
            "sourceAddress": sender_id,
            "messageType": message_type
        }
        if meta_data and isinstance(meta_data, dict):
            payload["metaData"] = meta_data
        url = f"https://{AIRTEL_SMS_HOST}/api/v5/send-sms-cm"
    else:
        # v4 and v6 — full DLT payload
        payload = {
            "customerId": customer_id,
            "destinationAddress": clean_phones,
            "message": content,
            "sourceAddress": sender_id,
            "messageType": message_type,
            "dltTemplateId": dlt_template_id,
            "entityId": entity_id
        }
        
        # OTP flag for SERVICE_IMPLICIT
        if message_type == 'SERVICE_IMPLICIT' and body.get('otp'):
            payload["otp"] = True
        
        # metaData (optional, flows end-to-end per Airtel spec)
        if meta_data and isinstance(meta_data, dict):
            payload["metaData"] = meta_data
        
        if api_version == 'v6':
            url = f"https://{AIRTEL_SMS_HOST}/api/v6/send-sms"
        else:
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
            
            _store_message(message_id, ','.join(clean_phones), content, 'SENT', message_type, sender_id, entity_id, dlt_template_id, provider_msg_id, len(clean_phones), api_version)
            
            resp = {
                'success': True,
                'messageId': message_id,
                'providerMessageId': provider_msg_id,
                'recipientCount': len(clean_phones),
                'status': 'sent',
                'apiVersion': api_version
            }
            
            # v6 echoes back additional fields
            if api_version == 'v6':
                resp['incorrectNum'] = result.get('incorrectNum', [])
            
            return _response(200, resp)
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Airtel SMS error: {e.code} - {error_body}")
        
        if e.code == 403:
            logger.error(json.dumps({
                'event': 'airtel_403_error',
                'service': 'sms',
                'url': url,
                'customer_id': customer_id,
                'auth_token_prefix': auth_token[:20] if auth_token else 'NONE',
                'note': 'Check: 1) Auth credentials valid? 2) Account activated? 3) IP whitelisted on Airtel side?',
                'airtel_ips_to_whitelist': ['125.19.17.212', '125.17.6.54', '122.187.47.153']
            }))
        
        return _response(e.code, {'error': f'Airtel API error: {error_body[:200]}'})
    except Exception as e:
        logger.error(f"SMS send error: {str(e)}")
        return _response(500, {'error': str(e)})


def _send_bulk_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Send bulk SMS via Airtel Conduit API.
    
    Uses a different endpoint and payload format than v4/v5/v6.
    Each recipient is a separate object with its own content, header, templateId.
    Triggered only when body has bulk=true.
    
    Endpoint: POST https://iqmessaging.airtel.in/conduit/api/v1/send-sms-bulk
    Auth: Basic only (no customerId header per Airtel curl)
    """
    phone_numbers = body.get('phoneNumbers', [])
    content = body.get('content', '')
    message_type = body.get('messageType', 'SERVICE_EXPLICIT')
    dlt_template_id = body.get('dltTemplateId')
    
    if not phone_numbers:
        return _response(400, {'error': 'phoneNumbers array is required for bulk'})
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
    # Each recipient is a separate object (can have different content/template)
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
    # Conduit bulk API: Authorization only, no customerId header
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
            _store_message(message_id, ','.join([p['msisdn'] for p in bulk_payload]), content, 'SENT', message_type, sender_id, entity_id, dlt_template_id, None, len(bulk_payload), 'bulk')
            
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
    """List SMS messages with pagination."""
    try:
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        limit = int(params.get('limit', 100))
        scan_kwargs = {'Limit': limit}
        
        # Support cursor-based pagination
        if params.get('nextToken'):
            try:
                import base64
                decoded = json.loads(base64.b64decode(params['nextToken']).decode('utf-8'))
                scan_kwargs['ExclusiveStartKey'] = decoded
            except Exception as e:
                logger.warning(f'Invalid pagination token: {e}')
        
        # Filter by status if provided
        if params.get('status'):
            scan_kwargs['FilterExpression'] = 'status = :s'
            scan_kwargs['ExpressionAttributeValues'] = {':s': params['status']}
        
        # Filter by direction if provided
        if params.get('direction'):
            if 'FilterExpression' in scan_kwargs:
                scan_kwargs['FilterExpression'] += ' AND direction = :d'
                scan_kwargs['ExpressionAttributeValues'][':d'] = params['direction']
            else:
                scan_kwargs['FilterExpression'] = 'direction = :d'
                scan_kwargs['ExpressionAttributeValues'] = {':d': params['direction']}
        
        result = table.scan(**scan_kwargs)
        messages = result.get('Items', [])
        messages.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        
        resp = {
            'messages': [_normalize_message(m) for m in messages],
            'count': len(messages)
        }
        
        # Include pagination token if more results
        if result.get('LastEvaluatedKey'):
            import base64
            resp['nextToken'] = base64.b64encode(json.dumps(result['LastEvaluatedKey'], default=str).encode('utf-8')).decode('utf-8')
        
        return _response(200, resp)
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


def _delete_message(message_id: str, request_id: str) -> Dict[str, Any]:
    """Delete a single SMS message."""
    if not message_id:
        return _response(400, {'error': 'messageId is required'})
    try:
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        table.delete_item(Key={'messageId': message_id})
        return _response(200, {'success': True, 'deleted': message_id})
    except Exception as e:
        logger.error(f"Delete message error: {str(e)}")
        return _response(500, {'error': str(e)})


def _clear_logs(request_id: str) -> Dict[str, Any]:
    """Delete all SMS message logs (paginated scan + batch delete)."""
    try:
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        deleted = 0
        last_key = None
        
        while True:
            scan_kwargs = {'ProjectionExpression': 'messageId'}
            if last_key:
                scan_kwargs['ExclusiveStartKey'] = last_key
            
            result = table.scan(**scan_kwargs)
            items = result.get('Items', [])
            
            if not items:
                break
            
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'messageId': item['messageId']})
                    deleted += 1
            
            last_key = result.get('LastEvaluatedKey')
            if not last_key:
                break
        
        return _response(200, {'success': True, 'deleted': deleted})
    except Exception as e:
        logger.error(f"Clear logs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _store_message(message_id: str, phone: str, content: str, status: str, 
                   message_type: str, sender_id: str, entity_id: str, 
                   dlt_template_id: str, provider_msg_id: str = None, 
                   recipient_count: int = 1, api_version: str = 'v4') -> None:
    """Store message record."""
    try:
        now = int(time.time())
        table = dynamodb.Table(AIRTEL_SMS_TABLE)
        
        item = {
            'messageId': message_id,
            'phoneNumber': phone,
            'content': content,
            'direction': 'OUTBOUND',
            'status': status,
            'messageType': message_type,
            'senderId': sender_id,
            'entityId': entity_id,
            'dltTemplateId': dlt_template_id,
            'recipientCount': recipient_count,
            'apiVersion': api_version,
            'createdAt': Decimal(str(now)),
            'expiresAt': Decimal(str(now + MESSAGE_TTL_SECONDS))
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
        'direction': item.get('direction', 'OUTBOUND'),
        'status': item.get('status', ''),
        'messageType': item.get('messageType', ''),
        'senderId': item.get('senderId', ''),
        'dltTemplateId': item.get('dltTemplateId', ''),
        'recipientCount': int(item.get('recipientCount', 1)),
        'providerMessageId': item.get('providerMessageId', ''),
        'apiVersion': item.get('apiVersion', 'v4'),
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


def _response(status_code: int, body: Dict, resp_origin: str = '') -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(resp_origin or origin),
        'body': json.dumps(body, default=str)
    }