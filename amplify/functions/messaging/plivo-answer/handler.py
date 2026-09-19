"""Plivo voice webhooks: answer, fallback, hangup and events.

  WhatsApp user / PSTN caller
    -> Plivo Voice Application (WECARE-WHATSAPP-IVR, 12775976954213184)
    -> POST https://api.wecare.digital/plivo/answer     -> <Play> + <Hangup/>
       POST https://api.wecare.digital/plivo/fallback    -> emergency XML
       POST https://api.wecare.digital/plivo/hangup      -> persist CDR, 2xx
       POST https://api.wecare.digital/plivo/events      -> record, 2xx

One Lambda serves all four routes. They share provider verification, the call
record and the post-call SMS de-duplication, and splitting them would mean three
copies of each or a shared layer to hold them. The function is still named
wecare-plivo-answer for continuity with its alias and integrations.

PROVIDER AUTHENTICATION (§18)
-----------------------------
Primary: Plivo X-Plivo-Signature-V3, verified in lambda_utils.plivo_signature
against the auth token from Secrets Manager.

The `?token=` shared secret is retained as DIAGNOSTIC COMPATIBILITY ONLY, per
§18, not as proof of provider identity. It matters that these are different
things: the token is a bearer secret sitting in a URL that appears in the Plivo
console and in our own snapshots, whereas the V3 signature covers the URL, the
sorted POST body and a per-request nonce, so it also proves the payload was not
edited in transit and cannot be replayed.

Plivo does NOT sign answer_url fetches - only callbacks. So:

    /plivo/answer     signature verified WHEN PRESENT, token gate enforced.
                      Cannot require a signature: a genuine answer_url fetch
                      arrives unsigned and rejecting it drops the call.
    /plivo/hangup     signature REQUIRED. It is a callback, and it is the route
    /plivo/events     with side effects (SMS, CDR writes).
    /plivo/fallback   signature verified when present; answer-style fetch.

That asymmetry is the whole reason the hangup side effect was worth moving off
the answer URL.

§19 RESPONSIBILITIES
--------------------
    answer    -> valid Plivo XML, 200, text/xml
    fallback  -> record the primary failure, return emergency XML, terminate
    hangup    -> persist final CDR state, dedupe by CallUUID, return 2xx
    events    -> record, return 2xx

The hangup endpoint MUST NOT return the answer IVR. Returning <Play> to a hangup
callback is how a terminated call gets re-answered.
"""
import base64
import json
import os
import time
import urllib.parse
from decimal import Decimal
from xml.sax.saxutils import escape

from lambda_utils.logging import get_logger, log_event

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')

MEDIA_BASE = os.environ.get('IVR_MEDIA_BASE', 'https://app.wecare.digital')
IVR_AUDIO_KEY = os.environ.get('IVR_AUDIO_KEY', 'stream/media/ivr/incoming_welcome.wav')
IVR_AUDIO_URL = os.environ.get('IVR_AUDIO_URL', f'{MEDIA_BASE}/{IVR_AUDIO_KEY}')

# --- post-call follow-up SMS -------------------------------------------------
# Body MUST match approved DLT template ivr-default (1007277993798259629)
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

# --- browser routing (Phase 7) -----------------------------------------------
# OFF by default. Turning this on changes what a real caller hears, so it is a
# production decision with its own approval - never a deployment side effect.
#
# false -> play the greeting and hang up   (the current, safe production default)
# true  -> <Dial><User> the agent endpoint (browser softphone)
PSTN_BROWSER_ROUTING_ENABLED = os.environ.get(
    'PSTN_BROWSER_ROUTING_ENABLED', 'false').lower() == 'true'

# The endpoint the inbound call is dialled to. A SIP URI is NOT accepted from a
# request - only this server-side configuration - so no caller can redirect a call
# to a destination of their choosing.
PSTN_AGENT_ENDPOINT = os.environ.get('PSTN_AGENT_ENDPOINT', '')

