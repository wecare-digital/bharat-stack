"""
Sinch RCS Send Lambda Function

Purpose: Send RCS messages via Sinch India Conversation API
Enterprise: WECARE.DIGITAL
App ID: wecaretrans
BOT Type: Transactional
Project ID: c8114d03-eeb2-401d-a8f1-abb93594cb33
Conv App ID: 01KQSB792X3R148D8ZGHQYW3SP

Authentication:
- Token endpoint: POST https://auth.aclwhatsapp.com/realms/ipmessaging/protocol/openid-connect/token
- Grant type: password
- Client ID: ipmessaging-client
- Username/Password from Secrets Manager: wecare/sinch/rcs

Send API:
- POST https://convapi.aclwhatsapp.com/v1/projects/{projectId}/messages:send
- Authorization: Bearer <token>

DLR Webhook: POST https://api.wecare.digital/webhook/sinch-rcs
DLR Events: MESSAGE_DELIVERY, EVENT_DELIVERY, MESSAGE_INBOUND, etc.

Templates:
- "rcsmenu" (Rich Card, approved, Jio, MEDIUM) — IVR/call disconnect notifications
- "rcsorder" (Rich Card, approved, Jio, MEDIUM) — order confirmation notifications
- "waalert" (Rich Card, approved, Jio, MEDIUM) — WhatsApp alert notifications
- Template creation: POST https://api.aclwhatsapp.com/access-api/v1/rcs/{botId}/templates

Secrets: wecare/sinch/rcs
Expected keys: username, password, project_id, app_id
"""

