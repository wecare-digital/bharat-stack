# Website checkout provisioning runbook (2026-10-01)

> STATUS: BLOCKED-ON-ENVIRONMENT. Not executed.
>
> This document is a runbook only. Nothing in it has been run. The sandbox has
> no AWS credentials: `aws sts get-caller-identity` fails, there is no `~/.aws`
> and no `wecare-prod` profile. Every live operation below (provision, upload,
> alias checkpoint, live monetary test) is reported BLOCKED-ON-ENVIRONMENT and
> must be run by an authorized operator once credentials arrive through the
> sandbox environment, never from a key pasted into chat.

## Scope and safety rules (read before anything)

- **Account / profile / region:** account `775261844268`, profile `wecare-prod`,
  region `us-east-1`. Every command below assumes
  `--profile wecare-prod --region us-east-1`.
- **A chat-pasted AWS key must never be used, stored or echoed.** The only
  acceptable credential source is the sandbox environment / a configured
  `wecare-prod` profile.
- **Secrets are referenced, never read.** Never call
  `secretsmanager get-secret-value`, never print a secret value. Use
  `{{resolve:secretsmanager:...}}` references and ARN-scoped IAM only.
- **WAF and Security Hub are out of scope** for this runbook.
- **Any Cognito change goes through `scripts/cognito_pool_safe_update.py`.**
  Direct `UpdateUserPool` is a full replace with a recorded trigger-deletion
  incident, so it is never called by hand. This runbook does not change Cognito;
  if a rotation decision ever touches an app client, that script is the only
  mechanism.
- **The initiation gate stays DISABLED.** No step here sets
  `CHECKOUT_INITIATION_ENABLED`, and the readiness inputs
  `EXPECTED_CONFIGURATION_NAME` / `EXPECTED_PROVIDER_MID` remain empty, so
  `payment_readiness` keeps checkout from ever reaching a live charge.
- **`_routes.json` is a dated inventory snapshot, not runtime config.** Nothing
  reads it. Routes live in the AWS HTTP API (apigatewayv2). Do not edit
  `_routes.json` as if it were configuration, and do not reuse a stale API id
  (for example `zllr9lrg7j`): rediscover the current id every time.
- **Git workflow:** single branch `stack`. Commit directly to `stack`,
  explicit-path staging only, no push and no PR (the orchestrator pushes).

### How to confirm the environment blocker is cleared

Run this first. Until it prints the expected account, every section stays
blocked:

```sh
aws sts get-caller-identity --profile wecare-prod --region us-east-1
# expect: "Account": "775261844268"
```

---

## Section 1: `wecare-checkout` function, `/ecommerce/*` routes, and IAM

The function, its least-privilege role, a published version and the `live` alias
are already defined by `scripts/provision_checkout.py`
(`FUNCTION_DIR = amplify/functions/ecommerce/checkout`). That script deliberately
leaves `CHECKOUT_INITIATION_ENABLED` absent and `EXPECTED_CONFIGURATION_NAME` /
`EXPECTED_PROVIDER_MID` empty, so the gate stays DISABLED. Normal code updates
after first provision go through `scripts/deploy_all_lambdas.py wecare-checkout`.

The two website endpoints the routes must target are the handlers in
`amplify/functions/shared/lambda_utils/ecommerce/website_checkout.py`:
`prepare_checkout` (the `/ecommerce/prepare-checkout` endpoint) and
`verify_callback` (the `/ecommerce/verify-callback` endpoint).

### Ordered operator commands

1. **Rediscover the current HTTP API id.** Never reuse a stale id.

   ```sh
   aws apigatewayv2 get-apis --profile wecare-prod --region us-east-1 \
     --query "Items[?Name=='wecare'] || Items[].{Name:Name,ApiId:ApiId,Endpoint:ApiEndpoint}"
   ```

   Record the resolved id and export it for the rest of the section:

   ```sh
   API_ID=<the id printed above>
   ```

