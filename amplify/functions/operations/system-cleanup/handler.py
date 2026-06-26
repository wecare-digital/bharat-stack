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

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

from lambda_utils.logging import get_logger

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
dynamodb_client = boto3.client('dynamodb', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
sqs = boto3.client('sqs', region_name=REGION)

# CORS headers provided by lambda_utils.response.cors_headers(origin)

# All clearable resources grouped by category
CLEANUP_RESOURCES = {
    'whatsapp_inbox': {
        'label': 'WhatsApp Inbox (Inbound)',
        'category': 'Messages',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-WhatsAppInboundTable',
    },
    'whatsapp_outbox': {
        'label': 'WhatsApp Outbox (Outbound)',
        'category': 'Messages',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-WhatsAppOutboundTable',
    },
    'contacts': {
        'label': 'Contacts',
        'category': 'Contacts',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-ContactsTable',
    },
    'media_files': {
        'label': 'Media Files (DB records)',
        'category': 'Media',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-MediaFilesTable',
    },
    'conversation_history': {
        'label': 'AI Conversation History',
        'category': 'AI',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-ConversationHistoryTable',
    },
    'ai_interactions': {
        'label': 'AI Interactions Log',
        'category': 'AI',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-AIInteractionsTable',
    },
    'whatsapp_calling': {
        'label': 'WhatsApp Call Logs',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-WhatsAppCallingTable',
    },
    'voice_cdr': {
        'label': 'Voice CDR Records',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-VoiceCDRTable',
    },
    'voice_calls': {
        'label': 'Voice Calls (Airtel)',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-VoiceCalls',
    },
    'voice_aws': {
        'label': 'Voice AWS (Pinpoint)',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-VoiceAwsTable',
    },
    'sms_aws': {
        'label': 'SMS AWS (Pinpoint)',
        'category': 'SMS',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-SmsAwsTable',
    },
    'airtel_sms': {
        'label': 'Airtel SMS Messages',
        'category': 'SMS',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-AirtelSMSTable',
    },
    'airtel_c2c': {
        'label': 'Airtel C2C Records',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-AirtelC2CTable',
    },
    'invoices': {
        'label': 'Invoices',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-InvoicesTable',
    },
    'invoice_items': {
        'label': 'Invoice Line Items',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-InvoiceItemsTable',
    },
    'invoice_assets': {
        'label': 'Invoice Assets (PDFs)',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-InvoiceAssetsTable',
    },
    'invoice_delivery_log': {
        'label': 'Invoice Delivery Log',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-InvoiceDeliveryLogTable',
    },
    'invoice_sequence': {
        'label': 'Invoice Sequence Counter',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-InvoiceSequenceTable',
    },
    'payments': {
        'label': 'Payments',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-PaymentsTable',
    },
    'razorpay_webhook_log': {
        'label': 'Razorpay Webhook Log',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-RazorpayWebhookLogTable',
    },
    'scheduled_messages': {
        'label': 'Scheduled Messages',
        'category': 'Messages',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-ScheduledMessagesTable',
    },
    'bulk_jobs': {
        'label': 'Bulk Jobs',
        'category': 'Bulk',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-BulkJobsTable',
    },
    'bulk_recipients': {
        'label': 'Bulk Recipients',
        'category': 'Bulk',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-BulkRecipientsTable',
    },
    'whatsapp_voice_log': {
        'label': 'WhatsApp Voice (TTS) Log',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-WhatsAppVoiceTable',
    },
    'obd_campaigns': {
        'label': 'OBD Campaigns',
        'category': 'Voice',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-OBDCampaigns',
    },
    's3_invoices': {
        'label': 'S3: Invoice Files',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/invoices/',
    },
    's3_whatsapp_media': {
        'label': 'S3: WhatsApp Media',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/whatsapp-media/',
    },
    's3_voice_recordings': {
        'label': 'S3: Voice Recordings',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/voice/',
    },
    's3_whatsapp_voice': {
        'label': 'S3: WhatsApp Voice (TTS)',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/whatsapp-media/voice/',
    },
    # --- Additional resources (full factory reset coverage) ---
    'dlq_messages': {
        'label': 'DLQ Messages (Failed Retry Queue)',
        'category': 'Messages',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-DLQMessagesTable',
    },
    'messages_legacy': {
        'label': 'Messages (Legacy Table)',
        'category': 'Messages',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-MessagesTable',
    },
    'dlt_templates': {
        'label': 'DLT Templates (Airtel SMS)',
        'category': 'SMS',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-DLTTemplates',
    },
    'wix_products_cache': {
        'label': 'Wix Products Cache',
        'category': 'Ecommerce',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-WixProductsCache',
    },
    'wix_orders_cache': {
        'label': 'Wix Orders Cache',
        'category': 'Ecommerce',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-WixOrdersCache',
    },
    'wix_order_ids': {
        'label': 'Wix Order ID Mapping',
        'category': 'Ecommerce',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-WixOrderIds',
    },
    'template_analytics': {
        'label': 'Template Analytics',
        'category': 'Analytics & Logs',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-TemplateAnalyticsTable',
    },
    'submit_requests': {
        'label': 'Flow Submit Requests',
        'category': 'Analytics & Logs',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-SubmitRequestsTable',
    },
    'audit_logs': {
        'label': 'Audit Logs',
        'category': 'Analytics & Logs',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-AuditLogsTable',
    },
    'rate_limit': {
        'label': 'Rate Limit Trackers',
        'category': 'System',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-RateLimitTable',
    },
    'sms_in_airtel': {
        'label': 'Airtel Inbound SMS',
        'category': 'SMS',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-SmsInAirtelTable',
    },
    'payu_webhook_log': {
        'label': 'PayU Webhook Log',
        'category': 'Invoices & Payments',
        'type': 'dynamodb',
        'table': 'stack-wecare-digital-PayUWebhookLogTable',
    },
    's3_whatsapp_media_incoming': {
        'label': 'S3: WhatsApp Media (Incoming)',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/whatsapp-media/incoming/',
    },
    's3_whatsapp_media_outgoing': {
        'label': 'S3: WhatsApp Media (Outgoing)',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/whatsapp-media/outgoing/',
    },
    's3_template_headers': {
        'label': 'S3: Template Headers',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/whatsapp-media/template-headers/',
    },
    's3_product_images': {
        'label': 'S3: Product Images',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/store/products/',
    },
    's3_reports': {
        'label': 'S3: Reports & Exports',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/reports/',
    },
    's3_whatsapp_calling_ai': {
        'label': 'S3: WhatsApp Calling AI Audio',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/whatsapp-media/calling-ai/',
    },
    's3_whatsapp_downloads': {
        'label': 'S3: WhatsApp Media Downloads',
        'category': 'S3 Storage',
        'type': 's3',
        'prefix': 'stack/whatsapp-media/downloads/',
    },
    # SQS Queues
    'sqs_inbound_dlq': {
        'label': 'SQS: Inbound DLQ',
        'category': 'SQS Queues',
        'type': 'sqs',
        'queue': 'stack-wecare-digital-inbound-dlq',
    },
    'sqs_bulk_dlq': {
        'label': 'SQS: Bulk DLQ',
        'category': 'SQS Queues',
        'type': 'sqs',
        'queue': 'stack-wecare-digital-bulk-dlq',
    },
    'sqs_bulk_queue': {
        'label': 'SQS: Bulk Queue',
        'category': 'SQS Queues',
        'type': 'sqs',
        'queue': 'stack-wecare-digital-bulk-queue',
    },
    'sqs_outbound_dlq': {
        'label': 'SQS: Outbound DLQ',
        'category': 'SQS Queues',
        'type': 'sqs',
        'queue': 'stack-wecare-digital-outbound-dlq',
    },
}

# ── Dynamic discovery config ──
TABLE_PREFIX = 'stack-wecare-digital-'
S3_ROOT_PREFIX = 'stack/'
S3_MAX_DEPTH = 3  # how many folder levels under stack/ to expose

# Tables that must NEVER be wiped (config, not records)
PROTECTED_TABLES = {
    'stack-wecare-digital-SystemConfigTable',
    'stack-wecare-digital-SystemConfig',
}


def _discover_tables() -> List[str]:
    """List every DynamoDB table that belongs to this stack (by name prefix)."""
    names: List[str] = []
    kwargs: Dict[str, Any] = {}
    try:
        while True:
            resp = dynamodb_client.list_tables(**kwargs)
            names.extend(resp.get('TableNames', []))
            last = resp.get('LastEvaluatedTableName')
            if not last:
                break
            kwargs['ExclusiveStartTableName'] = last
    except Exception as e:
        logger.warning(f'{{"event":"list_tables_error","error":"{e}"}}')
    return [n for n in names if n.startswith(TABLE_PREFIX) and n not in PROTECTED_TABLES]


def _discover_s3_prefixes(max_depth: int = S3_MAX_DEPTH) -> List[str]:
    """List every 'folder' (common prefix) under the stack/ root, up to max_depth levels."""
    found: List[str] = []

    def walk(prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        token = None
        while True:
            kwargs = {'Bucket': BUCKET, 'Prefix': prefix, 'Delimiter': '/'}
            if token:
                kwargs['ContinuationToken'] = token
            try:
                resp = s3.list_objects_v2(**kwargs)
            except Exception as e:
                logger.warning(f'{{"event":"s3_walk_error","prefix":"{prefix}","error":"{e}"}}')
                return
            for cp in resp.get('CommonPrefixes', []):
                p = cp['Prefix']
                found.append(p)
                walk(p, depth + 1)
            if resp.get('IsTruncated'):
                token = resp.get('NextContinuationToken')
            else:
                break

    walk(S3_ROOT_PREFIX, 1)
    return found


def _build_resources() -> Dict[str, Dict[str, Any]]:
    """
    Build the full id -> resource map: curated entries (with friendly labels/categories)
    merged with every dynamically discovered table and S3 folder so nothing is missed.
    Used by both preview (counts) and cleanup (delete) so ids always resolve consistently.
    """
    resources: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in CLEANUP_RESOURCES.items()}

    curated_tables = {v['table'] for v in CLEANUP_RESOURCES.values() if v['type'] == 'dynamodb'}
    curated_prefixes = {v['prefix'] for v in CLEANUP_RESOURCES.values() if v['type'] == 's3'}

    # Add any stack table not already curated
    for table in _discover_tables():
        if table in curated_tables:
            continue
        resources['auto_tbl_' + table] = {
            'label': table[len(TABLE_PREFIX):] or table,
            'category': 'Other Tables',
            'type': 'dynamodb',
            'table': table,
        }

    # Add any S3 folder not already curated
    for prefix in _discover_s3_prefixes():
        if prefix in curated_prefixes:
            continue
        resources['auto_s3_' + prefix] = {
            'label': 'S3: ' + prefix,
            'category': 'S3 Storage',
            'type': 's3',
            'prefix': prefix,
        }

    return resources


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """System cleanup handler — preview counts or delete selected resources."""
    global origin
    origin = extract_origin(event)
    # Support both API Gateway v1 (REST) and v2 (HTTP) event formats
    rc = event.get('requestContext', {})
    method = rc.get('http', {}).get('method', event.get('httpMethod', 'GET')).upper()

    if method == 'OPTIONS':
        return options_response(origin)

    if method == 'GET':
        return _preview()
    elif method == 'POST':
        return _cleanup(event)
    else:
        return {'statusCode': 405, 'headers': cors_headers(origin), 'body': json.dumps({'error': 'Method not allowed'})}



def _get_table_count(table_name: str) -> int:
    """Get actual item count for a DynamoDB table via scan."""
    try:
        table = dynamodb.Table(table_name)
        count = 0
        scan_kwargs = {'Select': 'COUNT'}
        while True:
            resp = table.scan(**scan_kwargs)
            count += resp.get('Count', 0)
            if 'LastEvaluatedKey' not in resp:
                break
            scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
        return count
    except Exception as e:
        logger.warning(f'{{"event":"table_count_error","table":"{table_name}","error":"{e}"}}')
        return -1


def _get_s3_count(prefix: str) -> int:
    """Get content file count under an S3 prefix (excludes folder markers)."""
    try:
        count = 0
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            for obj in page.get('Contents', []):
                if not obj['Key'].endswith('/'):
                    count += 1
        return count
    except Exception as e:
        logger.warning(f'{{"event":"s3_count_error","prefix":"{prefix}","error":"{e}"}}')
        return -1


def _get_sqs_count(queue_name: str) -> int:
    """Get approximate message count in an SQS queue."""
    try:
        url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
        attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible'])
        return int(attrs['Attributes'].get('ApproximateNumberOfMessages', 0)) + int(attrs['Attributes'].get('ApproximateNumberOfMessagesNotVisible', 0))
    except Exception as e:
        logger.warning(f'{{"event":"sqs_count_error","queue":"{queue_name}","error":"{e}"}}')
        return -1


def _preview() -> Dict[str, Any]:
    """Return live item counts for every clearable resource (curated + auto-discovered)."""
    resources = []
    for key, res in _build_resources().items():
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
        elif res['type'] == 'sqs':
            entry['queue'] = res['queue']
            entry['count'] = _get_sqs_count(res['queue'])
        resources.append(entry)

    return {
        'statusCode': 200,
        'headers': cors_headers(origin),
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
    """Delete content files under an S3 prefix, preserving folder markers (0-byte keys ending with /)."""
    deleted = 0
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        objects = page.get('Contents', [])
        if not objects:
            continue
        # Only delete actual files — skip folder markers (keys ending with "/" and size <= 3)
        delete_keys = [{'Key': obj['Key']} for obj in objects if not obj['Key'].endswith('/')]
        if not delete_keys:
            continue
        for i in range(0, len(delete_keys), 1000):
            batch = delete_keys[i:i + 1000]
            s3.delete_objects(Bucket=BUCKET, Delete={'Objects': batch})
            deleted += len(batch)
    return deleted


def _purge_sqs_queue(queue_name: str) -> int:
    """Purge all messages from an SQS queue."""
    try:
        url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
        attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['ApproximateNumberOfMessages'])
        count = int(attrs['Attributes'].get('ApproximateNumberOfMessages', 0))
        sqs.purge_queue(QueueUrl=url)
        return count
    except Exception as e:
        logger.warning(f"Cannot purge SQS queue {queue_name}: {e}")
        return 0


def _cleanup(event: Dict[str, Any]) -> Dict[str, Any]:
    """Delete selected resources."""
    try:
        body = json.loads(event.get('body', '{}'))
    except Exception:
        return {'statusCode': 400, 'headers': cors_headers(origin), 'body': json.dumps({'error': 'Invalid JSON body'})}

    selected = body.get('selected', [])
    if not selected:
        return {'statusCode': 400, 'headers': cors_headers(origin), 'body': json.dumps({'error': 'No resources selected'})}

    all_resources = _build_resources()
    results = []
    total_deleted = 0

    for key in selected:
        res = all_resources.get(key)
        if not res:
            results.append({'id': key, 'error': 'Unknown resource', 'deleted': 0})
            continue

        t0 = time.time()
        try:
            if res['type'] == 'dynamodb':
                count = _wipe_table(res['table'])
            elif res['type'] == 's3':
                count = _wipe_s3_prefix(res['prefix'])
            elif res['type'] == 'sqs':
                count = _purge_sqs_queue(res['queue'])
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
        'headers': cors_headers(origin),
        'body': json.dumps({
            'success': True,
            'results': results,
            'totalDeleted': total_deleted,
        }),
    }
