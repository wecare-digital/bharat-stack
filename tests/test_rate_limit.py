"""Tests for lambda_utils.rate_limit module."""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal


class TestCheckRateLimit:
    @patch('lambda_utils.rate_limit.dynamodb')
    def test_under_limit_returns_true(self, mock_ddb):
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.return_value = {
            'Attributes': {'messageCount': Decimal('5')}
        }
        assert check_rate_limit('whatsapp', 'phone-123', max_per_second=80) is True

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_over_limit_returns_false(self, mock_ddb):
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.return_value = {
            'Attributes': {'messageCount': Decimal('81')}
        }
        assert check_rate_limit('whatsapp', 'phone-123', max_per_second=80) is False

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_at_limit_returns_true(self, mock_ddb):
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.return_value = {
            'Attributes': {'messageCount': Decimal('80')}
        }
        assert check_rate_limit('whatsapp', 'phone-123', max_per_second=80) is True

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_error_fails_open(self, mock_ddb):
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.side_effect = Exception('DDB error')
        assert check_rate_limit('sms', 'phone-456') is True

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_custom_table_name(self, mock_ddb):
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.return_value = {
            'Attributes': {'messageCount': Decimal('1')}
        }
        check_rate_limit('email', 'user-1', table_name='CustomTable')
        mock_ddb.Table.assert_called_with('CustomTable')


class TestKeySchemaMatchesTheLiveTable:
    """The bug these tests missed.

    Every test above mocks `dynamodb` wholesale, so `update_item` accepts any Key
    shape. The module shipped `Key={'channel': ..., 'windowStart': ...}` against a
    table whose only key attribute is `id`. DynamoDB answers that with
    ValidationException, the module's `except Exception` caught it, and the function
    returned True - so `operations/bulk-worker` and `messaging/partner-onboarding`
    ran with no rate limit at all while five green tests said otherwise.

    Verified against the live table on 2026-09-25 with a read-only GetItem: the
    composite shape is rejected, `{'id': ...}` is accepted.
    """

    LIVE_KEY_ATTRIBUTES = {'id'}

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_the_key_matches_the_live_table_schema(self, mock_ddb):
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.return_value = {'Attributes': {'messageCount': Decimal('1')}}

        check_rate_limit('whatsapp', 'phone-123', max_per_second=80)

        key = mock_table.update_item.call_args.kwargs['Key']
        assert set(key) == self.LIVE_KEY_ATTRIBUTES, (
            f"Key uses {sorted(key)}; the live RateLimitTable keys on "
            f"{sorted(self.LIVE_KEY_ATTRIBUTES)} only. A mismatch raises "
            "ValidationException, which this module swallows and fails open on - "
            "so rate limiting silently stops applying."
        )

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_the_id_carries_channel_resource_and_window(self, mock_ddb):
        """Without the window in the id, every call collides on one row forever."""
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.return_value = {'Attributes': {'messageCount': Decimal('1')}}

        check_rate_limit('whatsapp', 'phone-123', max_per_second=80)

        parts = mock_table.update_item.call_args.kwargs['Key']['id'].split(':')
        assert parts[0] == 'whatsapp'
        assert parts[1] == 'phone-123'
        assert parts[2].isdigit(), f"expected a window timestamp, got {parts[2]!r}"

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_ttl_attribute_is_a_future_expiry(self, mock_ddb):
        """TTL is ENABLED on lastUpdatedAt live.

        So it must be an absolute future expiry. Writing "now" there would make the
        row eligible for deletion the moment it is created - and amplify/backend.ts
        asserted exactly that was happening. It is not: this writes now + 24h.
        """
        import time as _time
        from lambda_utils.rate_limit import check_rate_limit, TTL_SECONDS
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.return_value = {'Attributes': {'messageCount': Decimal('1')}}

        before = int(_time.time())
        check_rate_limit('whatsapp', 'phone-123')

        ttl = int(mock_table.update_item.call_args.kwargs['ExpressionAttributeValues'][':ttl'])
        assert ttl >= before + TTL_SECONDS, "lastUpdatedAt must be a future expiry"

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_a_schema_error_is_logged_at_error_not_warning(self, mock_ddb):
        """A permanent failure must not look like a transient one.

        Fail-open is deliberate and stays. What is not acceptable is that a rate
        limiter disabled on every single call logged at the same level as a blip.
        """
        from botocore.exceptions import ClientError
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException',
                       'Message': 'The provided key element does not match the schema'}},
            'UpdateItem',
        )

        with patch('lambda_utils.rate_limit.logger') as mock_logger:
            assert check_rate_limit('whatsapp', 'phone-123') is True  # still fails open
            level, message = mock_logger.log.call_args.args[0], mock_logger.log.call_args.args[1]
            assert level == 40, f"expected ERROR (40), got {level}"
            assert 'disabled_permanent_error' in message

    @patch('lambda_utils.rate_limit.dynamodb')
    def test_no_credential_or_message_text_reaches_the_log(self, mock_ddb):
        """Log the exception type, not its text - see .kiro/steering/secret-handling.md."""
        from lambda_utils.rate_limit import check_rate_limit
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        mock_table.update_item.side_effect = Exception('sensitive-detail-abc123')

        with patch('lambda_utils.rate_limit.logger') as mock_logger:
            check_rate_limit('whatsapp', 'phone-123')
            # Assert against EVERY call on the logger, not just .log(). Checking one
            # method made this test pass vacuously against the previous code, which
            # did leak the message but did so through .warning().
            assert mock_logger.method_calls, "expected the failure to be logged at all"
            assert 'sensitive-detail-abc123' not in str(mock_logger.method_calls)
