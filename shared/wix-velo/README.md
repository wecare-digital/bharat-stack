# Wix Velo Integration — WECARE.DIGITAL

The **live Wix Velo source of truth is `wecaredigital/site-store` on `main`**.
That repository is connected to the WECARE.DIGITAL Wix site through Wix Git
Integration & CLI for Sites.

`wecaredigital/stack.wecare.digital` is the AWS/Amplify/admin application. It is
**not** a second Wix source repository and should not be connected to the Wix
site. Any Velo copies under this repository's historical `store/` or
`shared/wix-velo/` paths are reference/migration material only and must not be
used to overwrite `site-store`.

| Repo | Branch | Purpose |
|------|--------|---------|
| `wecaredigital/site-store` | `main` | **LIVE Wix Velo source** — pages, public modules, backend modules, HTTP functions |
| `wecaredigital/stack.wecare.digital` | `stack` | AWS Lambdas, API Gateway, DynamoDB/S3, CRM/dashboard and integration services |

## Development rule

1. Wix/Velo changes are made in `site-store` on a feature branch.
2. AWS service changes are made in `stack.wecare.digital` on a feature branch.
3. Cross-repository features use an explicit API contract; do not duplicate the
   same implementation in both repos.
4. Review/merge each repository independently. Publish the Wix site from its
   connected `site-store` repository after the Wix-side change is approved.

## Important notes

- Wix page files have Wix internal IDs. Preserve the filenames/IDs already
  present in `site-store`; don't synthesize replacement page IDs in the stack
  repository.
- `site-store/src/backend/http-functions.js` is the authoritative Wix HTTP
  functions file. Historical copies in this repository may be incomplete.
- Order ID logic on the Wix site is authoritative in `site-store`; AWS should
  consume/sync it rather than maintaining a competing Velo source tree.
- New website translation/audio work lives in the dedicated AWS
  `wecare-site-language` service and the thin Velo proxy/controller in
  `site-store`.

## Order ID format

```
WD-ORD - {UUID8} - {DD-MM-YYYY} - {HH:MM:SS} - IST
Example: WD-ORD - A3F7B2C1 - 22-02-2026 - 17:43:01 - IST
```

## DynamoDB tables used by Wix integrations

| Table | Purpose |
|-------|---------|
| `stack-wecare-digital-WixOrderIds` | Lambda order ID mapping (orderId → wdOrderNumber) |
| `stack-wecare-digital-WixProductsCache` | Product cache for dashboard |
| `stack-wecare-digital-WixOrdersCache` | Order cache for dashboard |
| `stack-wecare-digital-SiteLanguageCache` | Cached site translations |

## Secrets

- Wix REST API credentials belong in AWS Secrets Manager / environment contracts,
  never in Git.
- Wix-side private values belong in Wix Secrets Manager, never in page/public
  code.
