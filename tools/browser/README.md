# Browser harness

Measurement scripts for the public pages. They render in real Chromium and compare
**rects**, because the things they check — reflow, overlap behind a fixed header,
controls inside a cross-origin iframe — are invisible to unit tests and to grep.

## Why this lives in the repo

It used to live in `/projects/pwtest`, outside the repo. A sandbox reset deletes that
entire directory, so the scripts vanished while the comments citing them survived in
git. `animcheck.js` ended up cited in four places — `src/pages/index.tsx`,
`src/components/RotatingHero.tsx`, `src/test/HomePage.test.tsx` and
`docs/grahak-os-handoff.md` — while existing nowhere on disk, and `mapprobe.js` was
cited by `ContactLocation.tsx` the same way. "Re-run the harness" was an instruction
nobody could follow.

Under `tools/browser/` the scripts are versioned with the code that cites them.

## Why Playwright is not in the app's package.json

This directory has its own `package.json` and depends on **`playwright-core`**, not
`playwright`. `playwright-core` never downloads a browser; it drives whatever binary it
is handed. That matters twice over: the app's own dependency tree stays free of a
browser-download postinstall that would run on every Amplify deploy, and the app's
lockfile — which is fragile enough already — is untouched.

## Setup

```bash
cd tools/browser
npm install          # one package, no browser download
```

Chromium is resolved at runtime by `lib/browser.js`, in this order: `$CHROME`, the
highest `chromium-*` revision under `/opt/playwright`, `~/.cache/ms-playwright`, then a
system Chrome. **Never hardcode the revision** — it changes across sandbox resets, and
a harness pinned to `chromium-1243` failed with "executable doesn't exist" on a box
holding `chromium-1232`, which reads like a broken harness rather than a moved browser
and cost a debugging round. If nothing is found the resolver throws naming every path it
searched.

If no Chromium is present at all:

```bash
cd tools/browser && npx playwright install chromium
```

## Running

Both scripts are dual-mode via `lib/serve.js`. With no `BASE` they boot their own static
server over `out/`; with `BASE` set they point at that origin and start nothing.

The `BASE` branch is verified against a separate static origin (identical results either
way). It has **not** been exercised against `next dev` in this sandbox: a dev server
started in one tool call is killed before the next call runs, so `curl` returns `000` and
it looks like the harness is broken rather than the server gone. To test dev, start the
server and run the harness in **one** command, and warm every route first — dev compiles
per route on first request, and an uncompiled route answers slowly enough to be measured
as a blank page.

```bash
npm run build                                          # produces out/
node tools/browser/animcheck.js                        # against the export
node tools/browser/contactcheck.js

BASE=http://localhost:3000 node tools/browser/animcheck.js   # against next dev
```

That distinction is load-bearing: `next.config.js` only sets `output:'export'` when
`NODE_ENV` is production, so `out/` is pre-generated HTML while dev is a live server
compiling per route. A suite that only ever ran against `out/` has not tested what you
see locally.

| Script | Checks |
|---|---|
| `lib/browser.js` | Chromium resolution; throws naming every path searched |
| `lib/serve.js` | Static server over `out/`, resolves `trailingSlash`, or honours `BASE` |
| `animcheck.js` | Rotating-headline reflow at 21 viewports (320–1920) on all four rotating surfaces, animation-family transition parity, console errors |
| `contactcheck.js` | Card and `#cl-title` vs the fixed header at 4 viewports, Google's in-frame controls with a click hit-test, keyless-embed tile canary |
| `seocheck.js` | The document head of all 15 public routes plus the 4 retired stubs: singleton tags, og/twitter derived from the page's own title and description, uniqueness, lengths, canonical and `og:url`, JSON-LD parse and `@id` conflicts, and that a real browser actually lands on `/contact/` from every retired URL |
| `typecheck.js` | Every visible `h1`/`h2`/`h3` on all 15 public routes at 2 widths; per-page consistency, the de-facto 40px rung, and the gap to the design contract |
| `uicheck.js` | Header lockup centring, and the two floating widgets: equal diameter, shared centre line, even gap, and that the open language panel clears the un-coverable WhatsApp button — 4 viewports |
| `homeprobe.js` | The home hero **off** the happy path: no-JS degradation, a viewport that changes after paint under reduced motion, the reduced-motion resting state, Tab stops that land on invisible controls, and whether anything above the fold is actionable |

## Current state

Re-measured 2026-09-26 against `out/`. The `seocheck` and `uicheck` figures previously
recorded here (12/12 and 28/28) were stale — both suites have grown since.

