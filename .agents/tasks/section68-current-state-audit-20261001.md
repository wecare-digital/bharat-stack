# Section 68 — current implementation audit (READ-ONLY)

**Produced** 2026-10-01, from live reads against AWS account `775261844268` / `us-east-1` and from
source at the commit named below.
**Changes made: NONE.** No source edit, no commit, no stage, no AWS mutation, no deploy, no
provider/Meta/Razorpay/Wix mutation. No secret value was read: every Secrets Manager observation
below is `ListSecrets`/`DescribeSecret` metadata only, and no credential appears in this file or in
any command that produced it.

---

## Summary answer, first

1. **The plan's premise is out of date in the most important place.** Section 8 of the
   implementation prompt states "the current WhatsApp/Razorpay payment path does not create the new
   checkout order". At HEAD `c082d586` it **does**: `razorpay-webhook._create_order_for_captured_payment`
   calls `lambda_utils.ecommerce.order_creation.reconcile_payment`, which verifies the capture
   against Razorpay's API and claims exactly one order identity. Likewise Section 34
   (`split allocate_order_identity`) and Section 35 (`remove reference mutation`) are **already
   done**: `allocate_order_identity` no longer exists, and `_sanitize_reference_id` raises
   `ReferenceIdTooLong` instead of truncating.

2. **What is genuinely missing is deployment and materialization, not design.** Three of the four
   new front-door functions exist in source and in the deploy map but **do not exist in AWS**:
   `wecare-checkout`, `wecare-customer-registration`, `wecare-email-verification`
   (`ResourceNotFoundException` on `GetFunctionConfiguration`). There are **no live API routes** for
   checkout, cart or registration. Two backing resources the code defaults to are also absent:
   DynamoDB `stack-wecare-digital-CustomersTable` and secret `wecare/otp/pepper`.

3. **`reconcile_payment` creates order *identity*, not an OrderTable row.** It writes
   `PROVIDERPAYMENT#`, `PAYMENTATTEMPT#` and `ORDERNO#` claim rows into the commerce-keys table
   (physically `stack-wecare-digital-WixOrderIds`) and returns `orderId` + `orderNumber`. Nothing
   on the paid path writes a business order row into `stack-wecare-digital-OrderTable`. That is the
   real remaining gap behind "paid transaction → commerce order", and `docs/execution/headless-checkout-20261001.md`
   says the same thing ("Paid-order code still needs the complete commerce-order materialization").

4. **Three concrete wiring defects found, all fail-closed but all blocking:**
   - `ecommerce/checkout` asks for readiness at path `/wa-business/payment-config/raw`, which
     `whatsapp-business-api` does not implement; it falls through to the `elif '/payment-config' in path`
     branch and returns `400 phoneId required`. Readiness can therefore never evaluate `PAYMENT_READY`.
   - `ecommerce/checkout` prices from Wix **Checkout V1** (`/ecom/v1/checkouts`) while the
     owner-selected model at HEAD is **Cart V2** (`cart_v2.py` / `customer_cart.py`). Two different
     price authorities.
   - Live `wecare-whatsapp-business-api` env still carries the values the repo has since classified
     as stale: `RAZORPAY_MID=[retired Razorpay account]` and `RAZORPAY_UPI_ID=wecaredigital83.rzp@icici`.
     `config/lambda-env-manifest.json` holds the corrected pair but has not been pushed live.
     A MID disagreement is exactly what `payment_readiness.RAZORPAY_MID_MISMATCH` blocks on.

5. **The repo contains two mutually contradictory 2026-09-30 claims about payment configurations**,
   and neither was re-verified here. `payment_readiness.py` records a live read returning
   `HTTP 200, ZERO configurations`; `.kiro/specs/whatsapp-wix-commerce/tasks.md` records the owner
   restoring four Active configurations. Both are dated the same day. **Item 12 is UNVERIFIED** —
   resolving it needs a live Meta read, which cannot be done here without a token.

6. **A live send path today names a template the repo's own live read says does not exist.**
   `wecare-secure-files` has `WA_PAY_TEMPLATE=wecare_pay` set in production, while
   `payment_readiness.py` records that WABA `2094615664435155` held exactly one template,
   `wecare_otp`, on 2026-09-30. Either the template read is stale or paid secure-file delivery is
   failing at Meta. **UNVERIFIED** — needs a live template read.

---

## Evidence, item by item

### 1. Git HEAD — KNOWN

```
git -C /Users/wecaredigital/wecare-store rev-parse HEAD        c082d5867240b819c6c26af4ab668575440868f9
git -C /Users/wecaredigital/wecare-store rev-parse origin/stack c082d5867240b819c6c26af4ab668575440868f9
```

Local and `origin/stack` agree. Branch `stack`, tracking `origin/stack`. Subject:
*"Build phone-owned Cart V2 backend with exact paise and gated payment writeback"*.

`git status --short` at audit time (not mine, and untouched):

```
 M .kiro/steering/META-BETA-REQUEST-EMAIL.md
?? scripts/retired_url_equity.py
```

Both left exactly as found. Under `multi-session-parallel-agents` rule 4 these are treated as
another session's work.

Recent history relevant to this audit (`git log --format=oneline -15`):

| Commit | Subject |
|---|---|
| `c082d586` | Build phone-owned Cart V2 backend with exact paise and gated payment writeback |
| `394d8e39` | Add the headless checkout front door and hosted status UI, consuming the payment core |
| `c06fe40d` | Reconcile the WhatsApp+Wix headless spec to Wix Cart V2, and probe it live |
| `9b868615` | Add the customer registration front door: WhatsApp OTP, then admin-provision the Cognito login |
| `854767f8` | Retire the stale @icici VPA and [retired Razorpay account] MID from the dashboard |
| `97027c53` | Pin authoritative Razorpay MID + UPI VPA from owner-confirmed live Meta config |

### 2. AWS account and region — KNOWN

`aws sts get-caller-identity`:

```
Account  775261844268
Arn      arn:aws:iam::775261844268:user/wecare-admin
```

`aws configure get region` → `us-east-1`. `AWS_PROFILE=wecare-prod`. No `aws login` /
`aws sso login` was run.

### 3. Live Lambda function count — KNOWN: **66**

`lambda ListFunctions`, fully paginated, `len(Functions) == 66`.

**Measurement caveat worth recording:** a single un-paginated CLI call
(`aws lambda list-functions --query 'length(Functions)' --no-paginate`) returned **50**. Any count
that does not state it paginated is not trustworthy here.

Runtimes: `python3.12` on all zip functions; one `PackageType=Image` (`wecare-docs-scraper`).

**Absent from the fleet, and expected by source:** `wecare-checkout`,
`wecare-customer-registration`, `wecare-email-verification` — all three return
`ResourceNotFoundException`. All three are declared in `scripts/deploy_all_lambdas.py::SPECS`
(`ecommerce/checkout`, `auth/customer-registration`, `auth/email-verification`) with
`provisioned_by` scripts (`provision_checkout.py`, `provision_customer_registration.py`,
`provision_email_verification.py`), so first creation is owned by those scripts, not by the
deploy-all path.

### 4. HTTP API route count — KNOWN: **359**

`apigatewayv2 GetRoutes --api-id zllr9lrg7j` → 359 items, `NextToken` absent. API name
`wecare-digital-api`, protocol `HTTP`, one stage `prod` with `AutoDeploy=true`,
`ThrottlingRateLimit=100`, `ThrottlingBurstLimit=200`. 66 integrations.

