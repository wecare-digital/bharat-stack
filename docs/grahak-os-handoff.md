# Grahak OS frontend handoff

Updated: **2026-09-22**

Scope: the public `/grahak-os` page and the site language widget. The backend /
security track has its own handoff in `docs/kiro-handoff.md` — this does not
replace it.

Design rules live in `.kiro/steering/grahak-os-design.md` and load automatically
when you open files under `src/pages/grahak-os/`, `src/components/` or
`src/styles/`. **Read that before changing any CSS here.**

## Position

| Field | Value |
|---|---|
| Branch | `feat/grahak-os-trust-a-i` |
| HEAD | `b58ef424` — **the Mac session is now committing to this branch too**, so pull before starting |
| vs `origin/stack` | `origin/stack` merged in — **0 behind**, no conflicts |
| PR | **[#3](https://github.com/wecare-digital/bharat-stack/pull/3) open into `stack`, `mergeable: true`, all checks green** |
| Frontend gate | 33 vitest pass (7 files), `tsc` clean, `npm run build` clean, `/grahak-os` exported |
| Python gate | **1598 passed, 1 skipped** |
| Provider policy | all 8 rules `ok` |
| CodeQL | green — *"No new alerts in code changed by this pull request"* |

## Complete

| Commit | What |
|---|---|
| `e4db6a9a` | Google Cloud Translation inside `wecare-site-language`, key from Secrets Manager at request time. Cloud Run relay deleted from the client |
| `4fe013cb` | Hero mockup rebuilt to the reference composition — 90px panel lap, full code sample, 0 bubble collisions |
| `b18d4b98` | Language widget UI — moved clear of the mockup and the WhatsApp button, lists languages without typing |
| `6a230ef0` | Meta card made neutral, logo lockup colour fixed, duplicate self-declared badge removed |
| `131f885c` | Meta card stripped to mark + designation, both halves equalised at 201px |

Earlier in the branch: hero cycling channel pill with per-channel tint and dot,
notion type ladder and single body level page-wide, black brand lockup, footer
stripped to brand signature, `!important` overrides removed from `Header.tsx`,
trust section as equal columns with the S3 Meta mark.

## Pending

Ordered by what unblocks the most.

### 1. Merge PR #3 — one click, and it is what makes any of this visible

`origin/stack` has already been merged into the branch (no conflicts) and the gate
re-run on the merged tree. **PR #3 is open into `stack` and `mergeable: true`.**

**Amplify builds `stack`** (`amplify.yml`, artifacts from `out/`) and every
workflow is `branches: [ stack ]`. That is why none of this work was visible on
`https://stack.wecare.digital/grahak-os/` while it sat on a branch — pushing a
branch deploys nothing. Merging the PR triggers the Amplify build; allow a few
minutes, then hard-refresh past CloudFront. If the build fails it will be in the
`preBuild` npm install, which uses `--legacy-peer-deps`.

`stack` has **no required status checks configured**, so nothing blocks the merge.
**All checks are green now.** Two gates were red; both are fixed, and neither was
caused by this branch's work.

**`Handler auth enforcement (source)`** — fixed in `3f60088d`, and it had nothing
to do with route auth. Its dependency step greps `requirements-dev.txt` for an
allowlist that omitted `cryptography`, which `tests/test_flow_crypto_and_ssrf.py`
imports at module scope, so pytest failed at *collection* on every run, including
on `stack`. A blocking gate that fails unconditionally teaches people to merge
through red, which is worse than no gate because it looks like coverage.

**`Provider policy gate`** — a scanner false positive, fixed in `9c43e67b` by the
Mac session. `plivo-answer` passed a bare `provider='plivo'` into
`notifications.handle_connected_call`, where that argument only selects which
voice-callback parser to run (`PROVIDER_PLIVO` → `from_plivo_dial_callback`,
`PROVIDER_META` → `from_meta_call_event`). It is a call-event discriminator, not an
SMS transport. The fix passes `notif_keys.PROVIDER_PLIVO` instead, and
`check-provider-policy.sh` now documents the convention.

Read that comment before touching this rule again: it explicitly rejects adding a
path exclusion to silence the gate, because that would blind it to a real Plivo SMS
assignment in the same file. Pass the named constant instead.

**`github-advanced-security`** cleared once CodeQL re-ran. Final state is explicit:
*"No new alerts in code changed by this pull request."*

### 2. Deploy the translation change — needs the Mac

```bash
python scripts/deploy_site_language.py
```

Until this runs, **translation still serves Amazon Translate**. The code is
committed and safe to deploy either way: provider defaults to `auto`, so a missing
key or a disabled API degrades to Amazon silently.

### 3. Enable Cloud Translation on the Google key — needs the Google console

The secret already exists: **`wecare/google/cloud`, field `api_key`** ("unified
Google API key", registered in `scripts/store_provider_secret.py`). Do **not**
create a `wecare/google-translate` — a parallel id means rotation updates one copy
and consumers keep reading the other.

Two things must be true on that key: Cloud Translation API **enabled** on the
project, and the key **not restricted** to other APIs. CloudWatch will name the
failure after deploy:

```
{"event":"google_translate_failed","error":"RuntimeError: google http 403: SERVICE_DISABLED","fallback":"aws"}
```

`SERVICE_DISABLED` → enable the API. `API_KEY_SERVICE_BLOCKED` → widen the key's
restrictions. `{"event":"translate_provider_resolved","provider":"google"}` → working.

Cost note: Google is ~$20/M characters after 500k free per month; Amazon Translate
is ~$15/M. Google is chosen for Indic quality, not price. The real cost control is
the existing DynamoDB cache (90-day TTL) plus request dedupe.

### 4. Verify the Meta designation string — needs the partner portal

The page says **"Meta Tech Partner"**. That could not be confirmed as a real Meta
designation: the badge Meta grants is **Meta Business Partner** (technology
providers are a category within it), it is awarded after review, and it cannot be
self-declared. Meta's brand guidance is also to use the logo files they publish
rather than a re-typed wordmark — the `.trust-wordmark` span is a stand-in.

The self-declared caps pill was removed. The remaining string is unchanged on
purpose: altering a partnership claim is the owner's call. One-line fix once
confirmed.

### 5. Wix still calls the uncapped Cloud Run relay — needs a decision

The Stack app no longer touches `wecare-translation-relay`, but the Wix site still
does for translation and TTS. **That is now the only path billing Google with no
request cap.** Note `stack` recently gained
`shared/wix-velo/backend/google-services.web.js`, a Wix backend web method that
reads `GOOGLE_SERVER_API_KEY` from Wix's own Secrets Manager — but it covers
weather / forecast / air / solar only, not translation.

Recommended: point Wix at `/site-language/translate` rather than adding translate
to the Wix module, because the Wix module has no cache and translation is the one
Google service that repeats constantly. The Wix domains are already in
`ALLOWED_ORIGINS`.

Also worth recording: there are now **two secret stores holding a Google key** —
AWS `wecare/google/cloud` and Wix `GOOGLE_SERVER_API_KEY`. If they hold the same
underlying key, a rotation must update both.

### 6. Home page is an empty scaffold

`src/pages/index.tsx` renders `home-shell` / `home-layout` divs and nothing else.
Not started. Should follow the same contract in
`.kiro/steering/grahak-os-design.md`.

### 7. Smaller items

- Section rhythm was never implemented — every section is `background:#fff`.
- `.why-section` has no `max-width` (~1391px vs `.api`'s 1300px).
- `_app.tsx` `mounted` gate ships an empty body on static export, so JSON-LD and
  meta are invisible to non-JS crawlers.
- `LanguageBar.tsx` has one **pre-existing** ESLint error
  (`react-hooks/set-state-in-effect`, the restore-saved-language effect). Verified
  present at HEAD before this session's changes; deliberately untouched because
  that effect governs language restore behaviour.
- `/site-language/*` routes are intentionally unauthenticated — the handler
  explains why — and the mitigation is the API Gateway throttle
  (15 rps / 30 burst) in `scripts/deploy_site_language.py`, not auth.

## Running it locally

Windows PowerShell 5.1 has no `&&`; chain with `;`. Single line, self-checking:

```powershell
cd C:\Users\wecar\bharat-stack; taskkill /IM node.exe /F 2>$null; git pull origin feat/grahak-os-trust-a-i; $h = git log --oneline -1; Write-Host "HEAD: $h" -ForegroundColor Cyan; if ($h -notlike "131f885c*") { Write-Host "WRONG COMMIT - stopping" -ForegroundColor Red } else { Remove-Item -Recurse -Force .next -ErrorAction SilentlyContinue; npm run dev }
```

Then `http://localhost:3000/grahak-os/` — **trailing slash required**
(`trailingSlash: true`), and **Ctrl+Shift+R** not F5, because styled-jsx CSS is
cached in `.next` and a plain refresh makes real changes look invisible.

`nvm` is not installed on that machine and is not needed — Node 24.19.0 is the
system Node.

## Environment notes

- Windows, repo at `C:\Users\wecar\bharat-stack`. Duplicate clones exist at
  `bharat-stack-preview` and `Workspaces\bharat-stack` — check `git log --oneline -1`
  before concluding a change "did not apply".
- `gh` CLI is not installed locally.
- All four hooks in `.kiro/hooks/` hardcode a macOS path
  (`D=/Users/wecaredigital/wecare-store`) and need Python, which is absent on the
  Windows machine. **The inline-secret guard described in
  `.kiro/steering/secret-handling.md` therefore does not run there.** Treat that
  rule as manual until the hooks are fixed.
- Grammarly injects attributes into `<body>` and causes a hydration warning.
  `suppressHydrationWarning` was drafted on a since-deleted branch and is **not**
  applied on this one.
