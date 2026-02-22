"""
Wix Store Integration Lambda Function

Purpose: Full bridge between WECARE.DIGITAL platform and Wix Stores/eCommerce REST APIs.
Supports two modes:
  - 'api' (default): Wix REST API at wixapis.com
  - 'velo': Velo HTTP Functions on your published Wix site (yoursite.com/_functions/*)

Velo mode gives access to custom order numbers and all Wix Data collection fields
that aren't exposed through the standard REST API.

Wix API Docs: https://dev.wix.com/docs/rest/business-solutions/stores
Velo HTTP Functions: https://dev.wix.com/docs/velo/apis/wix-http-functions
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import boto3

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Mode: 'api' or 'velo'
WIX_MODE = os.environ.get('WIX_MODE', 'api')

# REST API config
WIX_API_KEY = os.environ.get('WIX_API_KEY', '')
WIX_SITE_ID = os.environ.get('WIX_SITE_ID', '')
WIX_ACCOUNT_ID = os.environ.get('WIX_ACCOUNT_ID', '')
WIX_API_BASE = os.environ.get('WIX_API_BASE_URL', 'https://www.wixapis.com')

# Velo HTTP Functions config
WIX_VELO_BASE = os.environ.get('WIX_VELO_BASE_URL', '')  # e.g. https://www.yoursite.com
WIX_VELO_API_KEY = os.environ.get('WIX_VELO_API_KEY', '')  # shared secret for auth
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
PRODUCTS_CACHE_TABLE = os.environ.get('WIX_PRODUCTS_CACHE_TABLE', 'base-wecare-digital-WixProductsCache')
ORDERS_CACHE_TABLE = os.environ.get('WIX_ORDERS_CACHE_TABLE', 'base-wecare-digital-WixOrdersCache')


# ===================================================================
# HANDLER
# ===================================================================

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler — routes by path prefix.

    Routes:
      GET  /sites                        - List account sites (account-level)
      GET  /products                     - Query products
      GET  /products/:id                 - Get single product (full detail)
      GET  /collections                   - Query collections
      GET  /collections/:id              - Get single collection
      GET  /collections/:id/products     - Products in a collection
      GET  /inventory                    - Query inventory items
      GET  /inventory/:productId         - Inventory for a product
      GET  /orders                       - Search orders (full detail)
      GET  /orders/:id                   - Get single order (full detail)
      GET  /orders/:id/fulfillments      - Fulfillments for an order
      GET  /orders/:id/transactions      - Transactions for an order
      GET  /sample-products              - BNB CLUB sample product templates
      POST /create-product               - Create a single product
      POST /bulk-create-products         - Bulk create products
      POST /update-product               - Update a product
      POST /delete-product               - Delete a product
      POST /add-product-image            - Add image(s) to a product (URL or S3 key)
      POST /upload-product-image         - Upload base64 image to S3 + attach to product
      POST /sync/products                - Sync products → DynamoDB
      POST /sync/orders                  - Sync orders → DynamoDB
    """
    request_id = context.aws_request_id if context else 'local'

    try:
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'GET'))
        path = event.get('path', event.get('rawPath', '/'))
        params = event.get('queryStringParameters', {}) or {}

        logger.info(json.dumps({
            'action': 'wix_store_request',
            'method': http_method,
            'path': path,
            'mode': WIX_MODE,
            'requestId': request_id,
        }))

        # ---- Velo mode: route through Velo HTTP Functions ----
        if WIX_MODE == 'velo':
            body = _parse_body(event) if http_method == 'POST' else {}
            return _velo_route(path, params, request_id, http_method, body)

        # ---- POST: Product management (check before resource routes) ----
        if http_method == 'POST':
            if '/create-product' in path:
                body = _parse_body(event)
                return _create_product_rest(body, request_id)
            if '/bulk-create-products' in path:
                body = _parse_body(event)
                return _bulk_create_products_rest(body, request_id)
            if '/update-product' in path:
                body = _parse_body(event)
                product_data = body.get('product', body)
                pid = body.get('productId', product_data.get('id', ''))
                updates = body.get('updates', product_data)
                if not pid:
                    return _response(400, {'error': 'Missing productId', 'requestId': request_id})
                try:
                    result = _wix_request(f'/stores/v1/products/{pid}', method='PATCH', body={'product': updates})
                    return _response(200, {'product': result.get('product', {}), 'updated': True, 'requestId': request_id})
                except Exception as e:
                    return _response(500, {'error': str(e), 'requestId': request_id})
            if '/delete-product' in path:
                body = _parse_body(event)
                pid = body.get('productId', '')
                if not pid:
                    return _response(400, {'error': 'Missing productId', 'requestId': request_id})
                try:
                    _wix_request(f'/stores/v1/products/{pid}', method='DELETE')
                    return _response(200, {'deleted': True, 'requestId': request_id})
                except Exception as e:
                    return _response(500, {'error': str(e), 'requestId': request_id})
            if '/add-product-image' in path:
                body = _parse_body(event)
                return _add_product_image(body, request_id)
            if '/upload-product-image' in path:
                body = _parse_body(event)
                return _upload_product_image(event, body, request_id)

        # ---- Account-level ----
        if '/sites' in path:
            return _list_sites(params, request_id)

        # ---- Collections ----
        if '/collections' in path:
            coll_id = _extract_id(path, 'collections')
            if coll_id and '/products' in path.split('collections/' + coll_id)[-1]:
                return _collection_products(coll_id, params, request_id)
            if coll_id:
                return _get_collection(coll_id, request_id)
            return _list_collections(params, request_id)

        # ---- Products ----
        if '/products' in path:
            product_id = _extract_id(path, 'products')
            if product_id:
                return _get_product(product_id, request_id)
            return _list_products(params, request_id)

        # ---- Inventory ----
        if '/inventory' in path:
            product_id = _extract_id(path, 'inventory')
            if product_id:
                return _get_inventory(product_id, request_id)
            return _query_inventory(params, request_id)

        # ---- Orders ----
        if '/orders' in path:
            order_id = _extract_id(path, 'orders')
            if order_id:
                if '/fulfillments' in path:
                    return _order_fulfillments(order_id, request_id)
                if '/transactions' in path:
                    return _order_transactions(order_id, request_id)
                return _get_order(order_id, request_id)
            return _search_orders(params, request_id)

        # ---- Sync ----
        if '/sync' in path and http_method == 'POST':
            if 'products' in path:
                return _sync_products(request_id)
            if 'orders' in path:
                return _sync_orders(request_id)

        # ---- Sample products ----
        if '/sample-products' in path:
            return _get_sample_products(request_id)

        return _response(404, {'error': 'Not found', 'path': path})

    except Exception as e:
        logger.error(json.dumps({
            'action': 'wix_store_error',
            'error': str(e),
            'requestId': request_id,
        }))
        return _response(500, {'error': 'Internal server error', 'message': str(e)})


