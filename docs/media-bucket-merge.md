# Merging `app.wecare.digital` into `wecare-digital-get` — done, and what cannot follow

Measured and executed 2026-09-26.

## What is done

All 286.6 MB copied into `wecare-digital-get` under the existing `o/` prefix,
preserving key structure so the mapping is 1:1 and reversible:

    app.wecare.digital/stream/media/m/logo.png
      -> wecare-digital-get/o/stream/media/m/logo.png
      -> https://wecare.digital/get/o/stream/media/m/logo.png

The `/get/<*>` Amplify rewrite already proxies that bucket through CloudFront
`E2GP22R4BIFGQ3`, so nothing new had to be provisioned to serve it.

### Verified by key, not by count

The object counts deliberately do **not** match, and the reason is worth recording
because a count comparison would have looked like data loss:

| | |
|---|---|
| source objects | 266 |
| copied | 255 |
| skipped | **11, every one zero-byte** |
| extra at destination | 2 (pre-existing `o/healthcheck.txt`, `o/sample.txt`) |
| size mismatches | **0** |

The 11 skipped keys are S3 "folder marker" objects ending in `/` —
`ivr-cache/`, `ivr-prompts/`, `ivr-recordings/`, `stream/blog/`,
`stream/blog/archive/`, `stream/blog/manifests/`, `stream/blog/pilot/`,
`stream/blog/source/`, `stream/media/fonts/`, `stream/media/m/`,
`stream/media/reports/`. They hold no data and `aws s3 sync` correctly ignores
them. 266 − 11 = 255, matching the dry run exactly.

The byte total at the destination is 459 higher, which is precisely
27 + 432 — the two files that were already in `o/`.

Then proven behaviourally: five files fetched from both hosts and compared by
SHA-256, including the PNG, the SVG, the RCS video and `error.html`. All identical.

## What must NOT follow: the old host cannot be switched off

Same shape as the `r.wecare.digital` decision, and for a harder reason.

### 1. Meta-approved template media

`public/wa-tpl/` holds **61 objects**, and those URLs are embedded in WhatsApp
templates that Meta has already **approved**. Meta fetches the media from the URL
stored in the approved template at send time. Repointing `CDN_DOMAIN` changes what
*new* templates use; it does not rewrite templates already approved.

So retiring `app.wecare.digital` breaks approved templates until every one is
resubmitted and re-approved — and the standing rules forbid disturbing template
registration. This is the binding constraint.

### 2. BIMI is a live email-auth record

    default._bimi.wecare.digital
    "v=BIMI1; l=https://app.wecare.digital/stream/media/m/wecare-digital.svg; a=; avp=brand;"

The domain runs `p=reject` with fail-closed MTA-STS. The logo file now exists at
both locations, so the `l=` URL *could* move, but it is an email-authentication
record and belongs to the verify-before-and-after procedure in
`.kiro/steering/email-auth-dns.md`, not to a bulk find-and-replace.

### 3. Already-delivered content

RCS cards registered with Sinch and already on handsets, WhatsApp and SMS messages
already sent, and PWA icons cached by installed apps all reference the old host.
None can be edited after delivery.

## Repointing the 319 references

319 occurrences across 116 files. The good news is that the Lambda side is
**environment-driven, not hardcoded**, so most of it is config rather than code:

    MEDIA_BUCKET        = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
    CDN_DOMAIN          = os.environ.get('CDN_DOMAIN', 'app.wecare.digital')
    PUBLIC_MEDIA_PREFIX = os.environ.get('PUBLIC_MEDIA_PREFIX', 'public/wa-tpl/')

`config/lambda-env-manifest.json` carries 35 of those references, meaning the
values are already set per function and can be moved without a code deploy.

Safe to repoint, because they affect only what is rendered or minted next:

- UI asset URLs (`_app.tsx` logo/favicon, `manifest.json`, `sw.js`)
- SEO schema templates
- `MEDIA_BUCKET` / `CDN_DOMAIN` on functions that WRITE new media

Not safe to repoint by search-and-replace:

