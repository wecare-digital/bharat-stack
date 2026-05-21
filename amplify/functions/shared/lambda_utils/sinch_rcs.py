"""
Sinch RCS Notification Utility

Shared module for sending RCS messages via Sinch India Conversation API.
Used by: voice-in/cdr, whatsapp-calling, order notifications.

Authentication:
  Token endpoint: POST https://auth.aclwhatsapp.com/realms/ipmessaging/protocol/openid-connect/token
  Grant type: password
  Client ID: ipmessaging-client
  Username/Password from Secrets Manager: wecare/sinch/rcs

Send API:
  POST https://convapi.aclwhatsapp.com/v1/projects/{projectId}/messages:send
  Authorization: Bearer <token>

Config:
  - AWS Secret: wecare/sinch/rcs (keys: username, password, project_id, app_id)
  - Env: SINCH_RCS_ENABLED=true to activate

Templates (approved, Jio, MEDIUM height):
  - rcsmenu — IVR/call disconnect notifications
  - rcsorder — order confirmation notifications
  - waalert — WhatsApp alert notifications
"""

import os
import json
import time
import logging
import urllib.request
import urllib.error
import urllib.parse
import boto3

logger = logging.getLogger(__name__)

# Auth and API endpoints (same as rcs-send handler — the working one)
RCS_AUTH_URL = "https://auth.aclwhatsapp.com/realms/ipmessaging/protocol/openid-connect/token"
RCS_API_BASE = "https://convapi.aclwhatsapp.com/v1/projects"

# Cache credentials and token
_sinch_cache = {}
_token_cache = {'token': '', 'expires_at': 0, 'refresh_token': '', 'refresh_expires_at': 0}
_secrets_client = None


def _get_secrets_client():
    global _secrets_client
    if not _secrets_client:
        _secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
    return _secrets_client


def is_rcs_enabled() -> bool:
    """Check if Sinch RCS is enabled via environment variable."""
    return os.environ.get('SINCH_RCS_ENABLED', 'false').lower() == 'true'


def _load_sinch_credentials() -> dict:
    """Load Sinch credentials from Secrets Manager (cached)."""
    if _sinch_cache.get('loaded'):
        return _sinch_cache

    try:
        client = _get_secrets_client()
        resp = client.get_secret_value(SecretId='wecare/sinch/rcs')
        data = json.loads(resp['SecretString'])
        _sinch_cache.update({
            'username': data.get('username', 'wecaretrans'),
            'password': data.get('password', ''),
            'project_id': data.get('project_id', 'c8114d03-eeb2-401d-a8f1-abb93594cb33'),
            'app_id': data.get('app_id', '01KQSB792X3R148D8ZGHQYW3SP'),
            'loaded': True,
        })
        return _sinch_cache
    except Exception as e:
        logger.error(f'Sinch RCS credentials not available: {e}')
        return {}


def _get_token() -> str:
    """Get valid RCS auth token (cached, auto-refresh via username/password).
    
    Uses the same auth flow as rcs-send/handler.py which works correctly.
    """
    now = int(time.time())

    # Return cached token if still valid (with 30s buffer)
    if _token_cache['token'] and _token_cache['expires_at'] > now + 30:
        return _token_cache['token']

    # Try refresh token if available
    if _token_cache['refresh_token'] and _token_cache['refresh_expires_at'] > now + 30:
        token = _refresh_token()
        if token:
            return token

    # Full auth with username/password
    return _authenticate()


def _authenticate() -> str:
    """Authenticate with Sinch RCS using username/password grant."""
    creds = _load_sinch_credentials()
    username = creds.get('username', 'wecaretrans')
    password = creds.get('password', '')

    if not password:
        logger.error("RCS: No password in wecare/sinch/rcs secret — cannot authenticate")
        return ''

    body = urllib.parse.urlencode({
        'grant_type': 'password',
        'client_id': 'ipmessaging-client',
        'username': username,
        'password': password,
    }).encode()

    # Try both URL variants (same as rcs-send handler)
    urls = [
        RCS_AUTH_URL,
        "https://auth.aclwhatsapp.com/auth/realms/ipmessaging/protocol/openid-connect/token",
    ]

    for url in urls:
        try:
            req = urllib.request.Request(url, data=body, headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'cache-control': 'no-cache',
            }, method='POST')

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                token = data.get('access_token', '')
                if token:
                    now = int(time.time())
                    _token_cache['token'] = token
                    _token_cache['expires_at'] = now + data.get('expires_in', 300)
                    _token_cache['refresh_token'] = data.get('refresh_token', '')
                    _token_cache['refresh_expires_at'] = now + data.get('refresh_expires_in', 1800)
                    logger.info(f"RCS auth success, expires_in={data.get('expires_in')}s")
                    return token
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:100] if e.fp else ''
            logger.warning(f"RCS auth failed ({url}): HTTP {e.code} - {err}")
        except Exception as e:
            logger.warning(f"RCS auth error ({url}): {e}")

    logger.error("RCS auth FAILED on all URLs — check wecare/sinch/rcs password")
    return ''


