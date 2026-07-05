"""
Partner Onboarding Lambda  (Option B — Tech-Provider / Embedded Signup)

Completes the full WhatsApp Embedded Signup lifecycle for a business that
connects (onboards a new number) OR migrates an existing number to
WECARE.DIGITAL through Facebook Login for Business on /partners/ or the in-app
Connect WABA page.

Routes (HTTP API zllr9lrg7j, base api.wecare.digital):
  POST   /partners/embedded-signup   public  — complete onboarding/migration
  GET    /partners/tenants           admin   — list connected accounts (+ live status)
  DELETE /partners/tenants           admin   — disconnect a tenant
  OPTIONS *                          CORS preflight

Doc-accurate onboarding/migration sequence (Meta Solution Partner guide):
  1. Exchange OAuth `code` -> business (system-user) access token   [server-side]
  2. Share credit line with the WABA        POST /{extended_credit_id}/whatsapp_credit_sharing_and_attach
  3. Subscribe our app to the WABA          POST /{waba_id}/subscribed_apps
  4. Register the number for Cloud API      POST /{phone_number_id}/register  { messaging_product, pin }
     (registration re-associates a migrated number to the destination WABA;
      the client must have disabled two-step verification first for migrations)
  5. Fetch WABA + phone details for the tenant record
  6. Persist tenant + store token in per-tenant secret (auto-refreshed daily)

Refs:
  /whatsapp/embedded-signup  and  /solution-providers  (share credit line,
  manage webhooks, register phone numbers, migrate-phone-to-different-waba).
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
from lambda_utils.middleware import require_auth
from lambda_utils import partner_billing as billing
try:
    from lambda_utils.audit import record_audit
except Exception:  # noqa: BLE001
    def record_audit(**kwargs):  # type: ignore
        return None

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
API_VERSION = os.environ.get('META_API_VERSION', 'v25.0')
GRAPH_BASE = f'https://graph.facebook.com/{API_VERSION}'
APP_ID = os.environ.get('META_APP_ID', '2238810740192680')
TOKEN_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
REG_PIN = os.environ.get('WA_REG_PIN', '')                       # default 6-digit 2FA PIN
EXTENDED_CREDIT_ID = os.environ.get('META_EXTENDED_CREDIT_ID', '')  # solution-partner line of credit
USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', 'us-east-1_cSx0RHCIR')
PARTNER_GROUP = os.environ.get('PARTNER_GROUP', 'Partner')       # limited-access group for customers

_secrets = boto3.client('secretsmanager', region_name=REGION)
_ddb = boto3.resource('dynamodb', region_name=REGION)
_cognito = boto3.client('cognito-idp', region_name=REGION)
_cache = {}


def _provision_customer_user(email: str, waba_id: str) -> dict:
    """Create (or update) a limited-access Cognito login for the customer,
    scoped to their own WABA via custom:partner_waba_id and the Partner group.
    Cognito emails them an invite with a temporary password. Best-effort."""
    if not email or not waba_id:
        return {'step': 'customer_login', 'ok': None, 'detail': 'skipped (no email)'}
    attrs = [
        {'Name': 'email', 'Value': email},
        {'Name': 'email_verified', 'Value': 'true'},
        {'Name': 'custom:partner_waba_id', 'Value': waba_id},
    ]
    try:
        _cognito.admin_create_user(
            UserPoolId=USER_POOL_ID, Username=email, UserAttributes=attrs,
            DesiredDeliveryMediums=['EMAIL'])
        created = True
    except _cognito.exceptions.UsernameExistsException:
        try:
            _cognito.admin_update_user_attributes(
                UserPoolId=USER_POOL_ID, Username=email,
                UserAttributes=[{'Name': 'custom:partner_waba_id', 'Value': waba_id}])
        except Exception as e:  # noqa: BLE001
            return {'step': 'customer_login', 'ok': False, 'detail': f'update failed: {e}'}
        created = False
    except Exception as e:  # noqa: BLE001
        return {'step': 'customer_login', 'ok': False, 'detail': str(e)}
    try:
        _cognito.admin_add_user_to_group(UserPoolId=USER_POOL_ID, Username=email, GroupName=PARTNER_GROUP)
    except Exception as e:  # noqa: BLE001
        logger.warning(json.dumps({'event': 'partner_group_add_error', 'email': email, 'error': str(e)}))
    return {'step': 'customer_login', 'ok': True, 'detail': 'invited' if created else 'updated'}


# ── secret / graph helpers ────────────────────────────────────────────────
def _app_secret() -> str:
    if 'app_secret' not in _cache:
        raw = _secrets.get_secret_value(SecretId=TOKEN_SECRET).get('SecretString', '') or '{}'
        try:
            _cache['app_secret'] = (json.loads(raw).get('app_secret') or '').strip()
        except json.JSONDecodeError:
            _cache['app_secret'] = ''
    return _cache['app_secret']


def _graph(method: str, path: str, token: str = '', params: dict = None, payload: dict = None) -> dict:
    url = f'{GRAPH_BASE}/{path}'
    if params:
        url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
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
    return _graph('GET', 'oauth/access_token', params={
        'client_id': APP_ID, 'client_secret': _app_secret(), 'code': code,
    })


# ── onboarding steps ──────────────────────────────────────────────────────
def _share_credit_line(waba_id: str, token: str, currency: str) -> dict:
    """Step: share the solution-partner line of credit with the client WABA."""
    if not EXTENDED_CREDIT_ID:
        return {'step': 'share_credit_line', 'ok': None, 'detail': 'skipped (no line of credit configured)'}
    res = _graph('POST', f'{EXTENDED_CREDIT_ID}/whatsapp_credit_sharing_and_attach', token=token,
                 params={'waba_id': waba_id, 'waba_currency': currency or 'USD'})
    if res.get('error'):
        return {'step': 'share_credit_line', 'ok': False, 'detail': res['error'].get('message')}
    return {'step': 'share_credit_line', 'ok': True,
            'detail': res.get('allocation_config_id') or res.get('id') or 'shared'}


def _subscribe_app(waba_id: str, token: str) -> dict:
    res = _graph('POST', f'{waba_id}/subscribed_apps', token=token, payload={})
    if res.get('error'):
        return {'step': 'subscribe_app', 'ok': False, 'detail': res['error'].get('message')}
    return {'step': 'subscribe_app', 'ok': bool(res.get('success', True)), 'detail': 'subscribed'}


def _register_phone(phone_number_id: str, token: str, pin: str) -> dict:
    """Register the number for Cloud API. For a migrated number this re-associates
    it with the destination WABA (client must have disabled 2FA first)."""
    if not pin:
        return {'step': 'register_phone', 'ok': None, 'detail': 'skipped (no PIN provided)'}
    res = _graph('POST', f'{phone_number_id}/register', token=token,
                 payload={'messaging_product': 'whatsapp', 'pin': pin})
    if res.get('error'):
        return {'step': 'register_phone', 'ok': False, 'detail': res['error'].get('message')}
    return {'step': 'register_phone', 'ok': bool(res.get('success', True)), 'detail': 'registered'}


def _fetch_details(waba_id: str, phone_number_id: str, token: str) -> dict:
    out = {}
    if waba_id:
        w = _graph('GET', waba_id, token=token,
                   params={'fields': 'id,name,currency,account_review_status,timezone_id'})
        if not w.get('error'):
            out['waba'] = {'name': w.get('name'), 'currency': w.get('currency'),
                           'reviewStatus': w.get('account_review_status')}
    if phone_number_id:
        p = _graph('GET', phone_number_id, token=token,
                   params={'fields': 'id,display_phone_number,verified_name,quality_rating,'
                                     'code_verification_status,platform_type'})
        if not p.get('error'):
            out['phone'] = {'display': p.get('display_phone_number'), 'name': p.get('verified_name'),
                            'quality': p.get('quality_rating'),
                            'codeStatus': p.get('code_verification_status'),
                            'platform': p.get('platform_type')}
    return out


# ── persistence ───────────────────────────────────────────────────────────
def _store_token(waba_id: str, token: str, expires_in: int = 0) -> bool:
    now = datetime.now(timezone.utc)
    ttl = expires_in if expires_in and expires_in > 0 else 60 * 24 * 3600
    secret_name = f'wecare/partners/{waba_id}'
    payload = json.dumps({
        'access_token': token, 'wabaId': waba_id, 'updatedAt': now.isoformat(),
        'expiresAt': datetime.fromtimestamp(now.timestamp() + ttl, tz=timezone.utc).isoformat(),
    })
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
        _ddb.Table(SYSTEM_CONFIG_TABLE).put_item(Item={
            'id': f"partner_tenant_{record['wabaId']}",
            'configValue': json.dumps(record), 'updatedAt': record.get('connectedAt', ''),
        })
    except Exception as e:  # noqa: BLE001
        logger.error(json.dumps({'event': 'partner_tenant_persist_error', 'error': str(e)}))


def _list_tenants() -> list:
    tenants = []
    table = _ddb.Table(SYSTEM_CONFIG_TABLE)
    kwargs = {'FilterExpression': 'begins_with(id, :p)', 'ExpressionAttributeValues': {':p': 'partner_tenant_'}}
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get('Items', []):
            try:
                tenants.append(json.loads(item.get('configValue', '{}')))
            except json.JSONDecodeError:
                continue
        lek = resp.get('LastEvaluatedKey')
        if not lek:
            break
        kwargs['ExclusiveStartKey'] = lek
    return tenants


# ── HTTP handlers ─────────────────────────────────────────────────────────
def _do_onboard(body: dict, origin: str, request_id: str):
    code = (body.get('code') or '').strip()
    waba_id = (body.get('wabaId') or '').strip()
    phone_number_id = (body.get('phoneNumberId') or '').strip()
    business_id = (body.get('businessId') or '').strip()
    mode = (body.get('mode') or 'onboard').strip()          # 'onboard' | 'migrate'
    pin = (body.get('pin') or REG_PIN or '').strip()
    currency = (body.get('currency') or 'USD').strip()
    customer_email = (body.get('customerEmail') or '').strip()

    if not code:
        return cors_response(400, {'error': 'Missing authorization code'}, origin)

    logger.info(json.dumps({'event': 'partner_onboarding_start', 'mode': mode, 'wabaId': waba_id,
                            'phoneNumberId': phone_number_id, 'requestId': request_id}))

    token_resp = _exchange_code(code)
    if token_resp.get('error') or not token_resp.get('access_token'):
        err = token_resp.get('error', {})
        return cors_response(400, {'success': False, 'error': err.get('message', 'Code exchange failed')}, origin)
    token = token_resp['access_token']
    expires_in = int(token_resp.get('expires_in') or 0)

    steps = []
    if waba_id:
        steps.append(_share_credit_line(waba_id, token, currency))
        steps.append(_subscribe_app(waba_id, token))
    if phone_number_id:
        steps.append(_register_phone(phone_number_id, token, pin))
    details = _fetch_details(waba_id, phone_number_id, token)

    # Provision the customer's limited-access login (scoped to their WABA)
    if customer_email and waba_id:
        steps.append(_provision_customer_user(customer_email, waba_id))

    connected_at = datetime.now(timezone.utc).isoformat()
    token_stored = _store_token(waba_id or f'unknown-{request_id}', token, expires_in)
    _persist_tenant({
        'wabaId': waba_id, 'phoneNumberId': phone_number_id, 'businessId': business_id,
        'customerEmail': customer_email, 'mode': mode, 'connectedAt': connected_at,
        'status': 'CONNECTED', 'steps': steps, 'details': details, 'tokenStored': token_stored,
    })

    record_audit(action=f'partner.{mode}', actor=(customer_email or 'self-serve'),
                 resource_type='partner_waba', resource_id=waba_id,
                 details={'phoneNumberId': phone_number_id, 'steps': steps})
    logger.info(json.dumps({'event': 'partner_onboarding_done', 'mode': mode, 'wabaId': waba_id,
                            'steps': steps, 'requestId': request_id}))
    return cors_response(200, {
        'success': True, 'mode': mode, 'wabaId': waba_id, 'phoneNumberId': phone_number_id,
        'businessId': business_id, 'connectedAt': connected_at, 'steps': steps, 'details': details,
    }, origin)


ADMIN_ROLES = {'Admin', 'Operator'}


def _auth_ctx(event: dict) -> dict:
    a = event.get('_auth') or {}
    attrs = a.get('attributes') or {}
    return {
        'role': a.get('role', 'Viewer'),
        'isAdmin': a.get('role') in ADMIN_ROLES,
        'wabaId': (attrs.get('custom:partner_waba_id') or '').strip(),
        'username': a.get('username', ''),
    }


def _do_list(event: dict, origin: str):
    """Admin/Operator → all tenants. Customer (Viewer) → only their own WABA
    (scoped by the custom:partner_waba_id Cognito attribute)."""
    ctx = _auth_ctx(event)
    tenants = _list_tenants()  # records contain no tokens/secrets
    if not ctx['isAdmin']:
        tenants = [t for t in tenants if t.get('wabaId') and t.get('wabaId') == ctx['wabaId']]
    return cors_response(200, {'tenants': tenants, 'count': len(tenants), 'scope': ctx['role']}, origin)


def _do_me(event: dict, origin: str):
    """Customer self-view: return only the caller's own linked tenant."""
    ctx = _auth_ctx(event)
    if ctx['isAdmin']:
        # admins have no single 'own' tenant; direct them to the full list
        return cors_response(200, {'tenant': None, 'isAdmin': True}, origin)
    if not ctx['wabaId']:
        return cors_response(200, {'tenant': None, 'linked': False}, origin)
    for t in _list_tenants():
        if t.get('wabaId') == ctx['wabaId']:
            return cors_response(200, {'tenant': t, 'linked': True}, origin)
    return cors_response(200, {'tenant': None, 'linked': False}, origin)


