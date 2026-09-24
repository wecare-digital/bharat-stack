"""The agent panel must not advertise a capability the backend refuses.

`InternalChatTab.tsx` carries a TypeScript mirror of the governance catalog, because
the panel is React and the catalog is Python. A mirror can drift, and this one did:
it listed 30 bare tool names and initialised every one as enabled, so the panel read
"Tool Capabilities (30/30)" and offered an Enable All toggle - while
`governance.py` refuses 18 of them unconditionally and states there is deliberately
NO flag to enable an APPLY tool.

That made the toggle cosmetic for 18 tools and put `Send WhatsApp`,
`Delete Contact`, `Clear All Data` and `Create Invoice` in front of an operator as
things the agent could do. It is the same defect the UI label gate exists to catch,
in the screen where being wrong matters most: someone reads that list to decide what
to ask for.

These tests parse the TSX and compare it to the catalog entry by entry, so changing
the catalog fails here until the UI follows.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))

from lambda_utils.agent import governance as gov  # noqa: E402

TSX = ROOT / "src/components/dashboard/tabs/InternalChatTab.tsx"

ROW = re.compile(
    r"\{\s*id:\s*'(?P<id>[a-z_]+)',\s*"
    r"name:\s*'(?P<name>[^']+)',\s*"
    r"category:\s*'(?P<category>[^']+)',\s*"
    r"cls:\s*'(?P<cls>[A-Z]+)',\s*"
    r"refused:\s*(?P<refused>true|false)\s*\}"
)


@pytest.fixture(scope="module")
def ui_rows() -> dict[str, dict]:
    text = TSX.read_text(encoding="utf-8")
    rows = {}
    for m in ROW.finditer(text):
        rows[m.group("id")] = {
            "name": m.group("name"),
            "category": m.group("category"),
            "cls": m.group("cls"),
            "refused": m.group("refused") == "true",
        }
    return rows


@pytest.fixture(scope="module")
def internal_catalog() -> dict[str, gov.Tool]:
    return {
        name: tool for name, tool in gov.CATALOG.items()
        if tool.surface == gov.SURFACE_INTERNAL
    }


class TestTheMirrorMatchesTheCatalog:
    def test_the_ui_declares_a_state_for_every_tool(self, ui_rows):
        # If the annotated shape is ever reverted to bare names this finds nothing,
        # which is the loudest possible failure.
        assert len(ui_rows) > 0, (
            "no annotated tool rows found - has TOOLS_LIST lost its cls/refused "
            "fields?"
        )

    def test_same_set_of_tools_on_both_sides(self, ui_rows, internal_catalog):
        assert set(ui_rows) == set(internal_catalog), (
            f"ui-only={sorted(set(ui_rows) - set(internal_catalog))} "
            f"catalog-only={sorted(set(internal_catalog) - set(ui_rows))}"
        )

    def test_every_class_matches(self, ui_rows, internal_catalog):
        wrong = {
            tid: (row["cls"], internal_catalog[tid].tool_class)
            for tid, row in ui_rows.items()
            if row["cls"] != internal_catalog[tid].tool_class
        }
        assert not wrong, f"class mismatch (ui, catalog): {wrong}"

    def test_refused_matches_enablement_exactly(self, ui_rows, internal_catalog):
        # This is the assertion that matters. `refused` in the UI must be the
        # inverse of `enabled` in the catalog, for all 30.
        wrong = {
            tid: (row["refused"], internal_catalog[tid].enabled)
            for tid, row in ui_rows.items()
            if row["refused"] is internal_catalog[tid].enabled
        }
        assert not wrong, f"refused/enabled disagree (ui refused, catalog enabled): {wrong}"


class TestTheDangerousOnesAreMarkedRefused:
    """Named individually, because these are the ones a person would act on."""

    @pytest.mark.parametrize("tool_id", [
        "send_whatsapp", "send_sms", "send_email", "send_template",
        "send_whatsapp_pay", "make_voice_call", "schedule_message",
        "create_invoice", "create_contact", "update_contact",
        "delete_contact", "delete_messages", "delete_media_files",
        "clear_all_contact_data",
    ])
    def test_marked_refused_in_the_ui(self, ui_rows, tool_id):
        assert tool_id in ui_rows, f"{tool_id} vanished from the UI list"
        assert ui_rows[tool_id]["refused"] is True, (
            f"{tool_id} is presented as available; governance refuses it"
        )

    @pytest.mark.parametrize("tool_id", [
        "search_contacts", "get_messages", "get_stats", "list_templates",
    ])
    def test_reads_are_not_marked_refused(self, ui_rows, tool_id):
        assert ui_rows[tool_id]["refused"] is False


class TestThePanelCountsHonestly:
    def test_the_denominator_is_the_available_set(self):
        text = TSX.read_text(encoding="utf-8")
        # The old header divided by TOOLS_LIST.length, i.e. 30.
        assert "AVAILABLE.length} available" in text, (
            "the capability counter must be denominated in AVAILABLE, not the "
            "whole list"
        )
        assert "enabledTools.size}/{TOOLS_LIST.length}" not in text

    def test_enable_all_cannot_select_a_refused_tool(self):
        text = TSX.read_text(encoding="utf-8")
        assert "setEnabledTools(new Set(AVAILABLE.map(t => t.id)))" in text
        assert "setEnabledTools(new Set(TOOLS_LIST.map(t => t.id)))" not in text

    def test_refused_tools_render_without_a_checkbox(self):
        text = TSX.read_text(encoding="utf-8")
        assert "tool.refused ? (" in text, (
            "refused tools must not render a checkbox - a control implies it can be "
            "switched on, and it cannot be"
        )
        assert "REFUSED" in text


class TestGovernanceStillRefusesWrites:
    """A guard on the guard: if these ever flip, the UI test above is moot."""

    def test_no_apply_tool_is_enabled_on_either_surface(self):
        enabled_applies = [
            name for name, t in gov.CATALOG.items()
            if t.tool_class == gov.CLASS_APPLY and t.enabled
        ]
        assert enabled_applies == [], (
            f"APPLY tools are enabled without the approval path: {enabled_applies}"
        )

    def test_reads_are_still_available(self):
        enabled_reads = [
            name for name, t in gov.CATALOG.items()
            if t.tool_class == gov.CLASS_READ and t.enabled
        ]
        assert len(enabled_reads) >= 12
