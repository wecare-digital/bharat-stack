# Implementation Plan — /get hero + auth control UI

Branch: `feat/get-hero-and-auth-phone-ui` (already checked out; the owner asked for a branch
rather than direct work on `stack`, which overrides `.kiro/steering/git-workflow.md`'s
single-branch default — the steering file itself allows a named branch when the user asks).

Baseline measured before planning: `npx vitest run` → **58 files / 764 tests green**.
`out/` is a current static export. `agent-browser` is on PATH and drives a real Chromium.

---

## What was actually found (read, not assumed)

### The two "pages" are two stages of one file
`src/pages/get.tsx` declares `type Stage = 'mobile' | 'otp' | 'files'` (line 53) and renders
all three from `export default function FilesPage()`. There is no separate sign-in or OTP
route under `/get`. `/account/sign-in.tsx` is a *different*, already-migrated customer
sign-in page — and it is the model this work copies from.

### The site's canonical customer-auth control set already exists
`src/pages/account/sign-in.tsx` + `src/components/PhoneField.tsx` +
`src/components/PillButton.tsx` are the owner-sanctioned treatment, built on the earlier
instruction recorded verbatim in PillButton's docblock: *"In our home page design and theme,
the phone number button - make this style for cart login or any other login."* Measured
values:

| Token | `/account/sign-in/` + components | `/get` today |
|---|---|---|
| Field height | 52px (`.si-input`, `.pf`) | 52px (`.sf-input`) |
| Field border | `1px solid #e5e7eb` | `2px solid rgba(26,58,42,.18)` |
| Field radius | 10px | 12px |
| Field font | `inherit` family, 17px, `#1a1a1a` | 16px, `rgba(0,0,0,.95)` |
| Field focus | `outline:3px solid #1a3a2a; outline-offset:2px` (`.si-input`), `-3px` inset per segment (`.pf`) | `outline:3px solid #1a3a2a; outline-offset:2px` |
| Label | 14px / **700** / `#1a3a2a` / `margin-bottom:8px` | 14px / 600 / `letter-spacing:-.1px` |
| Primary button | `PillButton`: 52px, `border:2px solid #1a3a2a`, `border-radius:999px`, dark `#1a3a2a` label segment with `#fff` 17px/600 text, mint `#5fe3b0` action segment with `#1a3a2a` 17px/700 text, `2px #1a3a2a` divider, hover `translateY(-2px)` + `0 4px 12px rgba(26,58,42,.18)` + action → `#3da35a`, focus `3px #1a3a2a` offset 3px, disabled `opacity:.6`, reduced-motion kills transition + lift | `.sf-cta`: lime `#d1f470` fill, `2px solid #d1f470`, 50px radius, 52px, 17px/600, hover → `#fff` + lift |
| Quiet control | 44px floor, `#1a3a2a`, 16px/700, underline offset 3px (`.si-back`, `.cart-remove`) | `.sf-quiet`: `padding:10px` on a 15px line ≈ **38px**, under the 44px floor |
| Error banner | lime tint `rgba(209,244,112,.22)`, `border-inline-start:4px solid #d1f470`, 16px/700 `#1a3a2a` (`.si-error`) — **no red, standing owner instruction** | `.sf-note-bad`: `#fee2e2` on `#ef4444` with `#7f1d1d` — **red** |

### Where `cart.tsx` and `index.tsx` disagree, and which wins
Measured from the real files, with the resolution for each:

1. **Primary CTA shape.** `index.tsx` has exactly one control, `.home-close-cta` — a one-piece
   lime pill: `min-height:52px; padding:0 28px; border:2px solid #1a3a2a; border-radius:50px;
   background:#d1f470; color:#1a3a2a; 17px/600`, hover `#fff` + `translateY(-2px)` +
   `0 4px 12px rgba(26,58,42,.12)`, focus `3px #1a3a2a` offset 3px.
   `cart.tsx` has **no** CTA rule of its own any more — its checkout/login gate is `PillButton`,
   the two-segment dark-green + mint pill.
   **→ `PillButton` wins for /get's sign-in controls.** The owner named the cart button
   explicitly ("use .../cart/ button style here"), and PillButton's own docblock scopes it to
   "every customer login CTA ... built once so every customer login CTA uses the same markup
   and the same tokens and cannot drift." The one-piece lime pill stays for the *non-login*
   action on /get (the files-stage "Pay … on WhatsApp" button), because that is not a login.

