#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

AUTHOR = 'Anew by WECARE.DIGITAL'
CATEGORY = 'Gastronomy'
BATCH_SIZE = 25


def _inline_nodes(text: str):
    nodes = []
    pattern = re.compile(r'(\*\*.+?\*\*|\*[^*]+?\*)')
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            nodes.append({'type': 'TEXT', 'nodes': [], 'textData': {'text': text[pos:match.start()], 'decorations': []}})
        token = match.group(0)
        if token.startswith('**'):
            value = token[2:-2]
            decorations = [{'type': 'BOLD', 'fontWeightValue': 700}]
        else:
            value = token[1:-1]
            decorations = [{'type': 'ITALIC', 'italicData': True}]
        nodes.append({'type': 'TEXT', 'nodes': [], 'textData': {'text': value, 'decorations': decorations}})
        pos = match.end()
    if pos < len(text):
        nodes.append({'type': 'TEXT', 'nodes': [], 'textData': {'text': text[pos:], 'decorations': []}})
    return [n for n in nodes if n['textData']['text']]


def markdown_to_rich_content(markdown: str):
    lines = str(markdown or '').replace('\r\n', '\n').split('\n')
    nodes = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('## '):
            nodes.append({'type': 'HEADING', 'nodes': _inline_nodes(line[3:].strip()), 'headingData': {'level': 2}})
            i += 1
            continue
        if line.startswith('### '):
            nodes.append({'type': 'HEADING', 'nodes': _inline_nodes(line[4:].strip()), 'headingData': {'level': 3}})
            i += 1
            continue
        if line.startswith('- '):
            items = []
            while i < len(lines) and lines[i].strip().startswith('- '):
                value = lines[i].strip()[2:].strip()
                items.append({'type': 'LIST_ITEM', 'nodes': [{'type': 'PARAGRAPH', 'nodes': _inline_nodes(value), 'paragraphData': {}}], 'listItemData': {}})
                i += 1
            nodes.append({'type': 'BULLETED_LIST', 'nodes': items, 'bulletedListData': {'indentation': 0, 'offset': 0}})
            continue
        nodes.append({'type': 'PARAGRAPH', 'nodes': _inline_nodes(line), 'paragraphData': {}})
        i += 1
    return {'nodes': nodes}


def _heading_texts(ricos):
    out = []
    for node in ricos.get('nodes', []):
        if node.get('type') == 'HEADING':
            out.append(''.join((x.get('textData') or {}).get('text', '') for x in node.get('nodes', [])))
    return out


def validate_batch_document(document: dict):
    errors = []
    posts = document.get('posts')
    if not isinstance(posts, list):
        return ['posts must be a list']
    if len(posts) != BATCH_SIZE:
        errors.append(f'batch must contain exactly {BATCH_SIZE} posts')
    start = document.get('batch_start')
    end = document.get('batch_end')
    if not isinstance(start, int) or not isinstance(end, int) or end != start + BATCH_SIZE - 1:
        errors.append('batch_start/batch_end must describe one contiguous 25-post batch')
    ids, slugs, titles = [], [], []
    for idx, post in enumerate(posts):
        prefix = post.get('id') or f'index {idx}'
        ids.append(post.get('id'))
        slugs.append(post.get('slug'))
        titles.append(post.get('title'))
        required = ['id','title','slug','author','category','tags','seo_title','meta_description','canonical','source_ref','body_markdown','image_status']
        for key in required:
            if not post.get(key):
                errors.append(f'{prefix}: missing {key}')
        if post.get('author') != AUTHOR:
            errors.append(f'{prefix}: author must be {AUTHOR}')
        if post.get('category') != CATEGORY:
            errors.append(f'{prefix}: category must be {CATEGORY}')
        tags = post.get('tags') or []
        if not isinstance(tags, list) or not 1 <= len(tags) <= 3:
            errors.append(f'{prefix}: must have 1-3 tags')
        slug = str(post.get('slug') or '')
        if post.get('canonical') != f'https://wecare.digital/post/{slug}/':
            errors.append(f'{prefix}: canonical must match slug')
        body = str(post.get('body_markdown') or '')
        if '\\n' in body:
            errors.append(f'{prefix}: body contains literal escaped newline')
        ricos = markdown_to_rich_content(body)
        headings = _heading_texts(ricos)
        if 'Ingredients' not in headings:
            errors.append(f'{prefix}: missing Ingredients heading')
        if 'Method' not in headings:
            errors.append(f'{prefix}: missing Method heading')
        if not any(n.get('type') == 'BULLETED_LIST' for n in ricos.get('nodes', [])):
            errors.append(f'{prefix}: missing ingredient list')
        if post.get('image_status') != 'none':
            errors.append(f'{prefix}: image_status must be none')
    if len([x for x in slugs if x]) != len(set(x for x in slugs if x)):
        errors.append('duplicate slug inside batch')
    if len([x for x in titles if x]) != len(set(x for x in titles if x)):
        errors.append('duplicate title inside batch')
    if len([x for x in ids if x]) != len(set(x for x in ids if x)):
        errors.append('duplicate id inside batch')
    if isinstance(start, int) and len(posts) == BATCH_SIZE:
        expected = [f'GAST-{n:03d}' for n in range(start, start + BATCH_SIZE)]
        if ids != expected:
            errors.append('post ids must be contiguous and match batch_start through batch_end')
    return errors


