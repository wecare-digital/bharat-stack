# Customer WhatsApp OTP confirm failure + doubled sign-in label — findings

Worktree `/Users/wecaredigital/wecare-store/.worktrees/otp-fix`, branch `fix/otp-confirm`,
**rebased onto `origin/stack` at `bb1cf39b`** (started from `72a2c5d3`). Not pushed.

**Two commits, deliberately separate:**

| SHA | Commit | Ships via |
|---|---|---|
| `c86e82be` | `fix(auth): derive customer session identity from the Cognito sub` | **Backend.** Shared layer — needs `wecare-customer-session`, `wecare-checkout` and `wecare-wix-store` republished with their `live` aliases moved |
| `a815a353` | `docs: correct the change-authority row after rebasing onto the upstream pill fix` | docs only |
| `d171fd10` | `fix(a11y): name the pill by its visible text, fixing WCAG 2.5.3 Label in Name` | **Frontend**, via Amplify |

They are kept apart on purpose: different deployment paths, different blast radius, different
rollback. An accessibility change must not be entangled in a revert of the customer payment path.

Nothing was deployed, no version published, no alias moved, no pool mutated, no credential read.

---

## 0. Read this first — the pill scoping fix is NOT mine

Two corrections to the brief's framing, both discovered mid-task and both load-bearing.

**The pill repair landed upstream while I was working, in `2f742ec6`** ("fix(get): share the
sign-in controls, add the home top section, repair the pill", #185). That commit reached the *same
root cause I had proved independently* — segments hoisted into `const inner = (<>…</>)`, so
styled-jsx never stamped them — and fixed it the same way, by inlining the segments into both
branches. **I dropped my version of that fix entirely and rebased onto theirs.** My own C1 diff and
duplicate source guards are discarded, not merged; their two anti-re-hoist guards are left intact.
Attribution is theirs. What I kept is one *additive* test they do not have (see §4).

**The "doubled label" turned out to be TWO defects, and the second was a design call I escalated
rather than took.** `2f742ec6` repaired the *rendering*; `/account/sign-in` still passed
`label="Sign in"` and still showed two segments. Measured after that rebase, the confirm button
was:

| | |
|---|---|
| `textContent` (raw DOM) | `'Sign inConfirm code'` — still literally the reported string |
| `innerText` (what a sighted user reads) | `'Sign in Confirm code'` — now two distinct styled segments |
| accessible name | `'Confirm code'` — the action alone, hiding the visible label |

So the *run-together appearance* was gone, but the control still announced a name that did not
contain its visible text — a **WCAG 2.5.3 Label in Name** failure, Level A, whose real victims are
speech-input users: "click Sign in" at a button named "Confirm code" does nothing.

Three ways to fix it, two of which change what the owner sees. I implemented the single-label
option, then **reverted it before committing** and escalated, because it would have deleted a
label the owner's design brief asked for and **re-diverged `/account/sign-in` from `/get`, which
`2f742ec6` had just unified onto this identical pill on owner instruction**.

**Owner chose option C**, now implemented in `d171fd10`: drop `aria-hidden` from both segments and
drop `aria-label`, so the name becomes the visible text on all three surfaces with **zero pixels
moved**. Full measurement in §3.

**The auth outage in §1 is untouched by any of this** and is the primary fix in this branch.

---

## 1. Root cause, with the evidence that proves it

**`lambda_utils/customer_auth.authenticate()` required a Cognito attribute that does not exist in
the customer pool's schema, so it raised for every customer token, 100% of the time.**

### Measured live, 2026-10-02

| Fact | How measured |
|---|---|
| Pool `us-east-1_46ULYuukt` (`WECARE.DIGITAL-CUSTOMERS`) has exactly ONE custom attribute: `custom:partner_waba_id`. `custom:customer_id` is **absent from the schema** | `DescribeUserPool` → `has_custom_customer_id: false` |
| The pool's one user (CONFIRMED) carries `phone_number`, `phone_number_verified`, `name`, `custom:partner_waba_id`, `sub` — no customer id | `ListUsers`, attribute **names** only, no values read |
| 4 × `[WARNING] {"event":"customer_auth_no_customer_id"}` on 2026-10-02 at **02:44:00.283Z, 02:45:11.732Z, 05:33:55.013Z, 06:02:13.625Z**, on log streams tagged `[5]` (the live alias version) | `FilterLogEvents /aws/lambda/wecare-customer-session` |
| `stack-wecare-digital-CustomerSessionsTable` holds **0 items** — the exchange has never once succeeded | `DescribeTable` |
| Every other customer-keyed table also empty: OrderTable 0, PaymentAttemptsTable 0, WixOrderIds 0, WixOrdersCache 0. `CustomersTable` **does not exist** | `DescribeTable` ×6 |

A Cognito attribute absent from the schema cannot be set on a user, so the read returned `''` for
every token ever issued.

> **One measurement caveat worth recording.** My first CloudWatch query returned zero events and
> looked like it contradicted the plan. The filter pattern needed quoting
> (`"customer_auth_no_customer_id"`); unquoted it matched nothing. The events were always there.

### The failure chain, end to end

1. `requestOtp` → Cognito `InitiateAuth CUSTOM_AUTH` → the pool trigger sends the WhatsApp code.
   **This works**, and never touches `customer_auth`. That is why send succeeded.
2. Correct code → `RespondToAuthChallenge` **succeeds**, returning `AccessToken` + `RefreshToken`.
   The customer is authenticated at this instant.
3. Because a `RefreshToken` is present, `submitOtp` POSTs `{action:'exchange'}` to
   `/api/ecommerce/customer-session`.
4. Handler → `customer_auth.authenticate(event)` → `GetUser` OK → issuer pin OK →
   `custom:customer_id` absent → WARNING → raise.
5. Handler returns **401 `VERIFICATION_REQUIRED`** as a normal return.
6. `submitOtp`: `if (!response.ok) throw new Error('We could not remember this sign-in…')` —
   thrown **before** `storeSession()`, so the valid access token was discarded.
7. `sign-in.tsx` catch → `messageForAuthError(err)`. `err.name === 'Error'`, matching none of
   `TooManyRequests|LimitExceeded|TooManyFailedAttempts`,
   `ExpiredCode|NotAuthorized|ExpiredToken|ResourceNotFound`, or `CodeMismatch` → falls through to
   `return MSG.TRY_LATER` → **"Try again shortly."**

**Which classifier fired: the name-based `messageForAuthError`, on its CATCH-ALL branch.**
Not `messageForVerifyRejection`, and **not** the `>=500` mapping — there is no 5xx anywhere in this
failure. The brief's warning about the ambiguity was correct, and the 401 is what settles it.

**Why CloudWatch looked clean:** the handler returns 401 as a normal return. No raise escapes, no
traceback. The only line is a **WARNING**, which is not error-shaped. The brief's "zero
error-shaped events" reading was accurate — and the function was failing the entire time.

### Blast radius beyond sign-in
`customer_auth.require_customer` also gates `wecare-checkout` and `wecare-wix-store`, so no
customer could check out or load the store catalogue either. The four empty order/payment tables
are consistent with that.

### Commit 87d2c626 is eliminated as the cause of the confirm failure
Its diff touches only button markup and CSS. It does not touch `submitCode`, `submitOtp`, the
form's `onSubmit`, or any session state. The 0-item session table proves the exchange never worked
before it either. It **is** the proven cause of defect 2.

---

## 2. The confirm fix

### B1 — server, the root cause
New `customer_auth.customer_id_from_attributes(attributes)` makes the **Cognito `sub`** the single
authority for session identity, replacing the `custom:customer_id` read in `authenticate()`. All
three existing checks (GetUser liveness, issuer pin, `authorize_resource`) are untouched — only
the *source* of `identity.customer_id` changed.

Why `sub`, and why not the alternatives:

- **Adding the pool attribute is owner work.** `AddCustomAttributes` does exist (the design doc's
  claim that attributes cannot be added after creation is wrong), but it is an **irreversible pool
  schema mutation**, which the hard constraints reserve for the owner, and it would still need a
  backfill plus a stamp on every new user.
- **`CustomersTable` is not available** — measured absent, and nothing in the repo creates it.
- **`sub` is the strongest authority already in the token:** Cognito-assigned, immutable,
  pool-scoped, present on every user, not writable by the app client. It is already the field this
  same handler trusts for refresh-owner identity (`proven.subject != identity.subject`).

It is a **single authority, not a fallback.** "Custom attribute if present, else `sub`" would
silently re-key a customer the day somebody adds and backfills the attribute, orphaning the orders
filed under their old id. A test pins this: adding the impossible attribute must not change the
derived id.

**Shape change, stated plainly.** `identity/customer.py` defines the customer identity concept as
`CUS_<ULID>` and `is_customer_id` validates it; a `sub` is a UUID and does not satisfy that. I
checked both production callers of `is_customer_id` — `email-verification._mark_email_verified`
validates a `customerId` from a **request body**, and `is_checkout_ready` validates a field of a
**`CustomersTable` record**. Neither reads a session identity, and that table does not exist, so
nothing gates on the two agreeing. Manufacturing a `CUS_`-shaped value from the `sub` was rejected
deliberately: it would pass `is_customer_id` while not being a real issued identity, which is
worse than an honest mismatch. The `CUS_<ULID>` remains the customer *record's* identity; see the
follow-up below.

The `customer_auth_no_customer_id` warning and the raise are **kept** for the genuinely impossible
case of a token with no `sub`, and the event name is unchanged on purpose so the existing
CloudWatch evidence of this outage stays searchable.

### B2 — client, the amplifier
In `submitOtp`, `storeSession(token, expiresAt)` now runs **before** the exchange, and a failed
exchange returns `{ accessToken, expiresAt, remembered: false }` instead of throwing.

The reasoning: by that line the Cognito challenge has already succeeded, so the exchange buys
**persistence**, not authentication. Throwing converted a degraded remember-me into a total
sign-in failure *and* discarded a valid token. `restoreSession()` already treats a missing hint as
"sign in again", so `remembered: false` is a state the library already modelled. `remembered?:
boolean` on `CustomerSession` is purely additive.

B2 is worth having even with B1 in place: it is the difference between "the site is down" and
"remember-me is off".

**One extra line beyond the plan, and why.** A 200 whose body fails to parse would still have
thrown at `response.json()` and reproduced the identical symptom. That violates the same principle
B2 exists to establish, so the hint parse degrades instead of throwing. It is pinned by its own
test.

**The MSG table and both classifiers are unchanged**, as instructed. No new message, no new
branch. With B2 in place the exchange failure never reaches the catch-all, and a test asserts
`TRY_LATER` is not rendered on that path.

### B3 — reconciling registration
`auth/customer-registration/_provision_login` stamped `custom:customer_id` in its
`AdminCreateUser` attribute list. Since that attribute is not in the schema, **Cognito would have
rejected the whole call with `InvalidParameterException`** — a latent crash, unreached only because
this function has no deployed Lambda and no API route. The stamp is removed; the `customer_id`
parameter stays because `identity.registration.verify_and_register` calls `provision_login`
positionally. Three stale docstrings/comments claiming `customer_auth` requires that attribute
were corrected in `handler.py`, `identity/registration.py` and `test_registration.py`.

---

## 3. The doubled "Sign inConfirm code" label — diagnosed independently, FIXED UPSTREAM

**A real CSS failure, not a text bug.** `PillButton.tsx` built its two segments in an intermediate
variable (`const inner = (<>…</>)`). styled-jsx only adds its scope class to JSX in the tree it
transforms, so the `<button>`/`<a>` got the hash and the spans did not.

> **Attribution.** I reached this diagnosis and built a fix for it before learning that
> **`2f742ec6` had already landed the same diagnosis and the same fix** on `origin/stack`. My
> version is discarded; the tree now carries theirs. The evidence below is my own independent
> measurement, which corroborates their commit message rather than duplicating their work.

Measured in the **real build output**, pre-fix:

```
CSS shipped     .pill-label.jsx-69f2e5793ae0f718{…}   .pill-action.jsx-69f2e5793ae0f718{…}
markup shipped  <span class="pill-label">             <span class="pill-action">
the button      <button class="jsx-69f2e5793ae0f718 pill">    <-- correctly scoped
```

The hash matched the plan's independent production measurement **byte-identically**, confirming the
local tree is the code that was live. The selectors can never match, so **both segments were
completely unstyled**. Chrome reported, per segment:

```
display: block      background-color: rgba(0, 0, 0, 0)      color: rgb(0, 0, 0)
padding: 0px        font-weight: 400
```

Two bare black text nodes stacked inside a `#1a3a2a` pill — exactly the reported
`"Sign inConfirm code"`. **The cart CTA had the identical defect**, from the same component.

### C1 — scoping. DONE UPSTREAM in `2f742ec6`, verified by me, not reapplied

Their change writes the segments inline in **both** the `<a>` and `<button>` branches. Verified on
the rebased tree:

```
built markup   class="jsx-69f2e5793ae0f718 pill-label"    class="jsx-69f2e5793ae0f718 pill-action"
built CSS      .pill-label.jsx-69f2e5793ae0f718  (3x)     .pill-action.jsx-69f2e5793ae0f718  (4x)
```

Both segments now carry the hash their selectors require. Computed styles in Chrome 154 confirm
the repair end to end: `pill-label` `rgb(26,58,42)` / white / weight 600, `pill-action`
`rgb(95,227,176)` / `rgb(26,58,42)` / weight 700, both `display:flex` — against `display:block`,
`rgba(0,0,0,0)`, weight 400 before.

> A detail worth recording: **the hash is unchanged at `jsx-69f2e5793ae0f718`** across the fix. The
> CSS was always correct; only the markup lacked the stamp. That is why the defect was invisible to
> every source-level and jsdom-level check.

This also fixes the cart CTA, which had the identical defect from the same component.

### C2 — the label/name mismatch. RESOLVED VIA OPTION C, as its own commit

**Escalated, then owner-approved as option C** and implemented in `d171fd10`, kept deliberately
out of the auth commit. What follows records the escalation and the outcome.

The fix: neither segment is `aria-hidden` and there is no `aria-label`, so the accessible name is
the platform's concatenation of the visible text. The `ariaLabel` prop was **removed**, not merely
left unused — while it existed any caller could set a name that disagreed with the screen, which
is exactly how this shipped, so removing it makes the guarantee structural. The cart was its only
user.

| Surface | visible text | accessible name, before | after |
|---|---|---|---|
| `/account/sign-in` phone | Sign in \| Send code | `Send code` | **`Sign in Send code`** |
| `/account/sign-in` code | Sign in \| Confirm code | `Confirm code` | **`Sign in Confirm code`** |
| `/cart` | Checkout \| Proceed | `Proceed to checkout` | **`Checkout Proceed`** |
| `/get` | Collect \| Send code | `Send code` | **`Collect Send code`** |

Read from **Chrome 154's own accessibility tree** (`Accessibility.getPartialAXTree`, the data the
DevTools accessibility pane shows), not inferred from the markup.

