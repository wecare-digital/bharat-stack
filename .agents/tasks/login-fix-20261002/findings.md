# "not able login" — customer sign-in, /account/sign-in/ — findings

Worktree `/Users/wecaredigital/wecare-store/.worktrees/login-fix-20261002`, branch
`login-fix-20261002`, based on `stack` at `2ef4049d`. **Nothing was deployed.** No
`update-function-code`, no version published, no alias moved, no Cognito mutation, no API route
change, no OTP/WhatsApp/SMS/RCS sent to anyone.

---

## 0. Read this first — there are TWO layers, and I fixed the client one

The owner's report is one sentence and one screenshot. Underneath it are two independent faults,
and conflating them would be the main way to get this wrong.

| Layer | Fault | Status |
|---|---|---|
| **Server** | `customer_auth.authenticate()` requires a Cognito attribute that does not exist in the customer pool's schema, so the session exchange refuses **every** token the pool has ever issued | **STILL BROKEN IN PRODUCTION.** Not mine, not fixed here. A fix exists, undeployed and unmerged, on local branch `fix/otp-confirm` |
| **Client** | The number field looked pre-filled and the only failure feedback was a transient native tooltip; and the browser revealed both fields *behind* the fixed header on narrow viewports | **FIXED HERE**, undeployed |

**Do not read this report as "the login failure is a misleading placeholder."** Even a perfect form
cannot produce a signed-in session today. What I fixed is the part of the screen the owner
photographed, and it is genuinely defective — but it is not the production outage.

### The server fault, measured by me independently (read-only)

I confirmed this myself before being told about the parallel investigation, and the two agree:

| Fact | How measured |
|---|---|
| Pool `us-east-1_46ULYuukt` (`WECARE.DIGITAL-CUSTOMERS`) — all three CUSTOM_AUTH triggers **PRESENT**, all pointing at `wecare-customer-whatsapp-auth:live` | `DescribeUserPool` |
| `AllowAdminCreateUserOnly: true`, `MfaConfiguration: OFF` | `DescribeUserPool` |
| `wecare-customer-session` `live` → **version 5**, Active, LastModified `2026-10-02T02:26:43Z` | `GetAlias` + `GetFunctionConfiguration` |
| `stack-wecare-digital-CustomerSessionsTable` **ItemCount 0** — the exchange has never once succeeded | `DescribeTable` |

**The 2026-09-28 trigger-wipe has NOT recurred.** That was the explicit critical-finding check in
the brief, and the answer is negative: all three triggers are in place. Nothing needed
`cognito_pool_safe_update.py`, and no pool call of any kind was made.

So the OTP **send** works, `RespondToAuthChallenge` succeeds, the customer is genuinely
authenticated for an instant — and then `POST /ecommerce/customer-session` refuses them. That is
why this fails in a way that makes the client code look correct.

**I did not touch `src/lib/customerAuth.ts`.** I checked `git diff stack...fix/otp-confirm` first:
that branch changes `customerAuth.ts` (+45), `PillButton.tsx`, `cart.tsx` and eight test files, and
its only edits to `src/pages/account/sign-in.tsx` are **comment-only**, 11+ lines away from mine. It
does not touch `PhoneField.tsx` at all. **There is no collision.** Merging that branch remains an
owner decision; I did not merge, cherry-pick, or edit it.

---

## 1. Is this the same defect as `otp-confirm-fix-20261002`? — Partly, and the parts matter

| Item in the owner's screenshot | Same as prior work? |
|---|---|
| Login fails after a correct code | **SAME.** The `custom:customer_id` outage. Diagnosed and fixed on `fix/otp-confirm`; untouched here |
| The two-segment pill rendering | **SAME, and ALREADY FIXED** upstream in `2f742ec6`, which **is** an ancestor of my branch. Verified intact, not re-repaired |
| Grey `9876543210` read as a value | **DIFFERENT — new.** Not in the prior findings |
| Fields revealed behind the fixed header | **DIFFERENT — new.** Not in the prior findings |
| The empty gap above the footer | **DIFFERENT — new**, and it is *not fixed*. See §6; it needs an owner decision |

`git merge-base --is-ancestor 2f742ec6 HEAD` → yes. `… fix/otp-confirm HEAD` → no.

