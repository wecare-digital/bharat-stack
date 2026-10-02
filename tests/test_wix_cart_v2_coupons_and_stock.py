"""Coupons, gift cards, and the two V1 behaviours this migration must not inherit silently.

All four subjects come from the official Cart V2 documents, cited per claim:
guide  https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-guide
intro  https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/introduction
map    https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-mapping

COUPONS -- implemented
    `Add Coupon` is a dedicated V2 method; in V1 the code was passed inline in create/update.
    A coupon is a discount, so it lowers the collection total BEFORE our convenience fee and the
    GST on that fee are applied, which legitimately lowers the fee basis. It introduces no second
    payment rail and stays fully server-authoritative, because the code is a CLAIM that Wix
    validates rather than a value the caller supplies.

GIFT CARDS -- refused, and the refusal is tested as hard as the coupon support is
    `Add Gift Card` is also a dedicated V2 method, and this adapter implements neither it nor
    `Remove Gift Card`. See `cart_v2.calculate`'s comment for the three reasons; the decisive one
    is that a gift card settles inside Wix, on a rail the Razorpay capture verification cannot see.

OUT OF STOCK / REMOVED FROM CATALOGUE -- explicit, where V1 was silent
    V1 dropped a missing item and priced what was left. V2 reports it as an `ERROR` violation and
    as a line `status`, and this refuses with an actionable error naming the item.

SILENTLY REDUCED QUANTITY -- and the brief's framing of this one is wrong
    The migration guide says V1 silently reduced an over-ordered quantity and V2 "fails with
    explicit errors". The Cart V2 introduction is more specific and contradicts the inference:
    V2 STILL reduces -- "When inventory drops below the requested quantity, confirmedQuantity
    automatically decreases to match available stock." What V2 adds is `requestedQuantity` beside
    `confirmedQuantity`, where V1 carried only one number. So the reduction is detectable rather
    than prevented, and `CartV2.calculate` comparing the two is the only thing that turns a
    detectable silent change into a refusal.
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

from lambda_utils.ecommerce import checkout_pricing as cp  # noqa: E402
from lambda_utils.ecommerce import purchase_intent as pi  # noqa: E402
from lambda_utils.ecommerce.cart_v2 import (  # noqa: E402
    CartContractError, CartItemUnavailable, CartQuantityReduced, CartV2,
)
from lambda_utils.ecommerce.money import Money  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
NOW = 1_700_000_000
OWNED = {"addressLine1": "12 Dalhousie Square", "city": "Kolkata",
         "state": "West Bengal", "postalCode": "700001"}


def load(name):
    return json.loads((FIXTURES / f"wix_cart_v2_{name}.json").read_text())


class Wix:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, path, method="GET", body=None):
        self.calls.append((method.upper(), path, copy.deepcopy(body)))
        return copy.deepcopy(self.response)

    def paths(self, cart_id):
        return [(m, p.replace(cart_id, "{id}")) for m, p, _ in self.calls]


def components(response):
    prices = response["summary"]["priceSummary"]
    return {key: Money.from_wix(prices[key]["amount"]).paise
            for key in ("subtotal", "discount", "delivery", "additionalFees", "tax", "total")}


# ── coupons ──────────────────────────────────────────────────────────────────────

def test_add_coupon_routes_to_the_dedicated_v2_method():
    response = load("coupon_applied")
    wix = Wix(response)
    CartV2(wix).add_coupon(response["cart"]["id"], "WELCOME10")

    assert wix.paths(response["cart"]["id"]) == [("POST", "/ecom/v2/carts/{id}/add-coupon")]
    assert wix.calls[0][2] == {"couponCode": "WELCOME10"}


def test_a_coupon_lowers_the_collection_total():
    """The behavioural claim, measured against the un-couponed cart rather than asserted."""
    plain = CartV2(Wix(load("delivery_complete"))).calculate(
        load("delivery_complete")["cart"]["id"])
    couponed = CartV2(Wix(load("coupon_applied"))).calculate(
        load("coupon_applied")["cart"]["id"])

    assert couponed["componentsPaise"]["discount"] == 250000
    assert plain["componentsPaise"]["discount"] == 0
    assert couponed["amountPaise"] == plain["amountPaise"] - 250000
    assert couponed["amountPaise"] == 2299900


def test_a_coupon_reduces_the_discount_component_not_the_subtotal():
    """Cart V2 defines subtotal as line prices after ITEM-level automatic discounts and before
    cart-level discounts like coupons, so the existing reconciliation already covers a coupon and
    did not need widening."""
    couponed = CartV2(Wix(load("coupon_applied"))).calculate(
        load("coupon_applied")["cart"]["id"])
    assert couponed["componentsPaise"]["subtotal"] == 2499900  # unchanged by the coupon


def test_a_couponed_quote_still_reconciles_exactly():
    """collection + fee + GST == total, in integer paise, with the discount applied."""
    response = load("coupon_applied")
    snapshot = pi.build_intent(CartV2(Wix(response)), customer_id="CUS_abc123",
                               cart_id=response["cart"]["id"], owned_address=OWNED, now=NOW)
    quote = snapshot.quote

    assert quote.collection_before_convenience_paise == 2299900
    assert quote.total_payable_paise == (quote.collection_before_convenience_paise
                                        + quote.convenience_fee_paise
                                        + quote.convenience_gst_paise)
    split = quote.convenience_gst_split
    assert split.cgst_paise + split.sgst_paise + split.igst_paise == quote.convenience_gst_paise
    for value in (quote.collection_before_convenience_paise, quote.convenience_fee_paise,
                  quote.convenience_gst_paise, quote.total_payable_paise):
        assert type(value) is int


def test_a_coupon_lowers_the_convenience_fee_basis():
    """The fee is charged on the post-discount collection total, which is the documented basis."""
    plain = pi.build_intent(CartV2(Wix(load("delivery_complete"))), customer_id="CUS_abc123",
                            cart_id=load("delivery_complete")["cart"]["id"],
                            owned_address=OWNED, now=NOW).quote
    couponed = pi.build_intent(CartV2(Wix(load("coupon_applied"))), customer_id="CUS_abc123",
                               cart_id=load("coupon_applied")["cart"]["id"],
                               owned_address=OWNED, now=NOW).quote

    assert couponed.convenience_fee_paise < plain.convenience_fee_paise
    assert couponed.convenience_gst_paise < plain.convenience_gst_paise
    assert couponed.total_payable_paise < plain.total_payable_paise


def test_a_browser_cannot_supply_a_discount_amount_only_a_code_to_validate():
    """The property that makes customer-supplied coupons safe.

    The request carries a code and nothing financial. Wix decides the value, and the reduced total
    arrives through Calculate Cart like every other component, so a caller can ask for a discount
    to be validated and cannot grant itself one.
    """
    response = load("coupon_applied")
    wix = Wix(response)
    CartV2(wix).add_coupon(response["cart"]["id"], "WELCOME10")

    body = wix.calls[0][2]
    assert set(body) == {"couponCode"}
    serialized = json.dumps(body).lower()
    for financial in ("amount", "price", "discount", "paise", "total", "currency", "percent"):
        assert financial not in serialized


def test_an_invented_coupon_cannot_change_the_amount_without_wix_agreeing():
    """Wix's response is the only thing that moves the number.

    Here the provider ignores the code -- returning the un-couponed cart -- and the quote is the
    full price. A client-side "discount" that the server did not honour must not appear in the
    total.
    """
    response = load("delivery_complete")
    wix = Wix(response)
    adapter = CartV2(wix)
    adapter.add_coupon(response["cart"]["id"], "NOT-A-REAL-CODE")
    quoted = adapter.calculate(response["cart"]["id"])

    assert quoted["componentsPaise"]["discount"] == 0
    assert quoted["amountPaise"] == 2549900


@pytest.mark.parametrize("bad", ["", "   ", None, 123, "x" * 101, b"code"])
def test_a_malformed_coupon_code_never_reaches_the_provider(bad):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid coupon input reached the provider")

    with pytest.raises(ValueError):
        CartV2(forbidden).add_coupon(load("coupon_applied")["cart"]["id"], bad)


def test_removing_a_coupon_requires_the_coupon_id_v2_added():
    """V1 took only the cart; the mapping records that V2 also requires `couponId`."""
    response = load("delivery_complete")
    wix = Wix(response)
    CartV2(wix).remove_coupon(response["cart"]["id"], "c0up0n01-0000-4000-8000-00000000c0de")
    assert wix.calls[0][1].endswith("/remove-coupon")
    assert wix.calls[0][2] == {"couponId": "c0up0n01-0000-4000-8000-00000000c0de"}

    for bad in ("", "   ", None, 5):
        with pytest.raises(ValueError):
            CartV2(wix).remove_coupon(response["cart"]["id"], bad)


def test_the_applied_coupon_is_visible_in_the_non_payable_view():
    """So a customer can see the discount they applied before a payable quote exists."""
    response = load("coupon_applied")
    preview = CartV2(Wix(response)).preview(response["cart"]["id"])
    assert preview["coupons"][0]["code"] == "WELCOME10"
    assert preview["payable"] is False


# ── gift cards: refused ──────────────────────────────────────────────────────────

def test_the_adapter_has_no_gift_card_methods_at_all():
    """Refused by absence, not by a guard. `Add Gift Card` and `Remove Gift Card` are both
    first-class V2 methods, so leaving them out is a decision and this records it."""
    for forbidden in ("add_gift_card", "addGiftCard", "remove_gift_card", "gift_card"):
        assert not hasattr(CartV2, forbidden)

    # The endpoint shapes specifically, not the phrase: this file and `cart_v2` both discuss gift
    # cards at length in prose, and the thing being asserted is that no CALL is built.
    source = (ROOT / "amplify/functions/shared/lambda_utils/ecommerce/cart_v2.py").read_text()
    for endpoint in ("/add-gift-card", "/remove-gift-card"):
        assert endpoint not in source, f"cart_v2 must not reference {endpoint}"


def test_a_gift_card_on_the_cart_is_refused_rather_than_part_paid():
    """A gift card is a partial payment, and partial payment is off for this release.

    The decisive reason is narrower than that, though: a gift card settles INSIDE Wix, and every
    verification here can only confirm a Razorpay capture. The gift-card leg would be money moving
    on a rail the payment-integrity work cannot see.
    """
    response = load("delivery_complete")
    response["summary"]["paymentSummary"]["giftCards"] = [
        {"id": "gc-1", "amount": {"amount": "500.00"}}]
    with pytest.raises(CartContractError):
        CartV2(Wix(response)).calculate(response["cart"]["id"])


def test_a_gift_card_that_covers_the_whole_total_is_still_refused():
    """The case where Wix omits the payment gateway order id entirely, leaving nothing to verify."""
    response = load("delivery_complete")
    response["summary"]["paymentSummary"]["giftCards"] = [
        {"id": "gc-1", "amount": {"amount": "25499.00"}}]
    response["summary"]["paymentSummary"]["payNow"] = {"amount": "0", "convertedAmount": "0"}
    response["summary"]["paymentSummary"]["totalAfterGiftCards"] = {
        "amount": "0", "convertedAmount": "0"}
    with pytest.raises(CartContractError):
        CartV2(Wix(response)).calculate(response["cart"]["id"])


def test_the_estimate_never_asks_wix_to_calculate_gift_cards():
    """So a gift-card balance cannot appear in a figure a customer might read as their price."""
    response = load("delivery_complete")
    wix = Wix(response)
    CartV2(wix).estimate(response["cart"]["id"])
    assert wix.calls[0][2]["calculateGiftCards"] is False


def test_memberships_and_subscription_charges_are_refused_on_the_same_grounds():
    for field in ("memberships", "subscriptionCharges"):
        response = load("delivery_complete")
        response["summary"]["paymentSummary"][field] = [{"id": "x"}]
        with pytest.raises(CartContractError):
            CartV2(Wix(response)).calculate(response["cart"]["id"])


# ── Estimate Cart: the verified pre-address state ────────────────────────────────

def test_estimate_asks_for_no_component_that_would_need_an_address():
    """Verified against the Cart V2 introduction, not assumed.

    Estimate Cart is "a partial, component-based estimation controlled by boolean flags", and
    components not explicitly enabled are excluded. `calculateDelivery` and `calculateTax` are the
    two that need an address, so sending both false is what makes this answerable before the
    customer has chosen a destination.
    """
    response = load("live_demo")
    wix = Wix(response)
    estimate = CartV2(wix).estimate(response["cart"]["id"])

    method, path, body = wix.calls[0]
    assert (method, path.replace(response["cart"]["id"], "{id}")) == \
        ("POST", "/ecom/v2/carts/{id}/estimate")
    assert body == {"calculateDelivery": False, "calculateTax": False,
                    "calculateAdditionalFees": False, "calculateGiftCards": False}
    assert estimate["payable"] is False
    assert estimate["itemSubtotalPaise"] == 2499900


def test_estimate_works_on_the_real_address_less_cart_and_offers_no_total():
    """The pre-address display: item subtotals only, nothing that could be charged."""
    response = load("live_demo")
    estimate = CartV2(Wix(response)).estimate(response["cart"]["id"])
    for forbidden in ("amountPaise", "calculationId", "priceVerificationToken", "total"):
        assert forbidden not in estimate


def test_estimate_still_surfaces_blocking_violations():
    """The introduction says violations come back from both Estimate Cart and Calculate Cart, so
    this is also how a customer learns an item went out of stock before typing an address."""
    response = load("out_of_stock")
    estimate = CartV2(Wix(response)).estimate(response["cart"]["id"])
    assert {v["code"] for v in estimate["blockingViolations"]} == {"OUT_OF_STOCK"}


def test_the_estimate_flags_are_not_caller_controllable():
    """A caller that could switch `calculateDelivery` on would get a delivery-inclusive figure out
    of the method whose entire contract is "this is not your total"."""
    import inspect
    signature = inspect.signature(CartV2.estimate)
    assert list(signature.parameters) == ["self", "cart_id"]


# ── out of stock and removed from catalogue: explicit, where V1 was silent ───────

def test_an_out_of_stock_item_is_refused_and_named():
    """V1 would have priced what was left. The error carries the line id and the status so the
    customer can be told which item and why."""
    response = load("out_of_stock")
    with pytest.raises(CartItemUnavailable) as caught:
        CartV2(Wix(response)).calculate(response["cart"]["id"])

    assert caught.value.items == [
        {"lineItemId": response["cart"]["lineItems"][0]["id"], "status": "OUT_OF_STOCK"}]
    # Still a CartContractError, so every existing handler keeps catching it.
    assert isinstance(caught.value, CartContractError)


def test_an_item_removed_from_the_catalogue_is_refused_and_named():
    """V1's `NOT_FOUND` became V2's `REMOVED_FROM_CATALOG`, and V1 dropped such an item silently."""
    response = load("removed_from_catalog")
    with pytest.raises(CartItemUnavailable) as caught:
        CartV2(Wix(response)).calculate(response["cart"]["id"])
    assert caught.value.items[0]["status"] == "REMOVED_FROM_CATALOG"


@pytest.mark.parametrize("status", ["PARTIALLY_IN_STOCK", "OUT_OF_STOCK",
                                    "REMOVED_FROM_CATALOG", "", None, "IN_STOCK_MAYBE"])
def test_any_status_other_than_in_stock_refuses(status):
    """An allowlist of one. An unknown status is refused rather than assumed benign, which is the
    difference between adding a value to the enum and shipping a wrong charge."""
    response = load("delivery_complete")
    response["cart"]["lineItems"][0]["status"] = status
    with pytest.raises(CartItemUnavailable):
        CartV2(Wix(response)).calculate(response["cart"]["id"])


def test_an_unavailable_item_never_reaches_a_quote_snapshot():
    response = load("out_of_stock")
    with pytest.raises(CartItemUnavailable):
        pi.build_intent(CartV2(Wix(response)), customer_id="CUS_abc123",
                        cart_id=response["cart"]["id"], owned_address=OWNED, now=NOW)


def test_an_out_of_stock_cart_is_not_reported_as_a_delivery_problem():
    """The two refusals must stay distinguishable: "choose an address" and "this item is gone" need
    different things from the customer."""
    response = load("out_of_stock")
    with pytest.raises(Exception) as caught:
        pi.build_intent(CartV2(Wix(response)), customer_id="CUS_abc123",
                        cart_id=response["cart"]["id"], owned_address=OWNED, now=NOW)
    assert not isinstance(caught.value, pi.DeliveryDetailsRequired)


# ── the silent quantity reduction V2 did NOT fix ─────────────────────────────────

def test_a_silently_reduced_quantity_is_refused_with_both_numbers():
    """The correctness item, and the one the migration guide's wording would have let through.

    Wix reduced 3 units to 1 and priced the 1, so every money field in the response reconciles
    perfectly. Nothing about the total looks wrong -- it is simply the total for goods the customer
    did not agree to buy. Only comparing `requestedQuantity` against `confirmedQuantity` catches
    it.
    """
    response = load("quantity_reduced")
    with pytest.raises(CartQuantityReduced) as caught:
        CartV2(Wix(response)).calculate(response["cart"]["id"])

    assert caught.value.items == [{
        "lineItemId": response["cart"]["lineItems"][0]["id"],
        "requestedQuantity": 3, "confirmedQuantity": 1}]
    assert isinstance(caught.value, CartContractError)


def test_the_reduced_cart_would_otherwise_have_reconciled_perfectly():
    """Proves the previous test is catching something no arithmetic check could.

    The fixture's own components add up and its line totals match the subtotal. A suite that only
    verified the money would have passed this cart straight through to a charge.
    """
    response = load("quantity_reduced")
    parts = components(response)
    assert (parts["subtotal"] - parts["discount"] + parts["delivery"]
            + parts["additionalFees"] + parts["tax"]) == parts["total"]
    assert parts["total"] == 2549900


def test_a_reduced_quantity_never_reaches_a_quote_snapshot():
    response = load("quantity_reduced")
    with pytest.raises(CartQuantityReduced):
        pi.build_intent(CartV2(Wix(response)), customer_id="CUS_abc123",
                        cart_id=response["cart"]["id"], owned_address=OWNED, now=NOW)


def test_the_non_payable_view_reports_both_quantities_so_the_change_is_visible():
    """A customer cannot re-confirm a reduction they were never shown."""
    response = load("quantity_reduced")
    preview = CartV2(Wix(response)).preview(response["cart"]["id"])
    assert preview["items"][0]["requestedQuantity"] == 3
    assert preview["items"][0]["quantity"] == 1


@pytest.mark.parametrize("requested", [0, -1, None, "3", 3.0, True])
def test_an_unusable_requested_quantity_is_refused(requested):
    response = load("delivery_complete")
    response["cart"]["lineItems"][0]["quantityInfo"]["requestedQuantity"] = requested
    with pytest.raises(CartContractError):
        CartV2(Wix(response)).calculate(response["cart"]["id"])


# ── no Wix-hosted checkout, on any path ─────────────────────────────────────────

def test_nothing_here_reaches_a_wix_hosted_checkout_or_a_checkout_url():
    """This is a headless architecture: Wix prices, Razorpay collects on our own site.

    The migration guide notes that direct payment collection is not supported for a headless
    storefront and recommends the Wix-hosted checkout page. That guidance is about collecting
    THROUGH Wix, which this system does not do, so Get Checkout URL and `customCheckoutUrl` are
    both deliberately unused.
    """
    response = load("coupon_applied")
    wix = Wix(response)
    adapter = CartV2(wix)
    cart_id = response["cart"]["id"]
    adapter.add_coupon(cart_id, "WELCOME10")
    adapter.estimate(cart_id)
    adapter.calculate(cart_id)

    for _method, path, body in wix.calls:
        lowered = path.lower()
        for marker in ("checkout-url", "checkouturl", "redirect", "place-order", "pay"):
            assert marker not in lowered, f"reached {path}"
        assert "customCheckoutUrl" not in json.dumps(body or {})

    source = (ROOT / "amplify/functions/shared/lambda_utils/ecommerce/cart_v2.py").read_text()
    code = [line for line in source.splitlines()
            if "customCheckoutUrl" in line and not line.strip().startswith("#")]
    assert not code
