# Implementation Plan — port the shipped Subscribe / Contribute / Share footer into the VayuLok mock

**Branch:** `fix/vayulok-subscribe-inline` (verified active: `git -C /projects/sandbox/wecare-digital branch --show-current`).
Do not switch branches. Do not touch `feat/vayulok-update` or `vayulok-preview`. There is no `main`;
`stack` is the default and must not be committed to. No PR.

**Files in scope — and nothing else:**

- `docs/mocks/vayulok-live-mock.html` (edit this one)
- `docs/mocks/vayulok-final-v3.html` (byte-identical twin; produced by copy)
- `tools/browser/vayuloksubcheck.js` (harness extension)
- the five committed PNGs the harness regenerates (see step 12)

**Do NOT modify anything under `src/`.** Do not embed a Google Maps/Cloud key. Do not read AWS
Secrets Manager — never run `aws secretsmanager get-secret-value` / `batch-get-secret-value`. No
credential, key or token in any file. Leave `.vl-keygate` (grey scrim + "Maps key" card + `Load`)
exactly as it is: it is load-bearing for zero-network.

---

## 0. Facts established by reading and by measuring (read before step 1)

| Fact | Evidence |
| --- | --- |
| Both twins hash to `0c2ffb479014ff06fc1bb4a6657d07e18f82bbcd`, 1953 lines each | `git hash-object docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html` |
| `diff` and `cmp` are NOT installed | prior pass recorded it; use `git hash-object` (and `git --no-pager diff --no-index` as a cross-check) |
| The repo's unit gates do **not** cover `docs/mocks` | `grep -rln 'docs/mocks' src tests scripts .github package.json vitest.config.ts` → **no hits** |
| The only real verification for these files is the browser harness | `tools/browser/vayuloksubcheck.js`; `tools/browser/README.md` |
| Harness deps and Chromium are already present | `tools/browser/node_modules/` populated; `/opt/playwright/chromium-1232` |
| **Baseline is green: 432/432 assertions pass** at 1280×900 and 390×844 across both twins | `node tools/browser/vayuloksubcheck.js` → exit 0 |
| Commit `3fbfb180` item (a) — the location search — **is wired and works**; confirmed by running the harness, not by reading | 30+ passing assertions drive `#vl-search`: typing opens the list, `mumbai` matches 2 places on the **address**, ArrowDown/ArrowUp move and clamp, Enter commits, Escape closes without undoing, click commits, all four target nodes update, no-match line is not an option, no overflow with the list open |
| Commit `3fbfb180` item (b) — the old inline subscribe form — is gone from the DOM and from the CSS; the only survivors are **retirement comments** | `vl-sub-dial` 0 hits, `vl-sub-phone` 0 hits; `vl-pf-code`/`vl-pf-num` 1 hit each, both inside the comment at lines 318-319; harness already proves 0 elements, 0 CSS rules, 0 live JS identifiers |
| `.vl-contribute{padding-top:24px;border-top:...}` (line 913) is **fully shadowed** by `.vl-app-left > .vl-section` (line 463, two classes beats one) | computed `padding-top` is 40px, not 24px |
| The shipped Share WhatsApp control's href is `api.whatsapp.com`, a **second** remote host | `src/config/share.ts` `whatsappShareHref` |
| `.pill` itself computes **13.33px/400** (UA button font); the 17px/700 lives on `.pill-action` | measured in Chromium — assert the type on the inner span, never on the pill |

**Measured heights of the four ported controls** (Chromium, Inter-absent fallback, 1280×900):

| Control | height | radius | font | border | fill | padding |
| --- | --- | --- | --- | --- | --- | --- |
| `.blog-wa-subscribe` | **47px** | 999px | 17px/700 | **0px** | `rgb(209,244,112)` | `12px 20px` |
| `.pill` (Contribute) | **52px** | 999px | 17px/700 *(on `.pill-action`)* | 2px `rgb(26,58,42)` | `rgb(209,244,112)` | `0 28px` |
| `.share-btn` | **44px** × 44px | 50% | — | 2px `rgb(229,231,235)` | `#fff` | `0` |
| `.bc-choice-face` | **40px** | 999px | 15px/700 | 2px `rgb(229,231,235)` | `#fff` | `8px 16px` |

The 47px and 52px values are *derived from padding + line box*, not declared heights, so the harness
asserts the **declared** properties exactly and the height only as `>= 44` (the repo's AAA 2.5.5 bar),
with 47 recorded in a comment. Hardcoding 47 would make the suite brittle against a font-fallback
change on CI. **Needs verification during implementation:** re-measure and record the actual numbers.

---

## 1. Design decisions (made here, with reasons — do not re-open)

**D1. The Subscribe control stops being ROLE 1 and becomes its own role.** The shipped
`.blog-wa-subscribe` (`src/pages/post/[slug].tsx:772-782`) is a 999px pill, 17px/700, padding
`12px 20px`, **no border**. The mock's current `#vl-sub-wa` carries `.vl-btn` (ROLE 1: 13px radius,
16px/500, `0 24px`, 2px border). Those are different shapes, and the brief's goal is "match the real
site, do not reinvent". So the anchor gets a new class `.vl-wa-subscribe` = **ROLE 8**.

**D2. The Contribute button also stops being ROLE 1.** The shipped Contribute is
`<PillButton as="button" type="submit" action="Contribute">`, i.e. `.pill` + `.pill-action`
(`src/components/PillButton.tsx:202-258`): 999px, min-height 52px, padding `0 28px`, 2px `#1a3a2a`,
lime, label 17px/700. The owner's screenshot says "lime pill 'Contribute' with dark border" — a pill,
not the 13px-radius `.btn-lg`. So it becomes `.vl-pill` / `.vl-pill-action` = **ROLE 9**.
*Alternative rejected:* leaving it on `.vl-btn` — it would keep the mock's internal ROLE 1 doctrine
tidy while making the mock disagree with the real site, which is the whole defect being fixed.

