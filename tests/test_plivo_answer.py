"""Tests for the Plivo answer URL that drives the WhatsApp IVR.

No network calls, no Plivo API use. Asserts XML shape, content type and the
token gate, since a malformed response makes the caller hear silence.
"""
import os
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'plivo-answer')))

import handler as pa  # noqa: E402


def _event(body='', qs=None, b64=False):
    return {
        'requestContext': {'http': {'method': 'POST', 'path': '/plivo/answer'}},
        'headers': {'content-type': 'application/x-www-form-urlencoded'},
        'body': body,
        'isBase64Encoded': b64,
        'queryStringParameters': qs,
    }


PLIVO_FORM = (
    'CallUUID=abc-123&From=919903300044&To=918031830030'
    '&Direction=inbound&CallStatus=ringing'
)


# --------------------------------------------------------------------------
# Response contract
# --------------------------------------------------------------------------
def test_returns_xml_content_type():
    """Plivo ignores the body unless Content-Type is XML."""
    r = pa.handler(_event(PLIVO_FORM), None)
    assert r['statusCode'] == 200
    assert 'text/xml' in r['headers']['Content-Type']


def test_body_is_wellformed_xml():
    r = pa.handler(_event(PLIVO_FORM), None)
    ET.fromstring(r['body'])  # raises if malformed


def test_xml_is_play_then_hangup_in_order():
    r = pa.handler(_event(PLIVO_FORM), None)
    root = ET.fromstring(r['body'])
    assert root.tag == 'Response'
    assert [c.tag for c in root] == ['Play', 'Hangup']


def test_play_points_at_a_plivo_supported_format():
    r = pa.handler(_event(PLIVO_FORM), None)
    url = ET.fromstring(r['body']).find('Play').text
    assert url.startswith('https://')
    assert url.endswith(('.wav', '.mp3')), \
        'Plivo <Play> does not reliably support OGG/Opus'


def test_no_tts_or_record_elements():
    """The IVR is pre-recorded only: no Speak, no Record, no ElevenLabs."""
    body = pa.handler(_event(PLIVO_FORM), None)['body']
    for forbidden in ('<Speak', '<Record', '<GetDigits', '<Dial'):
        assert forbidden not in body


# --------------------------------------------------------------------------
# Body parsing
# --------------------------------------------------------------------------
def test_parses_form_encoded_body():
    p = pa._parse_body(_event(PLIVO_FORM))
    assert p['CallUUID'] == 'abc-123'
    assert p['Direction'] == 'inbound'


def test_parses_json_body_too():
    p = pa._parse_body(_event('{"CallUUID":"json-1"}'))
    assert p['CallUUID'] == 'json-1'


def test_parses_base64_body():
    import base64
    ev = _event(base64.b64encode(PLIVO_FORM.encode()).decode(), b64=True)
    assert pa._parse_body(ev)['CallUUID'] == 'abc-123'


def test_empty_body_still_answers():
    """A missing body must not stop the greeting from playing."""
    r = pa.handler(_event(''), None)
    assert r['statusCode'] == 200
    assert '<Play>' in r['body']


# --------------------------------------------------------------------------
# Token gate
# --------------------------------------------------------------------------
def test_no_token_configured_means_open(monkeypatch):
    monkeypatch.setattr(pa, 'ANSWER_TOKEN', '')
    assert pa.handler(_event(PLIVO_FORM), None)['statusCode'] == 200


def test_wrong_token_is_rejected_with_hangup(monkeypatch):
    monkeypatch.setattr(pa, 'ANSWER_TOKEN', 'sekret')
    r = pa.handler(_event(PLIVO_FORM, qs={'token': 'nope'}), None)
    assert r['statusCode'] == 403
    assert '<Hangup/>' in r['body']
    assert '<Play>' not in r['body'], 'must not leak the media URL'


def test_correct_token_is_accepted(monkeypatch):
    monkeypatch.setattr(pa, 'ANSWER_TOKEN', 'sekret')
    r = pa.handler(_event(PLIVO_FORM, qs={'token': 'sekret'}), None)
    assert r['statusCode'] == 200
    assert '<Play>' in r['body']


def test_xml_escaping_of_media_url(monkeypatch):
    monkeypatch.setattr(pa, 'IVR_AUDIO_URL', 'https://x/a.wav?a=1&b=2')
    body = pa.handler(_event(PLIVO_FORM), None)['body']
    assert '&amp;' in body
    ET.fromstring(body)