# ===================================================================
# WIX API CLIENT
# ===================================================================

def _wix_request(endpoint: str, method: str = 'GET', body: dict = None,
                 level: str = 'site') -> Dict[str, Any]:
    """
    Authenticated request to Wix REST API.

    level='site'    → sends wix-site-id header (products, orders, inventory, etc.)
    level='account' → sends wix-account-id header (sites API)
    These headers are mutually exclusive per Wix docs.
    """
    url = f"{WIX_API_BASE}{endpoint}"
    headers = {
        'Authorization': WIX_API_KEY,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if level == 'account':
        headers['wix-account-id'] = WIX_ACCOUNT_ID
    else:
        headers['wix-site-id'] = WIX_SITE_ID

    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(json.dumps({
            'action': 'wix_api_error',
            'status': e.code,
            'url': url,
            'response': error_body[:500],
        }))
        raise RuntimeError(f"Wix API error {e.code}: {error_body[:200]}")


# ===================================================================
# SITES (account-level)
# ===================================================================

def _list_sites(params: dict, request_id: str) -> Dict[str, Any]:
    """Query sites from Wix account. Use to discover WIX_SITE_ID."""
    limit = int(params.get('limit', 50))
    offset = int(params.get('offset', 0))

    result = _wix_request(
        '/site-management/v1/sites/query',
        method='POST',
        body={'query': {
            'paging': {'limit': limit, 'offset': offset},
            'sort': [{'fieldName': 'dateUpdated', 'order': 'DESC'}],
        }},
        level='account',
    )

    sites = []
    for s in result.get('sites', []):
        sites.append({
            'id': s.get('id'),
            'displayName': s.get('displayName', ''),
            'viewUrl': s.get('viewUrl', ''),
            'editUrl': s.get('editUrl', ''),
            'published': s.get('published', False),
            'premium': s.get('premium', False),
            'thumbnail': s.get('thumbnail', {}).get('url', ''),
            'dashboardUrl': f"https://manage.wix.com/dashboard/{s.get('id', '')}",
            'createdDate': s.get('dateCreated', ''),
            'updatedDate': s.get('dateUpdated', ''),
        })

    return _response(200, {
        'sites': sites,
        'totalResults': result.get('totalResults', len(sites)),
        'requestId': request_id,
    })


# ===================================================================
# PRODUCTS
# ===================================================================

def _list_products(params: dict, request_id: str) -> Dict[str, Any]:
    """Query products from Wix Stores catalog. Includes variants when requested."""
    limit = int(params.get('limit', 100))
    offset = int(params.get('offset', 0))
    include_variants = params.get('includeVariants', 'true').lower() == 'true'

    query_body = {
        'query': {
            'paging': {'limit': limit, 'offset': offset},
        },
        'includeVariants': include_variants,
        'includeHiddenProducts': params.get('includeHidden', 'false').lower() == 'true',
    }

    # Text search filter
    search = params.get('search')
    if search:
        query_body['query']['filter'] = {'name': {'$contains': search}}

    # Collection filter
    collection_id = params.get('collectionId')
    if collection_id:
        query_body['query']['filter'] = query_body['query'].get('filter', {})
        query_body['query']['filter']['collections.id'] = {'$hasSome': [collection_id]}

    result = _wix_request('/stores/v1/products/query', method='POST', body=query_body)
    products = result.get('products', [])

    # Enrich each product with site URL and stock summary
    for p in products:
        slug = p.get('slug', '')
        p['_siteUrl'] = f'https://www.wecare.digital/product-page/{slug}' if slug else ''
        p['_mainImage'] = _get_main_media(p)
        p['_mediaCount'] = len(p.get('media', {}).get('items', []))

    return _response(200, {
        'products': products,
        'totalResults': result.get('totalResults', len(products)),
        'siteUrl': 'https://www.wecare.digital',
        'dashboardUrl': f'https://manage.wix.com/dashboard/{WIX_SITE_ID}/store/products',
        'requestId': request_id,
    })


def _get_product(product_id: str, request_id: str) -> Dict[str, Any]:
    """Get full product detail including variants, options, media, collections, and site URL."""
    result = _wix_request(f'/stores/v1/products/{product_id}')
    product = result.get('product', {})

    # Also fetch inventory for this product
    try:
        inv = _wix_request(
            f'/stores/v2/inventoryItems/product/{product_id}/getVariants',
            method='POST',
            body={},
        )
        product['_inventory'] = inv.get('inventoryItem', {})
    except Exception as e:
        product['_inventory'] = {'error': str(e)}

    # Add computed fields for convenience
    slug = product.get('slug', '')
    product['_siteUrl'] = f'https://www.wecare.digital/product-page/{slug}' if slug else ''
    product['_dashboardUrl'] = f'https://manage.wix.com/dashboard/{WIX_SITE_ID}/store/products'
    product['_mediaCount'] = len(product.get('media', {}).get('items', []))
    product['_mainImage'] = _get_main_media(product)

    # Stock summary
    stock = product.get('stock', {})
    product['_stockSummary'] = {
        'inStock': stock.get('inStock', False),
        'trackInventory': stock.get('trackInventory', False),
        'inventoryStatus': stock.get('inventoryStatus', 'UNKNOWN'),
        'quantity': stock.get('quantity', None),
    }

    # Price summary
    price = product.get('price', {})
    product['_priceSummary'] = {
        'amount': price.get('price', 0),
        'currency': price.get('currency', 'INR'),
        'formatted': price.get('formatted', {}).get('price', ''),
        'discounted': price.get('formatted', {}).get('discountedPrice', ''),
    }

    return _response(200, {'product': product, 'requestId': request_id})


# ===================================================================
# COLLECTIONS
# ===================================================================

def _list_collections(params: dict, request_id: str) -> Dict[str, Any]:
    """Query store collections."""
    limit = int(params.get('limit', 100))
    offset = int(params.get('offset', 0))

    result = _wix_request('/stores/v1/collections/query', method='POST', body={
        'query': {
            'paging': {'limit': limit, 'offset': offset},
        }
    })

    return _response(200, {
        'collections': result.get('collections', []),
        'totalResults': result.get('totalResults', 0),
        'requestId': request_id,
    })


def _get_collection(collection_id: str, request_id: str) -> Dict[str, Any]:
    """Get a single collection by ID."""
    result = _wix_request(f'/stores/v1/collections/{collection_id}')
    return _response(200, {
        'collection': result.get('collection', {}),
        'requestId': request_id,
    })


def _collection_products(collection_id: str, params: dict, request_id: str) -> Dict[str, Any]:
    """Get products belonging to a specific collection."""
    limit = int(params.get('limit', 100))
    offset = int(params.get('offset', 0))

    result = _wix_request('/stores/v1/products/query', method='POST', body={
        'query': {
            'paging': {'limit': limit, 'offset': offset},
            'filter': {'collections.id': {'$hasSome': [collection_id]}},
        },
        'includeVariants': True,
    })

    return _response(200, {
        'collectionId': collection_id,
        'products': result.get('products', []),
        'totalResults': result.get('totalResults', 0),
        'requestId': request_id,
    })


# ===================================================================
# INVENTORY
# ===================================================================

def _query_inventory(params: dict, request_id: str) -> Dict[str, Any]:
    """Query inventory items across the store."""
    limit = int(params.get('limit', 100))
    offset = int(params.get('offset', 0))

    result = _wix_request('/stores-reader/v2/inventoryItems/query', method='POST', body={
        'query': {
            'paging': {'limit': limit, 'offset': offset},
        }
    })

    return _response(200, {
        'inventoryItems': result.get('inventoryItems', []),
        'totalResults': result.get('totalResults', 0),
        'requestId': request_id,
    })


def _get_inventory(product_id: str, request_id: str) -> Dict[str, Any]:
    """Get inventory variants for a specific product."""
    result = _wix_request(
        f'/stores/v2/inventoryItems/product/{product_id}/getVariants',
        method='POST',
        body={},
    )
    return _response(200, {
        'productId': product_id,
        'inventoryItem': result.get('inventoryItem', {}),
        'requestId': request_id,
    })


# ===================================================================
# ORDERS (full detail with custom order numbers)
# ===================================================================

def _search_orders(params: dict, request_id: str) -> Dict[str, Any]:
    """
    Search orders via eCommerce Orders API.
    Returns full order objects including:
      - number (custom/sequential order number)
      - buyerInfo (email, contactId, memberId)
      - lineItems with product details
      - priceSummary, shippingInfo, billingInfo
      - paymentStatus, fulfillmentStatus
      - channelInfo (including externalOrderId for custom order numbers)
      - customFields

    Query params:
      - status: APPROVED, CANCELED, etc.
      - paymentStatus: PAID, NOT_PAID, PARTIALLY_PAID, PARTIALLY_REFUNDED, FULLY_REFUNDED
      - fulfillmentStatus: NOT_FULFILLED, PARTIALLY_FULFILLED, FULFILLED
      - email: filter by buyer email
      - memberId: filter by Wix member ID (logged-in user)
      - customOrderNumber: filter by WD custom order number
      - dateFrom / dateTo: ISO date range on createdDate
      - limit / cursor: pagination
    """
    limit = int(params.get('limit', 50))

    search_body: Dict[str, Any] = {
        'search': {
            'cursorPaging': {'limit': limit},
            'sort': [{'fieldName': 'createdDate', 'order': 'DESC'}],
        }
    }

    # Build filter
    filt: Dict[str, Any] = {}

    if params.get('status'):
        filt['status'] = {'$eq': params['status'].upper()}
    if params.get('paymentStatus'):
        filt['paymentStatus'] = {'$eq': params['paymentStatus'].upper()}
    if params.get('fulfillmentStatus'):
        filt['fulfillmentStatus'] = {'$eq': params['fulfillmentStatus'].upper()}
    if params.get('email'):
        filt['buyerInfo.email'] = {'$eq': params['email']}
    if params.get('memberId'):
        filt['buyerInfo.memberId'] = {'$eq': params['memberId']}
    if params.get('orderNumber'):
        filt['number'] = {'$eq': int(params['orderNumber'])}

    # Date range
    date_filter = {}
    if params.get('dateFrom'):
        date_filter['$gte'] = params['dateFrom']
    if params.get('dateTo'):
        date_filter['$lte'] = params['dateTo']
    if date_filter:
        filt['createdDate'] = date_filter

    if filt:
        search_body['search']['filter'] = filt

    # Cursor-based pagination
    cursor = params.get('cursor')
    if cursor:
        search_body['search']['cursorPaging']['cursor'] = cursor

    result = _wix_request('/ecom/v1/orders/search', method='POST', body=search_body)
    orders = result.get('orders', [])

    # Enrich each order with a clean summary
    enriched = []
    for order in orders:
        enriched.append(_enrich_order(order))

    paging = result.get('pagingMetadata', {})

    return _response(200, {
        'orders': enriched,
        'totalResults': paging.get('count', len(enriched)),
        'cursors': paging.get('cursors', {}),
        'hasNext': paging.get('hasNext', False),
        'requestId': request_id,
    })


def _get_order(order_id: str, request_id: str) -> Dict[str, Any]:
    """Get full order detail by ID, including transactions and fulfillments."""
    result = _wix_request(f'/ecom/v1/orders/{order_id}')
    order = result.get('order', {})

    # Fetch transactions
    try:
        txn = _wix_request(f'/ecom/v1/transactions/orders/{order_id}')
        order['_transactions'] = txn.get('orderTransactions', {})
    except Exception:
        order['_transactions'] = []

    # Fetch fulfillments
    try:
        ful = _wix_request(f'/ecom/v1/fulfillments/orders/{order_id}')
        order['_fulfillments'] = ful.get('orderFulfillments', {})
    except Exception:
        order['_fulfillments'] = []

    return _response(200, {'order': _enrich_order(order), 'requestId': request_id})


def _order_fulfillments(order_id: str, request_id: str) -> Dict[str, Any]:
    """List fulfillments for a specific order."""
    result = _wix_request(f'/ecom/v1/fulfillments/orders/{order_id}')
    return _response(200, {
        'orderId': order_id,
        'fulfillments': result.get('orderFulfillments', {}),
        'requestId': request_id,
    })


def _order_transactions(order_id: str, request_id: str) -> Dict[str, Any]:
    """List transactions for a specific order."""
    result = _wix_request(f'/ecom/v1/transactions/orders/{order_id}')
    return _response(200, {
        'orderId': order_id,
        'transactions': result.get('orderTransactions', {}),
        'requestId': request_id,
    })


def _enrich_order(order: dict) -> dict:
    """
    Add a clean _summary to the raw order for easy consumption.
    Includes custom order number, buyer details, line items summary, totals.
    """
    buyer = order.get('buyerInfo', {})
    price = order.get('priceSummary', {})
    channel = order.get('channelInfo', {})
    billing = order.get('billingInfo', {}).get('contactDetails', {})
    shipping_info = order.get('shippingInfo', {})

    line_items_summary = []
    for item in order.get('lineItems', []):
        line_items_summary.append({
            'name': item.get('productName', {}).get('original', ''),
            'quantity': item.get('quantity', 0),
            'price': item.get('price', {}).get('amount', '0'),
            'sku': item.get('physicalProperties', {}).get('sku', ''),
            'image': item.get('image', {}).get('url', ''),
            'catalogItemId': item.get('catalogReference', {}).get('catalogItemId', ''),
        })

    order['_summary'] = {
        'orderNumber': order.get('number'),
        'externalOrderId': channel.get('externalOrderId', ''),
        'status': order.get('status', ''),
        'paymentStatus': order.get('paymentStatus', ''),
        'fulfillmentStatus': order.get('fulfillmentStatus', ''),
        'buyerEmail': buyer.get('email', ''),
        'buyerContactId': buyer.get('contactId', ''),
        'buyerMemberId': buyer.get('memberId', ''),
        'billingName': f"{billing.get('firstName', '')} {billing.get('lastName', '')}".strip(),
        'billingPhone': billing.get('phone', ''),
        'totalAmount': price.get('total', {}).get('amount', '0'),
        'subtotal': price.get('subtotal', {}).get('amount', '0'),
        'shipping': price.get('shipping', {}).get('amount', '0'),
        'tax': price.get('tax', {}).get('amount', '0'),
        'discount': price.get('discount', {}).get('amount', '0'),
        'currency': order.get('currency', ''),
        'lineItemCount': len(order.get('lineItems', [])),
        'lineItems': line_items_summary,
        'createdDate': order.get('createdDate', ''),
        'updatedDate': order.get('updatedDate', ''),
        'purchasedDate': order.get('purchasedDate', ''),
        'archived': order.get('archived', False),
        'customFields': order.get('customFields', []),
        'buyerNote': order.get('buyerNote', ''),
    }
    return order


# ===================================================================
# PRODUCT CREATION (REST API MODE)
# ===================================================================

SKU_PREFIX = 'WD'


def _generate_sku(product_name: str) -> str:
    """
    Auto-generate SKU in format WD-XX-XXXX.
    XX = first letter of first two words (split on spaces, dashes, em-dashes).
    XXXX = last 4 chars of base36 timestamp for uniqueness.
    """
    import re
    import time
    words = [w for w in re.split(r'[\s\-—–]+', product_name or '') if len(w) > 1]
    if len(words) >= 2:
        code = (words[0][0] + words[1][0]).upper()
    else:
        code = (product_name or 'XX')[:2].upper().ljust(2, 'X')
    suffix = _base36(int(time.time() * 1000))[-4:].upper()
    return f'{SKU_PREFIX}-{code}-{suffix}'


def _base36(num: int) -> str:
    """Convert integer to base36 string."""
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    if num == 0:
        return '0'
    result = ''
    while num:
        result = chars[num % 36] + result
        num //= 36
    return result


def _create_product_rest(body: dict, request_id: str) -> Dict[str, Any]:
    """Create a single product via Wix REST API. Auto-generates WD SKU if not provided.
    
    Accepts media in multiple formats (imported via Wix Media Manager):
      - product.imageUrls[]              (shorthand — list of public URLs)
      - product.s3Keys[]                 (S3 keys in app.wecare.digital bucket)
      - product.folder                   (Wix Media Manager folder: 'flags'|'products'|'bnb-club')
    """
    product_data = body.get('product', {})
    if not product_data.get('name'):
        return _response(400, {'error': 'Missing product.name', 'requestId': request_id})

    # Auto-generate SKU if not provided or doesn't have our prefix
    if not product_data.get('sku') or not product_data['sku'].startswith(SKU_PREFIX + '-'):
        product_data['sku'] = _generate_sku(product_data['name'])

    # Ensure all products are in stock by default
    if 'stock' not in product_data:
        product_data['stock'] = {'trackInventory': False, 'inStock': True}

    # Extract image URLs/keys for post-creation attachment (don't pass to create)
    image_urls = product_data.pop('imageUrls', [])
    s3_keys = product_data.pop('s3Keys', [])
    media_folder = product_data.pop('folder', 'products')

    try:
        result = _wix_request(
            '/stores/v1/products',
            method='POST',
            body={'product': product_data}
        )
        created_product = result.get('product', {})
        pid = created_product.get('id', '')

        # Attach images via Media Manager import flow (if any provided)
        if pid and (image_urls or s3_keys):
            try:
                _add_product_image({
                    'productId': pid,
                    'imageUrls': image_urls,
                    's3Keys': s3_keys,
                    'folder': media_folder,
                }, request_id)
                # Re-fetch product to get updated media
                created_product = _wix_request(f'/stores/v1/products/{pid}').get('product', {})
            except Exception as img_err:
                created_product['_imageAttachError'] = str(img_err)

        return _response(200, {
            'product': created_product,
            'created': True,
            'requestId': request_id,
        })
    except Exception as e:
        return _response(500, {'error': str(e), 'requestId': request_id})


def _bulk_create_products_rest(body: dict, request_id: str) -> Dict[str, Any]:
    """Bulk create products via Wix REST API (sequential)."""
    products_array = body.get('products', [])
    if not products_array:
        return _response(400, {'error': 'Missing or empty products array', 'requestId': request_id})

    results = []
    for product_data in products_array:
        # Auto-generate SKU if not provided
        if not product_data.get('sku') or not product_data['sku'].startswith(SKU_PREFIX + '-'):
            product_data['sku'] = _generate_sku(product_data.get('name', ''))
        # Ensure in stock by default
        if 'stock' not in product_data:
            product_data['stock'] = {'trackInventory': False, 'inStock': True}
        try:
            result = _wix_request(
                '/stores/v1/products',
                method='POST',
                body={'product': product_data}
            )
            created = result.get('product', {})
            results.append({
                'success': True,
                'name': product_data.get('name', ''),
                'productId': created.get('id', created.get('_id', '')),
            })
        except Exception as e:
            results.append({
                'success': False,
                'name': product_data.get('name', ''),
                'error': str(e),
            })

    return _response(200, {
        'total': len(products_array),
        'succeeded': len([r for r in results if r['success']]),
        'failed': len([r for r in results if not r['success']]),
        'results': results,
        'requestId': request_id,
    })


S3_BUCKET = 'app.wecare.digital'
S3_PRODUCT_PREFIX = 'store/products'

# Wix Media Manager folder IDs (WECARE Store structure)
WIX_MEDIA_FOLDERS = {
    'root': '1380adfd536841efa2557823f0e3f46f',       # WECARE Store
    'flags': '207cd45424d34ebb9652011e7a17b2a4',       # WECARE Store > Flags
    'products': '347f7383033f4838af6c3d52c267ac1c',    # WECARE Store > Products
    'bnb-club': 'f6f39ae4b1be412390a77588b0731f9c',   # WECARE Store > Products > BNB Club
}


def _s3_public_url(key: str) -> str:
    """Convert an S3 key to a public HTTPS URL."""
    return f'https://{S3_BUCKET}/{key}'


def _import_to_wix_media(url: str, display_name: str, folder: str = 'products') -> Dict[str, Any]:
    """
    Import an external image URL into Wix Media Manager.
    Returns the Wix-hosted media file descriptor.

    Uses POST https://www.wixapis.com/site-media/v1/files/import

    Args:
        url: Public URL of the image to import
        display_name: File name in Wix Media Manager (include extension)
        folder: Folder key from WIX_MEDIA_FOLDERS (default: 'products')
    """
    folder_id = WIX_MEDIA_FOLDERS.get(folder, WIX_MEDIA_FOLDERS['products'])

    # Detect mime type from extension
    ext = display_name.rsplit('.', 1)[-1].lower() if '.' in display_name else 'png'
    mime_map = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}
    mime_type = mime_map.get(ext, 'image/png')

    import_body = {
        'url': url,
        'displayName': display_name,
        'mediaType': 'IMAGE',
        'mimeType': mime_type,
        'parentFolderId': folder_id,
    }

    # Use site-media API (different from stores API)
    api_url = f'{WIX_API_BASE}/site-media/v1/files/import'
    headers = {
        'Authorization': WIX_API_KEY,
        'Content-Type': 'application/json',
        'wix-site-id': WIX_SITE_ID,
    }
    data = json.dumps(import_body).encode('utf-8')
    req = urllib.request.Request(api_url, data=data, headers=headers, method='POST')

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))

    return result.get('file', {})


