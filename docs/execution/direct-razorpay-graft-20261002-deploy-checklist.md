# Deployment checklist — the direct-Razorpay money grafts

Authored 2026-10-03. **No step below was executed.** This is the whole distance between the
committed code and a first payment, assembled in one place so it is read here rather than
discovered halfway through.

Enabling a live-payment flag is a **standing refusal** for the agent under
`.kiro/steering/01-standing-authorization.md`, so the one step that turns payments on is marked
OWNER-ONLY and was never attempted.

No credential, key id or secret value appears in this file.

---

## The fact that matters most, and it is independent of the gate

**`POST /ecommerce/verify-callback` does not exist on API `zllr9lrg7j`.** The browser's payment
return posts to a route that is not there, so **none of the five grafts can run at all in the
current deployment** — flag or no flag. `scripts/provision_checkout.ROUTE_KEYS` has held all four
route keys since the website path landed; `amplify/infra/checkout.json` declared only two until
this change, and the live API carries only `POST /ecommerce/checkout`,
`POST /ecommerce/checkout/status` and `POST /ecommerce/customer-session`.

That is why step 1 is a provisioner run and not a flag.

## The nine ordered steps

| # | Who | Step | The measured fact that makes it necessary |
|---|---|---|---|
| 1 | AGENT | `python scripts/provision_checkout.py` | creates the 2 missing routes and their 2 invoke permissions, and sets `ORDERS_TABLE`, `CONTACTS_TABLE` and `RAZORPAY_SECRET_ID` — all three absent from the live function's environment |
| 2 | AGENT | `python scripts/provision_customer_profile.py` | `wecare-customer-profile` does not exist (`ResourceNotFoundException`). Without it a shopper cannot create the verified CRM row step 6 requires |
| 3 | AGENT | `python scripts/provision_email_verification.py` | `wecare-email-verification` does not exist, and it is the **only** writer of the `wecare/otp/pepper` secret, which is `ResourceNotFoundException` today. The pepper is generated in-process with `secrets.token_urlsafe(48)` and is never printed, never passed on a command line, and never logged |
| 4 | AGENT | `python scripts/deploy_all_lambdas.py wecare-checkout wecare-customer-profile wecare-email-verification` | `$LATEST` does not serve: `wecare-checkout` is invoked through its `live` alias |
| 5 | AGENT | `python scripts/snapstart_publish.py` | publishes a version and moves `live` off **v5**. Without it the API keeps serving the old code whatever `update-function-code` did |
| 6 | OWNER | confirm a shopper can satisfy `PROFILE_REQUIRED` | `_checkout_profile` requires a Contacts row carrying `checkoutCustomerId == identity.customer_id`, a non-empty `email` **and** `emailVerifiedAt`. Until one exists every prepare answers `409 PROFILE_REQUIRED` — a correct fail-closed refusal, not a defect |
| 7 | **OWNER-ONLY** | set `CHECKOUT_INITIATION_ENABLED=true` on `wecare-checkout` | a live-payment flag. **Standing refusal for the agent.** `provision_checkout.py --verify` reports the gate being on as a problem, by design |
| 8 | AGENT | publish a version and move `live` again | an environment change does not reach the alias until a new version is published. Step 7 without step 8 changes nothing a customer can see |
| 9 | OWNER | first payment | — |

Steps 1–5 and 8 all fall inside the standing grant's `A3_PRODUCTION` class — additive routes,
tightening IAM, `update-function-code`, publish, move alias — and need no confirmation. **Nobody
ran them as part of authoring this change.** They are listed so the owner can see the whole
distance, not so an implementer closes it.

## What the first payment will and will not do

All four `wix_writeback.is_enabled()` conditions stay false. Only `WIX_SITE_ID` is set live, and
nothing in this change or this checklist touches `WIX_WRITEBACK_ENABLED`,
`WIX_ECOM_WRITE_CONFIRMED` or `WIX_CART_V2_WRITE_CONTRACT`. So:

**Live after step 8:**

- **Graft 1a** — the cart guard refuses a second payable order for a basket that is already paid,
  under two independent identities, and every payable Razorpay modal has the three cart rows
  written behind it before the browser sees it.
- **Graft 1b** — the cart page latches once the payment rail has returned a result, and offers a
  link to `/orders/` instead of a live CTA.
- **Graft 2** — the amount recorded to Wix is the **verified Razorpay leg**, not the order total,
  and a one-paise tender disagreement fails closed with the internal order record still written.
- **Graft 4** — the `PAYREF#` reference join, so the webhook and the browser return converge on
  one order instead of the capture quarantining for a human.

**Dormant after step 8, and this is the part worth reading before step 9:**

- **Grafts 3 and 5** cannot reach Wix. `accept_paid` writes the internal `OrderTable` record,
  stages `INTERNAL_ORDER_CREATED`, then stages `NEEDS_RECONCILIATION` /
  `WIX_WRITE_CONTRACT_REQUIRED` and returns. **No Wix order and no Wix payment record exist after
  the first payment.** Closing that is a separate change with its own attestation; the payload
  builder and the cart-completion call are both correct and both unreachable until then.

## Expected `--verify` output, so a known problem is not read as a regression

`python scripts/provision_checkout.py --verify` reports **exactly one** problem until step 4
lands:

```
env ORDERS_TABLE mismatch on live (v5)
```

That is the declaration being ahead of the deployment, which is the correct state for a change
that ships dormant. It clears at step 4.

`--verify` was **not run** as part of this change: it makes live AWS calls and is a
deploy-adjacent action.

## `EXPECTED_PROVIDER_MID`, and why it is not seeded

    EXPECTED_PROVIDER_MID = acc_TTFSyolquKEZEy

An **identifier of record**, not a secret — it already appears in `payment_readiness.py`'s own
docstring. It is recorded here and deliberately **not** seeded into
`provision_checkout.expected_environment()`, because `READINESS_KEYS` checks the two readiness
values for presence only and a seeded value makes `--verify` exit non-zero by design. The only way
back from that would be to weaken the readiness check, which is the opposite of what the check is
for. An owner fills it from a live Meta/Razorpay read at step 7's own discretion.

## Known gap, pre-existing and out of scope

Neither `wecare-customer-profile` nor `wecare-email-verification` has an `amplify/infra/*.json`
declaration of record. Both are provisioned by script only, so their IAM, environment and routes
exist in one place rather than two. That predates this change and is not closed by it. The remedy
is one template per function, modelled on `amplify/infra/checkout.json`, which this change has
just reconciled against its own provisioner and can serve as the pattern.

## Rollback

Every step is a pointer move or an additive declaration:

- steps 1–3 create resources; deleting them is owner work and requires pointwise confirmation.
- steps 4, 5 and 8 are `update-function-code` plus publish plus move alias. Rollback is
  `aws lambda update-alias --function-name wecare-checkout --name live --function-version 5`.
  Published versions are immutable and retained, so this is a pointer move rather than a redeploy.
- step 7 is one environment variable. Removing it and republishing returns the gate to off.

## Related

- `.agents/tasks/direct-razorpay-graft-20261002/design.md` — iteration 7, approved
- `.agents/tasks/direct-razorpay-graft-20261002/verification.md` — what was run and what it said
- `.kiro/steering/lambda-snapstart-deploy.md` — why a payments change is not live until the
  `live` alias moves
- `.kiro/steering/whatsapp-payments-india-reference.md` — the money rules this change implements
