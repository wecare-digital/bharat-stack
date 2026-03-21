"""
Ads Click-to-WhatsApp Attribution Lambda

Purpose: Track and attribute WhatsApp conversations originating from Meta ads
- POST /ad-attribution          → Record ad click attribution from inbound webhook referral data
- GET  /ad-attribution          → List attributions (with optional filters)
- GET  /ad-attribution/stats    → Aggregated stats by ad/campaign

When a user clicks a Click-to-WhatsApp ad, Meta includes a 'referral' object
in the inbound webhook with: source_url, source_type, source_id, headline, body, ctwa_clid.
This handler stores that data in the AdClickAttribution DynamoDB table.
"""

import os
import json
import time
import uuid
import boto3
from decimal import Decimal
from typing import Dict, Any

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, extract_origin
from lambda_utils.privacy import mask_phone

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)
AD_ATTRIBUTION_TABLE = os.environ.get('AD_ATTRIBUTION_TABLE', 'stack-wecare-digital-AdClickAttributionTable')

origin = ''


def _resp(code: int, body: Dict) -> Dict:
    return {'statusCode': code, 'headers': cors_headers(origin), 'body': json.dumps(body, default=str)}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)

    rc = event.get('requestContext', {})
    method = rc.get('http', {}).get('method', event.get('httpMethod', 'GET'))
    path = rc.get('http', {}).get('path', '') or event.get('rawPath', '') or event.get('path', '')
    params = event.get('queryStringParameters') or {}

    if method == 'OPTIONS':
        return _resp(200, {'ok': True})

    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
    except (json.JSONDecodeError, TypeError):
        body = {}

    try:
        if '/stats' in path:
            return _get_stats(params, request_id)
        if method == 'POST':
            return _record_attribution(body, request_id)
        if method == 'GET':
            return _list_attributions(params, request_id)
        return _resp(404, {'error': f'Unknown: {method} {path}'})
    except Exception as e:
        logger.exception(f'[{request_id}] Error')
        return _resp(500, {'error': str(e)})


def _record_attribution(body: Dict, request_id: str) -> Dict:
    """
    Record an ad click attribution event.
    Called by inbound-whatsapp-handler when a referral object is present.
    
    Body: {
        phone: str,
        contactId: str,
        referral: {
            source_url: str,
            source_type: str,  # 'ad' or 'post'
            source_id: str,    # Meta ad ID
            headline: str,
            body: str,
            ctwa_clid: str,    # Click-to-WhatsApp click ID
            media_type: str,
            image_url: str,
            video_url: str,
            thumbnail_url: str,
        },
        wabaId: str,
        phoneNumberId: str,
        whatsappMessageId: str,
    }
    """
    referral = body.get('referral', {})
    if not referral:
        return _resp(400, {'error': 'referral object required'})

    table = dynamodb.Table(AD_ATTRIBUTION_TABLE)
    now = int(time.time())
    item_id = str(uuid.uuid4())

    item = {
        'id': item_id,
        'phone': body.get('phone', ''),
        'contactId': body.get('contactId', ''),
        'sourceUrl': referral.get('source_url', ''),
        'sourceType': referral.get('source_type', ''),
        'sourceId': referral.get('source_id', ''),
        'headline': referral.get('headline', ''),
        'adBody': referral.get('body', ''),
        'ctwaClid': referral.get('ctwa_clid', ''),
        'mediaType': referral.get('media_type', ''),
        'imageUrl': referral.get('image_url', ''),
        'videoUrl': referral.get('video_url', ''),
        'thumbnailUrl': referral.get('thumbnail_url', ''),
        'wabaId': body.get('wabaId', ''),
        'phoneNumberId': body.get('phoneNumberId', ''),
        'whatsappMessageId': body.get('whatsappMessageId', ''),
        'createdAt': Decimal(str(now)),
        'ttl': Decimal(str(now + 180 * 86400)),  # 180 day retention
    }

    table.put_item(Item=item)
    logger.info(json.dumps({
        'event': 'ad_attribution_recorded',
        'id': item_id,
        'sourceType': referral.get('source_type', ''),
        'sourceId': referral.get('source_id', ''),
        'ctwaClid': referral.get('ctwa_clid', ''),
        'phone': mask_phone(body.get('phone', '')),
        'requestId': request_id,
    }))

    return _resp(200, {'success': True, 'id': item_id})


def _list_attributions(params: Dict, request_id: str) -> Dict:
    """List ad click attributions with optional filters."""
    table = dynamodb.Table(AD_ATTRIBUTION_TABLE)
    max_results = int(params.get('limit', '50'))

    # Filter by sourceId (ad ID) if provided
    source_id = params.get('sourceId', '')
    scan_kwargs = {}
    if source_id:
        scan_kwargs['FilterExpression'] = 'sourceId = :sid'
        scan_kwargs['ExpressionAttributeValues'] = {':sid': source_id}

    # Full pagination to collect up to max_results matching items
    items = []
    while len(items) < max_results:
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        if 'LastEvaluatedKey' not in response:
            break
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    items = items[:max_results]

    # Mask phone numbers in response
    for item in items:
        if item.get('phone'):
            item['phone'] = mask_phone(item['phone'])

    return _resp(200, {'attributions': items, 'count': len(items)})


def _get_stats(params: Dict, request_id: str) -> Dict:
    """Get aggregated attribution stats."""
    table = dynamodb.Table(AD_ATTRIBUTION_TABLE)

    # Full pagination scan for accurate stats
    items = []
    scan_kwargs = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        if 'LastEvaluatedKey' not in response:
            break
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    # Aggregate by sourceId
    by_source = {}
    by_type = {}
    for item in items:
        sid = item.get('sourceId', 'unknown')
        stype = item.get('sourceType', 'unknown')
        by_source[sid] = by_source.get(sid, 0) + 1
        by_type[stype] = by_type.get(stype, 0) + 1

    return _resp(200, {
        'totalAttributions': len(items),
        'bySourceId': by_source,
        'bySourceType': by_type,
    })
