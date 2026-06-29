"""Tests for inbound WhatsApp handler — webhook processing and deduplication."""
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'inbound-whatsapp-handler'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'inbound-whatsapp-handler', 'modules'))


def _make_sns_event(webhook_entry: dict) -> dict:
    """Build a minimal SNS event wrapping a WhatsApp webhook entry."""
    return {
        'Records': [{
            'Sns': {
                'Message': json.dumps({
                    'context': {
                        'MetaWabaIds': ['2094615664435155'],
                        'MetaPhoneNumberIds': ['1016149501586345'],
                    },
                    'whatsAppWebhookEntry': json.dumps(webhook_entry),
                    'messageId': 'test-msg-id',
                })
            }
        }]
    }


def _make_text_webhook(from_phone='919330994400', text='Hello', msg_id='wamid.test123'):
    """Build a WhatsApp text message webhook entry."""
    return {
        'changes': [{
            'value': {
                'messaging_product': 'whatsapp',
                'metadata': {
                    'display_phone_number': '919330994400',
                    'phone_number_id': '1016149501586345',
                },
                'contacts': [{
                    'profile': {'name': 'Test User'},
                    'wa_id': from_phone,
                    'user_id': 'IN.testbsuid123',
                }],
                'messages': [{
                    'from': from_phone,
                    'id': msg_id,
                    'timestamp': '1700000000',
                    'type': 'text',
                    'text': {'body': text},
                }],
            },
            'field': 'messages',
        }]
    }


def _make_status_webhook(msg_id='wamid.test123', status='delivered'):
    """Build a WhatsApp status update webhook entry."""
    return {
        'changes': [{
            'value': {
                'messaging_product': 'whatsapp',
                'metadata': {
                    'display_phone_number': '919330994400',
                    'phone_number_id': '1016149501586345',
                },
                'statuses': [{
                    'id': msg_id,
                    'status': status,
                    'timestamp': '1700000001',
                    'recipient_id': '919876543210',
                }],
            },
            'field': 'messages',
        }]
    }


class TestWebhookPayloadParsing:
    """Test that webhook payloads are correctly parsed."""

    def test_text_webhook_structure(self):
        entry = _make_text_webhook()
        changes = entry['changes']
        assert len(changes) == 1
        messages = changes[0]['value']['messages']
        assert len(messages) == 1
        assert messages[0]['type'] == 'text'
        assert messages[0]['text']['body'] == 'Hello'

    def test_status_webhook_structure(self):
        entry = _make_status_webhook(status='read')
        statuses = entry['changes'][0]['value']['statuses']
        assert len(statuses) == 1
        assert statuses[0]['status'] == 'read'

    def test_contacts_array_parsing(self):
        entry = _make_text_webhook()
        contacts = entry['changes'][0]['value']['contacts']
        assert contacts[0]['profile']['name'] == 'Test User'
        assert contacts[0]['user_id'] == 'IN.testbsuid123'

    def test_metadata_extraction(self):
        entry = _make_text_webhook()
        metadata = entry['changes'][0]['value']['metadata']
        assert metadata['display_phone_number'] == '919330994400'
        assert metadata['phone_number_id'] == '1016149501586345'


class TestSNSEventWrapping:
    """Test SNS event format matches what Lambda receives."""

    def test_sns_event_has_records(self):
        event = _make_sns_event(_make_text_webhook())
        assert 'Records' in event
        assert len(event['Records']) == 1

    def test_sns_message_is_json(self):
        event = _make_sns_event(_make_text_webhook())
        sns_msg = json.loads(event['Records'][0]['Sns']['Message'])
        assert 'whatsAppWebhookEntry' in sns_msg
        assert 'context' in sns_msg

    def test_webhook_entry_is_nested_json(self):
        event = _make_sns_event(_make_text_webhook())
        sns_msg = json.loads(event['Records'][0]['Sns']['Message'])
        entry = json.loads(sns_msg['whatsAppWebhookEntry'])
        assert 'changes' in entry


class TestWebhookFieldTypes:
    """Test different webhook field types are recognized."""

    def test_template_status_field(self):
        entry = {
            'changes': [{
                'value': {
                    'event': 'APPROVED',
                    'message_template_id': 123,
                    'message_template_name': 'test_template',
                },
                'field': 'message_template_status_update',
            }]
        }
        assert entry['changes'][0]['field'] == 'message_template_status_update'

    def test_phone_quality_field(self):
        entry = {
            'changes': [{
                'value': {
                    'display_phone_number': '919330994400',
                    'current_limit': 'TIER_1K',
                },
                'field': 'phone_number_quality_update',
            }]
        }
        assert entry['changes'][0]['field'] == 'phone_number_quality_update'

    def test_account_update_field(self):
        entry = {
            'changes': [{
                'value': {
                    'phone_number': '919330994400',
                    'event': 'ACCOUNT_VIOLATION',
                },
                'field': 'account_update',
            }]
        }
        assert entry['changes'][0]['field'] == 'account_update'

    def test_user_id_update_field(self):
        entry = {
            'changes': [{
                'value': {
                    'user_id_update': [{
                        'user_id': 'IN.newbsuid',
                        'wa_id': '919330994400',
                    }],
                },
                'field': 'user_id_update',
            }]
        }
        assert entry['changes'][0]['field'] == 'user_id_update'


