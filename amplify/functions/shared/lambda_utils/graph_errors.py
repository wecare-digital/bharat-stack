"""
Single Meta Graph API error normalizer.

`normalize(body, http_status)` returns a consistent envelope used everywhere:
    {error: {message, type, code, error_subcode, fbtrace_id, is_transient,
             error_user_title, error_user_msg, http_status, retryable, raw_masked}}
"""
import json
from typing import Any, Dict, Optional

# HTTP statuses that are safe to retry (network/throttle/5xx)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# Statuses that must NEVER be retried
NON_RETRYABLE_STATUS = {400, 401, 403, 404, 422}


def _parse(body: Any) -> Dict[str, Any]:
    if isinstance(body, dict):
        return body
    if isinstance(body, (bytes, bytearray)):
        body = body.decode('utf-8', errors='ignore')
    if isinstance(body, str):
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError, ValueError):
            return {'error': {'message': body}}
    return {}


def normalize(body: Any, http_status: Optional[int] = None) -> Dict[str, Any]:
    """Return a normalized error envelope from a Meta Graph error body/status."""
    from lambda_utils.masking import mask_secrets  # local import to avoid cycle

    parsed = _parse(body)
    err = parsed.get('error', parsed) if isinstance(parsed.get('error'), dict) else parsed
    code = err.get('code', http_status)

    is_transient = bool(err.get('is_transient', False))
    if http_status in RETRYABLE_STATUS:
        is_transient = True
    retryable = is_transient and http_status not in NON_RETRYABLE_STATUS

    return {
        'error': {
            'message': err.get('message', 'Unknown Meta API error'),
            'type': err.get('type', 'GraphAPIError'),
            'code': code,
            'error_subcode': err.get('error_subcode'),
            'fbtrace_id': err.get('fbtrace_id'),
            'is_transient': is_transient,
            'error_user_title': err.get('error_user_title'),
            'error_user_msg': err.get('error_user_msg'),
            'http_status': http_status,
            'retryable': retryable,
            'raw_masked': mask_secrets(parsed),
        }
    }


def is_error(result: Any) -> bool:
    return isinstance(result, dict) and 'error' in result


def is_retryable(http_status: Optional[int], body: Any = None) -> bool:
    if http_status in NON_RETRYABLE_STATUS:
        return False
    if http_status in RETRYABLE_STATUS:
        return True
    parsed = _parse(body) if body is not None else {}
    err = parsed.get('error', {}) if isinstance(parsed, dict) else {}
    return bool(err.get('is_transient', False))
