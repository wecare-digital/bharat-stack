# Implementation Plan — resolve the checkout DEPLOYMENT gap

Provision `wecare-checkout`, its `/ecommerce/*` routes on HTTP API `zllr9lrg7j`, and scoped
IAM, with `CHECKOUT_INITIATION_ENABLED` absent (initiation OFF), then verify the live contracts.

---

## What I measured (all re-derived live, 2026-10-01, account 775261844268 / us-east-1)

| Fact | Measured value |
|---|---|
| Caller identity | `arn:aws:iam::775261844268:user/wecare-admin` |
| `wecare-checkout` function | `ResourceNotFoundException` — absent |
| `wecare-checkout-role` | `NoSuchEntity` — absent |
| Routes on `zllr9lrg7j` | **359** total, **0** matching `ecommerce` |
| `POST https://wecare.digital/api/ecommerce/checkout` | **404** `{"message":"Not Found"}` |
| `POST .../api/ecommerce/checkout/status` | **404** `{"message":"Not Found"}` |
| `POST https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/ecommerce/checkout` | **404** — API-Gateway-level, confirms the Amplify `/api/*` rewrite already reaches the API |
| `GET https://wecare.digital/cart` | **301** → `/cart/` → **200** (cart renders; checkout is the missing half) |
| `wecare-razorpay-webhook` `live` alias | **v45** |
| `wecare-whatsapp-business-api` `live` alias | **v57** (the `SENDER_FUNCTION` target exists) |
| `stack-wecare-digital-PaymentAttemptsTable` | ACTIVE, key `paymentAttemptId` |
| `stack-wecare-digital-WixOrderIds` | ACTIVE, key `orderId` — matches `order_keys` default `key_attr="orderId"` |
| `git rev-parse origin/stack` | `315c53cfbfe09f8144c91610bd74d89a429f30ea` |
| `git rev-parse HEAD` | `98b62a1ee769c322d020c620ebfe8d0cd4ffa20a` |
| `HEAD...origin/stack` | **4 ahead, 8 behind** — local HEAD does not contain the reviewed checkout commits |
| Working tree | 38 dirty entries across three other sessions |

The `HEAD` / `origin/stack` divergence is the decisive reason to package from the archive:
`customer_session.py`, `checkout_pricing.py`, `website_checkout.py`, `order_keys.py`,
`razorpay_orders.py` and `customer_receipt.py` exist **only** on `origin/stack`. A package built
from the working tree would ship a handler whose siblings are missing or stale.

### What `scripts/provision_checkout.py` ALREADY does (13,837 bytes, byte-identical at HEAD and `origin/stack`)

- Creates IAM role `wecare-checkout-role` with `AWSLambdaBasicExecutionRole` plus one inline
  policy `CheckoutLeastPrivilege`: `secretsmanager:GetSecretValue` on
  `wecare/wix/headless-api-key-*`; `dynamodb:GetItem|PutItem|UpdateItem` on exactly the two
  tables above (no `DeleteItem`, deliberate); `lambda:InvokeFunction` on
  `wecare-whatsapp-business-api` and its `:live` alias. No Cognito permission — correct, because
  `customer_auth` calls `cognito-idp:GetUser` with the **customer's own** access token.
- Creates log group `/aws/lambda/wecare-checkout` with 30-day retention.
- Creates the function: `python3.12`, handler `handler.handler`, timeout 20s, memory 256 MB,
  tags, and an environment that **deliberately omits** `CHECKOUT_INITIATION_ENABLED` and leaves
  `EXPECTED_CONFIGURATION_NAME` / `EXPECTED_PROVIDER_MID` empty.
- `reconcile_environment` adds/repairs only the keys it owns and never clobbers an
  operator-set `CHECKOUT_INITIATION_ENABLED`.
