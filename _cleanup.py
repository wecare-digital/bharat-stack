"""
DEEP CLEAN: Wipe all test data from DynamoDB tables + S3 invoice/media files.
Preserves: SystemConfig table (payment_allowed_phones, etc.)
"""
import boto3
import json
import time

REGION = 'us-east-1'
BUCKET = 'app.wecare.digital'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

# ── Tables to FULLY WIPE (all items deleted) ──
WIPE_TABLES = {
    # Messages & Contacts
    'base-wecare-digital-WhatsAppInboundTable':     'id',
    'base-wecare-digital-WhatsAppOutboundTable':    'id',
    'base-wecare-digital-ContactsTable':            'id',
    'base-wecare-digital-MediaFilesTable':          'id',
    'base-wecare-digital-WhatsAppCallingTable':     'id',
    'base-wecare-digital-ConversationHistoryTable': 'phoneHash',
    'base-wecare-digital-AIInteractionsTable':      'id',
    # Invoices & Payments
    'base-wecare-digital-InvoicesTable':             'invoiceId',
    'base-wecare-digital-InvoiceItemsTable':         None,  # composite key
    'base-wecare-digital-InvoiceAssetsTable':        None,  # composite key
    'base-wecare-digital-InvoiceDeliveryLogTable':   None,  # composite key
    'base-wecare-digital-PaymentsTable':             'id',
    'base-wecare-digital-RazorpayWebhookLogTable':   'id',
    # Sequence table — reset to 0
    'base-wecare-digital-InvoiceSequenceTable':      'fy',
}

# ── S3 prefixes to wipe ──
S3_PREFIXES = [
    'invoices/',
    'stream/media/wa/',      # WhatsApp media downloads
]

def describe_key(table_name):
    """Get the key schema for a table."""
    client = boto3.client('dynamodb', region_name=REGION)
    desc = client.describe_table(TableName=table_name)
    keys = desc['Table']['KeySchema']
    return [(k['AttributeName'], k['KeyType']) for k in keys]

def wipe_table(table_name, pk_hint):
    """Delete all items from a DynamoDB table."""
    try:
        key_schema = describe_key(table_name)
    except Exception as e:
        print(f"  SKIP {table_name}: {e}")
        return 0

    key_names = [k[0] for k in key_schema]
    table = dynamodb.Table(table_name)
    deleted = 0

    # Use ExpressionAttributeNames to handle reserved keywords (e.g. "timestamp")
    proj_aliases = {f'#k{i}': name for i, name in enumerate(key_names)}
    scan_kwargs = {
        'ProjectionExpression': ', '.join(proj_aliases.keys()),
        'ExpressionAttributeNames': proj_aliases,
    }
    alias_to_name = {v: k for k, v in proj_aliases.items()}  # name -> alias (unused)

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


def wipe_s3_prefix(bucket, prefix):
    """Delete all objects under an S3 prefix."""
    deleted = 0
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = page.get('Contents', [])
        if not objects:
            continue
        delete_keys = [{'Key': obj['Key']} for obj in objects]
        # S3 delete_objects max 1000 per call
        for i in range(0, len(delete_keys), 1000):
            batch = delete_keys[i:i+1000]
            s3.delete_objects(Bucket=bucket, Delete={'Objects': batch})
            deleted += len(batch)
    return deleted


def main():
    print("=" * 60)
    print("DEEP CLEAN — WECARE.DIGITAL")
    print("=" * 60)
    total_db = 0
    total_s3 = 0

    # ── 1. Wipe DynamoDB tables ──
    print("\n── DynamoDB Tables ──")
    for table_name, pk in WIPE_TABLES.items():
        t0 = time.time()
        count = wipe_table(table_name, pk)
        elapsed = time.time() - t0
        total_db += count
        print(f"  {table_name}: {count} items deleted ({elapsed:.1f}s)")

    # ── 2. Wipe S3 prefixes ──
    print("\n── S3 Objects ──")
    for prefix in S3_PREFIXES:
        t0 = time.time()
        count = wipe_s3_prefix(BUCKET, prefix)
        elapsed = time.time() - t0
        total_s3 += count
        print(f"  s3://{BUCKET}/{prefix}*: {count} objects deleted ({elapsed:.1f}s)")

    # ── 3. Preserve SystemConfig ──
    print("\n── SystemConfig: PRESERVED (not wiped) ──")
    try:
        cfg_table = dynamodb.Table('base-wecare-digital-SystemConfigTable')
        resp = cfg_table.scan()
        for item in resp.get('Items', []):
            print(f"  kept: {item.get('id', '?')}")
    except Exception as e:
        print(f"  (could not read: {e})")

    print(f"\n{'=' * 60}")
    print(f"DONE: {total_db} DB items + {total_s3} S3 objects deleted")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
