# Implementation Plan — VayuLok app-shell mock (`docs/mocks/vayulok-app-mock.html`)

Deliverable: one self-contained, zero-network HTML file plus two committed screenshots, on
branch `feat/vayulok-update`. This is a **visual mock for the owner**, not production code.

---

## 0. Decisions made during exploration (rationale, not a design doc)

These were open questions. Each is now closed — the implementer must not re-decide them.

**D1 — Not decomposed into FEATs; one plan, one file.** The whole deliverable is a single
self-contained HTML document. Splitting it into separable features would make every feature
edit the same file and leave intermediate states that are half a page, so there is nothing to
decompose. The workflow's existing implement-and-review loop runs this plan.

**D2 — Branch rule conflict is resolved in favour of the task.**
`.kiro/steering/git-workflow.md` says commit directly to `stack` and never create feature
branches — but its own Rule 1 carves out "unless the user explicitly asks for a branch by
name", and the user did. `feat/vayulok-update` already exists, is checked out, has one commit
(`df01654d`), and tracks `origin/feat/vayulok-update` (verified). So: commit there, never on
`stack`. Do **not** `git checkout -b`.

**D3 — Verification runs through the repo's own browser harness, not a fresh Playwright
install.** `tools/browser/` is a deliberately separate harness package
(`playwright-core` + `lighthouse`) whose `lib/browser.js` resolves Chromium in a
revision-proof order (`$CHROME` → `$PLAYWRIGHT_BROWSERS_PATH` → highest `chromium-*` under
`/opt/playwright` → per-OS cache → system Chrome). Its header comment records that hardcoding
a revision already cost a debugging round. Verified on this box: `npm install` in
`tools/browser` succeeds (114 packages, no browser download) and `resolveChrome()` returns
`/opt/playwright/chromium-1232/chrome-linux64/chrome`. **Never hardcode that path.**
`tools/browser/node_modules` is gitignored (`.gitignore:2`), so installing there is safe.

**D4 — Zero-network is proven by an offline browser context, not only by grep.** Verified
prototype: `browser.newContext({ offline: true })` + `context.on('request')` +
`context.on('requestfailed')` over a `file://` navigation records **exactly one** request (the
document itself) and zero failures. Any `<script src>`, remote font or image would appear as a
second request or a `requestfailed`. Grep is kept as a *static* second gate, as the task
requires, but the offline context is the real proof.

**D5 — Inline SVG must carry NO `xmlns` attribute.** The task mandates a grep for `http://`
and `https://`. The conventional `xmlns="http://www.w3.org/2000/svg"` would fail that grep.
Verified in Chromium that an `<svg>` written inline in HTML with no `xmlns` still gets
`namespaceURI === "http://www.w3.org/2000/svg"` and renders at its correct box size, because
the HTML parser assigns the SVG namespace itself. So omit `xmlns` everywhere — it is both
unnecessary and the one thing that would break the URL grep.

