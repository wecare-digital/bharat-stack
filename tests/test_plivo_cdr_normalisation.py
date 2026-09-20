"""Plivo CDR rows must be readable by the CDR dashboard, not just present.

Regression guard for a silent failure. `plivo-answer._persist_cdr` had been
writing rows into VoiceCDRTable since the Plivo migration, in snake_case only.
Every read path (voice-cdr-read._format_record_for_ui, _calculate_stats, and the
CDR tab) binds to camelCase Airtel-era names, so those rows were in the table and
invisible in the product:

  * blank caller / destination / status cells
  * no date at all - there was no `createdAt`, which is BOTH the sort key for the
    read paths and the fallback the date renderer uses when `timestamp` is absent,
    so every Plivo row sorted to 0 and fell off the bottom of a limited page
  * they inflated `stats.total` while counting as neither inbound nor outbound
    and neither answered nor missed

Nothing raised. The tests below assert the reader-facing contract rather than the
storage call, because "put_item was called" was already true while the feature
was broken.
"""

from __future__ import annotations

import pathlib
import sys
from decimal import Decimal

import pytest

SHARED = pathlib.Path(__file__).resolve().parents[1] / "amplify/functions/shared"
FN = pathlib.Path(__file__).resolve().parents[1] / "amplify/functions/messaging/plivo-answer"
for p in (SHARED, FN):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import handler as plivo  # noqa: E402


class _FakeTable:
    def __init__(self):
        self.items = []

    def put_item(self, Item):  # noqa: N803 - boto3 kwarg name
        self.items.append(Item)


@pytest.fixture()
def captured(monkeypatch):
    table = _FakeTable()
    monkeypatch.setattr(plivo, "_table", lambda: table)
    # The breadcrumb writes to a different table; capture it instead of reaching out.
    calls = []
    import lambda_utils.message_store as ms

    monkeypatch.setattr(ms, "put_call_breadcrumb", lambda **kw: calls.append(kw))
    table.breadcrumbs = calls
    return table


def _persist(captured, **params):
    assert plivo._persist_cdr(params, "hangup", "req-1") is True
    return captured.items[-1]


# --------------------------------------------------------------------------
# the fields that made Plivo rows invisible
# --------------------------------------------------------------------------

def test_createdAt_is_written_so_the_row_can_sort_and_render_a_date(captured):
    """createdAt is the sort key AND the date fallback. Missing it hid the row twice."""
    item = _persist(captured, CallUUID="u1", From="+919876543210",
                    To="+918031830030", Direction="inbound",
                    CallStatus="completed", Duration="42")
    assert "createdAt" in item
    assert float(item["createdAt"]) > 0
    # the reader parses `timestamp` with '%Y-%m-%d %H:%M:%S'
    import datetime
    datetime.datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S")


def test_camelcase_number_fields_are_populated(captured):
    item = _persist(captured, CallUUID="u2", From="+919876543210",
                    To="+918031830030", Direction="inbound",
                    CallStatus="completed", Duration="10")
    assert item["callerNumber"] == "+919876543210"
    assert item["destinationNumber"] == "+918031830030"


def test_callType_is_the_uppercase_vocabulary_the_readers_filter_on(captured):
    """Plivo says 'inbound'; _calculate_stats compares against 'INBOUND'."""
    inbound = _persist(captured, CallUUID="u3", Direction="inbound",
                       CallStatus="completed", Duration="5")
    assert inbound["callType"] == "INBOUND"
    outbound = _persist(captured, CallUUID="u4", Direction="outbound",
                        CallStatus="completed", Duration="5")
    assert outbound["callType"] == "OUTBOUND"


def test_outbound_api_direction_still_maps_to_OUTBOUND(captured):
    """Plivo reports 'outbound-api' for API-originated calls."""
    item = _persist(captured, CallUUID="u5", Direction="outbound-api",
                    CallStatus="completed", Duration="5")
    assert item["callType"] == "OUTBOUND"


def test_unknown_direction_does_not_invent_a_call_type(captured):
    item = _persist(captured, CallUUID="u6", Direction="", CallStatus="completed",
                    Duration="5")
    assert "callType" not in item  # empty values are stripped, not guessed


# --------------------------------------------------------------------------
# status mapping
# --------------------------------------------------------------------------

