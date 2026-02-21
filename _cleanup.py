"""
DEEP CLEAN: Wipe ALL 29 resources — DynamoDB tables + S3 prefixes.
Preserves: SystemConfig table (payment_allowed_phones, etc.)
Direct boto3 access — no API Gateway needed.
"""
import boto3
import json
import time

REGION = 'us-east-1'
BUCKET = 'app.wecare.digital'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
ddb_client = boto3.client('dynamodb', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

# ── ALL 25 DynamoDB tables to wipe ──
WIPE_TABLES = [
    # Messages
    ('WhatsApp Inbox (Inbound)',       'base-wecare-digital-WhatsAppInboundTable'),
    ('WhatsApp Outbox (Outbound)',     'base-wecare-digital-WhatsAppOutboundTable'),
    ('Scheduled Messages',             'base-wecare-digital-ScheduledMessagesTable'),
    # Contacts
    ('Contacts',                       'base-wecare-digital-ContactsTable'),
    # Media
    ('Media Files (DB records)',       'base-wecare-digital-MediaFilesTable'),
    # AI
    ('AI Conversation History',        'base-wecare-digital-ConversationHistoryTable'),
    ('AI Interactions Log',            'base-wecare-digital-AIInteractionsTable'),
    # Voice
    ('WhatsApp Call Logs',             'base-wecare-digital-WhatsAppCallingTable'),
    ('Voice CDR Records',              'base-wecare-digital-VoiceCDRTable'),
    ('Voice Calls (Airtel)',           'base-wecare-digital-VoiceCalls'),
    ('Voice AWS (Pinpoint)',           'base-wecare-digital-VoiceAwsTable'),
    ('WhatsApp Voice (TTS) Log',       'base-wecare-digital-WhatsAppVoiceTable'),
    ('OBD Campaigns',                  'base-wecare-digital-OBDCampaigns'),
    ('Airtel C2C Records',             'base-wecare-digital-AirtelC2CTable'),
    # SMS
    ('SMS AWS (Pinpoint)',             'base-wecare-digital-SmsAwsTable'),
    ('Airtel SMS Messages',            'base-wecare-digital-AirtelSMSTable'),
    # Invoices & Payments
    ('Invoices',                       'base-wecare-digital-InvoicesTable'),
    ('Invoice Line Items',             'base-wecare-digital-InvoiceItemsTable'),
    ('Invoice Assets (PDFs)',          'base-wecare-digital-InvoiceAssetsTable'),
    ('Invoice Delivery Log',           'base-wecare-digital-InvoiceDeliveryLogTable'),
    ('Invoice Sequence Counter',       'base-wecare-digital-InvoiceSequenceTable'),
    ('Payments',                       'base-wecare-digital-PaymentsTable'),
    ('Razorpay Webhook Log',           'base-wecare-digital-RazorpayWebhookLogTable'),
    # Bulk
    ('Bulk Jobs',                      'base-wecare-digital-BulkJobsTable'),
    ('Bulk Recipients',                'base-wecare-digital-BulkRecipientsTable'),
]

# ── ALL 4 S3 prefixes to wipe ──
S3_PREFIXES = [
    ('S3: Invoice Files',          'invoices/'),
    ('S3: WhatsApp Media',         'stream/media/wa/'),
    ('S3: Voice Recordings',       'voice/voice-in/'),
    ('S3: WhatsApp Voice (TTS)',   'whatsapp-media/whatsapp-voice/'),
]


def get_key_names(table_name):
    """Get partition/sort key names from table description."""
    desc = ddb_client.describe_table(TableName=table_name)
    return [k['AttributeName'] for k in desc['Table']['KeySchema']]


def wipe_table(table_name):
    """Delete every item from a DynamoDB table using batch_writer."""
    try:
        key_names = get_key_names(table_name)
    except Exception as e:
        return -1, str(e)

    table = dynamodb.Table(table_name)
    deleted = 0

    # Project only key attributes (use aliases to avoid reserved-word issues)
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
                key = {k: item[k] for k in key_names if k in item}
                if key:
                    batch.delete_item(Key=key)
                    deleted += 1
        if 'LastEvaluatedKey' not in resp:
            break
        scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

    return deleted, None


def wipe_s3_prefix(prefix):
    """Delete all objects under an S3 prefix."""
    deleted = 0
    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            objects = page.get('Contents', [])
            if not objects:
                continue
            keys = [{'Key': obj['Key']} for obj in objects]
            for i in range(0, len(keys), 1000):
                batch = keys[i:i+1000]
                s3.delete_objects(Bucket=BUCKET, Delete={'Objects': batch})
                deleted += len(batch)
    except Exception as e:
        return deleted, str(e)
    return deleted, None


def main():
    print('=' * 65)
    print('  DEEP CLEAN — WECARE.DIGITAL — ALL 29 RESOURCES')
    print('=' * 65)

    total_db = 0
    total_s3 = 0
    errors = []

    # ── DynamoDB tables (25) ──
    print(f'\n{"Label":<35} {"Table":<45} {"Deleted":>8} {"Time":>6}')
    print('-' * 100)
    for label, table_name in WIPE_TABLES:
        t0 = time.time()
        count, err = wipe_table(table_name)
        elapsed = time.time() - t0
        if err:
            print(f'  {label:<33} {table_name:<45} {"ERROR":>8} {elapsed:5.1f}s  !! {err}')
            errors.append((label, err))
        else:
            total_db += count
            status = f'{count}' if count > 0 else '0'
            print(f'  {label:<33} {table_name:<45} {status:>8} {elapsed:5.1f}s')

    # ── S3 prefixes (4) ──
    print(f'\n{"Label":<35} {"Prefix":<45} {"Deleted":>8} {"Time":>6}')
    print('-' * 100)
    for label, prefix in S3_PREFIXES:
        t0 = time.time()
        count, err = wipe_s3_prefix(prefix)
        elapsed = time.time() - t0
        if err:
            print(f'  {label:<33} s3://{BUCKET}/{prefix:<35} {"ERROR":>8} {elapsed:5.1f}s  !! {err}')
            errors.append((label, err))
        else:
            total_s3 += count
            status = f'{count}' if count > 0 else '0'
            print(f'  {label:<33} s3://{BUCKET}/{prefix:<35} {status:>8} {elapsed:5.1f}s')

    # ── SystemConfig preserved ──
    print('\n── SystemConfig: PRESERVED ──')
    try:
        cfg = dynamodb.Table('base-wecare-digital-SystemConfigTable')
        resp = cfg.scan()
        for item in resp.get('Items', []):
            print(f'  kept: {item.get("id", "?")}')
    except Exception as e:
        print(f'  (could not read: {e})')

    # ── Summary ──
    print(f'\n{"=" * 65}')
    print(f'  DONE: {total_db} DB items + {total_s3} S3 objects deleted')
    if errors:
        print(f'  ERRORS: {len(errors)}')
        for label, err in errors:
            print(f'    - {label}: {err}')
    print(f'{"=" * 65}')


if __name__ == '__main__':
    main()
