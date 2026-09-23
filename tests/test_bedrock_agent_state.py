"""The Bedrock agent surface is dead, and every identifier naming it is fabricated.

Plan item 6.4 asked to "reconcile the live agent/alias/prepared state and fix stale
ids". Measured 2026-09-23 against account 775261844268, there is nothing to reconcile
it *to*:

    agents                       1  -> 4UUQYFWX64 (wecare-digital-agent)
      agentStatus                   NOT_PREPARED
      foundationModel               null
      instruction                   0 characters
      agentResourceRoleArn          null
      preparedAt                    never
      action groups                 0
      knowledge bases               0
      versions                      DRAFT only, NOT_PREPARED
      aliases                       TSTALIASID (AgentTestAlias) -> DRAFT
      last updated                  2026-04-25, five months ago
    knowledge bases in account   0
    wecare-agent-action-group resource policy
                                 apigateway.amazonaws.com only, NO
                                 bedrock.amazonaws.com principal

So the agent is an empty shell that was created and abandoned, the action group was
never wired to it, and Bedrock was never even granted permission to invoke that
Lambda. Preparing the agent would fail: it has no model, no instructions and no role.

Every identifier is stale, and the LIVE environment is worse than the source
defaults:

    wecare-ai-generate-response  INTERNAL_AGENT_ID=QIEEHEBTZO      does not exist
                                 INTERNAL_AGENT_ALIAS=ASCBD7YPUT   does not exist
                                 INTERNAL_KB_ID=D0JU8Q7IQS         does not exist
                                 EXTERNAL_KB_ID=LYMQLKZNY7         does not exist
    wecare-ai-query-kb           INTERNAL_KB_ID / EXTERNAL_KB_ID   do not exist
    wecare-whatsapp-calling      AI_AGENT_ID=Z4YAK0ZLBO            does not exist
                                 AI_AGENT_ALIAS=WANPKHQGIB         does not exist
                                 AI_KB_ID=static-faq               not an id at all

And the two Python functions that would consume them are unreachable:
`_invoke_bedrock_agent()` has ZERO call sites, and `_query_knowledge_base()` is
called only from inside it.

The resolution is retirement, not reconciliation. Dead code carrying fabricated
configuration is worse than absent code, because it makes the system look configured
- which is exactly why the action group's own docstring claimed a working agent for
months. The empty agent itself is left in place: deleting it is a destructive AWS
operation needing explicit confirmation, and it is inert and free.
"""

from __future__ import annotations

import io
import pathlib
import re
import tokenize

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Identifiers proven absent from the account. None of them may appear as a live
# default anywhere, because a default is what runs when nobody sets the variable.
FABRICATED_IDS = (
    "QIEEHEBTZO",    # agent, claimed by ai-generate-response's docstring and env
    "ASCBD7YPUT",    # alias for the above
    "Z4YAK0ZLBO",    # agent, live on wecare-whatsapp-calling
    "WANPKHQGIB",    # alias for the above
    "D0JU8Q7IQS",    # knowledge base, live on two functions
    "LYMQLKZNY7",    # knowledge base, live on two functions
)

# The one id that DOES exist, but names an empty never-prepared shell. Allowed to
# appear in prose that explains its state; never as a code default.
EMPTY_AGENT_ID = "4UUQYFWX64"

SOURCE_FILES = (
    "amplify/functions/ai/ai-generate-response/handler.py",
    "amplify/functions/ai/ai-config-management/handler.py",
    "amplify/functions/messaging/inbound-whatsapp-handler/handler.py",
    "amplify/functions/shared/config.ts",
    "src/types/dashboard.ts",
)


def _strip_comments(text: str, path: str) -> str:
    """Comments removed; string literals kept.

    These files now EXPLAIN the dead agent in comments, quoting the very ids that
    must not be used. A naive grep reports the documentation as the defect - the same
    trap `test_contact_key_wiring.code_only` exists for. String literals are kept
    because a fabricated default *is* a string literal, so stripping them would make
    every assertion here unfailable.
    """
    if not path.endswith(".py"):
        # TS/TSX: line and block comments.
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        return "\n".join(ln.split("//")[0] for ln in text.splitlines())

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


def _code(rel: str) -> str:
    path = ROOT / rel
    return _strip_comments(path.read_text(encoding="utf-8"), rel)


