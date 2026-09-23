"""Server-side Wix client for exact SEO read and blog mutation contracts."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import boto3

WIX_API = 'https://www.wixapis.com'
SITE_BASE = 'https://www.wecare.digital'
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


def _seo_fields(post: Dict[str, Any]) -> Dict[str, Any]:
    tags = post.get('seoData', {}).get('tags', []) or []
    title = next((tag.get('children', '') for tag in tags if tag.get('type') == 'title'), '')
    description = next((tag.get('props', {}).get('content', '') for tag in tags
                        if tag.get('type') == 'meta' and tag.get('props', {}).get('name') == 'description'), '')
    json_ld = [tag for tag in tags if tag.get('type') == 'script'
               and tag.get('props', {}).get('type') == 'application/ld+json']
    keywords = [item.get('term', '') for item in post.get('seoData', {}).get('settings', {}).get('keywords', [])]
    return {'seoTitle': title, 'metaDescription': description, 'keywords': keywords,
            'jsonLdCount': len(json_ld), 'hasCustomSeo': bool(tags), 'tagCount': len(tags)}


def list_blog_posts() -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    offset = 0
    while True:
        data = request('GET', f'/v3/posts?paging.limit=100&paging.offset={offset}&fieldsToInclude=SEO&fieldsToInclude=CONTENT_TEXT')
        page = data.get('posts', [])
        for post in page:
            fields = _seo_fields(post)
            posts.append({
                'id': post.get('id', ''), 'title': post.get('title', ''),
                'slug': post.get('slug', ''), 'excerpt': post.get('excerpt', ''),
                'contentText': str(post.get('contentText', ''))[:5000],
                'url': f"{SITE_BASE}/post/{post.get('slug', '')}",
                'coverImage': post.get('media', {}).get('coverImage', {}).get('image', {}).get('url', ''),
                'publishedDate': post.get('firstPublishedDate') or post.get('publishedDate', ''),
                'modifiedDate': post.get('lastPublishedDate', ''),
                'focusKeyword': (fields['keywords'] or [''])[0], **fields,
            })
        if len(page) < 100:
            return posts
        offset += 100


def find_blog_post(slug: str) -> Optional[Dict[str, Any]]:
    return next((post for post in list_blog_posts() if post.get('slug') == slug), None)


def blog_form_options() -> Dict[str, List[Dict[str, str]]]:
    categories = request('GET', '/blog/v3/categories?paging.limit=100').get('categories', [])
    tags = request('GET', '/blog/v3/tags?paging.limit=100').get('tags', [])
    select = lambda items: [
        {'id': item.get('id', ''), 'label': item.get('label', ''), 'slug': item.get('slug', '')}
        for item in items
    ]
    return {'categories': select(categories), 'tags': select(tags)}


def _rich_content(text: str) -> Dict[str, Any]:
    nodes = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        level = 0
        if line.startswith('### '): level, line = 3, line[4:]
        elif line.startswith('## '): level, line = 2, line[3:]
        elif line.startswith('# '): level, line = 1, line[2:]
        node = {'type': 'HEADING', 'headingData': {'level': level}} if level else {'type': 'PARAGRAPH'}
        node['nodes'] = [{'type': 'TEXT', 'textData': {'text': line}}]
        nodes.append(node)
    return {'nodes': nodes}


def create_blog_post(body: Dict[str, Any]) -> Dict[str, Any]:
    title, content = str(body.get('title', '')).strip(), str(body.get('content', '')).strip()
    if not title or not content:
        raise ValueError('title and content required')
    options = blog_form_options()
    tag_ids = []
    for label in body.get('tagLabels') or []:
        existing = next((tag for tag in options['tags'] if tag['label'].lower() == str(label).lower()), None)
        if existing:
            tag_ids.append(existing['id'])
        else:
            created = request('POST', '/blog/v3/tags', {'tag': {'label': str(label).strip()}})
            if created.get('tag', {}).get('id'):
                tag_ids.append(created['tag']['id'])
    draft = {'title': title, 'richContent': _rich_content(content), 'language': 'en'}
    if body.get('categoryIds'): draft['categoryIds'] = body['categoryIds']
    if tag_ids: draft['tagIds'] = tag_ids
    if body.get('hashtags'):
        draft['hashtags'] = [{'value': str(tag).lstrip('#').strip()} for tag in body['hashtags']]
    created = request('POST', '/blog/v3/draft-posts', {'draftPost': draft}).get('draftPost', {})
    if not created.get('id'):
        raise RuntimeError('Wix did not return a draft post ID')
    request('POST', f"/blog/v3/draft-posts/{created['id']}/publish", {})
    return {'postId': created['id'], 'slug': created.get('slug', ''), 'title': title}


def clean_blog_post(slug: str) -> Dict[str, Any]:
    post = find_blog_post(slug)
    if not post:
        raise LookupError('Blog post not found')
    request('PATCH', f"/blog/v3/draft-posts/{post['id']}", {
        'draftPost': {'seoData': {'tags': [], 'settings': {'keywords': []}}},
        'action': 'UPDATE_REVERT_TO_DRAFT',
    })
    request('POST', f"/blog/v3/draft-posts/{post['id']}/publish", {})
    return {'slug': slug, 'postId': post['id'], 'title': post['title'],
            'cleaned': {'tagsRemoved': post.get('tagCount', 0),
                        'keywordsRemoved': len(post.get('keywords', []))}}


def _blog_seo_data(audit: Dict[str, Any]) -> Dict[str, Any]:
    ai = audit.get('fullAiResponse', {})
    title, description = ai.get('seoTitle', ''), ai.get('metaDescription', '')
    url = f"{SITE_BASE}/post/{audit.get('slug', '')}"
    tags = [
        {'type': 'title', 'children': title, 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'name': 'description', 'content': description}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'name': 'robots', 'content': 'index, follow, max-image-preview:large'}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'property': 'og:title', 'content': title.replace(' | WECARE.DIGITAL', '')}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'property': 'og:description', 'content': description}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'property': 'og:url', 'content': url}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'property': 'og:type', 'content': 'article'}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'property': 'og:site_name', 'content': 'WECARE.DIGITAL'}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'property': 'og:locale', 'content': 'en_IN'}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'meta', 'props': {'name': 'twitter:card', 'content': 'summary_large_image'}, 'children': '', 'custom': True, 'disabled': False},
        {'type': 'link', 'props': {'rel': 'canonical', 'href': url}, 'children': '', 'custom': True, 'disabled': False},
    ]
    schemas = ai.get('jsonLd', {}) or {}
    for key in ('blogPosting', 'breadcrumbList', 'faqSchema'):
        schema = schemas.get(key)
        if schema and (key != 'faqSchema' or schema.get('mainEntity')):
            tags.append({'type': 'script', 'props': {'type': 'application/ld+json'},
                         'children': json.dumps(schema), 'custom': True, 'disabled': False})
    focus = ai.get('focusKeyword') or audit.get('focusKeyword', '')
    keywords = ([{'term': focus, 'isMain': True}] if focus else [])
    keywords += [{'term': value, 'isMain': False}
                 for value in (ai.get('secondaryKeywords') or [])[:9] if value]
    return {'tags': tags, 'settings': {'keywords': keywords}}


def apply_blog_audit(audit: Dict[str, Any]) -> None:
    if audit.get('pageType') != 'blog' or not audit.get('blogPostId'):
        raise ValueError('Only blog audits with a Wix post ID can be applied')
    post_id = audit['blogPostId']
    request('PATCH', f'/blog/v3/draft-posts/{post_id}', {
        'draftPost': {'seoData': _blog_seo_data(audit)},
        'action': 'UPDATE_REVERT_TO_DRAFT',
    })
    request('POST', f'/blog/v3/draft-posts/{post_id}/publish', {})


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
