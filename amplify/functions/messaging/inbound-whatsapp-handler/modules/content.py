"""
Message content extraction from WhatsApp webhook payloads.

Handles all WhatsApp message types: text, image, video, audio, document,
location, contacts, sticker, reaction, interactive, button, order, system,
unsupported, request_welcome, ephemeral, referral, ad_click, product, poll.
"""

import json
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def extract_content(message: Dict, msg_type: str) -> str:
    """Extract human-readable content string from a WhatsApp message based on type."""
    extractor = _EXTRACTORS.get(msg_type)
    if extractor:
        return extractor(message)

    logger.warning(json.dumps({
        'event': 'unknown_message_type',
        'messageType': msg_type,
        'messageKeys': list(message.keys()),
    }))
    return f'[{msg_type}]'


def _text(m: Dict) -> str:
    return m.get('text', {}).get('body', '')


def _image(m: Dict) -> str:
    return m.get('image', {}).get('caption', '[Image]')


def _video(m: Dict) -> str:
    return m.get('video', {}).get('caption', '[Video]')


def _audio(_m: Dict) -> str:
    return '[Audio]'


def _document(m: Dict) -> str:
    return m.get('document', {}).get('filename', '[Document]')


def _location(m: Dict) -> str:
    loc = m.get('location', {})
    return f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"


def _contacts(_m: Dict) -> str:
    return '[Contact Card]'


def _sticker(_m: Dict) -> str:
    return '[Sticker]'


def _reaction(m: Dict) -> str:
    return m.get('reaction', {}).get('emoji', '[Reaction]')


def _interactive(m: Dict) -> str:
    interactive = m.get('interactive', {})
    itype = interactive.get('type', '')

    if itype == 'button_reply':
        btn = interactive.get('button_reply', {})
        bid = btn.get('id', '')
        if bid.startswith(('opt_', 'rate_', 'menu_', 'lang_', 'store_')):
            return bid
        return btn.get('title', '[Button Reply]')

    if itype == 'list_reply':
        lr = interactive.get('list_reply', {})
        rid = lr.get('id', '')
        if rid.startswith(('lang_', 'brand_', 'menu_', 'opt_', 'rate_')):
            return rid
        return lr.get('title', '[List Reply]')

    if itype == 'nfm_reply':
        rj = interactive.get('nfm_reply', {}).get('response_json', '')
        return f'[Flow Response: {rj[:50]}...]' if len(rj) > 50 else f'[Flow Response: {rj}]'

    if itype == 'call_permission_reply':
        cpr = interactive.get('call_permission_reply', {})
        perm = cpr.get('permission', cpr.get('status', '')) or interactive.get('permission', 'unknown')
        return f'[Call Permission: {perm}]'

    return f'[Interactive: {itype}]'


def _button(m: Dict) -> str:
    return m.get('button', {}).get('text', '[Button]')


def _order(_m: Dict) -> str:
    return '[Order]'


def _system(m: Dict) -> str:
    return m.get('system', {}).get('body', '[System Message]')


def _request_welcome(_m: Dict) -> str:
    return '[User requested to start conversation]'


def _ephemeral(m: Dict) -> str:
    """Handle ephemeral (disappearing) messages.
    
    When a chat has disappearing messages enabled, Meta may deliver the
    message with type='ephemeral'.  The actual content is sometimes nested
    inside the ephemeral object or carried as a sibling field.  We try to
    extract it; if nothing is found, we label it clearly.
    """
    # Some ephemeral messages carry the real payload inside an 'ephemeral' key
    inner = m.get('ephemeral', {})
    if isinstance(inner, dict):
        # Check for nested text
        body = inner.get('text', {}).get('body', '') if isinstance(inner.get('text'), dict) else ''
        if body:
            return body
        # Check for nested message type
        for mtype in ('text', 'image', 'video', 'audio', 'document', 'sticker'):
            if mtype in inner:
                extractor = _EXTRACTORS.get(mtype)
                if extractor:
                    return extractor(inner)
    
    # Fallback: check if text/image/video etc. exist at the top level alongside type=ephemeral
    for mtype in ('text', 'image', 'video', 'audio', 'document'):
        if mtype in m and mtype != 'ephemeral':
            extractor = _EXTRACTORS.get(mtype)
            if extractor:
                result = extractor(m)
                if result and result not in ('[Image]', '[Video]', '[Audio]', '[Document]'):
                    return result
    
    return '[Disappearing Message — content not available via Business API]'


