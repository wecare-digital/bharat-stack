---
inclusion: fileMatch
fileMatchPattern: ["src/pages/grahak-os/**", "src/components/**", "src/styles/**"]
---

# Public page design contract (/grahak-os)

Calibrated against notion.com by measuring the live site, not by eye. Values below
are what the page currently ships. Change them deliberately, not incidentally.

## Type ladder

Notion's ladder is counterintuitive: **the section h2 is heavier than the hero
h1** (700 vs 600). That is intentional — do not "fix" it.

| Role | Selectors | Spec |
|---|---|---|
| Hero h1 | `.hero-left h1` | `clamp(36px,4.3vw,60px)` / **600** / lh `1.04` / ls `-2.2px` / `rgba(0,0,0,.95)` |
| Section h2 | `.section-header h2`, `.api-info h2`, `.trust-heading` | `clamp(32px,4.2vw,54px)` / **700** / lh `1.04` / ls `-1.875px` / `rgba(0,0,0,.95)` |
| Card heading | `.capability-card h3`, `.why-item strong`, `.trust-caption` | `22px` / **700** / lh `1.27` / ls `-0.25px` / `#000` |
| Body — one level only | `.hero-left p`, `.section-header p`, `.api-desc`, `.capability-card p`, `.why-item span`, `.trust-subtext` | `20px` / **400** / lh `1.4` / ls `-0.125px` / `rgba(0,0,0,.898)` |

**There is exactly ONE body level across the whole page.** Verify after any change:

```js
// in devtools, expect a single entry
var s={};['.hero-left p','.section-header p','.api-desc','.capability-card p','.why-item span','.trust-subtext']
 .forEach(q=>document.querySelectorAll(q).forEach(e=>{var c=getComputedStyle(e);
 s[c.fontSize+'/'+c.lineHeight+'/'+c.letterSpacing+'/'+c.color]=1}));Object.keys(s)
```

Eyebrows/labels are **not uppercase and not letter-spaced** — notion uses plain
`14px / 400 / rgba(0,0,0,.54)`. Do not add `text-transform:uppercase`.

## Palette

| Token | Use |
|---|---|
| `#1a1a1a` | Brand lockup ("Bharat Stack"), header + footer |
| `#1a3a2a` | Dark green — icons, phone header, active states, accents |
| `#d1f470` | Lime — **our own surfaces only** (sent bubbles, active tab, hero pill) |
| `#ece5dd` | WhatsApp chat beige |
| `rgba(0,0,0,.898)` | Body text |
| `rgba(0,0,0,.95)` | Headings |

**Never put lime on a third-party mark.** The Meta card was lime and read as a
sticker we printed ourselves; a borrowed logo must look borrowed. A test pins this.

The inverse also holds: lime **is** the right green for our own marks. `BrandBadge`
— the pill on `/`, `/grahak-os` and `/vayulok` — fills with **`#d1f470` at full
strength and `#1a3a2a` type**, the same pair as `.tab.active` and `.msg.sent`, with
no border (neither of those carries one either). `#1a3a2a` on `#d1f470` is ~10:1.

There are exactly **three** lime treatments in this design language. Reach for one
of these rather than mixing a fresh tint or a new alpha — inventing an in-between
value is how `#f2fbf6` and `#fbfff0` got here in the first place:

| Treatment | Use | Examples |
|---|---|---|
| `#d1f470` fill + `#1a3a2a` type | our own surfaces, full voice | `.msg.sent`, `.tab.active`, `BrandBadge` |
| `rgba(209,244,112,.22)` fill | transient state, not identity | nav hover / active / expanded |
| `#1a3a2a` fill + `#d1f470` type | inverted, dark | `Layout.tsx` mode switch |

The badge began on the `.22` tint and was lifted, because that value composites to
`(245,253,224)` over white — a wash that reads as barely-not-white rather than as a
green badge. It is a **state** tint, not an identity one; that distinction is the
reason the two exist.

Retired, do not reintroduce: `#2f6b52`, `#075e54`, `#f2fbf6`, `#fbfff0`,
`#1e293b` (as the code panel body). All five are now absent from the page — the
last holdouts were `#fbfff0` on three `:hover` rules and `#1e293b` on `.api-demo`,
cleared along with `#0f172a` and `#94a3b8` from the same slate ramp. **Both code
panels are `#000`.**