**359 confirms the plan's figure and retires the `361` figure** still quoted in
`.kiro/steering/00-current-owner-overrides.md`.

### 5. API authorization posture — KNOWN: **359 / 359 `AuthorizationType=NONE`**

`GetAuthorizers` → **0** authorizers. No route carries an `AuthorizerId`.

Interpretation, per `00-current-owner-overrides.md`: gateway configuration alone cannot distinguish
an intentionally public signed webhook from an accidentally public API. Handler-level
authentication does exist and is test-pinned — `lambda_utils.customer_auth.require_customer`
(issuer-pinned to the customer pool), `middleware`/`require_auth`, provider HMAC verification,
`lambda_utils/rate_limit.py`, and `tests/test_route_auth_enforcement.py` /
`tests/test_public_surface_role_permissions.py` / `tests/test_public_webhook_auth.py`.

Commerce-relevant routes live today (all `NONE` at the gateway):

| Route | Target |
|---|---|
| `GET /payments`, `GET /payments/{paymentId}` | `wecare-payments-read:live` |
| `GET/POST/PATCH /wa-business/orders...` | `wecare-whatsapp-business-api:live` |
| `GET /wa-business/payment-config/check` | `wecare-whatsapp-business-api:live` |
| `POST /invoices/from-payment`, `POST /invoices/{invoiceId}/send-payment-link` | `wecare-invoice-engine:live` |
| `POST /secure-files/{fileId}/order` | `wecare-secure-files:live` |
| `POST /partners/billing/topup-order` | `wecare-partner-onboarding:live` |

**No route exists for `/checkout`, `/wix-store/cart`, or customer registration.** WAF is absent in
both scopes by owner decision (2026-09-28), so there is no per-IP layer in front of these when they
do land — which is why Section 6's HTTP-front-door throttling is load-bearing rather than optional.

### 6. Customer Cognito pool `us-east-1_46ULYuukt` — KNOWN

`cognito-idp DescribeUserPool`:

| Field | Live value |
|---|---|
| `Name` | `WECARE.DIGITAL-CUSTOMERS` |
| `AdminCreateUserConfig.AllowAdminCreateUserOnly` | **`true`** |
| `DeletionProtection` | `ACTIVE` |
| `MfaConfiguration` | `OFF` |
| `EstimatedNumberOfUsers` | **1** |
| `UsernameAttributes` | `["phone_number"]` |
| Custom attributes | `custom:partner_waba_id` |

All four match the plan's Section 4 exactly. Public self-signup is closed.

**One discrepancy to flag against source, not against the plan:**
`auth/customer-registration/handler.py` stamps `custom:customer_id` on the provisioned user
(handler docstring, "stamping `custom:customer_id`"), but the live pool's only custom attribute is
`custom:partner_waba_id`. A `custom:customer_id` schema attribute is **not present on the pool**.
Cognito schema attributes cannot be added by `UpdateUserPool` after creation, so this needs
checking before registration is provisioned — and per `aws-agent-rules.md`, `UpdateUserPool` is a
full replace and must only ever be driven through `scripts/cognito_pool_safe_update.py`.

### 7. CUSTOM_AUTH triggers — KNOWN, all three correct

From the same `DescribeUserPool`, `LambdaConfig`:

```
DefineAuthChallenge          arn:aws:lambda:us-east-1:775261844268:function:wecare-customer-whatsapp-auth:live
CreateAuthChallenge          arn:aws:lambda:us-east-1:775261844268:function:wecare-customer-whatsapp-auth:live
VerifyAuthChallengeResponse  arn:aws:lambda:us-east-1:775261844268:function:wecare-customer-whatsapp-auth:live
```

All three present and pointing at the `live` alias — so the 2026-09-28 `UpdateUserPool` incident
recorded in `aws-agent-rules.md` is fully recovered. `wecare-customer-whatsapp-auth` live alias is
at version `10`; `OTP_TEMPLATE_NAME=wecare_otp`, `META_WABA_ID=2094615664435155`,
`META_PHONE_NUMBER_ID=1016149501586345`.

### 8. SES state — KNOWN, healthy

`sesv2 GetEmailIdentity` for `one@wecare.digital`:

| Field | Value |
|---|---|
| `IdentityType` | `EMAIL_ADDRESS` |
| `VerifiedForSendingStatus` | **`true`** |
| `VerificationStatus` | `SUCCESS` |
| `DkimAttributes.Status` | **`SUCCESS`**, `SigningEnabled: true`, RSA_2048 |

`sesv2 GetEmailIdentity` for the domain `wecare.digital`: `VerifiedForSendingStatus true`,
DKIM `SUCCESS`, `ConfigurationSetName: wecare-digital`, last successful DNS check
2026-09-30T22:08:40Z.

`sesv2 GetConfigurationSet --configuration-set-name wecare-digital`:

| Field | Value |
|---|---|
| `DeliveryOptions.TlsPolicy` | **`REQUIRE`** |
| `DeliveryOptions.SendingPoolName` | `ses-shared-pool` |
| `ReputationOptions.ReputationMetricsEnabled` | **`true`** |
| `SendingOptions.SendingEnabled` | `true` |
| `SuppressionOptions.SuppressedReasons` | **`["BOUNCE", "COMPLAINT"]`** |
| `VdmOptions` | engagement metrics ENABLED, optimized shared delivery ENABLED |

`ListConfigurationSets` → exactly one set, `wecare-digital`. `GetAccount`:
`ProductionAccessEnabled true`, `SendingEnabled true`, `EnforcementStatus HEALTHY`,
quota 50,000/24h at 14/s, `SentLast24Hours 0.0`.

Every value in the plan's Section 9 is confirmed. Email verification is not blocked by Meta.
Note the DKIM token anomaly recorded in `email-auth-dns.md` still stands: SES lists three tokens,
AWS publishes a key for only `v5w4wexbfyum54omlfe7l6ayada7j2nq`. SES `Status: SUCCESS` because one
published key is sufficient; which selector SES actually signs with remains **UNVERIFIED**.

### 9. DynamoDB counts — KNOWN, all four zero

`dynamodb Scan` with `Select=COUNT, ConsistentRead=true` (read-only), cross-checked against
`DescribeTable.ItemCount`:

| Table | Scan COUNT | DescribeTable ItemCount | Key | GSIs | TTL |
|---|---:|---:|---|---|---|
| `stack-wecare-digital-PaymentsTable` | **0** | 0 | `id` | `orderId-index`, `paymentId-index` | — |
| `stack-wecare-digital-InvoicesTable` | **0** | 0 | `invoiceId` | `referenceId-index`, `contactId-index` | — |
| `stack-wecare-digital-OrderTable` | **0** | 0 | `orderId` | `shortId`, `customerPhone`, `orderStatus`, `source` | **DISABLED** |
| `stack-wecare-digital-WixOrderIds` | **0** | 0 | `orderId` | none | **DISABLED** |

The plan's Section 7 is confirmed: **no live-data migration is required.**

Adjacent counts that matter and are *not* zero:

