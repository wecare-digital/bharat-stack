# Checkout and Razorpay readiness — measured findings, 2026-10-02

**Mode:** read-only investigation. Nothing was modified, deployed, published, staged, committed or pushed. No payment, refund, capture, OTP, message or provider mutation was performed. No secret value was read or printed.

**Repo:** `/Users/wecaredigital/wecare-store`, branch `stack`, `HEAD = 2ef4049d5f360a77518c716e5f3974b0d818f65e` (`git rev-parse HEAD`).
**Working tree at measurement:** only two untracked review files under `.agents/` (`git status --short`). Four warm sessions are live and `gift_card_store.py` / `tests/test_gift_card_store.py` were committed at HEAD mid-brief — see §9.
**Account:** 775261844268, `us-east-1`, profile `wecare-prod`.

---

## 1. Three-line answer

1. **Is checkout working? No — and not because of a bug.** The chain is deliberately switched off at two independent gates and a third is broken by accident. The live `wecare-checkout:live` (v4) carries `EXPECTED_CONFIGURATION_NAME=""` and `EXPECTED_PROVIDER_MID=""`, so `payment_readiness.evaluate` returns `CONFIGURATION_UNVERIFIED` and every create answers **409 `payment_unavailable`** before an attempt is even reserved; `CHECKOUT_INITIATION_ENABLED` is absent, so the next gate would answer `PAYMENT_INITIATION_DISABLED` anyway. On top of that, customer sign-in is **genuinely broken in production** — `custom:customer_id` is absent from the customer pool's schema, so `customer_auth.authenticate()` raises for every customer token, measured 5 times today, most recently 2026-10-02T08:01:04.893Z. Zero orders, zero payments, zero attempts, zero sessions have ever existed (`ItemCount: 0` on all of them).

2. **Is Razorpay connected? The plumbing is correct and live; the account is not yet transacting.** `POST /razorpay-webhook` → `wecare-razorpay-webhook:live` v47 is reachable and answers **401 `{"error": "Invalid signature"}`** to an unsigned body, so HMAC verification is live and fails closed. Secret wiring is correct and lazy (`wecare/razorpay-webhook:webhook_secret` for signatures, `wecare/razorpay/api` for the API pair). The retained MID `acc_TTFSyolquKEZEy` and VPA are on `wecare-whatsapp-business-api:live` v61; the retired `acc_HDfub6wOfQybuH` has **zero occurrences anywhere in the tree**. But **no capture has ever been processed**: `order_paid` and `payment_captured` are both 0 events since 2026-09-26.

3. **Anything else pending? Four things that block a purchase, in this order:** (a) the customer sign-in outage — fix exists on an unmerged branch; (b) the two owner-only readiness values, which no code may supply; (c) a reproduced **double-debit window in `gift_card_store.redeem()`** on the ordinary finalization path, open as of 13:45 today; (d) the website Razorpay Standard Checkout, which is tested source with **no production caller at all**. 84 of 114 spec tasks are still open (`grep -c` on `tasks.md`).

---

## 2. Checkout chain — DECLARED / DEPLOYED / VERIFIED

Vocabulary as the brief defines it. **DEPLOYED** means present and `Active` in the account *with the `live` alias pointing at the version containing it*. 58 → now **61 of 69** functions carry a `live` alias (re-measured, see §7), so the alias is the thing that matters.

| # | Step | Function (live alias / version) | Route | Table | State | Evidence |
|---|---|---|---|---|---|---|
| 1 | Browse catalogue | `wecare-wix-store:live` v33 | `GET /wix-store/{proxy+}` | `WixProductsCache` | **VERIFIED** | `GetFunctionConfiguration`: `Version 33, State Active, LastUpdateStatus Successful`; `/shop/` returns 200 HTML |
| 2 | Cart (browser-owned, prices never sent) | — (`src/lib/cart.ts`, `src/pages/cart.tsx`) | — | localStorage | **VERIFIED** | `npx vitest` set includes `src/test/CartCheckout.test.tsx`; no cart route exists server-side (364-route enumeration) |
| 3 | Customer sign-in — request OTP | `wecare-customer-whatsapp-auth:live` v12 (pool trigger) | Cognito `CUSTOM_AUTH` | pool `us-east-1_46ULYuukt` | **DEPLOYED, not VERIFIED** | `DescribeUserPool` → `LambdaConfig: [CreateAuthChallenge, DefineAuthChallenge, VerifyAuthChallengeResponse]`. Live send to a handset is not authorised by this task |
| 4 | **Customer session exchange** | `wecare-customer-session:live` v5 | `POST /ecommerce/customer-session` | `CustomerSessionsTable` | **DEPLOYED, VERIFIED BROKEN** | Probe → `403 {"error": "ORIGIN_REQUIRED"}` (handler executes). `FilterLogEvents` → **5 × `{"event":"customer_auth_no_customer_id"}`** on streams tagged `[5]` (the live version), last **2026-10-02T08:01:04.893Z**. `CustomerSessionsTable ItemCount: 0` |
| 5 | Checkout create — authoritative total | `wecare-checkout:live` v4 | `POST /ecommerce/checkout` | `WixOrderIds` (as `COMMERCE_KEYS_TABLE`), `PaymentAttemptsTable` | **DEPLOYED, partially VERIFIED** | Probe → `401 {"error":"VERIFICATION_REQUIRED",...}`: the auth gate executes. Beyond auth, nothing has ever run — 15 recent log events are `INIT_START`/`START`/`END`/`REPORT` only, `Duration: 1.79 ms`, **no application log line at all** |
| 6 | Readiness gate (live Meta readback) | `payment_readiness.evaluate` inside step 5 | — | — | **DEPLOYED, blocks by configuration** | Live env on `wecare-checkout:live`: `EXPECTED_CONFIGURATION_NAME: ""`, `EXPECTED_PROVIDER_MID: ""`. `payment_readiness.py:242-248` returns `CONFIGURATION_UNVERIFIED` for either, and `handler.py:485-491` answers **409 `payment_unavailable`** |
| 7 | Reserve `PAYREF#` + PaymentAttempt | step 5, `order_keys.allocate_payment_reference` | — | `WixOrderIds` | **DEPLOYED, never reached** | Code at `handler.py:494-516`, *after* the readiness return. `PaymentAttemptsTable ItemCount: 0` |
| 8a | Pay — **in-WhatsApp** `order_details` | `wecare-whatsapp-business-api:live` v61 | invoked by ARN, not routed | — | **DEPLOYED, gated off** | `CHECKOUT_INITIATION_ENABLED` **absent** from the live env → `handler.py:541-553` returns `PAYMENT_INITIATION_DISABLED` |
| 8b | Pay — **website Razorpay Standard Checkout** | **none** | **none** | — | **DECLARED ONLY** | `website_checkout.py` (24 KB) has **no production caller**: `grep` finds it only in `checkout/handler.py:58` (a docstring), `blog_contribution.py` (a sibling that mirrors it) and tests. `grep -rn "checkout.razorpay.com\|new Razorpay" src/` → **no matches** |
| 9 | Webhook receipt + signature verify | `wecare-razorpay-webhook:live` v47 | `POST /razorpay-webhook` | `RazorpayWebhookLogTable` | **VERIFIED** | Probe → `401 {"error": "Invalid signature"}` on both `https://wecare.digital/api/razorpay-webhook` and the `execute-api` host |
| 10 | Provider readback + reconcile → one order | `order_creation.reconcile_payment` via step 9 | — | `WixOrderIds`, `OrderTable` | **DEPLOYED, never exercised live** | 174 tests pass (§7). `order_paid`: **0 events** since 2026-09-26; `OrderTable ItemCount: 0`, `PaymentsTable ItemCount: 0` |
| 11 | Wix order write-back | `wix_writeback` via `finalization.accept_paid` | — | `WixOrderIds` | **DECLARED ONLY** | `finalization.py` has **no production caller** — see §3. `wix_writeback.is_enabled()` flags unset |
| 12 | Receipt | `customer_receipt.py` | **none** | — | **DECLARED ONLY** | No route; `test_checkout_package_completeness.py:43` states outright that `customer_receipt` "is NOT imported by the handler today" |
| 13 | Coupons | `wecare-coupons` | **none** | `CouponsTable` | **DECLARED ONLY** | Function **absent** from the 69-function `ListFunctions`. Probe → `404 {"message":"Not Found"}`. `CouponsTable` **absent** from the 82-table `ListTables` |
| 14 | Gift cards | `wecare-gift-cards`, `wecare-wix-giftcard-spi` | **none** | `GiftCardsTable` | **DECLARED ONLY** | Both functions absent; probe → `404`; `GiftCardsTable` absent |