def _do_disconnect(event: dict, waba_id: str, origin: str):
    if not waba_id:
        return cors_response(400, {'error': 'wabaId required'}, origin)
    actor = (event.get('_auth') or {}).get('username', 'admin')
    cleanup = {'cognitoDisabled': None, 'walletSuspended': None}
    try:
        table = _ddb.Table(SYSTEM_CONFIG_TABLE)
        item = table.get_item(Key={'id': f'partner_tenant_{waba_id}'}).get('Item')
        rec = json.loads(item['configValue']) if item else {'wabaId': waba_id}

        # Disable the customer's Cognito login (best-effort)
        cust_email = rec.get('customerEmail')
        if cust_email:
            try:
                _cognito.admin_disable_user(UserPoolId=USER_POOL_ID, Username=cust_email)
                cleanup['cognitoDisabled'] = True
            except Exception as e:  # noqa: BLE001
                cleanup['cognitoDisabled'] = False
                logger.warning(json.dumps({'event': 'partner_cognito_disable_error', 'error': str(e)}))

        # Suspend the wallet so no further sends/metering occur (best-effort)
        try:
            w = billing.get_wallet(waba_id)
            if w:
                billing._wallet_tbl().update_item(  # noqa: SLF001
                    Key={'wabaId': waba_id}, UpdateExpression='SET #s = :s',
                    ExpressionAttributeNames={'#s': 'status'}, ExpressionAttributeValues={':s': 'SUSPENDED'})
                cleanup['walletSuspended'] = True
        except Exception as e:  # noqa: BLE001
            logger.warning(json.dumps({'event': 'partner_wallet_suspend_error', 'error': str(e)}))

        rec['status'] = 'DISCONNECTED'
        rec['disconnectedAt'] = datetime.now(timezone.utc).isoformat()
        rec['disconnectedBy'] = actor
        table.put_item(Item={'id': f'partner_tenant_{waba_id}', 'configValue': json.dumps(rec),
                             'updatedAt': rec['disconnectedAt']})
    except Exception as e:  # noqa: BLE001
        return cors_response(500, {'error': str(e)}, origin)

    record_audit(action='partner.disconnect', actor=actor, resource_type='partner_waba',
                 resource_id=waba_id, details=cleanup)
    return cors_response(200, {'success': True, 'wabaId': waba_id, 'status': 'DISCONNECTED', 'cleanup': cleanup}, origin)