2. **Dry-run the provisioner** and read the plan before changing anything:

   ```sh
   AWS_PROFILE=wecare-prod AWS_REGION=us-east-1 \
     .venv/bin/python scripts/provision_checkout.py --dry-run
   ```

   Confirm the output reads `initiation: OFF (CHECKOUT_INITIATION_ENABLED not set)`.

3. **Apply** the provisioner (creates role, log group, function, published
   version, `live` alias; sets the env from `expected_environment()`):

   ```sh
   AWS_PROFILE=wecare-prod AWS_REGION=us-east-1 \
     .venv/bin/python scripts/provision_checkout.py
   ```

4. **Verify** the provisioner's own read-back:

   ```sh
   AWS_PROFILE=wecare-prod AWS_REGION=us-east-1 \
     .venv/bin/python scripts/provision_checkout.py --verify
   # expect: "initiation: OFF (expected)" and
   #         "checkout provisioning verified (initiation disabled)"
   ```

5. **Attach the least-privilege IAM for the website data paths.** The
   `provision_checkout.py` role already covers logs, the Wix API key secret by
   reference, the payment-attempts and commerce-keys tables, and invoke of the
   WhatsApp business Lambda. The website path additionally reads the
   commerce-keys and invoices tables and the Razorpay API secret by ARN (no
   wildcard, scoped to `wecare/razorpay/api`). Write the policy file first:

   `checkout-website-leastpriv.json`
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "CommerceKeysAndInvoices",
         "Effect": "Allow",
         "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
         "Resource": [
           "arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-WixOrderIds",
           "arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-PaymentAttemptsTable",
           "arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-InvoiceTable"
         ]
       },
       {
         "Sid": "ReadRazorpayApiKeyByArn",
         "Effect": "Allow",
         "Action": ["secretsmanager:GetSecretValue"],
         "Resource": [
           "arn:aws:secretsmanager:us-east-1:775261844268:secret:wecare/razorpay/api-*"
         ]
       }
     ]
   }
   ```

   > Confirm the exact invoices table name with
   > `aws dynamodb list-tables --profile wecare-prod --region us-east-1`
   > before applying; adjust the `InvoiceTable` ARN above to the live name. The
   > secret ARN keeps the trailing `-*` that Secrets Manager appends as the
   > random suffix; it is scoped to the one secret, not a wildcard namespace.

   ```sh
   aws iam put-role-policy --profile wecare-prod --region us-east-1 \
     --role-name wecare-checkout-role \
     --policy-name CheckoutWebsiteLeastPrivilege \
     --policy-document file://checkout-website-leastpriv.json
   ```

6. **Add the two `/ecommerce/*` routes and their integrations** to the current
   HTTP API, each targeting the `live` alias of `wecare-checkout`. Create the
   integration, grant the alias-qualified invoke permission BEFORE the route is
   reachable (a function-level statement does not authorize an alias invoke; the
   failure mode is a 500 with no Lambda log line), then create the route.

   ```sh
   ALIAS_ARN=arn:aws:lambda:us-east-1:775261844268:function:wecare-checkout:live

   # prepare-checkout
   PREP_INT=$(aws apigatewayv2 create-integration --profile wecare-prod --region us-east-1 \
     --api-id "$API_ID" --integration-type AWS_PROXY \
     --integration-uri "$ALIAS_ARN" --payload-format-version 2.0 \
     --query IntegrationId --output text)

   aws lambda add-permission --profile wecare-prod --region us-east-1 \
     --function-name wecare-checkout --qualifier live \
     --statement-id apigw-prepare-checkout \
     --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
     --source-arn "arn:aws:execute-api:us-east-1:775261844268:$API_ID/*/*/ecommerce/prepare-checkout"

   aws apigatewayv2 create-route --profile wecare-prod --region us-east-1 \
     --api-id "$API_ID" --route-key "POST /ecommerce/prepare-checkout" \
     --target "integrations/$PREP_INT"

   # verify-callback
   CB_INT=$(aws apigatewayv2 create-integration --profile wecare-prod --region us-east-1 \
     --api-id "$API_ID" --integration-type AWS_PROXY \
     --integration-uri "$ALIAS_ARN" --payload-format-version 2.0 \
     --query IntegrationId --output text)

   aws lambda add-permission --profile wecare-prod --region us-east-1 \
     --function-name wecare-checkout --qualifier live \
     --statement-id apigw-verify-callback \
     --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
     --source-arn "arn:aws:execute-api:us-east-1:775261844268:$API_ID/*/*/ecommerce/verify-callback"

   aws apigatewayv2 create-route --profile wecare-prod --region us-east-1 \
     --api-id "$API_ID" --route-key "POST /ecommerce/verify-callback" \
     --target "integrations/$CB_INT"
   ```

### Environment variables to set

Set only by `provision_checkout.py` via `expected_environment()`:
`PAYMENT_ATTEMPTS_TABLE`, `COMMERCE_KEYS_TABLE`, `WIX_API_KEY_SECRET`,
`WIX_SITE_ID`, `SENDER_FUNCTION`, `PAYMENT_WABA_ID`.

Left intentionally empty / unset so the gate stays DISABLED:

- `CHECKOUT_INITIATION_ENABLED`: unset (absent). Do not set it.
- `EXPECTED_CONFIGURATION_NAME`: empty string.
- `EXPECTED_PROVIDER_MID`: empty string.

With these empty, `payment_readiness` returns `CONFIGURATION_UNVERIFIED` and
`website_checkout.prepare_checkout` returns `PAYMENT_INITIATION_DISABLED`: no
gateway order, no payable attempt.

### Verification reads

```sh
aws lambda get-function --profile wecare-prod --region us-east-1 \
  --function-name wecare-checkout