# Seconds to ring the agent before giving up and falling back to the greeting.
PSTN_DIAL_TIMEOUT = int(os.environ.get('PSTN_DIAL_TIMEOUT', '25'))

# Where Plivo reports the dial outcome. This is the AUTHORITATIVE connected
# signal; see lambda_utils/pstn/notifications.py.
PSTN_DIAL_CALLBACK_URL = os.environ.get(
    'PSTN_DIAL_CALLBACK_URL', 'https://api.wecare.digital/plivo/dial-events')

CDR_TABLE = os.environ.get('VOICE_CDR_TABLE', 'stack-wecare-digital-VoiceCDRTable')
CDR_TTL_SECONDS = 90 * 24 * 60 * 60

PLIVO_ANSWER_SECRET_ID = os.environ.get('PLIVO_ANSWER_SECRET_ID', 'wecare/plivo-answer')
PLIVO_API_SECRET_ID = os.environ.get('PLIVO_API_SECRET_ID', 'wecare/plivo/api')

_answer_token_cache: str = ''
_plivo_auth_token_cache: str = ''
_ddb = None


def _table():
    global _ddb
    if _ddb is None:
        import boto3
        _ddb = boto3.resource('dynamodb', region_name=REGION)
    return _ddb.Table(CDR_TABLE)


def _secret_field(secret_id: str, field: str) -> str:
    try:
        import boto3
        sm = boto3.client('secretsmanager', region_name=REGION)
        raw = sm.get_secret_value(SecretId=secret_id).get('SecretString', '') or ''
        try:
            return (json.loads(raw).get(field) or '').strip()
        except (ValueError, TypeError):
            return raw.strip()
    except Exception as exc:  # noqa: BLE001
        log_event(logger, 'plivo_secret_unavailable', level='debug',
                  secretId=secret_id, field=field, error=type(exc).__name__)
        return ''


def _get_answer_token() -> str:
    """Diagnostic token. Only a successful lookup is cached.

    Caching the empty result would strand a sandbox that started before the
    secret existed - it would keep returning '' until recycled.
    """
    global _answer_token_cache
    if _answer_token_cache:
        return _answer_token_cache
    value = _secret_field(PLIVO_ANSWER_SECRET_ID, 'token') \
        or os.environ.get('PLIVO_ANSWER_TOKEN', '')
    if value:
        _answer_token_cache = value
    return value


def _get_plivo_auth_token() -> str:
    """The Plivo account auth token, used as the V3 signing key."""
    global _plivo_auth_token_cache
    if _plivo_auth_token_cache:
        return _plivo_auth_token_cache
    value = _secret_field(PLIVO_API_SECRET_ID, 'auth_token')
    if value:
        _plivo_auth_token_cache = value
    return value


# --------------------------------------------------------------------------
# responses
# --------------------------------------------------------------------------
def _xml(body: str, status: int = 200) -> dict:
    return {
        'statusCode': status,
        # Plivo ignores a non-XML content type and the caller hears silence.
        'headers': {'Content-Type': 'text/xml; charset=utf-8',
                    'Cache-Control': 'no-store'},
        'body': body,
    }


def _hangup_xml(status: int = 403) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n    <Hangup/>\n</Response>')


def _ivr_xml(audio_url: str) -> str:
    """Play the greeting, then hang up. No <Record>, no <Speak>, no TTS."""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'    <Play>{escape(audio_url)}</Play>\n'
            '    <Hangup/>\n'
            '</Response>')


def _dial_user_xml(endpoint_username: str) -> str:
    """Ring a browser agent endpoint, then fall back to the greeting.

    `<User>` dials a Plivo ENDPOINT, not an arbitrary SIP URI. The username comes
    from server configuration and is escaped, so neither a caller nor an operator
    request can point a live call at a destination of their choosing.

    `callbackUrl` carries the authoritative connected event. `callbackMethod` is
    POST to match every other callback on this application.

    If the agent does not answer within the timeout, the verbs AFTER <Dial>
    execute - so the caller hears the existing greeting rather than silence. That
    is why the greeting stays in this response instead of being replaced by it.
    """
    escaped = escape(endpoint_username)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'    <Dial timeout="{PSTN_DIAL_TIMEOUT}" '
            f'callbackUrl="{escape(PSTN_DIAL_CALLBACK_URL)}" '
            'callbackMethod="POST" redirect="false">\n'
            f'        <User>sip:{escaped}@phone.plivo.com</User>\n'
            '    </Dial>\n'
            f'    <Play>{escape(IVR_AUDIO_URL)}</Play>\n'
            '    <Hangup/>\n'
            '</Response>')


