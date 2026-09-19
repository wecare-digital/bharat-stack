"""The two live capabilities rescued from the retired India sender.

Retiring `sms-in/airtel` would have taken two things with it that are not
Airtel-specific:

  1. the TRAI DLT template registry - a record of content templates approved by
     the Indian regulator under OUR registered entity, which outlives any carrier;
  2. the only read path for `AirtelSMSTable`, which holds real delivered messages
     from two retired providers and is DLT audit evidence.

These tests pin the behaviour that makes deleting that function safe.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.comms import dlt as dlt_mod              # noqa: E402
from lambda_utils.comms import dlt_registry                 # noqa: E402
from lambda_utils.comms import legacy_history               # noqa: E402


class _FakeTable:
    """Minimal DynamoDB Table double: get/put/update/delete/scan."""

    def __init__(self, items=None, key_name="templateId"):
        self.items = {str(i[key_name]): dict(i) for i in (items or [])}
        self.key_name = key_name
        self.deleted = []
        self.scan_calls = []

    def get_item(self, Key):
        found = self.items.get(str(Key[self.key_name]))
        return {"Item": dict(found)} if found else {}

    def put_item(self, Item):
        self.items[str(Item[self.key_name])] = dict(Item)
        return {}

    def update_item(self, **kwargs):
        key = str(kwargs["Key"][self.key_name])
        if "ConditionExpression" in kwargs and key not in self.items:
            from botocore.exceptions import ClientError
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        row = self.items.setdefault(key, {self.key_name: key})
        values = kwargs.get("ExpressionAttributeValues", {})
        names = kwargs.get("ExpressionAttributeNames", {})
        for assignment in kwargs["UpdateExpression"][4:].split(", "):
            field, placeholder = [p.strip() for p in assignment.split("=")]
            row[names.get(field, field)] = values[placeholder]
        return {"Attributes": dict(row)}

    def delete_item(self, Key):
        self.deleted.append(str(Key[self.key_name]))
        self.items.pop(str(Key[self.key_name]), None)
        return {}

    def scan(self, **kwargs):
        self.scan_calls.append(kwargs)
        return {"Items": [dict(v) for v in self.items.values()]}

    def batch_writer(self):
        table = self

        class _Batch:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def delete_item(self_inner, Key):
                table.delete_item(Key)
        return _Batch()


# ==========================================================================
# DLT template registry
# ==========================================================================
@pytest.fixture
def registry(monkeypatch):
    table = _FakeTable(key_name="templateId")
    monkeypatch.setattr(dlt_registry, "_table", lambda: table)
    return table


def test_variables_are_extracted_in_positional_order():
    """DLT variables are positional in the approved template, so order matters."""
    found = dlt_registry.extract_variables("Hi {#name#}, order {#id#} for {#name#}")
    assert found == ["name", "id"]


def test_create_defaults_to_the_registered_identity(registry):
    created = dlt_registry.create_template({
        "templateId": "1000000000000000001",
        "name": "test-tpl",
        "content": "Hello {#var#}",
    })
    assert created["entityId"] == dlt_mod.ENTITY_ID
    assert created["senderId"] == dlt_mod.SENDER_ID
    assert created["variables"] == ["var"]


def test_create_requires_id_and_content(registry):
    with pytest.raises(dlt_registry.RegistryError):
        dlt_registry.create_template({"content": "x"})
    with pytest.raises(dlt_registry.RegistryError):
        dlt_registry.create_template({"templateId": "1"})


def test_create_rejects_an_invalid_message_type(registry):
    with pytest.raises(dlt_registry.RegistryError) as exc:
        dlt_registry.create_template({
            "templateId": "1", "content": "x", "messageType": "MARKETING"})
    assert exc.value.code == "INVALID_MESSAGE_TYPE"


def test_update_refuses_to_create_a_row(registry):
    """A typo'd id must not silently add a template nobody registered."""
    with pytest.raises(dlt_registry.RegistryError) as exc:
        dlt_registry.update_template({"templateId": "does-not-exist", "name": "x"})
    assert exc.value.code == "NOT_FOUND"


def test_update_rederives_variables_from_new_content(registry):
    dlt_registry.create_template({
        "templateId": "1000000000000000002", "content": "old {#a#}"})
    updated = dlt_registry.update_template({
        "templateId": "1000000000000000002", "content": "new {#b#} {#c#}"})
    assert updated["variables"] == ["b", "c"]


def test_update_cannot_empty_the_content(registry):
    dlt_registry.create_template({
        "templateId": "1000000000000000003", "content": "body"})
    with pytest.raises(dlt_registry.RegistryError):
        dlt_registry.update_template({
            "templateId": "1000000000000000003", "content": ""})


def test_builtin_template_cannot_be_deleted(registry):
    """Deleting it would not stop it being used - dlt.resolve checks builtins first.

    The only effect would be a registry that disagrees with live traffic.
    """
    builtin_id = dlt_mod.TEMPLATES["ivr-default"]
    with pytest.raises(dlt_registry.RegistryError) as exc:
        dlt_registry.delete_template(builtin_id)
    assert exc.value.code == "BUILTIN_TEMPLATE_PROTECTED"
    assert registry.deleted == []


def test_non_builtin_template_can_be_deleted(registry):
    dlt_registry.create_template({
        "templateId": "1000000000000000004", "content": "x"})
    result = dlt_registry.delete_template("1000000000000000004")
    assert result["deleted"] == "1000000000000000004"


