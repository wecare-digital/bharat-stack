# Vendor capability and version compatibility

Phase 0 output for the WhatsApp + Wix Headless conversational commerce build.
Measured against account `775261844268` / `us-east-1` on **2026-09-26**.

Two things this document refuses to do: report a documented-but-unmeasured fact as
verified, and carry a number forward without saying how it was obtained. Per
`.kiro/steering/00-current-owner-overrides.md` the counts below are a dated snapshot and
must be rediscovered at the start of each phase, not trusted.

## Evidence classes

| Class | Meaning |
|---|---|
| `LIVE` | measured against the account or the provider during this session |
| `DOC` | read from current official vendor documentation during this session |
| `REPO` | asserted by this repository's own code or docs, dated, not re-measured |
| `BLOCKED` | could not be established, with the blocker named |

## 1. AWS runtime and platform

| Component | Configured / actual | Latest GA | Evidence | State |
|---|---|---|---|---|
| Lambda runtime, existing fleet | `python3.12` on 64 of 64 functions | `python3.13` | `LIVE` `list-functions` runtime histogram | ✅ supported, not latest |
| Lambda runtime, proposed for new API | none yet | `nodejs24.x` | `DOC` Lambda added Node.js 24 support Nov 2025; LTS security/bug fixes expected to Apr 2028 | ⚠️ new runtime for this fleet |
| Node.js 26 | not used | preview only | `DOC` | ➖ correctly excluded |
| HTTP APIs | 1 — `zllr9lrg7j` (`wecare-digital-api`) | n/a | `LIVE` `get-apis` | ⚠️ drift: owner-overrides snapshot said 2 |
| IaC | Amplify Gen 2 (`@aws-amplify/backend ^1.23.0`) + CDK escape hatches, `aws-cdk-lib` pinned `2.270.0` | n/a | `REPO` | ✅ |
| Deploy path | `scripts/deploy_all_lambdas.py` → publish version → move `live` alias | n/a | `REPO` `.kiro/steering/lambda-snapstart-deploy.md` | ✅ |
| SnapStart | `ApplyOn=None` on all functions | n/a | `REPO` measured 2026-09-19 | ✅ off by design |

**Consequence for the architecture.** The prompt's `nodejs24.x` + CDK v2 + TypeScript
baseline is valid and GA, but it introduces a **second runtime and a second deploy
toolchain** into a fleet that is 64/64 Python with a bespoke Python deployer. Lambda's
Node.js 24 also dropped callback-style handlers, so any vendored sample using
`(event, context, callback)` will not run. `design.md` records the decision and its cost.

## 2. Meta WhatsApp Cloud API

| Item | Value | Evidence | State |
|---|---|---|---|
| Graph version in use | `v25.0` | `REPO` | ⚠️ sourced inconsistently, see below |
| `v26.0` | deliberately not adopted | `REPO` `meta-business-agent/handler.py:231-235` records that v26.0 "blocked a batch of commerce" calls | ⚠️ the prompt's `v26.0` baseline is **rejected** until re-tested |
| Business sender | `+919330994400`, phone id `1016149501586345`, WABA `2094615664435155` | `LIVE` re-measured 2026-09-30 | ✅ **healthy** — quality GREEN, `CLOUD_API`, official business account, WABA `APPROVED`. The `if False: # Phone 1 DISCONNECTED` comment was **stale and wrong** |
| Secondary sender | `+919903300044`, phone id `1055232054343117`, WABA `2513394156072604` | `REPO` | ✅ |
| Payment configurations | historically `WECAREDIGITAL` (Razorpay, MID `acc_TTFSyolquKEZEy`), `WECAREUPI` | `REPO` verified live 2026-08-23 | ⛔ **NOT currently present** — see the correction below |
| Payments India surface | `order_details`, `review_and_pay`, `reference_id`, per-WABA payment configuration, payment lookup `GET /{phone_id}/payments/{config}/{reference_id}`, webhook status notifications | `DOC` Meta Payments-in (PG + UPI intent) | ✅ matches the implemented payload |
| Live re-measurement | not possible this session | `BLOCKED` `wecare-whatsapp-business-api` returned `No authorization token provided`; minting an admin token to probe is out of scope | ⛔ |

### ⛔ Correction, 2026-09-30 — the payment configurations are not live

The row above records a reading taken on **2026-08-23**, and it was almost certainly true then.
It is not true now. Re-measured today through `wecare-whatsapp-business-api:live`:

```
GET /2094615664435155/payment_configurations   ->   HTTP 200, ZERO configurations
```

This is not a failed call. `_check_payment_gateway` populates `metaApiResponse` only when the
Graph result carries an `error`, and it came back `null` — so Meta answered, and answered "none".
Both names report `status: local_only`, `canReceivePayments: false`.

**So `WECAREDIGITAL` and `WECAREUPI` currently exist only as Python constants.** Read the 2026-08-23
row as *historically verified*, not *currently verified*; that distinction is the whole reason this
document exists. Meta's own reference warns that when `configuration_name` is invalid the customer
is simply unable to pay, so nothing may send an `order_details` message until it is restored —
which is owner-administrative work in WhatsApp Manager, not something application code may do.

