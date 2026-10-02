"""Hosting reconciliation preserves API rewrites and a real missing-page response."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / 'docs/execution/snapshots'
WWW = {'source': 'https://www.wecare.digital', 'target': 'https://wecare.digital', 'status': '301'}
FALLBACK = {'source': '/<*>', 'target': '/404.html', 'status': '404-200'}

@pytest.fixture
def redirects():
    spec = importlib.util.spec_from_file_location('hosting_redirects', ROOT / 'scripts/provision_legacy_redirects.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def rules():
    return json.loads((SNAPSHOTS / 'amplify-custom-rules-after-url-host-cleanup-20261001.json').read_text())

class Client:
    def __init__(self): self.written = None
    def update_app(self, **kwargs): self.written = kwargs['customRules']


def test_only_host_canonicalisation_is_an_explicit_redirect(redirects):
    assert redirects.desired_redirects() == [WWW]


def test_converged_configuration_is_not_rewritten(redirects, rules, tmp_path, monkeypatch):
    monkeypatch.setattr(redirects, 'ROOT', tmp_path)
    client = Client()
    assert redirects.apply(client, rules) == 0
    assert client.written is None


def test_unknown_redirect_removed_without_touching_proxy_rules(redirects, rules, tmp_path, monkeypatch):
    monkeypatch.setattr(redirects, 'ROOT', tmp_path)
    client = Client()
    existing = [{'source': '/retired-fixture', 'target': '/', 'status': '302'}] + rules
    assert redirects.apply(client, existing) == 0
    assert client.written == rules


def test_missing_page_rule_stays_last(rules):
    assert rules[-1] == FALLBACK
    assert sum(rule['source'] == '/<*>' for rule in rules) == 1


def test_both_mcp_forms_proxy_to_one_backend(rules):
    mcp = [rule for rule in rules if rule['source'] in ('/mcp', '/mcp/')]
    assert len(mcp) == 2
    assert len({rule['target'] for rule in mcp}) == 1
    assert all(rule['status'] == '200' for rule in mcp)


def test_no_path_redirects_shadow_api_or_staff_pages(rules):
    assert not [rule for rule in rules if rule['source'].startswith('/') and rule['status'] in ('301','302','307','308')]
    assert rules[0] == WWW
