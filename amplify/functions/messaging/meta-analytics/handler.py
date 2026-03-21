"""
Meta Analytics Lambda Handler

Purpose: Retrieve official Meta WhatsApp analytics via Graph API.
Endpoints:
  GET /meta-analytics/messaging    → Messaging analytics (sent, delivered, read counts)
  GET /meta-analytics/conversation → Conversation analytics (by type, pricing)
  GET /meta-analytics/template     → Template analytics from Meta (per-template performance)
  GET /meta-analytics/phone-quality → Phone number quality and messaging limits

Uses Meta Graph API:
  GET /{waba_id}/analytics          → Messaging analytics
  GET /{waba_id}/conversation_analytics → Conversation-based pricing analytics
  GET /{waba_id}/template_analytics → Per-template performance
  GET /{phone_id}                   → Phone quality rating + messaging limit tier
"""

import os
import json
import hmac
import hashlib
import logging
import boto3
import urllib.request
import urllib.parse
from typing import Dict, Any

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_headers, extract_origin

logger = get_logger(__name__)

secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')
META_TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
GRAPH_BASE = f'https://graph.facebook.com/{META_API_VERSION}'

WABA1_ID = os.environ.get('WABA1_ID', '1912405516040025')
WABA2_ID = os.environ.get('WABA2_ID', '1633959101297902')
PHONE1_META_ID = os.environ.get('PHONE1_META_ID', '960395407161423')
PHONE2_META_ID = os.environ.get('PHONE2_META_ID', '997428863451102')
WABA2_IDS = {WABA2_ID, PHONE2_META_ID}

_token_cache = {}
origin = ''


def _load_secrets():
    if 'loaded' in _token_cache:
        return
    resp = secrets_client.get_secret_value(SecretId=META_TOKEN_SECRET)
    secret = json.loads(resp['SecretString'])
    _token_cache['token1'] = (secret.get('access_token') or '').strip()
    _token_cache['token2'] = (secret.get('access_token_waba2') or secret.get('access_token') or '').strip()
    _token_cache['app_secret'] = (secret.get('app_secret') or '').strip()
    _token_cache['loaded'] = True


def _get_token(waba_id: str = None) -> str:
    _load_secrets()
    key = 'token2' if waba_id in WABA2_IDS else 'token1'
    return _token_cache.get(key, _token_cache.get('token1', ''))


def _graph_api(endpoint: str, params: Dict = None, waba_id: str = None) -> Dict:
    """GET request to Meta Graph API with appsecret_proof."""
    _load_secrets()
    token = _get_token(waba_id)
    app_secret = _token_cache.get('app_secret', '')
    url = f'{GRAPH_BASE}/{endpoint}'
    qs = dict(params or {})
    if app_secret:
        qs['appsecret_proof'] = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    if qs:
        url += '?' + urllib.parse.urlencode(qs)
    headers = {'Authorization': f'Bearer {token}'}
    req = urllib.request.Request(url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else str(e)
        logger.error(f'Graph API error {e.code}: {body}')
        try:
            return {'error': json.loads(body)}
        except (json.JSONDecodeError, TypeError):
            return {'error': {'message': body, 'code': e.code}}


def _resp(code: int, body: Dict) -> Dict:
    return {'statusCode': code, 'headers': cors_headers(origin), 'body': json.dumps(body, default=str)}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Route requests to appropriate analytics function."""
    global origin
    origin = extract_origin(event)
    rc = event.get('requestContext', {})
    http_method = rc.get('http', {}).get('method', event.get('httpMethod', 'GET'))
    path = rc.get('http', {}).get('path', '') or event.get('rawPath', '') or event.get('path', '')
    query = event.get('queryStringParameters') or {}

    if http_method == 'OPTIONS':
        return _resp(200, {'ok': True})

    waba_id = query.get('wabaId', WABA1_ID)

    if 'conversation' in path:
        return _get_conversation_analytics(waba_id, query)
    if 'template' in path:
        return _get_template_analytics(waba_id, query)
    if 'phone-quality' in path:
        return _get_phone_quality(query)
    # Default: messaging analytics
    return _get_messaging_analytics(waba_id, query)


def _get_messaging_analytics(waba_id: str, query: Dict) -> Dict:
    """
    GET /{waba_id}/analytics — messaging analytics.
    Query params: start (epoch), end (epoch), granularity (HALF_HOUR|DAY|MONTH)
    """
    params = {
        'fields': 'analytics.start({start}).end({end}).granularity({granularity})'.format(
            start=query.get('start', '0'),
            end=query.get('end', '9999999999'),
            granularity=query.get('granularity', 'DAY'),
        ),
    }
    result = _graph_api(waba_id, params=params, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    analytics = result.get('analytics', {})
    return _resp(200, {'analytics': analytics, 'wabaId': waba_id})


def _get_conversation_analytics(waba_id: str, query: Dict) -> Dict:
    """
    GET /{waba_id}/conversation_analytics — conversation-based pricing analytics.
    Returns conversation counts by type (UTILITY, MARKETING, AUTHENTICATION, SERVICE).
    """
    params = {
        'fields': 'conversation_analytics.start({start}).end({end}).granularity({granularity}).dimensions([{dims}])'.format(
            start=query.get('start', '0'),
            end=query.get('end', '9999999999'),
            granularity=query.get('granularity', 'DAY'),
            dims=query.get('dimensions', 'CONVERSATION_TYPE'),
        ),
    }
    result = _graph_api(waba_id, params=params, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    analytics = result.get('conversation_analytics', {})
    return _resp(200, {'conversationAnalytics': analytics, 'wabaId': waba_id})


def _get_template_analytics(waba_id: str, query: Dict) -> Dict:
    """
    GET /{waba_id}/template_analytics — per-template performance.
    Returns sent, delivered, read counts per template.
    """
    params = {
        'fields': 'template_analytics.start({start}).end({end}).granularity({granularity})'.format(
            start=query.get('start', '0'),
            end=query.get('end', '9999999999'),
            granularity=query.get('granularity', 'DAY'),
        ),
    }
    template_ids = query.get('templateIds')
    if template_ids:
        params['fields'] += f'.template_ids([{template_ids}])'
    result = _graph_api(waba_id, params=params, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    analytics = result.get('template_analytics', {})
    return _resp(200, {'templateAnalytics': analytics, 'wabaId': waba_id})


def _get_phone_quality(query: Dict) -> Dict:
    """
    GET /{phone_id} — phone number quality rating and messaging limits.
    Returns quality_rating, messaging_limit_tier, is_official_business_account.
    """
    phone_id = query.get('phoneId', PHONE1_META_ID)
    waba_id = WABA2_ID if phone_id == PHONE2_META_ID else WABA1_ID
    fields = 'display_phone_number,verified_name,quality_rating,messaging_limit_tier,is_official_business_account,name_status,throughput'
    result = _graph_api(phone_id, params={'fields': fields}, waba_id=waba_id)
    if 'error' in result:
        return _resp(400, result)
    return _resp(200, {'phoneQuality': result})
