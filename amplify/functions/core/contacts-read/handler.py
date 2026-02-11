"""
Contacts Read Lambda Function

Purpose: Retrieve contact details or list all contacts
Requirements: 2.3

Queries DynamoDB by contactId (single) or scans all (list).
Filters out soft-deleted records.
"""

import os
import json
import logging
import boto3
from typing import Dict, Any, List
from decimal import Decimal
from boto3.dynamodb.conditions import Attr

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Retrieve contact by contactId or list all contacts.
    If contactId is provided (path param or query param), returns single contact.
    Otherwise returns all non-deleted contacts.
    """
    request_id = context.aws_request_id if context else 'local'
    
    try:
        # Extract contactId from path parameters or query parameters
        path_params = event.get('pathParameters', {}) or {}
        query_params = event.get('queryStringParameters', {}) or {}
        contact_id = path_params.get('contactId') or query_params.get('contactId')
        
        table = dynamodb.Table(CONTACTS_TABLE)
        
        # If no contactId, list all contacts
        if not contact_id:
            return _list_all_contacts(table, request_id)
        
        # Get single contact by contactId
        response = table.get_item(Key={'id': contact_id})
        
        item = response.get('Item')
        
        if not item:
            logger.info(json.dumps({
                'event': 'contact_not_found',
                'contactId': contact_id,
                'requestId': request_id
            }))
            return _error_response(404, 'Contact not found')
        
        # Filter soft-deleted records
        if item.get('deletedAt') is not None:
            return _error_response(404, 'Contact not found')
        
        logger.info(json.dumps({
            'event': 'contact_read',
            'contactId': contact_id,
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': _cors_headers(),
            'body': json.dumps(_convert_from_dynamodb(item)),
        }
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'contact_read_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, 'Internal server error')


def _list_all_contacts(table, request_id: str) -> Dict[str, Any]:
    """Scan all non-deleted contacts."""
    try:
        filter_expr = Attr('deletedAt').not_exists() | Attr('deletedAt').eq(None)
        all_items = []
        scan_kwargs = {'FilterExpression': filter_expr}
        
        while True:
            response = table.scan(**scan_kwargs)
            all_items.extend(response.get('Items', []))
            if 'LastEvaluatedKey' not in response:
                break
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        
        contacts = [_convert_from_dynamodb(item) for item in all_items]
        
        logger.info(json.dumps({
            'event': 'contacts_list',
            'count': len(contacts),
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': _cors_headers(),
            'body': json.dumps({
                'contacts': contacts,
                'count': len(contacts)
            }),
        }
    except Exception as e:
        logger.error(json.dumps({
            'event': 'contacts_list_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, 'Internal server error')


def _cors_headers():
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }


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
    """Return error response."""
    return {
        'statusCode': status_code,
        'headers': _cors_headers(),
        'body': json.dumps({'error': message}),
    }
