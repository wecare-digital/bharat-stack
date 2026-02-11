"""
Contacts Delete Lambda Function

Purpose: Soft delete contact OR hard delete (contact + messages + media)
Requirements: 2.5

Soft delete: Sets deletedAt timestamp (default)
Hard delete: Removes contact, all messages, and media from S3
"""

import os
import json
import time
import logging
import boto3
from typing import Dict, Any, List
from decimal import Decimal
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Table names
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'Contact')
INBOUND_TABLE = os.environ.get('INBOUND_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Delete contact - supports soft delete (default) or hard delete.
    
    Query params:
    - hard=true: Hard delete (removes contact, messages, and media)
    - hard=false or omitted: Soft delete (sets deletedAt timestamp)
    """
    request_id = context.aws_request_id if context else 'local'
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }
    
    try:
        # Extract contactId from path parameters
        path_params = event.get('pathParameters', {}) or {}
        contact_id = path_params.get('contactId')
        
        if not contact_id:
            return _error_response(400, 'contactId is required')
        
        # Check if hard delete is requested
        query_params = event.get('queryStringParameters', {}) or {}
        is_hard_delete = query_params.get('hard', 'false').lower() == 'true'
        
        if is_hard_delete:
            return _hard_delete_contact(contact_id, request_id, headers)
        else:
            return _soft_delete_contact(contact_id, request_id, headers)
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'contact_delete_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, 'Internal server error')


def _soft_delete_contact(contact_id: str, request_id: str, headers: Dict) -> Dict[str, Any]:
    """Soft delete contact by setting deletedAt timestamp."""
    deleted_at = int(time.time())
    table = dynamodb.Table(CONTACTS_TABLE)
    
    try:
        # First check if contact exists
        get_response = table.get_item(Key={'id': contact_id})
        item = get_response.get('Item')
        
        # If not found by id, try scanning by contactId field
        if not item:
            scan_response = table.scan(
                FilterExpression='contactId = :cid',
                ExpressionAttributeValues={':cid': contact_id},
                Limit=1
            )
            items = scan_response.get('Items', [])
            if items:
                item = items[0]
                contact_id = item.get('id', contact_id)
        
        if not item:
            return _error_response(404, 'Contact not found')
        
        if item.get('deletedAt') is not None:
            return _error_response(404, 'Contact already deleted')
        
        # Perform soft delete
        table.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET #deletedAt = :deletedAt, #updatedAt = :updatedAt',
            ExpressionAttributeNames={
                '#deletedAt': 'deletedAt',
                '#updatedAt': 'updatedAt'
            },
            ExpressionAttributeValues={
                ':deletedAt': Decimal(str(deleted_at)),
                ':updatedAt': Decimal(str(deleted_at))
            }
        )
        
        logger.info(json.dumps({
            'event': 'contact_soft_deleted',
            'contactId': contact_id,
            'deletedAt': deleted_at,
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'contactId': contact_id,
                'deletedAt': deleted_at,
                'deleteType': 'soft',
                'message': 'Contact soft deleted successfully'
            }),
        }
        
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return _error_response(404, 'Contact not found or already deleted')


def _hard_delete_contact(contact_id: str, request_id: str, headers: Dict) -> Dict[str, Any]:
    """
    Hard delete: Remove contact, all messages, and media from S3.
    This is irreversible!
    """
    results = {
        'contactDeleted': False,
        'messagesDeleted': 0,
        'mediaDeleted': 0,
        's3Keys': []
    }
    
    try:
        # Step 1: Find and delete all messages for this contact
        messages = _get_contact_messages(contact_id)
        logger.info(f"Found {len(messages)} messages for contact {contact_id}")
        
        for msg in messages:
            # Delete media from S3 if exists
            s3_key = msg.get('s3Key')
            if s3_key:
                try:
                    _delete_s3_file(s3_key)
                    results['mediaDeleted'] += 1
                    results['s3Keys'].append(s3_key)
                except Exception as e:
                    logger.warning(f"Failed to delete S3 file {s3_key}: {e}")
            
            # Delete message from DynamoDB
            direction = msg.get('direction', 'inbound').upper()
            table_name = OUTBOUND_TABLE if direction == 'OUTBOUND' else INBOUND_TABLE
            table = dynamodb.Table(table_name)
            
            try:
                msg_id = msg.get('id') or msg.get('messageId')
                table.delete_item(Key={'id': msg_id})
                results['messagesDeleted'] += 1
            except Exception as e:
                logger.warning(f"Failed to delete message {msg.get('id')}: {e}")
        
        # Step 2: Delete the contact
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        try:
            contacts_table.delete_item(Key={'id': contact_id})
            results['contactDeleted'] = True
        except Exception as e:
            logger.warning(f"Failed to delete contact {contact_id}: {e}")
        
        logger.info(json.dumps({
            'event': 'contact_hard_deleted',
            'contactId': contact_id,
            'results': results,
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'contactId': contact_id,
                'deleteType': 'hard',
                'messagesDeleted': results['messagesDeleted'],
                'mediaDeleted': results['mediaDeleted'],
                'message': f"Hard deleted: contact, {results['messagesDeleted']} messages, {results['mediaDeleted']} media files"
            }),
        }
        
    except Exception as e:
        logger.error(f"Hard delete error: {e}")
        return _error_response(500, f'Hard delete failed: {str(e)}')


def _get_contact_messages(contact_id: str) -> List[Dict]:
    """Get all messages for a contact from both inbound and outbound tables."""
    messages = []
    
    for table_name, direction in [(INBOUND_TABLE, 'inbound'), (OUTBOUND_TABLE, 'outbound')]:
        try:
            table = dynamodb.Table(table_name)
            response = table.scan(
                FilterExpression='contactId = :cid',
                ExpressionAttributeValues={':cid': contact_id}
            )
            items = response.get('Items', [])
            for item in items:
                item['direction'] = direction
            messages.extend(items)
        except Exception as e:
            logger.warning(f"Error scanning {table_name}: {e}")
    
    return messages


def _delete_s3_file(stored_key: str) -> bool:
    """Delete file from S3, handling the AWS EUM suffix issue."""
    try:
        # Try exact key first
        try:
            s3_client.head_object(Bucket=MEDIA_BUCKET, Key=stored_key)
            s3_client.delete_object(Bucket=MEDIA_BUCKET, Key=stored_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise
        
        # Search with prefix
        if '.' in stored_key:
            base_prefix = stored_key.rsplit('.', 1)[0]
        else:
            base_prefix = stored_key
        
        response = s3_client.list_objects_v2(
            Bucket=MEDIA_BUCKET,
            Prefix=base_prefix,
            MaxKeys=5
        )
        
        for obj in response.get('Contents', []):
            s3_client.delete_object(Bucket=MEDIA_BUCKET, Key=obj['Key'])
            logger.info(f"Deleted S3 file: {obj['Key']}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"S3 delete error: {e}")
        raise


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Return error response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps({'error': message}),
    }
