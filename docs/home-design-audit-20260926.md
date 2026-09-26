# Home page — deep design check, 2026-09-26

`src/pages/index.tsx`, 961 lines, read in full and then measured. Every number below came
from a harness run in this session against `out/` from `npm run build`, not from reading.

**The suites that already existed all pass, and none of them sees anything below.**
`animcheck.js` 18/18 · `typecheck.js` 3/3 · `seocheck.js` 11/11 · `uicheck.js` 96/96 ·
`check_design_drift.py` OK · `tests/test_design_drift_tokens.py` 33/33 ·
`HomePage.test.tsx` 11/11. New gate `tools/browser/homeprobe.js`: **5/12**.

That gap is the finding behind the findings. The existing suites all measure the happy
path — JS running, motion allowed, viewport fixed at one width. Seven of the defects below
live in states none of them enters.

---

## H1 — Fake review schema and a false founding date still ship, on 17 and 123 pages

`FRONTEND_FULL_AUDIT.md` filed this as **P0 #2** against `src/pages/index.tsx`. It reads
as fixed, because `index.tsx` no longer contains a line of JSON-LD. It was not fixed. The
schema **moved to `src/pages/_app.tsx`**, which renders on every route, so the blast
radius grew while the finding looked closed.

| Claim | Source | In `out/` |
|---|---|---|
| `aggregateRating` `4.8` / `ratingCount` `150` | `_app.tsx:306-312` | **17** pages, `/` among them |
| `foundingDate: "2020"` | `_app.tsx:252` | **123** pages |
| `offers.price: "0"`, `priceCurrency: INR` | `_app.tsx:278-282` | 17 pages |

Verbatim from the built home page:

```
aggregateRating":{"@type":"AggregateRating","ratingValue":"4.8","ratingCount":"150", ...
foundingDate":"2020"
"offers":{"@type":"Offer","price":"0","priceCurrency":"INR", ...
```

Three separate problems, not one:

1. **150 reviews averaging 4.8 that do not exist.** Google's structured-data policy treats
   self-serving invented review markup as a manual-action risk for the whole site.
2. **`price: "0"` contradicts the page it ships on.** The closing band promises "Know the
   price before you commit" and the catalogue floor is ₹599 (`wix-catalog.json`, Viveka).
   The machine-readable version of this page says the product is free.
3. **The `Organization` description contradicts the hero.** It reads "Enterprise WhatsApp
   Business API platform for multi-channel customer engagement" (`_app.tsx:251`, restated
   at `:323`) — on 123 pages. The hero
   was deliberately rewritten *away* from that: no channel names, no platform framing,
   `Everyday AI, built for consumers / enterprises / climate tech / frontier tech`. The
   structured data still describes the company the page copy stopped being.

`seocheck.js` passes 11/11 here and cannot help: it asserts that 61 JSON-LD blocks
**parse** and that `@id`s do not collide. Neither is a truth check.

Fix is deletion for (1), a date for (2), and one string for (3) — but it is sitewide, so
it wants its own commit and a re-run of `seocheck.js`.

## H2 — The pill paints empty, and not only without JavaScript

**Amended after commit `869760f7`.** A parallel session found the same root cause (its F2)
and one consequence this section originally missed: the empty pill is on the **happy path
too**. `cycleW` starts `null`, so the first React render writes no inline width, and the
measuring effect only runs after mount. Sampled per animation frame from document start:

```
170 frames sampled; 4 with .home-cycle width 0
empty for ~194-206ms across 4 painted frames  (two runs: 206ms, 194ms)
first painted width t=263ms w=278 inline=278px
```

So **every visitor**, with JavaScript working and on a fast local server, sees the headline
as `Everyday AI, built for` with an empty pill for about 200ms. On a real network, behind
hydration, it is longer. That is a flash of incomplete positioning on the site's most
important h1, and it is the same single root cause as the no-JS case below — worth fixing
once, not twice.

### With JavaScript off, it never resolves at all

Measured, JS disabled, 1280×900:

```
.show applied: false | .home-cycle set width: (none) | box 0px
.home-mark::before  scaleX(1)   <- white shutter at full width, covering the tint
.home-mark-dot      scale(0)    <- invisible
```