| Script | Result |
|---|---|
| `animcheck.js` | **18/18** |
| `seocheck.js` | **11/11** |
| `typecheck.js` | **3/3** |
| `uicheck.js` | **96/96** |
| `contactcheck.js` | **12/13** — the one failure is blocked on a Google Maps API key |
| `homeprobe.js` | **5/12** — seven open defects, see `docs/home-design-audit-20260926.md` |

Those failures are left red deliberately. They are not tuned to pass.

### Review mocks are deleted once their decision ships

The `*review.js` scripts write a standalone HTML page into `docs/` so a design choice can be
looked at before it is built. Those pages are **committed on purpose** — the owner reviews
this repository through a browser, so a file that is not committed cannot be seen, and
`.gitignore`-ing them would make the mocks useless to the one person they are for.

What they are not is permanent. A mock exists to settle one question; once the answer is
merged, the file is a large stale copy of a page that has moved on. Four of them had
accumulated to **3.07 MB** of committed HTML describing decisions that were already live:

| File | Size | Decision it settled |
|---|---|---|
| `home-review.html` | 1.3 MB | band 1 — shipped in #72 |
| `close-review.html` | 712 kB | band 3 — shipped in #71, #77 |
| `flow-review.html` | 608 kB | band 2 — shipped in #70, #71 |
| `post-layout-review.html` | 404 kB | blog layout A/B/C — “B”, shipped in #76 |

All four are deleted. **Regenerate any of them in one command** — the generators are still
here and read the current `out/`, so a regenerated mock is more accurate than the committed
copy was anyway:

```
npm run build                          # the mocks measure out/
node tools/browser/homereview.js       # -> docs/home-review.html
node tools/browser/flowreview.js       # -> docs/flow-review.html
node tools/browser/closereview.js      # -> docs/close-review.html
node tools/browser/postlayoutreview.js # -> docs/post-layout-review.html
node tools/browser/dividerreview.js    # -> docs/divider-review.html
```

**So the rule is: delete the mock in the PR that ships its decision.** Not gitignore — that
was the other option considered and it fails the only reader.

#### Two things that make a committed mock unopenable

Both were hit in sequence handing one file to the owner, and neither is obvious.

**1. GitHub serves raw `.html` as `text/plain`.** A committed HTML mock therefore displays as
*source*, not as a page. `raw.githack.com` re-serves it as `text/html` and does work — it
returned 200 — but it is a third-party domain and it did not open for the owner. So an HTML
mock cannot be the only artefact. `dividershots.js` renders the HTML one to PNGs plus a
Markdown wrapper, which GitHub renders inline with no proxy; the HTML stays for anyone who
wants the live animation and a Replay button.

**2. A branch name containing `/` breaks every `blob` URL on it.** This repo names branches
`fix/…`, `feat/…`, `docs/…`, and GitHub's URL is `/blob/<ref>/<path>` with no delimiter
between them — so for branch `docs/divider-review-png` and path `docs/divider-review.md`,
`/blob/docs/divider-review-png/docs/divider-review.md` is unparseable and 404s. `refs/heads/`
does **not** rescue it; that 404s too. Options: name the branch without a slash, or link
`/pull/<n>/files` instead, which always resolves.

**Verify the URL with `curl -o /dev/null -w '%{http_code}'` before sending it.** Both failures
above looked fine when the link was constructed and 404'd when it was clicked. The two review pages tracked
today are `divider-review.html` (20 kB, open question) and `mocks/home-hero/` (48 kB, a
hand-written reference rather than a generated mock).

`dividerreview.js` is also the pattern to copy for new ones: it is 18 kB rather than 1.3 MB
because it renders the component's real CSS values inline instead of embedding screenshots,
and its animations run live with a Replay button — a staggered reveal cannot be judged from a
still image, which is exactly how the footer entrance came back as a bug report twice.

`homeprobe.js` exists because everything else here passed while seven defects shipped. The
other suites all measure one settled state: JS running, motion allowed, viewport fixed at
load. Every `homeprobe` failure lives in a state none of them enters — JavaScript off,
`prefers-reduced-motion`, or a resize after first paint. A suite that only tests the happy
path has not tested the page.

### What `seocheck.js` found on its first run, and what it got wrong

Worth recording, because two of its three initial failures were the harness's fault and
"fixing" the code to satisfy them would have deleted correct markup.

**Real:** `/grahak-os/` carried **three different titles and three different descriptions at
once** — a `<title>`, an `og:title` and a `twitter:title` that were three separate strings,
and likewise for the descriptions. Nothing chose between them; whichever a crawler or
unfurler read first won, so the page described itself differently depending on where its
link was pasted. It now uses `PageMeta` like every other route.

