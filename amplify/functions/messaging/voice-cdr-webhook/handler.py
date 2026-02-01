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
    """
    Process Airtel Voice CDR webhook events.
    
    Airtel sends CDR data via POST request with JSON payload containing:
    - Session and correlation IDs
    - Call timing and duration
    - Participant details
    - Status and hangup information
    - Recording URL
    """
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    
    logger.info(json.dumps({
        'event': 'voice_cdr_webhook_received',
        'requestId': request_id,
        'inboundNumber': INBOUND_NUMBER
    }))
    
    try:
        # Handle OPTIONS for CORS preflight
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', ''))
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        # Get headers and body
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        # Log incoming request details
        logger.info(json.dumps({
            'event': 'cdr_request_details',
            'contentType': headers.get('content-type', headers.get('Content-Type', '')),
            'bodyLength': len(body) if body else 0,
            'requestId': request_id
        }))
        
        # Parse webhook payload
        if isinstance(body, str):
            payload = json.loads(body) if body else {}
        else:
            payload = body or {}
        
        # Validate required fields
        vm_session_id = payload.get('vmSessionId', '')
        if not vm_session_id:
            logger.warning(json.dumps({
                'event': 'cdr_missing_session_id',
                'requestId': request_id
            }))
            return _response(400, {'error': 'Missing vmSessionId'})
        
        logger.info(json.dumps({
            'event': 'cdr_payload_received',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': payload.get('clientCorrelationId', ''),
            'callType': payload.get('callType', ''),
            'overallCallStatus': payload.get('overallCallStatus', ''),
            'requestId': request_id
        }))
        
        # Process and store CDR record
        cdr_record = _process_cdr(payload, request_id)
        _store_cdr_record(cdr_record, request_id)
        
        return _response(200, {
            'status': 'ok',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': payload.get('clientCorrelationId', ''),
            'message': 'CDR received and stored successfully'
        })
        
    except json.JSONDecodeError as e:
        logger.error(json.dumps({
            'event': 'cdr_parse_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(400, {'error': 'Invalid JSON payload'})
    except Exception as e:
        logger.error(json.dumps({
            'event': 'cdr_webhook_error',
            'error': str(e),
            'errorType': type(e).__name__,
            'requestId': request_id
        }))
        return _response(500, {'error': 'Internal server error'})


def _process_cdr(payload: Dict, request_id: str) -> Dict:
    """
    Process and normalize CDR payload from Airtel.
    
    Maps Airtel CDR fields to our DynamoDB schema.
    Converts durations from milliseconds to seconds for display.
    """
    current_time = int(time.time())
    ttl_expiry = current_time + (TTL_DAYS * 24 * 60 * 60)
    
    # Extract main identifiers
    vm_session_id = payload.get('vmSessionId', '')
    client_correlation_id = payload.get('clientCorrelationId', '')
    customer_id = payload.get('customerId', '')
    
    # Timestamps (Airtel sends epoch in milliseconds)
    start_time = payload.get('startTime', 0)
    end_time = payload.get('endTime', 0)
    call_answer_time = payload.get('callAnswerTime', 0)
    
    # Duration fields (in milliseconds)
    duration = payload.get('duration', 0)
    from_waiting_time = payload.get('fromWaitingTime', 0)
    conversation_duration = payload.get('conversationDuration', 0)
    billable_duration = payload.get('billableDuration', 0)
    
    # Call details
    call_type = payload.get('callType', 'UNKNOWN')
    overall_call_status = payload.get('overallCallStatus', '')
    hangup_status = payload.get('hangUpStatus', '')
    hangup_cause = payload.get('hangupCause', '')
    
    # Phone numbers
    caller_id = payload.get('callerId', '')
    caller_number = payload.get('callerNumber', '')
    destination_number = payload.get('destinationNumber', '')
    called_number = payload.get('calledNumber', '')
    display_cli_destination = payload.get('displayCliDestination', '')
    
    # Status details
    caller_number_status = payload.get('callerNumberStatus', '')
    caller_number_status_details = payload.get('callerNumberStatusDetails', '')
    destination_number_status = payload.get('destinationNumberStatus', '')
    destination_number_status_details = payload.get('destinationNumberStatusDetails', '')
    
    # Circle and operator info
    circle_name_caller = payload.get('circleNameCaller', '')
    circle_name_destination = payload.get('circleNameDestination', '')
    operator_name_caller = payload.get('operatorNameCaller', '')
    operator_name_destination = payload.get('operatorNameDestination', '')
    
    # Recording
    recording_url = payload.get('recordingURL', '')
    
    # Retry counts
    retry_count_caller = payload.get('retryCountCaller', 0)
    retry_count_destination = payload.get('retryCountDestination', 0)
    
    # Participants
    participants = payload.get('participants', [])
    
    # Timestamp from Airtel
    timestamp = payload.get('timestamp', '')
    
    # Build normalized record
    cdr_record = {
        'id': str(uuid.uuid4()),
        'vmSessionId': vm_session_id,
        'clientCorrelationId': client_correlation_id,
        'customerId': customer_id,
        
        # Timestamps
        'startTime': start_time,
        'endTime': end_time,
        'callAnswerTime': call_answer_time,
        'timestamp': timestamp,
        'createdAt': current_time,
        'expiresAt': ttl_expiry,
        
        # Duration (store both ms and seconds)
        'durationMs': duration,
        'durationSec': round(duration / 1000, 2) if duration else 0,
        'fromWaitingTimeMs': from_waiting_time,
        'fromWaitingTimeSec': round(from_waiting_time / 1000, 2) if from_waiting_time else 0,
        'conversationDurationMs': conversation_duration,
        'conversationDurationSec': round(conversation_duration / 1000, 2) if conversation_duration else 0,
        'billableDurationMs': billable_duration,
        'billableDurationSec': round(billable_duration / 1000, 2) if billable_duration else 0,
        
        # Call details
        'callType': call_type,
        'overallCallStatus': overall_call_status,
        'hangupStatus': hangup_status,
        'hangupCause': hangup_cause,
        
        # Phone numbers
        'callerId': caller_id,
        'callerNumber': caller_number,
        'destinationNumber': destination_number,
        'calledNumber': called_number,
        'displayCliDestination': display_cli_destination,
        
        # Status
        'callerNumberStatus': caller_number_status,
        'callerNumberStatusDetails': caller_number_status_details,
        'destinationNumberStatus': destination_number_status,
        'destinationNumberStatusDetails': destination_number_status_details,
        
        # Location info
        'circleNameCaller': circle_name_caller,
        'circleNameDestination': circle_name_destination,
        'operatorNameCaller': operator_name_caller,
        'operatorNameDestination': operator_name_destination,
        
        # Recording
        'recordingURL': recording_url,
        
        # Retry info
        'retryCountCaller': retry_count_caller,
        'retryCountDestination': retry_count_destination,
        
        # Participants count
        'participantsCount': len(participants),
        
        # Source tracking
        'source': 'airtel_cdr_webhook',
        'inboundNumber': INBOUND_NUMBER,
    }
    
    return cdr_record


def _store_cdr_record(record: Dict, request_id: str) -> None:
    """Store CDR record in DynamoDB with proper type conversion."""
    try:
        # Convert numeric values to Decimal for DynamoDB
        item = {}
        for key, value in record.items():
            if value is None or value == '':
                continue
            if isinstance(value, float):
                item[key] = Decimal(str(value))
            elif isinstance(value, int):
                item[key] = Decimal(str(value))
            else:
                item[key] = value
        
        table = dynamodb.Table(VOICE_CDR_TABLE)
        table.put_item(Item=item)
        
        logger.info(json.dumps({
            'event': 'cdr_record_stored',
            'id': record.get('id', ''),
            'vmSessionId': record.get('vmSessionId', ''),
            'callType': record.get('callType', ''),
            'overallCallStatus': record.get('overallCallStatus', ''),
            'callerNumber': record.get('callerNumber', ''),
            'destinationNumber': record.get('destinationNumber', ''),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'cdr_store_error',
            'vmSessionId': record.get('vmSessionId', ''),
            'error': str(e),
            'errorType': type(e).__name__,
            'requestId': request_id
        }))
        raise


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key',
            'Access-Control-Allow-Methods': 'POST,OPTIONS'
        },
        'body': json.dumps(body)
    }
