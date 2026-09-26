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