- Publishes v1 and creates the initial `live` alias — for this function only.
- `--dry-run` and `--verify` modes; `--verify` fails if `CHECKOUT_INITIATION_ENABLED` is truthy.
- Packages `handler.py` plus every `*.py` under `amplify/functions/shared/lambda_utils`, so all of
  `website_checkout.py`, `razorpay_orders.py`, `checkout_pricing.py`, `order_keys.py`,
  `payment_attempt.py`, `order_creation.py`, `customer_session.py`, `payment_status.py` land in
  the ZIP. I verified all 14 required modules exist at `origin/stack`. **No templates are
  needed** — `customer_receipt.py` formats values for the invoice engine and reads no template
  file; the only non-`.py` file under `shared/` is `config.ts`, which is irrelevant to Python.

### The exact gaps (what it does NOT do, or does wrong)

| # | Gap | Evidence |
|---|---|---|
| **G1** | **Creates zero API Gateway routes or integrations.** `zllr9lrg7j` is never mentioned in the script. This alone is the 404. | `grep -c zllr9lrg7j scripts/provision_checkout.py` = 0 |
| **G2** | **Never calls `lambda:AddPermission`**, so API Gateway could not invoke the function even if a route existed. `provision_missing_ui_routes.py:134-149` records the exact failure mode: a function-level statement does not authorise an **alias** invoke, producing a 500 with no Lambda log line. |
| **G3** | **`ROOT` is hard-wired to `parents[1]`**, so it can only package the live dirty tree. There is no way to package reviewed bytes from a clean snapshot. |
| **G4** | **No import validation before create.** `deploy_all_lambdas.py` calls `get_function_configuration` *before* `validate()` (lines ~708-730); for an absent function it takes the `awaiting_provisioning` branch and `continue`s. So `--dry-run` **cannot** validate `wecare-checkout` today — the validator only becomes usable *after* the function exists. |
| **G5** | **`config/lambda-env-manifest.json` has zero mentions of `wecare-checkout`.** |
| **G6** | **No IaC** under `amplify/` declares the function, its routes or its role. |
| **G7** | `--verify` checks env and the gate but never asserts the routes exist or that the integration points at `:live`. |

### Three findings that change what the plan can promise

1. **The gate-off response is NOT reachable by an unauthenticated probe.** `handler` calls
   `customer_auth.require_customer(event)` first and returns an opaque 401. Then `_create` calls
   Wix, *then* the readiness gate, and only *then* returns `PAYMENT_INITIATION_DISABLED`. With
   `EXPECTED_CONFIGURATION_NAME` / `EXPECTED_PROVIDER_MID` empty, `payment_readiness.evaluate`
   returns `CONFIGURATION_UNVERIFIED` → **409 `payment_unavailable`**, which short-circuits before
   the `PAYMENT_INITIATION_DISABLED` branch. So the honest, verifiable live contract change is
   **404 → 401**, and `PAYMENT_INITIATION_DISABLED` is reachable only with a real customer token
   *and* owner-supplied readiness values. The plan verifies what is actually true and says so.
2. **The website Razorpay path is present in the ZIP but NOT wired into the handler.** At
   `origin/stack` the handler mentions `website_checkout` and `razorpay_orders` only in its
   docstring; its sole top-level imports are `customer_auth`, `payment_readiness`,
   `order_keys`, `payment_attempt`, `wix_ecom`, `logging`, `response`. `_action` dispatches only
   `create` and `status`. Wiring it is the open **owner architecture decision** from the original
   request, so this plan deliberately does not wire it.
3. **`ConditionCheckItem` does not apply to this path.** `order_keys` uses `put_item` /
   `update_item` with `ConditionExpression` only — no `TransactWriteItems`, no
   `ConditionCheckItem`. And checkout gets its **own** role `wecare-checkout-role`, not the
   shared `wecare-digital-lambda-role` where the implicitDeny was measured. The plan still
   includes an explicit detection-and-report step rather than assuming.

### Design decisions I am making (no design doc existed)

- **D1 — add `--source-root` to `provision_checkout.py` rather than copying the script.** The
  script must *run* from the live tree (it is an owned path and the committed fix belongs there)
  but must *package* bytes from the `origin/stack` archive. A `--source-root` flag is one
  argument and keeps exactly one copy of the script. Rejected: running the archive's copy, which
  would mean maintaining the fix in two places.
