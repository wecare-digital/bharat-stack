# Checkout readiness — the two expected values, what the gate really compares, and the smallest safe live test

**Mode:** read-only diagnosis. Nothing was set, deployed, published, enabled, invoked-for-effect, committed or pushed. No `get-secret-value` / `batch-get-secret-value` in any spelling. No secret value is in this document. No message, OTP, payment, capture, refund or payment-configuration mutation.

**Repo:** `/Users/wecaredigital/wecare-store`, branch `stack`, local `HEAD = 32b632e3` (`git rev-parse --short HEAD`). `origin/stack = 8c46b132`, two commits ahead; `git diff --stat 32b632e3..8c46b132` is `ecommerce/customer-session/handler.py` (+14) plus four conversations content files — **nothing on the commerce path**, so every claim below holds at both.

**Account:** 775261844268, `us-east-1`, profile `wecare-prod`.

**Numbers re-measured because the prior report has moved:** `wecare-checkout:live` is **v5** (was v4), `wecare-customer-session:live` is **v6** (was v5), `wecare-wix-store:live` is **v34** (was v33), and `WIX_CART_V2_ENABLED=true` is now **set** on both checkout and wix-store (the prior report recorded it absent on every function). That last one changes the answer materially — see §4 row 2.

---

## 1. The dummy-value question, answered first

**Setting both values to arbitrary placeholders FAILS CLOSED. There is no false-pass shape anywhere in `payment_readiness.evaluate`.** The refusal to fill them with dummies was correct.

But the reason is not the one anybody assumed, and it is the more important finding:

> **The readiness gate cannot currently reach `PAYMENT_READY` with the REAL values either.** The live readback it performs targets a Lambda route that does not exist, so `evaluate` returns `META_UNAVAILABLE` regardless of what the two env values contain. Supplying the true configuration name and MID today changes the refusal's *label* and nothing else.

### The placeholder trace, concretely

1. Placeholders are non-empty, so all three early refusals are skipped (`payment_readiness.py:236-248`).
2. `evaluate` calls the injected `fetch_configurations(expected_waba_id)`. On the checkout path that is `_fetch_payment_configurations` in `amplify/functions/ecommerce/checkout/handler.py:172-199`, which invokes `SENDER_FUNCTION` (`wecare-whatsapp-business-api:live`, confirmed live) with:

```python
    invoke_event = {
        "httpMethod": "GET",
        "path": "/wa-business/payment-config/raw",
        "queryStringParameters": {"wabaId": waba_id},
    }
```

3. **`/wa-business/payment-config/raw` has no branch in the business API.** The dispatcher routes `elif '/payment-config/check' in path:` (≈6101) and then `elif '/payment-config' in path:` (≈6119). `/payment-config/raw` substring-matches the *second*, which opens with:

```python
        elif '/payment-config' in path:
            phone_id = params.get('phoneId') or body.get('phoneId')
            if not phone_id:
                return _resp(400, {'error': 'phoneId required'})
```

   The invoke supplies only `wabaId`, so the answer is `400 {'error': 'phoneId required'}`.
4. `_fetch_payment_configurations` parses that body and returns `{'error': 'phoneId required'}`.
5. `evaluate` hits `if response.get("error"): return _blocked(META_UNAVAILABLE, "Meta returned an error for payment_configurations")`.
6. `checkout/handler.py` step 2 of `_create`: `if not readiness.ready:` → **HTTP 409 `{"status": "payment_unavailable", "readiness": "META_UNAVAILABLE"}`**, before any reference is reserved and before any attempt row is written.

So a placeholder produces a 409. So does the real value. **Neither can produce a charge, and neither can produce a pass.**

For completeness: even if someone "fixed" the fetcher by pointing it at the existing `/payment-config` route *with* a `phoneId`, `_get_payment_config` returns `{'paymentConfig': ..., 'liveReadiness': ...}` — no `data` key — and `evaluate` answers `META_UNAVAILABLE` on that too (`"payment configuration readback carried no data field"`). The only input that can produce `PAYMENT_READY` is a Graph response whose `data[]` holds a dict with `configuration_name` equal to the expected string, `status` `active`, `payment_gateway.type` `razorpay`, and `payment_gateway.merchant_id` equal to the expected MID. Nothing in this repository can synthesise that.

---

## 2. What the gate compares — code-evidenced

### 2.1 Live readback, not a non-empty check — but it is both, in that order

`evaluate` (`amplify/functions/shared/lambda_utils/payment_readiness.py:216-345`) does three distinct things:

**(a) Non-empty preconditions, which refuse rather than skip.**

```python
    if not expected_waba_id:
        return _blocked(CONFIGURATION_UNVERIFIED, "no expected WABA id was supplied")
    if not expected_configuration_name:
        return _blocked(CONFIGURATION_UNVERIFIED,
                        "no expected payment configuration name was supplied")
    if not expected_provider_mid:
        # Deliberately not a pass. The MID is the only thing tying the Meta configuration to
        # the Razorpay account we hold credentials for; without it, a configuration could point
        # at a different merchant and the money would land there.
        return _blocked(CONFIGURATION_UNVERIFIED, ...)
```