`#4b5563` is also gone: pill labels are `rgba(0,0,0,.54)`, the label value above.
It was the only blue-tinted grey in the page's own copy and read cooler than the
neutral body text beside it.

## Hairlines — weight carries meaning

`2px` means hoverable, `1px` means static, and the colour is always `#e5e7eb`.

| Weight | Elements | Why |
|---|---|---|
| `2px solid #e5e7eb` | `.pill`, `.pp-pill`, `.capability-card`, `.mockup-wrapper` | All four have a `:hover` that swaps the border to lime `#d1f470`; it needs the weight to register |
| `1px solid #e5e7eb` | `.cap-icon`, `.why-item`, `.trust-card` | Static, no hover |

**Do not "unify" the two weights** — the split is a signal, not drift. `.trust-card`
was the one real inconsistency and used `rgba(0,0,0,.1)`; it is `#e5e7eb` now.

`.code-body`'s `1.5px solid rgba(255,255,255,.92)` is exempt: it is the editor-pane
stroke on a black panel, documented at its own rule.

## Hero mockup geometry — these are solved together

The code panel is anchored `bottom:0`, so **its top edge is a function of wrapper
height**: `panelTop = wrapperHeight - panelHeight`. Change one value and you move
the panel over the message bubbles.

```
.mockup-wrapper  min-height:614px      <- sets where the panel's top edge lands
.chat-area       min-height:504px      <- sets phone height (phone = 62 header + chat)
.phone           width:56% max 320px, top:28px
.code-box        width:60% max 340px   <- 56+60 = 116%, so a ~90px lap
```

Constraints that produced those numbers:

1. `panelTop` must clear the bottom of the **lowest right-aligned bubble** (~300px)
   → `wrapperHeight >= 577`
2. The panel should overhang the phone by only ~20px → `phoneBottom ≈ wrapperHeight - 20`

**The two min-heights move together, always.** They were 590/480 until the code
panel's `"message"` line grew past the panel's 36-character measure and wrapped to
two lines, adding ~22px of panel height. Both constraints above are differential, so
the pair went to 614/504: `panelTop` holds because the wrapper grew by what the panel
grew, and the ~20px overhang holds because the phone grew by what the wrapper grew.
Move one alone and you either drop the panel onto the sent bubbles or leave it
hanging 44px past the phone.

**Corollary: line length in `.code-body` is layout, not content.** 340px fits 36
monospace characters at 14px. Every extra wrapped line is ~22px of panel height
pushing the top edge up into the thread, so a copy edit in that code sample is a
geometry change — re-measure with the rect-intersection snippet below.

**The thread order is load-bearing.** Both `.msg.sent` bubbles sit at the top,
above the panel's edge; the lapped band below holds only `.msg.received` and the
typing dots, which are left-aligned and clear the panel. `.msg.received` is capped
at `66%` (not 82%) so it cannot grow past the panel's left edge.

Do **not** solve a collision by left-aligning a sent bubble — that puts a business
reply on the customer's side of the thread. Verify with rect intersection:

```js
var C=document.querySelector('.code-box').getBoundingClientRect();
[].forEach.call(document.querySelectorAll('.chat-area .msg'),function(e){var R=e.getBoundingClientRect();
if(Math.min(R.right,C.right)-Math.max(R.left,C.left)>2&&Math.min(R.bottom,C.bottom)-Math.max(R.top,C.top)>2)
console.warn('covered:',e.textContent)});
```

## Floating widgets — the z-index ceiling

`#wecarewa-widget` (injected by the external `wecare-wa-widget.js`) is **64×64 at
`right:16px bottom:120px` with `z-index: 2147483647`** — the maximum 32-bit
integer. **Nothing can ever be stacked above it.**

Consequence: a floating panel must clear it **geometrically**, not by z-index. Any
overlap means a green circle punches through your UI. `.wc-langbar` therefore sits
at `right:96px; bottom:16px` with its width capped against `calc(100vw - 108px)`.

## styled-jsx traps that have each caused a real bug here

1. **`<style jsx>` only scopes JSX statically visible inside `return`.** Extract
   markup into a variable or child component and **all** its styles silently
   vanish. This broke the hero pill once.
2. **styled-jsx does not scope composite components.** `<Link className="ft-link">`
   rendered with zero styles. `Footer.tsx` uses plain anchors with a documented
   `eslint-disable @next/next/no-html-link-for-pages` for this reason.
