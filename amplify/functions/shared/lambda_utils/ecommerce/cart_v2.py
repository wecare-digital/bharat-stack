"""Wix Cart V2 boundary. No order, checkout redirect, or payment collection calls.

Reference: Wix Cart V2 Calculate Cart and Stores Catalog V3 eCommerce integration.
The request client is injected by wix-store. All prices come from Wix calculation.
"""
from copy import deepcopy
from uuid import UUID

from .money import Money, positive_paise

STORES_APP_ID = "215238eb-22a5-4c36-9e7b-e7c08025e04e"
BASE = "/ecom/v2/carts"


class CartContractError(ValueError):
    """Wix returned a cart that is not safe to offer for payment."""


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
        if any(v.get("severity") != "WARNING" for v in summary.get("violations", [])):
            raise CartContractError("cart has blocking or unknown violations")
        if cart.get("demo"):
            raise CartContractError("demo cart cannot be paid")
        items = cart.get("lineItems") or []
        if not items:
            raise CartContractError("empty cart")
        for item in items:
            source = item.get("source") or {}
            reference = source.get("catalogReference") or {}
            if (item.get("customLineItem") or source.get("catalogOverrideFields") or
                    reference.get("appId") != STORES_APP_ID or
                    not (reference.get("options") or {}).get("variantId") or
                    (item.get("pricing") or {}).get("priceUndetermined") or
                    item.get("status") != "IN_STOCK" or
                    (item.get("paymentConfig") or {}).get("paymentOption") != "FULL_PAYMENT_ONLINE"):
                raise CartContractError("unsupported or unavailable catalog item")
            quantities = item.get("quantityInfo") or {}
            requested = quantities.get("requestedQuantity")
            if (type(requested) is not int or requested < 1 or
                    requested != quantities.get("confirmedQuantity")):
                raise CartContractError("requested quantity is not fully available")
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
        if any(payment.get(key) for key in ("giftCards", "memberships", "subscriptionCharges")):
            raise CartContractError("split or subscription payment is not supported")
        for field in ("payNow", "totalAfterGiftCards"):
            if Money.from_wix((payment.get(field) or {}).get("amount")).paise != total:
                raise CartContractError("full immediate payment required")
        for field in ("payLater", "payAfterFreeTrial"):
            if field in payment and Money.from_wix(payment[field].get("amount")).paise:
                raise CartContractError("deferred payment is not supported")
        return {"wixCartId": cart_id, "cartRevision": cart["revision"],
                "purchaseFlowId": cart["purchaseFlowId"],
                "calculationId": summary["calculationId"],
                "priceVerificationToken": summary["priceVerificationToken"],
                "amountPaise": total, "currency": "INR", "componentsPaise": components,
                "cart": deepcopy(cart), "summary": deepcopy(summary)}
