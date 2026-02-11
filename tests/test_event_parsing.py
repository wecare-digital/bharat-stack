"""
Unit tests for SNS event payload parsing.
Tests the AWS EUM Social envelope format and WhatsApp webhook entry extraction.
"""
import json
import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), 'r') as f:
        return json.load(f)


def parse_sns_envelope(record):
    """Parse AWS EUM Social SNS envelope."""
    sns_message = json.loads(record.get('Sns', {}).get('Message', '{}'))
    context = sns_message.get('context', {})
    webhook_entry = json.loads(sns_message.get('whatsAppWebhookEntry', '{}'))
    return sns_message, context, webhook_entry


class TestSNSEnvelopeParsing:
    def test_inbound_text_envelope(self):
        event = load_fixture('sns_inbound_text.json')
        sns_msg, ctx, entry = parse_sns_envelope(event['Records'][0])
        assert ctx['MetaWabaIds'] == ['1912405516040025']
        assert ctx['MetaPhoneNumberIds'] == ['960395407161423']
        assert sns_msg['aws_account_id'] == '775261844268'
        assert 'changes' in entry

    def test_inbound_text_message(self):
        event = load_fixture('sns_inbound_text.json')
        _, _, entry = parse_sns_envelope(event['Records'][0])
        value = entry['changes'][0]['value']
        msgs = value['messages']
        assert len(msgs) == 1
        assert msgs[0]['type'] == 'text'
        assert msgs[0]['text']['body'] == 'Hello from test'
        assert msgs[0]['from'] == '919876543210'
        assert msgs[0]['id'] == 'wamid.test123'

    def test_inbound_text_contacts(self):
        event = load_fixture('sns_inbound_text.json')
        _, _, entry = parse_sns_envelope(event['Records'][0])
        contacts = entry['changes'][0]['value']['contacts']
        assert contacts[0]['profile']['name'] == 'Test User'
        assert contacts[0]['wa_id'] == '919876543210'

    def test_inbound_media_message(self):
        event = load_fixture('sns_inbound_media.json')
        _, _, entry = parse_sns_envelope(event['Records'][0])
        msg = entry['changes'][0]['value']['messages'][0]
        assert msg['type'] == 'image'
        assert msg['image']['id'] == 'media123abc'
        assert msg['image']['mime_type'] == 'image/jpeg'
        assert msg['image']['caption'] == 'Check this out'

    def test_delivery_status(self):
        event = load_fixture('sns_status_delivered.json')
        _, _, entry = parse_sns_envelope(event['Records'][0])
        statuses = entry['changes'][0]['value']['statuses']
        assert len(statuses) == 1
        assert statuses[0]['status'] == 'delivered'
        assert statuses[0]['recipient_id'] == '919876543210'
        assert statuses[0]['id'] == 'wamid.outbound123'

    def test_template_status_update(self):
        event = load_fixture('sns_template_status.json')
        _, _, entry = parse_sns_envelope(event['Records'][0])
        change = entry['changes'][0]
        assert change['field'] == 'message_template_status_update'
        assert change['value']['event'] == 'APPROVED'
        assert change['value']['message_template_name'] == 'hello_world'

    def test_payment_captured(self):
        event = load_fixture('sns_payment_captured.json')
        _, _, entry = parse_sns_envelope(event['Records'][0])
        status = entry['changes'][0]['value']['statuses'][0]
        assert status['status'] == 'captured'
        assert status['type'] == 'payment'
        assert status['payment']['reference_id'] == 'order-ref-001'
        assert status['payment']['currency'] == 'INR'

    def test_metadata_extraction(self):
        event = load_fixture('sns_inbound_text.json')
        _, _, entry = parse_sns_envelope(event['Records'][0])
        metadata = entry['changes'][0]['value']['metadata']
        assert metadata['display_phone_number'] == '919330994400'
        assert metadata['phone_number_id'] == '960395407161423'