---

## 2. Hypothesis B — ACTIVELY DISPROVEN in a real browser

The dangerous hypothesis was that the input is genuinely broken. It is not, and this is measured
rather than read off the source.

Chrome (`/Applications/Google Chrome.app`, headless, driven over raw CDP — no packages installed)
against the **real `next build --webpack` static export**, not a dev bundle. Typed via the native
`HTMLInputElement.prototype.value` setter plus a bubbling `input` event, which is how a real
keystroke reaches React:

| Check | Result |
|---|---|
| Visible input is inside the `<form>` | **true** |
| DOM `value` after typing `9123456789` | `"9123456789"` |
| React's own prop value (`__reactProps*.value`) | `"9123456789"` — **state was written** |
| Number of text/tel inputs in the form | **1** — no duplicate, no shadow field |
| Hidden inputs in the form | **none** — nothing to fail to populate |
| What the client actually sent | `InitiateAuth` → `AuthParameters.USERNAME = "+919123456789"` |
| Phase reached | the code step, no error |

The submitted payload is the decisive one: **one** `+91`, not two, not none. So the country-code
composition is correct and the prior `phone-normalisation-fix-20261001` work is not regressed.
Reproduced identically at 1280×760, 1280×900, 760×900, 390×640, 390×400 and 320×568.

**Hypothesis B is eliminated.** No broken onChange, no ref-held value, no stripped digits, no
`required` on a hidden twin.

## 3. Hypothesis A — CONFIRMED, and it is worse than a misleading hint

Two findings, the second of which the brief did not anticipate.

### A1. The placeholder was a structurally valid Indian mobile number

`placeholder="9876543210"` — ten digits beginning with 9, which is exactly what
`normaliseMobile()` recognises as Indian, rendered in placeholder grey immediately beside a segment
reading **"+91 India"**. It reads as a number already in the field.

My reproduction screenshot (`.scratch/pre-desktop-after-scrollintoview.png` during the run) matches
the owner's screenshot item for item: grey `9876543210`, the orange-icon bubble "Please fill out
this field.", the `Sign in | Send code` pill, "Back to your cart", the empty gap, the footer
tagline.

### A2. The page's own error for this state was UNREACHABLE — the part that actually hurt

This is the finding I would call the real defect, and it is structural rather than cosmetic.

`required` on the number input makes the browser **block submit entirely**, so `startPhone` never
runs. Therefore `composeE164`'s empty-number branch — and the approved `BAD_NUMBER` message it
throws — **could never execute**. The page had a correct, approved answer for exactly this state
and no code path that could ever show it.

Measured before the fix, at all six viewports:

| | Before |
|---|---|
| Native bubble | `"Please fill out this field."` |
| Page's own inline error (`#si-error`, `role="alert"`) | **absent** |
| `aria-invalid` on the input | **null** |
| `aria-describedby` | `"si-hint"` — no error reference |

So a screen-reader user got the transient native announcement and **nothing else**: no
programmatic invalid state, nothing left on screen once the bubble dismissed, nothing to find on
tabbing back to the field. That is a WCAG 3.3.1 / 4.1.2 gap, not a cosmetic one.

---

## 4. The layout defect (item 7) — the reported symptom is real, but NOT the stated mechanism

The brief described the heading rendering "BEHIND / THROUGH the white logo header band". I tested
that claim directly and it is **false as stated**, which changes what the correct fix is.

### The header does not leak content through it — measured, not eyeballed

A differential test: screenshot the header band with heading content behind it, screenshot it with
nothing behind it, diff the two pixel by pixel inside the band. The header's own content cancels
out, so whatever remains is the bleed.

| Viewport | Max channel difference in the header band | Pixels differing by > 8 |
|---|---|---|
| 1280×760 | **2** / 255 | **0** of 138,240 |
| 390×640 | **1** / 255 | **0** of 37,440 |
| 320×568 | **1** / 255 | **0** of 30,720 |

Corroborated by direct sampling: the darkest pixel anywhere in the band with the heading behind it
is **254/255**, against **26/255** for the same text rendering unobstructed below the header.
`background: rgba(255,255,255,.97)` with `backdrop-filter: blur(20px)` is, in practice, opaque.