`.home-cycle` is `display:inline-block; overflow:hidden` and all four words inside it are
`position:absolute`, so they contribute nothing to its intrinsic width. Its width comes
only from the effect at `index.tsx:229-236`. No effect, no width: it computes to **0px**
and clips the word away completely. The headline renders as **"Everyday AI, built for"**
followed by an empty, untinted, dotless pill.

The page already contains the argument against this, at length, about the closing band
(`index.tsx:187-206`): *an entrance effect must never be the reason content cannot be
read*, which is why `.home-close` ships its final state and JS adds `.is-armed` to hide
the start state. The hero is the opposite — CSS ships the hidden state and JS reveals it.
One page, two doctrines, and the hero has the one it argues against.

Not an SEO or screen-reader defect: the words are in the static HTML and the `aria-hidden`
copies plus `.home-sr-only` mean assistive tech reads the full list. It is a sighted
no-JS / failed-bundle / CSP defect only.

## H3 — Reduced motion plus a resize clips 35% of the word, permanently

Measured, `prefers-reduced-motion: reduce`, 480 → 1280:

```
at 480 : pill 182px / word needs 182px / font 36px
at 1280: pill 182px / word needs 278px / font 55.04px
=> overflow:hidden cuts 96px (35%) off "consumers"
```

`cycleW` is measured in an effect keyed on `cycleIndex` alone (`index.tsx:229-236`) and
there is no resize listener. `font-size` is `clamp(36px,4.3vw,60px)`, so every word's
width is a function of viewport width. On the happy path a stale width self-heals at the
next tick, within 2400ms. Under reduced motion the interval never starts
(`index.tsx:179`), so **nothing ever re-measures** and the stale width is permanent.

Phone rotation is the ordinary trigger, and iOS "Reduce Motion" is widely enabled. The
reverse direction is the milder half of the same bug: 1280 → 480 leaves 96px of empty
tinted pill trailing the word.

`animcheck.js` cannot catch this — it sets each viewport and loads fresh, so it never
changes a viewport after paint. That is deliberate in its design and worth keeping; this
belongs in a separate gate, which is what `homeprobe.js` now is.

## M4 — The third Tab stop is an invisible button 1697px down the page

Measured Tab walk from load, 1280×900:

```
1. a.logo             "WECARE.DIGITAL"        top=24
2. button.nav-trigger ""                      top=31
3. a.home-close-cta   "Tell us what you need"  top=1697   <-- opacity:0
4. a.ft-home          "WECARE.DIGITAL"        top=1947
5. a.wc-wa            ""                      top=835
```

`.home-close.is-armed .home-close-cta{opacity:0}` (`index.tsx:731`) hides the CTA until the band scrolls
into view, and `opacity:0` does not remove an element from the tab order. So the only
CTA on the page is reachable, focusable and invisible — and it is the *first* content
stop, before the reader has passed anything. WCAG 2.4.7 (focus visible) and 2.4.11 (focus
appearance).

The `.is-armed` inversion correctly fixed *readability* without JS. It did not consider
focus. `visibility:hidden` or `@starting-style`, or arming with `inert`, all resolve it.

## M5 — Zero actions above the fold, now a number rather than a claim

Visible interactive elements whose box starts above the fold, inside `<main>`:

| Viewport | visible above fold | of those, inside `<main>` |
|---|---:|---:|
| 1280×900 | 3 | **0** |
| 1440×800 | 3 | **0** |
| 390×844 | 3 | **0** |

The three are `a.logo`, `button.nav-trigger` and the WhatsApp pill — all site chrome. (A
raw selector match counts 24, but 21 of those are mega-menu links behind an `opacity:0`
ancestor; they are correctly *not* in the tab order. The header is fine.)

This is the item `docs/grahak-os-handoff.md` and `FRONTEND_FULL_AUDIT.md` A.1 both raise,
and it is the one still waiting on the owner: the CTA's wording and destination, and
whether a price goes above the fold. Both are recorded as owner decisions, not agent
guesses. Any price must derive from `src/content/wix-catalog.json` — 7 products, floor
**₹599** (Viveka), next **₹999** (Referral Partner) — because a typed number goes stale
the moment the ₹49 tier lands.

## M6 — The reduced-motion shutter rule is inverted, and inert only by specificity

