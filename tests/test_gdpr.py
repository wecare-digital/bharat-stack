"""
Tests for GDPR DSAR utilities.
Covers: export_user_data, delete_user_data.
"""
import json
import sys
import os
from unittest.mock import patch, MagicMock
from decimal import Decimal
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
from lambda_utils.gdpr import export_user_data, delete_user_data, _sanitize_items


class TestExportUserData:
    def test_export_returns_structure(self):
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.query.return_value = {'Items': [{'id': '1', 'phone': '+91xxx'}]}
        mock_table.scan.return_value = {'Items': []}
        mock_dynamodb.Table.return_value = mock_table

        result = export_user_data(mock_dynamodb, 'contact-123', '+919330994400')
        assert 'contactId' in result
        assert 'tables' in result
        assert 'totalRecords' in result
        assert result['contactId'] == 'contact-123'

    def test_export_handles_missing_table(self):
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.query.side_effect = Exception('Table not found')
        mock_table.scan.side_effect = Exception('Table not found')
        mock_dynamodb.Table.return_value = mock_table

        result = export_user_data(mock_dynamodb, 'contact-123', '+919330994400')
        assert result['totalRecords'] == 0

    def test_export_with_no_phone(self):
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.query.return_value = {'Items': []}
        mock_table.scan.return_value = {'Items': []}
        mock_dynamodb.Table.return_value = mock_table

        result = export_user_data(mock_dynamodb, 'contact-123', '')
        assert result['totalRecords'] == 0


class TestDeleteUserData:
    def test_dry_run_does_not_delete(self):
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.query.return_value = {'Items': [{'id': '1', 'contactId': 'c1'}]}
        mock_table.scan.return_value = {'Items': []}
        mock_dynamodb.Table.return_value = mock_table

        result = delete_user_data(mock_dynamodb, 'contact-123', '+919330994400', dry_run=True)
        assert result['dryRun'] is True
        # batch_writer should NOT be called in dry_run
        mock_table.batch_writer.assert_not_called()

    def test_actual_delete(self):
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.query.return_value = {'Items': [{'id': '1', 'contactId': 'c1'}]}
        mock_table.scan.return_value = {'Items': []}
        mock_table.meta.client.describe_table.return_value = {
            'Table': {'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}]}
        }
        mock_batch = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_batch)
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
        mock_dynamodb.Table.return_value = mock_table

        result = delete_user_data(mock_dynamodb, 'contact-123', '+919330994400', dry_run=False)
        assert result['dryRun'] is False


class TestSanitizeItems:
    def test_decimal_conversion(self):
        items = [{'amount': Decimal('49.99'), 'name': 'test'}]
        result = _sanitize_items(items)
        assert result[0]['amount'] == 49.99
        assert result[0]['name'] == 'test'

    def test_empty_list(self):
        assert _sanitize_items([]) == []

    def test_nested_dict(self):
        items = [{'data': {'value': Decimal('10')}}]
        result = _sanitize_items(items)
        assert result[0]['data']['value'] == 10.0
