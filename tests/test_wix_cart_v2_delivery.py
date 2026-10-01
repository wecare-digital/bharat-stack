"""Cart V2 delivery: the address is required for the number to be RIGHT, not merely present.

Why these tests exist in this shape
-----------------------------------
The existing V2 suite's strongest routing assertion compares a list of `(method, path)` tuples.
That proves the adapter calls the endpoints it means to and nothing about whether the result is
safe to charge. These tests are driven by behaviour instead: an unpriceable cart yields no quote
and tells the customer what to fix, a priced cart's total reconciles in integer paise, and a
fabricated address never becomes a price.

The two fixtures are the whole argument
---------------------------------------
`wix_cart_v2_live_demo.json` is a REAL, redacted Calculate Cart response from the confirmed site
on 2026-10-01. It carries two `ERROR`-severity violations, `MISSING_DELIVERY_ADDRESS` and
`MISSING_DELIVERY_METHOD`, and it is never mutated here. `wix_cart_v2_delivery_complete.json` is
the same cart with a real West Bengal address and a chosen delivery method, derived from it so
the price arithmetic cannot drift: subtotal 24999.00 + delivery 500.00 = total 25499.00.

That delivery component is the point. It is money that does not exist until a method is chosen,
which is why a quote taken before then is not merely unvalidated but *short*. And in India the
address is the place of supply, deciding CGST+SGST versus IGST against seller GSTIN
19AAFFW7196L1Z8 -- so a placeholder address produces a plausible total with the wrong tax split,
on a real invoice, and that total gets charged. An honest refusal is the cheaper failure, and
`test_no_placeholder_address_can_ever_produce_a_price` is the assertion that keeps it so.

Provider references
-------------------
Method and field mapping, including Set Delivery Method / Remove Delivery Method being new in V2
with no V1 equivalent, and `shippingInfo.shippingDestination.address` -> `deliveryInfo.address`:
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-mapping
Totals not being stored on the entity, and V2 failing explicitly where V1 adjusted silently:
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-guide
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from lambda_utils.ecommerce.cart_v2 import (  # noqa: E402
    ADDRESS_FIELDS, CartContractError, CartV2, delivery_address, is_enabled,
)
from lambda_utils.ecommerce.money import Money  # noqa: E402
from lambda_utils.ecommerce.wix_address import (  # noqa: E402
    UnmappableAddress, gst_state_code, india_subdivision, to_wix_address,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
LIVE = FIXTURES / "wix_cart_v2_live_demo.json"
COMPLETE = FIXTURES / "wix_cart_v2_delivery_complete.json"

#: A real owned address in this application's own shape, as `identity.address` produces it.
OWNED = {
    "addressLine1": "12 Dalhousie Square",
    "city": "Kolkata",
    "state": "West Bengal",
    "postalCode": "700001",
}


def live():
    return json.loads(LIVE.read_text())


def delivery_complete():
    """The live cart WITH a real delivery address and method. Never mutates the live fixture."""
    return json.loads(COMPLETE.read_text())


class Wix:
    """Records every call and replays one response. A write is a recorded call, never real."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, path, method="GET", body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        return copy.deepcopy(self.response)

    def paths(self, cart_id):
        return [(m, p.replace(cart_id, "{id}")) for m, p, _ in self.calls]


# ── the live cart cannot be priced, and says why ─────────────────────────────────

def test_the_unmodified_live_cart_yields_no_quote():
    """`calculate` refuses, and that refusal is the contract working rather than a defect.

    Checkout V1 returned a total in this exact situation only because it validated nothing.
    """
    response = live()
    with pytest.raises(CartContractError):
        CartV2(Wix(response)).calculate(response["cart"]["id"])


def test_preview_lets_the_customer_see_what_to_fix_without_offering_a_price():
    """The pre-address state: item subtotals only, delivery and tax pending.

    This is the honest answer to "what do we show before an address is chosen?". It must be
    impossible to mistake for a payable amount, so it reports `payable: False`, names the money
    `itemSubtotalPaise` rather than a total, and carries none of the fields that could reach a
    gateway.
    """
    response = live()
    preview = CartV2(Wix(response)).preview(response["cart"]["id"])

    assert preview["payable"] is False
    assert preview["itemSubtotalPaise"] == 2499900
    assert {v["code"] for v in preview["blockingViolations"]} == {
        "MISSING_DELIVERY_ADDRESS", "MISSING_DELIVERY_METHOD"}
    for forbidden in ("amountPaise", "calculationId", "priceVerificationToken", "total"):
        assert forbidden not in preview, f"preview must not carry {forbidden}"
    assert "priceVerificationToken" not in json.dumps(preview)


