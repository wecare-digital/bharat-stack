"""
Partner Onboarding Lambda  (Option B — Tech-Provider / Embedded Signup)

Public endpoint that completes WhatsApp Embedded Signup for a business that
connected its own WhatsApp Business Account to WECARE.DIGITAL through the
Facebook Login for Business flow on /partners/.

Route:  POST /partners/embedded-signup   (+ OPTIONS for CORS preflight)
Public: yes (the security boundary is the short-lived Meta OAuth `code`), with
        IP rate-limiting.

Flow:
  1. Receive { code, wabaId, phoneNumberId, businessId } from the browser.
  2. Exchange the OAuth `code` for a business access token server-side
     (needs the app secret — never exposed to the browser).
  3. Best-effort: subscribe our app to the business's WABA and register the
     phone number so we can send/receive on their behalf.
  4. Persist a tenant record (SystemConfigTable) and store the business token in
     a per-tenant secret (wecare/partners/<wabaId>). The token is never returned.
  5. Return a sanitized result (no secrets).

Meta reference:
  https://developers.facebook.com/docs/whatsapp/embedded-signup
"""
import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

import boto3

from lambda_utils.response import cors_response, options_response, extract_origin
from lambda_utils.logging import get_logger
from lambda_utils.rate_limit import check_rate_limit

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
API_VERSION = os.environ.get('META_API_VERSION', 'v25.0')
GRAPH_BASE = f'https://graph.facebook.com/{API_VERSION}'
APP_ID = os.environ.get('META_APP_ID', '2238810740192680')
TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
REG_PIN = os.environ.get('WA_REG_PIN', '')  # 6-digit PIN for phone registration (optional)

_secrets = boto3.client('secretsmanager', region_name=REGION)
_ddb = boto3.resource('dynamodb', region_name=REGION)

_cache = {}


def _app_secret() -> str:
    if 'app_secret' not in _cache:
        raw = _secrets.get_secret_value(SecretId=TOKEN_SECRET).get('SecretString', '') or '{}'
        try:
            _cache['app_secret'] = (json.loads(raw).get('app_secret') or '').strip()
        except json.JSONDecodeError:
            _cache['app_secret'] = ''
    return _cache['app_secret']


def _graph_get(path: str, params: dict) -> dict:
    url = f'{GRAPH_BASE}/{path}?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            raw = r.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else str(e)
        try:
            return {'error': json.loads(body).get('error', {'message': body}), '_status': e.code}
        except json.JSONDecodeError:
            return {'error': {'message': body}, '_status': e.code}
    except Exception as e:  # noqa: BLE001
        return {'error': {'message': str(e)}}


def _graph_post(path: str, token: str, payload: dict) -> dict:
    url = f'{GRAPH_BASE}/{path}'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url, data=data, method='POST',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else str(e)
        try:
            return {'error': json.loads(body).get('error', {'message': body}), '_status': e.code}
        except json.JSONDecodeError:
            return {'error': {'message': body}, '_status': e.code}
    except Exception as e:  # noqa: BLE001
        return {'error': {'message': str(e)}}


def _exchange_code(code: str) -> dict:
    """Exchange the Embedded Signup OAuth code for a business access token."""
    return _graph_get('oauth/access_token', {
        'client_id': APP_ID,
        'client_secret': _app_secret(),
        'code': code,
    })


def _store_token(waba_id: str, token: str) -> bool:
    """Store the business token in a per-tenant secret. Never logged/returned."""
    secret_name = f'wecare/partners/{waba_id}'
    payload = json.dumps({'access_token': token, 'wabaId': waba_id, 'updatedAt': datetime.now(timezone.utc).isoformat()})
    try:
        _secrets.create_secret(Name=secret_name, SecretString=payload)
        return True
    except _secrets.exceptions.ResourceExistsException:
        _secrets.put_secret_value(SecretId=secret_name, SecretString=payload)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(json.dumps({'event': 'partner_token_store_error', 'wabaId': waba_id, 'error': str(e)}))
        return False


