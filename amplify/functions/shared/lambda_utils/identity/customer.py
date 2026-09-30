"""Customer identity: immutable id, mutable contacts, and the normalisation that guards both.

The rule
--------
**Customer identity is immutable. Phone and email are attributes.** A phone number can be
ported, recycled by a carrier, or simply mistyped and corrected; an email address changes with
a job. Keying a customer on either means that when one changes you either lose the order
history or silently merge two people. So identity is `CUS_<ULID>` and nothing else, and the
phone and email hang off it as verifiable, replaceable fields.

Normalisation is part of the identity contract, not a formatting convenience: uniqueness is
enforced on the *normalised* value, so two spellings of one phone number must collapse to one
string before any conditional write happens. Getting that wrong in either direction is a real
failure - too aggressive and two people share an account, too lax and one person gets two.

Why email normalisation stops at trim and lowercase
---------------------------------------------------
It is tempting to strip dots and `+tags`, because Gmail ignores them. Two reasons not to:

1. **It is only true at Gmail.** The local part is owned by the receiving server, and RFC 5321
   says it may be case sensitive and may treat dots as significant. `a.b@fastmail.com` and
   `ab@fastmail.com` can be different people. Applying Gmail's rules universally merges
   accounts that are not the same account.
2. **It changes what the customer typed.** The address is a delivery target as well as a key,
   and a receipt must go to the address they gave.

Lowercasing the *domain* is unambiguously safe (DNS is case-insensitive). Lowercasing the local
part is technically a mutation, but every provider in practice treats it as insensitive, and not
doing it lets one person register twice by holding shift. That trade is taken deliberately and
is recorded here so it is not re-litigated by accident.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from lambda_utils.identifiers import ULID_LENGTH, is_ulid, new_ulid

#: Prefixed so an identifier is self-describing in a log line, a URL or a support ticket.
#: `CUS_` plus 26 ULID symbols is 30 characters.
CUSTOMER_ID_PREFIX = "CUS_"
CUSTOMER_ID_LENGTH = len(CUSTOMER_ID_PREFIX) + ULID_LENGTH

#: India is the only market, and the only country code this business sends to.
DEFAULT_COUNTRY_CODE = "91"

#: Indian mobile numbers are ten digits beginning 6-9. Landlines and short codes are not
#: reachable on WhatsApp, so they are refused rather than silently prefixed.
_INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")

#: Deliberately permissive on the local part and strict on the shape. Full RFC 5322 validation
#: is famously not a regex, and a stricter pattern here rejects real addresses; the actual
#: proof that an address exists is the verification code we send to it.
_EMAIL_RE = re.compile(r"^[^@\s]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
                       r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$")

#: Long enough for a real name in any script, short enough to refuse a pasted essay.
MAX_NAME_LENGTH = 100


class InvalidPhoneNumber(ValueError):
    """The supplied value is not a phone number this business can reach on WhatsApp."""


class InvalidEmailAddress(ValueError):
    """The supplied value is not a usable email address."""


class InvalidName(ValueError):
    """The supplied name is empty or implausible."""


# ── identity ───────────────────────────────────────────────────────────────────

def new_customer_id() -> str:
    """Mint a fresh immutable customer id.

    ULID rather than UUIDv4 so ids sort by creation time, which makes "customers created today"
    a range read instead of a scan. The creation time being visible is acceptable for an
    internal identifier and is why this must not be used as a public order number.
    """
    return CUSTOMER_ID_PREFIX + new_ulid()


def is_customer_id(value: Any) -> bool:
    """True for a syntactically valid `CUS_<ULID>`."""
    if not isinstance(value, str) or len(value) != CUSTOMER_ID_LENGTH:
        return False
    if not value.startswith(CUSTOMER_ID_PREFIX):
        return False
    return is_ulid(value[len(CUSTOMER_ID_PREFIX):])


def assert_customer_id(value: Any) -> str:
    """Return `value` if it is a customer id, else raise.

    Used at trust boundaries. A customer id arriving from a browser must be checked for shape
    before it is used to build a key - but note that shape is not authorisation: the id must
    also match the caller's session, which is a separate check that belongs in the handler.
    """
    if not is_customer_id(value):
        raise ValueError(
            f"not a customer id: expected {CUSTOMER_ID_PREFIX}<26-char ULID>, got {value!r}"
        )
    return value


# ── phone ──────────────────────────────────────────────────────────────────────

def normalize_phone(raw: Any, *, default_country: str = DEFAULT_COUNTRY_CODE) -> str:
    """Return a phone number in E.164 (`+<digits>`), or raise `InvalidPhoneNumber`.

    Uniqueness is enforced on this value, so it must be reached identically from every spelling
    a customer might type: `93309 94400`, `+91 93309-94400`, `0093309...`, `09330994400`.

    The leading-zero and `00` cases matter more than they look. In India a mobile is often
    written with a trunk `0`, and `00` is the international prefix; treated as significant
    digits both produce a number that is not the customer's and that no conditional write would
    ever collide with, so the same person could register twice.
    """
    text = str(raw or "").strip()
    if not text:
        raise InvalidPhoneNumber("phone number is required")

    digits = re.sub(r"\D", "", text)
    if not digits:
        raise InvalidPhoneNumber("phone number contains no digits")

    # `00` international prefix, then a national trunk `0`. Order matters: strip the
    # international prefix first, or `0091...` loses the wrong zero.
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits.lstrip("0")

    if _INDIAN_MOBILE_RE.match(digits):
        digits = default_country + digits

    # Already country-prefixed Indian mobile.
    if digits.startswith(default_country) and _INDIAN_MOBILE_RE.match(digits[len(default_country):]):
        return "+" + digits

    # Any other country: accept a plausible E.164 length and let the provider judge it. The
    # business only sends to India today, so this path exists to avoid rejecting a customer
    # outright rather than to claim support.
    if 10 <= len(digits) <= 15:
        return "+" + digits

    raise InvalidPhoneNumber(
        f"not a reachable phone number: {len(digits)} digits after normalisation"
    )


def is_indian_mobile(e164: Any) -> bool:
    """True when `e164` is an Indian mobile, so India DLT and India RCS rules apply."""
    text = str(e164 or "")
    if not text.startswith("+" + DEFAULT_COUNTRY_CODE):
        return False
    return bool(_INDIAN_MOBILE_RE.match(text[1 + len(DEFAULT_COUNTRY_CODE):]))


# ── email ──────────────────────────────────────────────────────────────────────

def normalize_email(raw: Any) -> str:
    """Return the address trimmed and lowercased, or raise `InvalidEmailAddress`.

    Trim and lowercase, and nothing else. Dots are NOT stripped and `+tags` are NOT stripped -
    see the module docstring for why: those are Gmail's rules, not the internet's, and applying
    them merges accounts that may belong to different people.
    """
    text = str(raw or "").strip()
    if not text:
        raise InvalidEmailAddress("email address is required")
    if len(text) > 254:  # RFC 5321 maximum forward-path length
        raise InvalidEmailAddress("email address is too long")

    lowered = text.lower()
    if not _EMAIL_RE.match(lowered):
        raise InvalidEmailAddress("not a usable email address")
    return lowered


def email_domain(normalized: str) -> str:
    """The domain part of an already-normalised address."""
    return normalized.rsplit("@", 1)[-1]


# ── name ───────────────────────────────────────────────────────────────────────

def normalize_name(raw: Any, *, field: str = "name") -> str:
    """Collapse whitespace and trim, preserving case and script.

    Case is preserved on purpose. Title-casing breaks `McDonald`, `van der Berg` and every
    name outside the Latin script, and a name is displayed back to its owner - getting it wrong
    is the first thing they will notice.
    """
    text = str(raw or "")
    collapsed = " ".join(text.split())
    if not collapsed:
        raise InvalidName(f"{field} is required")
    if len(collapsed) > MAX_NAME_LENGTH:
        raise InvalidName(f"{field} must be at most {MAX_NAME_LENGTH} characters")
    return collapsed


def full_name(first: str, last: str) -> str:
    """`fullName`, derived rather than stored separately.

    Derived so it cannot drift from its parts. Storing all three lets an update to `firstName`
    leave a stale `fullName` on the receipt.
    """
    return " ".join(part for part in (first.strip(), last.strip()) if part)


# ── the record ─────────────────────────────────────────────────────────────────

def build_customer(*, first_name: str, last_name: str, phone: Any, email: Any,
                   customer_id: Optional[str] = None,
                   now: Optional[int] = None) -> Dict[str, Any]:
    """Build a customer record with everything normalised and nothing verified.

    `phoneVerifiedAt` and `emailVerifiedAt` are deliberately absent rather than `None`. Absence
    of the attribute is what lets a conditional write assert `attribute_not_exists` to mark a
    channel verified exactly once, and it keeps "never verified" distinguishable from "verified
    at an unknown time" - which a `None` would not.
    """
    import time

    first = normalize_name(first_name, field="firstName")
    last = normalize_name(last_name, field="lastName")
    normalized_phone = normalize_phone(phone)
    normalized_email = normalize_email(email)
    timestamp = int(time.time()) if now is None else int(now)

    return {
        "customerId": customer_id or new_customer_id(),
        "firstName": first,
        "lastName": last,
        "fullName": full_name(first, last),
        # Both kept: the normalised value is the key, the raw value is what the customer typed
        # and what a human should see when correcting a mistake.
        "phone": normalized_phone,
        "normalizedPhone": normalized_phone,
        "email": normalized_email,
        "normalizedEmail": normalized_email,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }


def verification_state(customer: Dict[str, Any]) -> Tuple[bool, bool]:
    """`(phone_verified, email_verified)` for a customer record."""
    return (
        bool(customer.get("phoneVerifiedAt")),
        bool(customer.get("emailVerifiedAt")),
    )


def is_checkout_ready(customer: Dict[str, Any]) -> bool:
    """True when this customer may proceed to a payment attempt.

    Both channels must be verified. The phone because the payment request is delivered there
    and an unverified number would send a payable message to whoever actually owns it; the
    email because it is the only channel that survives a WhatsApp number changing.
    """
    phone_ok, email_ok = verification_state(customer)
    return bool(
        phone_ok and email_ok
        and customer.get("firstName") and customer.get("lastName")
        and is_customer_id(customer.get("customerId"))
    )


__all__ = [
    "CUSTOMER_ID_PREFIX",
    "CUSTOMER_ID_LENGTH",
    "DEFAULT_COUNTRY_CODE",
    "MAX_NAME_LENGTH",
    "InvalidPhoneNumber",
    "InvalidEmailAddress",
    "InvalidName",
    "new_customer_id",
    "is_customer_id",
    "assert_customer_id",
    "normalize_phone",
    "is_indian_mobile",
    "normalize_email",
    "email_domain",
    "normalize_name",
    "full_name",
    "build_customer",
    "verification_state",
    "is_checkout_ready",
]
