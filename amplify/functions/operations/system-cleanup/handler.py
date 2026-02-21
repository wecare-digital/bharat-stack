"""
System Cleanup Lambda Handler
Provides selective cleanup of DynamoDB tables and S3 prefixes.
Returns item counts for preview, and deletes selected resources on confirm.
Preserves: SystemConfig table always.
"""

import os
import json
import time
import logging
import boto3
from typing import Dict, Any, List
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

REGION = os.environ.get('AWS_REGION', 'us-east-1')
BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
dynamodb_client = boto3.client('dynamodb', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

CORS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
}

# All clearable resources grouped by category
CLEANUP_RESOURCES = {
    'whatsapp_inbox': {
        'label': 'WhatsApp Inbox (Inbound)',
        'category': 'Messages',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-WhatsAppInboundTable',
    },
    'whatsapp_outbox': {
        'label': 'WhatsApp Outbox (Outbound)',
        'category': 'Messages',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-WhatsAppOutboundTable',
    },
    'contacts': {
        'label': 'Contacts',
        'category': 'Contacts',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-ContactsTable',
    },
    'media_files': {
        'label': 'Media Files (DB records)',
        'category': 'Media',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-MediaFilesTable',
    },
    'conversation_history': {
        'label': 'AI Conversation History',
        'category': 'AI',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-ConversationHistoryTable',
    },
    'ai_interactions': {
        'label': 'AI Interactions Log',
        'category': 'AI',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-AIInteractionsTable',
    },
    'whatsapp_calling': {
        'label': 'WhatsApp Call Logs',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-WhatsAppCallingTable',
    },
    'voice_cdr': {
        'label': 'Voice CDR Records',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-VoiceCDRTable',
    },
    'voice_calls': {
        'label': 'Voice Calls (Airtel)',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-VoiceCalls',
    },
    'voice_aws': {
        'label': 'Voice AWS (Pinpoint)',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-VoiceAwsTable',
    },
    'sms_aws': {
        'label': 'SMS AWS (Pinpoint)',
        'category': 'SMS',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-SmsAwsTable',
    },
    'airtel_sms': {
        'label': 'Airtel SMS Messages',
        'category': 'SMS',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-AirtelSMSTable',
    },
    'airtel_c2c': {
        'label': 'Airtel C2C Records',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-AirtelC2CTable',
    },
    'invoices': {
        'label': 'Invoices',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-InvoicesTable',
    },
    'invoice_items': {
        'label': 'Invoice Line Items',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-InvoiceItemsTable',
    },
    'invoice_assets': {
        'label': 'Invoice Assets (PDFs)',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-InvoiceAssetsTable',
    },
    'invoice_delivery_log': {
        'label': 'Invoice Delivery Log',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-InvoiceDeliveryLogTable',
    },
    'invoice_sequence': {
        'label': 'Invoice Sequence Counter',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-InvoiceSequenceTable',
    },
    'payments': {
        'label': 'Payments',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-PaymentsTable',
    },
    'razorpay_webhook_log': {
        'label': 'Razorpay Webhook Log',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-RazorpayWebhookLogTable',
    },
    'scheduled_messages': {
        'label': 'Scheduled Messages',
        'category': 'Messages',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-ScheduledMessagesTable',
    },
    'bulk_jobs': {
        'label': 'Bulk Jobs',
        'category': 'Bulk',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-BulkJobsTable',
    },
    'bulk_recipients': {
        'label': 'Bulk Recipients',
        'category': 'Bulk',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-BulkRecipientsTable',
    },
    'whatsapp_voice_log': {
        'label': 'WhatsApp Voice (TTS) Log',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-WhatsAppVoiceTable',
    },
    'obd_campaigns': {
        'label': 'OBD Campaigns',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'base-wecare-digital-OBDCampaigns',
    },
    's3_invoices': {
        'label': 'S3: Invoice Files',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'invoices/',
    },
    's3_whatsapp_media': {
        'label': 'S3: WhatsApp Media',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stream/media/wa/',
    },
    's3_voice_recordings': {
        'label': 'S3: Voice Recordings',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'voice/voice-in/',
    },
    's3_whatsapp_voice': {
        'label': 'S3: WhatsApp Voice (TTS)',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'whatsapp-media/whatsapp-voice/',
    },
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """System cleanup handler — preview counts or delete selected resources."""
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}

    method = event.get('httpMethod', 'GET').upper()

    if method == 'GET':
        return _preview()
    elif method == 'POST':
        return _cleanup(event)
    else:
        return {'statusCode': 405, 'headers': CORS, 'body': json.dumps({'error': 'Method not allowed'})}


