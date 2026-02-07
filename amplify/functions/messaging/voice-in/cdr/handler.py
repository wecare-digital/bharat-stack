"""
Airtel Voice CDR Webhook Handler Lambda Function

Purpose: Receive and store Call Detail Records (CDR) from Airtel Cloud Communication Platform
         Handles BOTH inbound and outbound call CDRs (C2C, OBD, direct inbound)

Webhook Configuration:
- URL: POST /voice-cdr-webhook
- Full URL: https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook
- Inbound Number: +91 9319767034
- Email: voice@wecare.digital

Recording Storage: s3://auth.wecare.digital/voice/voice-in/cdr/

Airtel IP Whitelist (if 403 errors):
- 125.19.17.212
- 125.17.6.54
- 122.187.47.153

NOTE: We do NOT need to whitelist IPs for sending SMS traffic.
      The above IPs only need whitelisting if receiving 403 errors on API calls.

CDR Callback Body Format (DEFAULT - no custom config needed from Airtel side):
{
  "vmSessionId": "unique-session-id",
  "clientCorrelationId": "xchange-tracking-id",
  "customerId": "WECAREDIG_v6J1SyLLI2auy7Lw9JrW",
  "callType": "INBOUND" | "OUTBOUND",
  "overallCallStatus": "Answered" | "Missed" | "Disconnected" | "Busy",
  "callerNumber": "9876543210",
  "destinationNumber": "9123456789",
  "calledNumber": "9319767034",
  "callerId": "8047311032",
  "startTime": 1705312200000,
  "endTime": 1705312245000,
  "callAnswerTime": 1705312205000,
  "duration": 45000,              // Total duration in milliseconds
  "fromWaitingTime": 5000,        // IVR/wait time in milliseconds
  "conversationDuration": 40000,  // Talk time in milliseconds
  "billableDuration": 40000,      // Billable duration in milliseconds
  "hangUpStatus": "USER_INITIATED" | "SYSTEM_INITIATED",
  "hangupCause": "NORMAL_CLEARING",
  "callerNumberStatus": "ANSWERED",
  "destinationNumberStatus": "ANSWERED",
  "circleNameCaller": "Maharashtra",
  "circleNameDestination": "Delhi",
  "operatorNameCaller": "Jio",
  "operatorNameDestination": "Airtel",
  "recordingURL": "https://...",
  "retryCountCaller": 0,
  "retryCountDestination": 0,
  "participants": [...],
  "timestamp": "2024-01-15T10:30:00Z"
}

Click-to-Call (C2C) Callback:
- Uses DEFAULT Airtel callback body (no custom config needed)
- CDR callbacks sent to this same /voice-cdr-webhook endpoint
- callType will be "OUTBOUND" for C2C initiated calls

OBD (Outbound Dialer) Callback:
- Uses DEFAULT Airtel callback body (no custom config needed)
- CDR callbacks sent to this same /voice-cdr-webhook endpoint
- callType will be "OUTBOUND" for OBD campaign calls

CDR Fields Reference (Airtel Documentation):
- vmSessionId: Application generated unique session ID
- clientCorrelationId: Xchange ID for searching CDR logs
- callType: INBOUND or OUTBOUND
- overallCallStatus: Answered, Missed, Disconnected, Busy
- Duration fields in milliseconds
- Recording URL for call playback
"""

import os
import json
import logging
import boto3
import uuid
import time
import urllib.request
from typing import Dict, Any, Optional
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)

# Environment variables
VOICE_CDR_TABLE = os.environ.get('VOICE_CDR_TABLE', 'base-wecare-digital-VoiceCDRTable')
S3_BUCKET = 'auth.wecare.digital'
S3_RECORDING_PREFIX = 'voice/voice-in/cdr/'

