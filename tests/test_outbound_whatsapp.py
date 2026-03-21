"""Tests for outbound WhatsApp Lambda handler — message payload building."""
import json
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'outbound-whatsapp'))


class TestBuildMessagePayload:
    """Test _build_message_payload for all message types."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'outbound-whatsapp'))
        """Mock AWS clients before importing handler."""
        with patch.dict(os.environ, {
            'AWS_REGION': 'us-east-1',
            'SEND_MODE': 'DRY_RUN',
        }):
            with patch('boto3.resource'), \
                 patch('boto3.client'):
                from handler import _build_message_payload, _normalize_phone_number
                self.build = _build_message_payload
                self.normalize = _normalize_phone_number

    def test_text_message(self):
        payload = self.build('+919330994400', 'Hello world', None, None, False, None, [])
        assert payload['type'] == 'text'
        assert payload['text']['body'] == 'Hello world'
        assert payload['messaging_product'] == 'whatsapp'

    def test_text_with_url_preview(self):
        payload = self.build('+919330994400', 'Check https://example.com', None, None, False, None, [])
        assert payload['text']['preview_url'] is True

    def test_text_without_url_preview(self):
        payload = self.build('+919330994400', 'No links here', None, None, False, None, [])
        assert payload['text']['preview_url'] is False

    def test_image_message(self):
        payload = self.build('+919330994400', 'Caption', 'image/jpeg', 'media-123', False, None, [])
        assert payload['type'] == 'image'
        assert payload['image']['id'] == 'media-123'
        assert payload['image']['caption'] == 'Caption'

    def test_video_message(self):
        payload = self.build('+919330994400', '', 'video/mp4', 'media-456', False, None, [])
        assert payload['type'] == 'video'
        assert payload['video']['id'] == 'media-456'

    def test_audio_message(self):
        payload = self.build('+919330994400', '', 'audio/ogg', 'media-789', False, None, [])
        assert payload['type'] == 'audio'

    def test_document_message_with_filename(self):
        payload = self.build('+919330994400', '', 'document/pdf', 'media-doc', False, None, [], filename='report.pdf')
        assert payload['type'] == 'document'
        assert payload['document']['filename'] == 'report.pdf'

    def test_sticker_message(self):
        payload = self.build('+919330994400', '', 'sticker', 'sticker-id', False, None, [])
        assert payload['type'] == 'sticker'

    def test_invalid_media_type_fallback(self):
        payload = self.build('+919330994400', '', 'application/zip', 'media-zip', False, None, [])
        assert payload['type'] == 'document'

    def test_template_message_basic(self):
        payload = self.build('+919330994400', '', None, None, True, 'hello_world', ['en'])
        assert payload['type'] == 'template'
        assert payload['template']['name'] == 'hello_world'
        assert payload['template']['language']['code'] == 'en'

    def test_template_with_params(self):
        payload = self.build('+919330994400', '', None, None, True, 'order_update', ['en', 'John', 'ORD-123'])
        assert payload['type'] == 'template'
        components = payload['template']['components']
        body_comp = [c for c in components if c['type'] == 'body']
        assert len(body_comp) == 1
        assert len(body_comp[0]['parameters']) == 2

    def test_otp_template_copy_code(self):
        payload = self.build('+919330994400', '', None, None, True, 'auth_otp', ['en', '123456'],
                           is_otp_template=True, otp_code='123456', otp_button_type='copy_code')
        assert payload['type'] == 'template'
        components = payload['template']['components']
        btn = [c for c in components if c['type'] == 'button']
        assert len(btn) == 1
        assert btn[0]['sub_type'] == 'copy_code'

    def test_otp_template_url(self):
        payload = self.build('+919330994400', '', None, None, True, 'auth_otp', ['en'],
                           is_otp_template=True, otp_code='654321', otp_button_type='url')
        btn = [c for c in payload['template']['components'] if c['type'] == 'button']
        assert btn[0]['sub_type'] == 'url'

    def test_contact_message(self):
        contact_data = json.dumps({
            '_type': 'contacts',
            'contacts': [{'name': {'formatted_name': 'John Doe'}, 'phones': [{'phone': '+1234567890'}]}]
        })
        payload = self.build('+919330994400', contact_data, None, None, False, None, [])
        assert payload['type'] == 'contacts'
        assert len(payload['contacts']) == 1

    def test_location_message(self):
        loc_data = json.dumps({
            '_type': 'location',
            'latitude': 37.4847,
            'longitude': -122.1477,
            'name': 'Meta HQ',
            'address': '1 Hacker Way'
        })
        payload = self.build('+919330994400', loc_data, None, None, False, None, [])
        assert payload['type'] == 'location'
        assert payload['location']['name'] == 'Meta HQ'

    def test_location_request_message(self):
        req_data = json.dumps({
            '_type': 'location_request',
            'body': 'Share your delivery location'
        })
        payload = self.build('+919330994400', req_data, None, None, False, None, [])
        assert payload['type'] == 'interactive'
        assert payload['interactive']['type'] == 'location_request_message'

    def test_address_message(self):
        addr_data = json.dumps({
            '_type': 'address',
            'body': 'Provide your shipping address',
            'parameters': {'country': 'IN'}
        })
        payload = self.build('+919330994400', addr_data, None, None, False, None, [])
        assert payload['type'] == 'interactive'
        assert payload['interactive']['type'] == 'address_message'

    def test_bsuid_recipient(self):
        payload = self.build('', 'Hello', None, None, False, None, [],
                           recipient_bsuid='US.13491208655302741918')
        assert payload.get('recipient') == 'US.13491208655302741918'

    def test_phone_normalization(self):
        normalized = self.normalize('+91 9330-994400')
        assert normalized.isdigit()
        assert '919330994400' in normalized


class TestMetaMessageErrors:
    """Test that error code mapping is complete."""

    def test_error_map_exists(self):
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'SEND_MODE': 'DRY_RUN'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import META_MESSAGE_ERRORS
                assert 131056 in META_MESSAGE_ERRORS  # Pair rate limit
                assert 131047 in META_MESSAGE_ERRORS  # Window
                assert 132001 in META_MESSAGE_ERRORS  # Template not found
                assert 131049 in META_MESSAGE_ERRORS  # Not on WhatsApp

    def test_all_errors_have_required_fields(self):
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'SEND_MODE': 'DRY_RUN'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import META_MESSAGE_ERRORS
                for code, info in META_MESSAGE_ERRORS.items():
                    assert 'msg' in info, f"Error {code} missing 'msg'"
                    assert 'action' in info, f"Error {code} missing 'action'"
                    assert 'retry' in info, f"Error {code} missing 'retry'"
