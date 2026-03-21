"""
Scheduled Messages Lambda Function
Manages scheduled template messages with CRUD operations and scheduled sending

Routes:
- GET /messages/scheduled - List scheduled messages
- POST /messages/scheduled - Create scheduled message
- PUT /messages/scheduled/{scheduledId} - Update scheduled message
- DELETE /messages/scheduled/{scheduledId} - Cancel scheduled message

Also handles CloudWatch Events trigger for sending due messages.
"""

import os
import json
import logging
import uuid
import boto3
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

from lambda_utils.logging import get_logger

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

SCHEDULED_TABLE = os.environ.get('SCHEDULED_TABLE', 'stack-wecare-digital-ScheduledMessagesTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
OUTBOUND_LAMBDA = os.environ.get('OUTBOUND_LAMBDA', 'wecare-outbound-whatsapp')

# CORS headers provided by lambda_utils.response.cors_headers(origin)

# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for scheduled messages."""
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)
    
    # Check if this is a CloudWatch Events trigger (scheduled execution)
    if event.get('source') == 'aws.events' or event.get('detail-type') == 'Scheduled Event':
        return _process_due_messages(request_id)
    
    # Handle API Gateway requests
    request_context = event.get('requestContext', {})
    if 'http' in request_context:
        http_method = request_context.get('http', {}).get('method', 'GET')
        path = request_context.get('http', {}).get('path', '') or event.get('rawPath', '')
    else:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
    
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({'event': 'scheduled_request', 'method': http_method, 'path': path}))
    
    if http_method == 'OPTIONS':
        return options_response(origin)

    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        
        if http_method == 'GET':
            return _list_scheduled(query_params, request_id)
        
        elif http_method == 'POST':
            return _create_scheduled(body, request_id)
        
        elif http_method == 'PUT':
            scheduled_id = path_params.get('scheduledId') or path.split('/')[-1]
            return _update_scheduled(scheduled_id, body, request_id)
        
        elif http_method == 'DELETE':
            scheduled_id = path_params.get('scheduledId') or path.split('/')[-1]
            return _cancel_scheduled(scheduled_id, request_id)
        
        return _error_response(400, 'Invalid request method')
    except Exception as e:
        logger.error(f'Scheduled messages error: {str(e)}')
        return _error_response(500, str(e))


def _list_scheduled(query_params: Dict[str, str], request_id: str) -> Dict[str, Any]:
    """List scheduled messages, optionally filtered by status."""
    table = dynamodb.Table(SCHEDULED_TABLE)
    status_filter = query_params.get('status', 'PENDING')
    
    try:
        if status_filter:
            # Query by status using GSI — paginate fully
            items = []
            query_kwargs = {
                'IndexName': 'status-scheduledAt-index',
                'KeyConditionExpression': '#status = :status',
                'ExpressionAttributeNames': {'#status': 'status'},
                'ExpressionAttributeValues': {':status': status_filter},
                'ScanIndexForward': True  # Oldest first
            }
            while True:
                response = table.query(**query_kwargs)
                items.extend(response.get('Items', []))
                if 'LastEvaluatedKey' not in response:
                    break
                query_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        else:
            # Scan all — paginate fully
            items = []
            scan_kwargs = {}
            while True:
                response = table.scan(**scan_kwargs)
                items.extend(response.get('Items', []))
                if 'LastEvaluatedKey' not in response:
                    break
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        
        # Convert Decimal to int/float for JSON serialization
        scheduled_messages = []
        for item in items:
            scheduled_messages.append(_normalize_item(item))
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'scheduledMessages': scheduled_messages,
                'count': len(scheduled_messages)
            })
        }
    except Exception as e:
        logger.error(f'List scheduled error: {str(e)}')
        return _error_response(500, f'Failed to list scheduled messages: {str(e)}')


