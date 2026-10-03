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
from lambda_utils.ecommerce import checkout_pricing as cp  # noqa: E402
from lambda_utils.ecommerce import order_keys  # noqa: E402
from lambda_utils.ecommerce import payment_attempt  # noqa: E402
from lambda_utils.ecommerce import purchase_intent  # noqa: E402
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