def _answer_xml() -> str:
    """The answer response, which depends on the browser-routing flag.

    Falls back to the greeting whenever browser routing is off OR no agent
    endpoint is configured. A flag turned on without an endpoint would otherwise
    emit a <Dial> to an empty destination, which drops the call - so the missing
    configuration is treated as "not enabled" and logged, rather than trusted.
    """
    if PSTN_BROWSER_ROUTING_ENABLED and PSTN_AGENT_ENDPOINT:
        return _dial_user_xml(PSTN_AGENT_ENDPOINT)
    if PSTN_BROWSER_ROUTING_ENABLED and not PSTN_AGENT_ENDPOINT:
        log_event(logger, 'plivo_browser_routing_misconfigured', level='error',
                  alert='PSTN_BROWSER_ROUTING_NO_ENDPOINT',
                  detail=('PSTN_BROWSER_ROUTING_ENABLED is true but '
                          'PSTN_AGENT_ENDPOINT is empty; serving the greeting '
                          'rather than dialling an empty destination'))
    return _ivr_xml(IVR_AUDIO_URL)


def _fallback_xml() -> str:
    """Emergency XML for when the primary answer URL failed (§19).

    Deliberately simpler than the IVR: the fallback fires precisely when
    something is already broken, so it must not depend on the same S3 media fetch
    that may be what failed. <Speak> needs no external asset.
    """
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            '    <Speak language="en-IN" voice="WOMAN">'
            'Thank you for calling WECARE DIGITAL. '
            'We are unable to take your call right now. '
            'Please message us on WhatsApp and we will follow up.'
            '</Speak>\n'
            '    <Hangup/>\n'
            '</Response>')


def _ack(payload: dict = None, status: int = 200) -> dict:
    return {'statusCode': status,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(payload or {'ok': True})}


# --------------------------------------------------------------------------
# request parsing / verification
# --------------------------------------------------------------------------
def _parse_body(event: dict) -> dict:
    """Plivo posts form-encoded; tolerate JSON. Single values collapsed."""
    raw = event.get('body') or ''
    if event.get('isBase64Encoded'):
        try:
            raw = base64.b64decode(raw).decode('utf-8', 'replace')
        except Exception:  # noqa: BLE001
            raw = ''
    if not raw:
        return {}
    stripped = raw.lstrip()
    if stripped.startswith('{'):
        try:
            return json.loads(stripped)
        except Exception:  # noqa: BLE001
            return {}
    return {k: v[0] if len(v) == 1 else v
            for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}


# Authentication strength, weakest last. Serving IVR XML and performing a SIDE
# EFFECT are different privileges, and conflating them was a real hole - see
# _route_answer.
TRUST_SIGNATURE = 'signature'    # V3 verified: cryptographically proven Plivo
TRUST_TOKEN = 'token'            # ?token= matched: proves a shared secret
TRUST_NONE = 'unverified'        # nothing proven


