"""
Unified Contacts Lambda Function

Purpose: All contact CRUD + search in a single handler
Routes by HTTP method:
  GET    /contacts              → list all contacts
  GET    /contacts/{contactId}  → get single contact
  GET    /contacts/search?q=... → search contacts
  POST   /contacts              → create contact
  PUT    /contacts/{contactId}  → update contact
  DELETE /contacts/{contactId}  → soft/hard delete contact

DynamoDB Table: base-wecare-digital-ContactsTable
"""

import os
import json
import uuid
import time
import logging
import re
import base64
import boto3
from typing import Dict, Any, List, Optional
from decimal import Decimal
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
INBOUND_TABLE = os.environ.get('INBOUND_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')

CORS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
}

ALLOWED_UPDATE_FIELDS = {
    'name', 'phone', 'email', 'shippingAddress', 'billingAddress',
    'optInWhatsApp', 'optInSms', 'optInEmail',
    'allowlistWhatsApp', 'allowlistSms', 'allowlistEmail',
}
OPT_IN_FIELDS = {
    'optInWhatsApp', 'optInSms', 'optInEmail',
    'allowlistWhatsApp', 'allowlistSms', 'allowlistEmail',
}

DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 100


# ─── Main Router ────────────────────────────────────────────────────────────

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Route by HTTP method to the appropriate action."""
    request_id = context.aws_request_id if context else 'local'
    method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'GET')).upper()

    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}

    path_params = event.get('pathParameters', {}) or {}
    query_params = event.get('queryStringParameters', {}) or {}
    contact_id = path_params.get('contactId') or path_params.get('proxy')
    resource = event.get('resource', event.get('rawPath', ''))

    try:
        # GET /contacts/search?q=...
        if method == 'GET' and ('search' in resource or query_params.get('q')):
            return _search(query_params, request_id)

        # GET /contacts or GET /contacts/{id}
        if method == 'GET':
            if contact_id:
                return _read_one(contact_id, request_id)
            return _list_all(request_id)

        # POST /contacts
        if method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return _create(body, request_id)

        # PUT /contacts/{id}
        if method == 'PUT':
            if not contact_id:
                return _err(400, 'contactId is required')
            body = json.loads(event.get('body', '{}'))
            return _update(contact_id, body, request_id)

        # DELETE /contacts/{id}
        if method == 'DELETE':
            if not contact_id:
                return _err(400, 'contactId is required')
            hard = query_params.get('hard', 'false').lower() == 'true'
            return _delete(contact_id, hard, request_id)

        return _err(405, f'Method {method} not allowed')

    except json.JSONDecodeError:
        return _err(400, 'Invalid JSON in request body')
    except Exception as e:
        logger.error(json.dumps({'event': 'contacts_error', 'error': str(e), 'method': method, 'requestId': request_id}))
        return _err(500, f'Internal server error: {str(e)}')


# ─── CREATE ─────────────────────────────────────────────────────────────────

def _create(body: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    phone = body.get('phone', '').strip() if body.get('phone') else None
    email = body.get('email', '').strip().lower() if body.get('email') else None

    if not phone and not email:
        return _err(400, 'At least one of phone or email is required')
    if phone and not _validate_phone(phone):
        return _err(400, 'Invalid phone number format')
    if email and not _validate_email(email):
        return _err(400, 'Invalid email format')

    contact_id = str(uuid.uuid4())
    now = int(time.time())

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

    table = dynamodb.Table(CONTACTS_TABLE)
    table.put_item(Item=_to_dynamo(contact))

    logger.info(json.dumps({'event': 'contact_created', 'contactId': contact_id, 'requestId': request_id}))
    return {'statusCode': 201, 'headers': CORS, 'body': json.dumps(_from_dynamo(contact))}


# ─── READ ONE ───────────────────────────────────────────────────────────────

def _read_one(contact_id: str, request_id: str) -> Dict[str, Any]:
    table = dynamodb.Table(CONTACTS_TABLE)
    resp = table.get_item(Key={'id': contact_id})
    item = resp.get('Item')

    if not item or item.get('deletedAt') is not None:
        return _err(404, 'Contact not found')

    logger.info(json.dumps({'event': 'contact_read', 'contactId': contact_id, 'requestId': request_id}))
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps(_from_dynamo(item))}


# ─── LIST ALL ───────────────────────────────────────────────────────────────

def _list_all(request_id: str) -> Dict[str, Any]:
    table = dynamodb.Table(CONTACTS_TABLE)
    filt = Attr('deletedAt').not_exists() | Attr('deletedAt').eq(None)
    all_items: List[Dict] = []
    kwargs: Dict[str, Any] = {'FilterExpression': filt}

    while True:
        resp = table.scan(**kwargs)
        all_items.extend(resp.get('Items', []))
        if 'LastEvaluatedKey' not in resp:
            break
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

    contacts = [_from_dynamo(i) for i in all_items]
    logger.info(json.dumps({'event': 'contacts_list', 'count': len(contacts), 'requestId': request_id}))
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps({'contacts': contacts, 'count': len(contacts)})}


# ─── SEARCH ─────────────────────────────────────────────────────────────────

def _search(params: Dict[str, str], request_id: str) -> Dict[str, Any]:
    query = (params.get('q') or '').strip().lower()
    limit = min(int(params.get('limit', DEFAULT_SEARCH_LIMIT)), MAX_SEARCH_LIMIT)
    next_token = params.get('nextToken')

    table = dynamodb.Table(CONTACTS_TABLE)
    filt = Attr('deletedAt').not_exists() | Attr('deletedAt').eq(None)

    scan_kwargs: Dict[str, Any] = {'FilterExpression': filt, 'Limit': limit * 3}
    if next_token:
        try:
            scan_kwargs['ExclusiveStartKey'] = json.loads(base64.b64decode(next_token).decode())
        except Exception:
            return _err(400, 'Invalid nextToken')

    resp = table.scan(**scan_kwargs)
    items = resp.get('Items', [])

    if query:
        items = [i for i in items if _matches(i, query)]

    items = items[:limit]
    contacts = [_from_dynamo(i) for i in items]

    result_token = None
    if resp.get('LastEvaluatedKey'):
        result_token = base64.b64encode(json.dumps(resp['LastEvaluatedKey'], default=str).encode()).decode()

    logger.info(json.dumps({'event': 'contacts_search', 'query': query, 'count': len(contacts), 'requestId': request_id}))
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps({'contacts': contacts, 'count': len(contacts), 'nextToken': result_token})}


# ─── UPDATE ─────────────────────────────────────────────────────────────────

def _update(contact_id: str, body: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    updates = {k: v for k, v in body.items() if k in ALLOWED_UPDATE_FIELDS and k not in ('id', 'contactId')}
    if not updates:
        return _err(400, 'No valid fields to update')

    for f in OPT_IN_FIELDS:
        if f in updates and not isinstance(updates[f], bool):
            return _err(400, f'{f} must be a boolean value')

    if 'phone' in updates and updates['phone'] and not _validate_phone(updates['phone']):
        return _err(400, 'Invalid phone number format')
    if 'email' in updates and updates['email']:
        updates['email'] = updates['email'].strip().lower()
        if not _validate_email(updates['email']):
            return _err(400, 'Invalid email format')

    updates['updatedAt'] = int(time.time())

    set_parts, names, values = [], {}, {}
    for i, (k, v) in enumerate(updates.items()):
        set_parts.append(f'#n{i} = :v{i}')
        names[f'#n{i}'] = k
        values[f':v{i}'] = Decimal(str(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else v

    table = dynamodb.Table(CONTACTS_TABLE)
    try:
        resp = table.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET ' + ', '.join(set_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues='ALL_NEW',
        )
    except Exception as e:
        if 'ConditionalCheckFailedException' in str(e):
            return _err(404, 'Contact not found')
        raise

    logger.info(json.dumps({'event': 'contact_updated', 'contactId': contact_id, 'fields': list(updates.keys()), 'requestId': request_id}))
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps(_from_dynamo(resp.get('Attributes', {})))}


# ─── DELETE (soft / hard) ───────────────────────────────────────────────────

def _delete(contact_id: str, hard: bool, request_id: str) -> Dict[str, Any]:
    if hard:
        return _hard_delete(contact_id, request_id)
    return _soft_delete(contact_id, request_id)


def _soft_delete(contact_id: str, request_id: str) -> Dict[str, Any]:
    table = dynamodb.Table(CONTACTS_TABLE)
    # Check exists
    resp = table.get_item(Key={'id': contact_id})
    item = resp.get('Item')
    if not item:
        # Try scanning by contactId field
        scan_resp = table.scan(FilterExpression='contactId = :cid', ExpressionAttributeValues={':cid': contact_id}, Limit=1)
        items = scan_resp.get('Items', [])
        if items:
            item = items[0]
            contact_id = item.get('id', contact_id)
        else:
            return _err(404, 'Contact not found')

    if item.get('deletedAt') is not None:
        return _err(404, 'Contact already deleted')

    now = Decimal(str(int(time.time())))
    table.update_item(
        Key={'id': contact_id},
        UpdateExpression='SET #d = :d, #u = :u',
        ExpressionAttributeNames={'#d': 'deletedAt', '#u': 'updatedAt'},
        ExpressionAttributeValues={':d': now, ':u': now},
    )

    logger.info(json.dumps({'event': 'contact_soft_deleted', 'contactId': contact_id, 'requestId': request_id}))
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps({'success': True, 'contactId': contact_id, 'deleteType': 'soft'})}


def _hard_delete(contact_id: str, request_id: str) -> Dict[str, Any]:
    msgs_deleted = 0
    media_deleted = 0

    # Delete messages from both tables
    for tbl_name in (INBOUND_TABLE, OUTBOUND_TABLE):
        try:
            tbl = dynamodb.Table(tbl_name)
            resp = tbl.scan(FilterExpression='contactId = :cid', ExpressionAttributeValues={':cid': contact_id})
            for msg in resp.get('Items', []):
                s3_key = msg.get('s3Key')
                if s3_key:
                    try:
                        _delete_s3(s3_key)
                        media_deleted += 1
                    except Exception:
                        pass
                try:
                    tbl.delete_item(Key={'id': msg.get('id') or msg.get('messageId')})
                    msgs_deleted += 1
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Error scanning {tbl_name}: {e}")

    # Delete contact
    try:
        dynamodb.Table(CONTACTS_TABLE).delete_item(Key={'id': contact_id})
    except Exception as e:
        logger.warning(f"Failed to delete contact {contact_id}: {e}")

    logger.info(json.dumps({'event': 'contact_hard_deleted', 'contactId': contact_id, 'msgs': msgs_deleted, 'media': media_deleted, 'requestId': request_id}))
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps({
        'success': True, 'contactId': contact_id, 'deleteType': 'hard',
        'messagesDeleted': msgs_deleted, 'mediaDeleted': media_deleted,
    })}


# ─── Helpers ────────────────────────────────────────────────────────────────

def _validate_phone(phone: str) -> bool:
    pattern = r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}[-\s\.]?[0-9]{0,9}$'
    return bool(re.match(pattern, phone.replace(' ', '')))


def _validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _matches(item: Dict[str, Any], query: str) -> bool:
    name = str(item.get('name', '')).lower()
    phone = str(item.get('phone', '')).lower()
    email = str(item.get('email', '')).lower()
    clean_q = query.lstrip('+')
    clean_p = phone.lstrip('+')
    return query in name or query in phone or query in email or clean_q in clean_p


def _delete_s3(stored_key: str):
    try:
        s3_client.head_object(Bucket=MEDIA_BUCKET, Key=stored_key)
        s3_client.delete_object(Bucket=MEDIA_BUCKET, Key=stored_key)
        return
    except ClientError as e:
        if e.response['Error']['Code'] != '404':
            raise
    # Prefix search fallback
    prefix = stored_key.rsplit('.', 1)[0] if '.' in stored_key else stored_key
    resp = s3_client.list_objects_v2(Bucket=MEDIA_BUCKET, Prefix=prefix, MaxKeys=5)
    for obj in resp.get('Contents', []):
        s3_client.delete_object(Bucket=MEDIA_BUCKET, Key=obj['Key'])


def _to_dynamo(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (Decimal(str(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
            for k, v in item.items() if v is not None}


def _from_dynamo(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (int(v) if isinstance(v, Decimal) and v % 1 == 0 else float(v) if isinstance(v, Decimal) else v)
            for k, v in item.items()}


def _err(code: int, msg: str) -> Dict[str, Any]:
    return {'statusCode': code, 'headers': CORS, 'body': json.dumps({'error': msg})}