import os
import json
import uuid
import time
import logging
import boto3
import boto3.dynamodb.conditions
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.message_store import put_message  # unified MessagesTable dual-write

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Configuration
RCS_AUTH_URL = "https://auth.aclwhatsapp.com/realms/ipmessaging/protocol/openid-connect/token"
RCS_API_BASE = "https://convapi.aclwhatsapp.com/v1/projects"
RCS_PROJECT_ID = os.environ.get('RCS_PROJECT_ID', 'c8114d03-eeb2-401d-a8f1-abb93594cb33')
RCS_APP_ID = os.environ.get('RCS_APP_ID', '01KQSB792X3R148D8ZGHQYW3SP')
RCS_SECRET_NAME = os.environ.get('RCS_SECRET_NAME', 'wecare/sinch/rcs')
RCS_TABLE = os.environ.get('RCS_TABLE', 'stack-wecare-digital-RcsMessagesTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'stack-wecare-digital-WhatsAppOutboundTable')
# Canonical unified table — inbox list now reads this (channel=rcs).
UNIFIED_TABLE = os.environ.get('UNIFIED_MESSAGES_TABLE', 'stack-wecare-digital-MessagesTable')

# Token cache (reuse within Lambda warm start)
_token_cache = {'token': '', 'expires_at': 0, 'refresh_token': '', 'refresh_expires_at': 0}
_secrets_cache = None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle RCS send requests."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')

    if http_method == 'OPTIONS':
        return options_response(origin)

    from lambda_utils.middleware import require_auth
    _auth = require_auth(event)
    if _auth is not None:
        return _auth

    if http_method == 'GET':
        return cors_response(200, {'status': 'ok', 'service': 'sinch-rcs'}, origin)

    try:
        body = json.loads(event.get('body', '{}'))
    except (json.JSONDecodeError, TypeError):
        return cors_response(400, {'error': 'Invalid JSON body'}, origin)

    action = body.get('action', 'send')

    if action == 'send':
        return _send_rcs(body, request_id, origin)
    elif action == 'list':
        return _list_messages(body, request_id, origin)
    elif action == 'templates':
        return _list_templates(body, request_id, origin)
    elif action == 'create_template':
        return _create_template(body, request_id, origin)
    elif action == 'delete_template':
        return _delete_template(body, request_id, origin)
    else:
        return cors_response(400, {'error': f'Unknown action: {action}'}, origin)


def _send_rcs(body: Dict, request_id: str, origin: str) -> Dict:
    """Send RCS message via Sinch Conversation API."""
    phone = body.get('phoneNumber', body.get('to', ''))
    template_id = body.get('templateId', body.get('template', 'rcsmenu'))
    parameters = body.get('parameters', {})
    text = body.get('text', '')  # For direct text messages (no template)
    language = body.get('language', 'en')
    metadata = body.get('metadata', '')

    if not phone:
        return cors_response(400, {'error': 'phoneNumber is required'}, origin)

    # Clean phone number — identity must be WITHOUT + prefix per Sinch docs
    clean = phone.replace('+', '').replace(' ', '').replace('-', '')
    if not clean.startswith('91'):
        clean = '91' + clean[-10:]
    identity = clean  # No + prefix — Sinch requires "919876543210" format

    # Get auth token
    token = _get_token()
    if not token:
        return cors_response(500, {'error': 'Failed to authenticate with Sinch RCS'}, origin)

    # Build message payload
    send_url = f"{RCS_API_BASE}/{RCS_PROJECT_ID}/messages:send"

    if text:
        # Direct text message (no template)
        payload = {
            "app_id": RCS_APP_ID,
            "recipient": {
                "identified_by": {
                    "channel_identities": [
                        {"channel": "RCS", "identity": identity}
                    ]
                }
            },
            "message": {
                "text_message": {
                    "text": text
                }
            }
        }

        # If choices provided, use choice_message (text with buttons)
        choices = body.get('choices', [])
        if choices:
            payload["message"] = {
                "choice_message": {
                    "text_message": {"text": text},
                    "choices": choices
                }
            }

    elif body.get('card'):
        # Rich card message
        payload = {
            "app_id": RCS_APP_ID,
            "recipient": {
                "identified_by": {
                    "channel_identities": [
                        {"channel": "RCS", "identity": identity}
                    ]
                }
            },
            "message": {
                "card_message": body.get('card')
            }
        }

    elif body.get('carousel'):
        # Carousel message
        payload = {
            "app_id": RCS_APP_ID,
            "recipient": {
                "identified_by": {
                    "channel_identities": [
                        {"channel": "RCS", "identity": identity}
                    ]
                }
            },
            "message": {
                "carousel_message": body.get('carousel')
            }
        }

    else:
        # Template message
        payload = {
            "app_id": RCS_APP_ID,
            "recipient": {
                "identified_by": {
                    "channel_identities": [
                        {"channel": "RCS", "identity": identity}
                    ]
                }
            },
            "message": {
                "template_message": {
                    "channel_template": {
                        "RCS": {
                            "template_id": template_id,
                            "language_code": language,
                            "parameters": parameters
                        }
                    }
                }
            }
        }

    # Optional: RCS → SMS fallback
    if body.get('fallback'):
        payload["channel_priority_order"] = ["RCS", "SMS"]

    if metadata:
        payload["message_metadata"] = metadata[:1024]

    logger.info(json.dumps({
        'event': 'rcs_send_request',
        'phone': clean[-4:],
        'template': template_id if not text else '(text)',
        'requestId': request_id,
    }))

    # Send
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(send_url, data=data, headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        }, method='POST')

        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = resp.read().decode()
            result = json.loads(resp_body)

            message_id = result.get('message_id', str(uuid.uuid4()))
            logger.info(json.dumps({
                'event': 'rcs_send_success',
                'messageId': message_id,
                'phone': clean[-4:],
                'requestId': request_id,
            }))

            # Persist message to RCS table
            _store_rcs_message(message_id, clean, text or f'[template:{template_id}]', 'sent', template_id, metadata)

            return cors_response(200, {
                'success': True,
                'messageId': message_id,
                'channel': 'RCS',
                'provider': 'sinch-rcs',
                'status': 'sent',
            }, origin)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:300] if e.fp else ''
        logger.error(f"RCS send error: HTTP {e.code} - {error_body}")
        return cors_response(e.code, {
            'error': f'RCS API error: {error_body[:200]}',
            'success': False,
        }, origin)
    except Exception as e:
        logger.error(f"RCS send error: {e}")
        return cors_response(500, {'error': str(e), 'success': False}, origin)


def _get_token() -> str:
    """Get valid RCS auth token (cached, auto-refresh)."""
    now = int(time.time())

    # Return cached token if still valid (with 30s buffer)
    if _token_cache['token'] and _token_cache['expires_at'] > now + 30:
        return _token_cache['token']

    # Try refresh token if available
    if _token_cache['refresh_token'] and _token_cache['refresh_expires_at'] > now + 30:
        token = _refresh_token()
        if token:
            return token

    # Full auth
    return _authenticate()