def pending_posts(document: dict, existing_slugs):
    existing = {str(s) for s in existing_slugs}
    return [post for post in document.get('posts', []) if str(post.get('slug') or '') not in existing]


def _walk_nodes(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_nodes(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_nodes(nested)


def audit_public_post(post: dict, expected: dict):
    errors = []
    slug = str(expected.get('slug') or '')
    if post.get('slug') != slug:
        errors.append(f'{slug}: slug mismatch')
    if post.get('authorName') != AUTHOR:
        errors.append(f'{slug}: author mismatch')
    if post.get('category') != CATEGORY:
        errors.append(f'{slug}: category mismatch')
    if post.get('coverImage'):
        errors.append(f'{slug}: cover image must be empty')
    nodes = ((post.get('richContent') or {}).get('nodes') or [])
    flat_parts = []
    headings = []
    node_types = []
    for node in _walk_nodes(nodes):
        kind = str(node.get('type') or '').upper()
        if kind:
            node_types.append(kind)
        text = (node.get('textData') or {}).get('text')
        if text:
            flat_parts.append(str(text))
        if kind == 'HEADING':
            value = ''.join(
                str((child.get('textData') or {}).get('text') or '')
                for child in node.get('nodes', []) or []
            )
            if value:
                headings.append(value)
    flat = ''.join(flat_parts)
    if '\\n' in flat:
        errors.append(f'{slug}: literal escaped newline in published body')
    if '## ' in flat:
        errors.append(f'{slug}: literal markdown heading in published body')
    if 'Ingredients' not in headings:
        errors.append(f'{slug}: missing Ingredients heading')
    if 'Method' not in headings:
        errors.append(f'{slug}: missing Method heading')
    if 'BULLETED_LIST' not in node_types:
        errors.append(f'{slug}: missing ingredient list')
    return errors


def _load_wix_module():
    import wix_blog_migrate as wix
    return wix


def _ensure_gastronomy_category(wix):
    data = wix.request(wix.TARGET_SITE_ID, 'GET', '/blog/v3/categories?paging.limit=100')
    for category in data.get('categories', []) or []:
        if str(category.get('label') or '').lower() == CATEGORY.lower():
            return str(category['id'])
    created = wix.request(
        wix.TARGET_SITE_ID,
        'POST',
        '/blog/v3/categories',
        {'category': {'label': CATEGORY, 'title': CATEGORY, 'slug': 'gastronomy', 'language': 'en'}},
    )
    return str(created['category']['id'])


def _ensure_tags(wix, labels):
    tags = []
    cursor = ''
    while True:
        paging = {'limit': 100}
        if cursor:
            paging['cursor'] = cursor
        data = wix.request(
            wix.TARGET_SITE_ID,
            'POST',
            '/v3/tags/query',
            {'query': {'cursorPaging': paging}},
        )
        tags.extend(data.get('tags', []) or [])
        cursor = str((((data.get('pagingMetadata') or {}).get('cursors') or {}).get('next')) or '')
        if not cursor:
            break
    existing = {str(tag.get('label') or '').lower(): str(tag.get('id') or '') for tag in tags}
    resolved = {}
    for label in labels:
        key = str(label).lower()
        if existing.get(key):
            resolved[label] = existing[key]
            continue
        created = wix.request(wix.TARGET_SITE_ID, 'POST', '/v3/tags', {'label': label, 'language': 'en'})
        resolved[label] = str(created['tag']['id'])
        existing[key] = resolved[label]
    return resolved


def publish_document(document: dict):
    errors = validate_batch_document(document)
    if errors:
        raise ValueError('batch validation failed: ' + '; '.join(errors))
    wix = _load_wix_module()
    existing_posts = wix.query_posts(wix.TARGET_SITE_ID)
    existing_slugs = {str(post.get('slug') or '') for post in existing_posts}
    pending = pending_posts(document, existing_slugs)
    if not pending:
        return {'created': 0, 'skipped': len(document.get('posts', [])), 'failures': []}
    member_id = wix.ensure_author()
    category_id = _ensure_gastronomy_category(wix)
    labels = sorted({label for post in pending for label in post.get('tags', [])})
    tag_ids = _ensure_tags(wix, labels)
    prepared = []
    for post in pending:
        prepared.append({
            'title': post['title'],
            'excerpt': post['meta_description'],
            'featured': False,
            'categoryIds': [category_id],
            'memberId': member_id,
            'tagIds': [tag_ids[label] for label in post['tags']],
            'language': 'en',
            'richContent': markdown_to_rich_content(post['body_markdown']),
            'seoSlug': post['slug'],
            'seoData': {'tags': [
                {'type': 'title', 'children': post['seo_title']},
                {'type': 'meta', 'props': {'name': 'description', 'content': post['meta_description']}},
            ]},
            'commentingEnabled': True,
        })
    created_count = 0
    failures = []
    for start in range(0, len(prepared), 20):
        batch = prepared[start:start + 20]
        data = wix.request(
            wix.TARGET_SITE_ID,
            'POST',
            '/blog/v3/bulk/draft-posts/create',
            {'draftPosts': batch, 'publish': True, 'returnFullEntity': False},
        )
        for result in data.get('results', []) or []:
            meta = result.get('itemMetadata') or {}
            if meta.get('success'):
                created_count += 1
            else:
                failures.append(meta.get('error') or {'error': 'unknown'})
    if failures:
        raise RuntimeError(f'{len(failures)} Wix publication item(s) failed: {failures}')
    return {'created': created_count, 'skipped': len(document.get('posts', [])) - len(pending), 'failures': []}


def fetch_public_post(slug: str):
    import boto3
    path = f'/seo-tools/blog-public/{slug}'
    payload = {
        'requestContext': {'apiId': 'gastronomy-audit', 'http': {'method': 'GET', 'path': path, 'sourceIp': '127.0.0.1'}},
        'rawPath': path,
    }
    response = boto3.client('lambda', region_name='us-east-1').invoke(
        FunctionName='wecare-seo-tools', InvocationType='RequestResponse', Payload=json.dumps(payload).encode()
    )
    raw = response['Payload'].read().decode()
    if response.get('FunctionError'):
        raise RuntimeError(raw[:500])
    outer = json.loads(raw)
    if int(outer.get('statusCode') or 0) != 200:
        raise RuntimeError(f'public-blog HTTP {outer.get("statusCode")}: {outer.get("body")}')
    body = json.loads(outer.get('body') or '{}')
    if body.get('ok') is not True:
        raise RuntimeError(f'public-blog returned not-ok for {slug}')
    return body.get('post') or {}


def audit_document(document: dict):
    errors = validate_batch_document(document)
    if errors:
        return errors
    audit_errors = []
    for expected in document.get('posts', []):
        audit_errors.extend(audit_public_post(fetch_public_post(expected['slug']), expected))
    return audit_errors


def load_document(path: Path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('manifest must be a JSON object')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    validate = sub.add_parser('validate')
    validate.add_argument('--manifest', required=True, type=Path)
    publish = sub.add_parser('publish')
    publish.add_argument('--manifest', required=True, type=Path)
    audit = sub.add_parser('audit')
    audit.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args(argv)
    doc = load_document(args.manifest)
    if args.command == 'validate':
        errors = validate_batch_document(doc)
        if errors:
            for error in errors:
                print(error)
            raise SystemExit(1)
        print(f"Validated {len(doc['posts'])} Gastronomy posts: GAST-{doc['batch_start']:03d} through GAST-{doc['batch_end']:03d}")
    elif args.command == 'publish':
        print(json.dumps(publish_document(doc), indent=2))
    elif args.command == 'audit':
        errors = audit_document(doc)
        if errors:
            for error in errors:
                print(error)
            raise SystemExit(1)
        print(f"Audited {len(doc['posts'])} published Gastronomy posts successfully")


if __name__ == '__main__':
    main()