def _verify_provider(event: dict, *, require_signature: bool) -> tuple:
    """(ok, trust_level, mechanism_or_reason).

    require_signature=True for callbacks, which Plivo does sign. False for
    answer-style fetches, which it does not - there the token is the only gate
    available, and requiring a signature would drop every genuine call.

    The third element is what callers must branch on before doing anything with a
    side effect. `ok=True` means "respond normally"; it does NOT mean "this request
    is proven to be Plivo".

    Why this returns a trust level rather than just a boolean
    --------------------------------------------------------
    Plivo does not sign answer_url fetches, so /plivo/answer cannot require a
    signature without dropping every real call. The previous version therefore
    returned True when no token was configured, which is defensible for RETURNING
    XML and indefensible for the rest of what that route does: it also handles the
    CallStatus=completed pass, which sends a DLT-templated SMS.

    That combination was an SMS-pumping vector. An unauthenticated
    POST /plivo/answer carrying CallStatus=completed&From=91XXXXXXXXXX would send a
    message to an arbitrary Indian number at our cost, under our registered sender.
    It required the token lookup to return empty - so a transient Secrets Manager
    failure, or the secret being removed, was enough to open it.

    Failing closed on a missing token instead would trade that for an outage:
    every inbound call would drop while the secret was unreadable. Neither is
    acceptable, so the privilege is split instead. Answer still serves XML at
    TRUST_NONE; side effects require TRUST_TOKEN or better.
    """
    from lambda_utils import plivo_signature

    auth_token = _get_plivo_auth_token()
    hdrs = plivo_signature.headers_lower(event)
    has_sig = bool(hdrs.get(plivo_signature.HEADER_V3)
                   or hdrs.get(plivo_signature.HEADER_MA_V3))

    if has_sig and auth_token:
        ok, reason = plivo_signature.verify_request(event, auth_token)
        if ok:
            return True, TRUST_SIGNATURE, f'signature_{reason}'
        return False, TRUST_NONE, reason

    if require_signature:
        return False, TRUST_NONE, ('signature_required_but_absent' if not has_sig
                                   else 'auth_token_not_configured')

    # Answer-style fetch: fall back to the diagnostic token gate.
    token = _get_answer_token()
    if not token:
        # Serve the call, but say so loudly and carry no privilege. A real call
        # must not drop because a secret read failed; a side effect must not run
        # because one did.
        log_event(logger, 'plivo_answer_token_unavailable', level='error',
                  alert='PLIVO_ANSWER_TOKEN_UNAVAILABLE',
                  detail=('answer-style request served unverified; side effects '
                          'suppressed'))
        return True, TRUST_NONE, 'unverified_no_token_configured'

    qs = event.get('queryStringParameters') or {}
    if qs.get('token') == token:
        return True, TRUST_TOKEN, 'token'
    return False, TRUST_NONE, 'bad_or_missing_token'


# --------------------------------------------------------------------------
# side effects
# --------------------------------------------------------------------------
def _claim_once(call_uuid: str, suffix: str) -> bool:
    """True when this (call, event) pair has not been handled yet.

    Plivo retries callbacks, and during the transition the hangup pass can arrive
    on BOTH /plivo/answer and /plivo/hangup. Without this, one call sends two
    DLT-templated SMS to the same customer.
    """
    if not call_uuid:
        return True
    try:
        from lambda_utils.webhook_dedup import claim_event
        return claim_event(f'{call_uuid}:{suffix}', source='plivo')
    except Exception as exc:  # noqa: BLE001
        # Dedup unavailable: proceed rather than drop a real event, but say so.
        log_event(logger, 'plivo_dedup_unavailable', level='warning',
                  callUuid=call_uuid, error=type(exc).__name__)
        return True


def _send_post_call_sms(caller: str, call_uuid: str, request_id: str) -> None:
    """Text the caller the self-service links. Fire and forget.

    Routes through wecare-sms-aws, which owns DLT resolution, rather than calling
    a provider directly - one place decides how Indian traffic is sent.
    """
    if not POST_CALL_SMS_ENABLED or not caller:
        return
    digits = ''.join(c for c in str(caller) if c.isdigit())
    if not (digits.startswith('91') and len(digits) == 12):
        log_event(logger, 'plivo_post_call_sms_skipped',
                  reason='non_indian_caller', callUuid=call_uuid,
                  requestId=request_id)
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
            FunctionName=SMS_FUNCTION, InvocationType='Event',
            Payload=json.dumps(payload).encode())
        log_event(logger, 'plivo_post_call_sms_queued', callUuid=call_uuid,
                  phone=digits[-4:], templateKey=DLT_TEMPLATE_KEY,
                  via=SMS_FUNCTION, requestId=request_id)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, 'plivo_post_call_sms_failed', level='warning',
                  callUuid=call_uuid,
                  error=f'{type(exc).__name__}: {str(exc)[:160]}',
                  requestId=request_id)


