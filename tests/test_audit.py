"""Tests for lambda_utils.audit and system_events."""
import json
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))

from lambda_utils import audit  # noqa: E402
from lambda_utils import system_events as se  # noqa: E402


class TestAudit:
    def test_record_audit_writes_item(self):
        table = MagicMock()
        with patch.object(audit, '_dynamodb') as ddb:
            ddb.Table.return_value = table
            log_id = audit.record_audit(action='template.create', actor='user1',
                                        resource_type='template', resource_id='hello',
                                        details={'category': 'MARKETING'})
        assert log_id
        item = table.put_item.call_args.kwargs['Item']
        assert item['action'] == 'template.create'
        assert item['userId'] == 'user1'
        assert item['expiresAt'] > 0
        assert json.loads(item['details'])['category'] == 'MARKETING'

    def test_record_audit_masks_secrets(self):
        table = MagicMock()
        with patch.object(audit, '_dynamodb') as ddb:
            ddb.Table.return_value = table
            audit.record_audit(action='secret.update', details={'access_token': 'SECRET'})
        item = table.put_item.call_args.kwargs['Item']
        assert 'SECRET' not in item['details']

    def test_record_audit_fails_open(self):
        with patch.object(audit, '_dynamodb') as ddb:
            ddb.Table.side_effect = RuntimeError('boom')
            assert audit.record_audit(action='x') is None


class TestSystemEvents:
    def test_record_event(self):
        table = MagicMock()
        with patch.object(se, '_dynamodb') as ddb:
            ddb.Table.return_value = table
            eid = se.record_system_event('template_rejected', waba_id='123', severity='warning',
                                         data={'template': 'x'})
        assert eid
        item = table.put_item.call_args.kwargs['Item']
        assert item['eventType'] == 'template_rejected'
        assert item['severity'] == 'warning'
        assert item['ttl'] > 0

    def test_invalid_severity_defaults_info(self):
        table = MagicMock()
        with patch.object(se, '_dynamodb') as ddb:
            ddb.Table.return_value = table
            se.record_system_event('x', severity='bogus')
        assert table.put_item.call_args.kwargs['Item']['severity'] == 'info'
