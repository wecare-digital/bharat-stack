# `.home-flow` — the home page section below the hero

Deep-check of the second section on `/` (`src/pages/index.tsx`, section at line 352).
The hero above it was corrected in #55; this is the next one down.

**Nothing here is applied to `src/`.** This is a mock for a decision.

## View it

`mock.html` is an **interactive mock**, not a picture. It renders the real section and lets
you toggle each of the three proposed fixes on and off, at six widths, with a live readout
of what each state measures.

Rendered in a browser, no clone or build needed:

**https://raw.githack.com/wecare-digital/bharat-stack/mock-device-audit/mock/home-flow/mock.html**

Or locally: `open mock/home-flow/mock.html` — it is a single self-contained file, no server.

The three PNGs are only there for anyone who cannot open the HTML:
`live-1024-as-is.png`, `live-1024-fixed.png`, `interactive-mock-full.png`.

> This is the first HTML mock in this repo. Every earlier one — header, footer, widget,
> language search, device audit — was PNG boards only.

## The three flaws

**1. The copy column has no `max-width`.** In two columns it sits in a 380px track — 47
characters per line, a proper measure. At ≤1024px the grid collapses and the column inherits
the full page width, so the same paragraph runs **120 characters** at 1024px and 88 at 768px.
The convention is 45–75. Both neighbours on this same page already cap themselves
(`.home-sub` at 560px, `.home-close-lead` at 782px), so this column is the outlier on its own
page.

**2. Two breakpoints were set independently and do not meet.** `.home-flow` drops to one
column at `max-width:1024px` (index.tsx:763). `.wt-window` steps 650px → 560px at
`max-width:767px` (WorkflowTerminal.tsx:466). Everything from **768px to 1024px** gets the
narrow layout *and* the desktop panel height: a 650px black panel at 100% of the measure with
nothing beside it — verbatim the condition the code comment says the two-column band was
introduced to remove. Six of eleven sampled widths are in that band, **including every iPad
in portrait** (768, 820, 834) plus Surface Pro and 1024.

**3. The h2 tracking is a fixed pixel against a fluid size.** `-1.2px` on
`clamp(28px,3.2vw,40px)` resolves to −3.00% at 40px, −3.66% at 32.8px and −4.29% at 28px.
Since #55 unified the h1 to a flat `-0.04em`, the page's two biggest headings now track
differently on desktop.

## Recommended

| # | Change | Reach |
|---|---|---|
| 1 | `.home-flow-copy{max-width:680px}` inside the existing `@media(max-width:1024px)` block | this section only |
| 2 | `767px` → `1024px` on the terminal's height media query | shared component, check other callers |
| 3 | `-1.2px` → `-0.03em` | **12 headings on 10 pages — needs a decision** |

Fix 3 is deliberately not recommended unilaterally. The comment above the rule records that
`.home-flow-title` is byte-for-byte identical to `.home-close-title`, `.cl-h2`, `.mo-h2`,
`.brx-h2` and `.pdp-h2`, and instructs that `node tools/browser/typecheck.js` be run before it
changes. `-0.03em` is chosen so the desktop rendering does not move at all (−0.03 × 40px =
exactly −1.2px); only the narrow end moves, toward the value desktop already has.

## Checked and **not** flaws

- **The squeezed terminal does not clip.** `.wt-cmd` is `white-space:nowrap` with
  `overflow-x:auto`, the obvious candidate. Measured from 553px of panel width upward:
  0 of 1 command lines clip, and nothing else inside the panel overflows.
- **390px is already correct.** The terminal ships at 560px below 767px, so the phone is the
  one narrow width with no panel problem. Only the tracking affects it.
- No horizontal overflow at any of the eleven widths.
- The list's 22px/20px rungs are the documented card-heading contract.
- The panel is never partly empty — content reaches full height at every timestamp.
- The 96px section rhythm comes from the parent's `gap`; there is no double margin.
- `align-items:start` is correct, which is why flaw 4 (the 136px ragged bottom at desktop) is
  reported rather than fixed.

## What the mock is and is not

The terminal is a **static stand-in** — the real one is JS-driven. Its box is honest (same
height, border, radius, bar colours, padding) and the transcript is sized to fill it (8% empty
at the bottom, against 0% on the real page) so that flaw 2 is not argued against a straw man.
An earlier draft had three steps and left ~38% of the panel empty, which overstated the case.

Media queries key off the viewport, not the container, so a mock inside a resizable frame
cannot use them: the ≤1024 state is `.is-narrow`, the ≥1025 state is `.is-wide`, `.is-mobile`
carries the ≤767 behaviour that already ships, and the frame feeds the `clamp()` a `--vw` so
the h2 resolves against the frame instead of the real viewport. Every other declaration is
transplanted from `index.tsx` byte-for-byte.

## Reproducing every number

The harnesses are in `tools/`. They are `.cjs` because the repo root `package.json` is
`"type": "module"`, and they reuse the repo's own `tools/browser/lib` for Chrome resolution and
static serving, so they need no hardcoded paths.

```
npm install && NODE_ENV=production npm run build     # produces out/
cd mock/home-flow/tools
node flowcheck.cjs      # 7 widths on the LIVE page: columns, heights, tracking, overflow
node flowband.cjs       # walks 744-1180, flags the worst-of-both widths
node flowmeasure.cjs    # characters per line, and what the neighbours cap themselves at
node flowcmd.cjs        # command-line clipping inside the squeezed panel
node drivemock.cjs      # drives THE MOCK: 6 widths x 2 toggle states, 22 assertions
```

`drivemock.cjs` is the one that keeps the mock honest. It clicks through every width and
toggle combination and asserts the readout matches an independent measurement. It has already
caught four defects in this mock: the two columns were transplanted in the wrong DOM order
(copy first, so desktop put the panel in the 380px track); the guide line and verdict were
computed before the browser reflowed and reported the previous width; the phone was shown with
a 650px panel when it ships 560px; and a CSS `transition` on the frame width meant the readout
measured mid-animation. A mock that reports numbers has to be tested like anything else that
reports numbers.