def test_preview_reports_no_blocking_violations_once_delivery_is_set():
    """The same reader, on the same cart with delivery supplied, has nothing left to resolve."""
    response = delivery_complete()
    preview = CartV2(Wix(response)).preview(response["cart"]["id"])
    assert preview["blockingViolations"] == []
    # Still never payable. `preview` is a diagnostic; `calculate` is the only quote.
    assert preview["payable"] is False


# ── with a real address and method, the quote is produced and reconciles ──────────

def test_a_delivery_complete_cart_produces_a_payable_quote():
    response = delivery_complete()
    wix = Wix(response)
    snapshot = CartV2(wix).calculate(response["cart"]["id"])

    assert snapshot["amountPaise"] == 2549900
    assert snapshot["currency"] == "INR"
    assert snapshot["cartRevision"] == "4"
    assert snapshot["calculationId"] == response["summary"]["calculationId"]


def test_the_quote_total_is_the_integer_paise_sum_of_its_components():
    """Reconciled as integers, not compared with a tolerance.

    The payment path fails closed on a one-paise mismatch, so a component breakdown that does not
    add up must never become an amount. No float appears anywhere in this arithmetic.
    """
    response = delivery_complete()
    snapshot = CartV2(Wix(response)).calculate(response["cart"]["id"])
    parts = snapshot["componentsPaise"]

    assert all(type(value) is int for value in parts.values())
    assert (parts["subtotal"] - parts["discount"] + parts["delivery"]
            + parts["additionalFees"] + parts["tax"]) == parts["total"]
    assert parts["total"] == snapshot["amountPaise"]


def test_delivery_is_real_money_in_the_total_and_not_a_rounding_artefact():
    """The reason the address is load-bearing rather than a formality.

    Without a delivery method there is no delivery charge, so a quote taken before one is chosen
    is not just unvalidated -- it is missing 500.00 of what the customer owes.
    """
    response = delivery_complete()
    snapshot = CartV2(Wix(response)).calculate(response["cart"]["id"])

    assert snapshot["componentsPaise"]["delivery"] == 50000
    assert snapshot["amountPaise"] - snapshot["componentsPaise"]["subtotal"] == 50000
    # And the pre-delivery subtotal is exactly what `preview` was willing to show.
    assert CartV2(Wix(live())).preview(live()["cart"]["id"])["itemSubtotalPaise"] == \
        snapshot["componentsPaise"]["subtotal"]


def test_the_quote_freezes_the_address_and_method_that_produced_it():
    """Both travel with the amount, because they are part of why it is that amount.

    A quote reused against a different destination would be a different tax treatment and a
    different delivery charge under the same number.
    """
    response = delivery_complete()
    snapshot = CartV2(Wix(response)).calculate(response["cart"]["id"])

    assert snapshot["deliveryAddress"]["subdivision"] == "IN-WB"
    assert snapshot["deliveryAddress"]["country"] == "IN"
    assert snapshot["deliveryMethod"]["id"]


def test_a_revision_change_between_calculate_and_the_summary_invalidates_the_quote():
    """The calculation must be bound to the cart it was taken against."""
    response = delivery_complete()
    response["summary"]["cartRevision"] = "99"
    with pytest.raises(CartContractError):
        CartV2(Wix(response)).calculate(response["cart"]["id"])


# ── the adapter calls, and what it still cannot do ───────────────────────────────

def test_the_delivery_methods_route_to_their_documented_endpoints():
    response = delivery_complete()
    wix = Wix(response)
    adapter = CartV2(wix)
    cart_id = response["cart"]["id"]

    adapter.set_delivery_address(cart_id, to_wix_address(OWNED))
    adapter.set_delivery_method(cart_id, "11111111-2222-3333-4444-555555555555")
    adapter.remove_delivery_method(cart_id)
    adapter.refresh(cart_id)

    assert wix.paths(cart_id) == [
        ("PATCH", "/ecom/v2/carts/{id}"),
        ("POST", "/ecom/v2/carts/{id}/set-delivery-method"),
        ("POST", "/ecom/v2/carts/{id}/remove-delivery-method"),
        ("POST", "/ecom/v2/carts/{id}/refresh"),
    ]