### Live probe evidence, verbatim

```
POST https://wecare.digital/api/ecommerce/checkout          401 application/json  {"error": "VERIFICATION_REQUIRED", "message": "Please verify your WhatsApp number to continue."}
POST https://wecare.digital/api/ecommerce/customer-session   403 application/json  {"error": "ORIGIN_REQUIRED"}
POST https://wecare.digital/api/razorpay-webhook             401 application/json  {"error": "Invalid signature"}
POST https://wecare.digital/api/ecommerce/coupons            404 application/json  {"message":"Not Found"}
POST https://wecare.digital/api/ecommerce/gift-cards         404 application/json  {"message":"Not Found"}
POST .../zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/ecommerce/checkout   401  (identical body)
POST .../zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/razorpay-webhook     401  {"error": "Invalid signature"}
```

All five POSTs carried `{}` and were rejected before any side effect. Every one is inert.

### One correction to the hostname in the code

`razorpay-webhook/handler.py:3` documents the webhook URL as `https://api.wecare.digital/razorpay-webhook`. That host answers **403 text/html** (not our API), and `apigatewayv2 GetDomainNames` returns **zero custom domain names** in this account. The reachable paths are `https://wecare.digital/api/razorpay-webhook` (via CloudFront) and the `execute-api` URL. The docstring is stale; it is a comment, not a configuration, so nothing breaks — but anyone pasting it into the Razorpay dashboard would configure a dead endpoint.

### Live table state — nothing has ever flowed

`DescribeTable`, all `ACTIVE`:

| Table | ItemCount | Keys / GSIs |
|---|---:|---|
| `stack-wecare-digital-PaymentAttemptsTable` | **0** | `paymentAttemptId`; `status-index`, `referenceId-index`, `customerId-index` |
| `stack-wecare-digital-OrderTable` | **0** | `orderId`; `shortId`, `customerPhone`, `orderStatus`, `source` |
| `stack-wecare-digital-PaymentsTable` | **0** | `id`; `orderId-index`, `paymentId-index` |
| `stack-wecare-digital-WixOrderIds` (= `COMMERCE_KEYS_TABLE`) | **0** | `orderId`; no GSI |
| `stack-wecare-digital-CustomerSessionsTable` | **0** | `sidHash` |
| `stack-wecare-digital-InvoicesTable` | **0** | `invoiceId`; `referenceId-index`, `contactId-index` |
| `stack-wecare-digital-RazorpayWebhookLogTable` | **154** | audit rows only |

`ItemCount` is a ~6-hourly estimate, so treat each `0` as "no sustained population" rather than a per-second guarantee. Six independent zeros plus zero `order_paid` log events is conclusive enough: **no customer has completed a purchase through this path.**

Worth recording because it resolves an older open question: `COMMERCE_KEYS_TABLE` is **not** a missing `CommerceKeys` table. It is set to `stack-wecare-digital-WixOrderIds`, which is keyed on `orderId` — exactly the partition key `order_keys` composes its `PAYREF#` / `PROVIDERPAYMENT#` / `PAYMENTATTEMPT#` / `ORDERNO#` prefixes against. Earlier audits reporting "`CommerceKeys` absent" were reading for a name that was never provisioned, not for a capability that is missing.

---

## 3. First break in the chain

**Step 4 — the customer session exchange — is the first step that is DEPLOYED and VERIFIED BROKEN.** Everything downstream is therefore unreachable by a real customer regardless of how the gates are set.

The cause is exact and measured, not inferred. `customer_auth.authenticate()` at `amplify/functions/shared/lambda_utils/customer_auth.py:165-171` reads:

```python
customer_id = str(attributes.get("custom:customer_id") or "")
...
if not customer_id:
    logger.warning('{"event":"customer_auth_no_customer_id"}')
    raise CustomerNotAuthenticated("session carries no customer id")
```

`DescribeUserPool` on `us-east-1_46ULYuukt` (`WECARE.DIGITAL-CUSTOMERS`) returns a schema whose **only** custom attribute is `custom:partner_waba_id`:

```
custom_attrs: ["custom:partner_waba_id"]
EstimatedNumberOfUsers: 1   AllowAdminCreateUserOnly: true   MfaConfiguration: OFF
```

An attribute absent from the schema cannot be set on a user, so the read returns `''` for **every token Cognito has ever issued against this pool**. The OTP *send* works (the pool triggers are intact and never touch `customer_auth`), and `RespondToAuthChallenge` succeeds — the customer is authenticated at that instant — and then the session exchange refuses them. That is why it reads as "the code was right and sign-in still failed".

### What it would take to verify step 4

The fix exists but **is not on `stack`**. `git worktree list` shows `.worktrees/otp-fix` on branch `fix/otp-confirm` at `c8cdb426`, and `git diff --stat stack...fix/otp-confirm` reports 13 files / 642 insertions touching `customer_auth.py` (+56), `auth/customer-registration/handler.py`, `identity/registration.py`, `src/lib/customerAuth.ts` and four test files. To verify step 4 end to end: merge that branch to `stack`, deploy `wecare-customer-session` and whichever functions import `customer_auth`, publish, move each `live` alias, then run one OTP round trip to the owner-nominated QA recipient. **The last step is owner-gated** (see §8).

Note what the second break would be if step 4 were fixed today: **step 6**, the readiness gate, which no amount of code can satisfy (§8).

---

## 4. Razorpay connection

### 4.1 Secret path and laziness — CORRECT, and the steering summary needs one qualification

There are two secrets and they are not interchangeable. Both are read **lazily, at request time**, measured by reading the live source:

| Consumer | Secret id | Field | When read |
|---|---|---|---|
| `payments/razorpay-webhook/handler.py:51,53-70` | `wecare/razorpay-webhook` | `webhook_secret` | `_get_webhook_secret()`, first request, cached per sandbox. Module scope holds only `_webhook_secret_cache = ''` |
| `shared/lambda_utils/integrations/razorpay_verify.py:56,96-110` | **`wecare/razorpay/api`** | `key_id` + `key_secret` | `_credentials()`, first use, `_cached` guard |
| `shared/lambda_utils/integrations/razorpay_orders.py:74` | `wecare/razorpay/api` | `key_id` + `key_secret` | lazy |
| `core/secure-files/razorpay_orders.py:82` | `wecare/razorpay/api` | `key_id` + `key_secret` | lazy |
| `messaging/partner-onboarding/handler.py:563` | `wecare/razorpay/api` | `key_id` + `key_secret` | lazy, with an explicit 501 if absent |

The qualification: `whatsapp-payments-india-reference.md` says "the webhook handler must read `wecare/razorpay/api`". Read precisely, that is about the **API pair**. The webhook handler correctly reads `webhook_secret` from `wecare/razorpay-webhook`, which is the only field that path has ever held, and the *authoritative verification* in the same request flow goes through `razorpay_verify`, which reads `wecare/razorpay/api`. Both halves are on the canonical path. `grep -rn "wecare/razorpay"` across `amplify/` and `scripts/` finds **no code reading `key_id` out of `wecare/razorpay-webhook`**.

`DescribeSecret` metadata only — no value was requested:

```
wecare/razorpay/api       LastChangedDate 2026-09-19T03:19:33Z  LastAccessedDate 2026-10-02  stages [AWSCURRENT, AWSPREVIOUS]  DeletedDate None
wecare/razorpay-webhook   LastChangedDate 2026-09-30T22:58:35Z  LastAccessedDate 2026-10-02  stages [AWSCURRENT]              DeletedDate None
```

Both are accessed as recently as today, so the consumers resolve.

> **`scripts/verify_razorpay_secret_path.py` was NOT run, deliberately.** The brief asks for it, but reading its source (`sm.get_secret_value(SecretId=...)` at lines 36, 63) shows it calls `secretsmanager get-secret-value` twice and brings credential material into the process. That is a hard prohibition in this same brief, in `aws-agent-rules.md` and in `01-standing-authorization.md`, and `block_catastrophic.py` denies it on the shell route. A standing refusal outranks a suggested verification step. I verified the same property by reading every call site above and by `DescribeSecret` metadata, which is strictly weaker on one point only: I cannot confirm `wecare/razorpay/api` actually *contains* populated `key_id`/`key_secret`. Named unblock in §8.

### 4.2 Which merchant account is current — PURGE COMPLETE, one coverage gap STILL OPEN

Live, on `wecare-whatsapp-business-api:live` v61:

```
RAZORPAY_MID    : acc_TTFSyolquKEZEy
RAZORPAY_UPI_ID : wecaredigitalbh511413.rzp@rxairtel
```

The retired account: `grep -rn "acc_HDfub6wOfQybuH"` across every `.py`, `.ts`, `.tsx` and `.json` in the tree returns **zero matches**. The purge is complete in source, and the retired identifier survives in no live code path.

`payment_readiness.py:27-39` records `acc_TTFSyolquKEZEy` as authoritative and compares the MID Meta reports against `expected_provider_mid`, refusing on disagreement rather than picking a winner. `tests/test_payment_readiness.py` — **52 passed**.

**The coverage gap the brief asks about is STILL OPEN.** The wrong-account fixture is now the synthetic `acc_RETIRED_FIXTURE` (`tests/test_payment_readiness.py:79-84`, `tests/test_payment_status.py:41,61`), so no test proves *this specific retired account id* is refused. The property is still pinned — a mismatching MID is refused — but the narrow regression naming `acc_HDfub6wOfQybuH` is gone. Severity **LOW**: the general property is what protects the money, and re-introducing the literal would put a retired identifier back in the tree, which the purge exists to prevent. Two prior reviews already flag the leftover prose that attributes history to a string that never existed (`razorpay-account-purge-20261002/review.md` items 4 and 5) — cosmetic, and still unfixed.

### 4.3 Webhook wiring and signature verification — VERIFIED

