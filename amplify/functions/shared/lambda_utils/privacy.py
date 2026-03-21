"""
PII redaction utilities for Lambda handlers.

Usage:
    from lambda_utils.privacy import mask_phone, mask_email, redact_pii

    masked = mask_phone('+919330994400')  # '+91****4400'
    masked = mask_email('user@example.com')  # 'u***@example.com'
    safe = redact_pii({'phone': '+919330994400', 'name': 'Test'})
"""

import re
from typing import Any, Dict


def mask_phone(phone: str) -> str:
    """Mask phone number, keeping country code and last 4 digits."""
    if not phone or not isinstance(phone, str):
        return '***'
    clean = phone.strip()
    if len(clean) <= 6:
        return '***'
    # Keep first 3 chars (e.g. +91) and last 4
    return clean[:3] + '****' + clean[-4:]


def mask_email(email: str) -> str:
    """Mask email address, keeping first char and domain."""
    if not email or not isinstance(email, str):
        return '***'
    parts = email.split('@')
    if len(parts) != 2:
        return '***'
    local = parts[0]
    return local[0] + '***@' + parts[1] if local else '***@' + parts[1]


_PHONE_RE = re.compile(r'\+?\d{10,15}')
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


def redact_pii(data: Dict[str, Any], phone_fields: list = None, email_fields: list = None) -> Dict[str, Any]:
    """
    Redact PII fields in a dictionary for safe logging.
    Auto-detects phone/email fields by name if not specified.
    Returns a new dict (does not mutate original).
    """
    if not isinstance(data, dict):
        return data

    phone_keys = set(phone_fields or [
        'phone', 'phoneNumber', 'phone_number', 'senderPhone', 'sender_phone',
        'recipientPhone', 'recipient_phone', 'fromNumber', 'from_number',
        'toNumber', 'to_number', 'callerNumber', 'destinationNumber',
        'from', 'to', 'wa_id', 'recipient_id', 'contactPhone',
    ])
    email_keys = set(email_fields or [
        'email', 'buyerEmail', 'contactEmail',
    ])

    result = {}
    for key, val in data.items():
        if key in phone_keys and isinstance(val, str):
            result[key] = mask_phone(val)
        elif key in email_keys and isinstance(val, str):
            result[key] = mask_email(val)
        elif isinstance(val, dict):
            result[key] = redact_pii(val, phone_fields, email_fields)
        else:
            result[key] = val
    return result


def redact_string(text: str) -> str:
    """Redact phone numbers and emails from a free-text string."""
    if not text or not isinstance(text, str):
        return text
    result = _PHONE_RE.sub(lambda m: mask_phone(m.group()), text)
    result = _EMAIL_RE.sub(lambda m: mask_email(m.group()), result)
    return result