```css
@media(prefers-reduced-motion:reduce){
  .home-mark::before{transform:scaleX(1)}   /* index.tsx:951 */
}
```

The comment above it says this "settles the pill into its resting state". `scaleX(1)` is
the **start** state — the white shutter at full width, covering the tint. The resting
state is `scaleX(0)`. The sibling rule for the dot is correct (`scale(1)`, matching
`.home-layout.show .home-mark-dot`).

Measured computed value under reduced motion: **`scaleX(0)`** — so it is not biting. The
reason is specificity, not intent: `.home-layout.show .home-mark::before` scores (0,2,1)
against this rule's (0,1,1), and a media query contributes nothing. Any edit to the
`.show` rule turns a latent inversion into a white pill for every reduced-motion visitor.

`HomePage.test.tsx:138` asserts only that the string
`@media(prefers-reduced-motion:reduce)` appears, under a comment claiming "reduced motion
settles the pill rather than leaving it mid-transition". The assertion does not check what
the block sets, which is why this passes.

## L7 — The file's design record contradicts the file

This page is documented by roughly 400 lines of comment, and the comments are the
artefact the next change will be based on. Several now describe a page that no longer
exists. Measured contradictions first:

| Comment | Says | Measured / actual |
|---|---|---|
| `index.tsx:21-23` | 5 words, `climate tech 290`, `AI applications 361`, "Spread 83px" | `animcheck`: 4 words, `climate tech` **298**, spread **22px** |
| `index.tsx:145` | "Five words, five distinct tints" | `CYCLE_WORDS` has **four** |
| `index.tsx:119-127` | "AI is now mentioned NOWHERE in the hero"; "the frame is `Everyday services for ___`" | h1 is `Everyday AI, built for` (`index.tsx:300`) — contradicted by the top of the same comment block, which explains the frame change |
| `index.tsx:475-476` | "The headline above is 'Everyday services for travel / rituals / documents'" | stale, and it names three **services**, which the same file bans twice |
| `index.tsx:686` | flow beat bodies are `rgba(0,0,0,.54)` | `.home-flow-list span` is `.898` — changed 40 lines earlier, with a comment saying so |
| `index.tsx:494` | the closing lead "says … you can buy one thing without committing to a bundle" | the lead says nothing about bundles |
| `index.tsx:569-572` | "not yet what `grahak-os-design.md` says … contract specifies `clamp(32px,4.2vw,54px)` … typecheck.js reports the gap" | steering row 19 **is** `clamp(28px,3.2vw,40px)`; `typecheck.js` reports no gap and its own header records why 54px lost |
| `index.tsx:800`, `:803` | "one section today", `.home-eyebrow below`, the badge being stretched | two sections; no `.home-eyebrow` rule and no badge exist |
| `index.tsx:231`, `:914` | pill glides between "Service" and "Intelligence" | neither word is in the set — leftovers from the Grahak OS hero |

The `climate tech 290` / `298` pair is the one to fix first: the header comment is the
place someone will look for the measurement, and it is both stale *and* internally
inconsistent with the block 100 lines below it.

## L8 — h1 text extraction repeats the word set five times

The h1's raw text content is:

```
Everyday AI, built forconsumers, enterprises, climate tech, frontier techconsumersenterprisesclimate techfrontier tech
```

Screen readers are correct — the four animated copies carry `aria-hidden` and
`.home-sr-only` supplies one clean list. But a naive text extractor (some social preview
generators, some crawlers) reads the set five times, with no space after "for". Cheap to
improve, and the sr-only span is the natural place.

## TYPE — Typography findings, measured with the font harnesses

Prompted by the fair observation that everything above is a runtime state and none of it is
type. Run with `measure-fonts-sitewide.js`, `measure-fonts-detail.js` and a computed-style
sweep of the top band at 1280.

### TYPE-1 — The top band renders in **two different Inter stacks**

| Element | Resolved family |
|---|---|
| header lockup — `span`, `.brand-dot`, `.brand-stack` | `Inter, ui-sans-serif, …` |
| hero — `.home-head-line`, `.home-sub` | `Inter, -apple-system, …` |

Both start with Inter, so on a warm load they are indistinguishable — which is exactly why
this has survived. They diverge the moment Inter is unavailable: the header falls to
`ui-sans-serif`, the hero to `-apple-system`. Two different faces in one lockup, 108px apart.

