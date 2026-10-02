# Customer WhatsApp OTP confirm outage — diagnosis and fix plan

Worktree: `/Users/wecaredigital/wecare-store/.worktrees/otp-fix` (branch `fix/otp-confirm`, at
`72a2c5d3` = `origin/stack`). All paths below are absolute under that worktree. The parent
`/Users/wecaredigital/wecare-store` belongs to another live session — do not touch it.

---

## (a) Root cause — PROVEN, with the evidence that proves it

`lambda_utils/customer_auth.authenticate()` requires the Cognito user attribute
**`custom:customer_id`**. That attribute **does not exist in the schema of pool
`us-east-1_46ULYuukt`**. The pool's only custom attribute is `custom:partner_waba_id`. It can
therefore never be present on any user, so `authenticate()` raises `CustomerNotAuthenticated` for
**every** customer token, 100% of the time, and has since the pool was created.

The chain, end to end:

1. `requestOtp` → Cognito `InitiateAuth CUSTOM_AUTH` → the pool trigger sends the WhatsApp code.
   **Works.** It never calls `customer_auth`. This is why send succeeds.
2. Owner types the correct code → `submitOtp` → `RespondToAuthChallenge` **succeeds** and returns
   `AccessToken` + `RefreshToken`. The customer is authenticated at this instant.
3. Because a `RefreshToken` is present, `submitOtp` POSTs `{action:'exchange'}` to
   `/api/ecommerce/customer-session`.
4. Handler `amplify/functions/ecommerce/customer-session/handler.py`: origin check passes →
   `customer_auth.authenticate(event)` → `GetUser` OK → issuer pin OK → `custom:customer_id`
   absent → `logger.warning('{"event":"customer_auth_no_customer_id"}')` → raise.
5. Handler returns **401 `VERIFICATION_REQUIRED`**.
6. `submitOtp`: `if (!response.ok) throw new Error('We could not remember this sign-in. Please try
   again.')` — thrown **before** `storeSession()`, so the valid access token is discarded.
7. `sign-in.tsx` `submitCode` catch → `messageForAuthError(err)`. `err.name === 'Error'`, which
   matches none of `TooManyRequests|LimitExceeded|TooManyFailedAttempts`,
   `ExpiredCode|NotAuthorized|ExpiredToken|ResourceNotFound`, or `CodeMismatch` → falls through to
   `return MSG.TRY_LATER` → **"Try again shortly."**

**Which classifier fired: the `name`-based `messageForAuthError`, on its FALLBACK branch.** Not
`messageForVerifyRejection`, not the `>=500` mapping. There is no 5xx anywhere in this failure. The
brief's warning was correct.

### Evidence

| Fact | How it was measured |
|---|---|
| Pool schema has only `custom:partner_waba_id` | `describe-user-pool … SchemaAttributes[?starts_with(Name,'custom')]` |
| The one pool user (1 user, CONFIRMED, created 2026-09-25) carries `phone_number`, `phone_number_verified`, `name`, `custom:partner_waba_id`, `sub` — no customer id | `list-users`, attribute **names** only, no values printed |
| 4 × `[WARNING] {"event":"customer_auth_no_customer_id"}` on 2026-10-02 at 02:44:00.283Z, 02:45:11.732Z, 05:33:55.013Z, 06:02:13.625Z | `filter-log-events /aws/lambda/wecare-customer-session` — these are the owner's confirm attempts |
| 18 invocations in 10 h, **0** `customer_auth_rejected` | same; the module's `logger.info` is suppressed, so the function's level is above INFO |
| `stack-wecare-digital-CustomerSessionsTable` holds **0 items** | `describe-table` — the exchange has never once succeeded, before or after 87d2c626 |
| Route exists and is reachable: `POST /ecommerce/customer-session` → `integrations/fryr558`, `AuthorizationType=NONE` | `apigatewayv2 get-routes` |
| `/api/<*>` rewrite is correct and forwards `Origin` | `amplify get-app customRules`; live probe returns **identical** bodies through `https://wecare.digital/api/…` and the execute-api URL |
| No Origin → `403 {"error":"ORIGIN_REQUIRED"}`; `Origin: https://wecare.digital` → `401 {"error":"VERIFICATION_REQUIRED"}`; `OPTIONS` → 204 | live read-only probes |

**Why CloudWatch looked clean:** the handler returns 401 as a *normal return* — no raise escapes, no
traceback. The only log line is **WARNING**, which is not error-shaped. The brief's "zero
error-shaped events" reading was accurate and the function was failing the whole time.

