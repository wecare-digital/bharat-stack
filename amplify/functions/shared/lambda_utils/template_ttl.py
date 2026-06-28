"""
Consolidated WhatsApp template TTL (message_send_ttl_seconds) service.

Single source of truth for TTL rules, validation, humanization and the
"null TTL after automatic category change" detection. All handlers should
import from here instead of re-implementing the bounds.

Rules (per Meta docs):
  AUTHENTICATION: 30 .. 900 seconds. -1 allowed (= 30-day TTL).
                  Recommend TTL <= the OTP/code expiry.
  UTILITY:        30 .. 43200 seconds. -1 allowed (= 30-day TTL).
  MARKETING:      43200 .. 2592000 seconds. -1 NOT allowed.
"""
from typing import Any, Dict, List, Optional

from .whatsapp_types import TTL_BOUNDS, TTL_NEG1_ALLOWED

# 30-day sentinel meaning of -1 (informational only)
NEG1_EQUIVALENT_SECONDS = 30 * 24 * 3600  # 2592000


def humanize_seconds(seconds: Any) -> str:
    """Render a TTL in seconds as a human-readable string."""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return str(seconds)
    if s == -1:
        return '30 days (maximum)'
    if s < 0:
        return f'{s} seconds'
    if s < 60:
        return f'{s} second' + ('' if s == 1 else 's')
    if s < 3600:
        m = s / 60
        return f'{m:g} minute' + ('' if m == 1 else 's')
    if s < 86400:
        h = s / 3600
        return f'{h:g} hour' + ('' if h == 1 else 's')
    d = s / 86400
    return f'{d:g} day' + ('' if d == 1 else 's')


def ttl_rules() -> Dict[str, Any]:
    """Return the full, human-readable TTL rule set for all categories."""
    categories = {}
    for cat, (lo, hi) in TTL_BOUNDS.items():
        neg1 = cat in TTL_NEG1_ALLOWED
        categories[cat] = {
            'minSeconds': lo,
            'maxSeconds': hi,
            'minHuman': humanize_seconds(lo),
            'maxHuman': humanize_seconds(hi),
            'allowNeg1': neg1,
            'neg1Meaning': '30-day TTL' if neg1 else None,
            'description': (
                f'{cat}: {humanize_seconds(lo)} to {humanize_seconds(hi)}'
                + (' (or -1 for a 30-day TTL)' if neg1 else ' (-1 not allowed)')
            ),
        }
    # Soft recommendation only — not enforced.
    categories['AUTHENTICATION']['recommendation'] = (
        'Set TTL less than or equal to the OTP/code expiry time.'
    )
    return {
        'field': 'message_send_ttl_seconds',
        'categories': categories,
        'notes': [
            'A null TTL can appear after Meta automatically changes a template category.',
            '-1 represents the maximum 30-day TTL and is only valid for AUTHENTICATION and UTILITY.',
        ],
    }


def validate_ttl(category: Optional[str], seconds: Any) -> Dict[str, Any]:
    """
    Structured validation. Returns:
      { ok: bool, error: str|None, warnings: [str], category: str,
        seconds: int|None, human: str|None }
    A None TTL is treated as valid (Meta applies its default) but surfaced
    as a warning so callers can flag a cleared TTL.
    """
    cat = (category or '').upper()
    result: Dict[str, Any] = {
        'ok': True,
        'error': None,
        'warnings': [],
        'category': cat,
        'seconds': None,
        'human': None,
    }

    if cat and cat not in TTL_BOUNDS:
        result['ok'] = False
        result['error'] = f'Unknown template category: {category}'
        return result

    if seconds is None:
        result['warnings'].append(
            'No TTL set (message_send_ttl_seconds is null); Meta will apply its default.'
        )
        return result

    try:
        s = int(seconds)
    except (TypeError, ValueError):
        result['ok'] = False
        result['error'] = 'message_send_ttl_seconds must be an integer'
        return result

    result['seconds'] = s
    result['human'] = humanize_seconds(s)

    if not cat:
        result['ok'] = False
        result['error'] = 'category is required to validate TTL'
        return result

    lo, hi = TTL_BOUNDS[cat]
    allow_neg1 = cat in TTL_NEG1_ALLOWED

    if s == -1:
        if not allow_neg1:
            result['ok'] = False
            result['error'] = f'{cat} TTL must be {lo}-{hi}s (-1 not allowed)'
        return result

    if not (lo <= s <= hi):
        result['ok'] = False
        suffix = ' (or -1 for 30 days)' if allow_neg1 else ' (-1 not allowed)'
        result['error'] = f'{cat} TTL must be {lo}-{hi}s{suffix}'
        return result

    return result


def validate_ttl_error(category: Optional[str], seconds: Any) -> Optional[str]:
    """Backwards-compatible helper: return an error string or None."""
    if seconds is None:
        return None
    res = validate_ttl(category, seconds)
    return None if res['ok'] else res['error']


def detect_null_ttl_after_category_change(
    old_category: Optional[str],
    new_category: Optional[str],
    new_ttl: Any,
) -> Optional[str]:
    """
    Return a warning string if a category change has cleared the TTL.
    Meta can auto-change a template's category (e.g. MARKETING <-> UTILITY)
    which may reset message_send_ttl_seconds to null.
    """
    old = (old_category or '').upper()
    new = (new_category or '').upper()
    if old and new and old != new and new_ttl is None:
        return (
            f'TTL was cleared after category changed from {old} to {new}. '
            f'Re-set message_send_ttl_seconds for the {new} category.'
        )
    return None
