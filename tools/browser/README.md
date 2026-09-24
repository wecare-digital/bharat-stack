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

## Known failures, and why they are left failing

Neither script is green, and both are honest about it rather than tuned to pass.

- **`animcheck.js` — 4 failures.** `/grahak-os/` and `/vayulok/` reflow at narrow
  widths: their pill sits inline mid-sentence, so the h1's line count depends on the
  active word and the page shifts every 2400ms. Measured: Grahak OS at 320px is 168px
  on `WhatsApp` against 128px on the other three; VayuLok at 320px is 126px on
  `Weather`/`Forecast`/`Heatmap` against 87px on `Air`/`Pollen`/`Solar`. Home and every
  surface built on `RotatingHero` put the pill on its own line and measure constant.
  Fixing the two inline copies changes their hero line structure, so it is an owner
  call, not a patch.
- **`contactcheck.js` — 1 failure.** Three Google controls on the keyless map embed are
  reachable, not inert. See the long comment above `.cl-lock` in `ContactLocation.tsx`
  for the measurements and the three options.

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
