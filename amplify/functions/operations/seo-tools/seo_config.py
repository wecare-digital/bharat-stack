"""Cost and capability configuration for the derived-SEO layer.

WHY THIS MODULE EXISTS. The brief asks for three things this fleet did not have a single
place for: an explicit COST_MODE, an explicit AI_ENABLED default of false, and a guarantee
that the derived-SEO work degrades to deterministic templates when AI is off. The individual
switches already existed and are respected here rather than duplicated:

  * ENABLE_BEDROCK_ASSIST  - the existing per-function cost flag the blog-draft route reads.
  * SystemConfig cost_flags - the runtime, no-deploy switch the handler's PermissionError
                              path already surfaces as a 409.

This module does NOT introduce a second source of truth. AI is considered enabled only when
BOTH the explicit AI_ENABLED flag is on AND the pre-existing ENABLE_BEDROCK_ASSIST is on, so
turning either off is sufficient to fall back to deterministic behaviour. That asymmetry is
deliberate: a safety switch should be easy to trip and require agreement to lift.

Nothing here reads a secret, calls AWS, or logs a value. It reads environment variables that
carry names and booleans only.
"""
from __future__ import annotations

import os
from typing import Dict


#: The three cost modes from the brief. FREE is the default and the only one that needs no
#: reasoning about spend: no AI, deterministic templates, no optional background compute
#: beyond the single low-frequency freshness check.
COST_MODE_FREE = "FREE"
COST_MODE_LOW_COST = "LOW_COST"
COST_MODE_ADVANCED = "ADVANCED"
_COST_MODES = (COST_MODE_FREE, COST_MODE_LOW_COST, COST_MODE_ADVANCED)


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def cost_mode() -> str:
    """The active cost mode. Unknown or unset values resolve to FREE.

    FREE is the fail-safe: an operator who fat-fingers the variable, or a deploy that forgets
    to set it, gets the cheapest posture rather than the most expensive one. ADVANCED must be
    spelled correctly and on purpose, which is the point of not defaulting to it.
    """
    raw = str(os.environ.get("COST_MODE", "") or "").strip().upper()
    return raw if raw in _COST_MODES else COST_MODE_FREE


def _explicit_ai_flag() -> bool:
    """The new, explicit AI_ENABLED switch. Default false, per the brief's hard requirement."""
    return _truthy(os.environ.get("AI_ENABLED", "false"))


def _bedrock_assist_flag() -> bool:
    """The pre-existing per-function cost flag. Kept as a second required condition rather than
    replaced, so a function that never had AI turned on does not silently gain it here."""
    return _truthy(os.environ.get("ENABLE_BEDROCK_ASSIST", "false"))


def ai_enabled() -> bool:
    """True only when AI is explicitly enabled AND the existing Bedrock cost flag is on AND the
    cost mode permits paid work.

    FREE mode can never enable AI regardless of the flags - the mode is the outer guard, and a
    public read path must never be one environment-variable typo away from a model call. AI is
    an enhancement; if this returns False the caller MUST produce a deterministic result.
    """
    if cost_mode() == COST_MODE_FREE:
        return False
    return _explicit_ai_flag() and _bedrock_assist_flag()


def faq_ai_generation_enabled() -> bool:
    """FAQ generation is a narrower switch on top of AI, defaulting off (FAQ_AI_GENERATION=false).

    The brief calls this out specifically: FAQs must not be generated automatically. So it
    requires ai_enabled() to be true AND its own flag to be set, and it is never on in FREE mode.
    """
    return ai_enabled() and _truthy(os.environ.get("FAQ_AI_GENERATION", "false"))


def snapshot() -> Dict[str, object]:
    """A log/report-safe view of the configuration. Booleans and a mode string only - it names
    no secret and carries no value, so it is safe to return from a status surface or log."""
    return {
        "costMode": cost_mode(),
        "aiEnabled": ai_enabled(),
        "faqAiGenerationEnabled": faq_ai_generation_enabled(),
        # The inputs, so an operator can see WHY aiEnabled resolved the way it did without
        # having to reason about the precedence in their head.
        "aiEnabledFlag": _explicit_ai_flag(),
        "bedrockAssistFlag": _bedrock_assist_flag(),
    }
