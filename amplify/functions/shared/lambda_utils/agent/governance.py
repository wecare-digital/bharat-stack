"""What the AI action group is allowed to do, and what it is refused.

Why this module exists
---------------------
`ai/agent-action-group` exposed twelve tools to a Bedrock agent, and eight of them
were things a language model should not be able to choose on its own:

  * SEND - `sendWhatsApp`, `sendSms`, `sendEmail` invoked `wecare-outbound-*`
    with a phone number and a body. No plan, no approval, no receipt. The model's
    tool choice was the authorisation, and the result was a real message to a real
    customer under our registered sender.
  * SCAN - `searchContacts` paginated the whole ContactsTable to exhaustion and
    then filtered in Python. `getStats` did three exhaustive scans. `getMessages`
    scanned both message tables. Every one of those was a `while True` on
    `LastEvaluatedKey`, billed per read, triggered by a model's whim.
  * DELETE - `deleteMessage` hard-deleted from the message store; `deleteContact`
    wrote a `deletedAt` marker.
  * FABRICATE - `createInvoice` returned `{'success': True, 'invoiceId':
    'INV-xxxxxxxx'}` and wrote nothing whatsoever.

The last one is the worst of the four and explains the shape of everything here. A
confident success that did not happen is more damaging than an error, because the
agent repeats it to a person, who then waits for an invoice that does not exist.

So: READ and status tools are enabled. Every APPLY tool is refused
**structurally**. There is deliberately no flag, because the approval, plan-hash
and receipt machinery that would make an APPLY safe does not exist yet - a flag
added now would be a switch nobody could safely throw, and the first person to
find it would throw it.

Three bugs were hiding inside the removed powers
------------------------------------------------
Worth recording, because each is invisible until you look at the power itself:

  * `_delete_message` wrapped the inbound delete in `try/except: pass` then
    deleted from outbound. DynamoDB's `delete_item` SUCCEEDS on a key that does
    not exist, so the inbound attempt never raised, the outbound branch was
    unreachable, and the function reported "deleted successfully" for any id -
    including one that never existed.
  * `_delete_contact` used `update_item ... SET deletedAt` with no existence
    check. DynamoDB upserts, so an unknown id CREATED a row holding nothing but
    `{id, deletedAt}`. A delete that manufactured records.
  * `_find_contact_by_phone` scanned with `contains(phone, last10)` and `Limit=1`.
    `Limit` applies BEFORE the FilterExpression, so it examined one arbitrary item
    and filtered it away, normally finding nobody; and `contains` is a substring
    match, so a hit could be the wrong person. ContactsTable has a `phone-index`
    GSI with an ALL projection, so the scan was never needed - `query_index`
    replaces it with an exact lookup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

# Tool classes. PLAN is declared but unused here; plan item 6.2 introduces
# dry-run tooling and will populate it.
CLASS_READ = "READ"
CLASS_PLAN = "PLAN"
CLASS_APPLY = "APPLY"

# Read bounds. Small on purpose: a "limit" of ten thousand is an exhaustive scan
# with extra steps, and an agent answering a question does not need every row.
DEFAULT_READ_LIMIT = 25
MAX_READ_LIMIT = 100


class ToolUnknown(KeyError):
    """The requested tool is not in the catalog. Never guessed at."""


@dataclass(frozen=True)
class Tool:
    name: str
    tool_class: str
    enabled: bool
    summary: str
    # Model-facing. Short, actionable, and free of topology: it travels back
    # through Bedrock into a prompt and then into a transcript.
    refusal: str = ""
    # Operator-facing forensics: WHY the power was removed, in implementation
    # terms. Deliberately excluded from `catalog_summary()`, because table names,
    # function names and API semantics are not a model's business - but they are
    # exactly what the next engineer needs so the power is not reintroduced.
    detail: str = ""


class ToolRefused(PermissionError):
    """The tool exists and is deliberately not executable."""

    def __init__(self, tool: str, tool_class: str, reason: str) -> None:
        super().__init__(reason)
        self.tool = tool
        self.tool_class = tool_class
        self.reason = reason

    def as_result(self) -> Dict[str, Any]:
        """The refusal, in the shape the handler returns.

        Carries `success: False` AND an explicit `refused: True`, and deliberately
        no key a caller could read as a completed side effect - no `invoiceId`, no
        `messageId`, no `sentAt`. That is the direct lesson of the placeholder
        `createInvoice`.
        """
        return {
            "success": False,
            "refused": True,
            "tool": self.tool,
            "toolClass": self.tool_class,
            "error": self.reason,
        }


_APPROVAL = (
    "Sending is refused. It needs an approved plan and a recorded receipt, and "
    "neither exists yet. Draft what you would send and hand it to a person for "
    "approval - do not state that anything was sent."
)

_APPROVAL_DETAIL = (
    "A model's tool choice is not an approval. This invoked the outbound sender "
    "directly with a phone number and a body, so the model's decision was the only "
    "authorisation between it and a real customer, under our registered sender. "
    "Build the plan-hash / approval / receipt path first, then route the send "
    "through it."
)

CATALOG: Dict[str, Tool] = {
    # ---------------- enabled: READ and status ----------------
    "getContact": Tool(
        name="getContact", tool_class=CLASS_READ, enabled=True,
        summary="Look up one contact by id, phone or email."),
    "searchContacts": Tool(
        name="searchContacts", tool_class=CLASS_READ, enabled=True,
        summary="Find contacts matching a query. Bounded and may be truncated."),
    "getMessages": Tool(
        name="getMessages", tool_class=CLASS_READ, enabled=True,
        summary="Recent messages for one contact. Bounded and may be truncated."),
    "getStats": Tool(
        name="getStats", tool_class=CLASS_READ, enabled=True,
        summary="Approximate counts of contacts and messages."),

    # ---------------- refused: APPLY ----------------
    "sendWhatsApp": Tool(
        name="sendWhatsApp", tool_class=CLASS_APPLY, enabled=False,
        summary="Send a WhatsApp message to a contact.",
        refusal=_APPROVAL, detail=_APPROVAL_DETAIL),
    "sendSms": Tool(
        name="sendSms", tool_class=CLASS_APPLY, enabled=False,
        summary="Send an SMS to a contact.",
        refusal=_APPROVAL, detail=_APPROVAL_DETAIL),
    "sendEmail": Tool(
        name="sendEmail", tool_class=CLASS_APPLY, enabled=False,
        summary="Send an email to a contact.",
        refusal=_APPROVAL, detail=_APPROVAL_DETAIL),
    "createContact": Tool(
        name="createContact", tool_class=CLASS_APPLY, enabled=False,
        summary="Create a contact.",
        refusal=("Creating a contact record is refused here. Ask a person to "
                 "create it, then look it up."),
        detail=("The contact service owns creation, including the invariant that "
                "`id` is the physical key and `contactId` is its alias. A second "
                "writer duplicating that logic is how the two drift apart.")),
    "updateContact": Tool(
        name="updateContact", tool_class=CLASS_APPLY, enabled=False,
        summary="Update a contact.",
        refusal=("Changing a contact record is refused here. Report what should "
                 "change and let a person apply it."),
        detail=("An unreviewed field-level update chosen by a model can overwrite "
                "provenance-bearing fields, which the identity work records per "
                "field precisely so an import cannot be admitted wholesale.")),
    "deleteContact": Tool(
        name="deleteContact", tool_class=CLASS_APPLY, enabled=False,
        summary="Mark a contact deleted.",
        refusal="Deleting a contact is refused. Only a person can do that.",
        detail=("The previous implementation used an unconditional `update_item`, "
                "which DynamoDB treats as an upsert, so deleting an unknown id "
                "CREATED a row containing only `{id, deletedAt}`. A delete that "
                "manufactures records. Deletion needs an existence check and a "
                "reviewed path.")),
    "deleteMessage": Tool(
        name="deleteMessage", tool_class=CLASS_APPLY, enabled=False,
        summary="Delete a message.",
        refusal=("Deleting a message is refused. Messages are the record of what "
                 "was said to a customer, so only a person can remove one. Do not "
                 "state that a message was deleted."),
        detail=("The previous implementation reported success for any id at all: "
                "`delete_item` succeeds on a key that does not exist, the inbound "
                "attempt was wrapped in `try/except: pass`, so the outbound branch "
                "was unreachable and every call returned 'deleted successfully'.")),
    "createInvoice": Tool(
        name="createInvoice", tool_class=CLASS_APPLY, enabled=False,
        summary="Create an invoice for a contact.",
        refusal=("Creating an invoice is refused here. Do not state that an "
                 "invoice exists; request one through the invoice service and "
                 "report only a number it returns."),
        detail=("The previous implementation fabricated `INV-<random>` and wrote "
                "nothing, so the agent told people an invoice existed when it did "
                "not. The invoice-engine function owns the GST number sequence, "
                "and minting an identifier outside it breaks that series.")),
}


def resolve(name: str) -> Tool:
    """The catalog entry, or `ToolUnknown`. Never a default."""
    key = str(name or "")
    if key not in CATALOG:
        raise ToolUnknown(f"unknown tool: {key!r}")
    return CATALOG[key]


def assert_executable(name: str) -> Tool:
    """The catalog entry, if it may run. Raises `ToolRefused` otherwise."""
    tool = resolve(name)
    if not tool.enabled:
        raise ToolRefused(tool.name, tool.tool_class, tool.refusal)
    return tool


def catalog_summary() -> Dict[str, Any]:
    """What a model may be told about its own tools.

    Names, classes and summaries only. No table name, function name or ARN - a
    model does not need the topology to call a tool, and anything put here ends up
    in a prompt, then in a transcript.
    """
    return {
        "enabled": {t.name: {"class": t.tool_class, "summary": t.summary}
                    for t in CATALOG.values() if t.enabled},
        "refused": {t.name: {"class": t.tool_class, "reason": t.refusal}
                    for t in CATALOG.values() if not t.enabled},
    }


# --------------------------------------------------------------------------
# bounded reads
# --------------------------------------------------------------------------
def bounded_limit(requested: Any,
                  *, default: int = DEFAULT_READ_LIMIT,
                  maximum: int = MAX_READ_LIMIT) -> int:
    """Clamp a caller-supplied limit. Anything unusable becomes the default."""
    try:
        value = int(requested)
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    return min(value, maximum)


def read_page(table: Any, *, limit: Any = DEFAULT_READ_LIMIT,
              **scan_kwargs: Any) -> Tuple[List[Dict[str, Any]], bool]:
    """One page of a scan, hard-bounded. Returns (items, truncated).

    Deliberately does NOT paginate. The code this replaces looped
    `while True` on `LastEvaluatedKey`, which on a table of any real size is an
    exhaustive scan billed per read and chosen by a model rather than by a person.

    `truncated` exists so a caller cannot present a partial answer as a total.
    "Found 25 contacts" and "found at least 25 contacts" are different claims, and
    the agent will repeat whichever one it is handed.

    An `ExclusiveStartKey` from a caller is refused: resuming across invocations
    turns a bounded read back into an unbounded one, one page per model turn.
    """
    if "ExclusiveStartKey" in scan_kwargs:
        raise ValueError(
            "read_page does not resume a scan; a caller-supplied "
            "ExclusiveStartKey would make a bounded read unbounded")

    capped = bounded_limit(limit)
    response = table.scan(Limit=capped, **scan_kwargs) or {}
    items = list(response.get("Items") or [])
    truncated = bool(response.get("LastEvaluatedKey")) or len(items) > capped
    return items[:capped], truncated


def query_index(table: Any, *, index_name: str, key_name: str, value: Any,
                limit: Any = 1) -> List[Dict[str, Any]]:
    """Exact lookup through a GSI. Never a scan, never a substring match.

    ContactsTable carries `phone-index` and `email-index`, both with ALL
    projections, so the lookup scans this replaces were never necessary - and the
    scan they used was wrong twice over: `Limit` applied before the
    FilterExpression so it usually matched nobody, and `contains` on the last ten
    digits could match a different number.
    """
    from boto3.dynamodb.conditions import Key

    if not str(value or "").strip():
        raise ValueError(f"{key_name} is required for an index lookup")

    response = table.query(
        IndexName=index_name,
        KeyConditionExpression=Key(key_name).eq(value),
        Limit=bounded_limit(limit, default=1),
    ) or {}
    return list(response.get("Items") or [])