def _authenticate() -> str:
    """Authenticate with Sinch RCS using username/password."""
    creds = _get_secrets()
    username = creds.get('username', 'wecaretrans')
    password = creds.get('password', '')

    if not password:
        logger.error("RCS password not configured in secrets")
        return ''

    body = urllib.parse.urlencode({
        'grant_type': 'password',
        'client_id': 'ipmessaging-client',
        'username': username,
        'password': password,
    }).encode()

    # Try both URL variants
    urls = [
        RCS_AUTH_URL,  # Without /auth/ prefix
        "https://auth.aclwhatsapp.com/auth/realms/ipmessaging/protocol/openid-connect/token",  # With /auth/
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


def _list_messages(body: Dict, request_id: str, origin: str) -> Dict:
    """List RCS messages from the canonical MessagesTable (channel=rcs).
    Reads via channel-index (bounded Query). Response shape preserved for the inbox."""
    from decimal import Decimal
    phone_filter = body.get('phoneNumber', '')
    limit = min(body.get('limit', 200), 1000)

    try:
        table = dynamodb.Table(UNIFIED_TABLE)
        resp = table.query(
            IndexName='channel-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('channel').eq('rcs'),
            ScanIndexForward=False,  # newest first
            Limit=max(limit, 200),
        )
        items = resp.get('Items', [])

        messages = []
        for item in items:
            msg = {}
            for k, v in item.items():
                msg[k] = int(v) if isinstance(v, Decimal) else v
            # Map canonical fields back to the inbox's expected shape.
            if not msg.get('phoneNumber'):
                msg['phoneNumber'] = msg.get('receivingPhone') or msg.get('senderPhone') or ''
            messages.append(msg)

        if phone_filter:
            clean = phone_filter.replace('+', '').replace(' ', '').replace('-', '')
            messages = [m for m in messages
                        if str(m.get('phoneNumber', '')).replace('+', '') == clean]

        messages.sort(key=lambda m: m.get('timestamp', m.get('createdAt', 0)) or 0, reverse=True)
        messages = messages[:limit]

        return cors_response(200, {'messages': messages, 'count': len(messages)}, origin)
    except Exception as e:
        logger.error(f"List RCS messages error: {e}")
        return cors_response(200, {'messages': [], 'count': 0}, origin)


def _list_templates(body: Dict, request_id: str, origin: str) -> Dict:
    """List RCS templates via v2 API (includes status)."""
    token = _get_token()
    if not token:
        return cors_response(500, {'error': 'Auth failed'}, origin)

    creds = _get_secrets()
    username = creds.get('username', 'wecaretrans')

    # v2 API uses username as appId
    url = f"https://api.aclwhatsapp.com/access-api/v2/rcs/{username}/templates"

    try:
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            # Normalize: ensure response is always a list
            templates = data if isinstance(data, list) else data.get('templates', [data] if data else [])
            return cors_response(200, {'templates': templates}, origin)
    except Exception as e:
        return cors_response(500, {'error': str(e)}, origin)


def _create_template(body: Dict, request_id: str, origin: str) -> Dict:
    """Create a new RCS template via v2 API."""
    token = _get_token()
    if not token:
        return cors_response(500, {'error': 'Auth failed'}, origin)

    name = body.get('name', '')
    text = body.get('text', '')
    template_type = body.get('type', 'text_message')

    if not name or not text:
        return cors_response(400, {'error': 'name and text are required'}, origin)

    creds = _get_secrets()
    username = creds.get('username', 'wecaretrans')

    # v2 API uses username as appId
    url = f"https://api.aclwhatsapp.com/access-api/v2/rcs/{username}/templates"

    # Build v2 payload format
    if template_type == 'text_message':
        payload_data = {
            "name": name,
            "type": "text_message",
            "component": {
                "text": text
            }
        }
    elif template_type == 'rich_card':
        # text field should be JSON with title, description, media
        try:
            card_data = json.loads(text) if text.startswith('{') else {"title": name, "description": text}
        except:
            card_data = {"title": name, "description": text}
        payload_data = {
            "name": name,
            "type": "rich_card",
            "component": card_data if 'richCard' in card_data else {
                "richCard": {
                    "standaloneCard": {
                        "cardOrientation": "VERTICAL",
                        "thumbnailImageAlignment": "LEFT",
                        "cardContent": {
                            "title": card_data.get('title', name),
                            "description": card_data.get('description', text),
                        }
                    }
                }
            }
        }
    else:
        payload_data = {
            "name": name,
            "type": template_type,
            "component": {"text": text}
        }

    payload = json.dumps(payload_data).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return cors_response(200, {'success': True, 'template': data}, origin)
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200] if e.fp else ''
        return cors_response(e.code, {'error': err}, origin)
    except Exception as e:
        return cors_response(500, {'error': str(e)}, origin)


