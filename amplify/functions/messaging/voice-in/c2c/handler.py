"""
Airtel Click-to-Call (C2C) Lambda Function

Purpose: Connect two users on a call via Airtel Kong API
Features:
- HMAC-SHA256 authentication (Kong gateway)
- Call recording (stored in S3)
- Real-time events and CDR callbacks

API Endpoints:
- POST /voice-in/c2c - Initiate C2C call
- GET /voice-in/c2c - List C2C calls
- DELETE /voice-in/c2c - Delete call logs

Airtel API: POST https://iqvoice.airtel.in/gateway/airtel-xchange/v2/click-to-call
Auth: HMAC-SHA256 via Kong gateway
Secrets: wecare/airtel/c2c

Recording Storage: s3://app.wecare.digital/stack/voice/

Kong Credentials (from Secrets Manager):
- app_id: WECAREDIG_fD4BKqUbC8k90jNrPR0n (HMAC username)
- api_key: u^5KLtH@11 (HMAC signing key)
- caller_id: 8047311032 (Airtel registered 10-digit VN)

HMAC-SHA256 Auth Headers:
- Authorization: hmac username="<app_id>", algorithm="hmac-sha256", headers="x-date digest", signature="<sig>"
- X-Date: <UTC timestamp>
- Digest: SHA-256=<base64(sha256(body))>

HMAC Signing Process:
1. SHA-256 hash the request body -> base64 encode -> Digest header
2. Build signature string: "x-date: <X-Date>\ndigest: <Digest>"
3. HMAC-SHA256 sign with api_key -> base64 encode -> signature param
4. Authorization: hmac username="<app_id>", algorithm="hmac-sha256", headers="x-date digest", signature="<sig>"

Airtel C2C Request Payload:
{
  "from": "8130078559",          // Party A (first to be called)
  "to": "7080003969",            // Party B (connected after A answers)
  "caller_id": "8047311032",     // CLI shown to Party A
  "to_caller_id": "8047311032",  // CLI shown to Party B
  "record": true,                // Enable call recording
  "early_media": true,           // Play network announcements
  "retry": {"count": 1}          // Retry count (max 3)
}

CDR Webhook: https://api.wecare.digital/voice-cdr-webhook
CDR callbacks are sent by Airtel to the webhook configured in the call flow.

Airtel IP Whitelist (if 403 errors):
- 125.19.17.212
- 125.17.6.54
- 122.187.47.153

Our API Request Body:
{
  "fromNumber": "9876543210",       // Party A
  "toNumber": "9123456789",         // Party B
  "enableRecording": true,          // default: true
  "contactId": "optional-id",       // Optional contact reference
  "retryCount": 1,                  // Retry count (default: 1, max: 3)
  "enableEarlyMedia": true          // default: true
}
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
from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

logger = get_logger(__name__)

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)
secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)

# Environment variables
AIRTEL_C2C_TABLE = os.environ.get('AIRTEL_C2C_TABLE', 'stack-wecare-digital-AirtelC2CTable')
VOICE_CDR_TABLE = os.environ.get('VOICE_CDR_TABLE', 'stack-wecare-digital-VoiceCDRTable')
AIRTEL_C2C_SECRET_NAME = os.environ.get('AIRTEL_C2C_SECRET_NAME', 'wecare/airtel/c2c')
AIRTEL_KONG_HOST = os.environ.get('AIRTEL_KONG_HOST', 'iqvoice.airtel.in')
S3_BUCKET = 'app.wecare.digital'
S3_RECORDING_PREFIX = 'stack/voice/'
CALL_TTL_SECONDS = 90 * 24 * 60 * 60

# Cached secrets
_secrets_cache = None


def _get_secrets() -> Dict[str, str]:
    """
    Fetch Airtel C2C credentials from Secrets Manager (cached).

    Expected secret keys:
    - app_id: HMAC username (e.g. WECAREDIG_fD4BKqUbC8k90jNrPR0n)
    - api_key: HMAC signing key (e.g. u^5KLtH@11)
    - caller_id: Airtel registered 10-digit VN (e.g. 8047311032)
    """
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


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Click-to-Call requests."""
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    global origin
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('rawPath', event.get('path', ''))
    query_params = event.get('queryStringParameters') or {}

    logger.info(json.dumps({
        'event': 'c2c_handler',
        'method': http_method,
        'path': path,
        'requestId': request_id
    }))

    try:
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'}, origin)

        body = json.loads(event.get('body', '{}')) if event.get('body') else {}

        # GET - List calls
        if http_method == 'GET':
            return _list_calls(query_params, request_id)

        # DELETE - Delete call logs
        if http_method == 'DELETE' or '/delete' in path or '/clear-logs' in path:
            call_ids = body.get('callIds', [])
            call_id = query_params.get('callId')
            hard_delete = query_params.get('hard') == 'true' or body.get('hardDelete', False)
            clear_all = body.get('clearAll', False)

            if clear_all:
                return _clear_logs(request_id)
            elif call_id:
                return _delete_call(call_id, hard_delete, request_id)
            elif call_ids:
                return _delete_calls(call_ids, hard_delete, request_id)
            return _response(400, {'error': 'callId, callIds, or clearAll is required'})

        # Detect Airtel CDR callback (Airtel may send C2C CDR callbacks to this endpoint)
        if http_method == 'POST' and _is_airtel_cdr_callback(body):
            return _handle_cdr_callback(body, request_id)

        # POST - Make C2C call (or clear logs via POST)
        from_number = body.get('fromNumber')
        to_number = body.get('toNumber')

        if body.get('clearAll') or body.get('_action') == 'clear-logs':
            return _clear_logs(request_id)

        enable_recording = body.get('enableRecording', True)
        contact_id = body.get('contactId', '')
        retry_count = min(int(body.get('retryCount', 1)), 3)
        enable_early_media = body.get('enableEarlyMedia', True)

        if not from_number or not to_number:
            return _response(400, {'error': 'fromNumber and toNumber are required'})

        call_id = str(uuid.uuid4())
        result = _make_c2c_call(from_number, to_number, enable_recording,
                                retry_count, enable_early_media, request_id)

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
            'message': 'Click-to-call initiated. Party A will be called first, then connected to Party B.'
        })

    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"C2C error: {str(e)}")
        return _response(500, {'error': 'Internal server error'})