| Table | Count | Why it matters |
|---|---:|---|
| `stack-wecare-digital-RazorpayWebhookLogTable` | **154** | Razorpay webhooks *have* fired. TTL **ENABLED** on `expiresAt`, which explains the drop from the 607 recorded in `payment_status.py` on 2026-09-23 — history is expiring, so this number is a floor, not a total. |
| `stack-wecare-digital-WebhookDedup` | 230 | TTL ENABLED on `ttl`; the dedup **lease**, as designed. |
| `stack-wecare-digital-PaymentAttemptsTable` | **0** | Provisioned, TTL **DISABLED** (correct per `payment_attempt.py`), never written — consistent with `wecare-checkout` not existing. |
| `stack-wecare-digital-ContactsTable` | 19 | — |
| `stack-wecare-digital-InvoiceSequenceTable` | 0 | No GST invoice number has been issued. |

`stack-wecare-digital-CustomersTable` — **DOES NOT EXIST** (`ResourceNotFoundException`). It is the
default `CUSTOMERS_TABLE` in `auth/customer-registration/handler.py`. 80 tables total in the
account; there is no `CommerceKeys` table either, and per `order_keys.commerce_keys_table_name()`
that is correct by design — it defaults to `WixOrderIds`.

### 10. WABA / sender state for `+919330994400` — SOURCE + CONFIG ONLY

Per the brief, no Meta Graph call was made, because every Graph read needs the system-user token
and a token must never reach a command line. **Live Meta sender health is UNVERIFIED here.**

What *is* verifiable:

| Identity | Value | Source |
|---|---|---|
| WABA 1 | `2094615664435155` | `whatsapp-business-api/handler.py:88` (`WABA1_ID` default); manifest `wecare-customer-whatsapp-auth.META_WABA_ID`, `wecare-secure-files.META_WABA_ID`, `PAYMENT_WABA_ID` |
| Phone 1 id | `1016149501586345` | `handler.py:90` (`PHONE1_META_ID`); live env on `wecare-customer-whatsapp-auth` and `wecare-secure-files` |
| WABA 2 | `2513394156072604` | `handler.py:89` |
| Phone 2 id | `1055232054343117` | `handler.py:91` |

**The stale "Phone 1 disconnected" claim is already gone from executable code.** A tree-wide grep
for `Phone 1 DISCONNECTED` / `Phone 1 is disconnected` across `amplify/**`, `src/**`, `config/**`
and `scripts/**` returns **zero** matches. `docs/compatibility.md:44` records the correction
explicitly: the `if False: # Phone 1 DISCONNECTED` comment "was **stale and wrong**". The only
surviving mention is `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:1510`, which is
the plan's own stale-documentation checklist — i.e. the item is already satisfied.

No mutation, deregistration or migration of any number was attempted. That is a standing refusal.

### 11. Live WhatsApp template inventory — **UNVERIFIED**

A live template read requires `GET /{waba}/message_templates` with the system-user token. Not done:
the token would have to enter a shell invocation, which `secret-handling` forbids outright, and the
brief instructs marking this UNVERIFIED rather than working around it.

What the repo claims, and where the claims disagree:

| Claim | Location | Status |
|---|---|---|
| WABA `2094615664435155` holds exactly one template, `wecare_otp`, and **no `wecare_pay`**, measured 2026-09-30 | `lambda_utils/payment_readiness.py:415` | most recent dated live read in the repo |
| `wecare_pay` is APPROVED and in use | `scripts/provision_secure_files_api.py:268`, `core/secure-files/whatsapp_delivery.py:6`, `payments/invoice-engine/handler.py:2217`, `src/api/client.ts:2221`, `src/pages/get.tsx:172` | contradicted by the above |
| `WA_PAY_TEMPLATE = wecare_pay` **live in production** | `GetFunctionConfiguration wecare-secure-files` | live config, observed today |

`wecare_otp` is corroborated as the OTP template by live env on `wecare-customer-whatsapp-auth`
(`OTP_TEMPLATE_NAME=wecare_otp`). The plan's Section 11 (`wecare_otp` APPROVED / AUTHENTICATION /
`en`) is consistent with source and env but was **not** re-read from Meta.

**Consequence to flag:** if the 2026-09-30 reading is current, the live paid secure-file delivery
path is naming an absent template and will fail at Meta. This needs a live template read before
anything is built on `wecare_pay`. Nothing here attempted to create or submit a template.

### 12. Live payment-config inventory — **UNVERIFIED**, and the repo contradicts itself

Same token constraint. Additionally, `/wa-business/payment-config/check` is gated by handler-level
auth (`docs/compatibility.md:48` records it returning `No authorization token provided`), and
invoking a production Lambda is outside "read-only AWS APIs", so it was not invoked.

Two contradictory claims, both dated 2026-09-30, both in the repo:

| Claim | Location |
|---|---|
| `GET /2094615664435155/payment_configurations` → **HTTP 200, ZERO configurations** | `lambda_utils/payment_readiness.py`, module docstring — presented as the live read that motivated the whole module |
| Four configurations **Active**: `WECAREDIGITAL` (razorpay, MID `acc_TTFSyolquKEZEy`) and `WECAREUPI` (`wecaredigitalbh511413.rzp@rxairtel`) on **both** WABAs, MCC `7392`, purpose `03` | `.kiro/specs/whatsapp-wix-commerce/tasks.md` — "restored by owner", recorded from a dashboard readout, explicitly **not re-probed** |

What the code declares locally (and correctly labels as *not* provider state) —
`whatsapp-business-api/handler.py:3169`:

```python
_DECLARED_CONFIGS = [
    {'name': 'WECAREDIGITAL', 'status': 'local_only', 'type': 'payment_gateway',
     'gateway': 'razorpay', 'mid': _RAZORPAY_MID},
    {'name': 'WECAREUPI', 'status': 'local_only', 'type': 'upi',
     'gateway': 'razorpay', 'upiId': _RAZORPAY_UPI_ID},
]
```

`_check_payment_gateway` sets `canReceivePayments = (status == 'active')` for Meta-reported configs
and hard-codes `canReceivePayments: False` with `note: 'Config exists locally but not found in Meta
API'` for local-only ones, then reports `activeConfigs` as the count of the former. So the plan's
Section 15 observation (`local_only`, `canReceivePayments false`, `activeConfigs 0`) is exactly what
that route emits **when Meta returns nothing** — it is a faithful rendering of an empty Meta read,
not a bug. There are deliberately no hardcoded MID/VPA fallbacks (`handler.py:3163`), so an unset
env yields `CONFIGURATION_UNVERIFIED` and blocks, which is the correct fail-closed direction.

`payment_readiness.py` states no name in a file will ever produce readiness. That holds:
`BLOCKING_STATES` is an explicit enumeration rather than `!= PAYMENT_READY`, so a new state cannot
become permissive by omission.

**Required live read to close this item:** one `payment_readiness.evaluate()` run, or one
`GET /{waba}/payment_configurations`, executed where the token stays out of argv.

### 13. Razorpay runtime evidence — KNOWN

`GetFunctionConfiguration wecare-whatsapp-business-api`, non-secret config keys only:

```
RAZORPAY_MID      [retired Razorpay account]
RAZORPAY_UPI_ID   wecaredigital83.rzp@icici
PAYMENT_WABA_ID   2094615664435155
```

`config/lambda-env-manifest.json:466-467`:

```
RAZORPAY_MID      acc_TTFSyolquKEZEy
RAZORPAY_UPI_ID   wecaredigitalbh511413.rzp@rxairtel
```

**Live env and the manifest disagree on both values.** `tasks.md` explains why: the manifest was
corrected and "is **not yet pushed live** — it rides with the credential-load step."

Razorpay secrets, metadata only (`DescribeSecret`, no value read):

