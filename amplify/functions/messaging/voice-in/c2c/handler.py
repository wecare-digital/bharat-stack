"""
Airtel Click-to-Call (C2C) Lambda Function

Purpose: Connect two users on a call via Airtel Kong API
Features:
- HMAC-SHA256 authentication
- Call recording
- Real-time events and CDR

API: POST https://iqvoice.airtel.in/gateway/airtel-xchange/v2/click-to-call
Secrets: wecare/airtel/c2c
"""

import os
import json
import uuid
import time
import logging
import boto3
import base64
import hashlib
import hmac
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)

# Environment variables
VOICE_CALLS_TABLE = os.environ.get('VOICE_CALLS_TABLE', 'base-wecare-digital-VoiceCalls')
AIRTEL_C2C_SECRET_NAME = os.environ.get('AIRTEL_C2C_SECRET_NAME', 'wecare/airtel/c2c')
AIRTEL_KONG_HOST = os.environ.get('AIRTEL_KONG_HOST', 'iqvoice.airtel.in')
CALL_TTL_SECONDS = 90 * 24 * 60 * 60

# Cached secrets
_secrets_cache = None


def _get_secrets() -> Dict[str, str]:
    """Fetch Airtel C2C credentials from Secrets Manager (cached)."""
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache
    
    try:
        response = secrets_client.get_secret_value(SecretId=AIRTEL_C2C_SECRET_NAME)
        _secrets_cache = json.loads(response['SecretString'])
        logger.info(f"Loaded secrets from {AIRTEL_C2C_SECRET_NAME}")
        return _secrets_cache
    except Exception as e:
        logger.error(f"Failed to load secrets: {str(e)}")
        return {}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Click-to-Call requests."""
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    
    logger.info(json.dumps({
        'event': 'c2c_handler',
        'method': http_method,
        'requestId': request_id
    }))
    
    try:
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        
        # GET - List calls
        if http_method == 'GET':
            return _list_calls(event.get('queryStringParameters', {}), request_id)
        
        # POST - Make C2C call
        from_number = body.get('fromNumber')
        to_number = body.get('toNumber')
        enable_recording = body.get('enableRecording', True)
        contact_id = body.get('contactId', '')
        
        if not from_number or not to_number:
            return _response(400, {'error': 'fromNumber and toNumber are required'})
        
        call_id = str(uuid.uuid4())
        result = _make_c2c_call(from_number, to_number, enable_recording, request_id)
        
        # Store call record
        _store_call(call_id, contact_id, to_number, result.get('providerCallId'), 
                    result.get('status', 'failed'), from_number, request_id)
        
        if not result.get('success'):
            return _response(500, {
                'error': result.get('error', 'Failed to initiate click-to-call'),
                'callId': call_id
            })
        
        return _response(200, {
            'callId': call_id,
            'status': 'initiated',
            'correlationId': result.get('providerCallId'),
            'message': 'Click-to-call initiated. First participant will be called, then connected to second.'
        })
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"C2C error: {str(e)}")
        return _response(500, {'error': 'Internal server error'})


def _make_c2c_call(from_number: str, to_number: str, 
                   enable_recording: bool, request_id: str) -> Dict[str, Any]:
    """Make Click-to-Call via Airtel Kong API with HMAC-SHA256 auth."""
    try:
        secrets = _get_secrets()
        app_id = secrets.get('app_id')
        api_key = secrets.get('api_key')
        caller_id = secrets.get('caller_id', '8047311032')
        
        if not app_id or not api_key:
            return {'success': False, 'error': 'Airtel C2C credentials not configured'}
        
        from_clean = _clean_phone_number(from_number)
        to_clean = _clean_phone_number(to_number)
        
        if not from_clean or not to_clean:
            return {'success': False, 'error': 'Invalid phone number format'}
        
        payload = {
            "from": from_clean,
            "to": to_clean,
            "caller_id": caller_id,
            "to_caller_id": caller_id,
            "record": enable_recording,
            "early_media": True,
            "retry": {"count": 1}
        }
        
        body_str = json.dumps(payload)
        auth_headers = _generate_hmac_headers(body_str, app_id, api_key)
        
        url = f"https://{AIRTEL_KONG_HOST}/gateway/airtel-xchange/v2/click-to-call"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': auth_headers['authorization'],
            'X-Date': auth_headers['x_date'],
            'Digest': auth_headers['digest']
        }
        
        req = urllib.request.Request(url, data=body_str.encode('utf-8'), headers=headers, method='POST')
        
        logger.info(json.dumps({
            'event': 'c2c_request',
            'url': url,
            'from': from_clean,
            'to': to_clean,
            'requestId': request_id
        }))
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('status') == 'success' or result.get('call_id'):
                return {
                    'success': True,
                    'status': 'initiated',
                    'providerCallId': result.get('call_id') or result.get('correlationId')
                }
            
            return {
                'success': False,
                'error': result.get('message') or result.get('errorMessage', 'API error')
            }
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"C2C HTTP error: {e.code} - {error_body}")
        return {'success': False, 'error': f'HTTP {e.code}: {error_body[:200]}'}
    except Exception as e:
        logger.error(f"C2C error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _generate_hmac_headers(body: str, app_id: str, api_key: str) -> Dict[str, str]:
    """Generate HMAC-SHA256 authentication headers for Airtel Kong API."""
    x_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    body_hash = hashlib.sha256(body.encode('utf-8')).digest()
    body_hash_b64 = base64.b64encode(body_hash).decode('utf-8')
    digest = f'SHA-256={body_hash_b64}'
    
    signature_raw = f'x-date: {x_date}\ndigest: {digest}'
    signature = hmac.new(
        api_key.encode('utf-8'),
        signature_raw.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    
    authorization = f'hmac username="{app_id}", algorithm="hmac-sha256", headers="x-date digest", signature="{signature_b64}"'
    
    return {'authorization': authorization, 'x_date': x_date, 'digest': digest}


def _list_calls(params: Dict, request_id: str) -> Dict[str, Any]:
    """List C2C calls."""
    try:
        table = dynamodb.Table(VOICE_CALLS_TABLE)
        result = table.scan(Limit=int(params.get('limit', 100)))
        calls = result.get('Items', [])
        calls.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        
        return _response(200, {
            'calls': [_normalize_call(c) for c in calls],
            'count': len(calls)
        })
    except Exception as e:
        logger.error(f"List calls error: {str(e)}")
        return _response(500, {'error': str(e)})


def _store_call(call_id: str, contact_id: str, phone: str, provider_call_id: str,
                status: str, from_number: str, request_id: str) -> None:
    """Store call record in DynamoDB."""
    try:
        now = int(time.time())
        table = dynamodb.Table(VOICE_CALLS_TABLE)
        
        item = {
            'id': call_id,
            'callId': call_id,
            'contactId': contact_id or '',
            'phoneNumber': phone,
            'fromNumber': from_number,
            'provider': 'airtel_kong',
            'callType': 'c2c',
            'status': status,
            'direction': 'OUTBOUND',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
            'ttl': Decimal(str(now + CALL_TTL_SECONDS)),
        }
        
        if provider_call_id:
            item['providerCallId'] = provider_call_id
            item['correlationId'] = provider_call_id
        
        table.put_item(Item=item)
    except Exception as e:
        logger.error(f"Store call error: {str(e)}")


def _normalize_call(item: Dict) -> Dict:
    """Normalize call record for API response."""
    return {
        'id': item.get('id', ''),
        'callId': item.get('callId', ''),
        'contactId': item.get('contactId', ''),
        'phoneNumber': item.get('phoneNumber', ''),
        'fromNumber': item.get('fromNumber', ''),
        'provider': item.get('provider', ''),
        'callType': item.get('callType', ''),
        'status': item.get('status', ''),
        'correlationId': item.get('correlationId', ''),
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _clean_phone_number(phone: str) -> str:
    """Clean phone number to 10 digits."""
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
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