def _refresh_token() -> str:
    """Refresh the RCS auth token."""
    body = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'client_id': 'ipmessaging-client',
        'refresh_token': _token_cache['refresh_token'],
    }).encode()

    try:
        req = urllib.request.Request(RCS_AUTH_URL, data=body, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'cache-control': 'no-cache',
        }, method='POST')

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            token = data.get('access_token', '')
            if token:
                now = int(time.time())
                _token_cache['token'] = token
                _token_cache['expires_at'] = now + data.get('expires_in', 300)
                _token_cache['refresh_token'] = data.get('refresh_token', '')
                _token_cache['refresh_expires_at'] = now + data.get('refresh_expires_in', 1800)
                return token
    except Exception as e:
        logger.warning(f"RCS token refresh failed: {e}")

    return ''


def _normalize_phone(phone: str) -> str:
    """Normalize phone for RCS — Sinch requires digits only WITHOUT + prefix.
    
    Sinch Conversation API identity format: "919903300044" (no + prefix).
    """
    clean = phone.replace('+', '').replace(' ', '').replace('-', '')
    if len(clean) == 10:
        clean = '91' + clean
    return clean


def send_rcs_text(phone: str, text: str, correlation_id: str = '') -> dict:
    """Send a plain text RCS message via Sinch Conversation API."""
    if not is_rcs_enabled():
        return {'success': False, 'error': 'RCS not enabled'}

    creds = _load_sinch_credentials()
    if not creds.get('project_id') or not creds.get('app_id'):
        return {'success': False, 'error': 'Sinch credentials not configured'}

    identity = _normalize_phone(phone)
    payload = {
        'app_id': creds['app_id'],
        'recipient': {
            'identified_by': {
                'channel_identities': [
                    {'channel': 'RCS', 'identity': identity}
                ]
            }
        },
        'message': {
            'text_message': {
                'text': text
            }
        },
    }

    return _send_sinch_message(payload)


def send_rcs_card(phone: str, title: str, description: str,
                  media_url: str = '', choices: list = None,
                  correlation_id: str = '') -> dict:
    """Send an RCS rich card via Sinch Conversation API."""
    if not is_rcs_enabled():
        return {'success': False, 'error': 'RCS not enabled'}

    creds = _load_sinch_credentials()
    if not creds.get('project_id') or not creds.get('app_id'):
        return {'success': False, 'error': 'Sinch credentials not configured'}

    identity = _normalize_phone(phone)

    card = {
        'title': title,
        'description': description,
    }
    if media_url:
        card['media_message'] = {'url': media_url}
    if choices:
        card['choices'] = [
            {'url_message': {'title': c['title'], 'url': c['url']}}
            for c in choices
        ]

    payload = {
        'app_id': creds['app_id'],
        'recipient': {
            'identified_by': {
                'channel_identities': [
                    {'channel': 'RCS', 'identity': identity}
                ]
            }
        },
        'message': {
            'card_message': card
        },
    }

    return _send_sinch_message(payload)


def send_rcs_template(phone: str, template_id: str = 'rcsmenu',
                     language: str = 'en', parameters: dict = None,
                     correlation_id: str = '') -> dict:
    """Send an RCS template message via Sinch Conversation API."""
    if not is_rcs_enabled():
        return {'success': False, 'error': 'RCS not enabled'}

    creds = _load_sinch_credentials()
    if not creds.get('project_id') or not creds.get('app_id'):
        return {'success': False, 'error': 'Sinch credentials not configured'}

    identity = _normalize_phone(phone)
    payload = {
        'app_id': creds['app_id'],
        'recipient': {
            'identified_by': {
                'channel_identities': [
                    {'channel': 'RCS', 'identity': identity}
                ]
            }
        },
        'message': {
            'template_message': {
                'channel_template': {
                    'RCS': {
                        'template_id': template_id,
                        'language_code': language,
                    }
                }
            }
        },
    }
    if parameters:
        payload['message']['template_message']['channel_template']['RCS']['parameters'] = parameters

    return _send_sinch_message(payload)