**D3. ROLE 1 (`.vl-btn`) survives with exactly one user: `Load` in `.vl-keygate`.** That control is
mock furniture, is not part of the ported blog footer, and the brief orders `.vl-keygate` left exactly
as is. The roles comment must say ROLE 1 now has one member *by design*, so a future pass does not
"fix" it by re-flattening the pills into it.

**D4. The Share WhatsApp control is a `<button>`, not an `<a>`, and all three are inert.** The shipped
primary is an `<a href="https://api.whatsapp.com/send?text=...">`. The task's HARD CONSTRAINT allows
exactly one external reference — the `wa.me` subscribe href — so a second remote host is not
available. A `<button type="button">` renders identically (`.share-btn` styles both, and it declares
`font:inherit`), stays keyboard-focusable, and keeps its `aria-label`. The brief itself describes the
row as "three `.share-btn` buttons". Record all three as **inert** in a comment, as the brief permits.

**D5. The `.share-fallback` input is NOT ported.** It exists only for the real `onCopy` catch path
(a refused clipboard write), which cannot occur with no handler; it is `hidden`, so it renders nothing;
and its `value={url}` would put a second `https://` literal in a file allowed exactly one. Drop the
element and its rule, and say why.

**D6. The row is hard-classed `is-native is-clip`.** The shipped CSS hides `.share-native` and
`.share-copy` until a `useEffect` adds those classes after feature-detecting `navigator.share` /
`navigator.clipboard`. Port the three rules verbatim *and* put both state classes on the row in the
markup — that is exactly the state a browser with both APIs renders, which is the state the owner's
screenshot was taken in. This keeps the shipped CSS unmodified instead of deleting rules to force
visibility.

**D7. `.vl-bc-title` gains `text-transform:uppercase`.** `BlogContribution.tsx:260-263` declares it,
so the real site renders **CONTRIBUTE**, which is what the screenshot shows and what the owner's note
calls "the CONTRIBUTE eyebrow". The DOM text stays the word `Contribute`. The file's existing comment
forbidding CSS uppercase was about the owner rejecting the *word* "Contribution" — not about casing;
rewrite that comment to record the distinction so the rule is not read as banning the ported
declaration.

**D8. The custom-amount block (`.bc-custom*`, "Amount in rupees") is NOT ported.** The shipped
component renders it only when `choice === OTHER` (`BlogContribution.tsx:189-215`); the mock is static
with the first chip selected, so the real site renders nothing there. Porting it would put on screen a
state the real page does not show in this state, which is the opposite of matching the real site.
The owner's copy list names "Amount in rupees" — it is the label of this conditional block, so it is
covered by this decision rather than omitted by accident. **Flag:** if the owner wants the "Other"
state illustrated, that is a second static state and a separate change.

**D9. The two dividers come from the existing left-column section rhythm, not from new rules.**
`.vl-app-left > .vl-section{margin-top:56px;padding-top:40px;border-top:1px solid var(--hair)}`
(line 463) already draws a hairline above every `.vl-section` in the column. Putting Contribute and
Share in `.vl-section` siblings yields exactly the two dividers in screenshot order with no new
layout — which is what the brief asks for. The shipped `.bc` / `.post-share` rhythm is `44px/24px`;
it is deliberately **not** ported, because this mock's column rhythm owns vertical spacing and two
competing rhythms in one column is the defect, not the fidelity.

**D10. `margin-top:44px` from `.blog-wa-subscribe` is deliberately dropped.** `.vl-sub-head` already
supplies `margin-bottom:20px` above the anchor and the section rhythm supplies the rest. Record the
omission inline, the way the file already records the dropped `min-height:91px`.

**D11. Copy (settled by owner decisions received during planning — do not re-litigate):**
- The contribute paragraph is **exactly** this one sentence, owner-supplied, in the existing
  `<p class="vl-bc-copy">` slot under `<h2 class="vl-bc-title">Contribute</h2>`:

  > If you found this useful, you&#8217;re welcome to make a small voluntary contribution.

  It replaces **both** the mock's current sentence ("If VayuLok is useful to you, a small voluntary
  contribution helps keep the monitor network and the forecasts running.") **and** the shipped blog
  sentence ("If this article was useful, …"). Neither may appear anywhere in the file.
  **The apostrophe in "you're" is U+2019 RIGHT SINGLE QUOTATION MARK, not ASCII `'`.** Encode it as
  `&#8217;`, matching the file's existing numeric-entity convention (`&#8377;` for ₹). A literal
  UTF-8 `’` is also acceptable, but a straight quote is not. One sentence, full stop, no leading or
  trailing whitespace inside the `<p>`. Port BlogContribution's *structure, classes and styling* —
  not its prose.
- Everything else is verbatim shipped copy: `Subscribe on WhatsApp`, the `CONTRIBUTE` eyebrow,
  `Choose an amount`, `Contribute`, the `SHARE` label, the aria-label `Contribution amount`, and the
  three share `aria-label`s.
- **Delete** both `.vl-placeholder` blocks (they describe microcopy that does not exist in either
  shipped component), their CSS, and the comments that cite them as precedent.
- **Delete** the head fragment "Pick the places you want watched." Keep the h2
  "Get air-quality alerts for your place" unchanged.
- Invent nothing.

