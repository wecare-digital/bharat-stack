"""Sinch Conversation API webhook HMAC verification.

Contract, from the official Sinch Conversation API callbacks documentation
(https://developers.sinch.com/docs/conversation/callbacks, retrieved
2026-09-21). Content rephrased for compliance with licensing restrictions:

A callback from a webhook that has a secret configured carries four headers:

    x-sinch-webhook-signature-timestamp   UTC timestamp the signature was computed
    x-sinch-webhook-signature-nonce       unique nonce, usable for replay defence
    x-sinch-webhook-signature-algorithm   currently always HmacSHA256
    x-sinch-webhook-signature             the signature itself

The signature is computed over the raw request body, the nonce and the
timestamp, joined with single dots, and base64-encoded:

    base64( HMAC_SHA256( secret, rawBody + "." + nonce + "." + timestamp ) )

Sinch is explicit that validation must use the **raw** body, before any JSON
parsing, reserialization, whitespace change or pretty-printing, because any of
those alters the digest. This module therefore takes the raw body string and
never parses it.

Why this exists
---------------
Until 2026-09-21 `POST /webhook/sinch-rcs` had `AuthorizationType=NONE` at the
gateway and no verification of any kind in the handler. Anyone could post a
forged inbound RCS message or delivery report, which the handler wrote into the
canonical messages table and which could trigger an automation rule that sends a
real outbound RCS message to a number supplied in the same unauthenticated body.

Callbacks are only signed when a secret is configured on the webhook at Sinch.
A missing secret is therefore an unverifiable request, not a trusted one, and
the caller must treat it as such - see `rcs-dlr/handler.py`, which answers with a
retryable 503 rather than processing it.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time
from typing import Any, Dict, Tuple

SIGNATURE_HEADER = "x-sinch-webhook-signature"
NONCE_HEADER = "x-sinch-webhook-signature-nonce"
TIMESTAMP_HEADER = "x-sinch-webhook-signature-timestamp"
ALGORITHM_HEADER = "x-sinch-webhook-signature-algorithm"

SUPPORTED_ALGORITHM = "hmacsha256"

# Reject a signature whose timestamp is implausibly old or far in the future.
# Generous by design: Sinch retries with exponential backoff, so a legitimate
# retry can be minutes old, and rejecting those would lose real receipts.
DEFAULT_MAX_SKEW_SECONDS = 15 * 60


def raw_body(event: Dict[str, Any]) -> str:
    """Return the untouched request body, base64-decoded if the gateway encoded it.

    Never json.loads here. The digest is computed over these exact bytes.
    """
    body = event.get("body")
    if body is None:
        return ""
    if not isinstance(body, str):
        # A dict body means something already parsed it, so the raw bytes that
        # Sinch signed are gone and no honest verification is possible.
        raise ValueError("body is not raw; signature cannot be verified")
    if event.get("isBase64Encoded"):
        try:
            return base64.b64decode(body).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"body is not decodable base64: {exc}") from exc
    return body


def _header(headers: Dict[str, Any], name: str) -> str:
    """Case-insensitive header lookup; API Gateway v2 lowercases, others may not."""
    if not headers:
        return ""
    if name in headers:
        return str(headers[name] or "")
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == name:
            return str(value or "")
    return ""


def expected_signature(secret: str, body: str, nonce: str, timestamp: str) -> str:
    """base64( HMAC_SHA256( secret, body + '.' + nonce + '.' + timestamp ) )."""
    signed_data = f"{body}.{nonce}.{timestamp}"
    digest = hmac.new(
        secret.encode("utf-8"), signed_data.encode("utf-8"), hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def verify(
    event: Dict[str, Any],
    secret: str,
    *,
    max_skew_seconds: int = DEFAULT_MAX_SKEW_SECONDS,
    now: float | None = None,
) -> Tuple[bool, str]:
    """Verify a Sinch webhook callback.

    Returns `(ok, reason)`. `reason` is a short stable token for logging and is
    safe to emit: it never contains the secret, the signature or the body.

    This function never fails open. An absent secret is a caller error - decide
    the HTTP response for that case at the call site, where the retry semantics
    are known.
    """
    if not secret:
        return False, "no_secret_configured"

    headers = event.get("headers") or {}
    signature = _header(headers, SIGNATURE_HEADER).strip()
    nonce = _header(headers, NONCE_HEADER).strip()
    timestamp = _header(headers, TIMESTAMP_HEADER).strip()
    algorithm = _header(headers, ALGORITHM_HEADER).strip()

    if not signature:
        return False, "missing_signature"
    if not nonce:
        return False, "missing_nonce"
    if not timestamp:
        return False, "missing_timestamp"

    # An unexpected algorithm must not be silently treated as SHA256.
    if algorithm and algorithm.replace("-", "").lower() != SUPPORTED_ALGORITHM:
        return False, "unsupported_algorithm"

    if max_skew_seconds:
        try:
            sent_at = float(timestamp)
        except (TypeError, ValueError):
            return False, "unparsable_timestamp"
        current = time.time() if now is None else now
        if abs(current - sent_at) > max_skew_seconds:
            return False, "timestamp_outside_window"

    try:
        body = raw_body(event)
    except ValueError:
        return False, "body_not_raw"

    candidate = expected_signature(secret, body, nonce, timestamp)
    if hmac.compare_digest(candidate, signature):
        return True, "ok"
    return False, "signature_mismatch"


def is_http_request(event: Dict[str, Any]) -> bool:
    """True when the event came through API Gateway rather than a direct invoke.

    Used to apply webhook verification only to requests that actually crossed the
    public boundary, so internal typed invocations - which were already verified
    upstream - are not required to carry a provider signature they never had.
    """
    if not isinstance(event, dict):
        return False
    rc = event.get("requestContext")
    if isinstance(rc, dict) and ("http" in rc or "requestId" in rc or "apiId" in rc):
        return True
    return bool(event.get("routeKey") or event.get("rawPath"))
