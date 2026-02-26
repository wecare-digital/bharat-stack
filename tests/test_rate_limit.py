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
