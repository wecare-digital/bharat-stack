"""Immutable plans for agent tools. PLAN and dry-run; never APPLY.

A plan says what an APPLY *would* do, identifies itself with a stable hash, and
derives an idempotency key from that hash. `assert_plan_applicable` exists so the
call site is honest about where the gate is - and it currently refuses every plan,
because every APPLY tool is disabled.

Built while nothing can use it, on purpose. The alternative is building the approval
and receipt machinery at the moment somebody wants a send turned on, which is the
worst time to be designing it.

Three decisions worth defending
-------------------------------
**The timestamp is not in the hash.** Two identical intents must produce the same
key, because that is what makes a retry idempotent. This repeats the
`flow_completion` finding: a deliberately coarse key merges two genuine requests
*visibly*, while a key that is too fine splits a retry and performs the side effect
twice, invisibly. When the side effect is a customer message or a payment, the
invisible failure is the expensive one.

**The catalog version IS in the hash.** A plan approved under one version of the
tool definitions must not be applied under another, because the tool's meaning may
have changed underneath it. That is the entire content of the word "immutable"
here - not that the object is frozen in memory, but that it cannot be reinterpreted.

**The hash covers real values; the description carries masked ones.** Hashing a
masked phone number would collapse two different recipients into one plan, which is
exactly the class of bug the rest of this work has been removing. So the hash sees
`+918100640044` and `describe_plan` shows `…0044`, matching the masking convention
used at every other log site in this codebase.

Mapping key order is not significant; list element order is
-----------------------------------------------------------
`{"a": 1, "b": 2}` and `{"b": 2, "a": 1}` are the same intent, so the canonical form
sorts keys. `[{"sku": "a"}, {"sku": "b"}]` is NOT the same as its reverse - invoice
line items and recipient lists carry meaning in their order - so lists are left
alone. Sorting them would merge two genuinely different plans.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from lambda_utils.agent import governance as gov

# Argument names whose values are masked before they appear in a description or a
# receipt. The value still reaches the hash in full.
_MASKED_ARGS = frozenset({"phone", "phonenumber", "to", "from", "recipient",
                          "email", "contactphone"})

# Argument names never echoed at all, in any form. Customer content: the plan hash
# already identifies the exact body without reproducing it.
_OMITTED_ARGS = frozenset({"message", "content", "body", "text", "caption",
                           "description", "notes", "justification"})


class PlanNotApplicable(ValueError):
    """The tool has no plan/apply split - a READ just runs.

    Offering a plan for a read would invite a model to "apply" one and then narrate
    a side effect that never existed, which is the `createInvoice` failure again in
    a new place.
    """


class PlanStale(ValueError):
    """The plan was built against a different catalog version."""


@dataclass(frozen=True)
class Plan:
    tool: str
    tool_class: str
    catalog_version: str
    arguments: Dict[str, Any]
    created_at: int
    plan_hash: str
    idempotency_key: str


def catalog_fingerprint() -> str:
    """A hash of the catalog's SHAPE: name, class and enablement only.

    Prose is excluded deliberately. Rewording a refusal must not invalidate every
    outstanding plan; reclassifying a tool or enabling one must. Computed rather than
    declared, so forgetting to bump `CATALOG_VERSION` is still detectable.
    """
    shape = sorted((t.name, t.tool_class, bool(t.enabled))
                   for t in gov.CATALOG.values())
    blob = json.dumps(shape, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def canonical_arguments(arguments: Optional[Dict[str, Any]]) -> Any:
    """Arguments in a form two equivalent requests agree on.

    Mapping keys are sorted; list order is preserved. Values are stringified so
    `"1"` and `1` do not produce two plans for one intent - a model may send either
    and means the same thing.
    """
    def norm(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): norm(value[k]) for k in sorted(value, key=str)}
        if isinstance(value, (list, tuple)):
            return [norm(v) for v in value]
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return str(value)

    return norm(dict(arguments or {}))


def plan_hash(tool: str, catalog_version: str,
              arguments: Optional[Dict[str, Any]]) -> str:
    """Stable identity for an intent. No timestamp, no nonce."""
    payload = {
        "tool": str(tool),
        "catalogVersion": str(catalog_version),
        "arguments": canonical_arguments(arguments),
    }
    blob = json.dumps(payload, separators=(",", ":"), sort_keys=True,
                      ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def build_plan(tool: str, arguments: Optional[Dict[str, Any]] = None,
               *, now: Optional[int] = None) -> Plan:
    """A dry-run plan for an APPLY tool. Performs nothing.

    Raises `ToolUnknown` for a tool that does not exist and `PlanNotApplicable` for a
    READ, which has nothing to plan.
    """
    entry = gov.resolve(tool)
    if entry.tool_class != gov.CLASS_APPLY:
        raise PlanNotApplicable(
            f"{entry.name} is a {entry.tool_class} tool and has no plan/apply "
            f"split; call it directly instead of planning it")

    digest = plan_hash(entry.name, gov.CATALOG_VERSION, arguments)
    return Plan(
        tool=entry.name,
        tool_class=entry.tool_class,
        catalog_version=gov.CATALOG_VERSION,
        arguments=canonical_arguments(arguments),
        created_at=int(now if now is not None else time.time()),
        plan_hash=digest,
        # Namespaced so a collision cannot cross tools and a key is readable in a
        # log line without decoding it.
        idempotency_key=f"{entry.name}#{digest}",
    )


def redacted_arguments(arguments: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Arguments safe to log or repeat: identifiers masked, content omitted."""
    out: Dict[str, Any] = {}
    for key, value in (arguments or {}).items():
        lowered = str(key).lower()
        if lowered in _OMITTED_ARGS:
            out[key] = f"<omitted {len(str(value))} chars>"
        elif lowered in _MASKED_ARGS:
            text = str(value)
            out[key] = f"...{text[-4:]}" if len(text) > 4 else "..."
        else:
            out[key] = value
    return out


