"""A deleted store must report 410, not 500.

Retiring a provider happens in two steps that can be months apart: switch the
sender off, then delete the table. Between them the read paths are fine. After,
DynamoDB raises `ResourceNotFoundException`, the handler's outer `except
Exception` turns it into a 500, and an operator is told the platform is broken
when the truth is that the data was deliberately deleted. Those are different
claims pointing at different remedies.

Measured 2026-09-24: neither `stack-wecare-digital-AirtelC2CTable` nor
`stack-wecare-digital-AirtelSMSTable` is in the account (both deleted 2026-09-20),
and `wecare-voice-in-c2c` — which names the first at five sites — took 39
invocations in 30 days. So these were live 500s, not dead code.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SHARED = Path(__file__).resolve().parent.parent / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import retired_store                      # noqa: E402
from lambda_utils.comms import legacy_history               # noqa: E402


class FakeResourceNotFound(Exception):
    """Shaped like botocore's synthesised error, which has no importable class."""

    def __init__(self):
        super().__init__("Requested resource not found")
        self.response = {"Error": {"Code": "ResourceNotFoundException",
                                   "Message": "Requested resource not found"}}


class FakeThrottling(Exception):
    def __init__(self):
        super().__init__("Throughput exceeded")
        self.response = {"Error": {"Code": "ProvisionedThroughputExceededException"}}


class AbsentTable:
    """Every operation behaves as DynamoDB does for a table that is gone."""

    def scan(self, **_kwargs):
        raise FakeResourceNotFound()

    def get_item(self, **_kwargs):
        raise FakeResourceNotFound()


# ---------------------------------------------------------------------------
# is_absent
# ---------------------------------------------------------------------------

def test_recognises_resource_not_found_by_error_code():
    assert retired_store.is_absent(FakeResourceNotFound()) is True


def test_recognises_it_by_class_name_when_there_is_no_response_dict():
    exc = type("ResourceNotFoundException", (Exception,), {})()
    assert retired_store.is_absent(exc) is True


def test_does_not_swallow_throttling():
    """The reason for matching on the code rather than catching ClientError.

    Throttling and access-denied are real faults and must keep surfacing as
    faults; a broad `except ClientError` here would hide both.
    """
    assert retired_store.is_absent(FakeThrottling()) is False


def test_does_not_swallow_an_unrelated_error():
    assert retired_store.is_absent(ValueError("nope")) is False
    assert retired_store.is_absent(KeyError("nope")) is False


def test_the_status_is_410_not_500_or_404():
    # 404 would say "no such endpoint"; 500 "we failed"; 410 "it existed and was
    # intentionally removed", which is the only one of the three that is true.
    assert retired_store.ABSENT_HTTP_STATUS == 410


def test_payload_is_stable_and_machine_readable():
    payload = retired_store.absent_payload(
        "stack-wecare-digital-Example", what="Example history", retired="Deleted 2026-09-20.")
    assert payload["storeAbsent"] is True
    assert payload["errorCode"] == "RETIRED_STORE_ABSENT"
    assert payload["sourceTable"] == "stack-wecare-digital-Example"
    assert "Deleted 2026-09-20." in payload["note"]
    # It must say retrying is pointless, because the natural reaction to an error
    # is to retry, and here that is wasted work forever.
    assert "retrying will not recover it" in payload["note"]


# ---------------------------------------------------------------------------
# legacy_history against an absent table
# ---------------------------------------------------------------------------

@pytest.fixture
def absent(monkeypatch):
    monkeypatch.setattr(legacy_history, "_table", lambda: AbsentTable())


def test_list_messages_reports_absence_instead_of_raising(absent):
    result = legacy_history.list_messages()
    assert result["storeAbsent"] is True
    assert result["messages"] == []
    assert result["count"] == 0
    assert result["errorCode"] == "RETIRED_STORE_ABSENT"


def test_counts_by_provider_does_not_report_zero_rows_exactly(absent):
    """The distinction that matters most in this file.

    `counts_by_provider` is the checksum a deletion decision is justified
    against. Reporting `total: 0, exact: True` for a table that is gone would
    read as evidence that there was never anything to lose — the opposite of
    what happened.
    """
    result = legacy_history.counts_by_provider()
    assert result["storeAbsent"] is True
    assert result.get("exact") is not True
    assert "total" not in result or result.get("total") in (None, 0)
    assert result["errorCode"] == "RETIRED_STORE_ABSENT"


def test_get_message_collapses_to_none(absent):
    """For a single-id lookup, "gone" and "no such row" are the same answer.

    Either way the record cannot be retrieved, so there is nothing for the caller
    to do differently. The list and counts paths do distinguish them, because
    there the difference IS the answer.
    """
    assert legacy_history.get_message("m1") is None


def test_purge_reports_zero_deleted_rather_than_claiming_success(absent):
    result = legacy_history.purge(confirm_table=legacy_history.LEGACY_SMS_TABLE)
    assert result["storeAbsent"] is True
    assert result["deleted"] == 0
    assert result["alreadyAbsent"] is True


def test_purge_still_refuses_without_the_typed_confirmation(absent):
    """The absence check must not short-circuit the destructive-intent guard."""
    result = legacy_history.purge(confirm_table="")
    assert result["errorCode"] == "CONFIRMATION_REQUIRED"
    assert "storeAbsent" not in result


def test_a_real_fault_still_raises(monkeypatch):
    """Absence handling must not become a catch-all.

    If throttling were swallowed as "the store is gone", a transient capacity
    problem would be reported as permanent data loss.
    """
    class Throttled:
        def scan(self, **_kwargs):
            raise FakeThrottling()

    monkeypatch.setattr(legacy_history, "_table", lambda: Throttled())
    with pytest.raises(FakeThrottling):
        legacy_history.list_messages()
