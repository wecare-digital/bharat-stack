"""Governance for AI-driven tools.

`governance` holds the tool catalog and the bounded read helpers. It is imported by
`ai/agent-action-group`, and is deliberately a shared module rather than private to
that handler: the next agent surface must inherit the same refusals instead of
re-deriving them, which is how the first set of ungoverned powers appeared.
"""

from lambda_utils.agent.governance import (  # noqa: F401
    CATALOG,
    CATALOG_VERSION,
    CLASS_APPLY,
    CLASS_PLAN,
    CLASS_READ,
    DEFAULT_READ_LIMIT,
    MAX_READ_LIMIT,
    Tool,
    ToolRefused,
    ToolUnknown,
    assert_executable,
    bounded_limit,
    catalog_summary,
    is_enabled,
    kill_switch_engaged,
    killed_tools,
    query_index,
    read_page,
    resolve,
)
from lambda_utils.agent.plans import (  # noqa: F401
    Plan,
    PlanNotApplicable,
    PlanStale,
    assert_plan_applicable,
    build_plan,
    canonical_arguments,
    catalog_fingerprint,
    describe_plan,
    plan_hash,
    redacted_arguments,
)
from lambda_utils.agent.receipts import (  # noqa: F401
    RESULT_APPLIED,
    RESULT_DUPLICATE,
    RESULT_FAILED,
    RESULT_REFUSED,
    RESULTS,
    build_receipt,
    record_receipt,
)
# Only the types are re-exported. `grant`, `check` and `consume` are deliberately
# NOT lifted into this namespace: bare `check(plan)` at a call site does not say what
# is being checked, and `assert_may_apply` reads as a general permission test rather
# than "spend a single-use human approval". Callers import the module -
# `from lambda_utils.agent import approvals` - so the verb keeps its subject.
from lambda_utils.agent.approvals import (  # noqa: F401
    Approval,
    ApprovalRejected,
)
from lambda_utils.agent.drafts import (  # noqa: F401
    DraftCorrupt,
    DraftMissing,
)

__all__ = [
    "Approval",
    "ApprovalRejected",
    "DraftCorrupt",
    "DraftMissing",
    "CATALOG",
    "CATALOG_VERSION",
    "CLASS_APPLY",
    "CLASS_PLAN",
    "CLASS_READ",
    "DEFAULT_READ_LIMIT",
    "MAX_READ_LIMIT",
    "RESULTS",
    "RESULT_APPLIED",
    "RESULT_DUPLICATE",
    "RESULT_FAILED",
    "RESULT_REFUSED",
    "Plan",
    "PlanNotApplicable",
    "PlanStale",
    "Tool",
    "ToolRefused",
    "ToolUnknown",
    "assert_executable",
    "assert_plan_applicable",
    "bounded_limit",
    "build_plan",
    "build_receipt",
    "canonical_arguments",
    "catalog_fingerprint",
    "catalog_summary",
    "describe_plan",
    "is_enabled",
    "kill_switch_engaged",
    "killed_tools",
    "plan_hash",
    "query_index",
    "read_page",
    "record_receipt",
    "redacted_arguments",
    "resolve",
]
