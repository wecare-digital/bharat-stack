# Inline one-step WhatsApp subscribe with a real calling-code field in the VayuLok mock

The change collapses the VayuLok subscribe block from a promised two-step verify flow to a single inline step, replaces a fake `+91 00000 00000` placeholder with a real divided calling-code field ported from `PhoneField.tsx`, and brings two cross-role control mismatches into line. The three reported defects were each diagnosed by measurement rather than reading: `Send code` (32px) sitting beside `Subscribe` (52px) in one row, a duplicated `.vl-sub-action` rule whose second copy carried `min-height:91px` and left the button's bottom edge 19.5px above its field's, and `Clear key` rendering at 32px between two 38px map pills. The "+" the report flagged turned out to be placeholder text standing in for a control that did not exist, and the "dialog" turned out to be an extra *step*, not an overlay — no `<dialog>`, `[role=dialog]`, `position:fixed` node or native validation bubble existed before or after. Edits land in both byte-identical twin HTML files plus regenerated screenshots.

**Watch for:** an unsupported calling code (e.g. `+92`, deliberately excluded) reverts to `+91` with no explanation and submit can then report success for a number under the wrong country code (confirmed); the `Subscribed` button label is never reset, so a later invalid submit shows `Subscribed` above an error line (confirmed); and the brief's own ROLE 1 contract — "13px font / 52px height from BlogSubscribe.tsx:338" — is wrong on both counts and was correctly not implemented, which needs an owner yes/no (confirmed).

**Verdict**: APPROVED

## High-level view

The role system is the spine of the fix. The stylesheet documented four roles while the section rendered six shapes, so two controls had no entry to drift *from*; all six are now enumerated with measured geometry and citations, `.vl-btn-quiet` is retired as a vacant ROLE 2 rather than renumbering, and `Clear key` moves to ROLE 5 through a separate `.vl-map-btn` class so it matches the map pills without joining their `aria-pressed` radio group.

On the brief's ROLE 1 contract there is a direct conflict, resolved against the brief. `button.css:31` is `border-radius:13px`, `.btn-lg` is `height:52px;font-size:16px`, 13px type belongs to the 36px `.btn-sm`, and `BlogSubscribe.tsx:338` is the 32px/12px-700 quiet shape — so "13px font / 52px height from BlogSubscribe.tsx:338" conflates a radius, a size class and the wrong role. Implementing it literally would have been a site-wide `button.css` change, so the owner should confirm.

Nothing modal ever existed, and the report was still correct: the extra *step* was promised by a `Send code` stub, a `.vl-verify-row` rule matching zero elements, and head copy reading "Verify your WhatsApp number once". All three are gone, and the result reports into a `role="status"` line present from first paint with its height reserved.

The phone field is a close port rather than a reimplementation — 59 of 59 dial codes with the shipped order and exclusions preserved, identical focus/commit/blur/Enter semantics, the ROLE 3 box on the container, and per-segment inset focus rings. The two omitted declarations and the single 17px→16px change are each justified in place.

The behavioral gap the port inherits is the unresolved-code path: a code the table does not offer is silently swapped back to the last committed one, on blur and again at submit, so a reader who types an excluded code can be told they subscribed a number that is not theirs. Separately, the success label is one-way — the error branch never restores `Subscribe`.

Zero-network, twin equality and screenshot regeneration all hold, independently re-verified here. What remains open is owner-facing: the `.vl-keygate` scrim is the only modal-looking thing left on the page and was deliberately untouched, the head copy is now a bare fragment awaiting the owner's words, and the preview URL the owner shared points at a branch 11 commits behind, so the fix will not be visible there until that branch is published and the cache-buster bumped.

<details>
<summary>Issues (7)</summary>

1. **Silent fallback on an unsupported calling code** — typing an excluded code (`+92`, `+86`, `+98`, `+963`, `+850`) reverts to the last committed code on blur and at submit with no message, and submit can then report `Subscribed +91…` for a non-Indian number. Report the unsupported code in `.vl-sub-status` instead of coercing silently.
2. **`Subscribed` label is never reset** — the invalid branch of the submit handler sets the status and `aria-invalid` but never restores `btn.textContent`, so a success followed by an invalid submit shows `Subscribed` above "Enter a 10-digit WhatsApp number". Reset the label in the error path.
3. **Brief's ROLE 1 contract is wrong** — "13px font / 52px height from BlogSubscribe.tsx:338" conflates `border-radius:13px`, `.btn-lg`'s 16px font and the 32px `.verify-row button`. Code is correct as shipped; get an explicit owner yes/no, since a literal reading is a site-wide `button.css` change.
4. **`.vl-keygate` left as-is** — the grey scrim and centred card over the map stage is the most modal-looking element on the page and was deliberately not touched. Confirm with the owner whether this was the reported "dialog"; if so it is a separate change.
5. **Head copy is a bare fragment** — "Pick the places you want watched." is the result of deletion-only editing. Needs the owner's wording for a sentence that names the one-step flow.
6. **Shared preview URL still serves the old mock** — `origin/vayulok-preview` is 11 commits behind this branch, so the URL the owner reported against will not show the fix until that branch is updated and `?v=` is bumped.
7. **New harness is not wired into anything** — `tools/browser/vayuloksubcheck.js` needs a manual `npm install --prefix tools/browser` and no CI job runs it, so nothing guards `docs/mocks` against regression on the next pass.

</details>

<details>
<summary>Details</summary>

### Six rendered shapes, four documented roles

`Clear key` is the case where the obvious fix would have been wrong. It had to match the two `.vl-layer` pills beside it to the pixel, but the script wires the AQI/PM2.5 radio group with `querySelectorAll('.vl-layer')`, so giving it that class would have enrolled it in the group and let pressing it un-press AQI, leaving the map claiming no active layer. Hence `.vl-layer,.vl-map-btn` sharing geometry while `[aria-pressed="true"]` stays on `.vl-layer` alone. The harness asserts group membership at the selector rather than by clicking, because the handler ends in `window.location.reload()`, which would destroy the execution context mid-measurement.

ROLE 2 is retired with its number left vacant rather than renumbering ROLE 3, because the numbers are cited from outside the file — including in this brief — and closing the gap would have invalidated those citations silently.

### The duplicated `.vl-sub-action` and the 19.5px dead space

`.vl-sub-action` was declared twice in two separate blocks, and because the copies set **disjoint** properties both applied and neither overrode the other — invisible to anyone reading the cascade, which is why this one needed a browser. The second copy carried `min-height:91px`, lifted from `BlogSubscribe.tsx:348`, where 91 is exact and load-bearing: input 52 + gap 7 + `.verify-row` 32.

```
shipped BlogSubscribe            this mock (no verify row)
  input        52                  label        17
  gap           7                  gap           7
  .verify-row  32                  field        52
  ------------- 91  = exact        ------------- 76  vs min-height 91
                                   => 52px button centred in 91 => 19.5px dead
                                      space above and below
```

With `align-items:flex-end` on the row, the row bottoms aligned while the button's own bottom edge finished 19.5px above the field's. Confirmed against source: `.blog-subscribe-action{display:flex;align-items:center;min-height:91px}`. The sibling `.vl-keyrow` was always written without it, which is why `Load` never showed the defect. Post-fix the delta is 0px at 1280; at 390 the action wraps to its own row and the harness detects which case applies rather than skipping, so a regression cannot hide behind the wrap.

### What the "dialog" actually was

The report was acted on only after being interrogated: zero `<dialog>` elements, zero `[role=dialog]`/`[aria-modal]`, no `position:fixed` node in the section, no `required`/`pattern`/`minlength` anywhere, `checkValidity()` true on every input, and clicking Subscribe both empty and filled fired zero dialog events while leaving `innerHTML.length` unchanged.

What the reader was reacting to was the extra **step**, promised in three places: `Send code` as a stub of the shipped two-step flow, a `.vl-verify-row` rule matching zero elements (the shell of step two), and head copy stating "Verify your WhatsApp number once, then pick the places you want watched." The replacement `role="status"` line is ported verbatim from `BlogSubscribe.tsx:347`, confirmed against source including the `is-done` weight. It reserves its own 22px from first paint, so reporting a result mounts nothing and shifts nothing; `.vl-subscribe` descendant count stays 16→16 across the whole interaction set.

Omitting `required`/`pattern`/`minlength` is grounded in repo history rather than preference — `PhoneField.tsx` records that the owner reported the native constraint bubble ("Please fill out this field." with an orange warning icon) as a defect in its own right, being unthemeable, untranslatable by the site's text walker, and contradictory to the standing no-red instruction. `aria-required="true"` carries the semantic. I confirmed independently that the only `required` substring in the file is that `aria-required`, and that `maxlength` appears only on the code segment, where it blocks typing rather than raising a bubble.

### The divided field, and what the port changed

```
.vl-pf  container: 52px tall, 1px #e5e7eb, 10px radius, overflow:hidden
  ┌──────────────┬────────────────────────────────────┐
  │ .vl-pf-code  │ .vl-pf-num                         │
  │ "+91"        │ "10-digit WhatsApp number"         │
  │ 78-86px      │ flex:1 1 auto, min-inline-size:0   │
  └──────────────┴────────────────────────────────────┘
                 ^ border-inline-end (logical: mirrors in RTL)
  segments carry no box of their own; inset focus ring per segment
```

Verified against source rather than taken from the note: `type="search"`, `inputMode="tel"`, `maxLength={4}`, `aria-label="Calling code"`, `placeholder="+91"`, focus-selects, commit-if-supported on input, blur-reverts, Enter preventDefault-then-blur — all present in `PhoneField.tsx`'s `DialCodeSearch` and all reproduced. `VL_DIAL_CODES` carries 59 entries against the shipped `DIAL_CODES`' 59, preserving India-first order and the documented exclusions (`+86`, `+98`, `+963`, `+850` WhatsApp-undeliverable; `+92` owner instruction 2026-10-02), each confirmed in `dialCodes.ts`.

Three deviations, each justified in place: `margin-bottom:20px` dropped because `.vl-cell{gap:7px}` owns that gap here and `BlogSubscribe.tsx:335` cancels it the same way; `scroll-margin-top` dropped because this mock has no fixed header; and 16px type instead of PhoneField's 17px (confirmed at lines 318/340) because 16px is ROLE 3's own size and what every other field in the section renders.

The focus treatment is per-segment for a stated reason: one ring around a container holding two focusable controls would not say which half has focus, and the lime is layered around the dark ring via `box-shadow` rather than used as the ring, because `#d1f470` on white measures 1.24:1 against WCAG 1.4.11's 3:1 while `#1a3a2a` is 12.48:1. The phone cell also stops being a `<label>` and gets a real `<label for>`, since a label points at exactly one control and this cell now holds two.

### An unsupported calling code fails quietly, and can report the wrong number

The submit handler opens with:

```js
var code = vlFindDial( dial.value ) ? dial.value : committed;
dial.value = code;
committed = code;
```

Traced end to end: a reader who wants `+92` types it, gets a transient `aria-invalid` and no message; clicking `Subscribe` blurs the segment, which reverts the display to `+91` and clears `aria-invalid`; submit then resolves `code` to `+91`, validates a 10-digit Pakistani mobile against India's 10-digit rule, passes, and reports `Subscribed +913001234567 to alerts for this place.` The reader asked for one country and is told they succeeded under another, the only signal being a flash of invalid styling they may never have seen.

The silent revert itself is faithful to `DialCodeSearch`, whose parent never receives an unsupported code, so this is inherited rather than invented. But the shipped product does not stop there: `dialCodes.ts:28` describes an "OTP cannot be delivered to this number" guard on `/get` as the companion to these exclusions, and the mock models the selector without that guard. Since the exclusion list is intentional and includes a market the owner named explicitly, the status line should say the code is not offered instead of swapping it out silently.

### The success label outlives its state

`btn.textContent = 'Subscribed'` is set on success and never restored. The invalid branch sets the status text, sets `aria-invalid` and focuses the field, but leaves the label alone, so success → clear the number → submit yields a button reading `Subscribed` directly above `Enter a 10-digit WhatsApp number for +91.` The harness's "does not flip the button label" assertion only covers an empty submit *before* any success, so this ordering is untested.

### Zero network, twin equality, screenshots

