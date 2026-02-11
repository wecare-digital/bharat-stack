"""
Media Cleanup Lambda Function

Purpose: Delete expired WhatsApp media IDs from Meta servers.
WhatsApp media IDs expire after 30 days, but calling DELETE explicitly
frees storage sooner and is good hygiene.

Triggered on schedule (EventBridge daily) or manually.
Scans MediaFilesTable for records older than 25 days and calls
delete_whatsapp_message_media for each.
"""

import os
import json
import time
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
social_messaging = boto3.client('socialmessaging', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

MEDIA_FILES_TABLE = os.environ.get('MEDIA_FILES_TABLE', 'base-wecare-digital-MediaFilesTable')
PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-5e020cecd221429996f6ae721cc42206')
CLEANUP_AGE_DAYS = int(os.environ.get('CLEANUP_AGE_DAYS', '25'))
MAX_DELETIONS = int(os.environ.get('MAX_DELETIONS', '50'))


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete expired WhatsApp media from Meta servers."""
    request_id = context.aws_request_id if context else 'local'
    deleted = 0
    failed = 0
    skipped = 0

    cutoff = int(time.time()) - (CLEANUP_AGE_DAYS * 86400)

    logger.info(json.dumps({
        'event': 'media_cleanup_start',
        'cutoffTimestamp': cutoff,
        'cutoffDays': CLEANUP_AGE_DAYS,
        'maxDeletions': MAX_DELETIONS,
        'requestId': request_id
    }))

    try:
        table = dynamodb.Table(MEDIA_FILES_TABLE)
        response = table.scan(
            FilterExpression='uploadedAt < :cutoff AND attribute_exists(whatsappMediaId)',
            ExpressionAttributeValues={':cutoff': Decimal(str(cutoff))},
            Limit=MAX_DELETIONS * 2
        )

        items = response.get('Items', [])
        logger.info(json.dumps({
            'event': 'media_cleanup_scan',
            'foundCount': len(items),
            'requestId': request_id
        }))

        for item in items[:MAX_DELETIONS]:
            media_id = item.get('whatsappMediaId', '')
            file_id = item.get('fileId', '')

            if not media_id:
                skipped += 1
                continue

            # Skip if already cleaned up
            if item.get('cleanedUp'):
                skipped += 1
                continue

            try:
                social_messaging.delete_whatsapp_message_media(
                    mediaId=media_id,
                    originationPhoneNumberId=PHONE_NUMBER_ID
                )

                # Mark as cleaned up
                table.update_item(
                    Key={'fileId': file_id},
                    UpdateExpression='SET cleanedUp = :t, cleanedUpAt = :now',
                    ExpressionAttributeValues={
                        ':t': True,
                        ':now': Decimal(str(int(time.time())))
                    }
                )

                deleted += 1
                logger.info(json.dumps({
                    'event': 'media_deleted',
                    'mediaId': media_id,
                    'fileId': file_id,
                    'requestId': request_id
                }))

            except Exception as e:
                failed += 1
                logger.warning(json.dumps({
                    'event': 'media_delete_error',
                    'mediaId': media_id,
                    'fileId': file_id,
                    'error': str(e),
                    'requestId': request_id
                }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'media_cleanup_error',
            'error': str(e),
            'requestId': request_id
        }))

    logger.info(json.dumps({
        'event': 'media_cleanup_complete',
        'deleted': deleted,
        'failed': failed,
        'skipped': skipped,
        'requestId': request_id
    }))

    return {
        'statusCode': 200,
        'body': json.dumps({
            'deleted': deleted,
            'failed': failed,
            'skipped': skipped
        })
    }
