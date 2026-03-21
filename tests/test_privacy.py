"""Tests for lambda_utils.privacy PII redaction module."""
import pytest
from lambda_utils.privacy import mask_phone, mask_email, redact_pii, redact_string


class TestMaskPhone:
    def test_full_phone(self):
        assert mask_phone('+919330994400') == '+91****4400'

    def test_short_phone(self):
        assert mask_phone('12345') == '***'

    def test_none(self):
        assert mask_phone(None) == '***'

    def test_empty(self):
        assert mask_phone('') == '***'

    def test_without_plus(self):
        result = mask_phone('919330994400')
        assert result.endswith('4400')
        assert '****' in result


class TestMaskEmail:
    def test_normal_email(self):
        assert mask_email('user@example.com') == 'u***@example.com'

    def test_none(self):
        assert mask_email(None) == '***'

    def test_no_at(self):
        assert mask_email('invalid') == '***'


class TestRedactPii:
    def test_redacts_phone_field(self):
        data = {'phone': '+919330994400', 'name': 'Test'}
        result = redact_pii(data)
        assert '9330994400' not in result['phone']
        assert result['name'] == 'Test'

    def test_redacts_email_field(self):
        data = {'email': 'user@example.com'}
        result = redact_pii(data)
        assert 'user' not in result['email']
        assert '@example.com' in result['email']

    def test_nested_dict(self):
        data = {'contact': {'phone': '+919330994400'}}
        result = redact_pii(data)
        assert '9330994400' not in result['contact']['phone']

    def test_original_unchanged(self):
        data = {'phone': '+919330994400'}
        redact_pii(data)
        assert data['phone'] == '+919330994400'

    def test_non_dict_passthrough(self):
        assert redact_pii('string') == 'string'


class TestRedactString:
    def test_redacts_phone_in_text(self):
        result = redact_string('Call me at 9330994400 please')
        assert '9330994400' not in result

    def test_redacts_email_in_text(self):
        result = redact_string('Email user@example.com for info')
        assert 'user@example.com' not in result
        assert '@example.com' in result

    def test_none_passthrough(self):
        assert redact_string(None) is None

    def test_no_pii(self):
        assert redact_string('Hello world') == 'Hello world'
