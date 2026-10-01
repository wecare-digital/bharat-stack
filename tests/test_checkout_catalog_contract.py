import pytest
from lambda_utils import wix_ecom
from lambda_utils.ecommerce.cart_v2 import STORES_APP_ID

PRODUCT = '8c4d4a7d-18c8-44f4-8eb0-78b9844a2365'
VARIANT = '69e90199-0a98-4d63-b743-05f5dbfbde2a'


def line(**options):
    return {'catalogReference': {'appId': STORES_APP_ID, 'catalogItemId': PRODUCT,
                                 'options': options}, 'quantity': 2}


def product(variants):
    return {'product': {'id': PRODUCT, 'visible': True, 'variantsInfo': {'variants': variants}}}


def variant(key=VARIANT):
    return {'id': key, 'visible': True, 'inventoryStatus': {'inStock': True}}


def test_resolves_single_variant_and_emits_no_browser_price(monkeypatch):
    monkeypatch.setattr(wix_ecom, '_request', lambda *args, **kwargs: product([variant()]))
    result = wix_ecom.normalized_catalog_items([line()])
    assert result == [line(variantId=VARIANT)]


def test_never_guesses_multi_variant_or_accepts_another_products_variant(monkeypatch):
    monkeypatch.setattr(wix_ecom, '_request', lambda *args, **kwargs: product([
        variant(), variant('2771864b-e525-4cb3-b8e4-c4e32101dc95')]))
    for supplied in (line(), line(variantId='unrelated')):
        with pytest.raises(wix_ecom.WixEcomError):
            wix_ecom.normalized_catalog_items([supplied])
    assert wix_ecom.normalized_catalog_items([line(variantId=VARIANT)]) == [line(variantId=VARIANT)]


def test_rejects_old_string_references_and_browser_money_before_provider_call(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('invalid input reached provider')
    monkeypatch.setattr(wix_ecom, '_request', forbidden)
    for supplied in ({'catalogReference': PRODUCT, 'quantity': 1},
                     {**line(), 'price': 1}, {**line(), 'quantity': True}):
        with pytest.raises(wix_ecom.WixEcomError):
            wix_ecom.normalized_catalog_items([supplied])