- `public/wa-tpl/` URLs inside approved templates — provider-side, needs re-approval
- the BIMI `l=` URL — email-auth change procedure
- `rcs/templates/**` entries already registered with Sinch — provider-side

## Recommended end state

Keep both. `wecare-digital-get/o/` becomes the canonical location that new media is
written to and served from; `app.wecare.digital` stays mapped indefinitely as a
read-only alias honouring URLs already committed to approved templates, delivered
messages and DNS. That is the same conclusion the URL shortener reached: migrate what
you *mint*, honour what you already *issued*.

Retiring the old host is a provider-coordination project — resubmit every affected
WhatsApp template, move BIMI, re-register RCS media — not an infrastructure change.

---

## Addendum, 2026-09-28 — the bucket went, the host stayed, the code never followed

Two things happened after the merge above, and together they produced a class of silent
failure worth recording.

### The old bucket was deleted; the old host was not

`aws s3api list-buckets` now returns six buckets and `app.wecare.digital` is not among
them. But `https://app.wecare.digital/...` still answers **HTTP 200**, because CloudFront
`E1DP37QIS4G0T4` was repointed at `wecare-digital-get` with **origin path `/o`**:

| Host | Distribution | Origin path | `<X>` resolves to |
|---|---|---|---|
| `wecare.digital/get/<X>` | `E2GP22R4BIFGQ3` | `""` | `<X>` |
| `app.wecare.digital/<X>` | `E1DP37QIS4G0T4` | `/o` | `o/<X>` |

So the "keep both" recommendation above was implemented, and the 61 Meta-approved
template media URLs still resolve. That is the good news, and it is also precisely what
makes the `o/` prefix **load-bearing rather than cosmetic**: an object is reachable on
both hosts only if its key starts with `o/`.

### The handler prefixes were never repointed

The section above says the Lambda side is "environment-driven, not hardcoded", and that
was right about the **bucket** and wrong about the **key**. Every `*_PREFIX` default still
carried the pre-merge shape — `stack/whatsapp-media/incoming/`, `public/wa-tpl/`,
`stream/media/m/...` — with no `o/` segment, because on the old bucket the whole bucket
*was* the public root.

Measured consequences, all live until 2026-09-28:

| Symptom | Cause |
|---|---|
| Invoice PDFs lost their logo and monospace font | `stream/media/m/wecare-digital.png` and `stream/media/fonts/DejaVuSansMono.ttf` are absent at the root, present under `o/` |
| Document downloads returned a dead URL | `DOCS_S3_BUCKET` was `wecare-digital-media` live and `wecare-digital-documents` in code — **neither bucket exists** — and the stored `storageKey` lacked `o/` |
| `system-cleanup` deleted nothing, reporting success | all 11 TTL prefixes plus `S3_ROOT_PREFIX` targeted `stack/` at the root, which holds zero objects |
| Wix product-image upload raised `NameError` | `S3_PRODUCT_PREFIX` was referenced but never defined anywhere in the repo |

None of these raised an alarm, and the reason is uncomfortable: a key written to the
bucket root still serves **HTTP 200** on the apex host. Verified by probe — a key at the
root and the same key under `o/` both returned 200, while a key under `secure/` returned
302. So a write to the wrong folder looked perfectly healthy from the apex and was simply
invisible to `app.wecare.digital`.

### What was done

`amplify/functions/shared/lambda_utils/media_paths.py` now owns the convention —
`PUBLIC_ROOT = "o/"`, `SECURE_ROOT = "secure/"`, plus `public()`, `secure()`,
`canonical()` and `public_url()`. 24 handlers compose their keys through it, and keys read
back out of DynamoDB go through `canonical()`, which roots a legacy un-prefixed key
without ever moving one between the public and gated roots.

No objects were moved. The data was always in the right place; the code was addressing one
level above it.

`scripts/verify_media_prefixes.py --live` enforces all of this, including the ordering
trap that caught three handlers on the first deploy: `media_paths` imported *below* its
first use is a module-scope `NameError` that byte-compiles cleanly and only fails when the
function is invoked.

### Closed out on 2026-09-28