**D12. The amounts are ₹50 / ₹200 / ₹400 / Other, with ₹50 pre-selected — and this DIVERGES from the
shipped config on purpose.** Superseding owner instruction (2026-10-02). The live values are
`src/config/contribution.ts` → `CONTRIBUTION_PRESETS_PAISE = [20000, 40000, 60000]` (= ₹200/₹400/₹600)
and `amplify/functions/shared/lambda_utils/ecommerce/blog_contribution.py:92` →
`CONTRIBUTION_PRESETS_PAISE = (20000, 40000, 60000)`. The two are declared separately **on purpose**
so the browser cannot widen the server's trusted amount, and three tests fail if they drift
(`src/test/BlogContribution.test.tsx`, `src/test/BlogDesign.test.tsx`,
`tests/test_blog_contribution.py`). Changing the real amounts is a larger, unauthorised change, so:
- `src/` and `amplify/` stay **untouched**.
- The mock's radio values are the plain rupee numbers `50` / `200` / `400` — **not paise** — because
  they no longer mirror a paise config and a paise literal would falsely imply they do.
- There is **no** assertion comparing the mock's faces to `CONTRIBUTION_PRESETS_PAISE`. Any such
  assertion from an earlier draft is dropped.
- An HTML comment at the amount block must record: owner-set for the mock, 2026-10-02, currently
  divergent from `CONTRIBUTION_PRESETS_PAISE`, and name both file paths above as what must change for
  the site to follow.

**Flag for the owner (carry into the final report, do not block on it):** `₹50` is the *lowest*
preset and it is the pre-selected default, which is revenue-affecting. The first-chip-checked
behaviour mirrors the shipped component (`useState(CONTRIBUTION_PRESETS_PAISE[0])`), so the pattern is
faithful — but the owner should confirm they want the cheapest option to be the default. A rollout of
these amounts to the real site would touch six files: the two mock twins, `src/config/contribution.ts`,
`amplify/functions/shared/lambda_utils/ecommerce/blog_contribution.py`, and the three tests named
above.

---

## 2. Exact CSS to port, with source locations

### Source 1 — `src/pages/post/[slug].tsx` → `.vl-wa-subscribe` (ROLE 8)

| Declaration | Source |
| --- | --- |
| `display:inline-flex;align-items:center;gap:10px` | `:773` |
| `margin-top:44px` | `:773` — **omitted**, see D10 |
| `padding:12px 20px;border-radius:999px` | `:774` |
| `background:#d1f470;color:#1a3a2a;font-weight:700;font-size:17px` | `:775` |
| `text-decoration:none;transition:transform .2s,box-shadow .2s` | `:776` |
| `.vl-wa-subscribe svg{flex:0 0 auto}` | `:778` |
| `:hover,:focus-visible{transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.18)}` | `:779-781` |
| `:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}` | `:782` |

Note: `#d1f470` = `var(--lime)`, `#1a3a2a` = `var(--green)`. Use the tokens where the file already
does, and cite the literal in the comment. **There is no border — that is the shipped value**; the
file's ROLE 1 note that "the border is the only thing giving the control an edge" applies to `.vl-btn`
and must not be copied onto ROLE 8.

### Source 2a — `src/components/BlogContribution.tsx` → `.vl-bc-*` (already ported; one gap)

Verified declaration-for-declaration against lines 260-307: `.vl-bc-copy` (`:264-267`),
`.vl-bc-fieldset` (`:269`), `.vl-bc-legend` (`:270`), `.vl-bc-choices` (`:271`), `.vl-bc-choice`
(`:273`), `.vl-bc-radio` (`:274`), `.vl-bc-choice-face` (`:275-280`), `:hover` (`:281-283`),
`:checked` (`:285`), `:focus-visible` (`:287`), `.vl-bc-submit-wrap` (`:300`) and the
reduced-motion pair (`:305-307`) **all already match exactly**. The single missing declaration is
`text-transform:uppercase` on `.vl-bc-title` (`:260-263`) — see D7.

### Source 2b — `src/components/PillButton.tsx` → `.vl-pill` / `.vl-pill-action` (ROLE 9)

| Declaration | Source |
| --- | --- |
| `display:inline-flex;align-items:center;justify-content:center;isolation:isolate` | `:203` |
| `min-height:52px;box-sizing:border-box` | `:204` |
| `border:2px solid #1a3a2a;border-radius:999px;background:#d1f470` | `:205` |
| `padding:0 28px;cursor:pointer` | `:206` |
| `font-family:inherit;text-decoration:none` | `:207` |
| `transition:background-color .2s,transform .2s,box-shadow .2s` | `:208` |
| `.vl-pill-action{display:inline-flex;align-items:center;justify-content:center;min-inline-size:0;color:#1a3a2a;font-size:17px;font-weight:700;line-height:1.2;text-align:center}` | `:219-224` |
| `:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.18)}` | `:233-235` |
| `:active{transform:translateY(0)}` | `:236` |
| `:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}` | `:241` |
| `@media(max-width:360px){.vl-pill{padding:0 18px}.vl-pill-action{font-size:16px}}` | `:250-253` |
| `@media(prefers-reduced-motion:reduce){.vl-pill{transition:none}.vl-pill:hover{transform:none;box-shadow:none}}` | `:256-259` |

Drop the `:not([disabled]):not([aria-disabled='true'])` qualifiers from `:hover`/`:active`: the mock's
pill is never disabled and the file's house style has no such state. Record the omission.
`.pill`'s `:disabled`/`[aria-busy]` rules (`:246-247`) are not ported for the same reason.
**The 360px breakpoint is below both harness viewports (1280, 390) — ported for fidelity, not covered
by an assertion. Flag as needs verification during implementation** (spot-check at 360 manually or add
a third viewport).

### Source 3 — `src/components/ShareLinks.tsx` → `.vl-share-*` (ROLE 10)

CSS is **styled-jsx inside the component**, lines 157-256 — *not* in `src/styles/inner-pages.css`.
The brief points at `inner-pages.css`; the only `.share-btn` there is lines 1947-1968, scoped under
`.layout .main-content .pay-page` / `.pay-link-page`, a 13px-radius white pay-page button with
`!important`. **It is a different control and must not be used.** Correcting the brief's pointer.

| Declaration | Source |
| --- | --- |
| `.vl-share-row{display:flex;align-items:center;flex-wrap:wrap;gap:12px}` | `:157` |
| `.vl-share-label{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a;margin-inline-end:2px}` | `:158` |
| `.vl-share-btn{position:relative;display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;flex:0 0 auto;padding:0;box-sizing:border-box;border:2px solid #e5e7eb;border-radius:50%;background:#fff;color:#1a3a2a;font:inherit;cursor:pointer;transition:background-color .2s,border-color .2s,transform .2s,box-shadow .2s}` | `:175-183` |
| `:hover{border-color:#1a3a2a;background:#d1f470;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}` | `:187-190` |
| `.is-primary{background:#d1f470;border-color:#1a3a2a}` / `.is-primary:hover{background:#fff;border-color:#1a3a2a}` | `:197-198` |
| `:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}` | `:201` |
| `.vl-share-btn svg{width:19px;height:19px;flex:0 0 auto;display:block}` | `:202` |
| `.vl-share-tip{position:absolute;bottom:calc(100% + 8px);left:50%;padding:5px 9px;border-radius:8px;background:#1a3a2a;color:#fff;font-size:12px;font-weight:600;letter-spacing:.01em;line-height:1.3;white-space:nowrap;pointer-events:none;opacity:0;transform:translateX(-50%) translateY(4px);transition:opacity .2s,transform .2s}` | `:211-219` |
| `:hover .vl-share-tip,:focus-visible .vl-share-tip{opacity:1;transform:translateX(-50%) translateY(0)}` | `:220-221` |
| `.is-done .vl-share-tip{...}` and `.is-done{background:#d1f470;border-color:#1a3a2a}` | `:224-225` |
| `.vl-share-btn svg circle,… svg line,… svg polyline,… svg path:not([fill]){fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}` | `:228-230` — **mandatory**: without it the native-share circles render as black discs |
| `.vl-share-native,.vl-share-copy{display:none}` + `.is-native`/`.is-clip` reveals | `:234-236` |
| `.vl-share-status{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}` | `:239` |
| `.share-fallback` | `:240-244` — **not ported**, see D5 |
| `@media(prefers-reduced-motion:reduce){.vl-share-btn,.vl-share-tip{transition:none}.vl-share-btn:hover{transform:none;box-shadow:none}…{transform:translateX(-50%)}}` | `:245-256` |

`.is-done` has no user in a static mock (nothing sets it). Port it anyway, with a comment, because it
is the resting half of the `.is-primary`/`.is-done` pair the shipped CSS declares together and
deleting half a state pair is how the `.vl-sub-action` class of defect starts. **Flag:** this is the
one place the file's "no dormant rules" rule is deliberately bent; say so explicitly in the comment so
a reviewer sees a decision rather than an oversight.

`.vl-share-tip` carries `calc(100% + 8px)` — a `+` **inside CSS in `<head>`**, which the harness's
"no `+` in the section" probe does not walk (it walks text nodes and attributes under `.vl-vayulok`).
Confirmed safe; do not introduce a `+` into any new DOM text or attribute.

---

## 3. Ordered steps

- [ ] **1. Replace the Subscribe anchor's markup and add the ROLE 8 rule.**
      In `docs/mocks/vayulok-live-mock.html`, replace the anchor at lines 1306-1307 with the shipped
      `.blog-wa-subscribe` form, keeping `id="vl-sub-wa"` (the harness and the one-permitted-remote-
      reference assertion both name it) and the existing `href`/`target`/`rel`:
      `<a class="vl-wa-subscribe" id="vl-sub-wa" href="https://wa.me/message/BEA3HNW3LNM3A1" target="_blank" rel="noopener noreferrer" aria-label="Subscribe on WhatsApp"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" width="20" height="20"><path fill="currentColor" d="…"/></svg><span>Subscribe on WhatsApp</span></a>`
      — copy the `d` attribute **verbatim** from `src/pages/post/[slug].tsx:519` (one long path, do not
      retype it). Add the ROLE 8 rule block from §2 Source 1 where the SUBSCRIBE CSS section's
      "THE PANEL'S ONE CONTROL" comment sits (lines 864-871), replacing that comment with one that
      cites `[slug].tsx:772-782`, states the no-border value is shipped, and records the dropped
      `margin-top:44px` (D10).
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: `node tools/browser/vayuloksubcheck.js docs/mocks/vayulok-live-mock.html` — expect the
      retired ROLE 1 assertions for `#vl-sub-wa` to FAIL at this point (they are rewritten in step 8);
      every other assertion, including `exactly 1 request`, `zero console errors` and
      `exactly ONE remote reference, the wa.me href`, must still pass.

