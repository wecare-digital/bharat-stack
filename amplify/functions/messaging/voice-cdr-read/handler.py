"""
Voice CDR Read Lambda Function

Purpose: Read Airtel Call Detail Records from DynamoDB for dashboard display
         Aligned with Airtel CDR spec Sections 2-6 (UI display, status matrix, dashboard)

Inbound Number: +91 9319767034
Email: voice@wecare.digital

Query Parameters:
- callType: INBOUND or OUTBOUND
- status: Answered, Missed, Busy, Disconnected
- limit: Number of records (default 50, max 200)
- startDate: Filter by date (epoch seconds)
- endDate: Filter by date (epoch seconds)
- callerNumber: Filter by caller phone
- destinationNumber: Filter by destination phone
- hangupStatus: Filter by hangup party (Party A, Party B, SYSTEM_INITIATED)
- callerNumberStatus: Disconnected, NetworkError, NotReachable, Busy, Noanswer, Answer
- destinationNumberStatus: Same as above
- circleNameCaller: Filter by caller circle/state
- search: Search by clientCorrelationId or vmSessionId

Dashboard Stats (per Airtel spec Section 6):
- Call trend (answered vs missed over time)
- Demographic view by circle/state
- Destination number status breakdown
- Avg customer waiting time
- Avg conversation duration
- Call volume by CLI with status mapping
"""

import os
import json
import logging
import boto3
from typing import Dict, Any, List
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from collections import defaultdict

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
VOICE_CDR_TABLE = os.environ.get('VOICE_CDR_TABLE', 'base-wecare-digital-VoiceCDRTable')

# Configuration
INBOUND_NUMBER = '+91 9319767034'
INBOUND_EMAIL = 'voice@wecare.digital'


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj) if obj % 1 else int(obj)
        return super().default(obj)


