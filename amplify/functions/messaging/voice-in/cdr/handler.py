"""
Airtel Voice CDR Webhook Handler Lambda Function

Purpose: Receive and store Call Detail Records (CDR) from Airtel Cloud Communication Platform

Webhook Configuration:
- URL: POST /voice-cdr-webhook
- Inbound Number: +91 9319767034
- Email: voice@wecare.digital

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
from typing import Dict, Any, Optional
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
VOICE_CDR_TABLE = os.environ.get('VOICE_CDR_TABLE', 'base-wecare-digital-VoiceCDRTable')

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
        
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        # GET - List CDR records
        if http_method == 'GET':
            return _list_cdrs(event.get('queryStringParameters', {}), request_id)
        
        # POST - Receive CDR webhook
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        if isinstance(body, str):
            payload = json.loads(body) if body else {}
        else:
            payload = body or {}
        
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
    """List CDR records with optional filters."""
    try:
        table = dynamodb.Table(VOICE_CDR_TABLE)
        from boto3.dynamodb.conditions import Attr
        
        scan_kwargs = {'Limit': int(params.get('limit', 100) if params else 100)}
        filter_expressions = []
        
        if params:
            if params.get('callType'):
                filter_expressions.append(Attr('callType').eq(params['callType']))
            if params.get('overallCallStatus'):
                filter_expressions.append(Attr('overallCallStatus').eq(params['overallCallStatus']))
            if params.get('callerNumber'):
                filter_expressions.append(Attr('callerNumber').contains(params['callerNumber']))
            if params.get('destinationNumber'):
                filter_expressions.append(Attr('destinationNumber').contains(params['destinationNumber']))
        
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
    return {
        'id': item.get('id', ''),
        'vmSessionId': item.get('vmSessionId', ''),
        'clientCorrelationId': item.get('clientCorrelationId', ''),
        'callType': item.get('callType', ''),
        'overallCallStatus': item.get('overallCallStatus', ''),
        'callerNumber': item.get('callerNumber', ''),
        'destinationNumber': item.get('destinationNumber', ''),
        'callerId': item.get('callerId', ''),
        'durationSec': float(item.get('durationSec', 0)),
        'conversationDurationSec': float(item.get('conversationDurationSec', 0)),
        'billableDurationSec': float(item.get('billableDurationSec', 0)),
        'hangupStatus': item.get('hangupStatus', ''),
        'hangupCause': item.get('hangupCause', ''),
        'callerNumberStatus': item.get('callerNumberStatus', ''),
        'destinationNumberStatus': item.get('destinationNumberStatus', ''),
        'circleNameCaller': item.get('circleNameCaller', ''),
        'circleNameDestination': item.get('circleNameDestination', ''),
        'operatorNameCaller': item.get('operatorNameCaller', ''),
        'operatorNameDestination': item.get('operatorNameDestination', ''),
        'recordingURL': item.get('recordingURL', ''),
        'timestamp': item.get('timestamp', ''),
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
