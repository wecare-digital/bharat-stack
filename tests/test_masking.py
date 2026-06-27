"""Tests for lambda_utils.masking."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))

from lambda_utils.masking import mask_secrets, mask_text  # noqa: E402


def test_authorization_masked():
    out = mask_secrets({'Authorization': 'Bearer abc.def.ghi'})
    assert out['Authorization'] == '***REDACTED***'


def test_access_token_masked():
    out = mask_secrets({'access_token': 'EAAJB123456789'})
    assert out['access_token'] == '***REDACTED***'


def test_appsecret_proof_masked():
    out = mask_secrets({'appsecret_proof': 'deadbeef'})
    assert out['appsecret_proof'] == '***REDACTED***'


def test_encrypted_flow_data_masked():
    out = mask_secrets({'encrypted_flow_data': 'XXXX', 'encrypted_aes_key': 'YYYY', 'initial_vector': 'ZZZZ'})
    assert out['encrypted_flow_data'] == '***REDACTED***'
    assert out['encrypted_aes_key'] == '***REDACTED***'
    assert out['initial_vector'] == '***REDACTED***'


def test_private_key_and_passphrase_masked():
    out = mask_secrets({'private_key': '-----BEGIN-----', 'passphrase': 'pp'})
    assert out['private_key'] == '***REDACTED***' and out['passphrase'] == '***REDACTED***'


def test_phone_partial_masked():
    out = mask_secrets({'phone': '919330994400'})
    assert out['phone'].endswith('4400') and '9330' not in out['phone']


def test_nested_and_list_masked():
    data = {'outer': {'access_token': 'T'}, 'arr': [{'token': 'Z'}, {'ok': 1}]}
    out = mask_secrets(data)
    assert out['outer']['access_token'] == '***REDACTED***'
    assert out['arr'][0]['token'] == '***REDACTED***'
    assert out['arr'][1]['ok'] == 1


def test_non_secret_passthrough():
    out = mask_secrets({'name': 'Pablo', 'count': 5})
    assert out == {'name': 'Pablo', 'count': 5}


def test_mask_text_bearer():
    assert '***REDACTED***' in mask_text('called with Authorization: Bearer abc.DEF-123 ok')