- **D2 — reuse `deploy_all_lambdas.build_zip` + `validate` inside the provisioner** instead of
  its private `_zip_package`. This closes G4 at the right place: validation happens *before*
  `create_function`, and the two scripts can no longer drift into producing different ZIPs for
  the same function. `deploy_all_lambdas.py` itself is **not** modified.
- **D3 — route keys are `POST /ecommerce/checkout` and `POST /ecommerce/checkout/status`.** Read
  off the consumers: `src/pages/cart.tsx:79` `${API_BASE}/ecommerce/checkout` POST with a Bearer
  token, and `src/pages/checkout/status.tsx:63,156` `${API_BASE}/ecommerce/checkout/status` POST.
  `_action` resolves `status` via `path.endswith("/status")`, so both land correctly. No
  `{proxy+}` — two explicit routes keep the surface exactly as wide as its two consumers.
- **D4 — integrate the `live` alias, not `$LATEST`,** matching the 58 aliased functions and the
  `lambda-snapstart-deploy` steering, and grant `AddPermission` with `Qualifier="live"` (G2).
- **D5 — do NOT grant `secretsmanager:GetSecretValue` on `wecare/razorpay/api`.**
  `razorpay_orders.RAZORPAY_SECRET_ID` defaults to that name, but nothing in the deployed
  handler's reachable code calls it (finding 2). Granting a Razorpay credential read to a
  function that cannot use it widens privilege for zero benefit. Recorded as the prerequisite
  grant for when the owner confirms the website architecture.
- **D6 — rely on API-level CORS for preflight.** `zllr9lrg7j` has a `CorsConfiguration`
  (`AllowOrigins` includes `https://wecare.digital`; `AllowHeaders` includes `authorization`),
  which HTTP APIs answer without an `OPTIONS` route. Probe it; add explicit `OPTIONS` routes
  only if the probe fails.
- **D7 — keep `provisioned_by` set on the checkout `Spec`.**
  `tests/test_deploy_map_provisioning.py` asserts the static spec map, including
  `test_exactly_one_spec_is_awaiting_provisioning`. Those tests describe the *spec table*, not
  live AWS, and must keep passing unchanged after provisioning.

---

## Plan

- [ ] 1. Create the clean source snapshot and record the deployed revision.
      `mkdir -p .scratch/deploy-checkout && git archive origin/stack | tar -x -C .scratch/deploy-checkout/`,
      then `git rev-parse origin/stack` and write the SHA to
      `.agents/tasks/checkout-deployment-20261001/deployed-revision.txt`. Do NOT `merge`,
      `rebase`, `reset` or `stash` in the live tree.
      Files: `.scratch/deploy-checkout/` (gitignored), `.agents/tasks/checkout-deployment-20261001/deployed-revision.txt`
      Verify: `test -f .scratch/deploy-checkout/amplify/functions/ecommerce/checkout/handler.py` and
      `test -f .scratch/deploy-checkout/amplify/functions/shared/lambda_utils/ecommerce/website_checkout.py`
      both succeed; the recorded SHA equals `315c53cf...`; `git status --short | wc -l` is still 38
      (the archive touched nothing tracked).

- [ ] 2. Snapshot the full rollback state BEFORE any mutation.
      Write four files: the complete route list
      (`aws apigatewayv2 get-routes --api-id zllr9lrg7j --max-results 1000 --region us-east-1`),
      the complete integration list (`get-integrations`), the captured
      `ResourceNotFoundException` for `wecare-checkout` plus `NoSuchEntity` for
      `wecare-checkout-role` as the documented "absent" baseline, and the current
      `wecare-digital-lambda-role` inline policy name list. Each file states the route/integration
      count in a header comment so a later diff is a single number.
      Files: `docs/execution/snapshots/checkout-routes-before-20261001.json`,
      `checkout-integrations-before-20261001.json`,
      `checkout-function-absent-before-20261001.json`,
      `checkout-shared-role-before-20261001.json`
      Verify: all four files exist and parse — `.venv/bin/python -c "import json,glob;[json.load(open(p)) for p in glob.glob('docs/execution/snapshots/checkout-*-before-20261001.json')]"` exits 0;
      the route snapshot reports exactly 359 items and zero `ecommerce` route keys.

