"""
Partner Token Refresh Lambda  (Option B — Embedded Signup)

Embedded Signup issues 60-day expiring system-user access tokens. This function
refreshes each connected tenant's token before it lapses so integrations keep
working without re-onboarding.

Trigger: EventBridge schedule (daily). Also invokable on demand.

For each secret matching prefix `wecare/partners/`:
  - read { access_token, expiresAt }
  - if expiring within REFRESH_WINDOW_DAYS, call:
      GET /oauth/access_token?grant_type=fb_exchange_token
          &client_id=APP_ID&client_secret=APP_SECRET
          &fb_exchange_token=<token>&set_token_expires_in_60_days=true
  - store the refreshed token + new expiresAt back into the secret

Meta reference:
  https://developers.facebook.com/docs/business-management-apis/system-users/install-apps-and-generate-tokens
"""
import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta

import boto3

from lambda_utils.logging import get_logger

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
API_VERSION = os.environ.get('META_API_VERSION', 'v25.0')
GRAPH_BASE = f'https://graph.facebook.com/{API_VERSION}'
APP_ID = os.environ.get('META_APP_ID', '2238810740192680')
TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
PARTNER_PREFIX = os.environ.get('PARTNER_SECRET_PREFIX', 'wecare/partners/')
REFRESH_WINDOW_DAYS = int(os.environ.get('REFRESH_WINDOW_DAYS', '15'))

SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
TENANT_PREFIX = 'partner_tenant_'

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


def _refresh(token: str) -> dict:
    qs = urllib.parse.urlencode({
        'grant_type': 'fb_exchange_token',
        'client_id': APP_ID,
        'client_secret': _app_secret(),
        'set_token_expires_in_60_days': 'true',
        'fb_exchange_token': token,
    })
    url = f'{GRAPH_BASE}/oauth/access_token?{qs}'
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            raw = r.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else str(e)
        try:
            return {'error': json.loads(body).get('error', {'message': body})}
        except json.JSONDecodeError:
            return {'error': {'message': body}}
    except Exception as e:  # noqa: BLE001
        return {'error': {'message': str(e)}}


def _list_partner_secrets():
    """Enumerate tenant secret names from SystemConfigTable (partner_tenant_*)
    rather than secretsmanager:ListSecrets (avoids a broad list-* grant)."""
    names = []
    try:
        table = _ddb.Table(SYSTEM_CONFIG_TABLE)
        kwargs = {
            'FilterExpression': 'begins_with(id, :p)',
            'ExpressionAttributeValues': {':p': TENANT_PREFIX},
            'ProjectionExpression': 'id',
        }
        while True:
            resp = table.scan(**kwargs)
            for item in resp.get('Items', []):
                waba_id = item['id'][len(TENANT_PREFIX):]
                if waba_id:
                    names.append(f'{PARTNER_PREFIX}{waba_id}')
            lek = resp.get('LastEvaluatedKey')
            if not lek:
                break
            kwargs['ExclusiveStartKey'] = lek
    except Exception as e:  # noqa: BLE001
        logger.error(json.dumps({'event': 'partner_tenant_scan_error', 'error': str(e)}))
    return names


def handler(event, context):
    now = datetime.now(timezone.utc)
    window = now + timedelta(days=REFRESH_WINDOW_DAYS)
    force = bool((event or {}).get('force'))

    checked = refreshed = skipped = failed = 0
    details = []

    for name in _list_partner_secrets():
        checked += 1
        try:
            raw = _secrets.get_secret_value(SecretId=name).get('SecretString', '') or '{}'
            data = json.loads(raw)
        except Exception as e:  # noqa: BLE001
            failed += 1
            logger.warning(json.dumps({'event': 'partner_refresh_read_error', 'secret': name, 'error': str(e)}))
            continue

        token = (data.get('access_token') or '').strip()
        if not token:
            skipped += 1
            continue

        # decide if refresh is due
        expires_at = data.get('expiresAt')
        due = force
        if not due and expires_at:
            try:
                due = datetime.fromisoformat(expires_at) <= window
            except ValueError:
                due = True
        elif not expires_at:
            due = True

        if not due:
            skipped += 1
            continue

        res = _refresh(token)
        if res.get('error') or not res.get('access_token'):
            failed += 1
            logger.warning(json.dumps({'event': 'partner_refresh_failed', 'secret': name,
                                       'error': (res.get('error') or {}).get('message')}))
            continue

        new_token = res['access_token']
        expires_in = int(res.get('expires_in') or (60 * 24 * 3600))
        new_expiry = (now + timedelta(seconds=expires_in)).isoformat()
        data.update({'access_token': new_token, 'updatedAt': now.isoformat(), 'expiresAt': new_expiry})
        _secrets.put_secret_value(SecretId=name, SecretString=json.dumps(data))
        refreshed += 1
        details.append({'secret': name, 'wabaId': data.get('wabaId'), 'newExpiresAt': new_expiry})

    summary = {'event': 'partner_token_refresh_summary', 'checked': checked,
               'refreshed': refreshed, 'skipped': skipped, 'failed': failed}
    logger.info(json.dumps(summary))
    return {'statusCode': 200, 'body': json.dumps({**summary, 'details': details})}
