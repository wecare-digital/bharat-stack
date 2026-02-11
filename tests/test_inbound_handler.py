"""
Unit tests for inbound WhatsApp handler.
Tests SNS event processing, content extraction, status handling, and idempotency.
Does NOT call AWS APIs (mocked).
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')

# Add lambdas to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas'))


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), 'r') as f:
        return json.load(f)


# Mock all AWS clients before importing handler
mock_dynamodb = MagicMock()
mock_sqs = MagicMock()
mock_social = MagicMock()
mock_s3 = MagicMock()
mock_lambda = MagicMock()

_original_boto3_resource = None
_original_boto3_client = None


def mock_resource(service, **kwargs):
    if service == 'dynamodb':
        return mock_dynamodb
    return MagicMock()


def mock_client(service, **kwargs):
    if service == 'sqs':
        return mock_sqs
    if service == 'socialmessaging':
        return mock_social
    if service == 's3':
        return mock_s3
    if service == 'lambda':
        return mock_lambda
    return MagicMock()


with patch('boto3.resource', side_effect=mock_resource), \
     patch('boto3.client', side_effect=mock_client):
    from inbound_handler.handler import (
        _extract_content, _resolve_phone_id, _ext_from_mime
    )


class TestExtractContent:
    """Test content extraction for all 18 message types."""

    def test_text(self):
        msg = {'type': 'text', 'text': {'body': 'Hello World'}}
        assert _extract_content(msg, 'text') == 'Hello World'

    def test_image_with_caption(self):
        msg = {'type': 'image', 'image': {'caption': 'My photo', 'id': 'media1'}}
        assert _extract_content(msg, 'image') == 'My photo'

    def test_image_no_caption(self):
        msg = {'type': 'image', 'image': {'id': 'media1'}}
        assert _extract_content(msg, 'image') == '[Image]'

    def test_video_with_caption(self):
        msg = {'type': 'video', 'video': {'caption': 'Watch this'}}
        assert _extract_content(msg, 'video') == 'Watch this'

    def test_audio(self):
        msg = {'type': 'audio', 'audio': {'id': 'media1'}}
        assert _extract_content(msg, 'audio') == '[Audio]'

    def test_document(self):
        msg = {'type': 'document', 'document': {'filename': 'report.pdf'}}
        assert _extract_content(msg, 'document') == 'report.pdf'

    def test_sticker(self):
        msg = {'type': 'sticker', 'sticker': {'id': 'media1'}}
        assert _extract_content(msg, 'sticker') == '[Sticker]'

    def test_location(self):
        msg = {'type': 'location', 'location': {'latitude': 22.57, 'longitude': 88.36}}
        result = _extract_content(msg, 'location')
        assert '22.57' in result
        assert '88.36' in result

    def test_contacts(self):
        msg = {'type': 'contacts', 'contacts': [{'name': {'formatted_name': 'Test'}}]}
        assert _extract_content(msg, 'contacts') == '[Contact Card]'

    def test_reaction(self):
        msg = {'type': 'reaction', 'reaction': {'emoji': '👍', 'message_id': 'wamid.123'}}
        assert _extract_content(msg, 'reaction') == '👍'

    def test_interactive_button_reply(self):
        msg = {'type': 'interactive', 'interactive': {'type': 'button_reply', 'button_reply': {'id': 'btn1', 'title': 'Yes'}}}
        assert _extract_content(msg, 'interactive') == 'Yes'

    def test_interactive_list_reply(self):
        msg = {'type': 'interactive', 'interactive': {'type': 'list_reply', 'list_reply': {'id': 'row1', 'title': 'Option A'}}}
        assert _extract_content(msg, 'interactive') == 'Option A'

    def test_interactive_nfm_reply(self):
        msg = {'type': 'interactive', 'interactive': {'type': 'nfm_reply', 'nfm_reply': {'response_json': '{"screen":"done"}'}}}
        result = _extract_content(msg, 'interactive')
        assert 'Flow' in result

    def test_button(self):
        msg = {'type': 'button', 'button': {'text': 'Quick Reply'}}
        assert _extract_content(msg, 'button') == 'Quick Reply'

    def test_order(self):
        msg = {'type': 'order', 'order': {'catalog_id': 'cat1'}}
        assert _extract_content(msg, 'order') == '[Order]'

    def test_system(self):
        msg = {'type': 'system', 'system': {'body': 'Number changed'}}
        assert _extract_content(msg, 'system') == 'Number changed'

    def test_unsupported_with_error(self):
        msg = {'type': 'unsupported', 'errors': [{'title': 'Unsupported type', 'details': 'poll'}]}
        result = _extract_content(msg, 'unsupported')
        assert 'poll' in result

    def test_request_welcome(self):
        msg = {'type': 'request_welcome'}
        assert 'start conversation' in _extract_content(msg, 'request_welcome').lower()

    def test_ephemeral(self):
        msg = {'type': 'ephemeral'}
        assert 'Disappearing' in _extract_content(msg, 'ephemeral')

    def test_unknown_type(self):
        msg = {'type': 'new_future_type'}
        result = _extract_content(msg, 'new_future_type')
        assert 'new_future_type' in result

    def test_referral(self):
        msg = {'type': 'referral', 'referral': {'source_type': 'ad', 'headline': 'Summer Sale'}}
        result = _extract_content(msg, 'referral')
        assert 'Referral' in result
        assert 'ad' in result
        assert 'Summer Sale' in result

    def test_referral_no_headline(self):
        msg = {'type': 'referral', 'referral': {'source_type': 'post'}}
        result = _extract_content(msg, 'referral')
        assert 'Referral' in result
        assert 'post' in result

    def test_ad_click(self):
        msg = {'type': 'ad_click', 'referral': {'source_url': 'https://fb.com/ad/123'}}
        result = _extract_content(msg, 'ad_click')
        assert 'Ad Click' in result

    def test_ad_click_no_url(self):
        msg = {'type': 'ad_click'}
        result = _extract_content(msg, 'ad_click')
        assert result == '[Ad Click]'

    def test_product(self):
        msg = {'type': 'product', 'product': {'catalog_id': 'cat1', 'product_retailer_id': 'sku-001'}}
        result = _extract_content(msg, 'product')
        assert 'Product' in result
        assert 'cat1' in result

    def test_product_inquiry(self):
        msg = {'type': 'product_inquiry', 'product_inquiry': {'catalog_id': 'cat2', 'product_retailer_id': 'sku-002'}}
        result = _extract_content(msg, 'product_inquiry')
        assert 'Product' in result

    def test_poll(self):
        msg = {'type': 'poll', 'poll': {'question': 'What is your favorite color?'}}
        result = _extract_content(msg, 'poll')
        assert 'Poll' in result
        assert 'favorite color' in result

    def test_poll_no_question(self):
        msg = {'type': 'poll', 'poll': {}}
        result = _extract_content(msg, 'poll')
        assert result == '[Poll]'


class TestResolvePhoneId:
    """Test phone number ID resolution from display phone."""

    def test_waba1_phone(self):
        result = _resolve_phone_id('919330994400')
        assert result == os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1',
                                         'phone-number-id-5e020cecd221429996f6ae721cc42206')

    def test_waba2_phone(self):
        result = _resolve_phone_id('919903300044')
        assert result == os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2',
                                         'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c')

    def test_unknown_phone_defaults_to_waba1(self):
        result = _resolve_phone_id('911234567890')
        assert result == os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1',
                                         'phone-number-id-5e020cecd221429996f6ae721cc42206')

    def test_phone_with_plus_prefix(self):
        result = _resolve_phone_id('+919330994400')
        assert 'phone-number-id' in result

    def test_phone_with_spaces(self):
        result = _resolve_phone_id('91 93309 94400')
        assert 'phone-number-id' in result


class TestExtFromMime:
    """Test MIME type to file extension mapping."""

    def test_jpeg(self):
        assert _ext_from_mime('image/jpeg') == '.jpg'

    def test_png(self):
        assert _ext_from_mime('image/png') == '.png'

    def test_mp4(self):
        assert _ext_from_mime('video/mp4') == '.mp4'

    def test_pdf(self):
        assert _ext_from_mime('application/pdf') == '.pdf'

    def test_ogg(self):
        assert _ext_from_mime('audio/ogg') == '.ogg'

    def test_webp(self):
        assert _ext_from_mime('image/webp') == '.webp'

    def test_unknown(self):
        assert _ext_from_mime('application/unknown') == '.bin'

    def test_docx(self):
        assert _ext_from_mime('application/vnd.openxmlformats-officedocument.wordprocessingml.document') == '.docx'


class TestSNSEventProcessing:
    """Test full SNS event parsing from fixtures."""

    def test_inbound_text_parses(self):
        event = load_fixture('sns_inbound_text.json')
        record = event['Records'][0]
        sns_msg = json.loads(record['Sns']['Message'])
        entry = json.loads(sns_msg['whatsAppWebhookEntry'])
        messages = entry['changes'][0]['value']['messages']
        assert len(messages) == 1
        assert messages[0]['type'] == 'text'

    def test_inbound_media_parses(self):
        event = load_fixture('sns_inbound_media.json')
        record = event['Records'][0]
        sns_msg = json.loads(record['Sns']['Message'])
        entry = json.loads(sns_msg['whatsAppWebhookEntry'])
        msg = entry['changes'][0]['value']['messages'][0]
        assert msg['type'] == 'image'
        assert msg['image']['id'] == 'media123abc'

    def test_status_delivered_parses(self):
        event = load_fixture('sns_status_delivered.json')
        record = event['Records'][0]
        sns_msg = json.loads(record['Sns']['Message'])
        entry = json.loads(sns_msg['whatsAppWebhookEntry'])
        statuses = entry['changes'][0]['value']['statuses']
        assert statuses[0]['status'] == 'delivered'

    def test_payment_captured_parses(self):
        event = load_fixture('sns_payment_captured.json')
        record = event['Records'][0]
        sns_msg = json.loads(record['Sns']['Message'])
        entry = json.loads(sns_msg['whatsAppWebhookEntry'])
        status = entry['changes'][0]['value']['statuses'][0]
        assert status['type'] == 'payment'
        assert status['payment']['reference_id'] == 'order-ref-001'

    def test_template_status_parses(self):
        event = load_fixture('sns_template_status.json')
        record = event['Records'][0]
        sns_msg = json.loads(record['Sns']['Message'])
        entry = json.loads(sns_msg['whatsAppWebhookEntry'])
        change = entry['changes'][0]
        assert change['field'] == 'message_template_status_update'
        assert change['value']['event'] == 'APPROVED'