def _persist_cdr(params: dict, route: str, request_id: str) -> bool:
    """Final call state into VoiceCDRTable. Never raises."""
    call_uuid = params.get('CallUUID') or ''
    if not call_uuid:
        return False
    now = int(time.time())
    item = {
        'id': f'plivo#{call_uuid}',
        'source': 'plivo',
        'route': route,
        'call_uuid': call_uuid,
        'from_number': params.get('From') or '',
        'to_number': params.get('To') or '',
        'direction': params.get('Direction') or '',
        'call_status': params.get('CallStatus') or '',
        'hangup_cause': params.get('HangupCause') or params.get('HangupCauseName') or '',
        'hangup_source': params.get('HangupSource') or '',
        'duration_seconds': params.get('Duration') or params.get('BillDuration') or '',
        'end_time': params.get('EndTime') or '',
        'received_at': now,
        'expiresAt': Decimal(str(now + CDR_TTL_SECONDS)),
    }
    try:
        _table().put_item(Item={k: v for k, v in item.items() if v not in ('', None)})
        return True
    except Exception as exc:  # noqa: BLE001
        log_event(logger, 'plivo_cdr_persist_failed', level='error',
                  callUuid=call_uuid, table=CDR_TABLE,
                  error=f'{type(exc).__name__}: {str(exc)[:160]}',
                  requestId=request_id)
        return False


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------
def _route_answer(params: dict, request_id: str, trust: str = TRUST_NONE) -> dict:
    """§19 answer: return valid Plivo XML.

    During the transition this URL is still registered as the hangup URL too, so
    a CallStatus=completed pass may arrive here. Handle it, de-duplicated against
    /plivo/hangup so the customer gets exactly one SMS per call.

    The completed pass is SIDE-EFFECTING - it sends a DLT-templated SMS - so it
    requires TRUST_TOKEN or better. Returning the IVR XML does not, because Plivo
    does not sign answer_url fetches and refusing an unsigned one would drop every
    real call. See _verify_provider for why the two are separated.
    """
    status = str(params.get('CallStatus', '')).lower()
    call_uuid = params.get('CallUUID', '')
    if status == 'completed':
        if trust == TRUST_NONE:
            # Refuse the side effect, not the request. An unverified caller must
            # not be able to make us text an arbitrary number.
            log_event(logger, 'plivo_postcall_refused_unverified', level='error',
                      callUuid=call_uuid, route='answer',
                      alert='PLIVO_UNVERIFIED_POSTCALL_ATTEMPT',
                      from_last4=str(params.get('From', ''))[-4:],
                      requestId=request_id)
            return _ack({'ok': True, 'callUuid': call_uuid,
                         'sideEffectsSuppressed': True}, status=202)
        if _claim_once(call_uuid, 'postcall'):
            _persist_cdr(params, 'answer-hangup-pass', request_id)
            _send_post_call_sms(params.get('From', ''), call_uuid, request_id)
        else:
            log_event(logger, 'plivo_postcall_deduped', callUuid=call_uuid,
                      route='answer', requestId=request_id)
        return {'statusCode': 200,
                'headers': {'Content-Type': 'text/plain'}, 'body': 'ok'}
    return _xml(_answer_xml())


def _route_fallback(params: dict, request_id: str) -> dict:
    """§19 fallback: record that the primary answer URL failed, then degrade."""
    log_event(logger, 'plivo_answer_primary_failed', level='error',
              callUuid=params.get('CallUUID', ''),
              from_last4=str(params.get('From', ''))[-4:],
              # Plivo reports why the primary failed in these fields.
              fallbackReason=params.get('FallbackReason', ''),
              primaryError=params.get('ErrorType', '') or params.get('Error', ''),
              requestId=request_id,
              alert='PLIVO_PRIMARY_ANSWER_URL_FAILED')
    _persist_cdr(params, 'fallback', request_id)
    return _xml(_fallback_xml())