Two more names survive from before the 2026-08-23 rebuild, in
`.kiro/steering/META-BETA-REQUEST-EMAIL.md`: `WECARE-RAZOR-PAY` (WABA1) and
`Razorpay_ManishAgarwal` (WABA2). Four configuration names across three files; none at Meta.

### ⚠️ Correction, 2026-09-30 — the Razorpay MID and UPI VPA both conflict

Neither value may be hard-coded until a restored configuration can be read back and compared.
They are not symmetric, though, and the asymmetry is the useful part:

| Value | Evidence | Weight |
|---|---|---|
| Retired account | Previously present in Lambda environment and historical webhook events. Removed from current source identifiers on 2026-10-02. | Retired; do not use for new payments |
| `acc_TTFSyolquKEZEy` | Owner-confirmed merchant decision, documented in `lambda_utils/payment_readiness.py` and pinned in the deployment manifest. | Authoritative merchant ID; API-key ownership still requires verification |

They are also different *fields*: one is the Razorpay merchant account, the other was only ever
claimed as the Meta configuration's `provider_mid`. `lambda_utils/payment_readiness.py` refuses
to enable payments unless the two agree.

The same shape applies to the UPI VPA: live env says `wecaredigital83.rzp@icici`, the code's
documented fallback says `wecaredigitalbh511413.rzp@rxairtel` — a different handle **and** a
different PSP suffix.

---

**Graph version sourcing is the real defect**, not the version number. `v25.0` reaches the
runtime three different ways: an env var with a default (9 files), a hard-coded module
constant with no env override (7 files), and a literal embedded in a URL string (3 files,
including the payment-lookup call). A single configurable source does not exist, so the
prompt's "must be upgradeable without rewriting business logic" requirement is currently
**unmet**.

## 3. Wix

| Item | Value | Evidence | State |
|---|---|---|---|
| Account id | `15f02319-40ff-4288-b8e6-69c791adae5e` | `LIVE` matches live Lambda env | ✅ |
| Headless site id | `fcd82f0c-9572-49c7-acfb-88fb05042ece` | `LIVE` matches live Lambda env and `src/config/wix.ts` | ✅ single site, no ambiguity |
| OAuth client id | `197cd718-e4ec-4e2e-b380-46c297eb18a2` | `REPO` | ✅ declared, **unused** |
| Auth mechanism, current | permanent admin API key, `Authorization: <raw key>` | `REPO` `wix-store/handler.py:81-123, 344-357` | ⚠️ older mechanism |
| Auth mechanism, recommended | OAuth `client_credentials` → short-lived access token | `DOC` Wix: client credentials are the recommended way to authorize admin operations in a headless project | ✅ spec targets this |
| Stores Catalog | V3 in Lambda code (`/stores/v3/products/{search,query,query-variants}`, `/stores/v3/inventory-items/query`) | `REPO` | ⚠️ capability not re-verified against the site |
| eCommerce Orders | **V1 is LATEST** for this family — read/search/patch (`/ecom/v1/orders/*`), 7 call sites | `DOC` + `REPO` | ✅ implemented, **not** deprecated |
| Order Transactions | **V1 is LATEST** — read (`/ecom/v1/transactions/orders/{id}`), 2 sites; plus 3 `/ecom/v1/payments/.../add-payment` sites in `wix_writeback` | `DOC` + `REPO` | ⚠️ write-back gated off; **no** payment recording live |
| Order Fulfillments | **V1 is LATEST** — read (`/ecom/v1/fulfillments/orders/{id}`), 2 sites | `DOC` + `REPO` | ✅ implemented |
| Cart / Checkout | **PRESENT, and this row previously said "absent", which was false.** Checkout V1 at `lambda_utils/wix_ecom.py:153` (`POST /ecom/v1/checkouts`) and `:211` (`GET /ecom/v1/checkouts/{id}`). Cart **V2** at `lambda_utils/ecommerce/cart_v2.py` (`/ecom/v2/carts/*`) | `REPO` grep, re-run 2026-10-01 | ⚠️ V2 implemented and tested, **opt-in** behind `WIX_CART_V2_ENABLED` (absent on every function, so absence keeps V1); Checkout V1 is what serves |
| Invoices v4 / Receipts v1 | **absent**; invoicing is homegrown (`payments/invoice-engine` + 5 tables + per-FY sequence) | `REPO` | ❌ decision required, see `design.md` |
| Site capability probe | not possible this session | `BLOCKED` no usable Wix credential exists — see §4 | ⛔ |

### `/ecom/v1` is six APIs sharing a prefix, not one deprecated API

Corrected 2026-10-01. The rows above used to read as though `/ecom/v1` were a single version to
migrate off. It is the prefix shared by six separate Wix eCommerce APIs, and **only two are in the
2027-02-01 removal**: eCommerce Cart and eCommerce Checkout, which Cart V2 replaces by combining
them into one Cart entity. Orders, Order Transactions and Order Fulfillments are current, carry no
deprecation notice, and appear nowhere in the Cart V2 migration mapping — for them V1 *is* latest.