2. **Control height.** `cart.tsx`'s secondary controls are 44px (`.cart-redeem-input`,
   `.cart-qty`, `.cart-remove`); `index.tsx`'s CTA and `PhoneField`/`.si-input` are 52px.
   **→ 52px for /get's fields and primary buttons** (they are the page's primary action and
   52px is the site CTA height the fields are built to match), **44px floor for quiet/text
   controls** (cart's rung, and the documented tap-target floor).

3. **Field radius.** `cart.tsx` 8px, `PhoneField`/`.si-input` 10px, `/get` 12px.
   **→ 10px.** `/account/sign-in/` is the other half of the same WhatsApp-OTP journey; the
   8px cart values are for secondary coupon/quantity inputs, not a primary auth field.

4. **Field font size.** `cart.tsx` 16px, `.si-input`/`PhoneField` 17px, `/get` 16px.
   **→ 17px.** Still ≥16px, so get.tsx's documented reason for its 16px floor (iOS Safari
   zooms the viewport on focus below 16px) is preserved.

5. **Control boundary contrast — the one place the site is wrong and this plan fixes it.**
   `#e5e7eb` on white measures **1.24:1** (the figure is already recorded in index.tsx's own
   measurement table at line ~684). `/get`'s `rgba(26,58,42,.18)` composites to ≈**1.39:1**.
   WCAG 1.4.11 wants **3:1** for the visual boundary that identifies a control, and on a white
   field with no fill difference the border is the only identifier — so both current values
   fail. **→ `#1a3a2a` (≈11.85:1), at 1px, in all three field declarations** (`.si-input`,
   `.pf`, and /get's new shared field class). This is not a new colour and not a new idea: the
   repo has already made exactly this correction twice, with the measurement written down each
   time — `.home-close-cta` ("THE BORDER IS #1a3a2a, NOT #d1f470 ... 1.18:1, and WCAG 1.4.11
   wants 3:1") and `.ship-close-cta`. The `1px #e5e7eb` hairline doctrine ("2px hoverable, 1px
   static, colour always `#e5e7eb`") is **retained unchanged** for surface edges, row rules and
   PhoneField's internal segment divider — those are decorative separators, not the boundary
   that identifies a control. Thickness is unchanged at 1px, so PhoneField's derived 9px inner
   segment radii stay correct and no layout moves.

6. **Error/status banners.** `cart.tsx` and `sign-in.tsx` carry the lime state tint under a
   standing "NO RED" owner instruction, enforced by `src/test/PublicPageTopBand.test.tsx`
   (`NO_RED_FILES`, plus a notation sweep for hex/rgb/hsl/named reds). `/get` is not in that
   list and still ships red. **→ /get adopts `.si-error`/`.cart-status` and is added to
   `NO_RED_FILES`.** Severity stays a weight + edge-width step (4px/700 for the alert, 3px/400
   for the status), never a hue, and `role="alert"` / `role="status"` are untouched, so colour
   was never and still is not the only signal.

### The reported visual difference between the two stages — reproduced from source
A source-only read can wrongly conclude "they already match", because both stages share one
`.sf-input` base rule and one `.sf-cta` rule. The real, reproducible deltas are:

- **(a)** `.sf-input-code` overrides the OTP field only: `letter-spacing:.34em; font-size:22px;
  font-weight:600; text-align:center`. 16px/400/left vs 22px/600/centre/tracked is a visibly
  different box. This is the single biggest cause of "phone fields differ".
- **(b)** The OTP submit is `disabled={busy || code.length < 4}`, so on arrival it renders at
  `opacity:.55` while the mobile submit arrives fully saturated. The two stages' buttons
  genuinely differ in colour and weight at first paint.
- **(c)** The OTP stage adds `.sf-quiet` ("Use a different number") — a ~38px borderless text
  button under a 52px pill, a second control rung the mobile stage does not have.
- **(d)** Placeholders differ in kind: `"8100640044"` vs `"——————"` (six em-dashes).

**Anything the owner saw beyond (a)–(d) is NOT dismissed.** The plan requires a runtime
agent-browser pass that reads computed styles on **both** stages and screenshots them, and any
residual difference must be written into the FEAT `findings` with its measurement. The owner was
already burned by a source-only review that missed a live difference.

### What `index.tsx`'s top section actually contains
`<main class="home-shell">` → `<div class="home-layout">` (max-width 1300, `padding:80px 24px
96px`, flex column, `gap:96px`) → three bands:

1. **`.home-hero`** — **no** brand badge (deliberately removed; the comment at index.tsx ~317
   records that it repeated the header lockup 109px below it), then `<h1 class="home-head">`
   made of a static frame line on its own block plus a rotating tinted pill (dot + measured
   width glide, 2400ms, `cubic-bezier(.16,1,.3,1)`, white entrance shutter), then one
   `<p class="home-sub">` body line at 20px/400/1.4/-.125px.
2. **`.home-flow`** — `WorkflowTerminal` in a two-column band with its own h2 and list.
3. **`.home-close`** — the scroll-reveal closing band (IntersectionObserver `threshold: 0.18`,
   `is-armed`/`is-in`, lime rule, staggered ticks, `.home-close-cta`).

**Decision: "the top section of home pages" = band 1 only, the animated hero,** reused through
`src/components/RotatingHero` (the extracted, self-styling version of that band — same
interval, easings, shutter and dot, asserted as one family by `tools/browser/animcheck.js`).
Band 2 is a marketing demo of messaging automation and has nothing to do with collecting a
file. Band 3 is **deliberately not added**: the owner asked for the TOP section, `/get` is a
sign-in surface whose single job is the form, and a second lime CTA band below the form would
compete with the submit control. `/shipments/` and `/perks/` carry the closing band because
they are landing pages with nothing to transact; `/get` has a form.
**`badgeLabel` is omitted**, following index.tsx's own documented removal (the header states
the brand 108px above) — and it buys ~58px of above-the-fold space on a page whose control
must stay in the first screen.

### The fold: measured, real, and answered by precedent
Measured in Chromium against the current `out/` at 1366×768: `/get`'s panel top **156px**,
phone input top **418px**, submit bottom **540px** — comfortable, because `.sf-shell` only pays
`calc(108px + 48px)` of clearance.

`RotatingHero` replaces that with `.rh-shell{padding-top:108px}` + `.rh-layout{padding:80px 24px
96px; gap:96px}`, and its `<h1>` is always **two** lines (frame block + pill block). Naively
nesting today's panel inside it puts the submit control ≈299px lower — **below the fold**.

The precedent that settles it: `/account/sign-in/`, the other half of this journey, measured on
the same build — card top **425**, phone field top **455**, pill bottom **624** at 1366×768
(620 at 1280×800, 625 at 1440×900). RotatingHero's second headline line costs ≈61px more than
PageTopBand's single line, so `/get` lands at a pill bottom of ≈640–685 **if and only if** the
page stops paying for furniture it does not need. Hence:

**Fold mitigations, in this order (apply all; they are also the right design calls):**
1. No `badgeLabel`.
2. `sub` is one line (today's lead already is).
3. The form is `RotatingHero`'s **first** child.
4. **Drop the tinted `.sf-panel`** and render the form as a plain 460px card matching
   `.si-card{width:100%;max-width:460px;margin:0}`. `clamp(28px,4vw,56px)` of panel padding
   goes with it (≈56px recovered at 1366px), and the lime tint — which is
   `.home-close-panel`'s *closing-band* treatment — stops competing with the hero at the top
   of the page. `/account/sign-in/` has no panel either.
5. If a measurement still fails, reduce the field's bottom margin from 20px to 14px and
   re-measure. **Do not** add a scroll cue or an in-page anchor.

**Hard acceptance number:** at 1366×768, 1440×900 and 1280×800 the submit control's
`getBoundingClientRect().bottom` must be ≤ `innerHeight − 40` **and** within 80px of
`/account/sign-in/`'s measured pill bottom at the same viewport.

**The page cannot restyle `.rh-layout`'s 96px gap or `.rh-shell`'s padding** — styled-jsx scopes
only the lowercase tags in the file it compiles, and `RotatingHero` is self-styling. Every
mitigation has to live in the page's own children. Do not try.

### Structural constraints confirmed
- `RotatingHero` renders the `<main>` and the `<h1>` (`subordinate` would downgrade them; /get
  must **not** pass it). So `get.tsx` must delete its own `<main className="sf-shell">`,
  `<h1 className="sf-title">`, `.sf-eyebrow` and `.sf-lead`. Built-HTML counts today are
  h1:1 / main:1 for `/get/`, `/cart/` and `/account/sign-in/` — that must still hold.
- Chrome is central: `_app.tsx`'s `isPublic` chain already lists `'/get'` (line ~990, grouped
  with `/cart` and `/account/sign-in`). The page must not import Header/Footer/SupportWidget/
  Layout.
- `/get` stays out of `PUBLIC_PAGE_META`, `scripts/generate-sitemap.js`,
  `scripts/generate-public-pages.js` and `config/public-pages.json`. Keep
  `components/SEO` with `noindex` (that is what emits `robots: noindex, nofollow`); do **not**
  switch to `PageMeta`, which is the marketing-page component.
- Every CTA on the public pages is a plain `<a>` with
  `// eslint-disable-next-line @next/next/no-html-link-for-pages`. Do not "fix" to `next/link`.
- `/get/` is already carried by `tools/audit/htmlcheck.js`, `tools/browser/devicecheck.js`,
  `lhcheck.js` and `sectioncheck.js`, so no route list needs editing. `sectioncheck` will
  report /get going from 1 band to 2 — that is a reported measurement, not an assertion.

### Auth logic that must not move
`requestOtp` / `submitOtp` / `normaliseMobile` behaviour, the `normaliseMobile(mobile)`
fail-fast on an obviously bad number, the `if (!challenge.registered)` guard that stops rather
than showing a code screen no code will satisfy, `restoreSession`/`clearSession` handling, the
401 → `clearSession()` + "Your session expired." path, the `NotAuthorizedException` → "Too many
incorrect attempts." path, `nextSessionFrom`, and every error/message string must behave exactly
as now.

Consequences, decided and recorded:
- **`PhoneField` is NOT used on /get.** It adds a dial-code `<select>`, and composing an E.164
  string ahead of `normaliseMobile` is precisely the change `sign-in.tsx` documents itself as
  making deliberately ("the dial code is composed here instead, ahead of it ... which leaves
  normaliseMobile nothing to infer"). On /get that would be a change to the auth input path,
  which is forbidden here. /get keeps its single whole-number input and therefore keeps
  `autoComplete="tel"` (not `tel-national`), because `normaliseMobile` is still the thing that
  infers +91.
- **The `code.length < 4` disable stays.** Disabling the mobile submit to match it would remove
  the only route to the fail-fast error, and removing the OTP disable would send a two-digit
  code to Cognito. A disabled control is a legitimate state, not an inconsistency: both stages
  get the *same* `PillButton` disabled treatment, and the test asserts the OTP submit becomes
  visually identical to the mobile submit once 4+ digits are typed.
- One treatment, both stages: `.sf-input-code`'s bespoke 22px/centred/`.34em` typography is
  **deleted**. `/account/sign-in/`'s code field is a plain `.si-input`, so plain is both the
  consistent answer and the site-matching one. The `onChange` digit-strip + `slice(0,6)` stays
  (input hygiene, not auth logic).

---

## Items

- [ ] 1. Replace `/get`'s control treatment with `/account/sign-in/`'s, value for value, across
      both the `mobile` and `otp` stages: one `.sf-field` class on both inputs
      (`min-height:52px; padding:0 16px; margin:0 0 20px; font-family:inherit; font-size:17px;
      color:#1a1a1a; background:#fff; border:1px solid #1a3a2a; border-radius:10px;
      box-sizing:border-box; width:100%` with
      `:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}` and
      `:disabled{background:#f6f7f5;color:rgba(0,0,0,.54);cursor:default}`), delete
      `.sf-input-code` and the six-em-dash placeholder, move `.sf-label` to 14px/700/`#1a3a2a`/
      `margin-bottom:8px` (drop the `-.1px` tracking), and add `type="tel"` / `type="text"` to
      the phone and code inputs. Keep every `id`/`htmlFor` pair, `inputMode`, `autoComplete`
      and `disabled={busy}` exactly as they are.
      Files: `src/pages/get.tsx`
      Verify: `npx vitest run` — 58 files still green; `npm run lint`; `npm run typecheck`.

- [ ] 2. Swap both stages' submit controls to `PillButton` — the cart/login pill the owner
      named — keeping their visible and accessible text byte-identical:
      mobile `<PillButton as="button" type="button" label="Sign in" action={busy ? 'Sending…' :
      'Send code on WhatsApp'} disabled={busy} busy={busy} block onClick={handleRequestOtp} />`,
      otp `action={busy ? 'Verifying…' : 'Verify'} disabled={busy || code.length < 4}`. Delete
      the `.sf-cta` rule's use on these two stages. Leave the files-stage "Pay … on WhatsApp"
      button on the one-piece lime CTA but correct its edge to `2px solid #1a3a2a` (the
      1.4.11-compliant lime treatment `.home-close-cta` and `.ship-close-cta` already use);
      record in the code comment that a payment action is not a login, which is why it does not
      take the login pill.
      Files: `src/pages/get.tsx`
      Verify: `npx vitest run`; `npm run lint`; `npm run typecheck` — all green. Depends on item 1.

- [ ] 3. Bring `/get`'s quiet controls and banners onto the site family: `.sf-quiet` →
      `min-height:44px; padding-inline:8px; border:none; background:none; color:#1a3a2a;
      font-family:inherit; font-size:16px; font-weight:700; cursor:pointer;
      text-decoration:underline; text-underline-offset:3px` with
      `:hover{background:rgba(209,244,112,.22);border-radius:8px}` and
      `:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px;border-radius:2px}` (clears
      the 44px tap floor it currently misses at ~38px); `.sf-note-bad` → `.si-error`'s lime
      treatment (`background:rgba(209,244,112,.22); border-inline-start:4px solid #d1f470;
      font-size:16px; font-weight:700; line-height:1.5; color:#1a3a2a; border-radius:10px;
      padding:14px 16px`); `.sf-note-ok` → the same at `3px` edge and weight 400. Delete every
      red value (`#fee2e2`, `#ef4444`, `#7f1d1d`). `role="alert"` / `role="status"` and all
      copy unchanged. Also move `.sf-file`'s edge to the static hairline `1px solid #e5e7eb`
      and `.sf-empty`/`.sf-fine` to the 16px/1.55/`rgba(0,0,0,.54)` hint rung.
      Files: `src/pages/get.tsx`
      Verify: `npx vitest run`; `npm run lint`; `npm run typecheck` — green. Depends on item 1.

- [ ] 4. Add `'src/pages/get.tsx'` to `NO_RED_FILES` in `src/test/PublicPageTopBand.test.tsx`,
      so the retired-value list **and** the hex/rgb/hsl/named-red notation sweep both cover
      `/get` from now on.
      Files: `src/test/PublicPageTopBand.test.tsx`
      Verify: `npx vitest run src/test/PublicPageTopBand.test.tsx` — passes, which is only true
      once item 3 has removed the red. Depends on item 3.

- [ ] 5. Close the WCAG 1.4.11 gap everywhere the owner's "update everywhere" reaches: change
      the field boundary colour only — `1px solid #e5e7eb` → `1px solid #1a3a2a` — in
      `.si-input` (`src/pages/account/sign-in.tsx`) and on the `.pf` container
      (`src/components/PhoneField.tsx`). Thickness, radius, height and the `#e5e7eb` internal
      segment divider are untouched, so nothing moves and PhoneField's derived 9px inner radii
      stay correct. Update both docblock comments to state the measurement (`#e5e7eb` 1.24:1 vs
      `#1a3a2a` 11.85:1 on white) and to say that the `1px #e5e7eb` hairline doctrine still
      governs surface edges and the divider.
      Files: `src/pages/account/sign-in.tsx`, `src/components/PhoneField.tsx`
      Verify: `npx vitest run src/test/AccountSignIn.test.tsx src/test/SignInMessages.test.tsx
      src/test/PublicPageTopBand.test.tsx` — pass; then the full `npx vitest run`.

- [ ] 6. Runtime proof for items 1–5, both stages, before the hero work starts. Build, serve
      and drive Chromium: `npm run build`, then
      `python3 -m http.server 8111 --bind 127.0.0.1 --directory out` in the background, then
      `agent-browser set viewport 1366 768` / `agent-browser open
      http://127.0.0.1:8111/get/` and `agent-browser eval` reading `getComputedStyle` +
      `getBoundingClientRect` for the phone input and the submit control. Reach the `otp` stage
      either by `agent-browser network route` stubbing the Cognito IdP response with a canned
      `registered:true` challenge, or by temporarily initialising `useState<Stage>('otp')` in a
      scratch build — **revert that line before committing**. Screenshot both stages and
      `/account/sign-in/` for comparison. Assert: both /get stages' inputs report identical
      `border`, `borderRadius`, `fontSize`, `fontWeight`, `letterSpacing`, `textAlign` and
      height; both submits report the `.pill`/`.pill-label`/`.pill-action` structure with
      identical computed values once the OTP field holds 4+ digits; the phone input is
      `type=tel`/`inputmode=tel`/`autocomplete=tel`; focus-visible outlines are present on
      both; and no red remains anywhere on the page. Record every number, and record any
      residual difference the owner may have seen that these numbers do not explain.
      Files: none (verification); evidence goes in the FEAT `findings`
      Verify: the measurements above, plus `node tools/audit/htmlcheck.js --route /get/` → no
      new findings. Depends on items 1–5.

- [ ] 7. Mount the home page's top section on `/get` by nesting the whole form inside
      `RotatingHero`. Add
      `const FILE_WORDS: CycleWord[] = [{word:'files',tint:'#dbeafe',dot:'#2563eb'},
      {word:'papers',tint:'#ede9fe',dot:'#9849e8'},{word:'records',tint:'#e0f7c8',dot:'#3da35a'},
      {word:'invoices',tint:'#fef3c7',dot:'#f0a818'}]` — four nouns that are true of this
      page's own subject (not the home page's marketing audiences), 5–8 characters so the pill
      barely travels, tints/dots reused verbatim from the established per-subject palette and
      deliberately excluding the red pair. Render
      `<RotatingHero ariaLabel="Your files" frame={stage === 'files' ? 'Your' : 'Collect your'}
      words={FILE_WORDS} sub={stage === 'files' ? 'Shared with your number.' : 'Verify your
      mobile number on WhatsApp to collect files shared with you.'}>` — no `badgeLabel`, no
      `subordinate` — with the form as its first and only child:
      `<section className="sf-card" aria-label="Collect your files">`. Delete `<main
      className="sf-shell">`, `<h1 className="sf-title">`, `.sf-eyebrow`, `.sf-lead` and the
      `.sf-shell`/`.sf-panel` rules (the hero owns the shell, the 108px/96px header clearance,
      the 1300px measure, the single `<h1>` and the single `<main>`); add
      `.sf-card{width:100%;max-width:460px;margin:0}` to match `.si-card`. Keep `<SEO … noindex
      />` exactly as it is. Keep a `@media(prefers-reduced-motion:reduce)` block for the
      files-stage lime CTA's hover lift.
      Files: `src/pages/get.tsx`
      Verify: `npx vitest run`; `npm run lint`; `npm run typecheck`; `npm run build` — all
      green. Depends on items 1–3.

- [ ] 8. Prove the structure and the fold in the built output. Rebuild, serve `out/`, and
      confirm: `node tools/audit/htmlcheck.js --route /get/` reports no H1-MANY / MANY-MAIN /
      label-association / heading-order finding; `out/get/index.html` (scripts and styles
      stripped) contains exactly one `<h1>` and one `<main>`, and the emitted markup carries
      `rh-shell`, `rh-layout`, `rh-head`, `rh-cyc-word`, `pill`, `pill-label`, `pill-action`
      and `sf-field` with their `jsx-…` scoping classes; `out/cart/index.html` is unchanged in
      h1/main count. Then measure the submit control at 1366×768, 1440×900 and 1280×800 and
      hold the acceptance number: `bottom ≤ innerHeight − 40` and within 80px of
      `/account/sign-in/`'s pill bottom at the same viewport (measured baseline: 624 / 625 /
      620). Apply mitigation 5 (field bottom margin 20px → 14px) only if a viewport fails, and
      record the final numbers. Screenshot `/get/` both stages, `/account/sign-in/` and
      `/cart/`.
      Files: `src/pages/get.tsx` (only if a mitigation is needed)
      Verify: the htmlcheck run, the built-HTML counts and the three viewport measurements
      above. Depends on item 7.

