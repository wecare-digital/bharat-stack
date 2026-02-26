"""
Messages Delete Lambda Handler
Deletes messages from WhatsAppInboundTable or WhatsAppOutboundTable
Also deletes associated media files from S3
ONLY deletes messages - does NOT delete contacts
"""

import json
import os
import logging
import boto3
from botocore.exceptions import ClientError

from lambda_utils.response import cors_response, options_response, extract_origin
from lambda_utils.logging import get_logger, log_event

logger = get_logger(__name__)

# Initialize clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
dynamodb_client = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Table names - actual tables used by the system
INBOUND_TABLE = os.environ.get('INBOUND_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
INBOUND_WHATSAPP_FUNCTION = os.environ.get('INBOUND_WHATSAPP_FUNCTION', 'wecare-inbound-whatsapp')

# Cache key schemas to avoid repeated describe_table calls
_key_schema_cache = {}

def _get_key_schema(table_name):
    """Get the key schema for a DynamoDB table (cached)."""
    if table_name not in _key_schema_cache:
        try:
            desc = dynamodb_client.describe_table(TableName=table_name)
            _key_schema_cache[table_name] = desc['Table']['KeySchema']
        except Exception:
            _key_schema_cache[table_name] = [{'AttributeName': 'id', 'KeyType': 'HASH'}]
    return _key_schema_cache[table_name]

def _build_delete_key(table_name, item):
    """Build the correct Key dict for delete_item based on actual table key schema."""
    schema = _get_key_schema(table_name)
    key = {}
    for ks in schema:
        attr = ks['AttributeName']
        if attr in item:
            key[attr] = item[attr]
        elif attr == 'id' and 'messageId' in item:
            key[attr] = item['messageId']
        elif attr == 'messageId' and 'id' in item:
            key[attr] = item['id']
    return key

def handler(event, context):
    """
    Delete a message by ID from the appropriate table.
    Also deletes associated media files from S3.
    ONLY deletes the message - does NOT affect contacts.
    """
    origin = extract_origin(event)
    
    # Handle OPTIONS preflight
    rc = event.get('requestContext', {})
    evt_method = rc.get('http', {}).get('method', event.get('httpMethod', ''))
    if evt_method == 'OPTIONS':
        return options_response(origin)

    # Support both API Gateway v1 (REST) and v2 (HTTP) event formats
    request_context = event.get('requestContext', {})
    if 'http' in request_context:
        http_method = request_context['http'].get('method', 'DELETE').upper()
        path = request_context['http'].get('path', '')
    else:
        http_method = event.get('httpMethod', 'DELETE').upper()
        path = event.get('path', '')
    if not path:
        path = event.get('rawPath', '')

    # ── DELETE /messages/clear-all — bulk wipe both tables ──
    if http_method == 'DELETE' and 'clear-all' in path:
        return _handle_clear_all(origin)

    # ── POST /messages/clear-all — alternative POST route ──
    if http_method == 'POST' and 'clear-all' in path:
        return _handle_clear_all(origin)

    # ── PATCH/PUT: Update payment/invoice fields ──
    if http_method in ('PUT', 'PATCH'):
        return _handle_update(event, origin)

    if http_method == 'POST':
        return _handle_create_invoice(event, origin)
    
    try:
        # Get message ID from path
        path_params = event.get('pathParameters', {}) or {}
        message_id = path_params.get('messageId')
        
        if not message_id:
            return cors_response(400, {'error': 'messageId is required'}, origin)
        
        # Get direction from query params to determine which table
        query_params = event.get('queryStringParameters', {}) or {}
        direction = query_params.get('direction', 'INBOUND').upper()
        
        # Also check if we should delete media (default: yes for hard delete)
        delete_media = query_params.get('deleteMedia', 'true').lower() == 'true'
        
        # Select table based on direction
        if direction == 'OUTBOUND':
            table_name = OUTBOUND_TABLE
        else:
            table_name = INBOUND_TABLE
        
        table = dynamodb.Table(table_name)
        
        # First, get the message to check for s3Key (and get all key attributes)
        s3_key = None
        item = None
        try:
            response = table.get_item(Key={'id': message_id})
            item = response.get('Item')
            if item:
                s3_key = item.get('s3Key')
        except ClientError as e:
            if 'ValidationException' in str(e):
                try:
                    response = table.get_item(Key={'messageId': message_id})
                    item = response.get('Item')
                    if item:
                        s3_key = item.get('s3Key')
                except Exception:
                    pass
            if not item:
                try:
                    resp = table.scan(
                        FilterExpression='id = :mid OR messageId = :mid',
                        ExpressionAttributeValues={':mid': message_id},
                        Limit=1
                    )
                    items = resp.get('Items', [])
                    if items:
                        item = items[0]
                        s3_key = item.get('s3Key')
                except Exception:
                    pass
        
        # Delete media from S3 if exists
        media_deleted = False
        if delete_media and s3_key:
            try:
                actual_key = _find_and_delete_s3_file(s3_key, message_id)
                if actual_key:
                    media_deleted = True
            except Exception:
                pass  # Continue with DynamoDB deletion even if S3 fails
        
        # Delete the message from DynamoDB using proper key schema
        try:
            if item:
                delete_key = _build_delete_key(table_name, item)
                table.delete_item(Key=delete_key)
            else:
                try:
                    table.delete_item(Key={'id': message_id})
                except ClientError:
                    table.delete_item(Key={'messageId': message_id})
        except Exception:
            pass  # Best effort delete

        return cors_response(200, {
            'success': True,
            'messageId': message_id,
            'table': table_name,
            'mediaDeleted': media_deleted,
            's3Key': s3_key,
            'message': f'Message deleted successfully{" (media also deleted)" if media_deleted else ""}'
        }, origin)
        
    except ClientError as e:
        return cors_response(500, {'error': 'Database error'}, origin)
    except Exception as e:
        return cors_response(500, {'error': 'Internal server error'}, origin)


def _handle_clear_all(origin):
    """Bulk wipe ALL messages from both Inbound and Outbound tables."""
    total = 0
    details = {}
    for tbl_name in (INBOUND_TABLE, OUTBOUND_TABLE):
        try:
            schema = _get_key_schema(tbl_name)
            key_names = [k['AttributeName'] for k in schema]
            table = dynamodb.Table(tbl_name)
            tbl_deleted = 0
            while True:
                # Only project key attributes for efficiency
                proj_aliases = {f'#k{i}': name for i, name in enumerate(key_names)}
                resp = table.scan(
                    ProjectionExpression=', '.join(proj_aliases.keys()),
                    ExpressionAttributeNames=proj_aliases,
                )
                items = resp.get('Items', [])
                if not items:
                    break
                with table.batch_writer() as batch:
                    for item in items:
                        key = {k: item[k] for k in key_names if k in item}
                        if key:
                            batch.delete_item(Key=key)
                            tbl_deleted += 1
                if 'LastEvaluatedKey' not in resp:
                    break
            details[tbl_name.split('-')[-1]] = tbl_deleted
            total += tbl_deleted
        except Exception as e:
            details[tbl_name] = f'error: {str(e)}'
    return cors_response(200, {'success': True, 'totalDeleted': total, 'details': details}, origin)


def _find_and_delete_s3_file(stored_key: str, message_id: str) -> str:
    """
    Find and delete the actual S3 file.
    AWS EUM Social API may append WhatsApp media ID to the filename.
    Returns the actual key that was deleted, or None if not found.
    """
    try:
        # First try the exact key
        try:
            s3_client.head_object(Bucket=MEDIA_BUCKET, Key=stored_key)
            s3_client.delete_object(Bucket=MEDIA_BUCKET, Key=stored_key)
            return stored_key
        except ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise
        
        # Key doesn't exist exactly, search with prefix
        if '.' in stored_key:
            base_prefix = stored_key.rsplit('.', 1)[0]
        else:
            base_prefix = stored_key
        
        # List objects with prefix
        response = s3_client.list_objects_v2(
            Bucket=MEDIA_BUCKET,
            Prefix=base_prefix,
            MaxKeys=5
        )
        
        contents = response.get('Contents', [])
        if contents:
            actual_key = contents[0]['Key']
            s3_client.delete_object(Bucket=MEDIA_BUCKET, Key=actual_key)

            return actual_key
        
        # Try with full stored key as prefix
        response = s3_client.list_objects_v2(
            Bucket=MEDIA_BUCKET,
            Prefix=stored_key,
            MaxKeys=5
        )
        
        contents = response.get('Contents', [])
        if contents:
            actual_key = contents[0]['Key']
            s3_client.delete_object(Bucket=MEDIA_BUCKET, Key=actual_key)
            return actual_key
        
        return None
        
    except Exception as e:
        raise


def _handle_update(event, origin):
    """Update editable fields on a payment/invoice record."""
    try:
        path_params = event.get('pathParameters', {}) or {}
        message_id = path_params.get('messageId')
        if not message_id:
            return cors_response(400, {'error': 'messageId required'}, origin)

        body = json.loads(event.get('body', '{}'))
        # Allowed editable fields
        ALLOWED = {
            'paymentItemName', 'paymentQuantity', 'paymentGstRate',
            'paymentPurpose', 'paymentDueRef', 'status',
            'paymentDiscount', 'paymentShipping',
            'paymentOrderId', 'paymentCustomerName', 'paymentCustomerPhone',
            'paymentCustomerEmail', 'paymentShippingAddress', 'paymentBillingAddress',
            'paymentPayFor',
        }
        updates = {k: v for k, v in body.items() if k in ALLOWED}
        if not updates:
            return cors_response(400, {'error': 'No valid fields to update'}, origin)

        table = dynamodb.Table(INBOUND_TABLE)
        expr_parts = []
        attr_names = {}
        attr_values = {}
        for i, (k, v) in enumerate(updates.items()):
            alias = f'#f{i}'
            val_alias = f':v{i}'
            expr_parts.append(f'{alias} = {val_alias}')
            attr_names[alias] = k
            attr_values[val_alias] = v

        table.update_item(
            Key={'id': message_id},
            UpdateExpression='SET ' + ', '.join(expr_parts),
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
        )

        return cors_response(200, {'success': True, 'messageId': message_id, 'updated': list(updates.keys())}, origin)
    except Exception as e:
        return cors_response(500, {'error': 'Internal server error'}, origin)


def _handle_create_invoice(event, origin):
    """Create an invoice from dashboard — invokes inbound-whatsapp handler to generate & send."""
    try:
        body = json.loads(event.get('body', '{}'))

        # Required fields
        contact_id = body.get('contactId', '')
        item_name = body.get('itemName', '')
        unit_price = float(body.get('unitPrice', 0))
        quantity = int(body.get('quantity', 1))

        if not contact_id or not item_name or unit_price <= 0:
            return cors_response(400, {'error': 'contactId, itemName, and unitPrice > 0 are required'}, origin)

        # Optional fields with defaults
        gst_rate = float(body.get('gstRate', 18))
        shipping = float(body.get('shipping', 49))
        discount = float(body.get('discount', 15))
        purpose = body.get('purpose', '')
        order_id = body.get('orderId', 'Offline')
        customer_name = body.get('customerName', '')
        customer_phone = body.get('customerPhone', '')
        customer_email = body.get('customerEmail', '')
        shipping_address = body.get('shippingAddress', '')
        billing_address = body.get('billingAddress', '')
        phone_number_id = body.get('phoneNumberId', '919330994400')

        # Invoke inbound-whatsapp handler with a special "create_invoice" action
        invoke_payload = {
            'action': 'create_invoice',
            'contactId': contact_id,
            'phoneNumberId': phone_number_id,
            'itemName': item_name,
            'unitPrice': unit_price,
            'quantity': quantity,
            'gstRate': gst_rate,
            'shipping': shipping,
            'discount': discount,
            'purpose': purpose,
            'orderId': order_id,
            'customerName': customer_name,
            'customerPhone': customer_phone,
            'customerEmail': customer_email,
            'shippingAddress': shipping_address,
            'billingAddress': billing_address,
            'senderPhone': customer_phone or contact_id,
        }

        response = lambda_client.invoke(
            FunctionName=INBOUND_WHATSAPP_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps(invoke_payload),
        )

        result_payload = json.loads(response['Payload'].read().decode('utf-8'))


        return cors_response(200, {
            'success': True,
            'message': 'Invoice created and sent via WhatsApp',
            'result': result_payload,
        }, origin)

    except Exception as e:
        return cors_response(500, {'error': 'Internal server error'}, origin)
