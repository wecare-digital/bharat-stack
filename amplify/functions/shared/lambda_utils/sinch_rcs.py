"""
Sinch RCS Notification Utility

Shared module for sending RCS messages via Sinch Conversation API.
Used by: voice-in/cdr, whatsapp-calling, order notifications, RCS inbox.

Sinch Conversation API:
  POST https://{region}.conversation.api.sinch.com/v1/projects/{project_id}/messages:send

Config:
  - AWS Secret: wecare/sinch/rcs
  - Env: SINCH_RCS_ENABLED=true to activate
  - Sinch must whitelist IP: 52.3.44.165

Secret keys:
  - project_id: Sinch project ID
  - app_id: Sinch Conversation app ID
  - key_id: Sinch API key ID
  - key_secret: Sinch API key secret
  - oauth_token: Pre-generated OAuth token (or generate from key_id/key_secret)
  - region: eu (default) or us

DLT fields (for SMS fallback via Sinch, if enabled):
  - dlt_principal_entity_id: 1201161991108627443
  - dlt_template_id: per template
  - sender_id: WDBEEP
"""

import os
import json
import logging
import urllib.request
import urllib.error
import boto3

logger = logging.getLogger(__name__)

# Cache Sinch credentials
_sinch_cache = {}
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
            'project_id': data.get('project_id', ''),
            'app_id': data.get('app_id', ''),
            'oauth_token': data.get('oauth_token', ''),
            'key_id': data.get('key_id', ''),
            'key_secret': data.get('key_secret', ''),
            'region': data.get('region', 'eu'),
            'loaded': True,
        })
        return _sinch_cache
    except Exception as e:
        logger.info(f'Sinch RCS credentials not available: {e}')
        return {}


def _normalize_phone(phone: str) -> str:
    """Normalize phone to E.164 format (+91XXXXXXXXXX)."""
    clean = phone.replace('+', '').replace(' ', '').replace('-', '')
    if len(clean) == 10:
        clean = '91' + clean
    return '+' + clean if not clean.startswith('+') else clean


def send_rcs_text(phone: str, text: str, correlation_id: str = '') -> dict:
    """Send a plain text RCS message via Sinch Conversation API.

    Returns: {'success': True, 'message_id': '...'} or {'success': False, 'error': '...'}
    """
    if not is_rcs_enabled():
        return {'success': False, 'error': 'RCS not enabled'}

    creds = _load_sinch_credentials()
    if not creds.get('project_id') or not creds.get('app_id') or not creds.get('oauth_token'):
        return {'success': False, 'error': 'Sinch credentials not configured'}

    e164 = _normalize_phone(phone)
    payload = {
        'app_id': creds['app_id'],
        'recipient': {
            'identified_by': {
                'channel_identities': [
                    {'channel': 'RCS', 'identity': e164}
                ]
            }
        },
        'message': {
            'text_message': {
                'text': text
            }
        },
        'channel_priority_order': ['RCS'],
        'message_content_type': 'CONTENT_NOTIFICATION',
    }
    if correlation_id:
        payload['correlation_id'] = correlation_id

    return _send_sinch_message(creds, payload)


def send_rcs_card(phone: str, title: str, description: str,
                  media_url: str = '', choices: list = None,
                  correlation_id: str = '') -> dict:
    """Send an RCS rich card via Sinch Conversation API.

    choices: list of {'title': '...', 'url': '...'} dicts for URL buttons
    Returns: {'success': True, 'message_id': '...'} or {'success': False, 'error': '...'}
    """
    if not is_rcs_enabled():
        return {'success': False, 'error': 'RCS not enabled'}

    creds = _load_sinch_credentials()
    if not creds.get('project_id') or not creds.get('app_id') or not creds.get('oauth_token'):
        return {'success': False, 'error': 'Sinch credentials not configured'}

    e164 = _normalize_phone(phone)

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
                    {'channel': 'RCS', 'identity': e164}
                ]
            }
        },
        'message': {
            'card_message': card
        },
        'channel_priority_order': ['RCS'],
        'message_content_type': 'CONTENT_NOTIFICATION',
    }
    if correlation_id:
        payload['correlation_id'] = correlation_id

    return _send_sinch_message(creds, payload)


def send_rcs_ivr_notification(phone: str, request_id: str = '') -> dict:
    """Send the standard IVR/call disconnect RCS notification.

    Rich card with video + Submit Request + WhatsApp Us buttons.
    Used by: CDR inbound calls, WhatsApp calling disconnect.
    """
    return send_rcs_card(
        phone=phone,
        title='WECARE.DIGITAL',
        description='Thanks for contacting WECARE.DIGITAL! Submit your request or message us on WhatsApp.',
        media_url='https://app.wecare.digital/stream/media/m/selfservice.mp4',
        choices=[
            {'title': 'Submit Request', 'url': 'https://wecare.digital/selfservice'},
            {'title': 'WhatsApp Us', 'url': 'https://r.wecare.digital/wa'},
        ],
        correlation_id=f'ivr_{request_id}' if request_id else '',
    )


def send_rcs_order_notification(phone: str, order_id: str = '',
                                 wd_order_id: str = '') -> dict:
    """Send order confirmation RCS notification.

    Rich card with order details + Track Order + WhatsApp Us buttons.
    Used by: Wix store order events, order notification Lambda.
    """
    desc = "Thanks for placing your order with WECARE.DIGITAL! Your order has been received. We'll review it and share updates shortly."
    if wd_order_id:
        desc = f"Order {wd_order_id} confirmed! " + desc

    return send_rcs_card(
        phone=phone,
        title='Order Confirmed — WECARE.DIGITAL',
        description=desc,
        choices=[
            {'title': 'Track Order', 'url': 'https://wecare.digital/selfservice'},
            {'title': 'WhatsApp Us', 'url': 'https://r.wecare.digital/wa'},
        ],
        correlation_id=f'order_{order_id}' if order_id else '',
    )


def send_rcs_wa_alert(phone: str, request_id: str = '') -> dict:
    """Send WA-Alert style RCS notification.

    Text message nudging user to check WhatsApp.
    """
    return send_rcs_text(
        phone=phone,
        text="We've sent an essential notification about your order/request to your registered WhatsApp number. Your prompt attention is appreciated. WECARE.DIGITAL",
        correlation_id=f'wa_alert_{request_id}' if request_id else '',
    )


def _send_sinch_message(creds: dict, payload: dict) -> dict:
    """Send message via Sinch Conversation API with retry on 503."""
    project_id = creds['project_id']
    region = creds.get('region', 'eu')
    token = creds['oauth_token']

    url = f'https://{region}.conversation.api.sinch.com/v1/projects/{project_id}/messages:send'
    data = json.dumps(payload).encode('utf-8')
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                msg_id = result.get('message_id', '')
                logger.info(json.dumps({
                    'event': 'sinch_rcs_sent',
                    'messageId': msg_id,
                    'attempt': attempt + 1,
                }))
                return {'success': True, 'message_id': msg_id, 'response': result}

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            if e.code in (502, 503) and attempt < max_retries - 1:
                import time
                time.sleep((attempt + 1) * 2)
                continue
            logger.error(f'Sinch RCS HTTP {e.code}: {error_body[:200]}')
            return {'success': False, 'error': f'HTTP {e.code}: {error_body[:200]}'}

        except Exception as e:
            if attempt < max_retries - 1:
                import time
                time.sleep((attempt + 1) * 2)
                continue
            logger.error(f'Sinch RCS error: {e}')
            return {'success': False, 'error': str(e)}

    return {'success': False, 'error': 'All retries failed'}