- [ ] 3. Close G3 and G4 in `scripts/provision_checkout.py`: add `--source-root` and
      pre-create import validation.
      Add `--source-root PATH` (default: repo root) that re-points `FUNCTION_DIR` / `SHARED_DIR`.
      Replace `_zip_package()` with a call into `deploy_all_lambdas.build_zip` + `validate` for
      the `wecare-checkout` Spec, resolved against the source root, and make `--dry-run` run that
      validation and print the packaged file count, byte size and base64 sha256 — so an
      unresolved import fails **before** `create_function` rather than after. Do not modify
      `deploy_all_lambdas.py`.
      Files: `scripts/provision_checkout.py`
      Verify: `.venv/bin/python scripts/provision_checkout.py --dry-run --source-root .scratch/deploy-checkout`
      prints a non-zero packaged file count, zero import errors, and `would create` for role,
      function and alias; it must upload nothing and exit 0.

- [ ] 4. Close G1, G2 and G7: add additive route provisioning to the provisioner.
      Port the proven pattern from `scripts/provision_missing_ui_routes.py:134-205` — alias-qualified
      `add_permission` (`Qualifier="live"`, `Principal="apigateway.amazonaws.com"`,
      `SourceArn=arn:aws:execute-api:us-east-1:775261844268:zllr9lrg7j/*/*`), reuse-or-create one
      `AWS_PROXY` integration with `PayloadFormatVersion="2.0"` pointing at
      `...function:wecare-checkout:live`, then `create_route` for `POST /ecommerce/checkout` and
      `POST /ecommerce/checkout/status`. Creation must be idempotent (skip any route key already
      present) and must never delete or modify an existing route or integration. Extend `--verify`
      to assert both route keys exist and resolve to the `:live` integration.
      Files: `scripts/provision_checkout.py`
      Verify: `.venv/bin/python scripts/provision_checkout.py --dry-run --source-root .scratch/deploy-checkout`
      reports both route keys as `would create` and names no other route; add
      `tests/test_provision_checkout_contract.py` (step 10) asserting the route-key list, the
      alias qualifier, and that `CHECKOUT_INITIATION_ENABLED` is absent from
      `expected_environment()` — run `.venv/bin/python -m pytest tests/test_provision_checkout_contract.py`.

- [ ] 5. Detect and REPORT the `ConditionCheckItem` question rather than widening any role.
      Add a check to `--verify` that simulates the checkout role's DynamoDB actions
      (`iam simulate-principal-policy` on `dynamodb:ConditionCheckItem`, `PutItem`, `UpdateItem`,
      `GetItem` against both table ARNs) and prints the verdict per action. If
      `ConditionCheckItem` is `implicitDeny` **and** a reachable code path needs it, the script
      must print a `REQUIRED GRANT` line naming the exact statement and exit non-zero — it must
      never add the permission itself, and must never touch `wecare-digital-lambda-role`.
      Files: `scripts/provision_checkout.py`
      Verify: after step 6, `.venv/bin/python scripts/provision_checkout.py --verify` prints the
      four per-action verdicts; given `order_keys` uses only `put_item`/`update_item` with
      `ConditionExpression`, the expected outcome is "ConditionCheckItem implicitDeny — not
      required by any reachable path" and exit 0.