def _persist_tenant(record: dict) -> None:
    try:
        table = _ddb.Table(SYSTEM_CONFIG_TABLE)
        table.put_item(Item={
            'id': f"partner_tenant_{record['wabaId']}",
            'configValue': json.dumps(record),
            'updatedAt': record['connectedAt'],
        })
    except Exception as e:  # noqa: BLE001
        logger.error(json.dumps({'event': 'partner_tenant_persist_error', 'error': str(e)}))


def handler(event, context):
    request_id = getattr(context, 'aws_request_id', 'local')
    origin = extract_origin(event)

    rc = event.get('requestContext', {})
    method = rc.get('http', {}).get('method') or event.get('httpMethod', 'POST')
    source_ip = (rc.get('http', {}) or {}).get('sourceIp') or rc.get('identity', {}).get('sourceIp', 'unknown')

    if method == 'OPTIONS':
        return options_response(origin)

    if method != 'POST':
        return cors_response(405, {'error': 'Method not allowed'}, origin)

    # IP rate-limit: onboarding is public; cap attempts.
    if not check_rate_limit('partner-onboarding', source_ip, max_per_second=2):
        return cors_response(429, {'error': 'Too many requests. Please retry shortly.'}, origin)

    try:
        body = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return cors_response(400, {'error': 'Invalid JSON body'}, origin)

    code = (body.get('code') or '').strip()
    waba_id = (body.get('wabaId') or '').strip()
    phone_number_id = (body.get('phoneNumberId') or '').strip()
    business_id = (body.get('businessId') or '').strip()

    if not code:
        return cors_response(400, {'error': 'Missing authorization code'}, origin)

    logger.info(json.dumps({
        'event': 'partner_onboarding_start', 'wabaId': waba_id,
        'phoneNumberId': phone_number_id, 'businessId': business_id, 'requestId': request_id,
    }))

    # 1) Exchange code -> business token
    token_resp = _exchange_code(code)
    if token_resp.get('error') or not token_resp.get('access_token'):
        err = token_resp.get('error', {})
        logger.warning(json.dumps({'event': 'partner_code_exchange_failed',
                                   'error': err.get('message'), 'requestId': request_id}))
        return cors_response(400, {'success': False, 'error': err.get('message', 'Code exchange failed')}, origin)

    business_token = token_resp['access_token']

    # 2) Best-effort provisioning on the connected WABA
    provisioning = {'subscribedApp': None, 'phoneRegistered': None}
    if waba_id:
        sub = _graph_post(f'{waba_id}/subscribed_apps', business_token, {})
        provisioning['subscribedApp'] = bool(sub.get('success')) if not sub.get('error') else False
    if phone_number_id and REG_PIN:
        reg = _graph_post(f'{phone_number_id}/register', business_token,
                          {'messaging_product': 'whatsapp', 'pin': REG_PIN})
        provisioning['phoneRegistered'] = bool(reg.get('success')) if not reg.get('error') else False

    # 3) Persist tenant + store token securely (never returned)
    connected_at = datetime.now(timezone.utc).isoformat()
    token_stored = _store_token(waba_id or f'unknown-{request_id}', business_token)
    _persist_tenant({
        'wabaId': waba_id,
        'phoneNumberId': phone_number_id,
        'businessId': business_id,
        'connectedAt': connected_at,
        'status': 'CONNECTED',
        'provisioning': provisioning,
        'tokenStored': token_stored,
    })

    logger.info(json.dumps({
        'event': 'partner_onboarding_done', 'wabaId': waba_id,
        'provisioning': provisioning, 'tokenStored': token_stored, 'requestId': request_id,
    }))

    return cors_response(200, {
        'success': True,
        'wabaId': waba_id,
        'phoneNumberId': phone_number_id,
        'businessId': business_id,
        'connectedAt': connected_at,
        'provisioning': provisioning,
    }, origin)
