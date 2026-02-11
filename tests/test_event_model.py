"""
Unit tests for NormalizedEvent dataclass.
Tests serialization, default values, and to_dict filtering.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas'))

from shared.event_model import NormalizedEvent


class TestNormalizedEventDefaults:
    def test_required_fields(self):
        evt = NormalizedEvent(eventType='INBOUND_MESSAGE', eventId='evt-001')
        assert evt.eventType == 'INBOUND_MESSAGE'
        assert evt.eventId == 'evt-001'

    def test_default_strings_empty(self):
        evt = NormalizedEvent(eventType='STATUS_UPDATE', eventId='evt-002')
        assert evt.whatsappMessageId == ''
        assert evt.messageType == ''
        assert evt.content == ''
        assert evt.senderPhone == ''
        assert evt.senderName == ''

    def test_default_numerics_zero(self):
        evt = NormalizedEvent(eventType='STATUS_UPDATE', eventId='evt-003')
        assert evt.fileSize == 0
        assert evt.latitude == 0.0
        assert evt.longitude == 0.0
        assert evt.timestamp == 0

    def test_default_dicts_empty(self):
        evt = NormalizedEvent(eventType='STATUS_UPDATE', eventId='evt-004')
        assert evt.interactiveData == {}
        assert evt.rawPayload == {}


class TestNormalizedEventToDict:
    def test_filters_empty_values(self):
        evt = NormalizedEvent(eventType='INBOUND_MESSAGE', eventId='evt-010', content='Hello')
        d = evt.to_dict()
        assert 'eventType' in d
        assert 'eventId' in d
        assert 'content' in d
        assert 'senderPhone' not in d  # empty string filtered
        assert 'fileSize' not in d  # zero filtered
        assert 'latitude' not in d  # 0.0 filtered

    def test_preserves_populated_fields(self):
        evt = NormalizedEvent(
            eventType='INBOUND_MESSAGE',
            eventId='evt-011',
            whatsappMessageId='wamid.abc',
            messageType='text',
            content='Hello World',
            senderPhone='919876543210',
            senderName='Test User',
            receivingPhone='919330994400',
            awsPhoneNumberId='phone-number-id-5e020cecd221429996f6ae721cc42206',
            timestamp=1700000000
        )
        d = evt.to_dict()
        assert d['whatsappMessageId'] == 'wamid.abc'
        assert d['messageType'] == 'text'
        assert d['senderPhone'] == '919876543210'
        assert d['timestamp'] == 1700000000

    def test_media_fields(self):
        evt = NormalizedEvent(
            eventType='INBOUND_MESSAGE',
            eventId='evt-012',
            mediaId='media123',
            mimeType='image/jpeg',
            s3Key='whatsapp-media/incoming/img.jpg',
            fileSize=102400
        )
        d = evt.to_dict()
        assert d['mediaId'] == 'media123'
        assert d['mimeType'] == 'image/jpeg'
        assert d['fileSize'] == 102400

    def test_location_fields(self):
        evt = NormalizedEvent(
            eventType='INBOUND_MESSAGE',
            eventId='evt-013',
            latitude=22.5726,
            longitude=88.3639,
            locationName='Kolkata'
        )
        d = evt.to_dict()
        assert d['latitude'] == 22.5726
        assert d['longitude'] == 88.3639
        assert d['locationName'] == 'Kolkata'

    def test_status_update_fields(self):
        evt = NormalizedEvent(
            eventType='STATUS_UPDATE',
            eventId='evt-014',
            whatsappMessageId='wamid.out123',
            status='delivered',
            recipientPhone='919876543210'
        )
        d = evt.to_dict()
        assert d['status'] == 'delivered'
        assert d['recipientPhone'] == '919876543210'

    def test_payment_fields(self):
        evt = NormalizedEvent(
            eventType='PAYMENT_STATUS',
            eventId='evt-015',
            paymentStatus='captured',
            referenceId='order-ref-001',
            amount='500.00',
            currency='INR'
        )
        d = evt.to_dict()
        assert d['paymentStatus'] == 'captured'
        assert d['referenceId'] == 'order-ref-001'
        assert d['amount'] == '500.00'
        assert d['currency'] == 'INR'

    def test_template_status_fields(self):
        evt = NormalizedEvent(
            eventType='TEMPLATE_STATUS',
            eventId='evt-016',
            templateName='hello_world',
            newStatus='APPROVED'
        )
        d = evt.to_dict()
        assert d['templateName'] == 'hello_world'
        assert d['newStatus'] == 'APPROVED'

    def test_interactive_fields(self):
        evt = NormalizedEvent(
            eventType='INBOUND_MESSAGE',
            eventId='evt-017',
            messageType='interactive',
            interactiveType='list_reply',
            interactiveData={'list_reply': {'id': 'row_1', 'title': 'Option 1'}}
        )
        d = evt.to_dict()
        assert d['interactiveType'] == 'list_reply'
        assert d['interactiveData']['list_reply']['id'] == 'row_1'

    def test_reaction_fields(self):
        evt = NormalizedEvent(
            eventType='INBOUND_MESSAGE',
            eventId='evt-018',
            messageType='reaction',
            reactionMessageId='wamid.original',
            reactionEmoji='\U0001F44D'
        )
        d = evt.to_dict()
        assert d['reactionMessageId'] == 'wamid.original'
        assert d['reactionEmoji'] == '\U0001F44D'

    def test_raw_payload_preserved(self):
        raw = {'entry': [{'changes': [{'value': {'messages': []}}]}]}
        evt = NormalizedEvent(
            eventType='INBOUND_MESSAGE',
            eventId='evt-019',
            rawPayload=raw
        )
        d = evt.to_dict()
        assert d['rawPayload'] == raw