# Configuration
INBOUND_NUMBER = '+919319767034'
INBOUND_EMAIL = 'voice@wecare.digital'
TTL_DAYS = 90  # CDR retention period


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process Airtel Voice CDR webhook events and list CDRs."""
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    
    logger.info(json.dumps({
        'event': 'voice_cdr_handler',
        'requestId': request_id,
        'inboundNumber': INBOUND_NUMBER
    }))
    
    try:
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', ''))
        path = event.get('rawPath', event.get('path', ''))
        query_params = event.get('queryStringParameters') or {}
        
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        # GET - List CDR records
        if http_method == 'GET':
            return _list_cdrs(query_params, request_id)
        
        # DELETE - Delete CDR logs
        if http_method == 'DELETE' or '/delete' in path or '/clear-logs' in path:
            body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            cdr_ids = body.get('cdrIds', [])
            cdr_id = query_params.get('cdrId') or query_params.get('id')
            hard_delete = query_params.get('hard') == 'true' or body.get('hardDelete', False)
            clear_all = body.get('clearAll', False)
            
            if clear_all:
                return _clear_logs(request_id)
            elif cdr_id:
                return _delete_cdr(cdr_id, hard_delete, request_id)
            elif cdr_ids:
                return _delete_cdrs(cdr_ids, hard_delete, request_id)
            return _response(400, {'error': 'cdrId, cdrIds, or clearAll is required'})
        
        # POST - Receive CDR webhook
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        if isinstance(body, str):
            payload = json.loads(body) if body else {}
        else:
            payload = body or {}
        
        # Support clear-logs via POST body action
        if payload.get('clearAll') or payload.get('_action') == 'clear-logs':
            return _clear_logs(request_id)
        
        vm_session_id = payload.get('vmSessionId', '')
        if not vm_session_id:
            return _response(400, {'error': 'Missing vmSessionId'})
        
        logger.info(json.dumps({
            'event': 'cdr_payload_received',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': payload.get('clientCorrelationId', ''),
            'callType': payload.get('callType', ''),
            'overallCallStatus': payload.get('overallCallStatus', ''),
            'requestId': request_id
        }))
        
        cdr_record = _process_cdr(payload, request_id)
        
        # Download and store recording in S3 if available
        if payload.get('recordingURL'):
            s3_key = _store_recording_to_s3(payload['recordingURL'], cdr_record['id'], request_id)
            if s3_key:
                cdr_record['s3RecordingKey'] = s3_key
                cdr_record['s3RecordingUrl'] = f"s3://{S3_BUCKET}/{s3_key}"
        
        _store_cdr_record(cdr_record, request_id)
        
        return _response(200, {
            'status': 'ok',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': payload.get('clientCorrelationId', ''),
            'message': 'CDR received and stored successfully'
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"CDR parse error: {str(e)}")
        return _response(400, {'error': 'Invalid JSON payload'})
    except Exception as e:
        logger.error(f"CDR handler error: {str(e)}")
        return _response(500, {'error': 'Internal server error'})


def _process_cdr(payload: Dict, request_id: str) -> Dict:
    """Process and normalize CDR payload from Airtel."""
    current_time = int(time.time())
    ttl_expiry = current_time + (TTL_DAYS * 24 * 60 * 60)
    
    duration = payload.get('duration', 0)
    from_waiting_time = payload.get('fromWaitingTime', 0)
    conversation_duration = payload.get('conversationDuration', 0)
    billable_duration = payload.get('billableDuration', 0)
    
    return {
        'id': str(uuid.uuid4()),
        'vmSessionId': payload.get('vmSessionId', ''),
        'clientCorrelationId': payload.get('clientCorrelationId', ''),
        'customerId': payload.get('customerId', ''),
        'startTime': payload.get('startTime', 0),
        'endTime': payload.get('endTime', 0),
        'callAnswerTime': payload.get('callAnswerTime', 0),
        'timestamp': payload.get('timestamp', ''),
        'createdAt': current_time,
        'expiresAt': ttl_expiry,
        'durationMs': duration,
        'durationSec': round(duration / 1000, 2) if duration else 0,
        'fromWaitingTimeMs': from_waiting_time,
        'fromWaitingTimeSec': round(from_waiting_time / 1000, 2) if from_waiting_time else 0,
        'conversationDurationMs': conversation_duration,
        'conversationDurationSec': round(conversation_duration / 1000, 2) if conversation_duration else 0,
        'billableDurationMs': billable_duration,
        'billableDurationSec': round(billable_duration / 1000, 2) if billable_duration else 0,
        'callType': payload.get('callType', 'UNKNOWN'),
        'overallCallStatus': payload.get('overallCallStatus', ''),
        'hangupStatus': payload.get('hangUpStatus', ''),
        'hangupCause': payload.get('hangupCause', ''),
        'callerId': payload.get('callerId', ''),
        'callerNumber': payload.get('callerNumber', ''),
        'destinationNumber': payload.get('destinationNumber', ''),
        'calledNumber': payload.get('calledNumber', ''),
        'displayCliDestination': payload.get('displayCliDestination', ''),
        'callerNumberStatus': payload.get('callerNumberStatus', ''),
        'callerNumberStatusDetails': payload.get('callerNumberStatusDetails', ''),
        'destinationNumberStatus': payload.get('destinationNumberStatus', ''),
        'destinationNumberStatusDetails': payload.get('destinationNumberStatusDetails', ''),
        'circleNameCaller': payload.get('circleNameCaller', ''),
        'circleNameDestination': payload.get('circleNameDestination', ''),
        'operatorNameCaller': payload.get('operatorNameCaller', ''),
        'operatorNameDestination': payload.get('operatorNameDestination', ''),
        'recordingURL': payload.get('recordingURL', ''),
        'retryCountCaller': payload.get('retryCountCaller', 0),
        'retryCountDestination': payload.get('retryCountDestination', 0),
        'participantsCount': len(payload.get('participants', [])),
        'source': 'airtel_cdr_webhook',
        'inboundNumber': INBOUND_NUMBER,
    }


def _store_cdr_record(record: Dict, request_id: str) -> None:
    """Store CDR record in DynamoDB."""
    try:
        item = {}
        for key, value in record.items():
            if value is None or value == '':
                continue
            if isinstance(value, (float, int)):
                item[key] = Decimal(str(value))
            else:
                item[key] = value
        
        table = dynamodb.Table(VOICE_CDR_TABLE)
        table.put_item(Item=item)
        
        logger.info(json.dumps({
            'event': 'cdr_record_stored',
            'id': record.get('id', ''),
            'vmSessionId': record.get('vmSessionId', ''),
            'requestId': request_id
        }))
    except Exception as e:
        logger.error(f"CDR store error: {str(e)}")
        raise


def _list_cdrs(params: Dict, request_id: str) -> Dict[str, Any]:
    """List CDR records with optional filters. Supports both inbound and outbound CDRs."""
    try:
        table = dynamodb.Table(VOICE_CDR_TABLE)
        from boto3.dynamodb.conditions import Attr
        
        scan_kwargs = {'Limit': int(params.get('limit', 200) if params else 200)}
        filter_expressions = []
        
        if params:
            if params.get('callType'):
                filter_expressions.append(Attr('callType').eq(params['callType']))
            if params.get('direction'):
                # direction maps to callType: INBOUND or OUTBOUND
                filter_expressions.append(Attr('callType').eq(params['direction'].upper()))
            if params.get('overallCallStatus'):
                filter_expressions.append(Attr('overallCallStatus').eq(params['overallCallStatus']))
            if params.get('callerNumber'):
                filter_expressions.append(Attr('callerNumber').contains(params['callerNumber']))
            if params.get('destinationNumber'):
                filter_expressions.append(Attr('destinationNumber').contains(params['destinationNumber']))
            if params.get('source'):
                filter_expressions.append(Attr('source').eq(params['source']))
        
        if filter_expressions:
            combined = filter_expressions[0]
            for expr in filter_expressions[1:]:
                combined = combined & expr
            scan_kwargs['FilterExpression'] = combined
        
        result = table.scan(**scan_kwargs)
        cdrs = result.get('Items', [])
        cdrs.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        
        return _response(200, {
            'cdrs': [_normalize_cdr(c) for c in cdrs],
            'count': len(cdrs)
        })
    except Exception as e:
        logger.error(f"List CDRs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _normalize_cdr(item: Dict) -> Dict:
    """Normalize CDR record for API response."""
    call_type = item.get('callType', '')
    return {
        'id': item.get('id', ''),
        'vmSessionId': item.get('vmSessionId', ''),
        'clientCorrelationId': item.get('clientCorrelationId', ''),
        'callType': call_type,
        'direction': call_type,  # INBOUND or OUTBOUND - same as callType
        'overallCallStatus': item.get('overallCallStatus', ''),
        'callerNumber': item.get('callerNumber', ''),
        'destinationNumber': item.get('destinationNumber', ''),
        'calledNumber': item.get('calledNumber', ''),
        'callerId': item.get('callerId', ''),
        'durationSec': float(item.get('durationSec', 0)),
        'conversationDurationSec': float(item.get('conversationDurationSec', 0)),
        'billableDurationSec': float(item.get('billableDurationSec', 0)),
        'fromWaitingTimeSec': float(item.get('fromWaitingTimeSec', 0)),
        'hangupStatus': item.get('hangupStatus', ''),
        'hangupCause': item.get('hangupCause', ''),
        'callerNumberStatus': item.get('callerNumberStatus', ''),
        'destinationNumberStatus': item.get('destinationNumberStatus', ''),
        'circleNameCaller': item.get('circleNameCaller', ''),
        'circleNameDestination': item.get('circleNameDestination', ''),
        'operatorNameCaller': item.get('operatorNameCaller', ''),
        'operatorNameDestination': item.get('operatorNameDestination', ''),
        'recordingURL': item.get('recordingURL', ''),
        's3RecordingUrl': item.get('s3RecordingUrl', ''),
        'source': item.get('source', 'airtel_cdr_webhook'),
        'timestamp': item.get('timestamp', ''),
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _store_recording_to_s3(recording_url: str, cdr_id: str, request_id: str) -> Optional[str]:
    """Download recording from Airtel and store in S3."""
    try:
        if not recording_url:
            return None
        
        # Download recording
        req = urllib.request.Request(recording_url)
        with urllib.request.urlopen(req, timeout=60) as response:
            audio_data = response.read()
        
        # Store in S3
        timestamp = int(time.time())
        s3_key = f"{S3_RECORDING_PREFIX}{timestamp}_{cdr_id}.wav"
        
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=audio_data,
            ContentType='audio/wav'
        )
        
        logger.info(json.dumps({
            'event': 'recording_stored_s3',
            'cdrId': cdr_id,
            's3Key': s3_key,
            'requestId': request_id
        }))
        
        return s3_key
    except Exception as e:
        logger.error(f"Store recording error: {str(e)}")
        return None


def _delete_cdr(cdr_id: str, hard_delete: bool, request_id: str) -> Dict[str, Any]:
    """Delete a single CDR record."""
    try:
        table = dynamodb.Table(VOICE_CDR_TABLE)
        
        if hard_delete:
            # Also delete recording from S3 if exists
            try:
                result = table.get_item(Key={'id': cdr_id})
                cdr = result.get('Item')
                if cdr and cdr.get('s3RecordingKey'):
                    s3.delete_object(Bucket=S3_BUCKET, Key=cdr['s3RecordingKey'])
            except Exception as e:
                logger.warning(f"Failed to delete S3 recording: {str(e)}")
            
            table.delete_item(Key={'id': cdr_id})
            return _response(200, {'success': True, 'deleted': cdr_id, 'type': 'hard'})
        else:
            now = int(time.time())
            table.update_item(
                Key={'id': cdr_id},
                UpdateExpression='SET #status = :status, deletedAt = :deletedAt',
                ExpressionAttributeNames={'#status': 'overallCallStatus'},
                ExpressionAttributeValues={
                    ':status': 'DELETED',
                    ':deletedAt': Decimal(str(now))
                }
            )
            return _response(200, {'success': True, 'deleted': cdr_id, 'type': 'soft'})
    except Exception as e:
        logger.error(f"Delete CDR error: {str(e)}")
        return _response(500, {'error': str(e)})


def _delete_cdrs(cdr_ids: list, hard_delete: bool, request_id: str) -> Dict[str, Any]:
    """Delete multiple CDR records."""
    deleted_count = 0
    for cdr_id in cdr_ids:
        try:
            result = _delete_cdr(cdr_id, hard_delete, request_id)
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
    """Clear all CDR logs."""
    try:
        table = dynamodb.Table(VOICE_CDR_TABLE)
        deleted_count = 0
        
        # Scan and delete all CDRs
        result = table.scan(ProjectionExpression='id,s3RecordingKey')
        for item in result.get('Items', []):
            # Delete S3 recording if exists
            if item.get('s3RecordingKey'):
                try:
                    s3.delete_object(Bucket=S3_BUCKET, Key=item['s3RecordingKey'])
                except Exception:
                    pass
            
            table.delete_item(Key={'id': item['id']})
            deleted_count += 1
        
        return _response(200, {
            'success': True,
            'deletedCount': deleted_count,
            'message': f'Cleared {deleted_count} CDR logs'
        })
    except Exception as e:
        logger.error(f"Clear logs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key',
            'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