**I had to correct my own first reading here.** I initially believed I could see ghosting in my own
reproduction screenshot and started designing a fix for the header's translucency. The pixel
measurement contradicted me. What the owner saw — and what I saw — is the heading being **covered**
by the header after a scroll, which looks like it has partly vanished. It is not showing through.

### What IS broken: the browser reveals the form fields *behind* the header

Nothing gives the document or these controls any clearance for a `position:fixed` 108px/96px
header. When the browser reveals a form control — on focus, on autofocus, or as part of refusing
an empty `required` field — it scrolls that control to the top of the scrollport, and the top of
the scrollport is **under the header**.

Measured before the fix, pixels of the input covered by the header:

| Viewport | On focus-reveal | On `scrollIntoView` |
|---|---|---|
| 320×568 | **36.1px behind the header** | **36.1px** |
| 390×400 (phone with keyboard up) | 0 | **50px behind the header** |
| 390×640, 760×900, 1280×760, 1280×900 | 0 | 0 |

A shopper on a narrow phone could not see the number they were typing. That is a direct, credible
contributor to "not able login" and it is unambiguously a defect.

### Choosing the fix by measurement rather than by taste

I tested three candidates by injecting CSS at runtime before changing any source:

| Candidate | Fixes the field? | Verdict |
|---|---|---|
| `scroll-margin-top` on `.pf` (the container) | **No** — byte-identical numbers to no fix at all | Rejected. The browser scrolls the **input**, not its wrapper, so the declaration never applies. This is the site's existing per-element pattern applied to the wrong element, and it would have looked like a fix while doing nothing |
| `html { scroll-padding-top }` | Yes | **Rejected.** `LegalDocument` (`.lgd-section`) and `ContactLocation` (`.cl`, `.cl-h2`, `.cl-map`) already carry their own `scroll-margin-top:128px/112px`. Scroll padding on the scrollport **adds** to scroll margin on the target, so this silently doubles their anchor clearance to 256px. Measured over-scrolling at 320px too (input pushed to 314.9px) |
| `scroll-margin-top` on `.pf-num` / `.si-input` | **Yes** | **Chosen.** Element-scoped, cannot double, no other route affected |

### After the fix — 0px covered at every viewport

| Viewport | Number field, focus | Number field, `scrollIntoView` | Code field, reveal |
|---|---|---|---|
| 1280×760 | 0 | 0 | 0 |
| 1280×900 | 0 | 0 | 0 |
| 760×900 | 0 | 0 | 0 |
| 390×640 | 0 | 0 | 0 |
| 390×400 | 0 | **0** (was 50) | 0 |
| 320×568 | **0** (was 36.1) | **0** (was 36.1) | 0 |

The **mobile widths were checked explicitly**, as the brief required: 320, 390 at two heights, and
760 at the breakpoint edge. The defect was in fact *only* visible at narrow widths, so checking
desktop alone would have missed it entirely.

---

## 5. The two-segment pill (item 5) — correct, and deliberately not touched

Verified in the browser, both phases, all six viewports:

| | |
|---|---|
| Element | **one** `<button type="submit">` |
| Left segment | `jsx-69f2e5793ae0f718 pill-label` · "Sign in" · bg `rgb(26,58,42)` · white · `display:flex` · weight 600 · `aria-hidden="true"` |
| Right segment | `jsx-69f2e5793ae0f718 pill-action` · "Send code" · bg `rgb(95,227,176)` · `display:flex` · weight 700 · `aria-hidden="true"` |
| Accessible name | **"Send code"** (the action alone) |
| Keyboard order | `select` "Country code" → `input` `#si-mobile` → `button` "Send code", all `tabIndex 0` |

**What each is supposed to do:** "Sign in" is a *static label*, not a control — it says what the
form is for. "Send code" is the *action* and the button's accessible name. Both segments are inside
one submit button, so pressing either runs `startPhone`. There is no second button and no state in
which the user must press "Send code" before "Sign in".

Both segments carry the `jsx-*` hash their selectors require, so `2f742ec6`'s repair is intact and
I did not re-repair it. The residual **WCAG 2.5.3 Label in Name** mismatch (visible
"Sign in Send code" vs accessible name "Send code") is the open owner decision the prior findings
escalated in their §9. **I did not reopen it and did not change it** — removing the visible "Sign in"
segment would alter what the owner sees and would re-diverge `/account/sign-in` from `/get`, which
`2f742ec6` had just unified on owner instruction.

