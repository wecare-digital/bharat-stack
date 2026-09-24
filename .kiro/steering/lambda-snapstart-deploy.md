---
inclusion: always
---

# Lambda version/alias deploy model (SnapStart is currently OFF)

**Corrected 2026-09-19 against the live account.** This file previously stated
that all ~49 Python functions behind the main HTTP API (`zllr9lrg7j`) run with
`SnapStart.ApplyOn = PublishedVersions`. That is not true. Measured across all
62 functions in `us-east-1` (account 775261844268) via
`GetFunctionConfiguration`, at both `$LATEST` and every published version:

    SnapStart.ApplyOn = None,  OptimizationStatus = Off      62 of 62

The deploy rule below is unchanged and still mandatory — but it is the **`live`
alias** that makes it mandatory, not SnapStart.

## Key facts

- Runtime: python3.12, x86_64, 62 of 62 functions.
- **56 of 62 functions have a `live` alias. Only these 6 do not:**
  `wecare-ad-attribution`, `wecare-docs-scraper`,
  `wecare-partner-token-refresh`, `wecare-seo-tools`, `wecare-sla-engine`,
  `wecare-url-shortener` (the unused twin of `stack-wecare-url-shortener`).
  The HTTP API integrations invoke the alias where one exists (e.g.
  `...:function:wecare-contacts:live`), so for those 56, `$LATEST` changes do
  NOT reach production until a version is published and the alias is moved.
  For the 6 above, `update-function-code` takes effect immediately.
  Counted sequentially with retries over `ListFunctions` + `ListAliases`,
  0 errors. An earlier concurrent count reported 34/28 because failed calls
  were silently treated as "no alias" — do not trust a count that does not
  report its error total.

  **Re-measured 2026-09-25: was 53/9.** `wecare-marketing-ads`,
  `wecare-partner-onboarding` and `wecare-push-notifications` have since gained
  a `live` alias — `provision_live_alias.py` and `provision_missing_ui_routes.py`
  create them, and both files note that doing so immediately moves those
  functions onto the publish-and-move path, because `snapstart_publish.py`
  discovers its targets by looking for the alias rather than from a list. So the
  count drifts on its own as aliases are provisioned. Treat the numbers here as a
  dated snapshot and re-derive them rather than trusting them; the deploy rule
  below does not depend on the count.
- `scripts/snapstart_publish.py` already keys membership on the alias rather
  than on `SnapStart.ApplyOn`, so it behaves correctly with SnapStart off.
- If SnapStart is ever enabled, everything in Gotchas below becomes live again;
  it is written to stay valid either way.

## Deploy rule (must follow)

After changing a function's code you MUST:
1. `aws lambda update-function-code ...` (updates `$LATEST`), then
2. publish a new version, wait for `State=Active`, and move the `live` alias.

Step 2 is automated by `scripts/snapstart_publish.py`:
```
python scripts/snapstart_publish.py                 # all SnapStart functions
python scripts/snapstart_publish.py wecare-contacts # specific ones
```
`scripts/deploy_all_lambdas.py` calls it at the end. If you deploy a function by
hand, run the publisher yourself or the API will keep serving old code.

There is also a second reason to move the alias, found on 2026-09-20: a function
caches its secrets on first use, so replacing a value in Secrets Manager does not
change what a warm sandbox serves. A freshly published version has no warm
environments. `scripts/refresh_secret_consumers.py <secret-id>` does exactly that
for every consumer of a secret, and `scripts/check_secrets_live.py` then confirms
the provider accepts the new value.

## Which deploy script to use

The PowerShell deploy scripts were deleted on 2026-09-20. They were Windows-only
(`\`-separated paths), so they could never run on this machine, and one of them
silently dropped the `flows/*.json` definitions from the package. There is one
deploy-all entrypoint:

```
python scripts/deploy_all_lambdas.py             # whole fleet, then publishes
python scripts/deploy_all_lambdas.py --dry-run   # build + validate, upload nothing
python scripts/deploy_all_lambdas.py --list      # the function map
python scripts/deploy_all_lambdas.py wecare-contacts
```

It covers all 60 zip-packaged functions, calls `snapstart_publish.py` itself,
and validates before uploading that every top-level import resolves either
inside the package or in one of the function's attached layers. Two functions
are deliberately outside it:

- `wecare-seo-tools` — different in-zip layout; `scripts/deploy_seo_tools.py`
  owns it along with its table and IAM policy.
- `wecare-docs-scraper` — `PackageType=Image`, ships via
  `.github/workflows/docs-scraper-deploy.yml`.

## Gotchas

- **Randomness:** never use `random` for anything that must be unique per call
  (e.g. url-shortener short codes) — use `secrets` / `os.urandom`. With
  SnapStart on, the snapshot freezes the `random` PRNG state and every restored
  environment produces the same sequence. Verified: no function imports
  `random`, and `core/url-shortener/handler.py` correctly uses `secrets`.
- **Init-time secrets:** fetch secrets lazily (on first request), not at import.
  This matters even with SnapStart off, because a module-scope read is cached
  for the life of the execution environment, so a rotation does not take effect
  until every warm sandbox recycles. With SnapStart on it is worse: the value is
  frozen into the published version until someone republishes. Fixed on
  2026-09-19 in `payments/razorpay-webhook`, `ecommerce/wix-store` and
  `messaging/outbound-sms`; the rest of the fleet already loaded lazily.
- **Cost:** not currently incurred, since SnapStart is off. If enabled, Python
  SnapStart bills for snapshot cache + restore.
- SnapStart is incompatible with provisioned concurrency.
