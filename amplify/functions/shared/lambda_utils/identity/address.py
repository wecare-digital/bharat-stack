"""Structured postal addresses, with billing and shipping as distinct records.

Why a structured entity rather than one free-form string
--------------------------------------------------------
Contacts and orders in this repo carry `shippingAddress`/`billingAddress` as flat strings
(see `validation.py`, `google_people.py`). A string is enough to print on a label and useless
for everything else: a payment request needs the postal code and country as separate fields, a
tax calculation needs the state, and an address correction needs to touch one line, not reparse
prose. So this module holds the components, and derives the one-line form from them rather than
the other way round.

The field set is the prompt's §10, and the component names match what `identity.google_people`
already emits (`addressLine1`, `city`, `state`, `postalCode`, `country`) so a Places/People
autocomplete result feeds straight in. `fullAddress` is derived, never the source of truth —
storing both and letting them drift is how a receipt ends up disagreeing with a shipping label.

Billing and shipping are two records, and "same as billing" is a decision, not a copy
-------------------------------------------------------------------------------------
`resolve_shipping` takes billing, a `shipping_differs` flag, and an optional shipping address,
and returns the shipping address to use. When they do not differ it returns the billing address
**by value** (a fresh dict), so a later edit to one cannot silently mutate the other through a
shared reference — the single most common bug in "same as billing" checkboxes. When they do
differ, the supplied shipping address is validated in its own right.

Manual entry always works
--------------------------
Nothing here requires a Google Place id, a lat/lng, or a verification state. Those may be
attached when an autocomplete provided them (`googlePlaceId`, `latitude`, `longitude`), but they
are optional metadata — a hand-typed address with none of them is a first-class, valid address.
Autocomplete is a convenience, never a gate.

India-first, not India-only
----------------------------
`country` defaults to India and `countryCode` to `IN`, because that is the only market today, but
a caller may pass another country and it is accepted. The postal-code check is loose on purpose:
a strict per-country regex rejects real addresses at the exact moment a customer is trying to pay,
and the delivery attempt is the real validation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

#: The market default. Matches `identity.customer.DEFAULT_COUNTRY_CODE` semantics.
DEFAULT_COUNTRY = "India"
DEFAULT_COUNTRY_CODE = "IN"

#: Long enough for a real line in any script, short enough to refuse a pasted document.
MAX_LINE_LENGTH = 200
MAX_FIELD_LENGTH = 100

#: The two roles an address can play on a customer/order.
BILLING = "billing"
SHIPPING = "shipping"

#: Structured components a caller may supply. `addressLine1` and `city` and `postalCode` are the
#: minimum that makes an address usable; the rest refine it.
_STRING_FIELDS = (
    "addressLine1", "addressLine2", "locality", "city", "state",
    "postalCode", "country", "countryCode",
)

#: Optional autocomplete metadata. Present only when a Places/People result supplied it; never
#: required, never a gate on manual entry.
_METADATA_FIELDS = ("googlePlaceId", "latitude", "longitude")


class InvalidAddress(ValueError):
    """The supplied value is not a usable postal address."""


def _clean(value: Any, *, limit: int) -> str:
    """Collapse whitespace, trim, and bound the length. Preserves case and script."""
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        raise InvalidAddress(f"a field exceeds {limit} characters")
    return text


def normalize_address(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Return a cleaned structured address, or raise `InvalidAddress`.

    The minimum for a usable address is `addressLine1`, `city` and `postalCode`. Everything else
    is optional. `fullAddress` is (re)derived here so it can never disagree with the components,
    even if a caller passed one in.
    """
    if not isinstance(raw, dict):
        raise InvalidAddress("address must be an object")

    out: Dict[str, Any] = {}
    for field in _STRING_FIELDS:
        limit = MAX_LINE_LENGTH if field.startswith("addressLine") else MAX_FIELD_LENGTH
        out[field] = _clean(raw.get(field), limit=limit)

    if not out["country"]:
        out["country"] = DEFAULT_COUNTRY
    if not out["countryCode"]:
        out["countryCode"] = DEFAULT_COUNTRY_CODE
    out["countryCode"] = out["countryCode"].upper()[:2] or DEFAULT_COUNTRY_CODE

    # The minimum viable set. Deliberately not a per-country regex on the postal code: a strict
    # pattern refuses real addresses mid-checkout, and the delivery attempt is the real proof.
    if not out["addressLine1"]:
        raise InvalidAddress("addressLine1 is required")
    if not out["city"]:
        raise InvalidAddress("city is required")
    if not out["postalCode"]:
        raise InvalidAddress("postalCode is required")

    # Optional autocomplete metadata, carried through only when present.
    for field in _METADATA_FIELDS:
        if raw.get(field) not in (None, ""):
            out[field] = raw[field]

    out["fullAddress"] = full_address(out)
    return out


def full_address(components: Dict[str, Any]) -> str:
    """The one-line rendering, derived from the components.

    Order and separators chosen so the line reads naturally and drops empty parts rather than
    leaving `, ,` gaps. Never stored as the source of truth — `normalize_address` recomputes it.
    """
    ordered = [
        components.get("addressLine1"),
        components.get("addressLine2"),
        components.get("locality"),
        components.get("city"),
        components.get("state"),
        components.get("postalCode"),
        components.get("country"),
    ]
    return ", ".join(part for part in (str(p or "").strip() for p in ordered) if part)


def resolve_shipping(*, billing: Dict[str, Any], shipping_differs: bool,
                     shipping: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The shipping address to use, given the billing address and the "differs" decision.

    When shipping does NOT differ, returns a by-value copy of the (normalised) billing address,
    so a later edit to one cannot mutate the other through a shared reference. When it DOES
    differ, validates the supplied shipping address in its own right.

    Raises `InvalidAddress` if `shipping_differs` is true but no shipping address was supplied —
    a checkbox ticked with an empty form is a mistake to catch, not a billing address to silently
    reuse.
    """
    billing_norm = normalize_address(billing)
    if not shipping_differs:
        return dict(billing_norm)  # by value, never the same object
    if not shipping:
        raise InvalidAddress(
            "shipping_differs is set but no shipping address was supplied")
    return normalize_address(shipping)


def build_addresses(*, billing: Dict[str, Any], shipping_differs: bool = False,
                    shipping: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Both addresses plus the decision, ready to persist against a customer or an order.

    Returns `{"billing": {...}, "shipping": {...}, "shippingDiffers": bool}`. The `shipping`
    entry is always a full valid address — equal to billing by value when they do not differ —
    so downstream code never has to special-case a missing shipping address.
    """
    billing_norm = normalize_address(billing)
    shipping_norm = resolve_shipping(
        billing=billing_norm, shipping_differs=shipping_differs, shipping=shipping)
    return {
        BILLING: billing_norm,
        SHIPPING: shipping_norm,
        "shippingDiffers": bool(shipping_differs),
    }


__all__ = [
    "DEFAULT_COUNTRY",
    "DEFAULT_COUNTRY_CODE",
    "MAX_LINE_LENGTH",
    "MAX_FIELD_LENGTH",
    "BILLING",
    "SHIPPING",
    "InvalidAddress",
    "normalize_address",
    "full_address",
    "resolve_shipping",
    "build_addresses",
]
