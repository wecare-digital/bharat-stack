"""Wix Cart V2 boundary. No order, checkout redirect, or payment collection calls.

Reference: Wix Cart V2 Calculate Cart and Stores Catalog V3 eCommerce integration.
The request client is injected by wix-store. All prices come from Wix calculation.

WHY V2 AND NOT CHECKOUT V1
--------------------------
Cart V2 unifies Cart V1 and Checkout V1 into one Cart entity, and those two APIs are removed
on 2027-02-01. A Checkout V1 id *is* a V2 cart id, so ids carry across unchanged.
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-guide

Two consequences shape everything below:

- **Totals are not stored on the entity.** Checkout V1 kept `priceSummary`, `taxSummary`,
  `payNow` and `payLater` on the checkout; V2 keeps none of them. They come from Calculate
  Cart as `summary.*`, which is why `calculate()` returns a bound snapshot rather than this
  module exposing V1-style total readers.
- **V2 validates where V1 silently adjusted.** Checkout V1 dropped a missing item and
  quietly reduced an over-ordered quantity. V2 answers with explicit `summary.violations`,
  and an `ERROR`-severity violation must block. `calculate()` refusing to quote is that rule,
  not a defect: V1's total was obtainable precisely because nothing validated it.

DELIVERY IS A DEDICATED SURFACE IN V2
-------------------------------------
Checkout V1 carried `shippingInfo.shippingDestination.address` and
`shippingInfo.selectedCarrierServiceOption` on the entity. V2 maps those to
`deliveryInfo.address` (set through Update Cart) and `deliveryInfo.method`, and the mapping
states that the method is set through the dedicated Set Delivery Method call. Set Delivery
Method and Remove Delivery Method are both new in V2 with no V1 equivalent.
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-mapping

WHAT THIS MODULE REFUSES TO BE ABLE TO DO
-----------------------------------------
There is no Place Order, no Mark Cart As Completed, no Get Checkout URL and no redirect
session here, and that is structural rather than an omission. Place Order is the V2
replacement for Checkout V1's Create Order and can enter Wix payment collection; this
architecture collects through Razorpay and records the order afterwards. A method that can
charge must not exist on the adapter a customer-facing route holds, so the guarantee is "the
code is absent", which a test can enumerate, instead of "the code is guarded".
"""
from copy import deepcopy
from uuid import UUID

from .money import Money, positive_paise

STORES_APP_ID = "215238eb-22a5-4c36-9e7b-e7c08025e04e"
BASE = "/ecom/v2/carts"

#: ISO 3166-1 alpha-2, two uppercase letters. Wix address fields are free-form strings, so
#: the country is the one field worth constraining here: it selects the delivery options and
#: the tax treatment, and a typo yields a silently different quote rather than an error.
_COUNTRY_LENGTH = 2

#: Every address field this module will forward, and nothing else. An allowlist rather than a
#: passthrough: an unrecognised key is a caller mistake or an attempt to reach a field that
#: is not an address, and both should fail before the call rather than after it.
ADDRESS_FIELDS = ("country", "subdivision", "city", "postalCode",
                  "streetAddress", "addressLine", "addressLine2")

#: The minimum that makes an address a DESTINATION rather than a region.
#:
#: `subdivision` is in here for a tax reason, not a postal one: in India it is the place of
#: supply, so an address without it still prices -- just with the wrong CGST/SGST-versus-IGST
#: split. A partial address is the failure mode worth refusing, because Wix answers it with a
#: number rather than an error and that number would be charged.
REQUIRED_ADDRESS_FIELDS = ("country", "subdivision", "city", "postalCode")


#: Truthy spellings accepted for either gate key, matching the rest of the fleet.
_TRUTHY = ("1", "true", "yes", "on")

#: The opt-OUT key. Cart V2 is the default; this turns it off.
DISABLE_KEY = "WIX_CART_V2_DISABLED"

