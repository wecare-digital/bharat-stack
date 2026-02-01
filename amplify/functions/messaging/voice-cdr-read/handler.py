"""
Voice CDR Read Lambda Function

Purpose: Read Airtel Call Detail Records from DynamoDB for dashboard display

Inbound Number: +91 9319767034
Email: voice@wecare.digital

Query Parameters:
- callType: INBOUND or OUTBOUND
- status: Answered, Missed, Busy, etc.
- limit: Number of records (default 50, max 100)
- startDate: Filter by date (epoch seconds)
- endDate: Filter by date (epoch seconds)
- callerNumber: Filter by caller phone
- search: Search by clientCorrelationId or vmSessionId
"""

import os
import json
import logging
import boto3
from typing import Dict, Any, List
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

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


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Read CDR records with optional filtering and statistics.
    
    Returns:
    - records: List of CDR records
    - count: Number of records returned
    - stats: Aggregated statistics
    - inboundNumber: Configured inbound number
    - email: Contact email
    """
    request_id = context.aws_request_id if context else 'local'
    
    logger.info(json.dumps({
        'event': 'voice_cdr_read_request',
        'requestId': request_id
    }))
    
    try:
        # Handle OPTIONS for CORS preflight
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', ''))
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        # Get query parameters
        params = event.get('queryStringParameters') or {}
        call_type = params.get('callType', '')
        status = params.get('status', '')
        limit = min(int(params.get('limit', 50)), 100)
        start_date = params.get('startDate', '')
        end_date = params.get('endDate', '')
        caller_number = params.get('callerNumber', '')
        search = params.get('search', '')
        
        logger.info(json.dumps({
            'event': 'cdr_query_params',
            'callType': call_type,
            'status': status,
            'limit': limit,
            'startDate': start_date,
            'endDate': end_date,
            'callerNumber': caller_number,
            'search': search,
            'requestId': request_id
        }))
        
        # Read from DynamoDB
        table = dynamodb.Table(VOICE_CDR_TABLE)
        
        # Build scan parameters
        scan_kwargs = {
            'Limit': limit * 2,  # Fetch more to account for filtering
        }
        
        # Build filter expression
        filter_expressions = []
        expression_values = {}
        expression_names = {}
        
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
            filter_expressions.append('callerNumber = :callerNumber')
            expression_values[':callerNumber'] = caller_number
        
        if search:
            filter_expressions.append('(contains(clientCorrelationId, :search) OR contains(vmSessionId, :search))')
            expression_values[':search'] = search
        
        if filter_expressions:
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expressions)
            scan_kwargs['ExpressionAttributeValues'] = expression_values
        
        if expression_names:
            scan_kwargs['ExpressionAttributeNames'] = expression_names
        
        # Scan table
        response = table.scan(**scan_kwargs)
        records = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response and len(records) < limit:
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = table.scan(**scan_kwargs)
            records.extend(response.get('Items', []))
        
        # Sort by createdAt descending (most recent first)
        records.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        
        # Limit to requested count
        records = records[:limit]
        
        # Calculate statistics
        stats = _calculate_stats(records)
        
        logger.info(json.dumps({
            'event': 'voice_cdr_read_success',
            'count': len(records),
            'stats': stats,
            'requestId': request_id
        }))
        
        return _response(200, {
            'records': records,
            'count': len(records),
            'stats': stats,
            'inboundNumber': INBOUND_NUMBER,
            'email': INBOUND_EMAIL
        })
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'voice_cdr_read_error',
            'error': str(e),
            'errorType': type(e).__name__,
            'requestId': request_id
        }))
        return _response(500, {'error': str(e)})


def _calculate_stats(records: List[Dict]) -> Dict:
    """
    Calculate statistics from CDR records.
    
    Returns:
    - total: Total number of records
    - inbound/outbound: Count by call type
    - answered/missed/busy: Count by status
    - avgDuration: Average conversation duration
    - avgWaitTime: Average waiting time
    - totalBillable: Total billable duration
    - byCircle: Breakdown by caller circle
    - byOperator: Breakdown by operator
    """
    total = len(records)
    if total == 0:
        return {
            'total': 0,
            'inbound': 0,
            'outbound': 0,
            'answered': 0,
            'missed': 0,
            'busy': 0,
            'avgDuration': 0,
            'avgWaitTime': 0,
            'totalBillable': 0,
            'byCircle': {},
            'byOperator': {}
        }
    
    # Count by call type
    inbound = sum(1 for r in records if r.get('callType') == 'INBOUND')
    outbound = sum(1 for r in records if r.get('callType') == 'OUTBOUND')
    
    # Count by status
    answered = sum(1 for r in records if r.get('overallCallStatus') == 'Answered')
    missed = sum(1 for r in records if r.get('overallCallStatus') == 'Missed')
    busy = sum(1 for r in records if r.get('overallCallStatus') == 'Busy')
    
    # Average durations
    durations = [float(r.get('conversationDurationSec', 0)) for r in records if r.get('conversationDurationSec')]
    wait_times = [float(r.get('fromWaitingTimeSec', 0)) for r in records if r.get('fromWaitingTimeSec')]
    billable = sum(float(r.get('billableDurationSec', 0)) for r in records)
    
    # Breakdown by circle
    by_circle = {}
    for r in records:
        circle = r.get('circleNameCaller', 'Unknown')
        if circle:
            by_circle[circle] = by_circle.get(circle, 0) + 1
    
    # Breakdown by operator
    by_operator = {}
    for r in records:
        operator = r.get('operatorNameCaller', 'Unknown')
        if operator:
            by_operator[operator] = by_operator.get(operator, 0) + 1
    
    return {
        'total': total,
        'inbound': inbound,
        'outbound': outbound,
        'answered': answered,
        'missed': missed,
        'busy': busy,
        'avgDuration': round(sum(durations) / len(durations), 2) if durations else 0,
        'avgWaitTime': round(sum(wait_times) / len(wait_times), 2) if wait_times else 0,
        'totalBillable': round(billable, 2),
        'byCircle': by_circle,
        'byOperator': by_operator
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