- **Route exists:** `POST /razorpay-webhook` → `wecare-razorpay-webhook:live`, `AuthorizationType: NONE`, on API `zllr9lrg7j`, stage `prod`, `AutoDeploy: true`. There is **no** `POST /payments/webhook` — an older audit named it; it is not in the 364-route enumeration.
- **Gateway config proves nothing here**, exactly as the brief warns: all 364 routes report `NONE`, `JWT` or `AWS_IAM`, and this one is `NONE` by design because Razorpay cannot present a JWT.
- **The handler is the control, and it works.** `handler(...)` reads `x-razorpay-signature`, base64-decodes the body if flagged, logs *shape only*, then `if not _verify_signature(body, signature): return 401`. An unsigned `{}` body to the live endpoint returned **`401 {"error": "Invalid signature"}`**. It fails closed.
- **Not an unsigned mutation path.** CRITICAL ruled out.

One measurement that looked alarming and is not, recorded so nobody re-raises it. `FilterLogEvents` reports **66 `webhook_signature_invalid`** events between 2026-09-26T15:46:02Z and 2026-10-02T08:05:40Z. Pulling the paired `webhook_received_shape` lines for the recent window shows what they are:

```
2026-10-02T02:35:19.706Z  {"event": "webhook_received_shape", "hasBody": false, "bodyLen": 0, "hasSignature": false, ...}
2026-10-02T08:05:40.680Z  {"event": "webhook_received_shape", "hasBody": true,  "bodyLen": 2, "hasSignature": false, ...}
```

`bodyLen: 2` is my own `{}` probe. These are empty, unsigned provisioning checks and probes, **not rejected Razorpay deliveries** — a real delivery carries a signature and a body (an older sample shows `bodyLen: 462, hasSignature: true`). So: **do not read this as "Razorpay's webhooks are being rejected".** I could not establish from logs whether a *signed* Razorpay delivery has arrived recently, because `razorpay_webhook_received` saturates the 1000-event page cap over any useful window; what I can state is that the success path has never fired (§4.5).

### 4.4 Status vocabulary — single authority, AST gate PASSES

`tests/test_payment_vocabulary_at_decision_points.py`: **56 passed in 0.39s**.

The gate asserts six handlers bind `lambda_utils.payment_status` (`invoice-engine`, `razorpay-webhook`, `inbound-whatsapp-handler`, `outbound-whatsapp`, `whatsapp-business-api`, `whatsapp-business-api/flows/track_request.py`) and walks the **AST** of those six plus three raw-scan-only files (`ecommerce/coupons`, `ecommerce/gift-cards`, `ecommerce/wix-giftcard-spi`) for `== 'captured'`. `FORBIDDEN_RAW = {"captured"}` only, with `paid` and `pending` deliberately excluded and the reasoning written into the file at lines 235-253.

The deliberate boundary the brief warns about is intact and tested. `test_the_invoice_document_lifecycle_is_deliberately_left_raw` (line 313) pins it: `InvoicesTable.status` is the document lifecycle `created → sent → paid → cancelled`, `inv.get('status') != 'paid'` is correct, and it must not be "fixed". `payment_status.py` exposes `canonical`, `for_storage`, `rank`, `should_apply`, `condition_expression` — monotonic ordering is owned by the module, so a late webhook cannot move an order backwards. `tests/test_payment_status.py`: **59 passed**.

### 4.5 Does the live Lambda serve this code?

| Function | `live` → version | State | LastUpdateStatus | LastModified (UTC) | CodeSha256 |
|---|---:|---|---|---|---|
| `wecare-whatsapp-business-api` | **61** | Active | Successful | 2026-10-02T04:09:40 | `rmzfLkYxOeRepo02c39cn56fbi6WX1LZ/ZT6AOil0q8=` |
| `wecare-razorpay-webhook` | **47** | Active | Successful | 2026-10-02T02:30:03 | `rOBqX9I1Tn412OY0RpxGJMFCQIxlSIezc4rhwKD7Os8=` |
| `wecare-checkout` | **4** | Active | Successful | 2026-10-02T02:34:41 | `ER/lVmown60DQYMlCRGsPetDvc41d0FeyJJO66yjvr0=` |
| `wecare-customer-session` | **5** | Active | Successful | 2026-10-02T02:26:43 | `y0VEASen1bn64XUGSRYK6qWw350dMC3rpAH0cYDqYCg=` |
| `wecare-wix-store` | **33** | Active | Successful | 2026-10-02T02:34:38 | `zS/mJxm1Q+bEYjH5rDFIMkp1/Al7Il139dbc+wHDNh8=` |
| `wecare-invoice-engine` | **40** | Active | Successful | 2026-10-02T02:30:23 | `9xExUQNIpYD9OEihd/R4aNv3yV3oVrtNRCBQbJXHtdg=` |

`wecare-whatsapp-business-api:live` v61 and its CodeSha256 match the deployment evidence in the original request exactly, and `WIX_SITE_URL` is `https://wecare.digital`. That claim is independently confirmed.

**What I did not confirm:** whether any of these CodeSha256 values corresponds byte-for-byte to `HEAD = 2ef4049d`. Doing so requires building each package (`deploy_all_lambdas.py --dry-run`) or running `provision_checkout.py --verify`, both of which are deploy scripts this brief forbids running. The timestamps (all 2026-10-02 02:26–04:09Z) predate HEAD's commits, so the live code is **almost certainly behind `stack`** — in particular `2ef4049d` (the gift-card void fix) and `cca83710` (initiation/finalization) are not in any deployed artifact. Stated as a bounded unknown, not a measurement.

---

## 5. Idempotency and money handling

### 5.1 Replay safety — resolve-before-generate is REAL, and the known defect is CLOSED

**Answer: yes, order creation is idempotent against a replayed payment event, and I verified it in the code rather than from a prior claim.**

`order_creation.reconcile_payment` (`order_creation.py:157+`) resolves in this order, and the ordering is the mechanism:

1. `load_attempt(reference_id)` — a reference with no stored attempt returns `UNKNOWN_REFERENCE` and refuses. The docstring states why plainly: "inventing an order from it is how a forged webhook becomes a free order."
2. `CUSTOMER_MISMATCH` is checked **before** the idempotent shortcut, so an existing order does not grant a different customer read access.
3. `order_keys.resolve_order_for_payment(table, attempt_id)` — **answered before contacting the provider**, deliberately, because redelivery is the common case.
4. On a miss, `order_keys.claim_order_for_payment` claims two conditional rows in a fixed order: `PROVIDERPAYMENT#<txn>` first ("one Razorpay payment may fund at most one order … the constraint an attacker or a provider retry would attack"), then `PAYMENTATTEMPT#<id>`. Losing either returns the **winner's** `orderId` rather than raising. A crash between the two claims recovers from the committed identity and never mints a second order.
5. The public number is reserved separately, `ORDERNO#<number>` under `attribute_not_exists`, and only by the claim winner — so a loser never burns a number.