### 87d2c626 is ELIMINATED as the cause of the confirm failure

Its diff touches only button markup and CSS in `sign-in.tsx` / `cart.tsx`, plus the new component.
It does not touch `submitCode`, `submitOtp`, the form's `onSubmit`, or any session state;
`type="submit"` is preserved and the form still calls `submitCode`. The 0-item session table proves
the exchange never worked before it either. **It is, however, the proven cause of (c).**

### Blast radius beyond sign-in

`customer_auth.require_customer` is the gate on `wecare-checkout` (`handler.py:248`) and
`wecare-wix-store` (`handler.py:368`). The same defect means **no customer can check out or load the
store catalogue either.** `OrderTable`, `PaymentAttemptsTable`, `WixOrderIds` and `WixOrdersCache`
all hold 0 items, consistent with that.

### Drift corrections against the brief — carry these

- `wecare-customer-session` live alias is at **v5**, not v4. (`LastModified 2026-10-02T02:26:43Z`.)
- Python is **`/Users/wecaredigital/wecare-store/.venv/bin/python`**. There is no `.venv` in the worktree.
- There is no `node_modules` in the worktree either. A gitignored symlink to the parent's has been
  created; see item 9.

---

## (b) The fix for confirm — two changes, no pool mutation, no deploy

**B1 (server, the root cause).** Derive the customer id from the token's own proven identity — the
Cognito `sub` — instead of `custom:customer_id`.

Why `sub`, and why not the alternatives:

