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

MEDIA_BASE = os.environ.get('IVR_MEDIA_BASE', 'https://app.wecare.digital')
IVR_AUDIO_KEY = os.environ.get('IVR_AUDIO_KEY', 'stream/media/ivr/incoming_welcome.wav')
IVR_AUDIO_URL = os.environ.get('IVR_AUDIO_URL', f'{MEDIA_BASE}/{IVR_AUDIO_KEY}')

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


def handler(event, context):
    """Answer a Plivo call with the fixed IVR."""
    request_id = getattr(context, 'aws_request_id', 'local') if context else 'local'
    params = _parse_body(event)
    qs = event.get('queryStringParameters') or {}

    if ANSWER_TOKEN and qs.get('token') != ANSWER_TOKEN:
        # Wrong/missing token: log and hang up without revealing anything.
        print(json.dumps({
            'event': 'plivo_answer_rejected',
            'reason': 'bad_or_missing_token',
            'requestId': request_id,
        }))
        return _xml_response(
            '<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n    <Hangup/>\n</Response>',
            status=403,
        )

    # Plivo sends CallUUID, From, To, Direction, CallStatus and similar.
    print(json.dumps({
        'event': 'plivo_answer',
        'callUuid': params.get('CallUUID', ''),
        'from': str(params.get('From', ''))[-4:],
        'to': str(params.get('To', ''))[-4:],
        'direction': params.get('Direction', ''),
        'callStatus': params.get('CallStatus', ''),
        'sipHeaders': params.get('SIPHeaders', ''),
        'audioUrl': IVR_AUDIO_URL,
        'requestId': request_id,
    }))

    return _xml_response(_ivr_xml(IVR_AUDIO_URL))
