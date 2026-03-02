"""
Rate limiting utility using DynamoDB RateLimitTrackers table.

Usage:
    from lambda_utils.rate_limit import check_rate_limit

    if not check_rate_limit('whatsapp', phone_number_id, max_per_second=80):
        return cors_response(429, {'error': 'Rate limit exceeded'})
"""

import os
import time
from decimal import Decimal
from typing import Optional

import boto3

from lambda_utils.logging import get_logger

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
RATE_LIMIT_TABLE = os.environ.get('RATE_LIMIT_TABLE', 'RateLimitTracker')
TTL_SECONDS = 86400  # 24 hours


def check_rate_limit(
    channel: str,
    resource_id: str,
    max_per_second: int = 80,
    table_name: Optional[str] = None,
) -> bool:
    """
    Atomic increment-and-check against the RateLimitTrackers table.

    Returns True if under the limit, False if exceeded.
    Fails open (returns True) on errors to avoid blocking traffic.
    """
    try:
        table = dynamodb.Table(table_name or RATE_LIMIT_TABLE)
        now = int(time.time())
        window_key = f"{channel}:{resource_id}"

        response = table.update_item(
            Key={'channel': window_key, 'windowStart': str(now)},
            UpdateExpression=(
                'SET messageCount = if_not_exists(messageCount, :zero) + :inc, '
                'lastUpdatedAt = :ttl'
            ),
            ExpressionAttributeValues={
                ':zero': Decimal('0'),
                ':inc': Decimal('1'),
                ':ttl': Decimal(str(now + TTL_SECONDS)),
            },
            ReturnValues='UPDATED_NEW',
        )

        count = int(response.get('Attributes', {}).get('messageCount', 0))
        return count <= max_per_second

    except Exception as e:
        logger.warning(f'{{"event":"rate_limit_error","channel":"{channel}","error":"{e}"}}')
        return True