def _add_product_media_api(product_id: str, wix_media_urls: list) -> Dict[str, Any]:
    """
    Attach images to a product using the dedicated Add Product Media endpoint.
    POST https://www.wixapis.com/stores/v1/products/{id}/media

    Args:
        product_id: Wix product ID
        wix_media_urls: List of Wix-hosted media URLs (from Media Manager)
    """
    media_items = [{'url': u, 'mediaType': 'IMAGE'} for u in wix_media_urls]
    api_url = f'{WIX_API_BASE}/stores/v1/products/{product_id}/media'
    headers = {
        'Authorization': WIX_API_KEY,
        'Content-Type': 'application/json',
        'wix-site-id': WIX_SITE_ID,
    }
    data = json.dumps({'media': media_items}).encode('utf-8')
    req = urllib.request.Request(api_url, data=data, headers=headers, method='POST')

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8') or '{}')


def _add_product_image(body: dict, request_id: str) -> Dict[str, Any]:
    """
    Add image(s) to an existing product by URL or S3 key.

    Flow:
      1. Import each image into Wix Media Manager (WECARE Store folder)
      2. Attach to product via dedicated Add Product Media endpoint

    Body:
      productId: required
      imageUrls: [url, ...]       — public URLs (S3, CDN, etc.)
      s3Keys: [key, ...]          — S3 keys in app.wecare.digital bucket
      folder: 'flags'|'products'|'bnb-club' — Wix Media Manager folder (default: 'products')
    """
    pid = body.get('productId', '')
    if not pid:
        return _response(400, {'error': 'Missing productId', 'requestId': request_id})

    folder = body.get('folder', 'products')
    urls_to_import = []

    for url in body.get('imageUrls', []):
        urls_to_import.append(url)
    for key in body.get('s3Keys', []):
        urls_to_import.append(_s3_public_url(key))

    if not urls_to_import:
        return _response(400, {'error': 'No imageUrls or s3Keys provided', 'requestId': request_id})

    try:
        # Step 1: Import each image into Wix Media Manager
        wix_media_urls = []
        imported_files = []
        for url in urls_to_import:
            # Extract filename from URL
            file_name = url.rstrip('/').split('/')[-1].split('?')[0] or 'image.png'
            wix_file = _import_to_wix_media(url, file_name, folder)
            wix_url = wix_file.get('url', '')
            if wix_url:
                wix_media_urls.append(wix_url)
                imported_files.append({
                    'wixId': wix_file.get('id', ''),
                    'wixUrl': wix_url,
                    'sourceUrl': url,
                    'displayName': wix_file.get('displayName', ''),
                })

        if not wix_media_urls:
            return _response(500, {'error': 'Failed to import images to Wix Media Manager', 'requestId': request_id})

        # Step 2: Attach to product via dedicated endpoint
        _add_product_media_api(pid, wix_media_urls)

        # Step 3: Verify by fetching product
        product = _wix_request(f'/stores/v1/products/{pid}').get('product', {})

        return _response(200, {
            'productId': pid,
            'mediaCount': len(product.get('media', {}).get('items', [])),
            'mainImage': _get_main_media(product),
            'importedFiles': imported_files,
            'updated': True,
            'requestId': request_id,
        })
    except Exception as e:
        return _response(500, {'error': str(e), 'requestId': request_id})


