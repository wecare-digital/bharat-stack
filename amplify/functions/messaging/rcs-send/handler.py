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
- "testing" (Text type) — test template
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
    else:
        return cors_response(400, {'error': f'Unknown action: {action}'}, origin)


def _send_rcs(body: Dict, request_id: str, origin: str) -> Dict:
    """Send RCS message via Sinch Conversation API."""
    phone = body.get('phoneNumber', body.get('to', ''))
    template_id = body.get('templateId', body.get('template', 'testing'))
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
    """List RCS messages from DynamoDB (for inbox)."""
    phone_filter = body.get('phoneNumber', '')
    limit = body.get('limit', 200)

    try:
        table = dynamodb.Table(RCS_TABLE)

        if phone_filter:
            # Query by phone number
            clean = phone_filter.replace('+', '').replace(' ', '').replace('-', '')
            resp = table.query(
                IndexName='phoneNumber-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('phoneNumber').eq(clean),
                Limit=limit,
                ScanIndexForward=False,
            )
        else:
            # Scan all (limited)
            resp = table.scan(Limit=limit)

        items = resp.get('Items', [])
        # Convert Decimal to int/float for JSON serialization
        messages = []
        for item in items:
            msg = {}
            for k, v in item.items():
                from decimal import Decimal
                msg[k] = int(v) if isinstance(v, Decimal) else v
            messages.append(msg)

        # Sort by createdAt descending
        messages.sort(key=lambda m: m.get('createdAt', 0), reverse=True)

        return cors_response(200, {'messages': messages, 'count': len(messages)}, origin)
    except Exception as e:
        logger.error(f"List RCS messages error: {e}")
        return cors_response(200, {'messages': [], 'count': 0}, origin)


def _list_templates(body: Dict, request_id: str, origin: str) -> Dict:
    """List RCS templates."""
    token = _get_token()
    if not token:
        return cors_response(500, {'error': 'Auth failed'}, origin)

    creds = _get_secrets()
    bot_id = creds.get('bot_id', '69e0b2c980cbf50614ffa5fd')
    url = f"https://api.aclwhatsapp.com/access-api/v1/rcs/{bot_id}/templates"

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
    """Create a new RCS template."""
    token = _get_token()
    if not token:
        return cors_response(500, {'error': 'Auth failed'}, origin)

    name = body.get('name', '')
    text = body.get('text', '')
    template_type = body.get('type', 'text_message')

    if not name or not text:
        return cors_response(400, {'error': 'name and text are required'}, origin)

    creds = _get_secrets()
    bot_id = creds.get('bot_id', '69e0b2c980cbf50614ffa5fd')
    url = f"https://api.aclwhatsapp.com/access-api/v1/rcs/{bot_id}/templates"

    payload = json.dumps({
        "name": name,
        "type": template_type,
        "textMessageContent": text
    }).encode()

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

# ── RCS Message Persistence ──
MESSAGE_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days


def _store_rcs_message(message_id: str, phone: str, content: str, status: str,
                       template_id: str = '', metadata: str = ''):
    """Persist RCS message to DynamoDB for audit trail. Links to contactId via phone lookup."""
    now = int(time.time())
    contact_id = _lookup_contact_by_phone(phone)

    try:
        table = dynamodb.Table(RCS_TABLE)
        item = {
            'messageId': message_id,
            'direction': 'OUTBOUND',
            'channel': 'RCS',
            'phoneNumber': phone,
            'content': content[:2000],
            'status': status,
            'templateId': template_id or 'none',
            'metadata': metadata[:1024] if metadata else 'none',
            'provider': 'sinch-rcs',
            'createdAt': now,
            'updatedAt': now,
            'expiresAt': now + MESSAGE_TTL_SECONDS,
        }
        # Only include GSI keys if they have non-empty values
        # DynamoDB doesn't allow empty strings for index key attributes
        if contact_id:
            item['contactId'] = contact_id
        logger.info(f"Storing RCS message: {message_id} phone={phone[-4:]} table={RCS_TABLE}")
        table.put_item(Item=item)
        logger.info(f"RCS message stored successfully: {message_id}")
    except Exception as e:
        # Don't fail the send if storage fails
        logger.error(f"Failed to store RCS message {message_id}: {type(e).__name__}: {e}")


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
