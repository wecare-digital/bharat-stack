"""A capture is usable only through a previously trusted attempt binding."""
import pathlib
import sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'amplify/functions/shared'))
from lambda_utils.integrations import razorpay_verify as rv


def captured(**overrides):
    return {'id': 'pay_bound', 'order_id': 'order_bound', 'status': 'captured',
            'amount': 59900, 'currency': 'INR', **overrides}


def test_event_alone_cannot_prove_payment_binding(monkeypatch):
    monkeypatch.setattr(rv, '_get', lambda _: pytest.fail('must not fetch event-selected payment'))
    with pytest.raises(rv.RazorpayUnavailable):
        rv.verifier_for_event(payment_id='pay_attacker', load_attempt=lambda _: {})('ref')


def test_matching_amount_from_another_order_is_rejected(monkeypatch):
    monkeypatch.setattr(rv, '_get', lambda _: captured(id='pay_attacker', order_id='order_other'))
    verify = rv.verifier_for_event(payment_id='pay_attacker',
                                   load_attempt=lambda _: {'providerOrderId': 'order_bound'})
    with pytest.raises(rv.RazorpayUnavailable):
        verify('ref')


def test_trusted_order_and_actual_payment_id_are_verified(monkeypatch):
    paths = []
    def get(path):
        paths.append(path)
        return captured()
    monkeypatch.setattr(rv, '_get', get)
    verify = rv.verifier_for_event(payment_id='pay_bound',
                                   load_attempt=lambda _: {'providerOrderId': 'order_bound'})
    assert verify('ref') == (True, 'pay_bound', 59900, 'INR')
    assert paths == ['/payments/pay_bound']


@pytest.mark.parametrize('amount', [59900.1, True, '59900', 0])
def test_provider_amount_is_not_coerced(monkeypatch, amount):
    monkeypatch.setattr(rv, '_get', lambda _: captured(amount=amount))
    verify = rv.verifier_for_event(payment_id='pay_bound',
                                   load_attempt=lambda _: {'providerPaymentId': 'pay_bound'})
    with pytest.raises(ValueError):
        verify('ref')


def test_order_lookup_uses_saved_order_not_webhook_order(monkeypatch):
    paths = []
    def get(path):
        paths.append(path)
        return {'items': [captured()]}
    monkeypatch.setattr(rv, '_get', get)
    verify = rv.verifier_for_event(order_id='order_attacker',
                                   load_attempt=lambda _: {'providerOrderId': 'order_bound'})
    assert verify('ref')[0] is True
    assert paths == ['/orders/order_bound/payments']