def _upload_product_image(event: dict, body: dict, request_id: str) -> Dict[str, Any]:
    """
    Upload a base64-encoded image to S3 and optionally attach it to a product.

    Body:
      imageBase64: required — base64-encoded image data
      fileName: required — e.g. 'visa-tourist.jpg'
      category: optional — subfolder under store/products/ (default: 'general')
      contentType: optional — e.g. 'image/jpeg' (default: auto-detect from extension)
      productId: optional — if provided, also attaches the image to this product
    """
    import base64

    image_b64 = body.get('imageBase64', '')
    file_name = body.get('fileName', '')
    if not image_b64 or not file_name:
        return _response(400, {'error': 'Missing imageBase64 or fileName', 'requestId': request_id})

    category = body.get('category', 'general').strip('/')
    s3_key = f'{S3_PRODUCT_PREFIX}/{category}/{file_name}'

    # Auto-detect content type
    ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else 'jpg'
    content_type = body.get('contentType', {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'webp': 'image/webp',
        'gif': 'image/gif', 'svg': 'image/svg+xml',
    }.get(ext, 'image/jpeg'))

    try:
        s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=base64.b64decode(image_b64),
            ContentType=content_type,
            CacheControl='public, max-age=31536000',
        )
        public_url = _s3_public_url(s3_key)

        result = {
            's3Key': s3_key,
            'publicUrl': public_url,
            'uploaded': True,
            'requestId': request_id,
        }

        # Optionally attach to product via Wix Media Manager import flow
        pid = body.get('productId', '')
        if pid:
            folder = body.get('folder', 'products')
            attach_result = _add_product_image({
                'productId': pid,
                'imageUrls': [public_url],
                'folder': folder,
            }, request_id)
            result['productAttached'] = True
            result['productId'] = pid

        return _response(200, result)
    except Exception as e:
        return _response(500, {'error': str(e), 'requestId': request_id})


