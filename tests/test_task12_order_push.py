"""Focused regression tests for Wix Catalog V3 and push devices."""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'amplify' / 'functions' / 'shared'
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))


def load_handler(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    with patch('boto3.client'), patch('boto3.resource'):
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def wix_handler():
    return load_handler(
        'task12_wix_store_handler',
        'amplify/functions/ecommerce/wix-store/handler.py',
    )


@pytest.fixture
def push_handler():
    return load_handler(
        'task12_push_handler',
        'amplify/functions/messaging/push-notifications/handler.py',
    )


def test_v3_product_normalizer_reads_variant_price_sku_and_options(wix_handler):
    product = {
        'id': 'prod-1',
        'revision': '7',
        'name': 'Coffee',
        'slug': 'coffee',
        'currency': 'INR',
        'productType': 'PHYSICAL',
        'plainDescription': 'Fresh coffee',
        'media': {
            'main': {'url': 'https://example.test/coffee.png'},
            'itemsInfo': {'items': [{'url': 'https://example.test/coffee.png'}]},
        },
        'inventory': {'availabilityStatus': 'IN_STOCK'},
        'options': [{
            'name': 'Size',
            'choicesSettings': {'choices': [{'name': 'Small'}, {'name': 'Large'}]},
        }],
        'variantsInfo': {'variants': [{
            'id': 'var-1',
            'sku': 'WD-COFFEE',
            'price': {'actualPrice': {'amount': '199'}},
            'choices': [{
                'optionChoiceNames': {'optionName': 'Size', 'choiceName': 'Small'},
            }],
        }]},
    }

    result = wix_handler._normalize_v3_product(product)

    assert result['_id'] == 'prod-1'
    assert result['price'] == 199.0
    assert result['formattedPrice'] == 'INR 199'
    assert result['sku'] == 'WD-COFFEE'
    assert result['inStock'] is True
    assert result['mainMedia']['url'].endswith('coffee.png')
    assert result['productOptions'][0]['choices'][0]['description'] == 'Small'
    assert result['variants'][0]['choices'] == {'Size': 'Small'}


def test_v3_product_list_hydrates_read_only_variants(wix_handler):
    product_page = {
        'products': [{
            'id': 'prod-1',
            'name': 'Coffee',
            'slug': 'coffee',
            'currency': 'INR',
            'productType': 'PHYSICAL',
            'plainDescription': 'Fresh coffee',
            'inventory': {},
        }],
        'pagingMetadata': {'count': 1, 'cursors': {}},
    }
    variant_page = {
        'variants': [{
            'variantId': 'var-1',
            'sku': 'WD-COFFEE',
            'price': {'actualPrice': {'amount': '199', 'formattedAmount': 'INR 199'}},
            'inventoryStatus': {'inStock': True},
            'productData': {'productId': 'prod-1', 'currency': 'INR'},
            'optionChoices': [{
                'optionChoiceNames': {'optionName': 'Size', 'choiceName': 'Small'},
            }],
        }],
        'pagingMetadata': {'count': 1, 'cursors': {}, 'hasNext': False},
    }

    with patch.object(
        wix_handler,
        '_wix_request',
        side_effect=[product_page, variant_page],
    ) as request:
        response = wix_handler._list_products({}, 'req-list')

    body = json.loads(response['body'])
    assert response['statusCode'] == 200
    assert body['products'][0]['price'] == 199.0
    assert body['products'][0]['sku'] == 'WD-COFFEE'
    assert body['products'][0]['inStock'] is True
    assert body['products'][0]['variants'][0]['choices'] == {'Size': 'Small'}

    product_call = request.call_args_list[0]
    variant_call = request.call_args_list[1]
    assert product_call.args[0] == '/stores/v3/products/query'
    assert 'PLAIN_DESCRIPTION' in product_call.kwargs['body']['fields']
    assert variant_call.args[0] == '/stores/v3/products/query-variants'
    assert variant_call.kwargs['body']['query']['filter'] == {
        'productData.productId': {'$in': ['prod-1']}
    }
    assert variant_call.kwargs['body']['query']['cursorPaging']['limit'] == 1000


def test_whatsapp_order_flow_has_no_velo_http_fallback():
    source = (
        ROOT
        / 'amplify'
        / 'functions'
        / 'messaging'
        / 'whatsapp-business-api'
        / 'flows'
        / 'orders.py'
    ).read_text()

    assert '/_functions/orders' not in source
    assert 'fetch_orders_velo_failed' not in source
    assert 'WIX_SITE_URL' not in source


def test_inventory_lookup_uses_inventory_items_v3_product_filter(wix_handler):
    with patch.object(wix_handler, '_wix_request', return_value={
        'inventoryItems': [{'id': 'inv-1', 'productId': 'prod-1', 'quantity': 4}]
    }) as request:
        response = wix_handler._get_inventory('prod-1', 'req-1')

    assert response['statusCode'] == 200
    endpoint = request.call_args.args[0]
    body = request.call_args.kwargs['body']
    assert endpoint == '/stores/v3/inventory-items/query'
    assert body['query']['filter'] == {'productId': {'$eq': 'prod-1'}}
    assert json.loads(response['body'])['inventoryItems'][0]['quantity'] == 4


def test_create_product_translates_legacy_admin_form_to_catalog_v3(wix_handler):
    created = {
        'id': 'prod-1',
        'revision': '1',
        'name': 'Tea',
        'currency': 'INR',
        'productType': 'PHYSICAL',
        'variantsInfo': {'variants': [{
            'id': 'var-1',
            'sku': 'WD-TEA',
            'price': {'actualPrice': {'amount': '149'}},
        }]},
    }
    with patch.object(wix_handler, '_wix_request', return_value={'product': created}) as request:
        response = wix_handler._create_product_rest({
            'product': {
                'name': 'Tea',
                'productType': 'physical',
                'priceData': {'currency': 'INR', 'price': 149},
                'sku': 'WD-TEA',
                'description': 'Assam tea',
                'weight': 0.25,
            }
        }, 'req-2')

    endpoint = request.call_args.args[0]
    body = request.call_args.kwargs['body']
    assert endpoint == '/stores/v3/products'
    assert body['product']['productType'] == 'PHYSICAL'
    variant = body['product']['variantsInfo']['variants'][0]
    assert variant['sku'] == 'WD-TEA'
    assert variant['price']['actualPrice']['amount'] == '149'
    assert variant['physicalProperties']['weight'] == 0.25
    assert response['statusCode'] == 200


def test_update_product_fetches_and_sends_current_revision(wix_handler):
    current = {
        'id': 'prod-1',
        'revision': '12',
        'name': 'Old',
        'options': [],
        'variantsInfo': {'variants': [{
            'id': 'var-1',
            'sku': 'WD-OLD',
            'price': {'actualPrice': {'amount': '100'}},
        }]},
    }
    updated = {
        **current,
        'revision': '13',
        'name': 'New',
        'currency': 'INR',
    }
    with patch.object(wix_handler, '_wix_request', side_effect=[
        {'product': current},
        {'product': updated},
    ]) as request:
        response = wix_handler._update_product_rest({
            'productId': 'prod-1',
            'updates': {'name': 'New', 'price': 120},
        }, 'req-3')

    patch_call = request.call_args_list[1]
    assert patch_call.args[0] == '/stores/v3/products/prod-1'
    assert patch_call.kwargs['method'] == 'PATCH'
    product = patch_call.kwargs['body']['product']
    assert product['revision'] == '12'
    assert product['name'] == 'New'
    assert product['variantsInfo']['variants'][0]['price']['actualPrice']['amount'] == '120'
    assert response['statusCode'] == 200


def test_push_registration_uses_live_id_key(push_handler):
    push_handler.SNS_ANDROID_ARN = 'android-platform'
    push_handler.sns = MagicMock()
    push_handler.sns.create_platform_endpoint.return_value = {'EndpointArn': 'endpoint-1'}
    push_handler.table = MagicMock()
    response = push_handler.register_token(
        {'deviceToken': 'device-token', 'platform': 'android', 'userId': 'user-1'},
        {},
    )
    assert response['statusCode'] == 200
    item = push_handler.table.put_item.call_args.kwargs['Item']
    assert item['id'] != 'device-token'
    assert item['deviceToken'] == 'device-token'
    assert item['userId'] == 'user-1'


def test_push_user_target_uses_scan_not_missing_gsi(push_handler):
    push_handler.table = MagicMock()
    push_handler.table.scan.return_value = {'Items': []}
    response = push_handler.send_push(
        {'userId': 'user-1', 'title': 'Title', 'body': 'Body'},
        {},
    )
    assert response['statusCode'] == 404
    push_handler.table.scan.assert_called_once()
    push_handler.table.query.assert_not_called()


def test_push_devices_require_admin(push_handler):
    denied = {'statusCode': 403, 'body': '{}'}
    event = {
        'requestContext': {
            'apiId': 'api-1',
            'http': {'method': 'GET', 'path': '/push/devices', 'sourceIp': '127.0.0.1'},
        },
        'rawPath': '/push/devices',
    }
    with patch.object(push_handler, 'require_auth', return_value=denied) as require_auth:
        response = push_handler.handler(event, None)
    assert response is denied
    require_auth.assert_called_once_with(event, required_role='Admin')
