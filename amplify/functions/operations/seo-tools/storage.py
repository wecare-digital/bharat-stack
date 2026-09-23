"""Durable DynamoDB persistence for SEO audits and AI request logs."""
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get('SEO_TOOLS_TABLE', 'stack-wecare-digital-SeoToolsTable')
_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource(
            'dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1')
        ).Table(TABLE_NAME)
    return _table


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def put_record(record: Dict[str, Any]) -> Dict[str, Any]:
    required = {'id', 'recordType', 'createdAt', 'slug'}
    missing = required - set(record)
    if missing:
        raise ValueError(f"Missing storage fields: {', '.join(sorted(missing))}")
    table().put_item(Item=_clean(record))
    return record


def get_audit(audit_id: str) -> Optional[Dict[str, Any]]:
    item = table().get_item(Key={'id': audit_id}).get('Item')
    if not item or item.get('recordType') != 'audit':
        return None
    return _json_safe(item)


def list_records(record_type: str, scope: str = '', limit: int = 200) -> List[Dict[str, Any]]:
    limit = min(max(limit, 1), 500)
    kwargs: Dict[str, Any] = {
        'IndexName': 'recordType-createdAt-index',
        'KeyConditionExpression': Key('recordType').eq(record_type),
        'ScanIndexForward': False,
    }
    items: List[Dict[str, Any]] = []
    while len(items) < limit:
        response = table().query(**kwargs)
        page = response.get('Items', [])
        if scope == 'pages':
            page = [item for item in page if item.get('pageType') != 'blog']
        elif scope == 'blog':
            page = [item for item in page if item.get('pageType') == 'blog']
        items.extend(page)
        if 'LastEvaluatedKey' not in response:
            break
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    return [_json_safe(item) for item in items[:limit]]


def list_slug_records(slug: str) -> List[Dict[str, Any]]:
    kwargs: Dict[str, Any] = {
        'IndexName': 'slug-createdAt-index',
        'KeyConditionExpression': Key('slug').eq(slug),
        'ScanIndexForward': False,
    }
    items: List[Dict[str, Any]] = []
    while True:
        response = table().query(**kwargs)
        items.extend(response.get('Items', []))
        if 'LastEvaluatedKey' not in response:
            break
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    return [_json_safe(item) for item in items]



BLOG_RECORD_TYPE = 'blogPost'
PUBLIC_SITE_URL = os.environ.get('PUBLIC_SITE_URL', 'https://wecare.digital').rstrip('/')


def _slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', str(value or '').strip().lower()).strip('-')
    if not slug:
        raise ValueError('A URL-safe blog slug could not be generated')
    return slug[:120]


def _blog_view(item: Dict[str, Any], include_content: bool = True) -> Dict[str, Any]:
    post = _json_safe(item)
    json_ld = post.get('jsonLd') or {}
    schemas = [value for value in json_ld.values() if isinstance(value, dict) and value]
    result = {
        'id': post.get('id', ''),
        'title': post.get('title', ''),
        'slug': post.get('slug', ''),
        'excerpt': post.get('excerpt', ''),
        'url': post.get('url') or f"{PUBLIC_SITE_URL}/post/{post.get('slug', '')}",
        'seoTitle': post.get('seoTitle', ''),
        'metaDescription': post.get('metaDescription', ''),
        'focusKeyword': post.get('focusKeyword', ''),
        'keywords': post.get('secondaryKeywords', []) or post.get('tags', []) or [],
        'jsonLd': json_ld,
        'jsonLdCount': len(schemas),
        'hasCustomSeo': bool(post.get('seoTitle') or post.get('metaDescription') or schemas),
        'tagCount': len(post.get('tags', []) or []),
        'publishedDate': post.get('publishedAt', ''),
        'modifiedDate': post.get('updatedAt', ''),
        'coverImage': post.get('coverImage', ''),
        'status': post.get('status', 'draft'),
        'category': post.get('category', ''),
        'tags': post.get('tags', []) or [],
        'hashtags': post.get('hashtags', []) or [],
        'authorName': post.get('authorName', 'WECARE.DIGITAL'),
        'robots': post.get('robots', 'index, follow, max-image-preview:large'),
    }
    if include_content:
        result['content'] = post.get('content', '')
        result['contentText'] = post.get('content', '')
    return result