def _get_sample_products(request_id: str) -> Dict[str, Any]:
    """Return BNB CLUB sample product templates."""
    samples = {
        'category': 'BNB CLUB',
        'products': [
            {
                'name': 'Visa Assistance — Tourist Visa (Single Country)',
                'productType': 'digital',
                'priceData': {'currency': 'INR', 'price': 2999},
                'sku': 'BNB-VISA-SINGLE-001',
                'ribbon': 'BNB CLUB',
                'brand': 'WECARE.DIGITAL',
            },
            {
                'name': 'Visa Assistance — Schengen Multi-Country',
                'productType': 'digital',
                'priceData': {'currency': 'INR', 'price': 4999},
                'sku': 'BNB-VISA-SCHENGEN-001',
                'ribbon': 'BNB CLUB',
                'brand': 'WECARE.DIGITAL',
            },
            {
                'name': 'Visa Assistance — Business / Conference Visa',
                'productType': 'digital',
                'priceData': {'currency': 'INR', 'price': 3999},
                'sku': 'BNB-VISA-BUSINESS-001',
                'ribbon': 'BNB CLUB',
                'brand': 'WECARE.DIGITAL',
            },
        ],
    }
    return _response(200, {**samples, 'requestId': request_id})


# ===================================================================
# SYNC TO DYNAMODB CACHE
# ===================================================================

