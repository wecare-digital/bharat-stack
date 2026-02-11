"""
Bulk Worker Lambda Function
Purpose: Process bulk messaging jobs from SQS queue
Reads recipients from BulkRecipientsTable and sends messages via WhatsApp/SMS/Email
"""
import os
import json
import logging
import time
import uuid
import boto3
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sqs = boto3.client('sqs', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
social_messaging = boto3.client('socialmessaging', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

BULK_JOBS_TABLE = os.environ.get('BULK_JOBS_TABLE', 'base-wecare-digital-BulkJobsTable')
BULK_RECIPIENTS_TABLE = os.environ.get('BULK_RECIPIENTS_TABLE', 'base-wecare-digital-BulkRecipientsTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
DEFAULT_PHONE_NUMBER_ID = os.environ.get('DEFAULT_PHONE_NUMBER_ID', 'phone-number-id-5e020cecd221429996f6ae721cc42206')
RATE_LIMIT_PER_SECOND = int(os.environ.get('RATE_LIMIT_PER_SECOND', '80'))

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}

def handler(event, context):
    """Process SQS messages for bulk sending."""
    request_id = context.aws_request_id if context else 'local'
    logger.info(f'[{request_id}] Bulk worker invoked')

    # Handle API Gateway HTTP requests (status check)
    if 'requestContext' in event and 'http' in event.get('requestContext', {}):
        return _response(200, {'status': 'bulk-worker-active', 'sendMode': SEND_MODE})

    # Handle SQS event
    records = event.get('Records', [])
    if not records:
        # Direct invocation with job details
        body = event if isinstance(event, dict) else json.loads(event)
        return _process_job(body, request_id)

    results = []
    for record in records:
        try:
            body = json.loads(record.get('body', '{}'))
            result = _process_job(body, request_id)
            results.append(result)
        except Exception as e:
            logger.error(f'[{request_id}] Error processing record: {e}')
            results.append({'error': str(e)})

    return {'statusCode': 200, 'body': json.dumps({'processed': len(results), 'results': results})}


def _process_job(body: Dict, request_id: str) -> Dict:
    """Process a single bulk job."""
    job_id = body.get('jobId')
    if not job_id:
        return {'error': 'jobId required'}

    jobs_table = dynamodb.Table(BULK_JOBS_TABLE)
    recipients_table = dynamodb.Table(BULK_RECIPIENTS_TABLE)
    contacts_table = dynamodb.Table(CONTACTS_TABLE)

    try:
        # Get job details
        job = jobs_table.get_item(Key={'jobId': job_id}).get('Item')
        if not job:
            return {'error': f'Job {job_id} not found'}

        if job.get('status') in ['CANCELLED', 'COMPLETED']:
            return {'status': 'skipped', 'reason': f'Job is {job["status"]}'}

        # Update job status to IN_PROGRESS
        jobs_table.update_item(
            Key={'jobId': job_id},
            UpdateExpression='SET #s = :s, updatedAt = :u',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':s': 'IN_PROGRESS', ':u': int(time.time())}
        )

        # Get pending recipients
        response = recipients_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('jobId').eq(job_id),
            FilterExpression=boto3.dynamodb.conditions.Attr('status').eq('PENDING')
        )
        recipients = response.get('Items', [])

        channel = job.get('channel', 'WHATSAPP')
        template_name = body.get('templateName')
        template_params = body.get('templateParams', [])
        content = body.get('content', '')
        phone_number_id = body.get('phoneNumberId', DEFAULT_PHONE_NUMBER_ID)

        sent_count = int(job.get('sentCount', 0))
        failed_count = int(job.get('failedCount', 0))

        for recipient in recipients:
            # Check if job was cancelled
            current_job = jobs_table.get_item(Key={'jobId': job_id}).get('Item', {})
            if current_job.get('status') == 'CANCELLED':
                break

            contact_id = recipient.get('contactId')
            recipient_id = recipient.get('recipientId')

            try:
                # Get contact phone
                contact = contacts_table.get_item(Key={'contactId': contact_id}).get('Item', {})
                phone = contact.get('phone', '')
                if not phone:
                    raise ValueError('No phone number')

                if SEND_MODE == 'LIVE' and channel == 'WHATSAPP':
                    _send_whatsapp(phone, phone_number_id, template_name, template_params, content, contact_id, request_id)

                # Update recipient status
                recipients_table.update_item(
                    Key={'jobId': job_id, 'recipientId': recipient_id},
                    UpdateExpression='SET #s = :s, sentAt = :t',
                    ExpressionAttributeNames={'#s': 'status'},
                    ExpressionAttributeValues={':s': 'SENT', ':t': int(time.time())}
                )
                sent_count += 1
            except Exception as e:
                logger.error(f'[{request_id}] Failed to send to {contact_id}: {e}')
                recipients_table.update_item(
                    Key={'jobId': job_id, 'recipientId': recipient_id},
                    UpdateExpression='SET #s = :s, errorDetails = :e',
                    ExpressionAttributeNames={'#s': 'status'},
                    ExpressionAttributeValues={':s': 'FAILED', ':e': str(e)}
                )
                failed_count += 1

            # Rate limiting
            time.sleep(1.0 / RATE_LIMIT_PER_SECOND)

        # Update job final status
        final_status = 'COMPLETED'
        jobs_table.update_item(
            Key={'jobId': job_id},
            UpdateExpression='SET #s = :s, sentCount = :sc, failedCount = :fc, updatedAt = :u',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':s': final_status, ':sc': sent_count, ':fc': failed_count, ':u': int(time.time())
            }
        )

        return {'jobId': job_id, 'status': final_status, 'sent': sent_count, 'failed': failed_count}

    except Exception as e:
        logger.error(f'[{request_id}] Job {job_id} error: {e}')
        jobs_table.update_item(
            Key={'jobId': job_id},
            UpdateExpression='SET #s = :s, updatedAt = :u',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':s': 'FAILED', ':u': int(time.time())}
        )
        return {'error': str(e)}


def _send_whatsapp(phone: str, phone_number_id: str, template_name: str,
                   template_params: list, content: str, contact_id: str, request_id: str):
    """Send WhatsApp message via Social Messaging API."""
    formatted_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
    if not formatted_phone.startswith('91') and len(formatted_phone) == 10:
        formatted_phone = '91' + formatted_phone

    if template_name:
        message_payload = {
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': 'en'},
                'components': [{'type': 'body', 'parameters': [{'type': 'text', 'text': p} for p in template_params]}] if template_params else []
            }
        }
    else:
        message_payload = {'type': 'text', 'text': {'body': content}}

    meta_payload = json.dumps({
        'messaging_product': 'whatsapp',
        'to': formatted_phone,
        **message_payload
    }).encode('utf-8')

    response = social_messaging.send_whatsapp_message(
        originationPhoneNumberId=phone_number_id,
        message=meta_payload,
        metaApiVersion='v20.0'
    )
    logger.info(f'[{request_id}] Sent to {formatted_phone}: {response.get("messageId")}')


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    return {'statusCode': status_code, 'headers': CORS_HEADERS, 'body': json.dumps(body, default=str)}