Independently re-verified rather than accepted from the note. The twins are byte-identical (`b35c2741…` for both), the `-1280` PNGs share one hash and the `-390` PNGs share another, and no conflict markers remain in either file. There are no `https://` literals, no `<link>`, no `@font-face`, no `@import`, no `<img>` and no `<script src>`; the single grep hit for those names is line 47, the preserved contract comment that documents their absence by naming them. Measured request count stays at 1 (the document) at both widths.

`diff`/`cmp` are not installed on this box, so `git diff --no-index` plus `md5sum` were substituted for the requested `diff` — a fair equivalent, and the harness additionally runs its full suite against `vayulok-final-v3.html`, so the twin is verified as a renderer rather than only byte-compared.

One thing for a reviewer not to misread: the PNG dimensions changed substantially (`-1280` was previously 1347px wide, not even 1280). The committed images were already stale against the committed HTML before this pass, so the new, correctly-sized images are a correction rather than a regression.

### Test coverage

`tools/browser/vayuloksubcheck.js` reports 268/268 assertions across four scopes (both twins × 1280/390), covering ROLE 1 geometry, the Subscribe baseline, the ROLE 3 divided box, ROLE 5 uniformity, absence of the retired rules, the interaction set with `page.on('dialog')` wired to fail, and request counts. It fills a real gap: nothing under `tests`, `src`, `scripts` or `.github` references `docs/mocks` or `vayulok-live-mock`.

Not tested: the stale-label ordering above; the unsupported-code submit path (only the typed and blurred states are asserted, not what submit composes afterwards); and no CI job invokes the harness, which needs a manual `npm install --prefix tools/browser` first — so nothing prevents the next pass from regressing this. `tsc --noEmit` is reported as 29672 errors both before and after on a stashed tree with empty `node_modules`, and `vitest` is reported as failing to resolve modules rather than claimed as passing.

### Deliberately out of scope

`.vl-keygate` is the one element on the page that genuinely looks like a modal — `position:absolute;inset:0;z-index:6`, a grey scrim over the map stage, a centred white card. It was left alone on the grounds that it sits in the map column rather than the subscribe flow and is load-bearing for the zero-network requirement, since the no-key state is what holds the page at zero outbound requests. It needs an explicit owner decision if that is what was meant.

The head copy is now "Pick the places you want watched." — the verification promise removed by deletion only, per the file's standing rule against inventing copy. It reads as a fragment and wants a real sentence in the owner's words.

Bundled alongside the two HTML files and the screenshots: the 538-line harness and two task notes under `.agents/tasks/`, outside the brief's stated file list though justified by the coverage gap. The branch's preceding commit (`2d6ca401`, "rebase VayuLok mock onto current stack") accounts for the bulk of the diff against `stack`; this review scopes to the fix commit, which is the change described in the brief.

</details>

<details>
<summary>File map</summary>

- `docs/mocks/vayulok-live-mock.html` — roles block rewritten to six documented roles; `.vl-btn-quiet` deleted; `.vl-pf` divided phone field added; duplicated `.vl-sub-action` and dead `.vl-verify-row` removed; `Send code` removed; inline `role="status"` line added; `Clear key` moved to `.vl-map-btn`; head copy trimmed; `DialCodeSearch`/`dialCodes.ts` ported as inline ES5.
- `docs/mocks/vayulok-final-v3.html` — byte-identical twin, same change.
- `docs/mocks/vayulok-live-mock-1280.png`, `vayulok-final-v3-1280.png` — regenerated at 1280×5567, pair byte-identical.
- `docs/mocks/vayulok-live-mock-390.png`, `vayulok-final-v3-390.png` — regenerated at 390×6519, pair byte-identical.
- `docs/mocks/vayulok-section-scrolled.png`, `vayulok-section-subscribe.png` — regenerated section shots showing the new field and action row.
- `tools/browser/vayuloksubcheck.js` — new headless-Chromium assertion harness (268 assertions, `--json` and `--shots` modes).
- `.agents/tasks/vayulok-subscribe-inline-plan.md`, `.agents/tasks/vayulok-verification.md` — plan and execution-based verification evidence.

Full diff: `git diff HEAD~1 HEAD` on `fix/vayulok-subscribe-inline` (fix commit `52f9d6f8`); against `stack` the diff additionally contains the preceding rebase commit `2d6ca401`.

</details>