`REFERENCE#` is present as `LEGACY_REFERENCE_PREFIX` and `resolve_payment_reference` falls back to it for rows written before the `PAYREF#` split (`order_keys.py:376`). Current writes use `PAYREF#`.

Tests, run here: `test_order_keys.py` **81 passed**, `test_order_creation.py` **50 passed**, `test_razorpay_webhook_order_creation.py` **12 passed**, `test_razorpay_webhook_captured_gating.py` **13 passed**, `test_razorpay_binding.py` **24 passed**.

**Spec task 2.2 is CLOSED.** The brief asks whether `_get_or_create_wd_order_number` still returns an unstored number on its exception path. It does not. `ecommerce/wix-store/handler.py:793-870` now reserves under `ORDERNO#` *before* returning, resolves a lost race to the winner's number, and **raises `order_keys.OrderIdentityUnavailable`** on a storage failure instead of returning. Its own docstring documents both the old `startswith('WD-ORD-')` idempotency bug (the generator emits a space at index 6, so the check was false for every number it had ever written) and the fail-open return.

**Two prior CRITICAL/HIGH findings are also CLOSED, verified in current source:**

- **R1/C1, the leaking gate.** `razorpay-webhook/handler.py:1130-1144` now branches on the typed outcome: `if reference_id and not verified_paid and outcome_kind == order_creation.UNKNOWN_REFERENCE:`. Every member of `PAID_BUT_BLOCKED_OUTCOMES` goes to quarantine instead of the legacy verifier. The comment at :1130 names the fix.
- **N2, the unverified wallet credit.** `_handle_wallet_topup_captured` (`handler.py:863-985`) now requires a stored intent (`resolve_topup_intent`), checks the WABA, validates and compares the amount, and claims a conditional per-payment idempotency marker (`claim_topup_credit`) before crediting. Each refusal routes to `_quarantine_unverified_capture`. Quarantine is now durable too — `order_keys.resolve_capture_quarantine` and `capture_quarantine_persist_failed` exist, which R3/N3 said did not.

### 5.2 Money — integer paise, and the `_money_amount` defect is CLOSED

`lambda_utils/ecommerce/money.py` is 31 lines and does exactly one thing: `Money.paise` must be `type(...) is int` (so `bool` and `Decimal` are both refused by type, not coerced), `currency` must be exactly `"INR"`, `from_wix` accepts only `[0-9]{1,14}(\.[0-9]{1,2})?` as a string, and `positive_paise` refuses a `bool`, a non-integral `Decimal` and a non-`int`. Currency is compared explicitly, never inferred from the amount. `tests/test_checkout_package_completeness.py:396` carries `test_no_float_arithmetic_on_the_money_path`, which asserts presence before parsing rather than skipping when a module is absent.

**The `_money_amount` latent defect the brief asks about is FIXED, not latent.** `wix_domain.py:61-90` now returns `''` for a non-numeric value, and its docstring explains that the bare `str(value)` tail meant `_money_amount('abc')` returned `'abc'` into a price field, *and* that a truthy junk value broke the caller's fallback chain so the real price range was never consulted. `tests/test_wix_domain.py:156-173` pins it: `_money_amount("abc") == ""`, `_money_amount({"amount": "not-a-price"}) == ""`, `_money_amount("") == ""`, `_money_amount("   ") == ""`.

**Does an amount mismatch fail closed? Yes.** `AMOUNT_MISMATCH` and `CURRENCY_MISMATCH` are both members of `PAID_BUT_BLOCKED_OUTCOMES`, `needs_human` is True for them, `customer_may_retry` is **hard-coded `False`** for every outcome with the reasoning written in ("the money is already taken, so a retry CTA there would charge twice"), and as of the R1/C1 fix they can no longer fall through to the legacy verifier.

### 5.3 One money defect that is genuinely OPEN

`gift_card_store.redeem()` has a **double-debit window**, reproduced by running the code — not inferred — by the reviewer at `HEAD 2ef4049d` at 13:45 today (`.agents/tasks/wix-coupons-giftcards-20261001/2026-10-02-134500-review.md`). The shape: `_decrement` moves the balance, then `_mark_settled` flips the claim-row marker. A transient failure *between* them leaves the marker saying "not applied", and the retry replays the money move. Reproduced result: final balance 10000 where 30000 is correct — a card debited twice for one payment attempt, contradicting `redeem`'s own first docstring line ("Move balance, exactly once per `(codeHash, paymentAttemptId)`"). `void()` has the mirror defect introduced by the fix for the previous review's finding: final balance 90000 where 50000 is correct.

The reviewer's prescribed fix is one `TransactWriteItems` so the balance move and the marker flip commit atomically; both items are in the same table, so no role gains an action.

**Reachability bounds the severity but does not remove it.** `redeem` is on the ordinary finalization path, which is the worse of the two — but neither `wecare-gift-cards` nor `GiftCardsTable` exists in the live account, so no customer can reach it today. This is a **HIGH** that must be closed before gift cards are provisioned, not a live incident.

---

## 6. Outstanding items, prioritised

Severity per `maintenance-reporting.md`. "Blocks purchase" means a customer cannot complete a purchase until it is closed.

