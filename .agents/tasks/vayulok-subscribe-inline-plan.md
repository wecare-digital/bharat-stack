# Implementation Plan — VayuLok subscribe block: button consistency, inline-only flow, real country code

Target files (must stay **byte-identical twins**):

- `docs/mocks/vayulok-live-mock.html`
- `docs/mocks/vayulok-final-v3.html`

Both are currently identical (`md5 6f73825a2560585055e958868fdbe174`). Edit `vayulok-live-mock.html`,
then copy it over `vayulok-final-v3.html`.

---

## 0. Environment facts established during exploration (read before step 1)

| Fact | Evidence |
| --- | --- |
| Branch is `fix/vayulok-subscribe-inline`, clean, **no conflict in progress** | no `MERGE_HEAD`/`REBASE*` in `.git`; `grep -c '^<<<<<<<'` on both mocks = 0 |
| It is `origin/stack` + 1 commit (`2d6ca401 docs(vayulok): rebase VayuLok mock onto current stack`) | `git rev-list --left-right --count origin/stack...HEAD` → `0 1` |
| The user's reported conflict was on `vayulok-preview`; that is already resolved by `2d6ca401` | `origin/vayulok-preview...HEAD` → `9 11` |
| **`diff` and `cmp` are NOT installed on this box** | `command -v diff` → missing |
| Twin comparison must therefore use `git --no-pager diff --no-index` or `md5sum` | both verified working, exit 0 / single hash |
| `npx vitest run`, `npx tsc --noEmit` and `npm run lint` **do not cover `docs/mocks`** | `grep -rln 'docs/mocks\|vayulok-live-mock' tests src scripts .github` → no hits |
| The repo's real rendered-UI verification tool is `tools/browser/` (playwright-core + `lib/browser.js`) | `tools/browser/README.md`; CI step "Browser harness" runs `npm install --prefix tools/browser` then the scripts |
| Harness installs and resolves Chromium here | `npm install --prefix tools/browser` → 114 packages; `resolveChrome()` → `/opt/playwright/chromium-1232/chrome-linux64/chrome` |
| `tools/browser/node_modules` is gitignored | `git check-ignore -v tools/browser/node_modules` → `.gitignore:2:node_modules/` |
| `.agents/` **is tracked** (105 files) — this plan file will show as untracked until committed | `git check-ignore .agents/...` → not ignored |
| The committed PNGs are already **stale** against the committed HTML | current render is `1280 x 5583` / `390 x 6547`; committed PNGs are `1347 x 6040` / `390 x 7506` |
| The file the user viewed is byte-identical in the subscribe region to the one measured here | `git show origin/vayulok-preview:docs/mocks/vayulok-live-mock.html` — same 81420 bytes, same line numbers 1021/1034/1037/1038 |

Harness launch recipe used for every measurement below (reuse it):

```bash
cd /projects/sandbox/wecare-digital
npm install --prefix tools/browser --no-audit --no-fund   # once per sandbox
node tools/browser/<script>.js
```

