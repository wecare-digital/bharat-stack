# Retired Razorpay MID and VPA cleanup - 2026-10-02

The owner explicitly retained `acc_TTFSyolquKEZEy` and `wecaredigitalbh511413.rzp@rxairtel` and requested the retired pair be removed from current files and WhatsApp live deployment.

The first MID cleanup had corrected the merchant setting but left the retired VPA in live version 59 and in repository notes. This follow-up corrects that incomplete state.

- Current tracked repository files: zero occurrences of either retired identifier. Historical descriptions use placeholders rather than falsely substituting the current pair into old observations.
- Deployment manifest and frontend constants retain the owner-confirmed pair.
- The existing WhatsApp-business API live archive was narrowly patched to remove stale textual references in handler.py and lambda_utils/payment_readiness.py. No payment implementation or feature flag was enabled by this text cleanup.
- Release ZIP contains zero retired-identifier occurrences. SHA256: `108228c915c10292187624a2a68860da1c66159a61cd709ed2a788c711a5d48b`; Lambda SHA: `EIIoyRXBApIYdiSipohg2hxmFZphzXCe0qeIxxGl1Is=`.
- `wecare-whatsapp-business-api:live` now runs version 60. Both live environment values use the retained pair; all other environment settings were preserved inside AWS without returning credentials into context.
- Focused payment and canonical-secret checks: 125 passed.

Credential secrets were not deleted or rotated. This verifies non-secret account and UPI identifiers, not API-key ownership or completed payment settlement. Older Git history and retained deployment versions remain historical evidence and are not active configuration. No WhatsApp messages, OTPs, captures, refunds, or provider payment configuration writes were performed.
