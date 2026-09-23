"""Receipts for agent tool attempts, including the refused ones.

A receipt answers "what did the agent try to do, and what came of it". Recording
only successes answers the wrong question: before this, an agent reaching for a
removed power left no trace at all, so there was no way to tell a well-behaved
prompt from one repeatedly trying to send.

Written through the existing `lambda_utils.audit` sink rather than a second parallel
trail. `AuditLogsTable` already exists, already masks, already has a TTL, and a
second audit store is a second thing to query during an incident.

Known limit, recorded rather than papered over
----------------------------------------------
`audit.record_audit` fails OPEN - it returns None and never raises, so a write
failure is invisible to the caller. That is correct for a receipt of a REFUSAL,
where nothing happened and the log is a convenience. It is NOT sufficient for a
receipt of a real side effect: if the send succeeds and the receipt write fails,
there is no record that a customer was messaged.

So when an APPLY is eventually enabled, the receipt must be claimed BEFORE the side
effect and confirmed after, the way `flow_completion.claim_completion` and the
invoice sequence already do it - claim first, act second, because a claim that
arrives after the action cannot prevent a duplicate. Nothing here is load-bearing in
that sense yet, because every APPLY is disabled.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from lambda_utils import audit
from lambda_utils.agent import plans as plan_module

RESULT_APPLIED = "applied"
RESULT_REFUSED = "refused"
RESULT_DUPLICATE = "duplicate"
RESULT_FAILED = "failed"

RESULTS = frozenset({RESULT_APPLIED, RESULT_REFUSED, RESULT_DUPLICATE,
                     RESULT_FAILED})

# Audit actions, one per result, so the trail is filterable without parsing JSON.
_ACTIONS = {
    RESULT_APPLIED: "agent.tool.applied",
    RESULT_REFUSED: "agent.tool.refused",
    RESULT_DUPLICATE: "agent.tool.duplicate",
    RESULT_FAILED: "agent.tool.failed",
}


def build_receipt(plan: "plan_module.Plan", *, result: str,
                  detail: str = "", actor: str = "agent",
                  now: Optional[int] = None) -> Dict[str, Any]:
    """The receipt record. Raises on an unrecognised result.

    Refusing an unknown result is deliberate: a receipt asserting that something
    unrecognised happened is worse than no receipt, because it looks like evidence.

    `applied` is derived from `result` rather than passed in, so the two cannot
    disagree - a receipt that says `refused` and `applied: true` would be exactly the
    kind of confident-but-wrong record this whole phase exists to remove.
    """
    if result not in RESULTS:
        raise ValueError(
            f"unknown receipt result {result!r}; expected one of "
            f"{sorted(RESULTS)}")

    return {
        "tool": plan.tool,
        "toolClass": plan.tool_class,
        "catalogVersion": plan.catalog_version,
        "planHash": plan.plan_hash,
        "idempotencyKey": plan.idempotency_key,
        "result": result,
        "applied": result == RESULT_APPLIED,
        "actor": actor,
        "detail": str(detail)[:500],
        # Identifiers masked, customer content omitted entirely. The plan hash
        # already pins the exact arguments without reproducing them.
        "arguments": plan_module.redacted_arguments(plan.arguments),
        "recordedAt": int(now if now is not None else time.time()),
    }


def record_receipt(plan: "plan_module.Plan", *, result: str,
                   detail: str = "", actor: str = "agent") -> Optional[str]:
    """Persist a receipt. Returns the audit log id, or None if the write failed.

    Never raises - see the module docstring for why that is acceptable today and
    what has to change before an APPLY is enabled.
    """
    receipt = build_receipt(plan, result=result, detail=detail, actor=actor)
    try:
        return audit.record_audit(
            action=_ACTIONS[result],
            actor=actor,
            resource_type="agent_tool",
            resource_id=plan.plan_hash,
            details=receipt,
        )
    except Exception:  # noqa: BLE001
        # `record_audit` already fails open; this guards a monkeypatched or future
        # sink that does not, so a receipt failure cannot become the caller's error.
        return None