def _referral(m: Dict) -> str:
    ref = m.get('referral', {})
    source = ref.get('source_type', 'unknown')
    headline = ref.get('headline', '')
    return f'[Referral: {source}] {headline}'.strip() if headline else f'[Referral: {source}]'


def _ad_click(m: Dict) -> str:
    ref = m.get('referral', {})
    return f'[Ad Click: {ref.get("source_url", "")}]' if ref.get('source_url') else '[Ad Click]'


def _product(m: Dict) -> str:
    prod = m.get('product', m.get('product_inquiry', {}))
    cid = prod.get('catalog_id', '')
    pid = prod.get('product_retailer_id', '')
    return f'[Product: {cid}/{pid}]' if cid else '[Product]'


def _poll(m: Dict) -> str:
    q = m.get('poll', {}).get('question', '')
    return f'[Poll: {q[:60]}]' if q else '[Poll]'


def extract_unsupported_content(message: Dict) -> str:
    """Extract info from unsupported message types.

    WhatsApp marks several message categories as 'unsupported' in the
    Business API webhook, most notably OTP / authentication templates
    sent by Meta itself.  We detect common patterns so the inbox can
    render a friendlier label instead of a generic error.
    
    Common causes of unsupported:
    - OTP / authentication templates (error 131051)
    - Disappearing / ephemeral messages sent to API numbers
    - Multi-image bundles
    - Polls, view-once, some interactive subtypes
    - Messages between two WABA/Cloud API numbers
    """
    errors = message.get('errors', [])

    # ── Detect OTP / authentication template ──
    # Meta delivers these with error code 131051 ("Message type is
    # currently not supported") but the sender is typically a short-code
    # or Meta-owned number.  The error detail string is the best signal.
    for error in errors:
        code = error.get('code', 0)
        details = error.get('details', '')
        title = error.get('title', '')
        error_text = (details or title or '').lower()

        # Error 131051 is the canonical "unsupported message type" code
        # that Meta uses for authentication / OTP templates delivered to
        # business numbers.
        if code == 131051 or 'not supported' in error_text:
            # Check if it's specifically an OTP/auth message
            if any(kw in error_text for kw in ('otp', 'authentication', 'security', 'verification')):
                return '[Unsupported: OTP or authentication message — content hidden by WhatsApp for security]'
            return f'[Unsupported: {details or title or "Message type not supported (error 131051)"}]'

        # Ephemeral / disappearing message error
        if 'ephemeral' in error_text or 'disappearing' in error_text:
            return '[Unsupported: Disappearing message — disable disappearing messages in this chat to fix]'

        if details:
            return f'[Unsupported: {details}]'
        if title:
            return f'[Unsupported: {title}]'

    if 'referral' in message:
        src = message['referral'].get('source_type', '')
        if src:
            return f'[Referral from {src}]'

    ctx = message.get('context', {})
    if ctx.get('referred_product'):
        return '[Product Inquiry]'

    for key in ('text', 'caption', 'body'):
        val = message.get(key, {})
        if isinstance(val, dict):
            body = val.get('body', '')
            if body:
                return body
        elif isinstance(val, str) and val:
            return val

    # Log the full message keys for debugging unknown unsupported types
    logger.warning(json.dumps({
        'event': 'unsupported_message_no_detail',
        'messageKeys': list(message.keys()),
        'errors': errors,
    }))

    return '[Message type not supported by WhatsApp Business API]'


# Dispatch table
_EXTRACTORS = {
    'text': _text, 'image': _image, 'video': _video, 'audio': _audio,
    'document': _document, 'location': _location, 'contacts': _contacts,
    'sticker': _sticker, 'reaction': _reaction, 'interactive': _interactive,
    'button': _button, 'order': _order, 'system': _system,
    'unsupported': lambda m: extract_unsupported_content(m),
    'request_welcome': _request_welcome, 'ephemeral': _ephemeral,
    'referral': _referral, 'ad_click': _ad_click,
    'product': _product, 'product_inquiry': _product, 'poll': _poll,
}