def describe_plan(plan: Plan) -> Dict[str, Any]:
    """What an APPLY would do, in a form safe to hand back to a model.

    `wouldApply` is computed from live enablement rather than hardcoded, so this
    cannot drift into claiming an apply is possible when it is not - or the reverse.
    """
    entry = gov.resolve(plan.tool)
    return {
        "tool": plan.tool,
        "toolClass": plan.tool_class,
        "catalogVersion": plan.catalog_version,
        "planHash": plan.plan_hash,
        "idempotencyKey": plan.idempotency_key,
        "createdAt": plan.created_at,
        "arguments": redacted_arguments(plan.arguments),
        "summary": entry.summary,
        "wouldApply": gov.is_enabled(plan.tool),
        "refusal": entry.refusal,
    }


def assert_plan_applicable(plan: Plan) -> Plan:
    """Raise unless this plan could be applied right now.

    Currently raises for every plan, because every APPLY tool is disabled. The
    function exists anyway so the gate has one home: a caller that later grows an
    apply path checks here rather than re-deriving the rule, which is how the first
    set of ungoverned powers came about.

    Order matters. The staleness check runs BEFORE the enablement check so that a
    plan built against an older catalog reports the real reason rather than a
    blanket refusal, which would send someone hunting the wrong problem on the day
    apply is enabled.
    """
    if plan.catalog_version != gov.CATALOG_VERSION:
        raise PlanStale(
            f"plan was built against catalog version {plan.catalog_version} and the "
            f"current version is {gov.CATALOG_VERSION}; rebuild the plan and have it "
            f"re-approved rather than applying it under changed definitions")

    expected = plan_hash(plan.tool, plan.catalog_version, plan.arguments)
    if expected != plan.plan_hash:
        raise PlanStale(
            "plan hash does not match its own contents; it was altered after being "
            "built and must not be applied")

    return gov.assert_executable(plan.tool)