def _get_table_count(table_name: str) -> int:
    """Get approximate item count for a DynamoDB table."""
    try:
        desc = dynamodb_client.describe_table(TableName=table_name)
        return desc['Table']['ItemCount']
    except Exception:
        return -1


def _get_s3_count(prefix: str) -> int:
    """Get object count under an S3 prefix."""
    try:
        count = 0
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            count += page.get('KeyCount', 0)
        return count
    except Exception:
        return -1


def _preview() -> Dict[str, Any]:
    """Return item counts for all clearable resources."""
    resources = []
    for key, res in CLEANUP_RESOURCES.items():
        entry = {
            'id': key,
            'label': res['label'],
            'category': res['category'],
            'type': res['type'],
        }
        if res['type'] == 'dynamodb':
            entry['table'] = res['table']
            entry['count'] = _get_table_count(res['table'])
        elif res['type'] == 's3':
            entry['prefix'] = res['prefix']
            entry['count'] = _get_s3_count(res['prefix'])
        resources.append(entry)

    return {
        'statusCode': 200,
        'headers': CORS,
        'body': json.dumps({'resources': resources}),
    }


def _wipe_table(table_name: str) -> int:
    """Delete all items from a DynamoDB table."""
    try:
        key_schema = dynamodb_client.describe_table(TableName=table_name)['Table']['KeySchema']
    except Exception as e:
        logger.warning(f"Cannot describe {table_name}: {e}")
        return 0

    key_names = [k['AttributeName'] for k in key_schema]
    table = dynamodb.Table(table_name)
    deleted = 0

    proj_aliases = {f'#k{i}': name for i, name in enumerate(key_names)}
    scan_kwargs = {
        'ProjectionExpression': ', '.join(proj_aliases.keys()),
        'ExpressionAttributeNames': proj_aliases,
    }

    while True:
        resp = table.scan(**scan_kwargs)
        items = resp.get('Items', [])
        if not items:
            break
        with table.batch_writer() as batch:
            for item in items:
                key = {k: item[k] for k in key_names}
                batch.delete_item(Key=key)
                deleted += 1
        if 'LastEvaluatedKey' not in resp:
            break
        scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

    return deleted


def _wipe_s3_prefix(prefix: str) -> int:
    """Delete all objects under an S3 prefix."""
    deleted = 0
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        objects = page.get('Contents', [])
        if not objects:
            continue
        delete_keys = [{'Key': obj['Key']} for obj in objects]
        for i in range(0, len(delete_keys), 1000):
            batch = delete_keys[i:i + 1000]
            s3.delete_objects(Bucket=BUCKET, Delete={'Objects': batch})
            deleted += len(batch)
    return deleted


def _cleanup(event: Dict[str, Any]) -> Dict[str, Any]:
    """Delete selected resources."""
    try:
        body = json.loads(event.get('body', '{}'))
    except Exception:
        return {'statusCode': 400, 'headers': CORS, 'body': json.dumps({'error': 'Invalid JSON body'})}

    selected = body.get('selected', [])
    if not selected:
        return {'statusCode': 400, 'headers': CORS, 'body': json.dumps({'error': 'No resources selected'})}

    results = []
    total_deleted = 0

    for key in selected:
        res = CLEANUP_RESOURCES.get(key)
        if not res:
            results.append({'id': key, 'error': 'Unknown resource', 'deleted': 0})
            continue

        t0 = time.time()
        try:
            if res['type'] == 'dynamodb':
                count = _wipe_table(res['table'])
            elif res['type'] == 's3':
                count = _wipe_s3_prefix(res['prefix'])
            else:
                count = 0
            elapsed = round(time.time() - t0, 1)
            results.append({'id': key, 'label': res['label'], 'deleted': count, 'elapsed': elapsed})
            total_deleted += count
        except Exception as e:
            logger.error(f"Cleanup error for {key}: {e}")
            results.append({'id': key, 'label': res['label'], 'error': str(e), 'deleted': 0})

    logger.info(json.dumps({'event': 'system_cleanup', 'selected': selected, 'totalDeleted': total_deleted}))

    return {
        'statusCode': 200,
        'headers': CORS,
        'body': json.dumps({
            'success': True,
            'results': results,
            'totalDeleted': total_deleted,
        }),
    }
