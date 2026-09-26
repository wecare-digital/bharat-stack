---
name: new-public-page
description: "Build or change a public page on wecare.digital to the standard the home band was held to — mock it before applying, measure every claim in a real browser, and verify it across mobile, foldable, webview, reduced-motion, no-JS and translated states. Use when creating a new public route, adding a top section, or changing shared chrome."
license: MIT
---

# New or changed public page

The house standard for public pages. It exists because a home-page audit found **seven
defects that every existing suite passed** — `animcheck` 18/18, `uicheck` 96/96, `typecheck`
3/3, `seocheck` 11/11, 251 unit tests, all green while the hero's rotating word rendered
blank on every single load. The suites all measured one settled state: JavaScript running,
motion allowed, viewport fixed at load. Every defect lived somewhere else.

**The rule this skill encodes: a page is not done when it looks right. It is done when the
states nobody looks at have been measured.**

---

## 1. Mock before you apply. Always.

Do not edit source to show someone a proposal. Generate a review page instead.

- **Harvest, never paste.** Extract CSS and markup from the real built export at generation
  time (`out/`), not by copying rules into a mock file. A hand-pasted mock is true exactly
  once; the day either source changes it shows the old design and says nothing. There is a
  working generator at `tools/browser/homereview.js` — copy its approach.
- **Panels are iframes at real widths**, only visually scaled. The frame must genuinely be
  1280 or 390 wide so `clamp()`, `vw` units, media queries and `position:fixed` all resolve
  as they would on a real screen. Rendering variants as divs in one document makes every
  viewport-relative unit wrong.
- **An iframe's height IS `100vh` inside it.** A 640px-tall panel showed a 320px menu where
  the live page gives 580px, because the rule was `calc(100vh - 320px)`. Use real viewport
  heights, not crops.
- **Emit panels as static markup. No JavaScript.** A mock whose panels are built by a script
  shows headings and nothing else in any viewer that does not run scripts — which is the
  exact defect class being documented.
- **Bake the settled state into "original" panels.** With scripting off, an un-hydrated hero
  renders its *defect*. A panel labelled "as it ships today" that shows the broken state is
  a lie. Server-rendered values plus the classes JS would add must be written into the markup.
- **Show the original first, at 1:1, labelled unmodified.** Then the proposal. Reviewers need
  the baseline more than they need the pitch.
- **If a state cannot be previewed faithfully, publish numbers instead.** Font fallback and
  `forced-colors` resolve against the operating system, so the build machine's rendering is
  not the reader's. A confident panel there is worse than a table.
- **Options are alternatives, and say so.** Label plainly that exactly one ships. Include a
  deliberately-wrong option only if you mark it "not a candidate".
- **Give the page a build stamp.** A cached copy is otherwise indistinguishable from a bug,
  and someone will report the cache as a defect.

## 2. Assert on the mock, do not look at it

Every before/after panel must be verified by reading computed style inside the frame. Looking
at it is not enough — this caught, in one project:

- a proposed fix that would have made a 200ms flash **permanent** (`position:static` alone
  turns a span into a non-replaced inline box whose `offsetWidth` is `0`, so the measuring
  effect wrote `width:0px`; it needed `display:inline-block`)
- injected fix CSS that **never applied**, because styled-jsx compiles `.x::before` to
  `.x.jsx-HASH::before` at (0,2,1) and the injection was (0,1,1)
- `\b` inside a JS template literal becoming a **backspace character**, so a class-strip regex
  silently stopped matching and every "before" panel showed the fixed state
- a CSS trim that dropped `*{box-sizing:border-box}`, reporting a 72px menu where the live
  page gives 40px

Assert **equality with live measurements**, not ranges. A range hides a fidelity drift; an
equality check fails the moment the mock stops matching the page.

## 3. The state matrix — the part that finds real defects

Run each of these. They are ordered by how many defects they have actually caught.

| State | How | What it catches |
|---|---|---|
| **No JavaScript** | omit the boot script / `javaScriptEnabled:false` | content that only exists after hydration |
| **First paint** | sample `requestAnimationFrame` from document start | width/height written by an effect after mount |
| **Reduced motion** | `reducedMotion:'reduce'` | intervals that never start, so nothing re-measures |
| **Resize after load** | `setViewportSize` post-load | values measured once and never again |
| **WCAG 1.4.12 text spacing** | inject `line-height:1.5;letter-spacing:.12em;word-spacing:.16em` | `overflow:hidden` on a JS-measured box. **Level AA** |
| **Translated** | see §5 | text that grows, and text that never translates |
| **Webfont swap** | block `fonts.googleapis.com`, compare | layout shift on every cold load |
| **`forced-colors: active`** | `forcedColors:'active'` | designs whose only cue is colour |
| **Dark mode** | `colorScheme:'dark'` | absent support, and absent *declaration* |
| **Keyboard** | walk `Tab` from load | focusable-but-invisible controls (`opacity:0` stays in the tab order) |

## 4. Device matrix — foldables are not optional

The failure mode that width-only testing cannot see is **wide AND short**. It is rare on a
phone and normal on a folded-landscape device.

```
phones      320×844 · 360×800 · 390×844 · 411×797 · 480×900
foldables   280×653  Galaxy Fold folded            653×280  ← folded landscape
            344×882  Z Fold cover                 882×344  ← cover landscape
            904×1084 Z Fold unfolded              1084×904
            360×880  Z Flip                        880×360  ← the common killer
            411×797  Pixel Fold outer              841×1010 inner
            540×720  Surface Duo one pane          720×540
            1114×705 Surface Duo spanned
            853×1280 Zenbook Fold                 1280×853
desktop     1280×900 · 1440×800 · 1920×1080
webview     390×844 with the OS chrome subtracted — use dvh, never vh
```

