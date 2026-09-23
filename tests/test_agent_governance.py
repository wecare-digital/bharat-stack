"""The AI action group's powers, and the fact that most of them are now refused.

What this replaces
------------------
`ai/agent-action-group` could, driven by an LLM's choice of tool:

  1. SEND directly - `sendWhatsApp`, `sendSms`, `sendEmail` each invoked
     `wecare-outbound-*` with a phone number and a body. No plan, no approval, no
     receipt. The model decided a real customer got a real message.
  2. SCAN whole tables - `searchContacts` paginated the ENTIRE ContactsTable to
     exhaustion and then filtered in Python; `getStats` did three exhaustive
     scans; `getMessages` scanned both message tables.
  3. DELETE data - `deleteMessage` hard-deleted from the message store;
     `deleteContact` claimed a soft delete.
  4. Report PLACEHOLDER success - `createInvoice` returned
     `{'success': True, 'invoiceId': 'INV-xxxxxxxx'}` and wrote nothing at all.

Three bugs were hiding inside those powers, each of which only matters because the
power existed:

  * `_delete_message` wrapped the inbound delete in `try/except: pass` and then
    deleted from outbound. DynamoDB's `delete_item` SUCCEEDS on a key that does not
    exist, so the inbound attempt never raised, the outbound branch was
    unreachable, and the function reported "deleted successfully" for any id at
    all - including one that never existed.
  * `_delete_contact` used `update_item ... SET deletedAt` with no existence
    check. DynamoDB upserts, so calling it with an unknown id CREATED a row
    holding nothing but `{id, deletedAt}`. A delete that manufactures records.
  * `_find_contact_by_phone` scanned with `contains(phone, ...)` and `Limit=1`.
    `Limit` is applied BEFORE the FilterExpression, so it examined one arbitrary
    item and filtered it out - normally finding nobody. And `contains` on the last
    10 digits is a substring match, so when it did match it could match the wrong
    number. Measured: ContactsTable has a `phone-index` GSI with an ALL
    projection, so the scan was never necessary in the first place.

The governing rule
------------------
READ and status tools are enabled. Every APPLY tool is refused, structurally -
there is no flag to flip, because the approval, plan-hash and receipt machinery
that would make an APPLY safe does not exist yet (plan item 6.2 builds it). A
flag added now would be a switch nobody could safely throw.

A refusal is not a failure and must never be shaped like a success. The whole
lesson of `createInvoice` is that a confident `success: True` is worse than an
error, because the agent repeats it to a person.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

SHARED = pathlib.Path(__file__).resolve().parents[1] / "amplify/functions/shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.agent import governance as gov  # noqa: E402

# The eight powers the brief requires removed, by tool name.
SENDERS = ("sendWhatsApp", "sendSms", "sendEmail")
DELETERS = ("deleteContact", "deleteMessage")
WRITERS = ("createContact", "updateContact")
FABRICATORS = ("createInvoice",)
ALL_APPLY = SENDERS + DELETERS + WRITERS + FABRICATORS

READERS = ("getContact", "searchContacts", "getMessages", "getStats")


# ==========================================================================
# the catalog is complete and self-describing
# ==========================================================================
def test_every_tool_has_a_class_and_a_summary():
    assert gov.CATALOG, "the catalog is empty"
    for name, tool in gov.CATALOG.items():
        assert tool.name == name, f"{name} disagrees with its key"
        assert tool.tool_class in (gov.CLASS_READ, gov.CLASS_PLAN, gov.CLASS_APPLY)
        assert tool.summary.strip(), f"{name} has no summary"


def test_the_catalog_covers_exactly_the_known_tools():
    assert set(gov.CATALOG) == set(READERS) | set(ALL_APPLY)


def test_no_apply_tool_is_enabled():
    """The load-bearing assertion. If this ever passes vacuously, the one below
    catches it."""
    enabled_apply = [t.name for t in gov.CATALOG.values()
                     if t.tool_class == gov.CLASS_APPLY and t.enabled]
    assert enabled_apply == [], f"APPLY tools are enabled: {enabled_apply}"


def test_there_are_apply_tools_to_disable():
    """Guards against the previous test passing because the class is unused."""
    apply_tools = [t.name for t in gov.CATALOG.values()
                   if t.tool_class == gov.CLASS_APPLY]
    assert len(apply_tools) >= 8, apply_tools


def test_read_tools_are_enabled():
    for name in READERS:
        assert gov.CATALOG[name].enabled, f"{name} is a READ and should work"
        assert gov.CATALOG[name].tool_class == gov.CLASS_READ


@pytest.mark.parametrize("name", ALL_APPLY)
def test_each_removed_power_is_classified_apply_and_refused(name):
    tool = gov.resolve(name)
    assert tool.tool_class == gov.CLASS_APPLY
    assert tool.enabled is False
    assert tool.refusal.strip(), f"{name} is refused without saying why"


@pytest.mark.parametrize("name", SENDERS)
def test_the_refusal_for_a_sender_names_the_missing_approval_path(name):
    """Not "disabled" - the reader needs to know what would make it safe."""
    assert gov.resolve(name).refusal.lower().count("approval") >= 1


def test_the_invoice_detail_points_at_the_real_invoice_path(name="createInvoice"):
    """It fabricated an id. Somewhere must say where a real invoice comes from, or
    the next person reimplements the placeholder.

    It belongs in `detail` rather than `refusal`: a function name is topology, and
    `refusal` travels back through Bedrock into a prompt and then a transcript.
    """
    tool = gov.resolve(name)
    assert "invoice-engine" in tool.detail
    assert "invoice-engine" not in tool.refusal


@pytest.mark.parametrize("name", ALL_APPLY)
def test_every_refusal_has_operator_forensics_behind_it(name):
    """The model-facing line is short by design, so the reason the power was
    removed has to live somewhere it will not be lost."""
    tool = gov.resolve(name)
    assert len(tool.detail.strip()) >= 60, f"{name} has no operator detail"


@pytest.mark.parametrize("name", ALL_APPLY)
def test_the_model_facing_refusal_carries_no_topology(name):
    """Anything in `refusal` ends up in a prompt. Table names, function names and
    API semantics are not a model's business."""
    text = gov.resolve(name).refusal.lower()
    for leak in ("stack-wecare-digital", "wecare-outbound", "dynamodb",
                 "update_item", "delete_item", "arn:aws", "invoice-engine",
                 "lambda", "gsi"):
        assert leak not in text, f"{name} refusal leaks {leak}"