This is the state live today: both env values are `""` on `wecare-checkout:live` v5, so the current refusal is `CONFIGURATION_UNVERIFIED`.

**(b) A live readback, via an injected fetcher.** The module holds no Meta client and no credential by design — `fetch_configurations` is a required keyword argument. Its docstring states the rule the whole module exists to enforce: *"a constant in source code is not provider state… the absence of a readback is itself a refusal."*

**(c) Six comparisons against what Meta reports**, in order:

| Check | Code | Refusal |
|---|---|---|
| response is a dict | `if not isinstance(response, dict)` | `META_UNAVAILABLE` |
| no `error` key | `if response.get("error")` | `META_UNAVAILABLE` |
| `data` key present | `if configurations is None` | `META_UNAVAILABLE` ("an absent `data` key is not an empty list") |
| `data` is a list | `if not isinstance(configurations, list)` | `META_UNAVAILABLE` |
| `data` non-empty | `if not configurations` | `PAYMENT_CONFIG_MISSING` |
| name match | `str(c.get("configuration_name", "")) == expected_configuration_name` | `PAYMENT_CONFIG_NAME_UNKNOWN` |
| WABA match | `reported_waba != expected_waba_id` | `PAYMENT_CONFIG_WABA_MISMATCH` |
| status | `str(match.get("status","")).strip().lower() != "active"` | `PAYMENT_CONFIG_INACTIVE` |
| gateway | `gateway != expected_gateway` (`"razorpay"`) | `PAYMENT_CONFIG_INACTIVE` |
| MID present | `if not reported_mid` | `CONFIGURATION_UNVERIFIED` |
| MID match | `reported_mid != expected_provider_mid` | `RAZORPAY_MID_MISMATCH` |

### 2.2 Comparison semantics — exact, case-sensitive, no normalisation on our side

- **Configuration name:** `str(c.get("configuration_name", "")) == expected_configuration_name`. Byte-exact. No `.strip()`, no `.lower()`, no `.casefold()` on either side. A trailing space or a different case **fails**.
- **MID:** `reported_mid = str(gateway_block.get("merchant_id", "")).strip()` then `reported_mid != expected_provider_mid`. Meta's side is stripped; **ours is not**. So `EXPECTED_PROVIDER_MID` must be the bare identifier with no surrounding whitespace and **no prefix beyond the `acc_` that is part of the id itself**.
- **Status and gateway** are the only normalised comparisons: both `.strip().lower()`.
- **Source of truth for the MID:** `payment_gateway.merchant_id` from `GET /{waba-id}/payment_configurations`. Not a Razorpay API readback, and deliberately **not** a webhook `account_id` — the module's docstring records why: *"a webhook `account_id` is evidence of which account sent an event, not proof of which account the Meta configuration settles into."*

### 2.3 Fail-closed on error, timeout and credential failure — YES, every path

```python
    try:
        response = fetch_configurations(expected_waba_id)
    except Exception as error:  # noqa: BLE001 - any failure to read must block
        return _blocked(META_UNAVAILABLE,
                        f"could not read payment configurations: {type(error).__name__}")
```

A bare `except Exception` covers a Graph error, a timeout, a credential failure, a Lambda `FunctionError`, a JSON parse failure — all → `META_UNAVAILABLE`, which is a member of `BLOCKING_STATES`. `BLOCKING_STATES` is **enumerated, not derived from `!= PAYMENT_READY`**, so a new state cannot become permissive by being added without being classified. `PaymentReadiness.__bool__` returns `self.ready`, so `if not readiness:` blocks even if a caller forgets `.ready`.

The only env var in the module is `WA_PAYMENTS_DISABLED`, and it is one-directional: *"there is deliberately no env var that can turn readiness ON."* Pinned by `test_no_environment_variable_can_force_readiness` and `test_the_kill_switch_can_only_tighten`.

```
$ .venv/bin/python -m pytest -q tests/test_payment_readiness.py tests/test_checkout_gate_contract.py tests/test_checkout_handler.py
70 passed in 0.31s
```

**No CRITICAL fail-open finding. The gate's logic is sound. Its wiring is broken in the refuse direction only.**

### 2.4 One gate that is declared and never called

`evaluate_for_delivery` — the per-send check that a customer's 24-hour service window is open, or that an approved `ORDER_DETAILS` template exists — has **no production caller**:

```
$ grep -rn "evaluate_for_delivery" amplify/ | grep -v __pycache__
amplify/functions/shared/lambda_utils/payment_readiness.py:370:def evaluate_for_delivery(*,
amplify/functions/shared/lambda_utils/payment_readiness.py:506:    "evaluate_for_delivery",
```