- **`paid_icon_s3_key` was deleted from `invoice-engine`.** It was read by nothing — a
  repo-wide search found one definition and zero uses — and `stream/media/m/paid.png` has
  no object *and no version history* in this bucket, so it was never migrated and probably
  never existed. A config key naming an unfetchable file that nothing fetches is the exact
  drift this audit was chasing.
- **`ai-generate-response` now resolves per-contact media from the message rows.** The new
  `_media_keys_for_contact` scans the messages table on `contactId` and roots each `s3Key`
  through `canonical()`, because the message row is the only thing that associates media
  with a contact. Verified against live data: 2 files (92266 and 68334 bytes), both needing
  rooting, where the old `media/<contactId>/` listing returned **0 objects**. The delete
  path refuses a `secure/` key outright, so a conversation-media tool cannot reach the
  gated tree.
- **`system-cleanup`'s docstring was corrected.** It claimed deletion happened "on
  confirm"; there is **no server-side confirmation token**. The gate is `require_auth` plus
  an explicit `selected` list, and the word "confirm" referred to a dialog in the admin UI.
  No EventBridge rule targets it. Worth stating plainly now that its prefixes reach real
  data.
- **`config/lambda-env-manifest.json` is at key parity with live.** 26 keys added, 2 stale
  removed, `--keys-only` now reports 0 differences. `scripts/env_manifest.py --keys-only`
  is a new mode that measures key-level drift from Lambda configuration alone, printing
  names and never values, so the scope of a drift can be established without the Secrets
  Manager read that `--export` requires. Every key added was cleared by env_manifest's own
  `SECRET_FIELD`/`CONFIG_FIELD`/`SHAPES` classifiers rather than by eye. A full `--export`
  is still the only thing that can detect a changed **value** on a key present in both.
- **`.github/workflows/media-prefixes.yml` makes the guard blocking.** A credential-free
  `source-gate` runs on every push and PR; a `live-gate` skips until
  `MEDIA_PREFIX_ROLE_ARN` is set. The checks are AST-based, after text scanning produced
  false positives in both directions — per-line missed rooting on a continuation line, and
  per-statement then flagged the prose *documenting* the convention.

### Still outstanding

- **24 objects under `o/stream/media/m/` are behind delete markers created 2026-09-28
  06:48–06:49**, including `selfservice.mp4`, `WECARE+SC.png` and `qr-selfservice.png`.
  `docs/execution/snapshots/get-delete-markers-removed-20260928.json` records markers being
  removed at 06:43–06:46, and new ones appeared 3–6 minutes later, so something is
  re-deleting them. **7 RCS template files registered with Sinch reference
  `selfservice.mp4` and `WECARE+SC.png` as `mediaUrl`/`thumbnailUrl`.** The 459-byte
  `qr-selfservice.png` version is intact behind its marker and recoverable. Not touched
  here, because this is another session's active media-parity work and a blind restore
  would thrash against whatever is re-deleting.
- **`app.wecare.digital` maps both 403 and 404 to HTTP 200 serving `/error.html`.**
  Confirmed by fetch: a missing object returns `200` with `content-type: text/html`, 596
  bytes, `x-cache: Error from cloudfront`. This is why the deletions above are invisible —
  and it means **Meta fetching an approved template's media gets a 200 and an HTML page
  instead of a 404**, so a broken template looks healthy to every status-code check. The
  apex distribution `E2GP22R4BIFGQ3` has no custom error responses and is unaffected.
  Fixing it means an `update-distribution` on the host serving Meta-approved media, which
  needs the entire `DistributionConfig` plus a matching `ETag` — a production CDN change
  worth deciding deliberately rather than folding into this one.
- A deleted object can still serve from the edge cache: `wecare-digital-rcs-h.png` has a
  live delete marker yet returned `200 image/png 89548 bytes`. "It works now" is not
  evidence the object exists.
- The docs-scraper image deploys from a workflow whose path filter covers
  `amplify/functions/operations/docs-scraper/**` but **not**
  `amplify/functions/shared/lambda_utils/**`, so a change confined to the shared module
  would not rebuild that image.