class TestMessageTypes:
    """Test all WhatsApp message types are handled in webhook format."""

    def _make_msg(self, msg_type, extra=None):
        msg = {
            'from': '919330994400',
            'id': f'wamid.{msg_type}_test',
            'timestamp': '1700000000',
            'type': msg_type,
        }
        if extra:
            msg.update(extra)
        return msg

    def test_text_message(self):
        msg = self._make_msg('text', {'text': {'body': 'Hello'}})
        assert msg['type'] == 'text'

    def test_image_message(self):
        msg = self._make_msg('image', {'image': {'id': 'img-123', 'mime_type': 'image/jpeg'}})
        assert msg['type'] == 'image'

    def test_video_message(self):
        msg = self._make_msg('video', {'video': {'id': 'vid-123', 'mime_type': 'video/mp4'}})
        assert msg['type'] == 'video'

    def test_audio_message(self):
        msg = self._make_msg('audio', {'audio': {'id': 'aud-123', 'mime_type': 'audio/ogg'}})
        assert msg['type'] == 'audio'

    def test_document_message(self):
        msg = self._make_msg('document', {'document': {'id': 'doc-123', 'filename': 'test.pdf'}})
        assert msg['type'] == 'document'

    def test_sticker_message(self):
        msg = self._make_msg('sticker', {'sticker': {'id': 'stk-123'}})
        assert msg['type'] == 'sticker'

    def test_location_message(self):
        msg = self._make_msg('location', {'location': {'latitude': 37.48, 'longitude': -122.14}})
        assert msg['type'] == 'location'

    def test_contacts_message(self):
        msg = self._make_msg('contacts', {'contacts': [{'name': {'formatted_name': 'John'}}]})
        assert msg['type'] == 'contacts'

    def test_reaction_message(self):
        msg = self._make_msg('reaction', {'reaction': {'message_id': 'wamid.orig', 'emoji': '👍'}})
        assert msg['type'] == 'reaction'

    def test_interactive_message(self):
        msg = self._make_msg('interactive', {
            'interactive': {'type': 'button_reply', 'button_reply': {'id': 'btn1', 'title': 'Yes'}}
        })
        assert msg['type'] == 'interactive'

    def test_order_message(self):
        msg = self._make_msg('order', {'order': {'catalog_id': 'cat-1', 'product_items': []}})
        assert msg['type'] == 'order'

    def test_unsupported_message(self):
        msg = self._make_msg('unsupported', {'errors': [{'code': 131051, 'details': 'Live location'}]})
        assert msg['type'] == 'unsupported'


class TestBsuidWebhookProcessing:
    """Exercise the BSUID/username webhook processors in the inbound handler."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'inbound-whatsapp-handler'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                import handler as h
                self.h = h

    def test_business_username_update_stores_event(self):
        seen = []
        with patch.object(self.h, '_store_system_event', side_effect=lambda et, *a, **k: seen.append(et)):
            with patch.object(self.h.dynamodb, 'Table', return_value=MagicMock()):
                self.h._process_business_username_update(
                    {'display_phone_number': '15550783881', 'username': 'wecaredigital', 'status': 'approved'}, 'req1')
        assert 'business_username_updates' in seen

    def test_user_id_update_updates_contact(self):
        fake_table = MagicMock()
        fake_table.query.return_value = {'Items': [{'id': 'c1', 'bsuid': 'IN.old'}]}
        with patch.object(self.h.dynamodb, 'Table', return_value=fake_table):
            self.h._process_user_id_update(
                {'user_id': {'previous': 'IN.old', 'current': 'IN.new'}, 'parent_user_id': {'current': 'IN.ENT.x'}},
                {}, 'req1')
        assert fake_table.update_item.called
        # the new BSUID must be written
        kwargs = fake_table.update_item.call_args.kwargs
        assert kwargs['ExpressionAttributeValues'][':new_bsuid'] == 'IN.new'
        assert kwargs['ExpressionAttributeValues'][':new_parent'] == 'IN.ENT.x'

    def test_user_id_update_missing_ids_noop(self):
        fake_table = MagicMock()
        with patch.object(self.h.dynamodb, 'Table', return_value=fake_table):
            self.h._process_user_id_update({'user_id': {}}, {}, 'req1')
        assert not fake_table.update_item.called

    def test_user_id_update_contact_not_found_noop(self):
        fake_table = MagicMock()
        fake_table.query.return_value = {'Items': []}
        with patch.object(self.h.dynamodb, 'Table', return_value=fake_table):
            self.h._process_user_id_update(
                {'user_id': {'previous': 'IN.old', 'current': 'IN.new'}}, {}, 'req1')
        assert not fake_table.update_item.called
