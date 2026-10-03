# Implementation Plan — VayuLok mock: WhatsApp subscribe button + working location search

Branch: `fix/vayulok-subscribe-inline` (already checked out at `52f9d6f8`, upstream
`origin/fix/vayulok-subscribe-inline` exists). Confirm with `git branch --show-current` and stay
there. Never touch `feat/vayulok-update`, `vayulok-preview`, `stack` or `main`. No pull request.

> `.kiro/steering/git-workflow.md` mandates single-branch work on `stack`. It also exempts a
> branch the user named explicitly, which `fix/vayulok-subscribe-inline` is. Push with
> `git push origin fix/vayulok-subscribe-inline` (no `-u`; upstream is already set).

Scope: `docs/mocks/vayulok-live-mock.html`, `docs/mocks/vayulok-final-v3.html` (byte-identical
twins, both at `dbdb2b83aad787d45e814151787f12931c5f5a56` today), the six companion PNGs beside
them, and `tools/browser/vayuloksubcheck.js` + `tools/browser/README.md`. Nothing under `src/`.

---

## Findings from the browser, before any fix is described

### TASK 3 — the real defect of the location search

Measured by rendering `file:///projects/sandbox/wecare-digital/docs/mocks/vayulok-live-mock.html`
in headless Chromium through the repo harness's own `lib/browser.js` (`launch` + `gotoStable`),
at 1280x900 and 390x844, clicking `#vl-search` and typing `Mum` with a 60ms key delay, then
pressing ArrowDown and Enter. Identical results at both widths.

**The field is inert decoration. There is no results UI, no handler and no dataset — nothing to
populate and nothing to hide.** Not a container that fails to fill, not a binding that never
fires, not something clipped at a particular width. Evidence:

| Probe | Result |
|---|---|
| `#vl-search` exists, accepts text | yes — `input.value` became `"Mum"`, `document.activeElement.id === 'vl-search'` |
| `.vl-search-field` box | 52px tall, 10px radius, `1px rgb(229,231,235)` — the ROLE 3 contract, correct |
| `[role=listbox], [role=option]` in the document | **0**, before typing and after |
| `<datalist>` elements | **0**; `list` attribute on the input is `null` |
| `[class*=result], [class*=suggest], [class*=option], [class*=menu], [class*=dropdown]` | **0**, before and after |
| children of `.vl-search` | exactly one: `DIV.vl-search-field` |
| CSS rules whose selector mentions `vl-search` | exactly 5: `.vl-search`, `.vl-search-field`, `.vl-search-field:focus-within`, `.vl-search-input`, `.vl-search-input::placeholder` — **no results-surface rule exists** |
| `<script>` elements in the document | 1; `script.textContent.indexOf('vl-search') === -1` — **the id appears nowhere in the inline JS, so no handler is bound** |
| `MutationObserver` on `document.body` (`childList`+`subtree`+`attributes`+`characterData`) across typing `Mum`, ArrowDown, Enter | **0 mutation records** |
| element count under `.vl-vayulok` | 473 before → 473 after |
| `.vl-place` / `.vl-place-addr` after ArrowDown+Enter | still `Connaught Place` / `New Delhi, Delhi 110001`; `window.scrollY` 0 |
| combobox attributes on the input (`role`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, `aria-autocomplete`, `autocomplete`) | all `null` |
| console errors / page errors / requests | 0 / 0 / 1 (the document itself) |

Zero console errors with zero mutations rules out a crashing or throwing handler; 1 request rules
out a failed fetch; identical behaviour at 390 and 1280 rules out clipping. A screenshot taken
with `Mum` in the field shows the field, then whitespace, then the `Connaught Place` heading —
nothing renders below the field at all. The mock's own script header states its scope outright:
"Four things and nothing else: the tabs, the map layer toggle, the runtime key gate, and the
subscribe field's calling-code segment plus its inline submit." Search was never built.

**So TASK 3 is new work, not a repair:** add a results surface, a handler, and an inline dataset.

### TASK 2 — the shared action shape already exists

Measured in the same run. All three ROLE 1 buttons already share one geometry, and the Contribute
button is one of them:

| Control | height | radius | font | padding | fill | border |
|---|---|---|---|---|---|---|
| `#vl-sub-btn` (Subscribe, being deleted) | 52 | 13px | 16px/500 | 24/24 | `rgb(209,244,112)` | 2px `rgb(26,58,42)` |
| `.vl-bc-submit-wrap .vl-btn` (Contribute) | 52 | 13px | 16px/500 | 24/24 | `rgb(209,244,112)` | 2px `rgb(26,58,42)` |
| `#vl-keyload` (Load) | 52 | 13px | 16px/500 | 24/24 | `rgb(209,244,112)` | 2px `rgb(26,58,42)` |
| `.vl-bc-choice-face` (amount chip, ROLE 4 — not to be touched) | 40 | 999px | 15px/700 | 16/16 | `rgb(255,255,255)` | 2px `rgb(229,231,235)` |

**Decision: the shared action-button class is the existing `.vl-btn`, defined in exactly ONE rule
block at `docs/mocks/vayulok-live-mock.html:215-224`** (the ROLE 1 rule, `min-height:52px;
padding:0 24px; border-radius:var(--r-btn); font-size:16px; font-weight:500; background:var(--lime);
color:var(--green); border:2px solid var(--green)`), with `:hover`, `:active` and `:focus-visible`
in the three rules beneath it. The new WhatsApp anchor takes that class; nothing is duplicated;
the shape stays switchable in one edit. Reported values above are its current computed values.

**The on-hold `src/styles/button.css` contract, for the record only — do NOT apply it.** That file
gives `.btn{border-radius:13px;font-weight:500;line-height:1}` + `.btn-lg{height:52px;padding:0 24px;
font-size:16px}` + `.btn-primary{background:#d1f470;color:#1a3a2a;border:2px solid #1a3a2a}` —
i.e. **identical to what `.vl-btn` renders today**. Under that contract the shared class would
become `border-radius:13px / height:52px / font-size:16px / font-weight:500`: **no change at all**.
The "13px / 52px / 16px / weight 500" in the earlier brief is the radius, the height, the font size
and the weight respectively — 13px is the radius, never the type size. `.btn-sm` is where 13px type
lives and it is 36px tall, a different role. Nothing to shrink.

Chip amounts: the owner's screenshot was described as ₹200/₹400/₹600/Other with ₹200 selected; the
file actually renders ₹99/₹249/₹499/Other with ₹249 checked (`vayulok-live-mock.html:1356-1369`).
Out of scope this pass — do not change the amounts or the chips. Flag it in the report.

### Left-column control audit (TASK 2's closing requirement)

After this change every row in `.vl-app-left` is single-role by construction:

| Row | Members | Role |
|---|---|---|
| search block | `.vl-search-field` only | ROLE 3 box (52/10px/1px #e5e7eb) |
| search results (new) | `.vl-search-option` rows only | ROLE 7 (new, see item 5) |
| subscribe panel | the WhatsApp anchor only | ROLE 1 |
| contribute amounts | four `.vl-bc-choice-face` | ROLE 4 |
| contribute submit | `Contribute` only | ROLE 1 |
| air/weather tabs | two `.vl-tab` | ROLE 6 |

### Environment facts discovered (affect verification)

- `npm` is not on `PATH`; it lives at `$HOME/.nvm/versions/node/v24.21.0/bin/npm`. `node` (v22.23.3)
  **is** on `PATH`.
- `tools/browser/node_modules` is already populated (`playwright-core` present) and Chromium
  resolves from `/opt/playwright/chromium-1232`. `npm install --prefix tools/browser` is therefore
  a no-op re-check, not a prerequisite — the harness runs today.
- The app's root `node_modules` is **absent**, so `npm run lint`, `npm run typecheck`, `npm test`
  and `npm run build` cannot run here (`eslint.config.mjs` fails with
  `Cannot find package 'eslint-config-next'`). Those suites provably do not cover `docs/mocks`
  anyway. Use `node --check` for harness syntax and the harness itself for behaviour.
- Baseline: `node tools/browser/vayuloksubcheck.js` → **268/268 assertions passed, exit 0**.
- `diff` and `cmp` are unavailable; use `git hash-object` for all equality proofs.
- Current `grep -c 'rel="stylesheet"\|<link \|src="http\|href="http'` on each mock = **0**.
- A stale `.agents/tasks/vayulok-subscribe-inline-plan.md` (35 KB, describes a "Contribute
  restyle") and `.agents/tasks/vayulok-review.{md,json}` exist. Ignore all three; this file
  supersedes them.

---

## Implementation Plan

- [ ] 1. Record the pre-change baseline so every later number has something to move against.
      Run the suite and capture: the assertion count (expect 268/268, exit 0), and the twin +
      PNG-pair hashes. `node tools/browser/vayuloksubcheck.js --json > /dev/null` first if you
      want machine-readable output. Also save the pristine original for item 7's negative check:
      `mkdir -p .scratch && git show HEAD:docs/mocks/vayulok-live-mock.html > .scratch/vayulok-orig.html`
      (`.scratch/` is gitignored and ESLint-ignored by design).
      Files: none modified.
      Verify: `node tools/browser/vayuloksubcheck.js` prints `268/268 assertions passed` and exits 0;
      `git hash-object docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html` prints
      `dbdb2b83aad787d45e814151787f12931c5f5a56` twice.

- [ ] 2. Harness, removals ONLY — strip every assertion that covers the form about to be deleted,
      so the suite stays green across the HTML change rather than failing through it. Delete from
      `tools/browser/vayuloksubcheck.js`, keeping its heavy-comment house style and recording the
      deletion reason where the file already records retirements:
      • `ROLE1_BUTTONS`: remove the `[ 'Subscribe', '#vl-sub-btn' ]` entry (leaves `Load` +
        `Contribute`; the anchor is re-added in item 4) — drops 5 per-scope assertions.
      • block (b): `Subscribe bottom meets field bottom (<=1px)` / `Subscribe wrapped to its own
        row (390 layout)`, `.vl-sub-action declares no min-height length`, `.vl-sub-action holds
        exactly one control`, and the `btn`/`action` probes that feed them — 3.
      • block (c) in full: `.vl-pf height 52`, `.vl-pf radius 10px`, `.vl-pf border 1px #e5e7eb`,
        and all eight `segs` assertions (`calling code defaults to +91`, `both segments fill the
        container content box`, `segments share one row`, `code segment carries only the divider
        border`, `number segment carries no border`, `number placeholder is not clipped`,
        `no required/pattern/minlength on either segment`, `aria-required carries the semantic
        instead`) plus the `divided phone field exists` else-branch — 11.
      • block (f) interactions: `empty submit reports inline`, `empty submit marks the number
        invalid`, `empty submit does not flip the button label`, `typing 971 commits +971`,
        `+971 updates the length hint`, `unsupported code is aria-invalid`, `blur reverts to the
        last committed code`, `valid submit composes E.164 inline`, `valid submit flips the label
        to Subscribed`, `valid submit marks the status done`, `valid submit clears aria-invalid`,
        `no element was added to the subscribe panel`, and the `htmlBefore`/`htmlAfter` probes — 12.
      KEEP `NO dialog fired during any interaction`, the whole of (d)/(e)/(g), and leave the
      `the only "+" is the calling-code control value` assertion untouched for now (it still
      passes against the unchanged HTML; it is repointed in item 4).
      Files: tools/browser/vayuloksubcheck.js
      Verify: `node --check tools/browser/vayuloksubcheck.js`, then
      `node tools/browser/vayuloksubcheck.js` → exit 0 with **144/144** (31 removed per scope x 4
      scopes = 124 off 268). If the count is not 144, something extra was removed or kept — fix
      before moving on.

- [ ] 3. TASK 1 + TASK 2 in the HTML: delete the inline subscribe form, put the WhatsApp anchor in
      its place on the shared `.vl-btn` class, and remove every selector and function that becomes
      dead. Edit `docs/mocks/vayulok-live-mock.html` only, then copy over the twin.
      **Markup (lines ~1259-1341)** — inside `<section class="vl-section"
      aria-labelledby="vl-sub-title">` / `<div class="vl-subscribe">` keep the `.vl-sub-head` block
      verbatim (the `VayuLok alerts` eyebrow, the `Get air-quality alerts for your place` heading,
      the `Pick the places you want watched.` line) and keep the closing `.vl-placeholder`. Delete
      everything between them: the whole `<form class="vl-sub-fields vl-sub-fields-single"
      id="vl-sub-form">` including `<label for="vl-sub-phone">WhatsApp number</label>`, the
      `<div class="vl-pf" id="vl-pf">` with `#vl-sub-dial` and `#vl-sub-phone`, the
      `<div class="vl-sub-action">` wrapper and `<button class="vl-btn" id="vl-sub-btn">`, and the
      `<p class="vl-sub-status" id="vl-sub-status" role="status">`. In their place put ONE anchor as
      a direct child of `.vl-subscribe` (no wrapper — a one-control row cannot drift):
      `<a class="vl-btn" id="vl-sub-wa" href="https://wa.me/message/BEA3HNW3LNM3A1" target="_blank" rel="noopener noreferrer">Subscribe on WhatsApp</a>`.
      Label decided: **`Subscribe on WhatsApp`** — names the destination and the action, and at
      16px/500 inside 24px padding it measures ~215px against the ~326px panel interior at 390px,
      so it cannot wrap (`.vl-btn` also sets `white-space:nowrap`). No new copy is invented.
      **CSS** — add `text-decoration:none;` to the single `.vl-btn` rule (~line 215): required
      because an `<a>` is underlined by the UA and a `<button>` is not, it changes nothing about how
      Contribute or Load render (their computed `text-decoration-line` is already `none`), and it
      keeps ONE rule governing both controls. Do not add a second class, a second rule, or any
      `#vl-sub-wa` declaration. Then delete, with every occurrence checked (the file has a history
      of a selector declared twice in disjoint blocks — grep each name):
      `.vl-sub-fields` (858), `.vl-sub-fields-single` (505), `.vl-sub-fields-single .vl-cell-wide`
      (506), `.vl-sub-action` (507), `.vl-cell` (859), `.vl-cell-wide` (860),
      `.vl-cell>span,.vl-cell>label` (867), `.vl-sub-status` (875), `.vl-sub-status.is-done` (876),
      and the entire ROLE 3 divided-form group `.vl-pf` (328), `.vl-pf-code` (342),
      `.vl-pf-code::-webkit-search-cancel-button` (357), `.vl-pf-num` (361),
      `.vl-pf-code:focus-visible, .vl-pf-num:focus-visible` (375-376), `.vl-pf:focus-within` (382)
      and the `@media(max-width:360px)` block at 385-388. Confirmed safe: `.vl-cell*` and `.vl-pf*`
      have no other users (`.vl-keyfield` serves the key gate), and `.vl-input` MUST STAY — the key
      gate uses it at line 1435. Keep `.vl-subscribe`, `.vl-sub-head*`, `.vl-sub-title`,
      `.vl-placeholder` and the `@media(max-width:767px)` `.vl-sub-head` / `.vl-subscribe` rules.
      **Inline JS** — delete `VL_DIAL_CODES` (1773), `VL_DEFAULT_DIAL` (1801), `vlNormaliseDial`
      (1804), `vlFindDial` (1810), `vlLengthHint` (1818), `vlValidLength` (1831) and the whole
      `( function phoneField () { ... } )()` IIFE (1839 to its close), plus the long
      DialCodeSearch/dialCodes.ts porting comment above them. Update the script's header comment
      from "Four things" to the three that remain (tabs, layer toggle, key gate) — item 5 adds the
      fourth back as the place search.
      **Comments/role table** — ROLE 3's table line 198 becomes
      `ROLE 3  text input  .vl-input, .vl-search-field  52px / 10px / 1px #e5e7eb` (the search
      field measures that box and was never listed; the left-column audit says list it). Trim ROLE
      3's prose to the single `.vl-input` form and replace the divided-form essay with a short
      retirement note in the file's own voice: the divided field went with the inline form when
      subscribing moved to WhatsApp, PhoneField.tsx remains its source if it is ever needed again.
      Rewrite the "SUBSCRIBE, WHATSAPP ONLY, AND NOW ONE STEP" comment block (477-507) to describe
      what the panel now is: one framing head and one ROLE 1 anchor, no fields, no status line —
      and keep its recorded history of the `min-height:91px` duplicate-rule defect, since that is
      the hazard note that stops it coming back.
      Then: `cp docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html`.
      Files: docs/mocks/vayulok-live-mock.html, docs/mocks/vayulok-final-v3.html
      Verify: `node tools/browser/vayuloksubcheck.js` → exit 0, still 144/144, with `zero console
      errors`, `zero page errors`, `exactly 1 request (the document)` and `no horizontal overflow`
      green at both widths. Then `node tools/browser/vayuloksubcheck.js --shots` and **open**
      `docs/mocks/vayulok-section-subscribe.png` and `docs/mocks/vayulok-live-mock-390.png` and
      look: the lime-tinted panel must show eyebrow, heading, the one-line copy, the
      `Subscribe on WhatsApp` pill in Contribute's exact shape, then the PLACEHOLDER note — no
      field, no status line, and no collapsed or doubled gap. If the gap reads wrong, fix spacing
      with the existing `.vl-sub-head{margin-bottom:20px}` / `.vl-placeholder{margin:20px 0 0}`
      rhythm; do not add copy.

- [ ] 4. Harness, additions for TASK 1 + TASK 2 — prove the deletion, the anchor and the shape
      parity. In `tools/browser/vayuloksubcheck.js`:
      • Re-add the anchor to `ROLE1_BUTTONS` as `[ 'Subscribe on WhatsApp', '#vl-sub-wa' ]` so it
        rejoins the five per-button ROLE 1 assertions and both cross-button ones (`share one
        height`, `share one font`).
      • Deletion proofs (one `page.evaluate` returning counts): `0` elements for each of
        `#vl-sub-form`, `#vl-sub-btn`, `#vl-sub-dial`, `#vl-sub-phone`, `#vl-pf`, `.vl-sub-status`,
        `.vl-sub-action`, `.vl-cell`, `.vl-sub-fields`; `0` for
        `.vl-subscribe form, .vl-subscribe input, .vl-subscribe button`; `0` CSS rules whose
        `selectorText` contains `vl-pf`, `vl-cell`, `vl-sub-fields`, `vl-sub-action` or
        `vl-sub-status` (extend the existing `quietRules` sweep, which already walks
        `document.styleSheets`); and `0` hits for `VL_DIAL_CODES`, `vlFindDial`, `vlLengthHint`,
        `vlValidLength`, `vlNormaliseDial` and `DialCodeSearch` in the concatenated
        `textContent` of every `<script>` in the document.
      • The anchor: exists; `tagName === 'A'`; `getAttribute('href')` **exactly**
        `https://wa.me/message/BEA3HNW3LNM3A1`; `target === '_blank'`; `rel` contains both
        `noopener` and `noreferrer`; visible text contains `WhatsApp`; `getClientRects().length === 1`
        and computed height 52 at BOTH widths (proves no wrap); `computedStyle.textDecorationLine
        === 'none'`; focusable (`page.focus('#vl-sub-wa')` then
        `document.activeElement.id === 'vl-sub-wa'`). **Never click it** — `target=_blank` would
        open a popup and a real navigation; href/target/rel plus focus is the whole claim.
      • Parity, asserted pairwise against the Contribute button rather than against a table:
        height, `borderTopLeftRadius`, `fontSize`, `fontWeight`, `backgroundColor`,
        `borderTopWidth`, `borderTopColor` and `paddingLeft/paddingRight` of `#vl-sub-wa` each
        EQUAL `.vl-bc-submit-wrap .vl-btn`'s — 8 assertions, one per property, so a failure names
        the property.
      • Shared-class proof: both controls' `classList` contain `vl-btn`, and the number of CSS
        rules whose `selectorText` is exactly `.vl-btn` is **1** — this is the guard against the
        file's historical "declared twice in disjoint blocks" defect.
      • Single-role row: `.vl-subscribe` contains exactly one element matching
        `a, button, input, select, textarea`, and it is `#vl-sub-wa`.
      • Repoint the `+` assertion: rename it `no "+" survives in the section` and require BOTH
        `plusText` and `plusAttr` to be empty — the calling-code control that was the only
        legitimate `+` is gone, and the wa.me href contains none.
      • Remote-reference proofs (the adjusted zero-network grep, done in the DOM):
        `document.querySelectorAll('link').length === 0`; no element has a `src` starting `http`;
        and **exactly one** attribute anywhere under `.vl-vayulok` has a value starting `http`,
        namely `#vl-sub-wa[href]` with the exact wa.me URL. Keep (g)'s request-count assertion as
        the primary zero-network signal.
      Files: tools/browser/vayuloksubcheck.js
      Verify: `node --check` then `node tools/browser/vayuloksubcheck.js` → exit 0 with the count
      risen from 144 (expect ~270-280; record the exact number). Every new assertion must read
      `ok`, including at 390.

- [ ] 5. TASK 3 in the HTML: build the location search — results surface, keyboard model, and the
      inline dataset. Edit the live mock, copy to the twin.
      **Decisions, with reasons.** (i) Follow the shipped combobox pattern in
      `src/components/SearchModal.tsx:145-240` — `role="combobox"` + `aria-expanded` +
      `aria-controls` + `aria-activedescendant` on the input, a `role="listbox"` container,
      `role="option"` rows with `aria-selected`, ArrowDown/ArrowUp **clamped** (`Math.min` /
      `Math.max`, no wrap), Enter commits the active row, Escape closes, and `mouseenter` moves the
      active row. That is the repo's own interaction model and the mock's head comment at ~line 302
      already cites a search-style field to the shipped PhoneField/DialCodeSearch pair; the
      SearchModal pattern is the one of the two that actually has a results list. (ii) The list is
      **absolutely positioned** below the field, not in flow, so opening it cannot shift the
      column — `.vl-app-left` carries `container-type:inline-size`, whose layout containment makes
      it the containing block and a stacking context, so the overlay cannot escape the left column
      or collide with the sticky map. (iii) **No resting shadow** — the file's token comment states
      the site has one shadow and it is a hover shadow. A 1px `--hair` border on `--paper` is the
      device, exactly as `.vl-map-legend` and `.vl-map-preview` do it. (iv) **Cap matches at 6** so
      the list never needs a scroll container inside an overlay. (v) Selecting a place updates the
      place NAME and ADDRESS only — `.vl-place`, `.vl-place-addr` and the map preview's
      `.vl-card-h` / `.vl-small` — and leaves every AQI/weather figure untouched: the mock's own
      disclosure line says every air and weather value is static placeholder data, and inventing
      per-city readings would contradict it.
      **CSS** (add beside the existing SEARCH block at ~532-546, using only existing tokens):
      add `position:relative` to `.vl-search`; then
      `.vl-search-results{position:absolute;top:calc(100% + 6px);inset-inline:0;z-index:5;margin:0;padding:0;list-style:none;overflow:hidden;border:1px solid var(--hair);border-radius:var(--r-field);background:var(--paper)}`,
      `.vl-search-results[hidden]{display:none}`,
      `.vl-search-option{display:block;min-height:52px;padding:10px 14px;cursor:pointer}`,
      `.vl-search-option + .vl-search-option{border-top:1px solid var(--hair)}`,
      `.vl-search-option[aria-selected="true"]{background:var(--lime)}`,
      `.vl-search-option-name{display:block;font-size:16px;font-weight:600;line-height:1.3;color:var(--ink-strong)}`,
      `.vl-search-option-addr{display:block;margin-top:2px;font-size:13px;line-height:1.4;color:var(--ink-muted)}`,
      `.vl-search-empty{margin:0;padding:14px;font-size:13px;line-height:1.45;color:var(--ink-muted)}`.
      No new radius, no new colour, no new type size: 10px is `--r-field`, the rows are flush
      hairline rows like `.vl-signal + .vl-signal`, the active fill is the same lime punctuation as
      `.vl-layer[aria-pressed="true"]` and the active tab (`#1a3a2a` on `#d1f470` measures 11.85:1
      per the harness README), and `overflow:hidden` keeps the first/last row's fill inside the
      10px corners for the same reason `.vl-pf` needed it.
      **Role table** — this is a seventh shape, and the roles block's standing instruction is "If
      you add a seventh shape, add a seventh role." Add
      `ROLE 7  result option  .vl-search-option  <measured>px / no radius / 16px-600 + 13px / hairline rows / lime active fill`
      with the height MEASURED in Chromium written in, and a note that it is a listbox row rather
      than a control in a row, so it shares a role with nothing else.
      **Markup** (~1027-1041): leave the `<label class="vl-label" for="vl-search">` and the SVG
      icon alone. On the input add `role="combobox"`, `aria-controls="vl-search-results"`,
      `aria-expanded="false"`, `aria-autocomplete="list"`, `autocomplete="off"`, `autocorrect="off"`,
      `spellcheck="false"`. After `.vl-search-field`, inside `.vl-search`, add
      `<ul class="vl-search-results" id="vl-search-results" role="listbox" aria-label="Matching places" hidden></ul>`.
      Add no constraint attributes (`required`/`pattern`/`minlength`) — the native validation bubble
      was the owner's original reported defect and the file records that decision.
      **Inline JS** — add one `( function placeSearch () { ... } )()` IIFE where the deleted
      `phoneField` one was, inside the existing single `<script>`, in the same ES5 style
      (`var`, `function`, no template literals, no arrow functions) with a comment recording that
      the dataset is sample data for a zero-network mock and that no geocoding API is called:
      `var VL_PLACES = [ [ 'Connaught Place', 'New Delhi, Delhi 110001' ], [ 'Bandra West', 'Mumbai, Maharashtra 400050' ], [ 'Andheri East', 'Mumbai, Maharashtra 400069' ], [ 'Koramangala', 'Bengaluru, Karnataka 560034' ], [ 'Whitefield', 'Bengaluru, Karnataka 560066' ], [ 'T. Nagar', 'Chennai, Tamil Nadu 600017' ], [ 'Salt Lake City', 'Kolkata, West Bengal 700064' ], [ 'Banjara Hills', 'Hyderabad, Telangana 500034' ], [ 'Shivajinagar', 'Pune, Maharashtra 411005' ], [ 'Navrangpura', 'Ahmedabad, Gujarat 380009' ], [ 'C-Scheme', 'Jaipur, Rajasthan 302001' ], [ 'Gomti Nagar', 'Lucknow, Uttar Pradesh 226010' ], [ 'Sector 17', 'Chandigarh 160017' ], [ 'Panampilly Nagar', 'Kochi, Kerala 682036' ] ];`
      Behaviour: `input` → case-insensitive substring match over name AND address, first 6 matches,
      rebuild the list with `document.createElement` + `textContent` only (never `innerHTML` with
      data — the key gate's own style), set `aria-expanded="true"`, remove `hidden`, set the active
      index to 0 and mirror it into `aria-activedescendant` (`vl-search-option-<i>`) and
      `aria-selected`; an empty query closes the list; a query with no matches shows one
      `<p class="vl-search-empty">No matching places in this mock's sample list.</p>` which carries
      NO `role="option"` and is not selectable. `keydown`: ArrowDown/ArrowUp clamp and
      `preventDefault`; Enter commits and `preventDefault`s; Escape closes and leaves the typed
      text; Tab closes. `mouseenter`/`mousemove` on a row sets the active index; `click` commits.
      Hazard to handle explicitly: bind `mousedown` on the list with `preventDefault()` so the
      field does not blur before the click lands, and close on `focusout` of `.vl-search` only
      when focus leaves the whole wrapper. Commit writes the name into the input and into
      `.vl-place` + `.vl-map-preview .vl-card-h`, the address into `.vl-place-addr` +
      `.vl-map-preview .vl-small`, then closes the list and sets `aria-expanded="false"`. No fetch,
      no timers, no storage, no Google Maps call — the `.vl-keygate` gate stays exactly as it is.
      Then `cp docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html`.
      Files: docs/mocks/vayulok-live-mock.html, docs/mocks/vayulok-final-v3.html
      Verify: `node tools/browser/vayuloksubcheck.js` → exit 0 at the item-4 count, with
      `zero console errors`, `zero page errors`, `exactly 1 request (the document)`,
      `zero non-file:// requests` and `no horizontal overflow` all green at 1280 and 390 (the
      search is not asserted yet — item 6 does that; this run proves nothing regressed and the new
      script does not throw).

- [ ] 6. Harness, search assertions — make the fix execution-verified. Add a block (h) to
      `tools/browser/vayuloksubcheck.js`, run at BOTH viewports, after the existing interaction
      block:
      1. rest state: `#vl-search` has `role=combobox`, `aria-controls=vl-search-results`,
         `aria-autocomplete=list`, `aria-expanded=false`; `#vl-search-results` exists with
         `role=listbox` and is not rendered (`getClientRects().length === 0`).
      2. `page.click('#vl-search')` + `page.type('#vl-search','mumbai',{delay:30})` →
         `aria-expanded=true`, `[role=option]` count is 2, every option's address text matches
         `/Mumbai/i`, and the list's rect has height > 0, `right <= documentElement.clientWidth`
         and `bottom > 0` (it is on screen, not clipped — the README's "treat could-not-tell as a
         failure" rule).
      3. ROLE 7 geometry: all option heights identical and >= 44 (the repo's chosen AAA 2.5.5 bar,
         per the harness README's target-size section), list `borderTopLeftRadius === '10px'` and
         `borderTopWidth/borderTopColor === '1px' / 'rgb(229, 231, 235)'`.
      4. active state is visible: option 0 has `aria-selected=true` and a `backgroundColor`
         different from option 1's; `aria-activedescendant` equals option 0's id.
      5. ArrowDown → `aria-activedescendant` and `aria-selected` move to option 1, and option 1's
         background is now the lime one. ArrowUp returns to option 0; a further ArrowUp clamps
         (stays at 0).
      6. capture the active option's name and address, press Enter → list closed
         (`aria-expanded=false`, zero client rects), `#vl-search.value` equals the captured name,
         and `.vl-place`, `.vl-place-addr`, `.vl-map-preview .vl-card-h`, `.vl-map-preview .vl-small`
         all equal the captured values. Compare against the captured strings, never against a
         hardcoded city, so the assertion survives a dataset edit.
      7. Escape: clear the field, type `beng`, confirm the list is open, press Escape → closed,
         `aria-expanded=false`, and `.vl-place` is unchanged from step 6's selection.
      8. no-match: type `zzzz` → zero `[role=option]`, exactly one `.vl-search-empty`, and the
         empty line carries no `role` attribute.
      9. mouse path: type `kochi`, click option 0 → the page updates the same four nodes.
      10. after all of the above, `document.documentElement.scrollWidth ===
          document.documentElement.clientWidth` (re-asserted at 390 with the list open) and the
          request count is STILL 1 — searching touches no network.
      Also update the file's header docblock: the three defects it was built for, plus what it now
      covers (the WhatsApp replacement, the shared ROLE 1 shape, and the search that had no
      implementation at all — cite the measured evidence in one line).
      Files: tools/browser/vayuloksubcheck.js
      Verify: `node --check`, then `node tools/browser/vayuloksubcheck.js` → exit 0, count risen
      again (expect roughly 320-340; record the exact number). Then prove the new assertions
      measure something rather than passing vacuously:
      `node tools/browser/vayuloksubcheck.js .scratch/vayulok-orig.html` must **fail** (non-zero
      exit) on the block (h) assertions and on the anchor/deletion assertions. Record which ones
      failed; that is the negative control for the whole change.

- [ ] 7. Harness, screenshots — repoint the `-scrolled` anchor at the open results list. In
      `SHOTS.anchors`, keep `vayulok-section-desktop.png` (top of page) and
      `vayulok-section-subscribe.png` (`scrollTo: '.vl-subscribe'`, which now frames the WhatsApp
      button), and change `vayulok-section-scrolled.png` from `scrollTo: '.vl-hours'` to the search
      state: add optional `focus`/`type` fields to the anchor descriptor and have `shoot()` scroll
      `.vl-search` into view, click `#vl-search`, type a query that matches more than one row
      (`mumbai` or `beng`), press ArrowDown so the active row is visibly lime, wait ~250ms, then
      screenshot. Update the `SHOTS` docblock to record that `-scrolled` now shows the search
      results list open and why (the brief requires one image that shows it; the 24-hour rail is
      already visible in the full-page PNGs).
      Files: tools/browser/vayuloksubcheck.js
      Verify: `node tools/browser/vayuloksubcheck.js --shots` exits 0 and prints the six written
      paths.

- [ ] 8. Regenerate every companion PNG, overwriting, and actually look at them.
      `node tools/browser/vayuloksubcheck.js --shots` writes
      `docs/mocks/vayulok-live-mock-1280.png`, `docs/mocks/vayulok-final-v3-1280.png`,
      `docs/mocks/vayulok-live-mock-390.png`, `docs/mocks/vayulok-final-v3-390.png` (full page,
      1280 and 390) and the three 1440x950 anchors
      `docs/mocks/vayulok-section-desktop.png`, `-scrolled`, `-subscribe`.
      Open each of the 1280 and 390 full-page images and both changed anchors and confirm by eye:
      the subscribe panel shows the `Subscribe on WhatsApp` pill and no field or status line; that
      pill is visually indistinguishable in shape from the Contribute pill below it; the amount
      chips are unchanged; the results list in `-scrolled` is open, legible, inside the column, not
      overlapping the map, with one row clearly lime-active; and at 390 nothing overflows and the
      button does not wrap.
      Files: the six PNGs under docs/mocks/
      Verify: suite exits 0; then
      `git hash-object docs/mocks/vayulok-live-mock-1280.png docs/mocks/vayulok-final-v3-1280.png`
      prints one hash twice, and the same for the `-390` pair.

- [ ] 9. Prove the twin and the zero-network constraint.
      Files: none modified.
      Verify: (a)
      `git hash-object docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html` prints
      the SAME hash twice (if not, re-copy and re-run items 8-9);
      (b) `grep -c 'rel="stylesheet"\|<link \|src="http\|href="http' docs/mocks/vayulok-live-mock.html`
      prints **1**, and `grep -n 'src="http\|href="http\|<link \|rel="stylesheet"'` shows that the
      single hit is the `#vl-sub-wa` anchor's `href="https://wa.me/message/BEA3HNW3LNM3A1"` —
      the one user-initiated navigation target the brief allows; same two commands on the twin;
      (c) the suite's `exactly 1 request (the document)` / `zero non-file:// requests` assertions
      are green at both widths in the final run.

- [ ] 10. Documentation and the report.
      Add a row for `vayuloksubcheck.js` to the "Current state" table in
      `tools/browser/README.md` with the final assertion count and the measurement date, and one
      short paragraph in the same house style recording the one finding that is worth keeping: the
      location search had **no implementation at all** — no results container, no handler, no
      dataset, zero MutationObserver records while typing — so every other check in the repo
      passed while a visible control did nothing, which is the same class of gap the file's own
      preamble describes.
      In the step report, state: the shared class is `.vl-btn` and the one rule block defining the
      shape is at `docs/mocks/vayulok-live-mock.html:215-224` (`min-height:52px`, `padding:0 24px`,
      `border-radius:var(--r-btn)`=13px, `font-size:16px`, `font-weight:500`,
      `background:var(--lime)`=#d1f470, `border:2px solid var(--green)`=#1a3a2a,
      `text-decoration:none`); under the on-hold `src/styles/button.css` contract those values
      would be unchanged (13px is the radius, 16px the type). **FLAG, do not fix:** (i) the
      `.vl-placeholder` consent/purpose-of-use block in the subscribe panel now sits under a panel
      that collects nothing — consent moves into the WhatsApp conversation, so the placeholder may
      no longer belong there; it is left exactly as-is pending the owner's words. (ii) The
      `Pick the places you want watched.` head line is left untouched per the brief. (iii) The
      Contribute amounts in the file are ₹99/₹249/₹499/Other with ₹249 selected, not the
      ₹200/₹400/₹600 the reference screenshot was described as — untouched this pass.
      (iv) The results dataset is sample data for a mock, not geocoding.
      Files: tools/browser/README.md
      Verify: `node tools/browser/vayuloksubcheck.js` final clean run, exit 0, count recorded in
      both the README row and the report.

- [ ] 11. Commit and push on the current branch only.
      `git branch --show-current` must print `fix/vayulok-subscribe-inline` before anything else.
      Stage by name: the two mock HTML files, the six PNGs, `tools/browser/vayuloksubcheck.js`,
      `tools/browser/README.md`, and `.agents/tasks/vayulok-subscribe-inline/plan.md`. Leave the
      untracked `.agents/tasks/vayulok-review.{md,json}` and the stale
      `.agents/tasks/vayulok-subscribe-inline-plan.md` alone, and delete `.scratch/vayulok-orig.html`
      (it is gitignored, so it cannot be committed, but remove it anyway). One commit, message
      naming what and why: the inline subscribe form replaced by the WhatsApp deep link on the
      shared ROLE 1 shape, and a location search that previously had no implementation.
      Then `git push origin fix/vayulok-subscribe-inline` — plain, no `-u`. No pull request.
      Files: git index only.
      Verify: `git status --short` shows no modified tracked files left; `git log --oneline -1`
      shows the new commit on `fix/vayulok-subscribe-inline`;
      `git rev-parse HEAD origin/fix/vayulok-subscribe-inline` prints the same SHA twice.

---

## Assumptions

1. The lime-tinted `.vl-subscribe` framing and its three copy strings survive the form's removal —
   the panel still reads as a complete block (eyebrow, heading, one-line copy, one action,
   placeholder note). If the browser shows otherwise after item 3, fix spacing within the existing
   `margin` rhythm; do not write new copy.
2. `Subscribe on WhatsApp` is the label. It is a destination plus a verb rather than product copy,
   and the brief offered it as the example.
3. The dataset's place, city and state names are real geography; its PIN codes are plausible and
   fall under the page's own standing disclosure that every value in the mock is placeholder data.
4. Selecting a place updates the place name and address only. Metrics stay put, because fabricating
   per-city AQI readings would contradict the mock's disclosure line.
5. `npm run lint` / `typecheck` / `test` / `build` cannot run in this sandbox (app `node_modules`
   absent) and provably do not cover `docs/mocks`. `node --check` plus the browser harness is the
   verification contract for this change.