---

## 6. NOT FIXED — needs an owner decision (item 8, and it is the deeper cause of item 7)

**Found while measuring item 7, and it is one wrong constant.**

`PageTopBand`'s `.ptb-shell` reserves space for the footer with
`min-height: calc(100dvh - 69px)` (`85px` below 768px). **The footer is 200px tall at desktop and
180px on mobile.** So the page is *unconditionally* taller than the viewport by the difference,
even when its content fits comfortably:

| Viewport | `maxScroll` | Predicted `footer − reservation` | Gap, "Back to your cart" → footer |
|---|---|---|---|
| 1280×900 | **131px** | 200 − 69 = **131** | 139px |
| 1440×1024 | **131px** | 200 − 69 = **131** | **258px** |
| 390×844 | **95px** | 180 − 85 = **95** | 108px |

The arithmetic matches exactly at every width, which is what identifies the constant as the cause.

Two consequences, both reported:

1. **Item 8** — the "large empty vertical gap between Back to your cart and the footer" is this.
2. **It is why item 7 can happen at all on a page whose content fits.** The page is always
   scrollable, so any scroll slides the heading under the fixed header.

**I did not change it, deliberately.** `.ptb-shell` is shared by five routes, and `RotatingHero`'s
`.rh-shell` carries the **identical** `69px`/`85px` constants across roughly fifteen more.
`PageTopBand`'s own docblock states the two must agree value for value. So fixing it is a
visible layout change to ~20 public routes, or a deliberate divergence from a documented contract —
either way an owner decision, not a bug fix I can take inside this loop. `tools/browser/uicheck.js`
would not have caught it: it asserts blank space *below* the footer, not the gap above it.

**Recommendation:** correct the reservation to the measured footer height, in `PageTopBand` and
`RotatingHero` together, and add the gap-above-footer assertion to `uicheck.js`. Awaiting
instruction.

### Second item for the owner, also not fixed

At **320px the number segment has only 88px of text room**, because the `+91 India` select takes
174px of the 288px available. No ten-digit mask of any grouping fits — I measured five
(`00000 00000`, `0000000000`, `00000 0000`, `00 00 00 00`, `000 000 0000`): all exceed 88px, while
all fit from 360px up. **A real ten-digit number a shopper types also clips at 320px.** That is
pre-existing and not introduced here, and narrowing the select is a visible change to a shared
control. Reported, not fixed.

### Third item, out of scope

`src/pages/get.tsx` passes the **identical** `placeholder="9876543210"` to the same component, so
it carries the same trap. I left it alone: `/get` is a public page the owner did not report, and
its copy is governed by the public-page process. The component default is now safe, so `/get` only
keeps the old value because it overrides it explicitly.

---

## 7. The fix — two files, 87 insertions, 3 deletions

### `src/components/PhoneField.tsx`

1. **`NUMBER_FORMAT_HINT = '00000 00000'`**, exported, and now the default when no `placeholder`
   prop is given. Zeros in two groups cannot be read as a value — an Indian mobile number never
   begins with 0 — and it is **language-neutral**, which a worded hint would not be: placeholder
   text is an attribute and `SupportWidget`'s translation walker rewrites text nodes only, so
   "10-digit number" would stay English for every non-English shopper. The prop still overrides.
2. **New optional `onInvalid` prop**, forwarded to the number input. This exists so a consumer can
   mirror the browser's refusal into its own error region **without removing `required`** — so the
   native affordance is kept and the programmatic association is added, rather than one traded for
   the other.
3. **`scroll-margin-top: 128px`** on `.pf-num`, `112px` in a new `@media(max-width:767px)` block.
   On the **input**, not the container, because the input is what the browser scrolls to.

### `src/pages/account/sign-in.tsx`

