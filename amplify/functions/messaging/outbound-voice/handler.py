"""
Outbound Voice Lambda Function
Purpose: Make outbound voice calls via Airtel IQ (C2C + OBD)
Unified endpoint for all Airtel voice call types
"""
import os
import json
import logging
import time
import uuid
import hashlib
import hmac
import boto3
import urllib.request
from typing import Dict, Any, Optional

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

from lambda_utils.logging import get_logger

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

VOICE_TABLE = os.environ.get('VOICE_TABLE', 'stack-wecare-digital-VoiceCalls')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
SECRET_NAME = os.environ.get('AIRTEL_SECRET', 'wecare/airtel-iq')
CDR_WEBHOOK_URL = os.environ.get('CDR_WEBHOOK_URL', 'https://api.wecare.digital/voice-cdr-webhook')

# CORS headers provided by lambda_utils.response.cors_headers(origin)

_secrets_cache = None

def _get_secrets() -> Dict[str, str]:
    global _secrets_cache
    if _secrets_cache:
        return _secrets_cache
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        _secrets_cache = json.loads(response['SecretString'])
        return _secrets_cache
    except Exception as e:
        logger.error(f'Failed to get secrets: {e}')
        return {}

# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event, context):
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)
    http = event.get('requestContext', {}).get('http', {})
    method = http.get('method', event.get('httpMethod', 'GET'))
    path = http.get('path', '') or event.get('rawPath', '')
    params = event.get('queryStringParameters') or {}

    if method == 'OPTIONS':
        return _response(200, {})

    try:
        if method == 'GET':
            return _list_calls(params, request_id)
        elif method == 'POST':
            body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            call_type = body.get('callType', 'click_to_call')
            if call_type == 'click_to_call':
                return _make_c2c_call(body, request_id)
            elif call_type == 'obd':
                return _make_obd_call(body, request_id)
            return _response(400, {'error': f'Unknown callType: {call_type}'})
        elif method == 'DELETE':
            call_id = params.get('callId')
            if call_id:
                return _delete_call(call_id, request_id)
            return _response(400, {'error': 'callId required'})
        return _response(400, {'error': 'Invalid method'})
    except Exception as e:
        logger.error(f'[{request_id}] Error: {e}')
        return _response(500, {'error': str(e)})


def _make_c2c_call(body: Dict, request_id: str) -> Dict:
    secrets = _get_secrets()
    app_id = secrets.get('app_id', '')
    api_key = secrets.get('api_key', '')
    customer_id = secrets.get('customer_id', '')

    from_number = body.get('fromNumber', '8047311032')
    to_number = body.get('toNumber', body.get('phoneNumber', ''))
    contact_id = body.get('contactId', '')

    if not to_number:
        return _response(400, {'error': 'toNumber/phoneNumber required'})

    call_id = str(uuid.uuid4())
    payload = json.dumps({
        'callerId': from_number,
        'destination': to_number,
        'callBackURLs': [
            {'eventType': 'CDR', 'notifyURL': CDR_WEBHOOK_URL, 'method': 'POST', 'headers': {}},
            {'eventType': 'ALL', 'notifyURL': CDR_WEBHOOK_URL, 'method': 'POST', 'headers': {}}
        ]
    })

    headers = _generate_hmac_headers(payload, app_id, api_key)
    headers['Content-Type'] = 'application/json'

    try:
        url = f'https://iqvoice.airtel.in/api/v1/customers/{customer_id}/c2c'
        req = urllib.request.Request(url, data=payload.encode(), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())

        _store_call(call_id, contact_id, to_number, result.get('vmSessionId', ''), 'click_to_call', request_id)
        return _response(200, {'callId': call_id, 'status': 'initiated', 'provider': 'airtel', 'callType': 'click_to_call'})
    except Exception as e:
        logger.error(f'[{request_id}] C2C call failed: {e}')
        return _response(500, {'error': f'Call failed: {str(e)}'})