| Secret | Stages | Versions | Last changed | Last accessed |
|---|---|---:|---|---|
| `wecare/razorpay/api` | `AWSCURRENT`, `AWSPREVIOUS` | 2 | 2026-09-19 | 2026-09-30 |
| `wecare/razorpay-webhook` | `AWSCURRENT` | 1 | 2026-07-02 | 2026-09-30 |

Both are live and being read. `wecare/razorpay/api` is referenced by name as
`RAZORPAY_SECRET_ID=wecare/razorpay/api` on `wecare-secure-files` and in the manifest, matching
`whatsapp-payments-india-reference.md`. **No rotation was performed or requested** — rotation is a
standing `MANUAL_OWNER_ACTION`.

Also live: `wecare/wix/headless-api-key` now has **`AWSCURRENT`, version count 1**, last changed
2026-09-26, last accessed 2026-09-30. `tasks.md` Phase 0.2 records it as `versionCount: 0` with no
`AWSCURRENT`, and states "Phases 6 onward are blocked on R0 — the Wix credential does not exist in
AWS". **That blocker is stale; the credential now exists.** `wecare-wix-store` carries
`WIX_API_KEY_SECRET=wecare/wix/headless-api-key` and `WIX_SITE_ID=fcd82f0c-9572-49c7-acfb-88fb05042ece`.

31 secrets total; 5 in scheduled-deletion state (`wecare/airtel-iq`, `wecare/airtel/c2c`,
`wecare/airtel/obd`, `wecare/airtel/sms`, `wecare/sinch/sms`) — all prohibited providers, left alone.
`wecare/otp/pepper` — **DOES NOT EXIST**, and it is the default `OTP_PEPPER_SECRET_ID` for the
registration front door.

### 14. MID conflicts — classified

| Occurrence | File:line | Class |
|---|---|---|
| `[retired Razorpay account]` | **live Lambda env** `wecare-whatsapp-business-api.RAZORPAY_MID` | **CURRENT CONFIG (live)** — and classified STALE by the repo |
| `acc_TTFSyolquKEZEy` | `config/lambda-env-manifest.json:467` | **CURRENT CONFIG (declared, not deployed)** |
| `acc_TTFSyolquKEZEy` | `tests/test_payment_readiness.py:25` — `MID = 'acc_TTFSyolquKEZEy'`, "Authoritative as of 2026-09-30 (owner-confirmed)" | **test-pinned expectation** |
| `[retired Razorpay account]` | `tests/test_payment_readiness.py:79-84` — used as the *mismatch* fixture asserting `RAZORPAY_MID_MISMATCH` | **test-pinned as stale** |
| both | `lambda_utils/payment_readiness.py:22-33` | **current prose, explicitly self-correcting** — records that the earlier reasoning was wrong and the owner reversed it |
| both | `whatsapp-business-api/handler.py:3163-3167` | **current prose** explaining why there are no hardcoded fallbacks |
| `acc_TTFSyolquKEZEy` | `.kiro/specs/.../tasks.md:24,26,34` | **current claim**, from an owner dashboard readout, not re-probed |
| `acc_TTFSyolquKEZEy` | `bw-crm.md:212,1164`; `docs/compatibility.md:46,81` | **HISTORICAL PROSE** — `compatibility.md:81` still weights it "weak — no live artefact", which the 2026-09-30 owner confirmation reversed |
| `[retired Razorpay account]` | `docs/compatibility.md:80` "strong — this is the account that talks to us" | **HISTORICAL PROSE, now superseded** |
| both | `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:534-552` | the plan's own statement of the conflict |

**Resolution state:** source, tests and manifest agree on `acc_TTFSyolquKEZEy`. Live env does not.
`docs/compatibility.md` still carries the reversed evidence weighting and is the main stale-prose
site remaining. **The authoritative value is still provider-readback-pending** (item 20-D): the
owner's dashboard readout is the only evidence, and `payment_readiness` deliberately refuses to
pick a winner from a file.

### 15. VPA conflicts — classified

| Occurrence | File:line | Class |
|---|---|---|
| `wecaredigital83.rzp@icici` | **live Lambda env** `wecare-whatsapp-business-api.RAZORPAY_UPI_ID` | **CURRENT CONFIG (live)** — classified STALE by the repo |
| `wecaredigitalbh511413.rzp@rxairtel` | `config/lambda-env-manifest.json:468` | **CURRENT CONFIG (declared, not deployed)** |
| `wecaredigitalbh511413.rzp@rxairtel` | `lambda_utils/payment_readiness.py:44-47` — "AUTHORITATIVE"; live-env value "was stale" | **current prose** |
| both | `whatsapp-business-api/handler.py:3164-3165` | **current prose** |
| `wecaredigitalbh511413.rzp@rxairtel` | `.kiro/specs/.../tasks.md:25,27,39` | **current claim**, owner dashboard readout |
| `wecaredigitalbh511413.rzp@rxairtel` | `bw-crm.md:213,1165` | **HISTORICAL PROSE** — carries the still-correct note that the `rxairtel` suffix is a payment address, **not** an Airtel messaging dependency (so it does not trip the prohibited-provider rule) |
| both | `docs/compatibility.md:87-89` | **HISTORICAL PROSE**, states the conflict unresolved |
| both | `integrations/.../KIRO-IMPLEMENTATION-PROMPT.md:570-576` | the plan's statement of the conflict |

`payment_readiness.py` states the real risk precisely: *"A stale VPA does not error — it silently
collects elsewhere"*. Commit `854767f8` already retired both stale values from the dashboard UI;
what remains is the **live Lambda env**, which is the one that actually gets sent.

### 16. Payment-reference defects — **already fixed at HEAD**

`amplify/functions/shared/lambda_utils/ecommerce/order_keys.py`:

- **`allocate_order_identity` does not exist.** Module docstring, lines 12-15: *"An earlier version
  of this module did exactly that — `allocate_order_identity` bound a Meta reference to a freshly
  reserved order number at payment-request time — and it is gone rather than deprecated, because a
  deprecated function that reserves an order number is a function someone calls."* A tree-wide grep
  finds the name only in that comment and in the plan's Section 34.
- **No truncation anywhere.** `assert_valid_meta_reference_id` (line 190) validates against
  `^[A-Za-z0-9._-]{1,35}$` and **raises `ValueError`** on failure; its docstring states the
  previous `_sanitize_reference_id` cut to 35 characters and that "Rejecting is the only safe response."
- **The identifier split is implemented as the plan asks.** Before payment:
  `new_payment_attempt_id` (UUIDv7), `mint_payment_reference` (`WD-PAY-` + 14 CSPRNG symbols over a
  32-symbol alphabet = 70 bits), `reserve_payment_reference` / `resolve_payment_reference`
  (`PAYREF#`, with `REFERENCE#` retained read-only). After PAID: `new_order_id` (UUIDv7),
  `claim_order_for_payment` (`PROVIDERPAYMENT#` then `PAYMENTATTEMPT#`, both conditional),
  `reserve_public_order_number` (`ORDERNO#`), `record_order_number_on_claim`.
- **`mint_reference_id` is an alias of `mint_payment_reference`** (line 295), kept for existing send
  callers. `reserve_order_number` survives for the Wix sync/backfill path only, on orders Wix has
  already collected payment for.

**Where a reference is still mutated before send — and why it is now safe.**
`_sanitize_reference_id` still exists in two handlers, but its behaviour is inverted:

