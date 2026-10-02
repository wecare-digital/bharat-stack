"""SEO lists published page data without calling the removed legacy page inventory."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def test_page_inventory_matches_generated_catalog_and_does_not_fetch_wix():
    spec = importlib.util.spec_from_file_location('catalog_wix', ROOT / 'amplify/functions/operations/seo-tools/wix.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog = json.loads((ROOT / 'config/public-pages.json').read_text())['pages']
    with patch.object(module, 'public_json', side_effect=AssertionError('page listing must use the local catalog')):
        result = module.list_site_pages()
    assert [p['path'] for p in result] == [p['path'] for p in catalog]
    assert all(p['url'] == 'https://wecare.digital' + p['path'] for p in result)
    assert [p['metaDescription'] for p in result] == [p['description'] for p in catalog]
