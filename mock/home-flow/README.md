# `.home-flow` — the home page section below the hero

Deep-check of the second section on `/` (`src/pages/index.tsx`, section at line 352).
The hero above it was corrected in #55; this is the next one down.

Measured on the built export (`out/`) at eleven viewport widths with the repo's own
browser harness, reduced motion on so the terminal is frozen and shots are comparable.
**Nothing has been applied to `src/`.** These are boards for a decision.

Open `mock.html` in a browser, or read the PNGs:

| Board | Finding |
|---|---|
| `1-line-length-doubles.png` | Line length goes 47 → 120 chars/line between 1025px and 1024px |
| `2-tablet-band-no-breakpoint-owns.png` | Layout collapses at 1024px, terminal only shrinks at 767px |
| `3-h2-tracking-fixed-px.png` | `letter-spacing:-1.2px` against a fluid `clamp()` size |
| `4-ragged-bottom-and-non-flaws.png` | 136px column height difference, plus what was checked and is fine |
| `5-what-changes.png` | The whole proposed diff: one line, one number, one question |
| `0-all-boards.png` | All of the above in one image |

## The three flaws, shortest form

**1. The copy column has no `max-width`.** In two columns it sits in a 380px track — 47
characters per line, a proper measure. At ≤1024px the grid collapses and the column
inherits the full page width, so the same paragraph runs **120 characters** at 1024px and
88 at 768px. The convention is 45–75. Both neighbours on this same page already cap
themselves (`.home-sub` at 560px, `.home-close-lead` at 782px), so this column is the
outlier on its own page.

**2. Two breakpoints were set independently and do not meet.** `.home-flow` drops to one
column at `max-width:1024px` (index.tsx:763). `.wt-window` steps 650px → 560px at
`max-width:767px` (WorkflowTerminal.tsx:466). Everything from **768px to 1024px** gets the
narrow layout *and* the desktop panel height: a 650px black panel at 100% of the measure
with nothing beside it — verbatim the condition the code comment says the two-column band
was introduced to remove. Six of the eleven sampled widths are in that band, **including
every iPad in portrait** (768, 820, 834) plus Surface Pro and 1024.

**3. The h2 tracking is a fixed pixel against a fluid size.** `-1.2px` on
`clamp(28px,3.2vw,40px)` resolves to −3.00% at 40px, −3.66% at 32.8px and −4.29% at 28px —
a 1.43× swing. Since #55 unified the h1 to a flat `-0.04em`, the page's two biggest
headings now track differently on desktop (−4.00% vs −3.00%).

## Recommended

| # | Change | Reach |
|---|---|---|
| 1 | `.home-flow-copy{max-width:680px}` inside the existing `@media(max-width:1024px)` block | this section only |
| 2 | `767px` → `1024px` on the terminal's height media query | shared component, check other callers |
| 3 | `-1.2px` → `-0.03em` | **12 headings on 10 pages — needs your answer** |

Fix 3 is deliberately not recommended unilaterally. The comment above the rule records that
`.home-flow-title` is byte-for-byte identical to `.home-close-title`, `.cl-h2`, `.mo-h2`,
`.brx-h2` and `.pdp-h2`, and instructs that `node tools/browser/typecheck.js` be run before
it changes. `-0.03em` is picked so the desktop rendering does not move at all (−0.03 × 40px
= exactly −1.2px); only the narrow end moves, toward the value desktop already has.

## Checked and **not** flaws

- **The squeezed terminal does not clip.** `.wt-cmd` is `white-space:nowrap` with
  `overflow-x:auto`, the obvious clipping candidate. Measured from 553px of panel width
  upward: 0 of 1 command lines clip, and nothing else inside the panel overflows.
- No horizontal overflow at any of the eleven widths.
- The list's 22px/20px rungs are the documented card-heading contract, not a mistake.
- The panel is never partly empty — content reaches its full height at every timestamp.
- The 96px section rhythm comes from the parent's `gap`; there is no double margin.
- `align-items:start` is correct, which is why flaw 4 (the 136px ragged bottom) is
  reported rather than fixed.

## Caveat on the mock

The terminal in `mock.html` is a **static stand-in** — the real one is JS-driven. Its box is
honest (same height, border, radius, bar colours, padding) but the transcript is abbreviated
to three steps. The flaws being shown are about the box's size and the text beside it, not
about the transcript.

Media queries key off the viewport, not the container, so a side-by-side board cannot use
them: the ≤1024 state is expressed as `.is-narrow` and the ≥1025 state as `.is-wide`.
All other declarations are transplanted from `index.tsx` verbatim.

## How to reproduce

The four harnesses that produced every number above are in `tools/` beside this file.
They are `.cjs` because the repo root `package.json` is `"type": "module"`, and they reuse
the repo's own `tools/browser/lib` for Chrome resolution and static serving, so they need no
hardcoded paths.

```
npm install && NODE_ENV=production npm run build     # produces out/
cd mock/home-flow/tools
node flowcheck.cjs      # 7 widths: columns, heights, tracking, overflow, + section shots
node flowband.cjs       # walks the 744-1180 breakpoint band, flags worst-of-both widths
node flowmeasure.cjs    # characters per line, and what the neighbours cap themselves at
node flowcmd.cjs        # command-line clipping inside the squeezed panel
```

Each writes its raw JSON to `tools/out-shots/`. `flowcheck.cjs` also drops a screenshot of
the live section at each width there, which is how the "Now" halves of the boards were
checked against the real page.