- [ ] 9. Add `src/test/GetPage.test.tsx`, following the style of
      `src/test/ShipmentsPage.test.tsx` and `src/test/PerksPage.test.tsx` (`render` from
      `@testing-library/react`, plus `fs.readFileSync` source assertions for the things jsdom
      cannot see). Mock `../lib/customerAuth` with `vi.mock` so `restoreSession` resolves null
      and `requestOtp` resolves `{registered:true, session:'s', destination:'…0044'}`, and mock
      `../api/client` so nothing hits the network. Cover:
      (i) exactly one `<h1>` and one `<main>`;
      (ii) the hero is the shared `RotatingHero`, not a lookalike — source contains
      `from '../components/RotatingHero'` and `<RotatingHero`, the `.rh-cyc-word` words equal
      `['files','papers','records','invoices']`, and the `<h1>` text contains `Collect your`;
      (iii) the page imports no chrome (`not.toMatch(/components\/(Header|Footer|SupportWidget|
      Layout)'/)`) and still imports `../components/SEO` with `noindex`;
      (iv) the shared control treatment across stages — the phone input and, after advancing to
      the `otp` stage, the code input both carry the single `sf-field` class and no stage-only
      variant class; both stages' submits render `PillButton`'s `.pill` + `.pill-label` +
      `.pill-action`; the otp submit is disabled on arrival and enabled after
      `fireEvent.change` puts 4+ digits in the field, at which point its class set matches the
      mobile submit's;
      (v) `prefers-reduced-motion` handling is still declared in the source;
      (vi) the stage-advance path is unchanged — `requestOtp` resolving `registered:false`
      leaves the stage on `mobile` and renders the "No files are registered to this number."
      copy rather than a code screen.
      Files: `src/test/GetPage.test.tsx`
      Verify: `npx vitest run src/test/GetPage.test.tsx` — all new tests pass; then
      `npx vitest run` — 59 files green. Depends on items 7 and 2.