Sitewide the same split is `Inter, -apple-system` ×1135 against `Inter, ui-sans-serif` ×105,
plus `SF Mono, Monaco` ×9 which is the terminal and legitimate. `index.tsx:~800` carries a
long, correct comment about why the hero declares its stack locally rather than inheriting
Amplify's; the header was never brought in line.

### TYPE-2 — The webfont swap moves the band on every cold load

`Inter` loads from Google with `display=swap`, so the fallback paints first. Measured with
`fonts.googleapis.com` blocked, then allowed:

| | frame line | h1 | hero band |
|---|---:|---:|---:|
| fallback face | 513.1px wide | 129.4px tall | 209.4px |
| Inter arrives | **506px** | **131.4px** | **211.4px** |
| delta | **−7.1px** | **+2px** | **+2px** |

So the headline narrows 7px and the band grows 2px taller when the font lands — a real layout
shift on every uncached visit. **`animcheck.js` can never catch this**, because `gotoStable`
waits on `document.fonts.ready` by design, which is the right call for reflow measurement and
the reason this was invisible. Fix is a metrics-matched fallback (`size-adjust` /
`ascent-override` on a local face) or preloading the woff2 to shrink the window; 2px may also
be acceptable, but it should be a decision.

### TYPE-3 — `.brand-dot` is the weakest text on the page at 3.94:1

Contrast of every top-band element against its actual background: `17.4`–`19.47` for
everything except `.brand-dot` at **3.94:1**. That **passes** AA, but only because 23px/800
qualifies as large text (≥18.66px bold, 3:1). It has no margin: shrink it below 18.66px or drop
the weight and it becomes a failure. Worth a note in the source so it is not "tidied" later.

### TYPE-4 — A source comment says a rung does not exist. It does.

`index.tsx` states that `20px/600` "was considered and rejected: it exists nowhere on the
site, and inventing a rung is the thing the h2 unification was done to stop."
`measure-fonts-detail.js` finds it: **`/my-order` `.mo-link` "Terms of Service"**, 20px/600.
The reasoning stands, the factual claim does not — and it is the tenth stale comment, on top
of the nine in L7.

### TYPE-5 — `15.5px` exists, ×71

`.lgd-disclaimer` and `.lgd-short` on `/terms` and `/privacy` resolve to **15.5px/400**. A
half-pixel size is almost always arithmetic rather than intent. Not the home page, but it is
in the shared legal layout, and 27 distinct size/weight pairs sitewide is the context.

### TYPE-6 — Tracking drift across the four hero copies

Already noted under propagation, but it belongs here too: `index.tsx` is on `-0.04em`
(correct, scales with the clamp) while `grahak-os`, `vayulok` and **`RotatingHero`** are all
still on `-2.2px` with `-1.2px`/`-0.8px` media overrides — the 2.75× optical swing. Since
`RotatingHero` is reached by 13 public routes, most of the site's headlines still carry the
bug the home page fixed.

---

## DIM — Other design dimensions: spacing overrides, colour modes, i18n, layering

Everything above is either a runtime state or type. These are the remaining axes, measured.

### DIM-1 — WCAG 1.4.12 Text Spacing **fails**, and it is the same root cause

1.4.12 is Level **AA** and normative: a user stylesheet setting `line-height:1.5`,
`letter-spacing:.12em`, `word-spacing:.16em` must not clip content. Applied:

```
before: pill 278px, word needs 277.5px
after : pill 278px, word needs 356.8px
=> 78.8px clipped — 22% of "consumers" — by overflow:hidden
```

No horizontal overflow is introduced and the h1 grows 131.4 → 171.7px as expected; the only
damage is the pill. This is the **same defect as H2/H3** seen from a third angle: a
JavaScript-measured width on an `overflow:hidden` box cannot survive anything that changes
glyph metrics.

**Fix A + Fix B close this.** `width:max-content` is correct under any spacing, and the
`ResizeObserver` refires when the word's box changes, so the px value JavaScript writes stays
correct. Worth recording because it turns those two from "repairs a flash" into "clears an AA
failure".

### DIM-2 — Translating the page clips the rotating word by 39px