`tools/browser/lib/browser.js` exports `launch()` and `gotoStable()` and finds Chromium itself —
never hardcode a revision (that file's header explains why).

---

## 1. Measured audit of EVERY button and button-like control in the VayuLok section

All numbers below are **computed styles and bounding rects measured in headless Chromium** at
viewport 1280×900 and 390×844 from `file:///.../vayulok-live-mock.html` — not read off the source.

The **ROLE 1 action contract** as the file actually documents it (lines 169–197) and as
`src/styles/button.css` defines it: `.btn` radius **13px** (button.css:31) + `.btn-lg` height
**52px** / font **16px** (button.css:52–56) + `.btn-primary` fill `#d1f470`, colour `#1a3a2a`,
border `2px solid #1a3a2a` (button.css:78–82), weight 500, padding `0 24px`.

| Control | Selector | Measured 1280 / 390 | ROLE | Verdict |
| --- | --- | --- | --- | --- |
| **Load** (key gate) | `#vl-keyload.vl-btn` | h52, radius 13px, 16px/500, border 2px `rgb(26,58,42)`, bg `rgb(209,244,112)`, pad `0 24px` | 1 | **CONFORMS** |
| **Subscribe** | `.vl-sub-action .vl-btn` | h52, radius 13px, 16px/500, border 2px, lime | 1 | geometry **CONFORMS**, **position does not** — see D1 |
| **Contribute** | `.vl-bc-submit-wrap .vl-btn` | h52, radius 13px, 16px/500, border 2px, lime | 1 | **CONFORMS** |
| **Send code** | `.vl-sub-action .vl-btn-quiet` | **h32**, radius 999px, **12px/700**, border 1px, white, pad `0 12px` | 2 | ROLE 2 by design, but **sits in the same row as a ROLE 1 button** — see D2 |
| **Clear key** | `#vl-keyclear.vl-btn-quiet` | **h32**, radius 999px, 12px/700, pad `0 12px`; `hidden` by default | 2 | **MISMATCH** against its row-mates — see D3 |
| **AQI** (pressed) | `#vl-layer-aqi.vl-layer` | h38, radius 999px, 13px/700, border 1px `rgb(26,58,42)`, bg lime, pad `0 16px` | map control (undocumented role) | consistent with PM2.5; pressed state intentional |
| **PM2.5** | `#vl-layer-pm.vl-layer` | h38, radius 999px, 13px/700, border 1px `rgb(229,231,235)`, white | map control | consistent |
| **Air / Weather** | `.vl-tab` ×2 | h40, radius 999px, 15px/700, border **0** | tab (undocumented role) | internally consistent |
| **₹99 / ₹249 / ₹499 / Other** | `.vl-bc-choice-face` ×4 | h40, radius 999px, 15px/700, border 2px, pad `8px 16px` | 4 (amount chip) | **CONFORMS** to BlogContribution.tsx:277 |
| WhatsApp number field | `.vl-subscribe .vl-input` | h52, radius 10px, border 1px `rgb(229,231,235)`, 16px, pad `0 14px` | 3 | **CONFORMS** to BlogSubscribe.tsx:329 |

### The three measured defects

**D1 — Subscribe floats 19.5px above the field it belongs to.** `.vl-sub-action` is declared
**twice**: line 307 (`display:flex;align-items:center;gap:12px;flex-wrap:wrap`) and line 644
(`display:flex;align-items:center;min-height:91px`). Both apply (verified: computed `gap:12px`,
`flex-wrap:wrap`, `min-height:91px` — they set different properties, so this is *not* a cascade
conflict, which is why it was worth measuring rather than assuming). The `91px` is lifted verbatim
from `BlogSubscribe.tsx:348` `.blog-subscribe-action{min-height:91px}`, where 91 = input 52 +
gap 7 + `.verify-row` 32. **The mock has no verify row**, so its `.vl-cell` is only **76px**
(label 17 + gap 7 + input 52). Measured consequence: `.vl-sub-action` is 91px tall holding a 52px
button centred in it, leaving **19.5px dead space above and below**; because `.vl-sub-fields` uses
`align-items:flex-end`, the row bottoms align but the **Subscribe button's bottom edge sits 19.5px
above the input's bottom edge**. Confirmed visually in the committed
`docs/mocks/vayulok-section-subscribe.png` and in a fresh crop. Identical at 390.

**D2 — two shapes butted together in one action row.** `Send code` (32px/999px/12px-700/white)
sits 12px from `Subscribe` (52px/13px/16px-500/lime). Centres align, heights differ by 20px.
This is the row the user pointed at, and it is the literal reading of "buttons are not matching".
It is removed by fix 2, not restyled.

**D3 — `Clear key` does not match its row-mates.** Revealed by removing `hidden` and re-measuring:
in `.vl-map-controls` it renders **h32, 12px/700, pad 0 12px** next to two `.vl-layer` pills at
**h38, 13px/700, pad 0 16px** — a 6px height difference and a 3px vertical offset inside a 3-item
row. Invisible in the committed screenshots because the no-key state hides it; visible to anyone
who loads a key, which is the state the mock exists to demonstrate.

**D4 — dead rule.** `.vl-verify-row` (line 643) matches **0 elements** in the rendered DOM — a
leftover of the two-step verify flow.

**D5 — the roles comment under-documents reality.** The block at lines 165–226 declares four roles
and asserts "there is exactly ONE rule here per role. Unused roles are deleted rather than left
dormant." The section actually renders **six** shapes (52, 40 tab, 40 chip, 38 map, 32 quiet, plus
the 52px field). The tab and map-control roles are absent from the contract, which is why "buttons
don't match the documented contract" is true as written even though the three ROLE 1 buttons pass.

### Recorded ambiguity (carry forward to review)

The task brief states the ROLE 1 contract is "**13px font** / 52px height, from
`BlogSubscribe.tsx:338`". **Reading the files, that is a conflation of two different things** and I
am not adopting it:

- The mock's line 290 comment says "'Subscribe' keeps the **13px/52px** action shape **from
  button.css:31**". `src/styles/button.css:31` is `border-radius: 13px`; `:52` is
  `.btn-lg{height:52px}` with `font-size:16px`. So **13px is the RADIUS, not the font size.**
- `BlogSubscribe.tsx:338` is `.verify-row button` — `32px` tall, `12px/700`, `999px` radius. That is
  the mock's **ROLE 2** quiet shape (line 199 cites it correctly), not ROLE 1.
- `docs/mocks/home-hero/index.html:192` independently confirms the action shape the VayuLok mock
  adopted: `height:52px;font-size:16px;font-weight:500;border-radius:13px;padding:0 24px`.

**Chosen interpretation: ROLE 1 = 13px radius + 52px height + 16px/500 + 2px `#1a3a2a` + lime.**
The three ROLE 1 buttons already satisfy it, so the fix is positional and cross-role, not a
restyle. **Alternative, rejected:** reading "13px font" literally and shrinking `.vl-btn` to 13px
type — rejected because it would break conformance with `button.css` `.btn-lg`, with
`home-hero/index.html` `.home-btn`, and with the file's own citation, i.e. it would *create* the
inconsistency being reported. If the owner truly meant 13px type, that is a change to
`src/styles/button.css` affecting every button on the site and is out of this task's scope.

---

## 2. Reconstruction of the "unnecessary dialog"

Rendered the page and interacted with it in headless Chromium. **Nothing that is literally a dialog
exists today**: `document.querySelectorAll('dialog')` → 0; `[role=dialog],[role=alertdialog],[aria-modal]`
→ 0; no `position:fixed` node anywhere in `.vl-vayulok`; clicking **Subscribe** with the field empty
and again with `9876543210` in it fired **zero** Playwright `dialog` events and changed
`document.body.innerHTML.length` by **0** (42452 → 42452). No control carries `required`, `pattern`,
`minlength` or `maxlength`; every form is `onsubmit="return false"` and `checkValidity()` is `true`.

**Primary interpretation (adopted): the "dialog" is the two-step verify/OTP confirmation the flow
still promises.** Three pieces of evidence, all in the artifact the user viewed:

1. `Send code` (line 1037) is a stub of `BlogSubscribe.tsx`'s real two-step flow, where pressing it
   swaps the row for an OTP `input.otp` + `Verify` button.
2. `.vl-verify-row` CSS is still present at line 643 and matches nothing — the shell of step two.
3. The head copy at line 1021 reads "**Verify your WhatsApp number once**, then pick the places you
   want watched." — it tells the reader there is a second screen before subscribing.

The user's words map onto this directly: "suub sbing section unnesary digalog" — the extra step is
*in the subscribing section*, which is where `Send code` is.

**Alternative interpretation B (recorded, deliberately NOT actioned): `.vl-keygate`.** It is the one
thing on the page that *looks* like a modal — `position:absolute;inset:0;z-index:6` (the only
`z-index >= 6` in the section) filling the map stage with a grey scrim and a centred white card
("Maps key" / `Load`). See `docs/mocks/vayulok-section-subscribe.png`. **Leave it alone**: the task
scopes fix 2 to "Subscribing must be completable inline, within the section itself", the key gate is
in the map column and not the subscribe flow, and it is *load-bearing* for the zero-network
requirement (the no-key state is what keeps outbound requests at 0). If the reviewer or owner
decides B was meant, that is a separate change and must be raised, not absorbed here.

**Alternative interpretation C (recorded, and actively guarded against): a native constraint-validation
bubble.** It does not fire today, but this repo has **already shipped a fix for exactly this defect**:
`src/components/PhoneField.tsx` removed `required` from the number input because "the owner reported
the native bubble ITSELF as the defect: 'Please fill out this field.' with an orange warning icon,
photographed on the live sign-in page… cannot be themed, cannot be translated… contradicts the
standing no-red instruction", replacing it with `aria-required="true"`. The new country-code control
in step 5 is the highest-risk place to reintroduce it, so step 5 forbids every constraint attribute
and step 9 asserts no dialog fires.

### How the flow collapses to one inline step

- Delete the `Send code` button (line 1037).
- Delete the dead `.vl-verify-row` rule (line 643).
- Remove the promise of a second step from line 1021 **by deletion only, writing no new words**:
  `Verify your WhatsApp number once, then pick the places you want watched.` → `Pick the places you
  want watched.` The mock's own standing rule is "do not invent copy" (see the two `.vl-placeholder`
  blocks). *Alternative:* a rewritten sentence naming the one-step flow — rejected because it is
  invented product copy; flag to the owner that a replacement sentence is welcome.
- Replace the second step with an **inline `role="status"` line**, ported verbatim from
  `BlogSubscribe.tsx:349-350` `.blog-subscribe-status{min-height:22px;margin:12px 0 0;font-size:14px;line-height:1.45;color:rgba(0,0,0,.7)}`
  as `.vl-sub-status`. On submit it reports inline; nothing new is mounted, nothing is overlaid.
- The completion strings are **lifted from the shipped component, not invented**: `BlogSubscribe.tsx`
  renders `action={ done ? 'Subscribed' : 'Subscribe' }`, so on inline submit the button label flips
  to `Subscribed` and the status line shows the composed number. On an empty/wrong-length number the
  status line shows the length hint derived from `nationalLengthHint('+91')` → `10-digit WhatsApp number`,
  and `aria-invalid="true"` goes on the number segment. No bubble, no overlay, no second row.

---

## 3. Design of the country-code control (modelled on `PhoneField.tsx`)

Today the only "+" anywhere in the VayuLok section is the **placeholder string `+91 00000 00000`**
(line 1034) — verified exhaustively: no `::before`/`::after` `content` in `.vl-vayulok` contains `+`,
and no text node in the section contains one. So the user's "check + for whats aletr" is the
**fake country code painted in placeholder grey inside the WhatsApp-alerts field** — a stray glyph
standing in for a control that does not exist. `PhoneField.tsx` documents this precise failure mode
for the `NUMBER_FORMAT_HINT` constant: a placeholder that reads as a value already in the field.

Replace it with the shipped divided field. Markup (inside the existing `.vl-cell.vl-cell-wide`,
`<label>` becomes a `<div>` because the cell now holds two controls — the visible `<span>` becomes
`<label for="vl-sub-phone">`):

```html
<div class="vl-pf">
  <input class="vl-pf-code" id="vl-sub-dial" type="search" inputmode="tel"
         autocomplete="off" autocorrect="off" spellcheck="false" enterkeyhint="next"
         aria-label="Calling code" maxlength="4" value="+91" placeholder="+91">
  <input class="vl-pf-num" id="vl-sub-phone" type="tel" inputmode="tel"
         autocomplete="tel-national" aria-required="true"
         placeholder="10-digit WhatsApp number" aria-describedby="vl-sub-status">
</div>
```