**False positive — `@id` duplication.** The check counted every `@id` in the JSON-LD and
reported all 15 routes as emitting duplicates. But an object with only `@id` is a
*reference* to an entity defined elsewhere, which is the correct way to link JSON-LD — every
page's `WebPage` references `#website` via `isPartOf`, and its own `#breadcrumb`. Only an
object carrying **both** `@type` and `@id` is a definition. Fixed to count definitions only.

**False positive — the retired stubs.** They reported as "not noindex, refresh is null"
while being completely correct. Their `<meta http-equiv="refresh" content="0;url=/contact/">`
fires the moment the document parses, so by the time Playwright could evaluate anything the
browser was already on `/contact/` and the harness was reading **`/contact/`'s** head. A
redirect working too well is indistinguishable from a broken head if you only look at the
rendered DOM. The stubs are now read as **raw HTML over HTTP** — which is also what a
crawler that does not execute JavaScript receives, so it is the more honest assertion — with
a separate browser check that the redirect does land on `/contact/`.

The general lesson, and it is the same one `elementFromPoint` taught in `contactcheck.js`:
**decide what the measurement is actually measuring before believing its verdict.**

### Fixed: the rotating-headline reflow (was 4 failures in `animcheck.js`)

`/grahak-os/` and `/vayulok/` put their pill inline mid-sentence, so the h1's line count
depended on which word was showing and the page shifted every 2400ms. Measured before the
fix, using `heights [...]` per viewport across 18 widths:

| Route | Widths that jumped | Heights | Delta |
|---|---|---|---|
| `/grahak-os/` | 320 | 128 / 168px | 40px |
| `/grahak-os/` | 340–360 | 87 / 128px | 41px |
| `/vayulok/` | 320 | 87 / 126px | 39px |
| `/vayulok/` | 450–520 | 47 / 87px | 40px |

Note neither was one contiguous band — `/vayulok/` was already stable at 340–430 and at
560+, which is why the fix is two narrow media queries per page rather than one breakpoint.

The fix gives the pill, or the word after it, its own line **only at the widths that
measured broken**, and leaves every other width untouched:

- `/grahak-os/` — `.hero-mark{display:block;width:fit-content}` below 374px.
- `/vayulok/` — `.vl-head-tail{display:block}` below 559px, plus
  `.vl-mark{display:block;width:fit-content}` below 339px. The second rule is needed
  because at 288px of usable width `Bharat <Heatmap>` does not fit on one line while
  `Bharat <Air>` does.

Desktop line structure on both pages is byte-identical to before — that was the constraint,
since forcing the break at every width would turn a correct two-line headline into three
lines on every desktop. `width:fit-content` is required alongside `display:block` or the
tinted pill stretches to the full column.

Re-run `animcheck.js` after changing either word list: a word longer than `WhatsApp` or
`Heatmap` moves these thresholds.
- **`contactcheck.js` — 1 failure.** Three Google controls on the keyless map embed are
  reachable, not inert. See the long comment above `.cl-lock` in `ContactLocation.tsx`
  for the measurements and the three options.
  **When `NEXT_PUBLIC_GOOGLE_MAPS_KEY` is set**, `ContactLocation` renders a Maps JS div
  instead of an iframe and `contactcheck.js` switches to its keyed branch, which asserts
  four different things: the div has a box, Maps JS actually painted into it, no controls
  survived `disableDefaultUI`, and Google's attribution is present. That branch exists so
  the harness does not go silent on the map the moment it changes shape. Exercised once
  with a deliberately invalid key, which failed it correctly — a rejected key renders a
  blank grey panel and throws nothing, so "painted" is the assertion that catches a bad
  key, a referrer restriction that excludes the deploy origin, or billing being off. It
  has **not** run with a real key; read its printed numbers on the first real run.
### Fixed: the type contract (was 2 failures in `typecheck.js`)

The design contract specified `clamp(32px,4.2vw,54px)` = 53.76px at 1280, which existed on
`/grahak-os/` and **nowhere else**, while `clamp(28px,3.2vw,40px)` = 40px was on ten pages.
Both sides are now reconciled onto the 40px rung — `.kiro/steering/grahak-os-design.md`
records the reason, and `CONTRACT` in `typecheck.js` matches it. Keep the two in step; if
they disagree, the harness is the only one of the pair that gets measured.

Why 40px and not 54px: the hero h1 is `clamp(36px,4.3vw,60px)`, which resolves to 55.04px at
1280, so a 53.76px h2 sat **1.28px** below it. The h2 being the heavier weight (700 vs 600),
the hierarchy inverted and the h2 read as the larger of the two.