| # | Item | Severity | Blocks purchase | State / evidence |
|---|---|---|---|---|
| 1 | **Customer sign-in is broken in production.** `custom:customer_id` absent from `us-east-1_46ULYuukt`; `customer_auth.authenticate()` raises for every customer token. Fix exists on unmerged `fix/otp-confirm` (`c8cdb426`, 13 files, +642) | **CRITICAL** | **YES** | 5 × `customer_auth_no_customer_id`, last 2026-10-02T08:01:04.893Z; `CustomerSessionsTable ItemCount: 0`; `DescribeUserPool` schema |
| 2 | **Readiness inputs are empty on `wecare-checkout:live`.** `EXPECTED_CONFIGURATION_NAME=""`, `EXPECTED_PROVIDER_MID=""` → `CONFIGURATION_UNVERIFIED` → 409 on every create. **Owner-only**: both values come from a live Meta/Razorpay read, and `payment_readiness` is written so no constant or env default can make it pass | **CRITICAL** | **YES** | Live `GetFunctionConfiguration`; `payment_readiness.py:236-248` |
| 3 | **Meta payment configuration presence is unmeasured.** `payment_readiness` has a `PAYMENT_CONFIG_MISSING` state whose comment records "the measured state on 2026-09-30" as *zero* configurations on WABA `2094615664435155`. I did not re-measure — the only read path is `GET /wa-business/payment-config/check`, which needs admin auth | **CRITICAL** | **YES** if still zero | Unverified. Named unblock in §8 |
| 4 | **`gift_card_store.redeem()` double-debits** on a retry after `_decrement` succeeds and `_mark_settled` fails; `void()` double-credits by the mirror defect | **HIGH** | NO (gift cards are not provisioned) | Reproduced by the 13:45 reviewer at HEAD; verdict `NEEDS_CHANGES` |
| 5 | **The website Razorpay Standard Checkout has no production caller.** `website_checkout.py` + `integrations/razorpay_orders.py` are tested source; `checkout/handler.py` returns only `PAYMENT_INITIATION_DISABLED` / `PAYMENT_REQUEST_SENT` / `payment_unavailable`. No browser `Razorpay()` anywhere in `src/` | **HIGH** | **YES** for a website purchase (NO for the retained in-chat flow) | `grep` for callers; `grep -rn "checkout.razorpay.com\|new Razorpay" src/` → no matches |
| 6 | **The in-chat vs website architecture decision is still open.** `.kiro/specs/.../requirements.md:5` records "WhatsApp/Razorpay collects payment externally" and "WhatsApp-only receipts"; the task brief asks for website Standard Checkout and a downloadable receipt. `checkout/handler.py:50-57` names this an unresolved **owner decision** and keeps both paths behind one gate | **HIGH** | **YES** — it decides which of 5 or 8a to finish | Owner decision, not an engineering gap |
| 7 | **`initiation.py` and `finalization.py` are dead code.** Committed as `cca83710` precisely because two committed design docs cited them by filename and line. `grep` across `amplify/`, `tests/`, `scripts/` finds **no `import`** of either; every hit is a docstring, a comment, or a test that reads the *source text* (`test_gift_cards_iam_and_table.py:716-719` even `pytest.skip`s if the file is absent). So the finalization path — internal order, Wix write-back, order number — exists but nothing calls it | **HIGH** | **YES** | `grep -rn` for importers; the commit message confirms the docs-before-code ordering |
| 8 | **Coupons and gift cards are DECLARED only.** `wecare-coupons`, `wecare-gift-cards`, `wecare-wix-giftcard-spi` are in `deploy_all_lambdas.py --list` but absent from `ListFunctions`; `CouponsTable` and `GiftCardsTable` absent from `ListTables`; no routes; probes 404 | **MEDIUM** | NO (a purchase does not require a coupon) | 69-function and 82-table enumerations; live 404s |
| 9 | **84 of 114 spec tasks open.** `grep -cE "^\s*- \[ \]"` → **84**; `- [x]` → **30** | **MEDIUM** | Partially — items 1-7 above are the subset that blocks | Re-measured; the "~98 open" figure in the brief is stale |
| 10 | **No receipt route exists.** `customer_receipt.py` is tested source; `test_checkout_package_completeness.py:43` states it is not imported by the handler | **MEDIUM** | NO (a purchase can complete without a downloadable receipt; R9.2 wants one) | — |
| 11 | **An incidental production deploy happened via CI.** Pushing new `lambda_utils/` modules matched the path filter in `.github/workflows/seo-tools-deploy.yml` and replaced `wecare-seo-tools` `$LATEST` (no `live` alias, so `$LATEST` is what the account serves). Now disclosed in `change-authority-matrix.md` as `A3_PRODUCTION via CI` with a post-deploy probe | **MEDIUM** | NO | `wix-coupons-giftcards-20261001/review.json` REV-1, closed by the 13:45 review |
| 12 | **Wix write-back is flag-disabled.** `wix_writeback.is_enabled()` false and no `wixOrderPayload` on any attempt, so `finalization.accept_paid` would stop at `NEEDS_RECONCILIATION` / `WIX_WRITE_CONTRACT_REQUIRED` | **MEDIUM** | NO (an internal paid order still commits first) | `finalization.py:80-83` |
| 13 | **The webhook URL in the handler docstring is dead.** `handler.py:3` names `https://api.wecare.digital/razorpay-webhook`; that host returns 403 and `GetDomainNames` returns zero custom domains | **LOW** | NO | Probe + `GetDomainNames` |
| 14 | **The retired-account regression is a synthetic fixture.** `acc_RETIRED_FIXTURE` replaced the real retired id, so the narrow proof that `acc_HDfub6wOfQybuH` specifically is refused is gone. The general MID-mismatch property is still pinned | **LOW** | NO | `grep`; `test_payment_readiness.py:79-84` |
| 15 | **Four xfails are real pending seams, not disabled tests.** SEAM-G1 (`cart_v2.calculate` refuses `giftCards`), SEAM-G7(a) (`finalization.py` passes `int(attempt['amountPaise'])` to `record_external_payment`, **overstating the provider payment** once a gift card funds part of the total), SEAM-G7(b) (`side_effect_guard.KNOWN_EFFECTS`), SEAM-G14 (`website_checkout` split). G7(a) is a money-correctness defect, latent only because `finalization.py` has no caller | **LOW** now, **HIGH** when item 7 is wired | NO today | `pytest -rx` output quoted in §7 |
| 16 | **Three provenance comments overclaim.** `test_payment_status.py` fixtures still say "the real live payload, copied from a RazorpayWebhookLogTable row" while `account_id` is synthetic; `test_payment_readiness.py:23` attributes history to a string that never existed | **INFORMATIONAL** | NO | Already recorded in `razorpay-account-purge-20261002/review.md` items 4-5; affects no assertion |

### Which prior-audit findings are now CLOSED

`.agents/tasks/checkout-audit-2026-10-01/findings.md` was measured against a **different checkout** (`/projects/sandbox/wecare-digital` at `f7304eba`), so none of its claims is current evidence. Re-measured against this tree:

| Prior finding | Now |
|---|---|
| R1/C1 — gate falls through to the legacy verifier on paid-but-blocked outcomes | **CLOSED** — branches on `outcome_kind == UNKNOWN_REFERENCE` (`handler.py:1141`) |
| N2 — wallet top-up credits from an unverified body, no intent, no idempotency | **CLOSED** — stored intent, WABA check, amount check, conditional `claim_topup_credit` |
| R3/N3 — quarantine is one log line | **CLOSED** — `resolve_capture_quarantine`, `capture_quarantine_persist_failed`, `scripts/reconcile_captures.py` |
| Task 2.2 — `_get_or_create_wd_order_number` returns an unstored number | **CLOSED** — reserves before returning, raises on storage failure |
| `_money_amount` passes junk through as `str(value)` | **CLOSED** — returns `''`, pinned by four assertions |
| Group 2 — the 121481-paise calculator and snapshot hash | **CLOSED** — `checkout_pricing.py` + `test_checkout_pricing.py` 346-test group passes |
| Group 3 — no website Razorpay checkout exists in any form | **PARTIALLY OPEN** — `website_checkout.py` now exists and is tested, but has no production caller and no browser half (item 5) |
| `CommerceKeys` table absent | **NOT A FINDING** — `COMMERCE_KEYS_TABLE` resolves to `stack-wecare-digital-WixOrderIds`, `ACTIVE` |
| R2 — legacy verifier has no payment-to-invoice binding or one-time claim | **LIKELY CLOSED, NOT FULLY VERIFIED** — `claim_legacy_invoice_payment` now shares the `PROVIDERPAYMENT#` namespace and the handler emits `legacy_invoice_binding_mismatch` / `legacy_invoice_payment_already_claimed` / `legacy_invoice_claim_released_unsettled`. I read the symbols but did not trace every branch |
| Spec contradicts the handoff on in-chat vs website | **STILL OPEN** — item 6 |

---

## 7. Test results — exact commands, exact counts

Interpreter is `.venv/bin/python`; plain `python` is not on `PATH`.

```
$ git rev-parse HEAD
2ef4049d5f360a77518c716e5f3974b0d818f65e

$ .venv/bin/python -m pytest -q
6788 passed, 1 skipped, 7 xfailed in 57.63s
```

That figure matches the 13:45 reviewer's independent run at the same HEAD (`6788 passed, 1 skipped, 7 xfailed in 55.32s`) exactly, which is a useful cross-check rather than a carried-forward claim.

Targeted groups, each run here:

```
$ .venv/bin/python -m pytest -q tests/test_payment_vocabulary_at_decision_points.py tests/test_payment_status.py tests/test_payment_readiness.py
167 passed in 0.72s

$ .venv/bin/python -m pytest -q tests/test_cart_v2.py tests/test_checkout_cart_v2_authority.py tests/test_checkout_catalog_contract.py \
    tests/test_checkout_gate_contract.py tests/test_checkout_handler.py tests/test_checkout_package_completeness.py \
    tests/test_checkout_pricing.py tests/test_checkout_release_check.py tests/test_coupon_logging_and_vocabulary.py \
    tests/test_coupon_reconciliation.py tests/test_coupon_store.py tests/test_coupons_iam_and_table.py \
    tests/test_coupons_routes_and_registry.py tests/test_customer_receipt.py tests/test_customer_session.py \
    tests/test_customer_session_endpoint.py
346 passed, 2 xfailed in 1.79s

$ .venv/bin/python -m pytest -q tests/test_gift_card_amounts_and_gst.py tests/test_gift_card_spi_auth.py \
    tests/test_gift_card_spi_contract.py tests/test_gift_card_store.py tests/test_gift_card_two_leg_finalization.py \
    tests/test_gift_cards_iam_and_table.py tests/test_order_creation.py tests/test_order_keys.py \
    tests/test_order_lookup_internal_contract.py tests/test_partner_razorpay_canonical_secret.py \
    tests/test_payment_attempt.py tests/test_payment_reconciliation_safety.py tests/test_payments.py \
    tests/test_razorpay_binding.py tests/test_razorpay_webhook_captured_gating.py \
    tests/test_razorpay_webhook_order_creation.py tests/test_redemption.py \
    tests/test_provision_checkout_contract.py tests/test_receipt_links.py tests/test_wix_writeback.py
648 passed, 5 xfailed in 1.85s
```

Per file:

```
test_payment_vocabulary_at_decision_points     56 passed in 0.39s
test_payment_status                            59 passed in 0.36s
test_payment_readiness                         52 passed in 0.14s
test_razorpay_binding                          24 passed in 0.13s
test_razorpay_webhook_captured_gating          13 passed in 0.18s
test_razorpay_webhook_order_creation           12 passed in 0.14s
test_order_keys                                81 passed in 0.61s
test_order_creation                            50 passed in 0.14s
test_checkout_handler                          13 passed in 0.12s
test_checkout_gate_contract                     5 passed in 0.03s
test_provision_checkout_contract               58 passed in 0.21s
test_coupon_store                              70 passed in 0.16s
test_gift_card_store                           56 passed in 0.17s
test_redemption                                31 passed in 0.13s
```

Zero failures and zero unexpected passes anywhere. The 7 xfails are deliberate, named seam markers rather than disabled tests — `pytest -rx` reports:

```
XFAIL test_the_convenience_fee_is_computed_on_the_full_collection_total  - SEAM-G1: cart_v2.calculate refuses giftCards ...
XFAIL test_only_one_gift_card_is_accepted                               - SEAM-G1 ...
XFAIL test_the_website_checkout_split_binds_the_charged_amount_...      - SEAM-G14: website_checkout.py is owned by the website-checkout workstream ...
XFAIL test_no_recorded_payment_exceeds_the_verified_capture_for_its_transaction_id
                                                                        - SEAM-G7(a): finalization.py passes int(attempt['amountPaise'])
                                                                          to record_external_payment today, which OVERSTATES the provider
                                                                          payment once a gift card funds part of the total ...
XFAIL test_the_gift_card_tender_claims_a_different_effect_key_...       - SEAM-G7(b): side_effect_guard.KNOWN_EFFECTS ...
```

**A test I did not run and why:** `scripts/verify_razorpay_secret_path.py` — it calls `get_secret_value` (§4.1). **TypeScript/vitest were not run**; this investigation is scoped to the Python commerce path and the live account, and the frontend claims above rest on `grep` plus the committed test names, not on a vitest run.

---

## 8. What cannot be verified without owner action

Each with the one specific unblock.