**Zero visual change, measured rather than claimed** — the only reason C is worth doing. Computed
style on all three surfaces after the change, identical to the pre-change measurement, with no CSS
touched:

```
.pill-label   display:flex  bg rgb(26,58,42)    color rgb(255,255,255)  weight 600  padding 0px 22px
.pill-action  display:flex  bg rgb(95,227,176)  color rgb(26,58,42)     weight 700  padding 0px 24px
.pill         border-radius 999px   border 2px rgb(26,58,42)
```

`hasAriaLabel:false` and `ariaHiddenSegments:0` on each. `/get`'s `label="Collect"`/`"Pay"` and the
cart's visible "Checkout Proceed" are unchanged.

Revert-checked: restoring `aria-hidden` + `aria-label` fails **all 14** cases of the new property
test.

#### Why C and not B

| | Change | What the owner sees | Cost |
|---|---|---|---|
| A. Leave it | nothing | two-tone pill | 2.5.3 mismatch stays on all three surfaces |
| B. Single-label on sign-in | `label` optional, one mint segment | sign-in loses its "Sign in" segment | re-diverges sign-in from `/get`, which `2f742ec6` had just unified on owner instruction; deletes a label the design brief asked for |
| **C. Chosen** | drop `aria-hidden` + `aria-label` | **nothing** | fixes 2.5.3 on all three surfaces; renames every pill, so five pinned queries had to change |

B is written up as an applicable diff in
[`option-b-single-label.md`](./option-b-single-label.md) and was **not** applied.

#### What I did not touch

`2f742ec6`'s comment-stripping anti-re-hoist source guard is **byte-unchanged**, as is my
`PillButtonBuildScope.test.ts`. Its render-side case kept its segment-presence assertions and had
only its accessibility-tree expectations inverted — asserting both segments were `aria-hidden` and
the name was the action alone *was* the 2.5.3 failure, not a requirement.

#### The original escalation, for the record

Even correctly styled, visible "Sign in Confirm code" with accessible name "Confirm code" is a
**WCAG 2.5.3 Label in Name** mismatch, and `aria-hidden` on a control's own visible label is the
anti-pattern that produces it. I had implemented an optional-`label` single-segment mode and
switched both sign-in CTAs to it.

**I reverted that before committing**, for two reasons that only became visible after the rebase:

1. It removes a visible label the owner's own design brief asked for ("make this style for cart
   login or any other login" — a two-segment pill with a static label).
2. `2f742ec6` had just **unified `/get` and `/account/sign-in` onto this identical two-segment
   pill**, on owner instruction, and `/get` passes `label="Collect"` and `label="Pay"`. Making
   sign-in single-label would re-diverge the two surfaces that commit had deliberately converged.

That is a product call with a user-visible effect, so it is not mine to take inside the loop. The
reverted change is written up as an applicable diff in
[`option-b-single-label.md`](./option-b-single-label.md). See §9 for the three options and a
recommendation.

**The cart keeps its two-segment form** regardless — its left segment ("Checkout") is not a
duplicate of its action ("Proceed").

**One bug of my own, avoided.** My first C2 attempt added `ariaLabel="Send code"` alongside
`action="Sending…"`, which makes the accessible name *not contain* the visible text while busy —
the very 2.5.3 failure C2 exists to fix. Caught and removed before commit.

### Why no test caught it
Under vitest the styled-jsx transform **does not run at all**: `<style jsx>` renders as a plain
`<style>` with **unscoped** selectors, so jsdom sees selectors that *would* match.
`PillButton.test.tsx` even said the colours were "the browser harness's job" — and no browser
harness existed. jsdom cannot observe this class of failure even in principle.

---

## 4. Regression tests

Nine of these fail if the corresponding fix is reverted — verified, not assumed (see §6).

### Python
`tests/test_customer_auth_and_throttle.py`
- **The fixture itself was the blind spot** and is fixed first: `FakeCognito` returned
  `custom:customer_id`, which no user in this pool can carry, so every case passed while
  production answered 401. It now defaults to `REAL_POOL_ATTRIBUTES`, the measured live set.
- `test_the_real_pool_attribute_set_authenticates` — the live attribute set must authenticate and
  yield `customer_id == sub`.
- `test_no_code_path_requires_the_custom_customer_id_attribute` — asserts the **property**, not a
  spelling: adding the impossible attribute must not change the derived id, so a fallback cannot
  be reintroduced.
- `test_a_token_with_no_sub_still_raises` — the remaining impossible case still fails closed.
- `test_the_derivation_is_a_single_documented_authority` — unit coverage of the helper.

`tests/test_customer_session_endpoint.py`
- `test_exchange_succeeds_with_the_real_derivation_and_the_real_pool_attributes` — stubs **only**
  Cognito `get_user` and lets the real `authenticate`, issuer pin and derivation run to a 200 with
  a `csrfToken` and `Set-Cookie`, asserting the session row is filed under the `sub`. Every other
  case in that file monkeypatches `authenticate` away, which is precisely why they were blind.
  Writing it also surfaced that the handler authenticates **twice** on exchange (to prove the
  refresh token belongs to the same customer), so the renewed token must be a customer-pool JWT too.