- [ ] **2. Set the contribution amounts, the paragraph and the eyebrow casing.**
      (a) **Amounts (D12).** Replace the four radio/face pairs at lines 1329-1344 with, in this order:
      `value="50"` / `&#8377;50` (**`checked`**), `value="200"` / `&#8377;200`, `value="400"` /
      `&#8377;400`, `value="other"` / `Other`. Keep `name="vl-amount"`, `class="vl-bc-radio"` and the
      `.vl-bc-choice` / `.vl-bc-choice-face` wrapping exactly as the port requires. Add the HTML
      comment D12 requires: owner-set for the mock (2026-10-02), divergent from
      `CONTRIBUTION_PRESETS_PAISE`, naming `src/config/contribution.ts` and
      `amplify/functions/shared/lambda_utils/ecommerce/blog_contribution.py:92` as what must change
      for the site to follow, and stating that neither is edited here.
      (b) **Paragraph (D11).** Replace the whole `<p class="vl-bc-copy">` body (lines 1320-1323) with
      the single owner-supplied sentence, using `&#8217;` for the apostrophe:
      `If you found this useful, you&#8217;re welcome to make a small voluntary contribution.`
      (c) **Eyebrow (D7).** Add `text-transform:uppercase` to `.vl-bc-title` (lines 888-891) and
      rewrite the two comments that forbid it (lines 884-887 and 1436-1438) to record that the
      rejected thing was the *word* "Contribution", not the casing.
      **Text greps are not a valid check here.** `999px` appears 10 times and `600` appears 9 times
      (font weights at lines 202/209/544/564/894 and PIN codes at 1777-1786), so `grep 99` and
      `grep 600` are both useless. Retirement is proved in the DOM by step 8: no `.vl-bc-choice-face`
      text matches `/₹(99|249|499|600)\b/` and no `.vl-bc-radio` value is in
      `{99, 249, 499, 600, 20000, 40000, 60000}`.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: `grep -n -- '8377;99\|8377;249\|8377;499\|8377;600\|value="99"\|value="249"\|value="499"\|this article was useful\|monitor network and the forecasts' docs/mocks/vayulok-live-mock.html`
      → no output (anchored cross-check only); the real verification is step 8's DOM assertions.

- [ ] **3. Swap the Contribute submit onto the ported pill (ROLE 9).**
      Replace `<button class="vl-btn" type="submit">Contribute</button>` (line 1349) with
      `<button class="vl-pill" type="submit"><span class="vl-pill-action">Contribute</span></button>`,
      mirroring `PillButton`'s own markup. Add the `.vl-pill` / `.vl-pill-action` rules from §2
      Source 2b immediately after `.vl-bc-submit-wrap` (line 912), with a comment citing
      `PillButton.tsx:202-258`, recording that the type lives on the inner span (the pill box itself
      computes the UA 13.33px/400), and recording the dropped `:disabled`/`[aria-busy]` qualifiers.
      Add `.vl-pill` to the `prefers-reduced-motion` transition list (line 950) and add the
      `@media(max-width:360px)` block at the end of the breakpoints section.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: as step 1 — the `.vl-bc-submit-wrap .vl-btn` assertions now fail pending step 8; nothing
      else regresses.

- [ ] **4. Add the Share row as a new left-column `.vl-section` (ROLE 10).**
      Insert, immediately after the Contribute `</section>` (line 1358) and still inside
      `.vl-app-left`, a `<div class="vl-section vl-share">` holding the ported row — mirroring the
      shipped `<div className="post-share"><ShareLinks/></div>`, which carries no heading:
      `<div class="vl-share-row is-native is-clip">` → `<span class="vl-share-label">Share</span>`;
      `<button type="button" class="vl-share-btn is-primary" aria-label="Share this page on WhatsApp">`
      with the WhatsApp SVG (`ShareLinks.tsx:108-110`) + `<span class="vl-share-tip" aria-hidden="true">WhatsApp</span>`;
      `<button type="button" class="vl-share-btn vl-share-native" aria-label="Share this page using your device">`
      with the three-circles-two-lines SVG (`:120-123`) + tip `Share`;
      `<button type="button" class="vl-share-btn vl-share-copy" aria-label="Copy link to this page">`
      with the link SVG (`:137-139`) + tip `Copy link`;
      then `<span class="vl-share-status" role="status" aria-live="polite"></span>`.
      Copy every SVG **verbatim** (same `viewBox`, `aria-hidden`, `focusable="false"`, same
      geometry attributes, no explicit fill/stroke on the drawn icons). Add the §2 Source 3 CSS as a
      new `SHARE` section after the CONTRIBUTE CSS block, and add `.vl-share-btn` + `.vl-share-tip` to
      the reduced-motion block. The comment must state: all three controls are **inert** (D4), the
      primary is a `<button>` not an `<a>` because only one external reference is permitted, and
      `is-native is-clip` is hard-classed because that is the state the real page renders when both
      APIs exist (D6).
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: step 8's harness block; interim, confirm the harness still reports
      `exactly ONE remote reference, the wa.me href`, `no horizontal overflow`, `zero console errors`.

- [ ] **5. Delete both `.vl-placeholder` blocks, their CSS and the comments that cite them.**
      Remove the markup at lines 1312-1316 and 1353-1357, the `.vl-placeholder` and
      `.vl-placeholder b` rules (lines 917-922) and the comment above them (lines 913-916). Then fix
      every cross-reference so none points at deleted markup: line 429 (`.vl-placeholder note`),
      lines 866-869 (the measured "20px below it to the placeholder rule" note), and lines 1273-1277
      (the "see the two `.vl-placeholder` blocks" precedent). Replace the precedent citation with the
      rule itself — this file does not invent copy — rather than pointing at an absent block.
      Rationale (owner decision): both placeholders described microcopy that exists in neither shipped
      component. `.blog-wa-subscribe` is a bare link with no consent/purpose text, and
      `BlogContribution.tsx`'s only user-facing strings are "Choose an amount", the aria-label
      "Contribution amount" and the conditional "Amount in rupees".
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: step 8 asserts no `PLACEHOLDER` text survives in the rendered page; the harness must also
      still report `zero console errors` and the unchanged request count.

- [ ] **6. Delete the head fragment and the selectors it orphans.**
      Remove `<p>Pick the places you want watched.</p>` (line 1278) and the comment block above it
      (lines 1269-1277). Keep the `h2` "Get air-quality alerts for your place" (line 1267) exactly.
      That `<p>` is the only user of `.vl-sub-head>p` (line 863) and of the two 767px tweaks
      `.vl-sub-head{display:block}` / `.vl-sub-head>p{margin-top:10px}` (lines 945-946) — delete all
      three per the file's own "unused roles are deleted rather than left dormant" rule. Keep
      `.vl-sub-head` (line 860) and `.vl-sub-head>div` (line 861): the `margin-bottom:20px` is
      load-bearing for the gap above the pill.
      **Grep EVERY occurrence of each selector before deleting** — the recorded hazard is
      `.vl-sub-action`, which was once declared twice in disjoint blocks so that both applied and
      neither looked wrong on its own. Current counts to work from: `vl-sub-head` 6, `vl-placeholder` 7,
      `vl-cell` 3, `vl-sub-action` 4, `vl-sub-status` 3, `vl-verify-row` 2, `vl-btn-quiet` 4, `vl-pf` 2
      — all but the `.vl-sub-head` ones are comment-only retirement notes.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: step 8 asserts the string "Pick the places" is absent from the rendered page, and that
      `.vl-sub-head`'s computed `margin-bottom` is still 20px.

- [ ] **7. Clean the remaining orphaned selectors and the retirement comments.**
      (a) Delete the fully-shadowed `.vl-contribute{padding-top:24px;border-top:1px solid var(--hair)}`
      (line 913) and remove `vl-contribute` from the section's class list (line 1318) — the section
      keeps its 40px/hairline from `.vl-app-left > .vl-section`, measured, so nothing moves.
      (b) Collapse the `.vl-pf` / `.vl-pf-code` / `.vl-pf-num` retirement comment (lines 316-334) to
      one or two sentences that keep the one durable fact — `src/components/PhoneField.tsx` and
      `src/lib/dialCodes.ts` are the source if a divided calling-code field is ever wanted again —
      and drop the enumeration of dead class names. This is the residual `vl-pf-code` / `vl-pf-num`
      reference the brief asked to clean; it is comment-only, so this is hygiene, not a fix.
      (c) Rewrite the roles table (lines 196-203) to add **ROLE 8** `.vl-wa-subscribe` (999px /
      17px-700 / no border / lime / `12px 20px`), **ROLE 9** `.vl-pill` + `.vl-pill-action` (999px /
      52px / 17px-700 / 2px #1a3a2a / `0 28px`) and **ROLE 10** `.vl-share-btn` (44×44 / 50% / 2px
      #e5e7eb, `.is-primary` lime + #1a3a2a), each with its `file:line` citation, and amend ROLE 1 to
      record that it now has exactly one member — `Load` — by design (D3), so no later pass
      re-flattens the pills into it. Keep role numbers stable; do not renumber 1-7.
      Files: `docs/mocks/vayulok-live-mock.html`
      Verify: `node tools/browser/vayuloksubcheck.js docs/mocks/vayulok-live-mock.html` — the
      `.vl-contribute` deletion must not change the section's computed `padding-top` (40px) or its
      `border-top-width` (1px); confirm via the new assertion added in step 8.

- [ ] **8. Extend `tools/browser/vayuloksubcheck.js` to the new roles and the new copy rules.**
      One file, following its existing conventions (`record()`, `probe()`, a `--json` flag,
      `process.exit(1)` on any failure, a header comment explaining *why* each block exists). Changes:
      1. `ROLE1_BUTTONS` → `[[ 'Load', '#vl-keyload' ]]` only. Replace the two now-vacuous
         "all action buttons share one height/font" cross-assertions with an assertion that ROLE 1 has
         exactly one member, citing D3 so the reduction reads as intended.
      2. Retire the `(c'')` pairwise WhatsApp-vs-Contribute parity block and the
         `both controls carry the SAME .vl-btn class` assertion — they asserted a shape the real site
         does not have. Replace with per-role blocks, one assertion per property:
         **ROLE 8** on `#vl-sub-wa`: `borderRadius` 999px, `paddingTop/Bottom` 12px,
         `paddingLeft/Right` 20px, `fontSize` 17px, `fontWeight` 700, `borderTopWidth` **0px**,
         `backgroundColor` `rgb(209, 244, 112)`, `color` `rgb(26, 58, 42)`, `textDecorationLine`
         `none`, `height >= 44` (measured 47), exactly **1** client rect at both widths (no wrap), and
         an inline `<svg>` first child with a `path[fill="currentColor"]`.
         **ROLE 9** on `.vl-bc-submit-wrap .vl-pill`: `height` 52, `borderRadius` 999px,
         `borderTopWidth` 2px `rgb(26, 58, 42)`, `backgroundColor` `rgb(209, 244, 112)`,
         `padding` `0px/28px`; and the type read from `.vl-pill-action` — 17px/700,
         `lineHeight` 20.4px (1.2×17) — explicitly **not** from the pill box, with a comment recording
         that the pill box computes the UA 13.33px/400 and that reading it there is the trap.
         **ROLE 10** on the three `.vl-share-btn`: all 44×44, `borderRadius` 50%,
         `borderTopWidth` 2px, uniform `top`/`bottom` (one row, one role), `.is-primary` fill
         `rgb(209, 244, 112)` + border `rgb(26, 58, 42)` and the other two fill `rgb(255, 255, 255)`
         + border `rgb(229, 231, 235)`; each has a non-empty `aria-label`; each contains exactly one
         `<svg>` sized 19×19; all three are keyboard-focusable via `page.focus`; the drawn icons'
         `circle`/`line`/`polyline` compute `fill:none` and `stroke` = the button's `color`.
      3. Keep the existing proofs that still hold and must not be weakened:
         `exactly ONE rule declares .vl-btn`, `subscribe panel holds exactly one control`
         (= `vl-sub-wa`), `no form/input/button left in the panel`,
         `exactly ONE remote reference, the wa.me href`, `no "+" survives in the section`,
         `zero <link> elements`, `zero <dialog> / role=dialog / aria-modal`,
         `nothing is position:fixed`, `no horizontal overflow`, `NO dialog fired`,
         `exactly 1 request`, `zero console/page errors`, and the whole search block.
      4. New content assertions:
         - the four `.vl-bc-choice-face` texts are exactly `₹50`, `₹200`, `₹400`, `Other`, **in that
           order**;
         - exactly 4 `.vl-bc-radio`, exactly one `:checked`, and the checked one's value is `50` and
           its face text is `₹50`;
         - no face text matches `/₹(99|249|499|600)\b/` and no radio `value` is in
           `{99, 249, 499, 600, 20000, 40000, 60000}` — DOM-level, because `999px` (10 hits) and `600`
           (9 hits, font weights and PIN codes) make a text grep useless;
         - **no** assertion compares the faces to `CONTRIBUTION_PRESETS_PAISE` — the divergence is
           intentional (D12); if an earlier draft of the harness grew one, delete it;
         - the `.vl-bc-copy` text equals exactly
           `If you found this useful, you’re welcome to make a small voluntary contribution.`
           (compare `textContent.trim()` with the whitespace collapsed, since the HTML may wrap);
         - `.vl-bc-copy` text contains `\u2019`, proving the apostrophe was not normalised to ASCII,
           and does **not** contain `'`;
         - `.vl-vayulok` innerText does **not** contain `this article was useful`;
         - innerText does **not** contain `monitor network and the forecasts`;
         - the checked face's computed `backgroundColor` is `rgb(209, 244, 112)` and `borderTopColor`
           `rgb(26, 58, 42)`, and an unchecked face's are `rgb(255, 255, 255)` / `rgb(229, 231, 235)`
           — asserted as a *difference* as well as against the literals, so "all four styled the same"
           cannot pass;
         - `.vl-share-label` renders uppercase (`textTransform === 'uppercase'`) and its text is
           `Share`; `.vl-bc-title` likewise, text `Contribute`;
         - `.vl-share-status` exists, has `role="status"` and `aria-live="polite"`, and is
           visually clipped (1×1);
         - `document.querySelectorAll('.vl-share-row > *')` yields label + 3 buttons + status, and
           all three buttons have a non-zero client rect at both widths (proving `is-native is-clip`
           actually reveals them);
         - **`.vl-vayulok` innerText does NOT contain `PLACEHOLDER`**;
         - **innerText does NOT contain `Pick the places`**;
         - `.vl-contribute` matches 0 elements **and** no CSS rule names it, while the Contribute
           section's computed `padding-top` is 40px and `border-top-width` 1px (proves step 7a moved
           nothing);
         - `.vl-sub-head` computed `margin-bottom` is 20px, and `.vl-sub-head > p` matches 0 elements
           and no CSS rule (proves step 6 removed the rule as well as the element).
      5. Add a fourth anchor screenshot, `{ name: 'vayulok-section-footer.png', w: 1440, h: 950, scrollTo: '.vl-share' }`,
         so the three ported blocks and both dividers are captured in one frame, and update the
         `SHOTS` docblock (lines 112-120) to describe it.
      Files: `tools/browser/vayuloksubcheck.js`
      Verify: `node tools/browser/vayuloksubcheck.js` — exit 0, **every** assertion passing at
      1280×900 and 390×844 for `docs/mocks/vayulok-live-mock.html`. The twin will still fail until
      step 9; run it against the live mock alone here:
      `node tools/browser/vayuloksubcheck.js docs/mocks/vayulok-live-mock.html`.

