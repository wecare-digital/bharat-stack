"""
Plivo Answer URL - returns Plivo XML for the fixed WhatsApp IVR.

Purpose: replace the Lightsail/Asterisk media endpoint for WhatsApp Calling.

  WhatsApp user
    -> Meta WhatsApp Business Calling
    -> SIP
    -> Plivo Voice Application (WECARE-WHATSAPP-IVR)
    -> POST https://api.wecare.digital/plivo/answer   (this Lambda)
    -> <Play> S3 IVR audio
    -> <Hangup/>

Deliberately NOT in scope:
  * Plivo WhatsApp APIs - WhatsApp Calling stays DIRECT Meta.
  * ElevenLabs or any TTS - the IVR is pre-recorded audio only.
  * Any outbound messaging side effect. This endpoint only answers calls.

Plivo posts application/x-www-form-urlencoded and expects an XML document
back. Content-Type MUST be text/xml or Plivo ignores the response and the
caller hears silence.

Audio format: Plivo <Play> handles MP3 and WAV. It does NOT reliably play
OGG/Opus, which is what the original Asterisk assets are, so a WAV copy was
generated losslessly from the .sln16 original. The .ogg and .sln16 files are
left untouched for Asterisk rollback.
"""
import json
import os
import urllib.parse
from xml.sax.saxutils import escape

from lambda_utils.logging import get_logger

# Every other function in the fleet logs through lambda_utils.logging, which
# honours the LOG_LEVEL env var. This one used bare print(), so its output could
# not be turned down and did not carry a level. Same JSON payloads, same keys.
logger = get_logger(__name__)

MEDIA_BASE = os.environ.get('IVR_MEDIA_BASE', 'https://app.wecare.digital')
IVR_AUDIO_KEY = os.environ.get('IVR_AUDIO_KEY', 'stream/media/ivr/incoming_welcome.wav')
IVR_AUDIO_URL = os.environ.get('IVR_AUDIO_URL', f'{MEDIA_BASE}/{IVR_AUDIO_KEY}')

# --- post-call follow-up SMS -------------------------------------------------
# After the greeting plays we text the caller the self-service links, matching
# what the Airtel IQ path already did for IVR calls.
#
# The body MUST match approved DLT template ivr-default (1007277993798259629)
# character for character. The operator silently drops mismatched content even
# though the API call succeeds, so do not "improve" this copy.
SMS_FUNCTION = os.environ.get('SMS_FUNCTION', 'wecare-sms-aws:live')
POST_CALL_SMS_ENABLED = os.environ.get('POST_CALL_SMS_ENABLED', 'true').lower() == 'true'
DLT_TEMPLATE_KEY = os.environ.get('DLT_TEMPLATE_KEY', 'ivr-default')
IVR_SMS_BODY = os.environ.get('IVR_SMS_BODY', (
    "Thanks for contacting WECARE.DIGITAL!\n\n"
    "Submit your request here: https://wecare.digital/selfservice "
    "or send us a message / voice note on WhatsApp: https://r.wecare.digital/wa.\n\n"
    "We'll review it and follow up if needed."
))

# Optional shared secret. Plivo does not sign answer_url requests the way it
# signs callbacks, so if set we require ?token=<value> on the URL. Absent a
# token the endpoint is still safe: it is read-only and returns static XML.
ANSWER_TOKEN = os.environ.get('PLIVO_ANSWER_TOKEN', '')


def _xml_response(body: str, status: int = 200) -> dict:
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'text/xml; charset=utf-8',
            'Cache-Control': 'no-store',
        },
        'body': body,
    }


