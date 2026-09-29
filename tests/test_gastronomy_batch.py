import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'gastronomy_batch.py'


def load_module():
    spec = importlib.util.spec_from_file_location('gastronomy_batch', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_post(n: int, title=None):
    slug = f'post-{n:03d}'
    return {
        'id': f'GAST-{n:03d}',
        'title': title or f'Post {n:03d}',
        'slug': slug,
        'author': 'Anew by WECARE.DIGITAL',
        'category': 'Gastronomy',
        'tags': ['Breakfast'],
        'seo_title': f'{title or f"Post {n:03d}"} | WECARE.DIGITAL',
        'meta_description': f'Meta description for post {n:03d}.',
        'canonical': f'https://wecare.digital/post/{slug}/',
        'source_ref': f'private source p.{n}',
        'image_status': 'none',
        'article_type': 'RECIPE',
        # THE BODY HAS TO CLEAR THE 250-CHARACTER EDITORIAL MINIMUM, WITH ROOM TO SPARE.
        #
        # This fixture is the VALID document that test_v2_manifest_accepts_150_posts asserts
        # is accepted, so every rule in validate_batch_document has to pass on it. It measured
        # 247 characters stripped against the >= 250 check in scripts/gastronomy_batch.py -
        # short by three - so that test failed with 150 identical
        # "body too thin for editorial publication" errors, one per post, which reads like a
        # validator bug rather than a three-character fixture.
        #
        # Both sides landed in b796cae5, so this was never a threshold that moved out from
        # under the fixture; they simply disagreed from the start. The threshold is the side
        # with intent behind it - there is a whole quality-gate around it in blog_quality_v2.py
        # - so the fixture is what changes.
        #
        # Deliberately ~300 rather than exactly 250. The tests below append a sentence to this
        # body and rely on it staying valid, and a fixture sitting three characters from a
        # boundary is one copy edit away from flipping back - the same argument the design
        # contract makes about .usecase-pills sitting 27px from its breakpoint.
        'body_markdown': (
            'This recipe has a clear culinary identity and enough context to explain what to look for before cooking.\n\n'
            '## Ingredients\n\n- 1 cup ingredient\n- 1 tsp spice\n\n'
            '## Method\n\nCook carefully, watching texture and heat rather than relying only on the clock. '
            'Let it rest off the heat before serving, so the texture settles rather than tightening.'
        ),
    }


def make_doc(start=455, size=25):
    return {
        'quality_version': 2,
        'batch_start': start,
        'batch_end': start + size - 1,
        'source_profile': {
            'label': 'Example source',
            'blocked_public_terms': ['Example Publisher', 'Example Author', 'Example Institute'],
            'required_public_attribution_terms': [],
        },
        'posts': [make_post(i) for i in range(start, start + size)],
    }


def test_v2_manifest_accepts_150_posts():
    m = load_module()
    doc = make_doc(size=150)
    assert m.validate_batch_document(doc, require_v2=True) == []


def test_manifest_over_150_is_rejected():
    m = load_module()
    doc = make_doc(size=151)
    errors = m.validate_batch_document(doc, require_v2=True)
    assert any('1-150' in e for e in errors)


def test_wix_chunk_size_remains_20():
    m = load_module()
    assert m.MAX_MANIFEST_POSTS == 150
    assert m.WIX_WRITE_CHUNK_SIZE == 20


def test_source_terms_are_dynamic_not_isha_specific():
    m = load_module()
    doc = make_doc(size=1)
    doc['posts'][0]['body_markdown'] += '\n\nExample Publisher prepared the original material.'
    errors = m.validate_batch_document(doc, require_v2=True)
    assert any('Example Publisher' in e for e in errors)
    assert not any('Isha' in e for e in errors)


def test_required_attribution_can_be_explicitly_allowed():
    m = load_module()
    doc = make_doc(size=1)
    doc['source_profile']['blocked_public_terms'] = ['Named Theory']
    doc['source_profile']['required_public_attribution_terms'] = ['Named Theory']
    doc['posts'][0]['body_markdown'] += '\n\nNamed Theory is discussed here because attribution is required.'
    errors = m.validate_batch_document(doc, require_v2=True)
    assert not any('Named Theory' in e for e in errors)


def test_generic_source_scaffolding_is_rejected():
    m = load_module()
    doc = make_doc(size=1)
    doc['posts'][0]['body_markdown'] += '\n\nThe cookbook says to toast the spice first.'
    errors = m.validate_batch_document(doc, require_v2=True)
    assert any('cookbook-facing language' in e for e in errors)


def test_personal_possessive_title_requires_justification():
    m = load_module()
    doc = make_doc(size=1)
    p = doc['posts'][0]
    p['title'] = "Caroline's Carob Almond Cookies"
    p['seo_title'] = "Caroline's Carob Almond Cookies | WECARE.DIGITAL"
    errors = m.validate_batch_document(doc, require_v2=True)
    assert any('personal/kinship name' in e for e in errors)


def test_personal_title_can_be_justified_when_identity_is_essential():
    m = load_module()
    doc = make_doc(size=1)
    p = doc['posts'][0]
    p['title'] = "Caroline's Carob Almond Cookies"
    p['seo_title'] = "Caroline's Carob Almond Cookies | WECARE.DIGITAL"
    p['public_name_justification'] = 'Established dish identity with required attribution.'
    errors = m.validate_batch_document(doc, require_v2=True)
    assert not any('personal/kinship name' in e for e in errors)


def test_health_claim_title_requires_review():
    m = load_module()
    doc = make_doc(size=1)
    p = doc['posts'][0]
    p['title'] = 'Cold Cure Soup'
    p['seo_title'] = 'Cold Cure Soup | WECARE.DIGITAL'
    errors = m.validate_batch_document(doc, require_v2=True)
    assert any('health-claim term' in e for e in errors)


def test_non_recipe_article_does_not_require_ingredients_method():
    m = load_module()
    doc = make_doc(size=1)
    p = doc['posts'][0]
    p['article_type'] = 'CULINARY_ARTICLE'
    p['body_markdown'] = (
        'A first substantial paragraph explains the culinary distinction clearly enough to orient the reader without source-facing framing.\n\n'
        'A second substantial paragraph develops the technique, ingredient logic, or cultural context while remaining independently written.'
    )
    errors = m.validate_batch_document(doc, require_v2=True)
    assert not any('Ingredients heading' in e for e in errors)
    assert not any('Method heading' in e for e in errors)


def test_legacy_manifest_can_still_validate_but_cannot_publish():
    m = load_module()
    legacy = {
        'batch_start': 41,
        'batch_end': 41,
        'posts': [make_post(41)],
    }
    assert not any('quality_version' in e for e in m.validate_batch_document(legacy, require_v2=False))
    assert any('quality_version' in e for e in m.validate_batch_document(legacy, require_v2=True))


def test_progress_is_variable_size_up_to_150():
    m = load_module()
    progress = {'completed_through': 454, 'next_id': 455, 'max_manifest_posts': 150}
    assert m.validate_progress(progress) == []
    advanced = m.advance_progress(progress, 455, 604)
    assert advanced['completed_through'] == 604
    assert advanced['next_id'] == 605
    assert advanced['last_manifest'] == 'GAST-455-GAST-604'


def test_progress_rejects_skip_and_over_150():
    m = load_module()
    progress = {'completed_through': 454, 'next_id': 455, 'max_manifest_posts': 150}
    try:
        m.advance_progress(progress, 456, 500)
    except ValueError as exc:
        assert 'next_id' in str(exc)
    else:
        raise AssertionError('expected skipped start to fail')

    try:
        m.advance_progress(progress, 455, 605)
    except ValueError as exc:
        assert '1-150' in str(exc)
    else:
        raise AssertionError('expected oversized manifest to fail')
