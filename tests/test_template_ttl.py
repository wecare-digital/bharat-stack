"""Tests for the consolidated TTL service (lambda_utils.template_ttl)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))

from lambda_utils import template_ttl as t  # noqa: E402
from lambda_utils import validation as v  # noqa: E402


def test_humanize_seconds():
    assert t.humanize_seconds(-1) == '30 days (maximum)'
    assert t.humanize_seconds(45) == '45 seconds'
    assert t.humanize_seconds(1) == '1 second'
    assert t.humanize_seconds(900) == '15 minutes'
    assert t.humanize_seconds(3600) == '1 hour'
    assert t.humanize_seconds(43200) == '12 hours'
    assert t.humanize_seconds(2592000) == '30 days'


def test_ttl_rules_shape():
    rules = t.ttl_rules()
    assert rules['field'] == 'message_send_ttl_seconds'
    cats = rules['categories']
    assert cats['AUTHENTICATION']['minSeconds'] == 30
    assert cats['AUTHENTICATION']['maxSeconds'] == 900
    assert cats['AUTHENTICATION']['allowNeg1'] is True
    assert 'recommendation' in cats['AUTHENTICATION']
    assert cats['MARKETING']['allowNeg1'] is False
    assert cats['UTILITY']['maxSeconds'] == 43200


def test_validate_ttl_ok():
    r = t.validate_ttl('AUTHENTICATION', 600)
    assert r['ok'] is True
    assert r['error'] is None
    assert r['seconds'] == 600
    assert r['human'] == '10 minutes'


def test_validate_ttl_out_of_range():
    r = t.validate_ttl('AUTHENTICATION', 5000)
    assert r['ok'] is False
    assert '30-900' in r['error']


def test_validate_ttl_neg1_rules():
    assert t.validate_ttl('UTILITY', -1)['ok'] is True
    assert t.validate_ttl('AUTHENTICATION', -1)['ok'] is True
    assert t.validate_ttl('MARKETING', -1)['ok'] is False


def test_validate_ttl_unknown_category():
    r = t.validate_ttl('PROMO', 100)
    assert r['ok'] is False
    assert 'Unknown' in r['error']


def test_validate_ttl_non_integer():
    r = t.validate_ttl('UTILITY', 'abc')
    assert r['ok'] is False
    assert 'integer' in r['error']


def test_validate_ttl_null_warns_but_ok():
    r = t.validate_ttl('UTILITY', None)
    assert r['ok'] is True
    assert any('null' in w for w in r['warnings'])


def test_error_helper_matches_legacy():
    # Backwards-compatible string-or-None behavior preserved
    assert t.validate_ttl_error('AUTHENTICATION', 600) is None
    assert t.validate_ttl_error('AUTHENTICATION', 5000) is not None
    assert t.validate_ttl_error('UTILITY', None) is None


def test_validation_module_delegates():
    # lambda_utils.validation.validate_template_ttl now delegates here
    assert v.validate_template_ttl('AUTHENTICATION', 600) is None
    assert v.validate_template_ttl('MARKETING', -1) is not None
    assert v.validate_template_ttl('UTILITY', -1) is None


def test_detect_null_ttl_after_category_change():
    # Category changed and TTL cleared -> warning
    w = t.detect_null_ttl_after_category_change('MARKETING', 'UTILITY', None)
    assert w is not None and 'cleared' in w
    # Same category -> no warning
    assert t.detect_null_ttl_after_category_change('UTILITY', 'UTILITY', None) is None
    # TTL present -> no warning
    assert t.detect_null_ttl_after_category_change('MARKETING', 'UTILITY', 600) is None
