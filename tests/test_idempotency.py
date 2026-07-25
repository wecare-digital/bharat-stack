"""Tests for lambda_utils.idempotency."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))

from lambda_utils import idempotency as idem  # noqa: E402


def test_dedupe_key_from_message():
    payload = {'entry': [{'changes': [{'value': {'messages': [{'id': 'wamid.ABC'}]}}]}]}
    assert idem.make_webhook_dedupe_key(payload) == 'msg:wamid.ABC'


def test_dedupe_key_from_status():
    payload = {'entry': [{'changes': [{'value': {'statuses': [{'id': 'wamid.S', 'status': 'delivered'}]}}]}]}
    assert idem.make_webhook_dedupe_key(payload) == 'status:wamid.S:delivered'


def test_dedupe_key_from_call():
    payload = {'entry': [{'changes': [{'value': {'calls': [{'id': 'call.1', 'event': 'connect'}]}}]}]}
    assert idem.make_webhook_dedupe_key(payload) == 'call:call.1:connect'


def test_dedupe_key_hash_fallback():
    payload = {'entry': [{'changes': [{'value': {'foo': 'bar'}}]}]}
    key = idem.make_webhook_dedupe_key(payload)
    assert key and key.startswith('hash:')


def test_check_and_put_new(monkeypatch):
    with patch.object(idem, 'claim_event', return_value=True) as m:
        assert idem.check_and_put_dedupe('wamid.NEW') is True
        m.assert_called_once()


def test_check_and_put_duplicate():
    with patch.object(idem, 'claim_event', return_value=False):
        assert idem.check_and_put_dedupe('wamid.DUP') is False


def test_admin_idempotency_key_stable():
    h = idem.body_hash({'a': 1, 'b': 2})
    assert idem.make_admin_idempotency_key('user1', 'template.create', h) == f'admin:user1:template.create:{h}'
    # hash stable regardless of key order
    assert idem.body_hash({'b': 2, 'a': 1}) == h


def test_safe_replay_key():
    assert idem.safe_replay_key('evt1', 'r2') == 'replay:evt1:r2'


def test_claim_admin_action_success():
    table = MagicMock()
    resource = MagicMock()
    resource.Table.return_value = table
    with patch.object(idem.boto3, 'resource', return_value=resource):
        assert idem.claim_admin_action('admin:key', 'admin-user', 'retry', 60) is True
    item = table.put_item.call_args.kwargs['Item']
    assert item['eventId'] == 'admin:key'
    assert item['source'] == 'admin:retry'
    assert item['actor'] == 'admin-user'
    assert item['ttl'] == item['expiresAt']


def test_claim_admin_action_duplicate_returns_false():
    table = MagicMock()
    table.put_item.side_effect = ClientError(
        {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'duplicate'}},
        'PutItem',
    )
    resource = MagicMock()
    resource.Table.return_value = table
    with patch.object(idem.boto3, 'resource', return_value=resource):
        assert idem.claim_admin_action('admin:key', 'admin-user', 'retry', 60) is False


def test_claim_admin_action_storage_failure_raises():
    table = MagicMock()
    table.put_item.side_effect = ClientError(
        {'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'unavailable'}},
        'PutItem',
    )
    resource = MagicMock()
    resource.Table.return_value = table
    with patch.object(idem.boto3, 'resource', return_value=resource):
        with pytest.raises(ClientError):
            idem.claim_admin_action('admin:key', 'admin-user', 'retry', 60)


def test_claim_admin_action_rejects_missing_identity():
    with pytest.raises(ValueError):
        idem.claim_admin_action('admin:key', '', 'retry', 60)