def _sync_products(request_id: str) -> Dict[str, Any]:
    """Sync all Wix products to local DynamoDB cache."""
    table = dynamodb.Table(PRODUCTS_CACHE_TABLE)
    synced = 0
    offset = 0

    while True:
        result = _wix_request('/stores/v1/products/query', method='POST', body={
            'query': {'paging': {'limit': 100, 'offset': offset}},
            'includeVariants': True,
        })
        products = result.get('products', [])
        if not products:
            break

        with table.batch_writer() as batch:
            for p in products:
                batch.put_item(Item={
                    'productId': p.get('id'),
                    'name': p.get('name', ''),
                    'slug': p.get('slug', ''),
                    'price': str(p.get('price', {}).get('formatted', {}).get('actualPrice', '0')),
                    'currency': p.get('price', {}).get('currency', 'USD'),
                    'inStock': p.get('stock', {}).get('inStock', False),
                    'productType': p.get('productType', 'physical'),
                    'mediaUrl': _get_main_media(p),
                    'rawData': json.dumps(p, default=str),
                    'syncedAt': datetime.now(timezone.utc).isoformat(),
                })
                synced += 1

        offset += 100
        if len(products) < 100:
            break

    logger.info(json.dumps({'action': 'sync_products_complete', 'count': synced, 'requestId': request_id}))
    return _response(200, {'message': f'Synced {synced} products', 'requestId': request_id})


