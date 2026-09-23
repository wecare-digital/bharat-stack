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


# ==========================================================================
# gaps found 2026-09-23 while wiring agent receipts through the audit sink
# ==========================================================================
# `mask_secrets` was key-name matching only, and its list had holes. It is used by
# `audit.record_audit`, `system_events.record_system_event`, `meta_client` and
# `graph_errors` - so an unmasked value lands in a persistent DynamoDB row, not just
# a log line that rotates.
#
# Two changes, in the spirit of the workspace rule that a secret must never reach a
# log: fill the key-name holes, and add a high-precision VALUE-shape backstop for
# issuer-prefixed credentials. The backstop deliberately matches the same prefixes
# the PreToolUse hook in scripts/block_inline_secrets.py refuses, and like that hook
# it will not catch an arbitrary high-entropy string with no issuer prefix. It is a
# backstop, not a substitute for not putting credentials in details dicts.

import pytest

from lambda_utils.masking import mask_secrets, mask_value

REDACTED = "***REDACTED***"


@pytest.mark.parametrize("key", [
    # These were all absent from _SECRET_KEYS. `auth_token` is the sharpest of them:
    # it is the literal field name of the Plivo account credential this codebase
    # reads, and `token` being in the list did not cover it.
    "api_key", "apiKey", "API_KEY", "apikey",
    "auth_token", "authToken", "auth_id",
    "refresh_token", "refreshToken",
    "api_secret", "apiSecret",
    "secret_access_key", "secretAccessKey",
    "session_token", "sessionToken",
    "webhook_secret", "webhookSecret",
    "credentials", "bearer",
])
def test_the_key_name_holes_are_closed(key):
    assert mask_secrets({key: "a-real-looking-value-000000"})[key] == REDACTED


@pytest.mark.parametrize("prefix", [
    "sk-", "rzp_live_", "rzp_test_", "AIza", "ghp_", "gho_", "xoxb-", "xoxp-",
    "AKIA", "ASIA", "sk_live_", "sk_test_", "pk_live_", "shpat_", "glpat-",
])
def test_an_issuer_shaped_value_is_masked_under_any_key_name(prefix):
    """The backstop. The key here is `notes` - a name no list would ever cover."""
    value = prefix + "0123456789abcdefghij"
    masked = mask_secrets({"notes": value})["notes"]
    assert value not in masked
    assert masked == REDACTED


def test_a_pem_private_key_body_is_masked_under_any_key_name():
    body = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----"
    assert mask_secrets({"blob": body})["blob"] == REDACTED


def test_an_issuer_shaped_value_is_masked_inside_a_list_and_nested_dict():
    value = "sk-0123456789abcdefghij"
    out = mask_secrets({"outer": {"inner": [{"whatever": value}]}})
    assert value not in str(out)


def test_the_backstop_does_not_fire_on_ordinary_prose():
    """A noisy mask is worse than none: it gets switched off, or the audit trail
    becomes unreadable and nobody consults it."""
    samples = {
        "action": "template.create",
        "message": "Asking about skirt sizes and skateboards",
        "note": "AKIAless text, no credential here",
        "reason": "ghost reference",
        "sku": "SK-1001",
        "id": "0123456789abcdefghij",
        "amount": "1200.00",
        "status": "Answered",
    }
    assert mask_secrets(samples) == samples


def test_the_backstop_requires_enough_length_to_be_a_credential():
    """`sk-` alone, or a short fragment, is prose. A real issuer token is long."""
    assert mask_secrets({"note": "sk-1"})["note"] == "sk-1"
    assert mask_secrets({"note": "AKIA"})["note"] == "AKIA"


def test_masking_still_returns_a_new_structure_not_a_mutated_one():
    original = {"api_key": "sk-0123456789abcdefghij", "keep": "me"}
    masked = mask_secrets(original)
    assert original["api_key"] == "sk-0123456789abcdefghij", "input was mutated"
    assert masked["api_key"] == REDACTED


def test_mask_value_agrees_with_mask_secrets_on_the_new_keys():
    """The two entry points must not disagree; `mask_value` is called directly by
    `graph_errors` and `meta_client`."""
    for key in ("api_key", "auth_token", "refresh_token"):
        assert mask_value(key, "some-long-credential-value") == REDACTED


def test_a_non_string_value_under_a_secret_key_is_still_redacted():
    """A caller may hand over a dict or a number; neither should survive."""
    assert mask_secrets({"api_key": 12345678901234567890})["api_key"] == REDACTED
    assert mask_secrets({"credentials": {"user": "u", "pass": "p"}})["credentials"] \
        == REDACTED