def _create_scheduled(body: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """Create a new scheduled message."""
    table = dynamodb.Table(SCHEDULED_TABLE)
    contacts_table = dynamodb.Table(CONTACTS_TABLE)
    
    # Validate required fields
    contact_id = body.get('contactId')
    template_name = body.get('templateName')
    scheduled_at = body.get('scheduledAt')
    
    if not contact_id:
        return _error_response(400, 'contactId is required')
    if not template_name:
        return _error_response(400, 'templateName is required')
    if not scheduled_at:
        return _error_response(400, 'scheduledAt is required')
    
    # Validate scheduled time is in the future
    try:
        scheduled_dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        if scheduled_dt <= datetime.now(timezone.utc):
            return _error_response(400, 'scheduledAt must be in the future')
    except ValueError:
        return _error_response(400, 'Invalid scheduledAt format. Use ISO 8601.')
    
    # Get contact details
    contact_name = None
    contact_phone = None
    try:
        contact_response = contacts_table.get_item(Key={'id': contact_id})
        if 'Item' in contact_response:
            contact = contact_response['Item']
            contact_name = contact.get('name', '')
            contact_phone = contact.get('phone', '')
    except Exception as e:
        logger.warning(f'Could not fetch contact: {str(e)}')
    
    # Create scheduled message
    scheduled_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    item = {
        'id': scheduled_id,
        'scheduledId': scheduled_id,
        'contactId': contact_id,
        'contactName': contact_name or '',
        'contactPhone': contact_phone or '',
        'recipientBsuid': body.get('recipientBsuid', ''),
        'templateName': template_name,
        'templateParams': body.get('templateParams', []),
        'phoneNumberId': body.get('phoneNumberId', ''),
        'scheduledAt': scheduled_at,
        'status': 'PENDING',
        'createdAt': now,
        'updatedAt': now
    }
    
    try:
        table.put_item(Item=item)
        logger.info(f'Created scheduled message: {scheduled_id}')
        
        return {
            'statusCode': 201,
            'headers': cors_headers(origin),
            'body': json.dumps(_normalize_item(item))
        }
    except Exception as e:
        logger.error(f'Create scheduled error: {str(e)}')
        return _error_response(500, f'Failed to create scheduled message: {str(e)}')


def _update_scheduled(scheduled_id: str, body: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """Update a scheduled message (only PENDING messages can be updated)."""
    table = dynamodb.Table(SCHEDULED_TABLE)
    
    if not scheduled_id:
        return _error_response(400, 'scheduledId is required')
    
    # Get existing item
    try:
        response = table.get_item(Key={'id': scheduled_id})
        if 'Item' not in response:
            return _error_response(404, 'Scheduled message not found')
        
        existing = response['Item']
        if existing.get('status') != 'PENDING':
            return _error_response(400, 'Only PENDING messages can be updated')
    except Exception as e:
        return _error_response(500, f'Failed to fetch scheduled message: {str(e)}')
    
    # Build update expression
    update_parts = []
    expr_names = {}
    expr_values = {}
    
    if 'scheduledAt' in body:
        # Validate new scheduled time
        try:
            scheduled_dt = datetime.fromisoformat(body['scheduledAt'].replace('Z', '+00:00'))
            if scheduled_dt <= datetime.now(timezone.utc):
                return _error_response(400, 'scheduledAt must be in the future')
        except ValueError:
            return _error_response(400, 'Invalid scheduledAt format')
        
        update_parts.append('#scheduledAt = :scheduledAt')
        expr_names['#scheduledAt'] = 'scheduledAt'
        expr_values[':scheduledAt'] = body['scheduledAt']
    
    if 'templateParams' in body:
        update_parts.append('#templateParams = :templateParams')
        expr_names['#templateParams'] = 'templateParams'
        expr_values[':templateParams'] = body['templateParams']
    
    if not update_parts:
        return _error_response(400, 'No valid fields to update')
    
    # Add updatedAt
    update_parts.append('#updatedAt = :updatedAt')
    expr_names['#updatedAt'] = 'updatedAt'
    expr_values[':updatedAt'] = datetime.now(timezone.utc).isoformat()
    
    try:
        response = table.update_item(
            Key={'id': scheduled_id},
            UpdateExpression='SET ' + ', '.join(update_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues='ALL_NEW'
        )
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(_normalize_item(response['Attributes']))
        }
    except Exception as e:
        logger.error(f'Update scheduled error: {str(e)}')
        return _error_response(500, f'Failed to update scheduled message: {str(e)}')


def _cancel_scheduled(scheduled_id: str, request_id: str) -> Dict[str, Any]:
    """Cancel a scheduled message."""
    table = dynamodb.Table(SCHEDULED_TABLE)
    
    if not scheduled_id:
        return _error_response(400, 'scheduledId is required')
    
    try:
        # Get existing item
        response = table.get_item(Key={'id': scheduled_id})
        if 'Item' not in response:
            return _error_response(404, 'Scheduled message not found')
        
        existing = response['Item']
        if existing.get('status') != 'PENDING':
            return _error_response(400, 'Only PENDING messages can be cancelled')
        
        # Update status to CANCELLED
        now = datetime.now(timezone.utc).isoformat()
        table.update_item(
            Key={'id': scheduled_id},
            UpdateExpression='SET #status = :status, #updatedAt = :updatedAt',
            ExpressionAttributeNames={'#status': 'status', '#updatedAt': 'updatedAt'},
            ExpressionAttributeValues={':status': 'CANCELLED', ':updatedAt': now}
        )
        
        logger.info(f'Cancelled scheduled message: {scheduled_id}')
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({'success': True, 'scheduledId': scheduled_id, 'status': 'CANCELLED'})
        }
    except Exception as e:
        logger.error(f'Cancel scheduled error: {str(e)}')
        return _error_response(500, f'Failed to cancel scheduled message: {str(e)}')


def _process_due_messages(request_id: str) -> Dict[str, Any]:
    """Process messages that are due to be sent (called by CloudWatch Events)."""
    table = dynamodb.Table(SCHEDULED_TABLE)
    now = datetime.now(timezone.utc).isoformat()
    
    logger.info(f'Processing due messages at {now}')
    
    try:
        # Query PENDING messages where scheduledAt <= now — paginate fully
        items = []
        query_kwargs = {
            'IndexName': 'status-scheduledAt-index',
            'KeyConditionExpression': '#status = :status AND #scheduledAt <= :now',
            'ExpressionAttributeNames': {'#status': 'status', '#scheduledAt': 'scheduledAt'},
            'ExpressionAttributeValues': {':status': 'PENDING', ':now': now},
            'Limit': 50  # Process up to 50 at a time
        }
        response = table.query(**query_kwargs)
        items = response.get('Items', [])
        # For due messages, we cap at 50 per invocation (Limit applies to evaluated items)
        while 'LastEvaluatedKey' in response and len(items) < 50:
            query_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = table.query(**query_kwargs)
            items.extend(response.get('Items', []))
        items = items[:50]
        
        logger.info(f'Found {len(items)} due messages')
        
        sent_count = 0
        failed_count = 0
        
        for item in items:
            scheduled_id = item['scheduledId']
            
            try:
                # Send the message via outbound Lambda
                payload = {
                    'body': json.dumps({
                        'contactId': item['contactId'],
                        'isTemplate': True,
                        'templateName': item['templateName'],
                        'templateParams': item.get('templateParams', []),
                        'phoneNumberId': item.get('phoneNumberId', ''),
                        'recipientBsuid': item.get('recipientBsuid', ''),
                    })
                }
                
                response = lambda_client.invoke(
                    FunctionName=OUTBOUND_LAMBDA,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )
                
                result = json.loads(response['Payload'].read())
                
                if response.get('StatusCode') == 200 and result.get('statusCode') in [200, 201]:
                    # Mark as SENT
                    table.update_item(
                        Key={'id': scheduled_id},
                        UpdateExpression='SET #status = :status, #sentAt = :sentAt, #updatedAt = :updatedAt',
                        ExpressionAttributeNames={
                            '#status': 'status',
                            '#sentAt': 'sentAt',
                            '#updatedAt': 'updatedAt'
                        },
                        ExpressionAttributeValues={
                            ':status': 'SENT',
                            ':sentAt': now,
                            ':updatedAt': now
                        }
                    )
                    sent_count += 1
                    logger.info(f'Sent scheduled message: {scheduled_id}')
                else:
                    # Mark as FAILED
                    error_msg = result.get('body', 'Unknown error')
                    table.update_item(
                        Key={'id': scheduled_id},
                        UpdateExpression='SET #status = :status, #errorMessage = :error, #updatedAt = :updatedAt',
                        ExpressionAttributeNames={
                            '#status': 'status',
                            '#errorMessage': 'errorMessage',
                            '#updatedAt': 'updatedAt'
                        },
                        ExpressionAttributeValues={
                            ':status': 'FAILED',
                            ':error': str(error_msg)[:500],
                            ':updatedAt': now
                        }
                    )
                    failed_count += 1
                    logger.error(f'Failed to send scheduled message {scheduled_id}: {error_msg}')
                    
            except Exception as e:
                # Mark as FAILED
                table.update_item(
                    Key={'id': scheduled_id},
                    UpdateExpression='SET #status = :status, #errorMessage = :error, #updatedAt = :updatedAt',
                    ExpressionAttributeNames={
                        '#status': 'status',
                        '#errorMessage': 'errorMessage',
                        '#updatedAt': 'updatedAt'
                    },
                    ExpressionAttributeValues={
                        ':status': 'FAILED',
                        ':error': str(e)[:500],
                        ':updatedAt': now
                    }
                )
                failed_count += 1
                logger.error(f'Exception sending scheduled message {scheduled_id}: {str(e)}')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed': len(items),
                'sent': sent_count,
                'failed': failed_count
            })
        }
    except Exception as e:
        logger.error(f'Process due messages error: {str(e)}')
        return {'statusCode': 500, 'headers': cors_headers(origin), 'body': json.dumps({'error': str(e)})}


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DynamoDB item to JSON-serializable format."""
    result = {}
    for key, value in item.items():
        if isinstance(value, Decimal):
            result[key] = int(value) if value % 1 == 0 else float(value)
        else:
            result[key] = value
    
    # Ensure id field exists for frontend compatibility
    if 'scheduledId' in result and 'id' not in result:
        result['id'] = result['scheduledId']
    
    return result


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Return error response."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps({'error': message})
    }
