"""Tests for lambda_utils.response module."""
import json
import pytest
from lambda_utils.response import (
    cors_headers, cors_response, options_response,
    extract_origin, error_response, ALLOWED_ORIGINS,
)


class TestCorsHeaders:
    def test_allowed_origin_reflected(self):
        h = cors_headers('https://stack.wecare.digital')
        assert h['Access-Control-Allow-Origin'] == 'https://stack.wecare.digital'

    def test_unknown_origin_falls_back(self):
        h = cors_headers('https://evil.com')
        assert h['Access-Control-Allow-Origin'] == ALLOWED_ORIGINS[0]

    def test_none_origin_falls_back(self):
        h = cors_headers(None)
        assert h['Access-Control-Allow-Origin'] == ALLOWED_ORIGINS[0]

    def test_localhost_allowed(self):
        h = cors_headers('http://localhost:3000')
        assert h['Access-Control-Allow-Origin'] == 'http://localhost:3000'

    def test_default_methods(self):
        h = cors_headers()
        assert 'GET' in h['Access-Control-Allow-Methods']
        assert 'POST' in h['Access-Control-Allow-Methods']

    def test_custom_methods(self):
        h = cors_headers(methods='GET,POST')
        assert h['Access-Control-Allow-Methods'] == 'GET,POST'

    def test_extra_headers(self):
        h = cors_headers(extra_headers='X-Custom')
        assert h['Access-Control-Allow-Headers'] == 'X-Custom'


class TestCorsResponse:
    def test_status_code(self):
        r = cors_response(200, {'ok': True})
        assert r['statusCode'] == 200

    def test_body_is_json(self):
        r = cors_response(200, {'msg': 'hello'})
        body = json.loads(r['body'])
        assert body['msg'] == 'hello'

    def test_error_status(self):
        r = cors_response(500, {'error': 'fail'})
        assert r['statusCode'] == 500

    def test_origin_passed_through(self):
        r = cors_response(200, {}, 'https://stack.wecare.digital')
        assert r['headers']['Access-Control-Allow-Origin'] == 'https://stack.wecare.digital'

    def test_serializes_datetime(self):
        from datetime import datetime
        r = cors_response(200, {'ts': datetime(2025, 1, 1)})
        body = json.loads(r['body'])
        assert '2025' in body['ts']


class TestOptionsResponse:
    def test_returns_200(self):
        r = options_response()
        assert r['statusCode'] == 200

    def test_with_origin(self):
        r = options_response('https://wecare.digital')
        assert r['headers']['Access-Control-Allow-Origin'] == 'https://wecare.digital'


class TestExtractOrigin:
    def test_lowercase_header(self):
        event = {'headers': {'origin': 'https://stack.wecare.digital'}}
        assert extract_origin(event) == 'https://stack.wecare.digital'

    def test_capitalized_header(self):
        event = {'headers': {'Origin': 'https://wecare.digital'}}
        assert extract_origin(event) == 'https://wecare.digital'

    def test_missing_headers(self):
        assert extract_origin({}) == ''

    def test_no_origin(self):
        assert extract_origin({'headers': {}}) == ''


class TestErrorResponse:
    def test_error_shape(self):
        r = error_response(400, 'Bad request')
        body = json.loads(r['body'])
        assert body['error'] == 'Bad request'
        assert body['statusCode'] == 400

    def test_with_details(self):
        r = error_response(422, 'Validation', details={'fields': ['name']})
        body = json.loads(r['body'])
        assert body['details']['fields'] == ['name']

    def test_without_details(self):
        r = error_response(500, 'Server error')
        body = json.loads(r['body'])
        assert 'details' not in body
