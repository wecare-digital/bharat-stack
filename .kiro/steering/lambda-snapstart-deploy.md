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
- **34 functions have a `live` alias; 28 do not.** The HTTP API integrations
  invoke the alias where one exists (e.g.
  `...:function:wecare-contacts:live`), so for those 34, `$LATEST` changes do
  NOT reach production until a version is published and the alias is moved.
  For the other 28 (including `wecare-razorpay-webhook`, `wecare-wix-store`,
  `wecare-invoice-engine`, `wecare-payments-read`, `wecare-marketing-ads`,
  `wecare-seo-tools`) `update-function-code` takes effect immediately.
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
The deploy scripts (`_deploy_all.ps1`, `_deploy_changed.ps1`,
`_deploy_meta_agent.ps1`) already call it at the end. If you deploy a function
by hand, run the publisher yourself or the API will keep serving old code.

## Which deploy script to use

The `.ps1` scripts are **Windows-only** — they use `\`-separated paths, so they
cannot run on macOS or Linux. The portable deploy-all is:

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