`tests/test_customer_registration_handler.py`
- Now asserts `custom:customer_id` is **absent** from the `AdminCreateUser` attributes, and that
  the attribute set is a subset of what the pool can actually hold.

### Frontend
`src/test/CustomerSessionRestore.test.ts`
- `keeps a successful sign-in when the session exchange is refused` — `submitOtp` must **resolve**,
  `getSession()` must hold the token, `remembered === false`, no `sessionHint`, and the refresh
  token must not reach either storage.
- `marks a successful exchange as remembered and writes the hint`.
- `treats a 200 with an unreadable body as a degraded session, not a failure`.

`src/test/SignInMessages.test.tsx` — extends its existing discipline (exact approved strings; the
page imports them by name); the seven-string table and no-red assertions are untouched.
- `signs in and shows no error when the exchange is refused (401)` — drives the **real**
  `submitOtp` through a stubbed `fetch`, asserts navigation to the return path, **no**
  `role="alert"`, and explicitly that `signInMessages.TRY_LATER` is not rendered.
- `signs in and remembers the device when the exchange succeeds (200)`.
- `names the confirm button by its action alone, never the concatenation` — and the same for the
  send button. **Rewritten after the rebase.** These originally asserted my C2 behaviour (one
  segment, `textContent === 'Confirm code'`). With C2 escalated rather than applied, they now pin
  the property that holds either way and is what actually keeps every role query working: the
  accessible name is the action alone, `getByRole('button', {name: /Sign in\s*Confirm code/})`
  finds nothing, and both segments are `aria-hidden`. If the owner approves C2 these tighten; they
  do not need rewriting again.
- **A mock-leak defect found while writing these:** an earlier `describe` in that file mocks
  `customerAuth.submitOtp` wholesale and never restores it. These tests exist to run the *real*
  `submitOtp`, so inheriting that mock made the first one silently test nothing (it failed on
  navigation). `vi.restoreAllMocks()` now runs in `beforeEach`, making the block order-independent.

`src/test/PillButton.test.tsx` — my single-label cases and my own source guard are **discarded**;
`2f742ec6`'s version is the base. Worth noting we independently arrived at the *same*
comment-stripping technique, for the same reason: the docblock explaining the rule necessarily
quotes the pattern it forbids, so matching raw source punishes the documentation. That trap caught
my first attempt too.

Option C then required two changes to that file, and the distinction between them matters:

- **Their comment-stripping anti-re-hoist source guard is byte-unchanged.** It is the scoping
  guard, and option C has nothing to do with scoping.
- **Their render-side case kept its segment-presence assertions and had its accessibility-tree
  expectations inverted.** It asserted both segments were `aria-hidden` and that the control
  answered to the action alone. Those two assertions *were* the WCAG 2.5.3 failure rather than a
  requirement, so they now assert the opposite. The exact-name pin stayed exact, moving from
  `'Send code'` to `'Collect Send code'`.
- Two pre-existing cases in the first describe block were likewise inverted: the old contract
  explicitly asserted the name must **not** be the concatenation, which is precisely what 2.5.3
  requires it to be.

**New in option C: `src/test/PillButtonAccessibleName.test.tsx`** — 14 cases asserting the
property (accessible name contains every visible segment, in reading order) across all ten real
prop shapes, including both busy states on every surface, plus the structural guards: no segment is
`aria-hidden`, no `aria-label` is set, passing the removed `ariaLabel` prop has no effect, and
`describedBy` still works. Revert-checked: restoring `aria-hidden` + `aria-label` fails all 14.

The five exact-name pins were updated across `AccountSignIn`, `SignInMessages`,
`PublicPageTopBand`, `CartCheckout` and `GetPage`. None was loosened to a regex or substring
matcher — `GetPage`'s pre-existing `/Send code/i` was in fact **tightened** to the exact
`'Collect Send code'`. The suite's only predicate matcher lives in the property test, where
"contains" is the criterion itself rather than a relaxed pin.

`src/test/PillButtonBuildScope.test.ts` (new, **kept — the one additive piece**) — the only layer
where scoping is observable. Reads `out/account/sign-in/index.html`, collects every `.pill*`
selector hash from the inlined `<style>` blocks and every pill-bearing `class` attribute from the
markup, and asserts each pill-classed element carries a hash its selector was written with, with a
second case narrowed specifically to `pill-label` and `pill-action`.

It is **not a duplicate of their guards, and this is the reason it was kept**: their guards assert
the *shape of the code* and enumerate the spellings they know about (`const inner`,
`const segments`, `function renderSegments`). A fourth way of lifting the JSX out of the return
tree — a child component, a `.map`, a render prop — passes all three and still ships unstyled.
This asserts the *outcome in the built artifact*, which cannot be evaded that way. The narrowed
case matters too: it still fails if only the **outer** control is scoped, which is exactly how the
defect presented. It asserts the property ("the selector can reach the element") rather than any
particular hash, and **skips with an explicit message naming the build command** when `out/` is
absent, so it never silently passes.

---

## 5. Live versus simulated

The OTP **send** cannot be exercised without an owner handset and no live-send flag may be
touched, so the confirm round trip was reproduced by canning exactly **two** network responses,
with everything else real. Browser: **Chrome 154.0.8037.93, headless, driven over CDP** (Node 24's
global `WebSocket`; no packages installed). The page served was the **real `next build --webpack`
static export**, not a dev bundle.

| Layer | LIVE | SIMULATED |
|---|---|---|
| Pool schema, pool user attributes, CloudWatch warnings, all six table item counts | real AWS read-only calls against account 775261844268 | nothing |
| Pill rendering, both phases, 1280/360/320 px and `prefers-reduced-motion: reduce` | real browser, real build, real styled-jsx output, real CSS cascade, real `getComputedStyle` | nothing |
| Reaching the code phase | real React state, real submit handler, real `composeE164`/`normaliseMobile` | the `InitiateAuth` challenge response |
| Confirm classification | real `submitCode`, real `messageForAuthError`, real `submitOtp`, real `storeSession` | `RespondToAuthChallenge` success, and the session endpoint's 401 / 200 |
| Server derivation | real handler + real `customer_auth` under pytest | Cognito `get_user` |

**Not exercised live:** a genuine Meta WhatsApp message to a handset, and the deployed Lambda (the
fix is not deployed). The owner QA number's masking is unchanged — `*******0044` stays ambiguous
between the QA recipient and the live business number; disambiguate on direction, channel or the
`wecare-customer-whatsapp-auth` delivery id.

### What the browser showed

**PRE-FIX** (defects reproduced before any change):