4. **Dropped the `placeholder="9876543210"` literal**, so the page inherits the safe default.
5. **`onInvalid={ () => setError( MSG.BAD_NUMBER ) }`**. `BAD_NUMBER` ("Enter a valid number.") is
   **not a new string and not a new decision** — it is already what `composeE164` raises for an
   empty value, so this makes the page's existing answer reachable rather than inventing one. It
   stays inside the owner's approved section-6 table, and a test pins that.
   Because `invalid={!!error}` and `describedBy` were already wired, this alone produces
   `aria-invalid="true"` and `aria-describedby="si-hint si-error"` pointing at the existing
   `role="alert"` region. **No new ARIA pattern was introduced.**
6. **`scroll-margin-top: 128px` / `112px` on `.si-input`**, the OTP code field — which needs it
   more, since the code phase is reached by submitting, on a page the shopper has usually already
   scrolled.

`required` is **kept**. Rate limiting, the per-phone OTP probe counter and every Cognito trigger are
untouched. No live-send flag exists or was added.

### After the fix, measured at all six viewports

| | After |
|---|---|
| Placeholder | `"00000 00000"`, not a `^[6-9]\d{9}$` shape, DOM value `""` |
| Native bubble | `"Please fill out this field."` — **kept** |
| Inline error | **`"Enter a valid number."`**, `role="alert"` |
| `aria-invalid` | **`"true"`** |
| `aria-describedby` | **`"si-hint si-error"`**, and the error's own `id` is in that list |
| OTP requests on the empty refusal | **0** |
| Recovery after typing | `USERNAME = "+919123456789"`, code phase reached, no error |

---

## 8. Tests — exact commands and counts

All run in `/Users/wecaredigital/wecare-store/.worktrees/login-fix-20261002`. Python is the parent's
`.venv`; Node resolves packages by ancestor walk-up. Nothing was installed.

| Gate | Command | Baseline (no new tests) | After |
|---|---|---|---|
| Frontend | `npx vitest run` | 61 files / **779 passed** | **63 files / 788 passed, 1 skipped, 0 failed** |
| Python | `/Users/wecaredigital/wecare-store/.venv/bin/python -m pytest tests/ -q` | — | **6751 passed, 1 skipped, 7 xfailed, 0 failed** |
| Typecheck | `npx tsc --noEmit` | — | **exit 0, no output** |
| Lint | `npx eslint` on the 4 changed/added files | — | **exit 0, no output** |
| Build | `node scripts/generate-public-pages.js && npx next build --webpack` | — | **exit 0** |
| Focused | `npx vitest run src/test/SignInEmptyNumberTrap.test.tsx src/test/SignInHeaderClearance.test.ts` | — | **9 passed, 1 skipped** |

**Zero pre-existing failures in either suite**, so there are none to name and none were left behind.
The baseline was measured by moving the two new files aside and re-running, not computed.
`npx next build` without `--webpack` fails here: `next.config.js` pins `turbopack.root` to the
worktree.

### New focused tests, and the layer each had to live at

**`src/test/SignInEmptyNumberTrap.test.tsx`** (5 cases) — every existing case in
`AccountSignIn.test.tsx` types a value first, so all of them walked straight past the one state the
shopper was stuck in.
- the placeholder cannot be read as a real number. **Asserts the property, not the old literal**: any
  mask whose digits could begin a real number is the defect, whatever its grouping.
- `required` is still present — the inline error was *added* to the native behaviour, not substituted.
- the refusal reaches the page's error region, with the message, `role="alert"`, `aria-invalid="true"`,
  and the error's `id` genuinely inside the input's `aria-describedby`.
- the message is one already in `SECTION_6_MESSAGES` — so this cannot drift into a seventh string.
- the recovery path still composes exactly one `+91`.

**`src/test/SignInHeaderClearance.test.ts`** (4 cases + 1 conditional skip) — reads
`out/account/sign-in/index.html`, because **a scroll offset only exists where there is layout and
jsdom has none**. A source-string assertion would pass on a declaration that could never reach its
element, which is exactly the failure `2f742ec6` fixed in `PillButton`. So it asserts two properties
of the shipped artifact: the clearance is at least the header's own height at **both** header
heights (catching a mobile override written as 0, or copied from the wrong header), and the
selector's `jsx-*` hash can actually reach the element.
One honest narrowing, named in the file: `.si-input` dresses the code field, which is **not in the
static export** (the export is the phone phase), so for it the hash check narrows to "a hash this
page actually stamps". Writing the stronger assertion there would be a test that looks tighter and
fails for the wrong reason. **This narrowing was forced by the test failing first** — I wrote the
strict version, it correctly reported no `.si-input` element, and that is how I learned it.
Skips with a message naming the build command when `out/` is absent, so it never passes quietly.