def _make_c2c_call(from_number: str, to_number: str, enable_recording: bool,
                   retry_count: int, enable_early_media: bool,
                   request_id: str) -> Dict[str, Any]:
    """
    Make Click-to-Call via Airtel Kong API with HMAC-SHA256 auth.

    Endpoint: POST https://iqvoice.airtel.in/gateway/airtel-xchange/v2/click-to-call
    Auth: HMAC-SHA256 (app_id as username, api_key as signing key)

    Payload:
    {
      "from": "<Party A number>",
      "to": "<Party B number>",
      "caller_id": "8047311032",
      "to_caller_id": "8047311032",
      "record": true,
      "early_media": true,
      "retry": {"count": 1}
    }
    """
    try:
        secrets = _get_secrets()
        app_id = secrets.get('app_id')
        api_key = secrets.get('api_key')
        caller_id = secrets.get('caller_id', '8047311032')

        if not app_id or not api_key:
            return {'success': False, 'error': 'Airtel C2C credentials (app_id/api_key) not configured'}

        from_clean = _clean_phone_number(from_number)
        to_clean = _clean_phone_number(to_number)

        if not from_clean or not to_clean:
            return {'success': False, 'error': 'Invalid phone number format'}

        if from_clean == to_clean:
            return {'success': False, 'error': 'From and To numbers cannot be the same'}

        payload = {
            "from": from_clean,
            "to": to_clean,
            "caller_id": caller_id,
            "to_caller_id": caller_id,
            "record": enable_recording,
            "early_media": enable_early_media,
            "retry": {"count": retry_count}
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
            'record': enable_recording,
            'retryCount': retry_count,
            'requestId': request_id
        }))

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))

            logger.info(json.dumps({
                'event': 'c2c_response',
                'statusCode': response.status,
                'result': result,
                'requestId': request_id
            }))

            # Success: {"status": "success", "correlationId": "Xchange123863"}
            if result.get('status') == 'success' or result.get('correlationId'):
                correlation_id = result.get('correlationId') or result.get('call_id') or result.get('id', '')
                return {
                    'success': True,
                    'status': 'initiated',
                    'providerCallId': correlation_id
                }

            return {
                'success': False,
                'error': result.get('errorMessage') or result.get('message') or 'Unknown API error',
                'errorCode': result.get('errorCode', '')
            }

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(json.dumps({
            'event': 'c2c_http_error',
            'statusCode': e.code,
            'errorBody': error_body[:500],
            'requestId': request_id
        }))

        error_msg = f'HTTP {e.code}'
        error_code = ''
        try:
            error_json = json.loads(error_body)
            error_msg = error_json.get('errorMessage') or error_json.get('message') or error_msg
            error_code = error_json.get('errorCode', '')
        except (json.JSONDecodeError, AttributeError):
            pass

        if e.code == 403:
            logger.error(json.dumps({
                'event': 'airtel_403_error',
                'service': 'c2c',
                'url': url,
                'app_id': app_id,
                'note': 'Check: 1) HMAC auth correct? 2) App ID valid? 3) IP whitelisted?',
                'airtel_ips_to_whitelist': ['125.19.17.212', '125.17.6.54', '122.187.47.153']
            }))

        return {
            'success': False,
            'error': f'{error_msg} (HTTP {e.code})',
            'errorCode': error_code
        }
    except Exception as e:
        logger.error(f"C2C error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _generate_hmac_headers(body: str, app_id: str, api_key: str) -> Dict[str, str]:
    """
    Generate HMAC-SHA256 authentication headers for Airtel Kong API.

    Process (matches Airtel Postman pre-request script):
    1. SHA-256 hash the body -> base64 -> Digest: SHA-256=<hash>
    2. Signature string: "x-date: <timestamp>\ndigest: <digest>"
    3. HMAC-SHA256(api_key, signature_string) -> base64 -> signature
    4. Authorization: hmac username="<app_id>", algorithm="hmac-sha256",
       headers="x-date digest", signature="<signature>"
    """
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

    authorization = (
        f'hmac username="{app_id}", algorithm="hmac-sha256", '
        f'headers="x-date digest", signature="{signature_b64}"'
    )

    return {'authorization': authorization, 'x_date': x_date, 'digest': digest}


def _list_calls(params: Dict, request_id: str) -> Dict[str, Any]:
    """List C2C calls."""
    try:
        table = dynamodb.Table(AIRTEL_C2C_TABLE)
        from boto3.dynamodb.conditions import Attr

        scan_kwargs = {'Limit': int(params.get('limit', 100))}
        filter_expressions = []

        if params.get('contactId'):
            filter_expressions.append(Attr('contactId').eq(params['contactId']))
        if params.get('status'):
            filter_expressions.append(Attr('status').eq(params['status']))
        if params.get('fromNumber'):
            filter_expressions.append(Attr('fromNumber').contains(params['fromNumber']))
        if params.get('toNumber'):
            filter_expressions.append(Attr('toNumber').contains(params['toNumber']))

        if filter_expressions:
            combined = filter_expressions[0]
            for expr in filter_expressions[1:]:
                combined = combined & expr
            scan_kwargs['FilterExpression'] = combined

        result = table.scan(**scan_kwargs)
        calls = result.get('Items', [])
        calls.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)

        return _response(200, {
            'calls': [_normalize_call(c) for c in calls],
            'count': len(calls)
        })
    except Exception as e:
        logger.error(f"List calls error: {str(e)}")
        return _response(500, {'error': str(e)})


