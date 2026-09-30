"""Short-lived receipt links, because a receipt is not a public document.

The exposure this addresses
--------------------------
**Closed 2026-09-30.** `payments/invoice-engine` used to write receipts under
`media_paths.public('stack/invoices/')` and hand back `https://{CDN_DOMAIN}/{s3_key}`. That prefix
is served by CloudFront **without authentication**, so every receipt ever generated was fetchable
forever by anyone holding its URL. It now writes under `media_paths.secure(...)` and returns a
presigned URL from `signed_url` below; `inbound-whatsapp-handler`, `system-cleanup` and the
dashboard's cleanup-prefix mirror moved in the same change, because two writers and a sweeper that
disagree about the root are worse than one that is wrong consistently.

The description below is kept in the past tense rather than deleted: it is the reasoning that
decided the urgency, and it is what makes the ordering defensible — the move happened while
`o/stack/invoices/` held **0 objects** and `InvoicesTable` held **0 rows**, so there was nothing
to migrate and no already-sent URL to strand.

The exposure is bounded rather than absent, and the bound is worth stating precisely because it
decides how urgent this is. The key is `wecare-digital-{reference_id}.{png,pdf}`, and a reference
is 14 CSPRNG symbols over a 32-symbol alphabet — 70 bits, not guessable. Bucket listing is off.
So the correct mental model is **unlisted-but-public**: safe from enumeration, unsafe the moment a
URL leaks, and a receipt carries a name, an address, a GSTIN and a purchase history.

Why this module rather than a change to invoice-engine
-----------------------------------------------------
Repointing live invoice storage is a bigger change than it appears. `send_invoice_whatsapp` passes
`mediaFile: s3_key` and lets the sender fetch from S3, so WhatsApp delivery does **not** depend on
the public URL — but the admin surface and the delivery log both read `imageUrl`, and swapping those
for expiring URLs breaks anything that cached one. That is a migration with its own blast radius,
not a side effect of adding order creation.

So this provides the correct primitive, the new order-confirmation path uses it from the start, and
the existing public URLs remain a **recorded** gap rather than a silent one. `media_paths` already
composes every key through `public()` / `secure()`, so moving the prefix later is a prefix change
plus an IAM change — not a rewrite.

Why an order number is not an authorisation
-------------------------------------------
The obvious shortcut is `/receipts/<orderNumber>`. It is wrong twice over: the number is printed on
the receipt and read aloud to support, so it is not a secret, and 12 characters over a 30-symbol
alphabet is guessable at scale if it is the only thing standing between a stranger and a customer's
address. A link must be either signed or gated behind a proven session — never derived from an
identifier the customer is encouraged to share.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Long enough for a customer to tap a link in WhatsApp minutes or hours later, short enough that a
#: forwarded message does not become a permanent grant. Receipts are re-issuable on demand through
#: an authenticated route, so a short life costs nothing but a click.
DEFAULT_TTL_SECONDS = int(os.environ.get("RECEIPT_LINK_TTL_SECONDS", str(24 * 60 * 60)))

#: A hard ceiling, checked rather than trusted. A caller passing a week would otherwise quietly
#: recreate the permanent-URL problem one presign at a time.
MAX_TTL_SECONDS = 7 * 24 * 60 * 60


class ReceiptLinkUnavailable(RuntimeError):
    """A signed link could not be produced.

    Raised rather than returning a public fallback URL. A receipt that cannot be delivered
    securely is a support ticket; one delivered over a permanent public URL is a disclosure, and
    the second is worse.
    """


def signed_url(s3_client: Any, *, bucket: str, key: str,
               filename: str = "",
               ttl_seconds: Optional[int] = None) -> str:
    """A presigned GET for a receipt object, valid for `ttl_seconds`.

    `s3_client` is injected so this module builds no AWS client and is testable without
    credentials.

    `filename`, when given, sets `Content-Disposition` so the download has a readable name rather
    than a content hash. It is part of the signature, so it cannot be tampered with in transit.
    """
    if not bucket or not key:
        raise ValueError("bucket and key are required")

    ttl = DEFAULT_TTL_SECONDS if ttl_seconds is None else int(ttl_seconds)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be positive")
    if ttl > MAX_TTL_SECONDS:
        # Refused, not clamped. Clamping hides the caller's intent; the caller asked for
        # something that defeats the purpose of signing and should be told.
        raise ValueError(
            f"ttl_seconds {ttl} exceeds the {MAX_TTL_SECONDS}s ceiling; a link that outlives a "
            "forwarded message is effectively permanent"
        )

    params = {"Bucket": bucket, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    try:
        url = s3_client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=ttl)
    except Exception as error:  # noqa: BLE001
        raise ReceiptLinkUnavailable(
            f"could not sign a receipt link: {type(error).__name__}"
        ) from error

    # Metadata only. The URL itself carries a grant, so it never reaches a log.
    logger.info('{"event":"receipt_link_signed","ttlSeconds":%d}', ttl)
    return url


def is_permanent_public_url(url: Any) -> bool:
    """True when `url` looks like an unsigned CDN link rather than a signed one.

    Used by tests and by the confirmation builder as a last line of defence: the whole point is
    that a receipt link expires, and the failure mode of getting this wrong is silent — a
    permanent URL works perfectly, forever, for everyone.

    Detects the absence of a signature rather than the presence of a domain, so it stays correct
    if the CDN host changes.
    """
    if not isinstance(url, str) or not url:
        return False
    if not url.startswith("http"):
        return False
    signed_markers = ("X-Amz-Signature=", "X-Amz-Credential=", "Signature=", "Expires=")
    return not any(marker in url for marker in signed_markers)


def assert_not_permanent(url: str) -> str:
    """Return `url` if it expires, else raise.

    Called on the way into a customer-facing message. A receipt link is the one artifact where a
    mistake is both invisible and permanent, so it is worth one comparison at the boundary.
    """
    if is_permanent_public_url(url):
        raise ReceiptLinkUnavailable(
            "refusing to send an unsigned receipt URL: it would grant access to a document "
            "carrying a name, an address and a GSTIN, to anyone the link is forwarded to, forever"
        )
    return url


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "MAX_TTL_SECONDS",
    "ReceiptLinkUnavailable",
    "signed_url",
    "is_permanent_public_url",
    "assert_not_permanent",
]
