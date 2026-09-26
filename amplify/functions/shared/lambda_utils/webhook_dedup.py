"""
Shared webhook idempotency helper.

Backed by the existing `WebhookDedup` DynamoDB model (PK: eventId; fields: source,
processedAt, expiresAt, ttl). Lets every webhook consumer (WhatsApp, Razorpay)
atomically claim an event id so retries / duplicate deliveries are processed once.

Usage:
    from lambda_utils.webhook_dedup import claim_event
    if not claim_event(message_id, source="whatsapp"):
        return  # duplicate — already processed, skip

`claim_event` returns True when the caller newly claimed the event (process it),
False when the event was already seen (skip). Fails OPEN on infra errors (returns True)
so a transient DynamoDB problem never silently drops a real event.
"""
import os
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from lambda_utils.logging import get_logger

logger = get_logger(__name__)

WEBHOOK_DEDUP_TABLE = os.environ.get('WEBHOOK_DEDUP_TABLE', 'stack-wecare-digital-WebhookDedup')
DEFAULT_TTL_DAYS = int(os.environ.get('WEBHOOK_DEDUP_TTL_DAYS', '7'))

_dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))


def _table():
    return _dynamodb.Table(WEBHOOK_DEDUP_TABLE)


def claim_event(event_id: Optional[str], source: str = 'whatsapp', ttl_days: int = DEFAULT_TTL_DAYS) -> bool:
    """Atomically claim an event id.

    Returns:
        True  -> newly claimed (caller SHOULD process the event)
        False -> already processed (caller SHOULD skip)
    Fails open (returns True) on missing id or DynamoDB errors so real events are never dropped.
    """
    if not event_id:
        return True
    now = int(time.time())
    expires_at = now + ttl_days * 24 * 60 * 60
    try:
        _table().put_item(
            Item={
                'eventId': str(event_id),
                'source': source,
                'processedAt': now,
                'expiresAt': expires_at,
                'ttl': expires_at,
            },
            ConditionExpression='attribute_not_exists(eventId)',
        )
        return True
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            logger.info('{"event":"webhook_duplicate_skipped","source":"%s","eventId":"%s"}' % (source, str(event_id)[:64]))
            return False
        logger.warning('{"event":"webhook_dedup_error","source":"%s","error":"%s"}' % (source, str(e)[:160]))
        return True  # fail open
    except Exception as e:  # noqa: BLE001 — never let dedup infra drop a real event
        logger.warning('{"event":"webhook_dedup_error","source":"%s","error":"%s"}' % (source, str(e)[:160]))
        return True


def is_duplicate(event_id: Optional[str], source: str = 'whatsapp', ttl_days: int = DEFAULT_TTL_DAYS) -> bool:
    """Convenience inverse of claim_event(): True when the event is a duplicate to skip."""
    return not claim_event(event_id, source=source, ttl_days=ttl_days)