#: The superseded opt-IN key, still honoured as an explicit disable for one release.
LEGACY_ENABLE_KEY = "WIX_CART_V2_ENABLED"


class CartContractError(ValueError):
    """Wix returned a cart that is not safe to offer for payment."""


class CartItemUnavailable(CartContractError):
    """A line item is out of stock, partially available, or gone from the catalogue.

    Its own type, carrying `.items`, because the customer can act on this and the caller needs to
    say WHICH item and WHY. Checkout V1 handled it by dropping a missing item from the checkout
    and pricing what was left, so a cart could silently shrink between review and payment. V2
    surfaces it as a violation and as a line `status`, and this refuses rather than inheriting
    V1's behaviour.

    V2 status values, renamed from V1's `availability.status`: `AVAILABLE` -> `IN_STOCK`,
    `PARTIALLY_AVAILABLE` -> `PARTIALLY_IN_STOCK`, `NOT_AVAILABLE` -> `OUT_OF_STOCK`,
    `NOT_FOUND` -> `REMOVED_FROM_CATALOG`.
    https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-mapping
    """

    def __init__(self, message, items=None):
        super().__init__(message)
        self.items = list(items or ())


class CartQuantityReduced(CartContractError):
    """Wix confirmed fewer units than were requested, so the cart no longer means what was asked.

    THIS ONE IS NOT FIXED BY THE MIGRATION, AND THE MIGRATION GUIDE'S WORDING INVITES THE OPPOSITE
    CONCLUSION. The guide says V1 silently reduced an over-ordered quantity and that V2 "fails with
    explicit errors" instead. Cart V2's own introduction is more specific, and it still reduces:

        "When inventory drops below the requested quantity, confirmedQuantity automatically
        decreases to match available stock."
        -- https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/introduction

    So V2 does not refuse an under-stocked cart. What it adds is `quantityInfo.requestedQuantity`
    beside `confirmedQuantity` -- V1 had only the one number -- which makes the reduction
    *detectable*. `CartV2.calculate` comparing the two is what turns a detectable silent change
    into a refusal, and it is the only thing doing so. A reduced quantity on a priced cart is a
    wrong amount charged for the wrong goods, which is a correctness failure rather than an
    inconvenience, so this must never be relaxed into a warning.

    Carries `.items` with the requested and confirmed figures so the customer can be told exactly
    what changed and re-confirm it deliberately.
    """

    def __init__(self, message, items=None):
        super().__init__(message)
        self.items = list(items or ())


def is_enabled(env=None):
    """Whether the Cart V2 path serves. Default **on**; `WIX_CART_V2_DISABLED` turns it off.

    Inverted from an opt-in on 2026-10-01, when Cart V2 became the default price authority.
    The gate is inverted rather than deleted for one specific reason: it keeps a **zero-commit
    rollback**. `/wix-store/cart` performs real Create Cart and Add Line Items writes against
    the live site for any authenticated customer, and with no gate the only way to stop that
    would be a code change and a review cycle. One environment variable and a redeploy is the
    cheaper lever, and the one an operator can pull under pressure.

    `WIX_CART_V2_ENABLED` is still read, and an explicitly falsy value still disables. A
    deployed environment carrying `WIX_CART_V2_ENABLED=false` means somebody decided to turn
    this off; inverting the default must not quietly overrule that decision. The key's mere
    absence is not a disable -- absence is how every function in the fleet is configured today,
    and treating it as "off" would make the inversion a no-op.
    """
    import os
    environ = os.environ if env is None else env
    if str(environ.get(DISABLE_KEY, "")).strip().lower() in _TRUTHY:
        return False
    legacy = environ.get(LEGACY_ENABLE_KEY)
    if legacy is not None and str(legacy).strip().lower() not in _TRUTHY:
        return False
    return True