# ==========================================================================
# no fabricated identifier survives as a default
# ==========================================================================
@pytest.mark.parametrize("rel", SOURCE_FILES)
@pytest.mark.parametrize("bad_id", FABRICATED_IDS)
def test_no_file_carries_a_fabricated_identifier(rel, bad_id):
    assert bad_id not in _code(rel), (
        f"{rel} still uses {bad_id}, which does not exist in the account. A default "
        f"is what runs when nobody sets the variable.")


@pytest.mark.parametrize("rel", SOURCE_FILES)
def test_the_empty_agent_is_not_used_as_a_code_default(rel):
    """`4UUQYFWX64` exists but is an empty shell: no model, no instruction, no role,
    never prepared, no action groups. Naming it as a default asserts a working agent."""
    assert EMPTY_AGENT_ID not in _code(rel), (
        f"{rel} names the empty agent in code. It may be described in a comment, "
        f"never used as a value.")


@pytest.mark.parametrize("rel", SOURCE_FILES)
def test_static_faq_is_not_presented_as_a_knowledge_base_id(rel):
    """`static-faq` is not an id in any format, and the account holds zero knowledge
    bases. It was a placeholder that read as configuration."""
    assert "'static-faq'" not in _code(rel)
    assert '"static-faq"' not in _code(rel)


# ==========================================================================
# the unreachable agent code is gone, not merely unused
# ==========================================================================
def test_the_unreachable_agent_invoker_is_removed():
    """`_invoke_bedrock_agent()` had zero call sites and `_query_knowledge_base()`
    was reachable only from inside it. Both carried stale ids, which is what made
    the system look configured."""
    code = _code("amplify/functions/ai/ai-generate-response/handler.py")
    assert "_invoke_bedrock_agent" not in code
    assert "_query_knowledge_base" not in code


def test_the_agent_runtime_client_is_removed():
    """Removing the capability means removing the means. A configured client is an
    invitation, and the shared role permits bedrock:InvokeAgent."""
    code = _code("amplify/functions/ai/ai-generate-response/handler.py")
    assert "bedrock_agent_runtime" not in code
    assert "bedrock-agent-runtime" not in code


def test_the_converse_path_is_untouched():
    """The live dashboard path uses Converse directly and must keep working. It is
    the reason no agent needs provisioning."""
    code = _code("amplify/functions/ai/ai-generate-response/handler.py")
    assert "bedrock_runtime" in code
    assert ".converse(" in code
    assert "_internal_converse_with_tools" in code


def test_no_agent_env_var_is_read_anywhere():
    """A variable nothing reads is still a claim, because an operator inspecting the
    function config reads it as configuration."""
    for rel in SOURCE_FILES:
        code = _code(rel)
        for var in ("INTERNAL_AGENT_ID", "INTERNAL_AGENT_ALIAS", "EXTERNAL_AGENT_ID",
                    "EXTERNAL_AGENT_ALIAS", "AI_AGENT_ID", "AI_AGENT_ALIAS"):
            assert var not in code, f"{rel} still reads {var}"


# ==========================================================================
# the manifest agrees
# ==========================================================================
def test_the_env_manifest_carries_no_fabricated_identifier():
    import json

    manifest = json.loads((ROOT / "config/lambda-env-manifest.json").read_text())
    blob = json.dumps(manifest)
    for bad_id in FABRICATED_IDS:
        assert bad_id not in blob, f"the manifest still pins {bad_id}"
    assert EMPTY_AGENT_ID not in blob


def test_the_manifest_has_no_agent_or_kb_variables():
    import json

    manifest = json.loads((ROOT / "config/lambda-env-manifest.json").read_text())
    offenders = {}
    for fn, env in (manifest.get("functions") or {}).items():
        stale = [k for k in env
                 if k in ("INTERNAL_AGENT_ID", "INTERNAL_AGENT_ALIAS",
                          "EXTERNAL_AGENT_ID", "EXTERNAL_AGENT_ALIAS",
                          "AI_AGENT_ID", "AI_AGENT_ALIAS",
                          "INTERNAL_KB_ID", "EXTERNAL_KB_ID", "AI_KB_ID")]
        if stale:
            offenders[fn] = stale
    assert offenders == {}, offenders


# ==========================================================================
# the state is written down where the next person will look
# ==========================================================================
def test_the_action_group_docstring_states_the_measured_agent_state():
    """It claimed a working agent for months. Whatever it says now must be checkable
    against the account."""
    text = (ROOT / "amplify/functions/ai/agent-action-group/handler.py").read_text()
    assert "NOT_PREPARED" in text
    assert EMPTY_AGENT_ID in text, "the docstring should name what actually exists"