def _sync_orders(request_id: str) -> Dict[str, Any]:
    """Sync Wix orders to local DynamoDB cache with full detail."""
    table = dynamodb.Table(ORDERS_CACHE_TABLE)
    synced = 0
    cursor = None

    while True:
        body: Dict[str, Any] = {
            'search': {
                'cursorPaging': {'limit': 100},
                'sort': [{'fieldName': 'createdDate', 'order': 'DESC'}],
            }
        }
        if cursor:
            body['search']['cursorPaging']['cursor'] = cursor

        result = _wix_request('/ecom/v1/orders/search', method='POST', body=body)
        orders = result.get('orders', [])
        if not orders:
            break

        with table.batch_writer() as batch:
            for o in orders:
                buyer = o.get('buyerInfo', {})
                price = o.get('priceSummary', {})
                channel = o.get('channelInfo', {})
                batch.put_item(Item={
                    'orderId': o.get('id'),
                    'orderNumber': str(o.get('number', '')),
                    'externalOrderId': channel.get('externalOrderId', ''),
                    'buyerEmail': buyer.get('email', ''),
                    'buyerPhone': o.get('billingInfo', {}).get('contactDetails', {}).get('phone', ''),
                    'totalPrice': str(price.get('total', {}).get('amount', '0')),
                    'currency': o.get('currency', 'USD'),
                    'paymentStatus': o.get('paymentStatus', ''),
                    'fulfillmentStatus': o.get('fulfillmentStatus', ''),
                    'status': o.get('status', ''),
                    'lineItemCount': len(o.get('lineItems', [])),
                    'createdDate': o.get('createdDate', ''),
                    'rawData': json.dumps(o, default=str),
                    'syncedAt': datetime.now(timezone.utc).isoformat(),
                })
                synced += 1

        paging = result.get('pagingMetadata', {})
        if paging.get('hasNext') and paging.get('cursors', {}).get('next'):
            cursor = paging['cursors']['next']
        else:
            break

    logger.info(json.dumps({'action': 'sync_orders_complete', 'count': synced, 'requestId': request_id}))
    return _response(200, {'message': f'Synced {synced} orders', 'requestId': request_id})


# ===================================================================
# HELPERS
# ===================================================================

