"""
Recursive secret/PII masking for safe logging.

`mask_secrets(obj)` returns a deep-copied structure with sensitive fields masked.
Covers auth tokens, app secrets, verify/flow tokens, encryption material, SIP creds,
payment references, and (by default) full phone numbers / WA IDs.
"""
import re
from typing import Any

# Keys whose values are fully redacted
_SECRET_KEYS = {
    'authorization', 'access_token', 'accesstoken', 'token', 'appsecret_proof',
    'app_secret', 'appsecret', 'verify_token', 'verifytoken', 'encrypted_flow_data',
    'encrypted_aes_key', 'initial_vector', 'private_key', 'privatekey', 'passphrase',
    'client_encryption_key', 'sip_password', 'password', 'secret', 'client_secret',
    'flow_token', 'flowtoken',
}
# Keys treated as phone/WA id (partial mask)
_PHONE_KEYS = {
    'phone', 'phonenumber', 'phone_number', 'wa_id', 'recipient_id', 'from', 'to',
    'sender_phone', 'senderphone', 'recipientphone', 'recipient_phone', 'callernumber',
    'destinationnumber', 'msisdn', 'user_wa_id',
}
# Keys treated as payment references (partial mask)
_PAYMENT_KEYS = {
    'payment_id', 'paymentid', 'order_id', 'orderid', 'razorpay_payment_id',
    'razorpay_order_id', 'reference_id', 'referenceid', 'txnid', 'mihpayid',
}

_FULL = '***REDACTED***'


def _mask_tail(value: str, keep: int = 4) -> str:
    if not isinstance(value, str) or len(value) <= keep + 2:
        return '***'
    return value[:2] + '****' + value[-keep:]


def mask_value(key: str, value: Any) -> Any:
    k = (key or '').lower()
    if k in _SECRET_KEYS:
        return _FULL
    if isinstance(value, str):
        if k in _PHONE_KEYS:
            return _mask_tail(value, 4)
        if k in _PAYMENT_KEYS:
            return _mask_tail(value, 4)
    return value


def mask_secrets(obj: Any) -> Any:
    """Deep-mask sensitive fields in dicts/lists; returns a new structure."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = (k or '').lower()
            if kl in _SECRET_KEYS:
                out[k] = _FULL
            elif isinstance(v, (dict, list)):
                out[k] = mask_secrets(v)
            else:
                out[k] = mask_value(k, v)
        return out
    if isinstance(obj, list):
        return [mask_secrets(i) for i in obj]
    return obj


# Mask "Bearer <token>" style strings inside free text
_BEARER_RE = re.compile(r'(Bearer\s+)([A-Za-z0-9._\-]+)', re.IGNORECASE)


def mask_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    return _BEARER_RE.sub(lambda m: m.group(1) + _FULL, text)