def _store_call(call_id: str, contact_id: str, to_number: str, provider_call_id: str,
                status: str, from_number: str, request_id: str) -> None:
    """Store call record in AirtelC2C DynamoDB table."""
    try:
        now = int(time.time())
        table = dynamodb.Table(AIRTEL_C2C_TABLE)

        secrets = _get_secrets()
        caller_id = secrets.get('caller_id', '8047311032')

        item = {
            'callId': call_id,
            'contactId': contact_id or '',
            'fromNumber': from_number,
            'toNumber': to_number,
            'callerId': caller_id,
            'status': status.upper(),
            'recordingEnabled': True,
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
            'expiresAt': Decimal(str(now + CALL_TTL_SECONDS)),
        }

        if provider_call_id:
            item['correlationId'] = provider_call_id

        table.put_item(Item=item)
    except Exception as e:
        logger.error(f"Store call error: {str(e)}")


def _normalize_call(item: Dict) -> Dict:
    """Normalize call record for API response."""
    return {
        'callId': item.get('callId', ''),
        'contactId': item.get('contactId', ''),
        'fromNumber': item.get('fromNumber', ''),
        'toNumber': item.get('toNumber', ''),
        'callerId': item.get('callerId', ''),
        'status': item.get('status', ''),
        'duration': int(float(item.get('duration', 0))),
        'recordingEnabled': item.get('recordingEnabled', True),
        'recordingUrl': item.get('recordingUrl', ''),
        's3RecordingKey': item.get('s3RecordingKey', ''),
        'correlationId': item.get('correlationId', ''),
        'errorDetails': item.get('errorDetails', ''),
        'createdAt': int(float(item.get('createdAt', 0))),
        'updatedAt': int(float(item.get('updatedAt', 0))),
    }


