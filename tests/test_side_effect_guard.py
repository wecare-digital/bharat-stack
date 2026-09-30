"""Per-side-effect idempotency for one order: each downstream effect runs at most once.

What this defends (R4.2, §47, §57)
----------------------------------
Order creation is already guaranteed unique by order_keys. This guard covers the STEPS AFTER the
order: create the Wix order, record the external payment, generate the receipt, send the
confirmation. Each must happen at most once and be individually retryable. The properties tested:
a claim has exactly one winner, the guard FAILS CLOSED on a storage error (a money/customer-facing
effect must not run when we cannot prove it has not), a crash between claim and confirm shows up
as `pending` (recoverable) not `done`, and replaying the same event five times performs each side
effect once.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402
from lambda_utils.ecommerce import side_effect_guard as guard  # noqa: E402

TABLE = "stack-wecare-digital-CommerceKeys"
ORDER = "01J8Z9Q9W9EXAMPLEORDERID000000"


@pytest.fixture
def table():
    return FakeDynamo(keys={TABLE: "orderId"}).Table(TABLE)


# ── claim once ──────────────────────────────────────────────────────────────────

def test_only_the_first_claim_wins(table):
    first = guard.claim(table, order_id=ORDER, effect=guard.WIX_ORDER)
    second = guard.claim(table, order_id=ORDER, effect=guard.WIX_ORDER)
    assert first is True
    assert second is False


def test_different_effects_are_independent(table):
    # Claiming the Wix order must not block claiming the receipt for the same order.
    assert guard.claim(table, order_id=ORDER, effect=guard.WIX_ORDER) is True
    assert guard.claim(table, order_id=ORDER, effect=guard.RECEIPT) is True


def test_an_unknown_effect_is_a_bug_not_a_new_effect(table):
    with pytest.raises(ValueError):
        guard.claim(table, order_id=ORDER, effect="charge_again")


# ── fails closed ──────────────────────────────────────────────────────────────

def test_a_storage_error_on_claim_blocks_the_effect(table):
    table.parent.arm_failure(TABLE, "put_item", FakeClientError("InternalServerError"))
    with pytest.raises(guard.SideEffectGuardUnavailable):
        guard.claim(table, order_id=ORDER, effect=guard.WIX_PAYMENT)


def test_a_storage_error_on_resolve_raises(table):
    table.parent.arm_failure(TABLE, "get_item", FakeClientError("InternalServerError"))
    with pytest.raises(guard.SideEffectGuardUnavailable):
        guard.resolve(table, order_id=ORDER, effect=guard.RECEIPT)


# ── claim -> confirm lifecycle ──────────────────────────────────────────────────

def test_claim_then_confirm_records_the_result(table):
    guard.claim(table, order_id=ORDER, effect=guard.WIX_ORDER)
    guard.confirm(table, order_id=ORDER, effect=guard.WIX_ORDER,
                  result={"wixOrderId": "wix-123"})
    marker = guard.resolve(table, order_id=ORDER, effect=guard.WIX_ORDER)
    assert marker["state"] == guard.DONE
    assert marker["result"] == {"wixOrderId": "wix-123"}
    assert guard.is_done(table, order_id=ORDER, effect=guard.WIX_ORDER) is True


def test_a_claim_without_confirm_is_pending_and_recoverable(table):
    guard.claim(table, order_id=ORDER, effect=guard.CONFIRMATION)
    marker = guard.resolve(table, order_id=ORDER, effect=guard.CONFIRMATION)
    # The crash-between-claim-and-confirm state: visible as pending, NOT done, so a retry finishes.
    assert marker["state"] == guard.PENDING
    assert guard.is_done(table, order_id=ORDER, effect=guard.CONFIRMATION) is False


def test_confirm_without_a_claim_is_refused(table):
    # A confirm must follow a claim; otherwise a crash could look completed.
    with pytest.raises(guard.SideEffectGuardUnavailable):
        guard.confirm(table, order_id=ORDER, effect=guard.RECEIPT)


def test_resolve_is_none_before_any_claim(table):
    assert guard.resolve(table, order_id=ORDER, effect=guard.WIX_ORDER) is None


# ── the §47 invariant: replay the event 5x, each effect happens once ────────────

def test_replaying_an_event_performs_each_side_effect_once(table):
    performed = {guard.WIX_ORDER: 0, guard.WIX_PAYMENT: 0,
                 guard.RECEIPT: 0, guard.CONFIRMATION: 0}

    def reconcile_once():
        for effect in (guard.WIX_ORDER, guard.WIX_PAYMENT,
                       guard.RECEIPT, guard.CONFIRMATION):
            if guard.claim(table, order_id=ORDER, effect=effect):
                performed[effect] += 1          # the actual side effect would run here
                guard.confirm(table, order_id=ORDER, effect=effect)

    for _ in range(5):                          # five duplicate deliveries
        reconcile_once()

    assert performed == {guard.WIX_ORDER: 1, guard.WIX_PAYMENT: 1,
                         guard.RECEIPT: 1, guard.CONFIRMATION: 1}