def delivery_address(address):
    """Validate a delivery address for `deliveryInfo.address`, or raise.

    Checkout V1's `shippingInfo.shippingDestination.address` maps to `deliveryInfo.address`
    in V2, written through Update Cart. Nothing financial is accepted: a caller cannot
    smuggle a price, a currency or a delivery charge in through an address field, which is
    the same rule `catalog_item` enforces for line items.
    """
    if not isinstance(address, dict) or not address:
        raise ValueError("a delivery address object is required")
    unknown = set(address) - set(ADDRESS_FIELDS)
    if unknown:
        raise ValueError("unsupported delivery address fields")
    country = address.get("country")
    if (not isinstance(country, str) or len(country) != _COUNTRY_LENGTH
            or not country.isalpha() or country != country.upper()):
        raise ValueError("country must be an uppercase ISO 3166-1 alpha-2 code")
    out = {}
    for field in ADDRESS_FIELDS:
        if field not in address:
            continue
        value = address[field]
        if field == "streetAddress":
            # Wix models this one as an object (name/number/apt), not a string.
            if not isinstance(value, dict) or not value or not all(
                    isinstance(part, str) and part.strip() for part in value.values()):
                raise ValueError("streetAddress must be an object of non-empty strings")
            out[field] = dict(value)
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        out[field] = value.strip()
    missing = [field for field in REQUIRED_ADDRESS_FIELDS if field not in out]
    if missing:
        raise ValueError(f"delivery address is missing {', '.join(missing)}")
    if not (out.get("addressLine") or out.get("streetAddress")):
        raise ValueError("delivery address needs a street line")
    return out


def identifier(value):
    if not isinstance(value, str) or str(UUID(value)) != value.lower():
        raise ValueError("invalid cart/catalog identifier")
    return value.lower()


def catalog_item(item):
    if not isinstance(item, dict) or set(item) != {"productId", "variantId", "quantity"}:
        raise ValueError("only productId, variantId and quantity are accepted")
    quantity = item["quantity"]
    if type(quantity) is not int or not 1 <= quantity <= 100000:
        raise ValueError("quantity must be a positive integer")
    return {"catalogReference": {
        "appId": STORES_APP_ID, "catalogItemId": identifier(item["productId"]),
        "options": {"variantId": identifier(item["variantId"])}}, "quantity": quantity}