def _route_hangup(params: dict, request_id: str) -> dict:
    """§19 hangup: persist final CDR, dedupe, return 2xx.

    Returns JSON, never the answer IVR. Returning <Play> to a hangup callback is
    how a terminated call gets re-answered.
    """
    call_uuid = params.get('CallUUID', '')
    fresh = _claim_once(call_uuid, 'postcall')
    persisted = _persist_cdr(params, 'hangup', request_id)
    if fresh:
        _send_post_call_sms(params.get('From', ''), call_uuid, request_id)
    else:
        log_event(logger, 'plivo_postcall_deduped', callUuid=call_uuid,
                  route='hangup', requestId=request_id)
    log_event(logger, 'plivo_hangup', callUuid=call_uuid,
              callStatus=params.get('CallStatus', ''),
              hangupCause=params.get('HangupCause', ''),
              duration=params.get('Duration', ''),
              cdrPersisted=persisted, deduped=not fresh, requestId=request_id)
    return _ack({'ok': True, 'callUuid': call_uuid, 'deduped': not fresh})


def _route_events(params: dict, request_id: str) -> dict:
    """§19 events: record and acknowledge."""
    call_uuid = params.get('CallUUID', '')
    log_event(logger, 'plivo_event', callUuid=call_uuid,
              event=params.get('Event', '') or params.get('EventName', ''),
              callStatus=params.get('CallStatus', ''), requestId=request_id)
    _persist_cdr(params, 'events', request_id)
    return _ack({'ok': True, 'callUuid': call_uuid})


# Callbacks are signed by Plivo; answer-style fetches are not.
def _route_dial_events(params: dict, request_id: str) -> dict:
    """The AUTHORITATIVE connected-call signal: <Dial callbackUrl>.

    Signature required. This route decides whether a customer gets a message, so
    an unsigned request must never reach the claim logic.

    Returns a retryable 5xx when the claim store is unreachable. That is
    deliberate: Plivo redelivers, so the cost of refusing to guess is latency,
    whereas guessing means duplicate SMS to real people under our registered DLT
    sender.
    """
    from lambda_utils.pstn import claims as pstn_claims
    from lambda_utils.pstn import notifications as pstn_notifications

    call_uuid = params.get('CallUUID', '')
    try:
        outcome = pstn_notifications.handle_connected(
            params, request_id=request_id, dispatch=_dispatch_notification)
    except pstn_claims.ClaimStoreUnavailable as exc:
        # Fail closed. 503 so Plivo retries; nothing was sent.
        log_event(logger, 'plivo_dial_claim_store_unavailable', level='error',
                  callUuid=call_uuid,
                  alert='PSTN_CLAIM_STORE_UNAVAILABLE',
                  error=type(exc).__name__, requestId=request_id)
        return _ack({'error': 'claim store unavailable, retry'}, status=503)

    _persist_cdr(params, 'dial-events', request_id)
    log_event(logger, 'plivo_dial_event', callUuid=call_uuid,
              dialAction=params.get('DialAction', ''),
              claimed=outcome.get('claimed'),
              reason=outcome.get('reason'), requestId=request_id)
    return _ack({'ok': True, 'callUuid': call_uuid,
                 'claimed': outcome.get('claimed', False)})


