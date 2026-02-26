"""
Airtel Voice CDR Webhook Handler Lambda Function

Purpose: Receive and store Call Detail Records (CDR) from Airtel Cloud Communication Platform
         Handles BOTH inbound and outbound call CDRs (C2C, OBD, direct inbound)

Webhook Configuration:
- URL: POST /voice-cdr-webhook
- Full URL: https://api.wecare.digital/voice-cdr-webhook
- Inbound Number: +91 9319767034
- Email: voice@wecare.digital

Recording Storage: s3://app.wecare.digital/voice/voice-in/cdr/

Airtel IP Whitelist (if 403 errors):
- 125.19.17.212
- 125.17.6.54
- 122.187.47.153

NOTE: We do NOT need to whitelist IPs for sending SMS traffic.
      The above IPs only need whitelisting if receiving 403 errors on API calls.

Airtel CDR Callback comes in TWO formats:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORMAT A (Standard camelCase - Inbound/C2C):
{
  "vmSessionId": "...", "clientCorrelationId": "...",
  "callType": "INBOUND", "overallCallStatus": "Answered",
  "callerNumber": "9876543210", "destinationNumber": "9123456789",
  "duration": 45000, "conversationDuration": 40000, ...
}

FORMAT B (Display/Custom CDR - OBD campaigns):
{
  "Session_ID": "...", "Client_Correlation_Id": "...",
  "Call_Type": "OUTBOUND", "Overall_Call_Status": "Answered",
  "Caller_Number": "8130078559", "Destination_Number": null,
  "duration": 31556, "conversationDuration": 24189,
  "Campaign_Id": "698af5ddb799f448d9d091c0", "Campaign_Name": "Test",
  "Date": "10/02/2026", "Time": "14:40:07",
  "Caller_Status": "Disconnected", "Destination_Status": "Disconnected",
  "Caller_Circle_Name": "Delhi", "Caller_Operator_Name": "Bharti Airtel (GSM)",
  "Caller_Duration": "00:31", "Conversation_Duration": "00:00:24",
  "Caller_Waiting_Time": "00:00:07", "Billable_Duration": "00:24",
  "participants": [...], ...
}

Both formats are accepted and normalized into the same VoiceCDR table schema.
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
from lambda_utils.logging import get_logger
from lambda_utils.response import cors_headers, extract_origin

logger = get_logger(__name__)

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)

# Environment variables
VOICE_CDR_TABLE = os.environ.get('VOICE_CDR_TABLE', 'base-wecare-digital-VoiceCDRTable')
S3_BUCKET = 'app.wecare.digital'
S3_RECORDING_PREFIX = 'voice/voice-in/cdr/'

# Configuration
INBOUND_NUMBER = '+919319767034'
INBOUND_EMAIL = 'voice@wecare.digital'
TTL_DAYS = 90  # CDR retention period


def _is_airtel_cdr_payload(payload: Dict) -> bool:
    """
    Detect if a POST payload is an Airtel CDR callback (vs a user API request).

    Airtel CDR payloads contain distinctive fields that user requests never have.
    Checks both Format A (camelCase) and Format B (Display_Format) field names.
    """
    # Format A (standard camelCase)
    if payload.get('vmSessionId') or payload.get('clientCorrelationId'):
        return True
    # Format B (OBD display format)
    if payload.get('Session_ID') or payload.get('Client_Correlation_Id'):
        return True
    # Either format may have these
    if payload.get('overallCallStatus') or payload.get('Overall_Call_Status'):
        return True
    if payload.get('participants') and isinstance(payload.get('participants'), list):
        # Has participants array with participantType — definitely a CDR
        for p in payload['participants']:
            if isinstance(p, dict) and p.get('participantType'):
                return True
    return False


def _normalize_airtel_payload(payload: Dict) -> Dict:
    """
    Normalize Airtel CDR payload from either Format A (camelCase) or Format B
    (Display_Format with underscores) into a consistent camelCase format.

    Format B fields (OBD CDR) → Format A equivalents:
    - Session_ID → vmSessionId
    - Client_Correlation_Id → clientCorrelationId
    - Overall_Call_Status → overallCallStatus
    - Caller_Number → callerNumber
    - Destination_Number → destinationNumber
    - Caller_ID → callerId
    - Call_Type → callType
    - Caller_Status → callerNumberStatus
    - Destination_Status → destinationNumberStatus
    - Caller_Circle_Name → circleNameCaller
    - Destination_Circle_Name → circleNameDestination
    - Caller_Operator_Name → operatorNameCaller
    - Destination_Operator_Name → operatorNameDestination
    - Hangup_Cause → hangupCause
    - Caller_Retry_Count → retryCountCaller
    - Destination_Retry_Count → retryCountDestination
    - Caller_Name → callerName
    - Destination_Name → destinationName
    - Campaign_Id → campaignId
    - Campaign_Name → campaignName
    - Recording → recordingURL
    - Customer_Name → customerId
    - Caller_Status_Detail → callerNumberStatusDetails
    - Destination_Status_Detail → destinationNumberStatusDetails
    """
    # Start with the original payload (Format A fields pass through)
    normalized = dict(payload)

    # Map Format B → Format A (only if Format A key is missing/empty)
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
        'Caller_Retry_Count': 'retryCountCaller',
        'Destination_Retry_Count': 'retryCountDestination',
        'Caller_Name': 'callerName',
        'Destination_Name': 'destinationName',
        'Campaign_Id': 'campaignId',
        'Campaign_Name': 'campaignName',
        'Recording': 'recordingURL',
        'Customer_Name': 'customerId',
        'Caller_Status_Detail': 'callerNumberStatusDetails',
        'Destination_Status_Detail': 'destinationNumberStatusDetails',
        'Destination_CLI': 'displayCliDestination',
        'DTMF_Capture': 'dtmfCapture',
        'Missed_Destination_Number': 'missedDestinationNumber',
        'Pulse_Count': 'pulseCount',
    }

    for display_key, camel_key in field_map.items():
        if payload.get(display_key) is not None and not normalized.get(camel_key):
            val = payload[display_key]
            # Clean up quoted empty strings like '""'
            if isinstance(val, str) and val.strip() in ('""', "''", ''):
                val = ''
            normalized[camel_key] = val

    # Handle callType from either field
    if not normalized.get('callType'):
        normalized['callType'] = payload.get('Call_Type', payload.get('callType', 'UNKNOWN'))

    # Handle customerId from Customer_Name
    if not normalized.get('customerId'):
        normalized['customerId'] = payload.get('Customer_Name', payload.get('customerId', ''))

    return normalized


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process Airtel Voice CDR webhook events and list CDRs."""
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    origin = extract_origin(event)
    
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
        
        # Normalize Airtel CDR payload (handles both Format A and Format B)
        payload = _normalize_airtel_payload(payload)
        
        vm_session_id = payload.get('vmSessionId', '')
        client_correlation_id = payload.get('clientCorrelationId', '')
        
        # Accept CDR if it has any identifying field (vmSessionId, clientCorrelationId, or participants)
        if not vm_session_id and not client_correlation_id and not payload.get('participants'):
            return _response(400, {'error': 'Missing vmSessionId or clientCorrelationId or participants'})
        
        logger.info(json.dumps({
            'event': 'cdr_payload_received',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': client_correlation_id,
            'callType': payload.get('callType', ''),
            'overallCallStatus': payload.get('overallCallStatus', ''),
            'campaignId': payload.get('campaignId', ''),
            'source': 'voice-cdr-webhook',
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
            'clientCorrelationId': client_correlation_id,
            'message': 'CDR received and stored successfully'
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"CDR parse error: {str(e)}")
        return _response(400, {'error': 'Invalid JSON payload'})
    except Exception as e:
        logger.error(f"CDR handler error: {str(e)}")
        return _response(500, {'error': 'Internal server error'})



def _safe_int(val) -> int:
    """Safely convert a value to int. Handles None, strings like '00:24', and numeric types."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        # Try direct numeric parse first
        try:
            return int(float(val))
        except (ValueError, TypeError):
            pass
        # If it's a mm:ss or hh:mm:ss display string, skip (not convertible to ms)
        return 0
    return 0


def _process_cdr(payload: Dict, request_id: str) -> Dict:
    """
    Process and normalize CDR payload from Airtel Cloud Communication Platform.

    Parses all fields per Airtel CDR spec including:
    - Session & correlation IDs
    - All duration fields (ms + sec conversion)
    - Participant details (From/To with status, hangup cause, retry count)
    - Events array (call lifecycle events with SIP/cause codes)
    - Overall call status derivation per Airtel spec matrix
    - Circle/operator info, recording URL, billable duration
    """
    current_time = int(time.time())
    ttl_expiry = current_time + (TTL_DAYS * 24 * 60 * 60)

    # Duration fields (all in milliseconds from Airtel)
    # Note: In Format B (OBD), some duration fields come as display strings like "00:24"
    # but 'duration', 'conversationDuration', 'fromWaitingTime' are still in ms
    duration = _safe_int(payload.get('duration', 0))
    from_waiting_time = _safe_int(payload.get('fromWaitingTime', 0))
    conversation_duration = _safe_int(payload.get('conversationDuration', 0))
    billable_duration = _safe_int(payload.get('billableDuration', 0))
    caller_duration = _safe_int(payload.get('callerDuration', 0))
    call_setup_time_caller = _safe_int(payload.get('callSetupTimeCaller', 0))

    # Parse participants array for caller/destination details
    participants = payload.get('participants', [])
    caller_name = ''
    destination_name = ''
    caller_participant = {}
    destination_participant = {}

    for p in participants:
        p_type = p.get('participantType', '')
        if p_type == 'From':
            caller_participant = p
            caller_name = p.get('participantName', '') or payload.get('callerName', '')
        elif p_type == 'To':
            destination_participant = p
            destination_name = p.get('participantName', '') or payload.get('destinationName', '')

    # Derive overall call status per Airtel spec matrix:
    # Caller=Answer + Dest=Answered -> Answered
    # Caller=Answer + Dest=Busy -> Missed
    # Caller=Answer + Dest=Missed -> Missed
    # Caller=Busy -> Missed
    # Caller=Missed -> Missed
    overall_status = payload.get('overallCallStatus', '')
    caller_status = payload.get('callerNumberStatus', '') or caller_participant.get('status', '')
    dest_status = payload.get('destinationNumberStatus', '') or destination_participant.get('status', '')

    if not overall_status and caller_status and dest_status:
        overall_status = _derive_overall_status(caller_status, dest_status)

    # Serialize participants and events for storage
    participants_json = ''
    events_json = ''
    try:
        if participants:
            participants_json = json.dumps(participants)
        events = payload.get('events', [])
        if events:
            events_json = json.dumps(events)
    except (TypeError, ValueError):
        pass

    return {
        'id': str(uuid.uuid4()),
        'vmSessionId': payload.get('vmSessionId', ''),
        'clientCorrelationId': payload.get('clientCorrelationId', ''),
        'customerId': payload.get('customerId', ''),

        # Timestamps
        'startTime': payload.get('startTime', 0),
        'endTime': payload.get('endTime', 0),
        'callAnswerTime': payload.get('callAnswerTime', 0),
        'timestamp': payload.get('timestamp', ''),
        'createdAt': current_time,
        'expiresAt': ttl_expiry,

        # Duration fields (ms + sec)
        'durationMs': duration,
        'durationSec': round(duration / 1000, 2) if duration else 0,
        'fromWaitingTimeMs': from_waiting_time,
        'fromWaitingTimeSec': round(from_waiting_time / 1000, 2) if from_waiting_time else 0,
        'conversationDurationMs': conversation_duration,
        'conversationDurationSec': round(conversation_duration / 1000, 2) if conversation_duration else 0,
        'billableDurationMs': billable_duration,
        'billableDurationSec': round(billable_duration / 1000, 2) if billable_duration else 0,
        'callerDuration': caller_duration,
        'callerDurationSec': round(caller_duration / 1000, 2) if caller_duration else 0,
        'callSetupTimeCaller': call_setup_time_caller,

        # Call details
        'callType': payload.get('callType', 'UNKNOWN'),
        'overallCallStatus': overall_status,
        'derivedOverallStatus': _derive_overall_status(caller_status, dest_status) if caller_status and dest_status else '',
        'hangupStatus': payload.get('hangUpStatus', ''),
        'hangupCause': payload.get('hangupCause', ''),

        # Phone numbers
        'callerId': payload.get('callerId', ''),
        'callerNumber': payload.get('callerNumber', ''),
        'destinationNumber': payload.get('destinationNumber', ''),
        'calledNumber': payload.get('calledNumber', ''),
        'displayCliDestination': payload.get('displayCliDestination', ''),

        # Caller/Destination names
        'callerName': caller_name,
        'destinationName': destination_name,

        # Status details
        'callerNumberStatus': caller_status,
        'callerNumberStatusDetails': payload.get('callerNumberStatusDetails', ''),
        'destinationNumberStatus': dest_status,
        'destinationNumberStatusDetails': payload.get('destinationNumberStatusDetails', ''),

        # Circle and operator info
        'circleNameCaller': payload.get('circleNameCaller', ''),
        'circleNameDestination': payload.get('circleNameDestination', ''),
        'operatorNameCaller': payload.get('operatorNameCaller', ''),
        'operatorNameDestination': payload.get('operatorNameDestination', ''),

        # Recording
        'recordingURL': payload.get('recordingURL', ''),

        # Retry info
        'retryCountCaller': payload.get('retryCountCaller', 0) or (caller_participant.get('retryCount', 0)),
        'retryCountDestination': payload.get('retryCountDestination', 0) or (destination_participant.get('retryCount', 0)),

        # Participants & Events (JSON strings)
        'participantsJson': participants_json,
        'eventsJson': events_json,
        'participantsCount': len(participants),

        # Metadata
        'source': 'airtel_cdr_webhook',
        'inboundNumber': INBOUND_NUMBER,

        # OBD Campaign fields (Format B only)
        'campaignId': payload.get('campaignId', ''),
        'campaignName': payload.get('campaignName', payload.get('Campaign_Name', '')),
        'pulseCount': _safe_int(payload.get('pulseCount', 0)),
        'dtmfCapture': payload.get('dtmfCapture', ''),
    }


def _derive_overall_status(caller_status: str, dest_status: str) -> str:
    """
    Derive overall call status per Airtel CDR spec matrix:
    
    Caller=Answer + Dest=Answered -> Answered
    Caller=Answer + Dest=Busy    -> Missed
    Caller=Answer + Dest=Missed  -> Missed
    Caller=Busy                  -> Missed
    Caller=Missed                -> Missed
    """
    caller_norm = caller_status.strip().lower() if caller_status else ''
    dest_norm = dest_status.strip().lower() if dest_status else ''
    
    # Map various status strings to normalized forms
    answered_statuses = {'answer', 'answered', 'disconnected'}
    missed_statuses = {'missed', 'noanswer', 'notreachable', 'removed', 'networkerror'}
    busy_statuses = {'busy'}
    
    if caller_norm in answered_statuses and dest_norm in answered_statuses:
        return 'Answered'
    if caller_norm in answered_statuses and dest_norm in busy_statuses:
        return 'Missed'
    if caller_norm in answered_statuses and dest_norm in missed_statuses:
        return 'Missed'
    if caller_norm in busy_statuses:
        return 'Missed'
    if caller_norm in missed_statuses:
        return 'Missed'
    
    # Fallback: if destination answered, call is answered
    if dest_norm in answered_statuses:
        return 'Answered'
    
    return 'Missed'


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
    """
    List CDR records with optional filters per Airtel CDR spec.
    
    Supports filters: callType, direction, overallCallStatus, callerNumber,
    destinationNumber, hangupStatus, callerNumberStatus, destinationNumberStatus,
    circleNameCaller, search (clientCorrelationId/vmSessionId), source, startDate, endDate.
    """
    try:
        table = dynamodb.Table(VOICE_CDR_TABLE)
        from boto3.dynamodb.conditions import Attr
        
        limit = int(params.get('limit', 200) if params else 200)
        scan_kwargs = {'Limit': limit * 2}
        filter_expressions = []
        
        if params:
            if params.get('callType'):
                filter_expressions.append(Attr('callType').eq(params['callType']))
            if params.get('direction'):
                filter_expressions.append(Attr('callType').eq(params['direction'].upper()))
            if params.get('overallCallStatus'):
                filter_expressions.append(Attr('overallCallStatus').eq(params['overallCallStatus']))
            if params.get('callerNumber'):
                filter_expressions.append(Attr('callerNumber').contains(params['callerNumber']))
            if params.get('destinationNumber'):
                filter_expressions.append(Attr('destinationNumber').contains(params['destinationNumber']))
            if params.get('hangupStatus'):
                filter_expressions.append(Attr('hangupStatus').eq(params['hangupStatus']))
            if params.get('callerNumberStatus'):
                filter_expressions.append(Attr('callerNumberStatus').eq(params['callerNumberStatus']))
            if params.get('destinationNumberStatus'):
                filter_expressions.append(Attr('destinationNumberStatus').eq(params['destinationNumberStatus']))
            if params.get('circleNameCaller'):
                filter_expressions.append(Attr('circleNameCaller').eq(params['circleNameCaller']))
            if params.get('source'):
                filter_expressions.append(Attr('source').eq(params['source']))
            if params.get('startDate'):
                filter_expressions.append(Attr('createdAt').gte(int(params['startDate'])))
            if params.get('endDate'):
                filter_expressions.append(Attr('createdAt').lte(int(params['endDate'])))
            if params.get('search'):
                search_val = params['search']
                filter_expressions.append(
                    Attr('clientCorrelationId').contains(search_val) | Attr('vmSessionId').contains(search_val)
                )
        
        if filter_expressions:
            combined = filter_expressions[0]
            for expr in filter_expressions[1:]:
                combined = combined & expr
            scan_kwargs['FilterExpression'] = combined
        
        result = table.scan(**scan_kwargs)
        cdrs = result.get('Items', [])
        
        # Paginate if needed
        while 'LastEvaluatedKey' in result and len(cdrs) < limit:
            scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']
            result = table.scan(**scan_kwargs)
            cdrs.extend(result.get('Items', []))
        
        cdrs.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        cdrs = cdrs[:limit]
        
        return _response(200, {
            'cdrs': [_normalize_cdr(c) for c in cdrs],
            'count': len(cdrs)
        })
    except Exception as e:
        logger.error(f"List CDRs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _ms_to_mmss(ms_val) -> str:
    """Convert milliseconds to mm:ss format for UI display (per Airtel CDR UI spec)."""
    try:
        total_sec = int(float(ms_val)) // 1000 if ms_val else 0
        minutes = total_sec // 60
        seconds = total_sec % 60
        return f"{minutes:02d}:{seconds:02d}"
    except (ValueError, TypeError):
        return "00:00"


def _normalize_cdr(item: Dict) -> Dict:
    """
    Normalize CDR record for API response.
    
    Includes all fields per Airtel CDR spec Section 2 (Standard CDR Field Display in UI):
    - Date (dd/mm/yy), Time (hh:mm:ss)
    - Call_ID (clientCorrelationId)
    - Caller_ID, Caller_Number, Destination_CLI, Destination_Number
    - Caller_Waiting_Time (mm:ss), Conversation_Duration (mm:ss)
    - Overall_Call_Status, Hangup_Cause
    - Caller_Status, Destination_Status
    - Caller_Circle_Name
    - Recording
    """
    call_type = item.get('callType', '')
    
    # Parse timestamp for date/time display (Airtel format: "2020-04-11 06:22:08")
    ts = item.get('timestamp', '')
    display_date = ''
    display_time = ''
    if ts:
        try:
            parts = ts.split(' ')
            if len(parts) >= 2:
                date_parts = parts[0].split('-')
                if len(date_parts) == 3:
                    display_date = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0][2:]}"
                display_time = parts[1]
        except (IndexError, ValueError):
            pass
    
    return {
        'id': item.get('id', ''),
        'vmSessionId': item.get('vmSessionId', ''),
        'clientCorrelationId': item.get('clientCorrelationId', ''),
        'customerId': item.get('customerId', ''),
        'callType': call_type,
        'direction': call_type,
        'overallCallStatus': item.get('overallCallStatus', ''),
        'derivedOverallStatus': item.get('derivedOverallStatus', ''),
        
        # Phone numbers
        'callerId': item.get('callerId', ''),
        'callerNumber': item.get('callerNumber', ''),
        'destinationNumber': item.get('destinationNumber', ''),
        'calledNumber': item.get('calledNumber', ''),
        'displayCliDestination': item.get('displayCliDestination', ''),
        
        # Names
        'callerName': item.get('callerName', ''),
        'destinationName': item.get('destinationName', ''),
        
        # Duration fields (seconds)
        'durationSec': float(item.get('durationSec', 0)),
        'conversationDurationSec': float(item.get('conversationDurationSec', 0)),
        'billableDurationSec': float(item.get('billableDurationSec', 0)),
        'fromWaitingTimeSec': float(item.get('fromWaitingTimeSec', 0)),
        'callerDurationSec': float(item.get('callerDurationSec', 0)),
        
        # Duration fields (mm:ss for UI display per Airtel spec)
        'fromWaitingTimeDisplay': _ms_to_mmss(item.get('fromWaitingTimeMs', 0)),
        'conversationDurationDisplay': _ms_to_mmss(item.get('conversationDurationMs', 0)),
        'billableDurationDisplay': _ms_to_mmss(item.get('billableDurationMs', 0)),
        'callerDurationDisplay': _ms_to_mmss(item.get('callerDuration', 0)),
        
        # Hangup details
        'hangupStatus': item.get('hangupStatus', ''),
        'hangupCause': item.get('hangupCause', ''),
        
        # Caller/Destination status
        'callerNumberStatus': item.get('callerNumberStatus', ''),
        'callerNumberStatusDetails': item.get('callerNumberStatusDetails', ''),
        'destinationNumberStatus': item.get('destinationNumberStatus', ''),
        'destinationNumberStatusDetails': item.get('destinationNumberStatusDetails', ''),
        
        # Circle and operator
        'circleNameCaller': item.get('circleNameCaller', ''),
        'circleNameDestination': item.get('circleNameDestination', ''),
        'operatorNameCaller': item.get('operatorNameCaller', ''),
        'operatorNameDestination': item.get('operatorNameDestination', ''),
        
        # Recording
        'recordingURL': item.get('recordingURL', ''),
        's3RecordingUrl': item.get('s3RecordingUrl', ''),
        's3RecordingKey': item.get('s3RecordingKey', ''),
        
        # Retry info
        'retryCountCaller': int(float(item.get('retryCountCaller', 0))),
        'retryCountDestination': int(float(item.get('retryCountDestination', 0))),
        
        # Metadata
        'source': item.get('source', 'airtel_cdr_webhook'),
        'participantsCount': int(float(item.get('participantsCount', 0))),
        
        # UI display fields (per Airtel CDR spec Section 2)
        'displayDate': display_date,
        'displayTime': display_time,
        'timestamp': ts,
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
    """Clear all CDR logs (handles pagination for large tables)."""
    try:
        table = dynamodb.Table(VOICE_CDR_TABLE)
        deleted_count = 0
        
        # Scan and delete all CDRs with pagination
        scan_kwargs = {'ProjectionExpression': 'id,s3RecordingKey'}
        while True:
            result = table.scan(**scan_kwargs)
            for item in result.get('Items', []):
                if item.get('s3RecordingKey'):
                    try:
                        s3.delete_object(Bucket=S3_BUCKET, Key=item['s3RecordingKey'])
                    except Exception:
                        pass
                table.delete_item(Key={'id': item['id']})
                deleted_count += 1
            
            if 'LastEvaluatedKey' not in result:
                break
            scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']
        
        return _response(200, {
            'success': True,
            'deletedCount': deleted_count,
            'message': f'Cleared {deleted_count} CDR logs'
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
