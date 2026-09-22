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

Retired, do not reintroduce: `#2f6b52`, `#075e54`, `#f2fbf6`, `#fbfff0`,
`#1e293b` (as the code panel body).

## Hero mockup geometry — these are solved together

The code panel is anchored `bottom:0`, so **its top edge is a function of wrapper
height**: `panelTop = wrapperHeight - panelHeight`. Change one value and you move
the panel over the message bubbles.

```
.mockup-wrapper  min-height:590px      <- sets where the panel's top edge lands
.chat-area       min-height:480px      <- sets phone height (phone = 62 header + chat)
.phone           width:56% max 320px, top:28px
.code-box        width:60% max 340px   <- 56+60 = 116%, so a ~90px lap
```

Constraints that produced those numbers:

1. `panelTop` must clear the bottom of the **lowest right-aligned bubble** (~300px)
   → `wrapperHeight >= 577`
2. The panel should overhang the phone by only ~20px → `phoneBottom ≈ wrapperHeight - 20`

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

- **Section rhythm is not implemented.** `.touchpoint`, `.api`, `.capabilities`,
  `.why-section` are all `background:#fff`. The intended alternating white / grey
  `#fafafa` rhythm was never applied.
- `.why-section` has **no `max-width`** — measures ~1391px against `.api`'s 1300px.
- `.page{overflow-x:hidden}` should be `clip` so tint bands reach the true viewport
  edge (~25px short today; changing it shifts all sections ~7.5px).
- `.pill` uses `font-size:var(--text-base)` while everything else is explicit, and
  a mobile breakpoint pushes it to 20px.
