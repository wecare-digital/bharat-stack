#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

AUTHOR = 'Anew by WECARE.DIGITAL'
CATEGORY = 'Gastronomy'
QUALITY_VERSION = 2
MAX_MANIFEST_POSTS = 150
WIX_WRITE_CHUNK_SIZE = 20

RECIPE_TYPES = {'RECIPE'}
GENERIC_SOURCE_PATTERNS = [
    (re.compile(r'\bsource note\b', re.I), 'source note'),
    (re.compile(r'\badapted from\b', re.I), 'adapted from'),
    (re.compile(r'\bindependently written from\b', re.I), 'independently written from'),
    (re.compile(r'\bthe source\b|\bsource recipe\b|\bsource[’\']s\b', re.I), 'source-facing language'),
    (re.compile(r'\bthe cookbook\b|\bthis cookbook\b|\bin the cookbook\b|\baccording to the cookbook\b', re.I), 'cookbook-facing language'),
    (re.compile(r'\bthe book says\b|\bin this book\b|\bthe book[’\']s\b', re.I), 'book-facing language'),
    (re.compile(r'\bthe author\b|\bauthor[’\']s\b', re.I), 'source-author biography'),
    (re.compile(r'\blearned from\b|\bcooked with\b|\bmarket connection\b', re.I), 'personal provenance'),
    (re.compile(r'\bashram\b|\bvolunteer(?:s)?\b|\bprogramme(?:s)?\b', re.I), 'source-institution provenance'),
]
CLEANUP_ARTIFACT_PATTERNS = [
    re.compile(r'\bThe\s+[’\']s\b'),
    re.compile(r'\bThe is\b'),
    re.compile(r'\bHere[’\']?s\b'),
    re.compile(r'\bas directs\b', re.I),
    re.compile(r'\bthe preparation the\b', re.I),
]
PERSONAL_TITLE_PATTERN = re.compile(
    r'^(?:Grandma|Granny|Mama|Papa|Aunty|Aunt|Uncle|Mom|Mother|Father|Dad)[’\']s\b|^[A-Z][A-Za-z.-]{2,}[’\']s\b'
)
HEALTH_TITLE_PATTERN = re.compile(r'\b(?:cure|detox|cleanse|heal|treat|prevent|medicinal)\b', re.I)


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
                items.append({
                    'type': 'LIST_ITEM',
                    'nodes': [{'type': 'PARAGRAPH', 'nodes': _inline_nodes(value), 'paragraphData': {}}],
                    'listItemData': {},
                })
                i += 1
            nodes.append({'type': 'BULLETED_LIST', 'nodes': items, 'bulletedListData': {'indentation': 0, 'offset': 0}})
            continue
        nodes.append({'type': 'PARAGRAPH', 'nodes': _inline_nodes(line), 'paragraphData': {}})
        i += 1
    return {'nodes': nodes}


