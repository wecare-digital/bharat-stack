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

## Branch checkpoint reconciliation

The shared checkout contains forward-revert e61a49c4 for its redundant local MID commit 57f5b505. It was not reverted again or altered by this session. Remote stack already contains the complete current purge and live deployment commit 27a3fb5d, so the pasted version-59/pending-VPA checkpoint is superseded. The remaining payment_readiness.py definition-list alignment and present-tense STALE wording were corrected to RETIRED/past tense without restoring either retired identifier. This follow-up changes source documentation only; live v60 continues to use the confirmed pair.

## Why "all other environment settings were preserved" — the method, for the next edit

The live-env correction above changed only `RAZORPAY_MID` and `RAZORPAY_UPI_ID` while keeping the function's other ~15 variables intact. That is not automatic and is easy to get catastrophically wrong: `aws lambda update-function-configuration --environment Variables={...}` **replaces the entire variable map**, so writing one key the obvious way silently deletes the rest — the function does not error, it just starts resolving defaults. It is the same failure shape that wiped three Cognito CUSTOM_AUTH triggers on 2026-09-28.

The safe path, used here and mandatory for any future single-variable change, is `scripts/set_lambda_env_flag.py`: it reads the current map, merges the one change, writes the whole map back, snapshots the before-state to disk, and then publishes a version and moves the `live` alias — because the HTTP API invokes `:live`, and a change to `$LATEST` does not reach production for the 58+ functions that carry an alias (`lambda-snapstart-deploy.md`). Never hand-run `update-function-configuration` with a partial `Variables` map against a live function.

This note was added after the fact: an earlier working branch's handoff doc that carried this reasoning was reverted during branch cleanup, and the operational "why" was briefly undocumented outside the tool's own header. Recorded here so it outlives any one branch.