def _is_airtel_cdr_callback(body: Dict) -> bool:
    """
    Detect if a POST payload is an Airtel CDR callback (vs a user C2C API request).

    Airtel CDR callbacks contain fields like vmSessionId, Session_ID,
    overallCallStatus, participants array, etc. that user C2C requests never have.
    User C2C requests have: fromNumber, toNumber, enableRecording.
    """
    # Format A (standard camelCase)
    if body.get('vmSessionId') or body.get('clientCorrelationId'):
        return True
    # Format B (display format)
    if body.get('Session_ID') or body.get('Client_Correlation_Id'):
        return True
    # Either format
    if body.get('overallCallStatus') or body.get('Overall_Call_Status'):
        return True
    if body.get('participants') and isinstance(body.get('participants'), list):
        for p in body['participants']:
            if isinstance(p, dict) and p.get('participantType'):
                return True
    return False


def _handle_cdr_callback(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Handle Airtel CDR callback that was sent to the C2C endpoint.

    Normalizes the payload and stores it in the VoiceCDR table.
    """
    try:
        normalized = _normalize_cdr_payload(body)
        vm_session_id = normalized.get('vmSessionId', '')
        client_correlation_id = normalized.get('clientCorrelationId', '')

        logger.info(json.dumps({
            'event': 'c2c_cdr_callback_received',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': client_correlation_id,
            'callType': normalized.get('callType', ''),
            'overallCallStatus': normalized.get('overallCallStatus', ''),
            'requestId': request_id
        }))

        current_time = int(time.time())
        ttl_expiry = current_time + (90 * 24 * 60 * 60)

        duration = _safe_int_val(normalized.get('duration', 0))
        from_waiting_time = _safe_int_val(normalized.get('fromWaitingTime', 0))
        conversation_duration = _safe_int_val(normalized.get('conversationDuration', 0))

        participants = normalized.get('participants', [])
        caller_name = ''
        destination_name = ''
        caller_status = normalized.get('callerNumberStatus', '')
        dest_status = normalized.get('destinationNumberStatus', '')
        participants_json = ''

        for p in participants:
            p_type = p.get('participantType', '')
            if p_type == 'From':
                caller_name = p.get('participantName', '') or normalized.get('callerName', '')
                if not caller_status:
                    caller_status = p.get('status', '')
            elif p_type == 'To':
                destination_name = p.get('participantName', '') or normalized.get('destinationName', '')
                if not dest_status:
                    dest_status = p.get('status', '')

        try:
            if participants:
                participants_json = json.dumps(participants)
        except (TypeError, ValueError):
            pass

        cdr_record = {
            'id': str(uuid.uuid4()),
            'vmSessionId': vm_session_id,
            'clientCorrelationId': client_correlation_id,
            'customerId': normalized.get('customerId', ''),
            'startTime': normalized.get('startTime', 0),
            'endTime': normalized.get('endTime', 0),
            'timestamp': normalized.get('timestamp', ''),
            'createdAt': current_time,
            'expiresAt': ttl_expiry,
            'durationMs': duration,
            'durationSec': round(duration / 1000, 2) if duration else 0,
            'fromWaitingTimeMs': from_waiting_time,
            'fromWaitingTimeSec': round(from_waiting_time / 1000, 2) if from_waiting_time else 0,
            'conversationDurationMs': conversation_duration,
            'conversationDurationSec': round(conversation_duration / 1000, 2) if conversation_duration else 0,
            'callType': normalized.get('callType', 'OUTBOUND'),
            'overallCallStatus': normalized.get('overallCallStatus', ''),
            'hangupCause': normalized.get('hangupCause', ''),
            'callerId': normalized.get('callerId', ''),
            'callerNumber': normalized.get('callerNumber', ''),
            'destinationNumber': normalized.get('destinationNumber', ''),
            'callerName': caller_name,
            'destinationName': destination_name,
            'callerNumberStatus': caller_status,
            'destinationNumberStatus': dest_status,
            'circleNameCaller': normalized.get('circleNameCaller', ''),
            'circleNameDestination': normalized.get('circleNameDestination', ''),
            'operatorNameCaller': normalized.get('operatorNameCaller', ''),
            'operatorNameDestination': normalized.get('operatorNameDestination', ''),
            'recordingURL': normalized.get('recordingURL', ''),
            'participantsJson': participants_json,
            'participantsCount': len(participants),
            'source': 'airtel_c2c_cdr_callback',
        }

        item = {}
        for key, value in cdr_record.items():
            if value is None or value == '':
                continue
            if isinstance(value, (float, int)):
                item[key] = Decimal(str(value))
            else:
                item[key] = value

        table = dynamodb.Table(VOICE_CDR_TABLE)
        table.put_item(Item=item)

        return _response(200, {
            'status': 'ok',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': client_correlation_id,
            'message': 'C2C CDR callback received and stored'
        })

    except Exception as e:
        logger.error(f"C2C CDR callback error: {str(e)}")
        return _response(500, {'error': f'CDR processing error: {str(e)}'})


def _normalize_cdr_payload(payload: Dict) -> Dict:
    """Normalize Airtel CDR from Format B (Display_Format) to camelCase."""
    normalized = dict(payload)
    field_map = {
        'Session_ID': 'vmSessionId',
        'Client_Correlation_Id': 'clientCorrelationId',
        'Overall_Call_Status': 'overallCallStatus',
        'Caller_Number': 'callerNumber',
        'Destination_Number': 'destinationNumber',
        'Caller_ID': 'callerId',
        'Call_Type': 'callType',
        'Caller_Status': 'callerNumberStatus',
        'Destination_Status': 'destinationNumberStatus',
        'Caller_Circle_Name': 'circleNameCaller',
        'Destination_Circle_Name': 'circleNameDestination',
        'Caller_Operator_Name': 'operatorNameCaller',
        'Destination_Operator_Name': 'operatorNameDestination',
        'Hangup_Cause': 'hangupCause',
        'Caller_Name': 'callerName',
        'Destination_Name': 'destinationName',
        'Recording': 'recordingURL',
        'Customer_Name': 'customerId',
        'Destination_CLI': 'displayCliDestination',
    }
    for display_key, camel_key in field_map.items():
        if payload.get(display_key) is not None and not normalized.get(camel_key):
            val = payload[display_key]
            if isinstance(val, str) and val.strip() in ('""', "''", ''):
                val = ''
            normalized[camel_key] = val
    if not normalized.get('callType'):
        normalized['callType'] = payload.get('Call_Type', 'OUTBOUND')
    if not normalized.get('customerId'):
        normalized['customerId'] = payload.get('Customer_Name', '')
    return normalized


def _safe_int_val(val) -> int:
    """Safely convert a value to int."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0
    return 0


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


def _delete_call(call_id: str, hard_delete: bool, request_id: str) -> Dict[str, Any]:
    """Delete a single C2C call record (soft or hard delete)."""
    try:
        table = dynamodb.Table(AIRTEL_C2C_TABLE)

        if hard_delete:
            # Delete S3 recording if exists
            try:
                result = table.get_item(Key={'callId': call_id})
                call = result.get('Item')
                if call and call.get('s3RecordingKey'):
                    s3.delete_object(Bucket=S3_BUCKET, Key=call['s3RecordingKey'])
            except Exception as e:
                logger.warning(f"Failed to delete S3 recording: {str(e)}")

            table.delete_item(Key={'callId': call_id})
            return _response(200, {'success': True, 'deleted': call_id, 'type': 'hard'})
        else:
            now = int(time.time())
            table.update_item(
                Key={'callId': call_id},
                UpdateExpression='SET #status = :status, deletedAt = :deletedAt, updatedAt = :updatedAt',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'DELETED',
                    ':deletedAt': Decimal(str(now)),
                    ':updatedAt': Decimal(str(now))
                }
            )
            return _response(200, {'success': True, 'deleted': call_id, 'type': 'soft'})
    except Exception as e:
        logger.error(f"Delete call error: {str(e)}")
        return _response(500, {'error': str(e)})