def test_setting_an_address_sends_only_the_address():
    """Never a currency, a price or a line item on the way past.

    Update Cart can write most of the entity. This call writes one field, so it cannot become a
    way to change what the cart costs.
    """
    response = delivery_complete()
    wix = Wix(response)
    CartV2(wix).set_delivery_address(response["cart"]["id"], to_wix_address(OWNED))

    body = wix.calls[0][2]
    assert set(body) == {"cart"}
    assert set(body["cart"]) == {"deliveryInfo"}
    assert set(body["cart"]["deliveryInfo"]) == {"address"}


def test_no_delivery_method_call_can_carry_a_price():
    """The option is an identifier; the charge is whatever Wix then reports."""
    response = delivery_complete()
    wix = Wix(response)
    CartV2(wix).set_delivery_method(response["cart"]["id"], "opt-1")

    serialized = json.dumps(wix.calls[0][2])
    for word in ("amount", "price", "currency", "paise", "total"):
        assert word not in serialized.lower()


def test_the_adapter_still_has_no_way_to_place_an_order_or_charge():
    """Enumerated as absent code, not as guarded code.

    Cart V2's Place Order replaces Checkout V1's Create Order and can enter Wix payment
    collection. Mark Cart As Completed lives in `wix_writeback` behind its own gates. Neither may
    appear on the adapter a customer-facing route holds, and "the method does not exist" is a
    stronger guarantee than "the method refuses".
    """
    for forbidden in ("place_order", "placeOrder", "mark_completed", "checkout_url",
                      "redirect_session", "create_order", "pay", "charge", "capture"):
        assert not hasattr(CartV2, forbidden), f"CartV2 must not expose {forbidden}"

    source = (ROOT / "amplify/functions/shared/lambda_utils/ecommerce/cart_v2.py").read_text()
    for marker in ("place-order", "mark-as-completed", "redirect-session", "/checkout"):
        in_code = [line for line in source.splitlines()
                   if marker in line and not line.strip().startswith("#")
                   and not line.strip().startswith('"')]
        assert not in_code, f"cart_v2 must not reference {marker} in code: {in_code[:2]}"


@pytest.mark.parametrize("bad", ["", "   ", None, 123, "x" * 201])
def test_a_delivery_method_id_is_validated_before_the_call(bad):
    wix = Wix(delivery_complete())

    def forbidden(*args, **kwargs):
        pytest.fail("invalid input reached the provider")

    with pytest.raises(ValueError):
        CartV2(forbidden).set_delivery_method(delivery_complete()["cart"]["id"], bad)
    assert not wix.calls


# ── the address bridge refuses rather than guesses ───────────────────────────────

def test_an_owned_address_maps_onto_the_wix_shape():
    mapped = to_wix_address(OWNED)
    assert mapped == {
        "country": "IN", "subdivision": "IN-WB", "city": "Kolkata",
        "postalCode": "700001", "addressLine": "12 Dalhousie Square",
    }
    assert set(mapped) <= set(ADDRESS_FIELDS)
    # And the result is one `delivery_address` accepts, so the bridge and the validator agree.
    assert delivery_address(mapped) == mapped


@pytest.mark.parametrize("name,iso,gst", [
    ("West Bengal", "IN-WB", "19"),
    ("west bengal", "IN-WB", "19"),
    ("  West   Bengal  ", "IN-WB", "19"),
    ("Maharashtra", "IN-MH", "27"),
    ("Karnataka", "IN-KA", "29"),
    ("Orissa", "IN-OR", "21"),
    ("Pondicherry", "IN-PY", "34"),
    ("Jammu & Kashmir", "IN-JK", "01"),
    ("NCT of Delhi", "IN-DL", "07"),
])
def test_indian_states_resolve_to_one_iso_and_one_gst_code(name, iso, gst):
    """Both codes from one table, so they cannot disagree about the same state."""
    assert india_subdivision(name) == (iso, gst)


@pytest.mark.parametrize("unknown", ["", None, "Atlantis", "WB", "Bengal", "Punjab Province"])
def test_an_unrecognised_state_refuses_instead_of_defaulting(unknown):
    """Silently dropping the subdivision would give Wix an address it would price with the wrong
    tax, and the error message says exactly that so the fix is to add the mapping."""
    with pytest.raises(UnmappableAddress) as caught:
        india_subdivision(unknown)
    assert "place of supply" in str(caught.value)


