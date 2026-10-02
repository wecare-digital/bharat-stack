# Customer WhatsApp OTP confirm failure + doubled sign-in label — findings

Worktree `/Users/wecaredigital/wecare-store/.worktrees/otp-fix`, branch `fix/otp-confirm`,
based on `72a2c5d3`. Nothing was deployed, no version published, no alias moved, no pool mutated.

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

## 3. The doubled "Sign inConfirm code" label

**A real CSS failure, not a text bug.** `PillButton.tsx` built its two segments in an intermediate
variable (`const inner = (<>…</>)`). styled-jsx only adds its scope class to JSX in the tree it
transforms, so the `<button>`/`<a>` got the hash and the spans did not.

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

### The fix, in two parts

- **C1 — scoping.** The segments are written inline in **both** the `<a>` and `<button>` branches;
  the intermediate variable is gone. This fixes sign-in and cart together.
- **C2 — one label per button.** `label` is now optional. Omitted, the pill renders a single
  full-radius action segment (`.pill-solo`), and `/account/sign-in` passes the action only. Even
  correctly styled, visible "Sign in Confirm code" with accessible name "Confirm code" fails
  **WCAG 2.5.3 Label in Name**, and `aria-hidden` on a control's own visible label is the
  anti-pattern that produced the mismatch. Now visible text == accessible name.
  The owner's two-tone treatment survives: the 2 px `#1a3a2a` edge and the mint action surface.
- **The cart keeps its two-segment form**, as instructed — its left segment ("Checkout") is not a
  duplicate of its action ("Proceed").

**I avoided introducing a 2.5.3 bug of my own.** My first attempt added `ariaLabel="Send code"`
alongside `action="Sending…"`, which makes the accessible name not contain the visible text while
busy. Removing it restores the original name behaviour exactly *and* satisfies 2.5.3.

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
- `renders the confirm button with a single label, not a concatenation` — asserts
  `textContent !== 'Sign inConfirm code'`, `=== 'Confirm code'`, name == visible text, and exactly
  one segment. Plus the same for the send button.
- **A mock-leak defect found while writing these:** an earlier `describe` in that file mocks
  `customerAuth.submitOtp` wholesale and never restores it. These tests exist to run the *real*
  `submitOtp`, so inheriting that mock made the first one silently test nothing (it failed on
  navigation). `vi.restoreAllMocks()` now runs in `beforeEach`, making the block order-independent.

`src/test/PillButton.test.tsx`
- Single-label mode: exactly one segment, visible text == accessible name, no `aria-hidden`
  element carrying label text, `.pill-solo` applied, and two segments still render when a label
  **is** given (so the cart is pinned unchanged). Solo anchors covered too.
- A source guard that the segments are **not** hoisted out of the returned tree.
  **It strips comments before matching**, because the docblock explaining the rule necessarily
  quotes the pattern it forbids — the same trap the payment-vocabulary gate documents, and it
  caught me on the first run. A third test guards the guard, so the stripping cannot empty the
  file and make the other two pass vacuously.

`src/test/PillButtonBuildScope.test.ts` (new) — the only layer where scoping is observable. Reads
`out/account/sign-in/index.html`, collects every `.pill*` selector hash from the inlined `<style>`
blocks and every pill-bearing `class` attribute from the markup, and asserts each pill-classed
element carries a hash its selector was written with. It asserts the **property** ("the selector
can reach the element") rather than any particular hash, which changes whenever the CSS does. It
**skips with an explicit message naming the build command** when `out/` is absent, so it never
silently passes.

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

**POST-FIX pill**, both phases: single segment, `textContent` exactly `Send code` / `Confirm code`,
`aria-label` equal to it, segment class `jsx-b7761065a244bd3 pill-action` — **hashed** — and
computed `display:flex`, `background-color:rgb(95,227,176)` (#5fe3b0), `color:rgb(26,58,42)`,
`padding:0px 24px`, `font-weight:700`; pill `border-radius:999px` on `rgb(26,58,42)`.

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
| Segments re-hoisted into `inner` + duplicate labels restored, then rebuilt | Built markup returned to bare `class="pill-action"` / `class="pill-label"` with **no hash** — the defect reproduced — and **6 vitest failures**, including the build-scope test. Restored and rebuilt → clean |

---

## 7. Gates — exactly what was run

All in `/Users/wecaredigital/wecare-store/.worktrees/otp-fix`. The worktree had no `.venv` and no
usable `node_modules`, so: `.venv` is a symlink to the parent's (gitignored), and Node resolves
packages by **ancestor walk-up** to `/Users/wecaredigital/wecare-store/node_modules` — verified
with `require.resolve`. A pre-existing `node_modules/node_modules` symlink was created one level
too deep and does nothing; it was left alone as harmless and gitignored. **Nothing was installed,
and nothing in the parent working tree was modified.**

| Gate | Command | Baseline on `72a2c5d3` | After |
|---|---|---|---|
| Frontend tests | `npx vitest run` | 59 files / **799** passed | **60 files / 818 passed, 0 failed** |
| Python tests | `./.venv/bin/python -m pytest tests/ -q` | 6749 passed, 5 failed | **6750 passed, 5 failed**, 3 skipped, 6 xfailed |
| Targeted customer tests | `pytest tests/test_customer_{session_endpoint,auth_and_throttle,session,whatsapp_auth,registration_handler}.py -q` | 96 passed | **109 passed** |
| Typecheck | `npx tsc --noEmit` | — | **exit 0, no output** |
| Lint | `npx eslint <7 changed files>` | — | **exit 0, clean** |
| Build | `node scripts/generate-public-pages.js && npx next build --webpack` | succeeds | **succeeds, 0 errors** |

`npx next build` without `--webpack` fails here: `next.config.js` pins `turbopack.root` to the
worktree and Turbopack will not resolve `next` through the ancestor walk-up. `--webpack` is required.

### Pre-existing failures — NOT mine, NOT fixed

`tests/test_url_host_routing_rules.py`, **5 failures**, from another session's `8b24baa0`,
unrelated to OTP. Measured at baseline **before** any change and unchanged after:

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
   checkout". Left alone as instructed; now visible rather than hidden by the styling bug.
5. **`wecare-customer-registration` has neither a deployed function nor a route**, so the
   unregistered branch of `sign-in.tsx` would still fail if a new number reached it.
