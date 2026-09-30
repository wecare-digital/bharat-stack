"""Cart contracts replay the redacted Oct 1 live demo response; no live writes."""
import copy
import json
import pathlib
import sys
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'amplify/functions/shared'))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from lambda_utils.ecommerce.cart_v2 import CartV2, CartContractError, catalog_item
from lambda_utils.ecommerce.money import Money, positive_paise
from lambda_utils.ecommerce.customer_cart import CustomerCart, CartBusy, CartMissing
from lambda_utils.customer_auth import CustomerIdentity, CustomerNotAuthorized
from crm_fake_dynamo import FakeDynamo

FIXTURE = pathlib.Path(__file__).parent / 'fixtures/wix_cart_v2_live_demo.json'


def live():
    return json.loads(FIXTURE.read_text())


def ready():
    # Explicitly synthetic success fixture; live demo lacked delivery details.
    result = live()
    result['cart']['demo'] = False
    result['summary']['violations'] = []
    return result


def item():
    ref = live()['cart']['lineItems'][0]['source']['catalogReference']
    return {'productId': ref['catalogItemId'], 'variantId': ref['options']['variantId'], 'quantity': 1}


class Wix:
    def __init__(self, response=None):
        self.calls = []
        self.response = ready() if response is None else response
        self.fail = False

    def __call__(self, path, method='GET', body=None):
        self.calls.append((method, path, body))
        if self.fail:
            raise TimeoutError('uncertain write')
        return copy.deepcopy(self.response)


@pytest.mark.parametrize('value,paise', [('0', 0), ('0.01', 1), ('599.9', 59990),
                                      ('24999.00', 2499900)])
def test_exact_money(value, paise):
    assert Money.from_wix(value).paise == paise
    assert Money.from_wix(Money(paise).to_wix()).paise == paise


@pytest.mark.parametrize('value', [True, 5.99, 599, Decimal('5.99'), '-1', 'NaN', '1e2',
                                 '0.001', '', ' 1', '90071992547410.00'])
def test_reject_ambiguous_or_fractional_money(value):
    with pytest.raises(ValueError):
        Money.from_wix(value)


def test_dynamo_minor_units_remain_exact():
    assert positive_paise(Decimal('59900')) == 59900
    with pytest.raises(ValueError):
        positive_paise(Decimal('59900.1'))


def test_live_contract_blocks_missing_shipping():
    response = live()
    with pytest.raises(CartContractError):
        CartV2(Wix(response)).calculate(response['cart']['id'])


def test_full_calculation_has_bound_integer_snapshot():
    wix = Wix()
    snap = CartV2(wix).calculate(wix.response['cart']['id'])
    assert snap['amountPaise'] == 2499900
    assert snap['cartRevision'] == '3'
    assert snap['calculationId'] == wix.response['summary']['calculationId']
    assert wix.calls[0][2] == {'refreshCart': True}
    assert 'wixCheckoutId' not in snap


@pytest.mark.parametrize('mutation', [
    lambda r: r['summary']['priceSummary']['total'].update(amount='24999.01'),
    lambda r: r['summary'].update(cartRevision='999'),
    lambda r: r['cart']['businessInfo'].update(currencyCode='USD'),
    lambda r: r['cart']['paymentInfo'].update(currencyCode='USD'),
    lambda r: r['cart']['customerInfo'].update(currencyCode='USD'),
    lambda r: r['cart']['lineItems'][0]['quantityInfo'].update(requestedQuantity=2),
    lambda r: r['summary']['paymentSummary'].update(giftCards=[{'id': 'gift'}]),
    lambda r: r['summary']['paymentSummary']['payLater'].update(amount='1'),
    lambda r: r['summary']['paymentSummary']['payNow'].update(amount='1'),
    lambda r: r['summary'].update(priceVerificationToken=''),
    lambda r: r['summary'].update(violations=[{'severity': 'UNKNOWN'}]),
    lambda r: r['cart'].update(orderPlaced=True),
])
def test_unsafe_calculation_never_returns_quote(mutation):
    wix = Wix()
    mutation(wix.response)
    with pytest.raises(ValueError):
        CartV2(wix).calculate(wix.response['cart']['id'])