def _make_obd_call(body: Dict, request_id: str) -> Dict:
    secrets = _get_secrets()
    app_id = secrets.get('app_id', '')
    api_key = secrets.get('api_key', '')
    customer_id = secrets.get('customer_id', '')

    to_number = body.get('toNumber', body.get('phoneNumber', ''))
    contact_id = body.get('contactId', '')
    caller_id = body.get('callerId', '8040761117')

    if not to_number:
        return _response(400, {'error': 'toNumber/phoneNumber required'})

    call_id = str(uuid.uuid4())
    payload = json.dumps({
        'callerId': caller_id,
        'destination': to_number,
        'callBackURLs': [
            {'eventType': 'CDR', 'notifyURL': CDR_WEBHOOK_URL, 'method': 'POST', 'headers': {}},
            {'eventType': 'ALL', 'notifyURL': CDR_WEBHOOK_URL, 'method': 'POST', 'headers': {}}
        ]
    })

    headers = _generate_hmac_headers(payload, app_id, api_key)
    headers['Content-Type'] = 'application/json'

    try:
        url = f'https://iqvoice.airtel.in/api/v1/customers/{customer_id}/obd'
        req = urllib.request.Request(url, data=payload.encode(), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())

        _store_call(call_id, contact_id, to_number, result.get('vmSessionId', ''), 'obd', request_id)
        return _response(200, {'callId': call_id, 'status': 'initiated', 'provider': 'airtel', 'callType': 'obd'})
    except Exception as e:
        logger.error(f'[{request_id}] OBD call failed: {e}')
        return _response(500, {'error': f'Call failed: {str(e)}'})


def _generate_hmac_headers(body: str, app_id: str, api_key: str) -> Dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    signature_string = f'{body}{timestamp}'
    signature = hmac.new(api_key.encode(), signature_string.encode(), hashlib.sha256).hexdigest()
    return {'X-App-Id': app_id, 'X-Timestamp': timestamp, 'X-Signature': signature}


def _list_calls(params: Dict, request_id: str) -> Dict:
    table = dynamodb.Table(VOICE_TABLE)
    try:
        all_calls = []
        scan_kwargs = {}
        while True:
            response = table.scan(**scan_kwargs)
            all_calls.extend(response.get('Items', []))
            if 'LastEvaluatedKey' not in response:
                break
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        calls = [_normalize(item) for item in all_calls]
        calls.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        return _response(200, {'calls': calls, 'count': len(calls)})
    except Exception as e:
        return _response(500, {'error': str(e)})


def _store_call(call_id, contact_id, to_number, provider_call_id, call_type, request_id):
    table = dynamodb.Table(VOICE_TABLE)
    now = int(time.time())
    table.put_item(Item={
        'id': call_id,
        'callId': call_id, 'contactId': contact_id, 'phoneNumber': to_number,
        'providerCallId': provider_call_id, 'provider': 'airtel', 'callType': call_type,
        'status': 'initiated', 'direction': 'OUTBOUND', 'duration': 0,
        'createdAt': now, 'updatedAt': now
    })


def _delete_call(call_id: str, request_id: str) -> Dict:
    table = dynamodb.Table(VOICE_TABLE)
    try:
        table.delete_item(Key={'id': call_id})
        return _response(200, {'success': True, 'callId': call_id})
    except Exception as e:
        return _response(500, {'error': str(e)})


def _normalize(item: Dict) -> Dict:
    return {
        'callId': item.get('callId', ''), 'contactId': item.get('contactId', ''),
        'phoneNumber': item.get('phoneNumber', ''), 'provider': item.get('provider', 'airtel'),
        'callType': item.get('callType', ''), 'status': item.get('status', ''),
        'direction': item.get('direction', 'OUTBOUND'), 'duration': int(item.get('duration', 0)),
        'recordingUrl': item.get('recordingUrl'), 'createdAt': int(item.get('createdAt', 0)),
        'updatedAt': int(item.get('updatedAt', 0))
    }


def _response(status_code: int, body: Dict, origin: str = '') -> Dict[str, Any]:
    return {'statusCode': status_code, 'headers': cors_headers(origin), 'body': json.dumps(body, default=str)}