@pytest.mark.parametrize("name", ALL_APPLY)
def test_the_refusal_tells_the_model_not_to_claim_it_happened(name):
    """The createInvoice lesson generalised. A refused tool that merely says "no"
    still leaves a model free to narrate a success, so each refusal either forbids
    the claim or routes the request to a person."""
    text = gov.resolve(name).refusal.lower()
    assert ("do not state" in text or "ask a person" in text
            or "let a person" in text or "only a person" in text
            or "hand it to a person" in text), gov.resolve(name).refusal


# ==========================================================================
# refusals are not successes
# ==========================================================================
@pytest.mark.parametrize("name", ALL_APPLY)
def test_assert_executable_raises_for_every_disabled_tool(name):
    with pytest.raises(gov.ToolRefused) as excinfo:
        gov.assert_executable(name)
    err = excinfo.value
    assert err.tool == name
    assert err.tool_class == gov.CLASS_APPLY
    assert err.reason.strip()


@pytest.mark.parametrize("name", READERS)
def test_assert_executable_allows_every_read_tool(name):
    assert gov.assert_executable(name).name == name


@pytest.mark.parametrize("name", ALL_APPLY)
def test_a_refusal_never_serialises_as_success(name):
    """`createInvoice` returned success: True having written nothing, and the agent
    repeated that to a person. No refusal may take that shape."""
    with pytest.raises(gov.ToolRefused) as excinfo:
        gov.assert_executable(name)
    payload = excinfo.value.as_result()
    assert payload["success"] is False
    assert payload["refused"] is True
    assert payload["toolClass"] == gov.CLASS_APPLY
    assert payload["tool"] == name
    assert payload["error"].strip()
    # No key that a caller could mistake for a completed side effect.
    for forbidden in ("invoiceId", "messageId", "contactId", "sentAt", "deleted"):
        assert forbidden not in payload


