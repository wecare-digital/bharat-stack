"""Razorpay order creation for paid secure-file downloads.

Imported lazily by ``handler._create_order`` and only when
``SECURE_FILES_PAYMENT_ENABLED`` is on, so that with the flag off this module is
never loaded, no credential is read and no Razorpay endpoint is contacted.

Credential handling
-------------------
The key is fetched from Secrets Manager **inside the function, at request time**,
and cached only for the life of the sandbox. It is never placed in an environment
variable, never logged, never returned to a caller, and never interpolated into a
command. ``key_id`` is publishable (the browser checkout needs it); ``key_secret``
is used only as HTTP basic auth here and must not leave this module.

The read is lazy rather than at import for the reason recorded in
``.kiro/steering/lambda-snapstart-deploy.md``: a module-scope secret read is
cached for the life of the execution environment, so a rotated value would not
take effect until every warm sandbox recycled.

Granting access is NOT this module's job. An order is only an intent to pay.
Entitlement is written by ``payments/razorpay-webhook`` after it verifies the
webhook signature, because a client-side success callback is trivially forged.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

import boto3

RAZORPAY_SECRET_ID = os.environ.get("RAZORPAY_SECRET_ID", "wecare/razorpay-webhook")
ORDERS_ENDPOINT = "https://api.razorpay.com/v1/orders"
TIMEOUT_SECONDS = 10

_sm = None
_cached: Optional[Dict[str, str]] = None


def _secrets_client():
    global _sm
    if _sm is None:
        _sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _sm


def _credentials() -> Dict[str, str]:
    """key_id and key_secret, cached per sandbox. Never logged."""
    global _cached
    if _cached is None:
        raw = _secrets_client().get_secret_value(SecretId=RAZORPAY_SECRET_ID)
        parsed = json.loads(raw.get("SecretString") or "{}")
        _cached = {
            "key_id": (parsed.get("key_id") or "").strip(),
            "key_secret": (parsed.get("key_secret") or "").strip(),
        }
    if not _cached["key_id"] or not _cached["key_secret"]:
        # Deliberately says which secret to look at and nothing about its contents.
        raise RuntimeError(f"Razorpay key_id/key_secret missing from {RAZORPAY_SECRET_ID}")
    return _cached


def create_order(*, amount_paise: int, receipt: str, notes: Dict[str, Any]) -> Dict[str, Any]:
    """Create an INR order and return Razorpay's record plus the public key id.

    ``payment_capture`` is left at Razorpay's account default rather than forced
    here: capture behaviour is payment configuration and is the account owner's
    decision, not this module's.
    """
    if amount_paise <= 0:
        raise ValueError("amount_paise must be positive")

    creds = _credentials()
    payload = json.dumps(
        {
            "amount": int(amount_paise),
            "currency": "INR",
            "receipt": receipt[:40],
            "notes": notes,
        }
    ).encode("utf-8")

    token = base64.b64encode(
        f"{creds['key_id']}:{creds['key_secret']}".encode("utf-8")
    ).decode("ascii")

    request = urllib.request.Request(
        ORDERS_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {token}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            order = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Razorpay error bodies describe the request, not the credential, but the
        # request carried basic auth - so surface the status only.
        raise RuntimeError(f"Razorpay order creation failed with HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Razorpay unreachable") from None

    order["key_id"] = creds["key_id"]
    return order