- [ ] **9. Copy the edited file over its twin and prove byte equality.**
      `cp docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html`
      Files: `docs/mocks/vayulok-final-v3.html`
      Verify: `git hash-object docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html | sort -u | wc -l`
      → `1`. Cross-check with
      `git --no-pager diff --no-index docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html; echo $?`
      → empty output and `0`. **`diff` and `cmp` are not installed — do not reach for them.**

- [ ] **10. Confirm the previous commit's search wiring still works (brief item a).**
      No code change expected: the handler, the dataset (`VL_PLACES`, 14 entries), the results
      listbox, the clamped arrow-key model, Enter/Escape and the four updated nodes are all present
      in the inline IIFE at lines 1773-1935, and the harness already drives them. This step is a
      confirmation, and a repair only if it regresses — the likeliest cause would be the new Share
      markup changing the absolutely-positioned overlay's containing block or widening the document.
      Files: none expected; `docs/mocks/vayulok-live-mock.html` only if a repair is needed.
      Verify: `node tools/browser/vayuloksubcheck.js` — the search block passes at both widths,
      including `selection updates the section heading`, `… the heading address`,
      `… the map preview name`, `… the map preview address`, `ArrowUp returns to row 1 and CLAMPS`,
      `Escape does not undo the committed selection`, and
      `no horizontal overflow with the list OPEN`.

- [ ] **11. Run the full verification pass on both twins.**
      In order:
      `npm install --prefix tools/browser --no-audit --no-fund` (idempotent; already satisfied here),
      then `node tools/browser/vayuloksubcheck.js` (both twins, both viewports — exit 0),
      then `node tools/browser/vayuloksubcheck.js --json > /dev/null` (shape check),
      then `npx tsc --noEmit`, `npm run lint` and `npx vitest run` as regression guards — they do not
      cover `docs/mocks`, so the only acceptable result is that they are **unchanged** from the
      pre-edit baseline. Capture the harness's final `N/N assertions passed` line as the evidence.
      Files: none
      Verify: harness exit 0 with every assertion passing on **both** `vayulok-live-mock.html` and
      `vayulok-final-v3.html`; `tsc`/`lint`/`vitest` no worse than baseline.

