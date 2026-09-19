"""Routing, DLT and E.164 contract for the provider-neutral SMS layer.

No network, no AWS. The EUM v2 client is stubbed so the assertions are about the
decisions the layer makes, not about boto3.

The cases that matter most are the ones that used to be wrong:

  * a 10-digit non-Indian number in full E.164 form must not become Indian
  * an Indian number with no approved DLT template must be REFUSED, not sent
  * an explicit region override must not switch DLT off
  * international sends must pin the origination identity, or AWS may pick the
    simulator number that silently discards traffic
"""
import importlib
import os
import sys
from pathlib import Path

import pytest

SHARED = Path(__file__).resolve().parents[1] / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.comms import dlt as dlt_mod          # noqa: E402
from lambda_utils.comms import numbers                  # noqa: E402
from lambda_utils.comms import region as region_mod     # noqa: E402
from lambda_utils.comms import sms as sms_mod           # noqa: E402


class _FakeClient:
    """Records send_text_message calls; never touches the network."""

    def __init__(self):
        self.calls = []
        self.raise_with = None

    def send_text_message(self, **params):
        if self.raise_with:
            raise self.raise_with
        self.calls.append(params)
        return {"MessageId": f"prov-{len(self.calls)}"}


@pytest.fixture
def fake(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(sms_mod, "_clients", {})
    monkeypatch.setattr(sms_mod, "_client", lambda region: client)
    client.region_calls = []
    return client


@pytest.fixture
def svc():
    return sms_mod.AwsSmsProvider()


# --------------------------------------------------------------------------
# E.164 — the misdelivery bug this layer exists to prevent
# --------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("9903300044", "+919903300044"),      # bare 10-digit -> India
    ("+919903300044", "+919903300044"),   # already E.164
    ("+6581234567", "+6581234567"),       # Singapore, 10 digits WITH +
    ("+4512345678", "+4512345678"),       # Denmark, 10 digits WITH +
    ("+4712345678", "+4712345678"),       # Norway
    ("+85212345678", "+85212345678"),     # Hong Kong
    ("+18444891209", "+18444891209"),     # US toll-free
    ("+91 99033 00044", "+919903300044"),  # spaces tolerated
    ("", ""),
    ("abc", ""),
])
def test_to_e164(raw, expected):
    assert numbers.to_e164(raw) == expected


def test_ten_digit_international_is_not_reclassified_as_india():
    """The regression that sent a Singapore number to an Indian subscriber."""
    assert numbers.to_e164("+6581234567") == "+6581234567"
    assert numbers.is_india("+6581234567") is False
    assert region_mod.resolve("+6581234567").region == "us-east-1"


@pytest.mark.parametrize("phone,expected", [
    ("+919903300044", True),
    ("+91990330004", False),    # 11 digits, too short
    ("+9199033000444", False),  # 13 digits, too long
    ("+6581234567", False),
    ("", False),
])
def test_is_india_requires_exact_length(phone, expected):
    assert numbers.is_india(phone) is expected


def test_iso_country_returns_none_rather_than_guessing():
    assert numbers.iso_country("+919903300044") == "IN"
    assert numbers.iso_country("+6581234567") is None


# --------------------------------------------------------------------------
# Region resolution
# --------------------------------------------------------------------------
def test_india_routes_to_ap_south_1_and_requires_dlt():
    route = region_mod.resolve("+919903300044")
    assert route.region == "ap-south-1"
    assert route.is_india is True
    assert route.requires_dlt is True


def test_non_india_routes_to_us_east_1_and_does_not_require_dlt():
    route = region_mod.resolve("+14255551234")
    assert route.region == "us-east-1"
    assert route.requires_dlt is False


def test_override_changes_region_but_never_drops_dlt():
    """A routing preference must not become a regulatory bypass."""
    route = region_mod.resolve("+919903300044", override_region="us-east-1")
    assert route.region == "us-east-1"
    assert route.requires_dlt is True, "India still needs DLT even if forced elsewhere"


# --------------------------------------------------------------------------
# DLT
# --------------------------------------------------------------------------
def test_known_template_resolves_from_builtin_map():
    r = dlt_mod.resolve("ivr-default")
    assert r.ok
    assert r.template_id == "1007277993798259629"
    assert r.source == "builtin"
    assert r.country_parameters() == {
        "IN_ENTITY_ID": "1201161991108627443",
        "IN_TEMPLATE_ID": "1007277993798259629",
    }


def test_empty_key_falls_back_to_default():
    assert dlt_mod.resolve("").template_key == "ivr-default"


def test_unknown_template_is_an_error_not_a_guess():
    r = dlt_mod.resolve("not-registered", allow_registry=False)
    assert not r.ok
    assert r.template_id == ""
    assert "not-registered" in r.error
    assert r.country_parameters() == {}


def test_country_parameters_emits_both_keys_or_neither():
    """Emitting one key is worse than none: accepted, then dropped downstream."""
    bad = dlt_mod.resolve("nope", allow_registry=False)
    assert bad.country_parameters() == {}
    good = dlt_mod.resolve("wd_order")
    assert set(good.country_parameters()) == {"IN_ENTITY_ID", "IN_TEMPLATE_ID"}