@pytest.mark.parametrize('extra', ['price', 'amount', 'customerId', 'catalogOverrideFields'])
def test_catalog_inputs_cannot_override_price_or_owner(extra):
    with pytest.raises(ValueError):
        catalog_item({**item(), extra: 'attacker'})


@pytest.fixture
def cart_store():
    table = FakeDynamo(keys={'keys': 'orderId'}).Table('keys')
    wix = Wix()
    identity = CustomerIdentity(customer_id='customer-a', phone='+919330994400', subject='subject-a')
    return CustomerCart(table, CartV2(wix), now=1000), table, wix, identity


def create(store, identity):
    command = {'action': 'create', 'requestId': str(uuid4()), 'items': [item()]}
    return command, store.execute(identity, command)


def test_phone_cart_replay_and_no_browser_wix_id(cart_store):
    store, table, wix, identity = cart_store
    command, result = create(store, identity)
    assert store.execute(identity, command) == result
    assert len(wix.calls) == 1
    assert set(result) == {'items'}
    row = next(iter(table.rows.values()))
    assert row['orderId'] == 'CUSTOMERCART#' + identity.phone
    assert row['wixCartId'] == wix.response['cart']['id']
    assert not any(k.startswith(('ORDERNO#', 'PAYREF#')) for k in table.rows)


def test_same_phone_different_customer_cannot_adopt_cart(cart_store):
    store, table, wix, identity = cart_store
    create(store, identity)
    impostor = CustomerIdentity(customer_id='customer-b', phone=identity.phone, subject='subject-b')
    with pytest.raises(CustomerNotAuthorized):
        store.execute(impostor, {'action': 'get'})
    assert len(wix.calls) == 1


def test_body_cannot_choose_cart_or_phone(cart_store):
    store, _, wix, identity = cart_store
    for key in ('wixCartId', 'phone', 'customerId', 'amountPaise'):
        with pytest.raises(ValueError):
            store.execute(identity, {'action': 'get', key: 'attacker'})
    assert not wix.calls


def test_uncertain_create_never_replays_even_after_expiry(cart_store):
    store, _, wix, identity = cart_store
    wix.fail = True
    command = {'action': 'create', 'requestId': str(uuid4()), 'items': [item()]}
    with pytest.raises(TimeoutError):
        store.execute(identity, command)
    store.now += 9999999
    with pytest.raises(CartBusy):
        store.execute(identity, command)
    assert len(wix.calls) == 1


def test_known_validation_failure_allows_customer_to_fix_cart(cart_store):
    store, _, wix, identity = cart_store
    create(store, identity)
    wix.response = live()
    with pytest.raises(CartContractError):
        store.execute(identity, {'action': 'calculate', 'requestId': str(uuid4())})
    assert store.execute(identity, {'action': 'get'})['items']


def test_quote_is_private_and_invalidated_by_mutation(cart_store):
    store, table, wix, identity = cart_store
    create(store, identity)
    result = store.execute(identity, {'action': 'calculate', 'requestId': str(uuid4())})
    assert result['amountPaise'] == 2499900
    assert 'priceVerificationToken' not in json.dumps(result)
    assert next(iter(table.rows.values()))['snapshot']['expiresAt'] == 1300
    store.execute(identity, {'action': 'add', 'requestId': str(uuid4()), 'item': item()})
    assert 'snapshot' not in next(iter(table.rows.values()))


def test_older_request_cannot_add_again_after_an_intervening_mutation(cart_store):
    store, _, wix, identity = cart_store
    create(store, identity)
    first = {'action': 'add', 'requestId': str(uuid4()), 'item': item()}
    store.execute(identity, first)
    store.execute(identity, {'action': 'add', 'requestId': str(uuid4()), 'item': item()})
    count = len(wix.calls)
    store.execute(identity, first)
    assert len(wix.calls) == count


def test_same_request_id_cannot_be_reused_for_different_amount_of_goods(cart_store):
    store, _, _, identity = cart_store
    command, _ = create(store, identity)
    command['items'][0]['quantity'] = 2
    with pytest.raises(ValueError):
        store.execute(identity, command)