def _ivr_xml(audio_url: str) -> str:
    """Play the greeting, then hang up. No <Record>, no <Speak>, no TTS."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Response>\n'
        f'    <Play>{escape(audio_url)}</Play>\n'
        '    <Hangup/>\n'
        '</Response>'
    )


def _parse_body(event: dict) -> dict:
    """Plivo posts form-encoded; tolerate JSON too."""
    raw = event.get('body') or ''
    if event.get('isBase64Encoded'):
        import base64
        try:
            raw = base64.b64decode(raw).decode('utf-8', 'replace')
        except Exception:
            raw = ''
    if not raw:
        return {}
    raw_stripped = raw.lstrip()
    if raw_stripped.startswith('{'):
        try:
            return json.loads(raw_stripped)
        except Exception:
            return {}
    return {k: v[0] if len(v) == 1 else v
            for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}


def _send_post_call_sms(caller: str, call_uuid: str, request_id: str) -> None:
    """Text the caller the self-service links after the greeting.

    Fire-and-forget: an SMS failure must never affect call handling, so every
    error is logged and swallowed. Invokes wecare-sms-aws, which owns the DLT
    routing, rather than calling Pinpoint directly - one place decides how
    Indian traffic is sent.
    """
    if not POST_CALL_SMS_ENABLED or not caller:
        return

    digits = ''.join(c for c in str(caller) if c.isdigit())
    if not (digits.startswith('91') and len(digits) == 12):
        # Non-Indian caller: no approved DLT template, so do not send.
        logger.info(json.dumps({
            'event': 'plivo_post_call_sms_skipped',
            'reason': 'non_indian_caller',
            'callUuid': call_uuid,
            'requestId': request_id,
        }))
        return

    try:
        import boto3
        payload = {
            'requestContext': {'http': {'method': 'POST', 'path': '/sms-aws/send'}},
            'headers': {'origin': 'https://app.wecare.digital'},
            'body': json.dumps({
                'phoneNumber': f'+{digits}',
                'content': IVR_SMS_BODY,
                'messageType': 'TRANSACTIONAL',
                'dltTemplateKey': DLT_TEMPLATE_KEY,
                'campaignName': 'plivo-ivr-follow-up',
            }),
        }
        boto3.client('lambda').invoke(
            FunctionName=SMS_FUNCTION,
            InvocationType='Event',          # async - do not block the call
            Payload=json.dumps(payload).encode(),
        )
        logger.info(json.dumps({
            'event': 'plivo_post_call_sms_queued',
            'callUuid': call_uuid,
            'phone': digits[-4:],
            'templateKey': DLT_TEMPLATE_KEY,
            'via': SMS_FUNCTION,
            'requestId': request_id,
        }))
    except Exception as e:                                   # noqa: BLE001
        logger.warning(json.dumps({
            'event': 'plivo_post_call_sms_failed',
            'callUuid': call_uuid,
            'error': f'{type(e).__name__}: {str(e)[:160]}',
            'requestId': request_id,
        }))


def handler(event, context):
    """Answer a Plivo call with the fixed IVR."""
    request_id = getattr(context, 'aws_request_id', 'local') if context else 'local'
    params = _parse_body(event)
    qs = event.get('queryStringParameters') or {}

    if ANSWER_TOKEN and qs.get('token') != ANSWER_TOKEN:
        # Wrong/missing token: log and hang up without revealing anything.
        logger.warning(json.dumps({
            'event': 'plivo_answer_rejected',
            'reason': 'bad_or_missing_token',
            'requestId': request_id,
        }))
        return _xml_response(
            '<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n    <Hangup/>\n</Response>',
            status=403,
        )

    # Plivo sends CallUUID, From, To, Direction, CallStatus and similar.
    call_uuid = params.get('CallUUID', '')
    caller = params.get('From', '')
    status = str(params.get('CallStatus', '')).lower()

    logger.info(json.dumps({
        'event': 'plivo_answer',
        'callUuid': call_uuid,
        'from': str(caller)[-4:],
        'to': str(params.get('To', ''))[-4:],
        'direction': params.get('Direction', ''),
        'callStatus': params.get('CallStatus', ''),
        'sipHeaders': params.get('SIPHeaders', ''),
        'audioUrl': IVR_AUDIO_URL,
        'requestId': request_id,
    }))

    # This same URL is registered as both answer_url and hangup_url. Plivo hits
    # it twice per call: once to fetch the XML (CallStatus ringing/in-progress)
    # and once when the call ends (CallStatus completed). Send the follow-up SMS
    # only on the hangup pass, so one call produces exactly one SMS.
    if status == 'completed':
        _send_post_call_sms(caller, call_uuid, request_id)
        # Plivo ignores the body of a hangup callback; 200 is all it needs.
        return {'statusCode': 200,
                'headers': {'Content-Type': 'text/plain'},
                'body': 'ok'}

    return _xml_response(_ivr_xml(IVR_AUDIO_URL))
