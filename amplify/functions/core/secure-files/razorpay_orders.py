"""Razorpay order creation for paid secure-file downloads.

Imported lazily by ``handler._create_order`` and only when
``SECURE_FILES_PAYMENT_ENABLED`` is on, so that with the flag off this module is
never loaded, no credential is read and no Razorpay endpoint is contacted.

Which secret, and why it matters
--------------------------------
There are **two** Razorpay secrets and they hold different fields::

    wecare/razorpay/api        key_id + key_secret    API auth  <- this module
    wecare/razorpay-webhook    webhook_secret         signature verification

Conflating them has already cost this codebase once: ``partner-onboarding`` read
the API pair out of ``wecare/razorpay-webhook``, which has only ever contained
``webhook_secret``, so ``key_id``/``key_secret`` came back empty and every
self-service top-up returned 501. Verified again 2026-09-25 - both secrets exist,
and the webhook one still holds exactly one field.

So this module reads ``wecare/razorpay/api`` and nothing else. If order creation
ever starts failing with a missing-key error, check that the env var was not
pointed back at the webhook secret.

Credential handling
-------------------
The key is fetched from Secrets Manager **inside the function, at request time**,
and cached only for the life of the sandbox. It is never placed in an environment
variable, never logged, never returned to a caller, and never interpolated into a
command. ``key_id`` is publishable (the browser checkout needs it); ``key_secret``
is used only as HTTP basic auth here and must not leave this module.

No Razorpay SDK is used. ``razorpay==2.0.1`` is in ``requirements-dev.txt`` only,
so it is not present in the Lambda runtime, and the Orders API is one POST -
bundling a dependency to make it would be the larger risk.

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

# wecare/razorpay/api, NOT wecare/razorpay-webhook. See the note above.
RAZORPAY_SECRET_ID = os.environ.get("RAZORPAY_SECRET_ID", "wecare/razorpay/api")
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