def _walk_nodes(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_nodes(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_nodes(nested)


def _heading_texts(ricos):
    out = []
    for node in ricos.get('nodes', []):
        if node.get('type') == 'HEADING':
            out.append(''.join((x.get('textData') or {}).get('text', '') for x in node.get('nodes', [])))
    return out


def _node_text(node):
    parts = []
    for nested in _walk_nodes(node):
        text = (nested.get('textData') or {}).get('text')
        if text:
            parts.append(str(text))
    return ''.join(parts).strip()


def _substantive_top_level_paragraphs(ricos):
    return [
        _node_text(node)
        for node in ricos.get('nodes', [])
        if node.get('type') == 'PARAGRAPH' and len(_node_text(node)) >= 60
    ]


def _quality_version(document):
    try:
        return int(document.get('quality_version') or 1)
    except (TypeError, ValueError):
        return 1


def _source_profile(document):
    profile = document.get('source_profile') or {}
    return {
        'label': str(profile.get('label') or '').strip(),
        'blocked_public_terms': [str(x).strip() for x in profile.get('blocked_public_terms', []) if str(x).strip()],
        'required_public_attribution_terms': [
            str(x).strip() for x in profile.get('required_public_attribution_terms', []) if str(x).strip()
        ],
    }


def _public_text(post):
    return '\n'.join([
        str(post.get('title') or ''),
        str(post.get('slug') or ''),
        str(post.get('seo_title') or ''),
        str(post.get('meta_description') or ''),
        str(post.get('body_markdown') or ''),
    ])


def _source_privacy_errors(post, source_profile, prefix):
    errors = []
    public = _public_text(post)
    allowed = {x.casefold() for x in source_profile.get('required_public_attribution_terms', [])}
    for regex, label in GENERIC_SOURCE_PATTERNS:
        if regex.search(public):
            errors.append(f'{prefix}: public copy contains {label}')
    for regex in CLEANUP_ARTIFACT_PATTERNS:
        if regex.search(public):
            errors.append(f'{prefix}: malformed source-cleanup artifact')
            break
    for term in source_profile.get('blocked_public_terms', []):
        if term.casefold() in allowed:
            continue
        if term.casefold() in public.casefold():
            errors.append(f'{prefix}: public copy leaks blocked source/private term "{term}"')
    title = str(post.get('title') or '')
    if PERSONAL_TITLE_PATTERN.search(title) and not post.get('public_name_justification'):
        errors.append(f'{prefix}: title exposes a personal/kinship name without justification')
    title_and_seo = f"{title}\n{post.get('seo_title') or ''}"
    if HEALTH_TITLE_PATTERN.search(title_and_seo) and not post.get('health_claim_reviewed'):
        errors.append(f'{prefix}: title/SEO contains a health-claim term without review')
    return errors


def validate_batch_document(document: dict, require_v2=False):
    errors = []
    posts = document.get('posts')
    if not isinstance(posts, list):
        return ['posts must be a list']
    if not 1 <= len(posts) <= MAX_MANIFEST_POSTS:
        errors.append(f'manifest must contain 1-{MAX_MANIFEST_POSTS} posts')

    quality_version = _quality_version(document)
    if require_v2 and quality_version < QUALITY_VERSION:
        errors.append(f'quality_version must be {QUALITY_VERSION} or higher for publish/audit')

    start = document.get('batch_start')
    end = document.get('batch_end')
    if start is not None or end is not None:
        if not isinstance(start, int) or not isinstance(end, int) or end != start + len(posts) - 1:
            errors.append('batch_start/batch_end must match the actual contiguous manifest size')

    profile = _source_profile(document)
    if quality_version >= QUALITY_VERSION and not isinstance(document.get('source_profile'), dict):
        errors.append('quality v2 manifest requires source_profile object')

    ids, slugs, titles = [], [], []
    for idx, post in enumerate(posts):
        prefix = post.get('id') or f'index {idx}'
        ids.append(post.get('id'))
        slugs.append(post.get('slug'))
        titles.append(post.get('title'))
        required = [
            'id', 'title', 'slug', 'author', 'category', 'tags', 'seo_title',
            'meta_description', 'canonical', 'source_ref', 'body_markdown', 'image_status',
        ]
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
        article_type = str(post.get('article_type') or 'RECIPE').upper()

        if len(body.strip()) < 250:
            errors.append(f'{prefix}: body too thin for editorial publication')
        min_paragraphs = 1 if article_type in RECIPE_TYPES else 2
        if len(_substantive_top_level_paragraphs(ricos)) < min_paragraphs:
            errors.append(f'{prefix}: needs {min_paragraphs} substantive prose paragraph(s) with real spacing')
        if article_type in RECIPE_TYPES:
            if 'Ingredients' not in headings:
                errors.append(f'{prefix}: missing Ingredients heading')
            if 'Method' not in headings:
                errors.append(f'{prefix}: missing Method heading')
            if not any(n.get('type') == 'BULLETED_LIST' for n in ricos.get('nodes', [])):
                errors.append(f'{prefix}: missing ingredient list')
        if post.get('image_status') != 'none':
            errors.append(f'{prefix}: image_status must be none')

        if quality_version >= QUALITY_VERSION:
            errors.extend(_source_privacy_errors(post, profile, prefix))

    if len([x for x in slugs if x]) != len(set(x for x in slugs if x)):
        errors.append('duplicate slug inside manifest')
    if len([x for x in titles if x]) != len(set(x for x in titles if x)):
        errors.append('duplicate title inside manifest')
    if len([x for x in ids if x]) != len(set(x for x in ids if x)):
        errors.append('duplicate id inside manifest')

    if isinstance(start, int) and len(posts):
        expected = [f'GAST-{n:03d}' for n in range(start, start + len(posts))]
        if ids != expected:
            errors.append('post ids must be contiguous and match batch_start through batch_end')
    return errors


def pending_posts(document: dict, existing_slugs):
    existing = {str(s) for s in existing_slugs}
    return [post for post in document.get('posts', []) if str(post.get('slug') or '') not in existing]


def _live_public_text(post):
    nodes = ((post.get('richContent') or {}).get('nodes') or [])
    flat = ''.join(
        str((node.get('textData') or {}).get('text') or '')
        for node in _walk_nodes(nodes)
    )
    return '\n'.join([
        str(post.get('title') or ''),
        str(post.get('slug') or ''),
        str(post.get('seoTitle') or ''),
        str(post.get('metaDescription') or ''),
        flat,
    ]), nodes


def audit_public_post(post: dict, expected: dict, source_profile=None, quality_version=1):
    errors = []
    source_profile = source_profile or {'blocked_public_terms': [], 'required_public_attribution_terms': []}
    slug = str(expected.get('slug') or '')
    if post.get('slug') != slug:
        errors.append(f'{slug}: slug mismatch')
    if post.get('title') and post.get('title') != expected.get('title'):
        errors.append(f'{slug}: title mismatch')
    if post.get('authorName') != AUTHOR:
        errors.append(f'{slug}: author mismatch')
    if post.get('category') != CATEGORY:
        errors.append(f'{slug}: category mismatch')
    if post.get('coverImage'):
        errors.append(f'{slug}: cover image must be empty')
    if post.get('seoTitle') is not None and post.get('seoTitle') != expected.get('seo_title'):
        errors.append(f'{slug}: SEO title mismatch')
    if post.get('metaDescription') is not None and post.get('metaDescription') != expected.get('meta_description'):
        errors.append(f'{slug}: meta description mismatch')

    public, nodes = _live_public_text(post)
    headings = []
    node_types = []
    for node in _walk_nodes(nodes):
        kind = str(node.get('type') or '').upper()
        if kind:
            node_types.append(kind)
        if kind == 'HEADING':
            value = ''.join(
                str((child.get('textData') or {}).get('text') or '')
                for child in node.get('nodes', []) or []
            )
            if value:
                headings.append(value)

    if not public.strip():
        errors.append(f'{slug}: published body is blank')
    if re.search(r'\b(?:undefined|null|nan)\b', public, re.IGNORECASE):
        errors.append(f'{slug}: editor placeholder token in published body')
    if re.search(r'\{\s*["\']?(?:type|nodes|richContent|textData)["\']?\s*:', public):
        errors.append(f'{slug}: raw editor JSON in published body')
    if '\\n' in public:
        errors.append(f'{slug}: literal escaped newline in published body')
    if '## ' in public:
        errors.append(f'{slug}: literal markdown heading in published body')

    article_type = str(expected.get('article_type') or 'RECIPE').upper()
    min_paragraphs = 1 if article_type in RECIPE_TYPES else 2
    if len(_substantive_top_level_paragraphs({'nodes': nodes})) < min_paragraphs:
        errors.append(f'{slug}: insufficient substantive prose paragraphs')
    if article_type in RECIPE_TYPES:
        if 'Ingredients' not in headings:
            errors.append(f'{slug}: missing Ingredients heading')
        if 'Method' not in headings:
            errors.append(f'{slug}: missing Method heading')
        if 'BULLETED_LIST' not in node_types:
            errors.append(f'{slug}: missing ingredient list')

    if quality_version >= QUALITY_VERSION:
        live_expected = dict(expected)
        live_expected['title'] = post.get('title') or expected.get('title')
        live_expected['slug'] = post.get('slug') or expected.get('slug')
        live_expected['seo_title'] = post.get('seoTitle') or expected.get('seo_title')
        live_expected['meta_description'] = post.get('metaDescription') or expected.get('meta_description')
        live_expected['body_markdown'] = public
        errors.extend(_source_privacy_errors(live_expected, source_profile, slug))
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
        data = wix.request(wix.TARGET_SITE_ID, 'POST', '/v3/tags/query', {'query': {'cursorPaging': paging}})
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
    errors = validate_batch_document(document, require_v2=True)
    if errors:
        raise ValueError('manifest validation failed: ' + '; '.join(errors))
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
    for start in range(0, len(prepared), WIX_WRITE_CHUNK_SIZE):
        chunk = prepared[start:start + WIX_WRITE_CHUNK_SIZE]
        data = wix.request(
            wix.TARGET_SITE_ID,
            'POST',
            '/blog/v3/bulk/draft-posts/create',
            {'draftPosts': chunk, 'publish': True, 'returnFullEntity': False},
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
    errors = validate_batch_document(document, require_v2=True)
    if errors:
        return errors
    profile = _source_profile(document)
    quality_version = _quality_version(document)
    audit_errors = []
    for expected in document.get('posts', []):
        audit_errors.extend(
            audit_public_post(fetch_public_post(expected['slug']), expected, profile, quality_version)
        )
    return audit_errors


def validate_progress(progress: dict):
    errors = []
    completed = progress.get('completed_through')
    next_id = progress.get('next_id')
    max_posts = progress.get('max_manifest_posts')
    if max_posts != MAX_MANIFEST_POSTS:
        errors.append(f'max_manifest_posts must be {MAX_MANIFEST_POSTS}')
    if not isinstance(completed, int) or completed < 0:
        errors.append('completed_through must be a non-negative integer')
    if not isinstance(next_id, int) or not isinstance(completed, int) or next_id != completed + 1:
        errors.append('next_id must equal completed_through + 1')
    return errors


def advance_progress(progress: dict, batch_start: int, batch_end: int):
    errors = validate_progress(progress)
    if errors:
        raise ValueError('invalid progress: ' + '; '.join(errors))
    count = batch_end - batch_start + 1
    if not 1 <= count <= MAX_MANIFEST_POSTS:
        raise ValueError(f'progress update must cover 1-{MAX_MANIFEST_POSTS} posts')
    if batch_start != progress['next_id']:
        raise ValueError(f'batch_start {batch_start} does not match next_id {progress["next_id"]}')
    updated = dict(progress)
    updated['completed_through'] = batch_end
    updated['next_id'] = batch_end + 1
    updated['last_manifest'] = f'GAST-{batch_start:03d}-GAST-{batch_end:03d}'
    return updated


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
        errors = validate_batch_document(doc, require_v2=False)
        if errors:
            for error in errors:
                print(error)
            raise SystemExit(1)
        print(f"Validated {len(doc['posts'])} Gastronomy posts")
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