class CartV2:
    def __init__(self, request):
        self.request = request

    def _cart(self, response, expected_id=None):
        cart = response.get("cart") if isinstance(response, dict) else None
        if not isinstance(cart, dict) or not cart.get("revision"):
            raise CartContractError("missing cart or revision")
        identifier(cart.get("id"))
        if expected_id and cart["id"] != expected_id:
            raise CartContractError("cart identity mismatch")
        if cart.get("orderPlaced") or cart.get("orderId"):
            raise CartContractError("cart is already completed")
        return cart

    def create(self, items):
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            raise ValueError("create requires 1 to 100 catalog items")
        return self._cart(self.request(BASE, method="POST", body={
            "catalogItems": [catalog_item(item) for item in items]}))

    def get(self, cart_id):
        cart_id = identifier(cart_id)
        return self._cart(self.request(f"{BASE}/{cart_id}"), cart_id)

    def add(self, cart_id, item):
        cart_id = identifier(cart_id)
        return self._cart(self.request(f"{BASE}/{cart_id}/add-line-items", method="POST",
                         body={"catalogItems": [catalog_item(item)]}), cart_id)

    def set_quantity(self, cart_id, line_id, quantity):
        if type(quantity) is not int or not 1 <= quantity <= 100000:
            raise ValueError("quantity must be a positive integer")
        cart_id, line_id = identifier(cart_id), identifier(line_id)
        return self._cart(self.request(f"{BASE}/{cart_id}/update-line-items", method="POST",
                         body={"lineItems": [{"lineItemId": line_id,
                                             "quantity": {"newQuantity": quantity}}]}), cart_id)

    def remove(self, cart_id, line_id):
        cart_id, line_id = identifier(cart_id), identifier(line_id)
        return self._cart(self.request(f"{BASE}/{cart_id}/remove-line-items", method="POST",
                         body={"lineItemIds": [line_id]}), cart_id)

    def refresh(self, cart_id):
        """Refresh Cart: re-evaluate prices, inventory and discounts. New in V2.

        Checkout V1's "Get Checkout with refresh" maps here. `calculate()` already passes
        `refreshCart`, so this exists for the case where a caller wants the re-evaluation
        without asking for a quote -- for example after a catalogue change, where forcing a
        quote would be the wrong shape of question.
        """
        cart_id = identifier(cart_id)
        return self._cart(self.request(f"{BASE}/{cart_id}/refresh", method="POST",
                                       body={}), cart_id)

    def set_delivery_address(self, cart_id, address):
        """Write `deliveryInfo.address` through Update Cart.

        Checkout V1 carried this as `shippingInfo.shippingDestination.address`; the V2 mapping
        moves it to `deliveryInfo.address`. Only the address is sent -- this never touches
        `businessInfo`, `paymentInfo` or line items, so it cannot change a currency or a price
        on the way past.

        The address is validated by `delivery_address` first. There is no default and no
        placeholder, deliberately: in India the delivery address is the place of supply, so a
        made-up address yields a real total with the wrong CGST/SGST-versus-IGST split, and
        that total is what a customer would be charged. An honest refusal is the cheaper
        failure.
        """
        cart_id = identifier(cart_id)
        return self._cart(self.request(f"{BASE}/{cart_id}", method="PATCH", body={
            "cart": {"deliveryInfo": {"address": delivery_address(address)}}}), cart_id)

    def set_delivery_method(self, cart_id, option_id):
        """Set Delivery Method. New in V2, with no Cart V1 or Checkout V1 equivalent.

        `option_id` identifies a shipping option Wix itself offered for this cart and address.
        It is an identifier, never a price: the delivery charge that follows is whatever
        `calculate()` reports in `summary.priceSummary.delivery`, and a caller cannot influence
        it. That is the same rule `catalog_item` applies to line items.
        """
        if not isinstance(option_id, str) or not option_id.strip() or len(option_id) > 200:
            raise ValueError("a delivery option id is required")
        cart_id = identifier(cart_id)
        return self._cart(self.request(f"{BASE}/{cart_id}/set-delivery-method", method="POST",
                                       body={"deliveryMethodId": option_id.strip()}), cart_id)

    def remove_delivery_method(self, cart_id):
        """Remove Delivery Method. New in V2.

        Present so a selected method can be withdrawn when the address changes, rather than a
        stale method surviving into a quote for a different destination.
        """
        cart_id = identifier(cart_id)
        return self._cart(self.request(f"{BASE}/{cart_id}/remove-delivery-method",
                                       method="POST", body={}), cart_id)

    def add_coupon(self, cart_id, code):
        """Add Coupon. New in V2 as a dedicated method; in V1 the code was inline in create/update.

        A coupon is a DISCOUNT, and it lands in `summary.priceSummary.discount`, not in the
        subtotal -- Cart V2 defines subtotal as line prices after item-level automatic discounts
        but BEFORE cart-level discounts like coupons. So the existing reconciliation,
        `subtotal - discount + delivery + additionalFees + tax == total`, already accounts for it
        and does not need widening.

        Applied SERVER-SIDE only. The code is a claim; Wix decides whether it is valid, what it is
        worth and whether this cart qualifies. A caller cannot supply a discount amount here, and
        the reduced total still arrives from Calculate Cart, so a browser cannot lower what it
        pays by inventing a coupon -- it can only ask for one to be validated.

        One coupon at a time: Cart V2's introduction states a cart supports a single coupon and
        adding a second returns an error.
        https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/introduction
        """
        if not isinstance(code, str) or not code.strip() or len(code.strip()) > 100:
            raise ValueError("a coupon code is required")
        cart_id = identifier(cart_id)
        return self._cart(self.request(f"{BASE}/{cart_id}/add-coupon", method="POST",
                                       body={"couponCode": code.strip()}), cart_id)

    def remove_coupon(self, cart_id, coupon_id):
        """Remove Coupon. V2 additionally requires the `couponId`, where V1 took only the cart."""
        if not isinstance(coupon_id, str) or not coupon_id.strip():
            raise ValueError("a coupon id is required")
        cart_id = identifier(cart_id)
        return self._cart(self.request(f"{BASE}/{cart_id}/remove-coupon", method="POST",
                                       body={"couponId": coupon_id.strip()}), cart_id)

    def estimate(self, cart_id):
        """A NON-PAYABLE item-subtotal view, for the state before a delivery address exists.

        This is the answer to "what do we show before the customer has chosen where it goes?", and
        Estimate Cart is the method Wix provides for it rather than a workaround. Verified against
        the Cart V2 introduction rather than assumed:

            "Estimate Cart: Performs a partial, component-based estimation controlled by boolean
            flags (calculateDelivery, calculateTax, calculateAdditionalFees, calculateGiftCards).
            Components not explicitly enabled are excluded from the calculation."
            -- https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/introduction

        All four flags are sent explicitly false. `calculateDelivery` and `calculateTax` are the
        two that need an address, so disabling them is what makes this answerable with no address
        -- which is precisely the pre-address state. `calculateGiftCards` is false because gift
        cards are refused outright on this path (see the module note below), and leaving it off
        keeps a gift-card balance from appearing in a number a customer might read as their price.

        The flags are not parameters. A caller that could switch `calculateDelivery` on would be
        able to obtain a delivery-inclusive figure through the method whose entire contract is
        "this is not your total", and that figure would then be one short conversion away from a
        charge.

        What it deliberately does NOT return: `amountPaise`, `calculationId`,
        `priceVerificationToken`, or anything else that could reach a gateway. The money is named
        `itemSubtotalPaise` because that is all it is. `payable` is always `False`.

        Violations still come back: the introduction says they are returned by both Calculate Cart
        and Estimate Cart, so this is also how the customer learns an item went out of stock before
        they have typed an address.
        """
        cart_id = identifier(cart_id)
        response = self.request(f"{BASE}/{cart_id}/estimate", method="POST", body={
            "calculateDelivery": False, "calculateTax": False,
            "calculateAdditionalFees": False, "calculateGiftCards": False})
        return self._not_payable(response, cart_id)

    def preview(self, cart_id):
        """The same non-payable view, from the FULL calculation.

        Kept separate from `estimate` because the two answer different questions. `estimate` is the
        lightweight pre-address figure; this runs Calculate Cart -- which "always runs
        checkout-level validations" -- and reports what it found without raising, so a caller can
        discover exactly why a cart is not yet payable. `purchase_intent` uses it to tell "no
        delivery address chosen" from "Wix returned something unsafe".
        """
        cart_id = identifier(cart_id)
        response = self.request(f"{BASE}/{cart_id}/calculate", method="POST",
                                body={"refreshCart": True})
        return self._not_payable(response, cart_id)

    def _not_payable(self, response, cart_id):
        """The shared non-payable projection. One shape, so `estimate` and `preview` cannot drift.

        `deliveryInfo` is handed back verbatim. The exact field Wix uses to enumerate available
        delivery options on a V2 cart could not be confirmed from a fetchable reference page, so
        this does not invent a name for it -- the caller gets what Wix sent, and the shape needs
        one live probe before a UI depends on it.
        """
        cart = self._cart(response, cart_id)
        summary = response.get("summary") or {}
        violations = [v for v in (summary.get("violations") or [])
                      if v.get("severity") != "WARNING"]
        prices = summary.get("priceSummary") or {}
        subtotal = Money.from_wix((prices.get("subtotal") or {}).get("amount")).paise
        return {"payable": False, "wixCartId": cart_id, "cartRevision": cart["revision"],
                "currency": "INR", "itemSubtotalPaise": subtotal,
                "blockingViolations": deepcopy(violations),
                "coupons": deepcopy(cart.get("coupons") or []),
                "deliveryInfo": deepcopy(cart.get("deliveryInfo") or {}),
                "items": [{"lineItemId": item.get("id"),
                           "requestedQuantity": (item.get("quantityInfo") or {}).get(
                               "requestedQuantity"),
                           "quantity": (item.get("quantityInfo") or {}).get("confirmedQuantity"),
                           "status": item.get("status")}
                          for item in (cart.get("lineItems") or [])]}

    def calculate(self, cart_id):
        cart_id = identifier(cart_id)
        response = self.request(f"{BASE}/{cart_id}/calculate", method="POST",
                                body={"refreshCart": True})
        cart = self._cart(response, cart_id)
        summary = response.get("summary") or {}
        if (summary.get("cartId") != cart_id or
                summary.get("cartRevision") != cart["revision"] or
                not summary.get("calculationId") or not summary.get("priceVerificationToken") or
                not cart.get("purchaseFlowId")):
            raise CartContractError("incomplete calculation binding")
        for field in ("businessInfo", "customerInfo", "paymentInfo"):
            if (cart.get(field) or {}).get("currencyCode") != "INR":
                raise CartContractError("all cart currencies must be INR")
        if any((summary.get("calculationErrors") or {}).values()) or summary.get("spiViolations"):
            raise CartContractError("calculation has unresolved legacy errors")
        if cart.get("demo"):
            raise CartContractError("demo cart cannot be paid")
        items = cart.get("lineItems") or []
        if not items:
            raise CartContractError("empty cart")
        # ITEM AVAILABILITY AND QUANTITY ARE CHECKED BEFORE THE GENERAL VIOLATIONS CHECK, AND THE
        # ORDER IS THE POINT. An out-of-stock cart carries an ERROR violation too, so checking
        # violations first would collapse "this item is gone" into the same generic refusal as
        # "no delivery address chosen" -- and those need different things from the customer. The
        # specific diagnosis has to come first to survive.
        unavailable = [{"lineItemId": item.get("id"), "status": item.get("status")}
                       for item in items if item.get("status") != "IN_STOCK"]
        if unavailable:
            raise CartItemUnavailable(
                "one or more items are not available at the requested quantity", unavailable)
        reduced = []
        for item in items:
            quantities = item.get("quantityInfo") or {}
            requested, confirmed = (quantities.get("requestedQuantity"),
                                    quantities.get("confirmedQuantity"))
            if type(requested) is not int or requested < 1:
                raise CartContractError("line item has no usable requested quantity")
            if requested != confirmed:
                reduced.append({"lineItemId": item.get("id"),
                                "requestedQuantity": requested,
                                "confirmedQuantity": confirmed})
        if reduced:
            raise CartQuantityReduced(
                "Wix confirmed fewer units than were requested", reduced)
        if any(v.get("severity") != "WARNING" for v in summary.get("violations", [])):
            raise CartContractError("cart has blocking or unknown violations")
        for item in items:
            source = item.get("source") or {}
            reference = source.get("catalogReference") or {}
            if (item.get("customLineItem") or source.get("catalogOverrideFields") or
                    reference.get("appId") != STORES_APP_ID or
                    not (reference.get("options") or {}).get("variantId") or
                    (item.get("pricing") or {}).get("priceUndetermined") or
                    (item.get("paymentConfig") or {}).get("paymentOption") != "FULL_PAYMENT_ONLINE"):
                raise CartContractError("unsupported or unavailable catalog item")
        prices = summary.get("priceSummary") or {}
        components = {key: Money.from_wix((prices.get(key) or {}).get("amount")).paise
                      for key in ("subtotal", "discount", "delivery", "additionalFees", "tax", "total")}
        total = positive_paise(components["total"])
        lines = summary.get("lineItems") or []
        expected_quantities = {item["id"]: item["quantityInfo"]["confirmedQuantity"] for item in items}
        calculated_quantities = {line.get("lineItemId"): line.get("quantity") for line in lines}
        if (len(lines) != len(items) or len(expected_quantities) != len(items) or
                calculated_quantities != expected_quantities or
                sum(Money.from_wix((line.get("totalPrice") or {}).get("amount")).paise
                    for line in lines) != components["subtotal"]):
            raise CartContractError("line calculation differs from cart")
        if (components["subtotal"] - components["discount"] + components["delivery"] +
                components["additionalFees"] + components["tax"] != total):
            raise CartContractError("price components do not match the total")
        payment = summary.get("paymentSummary") or {}
        # GIFT CARDS ARE REFUSED HERE, DELIBERATELY AND PERMANENTLY FOR THIS RELEASE.
        #
        # Cart V2 offers Add Gift Card / Remove Gift Card as dedicated new methods, and this
        # adapter implements NEITHER. Three independent reasons, the second of which is
        # disqualifying on its own:
        #
        # 1. A gift card is a PARTIAL PAYMENT, and partial payment is off for this release. The
        #    cart carries `payNow` beside `totalAfterGiftCards` precisely because the two differ
        #    once a card is applied, and Wix omits the payment gateway order id entirely when a
        #    gift card covers the whole total.
        # 2. A gift card settles INSIDE WIX. Every verification this system has -- the authoritative
        #    Razorpay captured-payment readback and the provider-payment binding -- can only verify
        #    a RAZORPAY capture. The gift-card leg would be money moving on a rail the payment
        #    integrity work cannot see, which is the exact failure class that work exists to
        #    prevent. A coupon has none of this problem: it is a discount, so it lowers one number
        #    and introduces no second rail.
        # 3. The convenience-fee basis becomes undefined -- is the 2.5% charged on the full
        #    collection total or on the post-gift-card remainder? That is a commercial and GST
        #    question against seller GSTIN 19AAFFW7196L1Z8, not an implementation detail.
        #
        # To revisit, the owner must decide (a) that partial payment is in scope, (b) how a
        # Wix-settled leg is authoritatively verified, and (c) the fee basis. Until then this check
        # stays exactly as it is: do not weaken it to make a gift card pass.
        if any(payment.get(key) for key in ("giftCards", "memberships", "subscriptionCharges")):
            raise CartContractError("split or subscription payment is not supported")
        for field in ("payNow", "totalAfterGiftCards"):
            if Money.from_wix((payment.get(field) or {}).get("amount")).paise != total:
                raise CartContractError("full immediate payment required")
        for field in ("payLater", "payAfterFreeTrial"):
            if field in payment and Money.from_wix(payment[field].get("amount")).paise:
                raise CartContractError("deferred payment is not supported")
        delivery = cart.get("deliveryInfo") or {}
        return {"wixCartId": cart_id, "cartRevision": cart["revision"],
                "purchaseFlowId": cart["purchaseFlowId"],
                "calculationId": summary["calculationId"],
                "priceVerificationToken": summary["priceVerificationToken"],
                "amountPaise": total, "currency": "INR", "componentsPaise": components,
                # Frozen alongside the amount because they are part of WHY it is that amount:
                # delivery is a component of the total and the address is the place of supply.
                # `build_snapshot` hashes both, so a changed address yields a different intent
                # rather than silently reusing a quote computed for somewhere else.
                "deliveryAddress": deepcopy(delivery.get("address") or {}),
                "deliveryMethod": deepcopy(delivery.get("method") or {}),
                "cart": deepcopy(cart), "summary": deepcopy(summary)}
