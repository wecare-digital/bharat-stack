# Secure file sharing — wecare.digital/get

Two tiers on one bucket. The open one is a plain CDN path; the gated one requires a
verified customer and a paid, single-use grant.

Status verified live 2026-09-25. Re-derive rather than trusting these numbers —
`.kiro/steering/00-current-owner-overrides.md` requires rediscovery per phase.

## Tiers

| Tier | Prefix | Gate | URL |
|---|---|---|---|
| Open | `o/` | none | `wecare.digital/get/o/<file>` |
| Gated | `secure/` | WhatsApp OTP, then ₹49 per download | `wecare.digital/files/` |

A link that matches nothing, and anything under `secure/`, redirects to the apex.

## Why the object key is opaque

Every gated upload lands at:

    secure/wecare-digital-<uuid4hex>-<uuid4hex><ext>

The key carries no customer name, no original filename and no sequence number, so it
cannot be guessed and one customer's key reveals nothing about another's. The
consequence is that the key is meaningless to a human, which is why
`SecureFilesTable` exists: it is the only place mapping an opaque key back to a
person and a readable name, and its `owner-created-index` GSI answers "which of these
files belongs to which customer" as a query rather than a scan.

**The unguessable key is a convenience, not the control.** CloudFront refuses the
whole `secure/` prefix, so these objects are reachable only through a presigned URL
issued after ownership and payment are both checked.

## Request path

    wecare.digital  (Amplify Hosting app d22dm4b0jn71jw)
      customRules, evaluated IN ORDER — /get/<*> must stay ABOVE the SPA catch-all
        /get            301 -> /
        /get/           301 -> /
        /get/<*>        200 rewrite -> d1kf2rchz7yras.cloudfront.net
        /files/         the app (must be in the _app.tsx public allowlist)
        /<*>            404-200 -> /index.html   <- catch-all, always last

    CloudFront E2GP22R4BIFGQ3
      no alternate domain name, so no Route 53 record and no ACM certificate
      Lambda@Edge origin-response v4:
        URI under secure/   -> 302 apex   (checked BEFORE status)
        status >= 400       -> 302 apex
      OAC EWEJQDZIBHRZU -> S3 wecare-digital-get (private, BPA on, AES256, versioned)

    api.wecare.digital (HTTP API zllr9lrg7j) -> wecare-secure-files:live

The prefix deny is checked before the response status deliberately: a gated object
that exists returns 200 from S3, so keying only off errors would serve it.

## Paid download flow

    GET /secure-files/mine                  customer's own files
    POST /secure-files/{fileId}/order       creates a Razorpay order + unpaid grant
    GET  /secure-files/{fileId}/download    redeems a paid grant -> 60s presigned URL

Entitlement is never taken from the browser. Razorpay Checkout's success callback is
forgeable, so it only stops the spinner. `paid` is set by one of two server paths:

1. the webhook at `POST /razorpay-webhook`, after fail-closed HMAC verification;
2. a fallback that asks Razorpay directly (`GET /v1/orders/{id}/payments`) when a
   redeem finds the grant unpaid.

Only `captured` counts. `authorized` means the money is held but not taken, and
granting on it would hand over the file for a payment that can still fail.

Redemption is a conditional write on `paid = true AND consumed = false`, so a
forwarded link is dead on second use and two concurrent requests cannot both win. The
webhook's own write requires `paid = false`, so a replayed webhook cannot revive a
spent grant.

If the fallback ever fires, it records `paidVia=reconcile` and logs
`WEBHOOK_MAY_NOT_BE_SUBSCRIBED`. That is the signal the webhook is not doing its job.

## Two Cognito pools, deliberately separate

| Pool | Id | Purpose |
|---|---|---|
| `WECARE.DIGITAL` | `us-east-1_cSx0RHCIR` | staff. Admin/Operator/Viewer |
| `WECARE.DIGITAL-CUSTOMERS` | `us-east-1_46ULYuukt` | customers. Phone-keyed, CUSTOM_AUTH |

Admin routes use `lambda_utils.middleware.require_auth`, which is hardcoded to the
staff pool. Customer routes must **not** reuse it: a customer token would pass
`get_user` and then silently degrade to role `Viewer` when its group lookup found
nothing. Instead `get_user` proves the token genuine (AWS checks signature and
expiry) and the `iss` claim is then pinned to the customer pool — sound precisely
because the token is already proven unmodified. No crypto dependency needed.