def _ms_to_mmss(ms_val) -> str:
    """Convert milliseconds to mm:ss format for UI display (per Airtel CDR spec)."""
    try:
        total_sec = int(float(ms_val)) // 1000 if ms_val else 0
        minutes = total_sec // 60
        seconds = total_sec % 60
        return f"{minutes:02d}:{seconds:02d}"
    except (ValueError, TypeError):
        return "00:00"


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Read CDR records with filtering, UI-formatted fields, and dashboard statistics.
    
    Returns:
    - records: List of CDR records with UI display fields
    - count: Number of records returned
    - stats: Aggregated statistics (per Airtel dashboard spec)
    - dashboard: Dashboard-specific aggregations
    - inboundNumber: Configured inbound number
    - email: Contact email
    """
    request_id = context.aws_request_id if context else 'local'
    
    logger.info(json.dumps({
        'event': 'voice_cdr_read_request',
        'requestId': request_id
    }))
    
    try:
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', ''))
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        params = event.get('queryStringParameters') or {}
        call_type = params.get('callType', '')
        status = params.get('status', '')
        limit = min(int(params.get('limit', 50)), 200)
        start_date = params.get('startDate', '')
        end_date = params.get('endDate', '')
        caller_number = params.get('callerNumber', '')
        destination_number = params.get('destinationNumber', '')
        hangup_status = params.get('hangupStatus', '')
        caller_number_status = params.get('callerNumberStatus', '')
        dest_number_status = params.get('destinationNumberStatus', '')
        circle_caller = params.get('circleNameCaller', '')
        search = params.get('search', '')
        include_dashboard = params.get('dashboard', '') == 'true'
        
        logger.info(json.dumps({
            'event': 'cdr_query_params',
            'callType': call_type,
            'status': status,
            'limit': limit,
            'dashboard': include_dashboard,
            'requestId': request_id
        }))
        
        table = dynamodb.Table(VOICE_CDR_TABLE)
        
        # Build scan with filters
        scan_kwargs = {'Limit': limit * 2}
        filter_expressions = []
        expression_values = {}
        
        if call_type:
            filter_expressions.append('callType = :callType')
            expression_values[':callType'] = call_type
        
        if status:
            filter_expressions.append('overallCallStatus = :status')
            expression_values[':status'] = status
        
        if start_date:
            filter_expressions.append('createdAt >= :startDate')
            expression_values[':startDate'] = int(start_date)
        
        if end_date:
            filter_expressions.append('createdAt <= :endDate')
            expression_values[':endDate'] = int(end_date)
        
        if caller_number:
            filter_expressions.append('contains(callerNumber, :callerNumber)')
            expression_values[':callerNumber'] = caller_number
        
        if destination_number:
            filter_expressions.append('contains(destinationNumber, :destNumber)')
            expression_values[':destNumber'] = destination_number
        
        if hangup_status:
            filter_expressions.append('hangupStatus = :hangupStatus')
            expression_values[':hangupStatus'] = hangup_status
        
        if caller_number_status:
            filter_expressions.append('callerNumberStatus = :callerNumStatus')
            expression_values[':callerNumStatus'] = caller_number_status
        
        if dest_number_status:
            filter_expressions.append('destinationNumberStatus = :destNumStatus')
            expression_values[':destNumStatus'] = dest_number_status
        
        if circle_caller:
            filter_expressions.append('circleNameCaller = :circleCaller')
            expression_values[':circleCaller'] = circle_caller
        
        if search:
            filter_expressions.append(
                '(contains(clientCorrelationId, :search) OR contains(vmSessionId, :search))'
            )
            expression_values[':search'] = search
        
        if filter_expressions:
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expressions)
            scan_kwargs['ExpressionAttributeValues'] = expression_values
        
        response = table.scan(**scan_kwargs)
        records = response.get('Items', [])
        
        while 'LastEvaluatedKey' in response and len(records) < limit:
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = table.scan(**scan_kwargs)
            records.extend(response.get('Items', []))
        
        records.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        records = records[:limit]
        
        # Format records for UI display
        formatted_records = [_format_record_for_ui(r) for r in records]
        
        # Calculate statistics
        stats = _calculate_stats(records)
        
        result = {
            'records': formatted_records,
            'count': len(formatted_records),
            'stats': stats,
            'inboundNumber': INBOUND_NUMBER,
            'email': INBOUND_EMAIL
        }
        
        # Include dashboard aggregations if requested
        if include_dashboard:
            result['dashboard'] = _calculate_dashboard(records)
        
        return _response(200, result)
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'voice_cdr_read_error',
            'error': str(e),
            'errorType': type(e).__name__,
            'requestId': request_id
        }))
        return _response(500, {'error': str(e)})


def _format_record_for_ui(item: Dict) -> Dict:
    """
    Format CDR record for UI display per Airtel CDR spec Section 2.
    
    Standard 16 fields:
    1. Date (dd/mm/yy)
    2. Time (hh:mm:ss)
    3. Call_ID (clientCorrelationId)
    4. Caller_ID (callerId)
    5. Caller_Number (callerNumber)
    6. Destination_CLI (destinationNumber)
    7. Destination_Number (displayCliDestination)
    8. Caller_Waiting_Time (mm:ss)
    9. Conversation_Duration (mm:ss)
    10. Overall_Call_Status
    11. Hangup_Cause
    12. Caller_Status
    13. Destination_Status
    14. Caller_Circle_Name
    15. Pulse_Count
    16. Recording
    """
    # Parse timestamp for date/time display
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
        
        # Standard UI fields (Section 2)
        'date': display_date,
        'time': display_time,
        'callId': item.get('clientCorrelationId', ''),
        'callerId': item.get('callerId', ''),
        'callerNumber': item.get('callerNumber', ''),
        'destinationCli': item.get('destinationNumber', ''),
        'destinationNumber': item.get('displayCliDestination', ''),
        'callerWaitingTime': _ms_to_mmss(item.get('fromWaitingTimeMs', 0)),
        'conversationDuration': _ms_to_mmss(item.get('conversationDurationMs', 0)),
        'overallCallStatus': item.get('overallCallStatus', ''),
        'hangupCause': item.get('hangupStatus', ''),
        'callerStatus': item.get('callerNumberStatus', ''),
        'destinationStatus': item.get('destinationNumberStatus', ''),
        'callerCircleName': item.get('circleNameCaller', ''),
        'recording': item.get('s3RecordingUrl', '') or item.get('recordingURL', ''),
        
        # Extended fields
        'clientCorrelationId': item.get('clientCorrelationId', ''),
        'customerId': item.get('customerId', ''),
        'callType': item.get('callType', ''),
        'direction': item.get('callType', ''),
        'derivedOverallStatus': item.get('derivedOverallStatus', ''),
        'calledNumber': item.get('calledNumber', ''),
        'displayCliDestination': item.get('displayCliDestination', ''),
        'callerName': item.get('callerName', ''),
        'destinationName': item.get('destinationName', ''),
        
        # Duration fields (seconds)
        'durationSec': float(item.get('durationSec', 0)),
        'conversationDurationSec': float(item.get('conversationDurationSec', 0)),
        'billableDurationSec': float(item.get('billableDurationSec', 0)),
        'fromWaitingTimeSec': float(item.get('fromWaitingTimeSec', 0)),
        'callerDurationSec': float(item.get('callerDurationSec', 0)),
        
        # Duration display (mm:ss)
        'billableDurationDisplay': _ms_to_mmss(item.get('billableDurationMs', 0)),
        'callerDurationDisplay': _ms_to_mmss(item.get('callerDuration', 0)),
        
        # Status details (SIP codes)
        'callerNumberStatusDetails': item.get('callerNumberStatusDetails', ''),
        'destinationNumberStatusDetails': item.get('destinationNumberStatusDetails', ''),
        'hangupStatus': item.get('hangupStatus', ''),
        'hangupCauseDetail': item.get('hangupCause', ''),
        
        # Circle and operator
        'circleNameCaller': item.get('circleNameCaller', ''),
        'circleNameDestination': item.get('circleNameDestination', ''),
        'operatorNameCaller': item.get('operatorNameCaller', ''),
        'operatorNameDestination': item.get('operatorNameDestination', ''),
        
        # Retry info
        'retryCountCaller': int(float(item.get('retryCountCaller', 0))),
        'retryCountDestination': int(float(item.get('retryCountDestination', 0))),
        
        # Recording URLs
        'recordingURL': item.get('recordingURL', ''),
        's3RecordingUrl': item.get('s3RecordingUrl', ''),
        
        # Metadata
        'source': item.get('source', 'airtel_cdr_webhook'),
        'participantsCount': int(float(item.get('participantsCount', 0))),
        'timestamp': ts,
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _calculate_stats(records: List[Dict]) -> Dict:
    """
    Calculate statistics from CDR records.
    
    Per Airtel CDR spec Section 3 (Overall Call Status matrix) and Section 6 (Dashboard).
    """
    total = len(records)
    if total == 0:
        return {
            'total': 0, 'inbound': 0, 'outbound': 0,
            'answered': 0, 'missed': 0, 'busy': 0, 'disconnected': 0,
            'avgConversationDuration': 0, 'avgWaitTime': 0, 'totalBillable': 0,
            'byCircle': {}, 'byOperator': {},
            'byCallerStatus': {}, 'byDestinationStatus': {},
            'byHangupStatus': {}
        }
    
    inbound = sum(1 for r in records if r.get('callType') == 'INBOUND')
    outbound = sum(1 for r in records if r.get('callType') == 'OUTBOUND')
    
    # Status counts per Airtel spec Section 3
    answered = sum(1 for r in records if r.get('overallCallStatus') == 'Answered')
    missed = sum(1 for r in records if r.get('overallCallStatus') == 'Missed')
    busy = sum(1 for r in records if r.get('overallCallStatus') == 'Busy')
    disconnected = sum(1 for r in records if r.get('overallCallStatus') == 'Disconnected')
    
    # Average durations (per Airtel dashboard spec Section 6)
    conv_durations = [float(r.get('conversationDurationSec', 0)) for r in records if r.get('conversationDurationSec')]
    wait_times = [float(r.get('fromWaitingTimeSec', 0)) for r in records if r.get('fromWaitingTimeSec')]
    billable = sum(float(r.get('billableDurationSec', 0)) for r in records)
    
    # Breakdown by circle (demographic view)
    by_circle = defaultdict(int)
    for r in records:
        circle = r.get('circleNameCaller', '') or 'Unknown'
        by_circle[circle] += 1
    
    # Breakdown by operator
    by_operator = defaultdict(int)
    for r in records:
        op = r.get('operatorNameCaller', '') or 'Unknown'
        by_operator[op] += 1
    
    # Breakdown by caller number status (per spec Section 1.1)
    by_caller_status = defaultdict(int)
    for r in records:
        cs = r.get('callerNumberStatus', '') or 'Unknown'
        by_caller_status[cs] += 1
    
    # Breakdown by destination number status
    by_dest_status = defaultdict(int)
    for r in records:
        ds = r.get('destinationNumberStatus', '') or 'Unknown'
        by_dest_status[ds] += 1
    
    # Breakdown by hangup status
    by_hangup = defaultdict(int)
    for r in records:
        hs = r.get('hangupStatus', '') or 'Unknown'
        by_hangup[hs] += 1
    
    return {
        'total': total,
        'inbound': inbound,
        'outbound': outbound,
        'answered': answered,
        'missed': missed,
        'busy': busy,
        'disconnected': disconnected,
        'avgConversationDuration': round(sum(conv_durations) / len(conv_durations), 2) if conv_durations else 0,
        'avgWaitTime': round(sum(wait_times) / len(wait_times), 2) if wait_times else 0,
        'totalBillable': round(billable, 2),
        'byCircle': dict(by_circle),
        'byOperator': dict(by_operator),
        'byCallerStatus': dict(by_caller_status),
        'byDestinationStatus': dict(by_dest_status),
        'byHangupStatus': dict(by_hangup),
    }


def _calculate_dashboard(records: List[Dict]) -> Dict:
    """
    Calculate dashboard-specific aggregations per Airtel CDR spec Section 6.
    
    Returns:
    - callTrend: Answered vs Missed by date
    - demographicView: Call count by caller circle/state
    - destinationStatusBreakdown: Count by destination number status
    - avgCustomerWaitingTime: Average fromWaitingTime (mm:ss)
    - avgConversationDuration: Average conversationDuration (mm:ss)
    - callVolumeByCli: Call count grouped by callerId with status breakdown
    """
    if not records:
        return {
            'callTrend': [], 'demographicView': {},
            'destinationStatusBreakdown': {},
            'avgCustomerWaitingTime': '00:00',
            'avgConversationDuration': '00:00',
            'callVolumeByCli': []
        }
    
    # Call trend by date (answered vs missed)
    trend_data = defaultdict(lambda: {'answered': 0, 'missed': 0, 'total': 0})
    for r in records:
        ts = r.get('timestamp', '')
        date_key = ts.split(' ')[0] if ts and ' ' in ts else 'unknown'
        trend_data[date_key]['total'] += 1
        status = r.get('overallCallStatus', '')
        if status == 'Answered':
            trend_data[date_key]['answered'] += 1
        else:
            trend_data[date_key]['missed'] += 1
    
    call_trend = [{'date': k, **v} for k, v in sorted(trend_data.items())]
    
    # Demographic view by circle/state
    demographic = defaultdict(int)
    for r in records:
        circle = r.get('circleNameCaller', '') or 'Unknown'
        demographic[circle] += 1
    
    # Destination number status breakdown
    dest_status_breakdown = defaultdict(int)
    for r in records:
        ds = r.get('destinationNumberStatus', '') or 'Unknown'
        dest_status_breakdown[ds] += 1
    
    # Average customer waiting time (fromWaitingTime)
    wait_times_ms = [float(r.get('fromWaitingTimeMs', 0)) for r in records if r.get('fromWaitingTimeMs')]
    avg_wait_ms = sum(wait_times_ms) / len(wait_times_ms) if wait_times_ms else 0
    
    # Average conversation duration
    conv_ms = [float(r.get('conversationDurationMs', 0)) for r in records if r.get('conversationDurationMs')]
    avg_conv_ms = sum(conv_ms) / len(conv_ms) if conv_ms else 0
    
    # Call volume by CLI (callerId) with status mapping
    cli_data = defaultdict(lambda: {'total': 0, 'answered': 0, 'missed': 0, 'inbound': 0, 'outbound': 0})
    for r in records:
        cli = r.get('callerId', '') or 'Unknown'
        cli_data[cli]['total'] += 1
        if r.get('overallCallStatus') == 'Answered':
            cli_data[cli]['answered'] += 1
        else:
            cli_data[cli]['missed'] += 1
        if r.get('callType') == 'INBOUND':
            cli_data[cli]['inbound'] += 1
        else:
            cli_data[cli]['outbound'] += 1
    
    call_volume_by_cli = [{'callerId': k, **v} for k, v in sorted(cli_data.items(), key=lambda x: x[1]['total'], reverse=True)]
    
    return {
        'callTrend': call_trend,
        'demographicView': dict(demographic),
        'destinationStatusBreakdown': dict(dest_status_breakdown),
        'avgCustomerWaitingTime': _ms_to_mmss(avg_wait_ms),
        'avgConversationDuration': _ms_to_mmss(avg_conv_ms),
        'avgCustomerWaitingTimeSec': round(avg_wait_ms / 1000, 2) if avg_wait_ms else 0,
        'avgConversationDurationSec': round(avg_conv_ms / 1000, 2) if avg_conv_ms else 0,
        'callVolumeByCli': call_volume_by_cli,
    }


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }
