# Verification note — Subscribe / Contribute / Share ported into the VayuLok mock twins

**Branch:** `fix/vayulok-subscribe-inline` (never left it; `feat/vayulok-update`, `vayulok-preview`
and `stack` untouched, no PR opened).
**Everything below was produced by EXECUTION, not by reading HTML.** Where a number appears, it was
measured in headless Chromium over `file://`.

> **The amounts/copy question raised during this pass was ANSWERED by the owner and is CLOSED:**
> ₹50/₹200/₹400 with ₹50 checked stand, the paragraph stands, both `.vl-placeholder` blocks stay
> deleted, and **no** parity assertion against `CONTRIBUTION_PRESETS_PAISE` is to be written. See §9.
>
> **A second owner correction landed mid-pass and is implemented:** the lime subscribe panel, its
> "VayuLok alerts" eyebrow and its "Get air-quality alerts for your place" h2 are all **removed**,
> because the live page has none of them. See §8a.

---

## 1. The exact command a reviewer should run

```sh
export PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH"   # npm is NOT on the default PATH here
cd /projects/sandbox/wecare-digital
npm install --prefix tools/browser --no-audit --no-fund      # idempotent; reported "up to date"
node tools/browser/vayuloksubcheck.js
```

**Result: `804/804 assertions passed`, process exit code `0`.** That is both twins
(`vayulok-live-mock.html` and `vayulok-final-v3.html`) at both viewports (1280x900 and 390x844).
`node tools/browser/vayuloksubcheck.js --json` also exits `0` and emits well-formed JSON.
Baseline before this pass was `432/432`; the suite grew by 372 assertions.

**`npm` is not on `$PATH` in this sandbox** — `which npm` fails; it lives at
`~/.nvm/versions/node/v22.23.3/bin`. That cost a round; hence the export line above.

---

## 2. Side-by-side: the real declarations vs the mock's computed values

Every "real" value is the declaration in the shipped source at the cited line. Every "mock" value is
`getComputedStyle` in Chromium. These are the assertion details, not a transcription.

### Subscribe — ROLE 8, `.vl-wa-subscribe` vs `.blog-wa-subscribe` (`src/pages/post/[slug].tsx:772-782`)

| Property | Real (declared) | Mock (computed) | |
| --- | --- | --- | --- |
| border-radius | `999px` | `999px` | ok |
| font-size / weight | `17px` / `700` | `17px/700` | ok |
| border | *none declared* | `0px` | ok |
| background | `#d1f470` | `rgb(209, 244, 112)` | ok |
| color | `#1a3a2a` | `rgb(26, 58, 42)` | ok |
| padding | `12px 20px` | `12px/12px`, `20px/20px` | ok |
| height | *not declared* | **47px** (asserted `>= 44`) | ok |

**The absence of a border is the shipped value**, not an omission — the retired ROLE 1 assertions
demanded `2px #1a3a2a` here, which is why a correct port first reported as a failure.
`height` is **not pinned to 47**: 47px is derived from padding + line box, so it moves with the font
fallback. It is asserted as `>= 44` (the AAA 2.5.5 bar) with 47 recorded in the detail string.

Also asserted: it is still an `<a>`; `href` is **exactly** `https://wa.me/message/BEA3HNW3LNM3A1`;
`target="_blank"`; `rel` contains both `noopener` and `noreferrer`; accessible name is exactly
`Subscribe on WhatsApp`; the visible `<span>` carries the same string; keyboard-focusable; one client
rect at both widths (the label does not wrap); not underlined.

**The glyph is asserted VERBATIM, not approximated.** The harness now reads
`src/pages/post/[slug].tsx` at run time, lifts the one `d` beginning `M17.47`, and compares the
mock's path to it character for character: `identical, 881 chars`. A retyped or truncated path fails.
(My first draft used a `> 1000` length floor, which was simply wrong — the real path is 881 chars.)

### Contribute — ROLE 9, `.vl-pill`/`.vl-pill-action` vs `.pill`/`.pill-action` (`src/components/PillButton.tsx:202-224`)

