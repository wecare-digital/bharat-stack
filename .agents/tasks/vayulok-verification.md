# Verification evidence — VayuLok subscribe block (fix/vayulok-subscribe-inline)

Everything below was **executed**, not inferred from reading the HTML. Numbers are computed
styles and `getBoundingClientRect` values from headless Chromium against a `file://` URL.
Re-run it all with one command:

```bash
cd /projects/sandbox/wecare-digital
npm install --prefix tools/browser --no-audit --no-fund   # once per sandbox
node tools/browser/vayuloksubcheck.js                     # 268/268, exit 0
```

**Result: 268/268 assertions passed, exit 0**, across four scopes —
`vayulok-live-mock.html @1280`, `@390`, `vayulok-final-v3.html @1280`, `@390`.
Viewports 1280x900 and 390x844.

---

## 1. The baseline, measured BEFORE any edit

Recorded so the fixes are demonstrably fixes and not restatements. All values from the
committed HTML at `2d6ca401`.

| Control | Selector | Height | Font | Radius | Border | Padding |
|---|---|---|---|---|---|---|
| Load | `#vl-keyload` | 52 | 16px/500 | 13px | 2px `rgb(26,58,42)` | 24/24 |
| Subscribe | `.vl-sub-action .vl-btn` | 52 | 16px/500 | 13px | 2px `rgb(26,58,42)` | 24/24 |
| Contribute | `.vl-bc-submit-wrap .vl-btn` | 52 | 16px/500 | 13px | 2px `rgb(26,58,42)` | 24/24 |
| **Send code** | `.vl-sub-action .vl-btn-quiet` | **32** | **12px/700** | **999px** | **1px** | **12/12** |
| **Clear key** | `#vl-keyclear` | **32** | **12px/700** | **999px** | 1px | **12/12** |
| AQI | `#vl-layer-aqi` | 38 | 13px/700 | 999px | 1px | 16/16 |
| PM2.5 | `#vl-layer-pm` | 38 | 13px/700 | 999px | 1px | 16/16 |
| Air / Weather | `.vl-tab` | 40 | 15px/700 | 999px | 0 | 22/22 |
| amount chip | `.vl-bc-choice-face` | 40 | 15px/700 | 999px | 2px | 16/16 |
| phone input | `.vl-subscribe .vl-input` | 52 | 16px/400 | 10px | 1px `rgb(229,231,235)` | 14/14 |

Other baseline facts, all measured:

- `.vl-sub-action` computed `min-height: 91px`, rendered height **91**, while `.vl-cell` was
  **76**. `Subscribe.bottom - input.bottom = **-19.5px**` at 1280 — the button finished 19.5px
  **above** the field it belongs to.
- `.vl-verify-row` matched **0 elements** (dead rule).
- `.vl-btn-quiet` matched **2 elements** (Send code, Clear key).
- The **only `+` anywhere in the section** was the attribute
  `INPUT.vl-input[placeholder="+91 00000 00000"]`. Zero `+` text nodes; no `::before`/`::after`
  content carrying one.
- `dialog` elements **0**, `[role=dialog],[role=alertdialog],[aria-modal]` **0**,
  `position:fixed` nodes in the section **0**, inputs with `required`/`pattern` **0**,
  `checkValidity()` true on every input.
- Clicking Subscribe empty, then with `9876543210`: **0** Playwright `dialog` events,
  `document.body.innerHTML.length` 42452 → 42452 (unchanged).
- Requests on load: **1** (the document). Document `scrollWidth == clientWidth` at both widths.

---

## 2. What each of the three reported problems actually was

### Fix 1 — "buttons are not matching"

Three distinct defects. All three ROLE 1 action buttons already conformed, so the mismatch was
**between roles and inside rows**, not a bad `.vl-btn` rule.

1. **The action row held two different shapes.** `Send code` (32 / 999px / 12px-700 / white)
   sat 12px from `Subscribe` (52 / 13px / 16px-500 / lime). Centres aligned, heights differed by
   **20px**. Removed with the two-step flow it belonged to (fix 2), leaving the row single-role.
2. **Subscribe floated 19.5px off its field's baseline.** `.vl-sub-action` was declared **twice**,
   in two separate blocks; the copies set **disjoint** properties so both applied and neither
   overrode the other — which is why this needed measuring rather than reading. The second copy
   carried `min-height:91px`, lifted from `BlogSubscribe.tsx:348`. In the shipped component 91 is
   exact: input 52 + gap 7 + `.verify-row` 32. **This mock has no verify row**, so 91 held a 52px
   button centred in it with 19.5px of dead space either side. Removed. The sibling row in the
   same file — `.vl-keyrow` holding the key field and `Load` — was always written without it,
   which is why `Load` never showed the defect and is the reference for what this row should be.
3. **The `+`/WhatsApp-alert finding, which is the one the report singles out.** The only `+` in
   the section was the string `+91 00000 00000` painted in **placeholder grey inside the
   WhatsApp-alerts number field** — a fake country code standing in for a control that did not
   exist, and ten digits beginning with 0 reading as a value already in the field.
   `PhoneField.tsx` documents this exact failure mode for its `NUMBER_FORMAT_HINT` constant.
   It is now a real, editable, labelled control holding a real value (fix 3).
4. **`Clear key` did not match its row-mates.** Revealed by removing `hidden` and re-measuring:
   **32px / 12px-700 / 12px padding** between two `.vl-layer` pills at **38px / 13px-700 / 16px**
   — a 6px height difference and a 3px vertical offset in a three-item row. Invisible in the
   committed screenshots only because the no-key state hides it; visible to anyone who loads a
   key, which is the state the mock exists to demonstrate. Moved to ROLE 5 as `.vl-map-btn`.

### Fix 2 — "unnecessary dialog"

**Nothing that is literally a dialog existed, and the report is still correct.** Interrogated
first: `dialog` elements 0, `[role=dialog]`/`[aria-modal]` 0, no `position:fixed` node in the
section, no `required`/`pattern`/`minlength` anywhere, every form `onsubmit="return false"`,
`checkValidity()` true. Clicking Subscribe empty and filled fired **zero** `dialog` events and
changed `innerHTML.length` by **0**.

**What the user is seeing is the extra STEP, in the subscribing section — the two-step
verify/OTP confirmation the flow still promised.** Three pieces of evidence, all in the artifact
at the URL that was shared:

1. `Send code` was a stub of `BlogSubscribe.tsx`'s real two-step flow, where pressing it swaps
   the row for an OTP `input.otp` plus a `Verify` button.
2. `.vl-verify-row` CSS was still present and matched **nothing** — the shell of step two.
3. The head copy read "**Verify your WhatsApp number once**, then pick the places you want
   watched." — telling the reader in words that there was another screen before subscribing.

Collapsed to one inline step: `Send code` deleted, the dead `.vl-verify-row` rule deleted, the
promise removed from the head copy **by deletion only**, and the second step replaced by an
inline `role="status"` line ported from `BlogSubscribe.tsx:347`. The status region is in the
document from first paint and reserves its own 22px, so reporting a result mounts nothing and
shifts nothing — verified: `.vl-subscribe` descendant count **16 → 16** across the whole
interaction set.

**Guarded against, on the repo's own history:** a native constraint-validation bubble. It did
not fire before and does not now, but `PhoneField.tsx` records that the owner reported that
bubble *itself* as a defect ("Please fill out this field." with an orange warning icon,
photographed on the live sign-in page — unthemeable, untranslatable, contradicts the standing
no-red instruction). The new control therefore carries **no** `required`, `pattern` or
`minlength`; `aria-required="true"` carries the semantic. Asserted empirically, not trusted.

**Recorded and deliberately NOT actioned — `.vl-keygate`.** It is the one thing on the page that
*looks* like a modal: `position:absolute;inset:0;z-index:6`, a grey scrim over the map stage with
a centred white card ("Maps key" / `Load`). Left alone because it is in the **map** column, not
the subscribe flow, and because it is load-bearing for the zero-network requirement — the no-key
state is what holds the page at 0 outbound requests. **If the owner meant this one, it is a
separate change and needs saying so.**

### Fix 3 — phone number with a country code

Implemented as a port of `src/components/PhoneField.tsx`, the component PR #196 reworked to
"Replace country dropdown with searchable calling code". One outlined container (`.vl-pf`) split
by a hairline, holding a calling-code segment (`.vl-pf-code`) and a national-number segment
(`.vl-pf-num`). Specifics followed from that file:

- The ROLE 3 box moves onto the **container** and the segments carry none of their own — its own
  comment: "The outline, the radius and the height live here, on the container".
- 9px logical inner corners (container's 10px minus its 1px border), square against the divider.
- The divider is a logical `border-inline-end` on the leading segment, so it mirrors in RTL.
- **Inset focus rings per segment**, not one on the container: there are two focusable controls
  inside it, so a single ring would not say which half has focus (WCAG 2.4.7). Lime is layered
  around the dark ring and never used as the ring — `#d1f470` on white is 1.24:1 against the 3:1
  WCAG 1.4.11 requires; `#1a3a2a` is 12.48:1.
- **No dropdown, no flag, no country name** — `PhoneField.tsx` states this outright, and
  `dialCodes.ts` forbids emoji flags because Windows ships no flag glyphs.
- Behaviour ports `DialCodeSearch`: focus selects, input normalises and commits on a supported
  code, blur reverts an unresolved code, Enter commits then blurs, `aria-invalid` while unresolved.
- `VL_DIAL_CODES` ports `DIAL_CODES` from `src/lib/dialCodes.ts` **preserving its order** (India
  first) **and its exclusions** (`+86`, `+98`, `+963`, `+850` — WhatsApp undeliverable; `+92` —
  owner instruction 2026-10-02). `vlNormaliseDial` / `vlFindDial` / `vlLengthHint` /
  `vlValidLength` port `normaliseDialSearch` / `findDialCode` / `nationalLengthHint` /
  `isValidNationalLength` with the same semantics, including "no rule for this country ⇒ accept
  anything non-empty".

Inline vanilla ES5 inside the file's existing IIFE, in its house style (`var`, no arrows, no
template literals, no `fetch`, no timers). Zero network.

---

## 3. Post-fix measurements

### ROLE 1 — every action button shares one geometry

| Assertion | 1280 | 390 |
|---|---|---|
| `all action buttons share one height` | **52** | **52** |
| `all action buttons share one font` | **16px/500** | **16px/500** |

Load / Subscribe / Contribute each independently assert height 52, font 16px/500, radius 13px,
border `2px rgb(26,58,42)`, fill `rgb(209,244,112)`.

### The Subscribe baseline

- 1280: `Subscribe bottom meets field bottom (<=1px)` → **0px**. (Was −19.5px.)
- 390: `Subscribe wrapped to its own row (390 layout)` → delta 64px, **wrapped**. The action wraps
  below the full-width field via `flex-wrap:wrap`, which is the intended mobile layout; the
  harness detects which case applies rather than skipping silently, so a regression to the
  dead-space bug cannot hide behind the wrap.
- `.vl-sub-action declares no min-height length` → **auto** at both widths. (`auto` is the pass:
  the initial computed value of `min-height` is `auto`, never `0px`; what must be gone is a
  **length**.)
- `.vl-sub-action holds exactly one control` → **1 child** at both widths.

### ROLE 3 — the divided field

| Assertion | Result (both widths) |
|---|---|
| `.vl-pf height 52` | **52px** |
| `.vl-pf radius 10px` | **10px** |
| `.vl-pf border 1px #e5e7eb` | **1px rgb(229, 231, 235)** |
| `calling code defaults to +91` | **+91** |
| `both segments fill the container content box` | **50/50 inside 52** |
| `segments share one row` | identical `top` (0px apart) |
| `code segment carries only the divider border` | outer `0px/0px/0px`, divider `1px` |
| `number segment carries no border` | `0px/0px/0px/0px` |
| `number placeholder is not clipped` | **fits** (`scrollWidth <= clientWidth`) |
| `no required/pattern/minlength on either segment` | `required:false, pattern:"", minLength:-1` on both |
| `aria-required carries the semantic instead` | `aria-required="true"` on `#vl-sub-phone` |
| `no horizontal overflow` | 1280 vs 1280 / **390 vs 390** |

50px, not 52, is correct and is asserted as "container height minus its two 1px borders": the
segments stretch to the container's **content** box. The 52 belongs to the container, which is the
entire point of the divided form, and `PhoneField` renders the same way.

### ROLE 5 — the map-control row, with `#vl-keyclear` revealed

| Assertion | Result |
|---|---|
| `map row has 3 controls` | 3 |
| `map row shares one height` | **38** |
| `map row shares one font size` | **13px** |
| `map row shares one font weight` | **700** |
| `map row shares one padding` | **16px/16px** |
| `map row is vertically flush` | one `top`, one `bottom` |
| `map row is 38px (ROLE 5)` | AQI 38, PM2.5 38, **Clear key 38** |

`Clear key` must not have joined the AQI/PM2.5 radio group now that it matches them visually.
Asserted **at the selector** rather than by clicking: its handler ends in
`window.location.reload()` by design (the Maps script cannot be unloaded, so a reload is the only
honest way back to the no-key state), so a real click destroys the execution context and ends the
measurement instead of failing or passing it — and `location.reload` is non-writable in Chrome, so
it cannot be stubbed. Group membership is decided by exactly one selector (the script does
`querySelectorAll('.vl-layer')`), so the NodeList *is* the question:

- `Clear key is .vl-map-btn, not .vl-layer` → `vl-map-btn`
- `Clear key is not in the layer toggle group` → group is `vl-layer-aqi, vl-layer-pm`
- `the layer group is exactly AQI + PM2.5` → 2 members
- `Clear key carries no aria-pressed state` → ok

### Retired role, dead rule, and no dialog of any kind

| Assertion | Result |
|---|---|
| `.vl-btn-quiet matches 0 elements` | 0 |
| `.vl-verify-row matches 0 elements` | 0 |
| `no .vl-btn-quiet / .vl-verify-row CSS rule survives` | **0 rules** |
| `zero <dialog> elements` | 0 |
| `zero role=dialog / aria-modal` | 0 |
| `nothing in the section is position:fixed` | none |
| `the only "+" is the calling-code control value` | `text []`, attr `INPUT#vl-sub-dial[value="+91"]`, `INPUT#vl-sub-dial[placeholder="+91"]` |

The CSS-rule check walks `document.styleSheets` for a **selector** containing `vl-btn-quiet` or
`vl-verify-row`, not for the string in the file. Both names are still written in the comments that
record their retirement, which is the useful place for them; what must be gone is any rule that
could style an element. Same reasoning applies to the zero-network grep — see §5.

### The interaction set (no dialog, inline only)

Run at both widths with `page.on('dialog')` wired to fail the run:

| Step | Assertion | Result |
|---|---|---|
| submit **empty** | reports inline | `Enter a 10-digit WhatsApp number for +91.` |
| | marks the number invalid | `aria-invalid="true"` |
| | does not flip the button label | `Subscribe` |
| type `971` | commits `+971` | `+971` |
| | updates the length hint | `8- or 9-digit WhatsApp number` |
| type `123` | unsupported code is `aria-invalid` | `true` |
| blur | reverts to last committed code | `+971` |
| submit `9876543210` on `+91` | composes E.164 inline | `Subscribed +919876543210 to alerts for this place.` |
| | flips the label | `Subscribed` |
| | marks the status done | `vl-sub-status is-done` |
| | clears `aria-invalid` | `null` |
| Enter in the code segment | does not submit | no change |
| whole set | **no element was added to the subscribe panel** | **16 → 16** |
| whole set | **NO dialog fired during any interaction** | **none** |

Submitting empty is the single most important click here: it is exactly where a `required`
attribute would raise the native bubble the owner reported.

### Zero network

| Assertion | 1280 | 390 |
|---|---|---|
| `exactly 1 request (the document)` | **1** | **1** |
| `zero non-file:// requests` | none | none |
| `zero console errors` | none | none |
| `zero page errors` | none | none |

---

## 4. Twin equality and the `diff` substitute

**`diff` and `cmp` are NOT installed on this box** — `command -v diff cmp` returns nothing. The
task asked for `diff <live-mock> <final-v3>` with empty output; the equivalent actually run:

```
$ git --no-pager diff --no-index docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html
(no output)
exit=0

$ md5sum docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html
b35c27416ae35f5d9bf520a6bcd5c616  docs/mocks/vayulok-live-mock.html
b35c27416ae35f5d9bf520a6bcd5c616  docs/mocks/vayulok-final-v3.html
unique hashes: 1
```

The twin is additionally verified **as a twin rather than only byte-compared** — the harness runs
its full 67-assertion suite against `vayulok-final-v3.html` as well, at both widths. A byte
comparison proves the files match, not that either renders correctly.

## 5. Zero-network contract, secondary cross-check

`grep -c 'rel="stylesheet"\|@font-face\|@import'` returns **1**, and that single hit is **line 47
of the preserved contract comment itself** — "THE FONT STACK IS DECLARED LOCALLY AND NEVER
FETCHED. No @font-face, no …". That note is preserved verbatim. There are no `src=` attributes
outside the runtime-assembled Maps URL, no `https://` literals, no `<link rel=stylesheet>`, no
`@font-face` and no `@import` rule. **The request count in §3 is the primary signal**; the grep
cannot be, because the file documents the absence of those things using their own names.

## 6. Screenshots regenerated

`node tools/browser/vayuloksubcheck.js --shots`, viewports pinned in the script:

| File | Dimensions |
|---|---|
| `docs/mocks/vayulok-live-mock-1280.png` | 1280 x 5567 |
| `docs/mocks/vayulok-final-v3-1280.png` | 1280 x 5567 |
| `docs/mocks/vayulok-live-mock-390.png` | 390 x 6519 |
| `docs/mocks/vayulok-final-v3-390.png` | 390 x 6519 |
| `docs/mocks/vayulok-section-desktop.png` | 1440 x 950 (regenerated byte-identical — the top of the page did not change) |
| `docs/mocks/vayulok-section-scrolled.png` | 1440 x 950 |
| `docs/mocks/vayulok-section-subscribe.png` | 1440 x 950 |

The `-1280` pair and the `-390` pair are each **byte-identical** to one another (one md5 per pair),
as the identical HTML twins require.

**The committed PNGs were already stale before this pass.** They were 1347x6040 and 390x7506,
while the *committed HTML* rendered 1280x5583 / 390x6547 — i.e. the `-1280.png` was not even 1280
wide. The new, correctly-sized and shorter images are the correction, not a regression. A reviewer
diffing image dimensions should not read the change as one.

Inspected by eye at both widths (not merely written):

- **1280** — one lime `Subscribe` button, baseline-flush with a **divided** field whose left
  segment reads `+91` behind a hairline, right segment placeholder `10-digit WhatsApp number`.
- **390** — field full width, action wrapped below it, nothing clipped, no horizontal scroll.
- **empty submit** — inline line `Enter a 10-digit WhatsApp number for +91.` under the field;
  dark inset focus ring on the number segment with the lime halo on the container; no popup.
- **valid submit** — button reads `Subscribed`, inline line
  `Subscribed +919876543210 to alerts for this place.`; the placeholder block below has not moved.
- **map controls** — AQI / PM2.5 / Clear key now one uniform 38px row (was 38 / 38 / 32).

## 7. Repo-level checks, reported honestly

- `node tools/browser/vayuloksubcheck.js` — **exit 0, 268/268**.
- `node tools/browser/vayuloksubcheck.js --json` — exit 0, parses, `passed: 268, failed: 0`.
- `npx tsc --noEmit` — **29672 errors, and the identical count on a clean `git stash` of this
  work (29672 before = 29672 after).** The app's `node_modules` is **empty** in this sandbox, so
  every error is a missing-dependency error (`Cannot find name 'process'`, `Cannot find module
  'vitest/config'`) in files this change never touches. Pre-existing and environmental.
- `npx vitest run` — fails with `ERR_MODULE_NOT_FOUND` for the same reason: dependencies are not
  installed. **Not claimed as passing.** Neither suite covers `docs/mocks` in any case — grep the
  `tests`, `src`, `scripts` and `.github` trees for `docs/mocks` or `vayulok-live-mock` and there
  are no hits, which is why `tools/browser/vayuloksubcheck.js` was added.
- `git status --short` lists only the intended paths; nothing under `src/`.

---

## 8. Interpretations made, and the alternatives rejected

Each of these was a genuine ambiguity. The reading taken is recorded with the one not taken.

### 8a. "13px font / 52px height" for the ROLE 1 action button

The brief states the ROLE 1 contract is **13px font / 52px height**, citing
`src/components/BlogSubscribe.tsx:338` `.verify-row button`. **Reading the cited files, that
conflates three different things, and it is not adopted:**

- `src/styles/button.css:31` is `border-radius: 13px`. **13px is the RADIUS.**
- The font size on the 52px size class is `.btn-lg{height:52px;padding:0 24px;font-size:16px}`
  (button.css:52-56). 13px type belongs to `.btn-sm`, which is **36px** tall (button.css:40-44).
- `BlogSubscribe.tsx:338` `.verify-row button` is **32px** tall at **12px/700**, radius 999px —
  that is the mock's retired **ROLE 2** quiet shape, not the action shape.
- `docs/mocks/home-hero/index.html:192` independently renders the action shape the VayuLok mock
  adopted: `height:52px;font-size:16px;font-weight:500;border-radius:13px;padding:0 24px`.

**Taken:** ROLE 1 = 13px **radius** + 52px height + 16px/500 + 2px `#1a3a2a` + `#d1f470`. All
three ROLE 1 buttons already satisfied it, so fix 1 is positional and cross-role, not a restyle.

**Rejected:** reading "13px font" literally and shrinking `.vl-btn` to 13px type. It would break
conformance with `button.css` `.btn-lg`, with `home-hero/index.html` `.home-btn` and with the
mock's own citation — i.e. it would **create** the inconsistency being reported. If the owner did
mean 13px type, that is a change to `src/styles/button.css` affecting every button on the site
and is outside this task's two-file scope. **Worth a yes/no from the owner.**

### 8b. "Make every button consistent against the ROLE 1 contract"

**Taken:** every control in a **single row** shares a role, and every member of a role shares its
geometry exactly. Both measured defects were breaches of that, not of the role table.

**Rejected:** flattening all six rendered shapes to 52px/16px. The brief also instructs that the
file's `file:line` comments *are* the design-token contract, and those comments source the chip
from `BlogContribution.tsx:277` (40px) and the quiet button from `BlogSubscribe.tsx:338` (32px). A
contribution chip is not a submit button; flattening them would destroy the hierarchy the shipped
components actually have and would contradict the same brief.

### 8c. Role numbering

**Taken:** ROLE numbers are stable and not reused. ROLE 2 is retired with its number left vacant,
so the brief's own "ROLE 1 action button" and "ROLE 3 text input" citations stay valid.

**Rejected:** renumbering ROLE 3 → ROLE 2 to close the gap. It would silently invalidate every
citation of these numbers made outside the file, including the one in the task brief.

### 8d. Segment type size — the one value not ported verbatim

`PhoneField.tsx` sets the segments to **17px**. The ported field uses **16px**.

**Taken:** 16px, because that is this role's own size (`BlogSubscribe.tsx:330`) and what
`.vl-input` renders for the search field and the key field in the same section. Porting 17px would
make the one divided field on the page the only field with a different type size — the class of
inconsistency this pass removes. Everything defining the **box** is PhoneField's, unchanged.

### 8e. Head copy

**Taken:** deletion only. "Verify your WhatsApp number once, then pick the places you want
watched." → "**Pick the places you want watched.**" The file's standing rule is not to invent copy
(see its two `.vl-placeholder` blocks).

**Rejected:** a rewritten sentence naming the one-step flow. It would read better and is welcome —
**it needs the owner's words.** Flagging it rather than writing it.

### 8f. No visible list of calling codes

**Taken:** search-input only, per `PhoneField.tsx` ("Search input only: no native country
dropdown, no flag, no country name"). Discoverability is carried by the always-visible `+91`, the
length-hint placeholder that updates with the code, and the inline status line.

**Rejected:** a native `<datalist>`. It would add filter-as-you-type for zero JS and zero network,
but it renders a **native popup** — the same class of unthemeable browser-chrome affordance fix 2
exists to remove — and it contradicts the shipped component's documented decision. **If the owner
wants a visible list, a datalist is the cheapest route and the decision is theirs.**

### 8g. `.vl-keygate` as the "dialog"

Recorded in §2 and **not actioned**. The most modal-looking thing on the page, but it is in the
map column rather than the subscribe flow, and it is what holds the page at zero requests.
**Needs an explicit decision if that is what was meant.**

---

## 9. Still open, outside this task's file list

**The URL the user shared will not show these fixes yet.**
`https://htmlpreview.github.io/?…/vayulok-preview/docs/mocks/vayulok-live-mock.html?v=30` reads
`origin/vayulok-preview`, which is **11 commits behind** this branch
(`git rev-list --left-right --count origin/vayulok-preview...HEAD` → `9 11`). The fix appears there
only once that branch is updated **and** the `?v=` cache-buster is bumped. Who does that is the
owner's call; it is not in this task's two-file scope.

On the original report's "which branch were we working on" and the merge conflict: the conflict
was on `vayulok-preview` and is **already resolved** — `2d6ca401 docs(vayulok): rebase VayuLok
mock onto current stack` put this work conflict-free on top of `origin/stack`
(`git rev-list --left-right --count origin/stack...HEAD` → `0 1`). There is **no conflict in
progress**: no `MERGE_HEAD`, no `REBASE*` in `.git`, and `grep -c '^<<<<<<<'` is 0 in both mocks.
Also noting that `.kiro/steering/git-workflow.md` mandates a single-branch workflow on `stack`,
while this work sits on `fix/vayulok-subscribe-inline` because the workflow placed it there —
**ask before merging or renaming** rather than switching branches unilaterally.
