# Checkout deployment — closing the `/ecommerce/*` 404, with payment initiation OFF

**Date:** 2026-10-01 · **Account:** 775261844268 · **Region:** us-east-1
**HTTP API:** `zllr9lrg7j` ("wecare-digital-api"), stage `prod`, `AutoDeploy: true`
**Deployed source revision:** `4c603188fd859be28c269db0b2250f76dbb378e5` — the `origin/stack` tip
at deploy time, and what the live function still runs.
**`origin/stack` now:** `83a8d60d` (this work landed as `13c9f7a2`). The two are not the same, and
the difference is recorded in
[the staleness note](#the-deployed-artifact-is-now-stale-and-that-is-recorded-not-fixed) rather
than quietly closed.

`POST /api/ecommerce/checkout` returned **404** because the function behind it had never been
created. It now returns **401**. That is the whole change: a reachable, authenticating endpoint
where there was no endpoint at all.

**Deploying with the gate off created no payment capability.** Nothing here can take money, and
two independent blocks have to be removed by an owner before anything can.

---

## Status

| Task | Status |
|---|---|
| `wecare-checkout` provisioned (python3.12, v1, `live` alias) | ✅ COMPLETE |
| `/ecommerce/*` routes + alias-qualified integration on `zllr9lrg7j` | ✅ COMPLETE |
| Scoped least-privilege IAM role, shared fleet role untouched | ✅ COMPLETE |
| `CHECKOUT_INITIATION_ENABLED` absent — initiation OFF | ✅ COMPLETE |
| Live contract verified 404 → 401, no payable attempt created | ✅ COMPLETE |
| No existing function's `live` alias moved | ✅ COMPLETE |
| `config/lambda-env-manifest.json` entry | ✅ COMPLETE |
| IaC declaration under `amplify/infra/` | ✅ COMPLETE |
| S3 bag-icon upload + provenance | ✅ COMPLETE |
| `PAYMENT_INITIATION_DISABLED` reached by an authenticated unit test | ✅ COMPLETE — `tests/test_checkout_handler.py` |
| `PAYMENT_INITIATION_DISABLED` reached by a live probe | ➖ NOT REQUIRED — structurally unreachable, and that is the [defence-in-depth](#why-payment_initiation_disabled-is-unreachable-live-and-why-that-is-correct) property, not a gap |
| Website-Razorpay architecture direction | ✅ **DECIDED** — website Razorpay Standard Checkout + downloadable receipt. See [the ruling](#the-architecture-ruling-decided-2026-10-01) |
| Website path wired into the deployed handler | ⏳ PENDING — ruling is settled, implementation is not. Handler still imports neither `website_checkout` nor `razorpay_orders`, at `4c603188` **or** at `83a8d60d` |
| Deployed artifact current with `origin/stack` | ⚠️ **STALE** — live is `4c603188`'s package; `order_keys.py` has moved since. Harmless while inert, [must be deployed before the gate is enabled](#the-deployed-artifact-is-now-stale-and-that-is-recorded-not-fixed) |
| `dynamodb:ConditionCheckItem` on the checkout role | ➖ NOT REQUIRED — measured, not assumed |

---

## Before / after

| | Before | After |
|---|---|---|
| `wecare-checkout` function | `ResourceNotFoundException` | `arn:aws:lambda:us-east-1:775261844268:function:wecare-checkout`, v1, `State: Active` |
| `wecare-checkout-role` | `NoSuchEntity` | `arn:aws:iam::775261844268:role/wecare-checkout-role` |
| `live` alias | — | `arn:...:function:wecare-checkout:live` → **v1** |
| Routes on `zllr9lrg7j` | **359** | **361** (+2, none removed, none retargeted) |
| Integrations | **66** | **67** (+1: `zkb6lxe`) |
| `POST /api/ecommerce/checkout` | **404** `{"message":"Not Found"}` | **401** `{"error": "VERIFICATION_REQUIRED", ...}` |
| `POST /api/ecommerce/checkout/status` | **404** | **401** |
| `PaymentAttemptsTable` item count | **0** | **0** |
| Log group | absent | `/aws/lambda/wecare-checkout`, 30-day retention |

### Resources created

```
function    arn:aws:lambda:us-east-1:775261844268:function:wecare-checkout
            python3.12 · handler.handler · 20s · 256 MB
            CodeSha256 917moZkEBIyIzGRQvChUup2PMoWfw4Ebmr863jnQBKI=
version     1  ("initial checkout release (initiation off)")
alias       live -> v1
role        wecare-checkout-role
            managed: AWSLambdaBasicExecutionRole
            inline:  CheckoutLeastPrivilege
log group   /aws/lambda/wecare-checkout  (30 days)
integration zkb6lxe  AWS_PROXY 2.0 -> arn:...:function:wecare-checkout:live
route       508jgfp  POST /ecommerce/checkout
route       gi2dibv  POST /ecommerce/checkout/status
permission  apigateway-invoke-checkout  on :live, SourceArn .../zllr9lrg7j/*/*
```

The `Qualifier` on that permission is load-bearing. A function-level statement does not authorise
an **alias** invoke, and the failure mode is a 500 with no Lambda log line at all, because the
function is never entered — which is how `POST /plivo/dial-events` once looked deployed and was
not (`scripts/provision_missing_ui_routes.ensure_permission` records it).

---

## The package came from `origin/stack`, and that was not a formality

The shared working tree holds three other sessions' in-flight edits, and local `HEAD` is **2
ahead / 25 behind** `origin/stack`. Measured directly, **five modules the checkout path needs
exist only on `origin/stack`** and are absent from the working tree:

```
customer_session.py                 worktree=NO   origin/stack=yes
ecommerce/website_checkout.py       worktree=NO   origin/stack=yes
ecommerce/checkout_pricing.py       worktree=NO   origin/stack=yes
ecommerce/customer_receipt.py       worktree=NO   origin/stack=yes
integrations/razorpay_orders.py     worktree=NO   origin/stack=yes
```

A package built from the working tree would have shipped a handler whose siblings were missing.
So the artifact was built from `git archive origin/stack` into `.scratch/deploy-checkout/`, and
the working tree was used only to hold the committed source changes. No `merge`, `rebase`,
`reset` or `stash` was run.

### Package and validation

```
112 files · 413,871 bytes · sha256 917moZkEBIyIzGRQvChUup2PMoWfw4Ebmr863jnQBKI=
imports: all resolve · 0 errors · 0 guarded warnings
tests / __pycache__ / .pyc shipped: none
non-.py members: none
```

All 16 required modules are present — `website_checkout.py`, `razorpay_orders.py`,
`checkout_pricing.py`, `order_keys.py`, `payment_attempt.py`, `order_creation.py`,
`customer_session.py`, `payment_status.py`, `customer_auth.py`, `payment_readiness.py`,
`wix_ecom.py`, `media_paths.py`, `response.py`, `logging.py`, `customer_receipt.py` and
`handler.py`.

**No templates are needed, and that is now asserted rather than assumed.** Nothing in the
package reads a `.html`/`.txt`/`.json`/`.j2` file from disk; the only non-`.py` file anywhere
under `shared/` is `config.ts`, which is irrelevant to Python.
`test_the_package_is_python_only` pins it, because "we don't need templates" is exactly the kind
of claim that silently stops being true.

The live `CodeSha256` equals the locally-computed package sha, so what is deployed is byte-for-byte
`4c603188`'s checkout path.

---

## Nothing became payable

Four independent facts, each measured:

1. **`CHECKOUT_INITIATION_ENABLED` is absent from the live environment** — not `"false"`, absent.
   The live variables are exactly `PAYMENT_ATTEMPTS_TABLE`, `COMMERCE_KEYS_TABLE`,
   `WIX_API_KEY_SECRET`, `WIX_SITE_ID`, `SENDER_FUNCTION`, `PAYMENT_WABA_ID`,
   `EXPECTED_CONFIGURATION_NAME` (empty) and `EXPECTED_PROVIDER_MID` (empty).
2. **Readiness blocks independently of the gate.** Both `EXPECTED_*` inputs are empty, so
   `payment_readiness.evaluate` returns `CONFIGURATION_UNVERIFIED`. Flipping the flag alone still
   cannot produce a payable message; an owner must additionally supply both values from a live
   Meta/Razorpay readback. Two separate actions, deliberately.
3. **`PaymentAttemptsTable` holds 0 items before and 0 after** every probe. No payable attempt and
   no gateway order was created.
4. **The role grants no Razorpay credential read.** See the IAM section.

### Why `PAYMENT_INITIATION_DISABLED` is unreachable live, and why that is correct

The task asked for `POST /api/ecommerce/checkout` with `action=create` to return
`PAYMENT_INITIATION_DISABLED`. **It returns 401, and no probe can make it return
`PAYMENT_INITIATION_DISABLED`.** The handler was not changed to make the literal assertion pass;
doing so would have weakened authentication to make a probe prettier.

**Reviewed and accepted as defence-in-depth, not as an untested branch** (owner, 2026-10-01:
three independent refusals stacked in front of a payable order is the intended design). Three
refusals, in execution order:

1. `handler.handler` calls `customer_auth.require_customer(event)` **first**, before parsing the
   body. An unauthenticated or invalidly-authenticated request gets an opaque 401 and never
   enters `_create`. Checkout is correctly not a public endpoint.
2. Inside `_create`, `payment_readiness.evaluate` runs **before** the `if not INITIATION_ENABLED`
   branch. With both `EXPECTED_*` empty it returns `CONFIGURATION_UNVERIFIED`, so the response is
   **409 `payment_unavailable`**, short-circuiting ahead of the gate.
3. Only then does the gate itself answer `PAYMENT_INITIATION_DISABLED`.

Reaching layer 3 live would need a real customer Cognito access token **and** owner-supplied
readiness values. Minting a customer token is not authorised here, and the readiness values are
owner-only. **So the measured live contract change is 404 → 401**, and the branch is reached
where it can be reached honestly: in a unit test with an authenticated fixture.

#### The branch IS exercised, with an authenticated fixture

`tests/test_checkout_handler.py::test_create_disabled_prepares_attempt_but_sends_nothing_and_makes_no_order`
stubs `customer_auth.authenticate` to return a `CustomerIdentity`, sets readiness to pass
(`EXPECTED_CONFIGURATION_NAME='WECAREDIGITAL'`, `EXPECTED_PROVIDER_MID='acc_TESTMID'`) and pins
`INITIATION_ENABLED=False` — so it enters the exact branch a live probe cannot, and asserts the
properties that matter rather than just the status string:

- `status == 'PAYMENT_INITIATION_DISABLED'`, `amountPaise == 59900` (Wix's authoritative 599.00 in
  integer paise), `currency == 'INR'`
- exactly **one** attempt row, bound to the customer, `checkoutMode == 'WIX_HEADLESS'`,
  `status == 'PAYMENT_READINESS_CHECKED'`
- a `PAYREF#` reservation exists, and **no** `ORDERNO#`, `PAYMENTATTEMPT#` or `PROVIDERPAYMENT#`
  row does — so no order was created
- the only internal invoke was the readiness payment-config read; **no** `send` path was invoked,
  so no payable message went out

`tests/test_razorpay_binding.py` covers the same state on the website path
(`wc.PAYMENT_INITIATION_DISABLED`). Between them the branch is covered for both flows; what is
absent is only a live HTTP observation of it, which is prevented by layers 1 and 2 above.

---

## Live probes (every code measured, not inferred)

| Probe | Before | After |
|---|---|---|
| `POST https://wecare.digital/api/ecommerce/checkout` | 404 | **401** |
| `POST https://wecare.digital/api/ecommerce/checkout/status` | 404 | **401** |
| `POST https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/ecommerce/checkout` | 404 | **401** |
| `POST .../prod/ecommerce/checkout/status` | 404 | **401** |
| `POST /api/ecommerce/checkout` with `Authorization: Bearer <invalid>` | — | **401**, JSON body |
| `POST /api/ecommerce/checkout/status` with a foreign `paymentAttemptId` | — | **401**, JSON body |
| `OPTIONS /api/ecommerce/checkout` preflight | — | **204** + `access-control-allow-origin: https://wecare.digital` |

After-body on all four checkout probes:

```json
{"error": "VERIFICATION_REQUIRED", "message": "Please verify your WhatsApp number to continue."}
```

Two details worth keeping:

- **The raw-API probe needs `/prod`.** `prod` is the only stage on `zllr9lrg7j`; there is no
  `$default`. A probe to `https://zllr9lrg7j.execute-api.../ecommerce/checkout` returns 404 even
  now, and that 404 means "no such stage", not "no such route". Reading it as a route failure
  would send someone looking in the wrong place.
- **A foreign `paymentAttemptId` returns the identical opaque 401** to an unauthenticated
  request, so the endpoint is not an IDOR oracle: a real attempt id and a fabricated one are
  indistinguishable from outside.

### Direct invokes

| Probe | Result |
|---|---|
| `wecare-checkout:live` with an `OPTIONS` event | `StatusCode 200`, `FunctionError: null` |
| `wecare-checkout:live` with a `POST` event, no `Authorization` | `StatusCode 200`, handler `401` |

The first is the **packaging proof**. A cold start executes every top-level import, so a module
missing from the ZIP surfaces here as `Unable to import module 'handler'`. It did not.

### Retained paths still work

| Path | Before | After |
|---|---|---|
| `POST /api/razorpay-webhook` | 401 | **401** |
| `POST /api/auth/validate` | 401 | **401** |
| `GET /api/webhook/sinch-rcs` | 200 | **200** |
| `GET /mcp` | 405 | **405** |
| `GET /get/o/public/wa-tpl/docs/wecare-digital-011f1811_Insurance.pdf` | — | **200** `application/pdf` |
| `GET /cart` (followed) | 200 | **200** |

### No existing alias moved

| Function | Before | After |
|---|---|---|
| `wecare-razorpay-webhook` | **v45** | **v45** |
| `wecare-whatsapp-business-api` | v57 | v57 |
| `wecare-contacts` | v26 | v26 |
| `wecare-outbound-whatsapp` | v43 | v43 |
| `wecare-invoice-engine` | v39 | v39 |

`scripts/deploy_all_lambdas.py` was **never run without a target**. One function was created; no
existing function's code, configuration or alias was touched.

### Route surface diff

```
before 359  after 361
added      508jgfp  POST /ecommerce/checkout
           gi2dibv  POST /ecommerce/checkout/status
removed    none
retargeted none
```

### Logs

`/aws/lambda/wecare-checkout` over 7 invocations shows `START` / `END` / `REPORT` only — **zero
application log lines**, because every request stopped at the 401, which does not log. No phone
number, no amount tied to an identity, no credential-shaped material, no import error.

---

## IAM: what was granted, and what deliberately was not

`wecare-checkout-role`, inline policy `CheckoutLeastPrivilege`:

| Sid | Action | Resource |
|---|---|---|
| `ReadWixApiKey` | `secretsmanager:GetSecretValue` | `wecare/wix/headless-api-key-*` |
| `PaymentAttemptAndCommerceKeys` | `dynamodb:GetItem`, `PutItem`, `UpdateItem` | the two named tables only |
| `InvokeWhatsAppSender` | `lambda:InvokeFunction` | `wecare-whatsapp-business-api` and `:live` |

Four deliberate omissions:

- **No `dynamodb:DeleteItem`.** A failed attempt is the evidence that no charge became an order.
- **No Cognito action.** `customer_auth.authenticate` calls `GetUser` with the **customer's own**
  access token, which authorises itself. An IAM grant would be privilege the function cannot use.
- **No `secretsmanager:GetSecretValue` on `wecare/razorpay/api`.** See below.
- **No wildcard, and `wecare-digital-lambda-role` was not touched.** That role is shared by ~65
  functions; a statement added for checkout would widen every one of them. Its 16 inline policy
  names are snapshotted unchanged for a later diff.

### `dynamodb:ConditionCheckItem` — measured, and NOT required

`iam simulate-principal-policy` against the new role, both table ARNs:

```
dynamodb:GetItem            allowed
dynamodb:PutItem            allowed
dynamodb:UpdateItem         allowed
dynamodb:ConditionCheckItem implicitDeny   <- and not required
```

`ConditionCheckItem` is only ever required inside `TransactWriteItems` / `TransactGetItems`. A
plain `put_item`/`update_item` carrying a `ConditionExpression` needs `PutItem`/`UpdateItem` and
nothing more — and that is all `order_keys` and `payment_attempt` use. **No grant was made and
none is needed.**

One correction worth recording, because the first version of this check was wrong in the
dangerous direction. The detector initially scanned the whole 112-file ZIP and reported a
`REQUIRED GRANT`, because `build_zip` ships the entire `lambda_utils` tree without pruning and
`crm/service.py` and `notifications/store.py` both use `TransactWriteItems`. **Neither is
imported by checkout.** The handler's import closure is **18 of the 112 packaged files** and
contains no transaction call at all. The check now walks that closure:

```
handler.py                              lambda_utils/http_path.py
lambda_utils/__init__.py                lambda_utils/identifiers.py
lambda_utils/customer_auth.py           lambda_utils/logging.py
lambda_utils/ecommerce/__init__.py      lambda_utils/middleware.py
lambda_utils/ecommerce/money.py         lambda_utils/payment_readiness.py
lambda_utils/ecommerce/order_keys.py    lambda_utils/rate_limit.py
lambda_utils/ecommerce/payment_attempt.py  lambda_utils/response.py
lambda_utils/ecommerce/wix_domain.py    lambda_utils/template_ttl.py
lambda_utils/validation.py              lambda_utils/wix_ecom.py
```

A grant report that cries wolf is one nobody reads, which is the same reasoning the inline-secret
hook is built on. `report_required_grants` **only simulates** — it holds no
`put_role_policy`/`attach_role_policy` call, pinned by
`test_the_grant_report_only_simulates`.

### The required grant I deliberately did not make

```
secretsmanager:GetSecretValue  on  arn:aws:secretsmanager:us-east-1:775261844268:secret:wecare/razorpay/api-*
```

`razorpay_orders.RAZORPAY_SECRET_ID` defaults to `wecare/razorpay/api`, and the module ships in
the ZIP — but **nothing in the handler's import closure reaches it** (see the 18 files above).
Granting a Razorpay credential read to code that cannot run widens privilege for zero benefit.
This is the prerequisite grant for the website-Razorpay path, to be made at the moment that path
is wired, and not before. `test_the_role_grants_no_razorpay_credential_read` pins the current
state so adding it has to be a deliberate edit.

---

## Three findings a reader needs

### 1. The website Razorpay path ships but is NOT wired in

At `4c603188`, `handler.py` mentions `website_checkout` and `razorpay_orders` **only in its
docstring**. Its top-level imports are `customer_auth`, `payment_readiness`, `order_keys`,
`payment_attempt`, `wix_ecom`, `logging`, `response` — confirmed by the 18-file import closure.
`_action` dispatches `create` and `status` and nothing else.

**Re-measured at `83a8d60d` after the merge: still true.** The import list is unchanged, so the
additive website contract (`CHECKOUT_OPTIONS_READY`, the callback with HMAC-over-stored-order-id
plus authoritative capture) is present in the artifact and still unreachable.

The architecture question that blocked it has since been answered, which changes the status from
"undecided" to "decided and not yet implemented" — see below. Both paths remain behind the same
`CHECKOUT_INITIATION_ENABLED` gate, off.

### The architecture ruling (decided 2026-10-01)

**Website Razorpay Standard Checkout + downloadable receipt.** Recorded in commit `9e3e77cb`
*"docs: reconcile checkout spec to website-only Razorpay ruling (FEAT-004)"*, which updated
`requirements.md`, `design.md` and `tasks.md`.

This supersedes the spec statements this deployment was written against. The earlier
"WhatsApp-only receipts" and "payment collected externally via WhatsApp" language is **retired**,
not merely overridden. Owner confirmation in session: WhatsApp stays as the support widget, OTP
sign-in, and authorised receipt/order notifications — it is **out of the purchase flow**. Commit
`b6646345` retired the in-WhatsApp payment-capture side effects on that basis.

Two things the ruling does **not** change, and both were re-confirmed with it:

- `CHECKOUT_INITIATION_ENABLED` stays **OFF**. Enabling it is owner-only and still ungranted.
- **No live monetary test** happens until the owner authorises it separately.

So the consequence for this deployment is narrow and worth stating plainly: the deployed function
is unaffected, because the website path it would run is not wired into the handler yet. The ruling
unblocks that implementation work; it does not retroactively change what was deployed. Note also
that `.kiro/steering/whatsapp-payments-india-reference.md` still describes the in-WhatsApp
posture — steering has not been reconciled to `9e3e77cb`, and whoever wires the website path
should expect to resolve that, since steering outranks a spec on conflict.

### The deployed artifact is now stale, and that is recorded, not fixed

Measured after the merge. The live function still runs the package built from `4c603188`; HEAD is
now `83a8d60d`:

```
live  CodeSha256  917moZkEBIyIzGRQvChUup2PMoWfw4Ebmr863jnQBKI=   112 files  413,871 bytes
HEAD  package     OU+pzkX/hi4/5lSYEsA8FlBDhjaFXzOV2HooSeSzk8o=   114 files  419,158 bytes
```

What moved, and whether it matters:

| File | Change | In the deployed import closure? |
|---|---|---|
| `lambda_utils/ecommerce/order_keys.py` | +100 lines: `claim_legacy_invoice_payment`, `release_legacy_invoice_payment_claim` (commits `86c36f43`, `72a68e31`) | **Yes** |
| `lambda_utils/integrations/razorpay_verify.py` | +23 lines | No |

`order_keys` **is** one of the 18 files the handler reaches, so this is real drift and not a
cosmetic hash difference. It is harmless **today** for one reason only: the function is inert.
Every request is refused at `customer_auth` before any `order_keys` call, so no code path that
differs between the two revisions can execute.

**It must be deployed before `CHECKOUT_INITIATION_ENABLED` is enabled.** One command, and it
reports the drift itself rather than relying on this note being read:

```
.venv/bin/python scripts/deploy_all_lambdas.py wecare-checkout --dry-run
#   packaged 114 files, 419158 bytes
#   WOULD UPDATE: 917moZkEBIyI... -> OU+pzkX/hi4/...
# then, to apply (publishes a version and moves the live alias for THIS function only):
.venv/bin/python scripts/deploy_all_lambdas.py wecare-checkout
```

Not done here deliberately: the task scope was to create the function with the gate off and verify
the contracts, and a code update plus an alias move from v1 to v2 is a separate action with no
benefit while the function cannot execute the changed code. Recording a known-stale artifact is
safer than a silent redeploy outside the reviewed scope.

### 2. The Razorpay credential read is lazy, but a rotation still needs a republish

`razorpay_orders._credentials()` reads `wecare/razorpay/api` inside a function at request time,
**not** at module scope — so it does not break the init-time rule in `lambda-snapstart-deploy`.
`test_the_handler_reads_its_payment_credential_lazily` asserts it over the AST.

But it caches into a module global `_cached`, which lives for the life of the execution
environment. A warm sandbox keeps serving the old value after a rotation. So a rotation of
`wecare/razorpay/api` still requires `scripts/refresh_secret_consumers.py wecare/razorpay/api`
to recycle the consumers. This is a correctly-written lazy read with a real operational
consequence, not a defect.

### 3. Working-tree test failures are foreign, and the committed tree is green

Measured three times, because "the tests fail" needs a scope before it means anything.

| Tree | Result |
|---|---|
| `4c603188` (deployed revision) + this commit's changes | **5726 passed, 3 skipped, 0 failed** |
| `83a8d60d` (merged `origin/stack`), clean `git archive` | **5757 passed, 1 skipped, 0 failed** |
| live working tree at the same HEAD | **22 failed, 5735 passed** |

The committed tree is green at both revisions. Every working-tree failure traces to one
uncommitted file belonging to another session —
`amplify/functions/shared/lambda_utils/ecommerce/order_creation.py`, on this task's
DO-NOT-TOUCH list — and the failures are confined to `test_razorpay_webhook_captured_gating.py`,
`test_razorpay_webhook_order_creation.py`, `test_order_creation.py` and
`test_payment_vocabulary_at_decision_points.py`.

None of this task's 14 paths is dirty; all match HEAD. The practical point for a reader: run the
suite against a clean archive before concluding anything from a red local run, because in this
shared tree a red run is the normal state rather than a signal.

---

## Changes committed

| Path | Why |
|---|---|
| `scripts/provision_checkout.py` | `--source-root`; delegated packaging + pre-create import validation; route/integration/alias-qualified-permission provisioning; closure-scoped IAM grant report; route assertions in `--verify` |
| `config/lambda-env-manifest.json` | `wecare-checkout` entry (67 functions / 397 variables) |
| `amplify/infra/checkout.json` | IaC declaration of record |
| `tests/test_provision_checkout_contract.py` | gate, routes, alias qualification, IAM omissions |
| `tests/test_checkout_package_completeness.py` | package completeness, determinism, lazy secret, no float money |
| `docs/execution/snapshots/checkout-*-20261001.json` | 8 before/after snapshots |
| `docs/execution/checkout-deployment-20261001.md` | this document |

`scripts/deploy_all_lambdas.py` was **not modified** — no packaging defect blocked the work; its
`build_zip`/`validate` were reused unchanged.

### Why the IaC is a CloudFormation template and not a CDK construct

`amplify/infra/checkout.json` follows the house style set by `amplify/infra/home-fallback.json`:
a standalone template that declares what a script owns. It is deliberately **not** imported into
`amplify/backend.ts`, for two measured reasons:

1. **`zllr9lrg7j` is not CloudFormation-managed.** It carries 361 routes created by provisioning
   scripts over time, and `amplify/link-resources.ts` records at its head that the one `HttpApi`
   construct it declares **has never been deployed** — there is no stack for it. A CDK construct
   added to the Amplify backend would create a **second** API, not extend this one.
2. **`amplify/backend.ts` states the Python Lambdas are deployed separately and are not managed
   by Amplify Gen 2.** Adopting one of them into the Amplify stack would put a live payment-path
   function under a stack that can delete it on a failed update.

`test_the_template_is_not_wired_into_the_amplify_backend` pins that separation, and
`aws cloudformation validate-template` accepts the template.

---

## S3 bag icon (§10)

Provenance verified against **two independent official sources**, both HTTP 200, path geometry
**byte-identical** to the committed file:

- [`google/material-design-icons@master`](https://raw.githubusercontent.com/google/material-design-icons/master/symbols/web/shopping_bag/materialsymbolsoutlined/shopping_bag_48px.svg)
- [`fonts.gstatic.com` release channel](https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/shopping_bag/default/48px.svg)

Material Symbols Outlined `shopping_bag`, 48px, FILL 0 / wght 400 / GRAD 0 / opsz 48. Licensed
under Apache License 2.0 per the [Material Symbols guide](https://developers.google.com/fonts/docs/material_symbols)
and the [repository LICENSE](https://github.com/google/material-design-icons/blob/master/LICENSE).
The only modification is the fill: upstream `#1f1f1f` replaced with the site chrome green
`#1a3a2a`. *Licence summary paraphrased; content was rephrased for compliance with licensing
restrictions.*

```
local     public/icons/shopping-bag.svg
          sha256 e3e7925a7ba2449bd09d0f2b5be12926822c14ff705eaa25a698988a7ac14792
          1,472 bytes
bucket    wecare-digital-get                (EXISTING — no bucket was created)
key       o/stream/media/m/shopping-bag.svg
composed  lambda_utils.media_paths.public("stream/media/m", "shopping-bag.svg")
CDN URL   https://wecare.digital/get/o/stream/media/m/shopping-bag.svg   -> 200
headers   content-type: image/svg+xml
          cache-control: public, max-age=31536000, immutable
          x-content-type-options: nosniff
etag      a21aff358cbb919e12ecb4dddf358a90
```

The key was composed through `media_paths.public(...)` and never hand-built, and
`media_paths.is_gated(key)` is `False` — asserted before the upload, not after. The destination
prefix is the one the committed file's own header names.

The `o/` prefix is public, so this object is **unlisted but public**: safe from enumeration
(bucket listing is blocked and the bucket policy grants `s3:GetObject` only to the CloudFront
service principal), not safe once the URL leaks. Correct for third-party Apache-2.0 artwork the
site already serves openly. **No receipt or payment artefact was written here**; private receipt
storage stays under `secure/`.

---

## Rollback

Non-destructive first: **set no flag and leave it alone.** The function is inert — it
authenticates, and with readiness unverified it refuses. There is no traffic to drain.

To remove it entirely, in this order. Every step below is in `block-catastrophic`'s
`DESTRUCTIVE_AWS` table and therefore **asks before acting** — each needs pointwise confirmation.

```
# 1. routes first, so the API stops resolving before the target disappears
aws apigatewayv2 delete-route --api-id zllr9lrg7j --route-id 508jgfp --region us-east-1
aws apigatewayv2 delete-route --api-id zllr9lrg7j --route-id gi2dibv --region us-east-1

# 2. the integration, now unreferenced
aws apigatewayv2 delete-integration --api-id zllr9lrg7j --integration-id zkb6lxe --region us-east-1

# 3. the alias, then the function
aws lambda delete-alias --function-name wecare-checkout --name live --region us-east-1
aws lambda delete-function --function-name wecare-checkout --region us-east-1

# 4. the role (policy first; IAM refuses to delete a role with an inline policy attached)
aws iam delete-role-policy --role-name wecare-checkout-role --policy-name CheckoutLeastPrivilege
aws iam detach-role-policy --role-name wecare-checkout-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name wecare-checkout-role
```

`/aws/lambda/wecare-checkout` is **retained** deliberately — the log group outlives the function
so the record of what it did survives the rollback.

Order matters: deleting the function before the routes leaves two routes pointing at a missing
target, which answers 500 rather than 404 and reads like a broken deployment instead of an absent
one.

Delete **only** the ids listed above. The before-snapshots are the authority on what existed
first: any `RouteId` or `IntegrationId` not in `checkout-routes-before-20261001.json` /
`checkout-integrations-before-20261001.json` was created by this change, and nothing else may be
touched.

### Snapshots

| File | Contents |
|---|---|
| `checkout-routes-before-20261001.json` | 359 routes, 0 `ecommerce` |
| `checkout-integrations-before-20261001.json` | 66 integrations, 0 checkout |
| `checkout-function-absent-before-20261001.json` | the captured `ResourceNotFoundException` + `NoSuchEntity` |
| `checkout-shared-role-before-20261001.json` | `wecare-digital-lambda-role`'s 16 inline policy names, unmodified |
| `checkout-routes-after-20261001.json` | 361 routes, the 2 added ids, empty removed/retargeted |
| `checkout-integrations-after-20261001.json` | 67 integrations, `zkb6lxe` |
| `checkout-live-probes-after-20261001.json` | every probe, code and body |
| `checkout-bag-icon-provenance-20261001.json` | icon provenance, checksums, object headers |

---

## Open

~~**Confirm the architecture direction.**~~ **Answered 2026-10-01** — website Razorpay Standard
Checkout + downloadable receipt, committed at `9e3e77cb`. See
[the ruling](#the-architecture-ruling-decided-2026-10-01).

Remaining, in the order they have to happen:

1. **Wire the website path into the handler** (implementation, not a decision). `handler.py`
   imports neither `website_checkout` nor `razorpay_orders` at `83a8d60d`, so the sanctioned flow
   is shipped-but-unreachable. Expect to reconcile
   `.kiro/steering/whatsapp-payments-india-reference.md`, which still describes the in-WhatsApp
   posture and outranks the spec on conflict.
2. **Grant `secretsmanager:GetSecretValue` on `wecare/razorpay/api`** to
   `wecare-checkout-role` — at the moment step 1 lands, not before. Still deliberately ungranted:
   the direction being decided does not make the credential usable while the code that reads it
   cannot execute. `test_the_role_grants_no_razorpay_credential_read` pins the current state so
   adding it is a deliberate edit.
3. **Deploy the current artifact.** The live function is `4c603188`'s package and `order_keys.py`
   has moved since — see
   [the staleness note](#the-deployed-artifact-is-now-stale-and-that-is-recorded-not-fixed).
   This must precede step 4.
4. **`CHECKOUT_INITIATION_ENABLED`** — owner-only, and still OFF. Setting it alone is neither
   sufficient nor safe: both `EXPECTED_*` readiness values must come from a live Meta/Razorpay
   readback first, or the endpoint returns 409 regardless.
5. **The live monetary test to +918100640044** remains deferred pending separate owner
   authorisation, as does the fleet-wide alias move across ~60 functions. Neither was touched here.

## Push

Resolved by the orchestrator, not by this session. `origin/stack` is now `83a8d60d` and local is
0 ahead / 0 behind; commit `13c9f7a2` is an ancestor of HEAD and present on the remote. The
non-fast-forward this document originally flagged was a genuine blocker — local `stack` was 3
ahead / 25 behind — and integrating it was the one-committer's call under
`.kiro/steering/multi-session-parallel-agents.md`. No `reset --hard`, stash, force push or history
rewrite was involved on either side.

---

## Related

- `.kiro/steering/whatsapp-payments-india-reference.md` — integer paise, `reference_id`, payment vocabulary
- `.kiro/steering/lambda-snapstart-deploy.md` — why the `live` alias is what production invokes
- `.kiro/steering/blog-production-s3.md` — the `o/` prefix decision the icon upload follows
- `docs/execution/snapshots/checkout-*-20261001.json` — the eight snapshots above
