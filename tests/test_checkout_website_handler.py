"""HTTP checkout handler wiring for website Razorpay Standard Checkout."""

import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeDynamo  # noqa: E402
from lambda_utils.ecommerce.checkout_pricing import compute_quote  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HANDLER_PATH = ROOT / "amplify/functions/ecommerce/checkout/handler.py"

ATTEMPTS = "stack-wecare-digital-PaymentAttemptsTable"
KEYS = "stack-wecare-digital-WixOrderIds"
CONTACTS = "stack-wecare-digital-ContactsTable"
CUSTOMER = "CUS_01J0000000000000000000000"
PHONE = "+919330994400"


class Identity:
    def __init__(self, customer_id=CUSTOMER, phone=PHONE):
        self.customer_id = customer_id
        self.phone = phone
        self.subject = "sub-fixture"

    def owns(self, value):
        return bool(value) and value == self.customer_id


def _checkout():
    return {
        "id": "wix-checkout-web",
        "currency": "INR",
        "priceSummary": {"total": {"amount": "599.00"}},
        "lineItems": [{"productName": {"original": "Viveka"}, "quantity": 1}],
    }


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("PAYMENT_ATTEMPTS_TABLE", ATTEMPTS)
    monkeypatch.setenv("COMMERCE_KEYS_TABLE", KEYS)
    monkeypatch.setenv("CONTACTS_TABLE", CONTACTS)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("WIX_CART_V2_ENABLED", raising=False)
    monkeypatch.delenv("WIX_CART_V2_DISABLED", raising=False)

    spec = importlib.util.spec_from_file_location("checkout_website_handler_under_test", HANDLER_PATH)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)

    fake = FakeDynamo(
        keys={ATTEMPTS: "paymentAttemptId", KEYS: "orderId", CONTACTS: "id"},
        indexes={CONTACTS: {"phone-index": ("phone", None)}},
    )
    monkeypatch.setattr(h, "_dynamodb", fake)
    monkeypatch.setattr(h.customer_auth, "require_customer",
                        lambda event: (Identity(), None))
    monkeypatch.setattr(h.wix_ecom, "create_checkout", lambda items, **kwargs: _checkout())
    monkeypatch.setattr(h, "INITIATION_ENABLED", False)
    return h, fake, monkeypatch


def event(action, **body):
    return {
        "requestContext": {"http": {"method": "POST", "sourceIp": "203.0.113.8"}},
        "headers": {"origin": "http://localhost:3000", "authorization": "Bearer fixture"},
        "body": json.dumps({"action": action, **body}),
    }


def line_items():
    return [{"catalogReference": {"catalogItemId": "p1"}, "quantity": 1}]


def profile(fake, *, customer=CUSTOMER, email="asha@example.com"):
    fake.Table(CONTACTS).put_item(Item={
        "id": "contact-1",
        "contactId": "contact-1",
        "phone": PHONE,
        "email": email,
        "name": "Asha Sen",
        "checkoutCustomerId": customer,
        "emailVerifiedAt": 1,
        "deletedAt": None,
    })


def test_prepare_requires_verified_crm_profile(env):
    h, fake, _ = env
    resp = h.handler(event(
        "prepare", lineItems=line_items(), requestKey="request-fixture-1"), None)
    assert resp["statusCode"] == 409
    assert json.loads(resp["body"])["error"] == "PROFILE_REQUIRED"
    assert fake.count(ATTEMPTS) == 0


