"""Meta webhook `X-Hub-Signature-256` verification over the raw request body.

Meta signs every webhook POST with HMAC-SHA256 keyed by the app secret and sends
the hex digest as `X-Hub-Signature-256: sha256=<digest>`. The digest covers the
exact bytes delivered, so verification must happen before any JSON parsing or
reserialization.

Two apps publish into this account (WABA1 and WABA2), each with its own app
secret, so a callback may legitimately be signed by either. Candidates are tried
in turn with a constant-time comparison.

Why this is shared
------------------
`whatsapp-calling` already verified signatures correctly on the canonical `/whatsapp`
ingress. `inbound-whatsapp` did not verify anything, because it was written to be
reached only by an internal `lambda_client.invoke` from that ingress - yet it also
sat behind a public `POST /whatsapp/inbound` route with `AuthorizationType=NONE`,
giving an unauthenticated caller a second door into the same message pipeline and
into its `create_invoice` branch. Extracting the check here means both entry
points enforce one implementation rather than two divergent copies.

This module never fails open: no candidate secret means no trust.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from typing import Any, Dict, Iterable, Tuple

SIGNATURE_HEADER = "x-hub-signature-256"


def raw_body(event: Dict[str, Any]) -> str:
    """Return the untouched body, base64-decoded if the gateway encoded it."""
    body = event.get("body")
    if body is None:
        return ""
    if not isinstance(body, str):
        raise ValueError("body is not raw; signature cannot be verified")
    if event.get("isBase64Encoded"):
        try:
            return base64.b64decode(body).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"body is not decodable base64: {exc}") from exc
    return body


def _header(headers: Dict[str, Any], name: str) -> str:
    if not headers:
        return ""
    if name in headers:
        return str(headers[name] or "")
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == name:
            return str(value or "")
    return ""


def expected_signature(secret: str, body: str) -> str:
    """`sha256=` + hex HMAC-SHA256 of the raw body, keyed by the app secret."""
    return "sha256=" + hmac.new(
        secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify(event: Dict[str, Any], secrets: Iterable[str]) -> Tuple[bool, str]:
    """Verify the Meta signature against any of `secrets`.

    Returns `(ok, reason)`. `reason` is a short stable token, safe to log: it
    never contains a secret, a signature or body content.
    """
    candidates = [s for s in (secrets or []) if s]
    if not candidates:
        return False, "no_app_secret_configured"

    header = _header(event.get("headers") or {}, SIGNATURE_HEADER).strip()
    if not header:
        return False, "missing_signature"

    try:
        body = raw_body(event)
    except ValueError:
        return False, "body_not_raw"

    for secret in candidates:
        if hmac.compare_digest(expected_signature(secret, body), header):
            return True, "ok"
    return False, "signature_mismatch"


def is_http_request(event: Dict[str, Any]) -> bool:
    """True when the event arrived through API Gateway rather than a direct invoke."""
    if not isinstance(event, dict):
        return False
    rc = event.get("requestContext")
    if isinstance(rc, dict) and ("http" in rc or "requestId" in rc or "apiId" in rc):
        return True
    return bool(event.get("routeKey") or event.get("rawPath"))
