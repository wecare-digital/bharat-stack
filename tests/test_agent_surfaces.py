"""One policy over BOTH agent surfaces — and the dashboard one is the live hole.

Phase 6.1 removed eight ungoverned powers from the Bedrock action group. That
surface cannot currently be reached at all: the account holds one agent,
`4UUQYFWX64`, status `NOT_PREPARED`.

Meanwhile the surface every operator actually uses kept all of its powers.
`/ai/generate` with `context: 'internal-admin'` runs a 30-tool Bedrock Converse
loop, and `_execute_internal_tool` dispatched straight to live sends and hard
deletes. Three UIs are wired to it: `FloatingAgent`, `InternalChatTab`, and the
dashboard AI tab.

Its system prompt did not merely permit that, it pushed for it:

    "ALWAYS use your tools to execute tasks. Never explain how to do something
     manually."
    "Be proactive: 'send message to Jignesh' -> search first, then send."
    "For payment requests, use send_whatsapp_pay tool directly."

The only guard anywhere in the stack was a substring match in `FloatingAgent`
against the text the USER typed, `['delete all', 'clear all', 'remove all',
'delete contact', 'clear data']`, evaluated before the model had chosen anything.
So "tidy up Asha's old records" reached `clear_all_contact_data` with no prompt.
`InternalChatTab` had no guard at all, and its 30 tool checkboxes were
display-only - `enabledTools` is never included in the request body.

What these tests pin
--------------------
1. Every dispatched tool name is in the catalog. A tool the catalog does not know
   about is an ungoverned tool, and the previous state is what that looks like.
2. The two surfaces cannot disagree. `send_whatsapp` and `sendWhatsApp` are the
   same capability under two spellings, and one being enabled while the other is
   refused would be the whole mechanism defeated by a naming convention.
3. Refused tools are not ADVERTISED to the model. Offering a tool and then
   refusing it teaches the model to promise things it cannot do, and it will
   narrate the promise.
4. A provider outage is distinguishable from an answer. The handler returned
   HTTP 200 with "Sorry, I encountered an error processing your request" - so a
   Bedrock outage and a real reply were the same shape to the UI.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify/functions/shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.agent import governance as gov  # noqa: E402

HANDLER = ROOT / "amplify/functions/ai/ai-generate-response/handler.py"

# The tools the dashboard loop dispatches, extracted from the source rather than
# listed here: a hand-maintained copy is how the UI's three tool lists drifted.
DISPATCHED = tuple(sorted(set(re.findall(
    r"tool_name == '([a-z_]+)'",
    HANDLER.read_text()[HANDLER.read_text().index("def _execute_internal_tool"):]
    .split("\ndef _tool_search_contacts")[0]))))

SENDERS = ("send_whatsapp", "send_whatsapp_buttons", "send_whatsapp_list",
           "send_whatsapp_flow", "send_whatsapp_pay", "send_template",
           "send_sms", "send_email", "make_voice_call", "schedule_message")
DESTRUCTIVE = ("delete_contact", "delete_messages", "delete_media_files",
               "clear_all_contact_data")
WRITES = ("create_contact", "update_contact", "add_contact_email", "create_invoice")


# ==========================================================================
# nothing escapes the catalog
# ==========================================================================
def test_the_dispatch_table_was_actually_found():
    """Guards the extraction above. If the handler is restructured this list goes
    empty and every assertion below passes vacuously."""
    assert len(DISPATCHED) == 30, DISPATCHED


@pytest.mark.parametrize("name", DISPATCHED)
def test_every_dispatched_tool_is_in_the_catalog(name):
    assert gov.resolve(name).name == name


def test_the_internal_surface_matches_the_dispatch_table_exactly():
    """A catalog entry with no dispatcher is dead weight; a dispatcher with no
    catalog entry is an ungoverned power."""
    assert set(gov.tools_for(gov.SURFACE_INTERNAL)) == set(DISPATCHED)


@pytest.mark.parametrize("name", SENDERS + DESTRUCTIVE + WRITES)
def test_every_send_write_and_delete_is_refused(name):
    tool = gov.resolve(name)
    assert tool.tool_class == gov.CLASS_APPLY, f"{name} is not classified APPLY"
    assert tool.enabled is False
    assert gov.is_enabled(name) is False


def test_the_read_tools_are_still_available():
    """Refusing everything would be safe and useless. The assistant has to remain
    able to answer questions, which is the point of 6.3."""
    enabled = [n for n in gov.tools_for(gov.SURFACE_INTERNAL)
               if gov.is_enabled(n)]
    assert len(enabled) == 12
    assert "search_contacts" in enabled and "get_stats" in enabled


def test_no_apply_tool_is_enabled_on_either_surface():
    offenders = [t.name for t in gov.CATALOG.values()
                 if t.tool_class == gov.CLASS_APPLY and t.enabled]
    assert offenders == []


# ==========================================================================
# the two surfaces cannot drift apart
# ==========================================================================
def test_paired_spellings_agree_on_class_and_enablement():
    """`send_whatsapp` and `sendWhatsApp` are one capability. One enabled and the
    other refused would be the whole mechanism defeated by a naming convention."""
    pairs = [(t, gov.resolve(t.counterpart))
             for t in gov.CATALOG.values() if t.counterpart]
    assert len(pairs) >= 10, "expected the overlapping capabilities to be linked"
    for tool, other in pairs:
        assert tool.tool_class == other.tool_class, f"{tool.name} vs {other.name}"
        assert tool.enabled == other.enabled, f"{tool.name} vs {other.name}"


def test_counterparts_point_at_the_other_surface():
    for tool in gov.CATALOG.values():
        if tool.counterpart:
            assert gov.resolve(tool.counterpart).surface != tool.surface


def test_every_catalog_entry_declares_a_surface():
    for tool in gov.CATALOG.values():
        assert tool.surface in (gov.SURFACE_AGENT, gov.SURFACE_INTERNAL)


def test_the_surfaces_do_not_share_a_name():
    """A single name meaning two things on two surfaces would make `resolve`
    ambiguous and the kill switch imprecise."""
    agent = set(gov.tools_for(gov.SURFACE_AGENT))
    internal = set(gov.tools_for(gov.SURFACE_INTERNAL))
    assert agent & internal == set()


def test_a_surface_is_told_only_its_own_spellings():
    internal = gov.catalog_summary(gov.SURFACE_INTERNAL)
    assert "sendWhatsApp" not in internal["refused"]
    assert "send_whatsapp" in internal["refused"]

    agent = gov.catalog_summary(gov.SURFACE_AGENT)
    assert "send_whatsapp" not in agent["refused"]
    assert "sendWhatsApp" in agent["refused"]


def test_the_catalog_version_was_bumped_for_the_new_tools():
    """30 tools were added and 18 reclassified as refused. A plan built against the
    old version must not be applied under the new definitions."""
    assert gov.CATALOG_VERSION != "1"


def test_catalog_summary_reflects_the_kill_switch_not_just_the_default(monkeypatch):
    """Advertising a switched-off tool as available is how a model comes to promise
    something that then fails."""
    assert "get_stats" in gov.catalog_summary(gov.SURFACE_INTERNAL)["enabled"]
    monkeypatch.setenv("AGENT_DISABLED_TOOLS", "get_stats")
    summary = gov.catalog_summary(gov.SURFACE_INTERNAL)
    assert "get_stats" not in summary["enabled"]
    assert "get_stats" in summary["refused"]


# ==========================================================================
# the handler: gated, honest, and not advertising what it will refuse
# ==========================================================================
def test_the_handler_imports_the_governance_module():
    assert "from lambda_utils.agent import governance" in HANDLER.read_text()


def test_the_handler_gates_tool_execution():
    """`_execute_internal_tool` must consult the catalog before dispatching, not
    after - a refusal that fires after the send is a log line, not a guard."""
    source = HANDLER.read_text()
    body = source[source.index("def _execute_internal_tool"):]
    body = body.split("\ndef _tool_search_contacts")[0]
    gate = body.index("assert_executable")
    first_dispatch = body.index("_tool_search_contacts(")
    assert gate < first_dispatch, "the gate runs after the first dispatch branch"


def _code_only(path: pathlib.Path) -> str:
    """Source with comments stripped.

    Needed because the fixed handler QUOTES the old prompt in a comment, to record
    why the change mattered. A naive grep then reports the documentation as the
    defect. Borrowed from `test_contact_key_wiring.code_only`, and for the same
    reason: prose describing a bug is not the bug.

    Docstrings are deliberately NOT stripped here - the prompt itself is a string
    literal, so removing string content would make these assertions unfailable.
    """
    import io
    import tokenize

    text = path.read_text()
    lines = text.splitlines()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                if 1 <= row <= len(lines):
                    lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return "\n".join(lines)


def test_the_prompt_no_longer_tells_the_model_to_send_without_asking():
    """The three lines that made this actively dangerous rather than merely
    permissive. Each one is quoted in a comment in the fixed handler, so this reads
    the comment-stripped source."""
    code = _code_only(HANDLER)
    assert "use send_whatsapp_pay tool directly" not in code
    assert "search first, then send" not in code
    assert "ALWAYS use your tools to execute tasks" not in code


def test_the_new_prompt_forbids_claiming_an_action_happened():
    """The failure mode that outlives the tools: a refused model narrating success."""
    code = _code_only(HANDLER)
    assert "NEVER state or imply that you have sent" in code


def test_the_new_prompt_is_built_from_the_catalog_not_a_hand_list():
    """Three hand-maintained tool lists already existed and all three had drifted."""
    code = _code_only(HANDLER)
    assert "gov.catalog_summary(gov.SURFACE_INTERNAL)" in code


def test_refused_tools_are_not_advertised_to_the_model():
    """Offering a tool and then refusing it teaches the model to promise things it
    cannot do, and it will narrate the promise to a person."""
    source = HANDLER.read_text()
    assert "_internal_tool_config(" in source, \
        "the toolConfig must be derived from the catalog, not a literal list"


def test_a_provider_outage_is_distinguishable_from_an_answer():
    """It returned HTTP 200 with 'Sorry, I encountered an error processing your
    request. Please try again.' - so a Bedrock outage and a real reply were the
    same shape to the UI, and the UI logged it as a success."""
    source = HANDLER.read_text()
    assert "providerUnavailable" in source