- [ ] **12. Regenerate the committed screenshots.**
      `node tools/browser/vayuloksubcheck.js --shots` — rewrites `vayulok-live-mock-{1280,390}.png`,
      `vayulok-final-v3-{1280,390}.png`, `vayulok-section-{desktop,scrolled,subscribe}.png` and the
      new `vayulok-section-footer.png`. The committed PNGs are already stale against the committed
      HTML (recorded in the previous pass), so new, shorter images are the correction, not a
      regression. Confirm the footer anchor actually shows, top to bottom: the lime Subscribe pill with
      its glyph, a hairline, CONTRIBUTE + the one-sentence paragraph, Choose an amount + the four
      chips `₹50 ₹200 ₹400 Other` with **₹50** filled lime, the lime Contribute pill, a hairline,
      SHARE + three circles with the first one lime.
      Files: the eight PNGs under `docs/mocks/`
      Verify: `node tools/browser/vayuloksubcheck.js --shots` exits 0 and prints the written paths;
      open `docs/mocks/vayulok-section-footer.png` and check it against the owner's screenshot order.

- [ ] **13. Commit, then push the branch.**
      Stage **only** the intended paths by name — `git add docs/mocks/vayulok-live-mock.html
      docs/mocks/vayulok-final-v3.html tools/browser/vayuloksubcheck.js` plus the regenerated PNGs
      and `.agents/tasks/vayulok-port-plan.md` — never `git add .` / `-A` / `-u`
      (`.kiro/steering/01-standing-authorization.md:57`). Commit with what + why. Then
      `git push -u origin fix/vayulok-subscribe-inline`, non-force. **No PR.** Do not push `stack`.
      Note the tension and that it is resolved by explicit owner instruction in this task:
      `.kiro/steering/git-workflow.md` is a single-branch policy and
      `01-standing-authorization.md:30` scopes `A2_REMOTE_CODE` to `git push origin stack`; the owner
      named this branch and asked for a plain push, which is the authority being relied on.
      Files: none (git only)
      Verify: `git status --short` lists only the intended paths before committing;
      `git -C . log --oneline -1` shows the new commit on `fix/vayulok-subscribe-inline`;
      `git rev-parse --abbrev-ref HEAD` is still `fix/vayulok-subscribe-inline`; the push reports the
      branch set up to track its own remote and no other ref is updated.

---

## 4. Needs verification during implementation (do not assume these are fine)

1. **The 47px Subscribe pill height and the 269.7px label width** were measured with Inter absent, so
   both depend on the fallback's metrics. Re-measure; assert declared properties exactly and height
   only as `>= 44`. At 390 the pill must still report **one** client rect inside `.vl-subscribe`'s
   16px padding — if the label wraps, the fix is the mock's column, not the shipped padding.
2. **`.vl-share-tip` horizontal overflow at 390.** The tips are absolute, `white-space:nowrap` and
   centred on 44px buttons; "Copy link" on the third button could push `documentElement.scrollWidth`
   past `clientWidth`. The harness's existing overflow assertion will catch it. If it fails, fix
   structurally (let the row wrap, or constrain the tip) — do not delete the tip, which is the only
   visible name on an icon-only control.
3. **The `@media(max-width:360px)` pill rule is below both harness viewports.** Spot-check at 360 or
   add a third viewport; it is currently unasserted.
4. **`.is-done` is ported with no user** — a deliberate exception to the file's "no dormant rules"
   rule (§2 Source 3). Confirm the comment says so, or a reviewer will read it as an oversight.
5. **The `.vl-share-status` live region is empty and inert.** Nothing writes to it, because nothing
   copies. Confirm the comment records that, and that it is still 1×1 clipped rather than occupying
   layout.
6. **Deleting `.vl-contribute`** is justified by a *computed* measurement (padding-top 40px, the
   `.vl-contribute` 24px being shadowed). Re-measure before and after; if the numbers move, the
   shadowing analysis was wrong and the rule must stay.
7. **`#vl-sub-wa`'s `aria-label`** duplicates the visible `<span>` text, matching the shipped anchor
   exactly. That is mild WCAG 2.5.3 redundancy rather than a violation (the name contains the visible
   text), and it is shipped — do not "fix" it here. Flag it for the owner if a reviewer raises it.
8. **The brief's pointer to `src/styles/inner-pages.css` for the Share CSS is wrong** (§2 Source 3).
   The real declarations are styled-jsx in `ShareLinks.tsx:157-256`. Confirm nothing was taken from
   the pay-page `.share-btn` at `inner-pages.css:1947-1968`.
9. **The ₹50 default is revenue-affecting and unconfirmed.** Owner-set amounts are ₹50/₹200/₹400 with
   the first chip checked, mirroring the shipped `useState(CONTRIBUTION_PRESETS_PAISE[0])`. The
   pattern is faithful, but it makes the *cheapest* option the default. Carry this to the final report
   for explicit confirmation; do not change it unilaterally.
10. **The mock's amounts now diverge from both live configs by design (D12).** Nothing under `src/` or
   `amplify/` may be touched to "reconcile" them, and no assertion may compare the two. Confirm the
   HTML comment naming `src/config/contribution.ts` and
   `amplify/functions/shared/lambda_utils/ecommerce/blog_contribution.py:92` is present, or the next
   reader will treat the divergence as a bug.
11. **Nothing wires this harness into CI.** `.github/workflows/build-test.yml:195-205` runs five
   browser scripts and `vayuloksubcheck.js` is not among them. Adding it is **out of scope** (scope is
   the two mocks plus `tools/browser/`) but it means nothing guards these files on the next pass —
   carry it to the review as a known gap, as the previous review already did.

---

## 5. Review contract

The implement/review loop's stop condition is unchanged: the reviewer writes
`/projects/sandbox/wecare-digital/.agents/tasks/vayulok-port-review.json` with
`{"verdict": "APPROVED" | "CHANGES_REQUESTED", ...}`, matching the shape of the existing
`.agents/tasks/vayulok-review.json`.