def test_list_reports_which_keys_the_send_path_knows(registry):
    dlt_registry.create_template({
        "templateId": "1000000000000000005", "name": "ivr-default", "content": "x"})
    listing = dlt_registry.list_templates()
    assert listing["builtinKeys"] == dlt_mod.known_keys()
    assert listing["templates"][0]["isBuiltinKey"] is True


def test_list_marks_a_non_builtin_name_as_such(registry):
    dlt_registry.create_template({
        "templateId": "1000000000000000006", "name": "something-else", "content": "x"})
    assert dlt_registry.list_templates()["templates"][0]["isBuiltinKey"] is False


# ==========================================================================
# legacy history
# ==========================================================================
LEGACY_ROWS = [
    {"messageId": "m1", "provider": "airtel", "content": "a", "status": "SENT",
     "createdAt": 100, "dltTemplateId": "1007277993798259629"},
    {"messageId": "m2", "provider": "sinch", "content": "b", "status": "FAILED",
     "createdAt": 200},
    {"messageId": "m3", "content": "c", "status": "SENT", "createdAt": 300},
]


@pytest.fixture
def history(monkeypatch):
    table = _FakeTable(LEGACY_ROWS, key_name="messageId")
    monkeypatch.setattr(legacy_history, "_table", lambda: table)
    return table


def test_original_provider_is_preserved_never_relabelled(history):
    rows = {r["messageId"]: r for r in legacy_history.list_messages()["messages"]}
    assert rows["m1"]["provider"] == "airtel"
    assert rows["m2"]["provider"] == "sinch"
    # and specifically NOT rewritten to the current provider
    assert rows["m1"]["provider"] != "aws-end-user-messaging"
    assert rows["m2"]["provider"] != "aws-end-user-messaging"


def test_rows_predating_the_provider_column_are_not_guessed(history):
    rows = {r["messageId"]: r for r in legacy_history.list_messages()["messages"]}
    # Names the route, not a vendor, because the vendor is genuinely unrecorded.
    assert rows["m3"]["provider"] == "legacy-india-operator"
    assert "Unrecorded" in rows["m3"]["providerLabel"]


def test_every_row_is_flagged_historical_and_read_only(history):
    for row in legacy_history.list_messages()["messages"]:
        assert row["isHistorical"] is True
        assert row["readOnly"] is True


def test_retired_providers_are_labelled_as_retired(history):
    rows = {r["messageId"]: r for r in legacy_history.list_messages()["messages"]}
    assert "retired" in rows["m1"]["providerLabel"].lower()
    assert "retired" in rows["m2"]["providerLabel"].lower()


def test_dlt_evidence_fields_survive(history):
    """A DLT dispute needs the template id and the carrier that delivered it."""
    row = legacy_history.get_message("m1")
    assert row["dltTemplateId"] == "1007277993798259629"
    assert row["provider"] == "airtel"


def test_status_filter_escapes_the_reserved_word(history):
    """`status` is a DynamoDB reserved word; unescaped it fails at runtime."""
    legacy_history.list_messages(status="SENT")
    kwargs = history.scan_calls[-1]
    assert "#s" in kwargs["FilterExpression"]
    assert kwargs["ExpressionAttributeNames"]["#s"] == "status"


def test_provider_filter_separates_the_two_retired_senders(history):
    legacy_history.list_messages(provider="sinch")
    kwargs = history.scan_calls[-1]
    assert kwargs["ExpressionAttributeValues"][":p"] == "sinch"


def test_module_exposes_no_create_or_update():
    """History is a statement about the past. Only reads and a retention purge."""
    for forbidden in ("create_message", "update_message", "store_message",
                      "put_message", "send"):
        assert not hasattr(legacy_history, forbidden)


def test_counts_are_exact_and_per_provider(history):
    counts = legacy_history.counts_by_provider()
    assert counts["exact"] is True
    assert counts["total"] == 3
    assert counts["byProvider"] == {
        "airtel": 1, "legacy-india-operator": 1, "sinch": 1}


def test_list_does_not_claim_a_global_ordering(history):
    """It is a paginated scan; a global sort claim would misdescribe the data."""
    assert legacy_history.list_messages()["pageOrderedOnly"] is True


def test_invalid_cursor_is_a_bad_request_not_a_crash(history):
    result = legacy_history.list_messages(cursor="!!!not-base64!!!")
    assert result["errorCode"] == "INVALID_CURSOR"


# --------------------------------------------------------------------------
# purge is guarded
# --------------------------------------------------------------------------
def test_purge_without_confirmation_deletes_nothing(history):
    result = legacy_history.purge(confirm_table="")
    assert result["errorCode"] == "CONFIRMATION_REQUIRED"
    assert history.deleted == []


def test_purge_with_the_wrong_table_name_deletes_nothing(history):
    result = legacy_history.purge(confirm_table="some-other-table")
    assert result["errorCode"] == "CONFIRMATION_REQUIRED"
    assert history.deleted == []


def test_purge_with_exact_confirmation_proceeds(history):
    result = legacy_history.purge(confirm_table=legacy_history.LEGACY_SMS_TABLE)
    assert result["deleted"] == 3
    assert sorted(history.deleted) == ["m1", "m2", "m3"]
