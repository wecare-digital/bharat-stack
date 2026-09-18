"""Tests for sms-aws destination-based routing and India DLT compliance.

Regression cover for a real defect: the handler detected an Indian MSISDN and
then executed a bare `pass`, so +91 traffic was sent via us-east-1 with no
TRAI DLT parameters at all.

These tests assert routing and parameter construction only. No SMS is sent -
the boto3 client is stubbed.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

import importlib.util

# Every Lambda handler in this repo is named handler.py, so a plain
# `import handler` races with other test modules (conftest clears the cache
# per test, but a module-level binding would already point at the wrong file).
# Load it by absolute path under a unique module name instead.
_HANDLER = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging',
    'sms-aws', 'handler.py'))
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared')))

_spec = importlib.util.spec_from_file_location('sms_aws_handler_under_test', _HANDLER)
sms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sms)


# --------------------------------------------------------------------------
# MSISDN classification
# --------------------------------------------------------------------------
@pytest.mark.parametrize("phone,expected", [
    ("+919903300044", True),
    ("919903300044", True),
    ("+918031830030", True),
    ("+14155552671", False),    # US
    ("+442071838750", False),   # UK
    ("+9190", False),           # too short
    ("+9199033000441", False),  # too long
    ("", False),
    (None, False),
])
def test_is_indian_msisdn(phone, expected):
    assert sms._is_indian_msisdn(phone) is expected


# --------------------------------------------------------------------------
# DLT template resolution
# --------------------------------------------------------------------------
def test_known_template_keys_resolve():
    assert sms._resolve_dlt_template("ivr-default")["templateId"] == "1007277993798259629"
    assert sms._resolve_dlt_template("wa-alert")["templateId"] == "1007284579074821763"
    assert sms._resolve_dlt_template("wd_order")["templateId"] == "1007723091207562020"


def test_empty_key_falls_back_to_default():
    r = sms._resolve_dlt_template("")
    assert r.get("templateKey") == "ivr-default"
    assert r.get("templateId") == "1007277993798259629"


def test_unknown_key_is_a_hard_error_not_a_silent_send():
    r = sms._resolve_dlt_template("no-such-template")
    assert "error" in r
    assert "templateId" not in r
    assert "no-such-template" in r["error"]


def test_entity_id_is_the_registered_pe_id():
    assert sms.INDIA_ENTITY_ID == "1201161991108627443"


def test_india_sender_id_is_registered_header():
    assert sms.INDIA_SENDER_ID == "WDBEEP"


# --------------------------------------------------------------------------
# Parameter construction: India must carry DLT, non-India must not
# --------------------------------------------------------------------------
def _capture_send(phone, india, template_id=None, dry_run=False):
    """Run _send_pinpoint_sms with a stubbed client and return the params."""
    fake = MagicMock()
    fake.send_text_message.return_value = {"MessageId": "mid-test"}
    with patch.object(sms.boto3, "client", return_value=fake), \
         patch.object(sms.pinpoint_sms, "send_text_message",
                      return_value={"MessageId": "mid-test"}) as intl:
        res = sms._send_pinpoint_sms(phone, "Test body", "TRANSACTIONAL", "req-1",
                                     use_india_region=india,
                                     dlt_template_id=template_id,
                                     dry_run=dry_run)
        if india:
            assert fake.send_text_message.called, "india client was not used"
            return res, fake.send_text_message.call_args.kwargs
        assert intl.called, "us-east-1 client was not used"
        return res, intl.call_args.kwargs


def test_india_send_includes_dlt_country_parameters():
    res, params = _capture_send("+919903300044", True, "1007277993798259629")
    assert res["success"] is True
    dcp = params["DestinationCountryParameters"]
    assert dcp["IN_ENTITY_ID"] == "1201161991108627443"
    assert dcp["IN_TEMPLATE_ID"] == "1007277993798259629"
    assert params["OriginationIdentity"] == "WDBEEP"


def test_india_dry_run_flag_is_passed_through():
    _res, params = _capture_send("+919903300044", True, "1007277993798259629", dry_run=True)
    assert params.get("DryRun") is True


def test_non_india_send_has_no_indian_dlt_fields():
    res, params = _capture_send("+14155552671", False)
    assert res["success"] is True
    assert "DestinationCountryParameters" not in params, \
        "Indian DLT fields must never be sent on non-India traffic"
    assert params["DestinationPhoneNumber"] == "+14155552671"


def test_india_without_template_id_still_sends_entity_id_only():
    """Defensive: entity id alone should not be dropped if template is absent."""
    _res, params = _capture_send("+919903300044", True, None)
    dcp = params.get("DestinationCountryParameters", {})
    assert dcp.get("IN_ENTITY_ID") == "1201161991108627443"
    assert "IN_TEMPLATE_ID" not in dcp


# --------------------------------------------------------------------------
# Regression guard on the original defect
# --------------------------------------------------------------------------
def test_regression_indian_number_is_not_silently_routed_international():
    """The old code detected +91 then executed `pass`, routing via us-east-1."""
    assert sms._is_indian_msisdn("+919903300044") is True, (
        "If this fails, destination-based routing is broken and Indian traffic "
        "will leave via us-east-1 without DLT parameters."
    )


# --------------------------------------------------------------------------
# E.164 formatting: regression cover for a MISDELIVERY bug
#
# The previous _format_e164 applied the +91 default to any 10-digit string,
# including numbers that already carried a country code. +6581234567 (Singapore)
# became +916581234567 - a different, real Indian subscriber - and was then
# routed to ap-south-1 with a DLT template attached.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("supplied,expected", [
    # Explicit country code must always be honoured, never re-prefixed.
    ("+6581234567", "+6581234567"),      # Singapore, 10 digits - the bug case
    ("+6591234567", "+6591234567"),      # Singapore
    ("+85261234567", "+85261234567"),    # Hong Kong
    ("+4512345678", "+4512345678"),      # Denmark, 10 digits
    ("+351211234567", "+351211234567"),  # Portugal
    ("+14255551234", "+14255551234"),    # USA
    ("+447700900123", "+447700900123"),  # UK
    ("+971501234567", "+971501234567"),  # UAE
    ("+919903300044", "+919903300044"),  # India, already E.164
    # Bare local numbers with no country code default to India.
    ("9903300044", "+919903300044"),
    ("8031830030", "+918031830030"),
    # Formatting noise must be stripped, prefix preserved.
    ("+65 8123 4567", "+6581234567"),
    ("+91-99033-00044", "+919903300044"),
    ("(425) 555-1234", "+914255551234"),  # bare 10 digits -> India, by design
    ("", ""),
    (None, ""),
])
def test_format_e164_honours_supplied_country_code(supplied, expected):
    assert sms._format_e164(supplied) == expected


@pytest.mark.parametrize("supplied,should_be_india", [
    ("+6581234567", False),     # was True before the fix - MISDELIVERY
    ("+6591234567", False),
    ("+4512345678", False),
    ("+14255551234", False),
    ("+447700900123", False),
    ("+919903300044", True),
    ("9903300044", True),
])
def test_routing_decision_after_formatting(supplied, should_be_india):
    """Formatting feeds the routing decision, so assert the end result."""
    assert sms._is_indian_msisdn(sms._format_e164(supplied)) is should_be_india


def test_ten_digit_international_no_longer_becomes_indian():
    """Explicit regression guard on the exact reported defect."""
    out = sms._format_e164("+6581234567")
    assert out == "+6581234567"
    assert not sms._is_indian_msisdn(out), (
        "A Singapore number must never be rewritten to +91 - it would be "
        "delivered to an unrelated Indian subscriber."
    )


# --------------------------------------------------------------------------
# Origination identity must never be the simulator
# --------------------------------------------------------------------------
SIMULATOR_NUMBER = "+14255556333"
TOLL_FREE_NUMBER = "+18444891209"


def test_origination_identity_is_pinned():
    """Unset means AWS chooses, and it may choose the simulator."""
    assert sms.ORIGINATION_IDENTITY, "must not be empty"


def test_origination_identity_is_not_the_simulator():
    assert sms.ORIGINATION_IDENTITY != SIMULATOR_NUMBER, (
        "SIMULATOR numbers return a MessageId without delivering anything"
    )


def test_origination_identity_defaults_to_registered_toll_free():
    assert sms.ORIGINATION_IDENTITY == TOLL_FREE_NUMBER


def test_non_india_send_passes_the_pinned_identity():
    fake = MagicMock()
    fake.send_text_message.return_value = {"MessageId": "mid"}
    with patch.object(sms, "pinpoint_sms", fake):
        sms._send_pinpoint_sms("+14255551234", "hi", "TRANSACTIONAL", "r1",
                               use_india_region=False)
    params = fake.send_text_message.call_args.kwargs
    assert params["OriginationIdentity"] == TOLL_FREE_NUMBER
    assert params["OriginationIdentity"] != SIMULATOR_NUMBER
    assert "DestinationCountryParameters" not in params