def send_rcs_ivr_notification(phone: str, request_id: str = '') -> dict:
    """Send the standard IVR/call disconnect RCS notification.

    Uses the approved 'rcsmenu' template (rich_card, MEDIUM height, Jio vendor).
    Template ID: rcsmenu | Status: approved | Enterprise: WECARE DIGITAL
    Content: Video card + "Get Started" button → https://r.wecare.digital/getstarted

    Fallback: If template send fails, sends as direct card_message.
    Used by: CDR inbound calls, WhatsApp calling disconnect.
    """
    normalized = _normalize_phone(phone)
    if not normalized or len(normalized) < 10:
        logger.warning(f'RCS IVR skipped — invalid phone: {phone}')
        return {'success': False, 'error': f'Invalid phone number: {phone}'}

    logger.info(f'RCS IVR sending to ...{normalized[-4:]} (template=rcsmenu, request_id={request_id})')

    # Primary: Send via approved 'rcsmenu' template
    result = send_rcs_template(
        phone=phone,
        template_id='rcsmenu',
    )

    if result.get('success'):
        logger.info(f'RCS IVR delivered: message_id={result.get("message_id", "")} phone=...{normalized[-4:]}')
        return result

    # Fallback: If template fails, send as direct rich card
    error_msg = result.get('error', 'unknown')
    logger.warning(f'rcsmenu template failed ({error_msg}), falling back to card_message')
    result = send_rcs_card(
        phone=phone,
        title='Thanks for contacting WECARE.DIGITAL!',
        description=(
            'Submit your request here: https://wecare.digital/selfservice '
            'or send us a message / voice note on WhatsApp: https://r.wecare.digital/wa.\n\n'
            "We'll review it and follow up if needed.\nWECARE.DIGITAL"
        ),
        media_url='https://app.wecare.digital/stream/media/m/selfservice.mp4',
        choices=[
            {'title': 'Get Started', 'url': 'https://r.wecare.digital/getstarted'},
        ],
    )

    if not result.get('success'):
        logger.error(f'RCS IVR card_message ALSO FAILED: phone=...{normalized[-4:]}, '
                     f'error={result.get("error", "unknown")}')

    return result


def send_rcs_order_notification(phone: str, order_id: str = '',
                                 wd_order_id: str = '') -> dict:
    """Send order confirmation RCS notification.

    Uses the approved 'rcsorder' template (rich_card, MEDIUM height, Jio vendor).
    """
    result = send_rcs_template(
        phone=phone,
        template_id='rcsorder',
    )

    if not result.get('success'):
        logger.info(f'rcsorder template failed, falling back to card_message')
        desc = (
            "Your order has been received. We'll review it and share updates shortly.\n\n"
            "Need help? Submit a request here: https://wecare.digital/selfservice "
            "or message / voice note us on WhatsApp: https://r.wecare.digital/wa.\n"
            "WECARE.DIGITAL"
        )
        if wd_order_id:
            desc = f"Order {wd_order_id} confirmed!\n\n" + desc

        result = send_rcs_card(
            phone=phone,
            title='Thanks for placing your order with WECARE.DIGITAL!',
            description=desc,
            media_url='https://app.wecare.digital/stream/media/m/selfservice.mp4',
            choices=[
                {'title': 'Get Started', 'url': 'https://r.wecare.digital/getstarted'},
            ],
        )

    return result


def send_rcs_wa_alert(phone: str, request_id: str = '') -> dict:
    """Send WA-Alert style RCS notification.

    Uses the approved 'waalert' template (rich_card, MEDIUM height, Jio vendor).
    """
    result = send_rcs_template(
        phone=phone,
        template_id='waalert',
    )

    if not result.get('success'):
        logger.info(f'waalert template failed, falling back to text')
        result = send_rcs_text(
            phone=phone,
            text="We've sent an essential notification about your order/request to your registered WhatsApp number. Your prompt attention is appreciated. WECARE.DIGITAL",
        )

    return result


def _send_sinch_message(payload: dict) -> dict:
    """Send message via Sinch Conversation API (convapi.aclwhatsapp.com).
    
    Uses the same API endpoint as rcs-send/handler.py which works correctly.
    Authenticates via username/password OAuth (auto-refresh).
    """
    creds = _load_sinch_credentials()
    project_id = creds.get('project_id', '')
    if not project_id:
        return {'success': False, 'error': 'No project_id configured'}

    token = _get_token()
    if not token:
        return {'success': False, 'error': 'RCS auth failed — check wecare/sinch/rcs password'}

    url = f'{RCS_API_BASE}/{project_id}/messages:send'
    data = json.dumps(payload).encode('utf-8')
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    # Extract recipient for logging
    recipient_identity = ''
    try:
        identities = payload.get('recipient', {}).get('identified_by', {}).get('channel_identities', [])
        if identities:
            recipient_identity = identities[0].get('identity', '')[-4:]
    except (KeyError, IndexError):
        pass

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                msg_id = result.get('message_id', '')
                logger.info(f'RCS sent: message_id={msg_id} phone=...{recipient_identity}')
                return {'success': True, 'message_id': msg_id, 'response': result}

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''

            # On 401, token may have expired mid-request — re-auth and retry
            if e.code == 401 and attempt < max_retries:
                logger.info('RCS 401 — re-authenticating...')
                _token_cache['token'] = ''
                _token_cache['expires_at'] = 0
                new_token = _authenticate()
                if new_token:
                    headers['Authorization'] = f'Bearer {new_token}'
                    continue

            if e.code in (502, 503) and attempt < max_retries:
                time.sleep((attempt + 1) * 2)
                continue

            logger.error(f'RCS send FAILED: HTTP {e.code} | {error_body[:200]} | phone=...{recipient_identity}')
            return {'success': False, 'error': f'HTTP {e.code}: {error_body[:200]}'}

        except Exception as e:
            if attempt < max_retries:
                time.sleep((attempt + 1) * 2)
                continue
            logger.error(f'RCS send error: {e} | phone=...{recipient_identity}')
            return {'success': False, 'error': str(e)}

    return {'success': False, 'error': 'All retries failed'}
