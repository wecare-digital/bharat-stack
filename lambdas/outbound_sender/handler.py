"""
Outbound WhatsApp Lambda — AWS EUM Social Reference Implementation

Sends WhatsApp messages via AWS End User Messaging Social ONLY.
NO direct Meta Graph API calls. All communication through boto3 socialmessaging client.

Supports: text, media (image/video/audio/document/sticker), template, interactive
(list/button/cta_url/location_request/flow), reaction, order_details, order_status.

Invoked via API Gateway (HTTP) or direct Lambda invoke.
"""
import json
import uuid
import time
import logging
import re
from typing import Dict, Any, Optional, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.config import (
    PHONE_NUMBER_ID_1, PHONE_NUMBER_ID_2, META_API_VERSION,
    MESSAGES_OUTBOUND_TABLE, CONTACTS_TABLE, MEDIA_BUCKET,
    MEDIA_OUTBOUND_PREFIX, RATE_LIMIT_PER_SECOND, SEND_MODE,
    LOG_LEVEL, MAX_TEXT_LENGTH, MESSAGE_TTL_SECONDS
)
from shared.social_client import send_message, upload_media, SocialMessagingError
from shared.validation import validate_e164, normalize_phone, validate_phone_number_id
from shared.storage import store_outbound_message

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

ALLOWLIST = {PHONE_NUMBER_ID_1, PHONE_NUMBER_ID_2}
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}