aws lambda get-alias --profile wecare-prod --region us-east-1 \
  --function-name wecare-checkout --name live
# record the FunctionVersion it points at (needed for rollback)

aws apigatewayv2 get-routes --profile wecare-prod --region us-east-1 --api-id "$API_ID" \
  --query "Items[?contains(RouteKey, '/ecommerce/')].{RouteKey:RouteKey,Target:Target}"
```

Confirm neither live env carries `CHECKOUT_INITIATION_ENABLED` set to a truthy
value (the `--verify` mode already fails loudly if it does).

### Rollback

Move the alias back to the prior published version recorded above:

```sh
aws lambda update-alias --profile wecare-prod --region us-east-1 \
  --function-name wecare-checkout --name live \
  --function-version <PRIOR_VERSION>
```

To back out the routes, delete the routes then their integrations:

```sh
aws apigatewayv2 delete-route --profile wecare-prod --region us-east-1 \
  --api-id "$API_ID" --route-id <ROUTE_ID>
aws apigatewayv2 delete-integration --profile wecare-prod --region us-east-1 \
  --api-id "$API_ID" --integration-id <INTEGRATION_ID>
```

### Unblock actions

- **AWS credentials via the sandbox environment** (not chat). Confirm with
  `aws sts get-caller-identity --profile wecare-prod --region us-east-1`
  returning account `775261844268`.
- Confirm the invoices table name is correct before applying the IAM policy:
  `aws dynamodb list-tables --profile wecare-prod --region us-east-1`.

---

## Section 2: S3 bag-icon upload and CDN URL

The bag icon is a public storefront UI asset, so it belongs under the public
root, not the gated `secure/` root. `amplify/functions/shared/lambda_utils/media_paths.py`
defines the contract: `PUBLIC_ROOT = "o/"`, bucket `wecare-digital-get`,
`CDN_DOMAIN = "wecare.digital/get"`. `public(*parts)` composes the key and
`public_url(key)` builds the apex URL. For a UI icon the composed key is
`public("stream/media/ui", "bag-icon.svg")` which yields
`o/stream/media/ui/bag-icon.svg`, and `public_url(...)` yields
`https://wecare.digital/get/o/stream/media/ui/bag-icon.svg`.

> Do not upload here (no credentials). Command and expected URL only. Confirm the
> exact filename and sub-prefix the frontend references before running, so the
> uploaded key matches what the storefront requests.