| Property | Real (declared) | Mock (computed) | |
| --- | --- | --- | --- |
| min-height | `52px` | `52px` | ok |
| border-radius | `999px` | `999px` | ok |
| border | `2px solid #1a3a2a` | `2px rgb(26, 58, 42)` | ok |
| background | `#d1f470` | `rgb(209, 244, 112)` | ok |
| padding | `0 28px` | `0px/0px`, `28px/28px` | ok |
| label font (**on the span**) | `17px` / `700` | `17px/700` | ok |
| label line-height | `1.2` | `20.4px` | ok |
| label colour | `#1a3a2a` | `rgb(26, 58, 42)` | ok |

**The type lives on the inner span and that is the trap.** `.vl-pill` is a `<button>`, so the pill
box itself computes the UA's **13.3333px** Arial. The harness asserts
`pill 13.3333px vs span 17px` as its own assertion, so if a later pass "simplifies" by moving the
font declaration onto the pill, that flips and the note above stops being a guess.

### Share — ROLE 10, `.vl-share-*` vs `.share-*`

**The brief's pointer was wrong and is corrected here.** The real declarations are **styled-jsx
inside `src/components/ShareLinks.tsx:157-256`**, not `src/styles/inner-pages.css`. That file does
contain a `.share-btn` at `1947-1968`, but it is scoped under `.pay-page`/`.pay-link-page` and is a
13px-radius white button with `!important` — a different control. **Nothing was taken from it.**

| Property | Real (declared) | Mock (computed) | |
| --- | --- | --- | --- |
| width x height | `44px` x `44px` | `44x44` (all three) | ok |
| border-radius | `50%` | `50%` | ok |
| border-width | `2px` | `2px` | ok |
| rest fill / border | `#fff` / `#e5e7eb` | `rgb(255,255,255)` / `rgb(229,231,235)` | ok |
| `.is-primary` fill / border | `#d1f470` / `#1a3a2a` | `rgb(209,244,112)` / `rgb(26,58,42)` | ok |
| icon size | `19px` x `19px` | `19px x 19px` | ok |

Row is vertically flush (`tops 1044.7 / bottoms 1088.7` — one row, one role). Exactly one
`.is-primary`, and it **is** the WhatsApp control; the primary's fill is asserted to **differ** from
the other two, so "all three styled the same" cannot pass. All three are keyboard-focusable
(driven via `page.focus`, verified by `document.activeElement`). The stroked icons compute
`fill:none` with `stroke` equal to the button's `color` — without that ported rule the native-share
mark renders as three black discs. Accessible names: `Share this page on WhatsApp`,
`Share this page using your device`, `Copy link to this page`.

---

## 3. Which share behaviours are inert — recorded explicitly, as the brief requires

**All three share controls are inert.** No clipboard write, no `navigator.share`, no navigation.
They are focusable, they carry their `aria-label`s and their hover/focus tips render, but nothing
happens on activation.

- **The WhatsApp share control is a `<button>`, not an `<a>` — a deliberate divergence.** The shipped
  primary is an anchor to `api.whatsapp.com`, a **second remote host**, and the task permits exactly
  one external reference (the `wa.me` subscribe href). A `<button type="button">` renders identically
  (`.vl-share-btn` styles both and declares `font:inherit`) and keeps its name and focusability.
- `.vl-share-status` is a real `role="status" aria-live="polite"` region, asserted 1x1-clipped and
  **empty** — nothing writes to it, because nothing copies.
- `.share-fallback` (`ShareLinks.tsx:240-244`) is **not ported**: it only serves the real `onCopy`
  catch path, it is `hidden`, and its `value={url}` would add a second absolute-URL literal.
- `.is-done` is ported **with no user** — the one place the file's "no dormant rules" rule is
  deliberately bent, because it is the resting half of the `.is-primary`/`.is-done` pair and
  deleting half a state pair is how the duplicate `.vl-sub-action` defect started. Commented as a
  decision so a reviewer does not read it as an oversight.
- The row is hard-classed `is-native is-clip`, because the shipped CSS hides those two until a
  `useEffect` feature-detects the APIs. That is the state a browser with both APIs renders. The
  rules are ported unmodified rather than deleted to force visibility, and the assertion that each
  button has a **non-zero client rect** is what proves the hard-classing actually reveals them.

---

## 4. The location search (previous commit's item **a**) — it already worked; **no repair needed**

Confirmed by driving it, not by reading it. At **both** viewports: typing opens the list; `mumbai`
returns `2 options` (matched on the **address**, not the name); the list has real height (`125px`),
is not clipped horizontally or vertically, and carries the `10px` radius and `1px #e5e7eb` border;
`ArrowDown` moves both `aria-selected` and `aria-activedescendant` and the lime active fill follows;
`ArrowUp` **clamps** at row 1; `Enter` closes the list and writes `Bandra West` into the field;
**all four** target nodes update (section heading, heading address, map preview name, map preview
address); a second query re-opens the list; `Escape` closes it **without** undoing the committed
selection; a no-match query renders one non-option empty line; clicking a row updates all four
nodes; and there is no horizontal overflow with the list **open**.

**Browser evidence is now committed:** `docs/mocks/vayulok-section-scrolled.png` was repurposed to
capture the results list **open**, typed through the real input via the real handler. No committed
image previously evidenced this behaviour — a reviewer could only read that it should work.

## 5. The old inline subscribe form (previous commit's item **b**) — fully gone

Grepped **every** occurrence of each selector, per the recorded `.vl-sub-action` hazard (it was once
declared **twice** in disjoint blocks so both applied and neither looked wrong alone):

`vl-sub-dial` **0**, `vl-sub-phone` **0**. `vl-sub-action` 5 hits, `vl-sub-status` 3, `vl-verify-row`
2, `vl-btn-quiet` 4, `vl-cell` 3 — **all comment-only retirement notes, zero CSS rules, zero
elements**, which the harness asserts as counts rather than assuming from reading.

**The residual `vl-pf-code`/`vl-pf-num` reference the brief asked to clean was a comment, and it is
cleaned** — the ROLE 3 retirement note was collapsed and no longer enumerates dead class names.
`src/components/PhoneField.tsx` and `src/lib/dialCodes.ts` are kept as the named source.

---

## 6. Zero-network, and the 390px check

- **`exactly 1 request (the document)`** and **`zero non-file:// requests`** at both viewports, on
  both twins. `zero console errors`, `zero page errors`, `NO dialog fired`.
- `zero <link> elements`. All CSS is inline, all icons are inline SVG, no external font/image/JS.
- The only external reference in the file is the `wa.me` href:
  `grep -o 'https\?://[^"'\'' ]*'` returns only `https://wa.me/message/BEA3HNW3LNM3A1`.
- **`.vl-keygate` is untouched** (load-bearing for zero-network). Its `maps.googleapis.com` host is
  assembled from an array `join` and is only ever used if a key is pasted by hand — never on load.
- **No API key, credential or token was added to any file.** AWS Secrets Manager was never read;
  `aws secretsmanager get-secret-value` / `batch-get-secret-value` were never run.
- **390px: nothing overflows or clips.** `document.scrollWidth === clientWidth === 390`. I inspected
  the rendered 390px frames directly: the Subscribe pill is a single line inside the panel, all four
  amount chips sit on one row, and the Share row and its tips stay inside the column. The only
  elements extending past 390 are the pre-existing `.vl-hour*` horizontal scroll carousel — none of
  the ported elements. Plan risk #2 (`.vl-share-tip` overflowing at 390) **did not materialise**.

---

## 7. Layout: three sections, two dividers, screenshot order

The three blocks are `.vl-section` siblings in `.vl-app-left`, so the dividers come from the existing
rhythm (`.vl-app-left > .vl-section{margin-top:56px;padding-top:40px;border-top:1px solid var(--hair)}`)
and **no new layout rule was added**. Asserted: exactly 3 ported sections, in screenshot order
(subscribe -> contribute -> share), all carrying the 1px `rgb(229,231,235)` hairline, every one at
`padding-top:40px` and `margin-top:56px`.

**Watch the off-by-one:** all three sections carry a hairline, so the **two dividers between the
three blocks** are the 2nd and 3rd hairlines; the first sits above Subscribe, separating the stack
from the content higher up the column. Counting all hairlines and expecting 2 is the mistake (my
first draft made it).

`.vl-contribute{padding-top:24px}` is **fully shadowed** by that two-class rule and is dead; the
assertion that every ported section computes `padding-top:40px` is the measurement proving so. **I
left the dead rule in place** rather than deleting it, because deleting it is coupled to the open
§9 decision and it changes nothing on screen either way.

**ROLE 1 is now down to exactly one member, `Load`, by design.** Asserted as a count, plus a DOM
sweep asserting no ported control was left on `.vl-btn`, so a later pass cannot quietly re-flatten
the pills back into it. The old "all action buttons share one height/font" pair was vacuous over a
one-element list and was replaced. The retired pairwise WhatsApp-vs-Contribute parity block demanded
the two controls be geometrically **identical** — which the real site is not, so passing it
*required* the mock to be wrong; it is replaced by the per-role blocks in §2.

---

## 8. The CONTRIBUTE eyebrow — casing ported, word unchanged

`BlogContribution.tsx:260-263` declares `text-transform:uppercase` on `.bc-title`, so the real site
renders **CONTRIBUTE**. The mock was rendering `Contribute` in sentence case and now matches.

**The word and the casing are two different questions, and only the casing changed.** The DOM text
is still the word `Contribute`; the thing the owner rejected was the **word** "Contribution". Two
comments in the file conflated the two and are rewritten to record the distinction. Both halves are
asserted: DOM text is exactly `Contribute`, is **not** `Contribution`, and computed
`text-transform` is `uppercase` — so "fixing" the casing by editing the markup to `CONTRIBUTE`
would fail the first assertion. **This is a visible change** (sentence case -> all caps) and is
flagged here for that reason, though the task brief, the plan and the shipped source all agree on it.

---

## 8a. The subscribe panel, eyebrow and heading — REMOVED (owner correction, mid-pass)

The owner compared the mock against the live reference page
(`/post/hear-the-story-without-turning-the-person-into-the-story/`) and identified the panel as the
one remaining mismatch. **Verified against the source before changing anything:** in
`src/pages/post/[slug].tsx` the `.blog-wa-subscribe` anchor follows the tags `</nav>`
**immediately** — no wrapping element, no heading before it.

Removed: the `.vl-subscribe` panel (2px `#d1f470`, `rgba(209,244,112,.22)`, 14px radius), the
`.vl-eyebrow` "VayuLok alerts", the `.vl-sub-title` h2 "Get air-quality alerts for your place", the
`.vl-sub-head` flex row and `.vl-sub-head>div`/`>p`, plus the three 767px tweaks
(`.vl-sub-head{display:block}`, `.vl-sub-head>p{margin-top:10px}`, `.vl-subscribe{padding:20px 16px}`)
and the now-unused `--lime-tint` token. **Removing the h2 reverses an earlier instruction to keep
it**, on the owner's explicit later instruction.

**`.vl-eyebrow` was NOT deleted, and grepping first is why.** It has a second, live user —
`<p class="vl-eyebrow">Health advisory</p>`. Deleting the rule because its *other* user went away
would have silently restyled an unrelated block. Every affected selector was grepped for **every**
occurrence first, per the recorded hazard that this file has had one selector declared twice in
disjoint blocks. Post-removal counts: `vl-subscribe` 2, `vl-sub-head` 3, `vl-sub-title` 2 — **all
comment-only retirement notes, zero CSS rules, zero elements**, asserted as counts by the harness.

**The orphaned ARIA reference was fixed, not just vacated.** The section carried
`aria-labelledby="vl-sub-title"`, pointing at the deleted h2's id. A dangling `aria-labelledby` is
*worse* than none — it names nothing while reading as wired, leaving the region unnamed. It is
replaced with `aria-label="Subscribe on WhatsApp"`. The harness asserts that if
`aria-labelledby` is present at all its target resolves, **and** that the section is still named.

**The separators now use the shipped margins.** They were 56px/40px, invented for this column. Both
shipped blocks declare the same rule — `.bc` (`BlogContribution.tsx:253-254`) and `.post-share`
(`[slug].tsx:787`): `margin-top:44px;padding-top:24px;border-top:1px solid #e5e7eb`. `#e5e7eb` is
`var(--hair)`, so colour and thickness already matched; only the spacing was ours, and it now comes
from the source. **One rule draws all three hairlines**, so they cannot drift — asserted as a
set-size of 1 over `(width, colour, padding-top, margin-top)`, not as three separate literals.

Measured after the change: `1px rgb(229, 231, 235) 24px 44px` on all three, identically.

**A probe went blind and was caught.** `subscribe panel holds exactly one control` queried
`.vl-subscribe a, .vl-subscribe button, ...`. With the panel gone that selector matches nothing, so
it reported "none" and **passed for the wrong reason** — it was proving the probe was blind, not
that the region was clean. It is re-anchored to the anchor's own `<section>` and its failure detail
now says so explicitly. The `-subscribe` screenshot anchor had the same defect (`scrollTo:
'.vl-subscribe'` silently does not scroll when the selector misses, which would have captured the
top of the page under a filename saying "subscribe"); it is re-anchored to `#vl-sub-wa`.

---

## 9. The amounts and the contribute paragraph — CLOSED by the owner

I raised this during the pass because my task brief and the implementation plan contradicted each
other on user-visible, revenue-affecting copy and both claimed owner authority. **The owner
confirmed: the plan's values stand.** Nothing here was changed in either direction.

| | Task brief said | **Confirmed, in the file** |
| --- | --- | --- |
| Amounts | `₹200/₹400/₹600`, `₹200` selected | **`₹50/₹200/₹400`, `₹50` selected** |
| Paragraph | shipped sentence verbatim | **"If you found this useful, you’re welcome to make a small voluntary contribution."** (U+2019) |
| `.vl-placeholder` blocks | "leave alone" | **deleted** |
| "Pick the places you want watched." | "leave alone" | **deleted** |

For the record, the brief was **stale** on these points: it stated the twins hash `0c2ffb47` and
that the mock "currently hardcodes `value="99"/"249"/"499"` with ₹249 checked" — both true *before*
`bd18e238`, false by the time I started. The mock's amounts therefore **diverge deliberately** from
`CONTRIBUTION_PRESETS_PAISE = [20000, 40000, 60000]` in `src/config/contribution.ts` and
`amplify/functions/shared/lambda_utils/ecommerce/blog_contribution.py:92`; an HTML comment at the
amount block records that and names both files as what a real rollout would have to change.
**Per instruction, no assertion compares the mock's faces to `CONTRIBUTION_PRESETS_PAISE`.**

**What is verified:**

- **`99`, `249` and `499` are gone** — asserted in the DOM, as both chip-face text and radio value,
  for each of the three numbers. Faces are `₹50 ₹200 ₹400 Other`.
- Exactly 4 chips and 4 radios, exactly **one** checked, the last chip is `Other`.
- Selected chip is lime `rgb(209,244,112)` with a `rgb(26,58,42)` border; unselected are
  `rgb(255,255,255)` with `rgb(229,231,235)`. Asserted as a **difference** as well as against the
  literals, so "all four styled the same" cannot pass.
- All four chips are ROLE 4 geometry: `999px`, `15px/700`.
- **These are DOM assertions, never greps.** `999px` appears ~10 times in the stylesheet and `600`
  ~9 times as font weights and PIN codes, so `grep 99` / `grep 600` match for reasons unrelated to
  an amount. A text grep here is noise.
- The paragraph is the owner's sentence with the **U+2019** apostrophe, not ASCII `'`.

---

## 10. Byte-equality (`git hash-object`; `diff` and `cmp` are NOT installed here)

| Pair | Hash (both files) | |
| --- | --- | --- |
| `vayulok-live-mock.html` + `vayulok-final-v3.html` | `4ac8441bc0733e4cb7854bae34ff6b2625dd537a` | identical |
| `vayulok-live-mock-1280.png` + `vayulok-final-v3-1280.png` | `2286230c591600098beba189ce0a6cab4ec71557` | identical |
| `vayulok-live-mock-390.png` + `vayulok-final-v3-390.png` | `2637a62165c65fb10b215ea8b3db69af937fbb94` | identical |

Method: edit `vayulok-live-mock.html` only, then
`cp docs/mocks/vayulok-live-mock.html docs/mocks/vayulok-final-v3.html`, then hash both.

Screenshots regenerated by `node tools/browser/vayuloksubcheck.js --shots`:
`vayulok-live-mock-{1280,390}.png`, `vayulok-final-v3-{1280,390}.png`,
`vayulok-section-{desktop,scrolled,subscribe,footer}.png`.
`vayulok-section-footer.png` is **new in this pass** and is the frame to check against the owner's
screenshot: it is the only one showing all three ported blocks and both dividers in one frame.
`vayulok-section-desktop.png` regenerated byte-identically (the top of the page did not change), so
it is not in the diff.

---

## 11. Known gaps and things a reviewer should not have to rediscover

1. **`tsc`, `lint` and `vitest` CANNOT RUN in this sandbox** — the repo root `node_modules` is not
   installed at all. `npx tsc --noEmit` fails on `Cannot find name 'process'` / `Cannot find module
   'vitest/config'` and `npm run lint` fails on `Cannot find package 'eslint-config-next'`. These are
   **pre-existing environment gaps, not regressions**: I touched **zero** `.ts`/`.tsx` files, and
   nothing under `src/` or `amplify/` was modified. Verified with `git status`.
2. **Nothing wires this harness into CI.** `.github/workflows/build-test.yml:195-205` runs five
   browser scripts and `vayuloksubcheck.js` is not among them. Adding it is out of scope (scope is
   the two mocks plus `tools/browser/`), but it means **nothing guards these files** on the next
   pass. The previous review already carried this gap.
3. **The repo's unit gates do not cover `docs/mocks` at all** — the browser harness is the only real
   verification for these two files.
4. **The `@media(max-width:360px)` pill rule is below both harness viewports** (1280 and 390). It is
   ported for fidelity and is **not covered by an assertion**.
5. **`.vl-placeholder` CSS and `.vl-sub-head>p` CSS are now orphaned** (their markup was deleted by
   `bd18e238`). I left both in place because removing them is coupled to the §9 decision — if the
   placeholders are restored, the CSS is needed again.
6. **`#vl-sub-wa`'s `aria-label` duplicates its visible `<span>` text.** That is exactly what the
   shipped anchor does. It is mild WCAG 2.5.3 redundancy rather than a violation (the accessible name
   contains the visible label) and was deliberately **not** "fixed", because the point is to mirror
   shipped markup.
7. **The harness now reads `src/pages/post/[slug].tsx` at run time** (read-only) to compare the
   WhatsApp glyph path verbatim. It is the only assertion here that would notice the **shipped** icon
   changing. If that file moves, that assertion reports `NOT FOUND` rather than silently passing.

---

## 12. STILL TO DO — the "same style everywhere" audit (deliberately a second commit)

The owner extended scope to *every* interactive control in the mock, each taking the shipped style
for **its own role** (explicitly *not* flattening everything to one shape). The owner also asked
that the Subscribe/Contribute/Share stack and the separators land **first** so the match is visible
immediately — which is what this commit is. Remaining controls to audit role-for-role:

- `.vl-keygate`'s **Load** button and its "Paste a Google Maps key" input (restyle only — the
  paste-a-key behaviour must keep working; `.vl-keygate` is load-bearing for zero-network)
- the **Clear key** control
- the **AQI / PM2.5** layer toggles (`.vl-layer`)
- the **"Search a city or place"** input and its results list

Canonical sources to read rather than guess: `src/styles/button.css` (note `.btn-lg` is 52px tall
with 16px type, `.btn-sm` is 36px with 13px type, and **the 13px figure in that file is the
BORDER-RADIUS, not a font size** — a brief has had this backwards before), `src/styles/inner-pages.css`,
and the three shipped components.

**HAZARD, carried forward so it is not rediscovered:** the map script wires its radio group with
`querySelectorAll('.vl-layer')`. Do **not** add `.vl-layer` to any control outside that group and do
**not** remove it from AQI/PM2.5 — an earlier round found that giving "Clear key" that class would
let pressing it un-press AQI and leave the map claiming no active layer. Controls sharing a row must
share geometry.
