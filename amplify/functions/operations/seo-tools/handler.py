"""SEO API for AWS-native blog content plus authenticated Admin SEO tools."""
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from lambda_utils.idempotency import (
    body_hash, claim_admin_action, make_admin_idempotency_key,
)
from lambda_utils.middleware import require_auth
from lambda_utils.response import cors_response, extract_origin, options_response

import ai
import storage
import wix

logger = logging.getLogger(__name__)
INPUT_COST_PER_M = 3.0
OUTPUT_COST_PER_M = 15.0


def _method_path(event: Dict[str, Any]) -> Tuple[str, str]:
    context = event.get('requestContext', {})
    method = context.get('http', {}).get('method', event.get('httpMethod', 'GET')).upper()
    path = context.get('http', {}).get('path') or event.get('rawPath') or event.get('path', '/')
    return method, path.rstrip('/') or '/'


def _body(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        value = json.loads(event.get('body', '{}') or '{}')
        if not isinstance(value, dict):
            raise ValueError('Request body must be a JSON object')
        return value
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid JSON request body') from error


def _actor(event: Dict[str, Any]) -> str:
    return str(event.get('_auth', {}).get('username', '')).strip()


def _response(status: int, body: Dict[str, Any], origin: str):
    return cors_response(status, body, origin)


def _query(event: Dict[str, Any], name: str, default: str = '') -> str:
    params = event.get('queryStringParameters') or {}
    return str(params.get(name, default) or default)


def _claim(body: Dict[str, Any], actor: str, action: str, origin: str):
    key = make_admin_idempotency_key(actor, action, body_hash(body))
    try:
        claimed = claim_admin_action(key, actor, action)
    except Exception:
        logger.exception('SEO Admin action claim failed')
        return _response(503, {
            'ok': False,
            'error': 'Mutation guard unavailable; no action was performed',
        }, origin)
    if not claimed:
        return _response(409, {
            'ok': False,
            'error': 'This Admin action was already submitted',
        }, origin)
    return None


def _slug(value: Any) -> str:
    slug = str(value or '').strip()
    if not slug:
        raise ValueError('path is required')
    return slug if slug.startswith('/') else '/' + slug


def _cost(input_tokens: int, output_tokens: int) -> float:
    value = (input_tokens / 1_000_000) * INPUT_COST_PER_M
    value += (output_tokens / 1_000_000) * OUTPUT_COST_PER_M
    return round(value, 4)


def _put_error_log(slug: str, page_type: str, started: float) -> None:
    storage.put_record({
        'id': f'log_{uuid.uuid4().hex}',
        'recordType': 'log',
        'createdAt': storage.now_iso(),
        'slug': slug,
        'blogSlug': slug,
        'pageType': page_type,
        'provider': 'aws-bedrock',
        'model': ai.PRIMARY_MODEL,
        'status': 'error',
        'errorMessage': 'SEO generation failed',
        'inputTokens': 0,
        'outputTokens': 0,
        'costEstimate': 0,
        'durationMs': int((time.monotonic() - started) * 1000),
    })


def _run_audit(page: Dict[str, Any], page_type: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    started = time.monotonic()
    slug = str(page['slug'])
    try:
        generated = ai.invoke_seo(page, page_type)
        result = generated['result']
        created_at = storage.now_iso()
        duration_ms = int((time.monotonic() - started) * 1000)
        input_tokens = int(generated.get('inputTokens', 0))
        output_tokens = int(generated.get('outputTokens', 0))
        estimate = _cost(input_tokens, output_tokens)
        log = {
            'id': f'log_{uuid.uuid4().hex}',
            'recordType': 'log',
            'createdAt': created_at,
            'slug': slug,
            'blogSlug': slug,
            'pageType': page_type,
            'provider': 'aws-bedrock',
            'model': generated.get('model', ai.PRIMARY_MODEL),
            'status': 'success',
            'inputTokens': input_tokens,
            'outputTokens': output_tokens,
            'costEstimate': estimate,
            'durationMs': duration_ms,
        }
        audit = {
            'id': f'audit_{uuid.uuid4().hex}',
            'recordType': 'audit',
            'createdAt': created_at,
            'updatedAt': created_at,
            'slug': slug,
            'blogSlug': slug,
            'blogPostId': page.get('id', ''),
            'blogTitle': page.get('title') or page.get('name') or slug,
            'pageType': page_type,
            'currentSeoTitle': page.get('seoTitle') or page.get('currentSeoTitle') or page.get('title', ''),
            'suggestedSeoTitle': result.get('seoTitle', ''),
            'currentMetaDescription': page.get('metaDescription', ''),
            'suggestedMetaDescription': result.get('metaDescription', ''),
            'focusKeyword': result.get('focusKeyword', ''),
            'secondaryKeywords': result.get('secondaryKeywords', []),
            'suggestedTags': result.get('categoryTags', []),
            'suggestedJsonLd': result.get('jsonLd', {}),
            'internalLinkSuggestions': result.get('internalLinks', []),
            'imageAltSuggestions': result.get('imageAltText', []),
            'seoScoreBefore': result.get('seoScoreBefore', 0),
            'seoScoreAfter': result.get('seoScoreAfter', 0),
            'scoreBreakdown': result.get('scoreBreakdown', {}),
            'warnings': result.get('warnings', []),
            'fullAiResponse': result,
            'aiProvider': 'aws-bedrock',
            'aiModel': generated.get('model', ai.PRIMARY_MODEL),
            'status': 'pending_review',
        }
        storage.put_record(log)
        storage.put_record(audit)
        return audit, {
            'inputTokens': input_tokens,
            'outputTokens': output_tokens,
            'costEstimate': estimate,
            'durationMs': duration_ms,
            'model': log['model'],
        }
    except Exception:
        logger.exception('SEO generation failed')
        try:
            _put_error_log(slug, page_type, started)
        except Exception:
            logger.exception('SEO error log persistence failed')
        raise


def _blog_audit(body: Dict[str, Any], actor: str, origin: str):
    slug = str(body.get('slug', '')).strip()
    if not slug:
        raise ValueError('slug is required')
    duplicate = _claim({'slug': slug}, actor, 'seo.blog.audit', origin)
    if duplicate:
        return duplicate
    post = storage.get_blog_post(slug)
    if not post:
        raise LookupError('Blog post not found')
    audit, log = _run_audit(post, 'blog')
    return _response(200, {'ok': True, 'audit': audit, 'log': log}, origin)


def _page_audit(body: Dict[str, Any], actor: str, origin: str):
    slug = _slug(body.get('path'))
    page_type = str(body.get('pageType') or 'page').strip().lower()
    stored_type = page_type if page_type in {'product', 'system'} else 'page'
    claim_body = {**body, 'path': slug}
    duplicate = _claim(claim_body, actor, f'seo.{stored_type}.audit', origin)
    if duplicate:
        return duplicate
    current = wix.page_seo(slug)
    page = {
        **body,
        **current,
        'slug': slug,
        'name': str(body.get('name') or slug.lstrip('/').replace('-', ' ')),
        'title': current.get('title') or body.get('name') or slug,
        'url': wix.SITE_BASE + slug,
        'currentSeoTitle': current.get('title', ''),
    }
    audit, log = _run_audit(page, stored_type)
    return _response(200, {'ok': True, 'audit': audit, 'log': log}, origin)


def _page_clean(body: Dict[str, Any], actor: str, origin: str):
    slug = _slug(body.get('path'))
    duplicate = _claim({**body, 'path': slug}, actor, 'seo.page.clean', origin)
    if duplicate:
        return duplicate
    removed = storage.delete_slug_audits(slug)
    current = wix.page_seo(slug)
    message = (
        f'Removed {removed} previous audit(s) for {slug}. Page is now clean for fresh audit.'
        if removed else f'No previous audits found for {slug}. Page is already clean.'
    )
    return _response(200, {
        'ok': True,
        'slug': slug,
        'name': body.get('name') or slug,
        'pageType': body.get('pageType') or 'site',
        'cleaned': {'auditsRemoved': removed, 'message': message},
        'currentSeo': current,
    }, origin)


def _review(body: Dict[str, Any], actor: str, origin: str):
    audit_id = str(body.get('auditId', '')).strip()
    action = str(body.get('action', '')).strip().lower()
    if not audit_id or action not in {'approve', 'reject', 'apply'}:
        raise ValueError('auditId and action (approve, reject, or apply) required')
    audit = storage.get_audit(audit_id)
    if not audit:
        raise LookupError('Audit not found')
    if action in {'approve', 'reject'}:
        target = 'approved' if action == 'approve' else 'rejected'
        updated = storage.transition_audit(
            audit_id, ['pending_review'], target, actor,
        )
        if not updated:
            return _response(409, {'ok': False, 'error': 'Audit state changed; refresh and retry'}, origin)
        return _response(200, {'ok': True, 'audit': updated}, origin)
    if audit.get('pageType') != 'blog':
        return _response(501, {
            'ok': False,
            'error': 'Applying SEO is currently supported for blog posts only',
        }, origin)
    if audit.get('status') != 'approved':
        return _response(409, {'ok': False, 'error': 'Audit must be approved before apply'}, origin)
    duplicate = _claim({'auditId': audit_id}, actor, 'seo.blog.apply', origin)
    if duplicate:
        return duplicate
    applying = storage.transition_audit(audit_id, ['approved'], 'applying', actor)
    if not applying:
        return _response(409, {'ok': False, 'error': 'Audit state changed; refresh and retry'}, origin)
    try:
        storage.apply_blog_audit(applying, actor)
    except Exception:
        logger.exception('AWS blog SEO apply failed')
        try:
            restored = storage.transition_audit(
                audit_id, ['applying'], 'approved', actor,
                {'applicationError': 'Blog SEO apply failed'},
            )
        except Exception:
            logger.exception('Failed to restore SEO audit after blog apply failure')
            restored = None
        if not restored:
            logger.error('SEO audit state is unconfirmed after blog apply failure')
            return _response(502, {
                'ok': False,
                'error': 'Blog SEO apply failed; audit state could not be confirmed. Refresh before retrying',
                'stateUnconfirmed': True,
            }, origin)
        return _response(502, {'ok': False, 'error': 'Blog SEO apply failed; audit remains approved'}, origin)
    applied_at = storage.now_iso()
    updated = storage.transition_audit(
        audit_id, ['applying'], 'applied', actor,
        {'appliedAt': applied_at, 'applicationError': ''},
    )
    if not updated:
        return _response(500, {
            'ok': False,
            'error': 'SEO was applied but final audit status persistence failed',
            'applied': True,
        }, origin)
    return _response(200, {'ok': True, 'audit': updated, 'applied': True}, origin)


def _route_get(path: str, event: Dict[str, Any], origin: str):
    if path.endswith('/blog-posts'):
        posts = storage.list_blog_posts()
        return _response(200, {'ok': True, 'posts': posts, 'total': len(posts)}, origin)
    if path.endswith('/blog-create'):
        return _response(200, {'ok': True, **storage.blog_form_options()}, origin)
    if path.endswith('/seo-logs'):
        record_type = 'log' if _query(event, 'type', 'audits') == 'logs' else 'audit'
        scope = _query(event, 'scope')
        records = storage.list_records(record_type, scope)
        key = 'logs' if record_type == 'log' else 'audits'
        return _response(200, {'ok': True, key: records}, origin)
    if path.endswith('/site-pages'):
        pages = wix.list_site_pages()
        return _response(200, {'ok': True, 'pages': pages, 'total': len(pages)}, origin)
    if path.endswith('/product-pages'):
        products = wix.list_products()
        return _response(200, {'ok': True, 'products': products, 'total': len(products)}, origin)
    return _response(404, {'ok': False, 'error': 'SEO route not found'}, origin)


def _route_post(path: str, body: Dict[str, Any], actor: str, origin: str):
    if path.endswith('/blog-create'):
        duplicate = _claim(body, actor, 'seo.blog.create', origin)
        if duplicate:
            return duplicate
        return _response(200, {'ok': True, **storage.create_blog_post(body, actor)}, origin)
    if path.endswith('/seo-clean'):
        slug = str(body.get('slug', '')).strip()
        if not slug:
            raise ValueError('slug required')
        duplicate = _claim({'slug': slug}, actor, 'seo.blog.clean', origin)
        if duplicate:
            return duplicate
        return _response(200, {'ok': True, **storage.clean_blog_post(slug, actor)}, origin)
    if path.endswith('/ai-seo-audit'):
        return _blog_audit(body, actor, origin)
    if path.endswith('/page-audit'):
        return _page_audit(body, actor, origin)
    if path.endswith('/page-clean'):
        return _page_clean(body, actor, origin)
    if path.endswith('/seo-approve'):
        return _review(body, actor, origin)
    return _response(404, {'ok': False, 'error': 'SEO route not found'}, origin)


def handler(event: Dict[str, Any], context: Optional[Any]):
    origin = extract_origin(event)
    method, path = _method_path(event)
    if method == 'OPTIONS':
        return options_response(origin)

    # Public read surface for Amplify static generation. Only published posts are
    # returned; drafts, audits, logs and Admin mutation routes remain protected.
    if method == 'GET' and (path.endswith('/blog-public') or '/blog-public/' in path):
        if '/blog-public/' in path:
            slug = path.split('/blog-public/', 1)[1].strip('/')
            post = storage.get_blog_post(slug, published_only=True)
            if not post:
                return _response(404, {'ok': False, 'error': 'Blog post not found'}, origin)
            return _response(200, {'ok': True, 'post': post}, origin)
        posts = storage.list_blog_posts(published_only=True, include_content=False)
        return _response(200, {'ok': True, 'posts': posts, 'total': len(posts)}, origin)

    auth_result = require_auth(event, required_role='Admin')
    if auth_result is not None:
        return auth_result
    actor = _actor(event)
    if not actor:
        return _response(403, {'ok': False, 'error': 'Admin identity required'}, origin)
    try:
        if method == 'GET':
            return _route_get(path, event, origin)
        if method == 'POST':
            return _route_post(path, _body(event), actor, origin)
        return _response(405, {'ok': False, 'error': 'Method not allowed'}, origin)
    except ValueError as error:
        return _response(400, {'ok': False, 'error': str(error)}, origin)
    except LookupError as error:
        return _response(404, {'ok': False, 'error': str(error)}, origin)
    except Exception:
        logger.exception('SEO tools request failed')
        return _response(500, {'ok': False, 'error': 'SEO operation failed'}, origin)
