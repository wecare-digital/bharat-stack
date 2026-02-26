"""Tests for lambda_utils.validation module."""
import json
import base64
import pytest
from lambda_utils.validation import (
    validate_body, validate_required, validate_phone,
    validate_email, sanitize_string, sanitize_html, sanitize_dict,
)


class TestValidateBody:
    def test_json_string_body(self):
        event = {'body': '{"name": "test"}', 'isBase64Encoded': False}
        assert validate_body(event) == {'name': 'test'}

    def test_base64_body(self):
        raw = json.dumps({'key': 'val'})
        encoded = base64.b64encode(raw.encode()).decode()
        event = {'body': encoded, 'isBase64Encoded': True}
        assert validate_body(event) == {'key': 'val'}

    def test_missing_body(self):
        assert validate_body({}) == {}

    def test_invalid_json(self):
        event = {'body': 'not-json', 'isBase64Encoded': False}
        assert validate_body(event) == {}

    def test_dict_body_passthrough(self):
        event = {'body': {'already': 'parsed'}}
        assert validate_body(event) == {'already': 'parsed'}

    def test_none_body(self):
        event = {'body': None}
        assert validate_body(event) == {}


class TestValidateRequired:
    def test_all_present(self):
        data = {'name': 'Alice', 'phone': '+1234567890'}
        assert validate_required(data, ['name', 'phone']) == []

    def test_missing_field(self):
        data = {'name': 'Alice'}
        assert validate_required(data, ['name', 'phone']) == ['phone']

    def test_empty_string(self):
        data = {'name': '   ', 'phone': '+1234567890'}
        assert validate_required(data, ['name', 'phone']) == ['name']

    def test_none_value(self):
        data = {'name': None}
        assert validate_required(data, ['name']) == ['name']

    def test_zero_is_valid(self):
        data = {'count': 0}
        assert validate_required(data, ['count']) == []

    def test_empty_fields_list(self):
        assert validate_required({}, []) == []


class TestValidatePhone:
    def test_valid_e164(self):
        assert validate_phone('+919330994400') is True

    def test_valid_without_plus(self):
        assert validate_phone('919330994400') is True

    def test_too_short(self):
        assert validate_phone('+12345') is False

    def test_too_long(self):
        assert validate_phone('+1234567890123456') is False

    def test_letters(self):
        assert validate_phone('+91abcdefgh') is False

    def test_none(self):
        assert validate_phone(None) is False

    def test_empty(self):
        assert validate_phone('') is False

    def test_strips_whitespace(self):
        assert validate_phone(' +919330994400 ') is True


class TestValidateEmail:
    def test_valid(self):
        assert validate_email('user@example.com') is True

    def test_subdomain(self):
        assert validate_email('user@mail.example.co.in') is True

    def test_no_at(self):
        assert validate_email('userexample.com') is False

    def test_no_domain(self):
        assert validate_email('user@') is False

    def test_none(self):
        assert validate_email(None) is False

    def test_empty(self):
        assert validate_email('') is False


class TestSanitizeString:
    def test_basic(self):
        assert sanitize_string('  hello  ') == 'hello'

    def test_truncate(self):
        assert len(sanitize_string('a' * 2000, max_length=100)) == 100

    def test_non_string(self):
        assert sanitize_string(123) == ''


class TestSanitizeHtml:
    def test_strips_script(self):
        assert 'script' not in sanitize_html('<script>alert("xss")</script>hello')
        assert 'hello' in sanitize_html('<script>alert("xss")</script>hello')

    def test_strips_tags(self):
        assert sanitize_html('<b>bold</b>') == 'bold'

    def test_truncates(self):
        assert len(sanitize_html('a' * 2000, max_length=50)) == 50

    def test_non_string(self):
        assert sanitize_html(None) == ''

    def test_entities(self):
        assert '&' in sanitize_html('&amp;')


class TestSanitizeDict:
    def test_sanitizes_specified_fields(self):
        data = {'name': '<b>Alice</b>', 'phone': '+1234567890'}
        result = sanitize_dict(data, ['name'])
        assert result['name'] == 'Alice'
        assert result['phone'] == '+1234567890'

    def test_leaves_non_string_fields(self):
        data = {'count': 42, 'name': '<i>test</i>'}
        result = sanitize_dict(data, ['count', 'name'])
        assert result['count'] == 42
        assert result['name'] == 'test'

    def test_original_unchanged(self):
        data = {'name': '<b>Alice</b>'}
        result = sanitize_dict(data, ['name'])
        assert data['name'] == '<b>Alice</b>'
        assert result['name'] == 'Alice'