### Revert checks — each fix is load-bearing

| Reverted | Result |
|---|---|
| Placeholder back to `9876543210` | **1 failure** (the placeholder case). Restored → 5 pass |
| `onInvalid` removed | **3 failures** (message, approved-table, recovery). Restored → 5 pass |
| Both `scroll-margin-top` declarations stripped, **rebuilt** | **2 failures** — `.pf-num ships no scroll-margin-top at all`, same for `.si-input`. Restored and rebuilt → 4 pass |

---

## 9. Live versus simulated

| Layer | Live | Simulated |
|---|---|---|
| Pool schema, triggers, `AllowAdminCreateUserOnly`, alias versions, `CustomerSessionsTable` count | real read-only AWS calls, account 775261844268 | nothing |
| Page render, computed styles, scroll geometry, pixel bleed, keyboard order, placeholder fit | real Chrome, real `next build --webpack` export, real styled-jsx output, real CSS cascade | nothing |
| Typing, React state, `composeE164`, the submitted payload, the `invalid` handler | real React, real handlers, real `normaliseMobile` | the `InitiateAuth` challenge response |

`window.fetch` was stubbed via `Page.addScriptToEvaluateOnNewDocument`, so it intercepts before app
code runs. **Both the Cognito host and `/api/` are intercepted, so no OTP could leave the machine
even accidentally.** On the empty-submit path the request count was **0** at every viewport.

## 10. What I could NOT verify

1. **That the fix works in production.** It is **UNDEPLOYED** and deliberately so. Per
   `lambda-snapstart-deploy.md` nothing here is live until the owner ships it — and this change is
   frontend-only, so it needs an Amplify build of `d22dm4b0jn71jw`, not a Lambda deploy.
2. **That a shopper can now log in.** They cannot. §0's server fault is live and unfixed.
3. **A real WhatsApp OTP delivery, and the real handset round trip.** No live send is authorised;
   the owner QA number was not messaged.
4. **The owner's actual browser, OS and viewport.** Chrome 1280×760 / 1280×900 / 760×900 / 390×640 /
   390×400 / 320×568 only. No Safari, no real iOS or Android, no real on-screen keyboard — the
   390×400 case *models* a keyboard-reduced viewport by resizing, which is not the same as a real
   `visualViewport` inset.
5. **Whether the owner had typed a number before the screenshot.** The native bubble proves the
   field was empty *at submit*; it cannot prove they never typed. The placeholder trap explains the
   screenshot; it does not prove it is the whole of what they experienced.
6. **The exact scroll position in the owner's screenshot.** I reproduced a state that matches it
   item for item, but the gesture that produced theirs is inferred, not observed.
7. **Any screen reader.** ARIA wiring is asserted structurally (`aria-invalid`, and the error's `id`
   inside `aria-describedby`). No VoiceOver, NVDA or JAWS run. Per the repo's standing note, full
   WCAG validation needs manual assistive-technology testing and expert review.
8. **`/get`'s behaviour** after the component default changed — it still passes its own placeholder
   explicitly, so it is unaffected, but I did not re-exercise that page in a browser.

---

## 11. Not done, and not asked for

- No deploy, no version publish, no alias move, no Amplify build trigger.
- **No Cognito call of any kind.** No `update-user-pool`, no `add-custom-attributes`. The triggers
  were measured present, so nothing was needed; had they been missing I would have reported it
  rather than repaired it.
- No `secretsmanager get-secret-value` / `batch-get-secret-value`, in any spelling. No credential on
  any command line.
- No merge, cherry-pick or edit of `fix/otp-confirm` or its worktree.
- No change to `src/lib/customerAuth.ts`, any Lambda, any env value, any rate limit, or the
  per-phone OTP probe counter.
- No change to `gift_card_store.py`, `test_gift_card_store.py`, or anything under
  `.agents/tasks/wix-coupons-giftcards-20261001/`. All work stayed inside this worktree; the parent
  checkout was not written to.
- `.scratch/` is gitignored and was deleted after the run.
