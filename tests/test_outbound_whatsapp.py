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


def _mk_urlopen(response_dict):
    """Build a urlopen context-manager mock returning the given JSON."""
    cm = MagicMock()
    cm.read.return_value = json.dumps(response_dict).encode()
    ctx = MagicMock()
    ctx.__enter__.return_value = cm
    ctx.__exit__.return_value = False
    return ctx


class TestOutboundAutoThumbReaction:
    """Auto 👍 reaction on every outbound message/template via the _send_direct_api choke point."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'outbound-whatsapp'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'SEND_MODE': 'LIVE'}):
            with patch('boto3.resource'), patch('boto3.client'):
                import handler as h
                self.h = h
                # Seed the token cache so _send_direct_api skips Secrets Manager.
                h._direct_api_cache['token'] = 'tok'
                h._direct_api_cache['app_secret'] = ''
                # Reset the auto-thumb config cache between tests.
                h._auto_thumb_cache['value'] = None
                h._auto_thumb_cache['ts'] = 0.0

    PHONE = 'phone-number-id-waba1-direct-1016149501586345'

    def test_reaction_triggered_for_text(self):
        with patch.object(self.h, '_auto_thumb_enabled', return_value=True):
            with patch.object(self.h, '_post_reaction_direct') as react:
                with patch('urllib.request.urlopen', return_value=_mk_urlopen({'messages': [{'id': 'wamid.OUT'}], 'contacts': [{'wa_id': '9199'}]})):
                    resp = self.h._send_direct_api(self.PHONE, json.dumps({'type': 'text', 'to': '919812345678', 'text': {'body': 'hi'}}))
                assert resp['messageId'] == 'wamid.OUT'
                react.assert_called_once()
                args = react.call_args.args
                assert args[0] == '1016149501586345'   # meta_phone_id (same WABA)
                assert args[3] == '919812345678'        # to
                assert args[4] == 'wamid.OUT'           # message_id

    def test_reaction_triggered_for_template(self):
        with patch.object(self.h, '_auto_thumb_enabled', return_value=True):
            with patch.object(self.h, '_post_reaction_direct') as react:
                with patch('urllib.request.urlopen', return_value=_mk_urlopen({'messages': [{'id': 'wamid.TMPL'}]})):
                    self.h._send_direct_api(self.PHONE, json.dumps({'type': 'template', 'to': '919812345678', 'template': {'name': 'wd_menu'}}))
                react.assert_called_once()
                assert react.call_args.args[4] == 'wamid.TMPL'

    def test_no_reaction_for_reaction_payload(self):
        with patch.object(self.h, '_auto_thumb_enabled', return_value=True):
            with patch.object(self.h, '_post_reaction_direct') as react:
                with patch('urllib.request.urlopen', return_value=_mk_urlopen({'messages': [{'id': 'wamid.R'}]})):
                    self.h._send_direct_api(self.PHONE, json.dumps({'type': 'reaction', 'to': '919', 'reaction': {'message_id': 'x', 'emoji': '\U0001F44D'}}))
                react.assert_not_called()

    def test_no_reaction_when_send_returns_no_id(self):
        with patch.object(self.h, '_auto_thumb_enabled', return_value=True):
            with patch.object(self.h, '_post_reaction_direct') as react:
                with patch('urllib.request.urlopen', return_value=_mk_urlopen({'messages': [{}]})):
                    self.h._send_direct_api(self.PHONE, json.dumps({'type': 'text', 'to': '919', 'text': {'body': 'hi'}}))
                react.assert_not_called()

    def test_disabled_toggle_skips(self):
        with patch.object(self.h, '_auto_thumb_enabled', return_value=False):
            with patch.object(self.h, '_post_reaction_direct') as react:
                with patch('urllib.request.urlopen', return_value=_mk_urlopen({'messages': [{'id': 'wamid.O'}]})):
                    self.h._send_direct_api(self.PHONE, json.dumps({'type': 'text', 'to': '919', 'text': {'body': 'hi'}}))
                react.assert_not_called()

    def test_post_reaction_direct_builds_payload(self):
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured['url'] = req.full_url
            captured['data'] = req.data
            return _mk_urlopen({})

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            self.h._post_reaction_direct('1016149501586345', 'tok', '', '919812345678', 'wamid.X')
        body = json.loads(captured['data'].decode())
        assert body['type'] == 'reaction'
        assert body['reaction']['message_id'] == 'wamid.X'
        assert body['reaction']['emoji'] == '\U0001F44D'
        assert body['to'] == '919812345678'
        assert '/1016149501586345/messages' in captured['url']

    def test_post_reaction_direct_skips_empty_args(self):
        with patch('urllib.request.urlopen') as uo:
            self.h._post_reaction_direct('1016149501586345', 'tok', '', '919', '')
            uo.assert_not_called()

    def test_auto_thumb_enabled_reads_config_false(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {'Item': {'configValue': 'false'}}
        with patch.object(self.h.dynamodb, 'Table', return_value=mock_table):
            assert self.h._auto_thumb_enabled() is False

    def test_auto_thumb_enabled_caches_within_ttl(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {'Item': {'configValue': 'true'}}
        with patch.object(self.h.dynamodb, 'Table', return_value=mock_table) as t:
            assert self.h._auto_thumb_enabled() is True
            assert self.h._auto_thumb_enabled() is True
            t.assert_called_once()  # second call served from cache

    def test_auto_thumb_enabled_defaults_when_unset(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}  # no Item → fall back to env default (True)
        with patch.object(self.h.dynamodb, 'Table', return_value=mock_table):
            assert self.h._auto_thumb_enabled() is True