| Observation | Value |
|---|---|
| Sent message | `Code sent on WhatsApp to *******0044.` (the owner's screen) |
| After a **correct** code | alert **`Try again shortly.`** |
| Navigated | no |
| `sessionStorage` access token | **`null`** — the valid token was discarded |
| Confirm button `textContent` | **`Sign inConfirm code`** |
| Segment classes / hash | `pill-label`, `pill-action` — **no `jsx-*` hash** |
| Button class | `jsx-69f2e5793ae0f718 pill` — correctly scoped |
| Segment computed style | `display:block`, `background-color:rgba(0,0,0,0)`, `padding:0px`, `font-weight:400` |
| Network | 3 requests; the only non-200 is the **401** on `/api/ecommerce/customer-session`. **No 5xx**, confirming the name-based catch-all fired |

**POST-FIX**, exchange **401** (degraded remember-me):

| Observation | Value |
|---|---|
| `finalUrl` / title | `http://127.0.0.1:3099/cart/` — `Your cart — WECARE.DIGITAL` |
| Alert | `''` — none |
| `sessionStorage` token | `canned.access.token` — **stored** |
| `localStorage` hint | `null` — correctly not remembered |

**POST-FIX**, exchange **200**: same navigation and token, **and** the hint lands in
`localStorage` (`{"csrfToken":"canned-csrf",…}`).

Both were re-measured after every rebase AND again after option C landed, and are unchanged: 401 →
`/cart/`, no alert, token stored, no hint; 200 → same plus the hint written. So the auth fix holds
on the upstream tree, not just on my branch point.

**POST-FIX pill, as committed** (upstream `2f742ec6`'s fix, my measurement) — two segments, both
hashed and correctly styled:

| Segment | class | computed |
|---|---|---|
| `pill-label` "Sign in" | `jsx-69f2e5793ae0f718 pill-label` | `display:flex`, `rgb(26,58,42)` bg, `rgb(255,255,255)` text, weight 600 |
| `pill-action` "Confirm code" | `jsx-69f2e5793ae0f718 pill-action` | `display:flex`, `rgb(95,227,176)` bg, `rgb(26,58,42)` text, weight 700 |

Accessible name `Confirm code`; `innerText` `Sign in Confirm code`; `textContent`
`Sign inConfirm code`. The run-together *appearance* is gone; the two visible labels remain — the
open decision in §9.

*(The single-segment, `jsx-b7761065a244bd3`, `.pill-solo` measurements I took earlier were of my
own C2 build, which is not what shipped in this commit. They are superseded by the table above.)*

**Viewports:** 460×52 at 1280 px, 328×52 at 360 px, 288×52 at 320 px — no overflow at any width,
font and padding stepping down via the existing media query. Under
`prefers-reduced-motion: reduce` the computed `transition` is `none`.

**Cart pill** (seeded cart, since it only renders with items): **two** segments, both now hashed
and styled — `pill-label` `rgb(26,58,42)`/white/600/22 px and `pill-action` mint/dark/700/24 px
with the 2 px divider — `aria-label` still `Proceed to checkout`, no `.pill-solo`. So the cart's
deliberate treatment is preserved, and its rendering is **incidentally repaired** by C1, because it
was shipping unstyled too.

---

## 6. Revert checks — the fixes are load-bearing

Each fix was reverted in place and the gates re-run, to prove the new tests would have caught the
defects rather than merely passing alongside them.

| Reverted | Result |
|---|---|
| `customer_id_from_attributes` back to `custom:customer_id` | **14 pytest failures**, including all four new auth cases and the new endpoint case. Restored → 45 pass |
| `submitOtp` back to throwing on a failed exchange | **2 vitest failures**: the library case and the page-level 401 case. Restored → 20 pass |
| Segments re-hoisted into `inner`, then rebuilt | Built markup returned to bare `class="pill-action"` / `class="pill-label"` with **no hash** — the defect reproduced — and the **build-scope test failed**. Restored and rebuilt → clean. This check was run against my own C1 before the rebase; it is the evidence that `PillButtonBuildScope.test.ts` genuinely catches the defect, which is why that test was the one piece kept |

---

## 7. Gates — exactly what was run

All in `/Users/wecaredigital/wecare-store/.worktrees/otp-fix`. The worktree had no `.venv` and no
usable `node_modules`, so: `.venv` is a symlink to the parent's (gitignored), and Node resolves
packages by **ancestor walk-up** to `/Users/wecaredigital/wecare-store/node_modules` — verified
with `require.resolve`. A pre-existing `node_modules/node_modules` symlink was created one level
too deep and does nothing; it was left alone as harmless and gitignored. **Nothing was installed,
and nothing in the parent working tree was modified.**

All figures below are from the tree as it stood at the **first** review: `d171fd10` on
`fix/otp-confirm` (auth commit `c86e82be`, a11y commit `d171fd10`), rebased onto `origin/stack`
at `bb1cf39b`. `origin/stack` moved **seven** times during this task and the gates were re-run
after each rebase; only the last run is reported.

> **Superseded, see §10.** Those commits no longer exist under those hashes — the branch was
> rebased again after this was written (`c86e82be`→`3ce4936b`, `a815a353`→`1b115fd5`,
> `d171fd10`→`2b581d8b`) and the whole branch has since been merged into `origin/stack`. §10
> carries the final measurement, on the tree that was actually gated, and explains why one true
> pass count here reads as a different true pass count there: **the two pytest invocations
> collect different numbers of tests.** `pytest tests/ -q` collects 6761; plain `pytest -q`
> collects 6798, because it also picks up
> `amplify/functions/messaging/whatsapp-business-api/tests/`. Always state which was run.

| Gate | Command | Baseline on `72a2c5d3` | Final |
|---|---|---|---|
| Frontend tests | `npx vitest run` | 59 files / 799 passed | **63 files / 803 passed, 0 failed** |
| Python tests | `.venv/bin/python -m pytest tests/ -q` | 6749 passed, 5 failed | **6748 passed, 5 failed** (all 5 pre-existing upstream, parity-verified), 1 skipped, 7 xfailed |
| Targeted customer tests | `pytest tests/test_customer_{session_endpoint,auth_and_throttle,session,whatsapp_auth,registration_handler}.py -q` | 96 passed | **101 passed** |
| Typecheck | `npx tsc --noEmit` | — | **exit 0, no output** |
| Lint | `npx eslint <9 changed files>` | — | **exit 0, 0 errors** (4 warnings, see below) |
| Build | `node scripts/generate-public-pages.js && npx next build --webpack` | succeeds | **succeeds, 0 errors** |

`npx next build` without `--webpack` fails here: `next.config.js` pins `turbopack.root` to the
worktree and Turbopack will not resolve `next` through the ancestor walk-up. `--webpack` is required.

**The 4 lint warnings are pre-existing and not mine.** All four are in `src/pages/cart.tsx` at
lines 405, 429, 456 and 475 (`react-hooks/set-state-in-effect` and three
`@next/next/no-location-assign-relative-destination`). My only edit to that file is at lines
639-654. Confirmed by linting the pre-change version of the same file: identical 4 warnings,
0 errors.

### The 818 → 803 vitest movement, fully accounted for

An intermediate run reported 818 and the final reports 803, having dipped to 789. I first called
the drop "upstream churn", which was an assumption rather than a measurement. It is now traced
exactly, because 29 tests vanishing while a file was added is also what a rebase silently dropping
someone's cases looks like.

**Cause: one data-driven `it.each` whose input array was deliberately shrunk.**
`src/test/MissingUrlNavigation.test.tsx` line 15 is `it.each( retired )( … )`, and `da78ef68`
("fix: purge obsolete customer link sources and Wix page inventory", which also renamed that file
from `RetiredUrlNavigation.test.tsx`) cut that array from **32 entries to 2**:

```
-const retired = [ 32 retired public paths ];
+const retired = [ '/release-check-missing-page', '/release-check-missing-page/nested' ];
```

| Step | Files | Tests |
|---|---:|---:|
| after first rebase, with my auth tests | 61 | 818 |
| `it.each( retired )` cases removed by `da78ef68` | | **−30** |
| `src/test/CurrentCustomerUrls.test.ts` added by `da78ef68` | **+1** | **+1** |
| after final auth-commit rebase | 62 | **789** |
| my `PillButtonAccessibleName.test.tsx` (option C) | **+1** | **+14** |
| 2.5.3 pins and inversions across 6 existing files | | **net 0** |
| **final** | **63** | **803** |

That accounts for the whole movement. Nothing of mine or anyone else's was dropped: the 30 tests
that disappeared were parametrized cases over a list the owner shrank on purpose, in the same
authorized public-path-removal work as `c7afae00`.

### Pre-existing Python failures: the brief's 5 were fixed, and 5 DIFFERENT ones arrived

This moved twice during the task, so the final state is stated first:

**Final tree: 5 failed, 6748 passed, 1 skipped, 7 xfailed. I cause none of the 5.** Measured by
parity rather than asserted — a clean worktree at `origin/stack` (`bb1cf39b`) with none of my
commits applied fails **the same 5**:

```
tests/test_url_host_routing_rules.py::test_only_host_canonicalisation_is_an_explicit_redirect
tests/test_url_host_routing_rules.py::test_converged_configuration_is_not_rewritten
tests/test_url_host_routing_rules.py::test_unknown_redirect_removed_without_touching_proxy_rules
tests/test_url_host_routing_rules.py::test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot
tests/test_legacy_redirect_rollback_snapshot.py::test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations
```

These are **not** the 5 the brief named. They are new, and they came in with the latest upstream
routing work (`bb1cf39b`, "Contribution amounts … and the /zip → /shipments 301"). Same area, same
file in four cases, different test names. Out of scope and left alone, per the same instruction
that covered the original set.

### The brief's original 5 were fixed upstream, not by me

The brief asked me to report `tests/test_url_host_routing_rules.py`'s 5 failures separately and not
fix them. I measured them at baseline and confirmed them untouched by my work — and then the rebase
made the point moot: **`c7afae00` ("test(routing): pin the owner-instructed [retired public path ef531503] removal instead
of the retired redirects") fixed them upstream.** On the committed tree that file is 13 passed / 0
failed, and the full Python suite has **zero failures of any kind**.

Recording this rather than quietly dropping it, because "5 known failures" was a stated premise of
the task and it is no longer true. For the record, the baseline set was:

```
test_no_sanctioned_redirect_can_shadow_a_passthrough_in_the_live_shape
test_the_provisioner_emits_only_the_two_sanctioned_exceptions
test_the_provisioner_now_PRESERVES_the_host_rule
test_provisioner_keeps_only_approved_home_redirects
test_provisioner_preserves_www_and_runtime_rewrites
```

### Failures I caused and fixed
One, found by the full suite and not left behind:
`test_customer_registration_handler.py::test_verify_creates_the_customer_and_provisions_a_login`
asserted the `custom:customer_id` stamp I removed. Updated to assert its **absence**, with the
reason recorded in the test.

---

## 8. Not done here — owner work

- **No deploy, no `publish-version`, no alias move.** Per `lambda-snapstart-deploy.md` this is not
  live until a version is published and the `live` alias moves. `customer_auth` is in the **shared
  layer**, so **three** functions need republishing: `wecare-customer-session` (live **v5**),
  `wecare-checkout` and `wecare-wix-store`. `scripts/snapstart_publish.py` must run.
- **No `update-user-pool` and no `add-custom-attributes`.** B1 is chosen precisely so no pool
  mutation is required. The attribute route is additive but irreversible, and belongs to the owner.
- **No credential read, no live-send flag change, no masking change.**

### Follow-ups recorded, not actioned
1. **Session identity vs record identity.** Sessions are now keyed on the Cognito `sub`; the
   customer *record* identity remains `CUS_<ULID>`. Nothing gates on the two agreeing today
   (`CustomersTable` does not exist and all order tables are empty), but whoever creates that table
   must decide which is the join key **before** any row exists.
2. **`stack-wecare-digital-CustomersTable` is missing** and no script creates it (design C-5). Two
   `is_customer_id` call sites are dead until it exists.
3. **Design doc C-1 is wrong** — `.agents/tasks/customer-session-20261001/design.md` claims Cognito
   cannot add a custom attribute after creation. `AddCustomAttributes` exists; what cannot be done
   is deleting one or changing its type.
4. **The cart pill's own WCAG 2.5.3 question** — visible "Checkout Proceed" vs name "Proceed to
   checkout". Left alone as instructed; now visible rather than hidden by the styling bug. Same
   question as §9, same answer needed.
5. **`wecare-customer-registration` has neither a deployed function nor a route**, so the
   unregistered branch of `sign-in.tsx` would still fail if a new number reached it.

---

## 9. The escalated decision — two visible labels in one button (RESOLVED: option C)

Raised rather than decided, because every available fix changes what the owner sees.

**The finding.** `/account/sign-in`'s pill shows two labels ("Sign in" + "Confirm code") while
announcing one ("Confirm code"). That is a **WCAG 2.5.3 Label in Name** mismatch, and
`aria-hidden` on a control's own visible label is the pattern that causes it. It is also still the
literal `textContent` the owner reported, `"Sign inConfirm code"`.

**Why I did not fix it.** It is no longer a rendering bug — `2f742ec6` fixed that, and the pill now
renders as the intended two-tone control. What remains is the *design*: the owner asked for this
two-segment treatment, and `2f742ec6` had just unified `/get` onto the identical pill with
`label="Collect"` / `label="Pay"`. Removing sign-in's label would re-diverge the two surfaces that
commit deliberately converged.

**The three options.**

| | Change | What the owner sees | Cost |
|---|---|---|---|
| **A. Leave it** | nothing | two-tone pill, "Sign in \| Confirm code" | 2.5.3 mismatch stays on sign-in, cart and `/get` |
| **B. Single-label on sign-in only** | my reverted C2 — `label` optional, one full-radius mint segment | sign-in loses its "Sign in" segment; `/get` and cart keep theirs | satisfies 2.5.3 on sign-in; re-diverges the surfaces just unified |
| **C. Keep two segments, fold the label into the name** | drop `aria-hidden` from `pill-label`, remove `aria-label`, let the name become "Sign in Confirm code" | nothing changes visually | satisfies 2.5.3 everywhere with no visual change — **but** it renames every pill, so `getByRole('button', {name:'Confirm code'})` breaks across `AccountSignIn`, `SignInMessages`, `CartCheckout`, `GetPage` and `PillButton` tests |

**C is the behaviour-preserving option** and is probably the right one, since it fixes the actual
accessibility defect without touching the owner's design — but it changes the accessible name of
every pill on the site, which is a visible contract several test files pin deliberately, so it is
not a silent edit either.

**Option B is written up as an applicable diff** in
[`option-b-single-label.md`](./option-b-single-label.md) — the exact edits, the `ariaLabel` trap to
avoid, the five test files that follow, and why option C may be preferable. Nothing in it is
applied.

**Recommendation.** Take **C** if the owner's two-tone design is to be kept, which the `/get`
unification suggests it is; take **B** only if the owner genuinely meant "there should be one
label on this button". **A** is tenable only as a deliberate, recorded deferral.

---

### RESOLVED: option C was authorized by the ORCHESTRATOR, implemented in `d171fd10`

**Corrected 2026-10-02 after review.** This section previously read "the owner chose C". That
was wrong in a way that matters: the authorization came from the **orchestrator**, not from the
site owner, and none of the owner's own messages mentions the pill, its accessible name or WCAG
at all. The review flagged the claim as unevidenced and it was right to. The authorization is
now a task artifact — [`option-c-authorization.md`](./option-c-authorization.md), written by the
orchestrator who gave it, carrying the decision, the date, the scope and the five conditions.
Read "authorized" as orchestrator-level, which is what it is.

Approved with five conditions, all met:

| Condition | How it was met |
|---|---|
| 1. Separate commit, not entangled with the auth fix | `d171fd10`, frontend only. The auth commit `c86e82be` contains no option-C change |
| 2. Update pinned queries to the new EXACT names, do not loosen to regex/substring | Exact strings written in `AccountSignIn`, `SignInMessages`, `PublicPageTopBand`, `CartCheckout`, `GetPage`, `PillButton`. `GetPage`'s pre-existing `/Send code/i` was **tightened** to the exact `'Collect Send code'`. The suite's only predicate matcher is inside the property test, where "contains" is the criterion itself |
| 3. Add the property test, not just the new spellings | `src/test/PillButtonAccessibleName.test.tsx` — 14 cases asserting the name contains every visible segment in reading order, across all ten real prop shapes including both busy states |
| 4. Zero visual change, verified | Chrome 154 computed style identical on all three surfaces; AX tree read directly. Table in §3 |
| 5. Leave `2f742ec6`'s guards and the build-scope test alone | Its comment-stripping source guard and `PillButtonBuildScope.test.ts` are byte-unchanged. Its render-side case kept its segment-presence assertions; only its accessibility-tree expectations were inverted, because those **were** the 2.5.3 failure |

Three details worth carrying:

- **The `ariaLabel` prop was removed, not merely unused.** While it existed, any caller could set a
  name that disagreed with the screen — exactly how this shipped. Removing it makes the guarantee
  structural: there is no longer a way to express the bug. A test asserts that passing it has no
  effect.
- **The name is computed through Testing Library's own `*ByRole` matching**, the same
  `computeAccessibleName` every other role query uses. Importing `dom-accessibility-api` directly
  was tried first and `tsc` cannot resolve its types through that package's `exports` map; the role
  query avoids both the import and a suppression, and is the more faithful measurement.
- **The comparison is per segment, not against `textContent`.** `textContent` is the raw
  concatenation with no separator (`"Sign inContinue"`) while the name algorithm joins with a
  space, so `name.contains(textContent)` fails on a *correctly* named control — a bug in the
  assertion, not the component. jsdom computes no layout, so `innerText` cannot supply the spacing
  either. This cost one wrong first attempt.

**Nothing in §1–§2 depends on this.** The auth fix is complete, green and independently
deployable, which is why it is a separate commit.

---

## 10. Review iteration 2 — every finding, and what actually happened to it

`review.json` returned **CHANGES_REQUESTED** with 7 findings (3 blocking). Before any of that is
discussed, one fact changes how the rest reads.

### 10.0 This task was being worked by TWO sessions at once, and most of it landed elsewhere

Measured, not inferred. I began at `d171fd10` with a clean worktree. During my first full pytest
run, **HEAD moved underneath me twice** and `origin/stack` three times:

| Time | What happened |
|---|---|
| 14:03 | I start. `HEAD = d171fd10`, worktree clean, `origin/stack = bb1cf39b` |
| 14:36 | `HEAD = fe893c81` — another session commits findings 1, 2, 3 and 4 **into this worktree** |
| 14:37 | The branch is **rebased**: `c86e82be`→`3ce4936b`, `a815a353`→`1b115fd5`, `d171fd10`→`2b581d8b`, `fe893c81`→`c37165ad`, plus a new `00d3838a` |
| 14:43 | `origin/stack = 07e2c016`, which **already contains the whole branch** plus finding 6's fix |
| 14:47 | I fast-forward to `07e2c016` (pure fast-forward; `HEAD` was an ancestor, nothing lost) |
| 14:57 | `origin/stack = 8c46b132` and still moving |

So the branch was pushed by another session while I was reviewing it, against the brief's "do
NOT push". Nothing was destroyed — `origin/stack` is a superset of everything on the branch at
every point I measured, and my two working-tree files were never touched by any of it. But it
means the honest answer to "did you fix the findings" is split, and it is recorded that way
below rather than claimed wholesale. **This is the fourth time work on this repository has been
duplicated across concurrent sessions.**

### 10.1 Findings 1 and 4 — the false `0 failed` and the stale rebase reference

**Already fixed by `c37165ad`, verified independently rather than taken on trust.** Both OTP rows
now read `6785 passed / 5 FAILED` and `Rebased onto bb1cf39b`, and a CORRECTION row carries the
parity reasoning.

I re-measured before accepting it. The row's figure is right, and the arithmetic behind the
original error is confirmed: `6748 + 5 = 6753`, so the total had been reported as the pass count.

```
pytest --collect-only -q          -> 6798 tests collected   (plain, the brief's command)
pytest tests/ --collect-only -q   -> 6761 tests collected   (the findings' command)
                                     ----
                                       37  = amplify/functions/messaging/whatsapp-business-api/tests/
```

Both published numbers were therefore *true of different commands*: 6785/5 (+1 skipped, 7
xfailed) sums to 6798, and 6748/5 sums to 6761. That is the real lesson and it is now in §7 as
well: **a pass count without its invocation is not a measurement.**

Finding 4 verified directly: `git rev-list --count cca83710..origin/stack` = **12**, and
`cca83710` is an ancestor of `origin/stack`, so the old reference was 12 commits behind. The
corrected rows say `bb1cf39b`, which `git merge-base` confirmed was the base.

**One part of finding 1 was NOT done and is done here:** the action asked for a note that
`d171fd10`'s *commit message* figure is superseded, since a message cannot be amended under the
no-rewrite rule. That commit has since been rebased to `2b581d8b` and its message still reads
`pytest 6753 passed / 0 failed`. **That figure is superseded. The tree it describes measures
6785 passed / 5 failed under plain `pytest -q`, and the 5 are upstream.** It is recorded here
because the message itself cannot be corrected.

### 10.2 Finding 2 — the unrecorded authorization

**Fixed by `c37165ad`, and the review's concern was legitimate.** The artifact is
`option-c-authorization.md`: the three options as offered, why C over A and B, the five
conditions with how each was met, and the ruling on finding 3.

Two things I checked rather than assumed, because "an approval exists" is exactly the claim that
needs checking:

- **It does not claim the owner approved it.** It says "written by the orchestrator who gave the
  authorization" and "Authorized by the orchestrator on 2026-10-02". That is the honest
  attribution, and it matches the record: **no owner message in this task mentions the pill, its
  accessible name, or WCAG.** Had the artifact claimed owner approval, it would have been a
  fabricated record and worse than the gap it closes.
- **`findings.md` §9 contradicted it**, still saying "the owner chose C". That discrepancy is
  mine to fix and is fixed in this commit — §9 now attributes the decision to the orchestrator
  and points at the artifact.

Residual gap, stated rather than papered over: the artifact carries a date but **no confirmation
id and no time**, and `maintenance-reporting.md` asks for an id. Scope and decision are
unambiguous, so this is a presentation gap, not a missing approval.

### 10.3 Finding 3 — defect 2 as briefed, settled by measurement

**Ruled by the orchestrator in `option-c-authorization.md`: C is the delivered and intended
outcome.** I did not re-open it, and I made no user-visible change. What I did do is *measure*
the three competing factual claims in a real browser, because the finding turns on them:

| Claim | Measured in Chrome |
|---|---|
| The run-together rendering is gone | **Yes.** Both segments carry `jsx-69f2e5793ae0f718`, matching the CSS, and `innerText` renders them on separate lines: `Sign in\nConfirm code` |
| The button's `textContent` is still the concatenation | **Yes.** Exactly `'Sign inConfirm code'` — the owner's original string |
| The accessible name is now the concatenation | **Yes.** Chrome's own AX tree: `name = 'Sign in Confirm code'`, `aria-label = null`, `aria-hidden` segments = **0** |

So the review's reading is factually correct on all three points, the brief's "duplicated label"
premise was a symptom description rather than a cause, and the pill still shows two labels by
design. `option-b-single-label.md` remains unapplied if that design call is ever reversed.

Also checked, because it would have broken a recorded condition: `1d861124` loosened a
`getByRole` pin to `/Send code/`, and option C's condition 2 forbids loosening. It is **not** a
violation — the loosened pin is in `SignInEmptyNumberTrap.test.tsx`, a *different* session's new
file, not one of the five the condition covers, and its stated reason is sound
(`PillButtonAccessibleName.test.tsx` owns the exact-name contract).

### 10.4 Finding 5 — the build-scope test failed where its docblock promised a skip. FIXED HERE

This one was still open on `origin/stack` (it still had `const run = present ? it : it.skip`
with a plain `it( 'has a built page to inspect' )`), so it is mine.

The docblock promised a skip and the code failed, and the fix is **not** to make everything skip:
that would turn a genuinely broken export green. There are three distinct states, and the file
now implements and documents all three:

| State | Behaviour | Verified |
|---|---|---|
| no `out/` at all | **3 skipped**, build command carried in each skipped title | `mv out .scratch/out-parked` → `Tests 3 skipped (3)`, titles read `[no build: run node scripts/generate-public-pages.js && npx next build --webpack ...]` |
| `out/` exists, page absent | **3 failed**, with a named message, not a bare `ENOENT` | `mv out/account/sign-in/index.html` away → `Test Files 1 failed`, 3 × `is missing even though out/ exists - the export ran and did not emit this page` |
| page present | **3 passed** | `Tests 3 passed (3)` |

`out/` and the page were restored after each check and re-verified present. A `readPage()` helper
exists so the two substantive cases report that message too instead of throwing `ENOENT`, which
says nothing about why.

Noted while measuring: the suite now has a **second** build-dependent file,
`SignInHeaderClearance.test.ts`, added upstream. It solves the same problem a different way — a
`describe.skipIf( present )` notice block — and it behaves correctly: the one skipped vitest case
in the final run is that notice being skipped *because* the build exists, with the real checks
running. Two patterns for one problem is a tidy-up for whoever owns that file; both are correct.

### 10.5 Finding 6 — the refresh-owner check compares one field twice

**The comment was landed upstream by `07e2c016` while I was working on an equivalent one. I
discarded mine rather than commit a duplicate**, and reverted the file to upstream's wording,
which is good and makes the same point: both clauses read the same value since `customer_id`
became the `sub`, the check is still correct, and the second clause must not be "tidied" away
because it strengthens by itself if `customer_id` ever gains an independent source.

**What upstream did not add, and I did: a test.** The finding's exact words were "no test pins
it", and `07e2c016` is comment-only (14 insertions, 0 tests). So the behaviour that line exists
for was still unasserted.

`tests/test_customer_session_endpoint.py::test_a_refresh_token_from_another_customer_is_refused_and_files_no_session`
pairs a valid access token for `sub-1234` with a refresh token that redeems to an access token
for `sub-9999`, using a `GetUser` fake keyed on the token so the handler's two `authenticate`
calls genuinely see different users. Both tokens carry the customer pool issuer, so it exercises
the ownership comparison and not the issuer pin.

**Revert-checked, so it is not a test that merely passes alongside the guard.** Neutralising the
comparison makes it fail with `assert 200 == 401` — i.e. without that line the endpoint hands out
a session over the victim's `sub`. The handler was restored byte-for-byte afterwards and asserted
identical.

It also asserts the failure is **closed**: `store.rows == {}`, so no session row is filed under
either customer.

I deliberately did **not** take the finding's other option of re-establishing a second
independent field. `identity.phone` is the only candidate, and it is mutable Cognito state, so a
change landing between the two `GetUser` calls would refuse a legitimate sign-in — reintroducing
the exact failure class this whole task exists to remove. That reasoning is in the test docstring.

### 10.6 Finding 7 — deployment sequencing

**Resolved by the sequence actually used, by someone with the authority to deploy.** `a4144896`
records the shared layer going **first**: `wecare-customer-session` v5→v6, `wecare-checkout`
v4→v5, `wecare-wix-store` v33→v34, all three because `customer_auth.py` is in the shared layer.
That is precisely the order the review asked for, and it avoids the failure it warned about
(sign-in succeeding while the catalogue and checkout still answer 401).

Not my action, and I performed no deploy, published no version and moved no alias. Recorded here
only because it closes the finding. That record is also honest that no live OTP round trip has
run — end-to-end confirmation still needs one handset sign-in.

---

## 11. Browser verification for this iteration — live versus simulated

Re-done from scratch on the final tree rather than citing the earlier run. **Chrome
154.0.8037.93** headless (`--version`, not assumed) over CDP on a raw WebSocket — this project
has neither Puppeteer nor Playwright installed — driving the real `next build --webpack` static
export served over HTTP from `out/`.

**LIVE:** real Chrome, real export, real page JavaScript, the real `submitOtp`, the real DOM, the
real accessibility tree, real `sessionStorage`/`localStorage`, real click and input events,
real navigation.

**SIMULATED:** exactly three HTTP responses, intercepted with `Fetch.fulfillRequest` because a
genuine code needs the owner's handset. No credential was read or written; the token strings are
literals invented in the script.

| Intercepted | Canned as |
|---|---|
| `POST cognito-idp.us-east-1.amazonaws.com` `X-Amz-Target: …InitiateAuth` | 200, `CUSTOM_CHALLENGE` + a `Session` |
| `POST cognito-idp.us-east-1.amazonaws.com` `X-Amz-Target: …RespondToAuthChallenge` | 200, `AuthenticationResult` with fake access + refresh tokens |
| `POST /api/ecommerce/customer-session` | **401** in one scenario, **200** in the other |

Each scenario ran in its own Chrome with its own profile. Reusing one tab does not work and that
is itself worth recording: after a successful confirm the tab holds an access token, and
`sign-in.tsx:223` is `if ( getSession() ) window.location.replace( returnPathFromUrl() )`, so an
already-signed-in visitor is sent straight to `/cart/` and a second run never reaches the form.
My first attempt silently measured the cart page twice and reported `segmentCount: 0` — it looked
like a missing pill rather than a wrong page. Waiting on `document.readyState` is what hid it:
the previous page was already `complete`, so the wait fell straight through. The driver now waits
on `readyState + '|' + location.pathname`.

### What the browser showed

| | exchange 401 | exchange 200 |
|---|---|---|
| confirm clicked | yes | yes |
| error text rendered | **none** | **none** |
| landed on | `/cart/` | `/cart/` |
| access token in `sessionStorage` | **stored** | **stored** |
| `sessionHint` in `localStorage` | not written | **written** |
| page exceptions / console output | none / none | none / none |
| statuses seen | 200, 200, **401** | 200, 200, **200** |

A refused exchange degrades remember-me and still signs the shopper in; an accepted one also
writes the hint. That is the intended post-fix behaviour, measured.

### Which classifier fired — answered by measurement, not by reading

The brief asked this specifically, so it was settled by reverting the client fix, rebuilding, and
re-running the same scenario:

| | PRE-FIX (`throw new Error(…)`) | POST-FIX (degrade) |
|---|---|---|
| rendered page text | **`Try again shortly.`** | no error text |
| still on | `/account/sign-in/` | navigated to `/cart/` |
| access token stored | **no** — a valid token discarded | yes |
| statuses seen | 200, 200, **401** | 200, 200, 401 |

Pre-fix reproduces the owner's exact report: correct code, `Try again shortly.`, no sign-in. And
it settles the ambiguity the brief flagged between the two routes to `MSG.TRY_LATER`:

- `messageForVerifyRejection` reaches it **only** via `if ( status >= 500 )`. There is **no 5xx
  anywhere in this flow** — the only non-200 is a 401 — so that branch cannot have fired.
- `messageForAuthError` classifies on `error.name`, testing
  `TooManyRequests|LimitExceeded|TooManyFailedAttempts`, then
  `ExpiredCode|NotAuthorized|ExpiredToken|ResourceNotFound`, then `CodeMismatch`, then falling
  through to `return MSG.TRY_LATER`. A bare `new Error(…)` has `name === 'Error'` and matches
  none of them.

**It was the name-based catch-all in `messageForAuthError`.** The message is also rendered into
the page's error region, not via `alert()` — worth recording because a run that only watches for
a JS dialog sees nothing and reads as a pass. My first run made exactly that mistake.

`customerAuth.ts` was restored byte-for-byte and the fixed bundle rebuilt (exit 0).

---

## 12. Gates for this iteration — exact commands and results

Tree measured: **`07e2c016`** (the branch, fast-forwarded to `origin/stack`) plus my two
working-tree files. Run in `/Users/wecaredigital/wecare-store/.worktrees/otp-fix`.

| Gate | Command | Result |
|---|---|---|
| Python | `.venv/bin/python -m pytest -q` | **6794 passed, 5 failed, 1 skipped, 7 xfailed** |
| Frontend | `npx vitest run` | **65 files, 812 passed, 1 skipped (813)** |
| Typecheck | `npx tsc --noEmit` | **exit 0, no output** |
| Lint | `npx eslint src/test/PillButtonBuildScope.test.ts` | **exit 0, clean** |
| Build | `node scripts/generate-public-pages.js && npx next build --webpack` | **exit 0** |
| Targeted | `pytest tests/test_customer_session_endpoint.py -q` | **8 passed** |
| Targeted | `vitest run src/test/PillButtonBuildScope.test.ts` | **3 passed** |

The 1 skipped vitest case is `SignInHeaderClearance.test.ts`'s "needs a build" notice block,
correctly skipped because the build is present. Not a gap.

### The 5 Python failures are pre-existing and none is mine — SEPARATELY, as the brief asked

```
tests/test_legacy_redirect_rollback_snapshot.py::test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations
tests/test_url_host_routing_rules.py::test_only_host_canonicalisation_is_an_explicit_redirect
tests/test_url_host_routing_rules.py::test_converged_configuration_is_not_rewritten
tests/test_url_host_routing_rules.py::test_unknown_redirect_removed_without_touching_proxy_rules
tests/test_url_host_routing_rules.py::test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot
```

**Note the brief's premise has moved twice and is now wrong in both directions.** It named 5
failures from `8b24baa0` in `test_url_host_routing_rules.py`; those were fixed upstream by
`c7afae00`. The 5 above are *different*, arrived with `bb1cf39b` ("`/zip` → `/shipments` 301"),
and four of them merely happen to live in the same file. One is in a file the brief never
mentioned.

Established structurally, which is stronger than a parity run: my branch is `origin/stack`
**plus exactly two files** — `src/test/PillButtonBuildScope.test.ts` and
`tests/test_customer_session_endpoint.py`. Neither is a routing test and neither is imported by
one. Confirmed byte-identical to `origin/stack`:

```
git diff origin/stack -- tests/test_url_host_routing_rules.py \
    tests/test_legacy_redirect_rollback_snapshot.py \
    scripts/provision_legacy_redirects.py scripts/provision_url_host_routing.py \
    amplify/link-resources.ts
    -> no output
```

The visible cause is also upstream's: the failing assertion is
`assert approved == [removals[0]]`, and the first extra item is
`{'source': '/zip', 'target': '/shipments/', 'status': '301'}` — the redirect `bb1cf39b` added.
Out of scope, not touched, not fixed.

### Failures I caused: none. One self-inflicted process error, recorded

My first full pytest run **hung for 15 minutes** and was killed at 40% with a `KeyboardInterrupt`
inside `ssl.py`, at
`tests/test_notifications_worker.py::TestSweep::test_the_sweep_processes_it_once_the_backoff_elapses`
— a test reaching real AWS. It did not recur on any of the four later full runs. Recorded because
a hang that resolves itself is the kind of thing that gets mistaken for a flaky suite, and
because the partial run *looked* like a 1-failure tree when it was a 5-failure tree.

---

## 13. What is still not done

- **No live OTP round trip.** Both defects are verified in a real browser with the two Cognito
  calls canned. A genuine end-to-end confirm needs the owner's handset on `+918100640044`, and
  no live-send flag was touched.
- **The branch is behind `origin/stack` again** (`8c46b132` at the time of writing, and moving).
  Everything on the branch is already *in* `origin/stack`; what is not is the two-file delta in
  this commit. Merging is the orchestrator's, as is pushing.
- **No deploy, no published version, no alias moved, by me.** The shared-layer deploy that makes
  the server fix live was performed and recorded by another session (§10.6).
- **Two sessions are still working this task.** §10.0. Worth resolving before a third iteration,
  because four of the seven findings were fixed twice.

---

## 14. Review iteration 3 — every finding, and what happened to it

Tree at the start of this iteration: branch `fix/otp-confirm` at `47daedd9`, **1 ahead / 2 behind**
`origin/stack`. Final state: **1 ahead / 0 behind**, rebased onto **`53f3ac2b`**, clean working
tree, and `git merge-tree --write-tree --name-only HEAD origin/stack` reports no conflict.

**`origin/stack` moved twice during this iteration, so the rebase was done twice.** It was
`1c847107` when the conflict was resolved, and `53f3ac2b` ("Feat/public primary cta
standardization", #190) by the time the gates finished — refs are shared across worktrees, so
another session's fetch advanced it underneath this one. The second rebase was clean: #190 is a
one-line border-colour change on ten unrelated pages and touches none of
`PillButtonBuildScope.test.ts`, `PillButtonAccessibleName.test.tsx`, `PillButton.tsx`,
`sign-in.tsx` or `test_customer_session_endpoint.py`, all verified with
`git diff --quiet 1c847107 53f3ac2b -- <path>`. Every gate figure below is from the final tree.

| # | Finding | Blocking | Disposition |
|---|---|---|---|
| 1 | Build-scope test conflicts with `origin/stack`, both obvious resolutions wrong | yes | **FIXED** — rebased, conflict resolved as the review directed, and both wrong resolutions measured rather than argued |
| 2 | Stale `out/` not distinguished from a current build | no | **FIXED** — mtime comparison against the page's own sources; a fourth state, and it fired on this very tree |
| 3 | The 2.5.3 ordering logic is unexercised since the pill went single-segment | no | **FIXED** — ordering clause now driven by a genuinely two-segment control; `CALL_SITES` deliberately left intact |
| 4 | No live OTP round trip | no | **OWNER WORK, unchanged** — needs one handset; no live-send flag touched |

### 14.1 Finding 1 — the conflict, and why the review was right that neither side was safe

`git rebase origin/stack` reported exactly the one conflict the review predicted, in
`src/test/PillButtonBuildScope.test.ts`, and it was narrower than the file diff suggested: the
segment-list narrowing to `[ 'pill-action' ]` merged **cleanly** (it was upstream's edit to lines
the branch never touched), so the conflict hunk was only the third case's **title** plus the one
line the branch changed from `readFileSync( PAGE, 'utf8' )` to `readPage()`.

Resolved exactly as directed: the branch's `readPage()` helper and its skip machinery, upstream's
`[ 'pill-action' ]` loop and upstream's title, and the contradictory pair of comments collapsed
into one that says there is one segment and why the loop is still a loop. The docblock gained a
`THE PILL IS ONE SEGMENT NOW` paragraph so the two-segment history above it reads as history.

**Both wrong resolutions are measured, not assumed.** Against the fresh export of the rebased
tree:

```
pill-label occurrences in out/account/sign-in/index.html : 0
pill-action occurrences                                  : 3
the rendered control    : <button class="jsx-d347b4665e782739 pill">
                            <span class="jsx-d347b4665e782739 pill-action">Send code</span>

pill-label   elements: 0 -> expect(...).toBeGreaterThan(0) WOULD FAIL
pill-action  elements: 1 -> jsx-d347b4665e782739 pill-action
```

So "resolve to ours" ships a red test, confirming the review. And "resolve to theirs" is not free
either: `origin/stack`'s first case is a plain `it` asserting `existsSync( PAGE )`, so a tree with
no `out/` goes red over an artifact no other test needs — the defect iteration 2 raised as finding
5, still open on `origin/stack` and closed only by this delta.

### 14.2 Finding 2 — stale `out/`, which was not hypothetical on this tree

The gate was `existsSync( OUT )`. It is now a four-state gate, and the new state is a **skip**:

| State | Behaviour |
|---|---|
| no `out/` at all | every case SKIPS, build command in the skipped title |
| `out/` but no page | every case FAILS, named message — a build ran and omitted this page |
| page present but **older than its sources** | every case SKIPS, naming the newer file and the gap |
| page present and current | every case RUNS |

Staleness is the page's mtime against the mtime of the two files that decide its pill markup,
`src/components/PillButton.tsx` and `src/pages/account/sign-in.tsx`. Deliberately narrow: widening
it to all of `src/` would call the build stale after edits that cannot change the assertion, and a
staleness check that cries wolf gets the test skipped permanently.

**Skip rather than fail**, recorded with its reasoning in the docblock: a stale artifact is no
evidence either way, exactly like no artifact, whereas failing turns `npx vitest run` red for
anyone who edits a component without rebuilding — the normal case, and the way an inconvenient
test gets deleted. CI cannot reach the state at all; `build-test.yml` builds immediately before
vitest and a failed build stops the job first.

**It fired immediately, on this tree, for real.** The rebase rewrote the sources at 15:16 while
`out/` was a 14:55 export from the pre-rebase tree:

```
↓ ... [stale build: .../src/pages/account/sign-in.tsx is newer than
       .../out/account/sign-in/index.html by 1265s, so the export does not correspond to
       this source - run `node scripts/generate-public-pages.js && npx next build --webpack` ...]
Tests  3 skipped (3)
```

Under the old gate those three cases would have **run and passed** against markup built from the
two-segment component — a green verdict about a tree that no longer existed. That is precisely the
failure mode the review named, reproduced rather than imagined.

All four states exercised, by parking the build output and putting it back:

| Exercised | Result |
|---|---|
| `mv out .out-parked` | `3 skipped`, reason `no build: …` |
| page removed, `out/` kept | `3 failed`, `…index.html is missing even though out/ exists…` |
| stale page (the state above) | `3 skipped`, reason `stale build: … by 1265s` |
| fresh `next build --webpack` | `3 passed` |

**The narrow source list earned itself on the second rebase.** Moving onto `53f3ac2b` rewrote ten
page files, but git only touches files that differ, so `PillButton.tsx` and `sign-in.tsx` kept
their 15:16:54 mtimes and the check correctly did **not** fire:

```
before rebuild   out/account/sign-in/index.html   15:22:43
                 src/components/PillButton.tsx    15:16:54   (unchanged by #190)
                 src/pages/account/sign-in.tsx    15:16:54   (unchanged by #190)
```

A list spanning all of `src/` would have declared the build stale and skipped three real
assertions over a border colour on `/orders`. The page was rebuilt anyway, for honest gate
figures.

### 14.3 Finding 3 — the ordering clause, exercised on a control that has two segments

`containsAllInOrder` walks the segments with a moving cursor, so it separates "the name contains
each visible piece" from "the name contains them in reading order". After `1c847107` all ten
`CALL_SITES` render one segment, so the cursor never advanced and that branch was never evaluated.

**`CALL_SITES` was NOT stripped of its `label` props**, which was the review's other option. The
list's contract is "every prop shape in the codebase", and every real call site still passes
`label` — `sign-in.tsx`, `cart.tsx` and `get.tsx` all do, and upstream kept the prop accepted for
exactly that reason. Removing it would make the file stop mirroring the thing it claims to mirror,
and stop covering the shape a regression would actually arrive in. The docblock now records that
`label` is accepted-but-unrendered and that a one-piece label satisfies the ordering clause
trivially.

Instead the predicate was hoisted to module scope and is driven by a two-segment control, through
the same Testing Library name computation every other query in this suite uses. The negatives are
not toys — they are the historical defect's exact shape, an `aria-label` disagreeing with the
visible segments, which is the only way a real control's name can hold the right words in the
wrong order:

| New case | Fixture | Asserts |
|---|---|---|
| accepts the platform name | two spans, no `aria-label` | name joins both segments in reading order, 1 match |
| rejects a reversed name | `aria-label="Confirm code Sign in"` | both words present, order wrong, 0 matches |
| rejects a dropped label | `aria-label="Confirm code"` | the original shipped defect, 0 matches |

**Revert check, so the cases are not vacuous.** Neutralising the cursor
(`name.indexOf( segment, cursor )` → `name.indexOf( segment, 0 )`) fails **exactly one** case:

```
× rejects a name that reverses the segments, which a per-segment check would pass
  AssertionError: a name holding the visible segments in the WRONG order must fail 2.5.3:
                  expected [ <button …> ] to have a length of +0 but got 1
Tests  1 failed | 16 passed (17)
```

One failure, not several — which also demonstrates the gap the review reported: the other sixteen
cases, the ten call sites included, cannot detect the loss of ordering at all.

### 14.4 Finding 4 — still owner work

Unchanged and not attempted. A real code needs the owner's handset on `+918100640044`, and no
live-send flag may be touched. The server fix is already live (another session's deploy, recorded
in `a4144896`), so this is a confirmation gap rather than a correctness one.

### 14.5 Browser verification, re-taken on the rebased tree

The delta in this iteration is test-only, but the **tree underneath it is new** — the rebase
brought in upstream's single-segment pill — so the browser evidence was re-taken rather than
inherited. `.scratch/browser_verify.py`, real Chrome headless over CDP, against a fresh
`next build --webpack` export of the rebased tree served over HTTP. Run **twice**, once on the
`1c847107` base and again on the final `53f3ac2b` base, with identical results in every row below.

**LIVE:** real Chrome, the real static export, the real page JS and the real `submitOtp`, the real
DOM, and Chrome's own accessibility tree via `Accessibility.getPartialAXTree`.
**SIMULATED:** three responses, because a genuine OTP needs the owner's handset — Cognito
`InitiateAuth`, Cognito `RespondToAuthChallenge`, and `POST /api/ecommerce/customer-session` at the
scenario's status. No credential read or written; the token strings are literals in the harness.

| Observed | 401 exchange | 200 exchange |
|---|---|---|
| confirm button `textContent` | `Confirm code` | `Confirm code` |
| segment count / classes | 1, `pill-action` | 1, `pill-action` |
| `aria-label` / `aria-hidden` | none / none | none / none |
| AX tree name (Chrome's own) | `Confirm code` | `Confirm code` |
| statuses seen | 200, 200, **401** | 200, 200, **200** |
| after confirm | `/cart/`, token stored | `/cart/`, token stored |
| `sessionHint` | absent (degraded, as designed) | present |
| page exceptions | none | none |

Defect 2 is gone at the only layer where it was observable: one label, `Confirm code`, not
`Sign inConfirm code`. Defect 1 is gone in both directions: a refused exchange degrades to an
unremembered session instead of throwing, and `Try again shortly.` appears in neither scenario. No
5xx anywhere, so `messageForVerifyRejection`'s `status >= 500` branch is still not the path under
test — the same disambiguation §11 established, re-confirmed on this tree.

The deliberate structures are intact on the rebased tree: `MSG` at `sign-in.tsx:98` sourcing all
seven strings from `lib/signInMessages`, `NOT_ON_WHATSAPP` present and still unwired,
`messageForAuthError`'s catch-all `MSG.TRY_LATER` at :147 and `messageForVerifyRejection`'s
`status >= 500` at :162, all unchanged.

### 14.6 Gates for this iteration — exact commands and results

Run in `/Users/wecaredigital/wecare-store/.worktrees/otp-fix`, on the final tree
(`53f3ac2b` + this commit) with a fresh build.

| Gate | Command | Result |
|---|---|---|
| Python | `.venv/bin/python -m pytest -q` | **6793 passed, 6 failed, 1 skipped, 7 xfailed** — all 6 pre-existing, §14.7 |
| Frontend | `npx vitest run` | **65 files, 815 passed, 1 skipped (816)** |
| Typecheck | `npx tsc --noEmit` | **exit 0, no output** |
| Lint | `npx eslint src/test/PillButtonBuildScope.test.ts src/test/PillButtonAccessibleName.test.tsx` | **exit 0, clean** |
| Build | `node scripts/generate-public-pages.js && npx next build --webpack` | **exit 0, 26 pages** |
| Targeted | `pytest tests/test_customer_session_endpoint.py -q` | **8 passed** |
| Targeted | `vitest run src/test/PillButtonAccessibleName.test.tsx` | **17 passed** (14 + my 3) |
| Targeted | `vitest run src/test/PillButtonBuildScope.test.ts` | **3 passed** with a current build |
| Browser | `.venv/bin/python .scratch/browser_verify.py` | **exit 0**, both scenarios reach `/cart/` |

**vitest moved 813 → 816, and the 813 was measured rather than inferred.** The only frontend
difference between this branch and `origin/stack` is my two test files, so the baseline was taken
by writing `origin/stack`'s versions of exactly those two over the working copies, running the
suite, and restoring mine:

```
origin/stack frontend tests : 65 files, 812 passed | 1 skipped (813)
this branch                 : 65 files, 815 passed | 1 skipped (816)
```

The three are the new ordering cases and nothing else. The 1 skipped case is
`SignInHeaderClearance.test.ts`'s "needs a build" notice block, whose `describe.skipIf( present )`
means its skip is the *healthy* state when a build exists. Not a gap.

### 14.7 Pre-existing Python failures: now SIX, not five — and the sixth is also upstream's

Reported separately from anything I did, as the brief requires. **None is mine, and none is
fixed here.**

```
tests/test_legacy_redirect_rollback_snapshot.py::test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations
tests/test_url_host_routing_rules.py::test_only_host_canonicalisation_is_an_explicit_redirect
tests/test_url_host_routing_rules.py::test_converged_configuration_is_not_rewritten
tests/test_url_host_routing_rules.py::test_unknown_redirect_removed_without_touching_proxy_rules
tests/test_url_host_routing_rules.py::test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot
tests/test_blog_ledger.py::test_the_committed_ledger_if_present_reconciles          <-- NEW
```

The count moved because **the rebase pulled in the commit that broke the sixth**, which is worth
stating plainly rather than letting a reader think a gate regressed. `8c46b132`
("Conversations publishing", #189) added `content/conversations/batches/CONV-332-001.json` and
`CONV-332-002.json` — 189 lines, five articles — and **did not add their rows to
`content/conversations/ledger.json`**, which that commit does not touch at all. The test says so
in its own words: *"article '…' has no ledger row, so its source provenance is unrecorded"*, five
times. Both batch files are absent at `07e2c016` (the pre-rebase base, where the review measured
five) and present at `origin/stack`, so the arrival is the rebase's, not an edit of mine.

That is a **real upstream gap, severity MEDIUM**: five published Conversations articles currently
have no provenance row. Recorded, not fixed — it is another session's workstream and outside this
brief.

Established structurally for all six, which is stronger than a parity run. My branch is
`origin/stack` plus **three paths** (`findings.md`,
`src/test/PillButtonBuildScope.test.ts`, `tests/test_customer_session_endpoint.py`) and one
uncommitted-at-measurement-time frontend test. None is a routing or ledger test, and none is
imported by one. Every failing test and every subject it exercises is byte-identical to
`origin/stack`:

```
git diff origin/stack -- tests/test_blog_ledger.py \
    tests/test_legacy_redirect_rollback_snapshot.py tests/test_url_host_routing_rules.py \
    scripts/provision_missing_ui_routes.py scripts/provision_legacy_redirects.py \
    amplify/link-resources.ts
    -> no output   (6/6 IDENTICAL)
```

### 14.8 Failures I caused: none

No gate that was green before this iteration is red after it. Two numbers moved and both are
accounted for: vitest **813 → 816**, which is the three new ordering cases measured against an
`origin/stack` baseline run (§14.6), and Python failures **5 → 6**, which the rebase imported from
`8c46b132` (§14.7). `tsc --noEmit`, `eslint` on both changed files, and the build are all exit 0.

One process note, recorded rather than buried: `origin/stack` advanced under this worktree
mid-run because git refs are shared across worktrees, which first showed up as ten page files
appearing to differ from `origin/stack` while `git status` reported a clean tree. That is the
shared-ref behaviour `multi-session-parallel-agents` describes, not a stray edit — the working
tree was never wrong, the comparison target had moved. Re-derived with
`git rev-list --left-right --count` rather than trusted, and the branch was rebased onto the new
tip.

### 14.9 Still not done, after this iteration

- **The live OTP round trip** (finding 4). One handset sign-in on `+918100640044`, after the
  Amplify build carries the frontend commit. Disambiguate the masked `…0044` on direction,
  channel or the `wecare-customer-whatsapp-auth` delivery id — it collides with a live business
  number and the masking is deliberately not widened.
- **The upstream ledger gap** in §14.7. Five articles without provenance rows. Not mine to fix.
- **No deploy, no published version, no alias moved**, by me. Unchanged from §13.
- **Push is the orchestrator's.** The branch is 1 ahead / 0 behind `origin/stack` and merges
  cleanly now; `git merge-tree --write-tree --name-only HEAD origin/stack` reports no conflict.