def test_a_non_india_address_needs_an_iso_subdivision_on_the_profile():
    """No table exists for other countries, and inventing one would repeat the India mistake."""
    with pytest.raises(UnmappableAddress):
        to_wix_address({**OWNED, "countryCode": "US", "state": "California"})
    assert to_wix_address({**OWNED, "countryCode": "US", "state": "US-CA"})["subdivision"] == \
        "US-CA"


def test_an_incomplete_owned_address_is_refused_before_it_reaches_wix():
    for missing in ("addressLine1", "city", "postalCode"):
        broken = {key: value for key, value in OWNED.items() if key != missing}
        with pytest.raises(UnmappableAddress):
            to_wix_address(broken)


def test_the_gst_state_code_is_resolved_for_the_fee_split_and_is_none_abroad():
    """`checkout_pricing` needs `intra_state` for the GST on OUR convenience fee, which is a
    different question from the supply tax Wix computes -- but the same place of supply."""
    assert gst_state_code(OWNED) == "19"
    assert gst_state_code({**OWNED, "countryCode": "US", "state": "US-CA"}) is None


# ── the validator at the Wix boundary ────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    {}, None, "12 Dalhousie Square", [],
    {"country": "IN"},                                  # no usable lines, but also:
    {"country": "in", "city": "Kolkata"},               # lowercase country
    {"country": "IND", "city": "Kolkata"},              # alpha-3
    {"country": "I1", "city": "Kolkata"},               # not alphabetic
    {"country": "IN", "city": ""},                      # empty field
    {"country": "IN", "amount": "1"},                   # not an address field
    {"country": "IN", "price": "1"},
    {"country": "IN", "currency": "USD"},
    {"country": "IN", "streetAddress": "a string"},     # Wix models this as an object
    {"country": "IN", "streetAddress": {"name": ""}},
])
def test_the_boundary_validator_refuses_anything_that_is_not_an_address(bad):
    with pytest.raises(ValueError):
        delivery_address(bad)


def test_no_placeholder_address_can_ever_produce_a_price():
    """The rule stated as a test, because it is the one that would be convenient to break.

    A fabricated address makes Calculate Cart answer 200 and yields a wrong CGST/SGST-versus-IGST
    split on an invoice carrying a real GSTIN -- and that total is what gets charged. So every
    route to an address must come from validated, owned data: there is no default country, no
    "unknown" subdivision, and an empty profile cannot be coerced into one.
    """
    for placeholder in ({}, {"state": "Unknown"}, {"state": "N/A", "city": "N/A"},
                        {"addressLine1": "-", "city": "-", "postalCode": "-"}):
        with pytest.raises(UnmappableAddress):
            to_wix_address(placeholder)


# ── the gate ─────────────────────────────────────────────────────────────────────

def test_cart_v2_is_on_by_default():
    """Inverted from an opt-in on 2026-10-01. Absence of configuration means V2 serves."""
    assert is_enabled({}) is True


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " true "])
def test_the_disable_key_turns_it_off(value):
    """Keeps a zero-commit rollback: one env var and a redeploy, no code change."""
    assert is_enabled({"WIX_CART_V2_DISABLED": value}) is False


@pytest.mark.parametrize("value", ["false", "0", "no", "off", ""])
def test_the_legacy_opt_in_key_still_disables_when_explicitly_falsy(value):
    """A deployed `WIX_CART_V2_ENABLED=false` is a decision, and inverting the default must not
    quietly overrule it."""
    assert is_enabled({"WIX_CART_V2_ENABLED": value}) is False


def test_the_legacy_key_set_true_leaves_it_on():
    assert is_enabled({"WIX_CART_V2_ENABLED": "true"}) is True


def test_the_absence_of_the_legacy_key_is_not_a_disable():
    """Every function in the fleet currently lacks it, so treating absence as off would make the
    inversion a no-op."""
    assert is_enabled({"SOMETHING_ELSE": "1"}) is True


def test_money_helpers_reject_float_on_the_delivery_path():
    """R6.1: no float arithmetic anywhere in the payment path."""
    for bad in (500.0, 5.99, True):
        with pytest.raises(ValueError):
            Money.from_wix(bad)