**Never subtract a magic number from the viewport.** A menu sized
`max-height:calc(100vh - 320px)` measured **0px** at 653×280 and 40px at 880×360. Anchor to a
real element: `calc(100dvh - 140px)` where 140 = the 108px header + 32px of air, both nameable.

**Height conditions need no width ceiling.** An existing rule in this repo guards the same
case with `@media (max-width:768px) and (max-height:500px)` — which misses 880 and 882 wide
entirely. Also honour `@media (vertical-viewport-segments: 2)`; there is precedent at
`src/styles/Layout.css:2204`, asserted by `BottomNav.test.tsx:140`.

Use `dvh`, not `vh`. `100vh` is the viewport with browser chrome *hidden*, so anything sized
to it is taller than what a phone visitor can see. Declare `vh` first as the fallback, `dvh`
second.

## 5. Translation — assume nothing is translated until measured

`SupportWidget` walks **text nodes** and rewrites `nodeValue`. Consequences, all measured
across 124 routes:

- **Attribute text is never translated.** `aria-label`, `title`, `placeholder`, `alt` are not
  text nodes. **1329 strings sitewide, 147 on public routes** stay English in every language —
  116 of them `aria-label`, so screen-reader users get English labels around translated text.
  If a string matters, it belongs in a text node or needs its own path.
- **`aria-hidden="true"` subtrees are skipped**, correctly — and a rotating headline word
  carries `aria-hidden` for an equally correct reason (so a screen reader does not read the
  headline once per word). The two combine into a **mixed-language headline**: the frame line
  translates, the word inside the pill does not. 78 nodes sitewide.
- **`data-wc-no-translate` is doing double duty.** It is meant to protect customer data in the
  dashboard, and it is also sitting on public eyebrow labels — "Legal Stuff — WECARE.DIGITAL",
  "Selfservice by WECARE.DIGITAL" — which then never translate. Check before adding it.
- **A translated word is wider.** "consumers" 278px → "उपभोक्ताओं" 317px, and Devanagari is
  taller at the same size. Any box with `overflow:hidden` and a JS-measured width will clip.
  `width:max-content` plus a `ResizeObserver` **on the text element, not its container**, is
  the pattern that survives it. Observing the container never fires or feeds itself.

Verify with the census in `tools/browser/pageaudit.js`, which reimplements the walker's filter
exactly and reports per route what would translate, what would be skipped, and why.

## 6. Structure every public page must carry

- Shared chrome: `header` + `footer` + support widget. Being public is the gate — a new public
  route picks all three up from `_app.tsx`'s public branch; do not add a per-page flag.
- A **top section after the header**: one visible `<h1>` inside `<main>`, above the fold,
  saying what the page is about. No CTA, no price, no conversion furniture in that band — the
  action belongs further down. Only the words, the rotation and the sub-line change per page.
- Exactly one `<h1>`. Section headings on the site's `clamp(28px,3.2vw,40px)/700/1.08/-1.2px`
  rung — verify with `typecheck.js`, do not invent a rung.
- Tracking in `em`, never `px`, on any fluid (`clamp`) font size. A fixed px value against a
  fluid size made optical tightness swing 2.75× across breakpoints.
- Declare the font stack on the component. Do not inherit `body` and hope: with the global rule
  absent, an inheriting lockup fell to a serif while a declaring headline stayed on Inter.
- Touch targets ≥ 44px. The site's CTA is `min-height:52px`.
- `opacity:0` does **not** remove an element from the tab order. Use `visibility:hidden` or
  `inert` for anything hidden pending a reveal.
- Entrance animations are **opt-in**: ship the readable final state in CSS and let JavaScript
  add a class that hides the start state. Never the reverse. See the `.is-armed` pattern in
  `src/pages/index.tsx` — and note it missed focus, so cover that too.
- Content that moves automatically for over 5s needs a pause mechanism (**WCAG 2.2.2**).

## 7. Gates to run before committing

```bash
npm run build                          # produces out/, which every harness reads
npx tsc --noEmit
npx vitest run
node tools/browser/animcheck.js        # rotating-headline reflow, 21 viewports
node tools/browser/homeprobe.js        # the degradation states from §3
node tools/browser/pageaudit.js        # structure + translation census + overflow
node tools/browser/uicheck.js
node tools/browser/typecheck.js
node tools/browser/seocheck.js
python3 scripts/check_design_drift.py
python3 -m pytest tests/test_design_drift_tokens.py -q
```

A new page adds a route to `pageaudit.js`'s discovery automatically. If it introduces a state
the matrix in §3 does not cover, add the assertion — a green suite that cannot see a defect is
worse than no suite, because it is cited as evidence.

## 8. What to commit

- **Source, tests and the mock in one reviewable change.** Add the assertion that pins the fix,
  and write *why* in the test body — the failure mode, not the expectation.
- **Comments are the artefact the next change is based on.** One band accumulated eleven
  incorrect comment claims: a measured width that was wrong by 8px, "five words" for a set of
  four, a rung described as nonexistent that existed, and an attribution to the wrong
  stylesheet. Re-measure anything a comment asserts, in the same commit.
- **Never commit to the default branch.** Push a feature branch and open a PR into it
  (`gh api repos/{owner}/{repo}/pulls -f head=... -f base=...`).
- **State what is not fixed.** Name the defects left open and why, and name what you did not
  check — print, RTL, real browser zoom — so the gap is visible rather than implied.
- **Regenerating a mock after applying its fixes invalidates it.** It harvests the built
  export, so its "before" panels pick up the fix and stop reproducing anything. Either keep the
  pre-fix mock as the evidence or say plainly in the PR that it no longer demonstrates.
