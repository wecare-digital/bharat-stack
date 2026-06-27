"""
Input validation utilities for Lambda handlers.

Usage:
    from lambda_utils.validation import validate_required, validate_body

    body = validate_body(event)
    errors = validate_required(body, ['contactId', 'phone'])
    if errors:
        return cors_response(400, {'error': 'Missing fields', 'fields': errors})
"""

import re
import json
from typing import Any, Dict, List, Optional


def validate_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely parse the request body from an API Gateway / Function URL event.
    Handles base64-encoded bodies and missing body gracefully.
    """
    import base64

    body = event.get('body', '{}')

    if event.get('isBase64Encoded') and body:
        try:
            body = base64.b64decode(body).decode('utf-8')
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Failed to base64-decode request body')

    if isinstance(body, str):
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return {}

    return body if isinstance(body, dict) else {}


def validate_required(data: Dict[str, Any], fields: List[str]) -> List[str]:
    """
    Check that all required fields are present and non-empty.
    Returns list of missing field names (empty list = all good).
    """
    missing = []
    for field in fields:
        val = data.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(field)
    return missing


# E.164 phone: optional +, 7-15 digits
_PHONE_RE = re.compile(r'^\+?\d{7,15}$')


def validate_phone(phone: Optional[str]) -> bool:
    """Validate phone number in E.164-ish format."""
    if not phone or not isinstance(phone, str):
        return False
    return bool(_PHONE_RE.match(phone.strip()))


# Basic email regex
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def validate_email(email: Optional[str]) -> bool:
    """Validate email address format."""
    if not email or not isinstance(email, str):
        return False
    return bool(_EMAIL_RE.match(email.strip()))


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Strip and truncate a string value."""
    if not isinstance(value, str):
        return ''
    return value.strip()[:max_length]