**D6 — Type ladder is an app-shell ladder derived from the steering contract, not a copy of
it.** `.kiro/steering/grahak-os-design.md` is scoped by `fileMatchPattern` to
`src/pages/grahak-os/**`, `src/components/**`, `src/styles/**` — `docs/mocks/` is out of
scope — and its single 20px body rung is calibrated to a 1300px marketing measure. A 455px
dense weather panel cannot carry 20px body text. So the ladder in §2 keeps the contract's
*principles* verbatim (the 700-over-600 weight inversion, negative tracking, and "eyebrows are
**not** uppercase and **not** letter-spaced") and restates the sizes for a dense surface, with
exactly one body rung inside the panel.

**D7 — Hairline weight from steering, hairline colour from the task.** Steering: `2px` means
hoverable, `1px` means static. The task's token list says rules are at ~11% green tint. These
are not in conflict — weight and colour are separate axes — so: `1px solid rgba(26,58,42,.11)`
for static rules, `2px solid rgba(26,58,42,.11)` only on the controls that have a hover or
pressed state (segmented tabs, layer buttons, "View details"). The task's explicit token list
is authoritative on colour, so `#e5e7eb` is **not** used.

**D8 — The pale lime ground is `rgba(209,244,112,.22)`.** Steering allows exactly three lime
treatments and names `rgba(209,244,112,.22)` as the pale one, warning that inventing an
in-between tint is how `#f2fbf6` and `#fbfff0` got into the codebase. So the health advisory
uses that exact value rather than a fresh tint.

**D9 — Mock-only map geometry colours are declared as such.** `#e9e6df` (given by the task)
does not exist anywhere in the repo — confirmed by grep. It and the two road/water greys in
§13 are mock-only map-surface colours, not brand tokens, and must be commented as such so a
later sweep does not adopt them.

**D10 — Placeholder city is Delhi, with October-plausible values.** Not the test fixture
'Lumpyngngad, Shillong'. AQI 168 is CPCB "Moderate" (101–200), which maps to the approved
amber accent pair — a realistic Delhi reading that also exercises a mid-severity colour rather
than a flat green.

**D11 — Screenshot geometry.** 1280×900 (a real laptop viewport) and 390×844 (iPhone-class),
both `fullPage: true`, `deviceScaleFactor: 1`. At 1280 the shell is `100dvh` and does not
overflow, so `fullPage` resolves to exactly 1280×900 — verified. The left panel scrolls
*internally*, which is faithful to a real app shell; the owner scrolls the live file to see
the lower sections.

**Assumption recorded:** the task says "rules at ~11% green tint" without an exact value;
`rgba(26,58,42,.11)` is used, derived from `#1a3a2a` at 11% alpha.

---

## 1. Exact token values — copy these verbatim

Declare as custom properties on `:root`. No other colour may appear in the file.

| Property | Value | Role |
|---|---|---|
| `--lime` | `#d1f470` | brand lime. **NOT `#d0f070`** |
| `--green` | `#1a3a2a` | deep green. **NOT `#183828`** |
| `--lime-tint` | `rgba(209,244,112,.22)` | pale lime ground (D8) |
| `--bg` | `#f8f8f8` | page behind the two panes |
| `--paper` | `#ffffff` | pane and card surfaces |
| `--soft` | `#f4f4f1` | inset cells, fact-rail cells, input field |
| `--ink` | `#111111` | primary type |
| `--muted` | `#5c5c57` | labels, captions, attribution |
| `--rule` | `rgba(26,58,42,.11)` | all hairlines (D7) |
| `--radius` | `13px` | every corner |
| `--shadow` | `0 4px 12px rgba(26,58,42,.12)` | the soft shadow. Reused from `BlogIndexView.tsx:523` / `BlogContribution.tsx:282`, not invented |

Approved accent pairs — use **only** these four, from the steering palette and
`src/pages/vayulok/index.tsx:78-83`:

| Pair | Dot | Tint | Used for |
|---|---|---|---|
| good | `#3da35a` | `#e0f7c8` | low pollutant bars, "Best outside" supporting dot |
| moderate | `#f0a818` | `#fef3c7` | AQI 168 dot + category, UV High |
| severe | `#dc2626` | `#fee2e2` | the weather-alert card tint (§9) |
| info | `#9849e8` | `#ede9fe` | reserved; use only if a fourth hue is needed |

Font stack, exactly this string, with **no** `@font-face` and **no** remote load:

```
font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
```

Heatmap / history ramp: `linear-gradient(90deg,var(--green),var(--lime))`.

**Never put lime on a third-party mark** (steering, pinned by a test): the provider-attribution
line in §13 must be `--muted` type on `--paper`, never lime, never green-filled.

## 2. Type ladder — app shell (D6)

| Rung | Spec | Applied to |
|---|---|---|
| metric-xl | `44px / 600 / lh 1 / ls -2.2px` | big temperature, big AQI number |
| card-title | `22px / 700 / lh 1.27 / ls -.25px` | place name, "Now", "Next 24 hours", "Air quality" |
| metric-md | `17px / 700 / lh 1.2 / ls -.25px` | fact-rail values, pollutant values, hour-card temp |
| body | `15px / 400 / lh 1.45 / ls -.125px` | the **one** body rung in the panel |
| label | `13px / 400 / lh 1.35 / ls 0` | field labels, `--muted`, not uppercase, not letter-spaced |
| micro | `12px / 400 / lh 1.4 / ls 0` | attribution, map caption, confidence pill |

Weight inversion is deliberate: card titles are 700, heavier than the 600 metric numbers above
them. Do not "fix" it — that is the contract's rule carried over.

---

## Implementation items

- [ ] 1. **Pre-flight: confirm branch, and record the baseline of the files that must not change.**
      Confirm `feat/vayulok-update` is checked out and the tree is clean. Record the hashes of the
      existing mock so §16 can prove it was untouched. Do **not** create a branch.
      Files: none (read-only).
      Verify:
      ```bash
      git -C /projects/sandbox/wecare-digital rev-parse --abbrev-ref HEAD
      git -C /projects/sandbox/wecare-digital status --porcelain
      sha256sum /projects/sandbox/wecare-digital/docs/mocks/vayulok-mock.html \
                /projects/sandbox/wecare-digital/docs/mocks/vayulok-mock-1280.png \
                /projects/sandbox/wecare-digital/docs/mocks/vayulok-mock-360.png
      ```
      Expected: prints `feat/vayulok-update`, no porcelain output, and these three hashes —
      `83cfd219058835d0192942673730ef9e0b10b5d690ec3128b1790608f7a5262b`,
      `a104673ce73a2e920542b584162f1173c400ab5ec77388ab4967d661e4e2fa80`,
      `6ea2e520fc7e89500050016033a30138c49220756bb796ba3e6990f586537b68`.
      If the branch is anything else, STOP — do not switch, do not create one; report it.

- [ ] 2. **Install the browser harness dependencies** so verification can run (D3).
      Files: none committed — `tools/browser/node_modules/` is gitignored (`.gitignore:2`).
      ```bash
      cd /projects/sandbox/wecare-digital/tools/browser && npm install --no-audit --no-fund
      ```
      Verify:
      ```bash
      node -e "console.log(require('/projects/sandbox/wecare-digital/tools/browser/lib/browser.js').resolveChrome())"
      ```
      Expected: prints an existing Chromium path (on this box
      `/opt/playwright/chromium-1232/chrome-linux64/chrome`). It must come from
      `resolveChrome()` — never paste the literal into any script.

- [ ] 3. **Create the file skeleton: head, banner, tokens, type ladder, two-pane shell.**
      Create `docs/mocks/vayulok-app-mock.html` with the leading HTML comment block (modelled on
      the sibling `vayulok-mock.html`: states INTERNAL DUMMY MOCK, not production code, why it
      lives in `docs/mocks/`, that it makes zero network calls, and that no API key or map library
      is present). Then `<head>`: `<meta charset>`, `<meta name="viewport">`,
      `<meta name="robots" content="noindex, nofollow">`, `<link rel="icon" href="data:,">` (a
      data URI — suppresses any favicon fetch, verified to add no request), `<title>DUMMY MOCK —
      VayuLok app shell (internal, not a live page)</title>`, and one `<style>`. Add §1 tokens and
      §2 ladder. Then **§12 banner** (`.vk-banner`, full-width, `--green` fill with `--lime` type
      — the contract's "inverted, dark" lime treatment — `role="note"`, text naming it an internal
      dummy mock, not a live page, not production code), and the **§1 two-pane shell**:
      ```
      .vk-shell{height:100dvh;padding:12px;display:grid;
        grid-template-columns:minmax(405px,455px) 1fr;gap:12px;
        box-sizing:border-box;background:var(--bg)}
      .vk-panel,.vk-stage{background:var(--paper);border-radius:var(--radius);box-shadow:var(--shadow)}
      .vk-panel{overflow-y:auto;position:relative}
      .vk-stage{overflow:hidden;position:relative}
      ```
      The banner sits above the shell, so give the shell `height:calc(100dvh - <banner>)` or wrap
      both in a `100dvh` column flex with the shell as `flex:1` — pick the flex wrapper, it
      survives a banner copy edit.
      Mobile: `@media (max-width:759px)` → `grid-template-columns:1fr;grid-template-rows:42dvh 1fr;`
      with the stage first in DOM order **or** `order:-1`; the panel below. Put the media query
      **after** the base rules (steering trap 4).
      **No `xmlns` on any SVG (D5).**
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: `node .agents/tasks/vayulok-app-mock-feat-vayulok-update-2026-10-02/verify-mock.cjs`
      does not exist yet, so for this item run the ad-hoc check that the file opens with zero
      network and zero console errors once item 14 exists. Until then, verify structurally:
      open the file and confirm it is valid HTML by `node -e "const s=require('fs').readFileSync('docs/mocks/vayulok-app-mock.html','utf8');if(!/<\/html>/.test(s))throw new Error('unterminated')"`.
      Items 4–13 are additive within this one file; the real gate is item 14.

- [ ] 4. **§2 sticky search header.** Inside `.vk-panel`, a `position:sticky;top:0` bar on
      `--paper` with a `1px solid var(--rule)` bottom hairline and a small `z-index`. Contains an
      inline magnifier SVG (circle + handle path, `stroke:var(--muted)`, `stroke-width:2`, 20px
      box, no `xmlns`) and a text input on `--soft` with `--radius`, `1px solid var(--rule)`,
      `placeholder="Search a city or place"`, left-padded clear of the icon. Resting state only —
      no focus-trapped styling needed beyond a `:focus-visible` outline of `2px solid var(--green)`.
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by item 14 (`panelScrolls` true and no console errors); visually, the header
      stays pinned in the 1280 screenshot.

- [ ] 5. **§3 place section.** A photo area as a **CSS gradient placeholder, no remote image**:
      a ~150px-tall block, `--radius`, e.g.
      `linear-gradient(135deg,#e9e6df,#f4f4f1 55%,rgba(209,244,112,.22))`, carrying a `micro`
      caption inside or directly beneath reading that the photo is illustrative and nothing is
      loaded. Below it: place name on the `card-title` rung (`New Delhi`), address on the `body`
      rung in `--muted` (`Connaught Place, New Delhi, Delhi 110001`).
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by item 14.

- [ ] 6. **§4 "Now" grid — two cells.** A `card-title` heading "Now", then
      `display:grid;grid-template-columns:1fr 1fr;gap:12px` (collapsing to `1fr` under 759px).
      Cell A **Weather**: `label` "Weather", `metric-xl` `31°`, `body` condition `Haze`,
      `label`/`micro` `Feels like 33°`.
      Cell B **Air quality**: `label` "Air quality", `metric-xl` `168` preceded by a 10px round
      AQI dot in the moderate accent `#f0a818`, `body` category `Moderate`, `label` `Dominant
      pollutant PM2.5`, and an "Observed nearby" confidence pill — inline-block, `micro` rung,
      `background:#fef3c7`, `color:var(--ink)`, `border-radius:999px`, `padding:4px 10px`.
      Both cells: `background:var(--soft)`, `--radius`, `padding:14px`, no border.
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by item 14, which asserts the rendered AQI dot colour.

- [ ] 7. **§5 fact rail.** One horizontally scrolling row:
      `display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x proximity;` with each cell
      `flex:0 0 auto;min-width:104px;background:var(--soft);border-radius:var(--radius);padding:12px`,
      a `label` caption above a `metric-md` value. Eight cells, in this order and with these values:
      Humidity `58%`, Wind speed `11 km/h`, Wind direction `NW`, Rainfall `0.0 mm`,
      Rain chance `8%`, Solar `6.2 kWh/m²`, UV `7 High`, PM2.5 `82 µg/m³`.
      Hide the scrollbar softly (`scrollbar-width:thin`) but do not disable scrolling.
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by item 14, which asserts the rail's `scrollWidth > clientWidth`.

- [ ] 8. **§6 health advisory on the pale lime ground.** A block with
      `background:rgba(209,244,112,.22)` (D8 — do not invent a tint), `--radius`,
      `padding:14px`, a `label`-rung "Health advisory" and `body`-rung placeholder guidance
      appropriate to AQI 168 (sensitive groups should limit prolonged outdoor exertion). No
      border; the tint carries it.
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by item 14, which asserts the computed background is `rgba(209,244,112,0.22)`.

- [ ] 9. **§7 signal strip — four cards.** A grid where the primary card spans the full width:
      `grid-template-columns:1fr 1fr`, primary at `grid-column:1 / -1`.
      - **Primary "Best outside"**: `background:var(--green)`, `color:#fff` with the headline
        figure in `var(--lime)`, `--radius`, `padding:16px`. Content: label "Best outside", a
        `card-title`/`metric-md` time window `6:00–8:00 am`, `body` supporting line.
      - **Secondary ×2** on `--soft` with `1px solid var(--rule)`: "Nearby air monitor" —
        `ITO, New Delhi · 2.4 km`; "Nearby weather station" — `Safdarjung · 6.1 km`.
      - **Weather alert, severity-tinted**: `background:#fee2e2` with a `#dc2626` 10px dot and
        `--ink` type (never white-on-tint), `label` "Weather alert", `body` `Dense haze advisory
        until 9:00 am`.
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by item 14, which asserts the primary card's computed background is
      `rgb(26, 58, 42)`.

- [ ] 10. **§8 "Next 24 hours" rail.** `card-title` heading, then the same horizontal-scroll
      pattern as item 7 with 8–12 hour cards, each `flex:0 0 auto;min-width:76px` on `--soft`
      with `--radius`: time on the `label` rung (`2 pm`, `3 pm`, …), temperature on `metric-md`,
      a `micro` rain figure (`0%`), and a `micro` AQI figure with its accent dot (`AQI 171`).
      Values should drift plausibly across the day (temp peaking mid-afternoon, AQI rising after
      sunset) — it is a mock, but it must not look like copy-paste.
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by item 14 (rail `scrollWidth > clientWidth`).

- [ ] 11. **§9 Air/Weather segmented tabs + the Air panel.**
      Tab strip: a `role="tablist"` of two `<button role="tab">` elements ("Air", "Weather") in a
      `--soft` track with `--radius`. The **active** tab is the brand identity fill —
      `background:var(--lime);color:var(--green);border:0` (~10:1), the same pair as
      `.tab.active`/`BrandBadge`. The inactive tab is transparent with `--muted` type. Air is
      active on load. Because `.tab` is a known global-CSS leak name in this repo (steering trap 5),
      **prefix every class `vk-`** and declare `background`, `border` and `width` explicitly.
      Under Air (`#vk-panel-air`):
      - **Pollutant list**: six rows, each a `label` name, a thin track
        (`height:6px;background:var(--rule);border-radius:999px`) with an inner bar whose width is
        a percentage and whose fill is the accent matching its level, and a `metric-md` value.
        PM2.5 `82 µg/m³`, PM10 `148 µg/m³`, NO₂ `41 µg/m³`, O₃ `26 µg/m³`, CO `0.9 mg/m³`,
        SO₂ `12 µg/m³`. Rows separated by `1px solid var(--rule)`.
      - **Three-up insight line**: `grid-template-columns:repeat(3,1fr)`, cells "Best hour
        `6 am`", "Peak hour `9 pm`", "Trend `Worsening`", each `label` over `metric-md`.
      - **24-bar history chart**: a flex row of 24 bars, `align-items:flex-end`, fixed height
        ~96px, each bar `flex:1;border-radius:3px 3px 0 0` with a varying inline `height` and
        `background:linear-gradient(180deg,var(--lime),var(--green))` so the ramp reads
        dark-green-to-lime across the set; add `aria-hidden="true"` on the bar row and a short
        `body`-rung caption naming the window ("Last 24 hours, AQI").
      Under Weather (`#vk-panel-weather`), `hidden` on load: a modest placeholder — three or four
      rows of the same row pattern (temperature, humidity, wind, rainfall) so the toggle visibly
      does something.
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by items 14 and 15 (the toggle assertion).

- [ ] 12. **§10 map stage overlays.** Inside `.vk-stage`, absolutely positioned over the
      placeholder from item 13:
      - **Layer buttons**, top-left: two `<button aria-pressed>` elements, "AQI" and "PM2.5", on
        `--paper` with `--radius`, `2px solid var(--rule)` (hoverable weight, D7) and `--shadow`.
        The pressed one is the brand fill — `background:var(--lime);color:var(--green)` — with
        `aria-pressed="true"`. AQI is pressed on load.
      - **Heatmap legend card**, bottom-left: `--paper`, `--radius`, `--shadow`, `padding:12px`,
        a `label` title "AQI heatmap", a gradient scale bar
        (`height:8px;border-radius:999px;background:linear-gradient(90deg,var(--green),var(--lime))`)
        and `micro` "Low" / "High" labels at each end.
      - **Map preview card**, bottom-right (full-width above the legend on mobile): `--paper`,
        `--radius`, `--shadow`, `padding:14px`. `card-title` `New Delhi`, `body`/`--muted`
        address, a three-up metric row (`Temperature 31°` / `AQI 168` / `PM2.5 82`) each
        `label` over `metric-md`, and a **"View details"** button —
        `background:var(--green);color:#fff;border:0;border-radius:var(--radius);padding:10px 16px`,
        `type="button"`, inert.
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by items 14 and 15 (the layer-toggle assertion).

- [ ] 13. **§10 CSS-only map placeholder, §11 attribution.**
      The stage background is the map geometry colour `#e9e6df` (D9 — comment it as a mock-only
      map surface, not a brand token). Over it, suggest geometry with **one inline SVG, no
      `xmlns`**, `width:100%;height:100%`, `preserveAspectRatio="none"`,
      `aria-hidden="true"`: a water polygon/band in a muted `#dce5e3`, and five or six road
      strokes in `#f4f4f1` at `stroke-width` 6, 4 and 2 (a hierarchy of arterials and side
      streets), plus two or three faint block fills. Both road and water greys are mock-only map
      colours — comment them as such. A visible caption must sit over the placeholder, `micro`
      rung on a `--paper` chip with `--radius`: **"Live map is not embedded in this mock."**
      **§11 attribution**, at the bottom of the stage (and/or the panel foot), both visible and
      correctly styled, `micro` rung, `--muted` on `--paper`, **never lime and never on a
      third-party mark**:
      - a provider-attribution line, and
      - a photo-credit line,
      each labelled as an **illustrative example of where the required attribution sits**, since
      the mock embeds no real map and no real photos. Add a comment stating explicitly that the
      pasted source's CSS which hid the provider logo, legal notices and photo credits is
      **deliberately not reproduced**, because hiding them violates Maps Platform terms.
      **Nothing in this item may introduce a URL, a key, a key-like placeholder, a
      `<meta name="google-maps-key">`, or any remote resource.**
      Files: `docs/mocks/vayulok-app-mock.html`
      Verify: covered by item 14, whose static gate greps for exactly these.

- [ ] 14. **Write the verification harness and run it — this is the real gate.**
      Create `.agents/tasks/vayulok-app-mock-feat-vayulok-update-2026-10-02/verify-mock.cjs`
      (a task artifact, not part of the mock). It must `require` the repo harness —
      `require('/projects/sandbox/wecare-digital/tools/browser/lib/browser.js')` for `launch`,
      `gotoStable` and `resolveChrome` — and **must not hardcode a Chromium path** (D3).
      For each of the two viewports `{1280×900}` and `{390×844}`:
      1. `browser.newContext({ offline:true, viewport, deviceScaleFactor:1 })`.
      2. Collect `context.on('request')` and `context.on('requestfailed')`; on the page collect
         `console` messages of type `error` and `pageerror`.
      3. `gotoStable(page, 'file:///projects/sandbox/wecare-digital/docs/mocks/vayulok-app-mock.html')`.
      4. **Assert zero network**: exactly one recorded request, and its URL is the mock's own
         `file://` URL; `requestfailed` is empty.
      5. **Assert no console errors**: both collections empty.
      6. **Assert rendered tokens** via `getComputedStyle` (stronger than grep — a value can be
         present in source yet overridden): the active tab computes
         `background-color: rgb(209, 244, 112)` and `color: rgb(26, 58, 42)`; the pressed layer
         button computes the same pair; the primary "Best outside" card computes
         `background-color: rgb(26, 58, 42)`; the advisory ground computes
         `rgba(209, 244, 112, 0.22)`; the AQI dot computes `rgb(240, 168, 24)`; the panel's
         `font-family` begins `Inter`.
      7. **Assert layout**: at 1280, `document.scrollingElement.scrollHeight` is within 2px of
         `innerHeight` (the shell really is `100dvh`, the page itself does not scroll); the left
         panel's `scrollHeight > clientHeight` (it scrolls internally); the panel's
         `getBoundingClientRect().width` is between 405 and 455 inclusive; both rails'
         `scrollWidth > clientWidth`. At 390, the stage's `getBoundingClientRect().top` is less
         than the panel's (the map stacked on top) and the stage height is ≈42% of `innerHeight`.
      8. `page.screenshot({ path, fullPage:true })` to
         `docs/mocks/vayulok-app-mock-1280.png` and `docs/mocks/vayulok-app-mock-390.png`.
      9. **Static gate** on the HTML source, in the same script or as the shell commands below:
         zero matches for `AIzaSy`, `googleapis`, `fonts.g`, `http://`, `https://`,
         `google-maps-key`, `<script src`, `fetch(`, `XMLHttpRequest`, `@font-face`,
         `setInterval`, `setTimeout`; zero matches for the drifted `d0f070` and `183828`; at
         least one match each for `d1f470` and `1a3a2a`.
      Exit non-zero with a named reason on any failure; print a PASS summary otherwise.
      Files: `.agents/tasks/vayulok-app-mock-feat-vayulok-update-2026-10-02/verify-mock.cjs`,
      `docs/mocks/vayulok-app-mock-1280.png`, `docs/mocks/vayulok-app-mock-390.png`
      Verify:
      ```bash
      cd /projects/sandbox/wecare-digital
      node .agents/tasks/vayulok-app-mock-feat-vayulok-update-2026-10-02/verify-mock.cjs
      grep -n "AIzaSy\|googleapis\|fonts\.g\|http://\|https://\|google-maps-key\|<script src\|fetch(\|XMLHttpRequest\|@font-face" docs/mocks/vayulok-app-mock.html; echo "grep-exit=$?"
      grep -c "d1f470" docs/mocks/vayulok-app-mock.html
      grep -c "1a3a2a" docs/mocks/vayulok-app-mock.html
      grep -n "d0f070\|183828" docs/mocks/vayulok-app-mock.html; echo "drift-exit=$?"
      ```
      Expected: the node script prints PASS and exits 0; both PNGs exist and are non-empty; the
      forbidden-pattern grep prints nothing and `grep-exit=1`; the two counts are ≥1; the drift
      grep prints nothing and `drift-exit=1`.

- [ ] 15. **Add the inline JS for the two toggles and assert it in the harness.**
      One `<script>` at the end of `<body>`, no `src`, **no timers, no data logic, no fetch**.
      - **Tab toggle**: on click of a `[role="tab"]`, set `aria-selected` true/false across the
        pair, swap the active class, and toggle the `hidden` attribute on `#vk-panel-air` /
        `#vk-panel-weather`.
      - **Layer buttons**: on click, set `aria-pressed="true"` on the clicked button and
        `"false"` on its sibling, swapping the lime fill class.
      Use `querySelectorAll` + `addEventListener`; no inline `onclick` attributes.
      Then extend item 14's harness with a **behavioural** assertion at 1280: click the
      "Weather" tab and assert `#vk-panel-weather` is visible while `#vk-panel-air` has `hidden`
      and `aria-selected` has flipped; click "PM2.5" and assert its `aria-pressed === "true"`,
      the AQI button's is `"false"`, and PM2.5's computed background is `rgb(209, 244, 112)`.
      Re-click "Air"/"AQI" to restore the default state **before** taking the screenshots, so the
      committed PNGs show Air active and AQI pressed as specified.
      Files: `docs/mocks/vayulok-app-mock.html`,
      `.agents/tasks/vayulok-app-mock-feat-vayulok-update-2026-10-02/verify-mock.cjs`
      Verify: re-run the item 14 command block. Expected: still PASS and exit 0, now including
      the toggle assertions, and still exactly one network request and zero console errors.

- [ ] 16. **Prove the existing mock was not touched, then review the screenshots.**
      Re-run the item 1 hashes and confirm all three are byte-identical. Then open both new PNGs
      and confirm they actually show the intended layout — two panes at 1280 with the lime tab and
      pressed lime layer button visible; stacked map-over-panel at 390 — and that no placeholder
      text is clipped or overlapping.
      Files: none modified.
      Verify:
      ```bash
      cd /projects/sandbox/wecare-digital
      sha256sum docs/mocks/vayulok-mock.html docs/mocks/vayulok-mock-1280.png docs/mocks/vayulok-mock-360.png
      git status --porcelain docs/mocks/
      ```
      Expected: the three hashes match item 1 exactly, and `git status --porcelain docs/mocks/`
      lists **only** the three new untracked paths (`vayulok-app-mock.html`,
      `vayulok-app-mock-1280.png`, `vayulok-app-mock-390.png`) — no `M` line for any existing
      mock file. If an existing file shows as modified, restore it with
      `git -C /projects/sandbox/wecare-digital checkout -- <path>` and find out why.

- [ ] 17. **Commit the mock and push to `feat/vayulok-update`.**
      Stage **exactly** the three required paths — never `git add -A`, never `git add .`
      (the repo tree contains unrelated stray files such as `no`, `nothing`, `sweep`).
      ```bash
      cd /projects/sandbox/wecare-digital
      git -C /projects/sandbox/wecare-digital add \
        docs/mocks/vayulok-app-mock.html \
        docs/mocks/vayulok-app-mock-1280.png \
        docs/mocks/vayulok-app-mock-390.png
      git -C /projects/sandbox/wecare-digital status --short
      ```
      Confirm the staged set is exactly those three, then commit with a descriptive what+why
      message (steering rule 5) recording: a second self-contained VayuLok **app-shell** mock
      alongside the existing landing mock; internal only, lives outside the Next.js build;
      **zero network requests and no API key of any kind**; the map is a CSS/SVG-only placeholder
      with a visible caption; provider and photo attribution shown as illustrative and the pasted
      source's attribution-hiding CSS deliberately not reproduced; brand tokens `#d1f470` /
      `#1a3a2a` / Inter; verified in headless Chromium at 1280 and 390 with one request (the file
      itself) and zero console errors.
      ```bash
      git -C /projects/sandbox/wecare-digital rev-parse --abbrev-ref HEAD   # must print feat/vayulok-update
      git -C /projects/sandbox/wecare-digital push origin feat/vayulok-update
      ```
      Files: the three paths above.
      Verify:
      ```bash
      git -C /projects/sandbox/wecare-digital show --stat --oneline HEAD
      git -C /projects/sandbox/wecare-digital log --oneline -1 origin/feat/vayulok-update
      git -C /projects/sandbox/wecare-digital log --oneline -1 origin/stack
      ```
      Expected: `HEAD` touches exactly the three new paths; `origin/feat/vayulok-update` is at the
      new commit; `origin/stack` is **unchanged at `fd0ae45a`**.
      **Never** push to `stack` or `main`. **Do not open a PR.**

- [ ] 18. **Commit the task artifacts as a separate, second commit.**
      Repo convention is to track review artefacts — commit `bc7cbba0` is literally *"chore: track
      every review artefact, because an untracked one was destroyed today"*, and `.agents/` is not
      gitignored (verified). The user's explicit instruction covers the mock commit, so the
      artifacts go in their **own** commit, after it, never mixed in.
      ```bash
      cd /projects/sandbox/wecare-digital
      git -C /projects/sandbox/wecare-digital add .agents/tasks/vayulok-app-mock-feat-vayulok-update-2026-10-02
      git -C /projects/sandbox/wecare-digital status --short
      ```
      Confirm nothing outside that directory is staged, commit as `chore:`, and push to
      `feat/vayulok-update` only.
      Files: everything under
      `.agents/tasks/vayulok-app-mock-feat-vayulok-update-2026-10-02/`
      Verify: `git -C /projects/sandbox/wecare-digital show --stat --oneline HEAD` lists only paths
      under that task directory, and `git -C /projects/sandbox/wecare-digital log --oneline -1 origin/stack`
      still prints `fd0ae45a`.

---

## Hard constraints the implementer must re-read before finishing

1. **No `AIzaSy` string anywhere** — not in code, not in a comment, not as a key-like
   placeholder. No `<meta name="google-maps-key">` or any key-bearing meta.
2. **Zero outbound requests**: no `<script src>`, no remote font or image, no `fetch`, no
   `XMLHttpRequest`, no `@font-face`. Proven by the offline context in item 14, not by eye.
3. **No URLs at all** in the file — which is why SVGs carry no `xmlns` (D5).
4. **Do not touch** `docs/mocks/vayulok-mock.html` or its two PNGs (item 16 proves it).
5. **Do not** create the file in `public/` or `src/pages/`; **do not** touch
   `src/pages/vayulok/index.tsx`.
6. **Do not** create a branch. Commit on `feat/vayulok-update`, push there, never `stack` or
   `main`, no PR.
7. Tokens are `#d1f470` and `#1a3a2a` — the drifted `#d0f070` and `#183828` must appear nowhere.
8. Lime never goes on a third-party mark, including the provider-attribution line.
