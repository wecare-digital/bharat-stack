"""Tests for the WhatsApp validators added to lambda_utils.validation."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))

from lambda_utils import validation as v  # noqa: E402


def test_graph_version():
    assert v.validate_graph_version('v25.0') is True
    assert v.validate_graph_version('25') is False


def test_numeric_id():
    assert v.validate_numeric_id('2094615664435155') is True
    assert v.validate_numeric_id('abc') is False


def test_qr_code_id():
    assert v.validate_qr_code_id('ABCDEFGH123456') is True   # 14 alnum
    assert v.validate_qr_code_id('short') is False
    assert v.validate_qr_code_id('TOOLONG12345678') is False  # 15


def test_pagination_limit():
    assert v.validate_pagination_limit(50) is True
    assert v.validate_pagination_limit(0) is False
    assert v.validate_pagination_limit(101) is False


def test_https_url():
    assert v.validate_https_url('https://x.com') is True
    assert v.validate_https_url('http://x.com') is False


def test_fields_allowlist():
    bad = v.validate_fields_allowlist('id,name,evil', {'id', 'name'})
    assert bad == ['evil']


def test_template_category():
    assert v.validate_template_category('marketing') is True
    assert v.validate_template_category('promo') is False


def test_template_ttl():
    assert v.validate_template_ttl('AUTHENTICATION', 600) is None
    assert v.validate_template_ttl('AUTHENTICATION', 5000) is not None
    assert v.validate_template_ttl('MARKETING', -1) is not None  # -1 not allowed
    assert v.validate_template_ttl('UTILITY', -1) is None


def test_template_buttons_grouping():
    bad = [{'type': 'QUICK_REPLY', 'text': 'a'}, {'type': 'URL', 'text': 'u', 'url': 'https://x'}, {'type': 'QUICK_REPLY', 'text': 'b'}]
    assert v.validate_template_buttons(bad) is not None
    good = [{'type': 'URL', 'text': 'u', 'url': 'https://x'}, {'type': 'QUICK_REPLY', 'text': 'a'}, {'type': 'QUICK_REPLY', 'text': 'b'}]
    assert v.validate_template_buttons(good) is None


def test_template_buttons_limits():
    assert v.validate_template_buttons([{'type': 'URL', 'text': 'x', 'url': 'u'}] * 3) is not None  # >2 URL


def test_flow_name_and_category():
    assert v.validate_flow_name('My Flow') is True
    assert v.validate_flow_name('x' * 201) is False
    assert v.validate_flow_category('SIGN_UP') is True
    assert v.validate_flow_category('NOPE') is False


def test_url_encoding_warning():
    assert v.needs_url_encoding_warning('New York') is True
    assert v.needs_url_encoding_warning('summer2023') is False
    assert v.needs_url_encoding_warning('Gonçalves') is True


def test_open_graph_checks():
    warns = v.check_open_graph({'og:title': 'T', 'og:description': '', 'og:url': 'u', 'og:image': 'rel'})
    assert any('description' in w for w in warns)
    assert any('absolute' in w for w in warns)