| Site | Behaviour at HEAD |
|---|---|
| `messaging/outbound-whatsapp/handler.py:2845` | Mints from `secrets` on empty input; **returns a canonical reference byte-for-byte** (`is_valid_meta_reference_id` and no doubled prefix); **raises `ReferenceIdTooLong`** over 35 chars; **raises** if handed a WD order number (`order_keys.is_wd_order_number`), checked *before* the pass-through so `WD-ORD-A1B2C3D4` cannot slip through as a valid-charset string. The old unconditional `.upper()` was removed because Meta's `reference_id` is case-sensitive. |
| `messaging/inbound-whatsapp-handler/handler.py:3145` | Inbound **lookup and display** normalisation only — not a send path. |

Call sites in `outbound-whatsapp`: lines 1060, 1254, 2025 — all on the outbound payment/order-status
message build. Those are now validate-or-fail, not transform.

**`PUBLIC_ORDER_NUMBER_*` note:** the minted form is `WD-ORD-` + 8 symbols over a 30-symbol
alphabet (~39.3 bits), total 15 characters. The plan's "12-char public order number" (Section 57
item 19) describes the **legacy** bare 12-character form, which `is_public_order_number` still
accepts for lookup but nothing mints. One residual inconsistency: `record_order_number_on_claim`'s
`ValueError` message still says *"not a valid 12-character public order number"* while validating
via `is_public_order_number`. Cosmetic, message-only.

### 17. Existing OrderTable writers — enumerated

`stack-wecare-digital-OrderTable` is reached by six code paths:

| Path | Operation |
|---|---|
| `messaging/whatsapp-business-api/flows/orders.py:107` | `put_item` — WhatsApp flow order creation |
| `messaging/whatsapp-business-api/flows/orders.py:206` | `put_item` — **manual order creation** (`manual_order_created`) |
| `messaging/whatsapp-business-api/flows/order_notes.py:60` | admin notes update |
| `messaging/whatsapp-business-api/handler.py:5626` | `update_item` — `ADD requestCount`, guarded on `order_id.startswith('WD-ORD')` |
| `core/service-api/handler.py:164/211` | `_create_order` / `_update_order` — **service API writes** |
| `messaging/whatsapp-business-api/service_api.py:158/197` | the twin of the above (see `tests/test_service_api_twin_divergence.py`) |
| `ecommerce/wix-store/handler.py:1574` | `put_item` — **Wix order mirroring** into the central table |

Reads: `_list_orders`, `_get_order`, `_track_order`, `flows/orders.py:262`.

So the plan's Section 8 is right that OrderTable has writers. **It is also right that none of them
is the paid-checkout path** — and that remains true at HEAD, because `reconcile_payment` writes
identity claims, not an OrderTable row (see item 18).

### 18. Current WhatsApp/Razorpay payment path — what it actually does today

**`amplify/functions/payments/razorpay-webhook/handler.py`** — `handler()` verifies the HMAC
signature first (401 on failure), then computes the dedup key via
`payment_status.dedup_key(payload)` (entity-id based across all 17 `ENTITY_KEYS`, not just
`payload.payment.entity`), takes a **lease** via `_is_duplicate_event`, logs the event, dispatches
on ~40 event types, and calls `_complete_event` **only on the success path** — the `except` branch
deliberately lets the lease lapse so Razorpay's retry is processed rather than dismissed.

`_handle_payment_captured` (line ~573) in order:

1. **Wallet top-up short-circuit** — `notes.purpose == 'wallet_topup'` → `partner_billing.topup`, return.
2. **Secure-file short-circuit** — `notes.purpose == 'secure_file_download'` → `_dispatch_download_grant_confirmation(order_id)`, return. This **grants nothing**; it only tells `wecare-secure-files` that "order X changed", because the webhook secret is in public git history. `secure-files._confirm_with_razorpay` is the only writer of `paid`.
3. Resolve `reference_id` from `notes.referenceId` / `reference_id` / `ref`, then `description`, then the Meta Payment Lookup API.
4. `_store_payment_record(payment, 'captured', ...)` → **PaymentsTable**.
5. **`_create_order_for_captured_payment(payment, reference_id, ...)`** ← the new step.
6. `_mark_invoice_paid_by_reference(reference_id)`, else `_mark_invoice_paid_by_phone_and_amount` → **InvoicesTable**.
7. `_post_payment_handler(...)` → **GST invoice creation, image generation, WhatsApp send**.
8. `_log_ctwa_purchase(...)` → Meta Conversions API.
9. `order_status` message back to the customer, resolving the originating phone id from the invoice.

**So the plan's Section 8 description of the path is accurate for steps 4, 6, 7, 9 — payment
records, invoice state, GST invoice, notifications. Step 5 is new and contradicts Section 8's
conclusion.**

`_create_order_for_captured_payment` (line 431):

- Builds `_load_attempt(ref)` from the `PAYREF#` row — authoritative `amountPaise`, `currency`,
  `customerId` come from the row written at payment-request time, **never from the webhook**
  ("Reading them from the webhook instead would make the comparison compare the event against itself").
- Calls `order_creation.reconcile_payment(table=..., reference_id=..., verify_payment=razorpay_verify.verifier_for_event(...), load_attempt=...)`.
- Logs `order_reconciliation_result`; on `needs_human` logs `alert: PAID_BUT_NO_ORDER` at ERROR.
- **Never raises** — a non-2xx would make Razorpay retry the whole event.
- It is a **no-op when no `PAYREF#` row exists**, which is every payment not originating from the
  new checkout. The existing invoice-only flows are untouched.

`order_creation.reconcile_payment` ordering (verified by reading the function):
resolve attempt → customer-ownership check **before** the idempotent shortcut → existing-order
shortcut (answered before contacting the provider) → **ask Razorpay** (`PROVIDER_UNAVAILABLE` on
failure; `NOT_PAID` if not captured) → **currency equality before amount** → **exact integer-paise
equality** via `money.positive_paise` (accepts DynamoDB `Decimal`, rejects float/bool/str) →
`payment_attempt.may_create_order` → `claim_order_for_payment` → `reserve_public_order_number` →
`record_order_number_on_claim`.

**Does it create a NEW checkout order? Partially — identity yes, business row no.**
Outputs are `orderId`, `orderNumber`, `paymentAttemptId` plus claim rows in the commerce-keys table
(`commerce_keys_table_name()` → `COMMERCE_KEYS_TABLE` → `WIX_ORDER_IDS_TABLE` →
`stack-wecare-digital-WixOrderIds`). Its own docstring is explicit about the boundary: *"It does not
create the Wix order, record the Wix transaction, generate the receipt or send the confirmation."*
`tests/test_order_creation.py::test_reconciliation_does_not_perform_the_downstream_side_effects`
pins that. **No code path writes an `OrderTable` row from a verified capture.**

**`amplify/functions/ecommerce/checkout/handler.py`** — exists in source, **not deployed**. It:
requires a proven customer session (`customer_auth.require_customer`, issuer-pinned); prices from
`wix_ecom.create_checkout` → `authoritative_total_paise` (integer paise, refuses non-whole,
`409 UNSUPPORTED_CURRENCY` on non-INR); gates on `payment_readiness.evaluate` (`409` with the
blocking state if not `PAYMENT_READY`); `order_keys.allocate_payment_reference` binding
`customerId`, `amountPaise`, `currency`, `wixCheckoutId`, `checkoutMode=WIX_HEADLESS`; writes the
attempt with `ConditionExpression="attribute_not_exists(paymentAttemptId)"`; and **returns
`PAYMENT_INITIATION_DISABLED` without sending** unless `CHECKOUT_INITIATION_ENABLED` is truthy
(default off). `_status` is IDOR-safe — missing attempt and someone else's attempt both return the
identical opaque 401. **It creates no order and imports no post-PAID function of `order_keys`.**

