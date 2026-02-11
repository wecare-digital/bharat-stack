"""DynamoDB storage layer with TTL support."""
import time
import uuid
import boto3
from decimal import Decimal
from typing import Dict, Any, Optional
from .config import (
    REGION, MESSAGES_INBOUND_TABLE, MESSAGES_OUTBOUND_TABLE,
    CONTACTS_TABLE, IDEMPOTENCY_TABLE,
    MESSAGE_TTL_SECONDS, IDEMPOTENCY_TTL_SECONDS
)

dynamodb = boto3.resource('dynamodb', region_name=REGION)


def store_inbound_message(message: Dict[str, Any]) -> str:
    table = dynamodb.Table(MESSAGES_INBOUND_TABLE)
    msg_id = message.get('id', str(uuid.uuid4()))
    now = int(time.time())
    item = {'id': msg_id, 'timestamp': now, 'expiresAt': now + MESSAGE_TTL_SECONDS}
    item.update({k: _to_decimal(v) for k, v in message.items()})
    table.put_item(Item=item)
    return msg_id


def store_outbound_message(message: Dict[str, Any]) -> str:
    table = dynamodb.Table(MESSAGES_OUTBOUND_TABLE)
    msg_id = message.get('id', str(uuid.uuid4()))
    now = int(time.time())
    item = {'id': msg_id, 'timestamp': now, 'expiresAt': now + MESSAGE_TTL_SECONDS}
    item.update({k: _to_decimal(v) for k, v in message.items()})
    table.put_item(Item=item)
    return msg_id


def check_idempotency(event_id: str) -> bool:
    table = dynamodb.Table(IDEMPOTENCY_TABLE)
    try:
        return 'Item' in table.get_item(Key={'eventId': event_id})
    except Exception:
        return False


def mark_processed(event_id: str):
    table = dynamodb.Table(IDEMPOTENCY_TABLE)
    table.put_item(Item={
        'eventId': event_id,
        'processedAt': int(time.time()),
        'expiresAt': int(time.time()) + IDEMPOTENCY_TTL_SECONDS
    })


def upsert_contact(phone: str, name: str = '', **kwargs) -> str:
    table = dynamodb.Table(CONTACTS_TABLE)
    response = table.query(
        IndexName='phone-index',
        KeyConditionExpression='phone = :phone',
        ExpressionAttributeValues={':phone': phone},
        Limit=1
    )
    if response.get('Items'):
        contact_id = response['Items'][0]['id']
        update_parts = ['lastInboundMessageAt = :ts']
        values = {':ts': int(time.time())}
        names = {}
        if name:
            update_parts.append('#n = :name')
            values[':name'] = name
            names['#n'] = 'name'
        table.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET ' + ', '.join(update_parts),
            ExpressionAttributeValues=values,
            **({"ExpressionAttributeNames": names} if names else {})
        )
        return contact_id
    contact_id = str(uuid.uuid4())
    item = {
        'id': contact_id, 'phone': phone, 'name': name or '',
        'createdAt': int(time.time()), 'lastInboundMessageAt': int(time.time())
    }
    item.update({k: _to_decimal(v) for k, v in kwargs.items()})
    table.put_item(Item=item)
    return contact_id


def update_message_status(message_id: str, status: str, table_name: str = None):
    tbl = table_name or MESSAGES_INBOUND_TABLE
    table = dynamodb.Table(tbl)
    table.update_item(
        Key={'id': message_id},
        UpdateExpression='SET #s = :status, statusUpdatedAt = :ts',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':status': status, ':ts': int(time.time())}
    )


def _to_decimal(val):
    if isinstance(val, float):
        return Decimal(str(val))
    if isinstance(val, dict):
        return {k: _to_decimal(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_to_decimal(v) for v in val]
    return val
