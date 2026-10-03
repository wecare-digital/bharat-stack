"""The money-correctness invariants this graft exists to hold, as executable assertions.

Why one file rather than rows spread across the existing suites
---------------------------------------------------------------
Every assertion here is about a property that spans more than one module: "a payable modal always
has paid memory behind it" touches `website_checkout`, `order_keys` and `checkout_pricing`; "only
the verified Razorpay leg reaches Wix" touches `finalization`, `wix_writeback` and the handler.
Filing each row under the module it happens to call first would scatter one invariant across four
files and make a regression look like four unrelated failures.

The fake is `coupon_fake_dynamo.FakeTable` throughout, deliberately: it evaluates `OR` and
parenthesised conditions, which every conditional claim in this change depends on.
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys
import time
from decimal import Decimal

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))
sys.path.insert(0, str(ROOT / "tests"))

from coupon_fake_dynamo import FakeClientError, FakeTable  # noqa: E402
from crm_fake_dynamo import FakeDynamo as CrmFakeDynamo  # noqa: E402
from lambda_utils.ecommerce import checkout_pricing as cp  # noqa: E402
from lambda_utils.ecommerce import order_keys  # noqa: E402
from lambda_utils.ecommerce import payment_attempt  # noqa: E402
from lambda_utils.ecommerce import purchase_intent  # noqa: E402
from lambda_utils.ecommerce import website_checkout  # noqa: E402
from lambda_utils.ecommerce import wix_writeback  # noqa: E402

KEYS_TABLE = "stack-wecare-digital-WixOrderIds"
ATTEMPTS_TABLE = "stack-wecare-digital-PaymentAttemptsTable"
ORDERS_TABLE = "stack-wecare-digital-OrderTable"
CUSTOMER = "CUS_graft_001"
CART = "11111111-2222-3333-4444-555555555555"
COLLECTION_PAISE = 100000


def _keys():
    """The commerce-keys table, whose partition attribute is `orderId` for every prefix."""
    return FakeTable(key_attr="orderId")


def _frozen(*, cart_id=CART, revision=1, line_quantity=1, redeem_paise=0,
            gift_card_id="", extra_line_field=None, items=None):
    """A frozen snapshot payload in `_snapshot_payload`'s exact shape."""
    quote = cp.compute_quote(COLLECTION_PAISE)
    if items is None:
        line = {"lineItemId": "line-1", "quantity": line_quantity,
                "totalPrice": {"amount": "1000.00"}}
        if extra_line_field is not None:
            # A field this build does NOT enumerate, standing in for the per-calculate residue
            # `basket_hash` cannot vouch for.
            line["physicalProperties"] = extra_line_field
        items = [line]
    payload = {
        "customer": CUSTOMER,
        "site": "site-1",
        "cart": {"id": cart_id, "revision": revision},
        "items": items,
        "address": {"city": "Kolkata"},
        "delivery": {"title": "Standard"},
        "components": quote.components(),
        "policyVersion": quote.policy_version,
        "payment": {
            "wixGiftCard": {"giftCardId": gift_card_id} if gift_card_id else None,
            "wixGiftCardRedeemPaise": int(redeem_paise),
            "wixPayNowPaise": quote.total_payable_paise - int(redeem_paise),
        },
    }
    return payload


# ── step 3: the three cart row families ────────────────────────────────────────

def test_the_cart_pointer_upsert_cannot_erase_a_paid_basket():
    """The single-slot pointer is upserted; the per-basket row is not reachable from that write.

    This is the iteration-5 hole in one assertion: paying basket B1 and then opening a different
    basket B2 on the same 30-day cart re-points `CARTPAYMENT#`, and the only surviving record that
    B1 was paid must be its own `CARTBASKET#` row.
    """
    table = _keys()
    b1, b2 = "hash_b1", "hash_b2"
    order_keys.record_cart_payment(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                   payment_attempt_id="A1", basket_hash=b1)
    order_keys.record_cart_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                  basket_hash=b1, payment_attempt_id="A1")
    # A later, genuinely different basket takes the single slot.
    order_keys.record_cart_payment(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                   payment_attempt_id="A2", basket_hash=b2)
    order_keys.record_cart_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                  basket_hash=b2, payment_attempt_id="A2")

    pointer = order_keys.resolve_cart_payment(table, customer_id=CUSTOMER, wix_cart_id=CART)
    assert pointer["paymentAttemptId"] == "A2", "the pointer is last-writer-wins, by design"
    survived = order_keys.resolve_cart_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                              basket_hash=b1)
    assert survived is not None and survived["paymentAttemptId"] == "A1", (
        "the paid memory for B1 must survive a later attempt on the same cart")


def test_the_narrow_paid_row_resolves_when_the_fine_one_cannot():
    """Keyed on two identities, so a `basket_hash` that moved is still refused by the narrow key."""
    table = _keys()
    order_keys.record_cart_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                  basket_hash="fine_v1", payment_attempt_id="A1",
                                  narrow_basket_hash="narrow_stable")
    order_keys.record_cart_narrow_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                         narrow_hash="narrow_stable", payment_attempt_id="A1",
                                         basket_hash="fine_v1")
    # Wix moved a non-enumerated field, so the fine identity composes a different key.
    assert order_keys.resolve_cart_basket(
        table, customer_id=CUSTOMER, wix_cart_id=CART, basket_hash="fine_v2") is None
    found = order_keys.resolve_cart_narrow_basket(
        table, customer_id=CUSTOMER, wix_cart_id=CART, narrow_hash="narrow_stable")
    assert found is not None and found["paymentAttemptId"] == "A1"


def test_a_recorded_basket_row_is_never_taken_over_by_a_stale_claim():
    """A RECORDED row cannot be claimed however old it is. Its failure mode is a second charge."""
    table = _keys()
    long_ago = int(time.time()) - 10 * 365 * 24 * 3600
    order_keys.record_cart_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                  basket_hash="b1", payment_attempt_id="A_PAID", now=long_ago)
    won = order_keys.claim_cart_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                       basket_hash="b1", payment_attempt_id="A_NEW")
    assert won is False, "a recorded row has an attempt behind it and is never stale"
    row = order_keys.resolve_cart_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                         basket_hash="b1")
    assert row["paymentAttemptId"] == "A_PAID"


@pytest.mark.parametrize("prefix", ["basket", "narrow"])
def test_a_stale_create_claim_releases_after_the_create_horizon(prefix):
    """Both halves: inside the horizon the claim holds; past it a later click may take it."""
    table = _keys()
    now = int(time.time())
    claim = (order_keys.claim_cart_basket if prefix == "basket"
             else order_keys.claim_cart_narrow_basket)
    kwargs = ({"basket_hash": "b1"} if prefix == "basket" else {"narrow_hash": "n1"})

    assert claim(table, customer_id=CUSTOMER, wix_cart_id=CART,
                 payment_attempt_id="A1", now=now, **kwargs) is True
    # Inside the horizon, with no CAS basis: the first claimer still holds it.
    assert claim(table, customer_id=CUSTOMER, wix_cart_id=CART,
                 payment_attempt_id="A2", now=now + 10, **kwargs) is False
    # Past it, a dead claimer's slot is available again.
    assert claim(table, customer_id=CUSTOMER, wix_cart_id=CART, payment_attempt_id="A3",
                 now=now + order_keys.CART_CREATE_CLAIM_STALE_SECONDS + 1,
                 **kwargs) is True


def test_a_claim_with_a_matching_cas_basis_repoints_a_failed_attempt():
    """The legitimate retry: the guard read A1 off the row, so A1 is the condition."""
    table = _keys()
    assert order_keys.claim_cart_basket(table, customer_id=CUSTOMER, wix_cart_id=CART,
                                        basket_hash="b1", payment_attempt_id="A1") is True
    assert order_keys.claim_cart_basket(
        table, customer_id=CUSTOMER, wix_cart_id=CART, basket_hash="b1",
        payment_attempt_id="A2", prior_payment_attempt_id="A1") is True
    assert order_keys.claim_cart_basket(
        table, customer_id=CUSTOMER, wix_cart_id=CART, basket_hash="b1",
        payment_attempt_id="A3", prior_payment_attempt_id="A1") is False, (
        "the row moved, so the compare-and-swap must fail")


@pytest.mark.parametrize("builder,kwargs", [
    (order_keys.record_cart_basket, {"basket_hash": ""}),
    (order_keys.record_cart_narrow_basket, {"narrow_hash": ""}),
])
def test_an_empty_key_part_raises_rather_than_composing_a_colliding_key(builder, kwargs):
    with pytest.raises(ValueError):
        builder(_keys(), customer_id=CUSTOMER, wix_cart_id=CART,
                payment_attempt_id="A1", **kwargs)


def test_a_read_failure_is_never_reported_as_absence():
    """Absence is the dangerous answer: the caller acts on it by creating a payable order."""
    class Raising:
        def get_item(self, **_):
            raise FakeClientError("ProvisionedThroughputExceededException")

    with pytest.raises(order_keys.OrderIdentityUnavailable):
        order_keys.resolve_cart_basket(Raising(), customer_id=CUSTOMER, wix_cart_id=CART,
                                       basket_hash="b1")
    with pytest.raises(order_keys.OrderIdentityUnavailable):
        order_keys.resolve_cart_narrow_basket(Raising(), customer_id=CUSTOMER,
                                              wix_cart_id=CART, narrow_hash="n1")
    with pytest.raises(order_keys.OrderIdentityUnavailable):
        order_keys.resolve_cart_payment(Raising(), customer_id=CUSTOMER, wix_cart_id=CART)


def test_a_throttled_claim_is_never_mistaken_for_a_free_slot():
    class Raising:
        def put_item(self, **_):
            raise FakeClientError("ThrottlingException")

    with pytest.raises(order_keys.OrderIdentityUnavailable):
        order_keys.claim_cart_narrow_basket(Raising(), customer_id=CUSTOMER, wix_cart_id=CART,
                                            narrow_hash="n1", payment_attempt_id="A1")


def test_no_cart_row_writer_ever_deletes():
    """The rows are evidence that money moved for a basket. No `DeleteItem`, and none granted."""
    source = (ROOT / "amplify/functions/shared/lambda_utils/ecommerce/order_keys.py"
              ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "cart" not in node.name:
            continue
        for inner in ast.walk(node):
            if (isinstance(inner, ast.Attribute) and inner.attr == "delete_item"):
                offenders.append(node.name)
    assert offenders == [], f"a cart row writer calls delete_item: {offenders}"


def test_is_conditional_failure_is_public_and_classifies():
    assert "is_conditional_failure" in order_keys.__all__
    assert order_keys.is_conditional_failure(
        FakeClientError("ConditionalCheckFailedException")) is True
    assert order_keys.is_conditional_failure(FakeClientError("ThrottlingException")) is False
    assert order_keys.is_conditional_failure(RuntimeError("no response attribute")) is False
    # The private alias is kept for the six internal call sites.
    assert order_keys._is_conditional_failure is order_keys.is_conditional_failure


def test_resolve_checkout_request_key_reads_the_row_reserve_wrote():
    table = _keys()
    order_keys.reserve_checkout_request_key(
        table, customer_id=CUSTOMER, request_key="K1",
        intent_fingerprint="fp", payment_attempt_id="A1")
    row = order_keys.resolve_checkout_request_key(
        table, customer_id=CUSTOMER, request_key="K1")
    assert row is not None and row["paymentAttemptId"] == "A1"
    assert order_keys.resolve_checkout_request_key(
        table, customer_id=CUSTOMER, request_key="K_absent") is None


def test_every_new_cart_surface_is_exported():
    for name in ("CART_PAYMENT_PREFIX", "CART_PAYMENT_KIND", "CART_BASKET_PREFIX",
                 "CART_BASKET_KIND", "CART_NARROW_BASKET_PREFIX", "CART_NARROW_BASKET_KIND",
                 "resolve_cart_payment", "record_cart_payment", "resolve_cart_basket",
                 "record_cart_basket", "claim_cart_basket", "resolve_cart_narrow_basket",
                 "record_cart_narrow_basket", "claim_cart_narrow_basket",
                 "resolve_checkout_request_key"):
        assert name in order_keys.__all__, name


# ── step 4: the two basket identities ──────────────────────────────────────────

def test_the_basket_hash_ignores_only_the_revision():
    """Both halves. The negative row matters more: a hash that dropped too much refuses forever."""
    base = _frozen(revision=1)
    bumped = _frozen(revision=7)
    assert cp._stable_hash(base) != cp._stable_hash(bumped), (
        "anti-vacuity: the quote hash MUST move when the revision moves")
    assert cp.basket_hash(base) == cp.basket_hash(bumped), "the revision is the one term dropped"

    # Negative half: everything else still changes the identity.
    for different in (_frozen(line_quantity=2), _frozen(redeem_paise=5000),
                      _frozen(cart_id="99999999-2222-3333-4444-555555555555")):
        assert cp.basket_hash(base) != cp.basket_hash(different)
    moved_address = _frozen()
    moved_address["address"] = {"city": "Delhi"}
    assert cp.basket_hash(base) != cp.basket_hash(moved_address), (
        "the address is part of the FINE identity; changing it changes what is paid")


def test_the_basket_hash_refuses_a_cartless_payload():
    with pytest.raises(cp.PricingError):
        cp.basket_hash({"items": []})
    with pytest.raises(cp.PricingError):
        cp.basket_hash("not a mapping")
    with pytest.raises(cp.PricingError):
        cp.basket_hash({"cart": {"id": ""}})


def test_the_narrow_basket_hash_covers_only_contract_checked_terms():
    base = _frozen()
    # POSITIVE half: a field nobody enumerated moved, and the narrow identity is unchanged.
    residue = _frozen(extra_line_field={"weight": 1.5 and "1.5"})
    assert cp.basket_hash(base) != cp.basket_hash(residue), (
        "anti-vacuity: the FINE identity must move, or this test proves nothing")
    assert cp.narrow_basket_hash(base) == cp.narrow_basket_hash(residue)
    moved_address = _frozen()
    moved_address["address"] = {"city": "Delhi"}
    assert cp.narrow_basket_hash(base) == cp.narrow_basket_hash(moved_address), (
        "the narrow identity deliberately ignores the address")

    # NEGATIVE half: every enumerated term still changes it.
    for different in (_frozen(line_quantity=2),
                      _frozen(redeem_paise=5000),
                      _frozen(gift_card_id="gc_1"),
                      _frozen(cart_id="99999999-2222-3333-4444-555555555555")):
        assert cp.narrow_basket_hash(base) != cp.narrow_basket_hash(different)


def test_the_narrow_basket_hash_ignores_line_order_but_not_line_identity():
    one = _frozen(items=[{"lineItemId": "a", "quantity": 1},
                         {"lineItemId": "b", "quantity": 2}])
    reordered = _frozen(items=[{"lineItemId": "b", "quantity": 2},
                               {"lineItemId": "a", "quantity": 1}])
    assert cp.narrow_basket_hash(one) == cp.narrow_basket_hash(reordered)
    requantified = _frozen(items=[{"lineItemId": "a", "quantity": 1},
                                  {"lineItemId": "b", "quantity": 3}])
    assert cp.narrow_basket_hash(one) != cp.narrow_basket_hash(requantified)


@pytest.mark.parametrize("items", [None, [], "not a list", [{"quantity": 1}], [42]])
def test_the_narrow_basket_hash_answers_empty_when_it_cannot_name_the_lines(items):
    payload = _frozen()
    payload["items"] = items
    assert cp.narrow_basket_hash(payload) == "", (
        "an empty narrow hash means 'no narrow identity available', which the guard falls back on")


def test_both_identities_survive_a_dynamodb_round_trip():
    """Ints come back as integral `Decimal`s. `_canonical` folds them, so the hashes must match."""
    payload = _frozen()
    round_tripped = json.loads(json.dumps(payload))

    def decimalise(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, dict):
            return {key: decimalise(inner) for key, inner in value.items()}
        if isinstance(value, list):
            return [decimalise(inner) for inner in value]
        return value

    stored = decimalise(round_tripped)
    assert cp.basket_hash(payload) == cp.basket_hash(stored)
    assert cp.narrow_basket_hash(payload) == cp.narrow_basket_hash(stored)


def test_the_existing_snapshot_hash_is_unchanged_by_the_additions():
    """`_snapshot_payload` and `build_snapshot` must be byte-identical in behaviour."""
    quote = cp.compute_quote(COLLECTION_PAISE)
    snapshot = cp.build_snapshot(
        customer_id=CUSTOMER, cart_id=CART, cart_revision=1, quote=quote,
        created_at=1_700_000_000, ttl_seconds=900, items=[{"lineItemId": "line-1",
                                                           "quantity": 1}])
    assert snapshot.snapshot_hash == cp._stable_hash(snapshot.frozen_data)
    assert "payment" not in snapshot.frozen_data, (
        "an omitted payment block must stay omitted, or every pre-existing hash moves")


# ── step 5: the Wix order payload, from the frozen quote ───────────────────────

def _calculated():
    return {
        "cart": {
            "lineItems": [{
                "id": "line-1",
                "name": {"original": "Thing"},
                "source": {"catalogReference": {"catalogItemId": "prod-1"}},
                "quantityInfo": {"confirmedQuantity": 2},
            }],
            "deliveryInfo": {"method": {"title": "Standard"},
                             "address": {"city": "Kolkata"}},
        },
        "summary": {
            "priceSummary": {"subtotal": {"amount": "1000.00"},
                             "discount": {"amount": "0.00"},
                             "delivery": {"amount": "0.00"},
                             "tax": {"amount": "0.00"}},
            "additionalFees": [],
            "lineItems": [{"lineItemId": "line-1", "quantity": 2,
                           "unitPrice": {"amount": "500.00"},
                           "totalPrice": {"amount": "1000.00"}}],
        },
    }


def test_the_wix_payload_relays_wix_money_and_adds_only_our_fee():
    quote = cp.compute_quote(COLLECTION_PAISE)
    payload = wix_writeback.build_wix_order_payload(cart=_calculated(), quote=quote)
    assert payload["currency"] == "INR"
    fees = [fee for fee in payload["additionalFees"]
            if fee["code"] == wix_writeback.CONVENIENCE_FEE_CODE]
    assert len(fees) == 1
    assert fees[0]["priceBeforeTax"] == {"amount": "25.00"}, "2.5% of 1000.00, exact"
    assert fees[0]["price"] == {"amount": "29.50"}, "fee plus 18% GST on the fee, exact"
    assert payload["priceSummary"]["subtotal"] == {"amount": "1000.00"}, "relayed verbatim"
    assert payload["priceSummary"]["total"] == {"amount": "1029.50"}
    assert payload["lineItems"][0]["catalogReference"] == {"catalogItemId": "prod-1"}
    assert payload["lineItems"][0]["quantity"] == 2


def test_the_wix_payload_compares_currency_explicitly():
    class NotInr:
        currency = "USD"

    with pytest.raises(ValueError):
        wix_writeback.build_wix_order_payload(cart=_calculated(), quote=NotInr())


def test_the_wix_payload_refuses_a_float_money_component():
    with pytest.raises(TypeError):
        wix_writeback._paise_money(100.0)
    with pytest.raises(TypeError):
        wix_writeback._paise_money(True)
    assert wix_writeback._paise_money(100) == {"amount": "1.00"}


# ── step 6: the calculation is exposed, not recomputed ─────────────────────────

class _CountingAdapter:
    """Counts `calculate` calls. One per checkout is the contract."""

    def __init__(self):
        self.calls = 0

    def calculate(self, cart_id):
        self.calls += 1
        calculated = _calculated()
        calculated.update({
            "currency": "INR", "amountPaise": COLLECTION_PAISE, "wixCartId": CART,
            "cartRevision": 3, "deliveryAddress": {"city": "Kolkata"},
            "deliveryMethod": {"title": "Standard"},
            "wixGiftCard": None, "wixGiftCardRedeemPaise": 0,
            "wixPayNowPaise": cp.compute_quote(COLLECTION_PAISE).total_payable_paise,
        })
        return calculated


def test_build_intent_still_calculates_exactly_once():
    address = {"addressLine1": "12 Dalhousie Square", "city": "Kolkata",
               "state": "West Bengal", "postalCode": "700001"}

    plain = _CountingAdapter()
    snapshot_a = purchase_intent.build_intent(
        plain, customer_id=CUSTOMER, cart_id=CART, owned_address=address, now=1_700_000_000)
    assert plain.calls == 1, "build_intent must still calculate exactly once"

    both = _CountingAdapter()
    snapshot_b, calculated = purchase_intent.build_intent_with_calculation(
        both, customer_id=CUSTOMER, cart_id=CART, owned_address=address, now=1_700_000_000)
    assert both.calls == 1
    assert snapshot_a.snapshot_hash == snapshot_b.snapshot_hash, (
        "the sibling must freeze the identical snapshot")
    assert "summary" in calculated and "cart" in calculated, (
        "the calculation must come back in build_wix_order_payload's shape")

    import inspect
    parameters = inspect.signature(purchase_intent.build_intent).parameters
    for name in ("ttl_seconds", "quote_fn"):
        assert name in parameters, (
            f"{name} must stay on the public surface rather than vanish into **kwargs")


# ══ GRAFT 1a — the double-charge guard, driven through the real handler ═════════
#
# Every row below calls `_website_prepare` through `handler.handler`, not `prepare_checkout`
# directly. A test that calls the guard itself cannot detect that its only production caller
# never reaches it, which is the failure mode this whole section exists to rule out.

import copy  # noqa: E402
import importlib.util  # noqa: E402

HANDLER_PATH = ROOT / "amplify/functions/ecommerce/checkout/handler.py"
FIXTURES = ROOT / "tests/fixtures"
CONTACTS_TABLE = "stack-wecare-digital-ContactsTable"
PHONE = "+919330994400"
#: Wix collection 25499.00 = items 24999.00 + delivery 500.00, from the shared fixture.
V2_COLLECTION_PAISE = 2549900
OWNED_ADDRESS = {"addressLine1": "12 Dalhousie Square", "city": "Kolkata",
                 "state": "West Bengal", "postalCode": "700001"}

#: A PUBLIC Razorpay key id for the stub, ASSEMBLED AT RUNTIME so this file contains no
#: issuer-shaped literal. `scripts/block_inline_secrets.py` refuses an `rzp_live_` token on a
#: command line and `scripts/scan_repo_secrets.py` must keep reporting real values, so a fixture
#: that merely LOOKS like a credential is worth avoiding even when it is not one. Only the public
#: key id is ever publishable; no `key_secret` appears anywhere in this file, and a test below
#: asserts that no response or log can carry one.
FIXTURE_PUBLIC_KEY_ID = "rzp_" + "live_" + "FIXTUREPUBLICID"
#: A sentinel standing in for the secret half, used ONLY to assert it never leaves the module
#: that reads it. It is not issuer-shaped and is not a credential.
FIXTURE_SECRET_SENTINEL = "SECRET-HALF-MUST-NEVER-APPEAR"


def _delivery_complete():
    return json.loads((FIXTURES / "wix_cart_v2_delivery_complete.json").read_text())


class _Identity:
    def __init__(self, customer_id=CUSTOMER, phone=PHONE):
        self.customer_id = customer_id
        self.phone = phone
        self.subject = "sub-graft"

    def owns(self, value):
        return bool(value) and value == self.customer_id


class _MultiTable:
    """One `boto3.resource('dynamodb')` stand-in over several `coupon_fake_dynamo.FakeTable`s.

    `coupon_fake_dynamo` is the fake used here rather than `crm_fake_dynamo` because every
    conditional claim in this change is a parenthesised `OR`, and a fake that cannot evaluate one
    cannot exercise the claim.
    """

    def __init__(self, keys):
        self.tables = {name: FakeTable(key_attr=key) for name, key in keys.items()}
        # The Contacts table is the ONE table reached with a boto3 `Key('phone').eq(...)`
        # condition object rather than an expression string, which `coupon_fake_dynamo.query`
        # does not parse. `crm_fake_dynamo` reads that object's own attributes, so the profile
        # lookup gets the fake that understands it while every conditional claim keeps the fake
        # that understands a parenthesised OR.
        self._crm = CrmFakeDynamo(keys={CONTACTS_TABLE: keys[CONTACTS_TABLE]},
                                  indexes={CONTACTS_TABLE: {"phone-index": ("phone", None)}})
        self.tables[CONTACTS_TABLE] = self._crm.Table(CONTACTS_TABLE)

    def Table(self, name):  # noqa: N802 - boto3's own spelling
        if name not in self.tables:
            raise AssertionError(f"the handler reached an unprovisioned table {name!r}")
        return self.tables[name]

    def rows(self, name):
        return [dict(row) for row in self.tables[name].rows.values()]

    def keys_with_prefix(self, prefix):
        return [key for key in self.tables[KEYS_TABLE].rows if str(key).startswith(prefix)]

    def count_prefix(self, prefix):
        return len(self.keys_with_prefix(prefix))


class _Wix:
    """A Cart V2 transport whose `calculate` response can be mutated per call.

    `revision_mode` is the lever the double-charge rows turn:

      'bump'  - `summary.cartRevision` and `cart.revision` are INCREMENTED on every calculate,
                which is what the live path does (prepare PATCHes the cart, then calculate
                refreshes it) and what makes `snapshot_hash` move for an unedited basket.
      'fixed' - held constant, so the same-request-key resume is reachable at all.

    `cart_v2.calculate` asserts the two are equal, so they move together or the stub is invalid.
    """

    def __init__(self, revision_mode="bump", mutate=None):
        self.base = _delivery_complete()
        self.revision_mode = revision_mode
        self.mutate = mutate
        self.calculates = 0
        self.calls = []

    def __call__(self, endpoint, method="GET", body=None):
        self.calls.append((method.upper(), endpoint))
        if endpoint.startswith("/stores/v3/products/"):
            reference = self.base["cart"]["lineItems"][0]["source"]["catalogReference"]
            return {"product": {
                "id": reference["catalogItemId"], "visible": True,
                "variantsInfo": {"variants": [{
                    "id": reference["options"]["variantId"], "visible": True,
                    "inventoryStatus": {"inStock": True}}]}}}
        response = copy.deepcopy(self.base)
        if "calculate" in endpoint:
            self.calculates += 1
            if self.revision_mode == "bump":
                revision = str(int(response["cart"]["revision"]) + self.calculates)
                response["cart"]["revision"] = revision
                response["summary"]["cartRevision"] = revision
            if self.mutate is not None:
                self.mutate(response, self.calculates)
        return response


class _Rig:
    """A loaded handler module plus its fakes, with the Razorpay client fully stubbed."""

    def __init__(self, monkeypatch, *, revision_mode="bump", mutate=None,
                 initiation_enabled=True, keys_table=None):
        monkeypatch.setenv("PAYMENT_ATTEMPTS_TABLE", ATTEMPTS_TABLE)
        monkeypatch.setenv("COMMERCE_KEYS_TABLE", KEYS_TABLE)
        monkeypatch.setenv("CONTACTS_TABLE", CONTACTS_TABLE)
        monkeypatch.setenv("ORDERS_TABLE", ORDERS_TABLE)
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("WIX_CART_V2_ENABLED", "true")
        monkeypatch.delenv("WIX_CART_V2_DISABLED", raising=False)
        # The gate is NEVER read from the environment here: `CHECKOUT_INITIATION_ENABLED` stays
        # absent, and `INITIATION_ENABLED` is injected as a module attribute instead. Setting the
        # env key in a test would be indistinguishable from enabling the flag.
        monkeypatch.delenv("CHECKOUT_INITIATION_ENABLED", raising=False)

        spec = importlib.util.spec_from_file_location(
            "graft_handler_under_test", HANDLER_PATH)
        self.h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.h)

        self.db = _MultiTable({ATTEMPTS_TABLE: "paymentAttemptId", KEYS_TABLE: "orderId",
                               CONTACTS_TABLE: "id", ORDERS_TABLE: "orderId"})
        if keys_table is not None:
            self.db.tables[KEYS_TABLE] = keys_table
        self.wix = _Wix(revision_mode=revision_mode, mutate=mutate)
        self.creates = []
        self.checkouts = []
        self.identity = _Identity()
        self.quantity = 1

        monkeypatch.setattr(self.h, "_dynamodb", self.db)
        monkeypatch.setattr(self.h, "INITIATION_ENABLED", initiation_enabled)
        monkeypatch.setattr(self.h, "_wix_request", self.wix)
        monkeypatch.setattr(self.h.wix_ecom, "_request", self.wix)
        monkeypatch.setattr(self.h, "LOAD_OWNED_ADDRESS",
                            lambda customer_id: dict(OWNED_ADDRESS))
        monkeypatch.setattr(self.h.customer_auth, "require_customer",
                            lambda event: (self.identity, None))
        monkeypatch.setattr(self.h.wix_ecom, "create_checkout", self._create_checkout)
        monkeypatch.setattr(self.h.razorpay_orders, "create_order", self._create_order)
        monkeypatch.setattr(self.h.razorpay_orders, "find_order_by_receipt",
                            lambda receipt: None)
        monkeypatch.setattr(self.h.razorpay_orders, "account_mode", lambda key_id: "live")
        monkeypatch.setattr(self.h, "_lambda_client", self._no_lambda)
        self._profile()

    # -- stubs -----------------------------------------------------------------
    def _no_lambda(self):
        raise AssertionError("the website prepare path must make no Lambda invoke")

    def _create_checkout(self, items, **_):
        self.checkouts.append(items)
        return {"id": f"wix-checkout-{len(self.checkouts)}", "currency": "INR",
                "priceSummary": {"total": {"amount": "599.00"}},
                "lineItems": [{"productName": {"original": "Thing"}, "quantity": 1}]}

    def _create_order(self, *, amount_paise, receipt, notes):
        self.creates.append({"amount_paise": amount_paise, "receipt": receipt,
                             "notes": dict(notes)})
        return {"id": f"order_GRAFT_{len(self.creates)}", "amount": amount_paise,
                "currency": "INR", "status": "created", "receipt": receipt,
                "key_id": FIXTURE_PUBLIC_KEY_ID}

    def _profile(self):
        self.db.Table(CONTACTS_TABLE).put_item(Item={
            "id": "contact-1", "contactId": "contact-1", "phone": PHONE,
            "email": "asha@example.com", "name": "Asha Sen",
            "checkoutCustomerId": CUSTOMER, "emailVerifiedAt": 1, "deletedAt": None})

    # -- driving ---------------------------------------------------------------
    def line_items(self):
        reference = self.wix.base["cart"]["lineItems"][0]["source"]["catalogReference"]
        return [{"catalogReference": {
            "appId": reference["appId"],
            "catalogItemId": reference["catalogItemId"],
            "options": {"variantId": reference["options"]["variantId"]}},
            "quantity": self.quantity}]

    def set_quantity(self, units):
        """Change the basket COHERENTLY, so the change is the guard's subject and not a fixture bug.

        `cart_v2.calculate` contract-checks that `requestedQuantity == confirmedQuantity` (or it
        raises `CartQuantityReduced`), that the line totals sum to `priceSummary.subtotal`, and
        that `subtotal - discount + delivery + additionalFees + tax == total`. Editing one field
        in isolation breaks one of those and the handler answers 503 -- which would look like the
        guard refusing when it is the stub that is inconsistent. `_require_same_basket` also
        compares the REQUESTED quantity against what the browser asked for, so the asked quantity
        moves with it.
        """
        self.quantity = units
        base = self.wix.base
        unit_paise = int(round(float(
            base["summary"]["lineItems"][0]["unitPrice"]["amount"].replace(",", "")) * 100))
        delivery_paise = int(round(float(
            base["summary"]["priceSummary"]["delivery"]["amount"].replace(",", "")) * 100))
        line_total = unit_paise * units
        money = lambda paise: {"amount": f"{paise // 100}.{paise % 100:02d}",
                               "convertedAmount": f"{paise // 100}.{paise % 100:02d}"}
        base["cart"]["lineItems"][0]["quantityInfo"].update(
            requestedQuantity=units, confirmedQuantity=units)
        base["summary"]["lineItems"][0]["quantity"] = units
        base["summary"]["lineItems"][0]["totalPrice"] = money(line_total)
        base["summary"]["priceSummary"]["subtotal"] = money(line_total)
        base["summary"]["priceSummary"]["total"] = money(line_total + delivery_paise)
        # `paymentSummary` reconciles against the total too: with no gift card,
        # `payNow == totalAfterGiftCards == total` or `calculate` raises
        # "full immediate payment required". Updating the total and not these is the fixture
        # contradicting itself.
        payment = base["summary"].setdefault("paymentSummary", {})
        payment["payNow"] = money(line_total + delivery_paise)
        payment["totalAfterGiftCards"] = money(line_total + delivery_paise)

    def prepare(self, request_key):
        event = {
            "requestContext": {"http": {"method": "POST", "sourceIp": "203.0.113.9"}},
            "headers": {"origin": "http://localhost:3000", "authorization": "Bearer t"},
            "body": json.dumps({"action": "prepare", "lineItems": self.line_items(),
                                "requestKey": request_key}),
        }
        response = self.h.handler(event, None)
        return response["statusCode"], json.loads(response["body"])

    def verify(self, *, order_id, payment_id="pay_GRAFT_1", signature="sig"):
        event = {
            "requestContext": {"http": {"method": "POST", "sourceIp": "203.0.113.9"}},
            "headers": {"origin": "http://localhost:3000", "authorization": "Bearer t"},
            "body": json.dumps({"action": "verify", "razorpay_order_id": order_id,
                                "razorpay_payment_id": payment_id,
                                "razorpay_signature": signature}),
        }
        response = self.h.handler(event, None)
        return response["statusCode"], json.loads(response["body"])

    def age_everything(self, seconds):
        """Push every timestamp on every row back by `seconds`, to cross a window deliberately."""
        for name in (KEYS_TABLE, ATTEMPTS_TABLE):
            table = self.db.Table(name)
            for key, row in list(table.rows.items()):
                row = dict(row)
                for field in ("recordedAt", "claimedAt", "paidAt", "updatedAt", "createdAt",
                              "reservedAt", "boundAt", "createClaimedAt"):
                    if field in row and isinstance(row[field], int):
                        row[field] = row[field] - seconds
                table.rows[key] = row

    def mark_paid(self):
        """Advance every stored attempt to PAYMENT_PAID, as a verified capture would."""
        table = self.db.Table(ATTEMPTS_TABLE)
        for key, row in list(table.rows.items()):
            row = dict(row)
            row["status"] = payment_attempt.PAYMENT_PAID
            row["attemptRank"] = payment_attempt.rank(payment_attempt.PAYMENT_PAID)
            row["paidAt"] = int(time.time())
            table.rows[key] = row

    def mark_failed(self):
        """Move every UNPAID attempt into a retryable state.

        `RETRYABLE_STATES` is where `may_create_order` and `is_in_flight` are BOTH false, which is
        the state that left the pre-graft guard with no window at all.
        """
        table = self.db.Table(ATTEMPTS_TABLE)
        for key, row in list(table.rows.items()):
            if row.get("status") == payment_attempt.PAYMENT_PAID:
                continue
            row = dict(row)
            row["status"] = payment_attempt.PAYMENT_FAILED
            row["attemptRank"] = payment_attempt.rank(payment_attempt.PAYMENT_FAILED)
            table.rows[key] = row


@pytest.fixture
def rig(monkeypatch):
    def build(**kwargs):
        return _Rig(monkeypatch, **kwargs)
    return build


def _rows_with(rig_instance, prefix):
    return [row for row in rig_instance.db.rows(KEYS_TABLE)
            if str(row["orderId"]).startswith(prefix)]


# ── (a) the revision-bumped two-prepare row ────────────────────────────────────

def test_a_revision_bump_does_not_unblock_a_paid_basket(rig):
    """The row the whole guard turns on: a bumped revision must not look like a new basket.

    Assertion 1 is the ANTI-VACUITY ANCHOR. If the two prepares produced the same
    `snapshot_hash`, this test would pass against a guard keyed on `snapshot_hash` and would
    prove nothing. The stub increments `cartRevision` exactly as the live path does, so the quote
    hash MUST differ and the basket identity MUST NOT.
    """
    r = rig(revision_mode="bump")
    code_1, body_1 = r.prepare("K1")
    assert code_1 == 200 and body_1["status"] == "CHECKOUT_OPTIONS_READY"
    assert len(r.creates) == 1

    paid_attempt = r.db.rows(ATTEMPTS_TABLE)[0]["paymentAttemptId"]
    first_hash = _rows_with(r, order_keys.REQUEST_KEY_PREFIX)[0]["snapshotHash"]
    r.mark_paid()

    pointer = _rows_with(r, order_keys.CART_PAYMENT_PREFIX)[0]
    basket_row = _rows_with(r, order_keys.CART_BASKET_PREFIX)[0]

    code_2, body_2 = r.prepare("K2_fresh")

    # 1. ANTI-VACUITY: the quote hash moved between the two prepares. Recomputed from the live
    #    snapshot the second prepare built, because the refused prepare writes no request-key row.
    second_snapshot, _calculated = r.h._website_snapshot(
        r.identity, r.line_items(), int(time.time()))
    assert second_snapshot.snapshot_hash != first_hash, (
        "the two prepares produced the same snapshot hash, so this row cannot distinguish a "
        "guard keyed on the basket from one keyed on the quote")
    # 2. ...and the BASKET identity did not.
    assert cp.basket_hash(second_snapshot.frozen_data) == pointer["basketHash"]
    assert pointer["basketHash"] == basket_row["basketHash"]
    # 3. The second prepare is refused, naming the PAID attempt.
    assert code_2 == 409
    assert body_2["status"] == website_checkout.CHECKOUT_AMBIGUOUS
    assert body_2["reason"] == website_checkout.CART_ALREADY_PAID
    assert body_2["paymentAttemptId"] == paid_attempt
    assert "options" not in body_2
    # 4. Exactly one provider create across the whole run.
    assert len(r.creates) == 1
    # 5. Exactly one row of each prefix, and NO second request key: step 2a sits above step 3, so
    #    a refusal writes nothing at all.
    assert r.db.count_prefix(order_keys.CART_PAYMENT_PREFIX) == 1
    assert r.db.count_prefix(order_keys.CART_BASKET_PREFIX) == 1
    assert r.db.count_prefix(order_keys.CART_NARROW_BASKET_PREFIX) == 1
    assert r.db.count_prefix(order_keys.GATEWAY_ORDER_PREFIX) == 1
    assert r.db.count_prefix(order_keys.PAYMENT_REFERENCE_PREFIX) == 1
    assert r.db.count_prefix(order_keys.REQUEST_KEY_PREFIX) == 1, (
        "a step-2a refusal must write NOTHING AT ALL, including its own request key")


# ── (b) the moved-Wix-field durability row ─────────────────────────────────────

def _move_a_non_enumerated_field(response, call_number):
    """From the third calculate on, move a `summary.lineItems` field this build does not enumerate.

    `physicalProperties` is inside a line item, is a raw Wix shape relayed straight into the
    frozen payload, and is NOT one of the terms `narrow_basket_hash` names. It therefore stands
    in for the per-calculate residue `basket_hash` cannot vouch for.
    """
    if call_number >= 3:
        for line in response["summary"]["lineItems"]:
            line["physicalProperties"] = {"weight": "1.25", "shippingGroup": "late"}


def test_a_paid_basket_survives_both_a_pointer_overwrite_and_a_moved_wix_field(rig):
    """Four stages, and stage (b) must be ALLOWED or the guard refuses legitimate purchases.

    (a) pay basket B1.  (b) past the window, a DIFFERENT basket B2 is allowed and upserts the
    single-slot pointer, destroying the only record that B1 was paid.  (c) B2 is abandoned into a
    retryable state, where `may_create_order` and `is_in_flight` are both false.  (d) re-present
    the unedited B1 with a field Wix controls moved, so `basket_hash` DIFFERS and the fine key
    misses -- and the NARROW row is what refuses it.

    The anchor is (d1): the fine identity must differ and the narrow one must not, or the row
    proves nothing about the second key.
    """
    r = rig(revision_mode="bump", mutate=_move_a_non_enumerated_field)

    # (a) B1 is paid.
    assert r.prepare("K1")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    r.mark_paid()
    b1_narrow = _rows_with(r, order_keys.CART_NARROW_BASKET_PREFIX)[0]
    b1_fine = b1_narrow["basketHash"]
    assert b1_fine, "the fixture must have produced a fine identity to begin with"

    # (b) Past the in-flight window a genuinely different basket is allowed.
    r.age_everything(website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS + 60)
    r.set_quantity(2)
    code_b, body_b = r.prepare("K2")
    assert code_b == 200 and body_b["status"] == "CHECKOUT_OPTIONS_READY", (
        "a genuinely different basket past the window is the legitimate repeat purchase and must "
        "be ALLOWED; refusing it is the over-block this guard must not have")
    assert len(r.creates) == 2

    # (c) B2 is abandoned.
    r.mark_failed()

    # (d) Re-present the UNEDITED B1, with a non-enumerated Wix field moved.
    r.set_quantity(1)
    presented, _calculated = r.h._website_snapshot(
        r.identity, r.line_items(), int(time.time()))

    # (d1) ANCHOR: the fine identity moved, the narrow one did not.
    assert cp.basket_hash(presented.frozen_data) != b1_fine, (
        "the moved field did not change the FINE identity, so this row does not exercise the "
        "missed-by-key path the narrow row exists for")
    assert cp.narrow_basket_hash(presented.frozen_data) == b1_narrow["narrowBasketHash"], (
        "the narrow identity moved too, so there is nothing left that could refuse the request")

    code_d, body_d = r.prepare("K3_fresh")
    # (d2) ...and the refusal came from it.
    assert code_d == 409, body_d
    assert body_d["reason"] == website_checkout.CART_ALREADY_PAID
    assert "options" not in body_d
    # (d3) Exactly two creates across the whole run: B1's and B2's, never a third.
    assert len(r.creates) == 2, (
        f"a third provider create means B1 was charged twice: "
        f"{[c['receipt'] for c in r.creates]}")


# ── (c) the NEW resumed-request-key-after-a-lost-pointer-write row ─────────────

class _PointerHostileTable(FakeTable):
    """A keys table that refuses ONE named cart-row write, once, and otherwise behaves.

    Parametrised over all three writers, because `_record_cart_pointer` treats every one of them
    as must-succeed and a divergence between them would be invisible.
    """

    def __init__(self, refuse_prefix):
        super().__init__(key_attr="orderId")
        self.refuse_prefix = refuse_prefix
        self.armed = True

    def put_item(self, Item=None, **kwargs):
        item = Item or {}
        key = str(item.get("orderId") or "")
        # Only a RECORD write, never a step-4b CLAIM: a claim carries `claimStage` and no
        # `recordedAt`, and refusing one raises OrderIdentityUnavailable out of step 4b as a 503.
        # That is correct behaviour and a different row; it is not the resume exit this exercises.
        if self.armed and key.startswith(self.refuse_prefix) and "recordedAt" in item:
            self.armed = False
            raise FakeClientError("ProvisionedThroughputExceededException")
        return super().put_item(Item=Item, **kwargs)


@pytest.mark.parametrize("refuse_prefix", [
    order_keys.CART_PAYMENT_PREFIX,
    order_keys.CART_BASKET_PREFIX,
    order_keys.CART_NARROW_BASKET_PREFIX,
])
def test_a_resumed_request_key_after_a_lost_pointer_write_still_guards_the_basket(
        rig, refuse_prefix):
    """The iteration-7 hole, closed: a payable modal reached through the RESUME exit.

    Prepare #1 loses one cart-row write, so it answers CART_POINTER_SAVE_FAILED with NO options
    and ZERO cart rows -- while `_link_request_key_to_order` has ALREADY written `gatewayOrderId`
    onto the REQUESTKEY# row. That is the anti-vacuity anchor: without it, prepare #2 would not
    reach `_resume_lost_request_key`'s `gatewayOrderId` branch at all and the row would prove
    nothing.

    Prepare #2 presents the SAME key against a healthy table, takes that branch, and must write
    all three rows before it may hand back a modal. Prepare #3, with a FRESH key after the
    payment, must then be refused 409 CART_ALREADY_PAID -- which it can only be because #2 wrote
    them.

    Run against a FIXED-revision stub, because `intent_fingerprint` carries `cart_revision`: with
    a bumping revision, prepare #2 answers INTENT_CHANGED at step 3 and the resume is unreachable.
    """
    hostile = _PointerHostileTable(refuse_prefix)
    r = rig(revision_mode="fixed", keys_table=hostile)

    # Prepare #1: one cart-row write is lost.
    code_1, body_1 = r.prepare("K")
    assert code_1 == 200, "CART_POINTER_SAVE_FAILED is uncertainty, not refusal"
    assert body_1["status"] == website_checkout.CHECKOUT_AMBIGUOUS
    assert body_1["reason"] == website_checkout.CART_POINTER_SAVE_FAILED
    assert "options" not in body_1, "no modal may open with the basket unguarded"
    assert len(r.creates) == 1
    # ANTI-VACUITY ANCHOR: a resumable request key exists, with no cart rows behind it.
    request_rows = _rows_with(r, order_keys.REQUEST_KEY_PREFIX)
    assert len(request_rows) == 1
    assert request_rows[0].get("gatewayOrderId"), (
        "without a stored gatewayOrderId prepare #2 cannot reach the resume branch, so this row "
        "would not exercise the exit it exists for")
    # No RECORDED row exists for the refused prefix. The distinction from "no row" is
    # load-bearing: step 4b's CLAIM has already written a `CARTNARROW#` row carrying `claimedAt`
    # and deliberately NO `recordedAt`, which is what puts it on the 120s create horizon instead
    # of the settling one. A paid-memory row is one with `recordedAt`.
    def _recorded(prefix):
        return [row for row in _rows_with(r, prefix) if row.get("recordedAt")]

    assert _recorded(refuse_prefix) == []
    if refuse_prefix == order_keys.CART_PAYMENT_PREFIX:
        # The fully non-vacuous parametrisation: the FIRST write failed, so none of the three
        # recorded rows exists and the basket has no paid memory at all.
        assert _recorded(order_keys.CART_BASKET_PREFIX) == []
        assert _recorded(order_keys.CART_NARROW_BASKET_PREFIX) == []

    # Prepare #2: the SAME key, healthy table. The resume exit must write the rows.
    code_2, body_2 = r.prepare("K")
    assert code_2 == 200
    assert body_2["status"] == "CHECKOUT_OPTIONS_READY", body_2
    assert len(r.creates) == 1, "the resume must not create a second payable order"
    assert r.db.count_prefix(order_keys.CART_PAYMENT_PREFIX) == 1
    assert r.db.count_prefix(order_keys.CART_BASKET_PREFIX) == 1
    assert r.db.count_prefix(order_keys.CART_NARROW_BASKET_PREFIX) == 1
    stored_binding = _rows_with(r, order_keys.GATEWAY_ORDER_PREFIX)[0]
    pointer = _rows_with(r, order_keys.CART_PAYMENT_PREFIX)[0]
    assert pointer["paymentAttemptId"] == stored_binding["paymentAttemptId"], (
        "the pointer must name the attempt that OWNS the payable order, not this invocation's")

    # The payment lands.
    r.mark_paid()

    # Prepare #3: a FRESH key for the same basket must be refused.
    code_3, body_3 = r.prepare("K_fresh")
    assert code_3 == 409, body_3
    assert body_3["reason"] == website_checkout.CART_ALREADY_PAID
    assert len(r.creates) == 1, (
        "a second provider create here is the double charge this whole graft exists to prevent")


@pytest.mark.parametrize("refuse_prefix", [
    order_keys.CART_PAYMENT_PREFIX,
    order_keys.CART_BASKET_PREFIX,
    order_keys.CART_NARROW_BASKET_PREFIX,
])
def test_a_prepare_onto_an_already_bound_order_still_writes_the_pointer(rig, refuse_prefix):
    """The behavioural half of the module-wide invariant, over the resume exit x all three writers.

    Whichever of the three writes fails, the answer is the same: CART_POINTER_SAVE_FAILED, 200,
    and NO options. A divergence between the three would mean one of them was best-effort after
    all.
    """
    hostile = _PointerHostileTable(refuse_prefix)
    r = rig(revision_mode="fixed", keys_table=hostile)
    assert r.prepare("K")[1]["reason"] == website_checkout.CART_POINTER_SAVE_FAILED
    # Re-arm against the resume exit specifically, so the SECOND prepare is the one that fails.
    hostile.armed = True
    code, body = r.prepare("K")
    assert code == 200
    assert body["reason"] == website_checkout.CART_POINTER_SAVE_FAILED
    assert "options" not in body
    assert len(r.creates) == 1


# ── per-defect regression rows ─────────────────────────────────────────────────

def test_a_fresh_request_key_cannot_open_a_second_order_for_one_cart(rig):
    """The headline defect: the reservation is keyed on the request key, the guard on the basket."""
    r = rig()
    assert r.prepare("K1")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    code, body = r.prepare("K2_fresh")
    assert code == 409
    assert body["reason"] == website_checkout.CART_PAYMENT_IN_FLIGHT
    assert len(r.creates) == 1


def test_a_paid_cart_with_an_edited_basket_past_the_window_is_not_refused(rig):
    """Tier 2's window, from the permissive side. The repeat purchase must survive."""
    r = rig()
    assert r.prepare("K1")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    r.mark_paid()
    r.age_everything(website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS + 60)
    r.set_quantity(3)
    code, body = r.prepare("K2_fresh")
    assert code == 200 and body["status"] == "CHECKOUT_OPTIONS_READY", body
    assert len(r.creates) == 2


def test_a_paid_basket_with_one_more_unit_past_the_window_is_not_refused(rig):
    """The fix from the permissive side: a real edit past the settling interval is payable."""
    r = rig()
    assert r.prepare("K1")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    r.mark_paid()
    r.age_everything(website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS + 60)
    r.set_quantity(2)
    assert r.prepare("K2_fresh")[0] == 200
    assert len(r.creates) == 2


def test_a_paid_basket_reordered_to_a_different_address_is_refused_past_the_window(rig,
                                                                                  monkeypatch):
    """The designed COST, pinned so it is a decision rather than a surprise.

    `narrow_basket_hash` ignores the address, so an address-only re-order of a paid basket
    matches narrowly FOREVER and is refused with no self-release. The two cases it cannot
    distinguish -- "Wix moved a field we do not control" and "the shopper re-ordered the same
    items to a different address" -- are observationally identical, and only one of them may pass.
    """
    r = rig()
    assert r.prepare("K1")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    r.mark_paid()
    r.age_everything(website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS + 60)
    # Same items, same tender, a different delivery address IN THE SAME STATE. The state matters:
    # an inter-state address flips `intra_state`, which changes the convenience-fee GST split,
    # which changes `quote.components()` -- and `components` IS a narrow term, so an inter-state
    # re-order hashes differently and is correctly ALLOWED. The cost documented here is the
    # intra-state case, where nothing the narrow identity names has moved.
    monkeypatch.setattr(r.h, "LOAD_OWNED_ADDRESS", lambda customer_id: {
        "addressLine1": "7 Park Street", "city": "Kolkata",
        "state": "West Bengal", "postalCode": "700016"})
    code, body = r.prepare("K2_fresh")
    assert code == 409, body
    assert body["reason"] == website_checkout.CART_ALREADY_PAID
    assert len(r.creates) == 1


def test_a_reload_in_the_paying_tab_is_refused_not_resumed(rig):
    """The paid arm sits ABOVE the same-request-key exemption, deliberately.

    `cart.tsx` never clears CHECKOUT_REQUEST_KEY, so the tab that just paid still holds its key.
    With the exemption first, a Proceed click would be handed a payable modal for a captured
    basket, and "no second charge" would rest entirely on Razorpay refusing a payment against an
    order already marked paid -- an external behaviour nothing here verifies.
    """
    r = rig(revision_mode="fixed")
    assert r.prepare("K")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    r.mark_paid()
    code, body = r.prepare("K")
    assert code == 409, body
    assert body["reason"] == website_checkout.CART_ALREADY_PAID
    assert "options" not in body
    assert len(r.creates) == 1


def test_a_reload_on_an_unpaid_attempt_still_resumes(rig):
    """The other half, and the reason the exemption exists at all."""
    r = rig(revision_mode="fixed")
    first = r.prepare("K")[1]
    assert first["status"] == "CHECKOUT_OPTIONS_READY"
    code, body = r.prepare("K")
    assert code == 200, body
    assert body["status"] == "CHECKOUT_OPTIONS_READY"
    assert body["options"]["orderId"] == first["options"]["orderId"]
    assert len(r.creates) == 1


def test_a_same_key_prepare_in_the_bumping_world_is_an_intent_change(rig):
    """The other revision world, where `intent_fingerprint` refuses before the resume is reached."""
    r = rig(revision_mode="bump")
    assert r.prepare("K")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    code, body = r.prepare("K")
    assert code == 409
    assert body["reason"] == "INTENT_CHANGED"
    assert len(r.creates) == 1


def test_a_legitimate_retry_after_a_failed_attempt_still_wins_the_claim(rig):
    """Arm 0 passes a retryable attempt, so the CAS basis names it and the claim re-points."""
    r = rig()
    assert r.prepare("K1")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    r.mark_failed()
    r.age_everything(website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS + 60)
    code, body = r.prepare("K2_fresh")
    assert code == 200 and body["status"] == "CHECKOUT_OPTIONS_READY", body
    assert len(r.creates) == 2


def test_two_overlapping_prepares_on_one_basket_open_one_payable_order(rig):
    """The interleaved row: a `create_order` stub that re-enters prepare before returning.

    MEASURED, and it is not where the design predicted. Step 4b's claim is written BEFORE
    `create_order`, so by the time the inner prepare runs, a `CARTNARROW#` row already exists
    carrying `claimedAt`, the winner's `paymentAttemptId` and the winner's `requestKey` -- while
    the winner's ATTEMPT row does not exist yet, because that is written after the create returns.
    The inner prepare therefore presents a different request key, fails the resume exemption,
    finds a claim with no readable attempt, and is refused by arm 0's bounded create-horizon
    window -- at step 2a, before its own reservation.

    That is strictly better than being refused at step 4b: it writes nothing at all, and it names
    the holder's attempt, which comes to exist moments later and which `/checkout/status/` can
    then resolve. The step-4b loser path -- where the refusal deliberately names NO attempt,
    because the holder's may not exist -- is exercised directly by
    `test_a_held_basket_claim_refuses_without_naming_an_attempt`.

    What is asserted here is the invariant, not the arm: ONE create, ONE gateway order, ONE
    reference, ONE modal.
    """
    r = rig(revision_mode="fixed")
    inner = {}
    original = r._create_order

    def reentrant(*, amount_paise, receipt, notes):
        if not inner:
            inner["code"], inner["body"] = r.prepare("K2")
        return original(amount_paise=amount_paise, receipt=receipt, notes=notes)

    r.h.razorpay_orders.create_order = reentrant
    code_1, body_1 = r.prepare("K1")

    assert len(r.creates) == 1, (
        f"two payable gateway orders for one basket: {[c['receipt'] for c in r.creates]}")
    assert r.db.count_prefix(order_keys.GATEWAY_ORDER_PREFIX) == 1
    assert r.db.count_prefix(order_keys.PAYMENT_REFERENCE_PREFIX) == 1
    # Exactly one modal, and it is the winner's.
    assert code_1 == 200 and body_1["status"] == "CHECKOUT_OPTIONS_READY"
    assert inner["code"] == 409
    assert inner["body"]["status"] == website_checkout.CHECKOUT_AMBIGUOUS
    assert inner["body"]["reason"] == website_checkout.CART_PAYMENT_IN_FLIGHT
    assert "options" not in inner["body"]
    # The loser wrote NOTHING: it was excluded at step 2a, above its own reservation.
    assert r.db.count_prefix(order_keys.REQUEST_KEY_PREFIX) == 1, (
        "the overlapping prepare is refused before step 3, so only the winner's key exists")
    # ...and it names the attempt that holds the basket, not its own.
    assert inner["body"]["paymentAttemptId"] == body_1["paymentAttemptId"]


def test_the_gate_off_path_claims_nothing(rig):
    """Step 4b is AFTER the gate, so a dormant prepare writes no claim and blocks nothing."""
    r = rig(initiation_enabled=False)
    code, body = r.prepare("K1")
    assert code == 200
    assert body["status"] == website_checkout.PAYMENT_INITIATION_DISABLED
    assert r.creates == []
    for prefix in (order_keys.CART_PAYMENT_PREFIX, order_keys.CART_BASKET_PREFIX,
                   order_keys.CART_NARROW_BASKET_PREFIX, order_keys.PAYMENT_REFERENCE_PREFIX,
                   order_keys.GATEWAY_ORDER_PREFIX, order_keys.ORDER_NUMBER_PREFIX):
        assert r.db.count_prefix(prefix) == 0, prefix
    assert r.db.rows(ATTEMPTS_TABLE) == []
    # A second gate-off prepare is not blocked by the first.
    assert r.prepare("K2")[1]["status"] == website_checkout.PAYMENT_INITIATION_DISABLED


def test_the_gate_off_prepare_leaves_no_payable_residue(rig):
    """The same property as the absence of anything payable, plus no stored Wix payload."""
    r = rig(initiation_enabled=False)
    r.prepare("K1")
    assert r.db.rows(ORDERS_TABLE) == []
    request_rows = _rows_with(r, order_keys.REQUEST_KEY_PREFIX)
    assert len(request_rows) == 1, "the reservation is the ONLY row a dormant prepare writes"
    assert not request_rows[0].get("referenceId")
    assert not request_rows[0].get("gatewayOrderId")
    assert not request_rows[0].get("createClaimedAt")


def test_a_snapshot_with_no_frozen_payload_is_rejected_as_basket_identity_required():
    """A guard that could not run is a different fact from a quote that will not settle."""
    quote = cp.compute_quote(COLLECTION_PAISE)
    snapshot = cp.QuoteSnapshot(
        customer_id=CUSTOMER, cart_id=CART, cart_revision=1, created_at=1_700_000_000,
        expires_at=1_700_000_900, policy_version=quote.policy_version, quote=quote,
        snapshot_hash="deadbeef", frozen_data={})
    with pytest.raises(website_checkout.CheckoutRejected) as raised:
        website_checkout.prepare_checkout(
            customer_id=CUSTOMER, snapshot=snapshot,
            presented_snapshot_hash="deadbeef", request_key="K", now=1_700_000_100,
            keys_table=_keys(),
            create_order=lambda **_: pytest.fail("nothing may be created"),
            find_order_by_receipt=lambda _: None, account_mode_of=lambda _: "live",
            initiation_enabled=True)
    assert raised.value.reason == website_checkout.BASKET_IDENTITY_REQUIRED
    assert raised.value.reason != "AMOUNT_NOT_SETTLED"


@pytest.mark.parametrize("resolver", ["resolve_cart_basket", "resolve_cart_narrow_basket",
                                      "resolve_cart_payment"])
def test_a_guard_read_failure_is_a_503_and_never_a_pass(rig, monkeypatch, resolver):
    """A throttle must never read as "no live payment": the caller acts on that by charging."""
    r = rig()

    def raising(*_args, **_kwargs):
        raise order_keys.OrderIdentityUnavailable("simulated throttle")

    monkeypatch.setattr(r.h.website_checkout.order_keys, resolver, raising)
    code, body = r.prepare("K1")
    assert code == 503
    assert body["error"] == "TEMPORARILY_UNAVAILABLE"
    assert r.creates == []


def test_a_held_basket_claim_refuses_without_naming_an_attempt(rig, monkeypatch):
    """A lost claim carries NO attempt id: the holder's attempt may not exist yet."""
    r = rig()
    monkeypatch.setattr(r.h.website_checkout.order_keys, "claim_cart_narrow_basket",
                        lambda *a, **k: False)
    monkeypatch.setattr(r.h.website_checkout.order_keys, "claim_cart_basket",
                        lambda *a, **k: False)
    code, body = r.prepare("K1")
    assert code == 409
    assert body["reason"] == website_checkout.CART_PAYMENT_IN_FLIGHT
    assert not body.get("paymentAttemptId"), (
        "an unresolvable attempt id would point /checkout/status/ at nothing, which is worse "
        "than none")
    assert r.creates == [], "a lost claim must create nothing"
    assert r.db.count_prefix(order_keys.PAYMENT_REFERENCE_PREFIX) == 0, (
        "the claim is BEFORE the mint, so a loser leaves no orphan PAYREF# row")


def test_a_throttled_basket_claim_is_a_503(rig, monkeypatch):
    r = rig()

    def raising(*_a, **_k):
        raise order_keys.OrderIdentityUnavailable("simulated throttle")

    monkeypatch.setattr(r.h.website_checkout.order_keys, "claim_cart_narrow_basket", raising)
    code, body = r.prepare("K1")
    assert code == 503 and body["error"] == "TEMPORARILY_UNAVAILABLE"
    assert r.creates == []


def test_a_basket_row_naming_another_customers_attempt_does_not_block(rig):
    """The rows are indexes, not authorities."""
    r = rig()
    assert r.prepare("K1")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    table = r.db.Table(ATTEMPTS_TABLE)
    for key, row in list(table.rows.items()):
        row = dict(row)
        row["customerId"] = "CUS_someone_else"
        table.rows[key] = row
    code, body = r.prepare("K2_fresh")
    assert code == 200 and body["status"] == "CHECKOUT_OPTIONS_READY", body


def test_a_dangling_basket_row_blocks_for_one_window_then_releases(rig):
    """Fail closed, but BOUNDED: blocking forever would brick a basket on an anomaly."""
    r = rig()
    assert r.prepare("K1")[1]["status"] == "CHECKOUT_OPTIONS_READY"
    # The attempt row vanishes; the cart rows remain. An anomaly, not a race.
    r.db.Table(ATTEMPTS_TABLE).rows.clear()
    assert r.prepare("K2_fresh")[0] == 409
    r.age_everything(website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS + 60)
    code, body = r.prepare("K3_fresh")
    assert code == 200 and body["status"] == "CHECKOUT_OPTIONS_READY", (
        "a dangling row must release after one window rather than bricking the basket")


def test_the_in_flight_horizon_outlasts_every_quote_ttl():
    """Three inequalities, because 900 was wrong: it EQUALS the V1 snapshot TTL."""
    spec = importlib.util.spec_from_file_location("graft_ttl_handler", HANDLER_PATH)
    handler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(handler)
    assert (website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS
            > handler.WEBSITE_SNAPSHOT_TTL_SECONDS)
    assert (website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS
            > purchase_intent.QUOTE_TTL_SECONDS)
    assert (website_checkout.CART_PAYMENT_IN_FLIGHT_SECONDS
            > website_checkout.CREATE_CLAIM_STALE_SECONDS)
    assert (website_checkout.CREATE_CLAIM_STALE_SECONDS
            == order_keys.CART_CREATE_CLAIM_STALE_SECONDS)


def test_v1_is_refused_when_the_gate_is_on(rig, monkeypatch):
    """V1 has no stable cart identity, so the guard cannot run and the branch is refused."""
    monkeypatch.delenv("WIX_CART_V2_ENABLED", raising=False)
    r = rig(initiation_enabled=True)
    monkeypatch.delenv("WIX_CART_V2_ENABLED", raising=False)
    code, body = r.prepare("K1")
    assert code == 409
    assert body["status"] == website_checkout.CHECKOUT_REJECTED
    assert body["reason"] == website_checkout.CART_V2_REQUIRED
    assert r.creates == [], "nothing may be created"
    assert r.checkouts == [], "and no Wix checkout may be minted either"
    for prefix in (order_keys.CART_PAYMENT_PREFIX, order_keys.CART_BASKET_PREFIX,
                   order_keys.CART_NARROW_BASKET_PREFIX, order_keys.PAYMENT_REFERENCE_PREFIX,
                   order_keys.GATEWAY_ORDER_PREFIX, order_keys.REQUEST_KEY_PREFIX):
        assert r.db.count_prefix(prefix) == 0, prefix


def test_v1_still_serves_when_the_gate_is_off(rig, monkeypatch):
    """The gate-off V1 body stays byte-identical in behaviour: 200 PAYMENT_INITIATION_DISABLED."""
    monkeypatch.delenv("WIX_CART_V2_ENABLED", raising=False)
    r = rig(initiation_enabled=False)
    monkeypatch.delenv("WIX_CART_V2_ENABLED", raising=False)
    code, body = r.prepare("K1")
    assert code == 200
    assert body["status"] == website_checkout.PAYMENT_INITIATION_DISABLED
    assert len(r.checkouts) == 1, "V1 mints its Wix checkout, exactly as before"


def test_two_v1_prepares_mint_two_checkout_ids(rig, monkeypatch):
    """The measurement the V1 refusal rests on: `create_checkout` is a create, not a resolve."""
    monkeypatch.delenv("WIX_CART_V2_ENABLED", raising=False)
    r = rig(initiation_enabled=False)
    monkeypatch.delenv("WIX_CART_V2_ENABLED", raising=False)
    r.prepare("K1")
    r.prepare("K2")
    assert len(r.checkouts) == 2
    # Two different cart ids for one basket is exactly why the cart-keyed guard cannot run here.
    assert r.wix is not None


# ── the module-wide invariant, by AST ──────────────────────────────────────────

WEBSITE_CHECKOUT_SOURCE = (
    ROOT / "amplify/functions/shared/lambda_utils/ecommerce/website_checkout.py")


def _enclosing_function(tree, target):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if inner is target:
                    return node.name
    return "<module>"


def test_only_the_choke_point_can_emit_a_payable_modal():
    """An AST walk, not a text scan: the comments in that module contain the strings searched for.

    Three assertions, and together they make "every payable modal has paid memory behind it" a
    property of the CALL GRAPH rather than a list of exits somebody has to keep up to date. This
    row is RED on the pre-graft module, which has two construction sites and two
    `_browser_options` call sites.
    """
    tree = ast.parse(WEBSITE_CHECKOUT_SOURCE.read_text(encoding="utf-8"))

    # (1) Exactly ONE `PreparedCheckout(...)` carrying `options=` or the ready status.
    ready_sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "PreparedCheckout"):
            continue
        payable = any(keyword.arg == "options" for keyword in node.keywords)
        payable = payable or any(
            keyword.arg == "status"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "CHECKOUT_OPTIONS_READY"
            for keyword in node.keywords)
        if payable:
            ready_sites.append(_enclosing_function(tree, node))
    assert ready_sites == ["_emit_payable_modal"], (
        f"a payable PreparedCheckout is constructed in {ready_sites}; it may only be constructed "
        f"in _emit_payable_modal, which is what writes the three cart rows first")

    # (2) Exactly ONE `_browser_options` call site, in the same function.
    browser_sites = [_enclosing_function(tree, node) for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                     and node.func.id == "_browser_options"]
    assert browser_sites == ["_emit_payable_modal"], (
        f"_browser_options is called from {browser_sites}; a second call site is a second way a "
        f"browser can receive payable options")

    # (3) The write precedes the construction, by line number, inside that one function.
    choke = [node for node in ast.walk(tree)
             if isinstance(node, ast.FunctionDef) and node.name == "_emit_payable_modal"][0]
    writes = [node.lineno for node in ast.walk(choke)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "_record_cart_pointer"]
    constructions = [node.lineno for node in ast.walk(choke)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                     and node.func.id == "_browser_options"]
    assert writes and constructions
    assert min(writes) < min(constructions), (
        "_record_cart_pointer must run BEFORE the options are built, or a failed write still "
        "yields a payable modal")


def test_the_browser_amount_and_the_attempt_amount_are_different_expressions():
    """The split, re-pinned here because the choke point moved it out of one function.

    `tests/test_gift_cards_iam_and_table.py`'s SEAM-G14 row asserts this by requiring
    `_browser_options` and `payment_attempt.build` to appear in the SAME function with different
    `amount_paise` expressions. The choke point deliberately separates them -- there is now
    exactly one `_browser_options` call site and it is not in the function that builds the attempt
    -- so that row's SCOPING no longer matches the structure. The PROPERTY is unchanged and is
    asserted here instead: the browser is shown the pay-now leg and the attempt records the full
    payable. That marked test is another workstream's and is left untouched.
    """
    tree = ast.parse(WEBSITE_CHECKOUT_SOURCE.read_text(encoding="utf-8"))
    binder = [node for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef) and node.name == "_bind_and_ready"][0]

    def _amounts(predicate):
        found = []
        for node in ast.walk(binder):
            if isinstance(node, ast.Call) and predicate(node.func):
                found += [ast.unparse(keyword.value) for keyword in node.keywords
                          if keyword.arg == "amount_paise"]
        return found

    built = set(_amounts(lambda f: isinstance(f, ast.Attribute) and f.attr == "build"))
    emitted = set(_amounts(lambda f: isinstance(f, ast.Name)
                           and f.id == "_emit_payable_modal"))
    assert built and emitted
    assert not (built & emitted), (
        f"the attempt and the modal are handed the same amount expression "
        f"{sorted(built & emitted)}, so the browser is shown a price that is not being charged")
    assert all("pay_now" in argument for argument in emitted), (
        f"the browser amount comes from {sorted(emitted)} rather than from the pay-now leg")
    assert all("full_amount" in argument for argument in built), (
        f"the attempt records {sorted(built)} rather than the full payable")