# AWS clients
import boto3
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
cloudwatch = boto3.client('cloudwatch', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

METRICS_NAMESPACE = 'WECARE.DIGITAL'

# Media size limits per WhatsApp Business Platform docs
MEDIA_SIZE_LIMITS = {
    'image': 5 * 1024 * 1024,       # 5 MB
    'video': 16 * 1024 * 1024,      # 16 MB
    'audio': 16 * 1024 * 1024,      # 16 MB
    'document': 100 * 1024 * 1024,  # 100 MB
    'sticker': 500 * 1024,          # 500 KB
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Send WhatsApp message via AWS EUM Social SendWhatsAppMessage API.
    Supports: text, media, template, interactive, reaction, order_details, order_status.
    """
    request_id = context.aws_request_id if context else 'local'
    logger.info(json.dumps({'event': 'outbound_start', 'sendMode': SEND_MODE, 'requestId': request_id}))

    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        logger.warning(json.dumps({'event': 'outbound_invalid_json', 'requestId': request_id}))
        return _error_response(400, 'Invalid JSON in request body')

    try:
        # Extract common fields
        contact_id = body.get('contactId', '')
        recipient_phone = body.get('recipientPhone', '')
        phone_number_id = body.get('phoneNumberId', PHONE_NUMBER_ID_1)
        content = body.get('content', '')

        # Resolve recipient phone from contact if not provided directly
        if not recipient_phone and contact_id:
            contact = _get_contact(contact_id)
            if not contact:
                return _error_response(404, 'Contact not found')
            recipient_phone = contact.get('phone', '')

        if not recipient_phone:
            return _error_response(400, 'recipientPhone or contactId is required')

        # Validate phone number ID is in allowlist
        if phone_number_id not in ALLOWLIST:
            return _error_response(403, f'Phone number ID not in allowlist')

        # Message type flags
        is_reaction = body.get('isReaction', False)
        is_template = body.get('isTemplate', False)
        is_interactive = body.get('isInteractive', False)
        is_order_status = body.get('isOrderStatus', False)
        is_location = body.get('isLocation', False)
        is_contacts = body.get('isContacts', False)
        media_file = body.get('mediaFile')
        media_type = body.get('mediaType')

        # Validate text length (skip for reactions)
        if not is_reaction and content and len(content) > MAX_TEXT_LENGTH:
            return _error_response(400, f'Content exceeds {MAX_TEXT_LENGTH} characters')

        # Rate limit check
        if not _check_rate_limit(phone_number_id):
            return _error_response(429, 'Rate limit exceeded')

        message_id = str(uuid.uuid4())

        # DRY_RUN mode — log without API call
        if SEND_MODE == 'DRY_RUN':
            return _handle_dry_run(message_id, recipient_phone, body, request_id)

        # Route to appropriate handler
        if is_reaction:
            return _send_reaction(message_id, contact_id, recipient_phone, phone_number_id, body, request_id)

        if is_order_status:
            return _send_order_status(message_id, contact_id, recipient_phone, phone_number_id, body, request_id)

        if is_interactive:
            return _send_interactive(message_id, contact_id, recipient_phone, phone_number_id, body, request_id)

        if is_template:
            return _send_template(message_id, contact_id, recipient_phone, phone_number_id, body, request_id)

        if media_file and media_type:
            return _send_media(message_id, contact_id, recipient_phone, phone_number_id, body, request_id)

        # Location message
        if is_location:
            return _send_location(message_id, contact_id, recipient_phone, phone_number_id, body, request_id)

        # Contacts (vCard) message
        if is_contacts:
            return _send_contacts(message_id, contact_id, recipient_phone, phone_number_id, body, request_id)

        # Default: text message
        return _send_text(message_id, contact_id, recipient_phone, phone_number_id, content, request_id)

    except SocialMessagingError as e:
        logger.error(json.dumps({'event': 'social_messaging_error', 'code': e.code, 'message': e.message, 'requestId': request_id}))
        _emit_metric('failed')
        return _error_response(e.http_status, e.message)
    except Exception as e:
        logger.error(json.dumps({'event': 'outbound_error', 'error': str(e), 'requestId': request_id}))
        _emit_metric('failed')
        return _error_response(500, 'Internal server error')


# ---------------------------------------------------------------------------
# Message senders
# ---------------------------------------------------------------------------

def _send_text(message_id: str, contact_id: str, recipient_phone: str,
               phone_number_id: str, content: str, request_id: str) -> Dict[str, Any]:
    """Send plain text message."""
    formatted = _format_phone(recipient_phone)
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': formatted,
        'type': 'text',
        'text': {'body': content, 'preview_url': False}
    }
    result = send_message(phone_number_id, payload, META_API_VERSION)
    wa_id = result.get('messageId', '')
    _store_record(message_id, contact_id, recipient_phone, content, 'text', wa_id, phone_number_id)
    _emit_metric('success')
    logger.info(json.dumps({'event': 'text_sent', 'messageId': message_id, 'waId': wa_id, 'requestId': request_id}))
    return _success_response(message_id, wa_id, 'text')


def _send_media(message_id: str, contact_id: str, recipient_phone: str,
                phone_number_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """Send media message (image, video, audio, document, sticker)."""
    media_file = body['mediaFile']  # S3 key
    media_type = body['mediaType']  # e.g. 'image/jpeg' or 'image'
    content = body.get('content', '')
    filename = body.get('mediaFileName')

    # Determine WhatsApp message type from MIME or simple type
    msg_type = media_type.split('/')[0] if '/' in media_type else media_type
    if msg_type not in ('image', 'video', 'audio', 'document', 'sticker'):
        msg_type = 'document'

    # Validate media size if provided
    file_size = body.get('mediaFileSize', 0)
    if file_size and msg_type in MEDIA_SIZE_LIMITS:
        limit = MEDIA_SIZE_LIMITS[msg_type]
        if file_size > limit:
            return _error_response(400, f'{msg_type} exceeds {limit // (1024*1024)}MB limit')

    # Upload media to WhatsApp via AWS EUM Social PostWhatsAppMessageMedia
    s3_key = media_file if media_file.startswith(MEDIA_OUTBOUND_PREFIX) else f"{MEDIA_OUTBOUND_PREFIX}{media_file}"
    media_id = upload_media(phone_number_id, MEDIA_BUCKET, s3_key)
    if not media_id:
        return _error_response(500, 'Media upload failed')

    formatted = _format_phone(recipient_phone)
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': formatted,
        'type': msg_type,
        msg_type: {'id': media_id}
    }
    if content and msg_type in ('image', 'video', 'document'):
        payload[msg_type]['caption'] = content
    if msg_type == 'document' and filename:
        payload[msg_type]['filename'] = filename[:240]

    result = send_message(phone_number_id, payload, META_API_VERSION)
    wa_id = result.get('messageId', '')
    _store_record(message_id, contact_id, recipient_phone, content or f'[{msg_type}]', msg_type, wa_id, phone_number_id)
    _emit_metric('success')
    logger.info(json.dumps({'event': 'media_sent', 'messageId': message_id, 'waId': wa_id, 'mediaType': msg_type, 'requestId': request_id}))
    return _success_response(message_id, wa_id, msg_type)


def _send_template(message_id: str, contact_id: str, recipient_phone: str,
                   phone_number_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """Send template message with optional parameters, header media, and payment order_details."""
    template_name = body.get('templateName', '')
    template_params = list(body.get('templateParams', []))
    header_image_url = body.get('headerImageUrl')
    order_details = body.get('orderDetails')
    is_payment_template = body.get('isPaymentTemplate', False)

    if not template_name:
        return _error_response(400, 'templateName is required')

    # Extract language code from first param if it looks like one (e.g. 'en', 'en_US')
    language = 'en'
    if template_params:
        first = template_params[0]
        if isinstance(first, str) and (len(first) == 2 or (2 <= len(first) <= 5 and '_' in first)):
            language = first
            template_params = template_params[1:]

    formatted = _format_phone(recipient_phone)
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': formatted,
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': language},
            'components': []
        }
    }

    # Header image component
    if header_image_url:
        payload['template']['components'].append({
            'type': 'header',
            'parameters': [{'type': 'image', 'image': {'link': header_image_url}}]
        })

    # Body parameters
    if template_params:
        payload['template']['components'].append({
            'type': 'body',
            'parameters': [{'type': 'text', 'text': str(p)} for p in template_params]
        })

    # Payment template with order_details button
    if is_payment_template and order_details:
        payload['template']['components'].append({
            'type': 'button',
            'sub_type': 'order_details',
            'index': 0,
            'parameters': [{'type': 'action', 'action': {'order_details': order_details}}]
        })

    # OTP / Authentication template support
    is_otp_template = body.get('isOtpTemplate', False) or body.get('isAuthenticationTemplate', False)
    otp_code = body.get('otpCode', '')
    otp_button_type = body.get('otpButtonType', 'copy_code')

    if is_otp_template and otp_code:
        btn_type = otp_button_type.lower() if otp_button_type else 'copy_code'
        if btn_type == 'url':
            payload['template']['components'].append({
                'type': 'button',
                'sub_type': 'url',
                'index': 0,
                'parameters': [{'type': 'text', 'text': str(otp_code)}]
            })
        else:
            payload['template']['components'].append({
                'type': 'button',
                'sub_type': 'copy_code',
                'index': 0,
                'parameters': [{'type': 'coupon_code', 'coupon_code': str(otp_code)}]
            })
        logger.info(json.dumps({'event': 'otp_template_built', 'template': template_name, 'btnType': btn_type, 'requestId': request_id}))

    result = send_message(phone_number_id, payload, META_API_VERSION)
    wa_id = result.get('messageId', '')
    _store_record(message_id, contact_id, recipient_phone, f'[template:{template_name}]', 'template', wa_id, phone_number_id)
    _emit_metric('success', is_template=True)
    logger.info(json.dumps({'event': 'template_sent', 'messageId': message_id, 'waId': wa_id, 'template': template_name, 'requestId': request_id}))
    return _success_response(message_id, wa_id, 'template')


def _send_reaction(message_id: str, contact_id: str, recipient_phone: str,
                   phone_number_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """Send reaction emoji to an existing message."""
    reaction_message_id = body.get('reactionMessageId')
    reaction_emoji = body.get('reactionEmoji', '\U0001F44D')

    if not reaction_message_id:
        return _error_response(400, 'reactionMessageId is required for reactions')

    formatted = _format_phone(recipient_phone)
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': formatted,
        'type': 'reaction',
        'reaction': {'message_id': reaction_message_id, 'emoji': reaction_emoji}
    }

    result = send_message(phone_number_id, payload, META_API_VERSION)
    wa_id = result.get('messageId', '')
    _emit_metric('success')
    logger.info(json.dumps({'event': 'reaction_sent', 'messageId': message_id, 'waId': wa_id, 'emoji': reaction_emoji, 'requestId': request_id}))
    return _success_response(message_id, wa_id, 'reaction', extra={'emoji': reaction_emoji})


def _send_order_status(message_id: str, contact_id: str, recipient_phone: str,
                       phone_number_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """Send order_status interactive message (payment confirmation)."""
    details = body.get('orderStatusDetails', {})
    reference_id = details.get('reference_id', '')
    order_status = details.get('order_status', 'completed')
    amount = details.get('amount', 0)

    try:
        amount = float(amount) if amount else 0.0
    except (ValueError, TypeError):
        amount = 0.0

    if order_status in ('completed', 'captured'):
        body_text = f"Payment of \u20b9{amount:.2f} received successfully! Thank you \u2705" if amount > 0 else details.get('description', 'Payment received successfully! Thank you \u2705')
        description = "Payment received. Thank you!"
        order_status = 'completed'
    elif order_status == 'failed':
        body_text = "Payment failed. Please try again \u274c"
        description = "Payment failed"
    else:
        body_text = details.get('description', 'Order status updated')
        description = body_text

    formatted = _format_phone(recipient_phone)
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': formatted,
        'type': 'interactive',
        'interactive': {
            'type': 'order_status',
            'body': {'text': body_text},
            'action': {
                'name': 'review_order',
                'parameters': {
                    'reference_id': reference_id,
                    'order': {'status': order_status, 'description': description}
                }
            }
        }
    }

    result = send_message(phone_number_id, payload, META_API_VERSION)
    wa_id = result.get('messageId', '')
    _store_record(message_id, contact_id, recipient_phone, f'[order_status:{order_status}]', 'order_status', wa_id, phone_number_id)
    _emit_metric('success')
    logger.info(json.dumps({'event': 'order_status_sent', 'messageId': message_id, 'waId': wa_id, 'status': order_status, 'requestId': request_id}))
    return _success_response(message_id, wa_id, 'order_status', extra={'orderStatus': order_status, 'referenceId': reference_id})


def _send_interactive(message_id: str, contact_id: str, recipient_phone: str,
                      phone_number_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """Send interactive message: list, button, cta_url, location_request, flow, order_details."""
    interactive_type = body.get('interactiveType', '')
    data = body.get('interactiveData', {})

    if not interactive_type:
        return _error_response(400, 'interactiveType is required')

    formatted = _format_phone(recipient_phone)
    base = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': formatted,
        'type': 'interactive'
    }

    builder = _INTERACTIVE_BUILDERS.get(interactive_type)
    if not builder:
        return _error_response(400, f'Invalid interactiveType: {interactive_type}')

    interactive_payload = builder(data, body)
    if isinstance(interactive_payload, dict) and interactive_payload.get('statusCode'):
        return interactive_payload  # error response from builder

    base['interactive'] = interactive_payload
    result = send_message(phone_number_id, base, META_API_VERSION)
    wa_id = result.get('messageId', '')
    _store_record(message_id, contact_id, recipient_phone, f'[interactive:{interactive_type}]', interactive_type, wa_id, phone_number_id)
    _emit_metric('success')
    logger.info(json.dumps({'event': 'interactive_sent', 'messageId': message_id, 'waId': wa_id, 'type': interactive_type, 'requestId': request_id}))
    return _success_response(message_id, wa_id, 'interactive', extra={'interactiveType': interactive_type})


def _send_location(message_id: str, contact_id: str, recipient_phone: str,
                   phone_number_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """Send location message."""
    latitude = body.get('latitude')
    longitude = body.get('longitude')
    if latitude is None or longitude is None:
        return _error_response(400, 'latitude and longitude are required')

    formatted = _format_phone(recipient_phone)
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': formatted,
        'type': 'location',
        'location': {
            'latitude': str(latitude),
            'longitude': str(longitude),
        }
    }
    if body.get('locationName'):
        payload['location']['name'] = body['locationName']
    if body.get('locationAddress'):
        payload['location']['address'] = body['locationAddress']

    result = send_message(phone_number_id, payload, META_API_VERSION)
    wa_id = result.get('messageId', '')
    _store_record(message_id, contact_id, recipient_phone, f'[Location: {latitude}, {longitude}]', 'location', wa_id, phone_number_id)
    _emit_metric('success')
    logger.info(json.dumps({'event': 'location_sent', 'messageId': message_id, 'waId': wa_id, 'requestId': request_id}))
    return _success_response(message_id, wa_id, 'location')


def _send_contacts(message_id: str, contact_id: str, recipient_phone: str,
                   phone_number_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """Send contacts (vCard) message."""
    contacts_data = body.get('contacts', [])
    if not contacts_data:
        return _error_response(400, 'contacts array is required')

    formatted = _format_phone(recipient_phone)
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': formatted,
        'type': 'contacts',
        'contacts': contacts_data
    }

    result = send_message(phone_number_id, payload, META_API_VERSION)
    wa_id = result.get('messageId', '')
    _store_record(message_id, contact_id, recipient_phone, f'[Contacts: {len(contacts_data)}]', 'contacts', wa_id, phone_number_id)
    _emit_metric('success')
    logger.info(json.dumps({'event': 'contacts_sent', 'messageId': message_id, 'waId': wa_id, 'count': len(contacts_data), 'requestId': request_id}))
    return _success_response(message_id, wa_id, 'contacts')


# ---------------------------------------------------------------------------
# Interactive message builders
# ---------------------------------------------------------------------------

def _build_list(data: Dict, body: Dict) -> Dict:
    """Build list interactive payload. Max 10 sections, 10 rows total."""
    result = {
        'type': 'list',
        'body': {'text': data.get('body', 'Please select an option')},
        'action': {'button': data.get('buttonText', 'View Options')[:20], 'sections': []}
    }
    if data.get('header'):
        result['header'] = {'type': 'text', 'text': data['header']}
    if data.get('footer'):
        result['footer'] = {'text': data['footer']}

    for section in data.get('sections', [])[:10]:
        s = {'title': section.get('title', 'Options'), 'rows': []}
        for row in section.get('rows', [])[:10]:
            s['rows'].append({
                'id': row.get('id', str(len(s['rows']))),
                'title': row.get('title', 'Option')[:24],
                'description': row.get('description', '')[:72]
            })
        if s['rows']:
            result['action']['sections'].append(s)
    return result


def _build_button(data: Dict, body: Dict) -> Dict:
    """Build reply-button interactive payload. Max 3 buttons."""
    result = {
        'type': 'button',
        'body': {'text': data.get('body', 'Please select an option')},
        'action': {'buttons': []}
    }
    header_type = data.get('headerType', 'text')
    if data.get('header') or header_type != 'text':
        if header_type == 'text' and data.get('header'):
            result['header'] = {'type': 'text', 'text': data['header']}
        elif header_type in ('image', 'video', 'document') and data.get('headerMedia'):
            h = {'type': header_type, header_type: {'link': data['headerMedia']}}
            if header_type == 'document':
                h[header_type]['filename'] = data.get('headerFilename', 'document.pdf')
            result['header'] = h
    if data.get('footer'):
        result['footer'] = {'text': data['footer']}

    for i, btn in enumerate(data.get('buttons', [])[:3]):
        result['action']['buttons'].append({
            'type': 'reply',
            'reply': {'id': btn.get('id', f'btn_{i}'), 'title': btn.get('title', 'Button')[:20]}
        })
    return result


def _build_cta_url(data: Dict, body: Dict) -> Dict:
    """Build CTA URL interactive payload."""
    url = data.get('url', '')
    if not url:
        return _error_response(400, 'url is required for cta_url')

    result = {
        'type': 'cta_url',
        'body': {'text': data.get('body', 'Click the button below')},
        'action': {
            'name': 'cta_url',
            'parameters': {'display_text': data.get('buttonText', 'Visit')[:20], 'url': url}
        }
    }
    if data.get('header'):
        ht = data.get('headerType', 'text')
        if ht == 'text':
            result['header'] = {'type': 'text', 'text': data['header']}
        elif ht in ('image', 'video') and data.get('headerMedia'):
            result['header'] = {'type': ht, ht: {'link': data['headerMedia']}}
    if data.get('footer'):
        result['footer'] = {'text': data['footer']}
    return result


def _build_location_request(data: Dict, body: Dict) -> Dict:
    """Build location request interactive payload."""
    return {
        'type': 'location_request_message',
        'body': {'text': data.get('body', 'Please share your location')},
        'action': {'name': 'send_location'}
    }


def _build_flow(data: Dict, body: Dict) -> Dict:
    """Build WhatsApp Flow interactive payload."""
    flow_id = data.get('flowId', '')
    if not flow_id:
        return _error_response(400, 'flowId is required for flow')

    result = {
        'type': 'flow',
        'body': {'text': data.get('body', 'Start the flow')},
        'action': {
            'name': 'flow',
            'parameters': {
                'flow_message_version': '3',
                'flow_token': data.get('flowToken', str(uuid.uuid4())),
                'flow_id': flow_id,
                'flow_cta': data.get('flowCta', 'Start')[:20],
                'flow_action': data.get('flowAction', 'navigate')
            }
        }
    }
    screen_id = data.get('screenId')
    if screen_id:
        fp = {'screen': screen_id}
        if data.get('flowData'):
            fp['data'] = data['flowData']
        result['action']['parameters']['flow_action_payload'] = fp
    if data.get('header'):
        result['header'] = {'type': 'text', 'text': data['header']}
    if data.get('footer'):
        result['footer'] = {'text': data['footer']}
    return result


def _build_order_details(data: Dict, body: Dict) -> Dict:
    """Build interactive order_details (payment request) payload."""
    order = body.get('orderDetails', data)
    reference_id = order.get('reference_id', str(uuid.uuid4()))
    currency = order.get('currency', 'INR')
    total_amount = order.get('total_amount', {'value': 100, 'offset': 100})
    payment_config = order.get('payment_configuration', 'WECARE-DIGITAL')

    result = {
        'type': 'order_details',
        'header': {'type': 'image', 'image': {'link': order.get('headerImage', 'https://app.wecare.digital/stream/media/m/wecare-digital.png')}},
        'body': {'text': order.get('body', 'Your payment is overdue\u2014please tap below to complete it \U0001f4b3\U0001f91d')},
        'footer': {'text': order.get('footer', 'WECARE.DIGITAL')},
        'action': {
            'name': 'review_and_pay',
            'parameters': {
                'reference_id': reference_id,
                'type': order.get('type', 'digital-goods'),
                'payment_settings': [{
                    'type': 'payment_gateway',
                    'payment_gateway': {'type': 'razorpay', 'configuration_name': payment_config}
                }],
                'currency': currency,
                'total_amount': total_amount,
                'order': order.get('order', {})
            }
        }
    }
    return result


# Map interactive types to builder functions
_INTERACTIVE_BUILDERS = {
    'list': _build_list,
    'button': _build_button,
    'cta_url': _build_cta_url,
    'location_request': _build_location_request,
    'flow': _build_flow,
    'order_details': _build_order_details,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_phone(phone: str) -> str:
    """Normalize phone to +digits format for WhatsApp API."""
    digits = re.sub(r'[^\d]', '', phone)
    return f"+{digits}" if digits else phone


def _get_contact(contact_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve contact from DynamoDB."""
    table = dynamodb.Table(CONTACTS_TABLE)
    try:
        resp = table.get_item(Key={'id': contact_id})
        return resp.get('Item')
    except Exception as e:
        logger.warning(json.dumps({'event': 'contact_lookup_fail', 'contactId': contact_id, 'error': str(e)}))
        return None


def _check_rate_limit(phone_number_id: str) -> bool:
    """Simple rate limit check. Returns True if under limit."""
    # In production, use DynamoDB atomic counter or ElastiCache
    # For reference implementation, always allow
    return True


def _store_record(message_id: str, contact_id: str, recipient_phone: str,
                  content: str, message_type: str, wa_message_id: str,
                  phone_number_id: str):
    """Store outbound message record in DynamoDB."""
    try:
        store_outbound_message({
            'id': message_id,
            'contactId': contact_id,
            'recipientPhone': recipient_phone,
            'content': content,
            'messageType': message_type,
            'channel': 'whatsapp',
            'direction': 'outbound',
            'status': 'sent',
            'whatsappMessageId': wa_message_id,
            'phoneNumberId': phone_number_id,
        })
    except Exception as e:
        logger.error(json.dumps({'event': 'store_record_fail', 'messageId': message_id, 'error': str(e)}))


def _handle_dry_run(message_id: str, recipient_phone: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """DRY_RUN mode — log payload without calling API."""
    logger.info(json.dumps({
        'event': 'dry_run',
        'messageId': message_id,
        'recipientPhone': recipient_phone,
        'body': body,
        'requestId': request_id
    }))
    return {
        'statusCode': 200,
        'headers': CORS_HEADERS,
        'body': json.dumps({'messageId': message_id, 'status': 'dry_run', 'mode': 'DRY_RUN'})
    }


def _success_response(message_id: str, wa_message_id: str, msg_type: str,
                      extra: Dict = None) -> Dict[str, Any]:
    """Standard success response."""
    resp = {
        'messageId': message_id,
        'whatsappMessageId': wa_message_id,
        'status': 'sent',
        'mode': SEND_MODE,
        'type': msg_type
    }
    if extra:
        resp.update(extra)
    return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps(resp)}


def _error_response(status_code: int, error: str) -> Dict[str, Any]:
    """Standard error response."""
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps({'error': error, 'status': 'failed'})
    }


def _emit_metric(status: str, is_template: bool = False):
    """Emit delivery metric to CloudWatch."""
    try:
        cloudwatch.put_metric_data(
            Namespace=METRICS_NAMESPACE,
            MetricData=[
                {
                    'MetricName': f'Messages{status.capitalize()}',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Channel', 'Value': 'WHATSAPP'},
                        {'Name': 'Status', 'Value': status.upper()},
                        {'Name': 'MessageType', 'Value': 'TEMPLATE' if is_template else 'FREEFORM'}
                    ]
                },
                {
                    'MetricName': 'MessagesTotal',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [{'Name': 'Channel', 'Value': 'WHATSAPP'}]
                }
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to emit metric: {e}")