@pytest.mark.parametrize("plivo_status,expected", [
    ("busy", "Busy"),
    ("no-answer", "Missed"),
    ("failed", "Missed"),
    ("cancel", "Missed"),
    ("timeout", "Missed"),
])
def test_unsuccessful_statuses_map_to_the_reader_vocabulary(captured, plivo_status,
                                                            expected):
    item = _persist(captured, CallUUID=f"s-{plivo_status}", Direction="inbound",
                    CallStatus=plivo_status)
    assert item["overallCallStatus"] == expected


def test_completed_with_talk_time_is_answered(captured):
    item = _persist(captured, CallUUID="u7", Direction="inbound",
                    CallStatus="completed", Duration="37")
    assert item["overallCallStatus"] == "Answered"


def test_completed_with_zero_duration_is_missed_not_answered(captured):
    """Plivo reports `completed` on a normal teardown whether or not anyone
    picked up. Trusting it blindly overstates the answer rate."""
    item = _persist(captured, CallUUID="u8", Direction="inbound",
                    CallStatus="completed", Duration="0")
    assert item["overallCallStatus"] == "Missed"


# --------------------------------------------------------------------------
# durations
# --------------------------------------------------------------------------

def test_duration_strings_become_numeric_seconds_and_millis(captured):
    """Plivo sends Duration as a string; the UI does float maths on durationSec."""
    item = _persist(captured, CallUUID="u9", Direction="inbound",
                    CallStatus="completed", Duration="90")
    assert item["durationSec"] == Decimal("90")
    assert item["durationMs"] == Decimal("90000")
    assert item["conversationDurationSec"] == Decimal("90")
    assert item["billableDurationSec"] == Decimal("90")


def test_billduration_is_used_when_duration_is_absent(captured):
    item = _persist(captured, CallUUID="u10", Direction="inbound",
                    CallStatus="completed", BillDuration="60")
    assert item["durationSec"] == Decimal("60")


def test_nonnumeric_duration_does_not_raise(captured):
    item = _persist(captured, CallUUID="u11", Direction="inbound",
                    CallStatus="completed", Duration="not-a-number")
    assert item["durationSec"] == Decimal("0")


# --------------------------------------------------------------------------
# invariants that must not regress
# --------------------------------------------------------------------------

def test_source_stays_plivo_because_the_table_is_shared(captured):
    """VoiceCDRTable holds Plivo and historical retired-provider rows.
    `source` is the only discriminator."""
    item = _persist(captured, CallUUID="u12", Direction="inbound",
                    CallStatus="completed", Duration="5")
    assert item["source"] == "plivo"
    assert item["id"] == "plivo#u12"


def test_snake_case_keys_are_retained_for_preexisting_rows(captured):
    """Rows written before normalisation carry these. A later callback for the
    same call must not strip them."""
    item = _persist(captured, CallUUID="u13", From="+911", To="+912",
                    Direction="inbound", CallStatus="completed", Duration="5")
    for key in ("call_uuid", "from_number", "to_number", "call_status",
                "received_at"):
        assert key in item


def test_missing_call_uuid_is_refused(captured):
    assert plivo._persist_cdr({"CallStatus": "completed"}, "hangup", "r") is False
    assert captured.items == []


def test_breadcrumb_is_written_as_plivo_not_airtel(captured):
    """src/pages/dm/calls keys its provider badge on this value."""
    _persist(captured, CallUUID="u14", From="+919876543210", To="+918031830030",
             Direction="inbound", CallStatus="completed", Duration="12")
    assert captured.breadcrumbs, "no breadcrumb written"
    assert captured.breadcrumbs[-1]["call_type"] == "plivo"


def test_breadcrumb_failure_does_not_lose_the_cdr(captured, monkeypatch):
    """The CDR is the record of record; a timeline nicety must not discard it."""
    import lambda_utils.message_store as ms

    def _boom(**kw):
        raise RuntimeError("messages table unavailable")

    monkeypatch.setattr(ms, "put_call_breadcrumb", _boom)
    assert plivo._persist_cdr(
        {"CallUUID": "u15", "Direction": "inbound", "CallStatus": "completed",
         "Duration": "5"}, "hangup", "r") is True
    assert captured.items[-1]["id"] == "plivo#u15"


def test_persist_returns_false_when_the_table_write_fails(captured, monkeypatch):
    def _boom(Item):  # noqa: N803
        raise RuntimeError("throughput exceeded")

    monkeypatch.setattr(captured, "put_item", _boom)
    assert plivo._persist_cdr(
        {"CallUUID": "u16", "Direction": "inbound", "CallStatus": "completed"},
        "hangup", "r") is False