Two defects in that handler, both fail-closed:

- `_fetch_payment_configurations` invokes `SENDER_FUNCTION` with `path="/wa-business/payment-config/raw"`.
  `whatsapp-business-api/handler.py` routes `'/payment-config/check' in path` (line 6101) and then
  `'/payment-config' in path` (line 6119). `/payment-config/raw` matches the **second**, which
  requires `phoneId` and returns `400 phoneId required` for a `wabaId` query. Readiness therefore
  receives a body with no `data` key and can never reach `PAYMENT_READY`.
- It prices via **Checkout V1** (`wix_ecom.create_checkout` → `POST /ecom/v1/checkouts`,
  `wix_ecom.py:153`), while `cart_v2.py` / `customer_cart.py` are the Cart V2 model the
  2026-10-01 audit selected. That audit already names this: *"Concurrent checkout/UI scaffolding …
  its V1 integration must be migrated before activation."*

**Cart V2 is deployed-but-off.** `wix-store/handler.py:371` returns `503 CART_UNAVAILABLE` unless
`WIX_CART_V2_ENABLED == 'true'`; live `wecare-wix-store` env does **not** carry that key.
`wix_writeback.py` is documented "INERT until switched on".

### 19. Changes required — gap list, observed state vs the plan's invariants

Severity per `maintenance-reporting.md`. Nothing here is exaggerated: no money has moved through
this path (`PaymentsTable = 0`), so every payment-path gap is latent rather than realised.

| # | Gap | Severity | Observed | Required |
|---|---|---|---|---|
| G1 | Three front-door Lambdas exist in source and in the deploy map but not in AWS | **HIGH** | `ResourceNotFoundException` for `wecare-checkout`, `wecare-customer-registration`, `wecare-email-verification` | Run the owning `scripts/provision_*.py`, then `snapstart_publish.py` to create `live` |
| G2 | No API routes for checkout, cart or registration | **HIGH** | 359 routes; none match | Additive route + integration creation (`A3_PRODUCTION`, IaC updated in the same change) |
| G3 | `CustomersTable` absent | **HIGH** | `ResourceNotFoundException` | Provision; key `customerId`; **TTL must stay DISABLED** (an immutable customer record) |
| G4 | `wecare/otp/pepper` absent | **HIGH** | `ResourceNotFoundException` | Owner-created; the OTP hash-at-rest pepper. Creating a secret *value* is owner work |
| G5 | Checkout readiness targets an unimplemented path | **HIGH** | `/wa-business/payment-config/raw` falls to the `phoneId` branch → 400 | Either add a `raw` branch to `whatsapp-business-api`, or point checkout at `/payment-config/check` and parse `gatewayChecks` |
| G6 | Live env MID/VPA are the values the repo calls stale | **HIGH** | `[retired Razorpay account]`, `wecaredigital83.rzp@icici` | Push manifest values; then `refresh_secret_consumers.py` / republish so no warm sandbox serves the old pair. **Blocked on item 20-D** |
| G7 | No `OrderTable` row is created from a verified capture | **HIGH** | `reconcile_payment` produces identity only; `OrderTable = 0` | Materialize the commerce order behind `side_effect_guard`, keyed on the claim, after `ORDER_CREATED` |
| G8 | Checkout prices from Wix V1 while the selected model is Cart V2 | **MEDIUM** | `/ecom/v1/checkouts` vs `cart_v2.py` | Migrate checkout onto a fresh server-owned V2 calculation; verify the snapshot at paid-order mapping |
| G9 | Cart V2 off in production | **MEDIUM** (intended) | `WIX_CART_V2_ENABLED` absent → `503 CART_UNAVAILABLE` | Leave off until G8 and the activation list in the 2026-10-01 audit are closed |
| G10 | `custom:customer_id` not on the pool schema | **MEDIUM** | pool custom attrs = `['custom:partner_waba_id']` only | Verify before provisioning. Cognito cannot add a schema attribute post-creation; use `scripts/cognito_pool_safe_update.py` for anything on this pool |
| G11 | A live path names `wecare_pay`, which the repo's last live read says is absent | **MEDIUM** | `wecare-secure-files.WA_PAY_TEMPLATE=wecare_pay` vs `payment_readiness.py:415` | Live template read; then item 20-B |
| G12 | `docs/compatibility.md` still carries the reversed MID/VPA evidence weighting | **LOW** | lines 46, 80-81, 87-89 | Relabel as `HISTORICALLY VERIFIED 2026-08-23 — NOT CURRENT` per Section 67; preserve the dates |
| G13 | `00-current-owner-overrides.md` still shows 361 routes | **LOW** | live 359 | Correct, noting it is a dated snapshot |
| G14 | `tasks.md` Phase 0.2 says the Wix credential does not exist | **LOW** | `wecare/wix/headless-api-key` has `AWSCURRENT` | Correct; R0 is no longer a blocker for Phases 6+ |
| G15 | `record_order_number_on_claim` error text says "12-character" | **INFORMATIONAL** | minted form is 15 chars | Message-only |
| G16 | No per-IP protection in front of public customer OTP | **MEDIUM** | WAF removed 2026-09-28; 0 web ACLs | The HTTP front door's `otp_throttle` per-IP axis **is** the control. It only exists once G1/G2 land |

### 20. Owner-only blockers — external, not engineering

These cannot be closed from this repo and must not be attempted here.

- **A. Choose the canonical Meta payment configuration name and create/restore it in
  WhatsApp Manager → Payments.** The repo holds two contradictory 2026-09-30 readings (item 12).
  Creating or modifying a Meta payment configuration is a standing refusal for this agent.
  *Unblock action:* owner runs `payment_readiness.evaluate()` or reads
  `GET /{waba}/payment_configurations`, and states the exact `configuration_name` per WABA.
- **B. Approve the payment template, if outside-24h sends are a requirement.** The only
  repo-evidenced live template is `wecare_otp`. `wecare_pay` is named by five code sites and by live
  `wecare-secure-files` env but is not evidenced at Meta. Submitting a template is an external Meta
  mutation. *Unblock action:* owner confirms the canonical template name and its APPROVED status,
  or confirms that all sends stay inside the service window.
- **C. Load / rotate the Razorpay live key + secret and the Wix admin token.** `tasks.md` records
  both were disclosed in a chat transcript on 2026-09-30 and must be **rotated**, not merely
  stored. Reading, rotating or replacing a provider credential is a standing refusal here.
  *Unblock action:* owner runs `set_wix_credential.py --verify`, `refresh_secret_consumers.py`,
  `check_secrets_live.py`.
- **D. Provider readback of MID and VPA.** The authoritative pair rests on a dashboard readout
  recorded in `tasks.md`, not on a machine read. Until a readback exists, G6 has no safe target.
  *Unblock action:* owner reads the `Payment gateway MID` and UPI VPA off the live configurations,
  or authorises a Graph read where the token stays out of argv.
- **E. Compliance mismatch, MCC 7392 vs purpose code 03.** `bw-crm.md:212` records MCC 7392 as
  consulting while purpose 03 was supplied as Travel, and requires provider/business confirmation
  rather than an implementation default. Unresolved.

