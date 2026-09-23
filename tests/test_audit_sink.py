"""The audit log was writing to the wrong key, and failing open hid it completely.

Measured 2026-09-23 against account 775261844268:

    stack-wecare-digital-AuditLogsTable   KeySchema: [('id', 'HASH')]
                                          ItemCount: 0

`lambda_utils.audit.record_audit` built its item with `logId` and never set `id`, so
every `put_item` raised

    ValidationException: One of the required keys was not given a value

and the helper's `except Exception` returned None. Not one audit record has ever
been stored. The helper declares 30-plus canonical actions - `template.create`,
`payment.refund`, `secret.update`, `dlq.replay`, `phone.register`, `phone.migrate`,
`flow.publish` - across 17 call sites in `partner-onboarding` and `waba-management`.
All of them have been writing into nothing.

Why the mismatch existed
------------------------
`amplify/data/resource.ts` declares `AuditLog` with `.identifier(['logId'])`, and the
helper was written against that declaration. But that file has never been deployed -
there is no AppSync API and no Amplify data stack in the account - so the live table
was created by a provisioning script with an `id` key. The declaration and reality
disagreed, and a fail-open helper meant nothing ever surfaced the disagreement.

The fix follows the pattern this repo already uses for the same problem: `id` is the
physical key and `logId` is a mirrored alias, exactly as `lambda_utils.contact_key`
handles `id`/`contactId`. Both are written, so a reader expecting either spelling
works, and they cannot diverge because one helper sets both.

Fail-open stays, because an audit write must not break a request. What changes is
that it can no longer be silently wrong forever: the shape is asserted here, and the
warning it emits is asserted too.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

SHARED = pathlib.Path(__file__).resolve().parents[1] / "amplify/functions/shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

import lambda_utils.audit as audit  # noqa: E402


class LiveShapedTable:
    """The table as it actually exists: partition key `id`, nothing else required."""

    def __init__(self):
        self.items = []

    def put_item(self, Item):  # noqa: N803
        if "id" not in Item:
            raise RuntimeError(
                "ValidationException: One of the required keys was not given a value")
        if not isinstance(Item["id"], str) or not Item["id"]:
            raise RuntimeError("ValidationException: key must be a non-empty string")
        self.items.append(Item)


@pytest.fixture()
def table(monkeypatch):
    live = LiveShapedTable()

    class FakeResource:
        def Table(self, name):  # noqa: N802
            live.name = name
            return live

    monkeypatch.setattr(audit, "_dynamodb", FakeResource())
    return live


def test_the_write_lands_in_the_table(table):
    """The assertion that was missing. Before the fix this returned None and the
    table stayed empty, on every call, in every function, forever."""
    log_id = audit.record_audit(action="template.create", actor="u1",
                                resource_type="template", resource_id="t1")
    assert log_id, "record_audit returned None - the write was swallowed again"
    assert len(table.items) == 1


def test_the_item_carries_the_physical_key(table):
    audit.record_audit(action="template.create", actor="u1")
    item = table.items[0]
    assert "id" in item, "the live table's partition key is `id`"
    assert item["id"]


def test_the_alias_is_written_too_and_matches(table):
    """`resource.ts` declares the identifier as `logId`, and a reader may use either
    spelling. One helper sets both, so they cannot diverge - the same reasoning as
    contact_key's `id`/`contactId` pair."""
    audit.record_audit(action="template.create", actor="u1")
    item = table.items[0]
    assert item["logId"] == item["id"]


def test_the_returned_id_is_the_stored_id(table):
    """A caller that logs the returned id must be able to find the row with it."""
    log_id = audit.record_audit(action="template.create", actor="u1")
    assert table.items[0]["id"] == log_id


def test_the_targeted_table_is_the_live_one(table):
    audit.record_audit(action="template.create")
    assert table.name == "stack-wecare-digital-AuditLogsTable"


def test_every_declared_action_writes_successfully(table):
    """All 30-plus canonical actions, not just one. Each was silently lost."""
    for action in sorted(audit.ACTIONS):
        assert audit.record_audit(action=action, actor="u1"), action
    assert len(table.items) == len(audit.ACTIONS)


def test_details_are_json_and_secret_masked(table):
    audit.record_audit(action="secret.update", actor="u1",
                       details={"api_key": "sk-not-a-real-key-000000000000",
                                "harmless": "visible"})
    stored = json.loads(table.items[0]["details"])
    assert stored["harmless"] == "visible"
    assert "sk-not-a-real-key" not in json.dumps(stored)


def test_an_absent_actor_becomes_system_rather_than_an_empty_key(table):
    audit.record_audit(action="dlq.replay")
    assert table.items[0]["userId"] == "system"


def test_a_ttl_is_set_so_the_table_does_not_grow_without_bound(table):
    audit.record_audit(action="template.create")
    assert int(table.items[0]["expiresAt"]) > 0


# --------------------------------------------------------------------------
# fail-open stays, but stops being invisible
# --------------------------------------------------------------------------
def test_a_write_failure_still_does_not_raise(table, monkeypatch):
    """An audit write must not break the request it is auditing."""
    def boom(Item):  # noqa: N803
        raise RuntimeError("throughput exceeded")

    monkeypatch.setattr(table, "put_item", boom)
    assert audit.record_audit(action="template.create") is None


def test_a_write_failure_is_logged_so_it_cannot_hide_forever(table, monkeypatch, caplog):
    """The reason this bug survived. Fail-open is fine; fail-open and silent is not,
    and the only way anyone would have found this is by noticing an empty table."""
    def boom(Item):  # noqa: N803
        raise RuntimeError("ValidationException: key missing")

    monkeypatch.setattr(table, "put_item", boom)
    with caplog.at_level("WARNING"):
        audit.record_audit(action="template.create")
    assert "audit_write_failed" in caplog.text


def test_the_helper_does_not_drop_the_key_when_a_value_is_empty(table):
    """`record_audit` strips empty values before writing, which is how a key could be
    omitted in the first place. `id` must survive that filter unconditionally."""
    audit.record_audit(action="template.create", actor="", resource_type="",
                       resource_id="", details=None)
    item = table.items[0]
    assert item["id"] and item["logId"] == item["id"]