- [ ] 6. Provision additively: role, log group, function (python3.12), env, v1, initial `live`
      alias — for `wecare-checkout` ONLY.
      Run `.venv/bin/python scripts/provision_checkout.py --source-root .scratch/deploy-checkout`.
      Do NOT run `scripts/deploy_all_lambdas.py` without a target argument. Move no other
      function's alias. `CHECKOUT_INITIATION_ENABLED` must remain absent from the environment.
      Files: none in the repo (AWS-side: `wecare-checkout`, `wecare-checkout-role`,
      `/aws/lambda/wecare-checkout`, 1 integration, 2 routes)
      Verify: `.venv/bin/python scripts/provision_checkout.py --verify` exits 0 and prints
      `initiation: OFF (expected)`; `aws lambda get-alias --function-name wecare-checkout --name live --region us-east-1`
      returns `FunctionVersion=1`; `aws lambda get-function-configuration --function-name wecare-checkout --region us-east-1 --query 'Environment.Variables'`
      shows no `CHECKOUT_INITIATION_ENABLED` key and empty `EXPECTED_CONFIGURATION_NAME` /
      `EXPECTED_PROVIDER_MID`; `aws apigatewayv2 get-routes --api-id zllr9lrg7j --max-results 1000 --region us-east-1 --query 'length(Items)'`
      returns **361** (359 + 2) and no pre-existing route key changed against the step-2 snapshot.

- [ ] 7. Confirm the packaged bytes match production using the now-usable import validator.
      With the function present, `deploy_all_lambdas.py` reaches `validate()`. Run it against the
      single target from inside the archive so it compares reviewed bytes to what is live.
      Files: none
      Verify: `cd .scratch/deploy-checkout && /Users/wecaredigital/wecare-store/.venv/bin/python scripts/deploy_all_lambdas.py wecare-checkout --dry-run`
      reports zero `ERROR:` lines and `would not update: sha matches live` — proving every
      top-level import resolves inside the package and that the live code is exactly `315c53cf`'s.

- [ ] 8. Register the function in `config/lambda-env-manifest.json` (G5).
      Add a `wecare-checkout` entry listing the env keys the provisioner owns
      (`PAYMENT_ATTEMPTS_TABLE`, `COMMERCE_KEYS_TABLE`, `WIX_API_KEY_SECRET`, `WIX_SITE_ID`,
      `SENDER_FUNCTION`, `PAYMENT_WABA_ID`, `EXPECTED_CONFIGURATION_NAME`,
      `EXPECTED_PROVIDER_MID`), matching the shape of the neighbouring entries. Record
      `CHECKOUT_INITIATION_ENABLED` as an explicitly-absent, owner-only flag. No secret value
      goes in this file — secret **names** only.
      Files: `config/lambda-env-manifest.json`
      Verify: `.venv/bin/python -c "import json;d=json.load(open('config/lambda-env-manifest.json'));assert 'wecare-checkout' in d['functions']"`
      exits 0; `.venv/bin/python -m pytest tests/ -k "manifest or env_manifest"` passes.

- [ ] 9. Declare the function, routes, integration and role in IaC under `amplify/` (G6), so the
      live change is reproducible rather than script-only.
      Follow whatever construct style the existing `amplify/` checkout-adjacent resources use
      (read it first; do not introduce a new IaC flavour). The declaration must encode: runtime
      `python3.12`, the two route keys, the alias-qualified integration, the inline
      least-privilege policy from step 6, and `CHECKOUT_INITIATION_ENABLED` as absent.
      Files: IaC under `amplify/` for the checkout function/routes/IAM (do **not** touch
      `amplify/functions/payments/razorpay-webhook/handler.py`,
      `amplify/functions/shared/lambda_utils/ecommerce/order_creation.py`, `finalization.py`
      or `initiation.py` — other sessions own them)
      Verify: the project's IaC synth/typecheck for the touched package passes, and a synth diff
      shows only additive checkout resources.

- [ ] 10. Add tests pinning the deployment contract.
      `tests/test_provision_checkout_contract.py`: the exact two route keys and no more; the
      integration target is alias-qualified `:live`; `add_permission` passes `Qualifier="live"`;
      `expected_environment()` contains no `CHECKOUT_INITIATION_ENABLED` and leaves both
      `EXPECTED_*` empty; the IAM policy grants no `dynamodb:DeleteItem`, no Cognito action, and
      no `secretsmanager` resource other than the Wix key (pins D5); the policy names only the two
      known table ARNs. `tests/test_checkout_package_completeness.py`: the built ZIP contains
      `handler.py` plus every module the checkout path can reach —
      `lambda_utils/ecommerce/{website_checkout,checkout_pricing,order_keys,payment_attempt,order_creation,customer_receipt}.py`,
      `lambda_utils/integrations/razorpay_orders.py`,
      `lambda_utils/{customer_session,customer_auth,payment_readiness,payment_status,wix_ecom}.py`.
      Files: `tests/test_provision_checkout_contract.py`,
      `tests/test_checkout_package_completeness.py`
      Verify: `.venv/bin/python -m pytest tests/test_provision_checkout_contract.py tests/test_checkout_package_completeness.py tests/test_checkout_handler.py tests/test_deploy_map_provisioning.py tests/test_payment_vocabulary_at_decision_points.py tests/test_checkout_pricing.py`
      — all pass, with `test_deploy_map_provisioning.py` unchanged (D7).

