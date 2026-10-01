"""`ecommerce/checkout` prices through Cart V2, and the amount it charges is the calculator's.

What this covers that `tests/test_checkout_handler.py` does not
--------------------------------------------------------------
That file exercises the Checkout V1 price authority, which became the opt-out path on 2026-10-01
and is pinned off there. This file is the default path: Cart V2.

The behavioural difference is not the version, it is the amount. The V1 branch charged
`priceSummary.total` straight from Wix. The V2 branch runs Wix's collection total through
`checkout_pricing.compute_quote`, which adds our convenience fee and the GST on that fee, and
charges `total_payable_paise`. That is the contract section 8 of the handler's own docstring states
for the website path — "amountPaise is the FEAT-001 calculator total (collection+fee+GST), never
the raw Wix total" — and before the Cart V2 producer existed, no code path honoured it.

Two refusals are asserted as hard as the success is, because both are the point:

* **No address, no price.** Cart V2 answers an address-less cart with `ERROR`-severity
  `MISSING_DELIVERY_ADDRESS` / `MISSING_DELIVERY_METHOD`, and the handler returns
  `DELIVERY_DETAILS_REQUIRED` rather than substituting a default. Delivery is a component of the
  total and the delivery address is the place of supply, so a fabricated address yields a real
  number with the wrong CGST/SGST-versus-IGST split against seller GSTIN 19AAFFW7196L1Z8 — and
  that number would be charged.
* **No order, ever, here.** This handler reserves an intent. An order exists only after an
  authoritative capture, so no call it makes may create or place one.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from crm_fake_dynamo import FakeDynamo  # noqa: E402

HANDLER = ROOT / "amplify/functions/ecommerce/checkout/handler.py"
FIXTURES = pathlib.Path(__file__).parent / "fixtures"
ATTEMPTS_TABLE = "stack-wecare-digital-PaymentAttemptsTable"
KEYS_TABLE = "stack-wecare-digital-CommerceKeys"
CUSTOMER = "CUS_01J8Z9EXAMPLECUSTOMER"

OWNED = {"addressLine1": "12 Dalhousie Square", "city": "Kolkata",
         "state": "West Bengal", "postalCode": "700001"}

#: Expected figures, re-derived here rather than copied from the implementation:
#: Wix collection 25499.00 = items 24999.00 + delivery 500.00.
COLLECTION_PAISE = 2549900
#: 2.5% convenience fee, then 18% GST on the fee, both half-up on integer paise.
FEE_PAISE = 63748
FEE_GST_PAISE = 11475
TOTAL_PAYABLE_PAISE = COLLECTION_PAISE + FEE_PAISE + FEE_GST_PAISE


def delivery_complete():
    return json.loads((FIXTURES / "wix_cart_v2_delivery_complete.json").read_text())


def live():
    return json.loads((FIXTURES / "wix_cart_v2_live_demo.json").read_text())


class _Identity:
    def __init__(self, customer_id=CUSTOMER):
        self.customer_id = customer_id
        self.phone = "+918100640044"
        self.subject = "subject-1"

    def owns(self, cid):
        return bool(cid) and cid == self.customer_id


class _FakeLambda:
    """Stands in for the WhatsApp sender and the payment-config readback."""

    def __init__(self):
        self.send_ok = True

    def invoke(self, FunctionName=None, InvocationType=None, Payload=None, **_):
        event = json.loads(Payload.decode("utf-8"))
        if "payment-config" in str(event.get("path") or ""):
            # A ready-looking raw payment_configurations readback for the WABA. Readiness is a
            # live provider readback in production; this makes it pass so the PRICE is what the
            # test is measuring. `tests/test_checkout_handler.py` covers the blocked states.
            inner = {"statusCode": 200, "body": json.dumps({"data": [{
                "configuration_name": "WECAREDIGITAL", "status": "active",
                "payment_gateway": {"type": "razorpay", "merchant_id": "acc_TESTMID"}}]})}
        else:
            inner = {"statusCode": 200 if self.send_ok else 502, "body": "{}"}
        return {"Payload": _Payload(json.dumps(inner).encode("utf-8"))}


class _Payload:
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw


class RecordingWix:
    """Replays a Cart V2 response and records every call, so a test can enumerate them."""

    def __init__(self, response=None):
        self.response = delivery_complete() if response is None else response
        self.calls = []

    def __call__(self, endpoint, method="GET", body=None):
        self.calls.append((method.upper(), endpoint))
        if endpoint.startswith("/stores/v3/products/"):
            # `normalized_catalog_items` resolves the live variant before pricing.
            reference = self.response["cart"]["lineItems"][0]["source"]["catalogReference"]
            return {"product": {
                "id": reference["catalogItemId"], "visible": True,
                "variantsInfo": {"variants": [{
                    "id": reference["options"]["variantId"], "visible": True,
                    "inventoryStatus": {"inStock": True}}]}}}
        return copy.deepcopy(self.response)

    def paths(self):
        return [path for _method, path in self.calls]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("PAYMENT_ATTEMPTS_TABLE", ATTEMPTS_TABLE)
    monkeypatch.setenv("COMMERCE_KEYS_TABLE", KEYS_TABLE)
    monkeypatch.setenv("EXPECTED_CONFIGURATION_NAME", "WECAREDIGITAL")
    monkeypatch.setenv("EXPECTED_PROVIDER_MID", "acc_TESTMID")
    monkeypatch.setenv("PAYMENT_WABA_ID", "2094615664435155")
    monkeypatch.setenv("APP_ENV", "development")
    # No gate key set at all: Cart V2 is the DEFAULT, and that is what is under test.
    monkeypatch.delenv("WIX_CART_V2_DISABLED", raising=False)
    monkeypatch.delenv("WIX_CART_V2_ENABLED", raising=False)

    spec = importlib.util.spec_from_file_location("checkout_cart_v2_under_test", HANDLER)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)

    fake = FakeDynamo(keys={ATTEMPTS_TABLE: "paymentAttemptId", KEYS_TABLE: "orderId"})
    lam = _FakeLambda()
    wix = RecordingWix()

    monkeypatch.setattr(h, "_dynamodb", fake)
    monkeypatch.setattr(h, "_lambda_client", lambda: lam)
    monkeypatch.setattr(h, "INITIATION_ENABLED", False)
    monkeypatch.setattr(h, "_wix_request", wix)
    monkeypatch.setattr(h.wix_ecom, "_request", wix)
    monkeypatch.setattr(h.customer_auth, "authenticate", lambda event: _Identity())
    # The owned-address loader seam. In production this reads the authenticated customer's
    # profile; here it returns a real address. It is NEVER taken from the request body.
    monkeypatch.setattr(h, "LOAD_OWNED_ADDRESS", lambda customer_id: dict(OWNED))
    return h, fake, lam, wix, monkeypatch


def _create_event(**over):
    reference = delivery_complete()["cart"]["lineItems"][0]["source"]["catalogReference"]
    body = {"lineItems": [{
        "catalogReference": {"appId": reference["appId"],
                             "catalogItemId": reference["catalogItemId"],
                             "options": {"variantId": reference["options"]["variantId"]}},
        "quantity": 1}]}
    body.update(over)
    return {
        "requestContext": {"http": {"method": "POST", "sourceIp": "203.0.113.5"}},
        "headers": {"origin": "http://localhost:3000", "authorization": "Bearer tok"},
        "body": json.dumps({"action": "create", **body}),
    }


# ── the default path is Cart V2 ──────────────────────────────────────────────────

def test_with_no_gate_key_set_the_handler_prices_through_cart_v2(env):
    h, _fake, _lam, wix, _mp = env
    response = h.handler(_create_event(), None)
    assert response["statusCode"] == 200
    assert all("/ecom/v1/checkouts" not in path for path in wix.paths()), \
        "the default path must not touch Checkout V1"
    assert any(path.startswith("/ecom/v2/carts") for path in wix.paths())


def test_the_charged_amount_is_the_calculator_total_not_the_raw_wix_total(env):
    """The behavioural change the migration exists to make.

    V1 charged Wix's `priceSummary.total`. V2 charges collection + convenience fee + GST on the
    fee, which is what `website_checkout` and `customer_receipt` have always expected and what
    nothing produced.
    """
    h, fake, _lam, _wix, _mp = env
    body = json.loads(h.handler(_create_event(), None)["body"])

    assert body["amountPaise"] == TOTAL_PAYABLE_PAISE
    assert body["amountPaise"] != COLLECTION_PAISE
    assert body["currency"] == "INR"
    attempts = fake.all_rows(ATTEMPTS_TABLE)
    assert len(attempts) == 1
    assert attempts[0]["amountPaise"] == TOTAL_PAYABLE_PAISE


def test_the_reserved_reference_records_both_the_collection_and_the_payable_amount(env):
    """So the fee and its GST stay auditable instead of being inferred from a difference."""
    h, fake, _lam, _wix, _mp = env
    h.handler(_create_event(), None)

    rows = [row for row in fake.all_rows(KEYS_TABLE) if str(row["orderId"]).startswith("PAYREF#")]
    assert len(rows) == 1
    reserved = rows[0]
    assert int(reserved["amountPaise"]) == TOTAL_PAYABLE_PAISE
    assert int(reserved["collectionPaise"]) == COLLECTION_PAISE
    assert reserved["wixCartId"] == delivery_complete()["cart"]["id"]
    assert int(reserved["cartRevision"]) == 4
    assert reserved["quoteHash"]


def test_the_v2_path_stores_no_wix_checkout_id(env):
    """In Cart V2 the cart id IS the checkout id, so a separate field identifies nothing.

    Still written as an empty string rather than removed: the field exists on a deployed Amplify
    data model and on stored rows, and dropping it is a separate, non-inert change.
    """
    h, fake, _lam, _wix, _mp = env
    h.handler(_create_event(), None)
    rows = [row for row in fake.all_rows(KEYS_TABLE) if str(row["orderId"]).startswith("PAYREF#")]
    assert rows[0]["wixCheckoutId"] == ""


def test_money_in_the_response_is_an_integer_number_of_paise(env):
    h, _fake, _lam, _wix, _mp = env
    body = json.loads(h.handler(_create_event(), None)["body"])
    assert type(body["amountPaise"]) is int
    assert "." not in json.dumps(body["amountPaise"])


# ── no address means no price, and no invented address ───────────────────────────

def test_without_an_owned_address_the_handler_refuses_instead_of_pricing(env):
    """The loader seam returns nothing, as it does in production until the profile read is wired.

    The response is a recoverable 409 naming what the customer must do, not a 500 and not a total
    computed from a placeholder.
    """
    h, fake, _lam, _wix, monkeypatch = env
    monkeypatch.setattr(h, "LOAD_OWNED_ADDRESS", None)
    response = h.handler(_create_event(), None)

    assert response["statusCode"] == 409
    assert json.loads(response["body"])["error"] == "DELIVERY_DETAILS_REQUIRED"
    # Nothing was reserved and no attempt exists: a refused price creates no intent.
    assert fake.all_rows(ATTEMPTS_TABLE) == []


def test_an_empty_profile_address_is_not_coerced_into_a_default(env):
    h, fake, _lam, _wix, monkeypatch = env
    for empty in ({}, None, ""):
        monkeypatch.setattr(h, "LOAD_OWNED_ADDRESS", lambda cid, value=empty: value)
        response = h.handler(_create_event(), None)
        assert response["statusCode"] == 409
        assert json.loads(response["body"])["error"] == "DELIVERY_DETAILS_REQUIRED"
    assert fake.all_rows(ATTEMPTS_TABLE) == []


def test_a_cart_wix_still_refuses_to_price_yields_no_attempt(env):
    """The unmodified live response: real `ERROR` violations, so no quote.

    Asserted end to end through the handler, not just at the adapter, because the failure that
    matters is a customer being charged — and that can only happen here.
    """
    h, fake, _lam, _wix, monkeypatch = env
    monkeypatch.setattr(h, "_wix_request", RecordingWix(live()))
    monkeypatch.setattr(h.wix_ecom, "_request", RecordingWix(live()))
    response = h.handler(_create_event(), None)

    assert response["statusCode"] == 409
    assert json.loads(response["body"])["error"] == "DELIVERY_DETAILS_REQUIRED"
    assert fake.all_rows(ATTEMPTS_TABLE) == []


def test_the_browser_cannot_supply_an_address_or_an_amount(env):
    """Authority comes from the session and the catalogue, never the request body.

    An address a browser can set is an address an attacker can set, and here that would move the
    place of supply and so the tax.
    """
    h, fake, _lam, _wix, _mp = env
    hostile = _create_event(deliveryAddress={"state": "Maharashtra", "city": "Mumbai"},
                            amountPaise=1, amount=1, collectionPaise=1)
    body = json.loads(h.handler(hostile, None)["body"])

    assert body["amountPaise"] == TOTAL_PAYABLE_PAISE
    rows = [row for row in fake.all_rows(KEYS_TABLE) if str(row["orderId"]).startswith("PAYREF#")]
    # The frozen address is the owned West Bengal one, so the fee GST stayed intra-state.
    assert rows[0]["quoteHash"]
    assert int(rows[0]["collectionPaise"]) == COLLECTION_PAISE


# ── the gate still switches back to V1 ──────────────────────────────────────────

def test_disabling_the_gate_returns_to_the_checkout_v1_authority(env):
    """The zero-commit rollback, proven rather than documented.

    V1 is retained and reachable by one environment variable, which is why the gate was inverted
    instead of deleted.
    """
    h, _fake, _lam, wix, monkeypatch = env
    monkeypatch.setenv("WIX_CART_V2_DISABLED", "true")
    monkeypatch.setattr(h.wix_ecom, "create_checkout", lambda items, **k: {
        "id": "wix-checkout-1", "currency": "INR",
        "priceSummary": {"total": {"amount": "599.00"}},
        "lineItems": [{"productName": {"original": "Viveka"}, "quantity": 1}]})

    body = json.loads(h.handler(_create_event(), None)["body"])
    # The raw Wix total, as the retained V1 contract specifies.
    assert body["amountPaise"] == 59900
    assert not any(path.startswith("/ecom/v2/carts") for path in wix.paths())


# ── nothing here can create or place an order ───────────────────────────────────

def test_the_whole_create_path_makes_no_order_or_charging_call(env):
    """Enumerated, so "no second charge" is demonstrated rather than asserted."""
    h, _fake, _lam, wix, _mp = env
    h.handler(_create_event(), None)

    for path in wix.paths():
        lowered = path.lower()
        for forbidden in ("/ecom/v1/orders", "/ecom/v2/carts/place-order", "place-order",
                          "mark-as-completed", "add-payment", "/checkout", "capture",
                          "charge", "redirect-session"):
            assert forbidden not in lowered, f"create path reached {path}"


def test_no_customer_is_routed_to_a_wix_hosted_checkout(env):
    """This is a headless architecture: Wix prices, Razorpay collects on our own site.

    A Get Checkout URL or a redirect session would hand the customer to a Wix payment surface,
    which is explicitly not the design.
    """
    h, _fake, _lam, wix, _mp = env
    response = h.handler(_create_event(), None)
    serialized = json.dumps(response)

    for marker in ("wixapis.com/_api/redirects", "checkoutUrl", "redirectSession",
                   "wix.com/checkout"):
        assert marker not in serialized
    assert all("redirect" not in path.lower() for path in wix.paths())


def test_initiation_stays_disabled_so_no_payable_message_goes_out(env):
    h, _fake, lam, _wix, _mp = env
    body = json.loads(h.handler(_create_event(), None)["body"])
    assert body["status"] == "PAYMENT_INITIATION_DISABLED"


# ── the two V1 behaviours, surfaced distinguishably through the handler ──────────

def _fixture(name):
    return json.loads((FIXTURES / f"wix_cart_v2_{name}.json").read_text())


@pytest.mark.parametrize("name,error", [
    ("out_of_stock", "ITEMS_UNAVAILABLE"),
    ("removed_from_catalog", "ITEMS_UNAVAILABLE"),
    ("quantity_reduced", "QUANTITY_REDUCED"),
])
def test_stock_problems_get_their_own_actionable_response(env, name, error):
    """Three distinct customer situations, three distinct answers, and no attempt in any of them.

    Checkout V1 would have priced around the first two and silently accepted the third. Each needs
    something different from the customer, so collapsing them into one generic 409 would be a
    usability loss on top of a correctness one.
    """
    h, fake, _lam, _wix, monkeypatch = env
    wix = RecordingWix(_fixture(name))
    monkeypatch.setattr(h, "_wix_request", wix)
    monkeypatch.setattr(h.wix_ecom, "_request", wix)

    response = h.handler(_create_event(), None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 409
    assert body["error"] == error
    assert body["items"], "the response must name what to fix"
    assert fake.all_rows(ATTEMPTS_TABLE) == []


def test_a_silently_reduced_quantity_does_not_become_a_charge(env):
    """The fixture's money reconciles perfectly; only requested-vs-confirmed reveals the problem."""
    h, fake, _lam, _wix, monkeypatch = env
    wix = RecordingWix(_fixture("quantity_reduced"))
    monkeypatch.setattr(h, "_wix_request", wix)
    monkeypatch.setattr(h.wix_ecom, "_request", wix)

    body = json.loads(h.handler(_create_event(), None)["body"])
    assert body["items"][0]["requestedQuantity"] == 3
    assert body["items"][0]["confirmedQuantity"] == 1
    assert "amountPaise" not in body
    assert fake.all_rows(ATTEMPTS_TABLE) == []


def test_a_coupon_discounted_cart_prices_and_reconciles_through_the_handler(env):
    """End to end with a coupon: the charged amount is the discounted collection plus fee and GST."""
    h, fake, _lam, _wix, monkeypatch = env
    wix = RecordingWix(_fixture("coupon_applied"))
    monkeypatch.setattr(h, "_wix_request", wix)
    monkeypatch.setattr(h.wix_ecom, "_request", wix)

    body = json.loads(h.handler(_create_event(), None)["body"])
    rows = [row for row in fake.all_rows(KEYS_TABLE) if str(row["orderId"]).startswith("PAYREF#")]
    collection = int(rows[0]["collectionPaise"])

    assert collection == 2299900                      # 24999.00 - 2500.00 + 500.00
    assert collection < COLLECTION_PAISE              # the coupon really did reduce it
    assert body["amountPaise"] > collection           # fee and its GST were added on top
    assert body["amountPaise"] == int(rows[0]["amountPaise"])