def _delete_calls(call_ids: list, hard_delete: bool, request_id: str) -> Dict[str, Any]:
    """Delete multiple C2C call records."""
    deleted_count = 0
    for call_id in call_ids:
        try:
            result = _delete_call(call_id, hard_delete, request_id)
            if json.loads(result.get('body', '{}')).get('success'):
                deleted_count += 1
        except Exception:
            pass

    return _response(200, {
        'success': True,
        'deletedCount': deleted_count,
        'type': 'hard' if hard_delete else 'soft'
    })


def _clear_logs(request_id: str) -> Dict[str, Any]:
    """Clear all C2C call logs (handles pagination for large tables)."""
    try:
        table = dynamodb.Table(AIRTEL_C2C_TABLE)
        deleted_count = 0

        scan_kwargs = {'ProjectionExpression': 'callId,s3RecordingKey'}
        while True:
            result = table.scan(**scan_kwargs)
            for item in result.get('Items', []):
                if item.get('s3RecordingKey'):
                    try:
                        s3.delete_object(Bucket=S3_BUCKET, Key=item['s3RecordingKey'])
                    except Exception:
                        pass
                table.delete_item(Key={'callId': item['callId']})
                deleted_count += 1

            if 'LastEvaluatedKey' not in result:
                break
            scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']

        return _response(200, {
            'success': True,
            'deletedCount': deleted_count,
            'message': f'Cleared {deleted_count} C2C call logs'
        })
    except Exception as e:
        logger.error(f"Clear logs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _response(status_code: int, body: Dict, origin: str = '') -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body, default=str)
    }
