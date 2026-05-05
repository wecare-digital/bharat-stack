"""
Sinch SMS DLR (Delivery Report) Webhook Handler

Endpoint: POST /webhook/sinch-dlr
Receives delivery status callbacks from Sinch India (ACL Gateway).

DLR POST payload format (from Sinch docs):
{
    "msg_id": "messageId",
    "mobile_no": "receiver",
    "rqst_ack_id": "responseid",
    "vendor_recv_dttime": "requestReceivedTime",
    "sms_delv_status": "status",
    "sms_delv_dttime": "dlrReceivedTime",
    "vendor_name": "SINCH INDIA",
    "channel_name": "SMS",
    "remarks": "stat",
    "msg_sent_dttime": "submitTime",
    "handsetTime": "time"
}
"""

import os
import json
import time
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_headers, extract_origin

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Tables
SMS_OUTBOUND_TABLE = os.environ.get('SMS_OUTBOUND_TABLE', 'stack-wecare-digital-SmsOutboundTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'stack-wecare-digital-WhatsAppOutboundTable')

# Status mapping from Sinch to our internal status
SINCH_STATUS_MAP = {
    'delivered': 'delivered',
    'DELIVRD': 'delivered',
    'D': 'delivered',
    'failed': 'failed',
    'FAILED': 'failed',
    'F': 'failed',
    'rejected': 'failed',
    'REJECTD': 'failed',
    'expired': 'failed',
    'EXPIRED': 'failed',
    'undelivered': 'failed',
    'UNDELIV': 'failed',
    'submitted': 'sent',
    'SUBMIT': 'sent',
    'accepted': 'sent',
    'ACCEPTD': 'sent',
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Sinch DLR webhook callbacks."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')

    # Handle GET (health check / verification)
    if http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({'status': 'ok', 'service': 'sinch-dlr-webhook'}),
        }

    # Parse body
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            # Try JSON first
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                # Try URL-encoded form data
                import urllib.parse
                data = dict(urllib.parse.parse_qsl(body))
        else:
            data = body or {}
    except Exception as e:
        logger.error(f'Failed to parse DLR body: {e}')
        return {
            'statusCode': 200,  # Always return 200 to Sinch to prevent retries
            'headers': cors_headers(origin),
            'body': json.dumps({'success': False, 'error': 'parse_error'}),
        }

    # Handle batch DLR (Sinch sends up to 500 per packet)
    if isinstance(data, list):
        for item in data:
            _process_dlr(item, request_id)
    else:
        _process_dlr(data, request_id)

    return {
        'statusCode': 200,
        'headers': cors_headers(origin),
        'body': json.dumps({'success': True, 'message': 'DLR received'}),
    }


def _process_dlr(data: Dict, request_id: str) -> None:
    """Process a single DLR record from Sinch."""
    # Extract fields (support both POST JSON format and GET query string format)
    msg_id = data.get('msg_id', data.get('messageId', data.get('msgid', '')))
    mobile = data.get('mobile_no', data.get('msisdn', data.get('reciever', '')))
    response_id = data.get('rqst_ack_id', data.get('responseId', data.get('responseid', '')))
    status_raw = data.get('sms_delv_status', data.get('dlrstatus', data.get('status', '')))
    dlr_time = data.get('sms_delv_dttime', data.get('dlrrecdtime', ''))
    submit_time = data.get('msg_sent_dttime', data.get('vendor_recv_dttime', ''))
    remarks = data.get('remarks', data.get('errordesc', ''))
    error_code = data.get('errorCode', data.get('err', ''))
    sender = data.get('sender', data.get('senderid', ''))

    # Normalize status
    status = SINCH_STATUS_MAP.get(status_raw, SINCH_STATUS_MAP.get(status_raw.upper() if status_raw else '', 'unknown'))

    logger.info(json.dumps({
        'event': 'sinch_dlr_received',
        'msgId': msg_id,
        'responseId': response_id,
        'mobile': mobile[-4:] if mobile else '',
        'status': status,
        'statusRaw': status_raw,
        'remarks': remarks,
        'errorCode': error_code,
        'requestId': request_id,
    }))

    # Update message status in DynamoDB
    now = int(time.time())

    # Try to find and update the message by provider message ID (response_id)
    # The outbound-sms Lambda stores providerMessageId which is the Sinch response ID
    if response_id or msg_id:
        _update_sms_status(
            provider_msg_id=response_id or msg_id,
            status=status,
            dlr_time=dlr_time,
            submit_time=submit_time,
            error_code=error_code,
            remarks=remarks,
            mobile=mobile,
            now=now,
        )


def _update_sms_status(provider_msg_id: str, status: str, dlr_time: str,
                       submit_time: str, error_code: str, remarks: str,
                       mobile: str, now: int) -> None:
    """Update SMS message status in DynamoDB."""
    # Try SMS outbound table first
    try:
        table = dynamodb.Table(SMS_OUTBOUND_TABLE)
        # Scan for the message by providerMessageId
        resp = table.scan(
            FilterExpression='providerMessageId = :pid',
            ExpressionAttributeValues={':pid': provider_msg_id},
            Limit=5,
        )
        items = resp.get('Items', [])
        if items:
            item = items[0]
            table.update_item(
                Key={'id': item['id']},
                UpdateExpression='SET #s = :status, dlrTimestamp = :dlr, dlrErrorCode = :ec, dlrRemarks = :rm, updatedAt = :now',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':status': status,
                    ':dlr': dlr_time,
                    ':ec': error_code,
                    ':rm': remarks,
                    ':now': Decimal(str(now)),
                },
            )
            logger.info(json.dumps({
                'event': 'sinch_dlr_updated',
                'messageId': item['id'],
                'providerMsgId': provider_msg_id,
                'status': status,
            }))
            return
    except Exception as e:
        logger.warning(f'SMS outbound table update failed: {e}')

    # Fallback: try the general messages table
    try:
        table = dynamodb.Table(MESSAGES_TABLE)
        resp = table.scan(
            FilterExpression='contains(providerMessageId, :pid) OR contains(content, :pid)',
            ExpressionAttributeValues={':pid': provider_msg_id[:30]},
            Limit=5,
        )
        items = resp.get('Items', [])
        if items:
            item = items[0]
            table.update_item(
                Key={'id': item['id']},
                UpdateExpression='SET #s = :status, dlrTimestamp = :dlr, dlrErrorCode = :ec, updatedAt = :now',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':status': status,
                    ':dlr': dlr_time,
                    ':ec': error_code,
                    ':now': Decimal(str(now)),
                },
            )
            logger.info(json.dumps({
                'event': 'sinch_dlr_updated_fallback',
                'messageId': item['id'],
                'status': status,
            }))
    except Exception as e:
        logger.warning(f'Fallback DLR update failed: {e}')
