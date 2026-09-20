# Externally-deployed functions

These Lambdas run in account `775261844268` but are **not** deployed by
`scripts/deploy_all_lambdas.py`. Their source is kept here so they are
version-controlled, reviewable and greppable. Editing a file here does **not**
deploy it.

## Why this directory exists

On 2026-09-20 an orphan audit found nine live Lambdas with no source anywhere in
this repo. They could not be patched, reviewed or diffed, and nothing in the
codebase revealed they existed. Three were retired-provider leftovers and were
deleted; one was a debugging scratch function and was deleted; the five here are
serving real traffic and were recovered from their deployed packages.

The concrete cost of the gap: `wecare-elevenlabs-postcall-sms` is an **enabled
DynamoDB stream consumer on `stack-wecare-digital-VoiceCDRTable`**. That is the
same table `plivo-answer._persist_cdr` writes to. Anyone changing the CDR write
path — which happened the same day, in `dd59173b` — had no way to discover a
consumer was attached to it. A stream trigger you cannot find in the source tree
is a trap, not an integration.

`scripts/check_provider_policy_live.py` treats anything listed in its
`EXTERNALLY_DEPLOYED` set as known; every other live function absent from the
deploy map fails the gate. Adding a function to AWS without adding it here or to
the deploy map is therefore now a build failure rather than a silent orphan.

## Contents

| Function | Trigger | Notes |
|---|---|---|
| `elevenlabs/postcall-sms` | **DynamoDB stream on `VoiceCDRTable`**, Enabled | Filters `id` prefix `elevenlabs#` and `event_type == post_call_transcription`. Sends the IVR follow-up SMS through `wecare-sms-aws:live` with `dltTemplateKey='ivr-default'`. Has its own idempotency lock (`sms_lock` / `sms_sent_at` on `ElevenLabsCallContext`). |
| `elevenlabs/call-hooks` | direct invoke | env: `AGENT_ID`, `PERSIST_FUNCTION`, `SMS_FUNCTION`, `SECRET_ID`, `TABLE_NAME` |
| `elevenlabs/mcp` | direct invoke | env: `SECRET_ID`, `SMS_FUNCTION` |
| `elevenlabs/init` | direct invoke | one-shot setup |
| `elevenlabs/enable-mcp` | direct invoke | one-shot setup |

All five are `python3.12`, single-file, handler `index.handler`.

## Known issue — duplicate post-call SMS

`elevenlabs/postcall-sms` and the Plivo connected-notification path
(`lambda_utils/pstn/notifications.py` via `/plivo/dial-events`) both send a
post-call SMS under the **same DLT template key `ivr-default`**, and they use
**different** idempotency stores: `ElevenLabsCallContext.sms_lock` versus the
PSTN claim table. Neither dedupes against the other, so a call that traverses
both paths texts the customer twice under our registered DLT sender. Not yet
reproduced against live traffic; recorded here rather than silently "fixed",
because the correct answer depends on which path should own the follow-up.

## Also externally deployed, but not stored here

- `wecare-seo-tools` — owned by `scripts/deploy_seo_tools.py` (different in-zip
  layout, plus its own table and IAM policy). Source lives under `amplify/`.
- `wecare-docs-scraper` — `PackageType=Image`, ships via
  `.github/workflows/docs-scraper-deploy.yml`.
