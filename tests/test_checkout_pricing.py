"""Section 7 checkout pricing: the convenience fee + GST-on-fee calculator and the immutable
quote snapshot.

The non-negotiable case is the 121481-paise fixture: a tax-exclusive 1,000 INR supply becomes a
1,180 INR collection (supply GST 180), a 29.50 INR convenience fee, 5.31 INR GST on that fee, and
a 1,214.81 INR == 121481 paise payable. Equally important are the refusals - a calculator that
silently rounds a bad input is worse than one that raises - and the snapshot contract: a frozen,
customer-owned quote whose hash changes when the cart changes and that cannot be charged once it
has expired.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))

from decimal import Decimal  # noqa: E402

from lambda_utils.ecommerce import checkout_pricing as cp  # noqa: E402
from lambda_utils.ecommerce.money import Money  # noqa: E402

# A tax-exclusive 1,000 INR supply: supply GST at 18% is 180 INR, so the authoritative approved
# collection is 1,180 INR == 118000 paise. The supply GST is computed upstream; it is the INPUT
# to the calculator, which only adds the convenience fee and the GST on that fee.
FIXTURE_COLLECTION_PAISE = 118000
NOW = 1_700_000_000


# ── the mandatory 121481-paise fixture ─────────────────────────────────────────────

def test_the_section_7_fixture_is_exact():
    quote = cp.compute_quote(FIXTURE_COLLECTION_PAISE)
    assert quote.collection_before_convenience_paise == 118000
    assert quote.convenience_fee_paise == 2950          # 29.50 INR
    assert quote.convenience_gst_paise == 531           # 5.31 INR
    assert quote.total_payable_paise == 121481          # 1,214.81 INR
    # The three numbers the customer, the gateway and the receipt must agree on reconcile.
    assert quote.total_payable_paise == (quote.collection_before_convenience_paise
                                         + quote.convenience_fee_paise
                                         + quote.convenience_gst_paise)


def test_the_fixture_total_is_a_payable_money():
    quote = cp.compute_quote(FIXTURE_COLLECTION_PAISE)
    assert quote.is_payable
    assert quote.as_payable_money() == Money(121481, "INR")


def test_components_dict_carries_rounded_values_and_policy_version():
    quote = cp.compute_quote(FIXTURE_COLLECTION_PAISE)
    comp = quote.components()
    assert comp["collectionBeforeConveniencePaise"] == 118000
    assert comp["convenienceFeePaise"] == 2950
    assert comp["convenienceGstPaise"] == 531
    assert comp["totalPayablePaise"] == 121481
    assert comp["policyVersion"] == cp.CALCULATION_POLICY_VERSION
    assert comp["sellerGstin"] == "19AAFFW7196L1Z8"


# ── round_half_up and tie boundaries ───────────────────────────────────────────────

def test_round_half_up_exact_formula():
    # 2.5% of 118000 paise is exactly 2950.0 -> 2950.
    assert cp.round_half_up(118000, cp.CONVENIENCE_FEE_BPS) == 2950
    # 18% of 2950 paise is exactly 5310000/10000 == 531.0 -> 531.
    assert cp.round_half_up(2950, cp.CONVENIENCE_GST_BPS) == 531


def test_round_half_up_rounds_a_half_tie_up():
    # Choose a collection whose fee is exactly N.5 paise. 2.5% == 1/40, so a collection of
    # 20 paise gives 0.5 -> rounds up to 1.
    assert cp.round_half_up(20, cp.CONVENIENCE_FEE_BPS) == 1
    # 60 paise -> 1.5 -> 2 (ties away from zero, i.e. up for non-negative values).
    assert cp.round_half_up(60, cp.CONVENIENCE_FEE_BPS) == 2
    # Just below a tie stays down: 19 paise -> 0.475 -> 0.
    assert cp.round_half_up(19, cp.CONVENIENCE_FEE_BPS) == 0


def test_round_half_up_rejects_negative_and_non_integer():
    with pytest.raises(cp.PricingError):
        cp.round_half_up(-1, cp.CONVENIENCE_FEE_BPS)
    with pytest.raises(cp.PricingError):
        cp.round_half_up(100.0, cp.CONVENIENCE_FEE_BPS)   # type: ignore[arg-type]


# ── rejection of invalid inputs ────────────────────────────────────────────────────

def test_rejects_float_collection():
    with pytest.raises(cp.PricingError):
        cp.compute_quote(118000.0)


def test_rejects_fractional_paise_decimal():
    with pytest.raises(cp.PricingError):
        cp.compute_quote(Decimal("118000.5"))


def test_accepts_an_integer_valued_decimal():
    # A Decimal that is an exact integer number of paise is fine - it is how DynamoDB numbers
    # arrive - and must produce the same answer as the int.
    quote = cp.compute_quote(Decimal("118000"))
    assert quote.total_payable_paise == 121481


def test_rejects_bool_collection():
    with pytest.raises(cp.PricingError):
        cp.compute_quote(True)


def test_rejects_negative_collection():
    with pytest.raises(cp.PricingError):
        cp.compute_quote(-1)


def test_rejects_overflow_collection():
    with pytest.raises(cp.PricingError):
        cp.compute_quote(9007199254740992)


def test_rejects_non_inr_currency():
    with pytest.raises(cp.PricingError):
        cp.compute_quote(118000, currency="USD")


def test_rejects_overflow_from_the_total_not_just_the_input():
    # A collection just under the ceiling would push the total over it once fee+GST are added.
    with pytest.raises(cp.PricingError):
        cp.compute_quote(cp._MAX_PAISE)


# ── zero-total behavior ────────────────────────────────────────────────────────────

def test_zero_collection_is_a_valid_but_unpayable_quote():
    quote = cp.compute_quote(0)
    assert quote.collection_before_convenience_paise == 0
    assert quote.convenience_fee_paise == 0
    assert quote.convenience_gst_paise == 0
    assert quote.total_payable_paise == 0
    assert not quote.is_payable
    assert not quote.requires_payment


def test_zero_total_quote_refuses_to_produce_a_gateway_amount():
    quote = cp.compute_quote(0)
    with pytest.raises(cp.PricingError):
        quote.as_payable_money()


# ── GSTIN handling ─────────────────────────────────────────────────────────────────

def test_seller_gstin_constant_is_the_documented_value():
    assert cp.SELLER_GSTIN == "19AAFFW7196L1Z8"


def test_buyer_gstin_equal_to_seller_is_rejected():
    with pytest.raises(cp.PricingError):
        cp.compute_quote(118000, buyer_gstin=cp.SELLER_GSTIN)


def test_malformed_buyer_gstin_is_rejected():
    with pytest.raises(cp.PricingError):
        cp.compute_quote(118000, buyer_gstin="not-a-gstin")


# ── CGST/SGST vs IGST reconciliation ───────────────────────────────────────────────

def test_intra_state_split_reconciles_to_the_total():
    quote = cp.compute_quote(FIXTURE_COLLECTION_PAISE, intra_state=True)
    split = quote.convenience_gst_split
    assert split.intra_state
    assert split.igst_paise == 0
    assert split.cgst_paise + split.sgst_paise == quote.convenience_gst_paise
    # 531 is odd: SGST floors to 265, CGST takes the remainder 266, summing to 531.
    assert split.sgst_paise == 265
    assert split.cgst_paise == 266


def test_inter_state_split_is_a_single_igst_line():
    quote = cp.compute_quote(FIXTURE_COLLECTION_PAISE, intra_state=False)
    split = quote.convenience_gst_split
    assert not split.intra_state
    assert split.cgst_paise == 0 and split.sgst_paise == 0
    assert split.igst_paise == quote.convenience_gst_paise


def test_split_gst_always_sums_back_for_odd_and_even_amounts():
    for amount in (0, 1, 2, 3, 530, 531, 999):
        intra = cp.split_gst(amount, intra_state=True)
        assert intra.cgst_paise + intra.sgst_paise == amount
        inter = cp.split_gst(amount, intra_state=False)
        assert inter.igst_paise == amount


def test_buyer_in_sellers_state_infers_intra_state():
    # Seller state code is "19"; a buyer GSTIN with the same prefix infers intra-state.
    quote = cp.compute_quote(118000, buyer_gstin="19AAAAA0000A1Z5")
    assert quote.convenience_gst_split.intra_state


def test_buyer_in_another_state_infers_inter_state():
    quote = cp.compute_quote(118000, buyer_gstin="27AAAAA0000A1Z5")
    assert not quote.convenience_gst_split.intra_state


# ── the quote object is immutable ──────────────────────────────────────────────────

def test_quote_is_frozen():
    quote = cp.compute_quote(118000)
    with pytest.raises(Exception):
        quote.total_payable_paise = 0   # type: ignore[misc]


# ── the immutable quote snapshot ───────────────────────────────────────────────────

def _snapshot(**overrides):
    quote = overrides.pop("quote", None) or cp.compute_quote(FIXTURE_COLLECTION_PAISE)
    params = dict(
        customer_id="CUS_01J0000000000000000000000",
        cart_id="cart-1",
        cart_revision=3,
        quote=quote,
        created_at=NOW,
        ttl_seconds=900,
        site="wecare.digital",
        items=[{"sku": "A", "qty": 1, "paise": 118000}],
        address={"line1": "1 Road", "state": "19"},
        delivery={"method": "standard"},
    )
    params.update(overrides)
    return cp.build_snapshot(**params)


def test_snapshot_exposes_the_contract_fields():
    snap = _snapshot()
    assert snap.cart_revision == 3
    assert snap.expires_at == NOW + 900
    assert snap.policy_version == cp.CALCULATION_POLICY_VERSION
    assert isinstance(snap.snapshot_hash, str) and len(snap.snapshot_hash) == 64
    assert snap.quote.total_payable_paise == 121481


def test_snapshot_hash_is_stable_across_identical_builds():
    assert _snapshot().snapshot_hash == _snapshot().snapshot_hash


def test_editing_the_cart_produces_a_different_hash():
    base = _snapshot()
    # A quantity change is a cart edit: new revision, new item list.
    edited = _snapshot(cart_revision=4,
                       items=[{"sku": "A", "qty": 2, "paise": 236000}])
    assert edited.snapshot_hash != base.snapshot_hash
    # The original object is untouched - a new snapshot, not a mutation.
    assert base.cart_revision == 3


def test_a_changed_address_changes_the_hash():
    base = _snapshot()
    moved = _snapshot(address={"line1": "2 Road", "state": "19"})
    assert moved.snapshot_hash != base.snapshot_hash


def test_a_changed_amount_changes_the_hash():
    base = _snapshot()
    other = _snapshot(quote=cp.compute_quote(100000))
    assert other.snapshot_hash != base.snapshot_hash


def test_snapshot_is_frozen():
    snap = _snapshot()
    with pytest.raises(Exception):
        snap.snapshot_hash = "x"   # type: ignore[misc]


def test_snapshot_expiry():
    snap = _snapshot()
    assert not snap.is_expired(NOW)
    assert not snap.is_expired(NOW + 899)
    assert snap.is_expired(NOW + 900)
    assert snap.is_expired(NOW + 1000)


def test_snapshot_matches_only_its_own_hash():
    snap = _snapshot()
    assert snap.matches(snap.snapshot_hash)
    assert not snap.matches("0" * 64)


def test_snapshot_rejects_non_positive_ttl():
    with pytest.raises(cp.PricingError):
        _snapshot(ttl_seconds=0)


def test_snapshot_rejects_missing_customer():
    with pytest.raises(cp.PricingError):
        _snapshot(customer_id="")