CSS — **the ROLE 3 contract (52px, 1px `#e5e7eb`, 10px radius) moves onto the container**, which is
exactly what `PhoneField.tsx` does ("The outline, the radius and the height live here, on the
container, and the two segments inside carry none of their own"). The ROLE 3 comment at lines
214–222 must be amended to say so, otherwise the contract text contradicts the markup.

```css
.vl-pf{display:flex;align-items:stretch;min-height:52px;
  border:1px solid var(--hair);border-radius:var(--r-field);background:var(--paper);overflow:hidden}
.vl-pf-code{flex:0 0 auto;border:0;border-inline-end:1px solid var(--hair);
  padding-inline:12px;min-inline-size:78px;max-inline-size:86px;
  background:var(--paper);color:var(--ink-base);font:inherit;font-size:17px;font-weight:600;cursor:text;
  border-start-start-radius:9px;border-end-start-radius:9px;
  border-start-end-radius:0;border-end-end-radius:0}
.vl-pf-code::-webkit-search-cancel-button{display:none}
.vl-pf-num{flex:1 1 auto;min-inline-size:0;border:0;padding-inline:16px;
  background:var(--paper);color:var(--ink-base);font:inherit;font-size:17px;
  border-start-start-radius:0;border-end-start-radius:0;
  border-start-end-radius:9px;border-end-end-radius:9px}
.vl-pf-code:focus-visible,.vl-pf-num:focus-visible{outline:3px solid var(--green);outline-offset:-3px}
.vl-pf:focus-within{border-color:var(--green);box-shadow:0 0 0 3px rgba(209,244,112,.55)}
@media(max-width:360px){.vl-pf-code{padding-inline:8px}.vl-pf-num{padding-inline:12px}}
```

Two declarations from `PhoneField.tsx` are **deliberately omitted**, each with a comment:
`margin-bottom:20px` (consumer spacing — `.vl-cell{gap:7px}` already owns it) and
`scroll-margin-top:128px/112px` (clears a fixed 108px header; the mock has no header).

Inline JS, ES5, appended inside the existing `(function(){'use strict'; … })()` IIFE at line 1187
and written in its house style (`var`, `Array.prototype.slice.call`, no arrow functions, no
template literals, no `fetch`, no timers):

- `VL_DIAL_CODES` — a compact literal `[['+91','India'],['+971','United Arab Emirates'], …]` ported
  from `src/lib/dialCodes.ts` `DIAL_CODES`, **preserving its order** (India first — "a select whose
  first option is the common answer is faster than one that opens on Argentina") and **preserving its
  exclusions** (`+86`, `+98`, `+963`, `+850` — WhatsApp undeliverable; `+92` — owner instruction).
  Cite `src/lib/dialCodes.ts` as the source of truth in a comment so the two cannot silently diverge.
- `vlNormaliseDial(raw)` — port of `normaliseDialSearch`: strip non-digits, `slice(0,3)`, re-prefix `+`.
- `vlFindDial(code)` / `vlLengthHint(code)` / `vlValidLength(code, national)` — ports of
  `findDialCode` / `nationalLengthHint` / `isValidNationalLength`, same semantics (including
  "no rule for this country ⇒ accept anything non-empty").
- Behaviour on `.vl-pf-code`, mirroring `DialCodeSearch`: `focus` → `select()`; `input` → normalise,
  commit when `vlFindDial` matches and refresh the number placeholder from `vlLengthHint`;
  `blur` → revert to the last committed code when unresolved; `keydown Enter` → `preventDefault()`
  then `blur()` when resolved. `aria-invalid="true"` while unresolved.
- Submit handler on `.vl-sub-fields`: `event.preventDefault()`, compose E.164 the way
  `BlogSubscribe.composePhone` does (`dial + national.replace(/\D/g,'').replace(/^0+/,'')`), then
  write the status line and flip the button label as described in §2.

**Design decision — no dropdown.** `PhoneField.tsx` states it outright: "Search input only: no
native country dropdown, no flag, no country name", and `dialCodes.ts` forbids emoji flags
(Windows renders them as bare letters). **Alternative considered and rejected: a native
`<datalist>`** — it would add filter-as-you-type discoverability for zero bytes of JS and zero
network, but it renders a **native popup**, which is the same class of unthemeable browser-chrome
affordance the user is complaining about in fix 2, and it contradicts the shipped component's
documented decision. Discoverability is carried instead by the always-visible `+91`, the
length-hint placeholder that updates with the code, and the inline status line. **Flag this to the
owner** — if they want a visible list, a datalist is the cheapest route and the decision is theirs.

**Enforced constraint, from `PhoneField.tsx`'s own history:** no `required`, no `pattern`, no
`minlength`, no `maxlength` on the number segment, and no `type="email"` anywhere —
`aria-required="true"` carries the semantic instead. `maxlength="4"` on the **code** segment is kept
because `DialCodeSearch` has it and `maxlength` alone never triggers a validation bubble (it blocks
typing). Step 9 asserts this empirically rather than trusting it.

---

## Ordered steps

- [ ] **1. Consolidate `.vl-sub-action` into one rule and fix the Subscribe baseline (D1).**
      Delete the duplicate at line 644 and keep a single rule next to the SUBSCRIBE CSS block:
      `.vl-sub-action{display:flex;align-items:center;gap:12px;flex-wrap:wrap}` — **no `min-height`**.
      Add a comment recording why `min-height:91px` (BlogSubscribe.tsx:348) was dropped: the 91 clears
      input 52 + gap 7 + `.verify-row` 32, and this mock has no verify row, so it was holding a 52px
      button 19.5px off the field's baseline. Also delete the dead `.vl-verify-row` rule (line 643, D4).
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: `node tools/browser/vayuloksubcheck.js` (created in step 7) is not available yet — for
      this step run the interim check from step 7's recipe manually, or defer verification to step 7
      and confirm only that the page still renders with 0 console errors and 1 request:
      `node tools/browser/vayuloksubcheck.js` after step 7 must report `subscribe button bottom ==
      number field bottom (±1px)` at both 1280 and 390.

- [ ] **2. Collapse the subscribe flow to one inline step (fix 2).**
      Delete the `Send code` button (line 1037). Edit line 1021 by deletion only to
      `Pick the places you want watched.` Add the inline status region immediately after the form:
      `<p class="vl-sub-status" id="vl-sub-status" role="status"></p>` with the `.vl-sub-status` rule
      ported verbatim from `BlogSubscribe.tsx:349-350`. Update the SUBSCRIBE comment block (lines
      297–307) so it no longer describes a `Send code` + `Subscribe` pair, and record that the
      one-step flow is deliberate.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: after step 7, `node tools/browser/vayuloksubcheck.js` reports `.vl-sub-action` children
      = 1, `.vl-btn-quiet` inside `.vl-subscribe` = 0, `.vl-verify-row` = 0, and no `dialog` event on
      submit. Depends on step 1 (same rule block).

- [ ] **3. Add the divided phone field with the +91 calling-code segment (fix 3).**
      Replace line 1034's single `.vl-input` with the `.vl-pf` / `.vl-pf-code` / `.vl-pf-num` markup
      from §3; turn the `.vl-cell` `<label>` into a `<div>` and its `<span>` into
      `<label for="vl-sub-phone">WhatsApp number</label>` (keeping `.vl-cell>span` styling working by
      extending the selector to `.vl-cell>span,.vl-cell>label`). Add the `.vl-pf*` CSS from §3 directly
      beneath the ROLE 3 `.vl-input` rule, and amend the ROLE 3 comment (lines 214–222) to state that
      the 52px/1px `#e5e7eb`/10px box has two forms — plain `.vl-input` and the divided `.vl-pf`
      container — citing `src/components/PhoneField.tsx`. Keep `.vl-cell-wide{min-width:270px}`.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: after step 7, computed assertions pass — `.vl-pf` height 52, `border-top-width` 1px,
      `border-top-color` `rgb(229,231,235)`, `border-radius` 10px; `.vl-pf-code` `value === '+91'`;
      segments carry 0 border width except the divider; both inputs have `required === false` and no
      `pattern`.

- [ ] **4. Add the inline calling-code JS inside the existing IIFE.**
      Append the `VL_DIAL_CODES` table and `vlNormaliseDial` / `vlFindDial` / `vlLengthHint` /
      `vlValidLength` ports plus the `.vl-pf-code` focus/input/blur/Enter handlers and the
      `.vl-sub-fields` submit handler, exactly as specified in §3, in the file's ES5 house style.
      Keep the `onsubmit="return false"` attribute on the form as the belt — the JS handler is the
      braces. Update the script's header comment ("Three things and nothing else") to name the fourth.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: after step 7, the interaction assertions pass — typing `971` in the code segment commits
      `+971` and the number placeholder becomes `8- or 9-digit WhatsApp number`; typing `123` leaves
      `aria-invalid="true"` and blur reverts to `+91`; submitting `9876543210` flips the button label
      to `Subscribed` and writes `+919876543210` into `#vl-sub-status`; **zero `dialog` events
      throughout**. Depends on step 3.

- [ ] **5. Unify the map-controls row and retire the now-unused ROLE 2 (D3, D5).**
      Extend the `.vl-layer` geometry rule's selector to `.vl-layer,.vl-map-btn` (and the `:hover` /
      `:focus-visible` rules likewise), leaving `[aria-pressed="true"]` on `.vl-layer` only, then
      change `#vl-keyclear` from `class="vl-btn-quiet"` to `class="vl-map-btn"`.
      **Do not give it `.vl-layer`** — the JS at line ~1205 attaches the pressed-state toggle to every
      `.vl-layer`, so `Clear key` would silently join the AQI/PM2.5 radio group. Using a separate
      geometry class leaves that selector untouched.
      `.vl-btn-quiet` then has **no remaining users** (its only two were `Send code`, deleted in step 2,
      and `Clear key`), so per the file's own rule — "Unused roles are deleted rather than left
      dormant" — delete the `.vl-btn-quiet` / `:hover` / `:focus-visible` rules and the ROLE 2 comment
      block (lines 199–210), and remove `.vl-btn-quiet` from the scoped-`[hidden]` comment at line 110
      (the `!important` there now exists for `.vl-map-btn`'s `display` — restate the reason, keep the rule).
      Then rewrite the roles comment block (lines 165–226) to enumerate **every** surviving shape with
      its measured geometry and its `file:line` citation: ROLE 1 action `.vl-btn` (52/13px/16-500,
      button.css:31+52+78), ROLE 2 text input `.vl-input` + `.vl-pf` (52/1px `#e5e7eb`/10px,
      BlogSubscribe.tsx:329 + PhoneField.tsx), ROLE 3 amount chip `.vl-bc-choice-face`
      (40/999px/15-700/2px, BlogContribution.tsx:277), ROLE 4 map control `.vl-layer`/`.vl-map-btn`
      (38/999px/13-700), ROLE 5 tab `.vl-tab` (40/999px/15-700, border 0). Renumber consistently.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: after step 7, with `hidden` removed from `#vl-keyclear` all three `.vl-map-controls`
      children measure height 38, `font-size` 13px, `padding-inline` 16px and identical `top`/`bottom`;
      `.vl-btn-quiet` matches 0 elements and the string `vl-btn-quiet` appears 0 times in the file;
      clicking `Clear key` does **not** change any `aria-pressed` attribute.

- [ ] **6. Re-assert the zero-network contract in the comments and in the markup.**
      Confirm the file still has no `<link rel=stylesheet>`, no `src=` outside the runtime-assembled
      Maps URL, no `@font-face`, no `@import`, no `https://` literal, and no new inline asset. The
      note near line 48 ("THE FONT STACK IS DECLARED LOCALLY AND NEVER FETCHED") stays verbatim.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: after step 7, the harness reports **exactly 1 request** (the `file://` document itself)
      at both widths, and `grep -c 'rel="stylesheet"\|@font-face\|@import' docs/mocks/vayulok-live-mock.html`
      is 0 — the request count is the real verification; the grep is only a secondary cross-check.

- [ ] **7. Add the verification harness `tools/browser/vayuloksubcheck.js`.**
      One script following the conventions of its neighbours (`'use strict'`, a header comment
      explaining *why* rects rather than grep, `require('./lib/browser')` for `launch`/`gotoStable`,
      a `--json` flag, `process.exit(1)` on any failed assertion). It must, at **1280×900 and
      390×844** against `file:///…/docs/mocks/vayulok-live-mock.html`:
      (a) assert the ROLE 1 contract on `#vl-keyload`, the `.vl-subscribe .vl-btn` and
      `.vl-bc-submit-wrap .vl-btn` — height 52, radius 13px, 16px/500, 2px `rgb(26,58,42)`,
      `rgb(209,244,112)`;
      (b) assert the Subscribe button's bottom equals the `.vl-pf` bottom within 1px;
      (c) assert the `.vl-pf` ROLE 3 box and the two segments' geometry;
      (d) assert `.vl-map-controls` children are uniform with `#vl-keyclear` revealed;
      (e) assert `.vl-btn-quiet` and `.vl-verify-row` match 0 elements and `dialog`/`[role=dialog]`/
      `[aria-modal]` count 0;
      (f) drive the interaction set from step 4 with a `page.on('dialog')` listener that fails the run
      if it ever fires, and assert `document.body.innerHTML` gains no new element wrapper;
      (g) assert request count is 1 and console/page errors are 0.
      This file is a **deliberate addition beyond the two HTML twins**: `tools/browser/README.md`
      exists precisely because "Re-run the harness" was once an instruction nobody could follow, and
      the repo's `npx vitest run` / `npx tsc --noEmit` / `npm run lint` provably do not cover
      `docs/mocks`. *Alternative:* keep the script outside the worktree — rejected, it would make this
      plan's verification unrepeatable by the reviewer.
      Files: `tools/browser/vayuloksubcheck.js`
      Verify: `npm install --prefix tools/browser --no-audit --no-fund && node tools/browser/vayuloksubcheck.js`
      — exit 0 and every assertion in (a)–(g) reported as passing at both widths.

- [ ] **8. Copy the edited file over its twin and prove they match.**
      `cp docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html`
      Files: `docs/mocks/vayulok-final-v3.html`
      Verify: `git --no-pager diff --no-index docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html; echo $?`
      → **empty output and `0`**. Cross-check:
      `md5sum docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html | awk '{print $1}' | sort -u | wc -l`
      → `1`. **`diff` is not installed on this box** — do not use it.

- [ ] **9. Run the full verification pass and record the evidence.**
      In order: `npm install --prefix tools/browser --no-audit --no-fund`;
      `node tools/browser/vayuloksubcheck.js` (exit 0);
      `node tools/browser/vayuloksubcheck.js --json > /dev/null` (shape check);
      then the same script pointed at `docs/mocks/vayulok-final-v3.html` so the twin is verified as a
      twin and not merely byte-compared. Repo-level regression guard: `git status --short` must list
      only the intended paths, and `npx tsc --noEmit` plus `npx vitest run` must still pass (they do
      not touch `docs/mocks`, so they are a cheap confirmation that nothing leaked into `src/`).
      Files: none
      Verify: all four commands exit 0; paste the harness's assertion table into the task findings.

- [ ] **10. Regenerate the companion screenshots with a pinned, documented recipe.**
      Add the capture to `tools/browser/vayuloksubcheck.js` behind a `--shots` flag (one script, one
      source of truth for viewports) and regenerate all seven PNGs for **both** twins:
      • `docs/mocks/vayulok-live-mock-1280.png` and `docs/mocks/vayulok-final-v3-1280.png` —
        viewport 1280×900, `fullPage:true`
      • `docs/mocks/vayulok-live-mock-390.png` and `docs/mocks/vayulok-final-v3-390.png` —
        viewport 390×844, `fullPage:true`
      • `docs/mocks/vayulok-section-desktop.png` — 1440×950, `scrollY = 0`
      • `docs/mocks/vayulok-section-scrolled.png` — 1440×950, `.vl-hours` scrolled into view
        (`{block:'center'}`)
      • `docs/mocks/vayulok-section-subscribe.png` — 1440×950, `.vl-subscribe` scrolled into view
        (`{block:'center'}`)
      The three 1440×950 anchors are **reconstructed from the committed images**, not documented
      anywhere — record the recipe in the script's header so the next pass does not have to guess.
      **Expect the full-page dimensions to change**: the committed `*-1280.png` are `1347×6040` and
      `*-390.png` are `390×7506`, while the *current committed HTML* renders `1280×5583` and
      `390×6547`. The committed PNGs are therefore **already stale**; the new `1280`-wide and shorter
      images are the correction, not a regression. Note it in the commit message so a reviewer
      diffing image sizes is not misled.
      Files: `tools/browser/vayuloksubcheck.js`, the seven PNGs above
      Verify: `node tools/browser/vayuloksubcheck.js --shots` exits 0; every PNG's width is 1280 / 390
      / 1440 as listed; `md5sum docs/mocks/vayulok-live-mock-1280.png docs/mocks/vayulok-final-v3-1280.png`
      yields one hash (same for the 390 pair); open `vayulok-section-subscribe.png` and confirm by eye
      that the lime panel shows **one** button, baseline-flush with a **divided** field whose left
      segment reads `+91`.

- [ ] **11. Commit on the current branch; do not push.**
      Stage only the intended paths by name — `.kiro/hooks/block-broad-git-staging.json` exists, so
      `git add -A` / `git add .` are blocked. Message: what + why, naming the three fixes, the ROLE 1
      radius-vs-font-size ambiguity and the chosen reading, and the screenshot dimension change.
      Also note that `.kiro/steering/git-workflow.md` mandates a single-branch workflow on `stack`;
      this work sits on `fix/vayulok-subscribe-inline` because the workflow placed it there, so
      **ask before merging or renaming** rather than switching branches unilaterally.
      Files: the two HTML twins, the seven PNGs, `tools/browser/vayuloksubcheck.js`, this plan file
      Verify: `git status --short` is empty afterwards; `git show --stat HEAD` lists exactly the
      intended paths and nothing under `src/`.

---

## Needs verification during implementation (do not assume these away)

1. **`Clear key` visual mismatch (D3).** Proven by computed styles with `hidden` removed; the cropped
   screenshot came back blank because the element sits behind the key-gate scrim at that scroll
   position. Re-capture it properly — scroll the map stage into view, remove `hidden`, then screenshot
   `.vl-map-controls` — and confirm the 38/38/38 row by eye as well as by rect.
2. **The 390px fit of the divided field.** Measured inner width at 390 is **322px**. With the code
   segment at 78–86px plus a 1px divider the number segment gets ~236px, and the placeholder
   `10-digit WhatsApp number` at 17px is roughly 190px — tight. If it clips or the field overflows,
   the remedy is already in `PhoneField.tsx`: tighten `padding-inline` (the `@media(max-width:360px)`
   rule) rather than shrinking the 52px target or the 17px type. Measure
   `.vl-pf-num.scrollWidth > clientWidth` and the document's `scrollWidth` at 390 (must stay 390).
3. **Whether the owner meant `.vl-keygate` by "dialog"** (alternative B in §2). Not actioned here.
   Raise it; do not silently remove the key gate — it is what holds the page at zero requests.
4. **Whether a visible calling-code list is wanted** (the rejected `<datalist>` in §3).
5. **The `vayulok-preview` branch.** The htmlpreview URL the user shared points at
   `origin/vayulok-preview`, which is 11 commits behind this branch. The fix will not appear at that
   URL until that branch is updated and the `?v=` cache-buster is bumped. Confirm with the owner who
   does that; it is outside this task's file list.
6. **No horizontal overflow regression.** Document `scrollWidth === clientWidth` today at both 1280
   and 390 (the `.vl-hour` elements that extend past the viewport are inside `.vl-hours`,
   `overflow-x:auto`, and are expected). Re-assert after the edits.

## Scratch artifacts from this exploration

The probe scripts used to produce every measurement above live **outside the worktree** at
`/projects/sandbox/.vlprobe/` (`probe2.cjs` dialogs/constraints, `probe3.cjs` row geometry,
`probe4.cjs` overflow + crops, `shotsize.cjs` screenshot dimensions). They are reference material
for step 7 and must not be committed.