3. **No backticks inside `<style jsx>` CSS comments.** The block is a template
   literal; one stray backtick ends it and the build fails with
   `Expected '</', got 'ident'`.
4. **Media queries come after base rules**, so a `font-size` in a breakpoint wins.
   When removing size overrides, confirm you did not strip the base rule too — the
   symptom is type silently falling back to an inherited 17px.
5. **Global unscoped CSS in `src/styles/*.css` leaks in** for generic class names:
   `.pill`, `.stat`, `.phone`, `.chat-area`, `.btn-primary`, `.sep`, `.msg-time`,
   `.ftr`, `.contact-name`. `Layout.css:214` has
   `.layout ~ .ftr{position:fixed;bottom:0}` — a dormant landmine; `ftr` was
   dropped from Footer because of it.

## Routing traps

- `next.config.js` sets `trailingSlash: true` → URLs need the trailing slash.
- `src/pages/_app.tsx:382` has an **exact-match** public route allowlist:
  `router.pathname === '/' || '/grahak-os' || '/contact-test' || '/faq' || '/partners'`.
  Any other route renders an empty body with HTTP 200. Add new public pages there
  or they will look like a 404 that isn't one.
- `_app.tsx` returns `null` until `mounted`, so the static export ships an **empty
  body** for `/grahak-os/`. All JSON-LD and meta are invisible to non-JS crawlers.
  Known, unaddressed.

## Verifying a change

A dev server exiting without error proves nothing. Render it and measure:

```bash
rm -rf .next && npx next dev -p 3000
# browser: a plain F5 is enough
```

**The "always hard refresh" rule is retired.** That symptom was `public/sw.js`
serving `/_next/static/*.js` cache-first with no revalidation — styled-jsx ships
its CSS inside those chunks, so a cached chunk meant stale design, and
`Ctrl+Shift+R` only appeared to fix it because a hard reload is what bypasses a
service worker. Registration is production-only now (`a4963b02`). A worker already
installed in your browser needs **one** hard refresh to be torn down; after that
`F5` reflects edits. If styles still look stale, confirm DevTools → Application →
Service Workers lists none on `localhost:3000` before suspecting the CSS.

Gate before committing: `npx tsc --noEmit`, `npx vitest --run`, `npm run build`.

`src/test/GrahakOsPage.test.tsx` asserts on **source strings**, so any CSS value
change here breaks it by design — update the assertion and its comment, do not
loosen it. Several assertions exist specifically to stop a past decision being
reverted; each says why.

## Known open issues

- ~~Section rhythm is not implemented.~~ **It is.** `#touchpoint,#capabilities` sit
  on `#fafafa` at `width:100vw` with a centring negative margin, and `.pp-inner`
  carries the 1300px measure — see the `FULL-BLEED SECTIONS (pp-*)` block. The
  earlier `background:#fff` on those section classes is overridden by those id
  selectors, so grepping for `background:#fff` makes it look unimplemented when it
  is not. Rhythm today: hero white, touchpoint grey, api white, capabilities grey,
  why / trust / closer white.
- `.why-section` has **no `max-width`** — measures ~1391px against `.api`'s 1300px.
  Visually inert (white on white, and its children are capped at 700/1100px and
  centred), so this is a consistency nit, not a visible defect.
- `.page{overflow-x:hidden}` should be `clip` so tint bands reach the true viewport
  edge (~25px short today; changing it shifts all sections ~7.5px). **Still open.**
- ~~`.pill` uses `font-size:var(--text-base)`, and a mobile breakpoint pushes it to
  20px.~~ **Both fixed.** `.pill` and `.pp-pill` are an explicit `15px`. The token
  was the real hazard: `--text-base` is declared as `16px` in `tokens.css` and
  `15px` in `Pages.css`, and only `Pages.css` is imported by `_app.tsx` — so the
  size was decided by import order, and importing `tokens.css` would have resized
  every pill. The `20px` was already dead: this TYPOGRAPHY CONTRACT block is later
  in source order at equal specificity, so its value had always won.
- `.usecase-pills` is a 3-column `max-content` grid, not wrapped flex, so the six
  use cases land 3 + 3 deterministically (2 columns at `=<767px`). Under flex they
  broke 4 + 2, and a tightened cap would have sat ~27px from the boundary — close
  enough for a copy edit or a fallback font to flip it back.
