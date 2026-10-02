"""Top-up API auth must never fall back to a webhook-signing secret."""
import ast
import json
from pathlib import Path
from unittest.mock import Mock


def load_credentials_function(client):
    path = Path(__file__).resolve().parents[1] / 'amplify/functions/messaging/partner-onboarding/handler.py'
    module = ast.parse(path.read_text())
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == '_razorpay_creds')
    namespace = {'_secrets': client, 'json': json}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['_razorpay_creds']


def test_reads_only_canonical_api_secret():
    client = Mock()
    client.get_secret_value.return_value = {'SecretString': json.dumps({'key_id': 'fixture-id', 'key_secret': 'fixture-secret'})}
    assert load_credentials_function(client)() == ('fixture-id', 'fixture-secret')
    client.get_secret_value.assert_called_once_with(SecretId='wecare/razorpay/api')


def test_missing_api_credentials_do_not_try_webhook_secret():
    client = Mock()
    client.get_secret_value.side_effect = RuntimeError('fixture unavailable')
    assert load_credentials_function(client)() == ('', '')
    client.get_secret_value.assert_called_once_with(SecretId='wecare/razorpay/api')
