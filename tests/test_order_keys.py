"""Order identity: reservation, resolve-before-generate, and Meta's reference_id limits.

Uses `crm_fake_dynamo.FakeDynamo` rather than a recording stub, for the reason that file
states: everything worth testing here *is* the ConditionExpression, and a fake that accepts
any condition would let a broken guard pass.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402
from lambda_utils.ecommerce import order_keys  # noqa: E402

TABLE = 'stack-wecare-digital-WixOrderIds'


@pytest.fixture
def table():
    # The live table's key is `orderId` (measured via DescribeTable), even though the
    # Amplify model declares `wixOrderId`. Tests bind to the physical truth.
    return FakeDynamo(keys={TABLE: 'orderId'}).Table(TABLE)


def _counting_generator(numbers):
    """A generator that yields a scripted sequence, to force collisions deterministically."""
    it = iter(numbers)
    return lambda _date='': next(it)


# ── Meta reference_id constraints (R2.9, and Meta's documented limits) ──────────

def test_meta_reference_id_limit_is_thirty_five():
    assert order_keys.META_REFERENCE_ID_MAX_LENGTH == 35


@pytest.mark.parametrize('value', [
    'WD-PAY-ABC123',
    'WD.PAY_123-x',
    'a',
    'A' * 35,
])
def test_valid_reference_ids_are_accepted(value):
    assert order_keys.is_valid_meta_reference_id(value)


@pytest.mark.parametrize('value', [
    '',                       # Meta: cannot be an empty string
    'A' * 36,                 # Meta: must not exceed 35 characters
    'WD PAY 123',             # space is outside the permitted charset
    'WD-ORD - A1B2C3D4 - 22-02-2026 - 23:30:00 - IST',  # the order number itself
    'ref/123',
    'ref#123',
    'ref@123',
    None,
    12345,
])
def test_invalid_reference_ids_are_rejected(value):
    assert not order_keys.is_valid_meta_reference_id(value)
    with pytest.raises(ValueError):
        order_keys.assert_valid_meta_reference_id(value)


def test_the_order_number_can_never_be_used_as_a_reference_id():
    """R2.9. This is the *reason* the two identifiers are separate, not a style choice:
    the order number is 46 chars and contains spaces and colons."""
    from lambda_utils.ecommerce.wix_domain import _generate_wd_order_number
    number = _generate_wd_order_number('2026-02-22T18:00:00Z')
    assert len(number) > order_keys.META_REFERENCE_ID_MAX_LENGTH
    assert not order_keys.is_valid_meta_reference_id(number)


def test_minted_reference_ids_are_always_meta_valid_and_unique():
    minted = {order_keys.mint_reference_id() for _ in range(5000)}
    assert len(minted) == 5000, 'mint_reference_id produced a duplicate'
    assert all(order_keys.is_valid_meta_reference_id(r) for r in minted)
    assert all(len(r) <= order_keys.RAZORPAY_RECEIPT_MAX_LENGTH for r in minted)


def test_mint_does_not_use_the_random_module():
    """SnapStart freezes `random`'s seed into the snapshot. Off today, but a payment join
    key must not depend on that remaining true."""
    import inspect
    source = inspect.getsource(order_keys)
    assert 'import secrets' in source
    assert 'import random' not in source


# ── the reuse check that never matched ─────────────────────────────────────────

def test_is_wd_order_number_matches_the_format_actually_generated():
    """The defect: `startswith('WD-ORD-')` is False for every number ever generated,
    because the generator emits a SPACE at index 6."""
    from lambda_utils.ecommerce.wix_domain import _generate_wd_order_number
    number = _generate_wd_order_number('2026-02-22T18:00:00Z')
    assert not number.startswith('WD-ORD-'), 'format changed; this test is now stale'
    assert order_keys.is_wd_order_number(number)


def test_is_wd_order_number_also_matches_the_compact_order_table_format():
    assert order_keys.is_wd_order_number('WD-ORD-A1B2C3D4')


@pytest.mark.parametrize('value', ['', 'WD-ORD', 'ORD-A1B2C3D4', 'WD-PAY-A1B2C3D4', None])
def test_is_wd_order_number_rejects_non_order_numbers(value):
    assert not order_keys.is_wd_order_number(value)


# ── reservation (R2.3, R2.4, R2.5) ─────────────────────────────────────────────

def test_reservation_row_is_written_before_the_number_is_returned(table):
    number = order_keys.reserve_order_number(table, '2026-02-22T18:00:00Z')
    row = table.get_item(Key={'orderId': order_keys.ORDER_NUMBER_PREFIX + number})['Item']
    assert row['orderNumber'] == number
    assert row['kind'] == 'ORDER_NUMBER_RESERVATION'


def test_ten_thousand_reservations_contain_no_duplicate(table):
    """R2.8. Asserted against the store, not against the generator, so a generator that
    repeats itself is caught by the conditional write rather than hidden by it."""
    numbers = [order_keys.reserve_order_number(table, '2026-02-22T18:00:00Z')
               for _ in range(10000)]
    assert len(set(numbers)) == 10000
    reserved = [k for k in table.rows if str(k).startswith(order_keys.ORDER_NUMBER_PREFIX)]
    assert len(reserved) == 10000


def test_a_collision_regenerates_rather_than_overwriting(table):
    """R2.4. The first number is taken; the caller must get the second, and the existing
    reservation must be left intact."""
    taken = order_keys.reserve_order_number(table, '', generate=lambda _d='': 'WD-ORD - AAAAAAAA - x')
    before = dict(table.get_item(Key={'orderId': order_keys.ORDER_NUMBER_PREFIX + taken})['Item'])

    got = order_keys.reserve_order_number(
        table, '', generate=_counting_generator([taken, 'WD-ORD - BBBBBBBB - x']))

    assert got == 'WD-ORD - BBBBBBBB - x'
    after = table.get_item(Key={'orderId': order_keys.ORDER_NUMBER_PREFIX + taken})['Item']
    assert after == before, 'the pre-existing reservation was mutated'


def test_exhausting_attempts_fails_closed(table):
    """R2.5. Never return a number that was not reserved."""
    order_keys.reserve_order_number(table, '', generate=lambda _d='': 'WD-ORD - CCCCCCCC - x')
    with pytest.raises(order_keys.OrderIdentityUnavailable):
        order_keys.reserve_order_number(
            table, '', generate=lambda _d='': 'WD-ORD - CCCCCCCC - x', attempts=3)


def test_a_dynamodb_error_yields_no_number_at_all(table):
    """R2.5, the defect being removed: the old code returned an UNSTORED number here."""
    table.parent.arm_failure(TABLE, 'put_item', FakeClientError('ProvisionedThroughputExceeded'))
    with pytest.raises(order_keys.OrderIdentityUnavailable):
        order_keys.reserve_order_number(table, '2026-02-22T18:00:00Z')
    assert table.parent.count(TABLE) == 0, 'a number leaked out of a failed reservation'


def test_a_read_error_raises_rather_than_reporting_no_reference(table):
    """A storage outage must not be indistinguishable from 'this reference is unknown',
    because the caller treats unknown as 'do not create an order'."""
    table.parent.arm_failure(TABLE, 'get_item', FakeClientError('ThrottlingException'))
    with pytest.raises(order_keys.OrderIdentityUnavailable):
        order_keys.resolve_reference(table, 'WD-PAY-ABC123')


# ── resolve-before-generate (R2.6, R2.7, R2.9) ─────────────────────────────────

def test_allocate_binds_a_reference_to_exactly_one_order_number(table):
    ref, number, created = order_keys.allocate_order_identity(table, order_date='2026-02-22T18:00:00Z')
    assert created is True
    assert order_keys.is_valid_meta_reference_id(ref)
    assert order_keys.is_wd_order_number(number)
    row = table.get_item(Key={'orderId': order_keys.REFERENCE_PREFIX + ref})['Item']
    assert row['orderNumber'] == number


def test_a_redelivered_meta_event_resolves_to_the_same_order(table):
    """R2.6. Five deliveries of one reference must produce one order number and one
    reservation, not five."""
    ref, first, created = order_keys.allocate_order_identity(table, order_date='2026-02-22T18:00:00Z')
    assert created is True

    for _ in range(4):
        again_ref, again, again_created = order_keys.allocate_order_identity(
            table, order_date='2026-02-22T18:00:00Z', reference_id=ref)
        assert (again_ref, again) == (ref, first)
        assert again_created is False

    reserved = [k for k in table.rows if str(k).startswith(order_keys.ORDER_NUMBER_PREFIX)]
    assert len(reserved) == 1


def test_retry_after_a_timeout_keeps_the_same_number(table):
    """R2.7. The caller re-enters with the reference it already minted."""
    ref = order_keys.mint_reference_id()
    _, first, created_first = order_keys.allocate_order_identity(
        table, order_date='2026-02-22T18:00:00Z', reference_id=ref)
    _, second, created_second = order_keys.allocate_order_identity(
        table, order_date='2026-02-22T18:00:00Z', reference_id=ref)
    assert first == second
    assert (created_first, created_second) == (True, False)


def test_an_unknown_reference_resolves_to_nothing(table):
    """Design step 3: no mapping means no order. A payment event must not mint one."""
    assert order_keys.resolve_reference(table, 'WD-PAY-NEVERSEEN') is None


def test_losing_the_bind_race_adopts_the_winner_and_never_reissues(table):
    """Two workers, one fresh reference. The loser must adopt the winner's number; the
    number it reserved is burned, which is the safe direction to lose in."""
    ref = order_keys.mint_reference_id()
    table.put_item(Item={
        'orderId': order_keys.REFERENCE_PREFIX + ref,
        'kind': 'REFERENCE_BINDING',
        'referenceId': ref,
        'orderNumber': 'WD-ORD - WINNER01 - x',
    })

    # Force the pre-read to miss so the code reaches the bind and loses it, which is the
    # real interleaving: both workers read 'absent', then both try to bind.
    seen = {'first': True}
    real_get = table.get_item

    def get_item(Key=None, **kw):
        if seen.pop('first', None) and Key.get('orderId', '').startswith(order_keys.REFERENCE_PREFIX):
            return {}
        return real_get(Key=Key, **kw)

    table.get_item = get_item

    got_ref, number, created = order_keys.allocate_order_identity(
        table, order_date='2026-02-22T18:00:00Z', reference_id=ref)

    assert (got_ref, number, created) == (ref, 'WD-ORD - WINNER01 - x', False)


def test_allocate_rejects_a_reference_meta_would_not_accept(table):
    with pytest.raises(ValueError):
        order_keys.allocate_order_identity(table, reference_id='WD PAY 123')
    assert table.parent.count(TABLE) == 0


# ── the reservation must never expire ──────────────────────────────────────────

def test_no_reservation_row_carries_a_ttl(table):
    """A TTL on a uniqueness reservation is a number that gets reissued once it expires.
    The live table has TTL DISABLED; this asserts the rows would not opt in either."""
    ref, number, _ = order_keys.allocate_order_identity(table, order_date='2026-02-22T18:00:00Z')
    for row in table.parent.all_rows(TABLE):
        assert 'ttl' not in row
        assert 'expiresAt' not in row