Customer users are created phone-keyed with `MessageAction='SUPPRESS'` and a
permanent random password that is never logged or returned, so they land `CONFIRMED`
and the only way in is a WhatsApp OTP. They are stamped with
`custom:partner_waba_id` because the OTP trigger refuses a user whose WABA scope does
not match.

## Two Razorpay secrets, not interchangeable

    wecare/razorpay/api        key_id + key_secret    API auth
    wecare/razorpay-webhook    webhook_secret only    signature verification

Conflating them has cost this codebase twice. `partner-onboarding` read the API pair
from the webhook secret and returned 501 on every top-up; this feature repeated it on
first write. `tests/test_secure_files.py` now pins both the module default and the
IAM grant.

No Razorpay SDK is bundled. `razorpay==2.0.1` is in `requirements-dev.txt` only, so
it is absent from the Lambda runtime, and the Orders API is a single POST.

## Live state, 2026-09-25

| Resource | Value |
|---|---|
| `wecare-secure-files` | live **v4**, python3.12 |
| `wecare-customer-whatsapp-auth` | live **v3** |
| `wecare-razorpay-webhook` | live **v33** |
| `wecare-get-miss-redirect` | **v4**, origin-response. No `live` alias — Lambda@Edge associates by version |
| `SecureFilesTable` | ACTIVE, GSI `owner-created-index` |
| `DownloadGrantsTable` | ACTIVE, GSI `order-index`, TTL on `expiresAt` |
| API routes | 7, all targeting `:live`, all 401 anonymously |
| Amplify | job 863 SUCCEED on `cdb89e9f` |

## Verify

    python scripts/verify_file_sharing.py                        # both tiers, 30 checks
    python scripts/provision_secure_files_api.py --verify        # lambda, routes, flag
    python scripts/provision_secure_file_sharing.py --verify     # tables, GSIs, TTL
    python scripts/provision_customer_whatsapp_auth.py --verify  # pool, client, triggers
    python -m pytest tests/test_secure_files.py                  # 34 invariants

## Enabling paid downloads

    python scripts/provision_secure_files_api.py --enable-payment

Three steps in one, and skipping any leaves a misleading state: write the **whole**
env map (a partial map deletes every variable not mentioned), publish a version (a
version freezes its environment), and move the `live` alias (the API invokes the
alias, so until this runs the change is real on `$LATEST` and invisible to every
request).

The flag is **sticky**. `provision_secure_files_api.py` reads the current value off
the live alias and preserves it, so re-provisioning cannot silently switch payments
back off. `deploy_all_lambdas.py` never touches configuration, so code deploys are
safe too. A brand-new function still starts off.

Rollback: `--disable-payment`, or the alias move the enable step prints.

## Pending

| Item | Status | Note |
|---|---|---|
| Paid downloads | ⚠️ **DISABLED** | `SECURE_FILES_PAYMENT_ENABLED=false`. Owner action; enabling payment capture is outside agent authority, and so is making it default-on |
| `verified -> list files` hop | ⏳ **UNPROVEN** | Needs a customer token, which needs the OTP from the handset. The handler deliberately never logs the code, so this cannot be closed from the code side |
| `payment.captured` subscription | ⏳ **UNCONFIRMED** | Dashboard-only. Materially de-risked: the reconcile fallback turns a missing subscription into a delay rather than a stranded payment. 316 webhook events were received 2026-09-24/25 and every one was `payment.downtime.*`, but `PaymentsTable` is empty, so no payment has ever been captured here and the absence proves nothing either way |
| Test leftovers | ➖ **INTENTIONAL** | A QA Cognito customer (`+918100640044`) and two seeded files. Harmless, useful for testing, removable on request |

## Two things that are easy to misread

`deploy_all_lambdas.py --dry-run` **always** reports `unchanged`, regardless of what
would change — the dry-run branch increments that tally unconditionally without
comparing shas. A dry run tells you packaging succeeded, not what would deploy.

`wecare-get-miss-redirect` has **no `live` alias**, and that is correct. Lambda@Edge
associations must name a published version; an alias is not permitted. Do not "fix"
it by adding one.

## Test links

| What | Link | Gate |
|---|---|---|
| Open sample | `https://wecare.digital/get/o/sample.txt` | none, downloads immediately |
| Open healthcheck | `https://wecare.digital/get/o/healthcheck.txt` | none |
| Gated sample | `https://wecare.digital/files/` → "Sample invoice.txt" | OTP to `+918100640044`, then ₹49 |
| Bad link | `https://wecare.digital/get/anything-else` | 302 to the apex |
