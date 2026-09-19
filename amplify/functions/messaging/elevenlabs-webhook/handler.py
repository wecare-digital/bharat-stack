"""ElevenLabs webhook receiver - post-call transcripts and audio notifications.

  ElevenLabs Agent conversation ends
    -> ElevenLabs post-call webhook
    -> POST https://api.wecare.digital/elevenlabs/webhook   (this Lambda)
    -> HMAC signature verified
    -> persisted to VoiceCDRTable as id = elevenlabs#<conversation_id>

Why this exists
---------------
Before this, the ElevenLabs workspace had zero webhooks configured and there was
no endpoint anywhere in the account that could receive one, so every conversation
ElevenLabs handled was write-only: the transcript existed in their dashboard and
nowhere in ours.

Signature verification
----------------------
ElevenLabs sends an `ElevenLabs-Signature` header shaped:

    t=<unix_seconds>,v0=<hex_hmac_sha256>

The HMAC is taken over ``f"{timestamp}.{raw_body}"`` keyed with the webhook
signing secret that ElevenLabs returns when the webhook is created. The header
may carry several ``v0=`` values during a secret rotation and ANY one matching is
valid, so all of them are checked. Deliveries older than the replay window are
rejected.

Two things matter for correctness here:

  * The HMAC must be computed over the EXACT bytes ElevenLabs sent. API Gateway
    may hand us a base64-encoded body (``isBase64Encoded``), and json.loads +
    json.dumps round-tripping would change whitespace and key order and break
    the signature. So the raw string is preserved and only parsed afterwards.
  * Comparison uses hmac.compare_digest. A plain == leaks timing information
    that can be used to forge a signature byte by byte.

Fail-closed: if the signing secret is not configured, requests are REJECTED
rather than accepted unverified. An unauthenticated transcript sink would let
anyone write arbitrary records into our call history.

Deliberately NOT in scope
-------------------------
  * Answering or controlling calls. Plivo owns the call leg via /plivo/answer.
  * Any outbound messaging side effect. This endpoint only records.
  * Audio storage. `send_audio` is off; if it is enabled later the base64 audio
    should go to S3, not into a DynamoDB item.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from decimal import Decimal
from typing import Optional, Tuple

import boto3

from lambda_utils.logging import get_logger, log_event

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
CDR_TABLE = os.environ.get('VOICE_CDR_TABLE', 'stack-wecare-digital-VoiceCDRTable')
SECRET_ID = os.environ.get('ELEVENLABS_SECRET_ID', 'wecare/elevenlabs')
SIGNING_SECRET_FIELD = os.environ.get('ELEVENLABS_SIGNING_FIELD', 'webhook_secret')
# ElevenLabs rejects its own deliveries outside a 30 minute window; mirror that.
MAX_SKEW_SECONDS = int(os.environ.get('ELEVENLABS_MAX_SKEW', '1800'))

_signing_secret_cache: Optional[str] = None
_ddb = None


def _table():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource('dynamodb', region_name=REGION)
    return _ddb.Table(CDR_TABLE)


def _signing_secret() -> str:
    """Load the signing secret lazily, on first request.

    Deliberately not at import time: a module-scope read is cached for the life
    of the execution environment, so rotating the secret would not take effect
    until every warm sandbox recycled. See .kiro/steering/lambda-snapstart-deploy.md.
    """
    global _signing_secret_cache
    if _signing_secret_cache is not None:
        return _signing_secret_cache
    try:
        sm = boto3.client('secretsmanager', region_name=REGION)
        raw = sm.get_secret_value(SecretId=SECRET_ID).get('SecretString') or '{}'
        data = json.loads(raw)
        _signing_secret_cache = (data.get(SIGNING_SECRET_FIELD) or '').strip()
    except Exception as exc:  # absent secret/field is the normal pre-provision state
        log_event(logger, 'elevenlabs_signing_secret_unavailable', level='warning',
                  secretId=SECRET_ID, field=SIGNING_SECRET_FIELD, error=str(exc))
        _signing_secret_cache = ''
    return _signing_secret_cache


def _parse_signature_header(header: str) -> Tuple[Optional[int], list]:
    """Return (timestamp, [candidate hex digests]) from `t=...,v0=...[,v0=...]`."""
    timestamp: Optional[int] = None
    digests: list = []
    for part in (header or '').split(','):
        part = part.strip()
        if part.startswith('t='):
            try:
                timestamp = int(part[2:])
            except ValueError:
                return None, []
        elif part.startswith('v0='):
            digests.append(part[3:])
    return timestamp, digests


def _raw_body(event: dict) -> str:
    """The exact body bytes as sent, before any JSON round-trip."""
    body = event.get('body') or ''
    if event.get('isBase64Encoded'):
        try:
            return base64.b64decode(body).decode('utf-8')
        except Exception:
            return ''
    return body


def _verify(event: dict, raw: str) -> Tuple[bool, str]:
    secret = _signing_secret()
    if not secret:
        # Fail closed. See module docstring.
        return False, 'signing_secret_not_configured'

    headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
    header = headers.get('elevenlabs-signature') or headers.get('x-elevenlabs-signature') or ''
    if not header:
        return False, 'missing_signature_header'

    timestamp, digests = _parse_signature_header(header)
    if timestamp is None or not digests:
        return False, 'malformed_signature_header'

    skew = abs(int(time.time()) - timestamp)
    if skew > MAX_SKEW_SECONDS:
        return False, f'stale_timestamp_{skew}s'

    expected = hmac.new(secret.encode('utf-8'),
                        f'{timestamp}.{raw}'.encode('utf-8'),
                        hashlib.sha256).hexdigest()
    # Any one matching v0 is valid, so a secret rotation does not drop events.
    if any(hmac.compare_digest(expected, candidate) for candidate in digests):
        return True, 'ok'
    return False, 'signature_mismatch'


def _json_safe(value):
    """DynamoDB rejects float; convert via str to avoid binary rounding drift."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


