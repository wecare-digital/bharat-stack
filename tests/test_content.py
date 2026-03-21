"""Tests for inbound WhatsApp content extraction module."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'inbound-whatsapp-handler'))

from modules.content import extract_content, extract_unsupported_content


class TestExtractContent:
    def test_text(self):
        msg = {'text': {'body': 'Hello world'}}
        assert extract_content(msg, 'text') == 'Hello world'

    def test_image_with_caption(self):
        msg = {'image': {'caption': 'My photo'}}
        assert extract_content(msg, 'image') == 'My photo'

    def test_image_no_caption(self):
        msg = {'image': {}}
        assert extract_content(msg, 'image') == '[Image]'

    def test_audio(self):
        assert extract_content({}, 'audio') == '[Audio]'

    def test_document(self):
        msg = {'document': {'filename': 'report.pdf'}}
        assert extract_content(msg, 'document') == 'report.pdf'

    def test_location(self):
        msg = {'location': {'latitude': 22.5, 'longitude': 88.3}}
        assert 'Location' in extract_content(msg, 'location')

    def test_sticker(self):
        assert extract_content({}, 'sticker') == '[Sticker]'

    def test_reaction(self):
        msg = {'reaction': {'emoji': '👍'}}
        assert extract_content(msg, 'reaction') == '👍'

    def test_interactive_button_reply(self):
        msg = {'interactive': {'type': 'button_reply', 'button_reply': {'id': 'opt_yes', 'title': 'Yes'}}}
        assert extract_content(msg, 'interactive') == 'opt_yes'

    def test_interactive_list_reply(self):
        msg = {'interactive': {'type': 'list_reply', 'list_reply': {'id': 'custom', 'title': 'My Choice'}}}
        assert extract_content(msg, 'interactive') == 'My Choice'

    def test_button(self):
        msg = {'button': {'text': 'Quick Reply'}}
        assert extract_content(msg, 'button') == 'Quick Reply'

    def test_order(self):
        assert extract_content({}, 'order') == '[Order]'

    def test_system(self):
        msg = {'system': {'body': 'Group created'}}
        assert extract_content(msg, 'system') == 'Group created'

    def test_request_welcome(self):
        assert 'conversation' in extract_content({}, 'request_welcome').lower()

    def test_poll(self):
        msg = {'poll': {'question': 'Favorite color?'}}
        assert 'Favorite color' in extract_content(msg, 'poll')

    def test_edit_with_text(self):
        msg = {'text': {'body': 'new text'}, 'context': {'id': 'wamid.xxx'}}
        result = extract_content(msg, 'edit')
        assert result == '[Edited] new text'

    def test_edit_no_text(self):
        msg = {'context': {'id': 'wamid.abc123'}}
        result = extract_content(msg, 'edit')
        assert result == '[Message edited: wamid.abc123]'

    def test_edit_empty(self):
        result = extract_content({}, 'edit')
        assert result == '[Message edited]'

    def test_revoke(self):
        result = extract_content({}, 'revoke')
        assert result == '[Message deleted by sender]'

    def test_unknown_type(self):
        result = extract_content({}, 'some_new_type')
        assert result == '[some_new_type]'


class TestExtractUnsupported:
    def test_with_error_details(self):
        msg = {'errors': [{'code': 131051, 'details': 'Live location'}]}
        assert 'Live location' in extract_unsupported_content(msg)

    def test_with_referral(self):
        msg = {'referral': {'source_type': 'ad'}}
        assert 'ad' in extract_unsupported_content(msg)

    def test_with_text_body(self):
        msg = {'text': {'body': 'hidden text'}}
        assert extract_unsupported_content(msg) == 'hidden text'

    def test_fallback(self):
        assert 'not supported' in extract_unsupported_content({})