- **Adding the pool attribute is possible but is OWNER WORK.** The existing design doc
  (`.agents/tasks/customer-session-20261001/design.md`, item C-1) states Cognito "cannot add a
  custom attribute after creation". **That is wrong** — `AddCustomAttributes` exists for exactly
  this; what you cannot do is delete one or change its type
  ([AddCustomAttributes](https://docs.aws.amazon.com/goto/WebAPI/cognito-idp/AddCustomAttributes),
  [add-custom-attributes CLI](https://docs.aws.amazon.com/goto/aws-cli/cognito-idp-2016-04-18/AddCustomAttributes)).
  Correct the doc. But it remains an **irreversible pool schema mutation**, so it is owner work per
  the hard constraints, and it would still need a backfill on the existing user plus a stamp on every
  new one. *(Content was rephrased for compliance with licensing restrictions.)*
- **`CustomersTable` is not available.** Design §8.1 makes `stack-wecare-digital-CustomersTable` the
  intended authority, but that table **does not exist** in the account and no script in the repo
  creates it (design C-5). Not a candidate for an outage fix.
- **`sub` is the strongest option already in the token.** Immutable, pool-scoped, present on every
  user, not writable by the app client, and already the field this handler compares for refresh-owner
  identity (`proven.subject != identity.subject`). A *mutable* custom attribute writable by the app
  client would be a worse authority, not a better one.
- **Zero migration risk, measured.** Every table that could hold a customer-keyed row is empty:
  CustomerSessionsTable 0, OrderTable 0, PaymentAttemptsTable 0 (it has a `customerId-index`),
  WixOrderIds 0, WixOrdersCache 0. Nothing is keyed on a pre-existing customer id, so this is a clean
  cut-over rather than an identity migration.

Make it a **single authority**, not "custom attribute if present, else `sub`". A fallback would
silently change a customer's identity the day someone adds and backfills the attribute, orphaning
their orders. One rule, in one helper, with the reasoning recorded in the file.

**B2 (client, the amplifier).** In `submitOtp`, the Cognito challenge has already succeeded — the
customer **is** authenticated. The exchange buys *persistence* ("Keep me signed in on this device"),
not authentication. Throwing before `storeSession()` converts a degraded remember-me into a total
sign-in failure and throws away a valid token. Store the session first; on exchange failure return
it with the degradation marked instead of throwing. `restoreSession()` already treats a missing hint
as "sign in again", so this is an already-modelled state.

B2 is worth doing on its own merits even after B1 lands: it is the difference between "the site is
down" and "remember-me is off".

**The MSG table and both classifiers stay as they are.** The `MSG.TRY_LATER` catch-all is correct
design; with B2 in place the exchange failure never reaches it. Pin that with a test rather than
adding a new message or a new branch.

---

## (c) The doubled "Sign inConfirm code" label — PROVEN, and it is a real CSS failure

`src/components/PillButton.tsx` builds its two segments in an intermediate variable:

```tsx
const inner = (<><span className="pill-label" …/><span className="pill-action" …/></>);
```

styled-jsx only adds its scope class to JSX in the tree it transforms. The `<button>` / `<a>` are in
the returned tree and get the hash; the spans, living in a separate variable, do not. Measured on the
live site and reproduced **byte-identically** in a local `--webpack` build (same hash, so the local
tree is the code that is live):

- CSS shipped: `.pill-label.jsx-69f2e5793ae0f718{…}`, `.pill-action.jsx-69f2e5793ae0f718{…}`
- Markup shipped: `<span class="pill-label">`, `<span class="pill-action">` — **no hash**
- `<button type="submit" aria-label="Send code" class="jsx-69f2e5793ae0f718 pill">` — the button *is* scoped

The selectors can never match. Both segments are **completely unstyled**: no background, no padding,
no flex, no divider, no `inline-flex`. Two bare inline text nodes inside a `#1a3a2a` pill render as
**"Sign inConfirm code"** in inherited dark type on a dark-green background. Exactly the screenshot.
**The cart CTA has the identical bug** — same component.

**Why no test caught it:** under vitest styled-jsx is not transformed at all. `<style jsx>` renders as
a plain `<style>` with **unscoped** selectors and React warns `Received true for a non-boolean
attribute jsx`. So jsdom sees selectors that *would* match. `PillButton.test.tsx` even says the
colours are "the browser harness's job" — and no browser harness exists.

Two parts to the fix:

- **C1 — scoping.** Inline the segments into both returned branches so styled-jsx scopes them. Fixes
  sign-in and cart together.
- **C2 — one label per button.** Even once correctly styled, visible text "Sign in Confirm code" with
  accessible name "Confirm code" fails **WCAG 2.5.3 Label in Name**, and `aria-hidden` on a control's
  own visible label is the anti-pattern that produced the mismatch. So the owner is substantively
  right that it is two labels in one button. Make `label` optional; when omitted, render a single
  full-radius action segment. On `/account/sign-in` pass only the action, so visible text ==
  accessible name == "Send code" / "Confirm code" — the names `AccountSignIn.test.tsx` and
  `SignInMessages.test.tsx` already pin, so those tests keep passing unchanged. The owner's two-tone
  treatment survives: the pill keeps its 2 px `#1a3a2a` edge and mint action surface.
- **Leave the cart's two-segment pill alone.** Its left segment ("Checkout") is not a duplicate of its
  action ("Proceed"). Its own 2.5.3 question — visible "Checkout Proceed" vs name "Proceed to
  checkout" — is a follow-up finding, out of scope here.

---

## Implementation plan

- [ ] 1. Put the customer-id derivation in one documented helper in
      `amplify/functions/shared/lambda_utils/customer_auth.py` and make the Cognito `sub` the single
      authority. Replace the `custom:customer_id` read in `authenticate()` with a call to a new
      `customer_id_from_attributes(attributes)`; keep all three existing checks (GetUser liveness,
      issuer pin, `authorize_resource`) untouched — only the *source* of `identity.customer_id`
      changes. Record in the docstring: the attribute does not exist in this pool's schema and never
      has; `sub` is immutable, pool-scoped and not client-writable; every customer-keyed table was
      measured empty on 2026-10-02 so there is nothing to migrate; and it is deliberately a single
      authority, not a fallback, so a later backfill cannot silently re-key a customer. Keep the
      raise and the `customer_auth_no_customer_id` warning for the genuinely impossible case of a
      token with no `sub`.
      Files: `amplify/functions/shared/lambda_utils/customer_auth.py`
      Verify: `/Users/wecaredigital/wecare-store/.venv/bin/python -m pytest tests/test_customer_auth_and_throttle.py tests/test_customer_session.py tests/test_customer_whatsapp_auth.py tests/test_customer_session_endpoint.py -q` — still 83 passed.

- [ ] 2. Add the Python regression tests that would have caught the outage.
      In `tests/test_customer_auth_and_throttle.py`: a `get_user` response carrying exactly the real
      pool's attribute set (`phone_number`, `phone_number_verified`, `name`,
      `custom:partner_waba_id`, `sub`) and **no** `custom:customer_id` must authenticate, and
      `identity.customer_id` must equal the `sub`; a second case asserting `custom:customer_id` is
      not required by any code path; a third asserting a token with no `sub` still raises
      `CustomerNotAuthenticated`. Depends on item 1.
      Files: `tests/test_customer_auth_and_throttle.py`
      Verify: `/Users/wecaredigital/wecare-store/.venv/bin/python -m pytest tests/test_customer_auth_and_throttle.py -q` — new cases pass; the first one fails if item 1 is reverted.

- [ ] 3. Make the endpoint test exercise the real derivation. Every case in
      `tests/test_customer_session_endpoint.py` currently monkeypatches
      `customer_auth.authenticate` to return a hardcoded `CustomerIdentity(customer_id='CUS_QA', …)`
      (lines 41-42), which is why the endpoint tests are blind to this failure. Add one case that
      stubs only Cognito `get_user` (with the attribute set from item 2) and lets the real
      `authenticate` run through `action='exchange'` to a 200 with a `csrfToken` and a `Set-Cookie`.
      Leave the existing stubbed cases alone — they cover other concerns.
      Files: `tests/test_customer_session_endpoint.py`
      Verify: `/Users/wecaredigital/wecare-store/.venv/bin/python -m pytest tests/test_customer_session_endpoint.py -q` — all pass, including the unstubbed case.

- [ ] 4. Reconcile `customer-registration` to the same single identity rule.
      `amplify/functions/auth/customer-registration/handler.py` stamps a `CUS_…` id onto
      `custom:customer_id` at `AdminCreateUser`. That attribute cannot exist in this pool, and after
      item 1 the stamped value is no longer what `authenticate` honours. Have it call
      `customer_auth.customer_id_from_attributes` (or the created user's `sub`) so the two cannot
      diverge, and note in the file that the function is **not deployed and has no route** today, so
      this is pinning rather than a behaviour change. Keep
      `tests/test_customer_registration_handler.py` green, adjusting its expectations to the shared
      helper rather than to a literal `CUS_` prefix. Depends on item 1.
      Files: `amplify/functions/auth/customer-registration/handler.py`, `tests/test_customer_registration_handler.py`
      Verify: `/Users/wecaredigital/wecare-store/.venv/bin/python -m pytest tests/test_customer_registration_handler.py -q` — all pass.

- [ ] 5. Stop a failed exchange from destroying a successful sign-in (`src/lib/customerAuth.ts`).
      In `submitOtp`, move `storeSession(token, expiresAt)` to **before** the
      `/api/ecommerce/customer-session` exchange. On a non-ok exchange response, do **not** throw:
      return `{ accessToken, expiresAt, remembered: false }`. On success set the hint as today and
      return `remembered: true`. Add the optional `remembered?: boolean` to `CustomerSession` (purely
      additive). Comment the reasoning: the Cognito challenge has already succeeded, the exchange buys
      persistence rather than authentication, and `restoreSession()` already treats a missing hint as
      "sign in again". Do not change `normaliseMobile` — its docblock requires byte-for-byte
      agreement with the backend.
      Files: `src/lib/customerAuth.ts`
      Verify: `npx vitest run src/test/CustomerSessionRestore.test.ts` — existing 6 cases still pass.

- [ ] 6. Pin the exchange-failure path in `src/test/CustomerSessionRestore.test.ts`.
      New case: Cognito resolves `AuthenticationResult` with a refresh token, the session endpoint
      resolves **401**; `submitOtp` must resolve (not reject), `getSession()` must return the access
      token, `remembered` must be `false`, the refresh token must not appear in either storage, and
      no `sessionHint` must be written. Today only the 200 path is covered, which is the gap that let
      this ship. Depends on item 5.
      Files: `src/test/CustomerSessionRestore.test.ts`
      Verify: `npx vitest run src/test/CustomerSessionRestore.test.ts` — new case passes; it fails if item 5 is reverted.

- [ ] 7. Pin the page-level symptom in `src/test/SignInMessages.test.tsx`, extending its existing
      discipline (exact approved strings, plus the page imports them by name).
      Two cases, both driving the real `submitOtp` through a stubbed `fetch` rather than mocking
      `customerAuth.submitOtp` — note that `AccountSignIn.test.tsx` mocks `submitOtp` wholesale,
      which is why no page test ever ran the exchange. (i) Cognito success + session endpoint 401:
      the page must navigate to the return path and must render **no** `role="alert"`; assert
      explicitly that `signInMessages.TRY_LATER` is not rendered. (ii) Cognito success + session
      endpoint 200: navigates, and the hint lands in `localStorage`. Keep the seven-string table and
      the no-red assertions untouched. Depends on items 5 and 6.
      Files: `src/test/SignInMessages.test.tsx`
      Verify: `npx vitest run src/test/SignInMessages.test.tsx src/test/AccountSignIn.test.tsx` — all pass.

- [ ] 8. Fix the styled-jsx scoping and add a single-label mode in
      `src/components/PillButton.tsx`. Delete the intermediate `inner` variable and write the two
      `<span>` segments inline inside **both** the `<a>` and the `<button>` branches, so styled-jsx
      attaches its scope class to them. Make `label` optional (`label?: string`); when it is absent
      render only the action segment and give it the full pill radius on both ends
      (`border-radius:999px`, no `border-inline-start` divider) so a one-segment pill still reads as
      the home-page treatment. Update the docblock: record that the segments must stay inside the
      returned JSX tree because styled-jsx does not transform JSX held in a variable, that this
      shipped unstyled to production, and that jsdom cannot catch it because vitest does not run the
      transform at all. Then switch both `/account/sign-in` CTAs to the single-label form — pass
      `action` only, drop `label="Sign in"` — so visible text equals the accessible name. Leave
      `src/pages/cart.tsx` on the two-segment form.
      Files: `src/components/PillButton.tsx`, `src/pages/account/sign-in.tsx`
      Verify: `npx vitest run src/test/PillButton.test.tsx src/test/AccountSignIn.test.tsx src/test/CartCheckout.test.tsx` — all pass, including the pinned names "Send code", "Confirm code", "Proceed to checkout".

- [ ] 9. Add the tests for the pill, at both the layer that can see names and the only layer that can
      see scoping.
      In `src/test/PillButton.test.tsx`: single-label mode renders exactly one segment, the accessible
      name equals the visible text, and no `aria-hidden` element carries label text; two-segment mode
      still names the action alone. Then a **new** `src/test/PillButtonBuildScope.test.ts` that reads
      `out/account/sign-in/index.html`, collects every `.pill*` selector hash from the inlined
      `<style>` blocks and every `class="…pill…"` attribute from the markup, and asserts every
      pill-classed element carries the matching `jsx-*` hash — with a `.skip` and an explicit message
      naming the build command when `out/` is absent, so it never silently passes.
      Build prerequisites, measured: there is no `node_modules` in the worktree. A gitignored symlink
      to `/Users/wecaredigital/wecare-store/node_modules` is already in place — keep it, and do **not**
      run `npm install` into the parent. `npx next build` **fails** here because `next.config.js` pins
      `turbopack.root` to the worktree and Turbopack will not resolve `next` through the symlink; use
      `--webpack`, which succeeds. Depends on item 8.
      Files: `src/test/PillButton.test.tsx`, `src/test/PillButtonBuildScope.test.ts`
      Verify: `node scripts/generate-public-pages.js && npx next build --webpack` then `npx vitest run src/test/PillButton.test.tsx src/test/PillButtonBuildScope.test.ts` — all pass. Confirm the build-scope test fails when item 8 is reverted.

- [ ] 10. Reproduce and verify in a real browser, then run the full gates.
      Reproduction, with the live/simulated split stated explicitly below. Then:
      `npx vitest run` (baseline to beat: **59 files / 799 tests, all passing**) and
      `/Users/wecaredigital/wecare-store/.venv/bin/python -m pytest tests/ -q`. Leave the **5
      pre-existing failures in `tests/test_url_host_routing_rules.py`** alone — they come from another
      session's `8b24baa0`, are unrelated to OTP, and the measured baseline is 5 failed / 8 passed.
      Record the outcome in `docs/execution/change-authority-matrix.md` with class, target, evidence
      and rollback, and hand the deploy over as owner work (see "Not done here").
      Files: `docs/execution/change-authority-matrix.md`
      Verify: `npx vitest run` — 799+ passing, 0 failing; `pytest tests/ -q` — no new failures beyond the 5 known ones.

---

## (e) Verification plan, including the real-browser reproduction

### Measured baselines, so a regression is distinguishable from the pre-existing state

| Gate | Baseline on `72a2c5d3` |
|---|---|
| `npx vitest run` | 59 files, 799 tests, **all pass** |
| `pytest tests/test_customer_session_endpoint.py test_customer_auth_and_throttle.py test_customer_session.py test_customer_whatsapp_auth.py` | **83 passed** |
| `pytest tests/test_url_host_routing_rules.py` | **5 failed / 8 passed** — pre-existing, out of scope |
| `node scripts/generate-public-pages.js && npx next build --webpack` | succeeds; reproduces the pill bug in `out/` |

### What is exercised live versus simulated

The OTP **send** cannot be exercised without an owner handset, and no live-send flag may be touched.
So the confirm round trip is reproduced by canning exactly two network responses, with everything
else real.

| Layer | Live | Simulated |
|---|---|---|
| Pill rendering, both phases | real browser, real Next build, real styled-jsx output, real CSS cascade | nothing |
| Reaching the code phase | real React state, real submit handler, real `composeE164` / `normaliseMobile` | `InitiateAuth` challenge response |
| Confirm classification | real `submitCode`, real `messageForAuthError`, real `storeSession` | `RespondToAuthChallenge` success, and the session endpoint's 401 / 200 |
| Server derivation | real handler + real `customer_auth` under pytest | Cognito `get_user` |
| Live endpoint posture | real read-only probes against production | nothing |

### Browser steps

1. `node scripts/generate-public-pages.js && npx next dev -p 3099` — a non-default port so it cannot
   collide with the other live session.
2. Open `http://localhost:3099/account/sign-in/`. **Before item 8**, confirm in DevTools that both
   segment spans carry no `jsx-*` class and `getComputedStyle` reports no background on them. This is
   the pre-fix rendering evidence; it is also already confirmed against the production HTML.
3. In the console, wrap `window.fetch` so that: `InitiateAuth` resolves a canned challenge with a
   masked destination; `RespondToAuthChallenge` resolves a canned `AuthenticationResult` carrying an
   AccessToken and a RefreshToken; and `/api/ecommerce/customer-session` resolves
   `401 {"error":"VERIFICATION_REQUIRED"}`. Drive the form by hand.
4. **Before item 5:** the page shows "Try again shortly." — the owner's symptom reproduced in a real
   browser with no handset. **After item 5:** the page navigates to the return path and
   `sessionStorage` holds the access token.
5. Flip the session stub to 200 and confirm the hint lands in `localStorage` and the page navigates.
6. **After item 8:** the confirm button reads exactly "Confirm code", one segment;
   `getComputedStyle` shows the mint background and the 999 px radius; the accessible name equals the
   visible text in the accessibility pane.
7. Check 360 px and 320 px widths and `prefers-reduced-motion: reduce`.

### Server verification without a deploy

Prove the derivation under pytest against a recorded `get_user` shape taken from the real pool's
attribute set. Then re-probe the live endpoint read-only to confirm the unauthenticated posture is
unchanged: no `Origin` → 403 `ORIGIN_REQUIRED`, `Origin` + invalid bearer → 401
`VERIFICATION_REQUIRED`.

### Needs runtime verification during implementation

- That the exchange was the **only** failing step in the owner's attempt. The 401 is proven
  server-side; that the browser's `RespondToAuthChallenge` returned a RefreshToken — and so entered
  the exchange branch at all — is inferred from the log timing and cannot be proven from logs, since
  Cognito's own API is not logged into this account. Browser step 4 settles it.
- The owner-reported symptom is **not** dismissed as already-working. It is reproduced in step 4
  before any fix is applied; if it does not reproduce there, stop and re-measure rather than
  proceeding.

### Not done here — carried as owner work

- **No deploy, no `publish-version`, no alias move.** Per `lambda-snapstart-deploy.md` the fix is not
  live until a version is published and the `live` alias moves. `customer_auth` lives in the **shared
  layer**, so `wecare-customer-session` (live **v5**), `wecare-checkout` and `wecare-wix-store` all
  need republishing, and `scripts/snapstart_publish.py` must run.
- **No `update-user-pool`, and no `add-custom-attributes`.** Option B1 is chosen precisely so that no
  pool mutation is required. If the owner later prefers the attribute route, it is additive and
  irreversible and belongs to them.
- **No credential read, no live-send flag change, no masking change.** `*******0044` stays ambiguous
  between the owner QA recipient and the live business number; disambiguate on direction, channel or
  the `wecare-customer-whatsapp-auth` delivery id.
- **Follow-ups recorded, not actioned:** the cart pill's own WCAG 2.5.3 question; the missing
  `stack-wecare-digital-CustomersTable` (design C-5); the wrong C-1 claim in
  `.agents/tasks/customer-session-20261001/design.md` about adding custom attributes; and
  `wecare-customer-registration` having neither a deployed function nor a route, which means the
  unregistered branch of `sign-in.tsx` would also fail if a new number ever reached it.