def _extract_id(path: str, resource: str) -> Optional[str]:
    """Extract resource ID from path like /orders/abc123 or /orders/abc123/fulfillments."""
    parts = path.rstrip('/').split('/')
    try:
        idx = parts.index(resource)
        if idx + 1 < len(parts) and parts[idx + 1]:
            return parts[idx + 1]
    except ValueError:
        pass
    return None


def _get_main_media(product: dict) -> str:
    """Extract main media URL from product."""
    return product.get('media', {}).get('mainMedia', {}).get('image', {}).get('url', '')


def _parse_body(event: dict) -> dict:
    """Parse request body from event."""
    body = event.get('body', '')
    if not body:
        return {}
    if isinstance(body, str):
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return {}
    return body


def _response(status_code: int, body: dict) -> Dict[str, Any]:
    """Build API Gateway response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
        },
        'body': json.dumps(body, default=str),
    }


# ===================================================================
# VELO HTTP FUNCTIONS MODE
# ===================================================================
# When WIX_MODE='velo', calls go to your Wix site's Velo HTTP Functions
# at https://www.yoursite.com/_functions/<endpoint>
#
# This gives access to Wix Data collections directly, including:
# - Custom order numbers (customOrderNumber field)
# - All Stores/Orders collection fields
# - All Stores/Products collection fields with collections included
# - Any custom fields you've added
#
# Required Velo code on Wix side: backend/http-functions.js
# Velo source code is in store/src/ — sync to Wix via Git integration.
# ===================================================================

def _velo_request(endpoint: str, params: dict = None, method: str = 'GET',
                  body: dict = None) -> Dict[str, Any]:
    """
    Call a Velo HTTP Function on the published Wix site.
    GET:  {WIX_VELO_BASE}/_functions/{endpoint}?key=val&...
    POST: {WIX_VELO_BASE}/_functions/{endpoint}  (body as JSON)
    """
    if not WIX_VELO_BASE:
        raise RuntimeError("WIX_VELO_BASE_URL not configured. Set it to your Wix site URL.")

    query_string = ''
    if params and method == 'GET':
        parts = [f"{k}={urllib.request.quote(str(v))}" for k, v in params.items() if v]
        if parts:
            query_string = '?' + '&'.join(parts)

    url = f"{WIX_VELO_BASE}/_functions/{endpoint}{query_string}"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if WIX_VELO_API_KEY:
        headers['X-Api-Key'] = WIX_VELO_API_KEY

    data = json.dumps(body).encode('utf-8') if body and method == 'POST' else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(json.dumps({
            'action': 'velo_api_error',
            'status': e.code,
            'url': url,
            'response': error_body[:500],
        }))
        raise RuntimeError(f"Velo HTTP error {e.code}: {error_body[:200]}")


def _velo_route(path: str, params: dict, request_id: str,
                http_method: str = 'GET', body: dict = None) -> Dict[str, Any]:
    """Route requests through Velo HTTP Functions."""

    # ---- POST: Product management ----
    if http_method == 'POST':
        if '/create-product' in path or (('/products' in path) and '/sync' not in path and not _extract_id(path, 'products')):
            result = _velo_request('create-product', method='POST', body=body)
            return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

        if '/bulk-create-products' in path:
            result = _velo_request('bulk-create-products', method='POST', body=body)
            return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

        if '/update-product' in path:
            result = _velo_request('update-product', method='POST', body=body)
            return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

        if '/delete-product' in path:
            result = _velo_request('delete-product', method='POST', body=body)
            return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

        # Sync — always uses REST API for bulk operations
        if '/sync' in path:
            if 'products' in path:
                return _sync_products(request_id)
            if 'orders' in path:
                return _sync_orders(request_id)

        return _response(404, {'error': 'POST route not found', 'path': path, 'mode': 'velo'})

    # ---- GET: Sample products ----
    if '/sample-products' in path:
        result = _velo_request('sample-products')
        return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

    # Products
    if '/products' in path:
        product_id = _extract_id(path, 'products')
        if product_id:
            result = _velo_request('product', {'id': product_id})
            return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})
        result = _velo_request('products', {
            'limit': params.get('limit', '100'),
            'search': params.get('search', ''),
            'collectionId': params.get('collectionId', ''),
        })
        return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

    # Orders (includes custom order numbers from Wix Data)
    if '/orders' in path:
        order_id = _extract_id(path, 'orders')
        if order_id:
            result = _velo_request('order', {'id': order_id})
            return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})
        result = _velo_request('orders', {
            'limit': params.get('limit', '50'),
            'status': params.get('status', ''),
            'email': params.get('email', ''),
            'memberId': params.get('memberId', ''),
            'customOrderNumber': params.get('customOrderNumber', ''),
        })
        return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

    # Collections
    if '/collections' in path:
        result = _velo_request('collections', {
            'limit': params.get('limit', '100'),
        })
        return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

    # Inventory
    if '/inventory' in path:
        product_id = _extract_id(path, 'inventory')
        if product_id:
            result = _velo_request('inventory', {'productId': product_id})
            return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})
        result = _velo_request('inventory-all', {
            'limit': params.get('limit', '100'),
        })
        return _response(200, {**result, 'requestId': request_id, 'mode': 'velo'})

    # Sites — always uses REST API (account-level, not available via Velo)
    if '/sites' in path:
        return _list_sites(params, request_id)

    # Sync — always uses REST API for bulk operations
    if '/sync' in path:
        if 'products' in path:
            return _sync_products(request_id)
        if 'orders' in path:
            return _sync_orders(request_id)

    return _response(404, {'error': 'Not found', 'path': path, 'mode': 'velo'})