def _do_billing_get(event: dict, origin: str):
    """Admin → all wallets. Customer → own wallet + recent ledger."""
    ctx = _auth_ctx(event)
    if ctx['isAdmin']:
        return cors_response(200, {'wallets': billing.list_wallets(), 'rateCard': billing.RATE_CARD}, origin)
    if not ctx['wabaId']:
        return cors_response(200, {'wallet': None, 'ledger': []}, origin)
    return cors_response(200, {
        'wallet': billing.get_wallet(ctx['wabaId']) or None,
        'ledger': billing.recent_ledger(ctx['wabaId'], limit=20),
    }, origin)


def _do_topup(event: dict, body: dict, origin: str):
    waba_id = (body.get('wabaId') or '').strip()
    try:
        amount = float(body.get('amount') or 0)
    except (TypeError, ValueError):
        return cors_response(400, {'error': 'Invalid amount'}, origin)
    if not waba_id or amount <= 0:
        return cors_response(400, {'error': 'wabaId and positive amount required'}, origin)
    actor = (event.get('_auth') or {}).get('username', 'admin')
    res = billing.topup(waba_id, amount, note=(body.get('note') or ''), actor=actor,
                        currency=(body.get('currency') or None))
    record_audit(action='partner.topup', actor=actor, resource_type='partner_wallet',
                 resource_id=waba_id, details={'amount': amount, 'balance': res.get('balance')})
    return cors_response(200, {'success': True, **res}, origin)


