"""Provider-neutral PSTN calling.

The seam between call handling and Plivo. Business code and the operations UI
depend on these shapes, not on provider field names, so a provider field being
renamed is a one-module change rather than a fleet-wide one.

    keys       idempotency key derivation - the exact claim-key format
    claims     fail-CLOSED atomic claims for side effects that must run once
    calls      PstnCall records, A/B leg correlation, cost attribution
    events     PstnCallEvent normalisation from provider callbacks
    presence   PstnAgentPresence with expiring availability

Why not reuse webhook_dedup
---------------------------
`lambda_utils.webhook_dedup.claim_event` fails OPEN: on any DynamoDB error it
returns True so a real webhook is never dropped. That is the right trade for an
inbound event you merely want to process once.

It is the WRONG trade for deciding whether to send a customer a message. Failing
open there means a store outage produces duplicate SMS to real people, billed to
us, under a registered DLT sender. `claims` therefore fails CLOSED and raises, so
the caller returns a retryable 5xx and the provider redelivers.

Both behaviours are correct for their own job, which is why this is a separate
module rather than a flag on the existing one - a flag would eventually be passed
wrongly.
"""
from .keys import (  # noqa: F401
    CONNECTED_NOTIFICATIONS_VERSION,
    channel_delivery_id,
    connected_claim_key,
    parse_channel_delivery_id,
)

__all__ = [
    "CONNECTED_NOTIFICATIONS_VERSION",
    "channel_delivery_id",
    "connected_claim_key",
    "parse_channel_delivery_id",
]
