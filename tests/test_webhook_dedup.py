"""Tests for the shared webhook dedup helper (lambda_utils.webhook_dedup)."""
import os
import sys
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))

from lambda_utils import webhook_dedup  # noqa: E402


def _conditional_failure():
    return ClientError({'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'exists'}}, 'PutItem')


class TestClaimEvent:
    def test_new_event_claimed(self):
        table = MagicMock()
        with patch.object(webhook_dedup, '_table', return_value=table):
            assert webhook_dedup.claim_event('wamid.ABC', source='whatsapp') is True
        # verify conditional put with TTL fields
        args, kwargs = table.put_item.call_args
        item = kwargs['Item']
        assert item['eventId'] == 'wamid.ABC'
        assert item['source'] == 'whatsapp'
        assert item['expiresAt'] == item['ttl'] and item['ttl'] > 0
        assert kwargs['ConditionExpression'] == 'attribute_not_exists(eventId)'

    def test_duplicate_event_skipped(self):
        table = MagicMock()
        table.put_item.side_effect = _conditional_failure()
        with patch.object(webhook_dedup, '_table', return_value=table):
            assert webhook_dedup.claim_event('wamid.DUP', source='whatsapp') is False

    def test_empty_id_fails_open(self):
        # No id -> cannot dedup, must process (True), no DynamoDB call
        with patch.object(webhook_dedup, '_table') as t:
            assert webhook_dedup.claim_event('', source='whatsapp') is True
            t.assert_not_called()

    def test_infra_error_fails_open(self):
        table = MagicMock()
        table.put_item.side_effect = ClientError({'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'slow'}}, 'PutItem')
        with patch.object(webhook_dedup, '_table', return_value=table):
            assert webhook_dedup.claim_event('wamid.X', source='whatsapp') is True

    def test_generic_exception_fails_open(self):
        table = MagicMock()
        table.put_item.side_effect = RuntimeError('boom')
        with patch.object(webhook_dedup, '_table', return_value=table):
            assert webhook_dedup.claim_event('wamid.Y') is True


class TestIsDuplicate:
    def test_is_duplicate_true_on_conditional_failure(self):
        table = MagicMock()
        table.put_item.side_effect = _conditional_failure()
        with patch.object(webhook_dedup, '_table', return_value=table):
            assert webhook_dedup.is_duplicate('wamid.DUP') is True

    def test_is_duplicate_false_on_new(self):
        table = MagicMock()
        with patch.object(webhook_dedup, '_table', return_value=table):
            assert webhook_dedup.is_duplicate('wamid.NEW') is False