# HTML/script tag pattern for XSS prevention
_SCRIPT_RE = re.compile(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')


def sanitize_html(value: str, max_length: int = 1000) -> str:
    """
    Strip HTML tags and script content from a string to prevent XSS.
    Also truncates to max_length.
    """
    if not isinstance(value, str):
        return ''
    # Remove script tags and their content first
    cleaned = _SCRIPT_RE.sub('', value)
    # Remove remaining HTML tags
    cleaned = _TAG_RE.sub('', cleaned)
    # Replace common HTML entities
    cleaned = cleaned.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    return cleaned.strip()[:max_length]


def sanitize_dict(data: Dict[str, Any], fields: List[str], max_length: int = 1000) -> Dict[str, Any]:
    """
    Sanitize specified string fields in a dictionary.
    Returns a new dict with sanitized values.
    """
    result = dict(data)
    for field in fields:
        if field in result and isinstance(result[field], str):
            result[field] = sanitize_html(result[field], max_length)
    return result


def normalize_phone(phone: Optional[str]) -> str:
    """
    Normalize a phone number to digits-only E.164 format (no + prefix).
    Strips whitespace, dashes, parentheses, and leading + sign.
    Returns empty string if input is invalid.
    """
    if not phone or not isinstance(phone, str):
        return ''
    # Strip all non-digit characters
    digits = re.sub(r'[^\d]', '', phone.strip())
    if len(digits) < 7 or len(digits) > 15:
        return ''
    return digits


def validate_amount(amount: Any, min_val: float = 0.01, max_val: float = 1000000.0) -> bool:
    """
    Validate a payment amount is within acceptable bounds.
    Returns True if valid, False otherwise.
    """
    try:
        val = float(amount)
        return min_val <= val <= max_val
    except (TypeError, ValueError):
        return False


# ============================================================================
# WhatsApp / Meta Graph validators (Part 2 shared foundation)
# ============================================================================

_GRAPH_VERSION_RE = re.compile(r'^v\d+\.\d+$')
_NUMERIC_ID_RE = re.compile(r'^\d{5,20}$')
_QR_ID_RE = re.compile(r'^[A-Za-z0-9]{14}$')


def validate_graph_version(v: Optional[str]) -> bool:
    return bool(v and _GRAPH_VERSION_RE.match(v))


def validate_numeric_id(v: Optional[str]) -> bool:
    """WABA ID / phone-number ID / business ID / user ID / bot ID — numeric string."""
    return bool(v and _NUMERIC_ID_RE.match(str(v)))


def validate_qr_code_id(v: Optional[str]) -> bool:
    """QR code IDs are exactly 14 alphanumeric chars."""
    return bool(v and _QR_ID_RE.match(str(v)))


def validate_pagination_limit(limit: Any, max_limit: int = 100) -> bool:
    try:
        n = int(limit)
        return 1 <= n <= max_limit
    except (TypeError, ValueError):
        return False


def validate_https_url(url: Optional[str], require_https: bool = True) -> bool:
    if not url or not isinstance(url, str):
        return False
    if require_https:
        return url.startswith('https://')
    return url.startswith('http://') or url.startswith('https://')


def validate_fields_allowlist(fields: Optional[str], allowed: set) -> List[str]:
    """Return any requested field names not in the allowlist."""
    if not fields:
        return []
    return [f.strip() for f in fields.split(',') if f.strip() and f.strip() not in allowed]


def validate_template_category(category: Optional[str]) -> bool:
    return (category or '').upper() in ('MARKETING', 'UTILITY', 'AUTHENTICATION')


def validate_template_ttl(category: Optional[str], seconds: Any) -> Optional[str]:
    """Return error string or None. -1 allowed only for AUTH/UTILITY (=30d)."""
    if seconds is None:
        return None
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return 'message_send_ttl_seconds must be an integer'
    cat = (category or '').upper()
    if cat == 'AUTHENTICATION':
        return None if (s == -1 or 30 <= s <= 900) else 'AUTHENTICATION TTL must be 30-900s (or -1)'
    if cat == 'UTILITY':
        return None if (s == -1 or 30 <= s <= 43200) else 'UTILITY TTL must be 30-43200s (or -1)'
    if cat == 'MARKETING':
        return None if (43200 <= s <= 2592000) else 'MARKETING TTL must be 43200-2592000s (-1 not allowed)'
    return f'Unknown template category: {category}'


def validate_template_buttons(buttons: Optional[list]) -> Optional[str]:
    """Counts + quick-reply grouping rules. Return error string or None."""
    if not buttons:
        return None
    if len(buttons) > 10:
        return 'A template may have at most 10 buttons'
    counts: Dict[str, int] = {}
    for b in buttons:
        t = (b.get('type') or '').upper()
        counts[t] = counts.get(t, 0) + 1
        if t in ('QUICK_REPLY', 'URL', 'PHONE_NUMBER', 'VOICE_CALL') and len(b.get('text', '')) > 25:
            return f'{t} button text must be <= 25 characters'
        if t == 'COPY_CODE' and len(str(b.get('example', ''))) > 20:
            return 'COPY_CODE example must be <= 20 characters'
        if t == 'PHONE_NUMBER' and len(str(b.get('phone_number', ''))) > 20:
            return 'PHONE_NUMBER must be <= 20 characters'
        if t == 'URL' and len(str(b.get('url', ''))) > 2000:
            return 'URL must be <= 2000 characters'
    if counts.get('COPY_CODE', 0) > 1:
        return 'At most 1 COPY_CODE button allowed'
    if counts.get('PHONE_NUMBER', 0) > 1:
        return 'At most 1 PHONE_NUMBER button allowed'
    if counts.get('URL', 0) > 2:
        return 'At most 2 URL buttons allowed'
    if counts.get('QUICK_REPLY', 0) > 10:
        return 'At most 10 QUICK_REPLY buttons allowed'
    types = [(b.get('type') or '').upper() for b in buttons]
    qr = [i for i, t in enumerate(types) if t == 'QUICK_REPLY']
    if qr and (max(qr) - min(qr) + 1) != len(qr):
        return 'Quick reply buttons must be grouped together (contiguous)'
    return None


def validate_flow_name(name: Optional[str]) -> bool:
    return bool(name) and len(name) <= 200


def validate_flow_category(category: Optional[str]) -> bool:
    valid = {'SIGN_UP', 'SIGN_IN', 'APPOINTMENT_BOOKING', 'LEAD_GENERATION', 'CONTACT_US',
             'CUSTOMER_SUPPORT', 'SURVEY', 'OTHER'}
    return (category or '').upper() in valid


def validate_join_approval_mode(mode: Optional[str]) -> bool:
    return mode in ('approval_required', 'auto_approve')


def needs_url_encoding_warning(value: Optional[str]) -> bool:
    """True if a template URL parameter value contains characters that should be percent-encoded."""
    if not value:
        return False
    return any(c in value for c in (' ', ':', '|')) or any(ord(c) > 127 for c in value)


def check_open_graph(og: Dict[str, str]) -> List[str]:
    """Best-effort Open Graph link-preview checks. Returns warnings list."""
    warnings = []
    if not og.get('og:title'):
        warnings.append('og:title is missing or empty')
    if not og.get('og:description'):
        warnings.append('og:description is missing or empty')
    if not og.get('og:url'):
        warnings.append('og:url is missing or empty')
    img = og.get('og:image', '')
    if not img:
        warnings.append('og:image is missing')
    elif not img.startswith('http'):
        warnings.append('og:image must be an absolute URL')
    return warnings