def test_concurrent_cart_writer_loses_before_calling_wix(cart_store):
    store, table, wix, identity = cart_store
    create(store, identity)
    original_put = table.put_item

    def race(**kwargs):
        pending = kwargs['Item']
        if pending.get('busy'):
            key = pending['orderId']
            table.rows[key]['version'] += 1
        return original_put(**kwargs)

    table.put_item = race
    with pytest.raises(CartBusy):
        store.execute(identity, {'action': 'add', 'requestId': str(uuid4()), 'item': item()})
    assert len(wix.calls) == 1


def test_expired_cart_does_not_return_or_order(cart_store):
    store, _, wix, identity = cart_store
    create(store, identity)
    store.now += 9999999
    with pytest.raises(CartMissing):
        store.execute(identity, {'action': 'get'})
    assert len(wix.calls) == 1


def test_cart_methods_cannot_place_or_charge_an_order():
    wix = Wix()
    adapter = CartV2(wix)
    cart_id = wix.response['cart']['id']
    line_id = wix.response['cart']['lineItems'][0]['id']
    adapter.create([item()]); adapter.get(cart_id); adapter.add(cart_id, item())
    adapter.set_quantity(cart_id, line_id, 2); adapter.remove(cart_id, line_id)
    adapter.calculate(cart_id)
    assert [(method, path.replace(cart_id, '{id}')) for method, path, _ in wix.calls] == [
        ('POST', '/ecom/v2/carts'), ('GET', '/ecom/v2/carts/{id}'),
        ('POST', '/ecom/v2/carts/{id}/add-line-items'),
        ('POST', '/ecom/v2/carts/{id}/update-line-items'),
        ('POST', '/ecom/v2/carts/{id}/remove-line-items'),
        ('POST', '/ecom/v2/carts/{id}/calculate')]


@pytest.fixture
def handler_module(monkeypatch):
    import importlib.util
    from unittest.mock import MagicMock
    import boto3
    monkeypatch.setattr(boto3, 'client', MagicMock())
    monkeypatch.setattr(boto3, 'resource', MagicMock())
    path = pathlib.Path(__file__).resolve().parents[1] / 'amplify/functions/ecommerce/wix-store/handler.py'
    spec = importlib.util.spec_from_file_location('cart_v2_handler_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cart_route_rejects_missing_customer_session_before_any_wix_call(handler_module, monkeypatch):
    monkeypatch.setattr(handler_module, '_wix_request', lambda *a, **k: pytest.fail('unauthorized call'))
    response = handler_module.handler({'httpMethod': 'POST', 'path': '/wix-store/cart',
                                       'headers': {}, 'body': '{}'}, None)
    assert response['statusCode'] == 401


def test_authenticated_cart_route_stays_disabled_until_deployment_verification(handler_module, monkeypatch):
    from lambda_utils import customer_auth
    identity = CustomerIdentity(customer_id='a', phone='+919330994400', subject='a')
    monkeypatch.setattr(customer_auth, 'require_customer', lambda _: (identity, None))
    monkeypatch.delenv('WIX_CART_V2_ENABLED', raising=False)
    monkeypatch.setattr(handler_module, '_wix_request', lambda *a, **k: pytest.fail('disabled call'))
    response = handler_module.handler({'httpMethod': 'GET', 'path': '/wix-store/cart', 'headers': {}}, None)
    assert response['statusCode'] == 503


def test_quote_replay_keeps_json_money_an_integer_after_dynamodb_roundtrip(cart_store):
    store, table, _, identity = cart_store
    create(store, identity)
    command = {'action': 'calculate', 'requestId': str(uuid4())}
    store.execute(identity, command)
    for key in list(table.rows):
        table.rows[key] = json.loads(json.dumps(table.rows[key]), parse_int=Decimal)
    result = store.execute(identity, command)
    assert type(result['amountPaise']) is int
    assert '2499900' in json.dumps(result)


def test_replayed_quote_is_rejected_after_cart_changes(cart_store):
    store, _, _, identity = cart_store
    create(store, identity)
    command = {'action': 'calculate', 'requestId': str(uuid4())}
    store.execute(identity, command)
    store.execute(identity, {'action': 'add', 'requestId': str(uuid4()), 'item': item()})
    with pytest.raises(ValueError):
        store.execute(identity, command)


def test_demo_never_becomes_payable_even_with_no_reported_violations():
    response = ready()
    response['cart']['demo'] = True
    with pytest.raises(CartContractError):
        CartV2(Wix(response)).calculate(response['cart']['id'])
