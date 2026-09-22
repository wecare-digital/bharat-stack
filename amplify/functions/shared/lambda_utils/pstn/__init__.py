"""Provider-neutral PSTN calling.

The seam between call handling and Plivo. Business code and the operations UI depend
on these shapes, not on provider field names, so a provider field being renamed is a
one-module change rather than a fleet-wide one.

    browser_token   Cognito-protected Browser SDK token minting

Notifications moved out, 2026-09-21
-----------------------------------
This package used to own connected-call notifications through three modules:

    keys            v1 claim-key derivation
    claims          fail-closed atomic claims
    notifications   the connected-event gate, eligibility and dispatch

All three are deleted. They now live in `lambda_utils.notifications`, which is
provider-neutral rather than PSTN-specific - the same domain serves WhatsApp Calling -
and which fixes three defects the originals carried:

* **Recipient.** `notifications.handle_connected` parsed `Direction` and then chose
  `event.caller` unconditionally, so a connected *outbound* call would have texted our
  own business CLI.
* **Durability.** The claim was written, then dispatch was attempted. A crash between
  the two left a claim nothing owned, and the provider's redelivery then found it
  taken and did nothing - a notification lost silently. The replacement writes the
  claim and the job in one transaction.
* **Existence.** `claims` defaulted to `stack-wecare-digital-PstnNotificationDelivery`,
  which was declared in four places and existed in none of the 66 live tables, so
  every claim raised `ClaimStoreUnavailable` and the route answered 503.
  `plivo_dial_event` fired 0 times in 14 days as a result.

The fail-closed reasoning those modules established was kept, and is restated in
`lambda_utils.notifications.store`: `webhook_dedup.claim_event` fails OPEN because
dropping a real inbound webhook is worse than processing it twice, and that trade
inverts when the side effect is sending a customer a message.
"""

__all__ = []
