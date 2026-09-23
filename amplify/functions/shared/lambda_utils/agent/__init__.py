"""Governance for AI-driven tools.

`governance` holds the tool catalog and the bounded read helpers. It is imported by
`ai/agent-action-group`, and is deliberately a shared module rather than private to
that handler: the next agent surface must inherit the same refusals instead of
re-deriving them, which is how the first set of ungoverned powers appeared.
"""

from lambda_utils.agent.governance import (  # noqa: F401
    CATALOG,
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
    query_index,
    read_page,
    resolve,
)

__all__ = [
    "CATALOG",
    "CLASS_APPLY",
    "CLASS_PLAN",
    "CLASS_READ",
    "DEFAULT_READ_LIMIT",
    "MAX_READ_LIMIT",
    "Tool",
    "ToolRefused",
    "ToolUnknown",
    "assert_executable",
    "bounded_limit",
    "catalog_summary",
    "query_index",
    "read_page",
    "resolve",
]
