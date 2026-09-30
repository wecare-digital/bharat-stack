"""Structured addresses: derived one-line form, and 'same as billing' that cannot alias.

What these tests defend
-----------------------
The two properties that make a structured address worth more than the flat string it replaces:
`fullAddress` is DERIVED so it can never disagree with the components, and a "shipping same as
billing" decision returns a by-VALUE copy so editing one address later cannot mutate the other.
Plus: manual entry with no autocomplete metadata is a first-class valid address, and the minimum
viable set (line1 + city + postal code) is enforced without a brittle per-country postal regex.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))

from lambda_utils.identity import address as addr  # noqa: E402


BILLING = {
    "addressLine1": "12 MG Road",
    "addressLine2": "Flat 3B",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postalCode": "560001",
}


# ── normalisation and the derived one-line form ─────────────────────────────────

def test_normalize_defaults_country_and_derives_full_address():
    out = addr.normalize_address(BILLING)
    assert out["country"] == "India"
    assert out["countryCode"] == "IN"
    # fullAddress is derived from the components, in reading order, with empty parts dropped.
    assert out["fullAddress"] == \
        "12 MG Road, Flat 3B, Bengaluru, Karnataka, 560001, India"


def test_full_address_is_recomputed_not_trusted_from_input():
    # A caller passing a stale/ wrong fullAddress must not win: it is derived, always.
    tampered = dict(BILLING, fullAddress="somewhere else entirely")
    out = addr.normalize_address(tampered)
    assert "somewhere else entirely" not in out["fullAddress"]
    assert out["fullAddress"].startswith("12 MG Road")


def test_whitespace_is_collapsed_and_case_preserved():
    out = addr.normalize_address(dict(BILLING, addressLine1="  12   MG   Road ",
                                      city="Bengaluru"))
    assert out["addressLine1"] == "12 MG Road"
    assert out["city"] == "Bengaluru"  # case preserved


# ── the minimum viable set ──────────────────────────────────────────────────────

@pytest.mark.parametrize("missing", ["addressLine1", "city", "postalCode"])
def test_missing_required_field_is_rejected(missing):
    payload = dict(BILLING)
    payload[missing] = ""
    with pytest.raises(addr.InvalidAddress):
        addr.normalize_address(payload)


def test_a_manual_address_with_no_autocomplete_metadata_is_valid():
    out = addr.normalize_address(BILLING)
    # No googlePlaceId / lat / lng required — manual entry is first-class.
    assert "googlePlaceId" not in out
    assert out["addressLine1"] == "12 MG Road"


def test_autocomplete_metadata_is_carried_through_when_present():
    out = addr.normalize_address(dict(BILLING, googlePlaceId="ChIJabc",
                                      latitude=12.97, longitude=77.59))
    assert out["googlePlaceId"] == "ChIJabc"
    assert out["latitude"] == 12.97
    assert out["longitude"] == 77.59


def test_a_non_india_country_is_accepted():
    out = addr.normalize_address(dict(BILLING, country="Nepal", countryCode="np"))
    assert out["country"] == "Nepal"
    assert out["countryCode"] == "NP"  # upper-cased


# ── same-as-billing must not alias ──────────────────────────────────────────────

def test_shipping_same_as_billing_returns_a_by_value_copy():
    billing = addr.normalize_address(BILLING)
    shipping = addr.resolve_shipping(billing=billing, shipping_differs=False)
    assert shipping == billing
    # Mutating the returned shipping copy must NOT change billing.
    shipping["city"] = "Mumbai"
    assert billing["city"] == "Bengaluru"


def test_shipping_differs_validates_the_supplied_address():
    ship = {"addressLine1": "9 Residency Rd", "city": "Bengaluru", "postalCode": "560025"}
    out = addr.resolve_shipping(billing=BILLING, shipping_differs=True, shipping=ship)
    assert out["addressLine1"] == "9 Residency Rd"
    assert out["fullAddress"].startswith("9 Residency Rd")


def test_shipping_differs_with_no_address_is_an_error():
    with pytest.raises(addr.InvalidAddress):
        addr.resolve_shipping(billing=BILLING, shipping_differs=True, shipping=None)


# ── build_addresses composes both plus the decision ─────────────────────────────

def test_build_addresses_not_differing_yields_equal_but_independent_records():
    both = addr.build_addresses(billing=BILLING, shipping_differs=False)
    assert both["shippingDiffers"] is False
    assert both["billing"] == both["shipping"]
    both["shipping"]["postalCode"] = "999999"
    assert both["billing"]["postalCode"] == "560001"


def test_build_addresses_differing_keeps_them_distinct():
    ship = {"addressLine1": "9 Residency Rd", "city": "Bengaluru", "postalCode": "560025"}
    both = addr.build_addresses(billing=BILLING, shipping_differs=True, shipping=ship)
    assert both["shippingDiffers"] is True
    assert both["billing"]["postalCode"] == "560001"
    assert both["shipping"]["postalCode"] == "560025"