`checkout/handler.py:202-208` calls `evaluate`, not `evaluate_for_delivery`. So nothing on the checkout path checks the service window or template approval. That matters for a live test: the function's own docstring notes the OTP is delivered by template and the code is typed on the web, which **opens no window**, so the common path may well need a template that was last measured as not existing.

---

## 3. The real values

### 3.1 Category first — both are identifiers, not credentials

This determines whether they may appear in this report at all, so it is settled before the values.

| Value | Category | Why |
|---|---|---|
| `EXPECTED_CONFIGURATION_NAME` | **Identifier.** Reportable in full. | It is a Meta configuration label that already sits in committed Python constants in three files and in four committed docs. `payment_readiness.as_dict()`'s own docstring: *"a configuration name, a WABA id and a merchant id are identifiers, not credentials."* |
| `EXPECTED_PROVIDER_MID` | **Identifier.** Reportable in full. | Already in the live Lambda environment of `wecare-whatsapp-business-api:live` v61 as `RAZORPAY_MID`, readable by any `GetFunctionConfiguration` caller, and in the **Description field** of a Secrets Manager entry (§3.4). |

Neither is a credential. `wecare/razorpay/api` holds the credential pair; the MID is the account label that pair belongs to.

### 3.2 `EXPECTED_CONFIGURATION_NAME` = `WECAREDIGITAL`

All recorded copies **agree**, and the agreement is on one string:

| Source | What it records |
|---|---|
| `amplify/functions/messaging/outbound-whatsapp/handler.py:402-405` — `PHONE_PAYMENT_GATEWAYS` | `PHONE_NUMBER_ID_1: {'razorpay': 'WECAREDIGITAL'}  # +919330994400 (WABA1)` and `PHONE_NUMBER_ID_2: {'razorpay': 'WECAREDIGITAL'}  # +919903300044 (WABA2)` |
| `amplify/functions/messaging/whatsapp-business-api/handler.py:3169-3174` — `_DECLARED_CONFIGS` | `{'name': 'WECAREDIGITAL', 'status': 'local_only', 'type': 'payment_gateway', 'gateway': 'razorpay', 'mid': _RAZORPAY_MID}` and `{'name': 'WECAREUPI', ..., 'type': 'upi', ...}` |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md:12-28` — the production-gate table | Four configurations reported **Active** by the owner on 2026-09-30: `WECAREDIGITAL` (razorpay, MID `acc_TTFSyolquKEZEy`) and `WECAREUPI` (`wecaredigitalbh511413.rzp@rxairtel`) on **both** WABAs, MCC `7392`, purpose `03` |
| `docs/whatsapp-experience-structure.md:377` | *"`WECAREDIGITAL` (PG) and `WECAREUPI` (VPA) — identical names on both WABAs"* |
| `payment_readiness.py` docstring | `WECAREDIGITAL` on WABA `2094615664435155` **and the same on** WABA `2513394156072604` |
| `config/lambda-env-manifest.json:100-101` | `"EXPECTED_CONFIGURATION_NAME": ""` — the manifest carries the **empty** seed, not the value |

Two retired names exist and must not be used: `WECARE-RAZOR-PAY` (`tests/test_payments.py:91`, commented *"retired 2026-08-23"*) and `Razorpay_ManishAgarwal` (steering, per `docs/compatibility.md:70`).

### 3.3 Which WABA — the ambiguity the steering warns about does not apply here

The steering warns that naming WABA2's configuration on a WABA1 message fails at Meta rather than at our validation. **That hazard is absent for this value, because the name is identical on both WABAs.** Every source above says so independently.

What does need stating:

- `wecare-checkout:live` v5 carries `PAYMENT_WABA_ID = 2094615664435155` (live-measured), which is **WABA1** (`WABA1_ID` default in `whatsapp-business-api/handler.py:88`, `# WECARE.DIGITAL (Direct API)`). It matches `config/lambda-env-manifest.json:103`. The readiness readback therefore asks WABA1 only.
- **`WECAREUPI` is the wrong value**, and it fails in a non-obvious place. It is `type: upi`, so Meta reports no `payment_gateway.type == 'razorpay'` for it; `evaluate` would answer `PAYMENT_CONFIG_INACTIVE` (`"gateway is '' , not 'razorpay'"`), not a name error. The razorpay-gateway configuration is `WECAREDIGITAL`.

**So: `EXPECTED_CONFIGURATION_NAME = WECAREDIGITAL`, correct for WABA1, and the same string would be correct for WABA2.**

### 3.4 `EXPECTED_PROVIDER_MID` = `acc_TTFSyolquKEZEy`, bare

Three independent live artefacts, none of which required reading a secret value:

1. **Live Lambda env**, `GetFunctionConfiguration` on `wecare-whatsapp-business-api:live` (v61, Active/Successful, LastModified `2026-10-02T04:09:40Z`): `RAZORPAY_MID = acc_TTFSyolquKEZEy`, `RAZORPAY_UPI_ID = wecaredigitalbh511413.rzp@rxairtel`.
2. **Secrets Manager metadata only** (`ListSecrets`, no value read): `wecare/razorpay/api` Description = `"LIVE Razorpay API credentials for WECARE.DIGITAL BHARATWORKS (acc_TTFSyolquKEZEy)"`. The credentialled account names itself in its own description.
3. `payment_readiness.py`'s resolution block records `acc_TTFSyolquKEZEy` as AUTHORITATIVE, confirmed by the owner against the live Meta dashboard on 2026-09-30, reversing the repo's earlier guess.

Retired account `acc_HDfub6wOfQybuH`: **zero occurrences tree-wide** (re-confirmed; `payment_readiness.py` now writes `[retired Razorpay account]` in prose).

**Form:** bare, exactly `acc_TTFSyolquKEZEy`. No prefix, no quotes, no whitespace — §2.2 shows our side of the comparison is not stripped.

### 3.5 The owner's Secrets Manager hint — resolved, and it does not need a secret read

`ListSecrets` (metadata only, 32 secrets) contains exactly one plausible holder:

| Name | ARN | Description | LastChanged |
|---|---|---|---|
| `wecare/meta/payments` | `arn:aws:secretsmanager:us-east-1:775261844268:secret:wecare/meta/payments-8L2LIa` | **"Meta WhatsApp Business payment configurations (WABA ids, gateway MID, UPI id) - no credentials"** | 2026-09-18T09:40:43Z |

No tags. **I did not read it.** Its own description says it holds no credentials and names exactly the three fields in question — which corroborates §3.1: these are identifiers filed in Secrets Manager as a durable record, not secret material.

Note the date: `2026-09-18`, which **predates** the 2026-09-30 MID correction. So it may still hold the retired MID. Treat it as a record to *confirm against*, not as a source to copy from blind.

### 3.6 By-reference injection — NOT available today, and here is the measurement

The sanctioned `{{resolve:secretsmanager:...}}` form cannot be used for these two values as the function is currently managed:

| Check | Result |
|---|---|
| `grep -rn "resolve:secretsmanager" amplify/ config/ scripts/` | **Zero** occurrences in `amplify/` or `config/`. Every hit is in a guard script (`block_inline_secrets.py:78`, `block_catastrophic.py:157`, `verify_secret_hook.py:62`) where it appears as an *allowed* pattern, never as a deployed dynamic reference. |
| Does a CloudFormation stack own `wecare-checkout`? | **No.** `ListStacks` returns **4** stacks total: `CDKToolkit`, `wecare-customer-sessions`, `wecare-home-fallback`, `wecare-workspace-mcp`. None owns the checkout function. |
| How is the live function managed? | `scripts/provision_checkout.py` via the Lambda API — `lam().create_function(..., Environment={"Variables": expected_environment()})` (:500) and `lam().update_function_configuration(FunctionName=FUNCTION_NAME, Environment={"Variables": current})` (:530-531). `amplify/infra/checkout.json` is a declaration-only template; its env block carries `"EXPECTED_CONFIGURATION_NAME": ""` / `"EXPECTED_PROVIDER_MID": ""` (:178-179). |
| Does `scripts/set_lambda_env_flag.py` support a reference? | **No.** `--set KEY=VALUE` is split on `=` and written literally (`merged[key] = value`). Literals only. |

**Consequence, stated plainly:** CloudFormation dynamic references resolve **only** inside CloudFormation. Passed through `update-function-configuration`, `{{resolve:secretsmanager:...}}` would be stored as that literal 60-character string, and §2.2's byte-exact comparison would then refuse it as a name/MID mismatch — fail-closed, but useless.

**This is not a blocker, because neither value is a credential.** The repo's actual by-reference pattern is to put the secret **name** in env and read lazily in the handler — `WIX_API_KEY_SECRET = wecare/wix/headless-api-key` on checkout v5, `RAZORPAY_SECRET_ID` on `wecare-secure-files`. That pattern exists for credentials. An identifier does not need it.

The recommendation to lead with is therefore different from the one the hint anticipated: **put the two values in `provision_checkout.py::expected_environment()` and let the provisioning script own them**, rather than typing them into `set_lambda_env_flag.py --set`. Reasons: (a) the script already has a `READINESS_KEYS` carve-out that only *adds* these keys when absent and never clobbers an operator-set value (:516-523), so the two mechanisms are designed to coexist; (b) the value then lives in reviewed source instead of a shell invocation; (c) `scripts/block_inline_secrets.py` would **not** block either value on a command line anyway — no issuer prefix, and `EXPECTED_*` matches none of its `*SECRET*` / `*TOKEN*` / `*API_KEY*` assignment patterns — so the guard is not what stops this, judgement is.

### 3.7 What is UNDETERMINED

**The string is known. Meta's current state is not.** The repository holds two directly contradictory records from the same day:

| Record | Claim |
|---|---|
| `payment_readiness.py:7` | `GET /{2094615664435155}/payment_configurations -> HTTP 200, ZERO configurations` (2026-09-30) |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md:12-28` | Owner restored four configurations, all **Active**, on both WABAs (2026-09-30) — explicitly *"Recorded from the owner's dashboard readout, not re-probed by this session"* |

`docs/compatibility.md:63` still says *"`WECAREDIGITAL` and `WECAREUPI` currently exist only as Python constants."*

I could not resolve this, by rule: the only read path needs the Meta system-user token from `wecare/meta-system-user-token`, and I may not read it or put it on a command line.

**Exact owner action that supplies it — and it needs no env change and no deploy:**

```
GET https://wecare.digital/api/wa-business/payment-config/check?wabaId=2094615664435155
    (admin-authenticated; the route exists live and already calls Meta)
```

`_check_payment_gateway` (`whatsapp-business-api/handler.py:3253+`) performs the real Graph read and returns, per configuration, `name`, `status`, `gateway`, `mid`, `mcc`, `purposeCode` and `canReceivePayments`. The owner needs to report four fields and nothing else: **the configuration `name`, its `status`, its `gateway`, and its `mid`.** None of those is a credential. If `name == WECAREDIGITAL`, `status == active`, `gateway == razorpay` and `mid == acc_TTFSyolquKEZEy`, then both expected values are confirmed against the live provider and §3.2/§3.4 become measurements rather than records.

**Do not set either value before that readout.** A wrong name is worse than an empty one — empty fails closed at a known state, wrong fails at Meta in front of a customer who has already tapped Pay.

---

## 4. Everything else gating a completable purchase

Ordered by where a customer hits it. "Reached first" is the refusal a signed-in customer would actually see **today**.

| # | Gate | Live state (measured) | Class |
|---|---|---|---|
| 1 | **Customer sign-in** | **DONE.** `3ce4936b fix(auth): derive customer session identity from the Cognito sub` is merged; `customer_id_from_attributes` now returns the Cognito `sub` and `custom:customer_id` is gone from the code path. `wecare-customer-session:live` is **v6**, LastModified `2026-10-02T09:07:57Z`, after that commit. `DescribeUserPool us-east-1_46ULYuukt` confirms the attribute still is not in the schema (only `custom:partner_waba_id`) and all three `CUSTOM_AUTH` triggers are intact. **Not end-to-end verified** — that needs one live OTP round trip, which this task does not authorise. | **done** (code), owner-only to verify |
| 2 | **Cart V2 with no address loader — THE REFUSAL REACHED FIRST** | `WIX_CART_V2_ENABLED=true` is **live on `wecare-checkout:live` v5** and on `wecare-wix-store:live` v34 (measured; the prior report said absent everywhere). `cart_v2.is_enabled()` therefore returns True, so `_create` takes the `_v2_snapshot` branch, which opens `loader = LOAD_OWNED_ADDRESS` — a module constant hard-set to `None` at `checkout/handler.py:143` — and raises `purchase_intent.DeliveryDetailsRequired`. Result: **409 `DELIVERY_DETAILS_REQUIRED` on every create, before readiness is consulted at all.** | **code-fixable** (wire the profile address loader) or operator (unset the flag to fall back to Checkout V1) |
| 3 | **Readiness readback route** | `/wa-business/payment-config/raw` is unimplemented → `400 phoneId required` → `META_UNAVAILABLE`. §1. | **code-fixable** |
| 4 | **The two expected values** | `EXPECTED_CONFIGURATION_NAME=""`, `EXPECTED_PROVIDER_MID=""` on v5. Strings known (§3.2, §3.4); Meta's live state UNDETERMINED (§3.7). | **owner-only** |
| 5 | **`CHECKOUT_INITIATION_ENABLED`** | Read in exactly **one** place: `amplify/functions/ecommerce/checkout/handler.py:123-124`. **Absent** from `wecare-checkout:live` v5's nine env keys. Accepting values: `1`, `true`, `yes`, `on` (lower-cased, stripped). **Correction to the brief:** it is *not* read by `wecare-whatsapp-business-api` — `grep -rn CHECKOUT_INITIATION_ENABLED amplify/` returns only the checkout handler plus docstrings in `redemption.py`, `website_checkout.py`, `blog_contribution.py` and `amplify/infra/checkout.json`. **What it enables:** the single `_send_order_details` call. With it absent, `_create` returns `200 PAYMENT_INITIATION_DISABLED` *after* writing the attempt row. **Can turning it on charge a real customer? Yes in principle, no in practice today** — it would send a real Meta `order_details` to a real handset, which is a payable message; but gates 2, 3 and 6 all refuse before and after it, so the send cannot currently happen. | **owner decision** |
| 6 | **In-chat send path is a 404** | `_send_order_details` posts `path="/wa-business/messages/send/interactive-payment"`. `_route_send_message` tests nine suffixes (`/text`, `/template`, `/media`, `/interactive`, `/flow`, `/contacts`, `/location`, `/product(s)`, `/request-contact-info`) and ends `return _resp(404, {'error': f'Unknown send path: {path}'})`. `interactive-payment` matches none, so `_send_order_details` returns False → **502 `SEND_FAILED`**. | **code-fixable** |
| 7 | **Service window / template never checked** | `evaluate_for_delivery` has no production caller (§2.4). `wecare-secure-files:live` v22 carries `WA_PAY_TEMPLATE=wecare_pay`; `payment_readiness.py` records this WABA holding only `wecare_otp` at Meta as of 2026-09-30, unverified since. | **code-fixable** + **owner-only** (template approval) |
| 8 | **Website Razorpay Standard Checkout** | Still no production caller. `website_checkout.py` is imported only by `customer_receipt.py` and `redemption.py` (neither deployed); in `checkout/handler.py` it appears only in two docstrings (:58, :331). Browser half absent: `grep -rn "new Razorpay\|checkout.razorpay.com\|window.Razorpay" src/` → **no matches** at `32b632e3`. | **code-fixable**, large |
| 9 | **Customer receipt has no route** | The 364-route enumeration of API `zllr9lrg7j` contains four commerce routes and no receipt route: `POST /ecommerce/checkout`, `POST /ecommerce/checkout/status`, `POST /ecommerce/customer-session`, `POST /razorpay-webhook`. All four report `AuthorizationType: NONE` with handler-level `require_auth` as the control. | **code-fixable**, not purchase-blocking |
| 10 | **Wix order write-back** | `finalization.py` has no importer. Flags unset. **Should stay off for a first live test** — an internal paid order commits first, and a write-back failure would add a second failure mode to the one thing being measured. | **leave off** |
| 11 | **Gift cards / coupons — NOT REACHABLE, and this de-risks the decision** | `ListFunctions` returns 69; no `wecare-gift-cards`, `wecare-coupons` or `wecare-wix-giftcard-spi`. `ListTables` returns 82; no `GiftCardsTable` or `CouponsTable`. No routes. **Decisively: `gift_card_store` is not in the checkout import closure.** `checkout/handler.py:88-89` imports `cart_v2, customer_cart, order_keys, payment_attempt, purchase_intent` — no `gift_card_store`, no `finalization`, no `redemption`. The only handler importing the gift-card store is `ecommerce/wix-giftcard-spi/handler.py`, which is not deployed. **So the `redeem()`/`void()` double-move cannot be triggered on the ordinary checkout path with gift cards absent.** | **not blocking**; keep the open HIGH |
| 11a | The double-move defect itself, for the record | Still **open** at HEAD. `review.json` at `180e180e` is `CHANGES_REQUESTED` with REV-6 (HIGH): the applied-move marker closes the reproduced window, then `_drop_applied_marker` deletes it and re-opens the same double-move under a different interleaving. `gift_card_store.py:1248-1251` still shows `_decrement` → `_mark_settled` → `_drop_applied_marker`. Must close before provisioning, not after. | code-fixable, **not** on the critical path |
| 12 | Razorpay webhook + signature verification | `POST /razorpay-webhook` → `wecare-razorpay-webhook:live` **v47**, Active/Successful. Carried forward from the prior report (401 `Invalid signature` on an unsigned body); not re-probed here. | **done** |
| 13 | Zero transactions, ever | `DescribeTable` today: `PaymentAttemptsTable` **0**, `OrderTable` **0**, `PaymentsTable` **0**, `WixOrderIds` **0**, `CustomerSessionsTable` **0**, `InvoicesTable` **0**, `WixOrdersCache` **0**. Customer pool holds **1** user. | context |

**Count the independent refusals between a signed-in customer and a charge: four (rows 2, 3, 4, 6), two of which are code defects rather than deliberate gates.** The two expected values are not the last thing standing — they are the third of four.

---

## 5. Minimum-risk live test

### 5.1 Recommended route — and it starts with zero money at risk

**Stage A, today, no env change, no deploy, owner-runnable:** call the existing admin route `GET /wa-business/payment-config/check?wabaId=2094615664435155` and report `name`, `status`, `gateway`, `mid` (§3.7). It already performs the real Graph read. This resolves the only genuinely UNDETERMINED value in this report and settles the 2026-09-30 contradiction. **If it reports zero configurations, every downstream plan changes and no code fix is worth writing yet.**

**Stage B, code-only, nothing enabled:** fix rows 2, 3 and 6 of §4 — wire `LOAD_OWNED_ADDRESS` (or unset `WIX_CART_V2_ENABLED` to fall back to V1), add a `raw` branch to the business API (or repoint the fetcher at `/payment-config/check` and parse `gatewayChecks`), and add an `interactive-payment` suffix to `_route_send_message`. All three are local, reversible, test-covered work with the gates still off.

**Stage C, readiness proven with no payable message:** set the two expected values **with `CHECKOUT_INITIATION_ENABLED` still absent**. `_create` then runs the real Meta readback and returns either `200 PAYMENT_INITIATION_DISABLED` (readiness passed — the single strongest piece of evidence available without spending money) or `409` naming the exact blocking state. **Zero charge risk: the payable message is a separate gate and it is off.**

Note the one cost of Stage C, which `provision_checkout.py` itself warns about at :977-982: with readiness satisfied and initiation off, an authenticated `create` reaches a live Wix write and persists a `PaymentAttempt` row **before** the flag refuses. So Stage C leaves Wix carts and attempt rows behind. That is accounting litter, not money.

**Stage D, one real charge, only if the owner decides:** see §5.3.

### 5.2 Razorpay test mode — supported in code, unusable for the in-chat path

The codebase **does** understand a test key pair. `integrations/razorpay_orders.py:130-141`:

```python
def account_mode(key_id: str) -> str:
    """`test` or `live`, inferred from the key id prefix Razorpay documents.
    `rzp_test_` is test mode; `rzp_live_` is live. The mode is persisted on the binding so a
    callback or a reconciliation can refuse a result produced under a different mode than the one
    the order was created in — a test-mode success must never settle a live-mode order.
    """