This one is not hypothetical: the site ships a language switcher, and the whole
`site-language` service exists to translate this page. A client-side translation rewrites the
text node and nothing else — the pill keeps the width measured for English:

```
english: pill 278px for "consumers"      (277.5px)
hindi  : pill 278px for "उपभोक्ताओं"        (317px)   => 39px clipped
```

Devanagari is also taller than Latin at the same size, so the clipping is not only horizontal.
**Fix A + Fix B close this too**, for the same reason as DIM-1.

### DIM-3 — In forced-colors mode the pill loses both the tint and the dot

`forced-colors: active` (Windows High Contrast). Measured: `.home-mark` background →
`rgb(255,255,255)` and `.home-mark-dot` → `rgb(255,255,255)`. There are **no
`@media (forced-colors)` rules anywhere on the site**. So the pill stops being a pill: no
tint, no dot, and the rotating word reads as ordinary headline text.

That matters more here than it would elsewhere, because the source argues the rotation is
doing "argumentative work rather than decoration" — the four tints *are* the message. My own
prediction that an inline background would survive was **wrong**; forced colors overrides
inline styles too, which is why this was measured rather than reasoned.

```css
@media (forced-colors: active){
  /* keep the pill readable as a shape when its colour is taken away */
  .home-mark{border:1px solid CanvasText}
  .home-mark-dot{forced-color-adjust:none}
}
```

### DIM-4 — No dark-mode support, and nothing declares that

No `prefers-color-scheme` rule exists anywhere on the page, and there is no
`<meta name="color-scheme">`. Under `colorScheme: dark` the band renders unchanged: shell
`rgb(255,255,255)`, h1 `rgba(0,0,0,.95)`, header `rgba(255,255,255,.97)`.

Rendering light-only is a legitimate brand decision. Leaving it **undeclared** is not: without
`<meta name="color-scheme" content="light">` the browser may still apply dark heuristics to
form controls and scrollbars, so the page gets a partial dark treatment it never asked for.
One line, and it makes the decision explicit.

### DIM-5 — Clean: layering and reflow

Reported so they are not re-investigated.

- **Layering.** Header `z-index 1001`, menu `1002`, support widget `1300`. The widget would
  paint over an open menu, but measured at 1280×900, 844×390 and 390×844 the two boxes
  **never intersect**. No defect; the z-order is simply never exercised.
- **Reflow at 320px.** `0px` of horizontal overflow, furthest-right element at exactly 320px.
  Clean.

### Not checked

Print stylesheet, RTL (`dir="rtl"`), and real browser zoom at 200/400% as distinct from a
narrow viewport. Named so the gap is visible rather than implied.

---

## M-HDR — The shared header's mega-menu collapses to a sliver on a short viewport

Found while extending the 1:1 review treatment to the header. Measured across nine viewports
with the menu open:

| Viewport | menu box | content | verdict |
|---|---:|---:|---|
| 390×844 portrait | 358×536 | 1028px | scrolls, usable |
| 768×900 | 512×580 | 700px | usable |
| 1280×900 | 760×403 | 399px | fits outright |
| **844×390 landscape** | **588×70** | **700px** | **20 links in a 66px scroller** |

`Header.tsx:489` sizes the menu `max-height:calc(100vh - 320px)`, and the override that
repositions it (`Header.tsx:621`) is gated on `@media(max-width:767px)`. So any window
**wider** than 767 but short falls back to the desktop rule — a landscape phone, or a short
desktop window. The threshold is roughly 620px of viewport height.

Two smaller things in the same declaration: it uses `100vh` rather than `100dvh`, which is
the exact unit defect `index.tsx` already fixed and documented for `.home-shell`; and `320`
corresponds to no element in the layout, the same magic-number family as the 108/96 header
heights.

```css
/* anchor to the header, and use dvh: 140 = the 108px header + 32px of air */
.nav-menu{max-height:calc(100dvh - 140px)}
```

Measured effect at 844×390: **70px → 250px**, still inside the 390px viewport.

**Credit where it is due — the header's accessibility is already right**, which is why this
is geometry only: `aria-expanded` on the trigger, Escape closes from anywhere, an outside
pointerdown dismisses, focus returns to the trigger on close, and the closed menu is
`visibility:hidden` so its 20 links are genuinely out of the tab order. That last one is
what the earlier above-fold count confirmed independently.