def _delete_template(body: Dict, request_id: str, origin: str) -> Dict:
    """Delete an RCS template."""
    token = _get_token()
    if not token:
        return cors_response(500, {'error': 'Auth failed'}, origin)

    name = body.get('name', '')
    if not name:
        return cors_response(400, {'error': 'Template name is required'}, origin)

    creds = _get_secrets()
    bot_id = creds.get('bot_id', '69e0b2c980cbf50614ffa5fd')
    username = creds.get('username', 'wecaretrans')

    # Try multiple endpoint formats (v1 with botId, v2 with username)
    urls = [
        f"https://api.aclwhatsapp.com/access-api/v2/rcs/{username}/templates/{name}",
        f"https://api.aclwhatsapp.com/access-api/v1/rcs/{bot_id}/templates/{name}",
        f"https://api.aclwhatsapp.com/access-api/v1/rcs/{bot_id}/templates?name={name}",
    ]

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }, method='DELETE')
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_body = resp.read().decode()
                try:
                    data = json.loads(resp_body)
                except:
                    data = {'raw': resp_body[:200]}
                logger.info(f"Template deleted: {name} via {url}")
                return cors_response(200, {'success': True, 'deleted': name, 'response': data}, origin)
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:200] if e.fp else ''
            if e.code == 404:
                continue  # Try next URL format
            logger.warning(f"Delete template error: HTTP {e.code} - {err} (url: {url})")
            return cors_response(e.code, {'error': err, 'name': name}, origin)
        except Exception as e:
            logger.warning(f"Delete template error: {e} (url: {url})")
            continue

    # All URLs failed with 404
    return cors_response(404, {
        'error': 'Template deletion not supported by Sinch API or template not found',
        'name': name,
        'note': 'Sinch RCS API may not support template deletion. Contact Sinch support.',
    }, origin)


# ── RCS Message Persistence ──
MESSAGE_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days


def _store_rcs_message(message_id: str, phone: str, content: str, status: str,
                       template_id: str = '', metadata: str = ''):
    """Persist RCS message to the canonical MessagesTable only.

    Phase 4: legacy RcsMessagesTable dual-write STOPPED — canonical is the sole store
    (RCS list/DLR already read canonical). RcsMessagesTable retained read-only during
    the soak, then deleted.
    """
    now = int(time.time())
    contact_id = _lookup_contact_by_phone(phone)

    # Canonical write (single source of truth for the unified inbox).
    put_message(
        channel='rcs',
        direction='outbound',
        contact_id=contact_id or '',
        content=content[:2000],
        status=status,
        message_id=message_id,
        message_type='text',
        receiving_phone=phone,
        timestamp=now,
    )


def _lookup_contact_by_phone(phone: str) -> str:
    """Look up contactId from Contacts table by phone number. Returns '' if not found."""
    if not phone:
        return ''
    # Normalize: try with and without 91 prefix
    clean = phone.replace('+', '').replace(' ', '').replace('-', '')
    variants = [clean]
    if clean.startswith('91') and len(clean) == 12:
        variants.append(clean[2:])  # 10-digit
        variants.append(f'+{clean}')  # +91...
    elif len(clean) == 10:
        variants.append(f'91{clean}')  # 91...
        variants.append(f'+91{clean}')  # +91...

    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        for variant in variants:
            resp = table.query(
                IndexName='phone-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('phone').eq(variant),
                Limit=1,
            )
            items = resp.get('Items', [])
            if items:
                return items[0].get('contactId', '')
    except Exception as e:
        logger.debug(f"Contact lookup by phone failed: {e}")
    return ''


def _get_secrets() -> dict:
    """Load RCS secrets from Secrets Manager (cached)."""
    global _secrets_cache
    if _secrets_cache:
        return _secrets_cache
    try:
        resp = secrets_client.get_secret_value(SecretId=RCS_SECRET_NAME)
        _secrets_cache = json.loads(resp['SecretString'])
        return _secrets_cache
    except Exception as e:
        logger.error(f"Failed to load RCS secrets: {e}")
        return {}
