"""E.164 normalisation and country resolution for the communications stack.

Extracted from messaging/sms-aws/handler.py so that exactly one implementation
decides what country a destination is in. Before this, the same decision was made
independently in six places by inlined `startswith('91') and len == 12` tests, and
they did not all agree.

The correctness issue this module exists to prevent
---------------------------------------------------
An earlier version of `_format_e164` applied a `+91` default to ANY 10-digit
string. Several countries are exactly 10 digits in full E.164 form:

    +6581234567   Singapore
    +85212345678  Hong Kong
    +4512345678   Denmark
    +4712345678   Norway
    +351912345678 Portugal

So `+6581234567` became `+916581234567` - a different, unrelated Indian
subscriber - and was then routed to ap-south-1 with an Indian DLT template
attached. That is misdelivery, not merely misrouting: a real message went to a
real stranger.

The rule is therefore: an explicit leading '+' means the caller already supplied
a country code and it is honoured verbatim. Only a BARE 10-digit number with no
'+' is assumed to be Indian.
"""
from __future__ import annotations

from typing import Optional

INDIA_CC = "91"
INDIA_ISO = "IN"

# +91 plus a 10-digit subscriber number.
INDIA_E164_LENGTH = 12


def to_e164(phone: str) -> str:
    """Return E.164 (`+<digits>`) or '' when the input cannot be one.

    Honours an explicit '+'. Assumes India only for a bare 10-digit number.
    """
    if not phone:
        return ""
    raw = str(phone).strip()
    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return ""
    if raw.startswith("+"):
        # Country code already present. Never re-prefix.
        return f"+{digits}"
    if len(digits) == 10:
        # Bare local number, no country code: India.
        return f"+{INDIA_CC}{digits}"
    return f"+{digits}"


def is_india(phone_e164: str) -> bool:
    """True only for +91 followed by exactly 10 digits.

    The length check matters. Without it, '+9198...' style malformed input and
    other country codes beginning '91' would be misclassified as Indian and would
    then attract DLT parameters that are invalid outside India.
    """
    digits = str(phone_e164 or "").lstrip("+")
    return digits.startswith(INDIA_CC) and len(digits) == INDIA_E164_LENGTH


def iso_country(phone_e164: str) -> Optional[str]:
    """Best-effort ISO-3166 alpha-2 for the destination.

    Deliberately narrow: India is the only country this stack makes regulatory
    decisions about, so India is the only code resolved with confidence. Everything
    else returns None, which callers must treat as "international, default region"
    rather than as an error.

    Resist widening this into a full prefix table. A partial table that looks
    authoritative is worse than an explicit None, because callers start trusting
    it for routing decisions it cannot actually support.
    """
    if not phone_e164:
        return None
    if is_india(phone_e164):
        return INDIA_ISO
    return None


def last4(phone: str) -> str:
    """Last 4 digits, for logging. Never log a full destination number."""
    digits = "".join(c for c in str(phone or "") if c.isdigit())
    return digits[-4:] if len(digits) >= 4 else ""