## L9 — `will-change:width` is permanent on `.home-cycle`

`index.tsx:923`. `will-change` is meant to be applied shortly before a transition and
removed after; left on, it holds compositing resources for the life of the page. Under
reduced motion the transition is disabled and the hint is pure cost.

---

## Not wrong — clearing stale items so they stop being re-reported

`FRONTEND_FULL_AUDIT.md` section A is mostly obsolete, and the one live item in it (H1
above) is filed against the wrong file. Checked against current source:

| A.n | Claim | Status |
|---|---|---|
| A.1 | No functional CTA | **still true** — M5, measured 0 in `<main>` above the fold |
| A.2 | No header nav, no footer | **obsolete** — `_app.tsx:579`, `:584`, `:1044`, `:1046` |
| A.3 | Fake review schema | **still true, wrong file** — moved to `_app.tsx`, now on 17 pages (H1) |
| A.4 | `foundingDate: 2020` | **still true, wrong file** — `_app.tsx:252`, on 123 pages (H1) |
| A.5 | `api.wecare.digital/v1/...` examples | **obsolete** — no such example remains on this page |
| A.6 | Vague stat placeholders | **obsolete** — none on this page |
| A.7 | Fake `<button>` pills, `cursor:default` | **obsolete** — zero `<button>` in `index.tsx` |

## Suggested order

1. **H1** — sitewide schema; own commit, re-run `seocheck.js`. Deletion plus two strings.
2. **H3** then **H2** — one resize listener and one `.is-armed`-style inversion fix the
   two together; `homeprobe.js` goes 5/12 → 10/12 with M4.
3. **M4** — `visibility`/`inert` instead of bare `opacity:0`.
4. **M6**, **L7**, **L8**, **L9** — one cleanup commit; no behaviour change except M6.
5. **M5** — blocked on the owner: CTA wording, CTA destination, price above the fold.

`homeprobe.js` is committed alongside this so each claim is re-runnable rather than
re-argued. It fails 7 assertions today by design — it is the record of what is still open.

---

## Reconciliation with the parallel audit in `869760f7`

Another session audited the same band while this ran. The two overlap on exactly two
findings and are otherwise complementary, so **neither supersedes the other**.

**Agreed, found independently:** its F1 = M5 here (no action, no focusable element above
the fold) · its F2 = H2 here (the pill ships 0-width). F2 also caught the first-paint
window, which is why H2 above is amended rather than left as a no-JS-only defect.

**Only in `869760f7`** — all five are real and not covered here:

| | Finding |
|---|---|
| F3 | 188px of blank white above the first word (108px header + 80px layout padding); the 80px was tuned around the deleted badge |
| F4 | The positioning takes 9.6s to read (4 words × 2400ms) and cannot be paused — WCAG 2.2.2 territory, since it moves automatically for over 5s |
| F5 | All-text fold; ~40% of the 1300px measure is empty and the first visual on the site is below it |
| F6 | Header height `108`/`96` is a magic number in four files, while `design-tokens.ts` `layout.headerHeight` is `60` (the dashboard bar) |
| F7 | `.btn` omits `'Inter'` from its font stack, so buttons render in the system face sitewide; `transition:all` also delays the focus ring |

**Only here** — H1 (fake schema sitewide in `_app.tsx`), H3 (reduced-motion resize clip),
M4 (invisible Tab stop), M6 (inverted reduced-motion rule), L7–L9.

### Two mock directories now exist, and one should go

- `docs/mocks/home-hero/index.html` — `869760f7`. Self-contained HTML, header and hero CSS
  copied verbatim, three frames. **Interactive**, so the rotation and focus can be driven
  by hand; **copied CSS**, so it can drift from `index.tsx` silently.
- `docs/mockups/home-hero-20260926/` — this session. Screenshots taken by injecting into
  the real static export, so fidelity cannot drift; **static**, so nothing can be clicked.

The fidelity/interactivity trade is genuine and the duplication is not worth keeping.
`docs/FRONTEND_DUPLICATION_AUDIT.md` exists because of exactly this pattern. Suggest
keeping the injection approach (it cannot go stale) and folding the interactive frames into
it as a `--serve` mode, then deleting the copied-CSS mock — but that is a call to make, not
one to take quietly.