# --------------------------------------------------------------------------
# Sending — India
# --------------------------------------------------------------------------
def test_india_send_attaches_sender_id_and_dlt(fake, svc):
    r = svc.send_transactional_sms("+919903300044", "hello",
                                   dlt_template_key="ivr-default")
    assert r.success
    assert r.route.region == "ap-south-1"
    p = fake.calls[0]
    assert p["OriginationIdentity"] == "WDBEEP"
    assert p["DestinationCountryParameters"]["IN_ENTITY_ID"] == "1201161991108627443"
    assert p["DestinationCountryParameters"]["IN_TEMPLATE_ID"] == "1007277993798259629"
    assert p["MessageType"] == "TRANSACTIONAL"


def test_india_send_without_approved_template_is_refused(fake, svc):
    r = svc.send_sms("+919903300044", "hello", dlt_template_key="not-registered")
    assert not r.success
    assert r.error_code == "MISSING_DLT_TEMPLATE"
    assert fake.calls == [], "nothing may reach the provider"


def test_india_send_defaults_to_ivr_default_when_no_key_given(fake, svc):
    r = svc.send_sms("+919903300044", "hello")
    assert r.success
    assert fake.calls[0]["DestinationCountryParameters"]["IN_TEMPLATE_ID"] \
        == "1007277993798259629"


# --------------------------------------------------------------------------
# Sending — international
# --------------------------------------------------------------------------
def test_international_send_pins_origination_identity(fake, svc):
    """Unpinned, AWS may pick the SIMULATOR number and silently discard the send."""
    r = svc.send_transactional_sms("+14255551234", "hello")
    assert r.success
    p = fake.calls[0]
    assert p["OriginationIdentity"] == "+18444891209"
    assert "DestinationCountryParameters" not in p, "Indian DLT is invalid abroad"


def test_international_send_never_carries_indian_dlt(fake, svc):
    svc.send_sms("+6581234567", "hello", dlt_template_key="ivr-default")
    assert "DestinationCountryParameters" not in fake.calls[0]


# --------------------------------------------------------------------------
# Validation, dry run, errors
# --------------------------------------------------------------------------
def test_invalid_phone_is_rejected_before_any_send(fake, svc):
    r = svc.send_sms("abc", "hello")
    assert not r.success and r.error_code == "INVALID_PHONE"
    assert fake.calls == []


def test_empty_content_is_rejected(fake, svc):
    r = svc.send_sms("+919903300044", "")
    assert not r.success and r.error_code == "MISSING_CONTENT"
    assert fake.calls == []


def test_dry_run_sets_dryrun_and_still_validates_dlt(fake, svc):
    r = svc.send_sms("+919903300044", "hello", dlt_template_key="ivr-default",
                     dry_run=True)
    assert r.success and r.dry_run
    assert fake.calls[0]["DryRun"] is True


def test_dry_run_still_refuses_a_missing_template(fake, svc):
    r = svc.send_sms("+919903300044", "hi", dlt_template_key="nope", dry_run=True)
    assert not r.success and r.error_code == "MISSING_DLT_TEMPLATE"
    assert fake.calls == []


def test_provider_exception_is_returned_not_raised(fake, svc):
    fake.raise_with = RuntimeError("throttled")
    r = svc.send_sms("+14255551234", "hello")
    assert not r.success
    assert "throttled" in r.error
    assert r.error_code == "RuntimeError"


# --------------------------------------------------------------------------
# Delivery status honesty
# --------------------------------------------------------------------------
def test_get_delivery_status_admits_receipts_are_not_ingested(svc):
    status = svc.get_delivery_status("abc")
    assert status["status"] == "UNKNOWN_NO_RECEIPTS"
    assert "not ingested" in status["detail"]


@pytest.mark.parametrize("event,expected", [
    ("TEXT_DELIVERED", "delivered"),
    ("TEXT_SUCCESSFUL", "sent"),
    ("TEXT_BLOCKED", "failed"),
    ("TEXT_CARRIER_UNREACHABLE", "failed"),
    ("TEXT_TTL_EXPIRED", "failed"),
    ("SOMETHING_NEW", "unknown"),
])
def test_delivery_receipt_mapping(svc, event, expected):
    out = svc.process_delivery_receipt({"eventType": event, "messageId": "m1"})
    assert out["status"] == expected
    assert out["providerMessageId"] == "m1"


# --------------------------------------------------------------------------
# The provider rule itself
# --------------------------------------------------------------------------
def test_there_is_exactly_one_sms_provider_and_it_is_aws():
    svc = sms_mod.get_sms_service()
    assert isinstance(svc, sms_mod.AwsSmsProvider)
    assert svc.provider_name == "aws-end-user-messaging"


def test_facade_returns_a_singleton():
    from lambda_utils.comms import get_sms_service
    assert get_sms_service() is get_sms_service()


def test_no_legacy_aws_sms_transport_in_the_module():
    """SNS SMS and classic Pinpoint are explicitly out of scope (§4)."""
    source = (Path(sms_mod.__file__)).read_text()
    for banned in ("AWS.SNS.SMS", "sns.publish", "send_messages("):
        assert banned not in source, f"{banned} must not appear in the SMS provider"
