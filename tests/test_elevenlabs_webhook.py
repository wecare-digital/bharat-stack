"""Signature verification and persistence contract for the ElevenLabs webhook.

No network calls, no ElevenLabs API use, no DynamoDB. The signing secret and the
table are both stubbed.

The signature tests are the point of this file. This endpoint is a public,
unauthenticated-by-default URL whose only protection is the HMAC, so the
interesting cases are all the ways a forgery must fail: no header, wrong secret,
replayed timestamp, body mutated after signing, and an unconfigured secret
(which must fail CLOSED rather than accept everything).
"""
import base64
import hashlib
import hmac
import importlib.util
import json
import os
import time

import pytest

_HANDLER = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging',
    'elevenlabs-webhook', 'handler.py'))

_spec = importlib.util.spec_from_file_location('elevenlabs_webhook_under_test', _HANDLER)
ew = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ew)

SECRET = 'wsec_test_signing_secret_value'
BODY = json.dumps({
    "type": "post_call_transcription",
    "event_timestamp": 1758300000,
    "data": {
        "conversation_id": "conv_test_123",
        "agent_id": "agent_test_456",
        "status": "done",
        "transcript": [{"role": "agent", "message": "Hello from WECARE DIGITAL"}],
    },
})


class _FakeTable:
    def __init__(self):
        self.items = []
        self.explode = False

    def put_item(self, Item):
        if self.explode:
            raise RuntimeError("dynamodb unavailable")
        self.items.append(Item)


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    """Stub the secret and the table; reset the module cache between tests."""
    table = _FakeTable()
    monkeypatch.setattr(ew, '_signing_secret_cache', SECRET)
    monkeypatch.setattr(ew, '_table', lambda: table)
    yield table
    monkeypatch.setattr(ew, '_signing_secret_cache', None)


def _sign(secret, timestamp, body):
    return hmac.new(secret.encode(), f'{timestamp}.{body}'.encode(),
                    hashlib.sha256).hexdigest()


def _event(body=BODY, *, secret=SECRET, timestamp=None, header=None,
           b64=False, extra_v0=None):
    ts = int(time.time()) if timestamp is None else timestamp
    if header is None:
        sig = _sign(secret, ts, body)
        header = f't={ts},v0={sig}'
        if extra_v0:
            header += f',v0={extra_v0}'
    payload = base64.b64encode(body.encode()).decode() if b64 else body
    return {
        'requestContext': {'http': {'method': 'POST', 'path': '/elevenlabs/webhook'}},
        'headers': {'content-type': 'application/json', 'ElevenLabs-Signature': header},
        'body': payload,
        'isBase64Encoded': b64,
    }


# --------------------------------------------------------------------------
# Accepted
# --------------------------------------------------------------------------
def test_valid_signature_is_accepted_and_persisted(_stub):
    r = ew.handler(_event(), None)
    assert r['statusCode'] == 200
    assert json.loads(r['body'])['conversation_id'] == 'conv_test_123'
    assert len(_stub.items) == 1
    assert _stub.items[0]['id'] == 'elevenlabs#conv_test_123'
    assert _stub.items[0]['source'] == 'elevenlabs'
    assert _stub.items[0]['event_type'] == 'post_call_transcription'


def test_base64_encoded_body_verifies():
    """API Gateway may base64 the body; the HMAC must be over the decoded bytes."""
    assert ew.handler(_event(b64=True), None)['statusCode'] == 200


def test_rotation_second_v0_candidate_is_accepted():
    """During a secret rotation the header carries several v0 values; any match wins."""
    ev = _event()
    ts, good = ev['headers']['ElevenLabs-Signature'].split(',')
    ev['headers']['ElevenLabs-Signature'] = f'{ts},v0=' + 'a' * 64 + f',{good}'
    assert ew.handler(ev, None)['statusCode'] == 200


# --------------------------------------------------------------------------
# Rejected - each of these would be a forgery or a replay
# --------------------------------------------------------------------------
def test_missing_signature_header_is_rejected():
    ev = _event()
    del ev['headers']['ElevenLabs-Signature']
    assert ew.handler(ev, None)['statusCode'] == 401


def test_wrong_secret_is_rejected(_stub):
    assert ew.handler(_event(secret='wsec_attacker_guess'), None)['statusCode'] == 401
    assert _stub.items == []


def test_body_mutated_after_signing_is_rejected():
    """Sign one body, send another: the classic tamper case."""
    ev = _event()
    ev['body'] = BODY.replace('Hello from WECARE DIGITAL', 'transfer all funds')
    assert ew.handler(ev, None)['statusCode'] == 401


def test_stale_timestamp_is_rejected():
    old = int(time.time()) - (ew.MAX_SKEW_SECONDS + 60)
    assert ew.handler(_event(timestamp=old), None)['statusCode'] == 401


def test_future_timestamp_beyond_skew_is_rejected():
    future = int(time.time()) + (ew.MAX_SKEW_SECONDS + 60)
    assert ew.handler(_event(timestamp=future), None)['statusCode'] == 401


def test_malformed_header_is_rejected():
    for bad in ('', 'garbage', 'v0=deadbeef', 't=notanumber,v0=deadbeef', 't=123'):
        assert ew.handler(_event(header=bad), None)['statusCode'] == 401, bad


def test_unconfigured_secret_fails_closed(monkeypatch):
    """No signing secret must mean REJECT, never accept-everything."""
    monkeypatch.setattr(ew, '_signing_secret_cache', '')
    assert ew.handler(_event(), None)['statusCode'] == 401


def test_rejection_does_not_leak_the_reason():
    """The body must not tell an attacker which check failed."""
    body = ew.handler(_event(secret='nope'), None)['body'].lower()
    for leak in ('signature', 'mismatch', 'secret', 'timestamp', 'stale'):
        assert leak not in body


# --------------------------------------------------------------------------
# Payload handling
# --------------------------------------------------------------------------
def test_invalid_json_with_valid_signature_is_400_not_500():
    assert ew.handler(_event(body='this is not json'), None)['statusCode'] == 400


def test_persist_failure_returns_500_so_elevenlabs_retries(_stub):
    _stub.explode = True
    assert ew.handler(_event(), None)['statusCode'] == 500


def test_floats_are_converted_for_dynamodb(_stub):
    """DynamoDB rejects float outright, so a cost/duration field must become Decimal."""
    body = json.dumps({"type": "post_call_transcription",
                       "data": {"conversation_id": "c1", "cost": 1.25}})
    assert ew.handler(_event(body=body), None)['statusCode'] == 200
    from decimal import Decimal
    assert _stub.items[0]['payload']['data']['cost'] == Decimal('1.25')


def test_missing_conversation_id_still_persists(_stub):
    body = json.dumps({"type": "ping", "data": {}})
    assert ew.handler(_event(body=body), None)['statusCode'] == 200
    assert _stub.items[0]['id'].startswith('elevenlabs#no-conv-')
