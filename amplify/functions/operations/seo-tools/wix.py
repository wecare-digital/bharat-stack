"""Server-side Wix client limited to commerce/product and legacy page SEO reads."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import boto3

WIX_API = 'https://www.wixapis.com'
SITE_BASE = 'https://wecare.digital'
SECRET_NAME = os.environ.get('WIX_API_KEY_SECRET', '').strip()
SITE_ID = os.environ.get('WIX_SITE_ID', '').strip()
ACCOUNT_ID = os.environ.get('WIX_ACCOUNT_ID', '').strip()
WIX_CLIENT_ID = os.environ.get(
    'WIX_CLIENT_ID', '197cd718-e4ec-4e2e-b380-46c297eb18a2'
).strip()
_api_key = None
_visitor_access_token = None
_visitor_access_token_expires_at = 0.0

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
    if not SECRET_NAME or not SITE_ID:
        raise RuntimeError('Wix Headless credentials are not configured')
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
    if ACCOUNT_ID:
        headers['wix-account-id'] = ACCOUNT_ID
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


def _load_visitor_access_token() -> str:
    global _visitor_access_token, _visitor_access_token_expires_at
    now = time.time()
    if (
        _visitor_access_token
        and now < _visitor_access_token_expires_at - 60
    ):
        return _visitor_access_token
    if not WIX_CLIENT_ID:
        raise RuntimeError('Wix Headless client ID is not configured')
    payload = json.dumps({
        'clientId': WIX_CLIENT_ID,
        'grantType': 'anonymous',
    }).encode('utf-8')
    req = urllib.request.Request(
        WIX_API + '/oauth2/token',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        error.read()
        raise RuntimeError(
            f'Wix visitor token request failed with status {error.code}'
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError('Wix visitor token request failed') from error

    token = str(data.get('access_token') or '').strip()
    if not token:
        raise RuntimeError('Wix visitor token response did not include an access token')
    expires_in = int(data.get('expires_in') or 0)
    _visitor_access_token = token
    _visitor_access_token_expires_at = now + max(expires_in, 300)
    return token


def public_blog_request(
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(
        WIX_API + path,
        data=data,
        headers={
            'Authorization': _load_visitor_access_token(),
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        error.read()
        raise RuntimeError(
            f'Wix public Blog API request failed with status {error.code}'
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError('Wix public Blog API request failed') from error


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


DEFAULT_BLOG_AUTHOR = os.environ.get('WIX_BLOG_AUTHOR_NAME', 'Anew by WECARE.DIGITAL').strip() or 'Anew by WECARE.DIGITAL'


def _seo_values(post: Dict[str, Any]) -> Dict[str, Any]:
    seo = post.get('seoData') or {}
    title = ''
    description = ''
    robots = 'index, follow, max-image-preview:large'
    for tag in seo.get('tags', []) or []:
        tag_type = str(tag.get('type') or '').lower()
        props = tag.get('props') or {}
        if tag_type == 'title':
            title = str(tag.get('children') or '').strip()
        elif tag_type == 'meta':
            name = str(props.get('name') or '').lower()
            if name == 'description':
                description = str(props.get('content') or '').strip()
            elif name == 'robots':
                robots = str(props.get('content') or robots).strip()
    keywords = []
    for keyword in (seo.get('settings') or {}).get('keywords', []) or []:
        term = str(keyword.get('term') or '').strip()
        if term:
            keywords.append(term)
    return {
        'seoTitle': title,
        'metaDescription': description,
        'robots': robots,
        'keywords': keywords,
    }


def _paged_blog_labels(path: str, key: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    offset = 0
    while True:
        data = public_blog_request(
            'POST',
            path,
            {'query': {'paging': {'limit': 100, 'offset': offset}}},
        )
        page = data.get(key, []) or []
        items.extend(page)
        if len(page) < 100:
            break
        offset += len(page)
    return items


def _blog_reference_maps() -> Dict[str, Dict[str, str]]:
    categories = _paged_blog_labels('/blog/v3/categories/query', 'categories')
    tags = _paged_blog_labels('/v3/tags/query', 'tags')
    return {
        'categories': {
            str(item.get('id') or ''): str(
                item.get('label') or item.get('title') or ''
            ).strip()
            for item in categories if item.get('id')
        },
        'tags': {
            str(item.get('id') or ''): str(item.get('label') or '').strip()
            for item in tags if item.get('id')
        },
    }


def _blog_view(post: Dict[str, Any], refs: Dict[str, Dict[str, str]], include_content: bool) -> Dict[str, Any]:
    slug = str(post.get('slug') or '').strip()
    seo = _seo_values(post)
    category_ids = post.get('categoryIds') or []
    tag_ids = post.get('tagIds') or []
    category = next((refs['categories'].get(str(value), '') for value in category_ids if refs['categories'].get(str(value))), '')
    tags = [refs['tags'][str(value)] for value in tag_ids if refs['tags'].get(str(value))]
    author = DEFAULT_BLOG_AUTHOR
    result = {
        'id': post.get('id', ''),
        'title': post.get('title', ''),
        'slug': slug,
        'excerpt': post.get('excerpt', ''),
        'url': f'{SITE_BASE}/post/{slug}/',
        'seoTitle': seo['seoTitle'],
        'metaDescription': seo['metaDescription'],
        'focusKeyword': seo['keywords'][0] if seo['keywords'] else '',
        'keywords': seo['keywords'],
        'jsonLd': {},
        'publishedDate': post.get('firstPublishedDate', ''),
        'modifiedDate': post.get('lastPublishedDate') or post.get('firstPublishedDate', ''),
        'coverImage': '',
        'category': category,
        'tags': tags,
        'hashtags': post.get('hashtags', []) or [],
        'authorName': author,
        'robots': seo['robots'],
    }
    if include_content:
        result['content'] = post.get('contentText', '') or ''
        result['richContent'] = post.get('richContent') or {}
    return result


def list_blog_posts() -> List[Dict[str, Any]]:
    refs = _blog_reference_maps()
    posts: List[Dict[str, Any]] = []
    cursor = ''
    while True:
        paging = {'limit': 100}
        if cursor:
            paging['cursor'] = cursor
        body = {
            'fieldsets': ['URL', 'SEO'],
            'query': {'cursorPaging': paging},
            'skipCount': True,
        }
        data = public_blog_request('POST', '/v3/posts/query', body)
        posts.extend(data.get('posts', []) or [])
        cursor = str(((data.get('pagingMetadata') or {}).get('cursors') or {}).get('next') or '')
        if not cursor:
            break
    return [_blog_view(post, refs, include_content=False) for post in posts]


def get_blog_post_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    wanted = str(slug or '').strip().strip('/')
    if not wanted:
        return None
    refs = _blog_reference_maps()
    params = urllib.parse.urlencode([
        ('fieldsets', 'URL'),
        ('fieldsets', 'CONTENT_TEXT'),
        ('fieldsets', 'SEO'),
        ('fieldsets', 'RICH_CONTENT'),
    ])
    try:
        data = public_blog_request(
            'GET',
            '/v3/posts/slugs/' + urllib.parse.quote(wanted, safe='') + '?' + params,
        )
    except RuntimeError as error:
        if 'status 404' in str(error):
            return None
        raise
    post = data.get('post')
    if not post:
        return None
    return _blog_view(post, refs, include_content=True)


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
