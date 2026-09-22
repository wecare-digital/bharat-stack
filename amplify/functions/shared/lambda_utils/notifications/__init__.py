"""The shared, provider-neutral notification domain.

Replaces eight scattered connected-call notification producers - seven of which
fired on something that is not a connection - with one event contract, one claim
scheme, one state machine and one transactional outbox.

Public surface, in the order a producer meets it::

    service.handle_connected_call(params, provider=..., sender_phone_id=...)

That is the whole interface for a webhook handler. Everything below it is reachable
for workers and tests, but a producer should not need any of it:

    events        the normalized ConnectedCallEvent and its two adapters
    keys          claim-key derivation (parent + per-channel), v2
    policy        per-channel eligibility, provider and template selection
    states        the delivery state machine: legal moves and receipt ordering
    store         the four tables and the atomic claim-plus-publish
    suppression   cutover watermark and the legacy-notified ledger

Import the submodules rather than re-exporting their contents here. Each module has
a docstring explaining the failure it exists to prevent, and a flat namespace of
loose functions would separate `decide_rcs` from the reason it refuses to fall back
to Sinch outside India.
"""

from __future__ import annotations

__all__ = ["events", "keys", "policy", "service", "states", "store", "suppression"]
