"""Server-side Wix client limited to commerce/product and legacy page SEO reads."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import boto3

WIX_API = 'https://www.wixapis.com'
SITE_BASE = 'https://wecare.digital'
SECRET_NAME = os.environ.get('WIX_API_KEY_SECRET', 'wecare/wix-api-key')
SITE_ID = os.environ.get('WIX_SITE_ID', '')
_api_key = None

SITE_PAGES = [
    ('/', 'Homepage', 'landing'), ('/bnb', 'BNB Club', 'brand_hub'),
    ('/bnb-store', 'BNB Club Store', 'store'),
    ('/legal-champ', 'Legal Champ', 'brand_hub'),
    ('/legalchamp-store', 'Legal Champ Store', 'store'),
    ('/ritual', 'Ritual Guru', 'brand_hub'),
    ('/ritual-store', 'Ritual Guru Store', 'store'),
    ('/swdhya', 'Swdhya', 'brand_hub'),
    ('/swdhya-store', 'Swdhya Store', 'store'),
    ('/no-fault', 'No Fault', 'brand_hub'),
    ('/nofault-store', 'No Fault Store', 'store'),
    ('/expoweek', 'Expo Week', 'brand_hub'), ('/star', 'STAR Member Hub', 'utility'),
    ('/one', 'WECARE.DIGITAL App', 'utility'), ('/faq', 'FAQ', 'informational'),
    ('/contact', 'Contact Us', 'informational'),
    ('/legal-stuff', 'Terms & Policies', 'legal'), ('/privacy', 'Privacy Policy', 'legal'),
    ('/careers-plus-culture', 'Careers & Culture', 'informational'),
    ('/partner-up', 'Partnership Program', 'informational'),
    ('/enterprise-assist', 'Enterprise Support', 'service'),
    ('/gift-card', 'eGift Card', 'service'), ('/blog', 'Blog Index', 'blog_hub'),
    ('/sitemap', 'HTML Sitemap', 'utility'), ('/appointment', 'Schedule Appointment', 'service'),
    ('/submit-request', 'Submit Request', 'service'), ('/track-request', 'Track Request', 'service'),
    ('/amend-request', 'Amend Request', 'service'), ('/order-notes', 'Order Notes', 'service'),
    ('/drop-docs', 'Document Upload', 'service'), ('/rx-slot', 'Prescription Slot', 'service'),
    ('/selfservice', 'Self-Service Portal', 'service'), ('/search', 'Search', 'utility'),
    ('/leave-review', 'Leave Review', 'service'), ('/loyalty', 'Loyalty Rewards', 'service'),
    ('/referral', 'Referral Program', 'service'), ('/bring-friends', 'Refer Friends', 'service'),
]


def _load_api_key() -> str:
    global _api_key
    if _api_key is not None:
        return _api_key
    raw = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1')).get_secret_value(
        SecretId=SECRET_NAME
    ).get('SecretString', '')
    try:
        value = json.loads(raw)
        _api_key = str(value.get('api_key') or value.get('apiKey') or value.get('key') or value.get('value') or '')
    except (TypeError, ValueError):
        _api_key = str(raw)
    if not _api_key or not SITE_ID:
        raise RuntimeError('Wix server configuration is incomplete')
    return _api_key


def request(method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {
        'Authorization': _load_api_key(), 'wix-site-id': SITE_ID,
        'Content-Type': 'application/json', 'Accept': 'application/json',
    }
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(WIX_API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        error.read()
        raise RuntimeError(f'Wix API request failed with status {error.code}') from error
    except urllib.error.URLError as error:
        raise RuntimeError('Wix API request failed') from error


def public_json(path: str, timeout: int = 8) -> Dict[str, Any]:
    req = urllib.request.Request(SITE_BASE + path, headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception:
        return {}


def page_seo(path: str) -> Dict[str, Any]:
    value = public_json('/_functions/seohead?path=' + urllib.parse.quote(path, safe=''))
    schemas = value.get('structuredData', []) or []
    return {
        'title': value.get('title', ''), 'metaDescription': value.get('description', ''),
        'keywords': value.get('keywords', []) or [],
        'jsonLdTypes': [schema.get('@type') for schema in schemas if schema.get('@type')],
        'hasJsonLd': bool(schemas), 'canonical': value.get('canonical', ''),
    }


def list_site_pages() -> List[Dict[str, Any]]:
    def load_page(definition):
        path, name, page_type = definition
        seo = page_seo(path)
        return {
            'path': path, 'name': name, 'type': page_type,
            'url': SITE_BASE + path, **seo,
            'title': seo.get('title') or name,
            'canonical': seo.get('canonical') or SITE_BASE + path,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(load_page, SITE_PAGES))


def list_products() -> List[Dict[str, Any]]:
    data = request('POST', '/stores/v3/products/query', {
        'fields': ['CURRENCY', 'MEDIA_ITEMS_INFO', 'DESCRIPTION'],
        'query': {'cursorPaging': {'limit': 100}},
    })
    products = []
    for product in data.get('products', []):
        price_range = product.get('actualPriceRange', {}) or {}
        minimum = price_range.get('minValue', {}) or {}
        amount = minimum.get('amount', '')
        currency = product.get('currency', 'INR')
        media = product.get('media', {}) or {}
        image = (media.get('main', {}) or {}).get('url', '')
        inventory = product.get('inventory', {}) or {}
        availability = str(inventory.get('availabilityStatus', '')).upper()
        products.append({
            'id': product.get('id', ''), 'name': product.get('name', ''),
            'slug': product.get('slug', ''),
            'url': f"{SITE_BASE}/store/product/{product.get('slug', '')}",
            'description': str(product.get('plainDescription', '') or '')[:200],
            'price': f"{currency} {amount}".strip() if amount else '',
            'priceAmount': amount or 0, 'currency': currency,
            'inStock': availability in ('IN_STOCK', 'PARTIALLY_OUT_OF_STOCK'),
            'image': image,
            'type': str(product.get('productType', '')).lower(),
            'hasJsonLd': False, 'jsonLdType': '',
        })
    return products