| # | Cannot verify | Named unblock |
|---|---|---|
| 1 | That `wecare/razorpay/api` actually holds populated `key_id` and `key_secret` | **Owner runs `python scripts/verify_razorpay_secret_path.py` themselves** and reports only the `FIX CONFIRMED` line. I may not call `get_secret_value`. (The script's own output is already fingerprint-only — no prefix, no value.) |
| 2 | Whether WABA `2094615664435155` currently reports a payment configuration, and under which name and MID | Owner reads WhatsApp Manager, or calls `GET /wa-business/payment-config/check` with an admin token, and supplies `EXPECTED_CONFIGURATION_NAME`. No application code may create a configuration |
| 3 | That one OTP round trip completes through to a live session | Owner authorises a test send to the nominated QA recipient **+918100640044** — **not authorised by this task**. Prerequisite: `fix/otp-confirm` merged, deployed, and each `live` alias moved |
| 4 | That a real Razorpay capture reconciles into exactly one paid order | A live payment. Prohibited here outright — no capture, no test-mode charge |
| 5 | That the `webhook_secret` in Secrets Manager matches what the Razorpay dashboard signs with | Owner compares the Razorpay dashboard webhook secret against `wecare/razorpay-webhook` out of band. Note `LastChangedDate 2026-09-30T22:58:35Z` on that secret — if the dashboard was not updated in the same change, every real delivery would 401 and nothing in this report would have detected it |
| 6 | That live Lambda bytes equal `HEAD` | `python scripts/deploy_all_lambdas.py --dry-run` or `provision_checkout.py --verify` — both are deploy scripts, forbidden by this brief |
| 7 | Whether `PAYMENT_INITIATION_DISABLED` should become the website or the in-chat path | Owner settles item 6 in §6. The spec and the task brief disagree and both are dated 2026-10-01 |

---

## 9. What I could not determine

Stated explicitly, because an honest unknown is worth more than a confident invention.

1. **Whether a signed Razorpay webhook has ever been processed successfully.** `razorpay_webhook_received` saturates the 1000-event `FilterLogEvents` page cap over any window long enough to matter, and two attempts to count the success-path event names across a 22-day window timed out in the MCP sandbox after ~6 minutes. What I *can* state from a completed narrow query: `order_paid` = **0** and `payment_captured` = **0** events between 2026-09-26 and 2026-10-02T08:05Z. Combined with six `ItemCount: 0` tables, no order has been created. Whether an *earlier* capture succeeded and was later cleared, I cannot say.
2. **Which of the 154 `RazorpayWebhookLogTable` rows are real deliveries versus probes.** Deciding that needs a `Scan` of a table holding live payment payloads, which I chose not to do for a diagnostic question.
3. **Whether live Lambda bytes match `HEAD`** — see §8 item 6. The timestamps make "behind `stack`" the strong inference, not a measurement.
4. **R2's full closure.** `claim_legacy_invoice_payment` and the three new `legacy_invoice_*` log events strongly indicate the binding and one-time claim now exist. I read the symbol names and the handler's call sites; I did not trace every branch of `_verified_legacy_invoice` (`handler.py:575-737`) to prove one payment can no longer settle two invoices.
5. **Whether `wecare-checkout:live` v4 would reach step 7 if readiness were satisfied.** It has never executed past the auth gate — the 15 recent log events carry no application line at all — so steps 7 onward are proven by unit tests, never by a live invocation.
6. **The state of `.worktrees/login-fix-20261002`** (branch `login-fix-20261002`, at the same `2ef4049d`). I did not diff it. A fourth concurrent worktree may hold further sign-in work, and `wix-migration`, `get-hero-auth-ui-2026-10-02` and `customer-experience-merge-2026-10-02` task directories were not read.
7. **Frontend behaviour.** No vitest run and no browser measurement. Every claim about `src/` rests on reading source and `grep`.

### Concurrency caveat

Four warm sessions were live during this investigation. `gift_card_store.py` and `tests/test_gift_card_store.py` — named in the brief as being actively edited — were **committed** at `HEAD 2ef4049d` by the time I measured, and the only untracked files were two review documents. The full suite is green, so nothing here is a half-finished edit misreported as a defect. The `redeem()` double-debit in §5.3 is the exception worth naming precisely: it is **not** a broken edit, it is a defect the reviewer reproduced by executing the committed code, and the fix is not yet written.

---

## 10. Recommendations — ordered, nothing implemented

1. **Merge `fix/otp-confirm` to `stack`, deploy it, and move each `live` alias.** Without it no customer can hold a session, so every other fix is untestable end to end. 13 files, +642/-34, already reviewed in its own findings document.
2. **Get the two readiness values from the owner** and set `EXPECTED_CONFIGURATION_NAME` / `EXPECTED_PROVIDER_MID` on `wecare-checkout`. Confirm the Meta configuration exists first — if WABA `2094615664435155` still reports zero, that is owner-administrative work in WhatsApp Manager and no code change helps.
3. **Settle item 6 in §6 — in-chat or website — before writing more checkout code.** Seven of the sixteen outstanding items trace back to this one undecided question, and `website_checkout.py` plus `initiation.py`/`finalization.py` are already ~35 KB of tested-but-uncalled code accruing against a decision nobody has made.
4. **Close the `redeem()` / `void()` atomicity defect with one `TransactWriteItems`** before `wecare-gift-cards` or `GiftCardsTable` is provisioned. Both items are in the same table; no role gains an action. Closing it after provisioning means closing it with real balances in flight.
5. **Verify the Razorpay dashboard webhook secret against `wecare/razorpay-webhook`.** That secret changed on 2026-09-30T22:58Z. A mismatch would 401 every real delivery and produce exactly the log picture this account shows — the one failure mode no test in this repo can catch.
6. **Wire `finalization.accept_paid` or delete it.** Committed code with no caller, cited by two design documents, is the documentation pointing at the implementation rather than the other way round. SEAM-G7(a) — `int(attempt['amountPaise'])` overstating the provider payment once a gift card part-funds the total — must be fixed *in the same change*, not after it goes live.
7. **Fix the dead webhook URL in `razorpay-webhook/handler.py:3`.** A one-line comment change that stops someone configuring a 403 host in the Razorpay dashboard.

---

*Prepared read-only. No AWS mutation, no git write, no deploy, no payment, no message, no secret value. Every number above is quoted from a command I ran; where I did not run one, the row says so.*