- [ ] 11. Verify the live contracts with REAL HTTP probes, and record the honest result.
      Run and capture every one of these:
      (a) `curl -s -o /dev/null -w '%{http_code}' -X POST https://wecare.digital/api/ecommerce/checkout -H 'content-type: application/json' -d '{"action":"create","lineItems":[]}'`
      → expect **401** (was 404). The 404→401 flip is the real deliverable.
      (b) same for `.../api/ecommerce/checkout/status` with `{}` → expect **401**.
      (c) the direct API host `https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/ecommerce/checkout`
      → expect **401**, proving the route resolves at the API and not only through Amplify.
      (d) `curl -i -X OPTIONS .../api/ecommerce/checkout -H 'Origin: https://wecare.digital' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: authorization,content-type'`
      → expect 2xx with `access-control-allow-origin: https://wecare.digital` (D6). If this
      fails, add `OPTIONS /ecommerce/checkout` and `OPTIONS /ecommerce/checkout/status` routes
      and re-probe.
      (e) `aws lambda invoke --function-name wecare-checkout:live --payload` an `OPTIONS` event
      → 200. This is the packaging proof: a cold start executes every top-level import, so a
      missing module surfaces here as an `Unable to import module` error.
      (f) `aws lambda invoke --function-name wecare-checkout:live` with a `POST` event carrying no
      `Authorization` header → the opaque 401 body, proving `customer_auth` and its lazy
      `boto3.client('cognito-idp')` load.
      (g) `aws logs tail /aws/lambda/wecare-checkout --since 10m` → confirm only
      `checkout_*` event names and opaque ids; assert **no** phone number, amount-with-identity,
      or credential-shaped material. Never echo a secret into the report.
      (h) `aws apigatewayv2 get-stage --api-id zllr9lrg7j --stage-name '$default'` → `AutoDeploy`
      true, so the new routes are already served.
      (i) re-run `.venv/bin/python scripts/provision_checkout.py --verify` → exit 0, initiation OFF.
      Write every probe and its response code to an "after" snapshot.
      Files: `docs/execution/snapshots/checkout-routes-after-20261001.json`,
      `docs/execution/snapshots/checkout-live-probes-after-20261001.json`
      Verify: (a), (b) and (c) all return 401; (e) returns 200; the after-route snapshot reports
      361 routes with exactly the two new keys added and none removed. If any probe returns 500,
      stop — per `provision_missing_ui_routes.py:134-141` that signature means the alias invoke
      permission is missing, and step 4's `Qualifier="live"` must be re-checked before anything
      else.

- [ ] 12. S3 bag-icon provenance (last, independent of everything above).
      `public/icons/shopping-bag.svg` is committed and already served at
      `https://wecare.digital/icons/shopping-bag.svg` (probed: **200**);
      `src/components/HeaderCart.tsx:22` records that the committed copy exists "for upload to the
      media" bucket. Upload it to the **existing** bucket `wecare-digital-get` under the public
      `o/` root — compose the key through `amplify/functions/shared/lambda_utils/media_paths.py`
      (`media_paths.public(...)`), never by hand, and never create a new bucket. Record the
      resulting CDN URL and the object's sha256 as provenance.
      Files: `docs/execution/snapshots/checkout-bag-icon-provenance-20261001.json`
      Verify: `aws s3api head-object --bucket wecare-digital-get --key <composed key>` returns
      the object, and `curl -s -o /dev/null -w '%{http_code}' <media_paths.public_url(key)>`
      returns 200 with `content-type: image/svg+xml`.