def _reply(status: int, body: dict) -> dict:
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body),
    }


def handler(event, context):
    raw = _raw_body(event)

    ok, reason = _verify(event, raw)
    if not ok:
        # Do not echo the reason to the caller: it tells an attacker which part
        # of the forgery failed. It is logged for us instead.
        log_event(logger, 'elevenlabs_webhook_rejected', level='warning',
                  reason=reason, bodyBytes=len(raw))
        return _reply(401, {'error': 'unauthorized'})

    try:
        payload = json.loads(raw) if raw else {}
    except ValueError:
        log_event(logger, 'elevenlabs_webhook_bad_json', level='warning',
                  bodyBytes=len(raw))
        return _reply(400, {'error': 'invalid json'})

    event_type = payload.get('type') or 'unknown'
    data = payload.get('data') or {}
    conversation_id = (data.get('conversation_id')
                       or payload.get('conversation_id')
                       or f'no-conv-{int(time.time() * 1000)}')

    item = _json_safe({
        'id': f'elevenlabs#{conversation_id}',
        'source': 'elevenlabs',
        'event_type': event_type,
        'conversation_id': conversation_id,
        'agent_id': data.get('agent_id'),
        'status': data.get('status'),
        'received_at': int(time.time()),
        'event_timestamp': payload.get('event_timestamp'),
        'payload': payload,
    })

    try:
        _table().put_item(Item={k: v for k, v in item.items() if v is not None})
    except Exception as exc:
        # 500 so ElevenLabs retries rather than dropping the transcript.
        log_event(logger, 'elevenlabs_webhook_persist_failed', level='error',
                  conversationId=conversation_id, table=CDR_TABLE, error=str(exc))
        return _reply(500, {'error': 'persist failed'})

    log_event(logger, 'elevenlabs_webhook_stored',
              conversationId=conversation_id, eventType=event_type,
              table=CDR_TABLE, bodyBytes=len(raw))
    return _reply(200, {'ok': True, 'conversation_id': conversation_id})
