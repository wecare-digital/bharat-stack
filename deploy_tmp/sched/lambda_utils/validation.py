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