def test_an_unknown_tool_is_refused_rather_than_guessed():
    with pytest.raises(gov.ToolUnknown):
        gov.resolve("dropAllTables")
    with pytest.raises(gov.ToolUnknown):
        gov.assert_executable("")


def test_the_catalog_summary_is_safe_to_hand_to_a_model():
    summary = gov.catalog_summary()
    assert set(summary["enabled"]) == set(READERS)
    assert set(summary["refused"]) == set(ALL_APPLY)
    # A model should be told the class, never a table name, function name or ARN.
    blob = str(summary).lower()
    for leak in ("stack-wecare-digital", "wecare-outbound", "arn:aws", "dynamodb"):
        assert leak not in blob, f"catalog summary leaks {leak}"


# ==========================================================================
# bounded reads — the scan powers, replaced rather than kept
# ==========================================================================
@pytest.mark.parametrize("requested,expected", [
    (None, gov.DEFAULT_READ_LIMIT),
    (0, gov.DEFAULT_READ_LIMIT),
    ("", gov.DEFAULT_READ_LIMIT),
    ("not a number", gov.DEFAULT_READ_LIMIT),
    (-5, gov.DEFAULT_READ_LIMIT),
    (1, 1),
    (10, 10),
    (gov.MAX_READ_LIMIT, gov.MAX_READ_LIMIT),
    (gov.MAX_READ_LIMIT + 1, gov.MAX_READ_LIMIT),
    (10 ** 9, gov.MAX_READ_LIMIT),
])
def test_bounded_limit_clamps_every_input(requested, expected):
    assert gov.bounded_limit(requested) == expected


def test_the_maximum_read_limit_is_small_enough_to_be_a_bound():
    """A "limit" of ten thousand is an exhaustive scan with extra steps."""
    assert gov.MAX_READ_LIMIT <= 100
    assert gov.DEFAULT_READ_LIMIT <= gov.MAX_READ_LIMIT


class _FakeTable:
    """Records how it was called. Pages forever if allowed to."""

    def __init__(self, total=500):
        self.total = total
        self.scan_calls = []
        self.query_calls = []

    def scan(self, **kwargs):
        self.scan_calls.append(kwargs)
        limit = kwargs.get("Limit", self.total)
        start = int((kwargs.get("ExclusiveStartKey") or {}).get("id", 0))
        items = [{"id": str(i)} for i in range(start, min(start + limit, self.total))]
        out = {"Items": items, "Count": len(items)}
        if start + len(items) < self.total:
            out["LastEvaluatedKey"] = {"id": str(start + len(items))}
        return out

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return {"Items": [{"id": "found"}], "Count": 1}


def test_read_page_reads_one_page_and_stops():
    """The old code looped `while True` on LastEvaluatedKey. On a table of any real
    size that is an exhaustive scan billed per read, driven by a model's whim."""
    table = _FakeTable(total=500)
    items, truncated = gov.read_page(table, limit=25)
    assert len(items) == 25
    assert truncated is True, "a truncated read must say so rather than imply totality"
    assert len(table.scan_calls) == 1, "read_page paginated"


def test_read_page_passes_the_limit_to_dynamodb_not_just_python():
    """Slicing in Python still pays for and transfers the whole table."""
    table = _FakeTable(total=500)
    gov.read_page(table, limit=25)
    assert table.scan_calls[0]["Limit"] == 25


def test_read_page_reports_not_truncated_when_the_table_is_exhausted():
    table = _FakeTable(total=5)
    items, truncated = gov.read_page(table, limit=25)
    assert len(items) == 5
    assert truncated is False


def test_read_page_clamps_a_caller_supplied_limit():
    table = _FakeTable(total=500)
    items, _ = gov.read_page(table, limit=10 ** 6)
    assert len(items) <= gov.MAX_READ_LIMIT
    assert table.scan_calls[0]["Limit"] <= gov.MAX_READ_LIMIT


