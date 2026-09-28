import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'gastronomy_batch.py'


def load_module():
    spec = importlib.util.spec_from_file_location('gastronomy_batch', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_post(n: int):
    slug = f'post-{n:03d}'
    return {
        'id': f'GAST-{n:03d}',
        'title': f'Post {n:03d}',
        'slug': slug,
        'author': 'Anew by WECARE.DIGITAL',
        'category': 'Gastronomy',
        'tags': ['Breakfast'],
        'seo_title': f'Post {n:03d} | WECARE.DIGITAL',
        'meta_description': f'Meta description for post {n:03d}.',
        'canonical': f'https://wecare.digital/post/{slug}/',
        'source_ref': f'book p.{n}',
        'image_status': 'none',
        'body_markdown': 'This recipe has a clear culinary identity and enough context to explain what to look for before cooking. The opening should orient the reader without padding or generic filler.\n\nA second paragraph explains texture, balance, or ingredient choice so the article adds useful culinary context beyond a bare transcription of the recipe.\n\n## Ingredients\n\n**Makes 2 servings**\n\n- 1 cup ingredient\n- 1 tsp spice\n\n## Method\n\nCook carefully, watching the texture and heat rather than relying only on the clock. The method should be concise but complete enough to reproduce the dish.\n\n## Technique\n\nA final paragraph explains the practical cue that matters most when serving or finishing the dish, keeping the article useful and specific.',
    }


def make_doc(start=41):
    return {'batch_start': start, 'batch_end': start + 24, 'posts': [make_post(i) for i in range(start, start + 25)]}


def test_valid_25_post_batch_and_ricos_structure():
    m = load_module()
    doc = make_doc()
    assert m.validate_batch_document(doc) == []
    ricos = m.markdown_to_rich_content(doc['posts'][0]['body_markdown'])
    types = [n['type'] for n in ricos['nodes']]
    headings = [''.join(x.get('textData', {}).get('text', '') for x in n.get('nodes', [])) for n in ricos['nodes'] if n['type'] == 'HEADING']
    assert 'Ingredients' in headings
    assert 'Method' in headings
    assert 'BULLETED_LIST' in types


def test_literal_escaped_newline_is_rejected():
    m = load_module()
    doc = make_doc()
    doc['posts'][0]['body_markdown'] = r'Opening.\n\n## Ingredients\n\n- 1 cup x\n\n## Method\n\nCook.'
    errors = m.validate_batch_document(doc)
    assert any('literal escaped newline' in e for e in errors)


def test_duplicate_slug_is_rejected():
    m = load_module()
    doc = make_doc()
    doc['posts'][1]['slug'] = doc['posts'][0]['slug']
    errors = m.validate_batch_document(doc)
    assert any('duplicate slug' in e for e in errors)


def test_non_contiguous_ids_are_rejected():
    m = load_module()
    doc = make_doc()
    doc['posts'][2]['id'] = 'GAST-999'
    errors = m.validate_batch_document(doc)
    assert any('contiguous' in e for e in errors)


def test_required_editorial_metadata_is_enforced():
    m = load_module()
    doc = make_doc()
    p = doc['posts'][0]
    p['author'] = 'Other'
    p['category'] = 'Conversations'
    p['tags'] = []
    p['canonical'] = 'https://example.com/x'
    p['body_markdown'] = 'No recipe structure.'
    errors = m.validate_batch_document(doc)
    joined = '\n'.join(errors)
    assert 'author' in joined
    assert 'category' in joined
    assert '1-3 tags' in joined
    assert 'canonical' in joined
    assert 'Ingredients' in joined
    assert 'Method' in joined


def test_pending_posts_skips_existing_slugs():
    m = load_module()
    doc = make_doc()
    pending = m.pending_posts(doc, {'post-041', 'post-050'})
    assert len(pending) == 23
    assert all(p['slug'] not in {'post-041', 'post-050'} for p in pending)


def test_live_audit_rejects_literal_markdown_and_missing_structure():
    m = load_module()
    expected = make_post(41)
    bad = {
        'slug': expected['slug'],
        'authorName': 'Anew by WECARE.DIGITAL',
        'category': 'Gastronomy',
        'tags': expected['tags'],
        'seoTitle': expected['seo_title'],
        'metaDescription': expected['meta_description'],
        'richContent': {'nodes': [
            {'type': 'PARAGRAPH', 'nodes': [{'type': 'TEXT', 'textData': {'text': r'Intro.\n\n## Ingredients\n- x\n\n## Method\nCook.'}}]}
        ]},
    }
    errors = m.audit_public_post(bad, expected)
    joined = '\n'.join(errors)
    assert 'literal escaped newline' in joined
    assert 'Ingredients heading' in joined
    assert 'Method heading' in joined
    assert 'ingredient list' in joined


def test_initial_progress_state_is_valid_and_advances_one_batch():
    m = load_module()
    progress = {
        'completed_through': 40,
        'next_id': 41,
        'batch_size': 25,
        'total': 340,
        'last_batch': 'GAST-031-GAST-040',
    }
    assert m.validate_progress(progress) == []
    advanced = m.advance_progress(progress, 41, 65)
    assert advanced['completed_through'] == 65
    assert advanced['next_id'] == 66
    assert advanced['last_batch'] == 'GAST-041-GAST-065'


def test_progress_refuses_skipped_or_partial_batch():
    m = load_module()
    progress = {'completed_through': 40, 'next_id': 41, 'batch_size': 25, 'total': 340, 'last_batch': 'GAST-031-GAST-040'}
    try:
        m.advance_progress(progress, 42, 66)
    except ValueError as exc:
        assert 'next_id' in str(exc)
    else:
        raise AssertionError('expected skipped batch to fail')

    bad = dict(progress, next_id=50)
    errors = m.validate_progress(bad)
    assert any('next_id' in e for e in errors)


def test_quality_gate_rejects_thin_or_fused_recipe_body():
    m = load_module()
    doc = make_doc()
    doc['posts'][0]['body_markdown'] = (
        'Very short intro.\n'
        'Another fused line.\n'
        '## Ingredients\n'
        '- 1 cup ingredient\n'
        '## Method\n'
        'Mix and serve.'
    )
    errors = m.validate_batch_document(doc)
    joined = '\n'.join(errors)
    assert 'body too thin' in joined
    assert 'substantive prose paragraphs' in joined


def test_live_audit_rejects_editor_tokens_and_single_paragraph_body():
    m = load_module()
    expected = make_post(41)
    bad = {
        'slug': expected['slug'],
        'authorName': 'Anew by WECARE.DIGITAL',
        'category': 'Gastronomy',
        'richContent': {'nodes': [
            {
                'type': 'PARAGRAPH',
                'nodes': [{
                    'type': 'TEXT',
                    'textData': {
                        'text': 'undefined raw editor placeholder body that should never reach production'
                    }
                }],
                'paragraphData': {}
            },
            {
                'type': 'HEADING',
                'nodes': [{'type': 'TEXT', 'textData': {'text': 'Ingredients'}}],
                'headingData': {'level': 2}
            },
            {
                'type': 'BULLETED_LIST',
                'nodes': [{
                    'type': 'LIST_ITEM',
                    'nodes': [{
                        'type': 'PARAGRAPH',
                        'nodes': [{'type': 'TEXT', 'textData': {'text': '1 cup ingredient'}}],
                        'paragraphData': {}
                    }]
                }]
            },
            {
                'type': 'HEADING',
                'nodes': [{'type': 'TEXT', 'textData': {'text': 'Method'}}],
                'headingData': {'level': 2}
            }
        ]},
    }
    errors = m.audit_public_post(bad, expected)
    joined = '\n'.join(errors)
    assert 'editor placeholder token' in joined
    assert 'substantive prose paragraphs' in joined
