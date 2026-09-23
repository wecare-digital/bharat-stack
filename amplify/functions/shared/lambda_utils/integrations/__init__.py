"""Outbound data integrations: a shared registry and a uniform read result.

`registry` is deliberately the only module here for now. It describes providers and
never calls them, because a registry that fetches is a status page that costs quota.
Adapters, when they exist, import from here rather than re-deriving ownership,
scopes and freshness per call site.
"""

from lambda_utils.integrations.registry import (  # noqa: F401
    ACCESS_CREDENTIAL_ABSENT,
    ACCESS_SCOPE_UNVERIFIED,
    ACCESS_STATES,
    ACCESS_VERIFIED,
    REGISTRY,
    Provider,
    ReadResult,
    describe_registry,
    resolve,
    waiting_for_owner,
)

__all__ = [
    "ACCESS_CREDENTIAL_ABSENT",
    "ACCESS_SCOPE_UNVERIFIED",
    "ACCESS_STATES",
    "ACCESS_VERIFIED",
    "REGISTRY",
    "Provider",
    "ReadResult",
    "describe_registry",
    "resolve",
    "waiting_for_owner",
]