def _dispatch_notification(*, channel: str, delivery_id: str, destination: str,
                           body: str, provider: str, dlt_template_key: str,
                           a_leg_uuid: str, request_id: str) -> None:
    """Send one channel for a claimed connected call.

    Called once per eligible channel, AFTER that channel's claim succeeded, so an
    exception here leaves the channel PENDING and retryable rather than duplicating
    a completed one.

    SMS goes through the shared dispatcher, which routes to AWS End User Messaging
    and applies the DLT gate. RCS is not dispatched inline yet - see below.
    """
    from lambda_utils.pstn import claims as pstn_claims
    from lambda_utils.pstn import notifications as pstn_notifications

    if channel == 'sms':
        from lambda_utils.comms.notify import send_notification_sms
        outcome = send_notification_sms(
            destination, body, dlt_template_key=dlt_template_key,
            campaign='plivo-connected-notification', request_id=request_id,
            wait=True)
        if outcome.ok:
            pstn_claims.record_attempt(
                delivery_id, state='SENT', provider=provider,
                provider_message_id=outcome.provider_message_id,
                request_id=request_id)
            return
        category, permanent = pstn_notifications.classify_provider_error(
            outcome.error or outcome.skipped_reason)
        pstn_claims.record_attempt(
            delivery_id, state='FAILED', provider=provider,
            error_category=category, error_is_permanent=permanent,
            request_id=request_id)
        return

    if channel == 'rcs':
        # India RCS runs through the approved Sinch module. It is left PENDING here
        # rather than sent inline because a second synchronous provider call inside
        # a signed webhook would add its latency to Plivo's callback timeout, and a
        # timeout mid-send is the one case where the claim cannot record what
        # happened. A queued worker owns this; until it exists the row stays
        # PENDING and visibly unsent rather than being reported as delivered.
        log_event(logger, 'plivo_rcs_deferred', deliveryId=delivery_id,
                  provider=provider, requestId=request_id)
        return

    raise ValueError(f'unknown notification channel {channel!r}')


_ROUTES = {
    '/plivo/answer':   (_route_answer,   False),
    '/plivo/fallback': (_route_fallback, False),
    '/plivo/hangup':   (_route_hangup,   True),
    '/plivo/events':   (_route_events,   True),
    # Signature REQUIRED: this route decides whether a customer is messaged.
    '/plivo/dial-events': (_route_dial_events, True),
}


def handler(event, context):
    request_id = getattr(context, 'aws_request_id', 'local') if context else 'local'

    # Strip the API Gateway stage prefix. Measured: a request to
    # https://api.wecare.digital/plivo/hangup arrives with
    # rawPath="/prod/plivo/hangup", so matching rawPath directly sends every
    # callback to the default route - and if that default is the answer handler,
    # a hangup callback gets the IVR back, which re-answers a terminated call.
    from lambda_utils import plivo_signature
    path = plivo_signature.normalize_path(event).rstrip('/') or '/plivo/answer'

    if path not in _ROUTES:
        # Do not silently treat an unrecognised path as an answer fetch. That is
        # what hid the stage-prefix bug: /prod/plivo/hangup "worked" by falling
        # through to the IVR instead of failing visibly.
        log_event(logger, 'plivo_unknown_path', level='warning',
                  path=path, rawPath=event.get('rawPath', ''),
                  requestId=request_id)
    route, require_signature = _ROUTES.get(path, (_route_answer, False))

    ok, trust, mechanism = _verify_provider(event,
                                            require_signature=require_signature)
    if not ok:
        # Do not tell the caller which check failed.
        log_event(logger, 'plivo_request_rejected', level='warning',
                  path=path, reason=mechanism, requestId=request_id)
        if path in ('/plivo/answer', '/plivo/fallback'):
            return _xml(_hangup_xml(), status=403)
        return _ack({'error': 'unauthorized'}, status=401)

    params = _parse_body(event)
    log_event(logger, 'plivo_request', path=path, auth=mechanism, trust=trust,
              callUuid=params.get('CallUUID', ''),
              from_last4=str(params.get('From', ''))[-4:],
              to_last4=str(params.get('To', ''))[-4:],
              direction=params.get('Direction', ''),
              callStatus=params.get('CallStatus', ''),
              # A REAL SIP call carries SIP headers; synthetic tests do not.
              sipHeaders=params.get('SIPHeaders', ''),
              requestId=request_id)

    if route is _route_answer:
        return route(params, request_id, trust)
    return route(params, request_id)