def test_read_page_never_accepts_an_exclusive_start_key_from_a_caller():
    """Resuming a scan across invocations is how a bounded read becomes an
    unbounded one, one page per model turn."""
    table = _FakeTable(total=500)
    with pytest.raises(ValueError):
        gov.read_page(table, limit=25, ExclusiveStartKey={"id": "100"})


def test_query_index_uses_the_index_rather_than_scanning():
    """ContactsTable has phone-index and email-index with ALL projections, so the
    lookup scans were never needed."""
    table = _FakeTable()
    items = gov.query_index(table, index_name="phone-index",
                            key_name="phone", value="+918100640044", limit=1)
    assert items == [{"id": "found"}]
    assert table.scan_calls == [], "query_index fell back to a scan"
    call = table.query_calls[0]
    assert call["IndexName"] == "phone-index"
    assert call["Limit"] == 1


def test_query_index_is_an_exact_match_not_a_substring():
    """`contains(phone, last10)` could match a different number that happens to
    contain those digits. An index Query cannot."""
    table = _FakeTable()
    gov.query_index(table, index_name="phone-index", key_name="phone",
                    value="+918100640044", limit=1)
    expression = str(table.query_calls[0].get("KeyConditionExpression"))
    assert "contains" not in expression.lower()


def test_query_index_refuses_an_empty_value():
    table = _FakeTable()
    with pytest.raises(ValueError):
        gov.query_index(table, index_name="phone-index", key_name="phone",
                        value="", limit=1)
    assert table.query_calls == []


# ==========================================================================
# the handler — the removed powers are gone, not guarded
# ==========================================================================
import importlib.util  # noqa: E402

_HANDLER_PATH = (pathlib.Path(__file__).resolve().parents[1]
                 / "amplify/functions/ai/agent-action-group/handler.py")