- [ ] 10. Full gate and a single local commit. Run `npm test` (which is `vitest run`, **not**
      Jest), `npm run lint`, `npm run typecheck`, `npm run build` (static export to `out/`,
      and it also runs `scripts/generate-public-pages.js`, `generate-sitemap.js`,
      `generate-blog-search-index.js`, `generate-llms-txt.js` — confirm `/get` did **not**
      appear in `config/public-pages.json`, `out/sitemap.xml` or `out/llms.txt`), then
      `node tools/audit/htmlcheck.js`. Stage the changed files by explicit path only
      (`.kiro/hooks/block-broad-git-staging.json` denies `git add -A`/`.`/`-u`) and commit on
      `feat/get-hero-and-auth-phone-ui`. Do not push.
      Files: none (gate + commit)
      Verify: all four npm commands exit 0, `htmlcheck` reports no new finding, `git status`
      shows a clean tree, and `git log --oneline -1` shows the new commit on the branch.
      Depends on every item above.

---

## Gaps and assumptions

- **Residual visual difference.** If the agent-browser pass in item 6 cannot reproduce a
  difference the owner reported beyond (a)–(d) above, that is **not** grounds to close it. Write
  the measurement into `findings` and say plainly what was and was not reproduced.
- **`tools/browser/` harnesses** (`devicecheck`, `animcheck`, `sectioncheck`, `lhcheck`,
  `pageaudit`) need `cd tools/browser && npm install` for `playwright-core`, which is not
  installed here and may not install offline. They are **best-effort**; `agent-browser` is the
  mandated substitute and is already proven working against `out/` on `127.0.0.1:8111`.
- **`sectioncheck`** will now report `/get/` as 2 bands instead of 1. That is a reported
  measurement, not an assertion, and the new number is correct.
- **`npm run build` emits `out/` and generated files.** `tsconfig.tsbuildinfo` and `out/` are
  build artefacts; check `git status` before staging and do not commit them unless they were
  already tracked.
- **The `/zip/` → `/shipments/` CDN redirect** named in `shipments.tsx` is an Amplify Console
  action outside this repo and outside this task. Not touched.