A sixth item is *not* a blocker any more and should stop being treated as one: the Wix headless
credential now has an `AWSCURRENT` version.

### 21. Tests — what is already pinned

`git show --stat dc7d409a` → *"Reserve the order number before returning it, and stop deriving
reference_id from it"*, 3 files: `ecommerce/wix-store/handler.py` (89 ±),
`lambda_utils/ecommerce/order_keys.py` (+321), `tests/test_order_keys.py` (+257).
`tests/test_order_keys.py:397` still names it: *"The dc7d409a philosophy, preserved: never return an
unreserved identifier."* Section 33's five protections (conditional reservation, fail-closed
DynamoDB, uniqueness, `secrets`, Meta-compatible validation, collision handling, no unstored-number
escape) are all present in `order_keys.py` at HEAD.

`lambda_utils/payment_status.py` pins:
- a **monotonic ladder** — `created 10 < pending 20 < authorized 30 < failed 40 < captured 50 <
  refunded 60 < disputed 70`, with each placement justified in the docstring (`authorized` below
  `failed` because a hold is not a receipt; `failed` below `captured` because positive evidence of
  money arriving outranks an earlier failure; `refunded` above `captured` so a redelivered capture
  cannot un-refund).
- `condition_expression()` as the **authority** (an atomic `ConditionExpression`), with
  `should_apply()` for in-memory use only, because a read-then-write lets two concurrent deliveries
  both through.
- `canonical()` lenient on read / `for_storage()` strict on write — deliberately asymmetric.
- `paise()` / `rupees_str()` — integer minor units; rupees rendered as a **string** so it cannot be
  arithmetic'd by accident.
- `dedup_key()` over 17 `ENTITY_KEYS` — the fix for the measured loss of ≥59 distinct events in
  four days.
- `entity_summary()` excludes `email`, `contact`, `vpa`, `card_id`, `notes`.
- `InvoicesTable.status` is explicitly **not** this vocabulary (document lifecycle, a different axis).

Commerce/payment test files present at HEAD (17 directly relevant): `test_order_keys.py`,
`test_order_creation.py`, `test_payment_attempt.py`, `test_payment_readiness.py`,
`test_payment_reconciliation_safety.py`, `test_payment_status.py`,
`test_payment_vocabulary_at_decision_points.py`, `test_payments.py`,
`test_razorpay_webhook_order_creation.py`, `test_razorpay_binding.py`,
`test_reference_id_never_truncated.py`, `test_checkout_handler.py`, `test_cart_v2.py`,
`test_wix_writeback.py`, `test_side_effect_guard.py`, `test_receipt_links.py`,
`test_customer_registration_handler.py`, `test_email_verification_handler.py`.

Invariants already asserted (test names read verbatim):

| Invariant | Test |
|---|---|
| A verified capture creates exactly one order | `test_razorpay_webhook_order_creation::test_a_verified_capture_creates_one_order` |
| A redelivery creates no second order | `…::test_a_redelivery_does_not_create_a_second_order` |
| The event body is not trusted | `…::test_the_event_body_is_not_trusted`; `…::test_an_event_amount_that_disagrees_with_the_provider_is_irrelevant` |
| Amount / currency mismatch blocks and flags a human | `…::test_a_provider_amount_mismatch_blocks_and_flags_for_a_human`; `…::test_a_currency_mismatch_blocks` |
| A payment with no attempt passes through untouched | `…::test_a_payment_with_no_attempt_creates_nothing_and_does_not_error` |
| Reconciliation never raises into the webhook | `…::test_reconciliation_never_raises_into_the_webhook` |
| The lease is a lease, completed on success only | `…::test_the_handler_uses_the_leased_claim_not_the_permanent_one`; `…::test_completion_happens_on_the_success_path_only` |
| One paise fails closed; any difference fails closed | `test_order_creation::test_a_one_paise_mismatch_fails_closed`; `…::test_any_amount_difference_fails_closed` |
| Currency is checked before amount | `test_order_creation::test_currency_is_checked_before_amount` |
| Provider is authoritative in both directions | `…::test_the_attempt_state_does_not_override_the_provider` |
| §61 — pending/failed/cancelled/expired → zero orders | `…::test_a_non_paid_state_with_an_unpaid_provider_creates_zero_orders` |
| Concurrent reconciliation leaves one order | `…::test_concurrent_reconciliation_still_leaves_one_order` |
| One provider payment cannot fund two orders | `…::test_one_provider_payment_cannot_fund_two_orders` |
| A crash between claiming and numbering is finished on re-entry, without a second id | `…::test_a_crash_between_claiming_and_numbering_is_finished_on_re_entry`; `…::test_finishing_an_interrupted_order_does_not_mint_a_second_id` |
| **§46 — reconciliation cannot charge the customer**, asserted as an enumerated allowlist | `…::test_reconciliation_cannot_charge_the_customer`; `…::test_no_permitted_call_is_a_money_movement` |
| Downstream side effects are not folded in | `…::test_reconciliation_does_not_perform_the_downstream_side_effects` |
| Paid-but-blocked never offers a retry; the two failure families are disjoint | `…::test_every_paid_but_blocked_outcome_refuses_a_retry_and_wants_a_human`; `…::test_the_two_failure_families_are_disjoint` |
| DynamoDB `Decimal` paise accepted without rounding; float/bool/str rejected | `…::test_dynamodb_decimal_paise_is_accepted_without_rounding`; `…::test_provider_amount_must_be_exact_integer_paise` |
| An order number must not be used as a reference_id; over-long raises | `test_reference_id_never_truncated` (lines 103-122) |
| A MID mismatch blocks | `test_payment_readiness::test_a_mid_mismatch_blocks_payment` |
| `captured` is banned as a raw literal at decision points (AST walk, not text) | `test_payment_vocabulary_at_decision_points` |

R7.4's "explicit test enumerating the Wix calls the reconciliation path can make" is therefore
**already satisfied** by `test_reconciliation_cannot_charge_the_customer`.

`docs/execution/headless-checkout-20261001.md` records the last focused regression run:
**382 passed** on Python 3.12, `git diff --check` clean. **Not re-run here** — the local shell lost
the ability to fork external processes mid-audit (see below), and this step is read-only anyway.

### 22. Rollback strategy

**No changes were made, so nothing needs rolling back.** For the record, any change that follows
this audit is bound by:

- **`git-workflow`** — single branch `stack`, commit directly, `git push origin stack`, no feature
  branches, no force push, no history rewrite.
- **`multi-session-parallel-agents` rule 3b** — the working tree already holds another session's
  modification (`.kiro/steering/META-BETA-REQUEST-EMAIL.md`) and an untracked file
  (`scripts/retired_url_equity.py`). Any commit must therefore use
  `git commit --only <explicit paths> -F <message-file>`; `git add` + chained commit is documented
  as insufficient when the index arrives dirty.
- **`lambda-snapstart-deploy`** — `update-function-code` alone does not reach production for the 58
  functions behind a `live` alias. Every payments-relevant function measured today has one:
  `wecare-razorpay-webhook:live` → v45, `wecare-whatsapp-business-api:live` → v57,
  `wecare-outbound-whatsapp:live` → v43, `wecare-inbound-whatsapp:live` → v66,
  `wecare-customer-whatsapp-auth:live` → v10, `wecare-wix-store:live` → v31,
  `wecare-invoice-engine:live` → v39, `wecare-secure-files:live` → v21. Those version numbers are
  also the **rollback targets**: capture them before publishing, then move the alias back.
  `SnapStart.ApplyOn = None` / `OptimizationStatus = Off` on all eight, re-confirmed today.