def list_blog_posts(published_only: bool = False, limit: int = 500, include_content: bool = True) -> List[Dict[str, Any]]:
    posts = list_records(BLOG_RECORD_TYPE, limit=limit)
    if published_only:
        posts = [post for post in posts if post.get('status') == 'published']
    return [_blog_view(post, include_content=include_content) for post in posts]


def get_blog_post(slug: str, published_only: bool = False) -> Optional[Dict[str, Any]]:
    wanted = str(slug or '').strip().strip('/')
    if not wanted:
        return None
    for item in list_slug_records(wanted):
        if item.get('recordType') != BLOG_RECORD_TYPE:
            continue
        if published_only and item.get('status') != 'published':
            continue
        return _blog_view(item, include_content=True)
    return None


def blog_form_options() -> Dict[str, List[Dict[str, str]]]:
    posts = list_blog_posts(limit=500, include_content=False)
    category_values = sorted({str(post.get('category', '')).strip() for post in posts if post.get('category')})
    tag_values = sorted({
        str(tag).strip()
        for post in posts
        for tag in (post.get('tags') or [])
        if str(tag).strip()
    })
    return {
        'categories': [{'id': value, 'label': value, 'slug': _slugify(value)} for value in category_values],
        'tags': [{'id': value, 'label': value, 'slug': _slugify(value)} for value in tag_values],
    }


def create_blog_post(body: Dict[str, Any], actor: str) -> Dict[str, Any]:
    title = str(body.get('title', '')).strip()
    content = str(body.get('content', '')).strip()
    if not title or not content:
        raise ValueError('title and content required')

    slug = _slugify(str(body.get('slug') or title))
    if get_blog_post(slug):
        raise ValueError(f'Blog slug already exists: {slug}')

    created_at = now_iso()
    status = str(body.get('status') or 'published').strip().lower()
    if status not in {'draft', 'published'}:
        raise ValueError('status must be draft or published')
    category = str(body.get('category') or '').strip()
    if not category:
        category_ids = body.get('categoryIds') or []
        category = str(category_ids[0]).strip() if category_ids else ''

    tags = [str(value).strip() for value in (body.get('tagLabels') or body.get('tags') or []) if str(value).strip()]
    hashtags = [str(value).lstrip('#').strip() for value in (body.get('hashtags') or []) if str(value).strip()]
    clean_content = re.sub(r'^#{1,3}\s+', '', content, flags=re.MULTILINE).strip()
    excerpt = str(body.get('excerpt') or '').strip() or re.sub(r'\s+', ' ', clean_content)[:220].strip()

    record = {
        'id': f'blog_{uuid.uuid4().hex}',
        'recordType': BLOG_RECORD_TYPE,
        'createdAt': created_at,
        'updatedAt': created_at,
        'publishedAt': created_at if status == 'published' else '',
        'slug': slug,
        'title': title,
        'excerpt': excerpt,
        'content': content,
        'status': status,
        'category': category,
        'tags': tags,
        'hashtags': hashtags,
        'coverImage': str(body.get('coverImage') or '').strip(),
        'authorName': str(body.get('authorName') or actor or 'WECARE.DIGITAL').strip(),
        'seoTitle': str(body.get('seoTitle') or '').strip(),
        'metaDescription': str(body.get('metaDescription') or '').strip(),
        'focusKeyword': str(body.get('focusKeyword') or '').strip(),
        'secondaryKeywords': body.get('secondaryKeywords') or [],
        'jsonLd': body.get('jsonLd') or {},
        'robots': str(body.get('robots') or 'index, follow, max-image-preview:large').strip(),
        'url': f'{PUBLIC_SITE_URL}/post/{slug}',
        'version': 1,
        'createdBy': actor,
        'updatedBy': actor,
    }
    put_record(record)
    return {
        'postId': record['id'],
        'slug': slug,
        'title': title,
        'status': status,
        'url': record['url'],
        'rebuildRequired': status == 'published',
    }


