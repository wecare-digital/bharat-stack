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
    args = parser.parse_args(argv)
    if args.command == 'validate':
        doc = load_document(args.manifest)
        errors = validate_batch_document(doc)
        if errors:
            for error in errors:
                print(error)
            raise SystemExit(1)
        print(f"Validated {len(doc['posts'])} Gastronomy posts: GAST-{doc['batch_start']:03d} through GAST-{doc['batch_end']:03d}")


if __name__ == '__main__':
    main()