- **Secret-consumer refresh** — a warm sandbox caches a secret for the life of the execution
  environment, so an env or secret change needs `scripts/refresh_secret_consumers.py <secret-id>`
  plus `scripts/check_secrets_live.py`, not just a value swap.
- **Flags stay off.** `CHECKOUT_INITIATION_ENABLED`, `WIX_CART_V2_ENABLED`, `WA_LIVE_SMOKE_TEST`,
  `PSTN_BROWSER_ROUTING_ENABLED` and every write-back flag remain absent/false. Enabling a
  live-send flag is a standing refusal.

---

## Section 57 "unblocked now" — which items are genuinely startable today

Judged against observed state, not against the plan's own optimism.

**Startable today, and mostly already done (13 of 23):**

| # | Item | State |
|---|---|---|
| 1 | Spec corrections | Startable. G12-G14 are documentation-only and need no provider read |
| 2 | Customer identity model | **Done** — `lambda_utils/identity/{customer,registration,address,provenance}.py`, `test_customer_identity.py` |
| 3 | Public registration front door | **Code done, not deployed** — `auth/customer-registration/handler.py`; blocked on G1/G2/G3/G4 |
| 4 | Per-IP / per-phone rate limiting | **Done in code** — `otp_throttle.py` (both axes, fail-closed), `rate_limit.py`, `test_otp_throttle.py`, `test_customer_auth_and_throttle.py`. Reaches production only with G1/G2 |
| 5 | WhatsApp OTP | **Live** — `wecare-customer-whatsapp-auth:live` v10, `OTP_TEMPLATE_NAME=wecare_otp`, three CUSTOM_AUTH triggers correct |
| 6 | Admin-side Cognito provisioning | **Code done** in the registration handler; needs G10 resolved |
| 7 | Customer session flow | **Done** — `customer_auth.require_customer`, issuer-pinned; `authorize_resource` for IDOR |
| 8 | SESv2 email OTP | **Code done, not deployed** — `auth/email-verification`, `comms/verification_email.py`; SES itself fully verified (item 8) |
| 9-10 | Billing / shipping address | **Done** — `identity/address.py`, `test_customer_address.py` |
| 13 | PaymentAttempt model | **Done** — `ecommerce/payment_attempt.py`, table provisioned with TTL DISABLED, 0 rows |
| 14 | Canonical payment reference | **Done** — item 16 |
| 16 | Payment history | **Live** — `wecare-payments-read:live` on `GET /payments`, `GET /payments/{paymentId}` |
| 17 | Split `order_keys` | **Done** — item 16 |
| 19 | Public order number | **Done**, with a format note: minted as `WD-ORD-`+8 (15 chars), not 12; the bare 12-char form is lookup-only |
| 23 | Tests | **Substantially done** — item 21 |

**Startable but incomplete, and not blocked on the owner:**

| # | Item | What is left |
|---|---|---|
| 12 | Wix authoritative checkout | Cart V2 exists and was live-probed; **G8** — migrate checkout off `/ecom/v1/checkouts`. The Wix credential now has `AWSCURRENT`, so this is no longer blocked |
| 18 | Paid-only internal order creation | Identity claiming is done and test-pinned; **G7** — the `OrderTable` row, plus Wix order association behind `side_effect_guard` |
| 21 | Receipt | `receipt_links.py` + `test_receipt_links.py` exist; wiring to a paid order depends on G7 |
| 22 | WhatsApp confirmation | Send machinery exists; **may name a template that does not exist (G11)** |

**Gated on the Section 56 owner-only blockers:**

| # | Item | Gated on |
|---|---|---|
| 15 | Payment readiness gate | **A + D.** The module is complete and test-pinned, but it cannot return `PAYMENT_READY` without a live configuration read and an agreed `expected_provider_mid`. **G5 additionally blocks it structurally** — that one is ours to fix, not the owner's |
| 11 | Native checkout integration / hosted payment handoff | **A + B.** The hosted status UI is committed (`394d8e39`); a live payment request needs a configuration name and, outside the 24-hour window, an approved ORDER_DETAILS template |
| 20 | Success / failure / finalizing UI | Buildable against fixtures now; **live verification** needs A + B |
| — | Any live send or capture | **A + B + C**, plus the standing refusal on enabling a live-send flag. Live QA sends go only to the owner-nominated recipient `+918100640044` |

**Net:** roughly 15 of the 23 Section 57 items are already implemented in source at HEAD. The
critical path is **not** design work — it is (a) provisioning and routing the three absent
front-door functions plus `CustomersTable` and the OTP pepper (G1-G4), (b) fixing the
`/payment-config/raw` wiring (G5), (c) materializing the commerce order (G7), and (d) waiting on
the owner for the configuration name, template approval, credential load and MID/VPA readback.

---

## Method and limitations

**Live reads used** (all read-only): `git rev-parse`, `git status --short`, `git log`,
`git show --stat`, `git ls-files`; `sts get-caller-identity`; `lambda ListFunctions`,
`GetFunctionConfiguration`, `ListAliases`; `apigatewayv2 GetRoutes`, `GetIntegrations`,
`GetAuthorizers`, `GetApi`, `GetStages`; `cognito-idp DescribeUserPool`;
`sesv2 GetEmailIdentity`, `GetConfigurationSet`, `ListConfigurationSets`, `GetAccount`;
`dynamodb Scan (Select=COUNT, ConsistentRead)`, `DescribeTable`, `DescribeTimeToLive`, `ListTables`;
`secretsmanager ListSecrets`, `DescribeSecret`.

**Never run:** `secretsmanager get-secret-value` / `batch-get-secret-value` in any spelling; any
Meta Graph call; any Razorpay API call; any Wix API call; any Lambda `Invoke`; any write, publish,
alias move or delete. No credential appeared in any command line.

**Tooling note.** The local shell lost the ability to `fork` part-way through
(`zsh: fork failed: resource temporarily unavailable`), which is why the AWS reads after the first
two batches were issued through the sandboxed AWS API path rather than the CLI, and why git was
driven with `exec` (which replaces the shell instead of forking). This is a local resource
condition, not an AWS or repository problem; it did not degrade any observation, but it did prevent
re-running the test suite, so item 21's "382 passed" is cited from
`docs/execution/headless-checkout-20261001.md` rather than re-measured.

**Explicitly UNVERIFIED, and why:**

| Item | Reason |
|---|---|
| 10 — live WABA/sender health | Meta Graph read needs the system-user token; a token must never enter a command line |
| 11 — live template inventory | same |
| 12 — live payment-config inventory | same; `/payment-config/check` also needs handler auth, and invoking a production Lambda is outside read-only AWS APIs |
| Which SES DKIM selector is actually signed with | needs the `s=` value from a real sent message |
| Wix site / dashboard state beyond `WIX_SITE_ID` | needs an authenticated Wix dashboard |
| Whether the four Meta payment configurations are presently Active | the only evidence is a dashboard readout recorded in `tasks.md`; the repo's own last machine read said zero |

**Historical evidence is labelled as historical throughout.** Where this report cites a dated
measurement (the 607-row webhook log, the 2026-08-23 configuration verification, the 2026-09-30
zero-configuration probe), it is cited as a dated reading and not as current live state.
