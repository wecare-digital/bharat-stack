# Customer WhatsApp OTP confirm failure + doubled sign-in label — findings

Worktree `/Users/wecaredigital/wecare-store/.worktrees/otp-fix`, branch `fix/otp-confirm`,
**rebased onto `origin/stack` at `cca83710`** (started from `72a2c5d3`). Nothing was deployed, no
version published, no alias moved, no pool mutated.

---

## 0. Read this first — the pill fix is NOT mine, and one decision is open

Two corrections to the brief's framing, both discovered mid-task and both load-bearing.

**The pill repair landed upstream while I was working, in `2f742ec6`** ("fix(get): share the
sign-in controls, add the home top section, repair the pill", #185). That commit reached the *same
root cause I had proved independently* — segments hoisted into `const inner = (<>…</>)`, so
styled-jsx never stamped them — and fixed it the same way, by inlining the segments into both
branches. **I dropped my version of that fix entirely and rebased onto theirs.** My own C1 diff and
duplicate source guards are discarded, not merged; their two anti-re-hoist guards are left intact.
Attribution is theirs. What I kept is one *additive* test they do not have (see §4).

**The "doubled label" is now a product decision, not a defect, and I have NOT made it.** Their fix
repaired the *rendering*; `/account/sign-in` still passes `label="Sign in"` and still shows two
segments. Measured after rebase, the confirm button is:

| | |
|---|---|
| `textContent` (raw DOM) | `'Sign inConfirm code'` — still literally the reported string |
| `innerText` (what a sighted user reads) | `'Sign in Confirm code'` — now two distinct styled segments |
| accessible name | `'Confirm code'` — the action alone |

So the *run-together appearance* the owner complained about is gone, but it is still two visible
labels in one control, which is still a **WCAG 2.5.3 Label in Name** mismatch. Removing the
"Sign in" segment would change what the owner sees and would **re-diverge `/account/sign-in` from
`/get`, which `2f742ec6` had just unified onto this identical pill on owner instruction**. That is
a design call, not a bug fix, so it is escalated rather than taken. See §9.

**The auth outage in §1 is untouched by any of this** and is the real fix in this branch.

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

### C2 — one label per button. NOT DONE. Escalated as a design decision

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

`src/test/PillButton.test.tsx` — **left exactly as `2f742ec6` wrote it.** My single-label cases and
my source guard are discarded. Their two new cases (a comment-stripping source guard against
re-hoisting, and a render check that both segments appear with the action as the accessible name)
are intact and not weakened. Worth noting we independently arrived at the *same* comment-stripping
technique, for the same reason: the docblock explaining the rule necessarily quotes the pattern it
forbids, so matching raw source punishes the documentation. That trap caught my first attempt too.

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

Both were re-measured **after the rebase** onto `2f742ec6`+`cca83710` and are unchanged: 401 →
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

All figures below are **after the rebase onto `cca83710`**, which is the tree that was committed.

| Gate | Command | Baseline on `72a2c5d3` | After, on `cca83710` |
|---|---|---|---|
| Frontend tests | `npx vitest run` | 59 files / **799** passed | **61 files / 818 passed, 0 failed** |
| Python tests | `./.venv/bin/python -m pytest tests/ -q` | 6749 passed, **5 failed** | **6757 passed, 0 FAILED**, 1 skipped, 7 xfailed |
| Targeted customer tests | `pytest tests/test_customer_{session_endpoint,auth_and_throttle,session,whatsapp_auth,registration_handler}.py -q` | 96 passed | **101 passed** |
| Typecheck | `npx tsc --noEmit` | — | **exit 0, no output** |
| Lint | `npx eslint <5 changed files>` | — | **exit 0, no output** |
| Build | `node scripts/generate-public-pages.js && npx next build --webpack` | succeeds | **succeeds, 0 errors** |

`npx next build` without `--webpack` fails here: `next.config.js` pins `turbopack.root` to the
worktree and Turbopack will not resolve `next` through the ancestor walk-up. `--webpack` is required.

### The 5 pre-existing failures are GONE, and not by my hand

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

## 9. THE ONE OPEN DECISION — two visible labels in one button

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

**Nothing in §1–§2 depends on this.** The auth fix is complete, green and independently
deployable.
