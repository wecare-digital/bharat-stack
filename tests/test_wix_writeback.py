"""The Wix write-back path RECORDS a payment and can never collect one (R7.4).

The test R7.4 asks for, verbatim from the requirement: "an explicit test enumerating the Wix
calls the reconciliation path can make", proving none can charge. Plus: the path is inert by
default (disabled until both the capability probe and the flag are set), it creates the Wix order
once and records the payment once across retries, and no float arithmetic touches the amount.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeDynamo  # noqa: E402
from lambda_utils.ecommerce import wix_writeback as wb  # noqa: E402

TABLE = "stack-wecare-digital-CommerceKeys"
ORDER = "01J8Z9Q9W9EXAMPLEORDERID000000"
TXN = "pay_ABC123"


@pytest.fixture
def table():
    return FakeDynamo(keys={TABLE: "orderId"}).Table(TABLE)


class _RecordingWix:
    """Captures every Wix call so a test can enumerate exactly what the path did."""

    def __init__(self):
        self.calls = []

    def __call__(self, path, method="GET", body=None):
        self.calls.append((method.upper(), path))
        if path == "/ecom/v1/orders":
            return {"order": {"id": "wix-order-1"}}
        if "/add-payment" in path:
            return {"orderTransactions": {"orderId": "wix-order-1", "payments": body["payments"]}}
        raise AssertionError(f"unexpected Wix call: {method} {path}")


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("WIX_WRITEBACK_ENABLED", "true")
    monkeypatch.setenv("WIX_ECOM_WRITE_CONFIRMED", "true")
    monkeypatch.setenv("WIX_SITE_ID", wb.CONFIRMED_SITE_ID)
    monkeypatch.setenv("WIX_CART_V2_WRITE_CONTRACT", wb.WRITE_CONTRACT)


# ── R7.4: enumerate the calls, none can charge ──────────────────────────────────

def test_the_only_allowed_endpoints_are_create_order_and_record_payment():
    # The complete, static set. If someone adds an endpoint, this fails until they update the
    # test — which forces a human to look at whether the new endpoint can charge.
    assert wb.ALLOWED_ENDPOINTS == frozenset({
        ("POST", "/ecom/v1/orders"),
        ("POST", "/ecom/v1/payments/orders/{orderId}/add-payment"),
    })


def test_no_allowed_endpoint_is_a_charging_endpoint():
    # Every allowlisted path, checked against the charging markers. None may match.
    for _method, template in wb.ALLOWED_ENDPOINTS:
        concrete = template.replace("{orderId}", "wix-order-1")
        assert not wb._endpoint_would_charge(concrete), \
            f"{template} matches a charging marker"


@pytest.mark.parametrize("charging_path", [
    "/ecom/v1/payments/create-transaction",
    "/ecom/v1/orders/wix-order-1/charge",
    "/ecom/v1/orders/wix-order-1/capture",
    "/ecom/v1/orders/wix-order-1/payment-requests",
    "/ecom/v1/checkout/wix-order-1",
])
def test_a_charging_call_is_refused_before_any_request(charging_path):
    wix = _RecordingWix()
    with pytest.raises(wb.WixWouldCharge):
        wb._guarded_call(wix, method="POST", path=charging_path)
    # Nothing was sent.
    assert wix.calls == []


def test_an_off_allowlist_call_is_refused():
    wix = _RecordingWix()
    with pytest.raises(wb.WixEndpointNotAllowed):
        wb._guarded_call(wix, method="DELETE", path="/ecom/v1/orders/wix-order-1")
    assert wix.calls == []


def test_a_full_reconciliation_writeback_makes_only_non_charging_calls(table, enabled):
    wix = _RecordingWix()
    wb.create_wix_order(table, wix, order_id=ORDER, order_payload={"lineItems": []})
    wb.record_external_payment(table, wix, order_id=ORDER, wix_order_id="wix-order-1",
                               provider_transaction_id=TXN, amount_paise=59900)
    # Enumerate: exactly create-order then add-payment. Both non-charging by the markers.
    assert wix.calls == [
        ("POST", "/ecom/v1/orders"),
        ("POST", "/ecom/v1/payments/orders/wix-order-1/add-payment"),
    ]
    for _method, path in wix.calls:
        assert not wb._endpoint_would_charge(path)


# ── inert by default ────────────────────────────────────────────────────────────

def test_disabled_by_default_even_with_the_flag_alone(monkeypatch, table):
    monkeypatch.setenv("WIX_WRITEBACK_ENABLED", "true")   # flag on
    monkeypatch.delenv("WIX_ECOM_WRITE_CONFIRMED", raising=False)  # probe NOT confirmed
    assert wb.is_enabled() is False
    with pytest.raises(wb.WixWritebackDisabled):
        wb.create_wix_order(table, _RecordingWix(), order_id=ORDER, order_payload={})


def test_disabled_with_the_probe_alone(monkeypatch, table):
    monkeypatch.delenv("WIX_WRITEBACK_ENABLED", raising=False)
    monkeypatch.setenv("WIX_ECOM_WRITE_CONFIRMED", "true")
    assert wb.is_enabled() is False


# ── idempotency: order once, payment once ───────────────────────────────────────

def test_create_order_is_idempotent(table, enabled):
    wix = _RecordingWix()
    first = wb.create_wix_order(table, wix, order_id=ORDER, order_payload={})
    second = wb.create_wix_order(table, wix, order_id=ORDER, order_payload={})
    assert first["created"] is True
    assert second["created"] is False
    assert second["wixOrderId"] == "wix-order-1"
    # Only ONE create call was made across two invocations.
    assert [c for c in wix.calls if c == ("POST", "/ecom/v1/orders")] == \
        [("POST", "/ecom/v1/orders")]


def test_record_payment_is_idempotent(table, enabled):
    wix = _RecordingWix()
    first = wb.record_external_payment(table, wix, order_id=ORDER, wix_order_id="wix-order-1",
                                       provider_transaction_id=TXN, amount_paise=59900)
    second = wb.record_external_payment(table, wix, order_id=ORDER, wix_order_id="wix-order-1",
                                        provider_transaction_id=TXN, amount_paise=59900)
    assert first["recorded"] is True
    assert second["recorded"] is False
    add_calls = [c for c in wix.calls if "/add-payment" in c[1]]
    assert len(add_calls) == 1


# ── money is integer paise, no float ────────────────────────────────────────────

@pytest.mark.parametrize("paise,expected", [
    (59900, "599.00"), (1, "0.01"), (100, "1.00"), (349900, "3499.00"), (10, "0.10")])
def test_paise_renders_without_float(paise, expected):
    assert wb._paise_to_decimal_string(paise) == expected


def test_record_payment_rejects_non_integer_amount(table, enabled):
    with pytest.raises(TypeError):
        wb.record_external_payment(table, _RecordingWix(), order_id=ORDER,
                                   wix_order_id="wix-order-1", provider_transaction_id=TXN,
                                   amount_paise=599.0)  # float refused


@pytest.mark.parametrize('field,value', [
    ('WIX_SITE_ID', 'wrong-site'), ('WIX_SITE_ID', ''),
    ('WIX_CART_V2_WRITE_CONTRACT', ''), ('WIX_CART_V2_WRITE_CONTRACT', 'v1')])
def test_site_and_contract_gates_block_all_order_writes(table, enabled, monkeypatch, field, value):
    monkeypatch.setenv(field, value)
    wix = _RecordingWix()
    with pytest.raises(wb.WixWritebackDisabled):
        wb.create_wix_order(table, wix, order_id=ORDER, order_payload={})
    assert wix.calls == []


def test_timeout_cannot_create_a_second_wix_order(table, enabled):
    calls = []
    def uncertain(*args, **kwargs):
        calls.append(args)
        raise TimeoutError('could have succeeded')
    with pytest.raises(TimeoutError):
        wb.create_wix_order(table, uncertain, order_id=ORDER, order_payload={})
    with pytest.raises(wb.WixWritebackPending):
        wb.create_wix_order(table, uncertain, order_id=ORDER, order_payload={})
    assert len(calls) == 1


def test_incomplete_wix_response_is_not_recorded_as_success(table, enabled):
    with pytest.raises(wb.WixWritebackPending):
        wb.create_wix_order(table, lambda *a, **k: {}, order_id=ORDER, order_payload={})
    with pytest.raises(wb.WixWritebackPending):
        wb.create_wix_order(table, _RecordingWix(), order_id=ORDER, order_payload={})


def test_confirmed_payment_cannot_be_reused_with_different_amount(table, enabled):
    wix = _RecordingWix()
    kwargs = dict(order_id=ORDER, wix_order_id='wix-order-1', provider_transaction_id=TXN)
    wb.record_external_payment(table, wix, amount_paise=59900, **kwargs)
    with pytest.raises(wb.WixWritebackPending):
        wb.record_external_payment(table, wix, amount_paise=59901, **kwargs)
    assert len(wix.calls) == 1
