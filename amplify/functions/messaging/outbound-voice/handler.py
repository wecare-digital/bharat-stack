"""
Outbound Voice Lambda Function
Purpose: Make outbound voice calls via Airtel IQ (C2C + OBD)
Unified endpoint for all Airtel voice call types

C2C API Formats:
━━━━━━━━━━━━━━━
1. Simplified Kong v2 (default):
   POST https://iqvoice.airtel.in/gateway/airtel-xchange/v2/click-to-call
   Simple from/to/caller_id payload — Airtel wraps into workflow internally

2. Full Workflow (advanced — per Airtel C2C API Spec):
   POST https://iqvoice.airtel.in/gateway/airtel-xchange/v2/execute/workflow
   Full callFlowConfiguration with initiateCall, addParticipant, record components
   Supports: merging strategies (SEQUENTIAL/ROUND_ROBIN/PARALLEL), per-component
   callbacks, maxRetries per participant (max 3), enableEarlyMedia, maxTime

Auth: HMAC-SHA256 via Kong gateway (app_id as username, api_key as signing key)

C2C Call Flow (per Airtel spec):
1. Airtel initiates call to Party A (initiateCall_1.participants[0])
2. Once Party A answers, recording starts (record.enabled=true)
3. New call initiated to Party B (addParticipant_1.participants[0])
4. Both parties patched together when Party B answers
5. Real-time events posted to callbackURLs during call
6. CDR posted to callbackURL after call ends (includes recordingURL)

Callback Event Types: ALL, CALL, MEDIA, DTMF, RECORD, CDR, API, SUBMITTED, DELIVERED, ERROR

Call Response: {"status": "success", "correlationId": "Xchange123863"}
Error Codes: INCORRECT_CALL_FLOW_ID, CUSTOMER_DETAILS_NOT_AVAILABLE,
  INCORRECT_CUSTOMER_ID, INVALID_CALLER_ID, DUPLICATE_PARTICIPANT_ADDRESS_FOUND,
  FROM_NUMBER_NULL_ERROR, TO_NUMBER_NULL_ERROR, FROM_PARTICIPANT_MAX_RETRIES_GREATER_THAN_REQUIRED_VALUE (max 3)
"""
import os
import json
import logging
import time
import uuid
import hashlib
import hmac
import base64
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
SECRET_NAME = os.environ.get('AIRTEL_SECRET', 'wecare/airtel/c2c')
CDR_WEBHOOK_URL = os.environ.get('CDR_WEBHOOK_URL', 'https://api.wecare.digital/voice-in/c2c')

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
    """
    Make a Click-to-Call via Airtel Kong API.
    
    Supports two modes:
    1. Simple (default): Uses /v2/click-to-call with from/to/caller_id
    2. Workflow: Uses /v2/execute/workflow with full callFlowConfiguration
       Set body.useWorkflow=true and optionally body.callFlowId
    
    Per Airtel C2C spec:
    - maxRetries per participant: max 3
    - mergingStrategy: SEQUENTIAL (default), ROUND_ROBIN, PARALLEL
    - enableEarlyMedia: plays actual network announcements
    - record.enabled: true by default
    - callbackURLs: CDR + ALL events
    """
    secrets = _get_secrets()
    app_id = secrets.get('app_id', '')
    api_key = secrets.get('api_key', '')
    caller_id = secrets.get('caller_id', '8047311032')
    call_flow_id = secrets.get('call_flow_id', '')

    from_number = body.get('fromNumber', '')
    to_number = body.get('toNumber', body.get('phoneNumber', ''))
    contact_id = body.get('contactId', '')
    use_workflow = body.get('useWorkflow', False)
    retry_count = min(int(body.get('retryCount', 1)), 3)  # max 3 per Airtel spec
    enable_early_media = body.get('enableEarlyMedia', True)
    enable_recording = body.get('enableRecording', True)

    if not to_number:
        return _response(400, {'error': 'toNumber/phoneNumber required'})

    if not from_number:
        return _response(400, {'error': 'fromNumber required'})

    call_id = str(uuid.uuid4())

    if use_workflow and call_flow_id:
        # Full workflow format per Airtel C2C API Spec Section 1.3
        payload = json.dumps({
            'callFlowId': body.get('callFlowId', call_flow_id),
            'customerId': secrets.get('customer_id', app_id),
            'callType': 'OUTBOUND',
            'callerId': caller_id,
            'callFlowConfiguration': {
                'initiateCall_1': {
                    'callerId': caller_id,
                    'mergingStrategy': body.get('mergingStrategy', 'SEQUENTIAL'),
                    'participants': [{
                        'participantAddress': from_number,
                        'callerId': caller_id,
                        'participantName': 'A',
                        'maxRetries': retry_count,
                        'maxTime': 0
                    }],
                    'maxTime': 0,
                    'callBackURLs': [
                        {
                            'eventType': 'CDR',
                            'notifyURL': CDR_WEBHOOK_URL,
                            'method': 'POST',
                            'headers': {}
                        },
                        {
                            'eventType': 'ALL',
                            'notifyURL': CDR_WEBHOOK_URL,
                            'method': 'POST',
                            'headers': {}
                        }
                    ]
                },
                'addParticipant_1': {
                    'mergingStrategy': 'SEQUENTIAL',
                    'maxTime': 0,
                    'participants': [{
                        'participantAddress': to_number,
                        'callerId': caller_id,
                        'participantName': 'B',
                        'maxRetries': retry_count,
                        'maxTime': 0,
                        'enableEarlyMedia': enable_early_media
                    }]
                },
                'record': {
                    'enabled': enable_recording
                }
            }
        })
        url = 'https://iqvoice.airtel.in/gateway/airtel-xchange/v2/execute/workflow'
    else:
        # Simplified Kong v2 format
        payload = json.dumps({
            'from': from_number,
            'to': to_number,
            'caller_id': caller_id,
            'to_caller_id': caller_id,
            'record': enable_recording,
            'early_media': enable_early_media,
            'retry': {'count': retry_count},
            'callbacks': [
                {
                    'event_type': 'CDR',
                    'notify_url': CDR_WEBHOOK_URL,
                    'method': 'POST',
                    'headers': {'Content-Type': 'application/json'},
                    'serviceId': 'wecareCDRDetailsService_c2c',
                    'projectId': 'We_CareCDRDetails_c2c'
                }
            ]
        })
        url = 'https://iqvoice.airtel.in/gateway/airtel-xchange/v2/click-to-call'

    headers = _generate_hmac_headers(payload, app_id, api_key)
    headers['Content-Type'] = 'application/json'

    try:
        req = urllib.request.Request(url, data=payload.encode(), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())

        correlation_id = result.get('correlationId', result.get('vmSessionId', ''))
        _store_call(call_id, contact_id, to_number, correlation_id, 'click_to_call', request_id)
        return _response(200, {
            'callId': call_id,
            'correlationId': correlation_id,
            'status': 'initiated',
            'provider': 'airtel',
            'callType': 'click_to_call',
            'mode': 'workflow' if (use_workflow and call_flow_id) else 'simple'
        })
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f'[{request_id}] C2C call failed: {e.code} - {error_body}')
        return _response(e.code, {'error': f'Airtel C2C error: {error_body[:300]}'})
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
    """Generate HMAC-SHA256 auth headers for Airtel Kong API (C2C format)."""
    from datetime import datetime, timezone
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

    return {
        'Authorization': f'hmac username="{app_id}", algorithm="hmac-sha256", headers="x-date digest", signature="{signature_b64}"',
        'X-Date': x_date,
        'Digest': digest
    }


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


def _response(status_code: int, body: Dict, resp_origin: str = '') -> Dict[str, Any]:
    return {'statusCode': status_code, 'headers': cors_headers(resp_origin or origin), 'body': json.dumps(body, default=str)}