### Command (operator, once credentials exist)

```sh
aws s3 cp ./bag-icon.svg \
  s3://wecare-digital-get/o/stream/media/ui/bag-icon.svg \
  --profile wecare-prod --region us-east-1 \
  --content-type image/svg+xml --cache-control "public, max-age=86400"
```

Equivalent `put-object` form:

```sh
aws s3api put-object --profile wecare-prod --region us-east-1 \
  --bucket wecare-digital-get --key o/stream/media/ui/bag-icon.svg \
  --body ./bag-icon.svg --content-type image/svg+xml \
  --cache-control "public, max-age=86400"
```

### Expected CDN URL

```
https://wecare.digital/get/o/stream/media/ui/bag-icon.svg
```

This matches `public_url("stream/media/ui/bag-icon.svg")`: the public key sits
under `o/`, served through the single CloudFront distribution on
`wecare.digital/get`. The key is NOT placed under `secure/` (that root is gated
at the edge and would 302), and it is NOT written to the bucket root (which still
serves 200 and would silently diverge from the composed key).

### Verification (HEAD)

```sh
# object exists in the bucket under the public prefix
aws s3api head-object --profile wecare-prod --region us-east-1 \
  --bucket wecare-digital-get --key o/stream/media/ui/bag-icon.svg

# served publicly through the CDN (expect HTTP/2 200, content-type image/svg+xml)
curl -sI https://wecare.digital/get/o/stream/media/ui/bag-icon.svg
```

### Rollback

```sh
aws s3api delete-object --profile wecare-prod --region us-east-1 \
  --bucket wecare-digital-get --key o/stream/media/ui/bag-icon.svg
```

### Unblock actions

- **AWS credentials via the sandbox environment.** Confirm with
  `aws sts get-caller-identity --profile wecare-prod --region us-east-1`.
- The final `bag-icon.svg` artifact and its exact storefront-referenced path, so
  the uploaded key matches the requested key.

---

## Section 3: Pre-deploy alias checkpoint across the ~60 Lambdas

The HTTP API invokes the `live` alias of each function, and
`scripts/deploy_all_lambdas.py` + `scripts/snapstart_publish.py` move those
aliases. Moving an alias back one version is a single call; undoing an
`update_function_code` on `$LATEST` means rebuilding and re-uploading a package
that may no longer exist. So before any fleet deploy, snapshot every function's
current `live` target version, and keep that snapshot as the one-command
rollback source. This is the recorded-incident mitigation: a Cognito
`UpdateUserPool` is a full replace that once deleted triggers, and an unqualified
`$LATEST` cutover changes mid-flight; the alias model plus this checkpoint is how
a regressing deploy is reversed without a rebuild.

### Snapshot every live alias target BEFORE deploying

```sh
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
CHECKPOINT="docs/execution/alias-checkpoint-${STAMP}.tsv"

aws lambda list-functions --profile wecare-prod --region us-east-1 \
  --query "Functions[].FunctionName" --output text | tr '\t' '\n' | sort \
| while read -r FN; do
    VER=$(aws lambda get-alias --profile wecare-prod --region us-east-1 \
            --function-name "$FN" --name live \
            --query FunctionVersion --output text 2>/dev/null)
    if [ -n "$VER" ] && [ "$VER" != "None" ]; then
      printf '%s\t%s\n' "$FN" "$VER" >> "$CHECKPOINT"
    fi
  done

wc -l "$CHECKPOINT"   # expect roughly 60 function:version pairs
```

The dated `alias-checkpoint-<STAMP>.tsv` is the authoritative pre-deploy state.
Commit it alongside the deploy for an auditable record.

### Verify the checkpoint is complete

```sh
# every recorded version is still a resolvable alias target
while IFS=$'\t' read -r FN VER; do
  CUR=$(aws lambda get-alias --profile wecare-prod --region us-east-1 \
          --function-name "$FN" --name live --query FunctionVersion --output text)
  printf '%s\t%s\t%s\n' "$FN" "$VER" "$CUR"
done < "$CHECKPOINT"
```