Of this repo's 16 `/ecom/v1` call sites in `amplify/`, **2** are in the removal (both Checkout V1,
both in `lambda_utils/wix_ecom.py`) and **14** are not. Migrating the 14 is not possible — Cart V2
has no order search — and deleting them would break live staff order management. They are
deliberately untouched.

| Family | `amplify/` call sites | Removed 2027-02-01? |
|---|---:|---|
| Checkout V1 (`/ecom/v1/checkouts…`) | 2 | **Yes** — migrated to Cart V2, V1 retained behind the gate |
| Orders (`/ecom/v1/orders…`) | 7 | No |
| Order Transactions (`…/transactions…`, `…/add-payment`) | 5 | No |
| Order Fulfillments (`/ecom/v1/fulfillments…`) | 2 | No |

Sources:
[Purchase Flow: Introduction](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/introduction),
[Cart V2: Migration Guide](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-guide),
[Cart V2: Migration Mapping](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-mapping),
[About Orders](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/introduction).
Content was rephrased for compliance with licensing restrictions.

**Catalog version, installed apps and Invoices availability cannot be verified**, because
every probe needs a credential the account does not currently hold. The prompt's §0 items
4-7 are therefore `BLOCKED`, not satisfied. Treating "the code calls V3" as proof the site
*is* V3 would be exactly the kind of inference this document exists to prevent.

## 4. Credential state — the blocking finding

| Location | Expected | Actual | Evidence |
|---|---|---|---|
| Secrets Manager `wecare/wix/headless-api-key` | holds the credential | **exists but holds no value**: `versionCount: 0`, no `AWSCURRENT`, `get_secret_value` → `ResourceNotFoundException`, `LastAccessedDate: None` | `LIVE` `describe-secret` + `set_wix_credential.py --status` |
| `wecare-wix-store` env `WIX_API_KEY_SECRET` | secret name | **absent** | `LIVE` `get-function-configuration` |
| `wecare-wix-store` env `WIX_CREDENTIALS_DISABLED` | unset when live | `true` | `LIVE` |
| `scripts/set_wix_credential.py` `SECRET_NAME` | `wecare/wix/headless-api-key` | was `wecare/wix/headless` — a name that has never existed | `LIVE` fixed 2026-09-26 |
| `~/aws-new-keys-SAVE-THEN-DELETE.txt` | may hold the key | **0** `IST.`-prefixed tokens; only a reference to the retired secret name `wecare/wix-api-key` | `LIVE` shape-only scan, no values rendered |
| Retired `wecare/wix-api-key` | n/a | not present among the account's 25 secrets | `LIVE` `list-secrets` |

So Wix is off **four** independent ways, and the credential is not recoverable from any
authorized location. Only the owner can mint a new one in the Wix dashboard, which shows
an API key exactly once at creation. This is `MANUAL_OWNER_ACTION`; see the unblock
sequence in `.kiro/specs/whatsapp-wix-commerce/requirements.md` §R0.

`docs/wix-headless.md` separately records that the previous key was pasted into a chat and
must be treated as compromised, which is consistent with it having been removed
deliberately and the empty container created on 2026-09-24 as a placeholder.

## 5. Frontend

| Item | Value | Evidence | State |
|---|---|---|---|
| Framework | Next.js 16 + React 19, `pages` router, `output: 'export'` | `REPO` | ⚠️ conflicts with prompt's Astro default |
| Hosting | Amplify app `d22dm4b0jn71jw` | `REPO` | ✅ |
| Server-side code | **none** — static export has no server, so no middleware and no route handlers | `REPO` `next.config.js` | ⚠️ constrains tracking-token handling |

The static export is load-bearing for the design: the Wix SDK's `OAuthStrategy` +
`middleware.js` visitor-session pattern in the vendored reference templates **cannot be
copied**, and a tracking token cannot be validated in the frontend. Both must move into
Lambda. `design.md` §Tracking security depends on this.

## 6. Drift watch

Re-derive before each phase rather than trusting this table.

| Fact | Snapshot | How to re-derive |
|---|---|---|
| Function count / runtimes | 64, all `python3.12` | `aws lambda list-functions --query 'Functions[].Runtime'` |
| HTTP APIs | 1 (`zllr9lrg7j`) | `aws apigatewayv2 get-apis` |
| Functions with a `live` alias | drifts as aliases are provisioned | `ListFunctions` + `ListAliases`, sequentially, reporting the error total |
| Wix credential state | empty container | `python scripts/set_wix_credential.py --status` |
| Secret inventory | 25 | `aws secretsmanager list-secrets` |
| Meta payment configs | 2 per WABA, dated 2026-08-23 | `/whatsapp-business/payment-config/check` with an admin token |
| Graph version | `v25.0`, v26.0 rejected | `grep -rn META_API_VERSION amplify/` |