`typecheck.js` now separates two things it used to conflate:

- `NON_SECTION` — not a section heading at all (card titles, widget labels, and
  `.lgd-toc-title`, which is a 14px uppercase eyebrow that happens to be marked up as an
  `h2`). Correctly small; scaling them would be a regression.
- `RUNG_EXCEPTIONS` — genuine section headings deliberately off the rung, each needing a
  recorded reason. Currently one entry: `.lgd-h2` stays at 28px because `/terms/` and
  `/privacy/` carry 71 numbered legal sections between them (47 and 24), and at 40px each clause
  heading reads as a page title. Reported, not failed, with the reason printed.

An exception with no justification is drift with a comment on it — the default answer is no.

## Navigation: use `gotoStable`, not `waitUntil:'networkidle'`

Every harness here originally navigated with `waitUntil:'networkidle'`, and it failed the
first time the suite ran in CI: `typecheck.js` died on `page.goto: Timeout 30000ms exceeded`
**after** `animcheck` and `seocheck` had already passed green on the same runner.

`networkidle` resolves only after 500ms with no in-flight requests, so anything keeping a
connection warm — an analytics beacon, a font request that retries, a poll — can stop it
resolving at all. It is a proxy for "the page has settled" whose truth depends on conditions
that have nothing to do with the page. It is also flakiest on the harness that navigates
most: `typecheck` visits 15 routes at 2 widths, so it gets 30 chances to hit it where
`animcheck` gets 4. That is why the failure looked page-specific when it was not.

`gotoStable` in `lib/browser.js` waits for the thing that actually changes a measurement:
**`document.fonts.ready`**. Text width, line count and reflow all shift when a fallback face
is swapped for Inter, and that is the one late resource that can alter a number. Waiting on
the real dependency instead of on a correlate is both more correct and more reliable.

Switching all five suites over produced **byte-identical output** for every one of them,
which is the check to repeat if you change it again.

## `npm run build` can fail on a 429, and that is the build working

Re-running these suites means re-running `npm run build`, and the build fetches the blog
corpus. `src/lib/public-blog.ts` retries a 429 with jittered exponential backoff
(`MAX_ATTEMPTS = 4`) and then **throws on purpose**:

```
blog listing: gave up after 4 attempts (last: HTTP 429). Failing the build on purpose -
continuing would emit an index that links pages which were never generated.
```

That is `b4224003` ("A throttled blog fetch must fail the build, not ship a dead link"),
and it exists because a per-slug fetch that failed became `notFound`, which under
`output:'export'` emits no page while the index still renders the link — 219 dead links
reached the live site that way.

So a red build with that message is **not a code defect**. It is most likely you: several
full builds in quick succession, which is exactly what a measure-fix-re-measure loop does.
Wait, then build again. Do not raise `MAX_ATTEMPTS` to make your own loop quieter — it is a
measured value, and the failure it produces is the one that stops dead links shipping.

## Writing new checks

- Use **`window.__visible`** from `lib/visible.js` rather than writing a visibility test.
  Install it with `installVisible( page )` after `newPage()` and before the first `goto`.
  Seven suites here each grew their own version and no two agreed; the weakest was
  `r.width > 0 && r.height > 0`, which is a *box* test. Measured on `/grahak-os/`: written
  that way, a focusable sweep returns **28** elements where **7** are reachable — the other
  21 are links inside the closed nav panel. Used to assert "every focusable control has a
  focus ring" it fails on 21 controls nobody can reach, and the false result looks exactly
  like a regression in the page. `lib/visible.js` documents what it does and does not catch;
  read that before trusting it for occlusion or clipping.
- Compare **rects** from `getBoundingClientRect`, not DOM elements. "Is the element
  present" answers nothing about what a visitor can see.
- **Scope selectors.** `document.querySelector('input')` matched the header's nav search
  field rather than a sign-in field and produced a confident false failure.
- `elementFromPoint` takes **viewport** coordinates and returns `null` for anything
  off-screen. Scroll the target into view first. Not doing so returned `null` for all
  five map controls, which was then read as "the click was blocked" — the check passed
  while three controls were live. **Treat "could not tell" as a failure, never as a
  pass.**
- Suppress transitions before measuring a value that animates, or you will measure a
  mid-transition number with full confidence.
- Keep console-error allowlists narrow and justify each entry. A broad `/error/i` filter
  would have permanently hidden the `X-Frame-Options` error that these checks surfaced.
