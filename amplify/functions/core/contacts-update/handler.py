"""
Contacts Update Lambda Function

Purpose: Update contact information
"""

import os
import json
import time
import logging
import boto3
import re
from typing import Dict, Any, List
from decimal import Decimal
from boto3.dynamodb.conditions import Attr

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'Contact')

# Allowed update fields
ALLOWED_FIELDS = {'name', 'phone', 'email', 'shippingAddress', 'billingAddress', 'optInWhatsApp', 'optInSms', 'optInEmail', 'allowlistWhatsApp', 'allowlistSms', 'allowlistEmail'}
OPT_IN_FIELDS = {'optInWhatsApp', 'optInSms', 'optInEmail', 'allowlistWhatsApp', 'allowlistSms', 'allowlistEmail'}

# CORS headers
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update contact record."""
    request_id = context.aws_request_id if context else 'local'
    
    try:
        # Extract contactId from path parameters
        path_params = event.get('pathParameters', {}) or {}
        contact_id = path_params.get('contactId')
        
        if not contact_id:
            return _error_response(400, 'contactId is required')
        
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        if not body:
            return _error_response(400, 'Request body is required')
        
        # Filter to allowed fields only (exclude key attributes)
        updates = {k: v for k, v in body.items() if k in ALLOWED_FIELDS and k not in ('id', 'contactId')}
        
        logger.info(json.dumps({
            'event': 'contact_update_debug',
            'contactId': contact_id,
            'bodyKeys': list(body.keys()),
            'updateKeys': list(updates.keys()),
            'requestId': request_id,
        }))
        
        if not updates:
            return _error_response(400, 'No valid fields to update')
        
        # Validate opt-in changes are explicit booleans
        for field in OPT_IN_FIELDS:
            if field in updates:
                if not isinstance(updates[field], bool):
                    return _error_response(400, f'{field} must be a boolean value')
        
        # Validate phone/email if provided
        if 'phone' in updates and updates['phone']:
            if not _validate_phone(updates['phone']):
                return _error_response(400, 'Invalid phone number format')
        
        if 'email' in updates and updates['email']:
            updates['email'] = updates['email'].strip().lower()
            if not _validate_email(updates['email']):
                return _error_response(400, 'Invalid email format')
        
        # Add updatedAt timestamp
        updates['updatedAt'] = int(time.time())
        
        # Build update expression
        update_expr, expr_names, expr_values = _build_update_expression(updates)
        
        # Update in DynamoDB
        table = dynamodb.Table(CONTACTS_TABLE)
        
        try:
            response = table.update_item(
                Key={'id': contact_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ReturnValues='ALL_NEW'
            )
        except Exception as update_err:
            error_msg = str(update_err)
            if 'ConditionalCheckFailedException' in error_msg:
                return _error_response(404, 'Contact not found or has been deleted')
            raise update_err
        
        updated_contact = response.get('Attributes', {})
        
        logger.info(json.dumps({
            'event': 'contact_updated',
            'contactId': contact_id,
            'updatedFields': list(updates.keys()),
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps(_convert_from_dynamodb(updated_contact)),
        }
        
    except json.JSONDecodeError:
        return _error_response(400, 'Invalid JSON in request body')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'contact_update_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Internal server error: {str(e)}')


def _build_update_expression(updates: Dict[str, Any]) -> tuple:
    """Build DynamoDB update expression."""
    set_parts: List[str] = []
    expr_names: Dict[str, str] = {}
    expr_values: Dict[str, Any] = {}
    
    for i, (key, value) in enumerate(updates.items()):
        name_placeholder = f'#n{i}'
        value_placeholder = f':v{i}'
        
        set_parts.append(f'{name_placeholder} = {value_placeholder}')
        expr_names[name_placeholder] = key
        
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            expr_values[value_placeholder] = Decimal(str(value))
        else:
            expr_values[value_placeholder] = value
    
    update_expr = 'SET ' + ', '.join(set_parts)
    return update_expr, expr_names, expr_values


def _validate_phone(phone: str) -> bool:
    """Validate phone number format - accepts international formats."""
    # Allow: +919330994400, +91 93309 94400, (91) 93309-94400, etc.
    pattern = r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}[-\s\.]?[0-9]{0,9}$'
    return bool(re.match(pattern, phone.replace(' ', '')))


def _validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _convert_from_dynamodb(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DynamoDB types to Python types."""
    result = {}
    for key, value in item.items():
        if isinstance(value, Decimal):
            result[key] = int(value) if value % 1 == 0 else float(value)
        else:
            result[key] = value
    return result


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Return error response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps({'error': message}),
    }
