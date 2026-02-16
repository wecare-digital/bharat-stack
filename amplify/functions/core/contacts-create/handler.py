"""
Contacts Create Lambda Function

Purpose: Create new contact with opt-in defaults
All opt-ins enabled by default for production.
"""

import os
import json
import uuid
import time
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal
import re

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'Contact')

# CORS headers
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a new contact record."""
    request_id = context.aws_request_id if context else 'local'
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Validate at least phone or email
        phone = body.get('phone', '').strip() if body.get('phone') else None
        email = body.get('email', '').strip().lower() if body.get('email') else None
        
        if not phone and not email:
            return _error_response(400, 'At least one of phone or email is required')
        
        # Validate phone format if provided
        if phone and not _validate_phone(phone):
            return _error_response(400, 'Invalid phone number format')
        
        # Validate email format if provided
        if email and not _validate_email(email):
            return _error_response(400, 'Invalid email format')
        
        # Generate contact ID and timestamps
        contact_id = str(uuid.uuid4())
        now = int(time.time())
        
        # Create contact with all opt-ins enabled by default
        contact = {
            'id': contact_id,
            'contactId': contact_id,
            'name': body.get('name', '').strip(),
            'phone': phone,
            'email': email,
            'shippingAddress': body.get('shippingAddress', '').strip() if body.get('shippingAddress') else None,
            'billingAddress': body.get('billingAddress', '').strip() if body.get('billingAddress') else None,
            'optInWhatsApp': True,
            'optInSms': True,
            'optInEmail': True,
            'allowlistWhatsApp': True,
            'allowlistSms': True,
            'allowlistEmail': True,
            'lastInboundMessageAt': None,
            'createdAt': now,
            'updatedAt': now,
            'deletedAt': None,
        }
        
        # Store in DynamoDB
        table = dynamodb.Table(CONTACTS_TABLE)
        table.put_item(Item=_convert_to_dynamodb(contact))
        
        logger.info(json.dumps({
            'event': 'contact_created',
            'contactId': contact_id,
            'hasPhone': bool(phone),
            'hasEmail': bool(email),
            'requestId': request_id
        }))
        
        return {
            'statusCode': 201,
            'headers': CORS_HEADERS,
            'body': json.dumps(_convert_from_dynamodb(contact)),
        }
        
    except json.JSONDecodeError:
        return _error_response(400, 'Invalid JSON in request body')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'contact_create_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Internal server error: {str(e)}')


def _validate_phone(phone: str) -> bool:
    """Validate phone number format - accepts international formats."""
    # Allow: +919330994400, +91 93309 94400, (91) 93309-94400, etc.
    pattern = r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}[-\s\.]?[0-9]{0,9}$'
    return bool(re.match(pattern, phone.replace(' ', '')))


def _validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _convert_to_dynamodb(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Python types to DynamoDB types."""
    result = {}
    for key, value in item.items():
        if value is None:
            continue
        elif isinstance(value, bool):
            result[key] = value
        elif isinstance(value, (int, float)):
            result[key] = Decimal(str(value))
        else:
            result[key] = value
    return result


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