@pytest.fixture()
def agent(monkeypatch):
    """The handler with DynamoDB and auth stubbed. No network, no AWS."""
    spec = importlib.util.spec_from_file_location("agent_action_under_test",
                                                  _HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakeTable:
        def __init__(self, name):
            self.name = name
            self.scans = []
            self.queries = []
            self.gets = []
            self.items = []

        def scan(self, **kwargs):
            self.scans.append(kwargs)
            return {"Items": list(self.items)}

        def query(self, **kwargs):
            self.queries.append(kwargs)
            return {"Items": list(self.items)}

        def get_item(self, Key):  # noqa: N803
            self.gets.append(Key)
            return {"Item": self.items[0]} if self.items else {}

        def delete_item(self, **kwargs):
            raise AssertionError("the handler must not be able to delete")

        def put_item(self, **kwargs):
            raise AssertionError("the handler must not be able to write")

        def update_item(self, **kwargs):
            raise AssertionError("the handler must not be able to write")

    tables = {}

    class FakeClient:
        def describe_table(self, TableName):  # noqa: N803
            return {"Table": {"ItemCount": 7}}

    class FakeResource:
        class meta:  # noqa: N801
            client = FakeClient()

        def Table(self, name):  # noqa: N802
            return tables.setdefault(name, FakeTable(name))

    monkeypatch.setattr(module, "dynamodb", FakeResource())

    import lambda_utils.middleware as mw
    monkeypatch.setattr(mw, "require_auth", lambda event: None)

    module._tables = tables
    return module


def _invoke(agent, function=None, api_path=None, **params):
    event = {"actionGroup": "wecare-actions",
             "parameters": [{"name": k, "value": v} for k, v in params.items()]}
    if function:
        event["function"] = function
    if api_path:
        event["apiPath"] = api_path
    response = agent.handler(event, None)
    import json as _json
    body = response["response"]["functionResponse"]["responseBody"]["TEXT"]["body"]
    return _json.loads(body)


def test_the_handler_has_no_sender_left_in_it(agent):
    """Deleted, not guarded. A disabled function that still works is how a power
    comes back the next time someone edits the routing table."""
    for gone in ("_send_whatsapp", "_send_sms", "_send_email", "_create_invoice",
                 "_delete_contact", "_delete_message", "_create_contact",
                 "_update_contact"):
        assert not hasattr(agent, gone), f"{gone} is still defined"


def test_the_handler_holds_no_lambda_client_and_no_outbound_function_name(agent):
    """Removing a capability means removing the means. The IAM role already permits
    lambda:InvokeFunction on wecare-*, so a leftover function name is an
    invitation."""
    assert not hasattr(agent, "lambda_client")
    source = _HANDLER_PATH.read_text()
    assert "OUTBOUND_WHATSAPP_FUNCTION" not in source
    assert "OUTBOUND_SMS_FUNCTION" not in source
    assert "OUTBOUND_EMAIL_FUNCTION" not in source


def test_the_read_table_and_the_catalog_agree(agent):
    """The previous handler had TWO independent routing tables, one for function
    names and one for API paths, so a tool could be reachable by one spelling and
    not the other. A route the catalog does not know about is an ungoverned tool."""
    assert set(agent._READS) == set(gov.catalog_summary()["enabled"])
    assert set(agent._API_PATH_TO_TOOL.values()) == set(gov.CATALOG)


@pytest.mark.parametrize("name", ALL_APPLY)
def test_every_removed_power_is_refused_by_function_name(agent, name):
    result = _invoke(agent, function=name, contactId="c1", message="hello",
                     phone="+918100640044", amount="100")
    assert result["success"] is False
    assert result["refused"] is True
    assert result["toolClass"] == gov.CLASS_APPLY


@pytest.mark.parametrize("api_path,tool", [
    ("/send-whatsapp", "sendWhatsApp"),
    ("/send-sms", "sendSms"),
    ("/send-email", "sendEmail"),
    ("/delete-contact", "deleteContact"),
    ("/delete-message", "deleteMessage"),
    ("/create-invoice", "createInvoice"),
    ("/create-contact", "createContact"),
    ("/update-contact", "updateContact"),
])
def test_every_removed_power_is_refused_by_api_path_too(agent, api_path, tool):
    """The second spelling. Refusing one and not the other refuses nothing."""
    result = _invoke(agent, api_path=api_path, contactId="c1", message="hi")
    assert result["refused"] is True
    assert result["tool"] == tool


def test_an_unknown_tool_lists_what_is_available_without_guessing(agent):
    result = _invoke(agent, function="dropAllTables")
    assert result["success"] is False
    assert result["refused"] is True
    assert set(result["available"]) == set(READERS)


def test_the_refusal_still_uses_the_bedrock_envelope(agent):
    """Bedrock needs the envelope even for a refusal. Returning a bare dict makes
    the agent see a malformed tool result rather than a reason."""
    event = {"function": "sendWhatsApp", "parameters": []}
    response = agent.handler(event, None)
    assert response["messageVersion"] == "1.0"
    assert response["response"]["function"] == "sendWhatsApp"


# --------------------------------------------------------------------------
# reads: bounded, indexed, and honest
# --------------------------------------------------------------------------
def test_a_contact_lookup_by_phone_uses_the_index_not_a_scan(agent):
    table = agent.dynamodb.Table(agent.CONTACTS_TABLE)
    table.items = [{"id": "c1", "name": "A", "phone": "+918100640044"}]
    result = _invoke(agent, function="getContact", phone="+918100640044")
    assert result["success"] is True
    assert table.scans == [], "the lookup scanned"
    assert table.queries[0]["IndexName"] == "phone-index"


def test_a_soft_deleted_contact_is_not_returned(agent):
    table = agent.dynamodb.Table(agent.CONTACTS_TABLE)
    table.items = [{"id": "c1", "name": "A", "deletedAt": "2026-01-01"}]
    assert _invoke(agent, function="getContact", contactId="c1")["success"] is False


def test_a_contact_view_is_an_allowlist_not_the_row(agent):
    """Returning the row hands a model every field the record ever accumulated,
    and from there into a prompt and a transcript."""
    table = agent.dynamodb.Table(agent.CONTACTS_TABLE)
    table.items = [{"id": "c1", "name": "A", "phone": "+91811",
                    "internalRiskScore": 0.97, "provenance": {"name": "google"},
                    "authToken": "should-never-surface"}]
    result = _invoke(agent, function="getContact", contactId="c1")
    assert set(result["contact"]) == {"id", "name", "phone", "email", "createdAt"}


def test_search_sends_a_limit_to_dynamodb_and_reads_one_page(agent):
    table = agent.dynamodb.Table(agent.CONTACTS_TABLE)
    table.items = [{"id": f"c{i}", "name": "Asha"} for i in range(5)]
    result = _invoke(agent, function="searchContacts", query="asha")
    assert result["success"] is True
    assert len(table.scans) == 1, "search paginated"
    assert table.scans[0]["Limit"] <= gov.MAX_READ_LIMIT


def test_search_reports_truncation_rather_than_implying_totality(agent):
    """The old version said "Found N contacts" after reading the whole table. A
    bounded read must not make the same claim."""
    table = agent.dynamodb.Table(agent.CONTACTS_TABLE)

    def truncated_scan(**kwargs):
        table.scans.append(kwargs)
        return {"Items": [{"id": "c1", "name": "Asha"}],
                "LastEvaluatedKey": {"id": "c1"}}

    table.scan = truncated_scan
    result = _invoke(agent, function="searchContacts", query="asha")
    assert result["truncated"] is True
    assert "more may exist" in result["message"]


def test_search_excludes_soft_deleted_rows_at_the_database(agent):
    table = agent.dynamodb.Table(agent.CONTACTS_TABLE)
    table.items = [{"id": "c1", "name": "Asha"}]
    _invoke(agent, function="searchContacts", query="asha")
    assert "deletedAt" in table.scans[0]["FilterExpression"]


def test_stats_does_not_scan_anything(agent):
    """Three exhaustive scans, on every call, because a model asked how things are
    going. Table metadata is approximate and says so."""
    result = _invoke(agent, function="getStats")
    assert result["success"] is True
    assert result["approximate"] is True
    assert "lag" in result["message"]
    for table in agent._tables.values():
        assert table.scans == [], f"{table.name} was scanned"


def test_get_messages_reads_one_bounded_page_per_table(agent):
    result = _invoke(agent, function="getMessages", contactId="c1")
    assert result["success"] is True
    scanned = [t for t in agent._tables.values() if t.scans]
    assert len(scanned) == 2, "expected exactly the two message tables"
    for table in scanned:
        assert len(table.scans) == 1, f"{table.name} paginated"
        assert table.scans[0]["Limit"] <= gov.MAX_READ_LIMIT


def test_get_messages_refuses_without_a_contact(agent):
    assert _invoke(agent, function="getMessages")["success"] is False


def test_a_caller_cannot_raise_the_read_limit(agent):
    table = agent.dynamodb.Table(agent.CONTACTS_TABLE)
    table.items = [{"id": "c1", "name": "Asha"}]
    _invoke(agent, function="searchContacts", query="asha", limit="100000")
    assert table.scans[0]["Limit"] == gov.MAX_READ_LIMIT


def test_a_read_failure_does_not_leak_the_exception_text(agent, monkeypatch):
    """An exception string can carry a table name or a key, and this response is
    read by a model and then repeated to a person."""
    table = agent.dynamodb.Table(agent.CONTACTS_TABLE)

    def boom(**kwargs):
        raise RuntimeError(
            "ValidationException: table stack-wecare-digital-ContactsTable key id")

    table.scan = boom
    result = _invoke(agent, function="searchContacts", query="asha")
    assert result["success"] is False
    assert "stack-wecare-digital" not in result["error"]
    assert "ValidationException" not in result["error"]


def test_auth_failure_short_circuits_before_any_tool_runs(agent, monkeypatch):
    import lambda_utils.middleware as mw
    monkeypatch.setattr(mw, "require_auth",
                        lambda event: {"statusCode": 401, "body": "{}"})
    response = agent.handler({"function": "getStats", "parameters": []}, None)
    assert response["statusCode"] == 401
