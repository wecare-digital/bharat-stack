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

## Current state

| Script | Result |
|---|---|
| `animcheck.js` | **18/18** |
| `seocheck.js` | **12/12** |
| `typecheck.js` | **3/3** |
| `uicheck.js` | **28/28** |
| `contactcheck.js` | **12/13** — the one failure is blocked on a Google Maps API key |

The single remaining failure is left red deliberately. It is not tuned to pass.

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
  `/privacy/` carry 45 numbered legal sections between them, and at 40px each clause
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

## Writing new checks

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