```

**But it cannot be used for the WhatsApp in-chat path, and the reason is structural.** On that path Meta collects the money against the MID on the *Meta payment configuration*, which is the live `acc_TTFSyolquKEZEy`. Making it test mode would require either:

- a second Meta payment configuration pointing at a test MID — a **payment-configuration mutation**, prohibited for the agent and owner-only at Meta; or
- replacing `wecare/razorpay/api` with a test pair — a **credential mutation**, prohibited, and it would break signature verification for live deliveries while in place.

Then `EXPECTED_PROVIDER_MID` would have to change to the test MID too, or `RAZORPAY_MID_MISMATCH` refuses. So test mode is not a shortcut here.

**Test mode IS the right answer for the website Standard Checkout path**, which does not involve Meta at all: `razorpay_orders.create_order` + the browser modal, keyed on `public_key_id()`. But §4 row 8 shows that path has no production caller and no browser half, so there is nothing to test yet. **If the owner's real goal is a safe live checkout test, building the website path with a test key pair is the lower-risk destination** — it is more work and far less exposure than charging a real card through the in-chat path.

### 5.3 A single controlled in-chat transaction — feasibility only

Feasible in principle, to the owner-nominated QA recipient **+918100640044** (`.kiro/steering/02-qa-recipient.md`; India, not a business number, passes the self-messaging backstop). **A live send is not authorised by this task and needs a separate owner decision.**

Preconditions, all of them:

1. Stage A confirms the configuration is Active with the expected MID.
2. Stages B and C complete and readiness measured `PAYMENT_READY`.
3. `CHECKOUT_INITIATION_ENABLED=true` on `wecare-checkout`, published, alias moved.
4. The customer's 24-hour window open, or `wecare_pay` APPROVED at Meta — nothing currently checks either (§2.4).
5. Amount: **100 paise (₹1)**, the minimum chargeable Razorpay leg this repo already encodes (`gift_card_store.RAZORPAY_MIN_LEG_PAISE = 100`).

**What could go wrong, honestly:**

- **A real customer could be affected while the flag is on.** `POST /ecommerce/checkout` is `AuthorizationType=NONE` at the gateway with `require_auth` in the handler as the only control, and **there is no WAF in front of this account any more** (both web ACLs deleted 2026-09-28). Any signed-in customer who reaches checkout during the window gets a real payable message. The pool holds one user today, which bounds but does not remove this.
- **Money left somewhere is owner-only to reverse.** Refund is a **standing refusal** for the agent. ₹1 captured must be refunded by the owner from the Razorpay dashboard, or written off. The repo has a `/wa-business/payment-refund` route; the agent must not call it.
- **Two paths can fail after the money moves.** A capture that cannot be reconciled lands in `PAID_BUT_BLOCKED_OUTCOMES`, where `customer_may_retry` is hard-coded `False` — so the money is taken and the customer sees no retry. That is the correct direction, and it is also the state a human has to clear.
- **Carried forward, not re-verified:** a prior audit (C4) found nothing writes `providerPaymentId` / `providerOrderId` at initiation while `razorpay_verify` requires one of them. If that is still true, a real capture cannot reconcile and Stage D produces a charge with no order. **Verify C4 before Stage D.** I did not re-trace it.

### 5.4 The honest recommendation

**Do not switch the gates on now.** Run Stage A today — it costs nothing, risks nothing, and it is the only step that resolves a value no amount of code reading can supply. Then Stages B and C, which prove readiness with a zero-charge outcome. Only consider Stage D after C4 is re-verified, and prefer building the website path with a Razorpay test key pair over charging a real card in-chat.

---

## 6. Rollback

Every lever, with its measured mechanism and expected time.

| Lever | Exact action | Time | Notes |
|---|---|---|---|
| **Kill readiness outright (one key, cannot be argued with)** | `WA_PAYMENTS_DISABLED=true` on `wecare-checkout` | ~1 min | `payment_readiness.py:198` `_KILL_SWITCH`. Checked **first** in `evaluate`, before every other input, and can only tighten. Blocks regardless of the other two values. The fastest safe stop. |
| **Turn initiation off** | `python scripts/set_lambda_env_flag.py --set CHECKOUT_INITIATION_ENABLED=false --functions wecare-checkout --apply` | ~1-2 min | `false` is not in the truthy set, so it reads as off. The script reads-merges-writes (never a bare `--environment` replace), waits for `Active`, verifies no key was lost, then **publishes a version and moves the `live` alias** — required, because the HTTP API invokes `:live`. |
| **Revert the expected values** | same script, `EXPECTED_CONFIGURATION_NAME=` / `EXPECTED_PROVIDER_MID=` to empty | ~1-2 min each | Restores `CONFIGURATION_UNVERIFIED`. `provision_checkout.py` will not clobber an operator-set value in either direction (`READINESS_KEYS` carve-out, :516-523). |
| **Roll the whole function back** | `aws lambda update-alias --function-name wecare-checkout --name live --function-version 5` | **seconds** | v5 is the current live version and is the rollback target for anything published after it. This reverts code **and** the environment baked into that version. |
| **Before-state snapshot** | written automatically by `set_lambda_env_flag.py` to `docs/execution/snapshots/lambda-env-before-<key>-<stamp>.json` before any write | — | Includes the full prior variable map and the prior `live` version per function. |

A warm-sandbox caveat that does **not** bite here: `INITIATION_ENABLED` is read at module scope (`handler.py:123`), so a value change would be invisible to a warm environment — but `update-function-configuration` recycles execution environments, and publishing a new version guarantees cold ones. Moving the alias is what makes it reach production.

**Rollback is fast and complete. That is the one genuinely reassuring thing in this report.**

---

## 7. What I could not determine

Stated explicitly. An honest unknown beats a confident invention.

1. **Whether Meta currently holds `WECAREDIGITAL` Active on WABA `2094615664435155` with MID `acc_TTFSyolquKEZEy`.** The decisive unknown. Two contradictory 2026-09-30 records (§3.7). Needs the owner-run Graph read; the only path requires the Meta token, which I may not touch.
2. **The contents of `wecare/meta/payments`.** Not read, by rule. Name, ARN, Description and LastChanged reported instead. Its `2026-09-18` LastChanged predates the MID correction, so it may hold the retired value.
3. **Whether live Lambda bytes equal `HEAD` byte-for-byte.** Inferred, not measured, from commit times against `LastModified`: the business-API handler's last commit is `27a3fb5d` at 2026-10-02 09:34 IST (04:04 UTC) and v61 was built at 04:09:40 UTC, so v61 includes it; the checkout handler's last commit is `089ba325` at 06:51 IST (01:21 UTC) and v5 was built at 09:08:03 UTC, so v5 includes it. Proving it needs a build, which this brief forbids.
4. **I did not invoke the business-API Lambda to re-reproduce the `400 phoneId required`.** The claim rests on the code trace in §1 plus two prior recorded live invocations (`docs/execution/first-deep-audit-20261001-codex.md:38`, `.agents/tasks/section68-current-state-audit-20261001.md:555-560`). The exact inert check, if the orchestrator wants it first-hand: invoke `wecare-whatsapp-business-api:live` with `{"httpMethod":"GET","path":"/wa-business/payment-config/raw","queryStringParameters":{"wabaId":"2094615664435155"}}` — it refuses on the missing `phoneId` before any Graph call or write.
5. **Whether `wecare_pay` is APPROVED at Meta.** Same token constraint. `wecare-secure-files:live` v22 carries `WA_PAY_TEMPLATE=wecare_pay`; the last measurement said only `wecare_otp` exists.
6. **Whether prior finding C4 is still open** — nothing writing `providerPaymentId`/`providerOrderId` at initiation while `razorpay_verify` requires one. Not re-traced. **This is the one carried-forward item that could turn a real charge into an unreconcilable one, so it must be re-verified before any Stage D.**
7. **Whether a signed Razorpay webhook has ever been processed successfully.** Carried forward unresolved; `order_paid` and `payment_captured` were both 0 events in the prior window, and `OrderTable`/`PaymentsTable` are still 0 today.
8. **End-to-end sign-in.** The fix is merged and deployed (v6), but no live OTP round trip was performed, so "sign-in works" is a code-and-deploy claim, not a measured one.
9. **Frontend behaviour.** No vitest run, no browser measurement. Claims about `src/` rest on reading source and `grep`.
10. **Concurrency caveat.** Other sessions are live. `git status --short` at measurement showed only `.agents/` report and review files modified or untracked — no commerce source file was dirty. This document is the only file I created.

---

*Read-only throughout. No AWS mutation, no git write, no deploy, no payment, no message, no secret value. Every count, version, env value, route and table figure above is quoted from a command run in this session; where it is carried forward from an earlier report or inferred, the row says so.*