def clean_blog_post(slug: str, actor: str) -> Dict[str, Any]:
    post = get_blog_post(slug)
    if not post:
        raise LookupError('Blog post not found')
    items = [item for item in list_slug_records(post['slug']) if item.get('recordType') == BLOG_RECORD_TYPE]
    if not items:
        raise LookupError('Blog post not found')
    raw = items[0]
    removed_tags = int(bool(raw.get('seoTitle'))) + int(bool(raw.get('metaDescription')))
    removed_keywords = len(raw.get('secondaryKeywords') or [])
    raw.update({
        'seoTitle': '',
        'metaDescription': '',
        'focusKeyword': '',
        'secondaryKeywords': [],
        'jsonLd': {},
        'updatedAt': now_iso(),
        'updatedBy': actor,
        'version': int(raw.get('version') or 1) + 1,
    })
    table().put_item(Item=_clean(raw))
    return {
        'slug': post['slug'],
        'postId': post['id'],
        'title': post['title'],
        'cleaned': {'tagsRemoved': removed_tags, 'keywordsRemoved': removed_keywords},
    }


def apply_blog_audit(audit: Dict[str, Any], actor: str) -> Dict[str, Any]:
    slug = str(audit.get('slug') or audit.get('blogSlug') or '').strip()
    post = get_blog_post(slug)
    if not post:
        raise LookupError('Blog post not found')
    items = [item for item in list_slug_records(slug) if item.get('recordType') == BLOG_RECORD_TYPE]
    if not items:
        raise LookupError('Blog post not found')
    raw = items[0]
    ai = audit.get('fullAiResponse') or {}
    raw.update({
        'seoTitle': ai.get('seoTitle') or audit.get('suggestedSeoTitle') or '',
        'metaDescription': ai.get('metaDescription') or audit.get('suggestedMetaDescription') or '',
        'focusKeyword': ai.get('focusKeyword') or audit.get('focusKeyword') or '',
        'secondaryKeywords': ai.get('secondaryKeywords') or audit.get('secondaryKeywords') or [],
        'jsonLd': ai.get('jsonLd') or audit.get('suggestedJsonLd') or {},
        'updatedAt': now_iso(),
        'updatedBy': actor,
        'version': int(raw.get('version') or 1) + 1,
    })
    table().put_item(Item=_clean(raw))
    return _blog_view(raw, include_content=True)

def transition_audit(
    audit_id: str,
    expected_statuses: Iterable[str],
    new_status: str,
    actor: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    expected = list(expected_statuses)
    if not expected:
        raise ValueError('At least one expected status is required')
    names = {'#status': 'status'}
    values: Dict[str, Any] = {
        ':newStatus': new_status, ':actor': actor, ':updatedAt': now_iso(),
        ':auditType': 'audit',
    }
    assignments = ['#status = :newStatus', 'reviewedBy = :actor', 'updatedAt = :updatedAt']
    for index, status in enumerate(expected):
        values[f':expected{index}'] = status
    for index, (key, value) in enumerate((extra or {}).items()):
        name, token = f'#extra{index}', f':extra{index}'
        names[name], values[token] = key, _clean(value)
        assignments.append(f'{name} = {token}')
    condition = 'recordType = :auditType AND #status IN (' + ', '.join(
        f':expected{index}' for index in range(len(expected))
    ) + ')'
    try:
        response = table().update_item(
            Key={'id': audit_id}, UpdateExpression='SET ' + ', '.join(assignments),
            ConditionExpression=condition, ExpressionAttributeNames=names,
            ExpressionAttributeValues=values, ReturnValues='ALL_NEW',
        )
        return _json_safe(response.get('Attributes', {}))
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            return None
        raise


def delete_slug_audits(slug: str) -> int:
    audits = [item for item in list_slug_records(slug) if item.get('recordType') == 'audit']
    for item in audits:
        table().delete_item(Key={'id': item['id']})
    return len(audits)
