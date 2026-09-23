"""Every contact writer emits both identifiers, and every reader resolves either one.

`test_contact_key.py` tests the module. This file tests that the module is actually
*used*, because the defect CRM-KEY-001 describes is not in the helper - it is in the gap
between six writers and four readers that each made their own assumption.

The concrete defect, found by reading the six `put_item` sites
-------------------------------------------------------------
Four writers set `id` **and** `contactId`. Two set `id` only:

    ai-generate-response  _update_contact_customer_info   source='payment_flow'
    ai-generate-response  bot subscribe                   source='bot_subscribe'

And both RCS readers resolved a contact with ``items[0].get('contactId', '')`` - no
fallback to `id`. So a contact whose row was first created by either of those two paths
returned `''`, and that empty string was passed straight to
``put_message(contact_id='')``. The message was stored, the send succeeded, nothing
raised, and the message was attached to no contact. That is the whole failure: invisible
in the inbox, invisible in the logs.

It is not hypothetical. Those two writers are live, they are the WhatsApp payment-flow
and bot-subscribe paths, and RCS reaches the same handsets.

Why these assertions read the source
------------------------------------
The invariant is "no writer anywhere sets one identifier without the other". A
behavioural test over one handler cannot express that - it passes while the next handler
added next month reintroduces the bug. Reading the six known sites is what makes the
guarantee fleet-wide, so the test fails when someone hand-writes `'id': x` again.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import contact_key  # noqa: E402

FUNCTIONS = ROOT / "amplify" / "functions"

#: Every source file that writes a row into ContactsTable, found via `put_item` on a
#: contacts table handle. Listed explicitly so that adding a seventh writer without
#: adding it here is caught by `test_writer_inventory_is_complete`.
CONTACT_WRITERS = (
    "ai/ai-generate-response/handler.py",
    "ai/agent-action-group/handler.py",
    "core/contacts/handler.py",
    "messaging/outbound-whatsapp/handler.py",
    "messaging/inbound-whatsapp-handler/handler.py",
)

#: Readers that resolve a contact id out of a `phone-index` query result.
CONTACT_PHONE_READERS = (
    "messaging/rcs-send/handler.py",
    "messaging/rcs-dlr/handler.py",
)


def source(rel: str) -> str:
    return (FUNCTIONS / rel).read_text(encoding="utf-8")


def code_only(rel: str) -> str:
    """Source with docstrings and comments removed.

    Needed because the fixed handlers *quote* the old broken expression in their
    docstrings to explain what changed, and a naive substring search then reports the
    documentation as the defect. Prose describing a bug is not the bug.
    """
    import ast
    import io
    import tokenize

    text = source(rel)
    tree = ast.parse(text)
    docstring_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            docstring_lines.update(range(first.lineno, (first.end_lineno or
                                                        first.lineno) + 1))

    lines = text.splitlines()

    # Blank out `#` comments in place, using the tokenizer so a `#` inside a string
    # literal survives. Editing in place matters: joining tokens instead would split
    # every expression across lines and make the substring assertions below unfailable.
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.COMMENT:
                continue
            row, col = tok.start
            if 1 <= row <= len(lines):
                lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass

    return "\n".join(line for lineno, line in enumerate(lines, start=1)
                     if lineno not in docstring_lines)


class TestWritersUseTheHelper:
    """No writer may set either identifier field by hand."""

    @pytest.mark.parametrize("rel", CONTACT_WRITERS)
    def test_imports_contact_key(self, rel: str) -> None:
        assert "from lambda_utils import contact_key" in source(rel), (
            f"{rel} writes contact rows but does not import contact_key")

    @pytest.mark.parametrize("rel", CONTACT_WRITERS)
    def test_calls_contact_item_keys(self, rel: str) -> None:
        assert "contact_key.contact_item_keys(" in source(rel), (
            f"{rel} must build its identifier fields with contact_item_keys")

    @pytest.mark.parametrize("rel", CONTACT_WRITERS)
    def test_no_handwritten_contact_id_literal(self, rel: str) -> None:
        """`'contactId': contact_id` in an item dict is the drift this replaces.

        Restricted to the exact assignment of the local `contact_id` variable, so the
        many legitimate uses - API response bodies, log lines, message rows in other
        tables - are untouched. It is specifically the *contact row* that must not name
        the field directly.
        """
        text = code_only(rel)
        offenders = re.findall(
            r"'id':\s*contact_id,\s*\n\s*'contactId':\s*contact_id,", text)
        assert not offenders, (
            f"{rel} still pairs 'id' and 'contactId' by hand; use contact_item_keys so "
            "the two cannot diverge")

    def test_writer_inventory_is_complete(self) -> None:
        """Catch a seventh writer that this file does not know about.

        Greps the tree for a `put_item` against a contacts table handle rather than
        trusting the list above, because the list going stale is exactly how the
        payment_flow writer stayed broken.
        """
        found = set()
        for path in FUNCTIONS.rglob("handler.py"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"contacts_table\.put_item|table\.put_item\(Item=_to_dynamo",
                         text):
                found.add(str(path.relative_to(FUNCTIONS)))
        unknown = found - set(CONTACT_WRITERS)
        assert not unknown, (
            f"new contact writer(s) not covered by this test: {sorted(unknown)}; add "
            "them to CONTACT_WRITERS and route them through contact_item_keys")


class TestReadersResolveEitherSpelling:
    @pytest.mark.parametrize("rel", CONTACT_PHONE_READERS)
    def test_imports_contact_key(self, rel: str) -> None:
        assert "from lambda_utils import contact_key" in source(rel), (
            f"{rel} resolves contact ids but does not import contact_key")

    @pytest.mark.parametrize("rel", CONTACT_PHONE_READERS)
    def test_no_bare_alias_read(self, rel: str) -> None:
        """The precise line that caused the silent detachment.

        ``items[0].get('contactId', '')`` returns `''` for an `id`-only row, and `''` is
        a valid-looking contact id to every caller downstream.
        """
        text = code_only(rel)
        assert "items[0].get('contactId', '')" not in text, (
            f"{rel} still reads the alias with no fallback; an id-only row yields '' "
            "and the message is stored against no contact")

    @pytest.mark.parametrize("rel", CONTACT_PHONE_READERS)
    def test_resolves_through_helper(self, rel: str) -> None:
        assert "contact_key.resolve(" in source(rel), (
            f"{rel} must resolve the contact id through contact_key.resolve")

    @pytest.mark.parametrize("rel", CONTACT_PHONE_READERS)
    def test_reports_a_diverged_row(self, rel: str) -> None:
        """A mismatch must be logged, not swallowed.

        `resolve` still returns a usable key, so the send is not blocked - but the row is
        evidence that a writer is broken, and that has to reach CloudWatch or it will not
        be found until a customer reports missing messages.
        """
        text = source(rel)
        assert "contact_key.assert_consistent(" in text
        assert "contact_key_mismatch" in text, (
            f"{rel} must emit a contact_key_mismatch event when the two disagree")


class TestTheDefectIsRealNotTheoretical:
    """Reproduce, on the helper, exactly what the two id-only writers produced."""

    def test_id_only_row_was_unresolvable_before(self) -> None:
        id_only = {"id": "c-123", "phone": "+918100640044"}
        # What the old reader did:
        assert id_only.get("contactId", "") == ""
        # What the new reader does:
        assert contact_key.resolve(id_only) == "c-123"

    def test_writers_now_produce_a_resolvable_row(self) -> None:
        row = {**contact_key.contact_item_keys("c-123"), "phone": "+918100640044"}
        assert row["id"] == "c-123"
        assert row["contactId"] == "c-123"
        # Resolvable by the old reader shape as well, so nothing that still reads the
        # alias directly is broken by this change.
        assert row.get("contactId", "") == "c-123"
        assert contact_key.resolve(row) == "c-123"

    def test_alias_only_row_resolves_rather_than_returning_empty(self) -> None:
        """A projection may return only the alias; that must still yield a key."""
        assert contact_key.resolve({"contactId": "c-9"}) == "c-9"
