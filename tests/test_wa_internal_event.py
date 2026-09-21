"""The ingress-to-worker contract, and why it still accepts the legacy shape.

Provenance
----------
`wecare-whatsapp-calling` verifies Meta's signature and then forwards non-call
events to `wecare-inbound-whatsapp` by async `lambda_client.invoke`. It wrapped
them in a synthetic SNS envelope:

    {"Records":[{"Sns":{"Message":"{\\"whatsAppWebhookEntry\\": \\"{...}\\"}"}}]}

A fossil of an architecture where Meta delivered through AWS End User Messaging
Social into a topic. Verified on 2026-09-21: no SNS subscription to this function
exists in `amplify/backend.ts`, `amplify/backend-resources.ts`, or the live
event-source mappings, and the AWS account has no linked WABA. The shape described
nothing, cost a double JSON encode, and pointed every reader at a topic that was
never there.

`parse()` keeps the legacy arm deliberately. The two Lambdas deploy separately and
the invoke is asynchronous, so in-flight events can carry the old shape, and
`dlq-replay` may hold stored payloads in it for its retention period. These tests
pin both arms and the equivalence between them.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
FUNCTIONS = ROOT / "amplify" / "functions"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import wa_internal_event as wie  # noqa: E402

ENTRY = {
    "id": "2094615664435155",
    "changes": [{
        "field": "messages",
        "value": {
            "metadata": {"display_phone_number": "919330994400",
                         "phone_number_id": "1016149501586345"},
            "messages": [{"from": "919900000000", "id": "wamid.TEST", "type": "text",
                          "text": {"body": "hello"}}],
        },
    }],
}


def legacy_envelope(entry=ENTRY, waba="2094615664435155",
                    phones=("1016149501586345",), rid="req-1"):
    """Byte-for-byte the shape the old producer built."""
    return {
        "Records": [{
            "Sns": {
                "Message": json.dumps({
                    "context": {"MetaWabaIds": [waba],
                                "MetaPhoneNumberIds": list(phones)},
                    "whatsAppWebhookEntry": json.dumps(entry),
                    "messageId": rid,
                }),
                "MessageId": rid,
            }
        }]
    }


class TestBuild:
    def test_entry_is_a_dict_not_a_json_string(self):
        """The double encoding was the whole complaint."""
        ev = wie.build(entry=ENTRY, waba_id="W1", meta_phone_number_ids=["P1"],
                       request_id="r1")
        assert isinstance(ev["entry"], dict)
        assert ev["entry"]["changes"][0]["field"] == "messages"

    def test_it_is_self_describing(self):
        ev = wie.build(entry=ENTRY, waba_id="W1", meta_phone_number_ids=["P1"],
                       request_id="r1")
        assert ev["source"] == "meta-direct"
        assert ev["version"] == wie.CONTRACT_VERSION
        assert ev["wabaId"] == "W1"
        assert ev["metaPhoneNumberIds"] == ["P1"]
        assert ev["requestId"] == "r1"

    def test_it_mentions_no_sns(self):
        ev = wie.build(entry=ENTRY, waba_id="W1", meta_phone_number_ids=[],
                       request_id="r1")
        assert "Records" not in ev
        assert "Sns" not in json.dumps(ev)

    def test_it_survives_a_json_round_trip(self):
        """It is delivered as an invoke Payload, so it must be serializable."""
        ev = wie.build(entry=ENTRY, waba_id="W1", meta_phone_number_ids=["P1"],
                       request_id="r1")
        assert wie.parse(json.loads(json.dumps(ev)))[0]["entry"] == ENTRY


class TestParseTyped:
    def test_round_trips_build(self):
        ev = wie.build(entry=ENTRY, waba_id="W1", meta_phone_number_ids=["P1", "P2"],
                       request_id="r1")
        items = wie.parse(ev)
        assert len(items) == 1
        it = items[0]
        assert it["shape"] == "typed"
        assert it["entry"] == ENTRY
        assert it["waba_id"] == "W1"
        assert it["waba_ids"] == ["W1"]
        assert it["phone_number_ids"] == ["P1", "P2"]
        assert it["message_id"] == "r1"

    def test_tolerates_a_stringified_entry(self):
        ev = wie.build(entry=ENTRY, waba_id="W1", meta_phone_number_ids=[],
                       request_id="r1")
        ev["entry"] = json.dumps(ENTRY)
        assert wie.parse(ev)[0]["entry"] == ENTRY

    def test_missing_waba_yields_an_empty_list_not_a_none(self):
        ev = wie.build(entry=ENTRY, waba_id="", meta_phone_number_ids=[],
                       request_id="r1")
        assert wie.parse(ev)[0]["waba_ids"] == []


class TestParseLegacy:
    def test_the_old_envelope_still_parses(self):
        items = wie.parse(legacy_envelope())
        assert len(items) == 1
        assert items[0]["shape"] == "legacy-sns"
        assert items[0]["entry"] == ENTRY

    def test_both_shapes_produce_identical_work(self):
        """The equivalence that makes the transition safe."""
        typed = wie.parse(wie.build(entry=ENTRY, waba_id="2094615664435155",
                                    meta_phone_number_ids=["1016149501586345"],
                                    request_id="req-1"))[0]
        legacy = wie.parse(legacy_envelope())[0]
        for key in ("entry", "waba_ids", "waba_id", "phone_number_ids", "message_id"):
            assert typed[key] == legacy[key], key

    def test_multiple_records_become_multiple_items(self):
        env = legacy_envelope()
        env["Records"].append(env["Records"][0])
        assert len(wie.parse(env)) == 2

    def test_an_unparsable_record_is_skipped_not_fatal(self):
        env = legacy_envelope()
        env["Records"].insert(0, {"Sns": {"Message": "not json"}})
        items = wie.parse(env)
        assert len(items) == 1
        assert items[0]["entry"] == ENTRY

    def test_an_unparsable_inner_entry_is_skipped(self):
        env = {"Records": [{"Sns": {"Message": json.dumps({
            "context": {}, "whatsAppWebhookEntry": "{not json", "messageId": "r"})}}]}
        assert wie.parse(env) == []


class TestParseRejections:
    """Never raises: this sits at the top of an async worker, where raising would
    send a poison event to the DLQ on every retry."""

    @pytest.mark.parametrize("bad", [
        {}, {"Records": []}, {"foo": "bar"}, None, "a string", 42, [],
        {"requestContext": {"http": {"method": "POST"}}, "body": "{}"},
    ])
    def test_unrecognised_input_returns_empty(self, bad):
        assert wie.parse(bad) == []

    def test_is_internal_event_distinguishes_an_http_request(self):
        http_event = {"requestContext": {"http": {"method": "POST"},
                                        "apiId": "zllr9lrg7j"},
                      "body": "{}", "headers": {}}
        assert wie.is_internal_event(http_event) is False
        assert wie.is_internal_event(legacy_envelope()) is True
        assert wie.is_internal_event(
            wie.build(entry=ENTRY, waba_id="W", meta_phone_number_ids=[],
                      request_id="r")) is True


class TestWiring:
    PRODUCER = (FUNCTIONS / "messaging" / "whatsapp-calling" / "handler.py").read_text()
    CONSUMER = (FUNCTIONS / "messaging" / "inbound-whatsapp-handler"
                / "handler.py").read_text()

    def test_producer_builds_the_typed_event(self):
        assert "wa_internal_event.build(" in self.PRODUCER

    def test_producer_no_longer_fabricates_an_sns_envelope(self):
        assert "'Records': [{" not in self.PRODUCER
        assert "'Sns': {" not in self.PRODUCER

    def test_consumer_parses_through_the_shared_contract(self):
        assert "wa_internal_event.parse(event)" in self.CONSUMER

    def test_consumer_no_longer_reaches_into_sns_itself(self):
        assert "record.get('Sns', {}).get('Message'" not in self.CONSUMER

    def test_consumer_logs_which_shape_arrived(self):
        """So the legacy arm's retirement can be measured, not guessed."""
        assert "'shapes'" in self.CONSUMER

    def test_unrecognised_events_are_reported(self):
        assert "inbound_unrecognised_event" in self.CONSUMER

    def test_the_dlq_payload_is_replayable(self):
        """dlq-replay invokes the stored payload directly, so it must be a shape
        parse() accepts - it previously stored half an SNS envelope.

        Anchored on the record-level error path. There is an EARLIER
        `_send_to_dlq` for the timeout guard which stores
        `{'messages': [...]}`; that shape is still not replayable and is
        tracked separately rather than half-fixed here.
        """
        idx = self.CONSUMER.index("record_processing_error")
        window = self.CONSUMER[idx:idx + 900]
        assert "_send_to_dlq(" in window
        assert "wa_internal_event.build(" in window

    def test_the_timeout_guard_dlq_shape_is_a_known_gap(self):
        """Documented so it is not mistaken for fixed. parse() rejects it."""
        assert wie.parse({"messages": [{"id": "wamid.X"}]}) == []
        assert "'timeout_guard'" in self.CONSUMER

    def test_no_stale_loop_variable_survived_the_refactor(self):
        """`record` was the old loop variable; a leftover reference would be a
        NameError on the error path only."""
        idx = self.CONSUMER.index("record_processing_error")
        window = self.CONSUMER[idx:idx + 700]
        assert "_send_to_dlq(record," not in window
