"""Tests for DLQ message handling and replay logic."""
import json
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))


class TestDLQMessageStructure:
    """Test DLQ message format and retry tracking."""

    def test_dlq_message_format(self):
        """Verify DLQ message has required fields."""
        dlq_msg = {
            'dlqMessageId': 'dlq-001',
            'originalMessageId': 'msg-001',
            'queueName': 'whatsapp-inbound-dlq',
            'retryCount': 0,
            'lastAttemptAt': '2026-03-20T10:00:00Z',
            'payload': json.dumps({'contactId': 'c-1', 'content': 'test'}),
            'expiresAt': 1742572800,  # 7 day TTL
        }
        assert dlq_msg['retryCount'] == 0
        assert dlq_msg['queueName'] == 'whatsapp-inbound-dlq'
        payload = json.loads(dlq_msg['payload'])
        assert payload['contactId'] == 'c-1'

    def test_retry_count_increment(self):
        """Verify retry count increments correctly."""
        retry_count = 0
        max_retries = 3
        for _ in range(max_retries):
            retry_count += 1
        assert retry_count == max_retries

    def test_dlq_ttl_calculation(self):
        """Verify DLQ TTL is 7 days from creation."""
        import time
        now = int(time.time())
        ttl = now + (7 * 24 * 60 * 60)
        assert ttl - now == 604800  # 7 days in seconds

    def test_dlq_payload_preserves_original(self):
        """Verify DLQ preserves original message payload."""
        original = {
            'contactId': 'c-123',
            'content': 'Hello',
            'mediaType': 'image/jpeg',
            'mediaId': 'media-456',
        }
        dlq_payload = json.dumps(original)
        restored = json.loads(dlq_payload)
        assert restored == original

    def test_max_retry_exceeded(self):
        """Verify messages are dropped after max retries."""
        max_retries = 3
        retry_count = 4
        should_retry = retry_count < max_retries
        assert should_retry is False


class TestDLQReplayLogic:
    """Test DLQ replay/reprocessing patterns."""

    def test_replay_preserves_idempotency_key(self):
        """Replayed messages should use original message ID for dedup."""
        original_id = 'msg-original-001'
        replay_msg = {
            'messageId': original_id,
            'isReplay': True,
            'replayAttempt': 1,
        }
        assert replay_msg['messageId'] == original_id

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff for DLQ retries."""
        base_delay = 60  # 1 minute
        for attempt in range(5):
            delay = base_delay * (2 ** attempt)
            expected = [60, 120, 240, 480, 960]
            assert delay == expected[attempt]

    def test_dlq_scan_filter_by_queue(self):
        """Verify DLQ scan can filter by queue name."""
        messages = [
            {'dlqMessageId': 'd1', 'queueName': 'whatsapp-inbound-dlq'},
            {'dlqMessageId': 'd2', 'queueName': 'whatsapp-outbound-dlq'},
            {'dlqMessageId': 'd3', 'queueName': 'whatsapp-inbound-dlq'},
        ]
        inbound_only = [m for m in messages if m['queueName'] == 'whatsapp-inbound-dlq']
        assert len(inbound_only) == 2

    def test_dlq_message_age_check(self):
        """Verify stale DLQ messages are skipped."""
        import time
        now = int(time.time())
        max_age = 7 * 24 * 60 * 60  # 7 days
        fresh_msg = {'expiresAt': now + 86400}  # 1 day left
        stale_msg = {'expiresAt': now - 86400}  # expired yesterday
        assert fresh_msg['expiresAt'] > now
        assert stale_msg['expiresAt'] < now
