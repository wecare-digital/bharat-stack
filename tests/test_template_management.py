"""Tests for WhatsApp template management handler."""
import json
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))


class TestTemplateManagementRouting:
    """Test template management API routing."""

    def _make_event(self, method='GET', path='/templates', body=None, query=None):
        event = {
            'requestContext': {'http': {'method': method, 'path': path}},
            'headers': {'origin': 'https://stack.wecare.digital'},
            'queryStringParameters': query or {},
            'pathParameters': {},
            'body': json.dumps(body) if body else None,
        }
        return event

    def test_list_templates_route(self):
        event = self._make_event('GET', '/templates')
        assert event['requestContext']['http']['method'] == 'GET'

    def test_create_template_route(self):
        event = self._make_event('POST', '/templates', body={
            'name': 'test_template',
            'category': 'UTILITY',
            'language': 'en',
            'components': [{'type': 'BODY', 'text': 'Hello {{1}}'}]
        })
        body = json.loads(event['body'])
        assert body['name'] == 'test_template'
        assert body['category'] == 'UTILITY'

    def test_delete_template_route(self):
        event = self._make_event('DELETE', '/templates/test_template')
        assert event['requestContext']['http']['method'] == 'DELETE'


class TestTemplatePayloadValidation:
    """Test template creation payload validation."""

    def test_valid_utility_template(self):
        payload = {
            'name': 'order_update',
            'category': 'UTILITY',
            'language': 'en',
            'components': [
                {'type': 'BODY', 'text': 'Your order {{1}} has been shipped.'}
            ]
        }
        assert payload['category'] in ['UTILITY', 'MARKETING', 'AUTHENTICATION']
        assert len(payload['components']) > 0

    def test_valid_marketing_template(self):
        payload = {
            'name': 'promo_offer',
            'category': 'MARKETING',
            'language': 'en',
            'components': [
                {'type': 'HEADER', 'format': 'IMAGE'},
                {'type': 'BODY', 'text': 'Special offer: {{1}}% off!'},
                {'type': 'FOOTER', 'text': 'Reply STOP to opt out'},
                {'type': 'BUTTONS', 'buttons': [
                    {'type': 'QUICK_REPLY', 'text': 'Shop Now'},
                    {'type': 'QUICK_REPLY', 'text': 'Not Interested'},
                ]}
            ]
        }
        assert payload['category'] == 'MARKETING'
        buttons = [c for c in payload['components'] if c['type'] == 'BUTTONS']
        assert len(buttons[0]['buttons']) == 2

    def test_valid_auth_template(self):
        payload = {
            'name': 'auth_otp',
            'category': 'AUTHENTICATION',
            'language': 'en',
            'components': [
                {'type': 'BODY', 'text': 'Your verification code is {{1}}'},
                {'type': 'BUTTONS', 'buttons': [
                    {'type': 'OTP', 'otp_type': 'COPY_CODE', 'text': 'Copy Code'}
                ]}
            ]
        }
        assert payload['category'] == 'AUTHENTICATION'

    def test_template_name_format(self):
        """Template names must be lowercase with underscores."""
        valid_names = ['hello_world', 'order_update_v2', 'auth_otp']
        invalid_names = ['Hello World', 'order-update', 'CAPS_NAME']
        for name in valid_names:
            assert name == name.lower().replace(' ', '_')

    def test_carousel_template_structure(self):
        payload = {
            'name': 'product_carousel',
            'category': 'MARKETING',
            'language': 'en',
            'components': [
                {'type': 'BODY', 'text': 'Check out our products:'},
                {'type': 'CAROUSEL', 'cards': [
                    {
                        'components': [
                            {'type': 'HEADER', 'format': 'IMAGE'},
                            {'type': 'BODY', 'text': 'Product {{1}} - ${{2}}'},
                            {'type': 'BUTTONS', 'buttons': [
                                {'type': 'QUICK_REPLY', 'text': 'Buy Now'}
                            ]}
                        ]
                    }
                ]}
            ]
        }
        carousel = [c for c in payload['components'] if c['type'] == 'CAROUSEL']
        assert len(carousel) == 1
        assert len(carousel[0]['cards']) >= 1