### One-command rollback (restore every alias from the checkpoint)

```sh
while IFS=$'\t' read -r FN VER; do
  aws lambda update-alias --profile wecare-prod --region us-east-1 \
    --function-name "$FN" --name live --function-version "$VER" \
    && echo "restored $FN -> v$VER"
done < "$CHECKPOINT"
```

After a rollback, confirm fleet health with the existing differential checker:

```sh
AWS_PROFILE=wecare-prod AWS_REGION=us-east-1 \
  .venv/bin/python scripts/post_deploy_health.py
```

> Alias safety note: never repoint a route integration to `$LATEST` to "undo" a
> deploy, and never hand-run `UpdateUserPool`. Alias moves are the only reversible
> cutover; Cognito changes go through `scripts/cognito_pool_safe_update.py`.

### Unblock actions

- **AWS credentials via the sandbox environment.** Confirm with
  `aws sts get-caller-identity --profile wecare-prod --region us-east-1`.
- The checkpoint must be taken immediately before the deploy it protects; a stale
  checkpoint restores stale versions.

---

## Section 4: Authorized cancel-only live monetary test to +918100640044

> NEVER agent-executed. BLOCKED-ON-ENVIRONMENT.
>
> This is a live test against the real payment provider. It is performed only by
> an authorized human operator with explicit owner sign-off, only after AWS
> credentials and provider access exist. The agent must never run it, and no live
> result is fabricated. The design keeps money from being retained: the smallest
> possible order is created, driven through the website callback, then cancelled
> or refunded so nothing settles.

### Preconditions (all must hold)

- Owner sign-off recorded for a live cancel-only verification to `+918100640044`.
- `aws sts get-caller-identity` succeeds for `wecare-prod`.
- Provider (Razorpay) live access available to the operator out of band; secret
  values are never printed and never placed on a command line.
- Note: the initiation gate stays DISABLED for normal operation. This test is a
  deliberate, owner-authorized, time-boxed exception run by a human; it is not a
  change to the deployed gate configuration and must be returned to the disabled
  baseline immediately after.

### Minimal steps for the authorized operator

1. Create the smallest gateway order (the minimum provider-accepted INR amount,
   integer paise) through the owner-authorized checkout path for the test
   customer bound to `+918100640044`.
2. Drive the website callback (`/ecommerce/verify-callback`) with the
   provider-returned `razorpay_payment_id|razorpay_order_id|razorpay_signature`,
   exactly as the browser would relay them. The handler re-verifies the HMAC
   against the server-stored order id and still requires the authenticated
   captured-payment readback.
3. **Immediately cancel or refund** so no money is captured or retained: if the
   payment is not yet captured, cancel the order; if a capture occurred, issue a
   full refund at once. The goal is zero settled value.

### Reads to confirm no settled payment remains

- Confirm no captured, unrefunded payment exists for the test order via the
  authoritative provider readback the backend already uses
  (`lambda_utils/integrations/razorpay_verify`), driven through an operator read,
  not a fabricated result.
- Confirm the account ledger / payments view shows the order as cancelled or
  fully refunded with net zero retained.
- Confirm no order was created on our side: checkout creates no order, and an
  order exists only after `razorpay-webhook` reconciliation verifies a capture;
  a cancelled or refunded attempt must leave only the PaymentAttempt evidence,
  no settled order.

### Rollback / cleanup

The test is self-reversing by design (cancel/refund is the final step). If a
refund is pending, track it to completion and re-confirm net zero before closing
the test. Return the function to its disabled-gate baseline and verify with
`scripts/provision_checkout.py --verify`.

### Unblock actions

- **Owner authorization** for the live cancel-only test to `+918100640044`,
  recorded before any step is run.
- **AWS credentials via the sandbox environment.** Confirm with
  `aws sts get-caller-identity --profile wecare-prod --region us-east-1`.
- **Wix publication** of the storefront so the website checkout path is live
  end to end for the test.
- Provider (Razorpay) live access for the operator, handled out of band with no
  secret value printed.