- [ ] 13. Write the single dated closure document and commit by explicit path with `--only`.
      `docs/execution/checkout-deployment-20261001.md` must carry: the deployed source revision
      `315c53cf...`; the before/after table (function absent → v1/`live`; routes 359 → 361;
      `/api/ecommerce/checkout` 404 → 401); every probe from step 11 with its code; the exact
      rollback procedure (`delete-route` ×2 by RouteId, `delete-integration`, `delete-alias live`,
      `delete-function wecare-checkout`, `delete-role-policy` + `delete-role wecare-checkout-role`
      — each requiring pointwise confirmation under `block-catastrophic`'s `DESTRUCTIVE_AWS`
      table); the four snapshot paths; and the three findings above stated plainly — that
      `PAYMENT_INITIATION_DISABLED` needs a customer token plus owner-supplied readiness values,
      that the website Razorpay path ships in the ZIP but is **not wired** into the handler
      pending the owner's architecture decision, and that `secretsmanager:GetSecretValue` on
      `wecare/razorpay/api` is the prerequisite grant for that path and was deliberately not
      given. Also record the `razorpay_orders._cached` warm-sandbox credential cache: it is a
      request-time read (not module-scope, so it does not break the documented init-time rule)
      but a rotation still needs `scripts/refresh_secret_consumers.py wecare/razorpay/api`.
      Then stage and commit the owned paths only:
      `git add <new files> && git commit --only <all owned paths> -F <message-file>` — the index
      is dirty with three other sessions' work, so `--only` is mandatory, not optional. Then
      `git push origin stack`.
      Files: `docs/execution/checkout-deployment-20261001.md`, plus the owned paths from steps
      3-12
      Verify: `git show --stat HEAD` lists only the owned paths and none of the 38 foreign dirty
      entries; `git status --short | wc -l` shows the other sessions' files still unstaged;
      `.venv/bin/python -m pytest tests/test_provision_checkout_contract.py tests/test_checkout_package_completeness.py tests/test_checkout_handler.py tests/test_deploy_map_provisioning.py tests/test_payment_vocabulary_at_decision_points.py`
      passes on the committed tree.

---

## Guardrails this plan encodes

- **Nothing becomes payable.** `CHECKOUT_INITIATION_ENABLED` is never set; both `EXPECTED_*`
  readiness inputs stay empty, so `payment_readiness` blocks independently of the flag; the
  website path is not wired; no capture, refund or payment-configuration mutation appears
  anywhere. Step 10's tests pin all of it.
- **No secret on a command line, in argv, or in a log.** Only secret *names* appear
  (`wecare/wix/headless-api-key`, `wecare/razorpay/api`). No
  `secretsmanager get-secret-value`/`batch-get-secret-value` in any step. Step 11(g) explicitly
  asserts the log output carries no credential-shaped material.
- **Integer paise only.** `checkout_pricing` is `Decimal`/`ROUND_HALF_UP` throughout with
  integer-paise results (verified at `origin/stack`); `wix_ecom.authoritative_total_paise`
  refuses a non-whole-paise total rather than rounding.
- **Payment vocabulary.** Zero raw `'captured'` literals in the handler, `website_checkout.py`
  or `razorpay_orders.py`; `tests/test_payment_vocabulary_at_decision_points.py` runs in steps
  10 and 13.
- **Additive only.** No existing route, integration, alias or function is modified or deleted.
  `deploy_all_lambdas.py` is only ever invoked with the single target `wecare-checkout` and
  `--dry-run`. No WAF, no Security Hub, no DNS/MX/MTA-STS/SPF/DMARC, no Cognito call of any
  kind (so no `UpdateUserPool` full-replace hazard), no new S3 bucket.
- **Other sessions untouched.** Every DO-NOT-TOUCH path stays out of the diff, the live working
  tree is never merged/rebased/reset/stashed, and the commit uses `--only` against a dirty
  shared index.
