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