def test_disabled_gate_never_calls_razorpay(env):
    h, fake, monkeypatch = env
    profile(fake)
    monkeypatch.setattr(
        h.razorpay_orders, "create_order",
        lambda **kwargs: pytest.fail("disabled website gate must not create a Razorpay order"),
    )
    resp = h.handler(event(
        "prepare", lineItems=line_items(), requestKey="request-fixture-2",
        amountPaise=1, currency="USD"), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "PAYMENT_INITIATION_DISABLED"
    assert fake.count(ATTEMPTS) == 0


# ── the Cart V2 harness these three prepare/verify rows now need ───────────────
#
# `_website_snapshot` REFUSES the Checkout V1 branch when the initiation gate is on, because V1
# mints a NEW Wix checkout id per prepare (`wix_ecom.create_checkout` is a create, not a resolve)
# so the one-live-payment-per-basket guard has no stable cart identity to key on. These rows drive
# a REAL prepare with the gate on, so they have to go through Cart V2, which is the serving path
# on the live function anyway (`WIX_CART_V2_ENABLED=true` on `wecare-checkout`).
#
# The fixtures and the stub shape are the ones `tests/test_checkout_cart_v2_authority.py` already
# owns, reused rather than re-derived so the two files cannot disagree about what a calculate
# response looks like.
FIXTURES = ROOT / "tests/fixtures"
#: Wix collection 25499.00 = items 24999.00 + delivery 500.00, from the shared fixture.
V2_COLLECTION_PAISE = 2549900
OWNED_ADDRESS = {"addressLine1": "12 Dalhousie Square", "city": "Kolkata",
                 "state": "West Bengal", "postalCode": "700001"}


def _delivery_complete():
    return json.loads((FIXTURES / "wix_cart_v2_delivery_complete.json").read_text())


class _RecordingWix:
    """Replays a Cart V2 calculate response and records every call."""

    def __init__(self):
        self.response = _delivery_complete()
        self.calls = []

    def __call__(self, endpoint, method="GET", body=None):
        self.calls.append((method.upper(), endpoint))
        if endpoint.startswith("/stores/v3/products/"):
            reference = self.response["cart"]["lineItems"][0]["source"]["catalogReference"]
            return {"product": {
                "id": reference["catalogItemId"], "visible": True,
                "variantsInfo": {"variants": [{
                    "id": reference["options"]["variantId"], "visible": True,
                    "inventoryStatus": {"inStock": True}}]}}}
        return copy.deepcopy(self.response)

    def paths(self):
        return [path for _method, path in self.calls]


def enable_cart_v2(h, monkeypatch):
    """Switch the handler onto the Cart V2 price authority and stub its Wix transport."""
    monkeypatch.setenv("WIX_CART_V2_ENABLED", "true")
    monkeypatch.delenv("WIX_CART_V2_DISABLED", raising=False)
    wix = _RecordingWix()
    monkeypatch.setattr(h, "_wix_request", wix)
    monkeypatch.setattr(h.wix_ecom, "_request", wix)
    monkeypatch.setattr(h, "LOAD_OWNED_ADDRESS", lambda customer_id: dict(OWNED_ADDRESS))
    return wix


def v2_line_items():
    reference = _delivery_complete()["cart"]["lineItems"][0]["source"]["catalogReference"]
    return [{"catalogReference": {"appId": reference["appId"],
                                  "catalogItemId": reference["catalogItemId"],
                                  "options": {"variantId": reference["options"]["variantId"]}},
             "quantity": 1}]


def test_prepare_uses_wix_plus_central_fee_not_browser_money(env):
    h, fake, monkeypatch = env
    profile(fake)
    monkeypatch.setattr(h, "INITIATION_ENABLED", True)
    enable_cart_v2(h, monkeypatch)

    created = {}
    def create_order(*, amount_paise, receipt, notes):
        created.update(amount=amount_paise, receipt=receipt, notes=dict(notes))
        return {
            "id": "order-handler-1",
            "amount": amount_paise,
            "currency": "INR",
            "status": "created",
            "receipt": receipt,
            "key_id": "fixture-live-publishable",
        }

    monkeypatch.setattr(h.razorpay_orders, "create_order", create_order)
    monkeypatch.setattr(h.razorpay_orders, "find_order_by_receipt", lambda receipt: None)
    monkeypatch.setattr(h.razorpay_orders, "account_mode", lambda key_id: "live")

    resp = h.handler(event(
        "prepare", lineItems=v2_line_items(), requestKey="request-fixture-3",
        amountPaise=1, currency="USD"), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "CHECKOUT_OPTIONS_READY"

    expected = compute_quote(V2_COLLECTION_PAISE).total_payable_paise
    assert created["amount"] == expected
    assert body["options"]["amountPaise"] == expected
    assert body["options"]["currency"] == "INR"
    assert body["options"]["prefill"] == {
        "name": "Asha Sen",
        "email": "asha@example.com",
        "contact": PHONE,
    }
    assert "key_secret" not in body["options"]

    attempts = fake.all_rows(ATTEMPTS)
    assert len(attempts) == 1
    assert attempts[0]["customerId"] == CUSTOMER
    assert attempts[0]["providerOrderId"] == "order-handler-1"
    assert attempts[0]["checkoutMode"] == "WEBSITE_RAZORPAY_STANDARD"


def test_verified_callback_requires_owned_attempt_and_authoritative_capture(env):
    h, fake, monkeypatch = env
    profile(fake)
    monkeypatch.setattr(h, "INITIATION_ENABLED", True)
    enable_cart_v2(h, monkeypatch)
    expected = compute_quote(V2_COLLECTION_PAISE).total_payable_paise

    monkeypatch.setattr(h.razorpay_orders, "create_order", lambda **kwargs: {
        "id": "order-handler-verify",
        "amount": kwargs["amount_paise"],
        "currency": "INR",
        "status": "created",
        "receipt": kwargs["receipt"],
        "key_id": "fixture-live-publishable",
    })
    monkeypatch.setattr(h.razorpay_orders, "find_order_by_receipt", lambda receipt: None)
    monkeypatch.setattr(h.razorpay_orders, "account_mode", lambda key_id: "live")
    prepared = h.handler(event(
        "prepare", lineItems=v2_line_items(), requestKey="request-fixture-4"), None)
    assert json.loads(prepared["body"])["status"] == "CHECKOUT_OPTIONS_READY"

    monkeypatch.setattr(h.razorpay_orders, "verify_checkout_signature", lambda **kwargs: True)
    monkeypatch.setattr(
        h.razorpay_verify, "verifier_for_event",
        lambda **kwargs: (lambda reference: (True, "payment-handler-1", expected, "INR")),
    )

    verified = h.handler(event(
        "verify",
        razorpay_order_id="order-handler-verify",
        razorpay_payment_id="payment-handler-1",
        razorpay_signature="fixture-signature",
    ), None)
    assert verified["statusCode"] == 200
    body = json.loads(verified["body"])
    assert body["status"] == "VERIFIED_PAID"

    attempt = fake.all_rows(ATTEMPTS)[0]
    assert attempt["status"] == "PAYMENT_PAID"
    assert attempt["providerPaymentId"] == "payment-handler-1"
    assert attempt["providerOrderId"] == "order-handler-verify"


def test_signature_valid_but_not_captured_does_not_mark_paid(env):
    h, fake, monkeypatch = env
    profile(fake)
    monkeypatch.setattr(h, "INITIATION_ENABLED", True)
    enable_cart_v2(h, monkeypatch)

    monkeypatch.setattr(h.razorpay_orders, "create_order", lambda **kwargs: {
        "id": "order-handler-pending",
        "amount": kwargs["amount_paise"],
        "currency": "INR",
        "status": "created",
        "receipt": kwargs["receipt"],
        "key_id": "fixture-live-publishable",
    })
    monkeypatch.setattr(h.razorpay_orders, "find_order_by_receipt", lambda receipt: None)
    monkeypatch.setattr(h.razorpay_orders, "account_mode", lambda key_id: "live")
    h.handler(event(
        "prepare", lineItems=v2_line_items(), requestKey="request-fixture-5"), None)

    monkeypatch.setattr(h.razorpay_orders, "verify_checkout_signature", lambda **kwargs: True)
    monkeypatch.setattr(
        h.razorpay_verify, "verifier_for_event",
        lambda **kwargs: (lambda reference: (False, "", 0, "")),
    )
    resp = h.handler(event(
        "verify",
        razorpay_order_id="order-handler-pending",
        razorpay_payment_id="payment-handler-pending",
        razorpay_signature="fixture-signature",
    ), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["status"] == "NOT_CAPTURED"
    assert fake.all_rows(ATTEMPTS)[0]["status"] != "PAYMENT_PAID"


def test_callback_for_another_customer_is_opaque_401(env):
    h, fake, monkeypatch = env
    profile(fake)
    monkeypatch.setattr(h, "INITIATION_ENABLED", True)
    enable_cart_v2(h, monkeypatch)
    monkeypatch.setattr(h.razorpay_orders, "create_order", lambda **kwargs: {
        "id": "order-handler-owner",
        "amount": kwargs["amount_paise"],
        "currency": "INR",
        "status": "created",
        "receipt": kwargs["receipt"],
        "key_id": "fixture-live-publishable",
    })
    monkeypatch.setattr(h.razorpay_orders, "find_order_by_receipt", lambda receipt: None)
    monkeypatch.setattr(h.razorpay_orders, "account_mode", lambda key_id: "live")
    h.handler(event(
        "prepare", lineItems=v2_line_items(), requestKey="request-fixture-6"), None)

    monkeypatch.setattr(h.customer_auth, "require_customer",
                        lambda event: (Identity(customer_id="CUS_other"), None))
    resp = h.handler(event(
        "verify",
        razorpay_order_id="order-handler-owner",
        razorpay_payment_id="payment-other",
        razorpay_signature="fixture-signature",
    ), None)
    assert resp["statusCode"] == 401
