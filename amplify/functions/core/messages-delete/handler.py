"""
Messages Delete Lambda Handler
Deletes messages from WhatsAppInboundTable or WhatsAppOutboundTable
Also deletes associated media files from S3
ONLY deletes messages - does NOT delete contacts
"""

import json
import os
import boto3
from botocore.exceptions import ClientError

# Initialize clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Table names - actual tables used by the system
INBOUND_TABLE = os.environ.get('INBOUND_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')

def handler(event, context):
    """
    Delete a message by ID from the appropriate table.
    Also deletes associated media files from S3.
    ONLY deletes the message - does NOT affect contacts.
    """
    print(f"Event: {json.dumps(event)}")
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'DELETE,PUT,PATCH,OPTIONS'
    }
    
    # Handle OPTIONS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    # ── PATCH/PUT: Update payment/invoice fields ──
    http_method = event.get('httpMethod', 'DELETE').upper()
    if http_method in ('PUT', 'PATCH'):
        return _handle_update(event, headers)
    
    try:
        # Get message ID from path
        path_params = event.get('pathParameters', {}) or {}
        message_id = path_params.get('messageId')
        
        if not message_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'messageId is required'})
            }
        
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
        
        # First, get the message to check for s3Key
        s3_key = None
        try:
            response = table.get_item(Key={'id': message_id})
            item = response.get('Item')
            if item:
                s3_key = item.get('s3Key')
                print(f"Found message {message_id}, s3Key: {s3_key}")
        except ClientError as e:
            # Try with 'messageId' key if 'id' fails
            if 'ValidationException' in str(e):
                try:
                    response = table.get_item(Key={'messageId': message_id})
                    item = response.get('Item')
                    if item:
                        s3_key = item.get('s3Key')
                except ClientError as inner_e:
                    logger.warning(f"Failed to get message with messageId key: {str(inner_e)}")
                except Exception as inner_e:
                    logger.warning(f"Unexpected error getting message: {str(inner_e)}")
        
        # Delete media from S3 if exists
        media_deleted = False
        if delete_media and s3_key:
            try:
                # The s3Key might have a suffix appended by AWS EUM
                # Try to find and delete the actual file
                actual_key = _find_and_delete_s3_file(s3_key, message_id)
                if actual_key:
                    media_deleted = True
                    print(f"Deleted S3 file: {actual_key}")
            except Exception as e:
                print(f"Warning: Failed to delete S3 file {s3_key}: {e}")
                # Continue with DynamoDB deletion even if S3 fails
        
        # Delete the message from DynamoDB
        try:
            table.delete_item(Key={'id': message_id})
            print(f"Deleted message {message_id} from {table_name}")
        except ClientError as e:
            # Try with 'messageId' key if 'id' fails
            if 'ValidationException' in str(e):
                table.delete_item(Key={'messageId': message_id})
                print(f"Deleted message {message_id} from {table_name} using messageId key")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'messageId': message_id,
                'table': table_name,
                'mediaDeleted': media_deleted,
                's3Key': s3_key,
                'message': f'Message deleted successfully{" (media also deleted)" if media_deleted else ""}'
            })
        }
        
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Database error: {str(e)}'})
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }


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
            print(f"Deleted S3 file with prefix match: {actual_key}")
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
        
        print(f"S3 file not found for key: {stored_key}")
        return None
        
    except Exception as e:
        print(f"Error finding/deleting S3 file: {e}")
        raise


def _handle_update(event, headers):
    """Update editable fields on a payment/invoice record."""
    try:
        path_params = event.get('pathParameters', {}) or {}
        message_id = path_params.get('messageId')
        if not message_id:
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'messageId required'})}

        body = json.loads(event.get('body', '{}'))
        # Allowed editable fields
        ALLOWED = {
            'paymentItemName', 'paymentQuantity', 'paymentGstRate',
            'paymentPurpose', 'paymentDueRef', 'status',
            'paymentDiscount', 'paymentShipping',
        }
        updates = {k: v for k, v in body.items() if k in ALLOWED}
        if not updates:
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'No valid fields to update'})}

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

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'success': True, 'messageId': message_id, 'updated': list(updates.keys())})
        }
    except Exception as e:
        print(f"Update error: {e}")
        return {'statusCode': 500, 'headers': headers, 'body': json.dumps({'error': str(e)})}