def handler(event, context):
    request_id = getattr(context, 'aws_request_id', 'local')
    origin = extract_origin(event)

    # Internal Lambda-to-Lambda metering: {action:'charge', wabaId, category, messageId, amount?}
    if event.get('action') == 'charge' and not event.get('requestContext'):
        return billing.charge(event.get('wabaId', ''), amount=event.get('amount'),
                              category=event.get('category', ''), message_id=event.get('messageId', ''),
                              note=event.get('note', ''))

    rc = event.get('requestContext', {})
    method = rc.get('http', {}).get('method') or event.get('httpMethod', 'POST')
    path = rc.get('http', {}).get('path') or event.get('rawPath', '') or event.get('path', '')
    source_ip = (rc.get('http', {}) or {}).get('sourceIp') or rc.get('identity', {}).get('sourceIp', 'unknown')
    qs = event.get('queryStringParameters') or {}

    if method == 'OPTIONS':
        return options_response(origin)

    # Customer self-view (any authenticated user): only their own tenant
    if '/partners/me' in path:
        auth = require_auth(event)
        if auth is not None:
            return auth
        return _do_me(event, origin)

    # Billing: top-up (Admin) / view wallets (admin all, customer own)
    if '/partners/billing' in path:
        if '/topup' in path and method == 'POST':
            auth = require_auth(event, required_role='Admin')
            if auth is not None:
                return auth
            try:
                body = json.loads(event.get('body') or '{}')
            except json.JSONDecodeError:
                return cors_response(400, {'error': 'Invalid JSON body'}, origin)
            return _do_topup(event, body, origin)
        if method == 'GET':
            auth = require_auth(event)
            if auth is not None:
                return auth
            return _do_billing_get(event, origin)
        return cors_response(405, {'error': 'Method not allowed'}, origin)

    # Tenant management: GET (role-scoped list) / DELETE (Admin-only)
    if '/partners/tenants' in path or method in ('GET', 'DELETE'):
        if method == 'DELETE':
            auth = require_auth(event, required_role='Admin')
            if auth is not None:
                return auth
            return _do_disconnect(event, (qs.get('wabaId') or '').strip(), origin)
        if method == 'GET':
            auth = require_auth(event)
            if auth is not None:
                return auth
            return _do_list(event, origin)
        return cors_response(405, {'error': 'Method not allowed'}, origin)

    # Public onboarding endpoint
    if method != 'POST':
        return cors_response(405, {'error': 'Method not allowed'}, origin)
    if not check_rate_limit('partner-onboarding', source_ip, max_per_second=2):
        return cors_response(429, {'error': 'Too many requests. Please retry shortly.'}, origin)
    try:
        body = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return cors_response(400, {'error': 'Invalid JSON body'}, origin)
    return _do_onboard(body, origin, request_id)
