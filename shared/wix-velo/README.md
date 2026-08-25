# Shared Wix Velo Code — WECARE.DIGITAL

This folder is the **intended source of truth** for Wix Velo backend code shared between two repos:

| Repo | Branch | Visibility | Purpose |
|------|--------|-----------|---------|
| `wecare-digital/bharat-stack` | `stack` | public | Stack CRM dashboard, Lambdas, Amplify. Has a reference copy at `store/src/`. Amplify app `d22dm4b0jn71jw` builds from here. |
| `wecare-digital/store` | `main` | private | **LIVE on Wix** — connected via Git Integration. Auto-syncs to Wix Editor on push |

> **Repo names corrected 2026-08-25.** This file previously named
> `wecaredigital/stack.wecare.digital` and `wecaredigital/store.wecare.digital`.
> The GitHub account `wecaredigital` (no hyphen) **does not exist**, and neither
> repo name resolves. The owning account is `wecare-digital` (hyphenated, user
> id 319896805) and it has exactly two repos, listed above.

> The Wix repo is **not** cloned by default. `sync.ps1` expects it as a sibling
> directory (`../store`) and skips it when absent.

## How It Works

1. Edit files here in `shared/wix-velo/backend/`
2. Run `.\shared\wix-velo\sync.ps1 -DryRun` and read the report
3. Run `.\shared\wix-velo\sync.ps1` to copy to both repos
4. Push both repos

## Drift Warning — read before running sync

"Source of truth" is an intention, not a guarantee. It has already been violated:

- On 2026-08-25, `shared/wix-velo/backend/events.js` was **156 lines** while the
  live `store/src/backend/events.js` was **379 lines**. The live copy had gained
  `sendOrderNotifications()` and the Sinch SMS/RCS order-notification wiring
  (commits `b945cff2`, `0e342244`, `e6d781d2`) that were never promoted back here.
- The old `sync.ps1` copied unconditionally, so running it would have **deleted
  that live functionality** and, on push, auto-deployed the regression to Wix.
- The shared copy has since been reconciled from the live copy.

`sync.ps1` now refuses to overwrite a destination that differs from the source and
is larger than it. Use `-Pull` to promote a repo's version into `shared/`, and
`-Force` only when you genuinely intend to shrink a file.

Always run `-DryRun` first.

## Important Notes

- **Page files** (e.g. `Thank You Page.f0at2.js`) have Wix internal IDs — they can ONLY be created from the Wix Editor. Don't create page files here.
- **http-functions.js** in the Wix repo is a massive file with SEO/sitemap/RSS/AI feeds code. The stack repo has a simpler version. It is intentionally excluded from `$SyncFiles`. Don't overwrite the Wix version.
- **orderId.web.js**, **orderId-helpers.js** and **events.js** are the critical shared files — they handle order ID generation. `orderId-helpers.js` was previously missing from the sync list and is now included.
- **events.js cannot import `webMethod` exports.** It must import from `orderId-helpers.js` (plain `.js`), never from `orderId.web.js`, or Wix raises `BAD_USER_CODE`.

## Wix site ID — corrected 2026-08-25

The production Wix site ID is:

```
c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5
```

`store/wix.config.json` previously targeted `461dece3-613a-42b3-a30c-ed9256898e78`,
which is **not a real site** — the Wix site-properties API returns
`404 meta-site ... not found` for it, and it appears zero times in the rendered
production HTML. Every Wix dashboard/editor deep link built from it was broken.

Three independent sources confirm the correct ID:

| Source | Value |
|--------|-------|
| Rendered production HTML (`metaSiteId`, 82 occurrences) | `c17b0e20-…` |
| AWS Secrets Manager `wecare/wix-api-key` → `site_id` | `c17b0e20-…` |
| Wix `site-properties/v4/properties` → HTTP 200 | `c17b0e20-…` |

Corrected in 14 places across `store/wix.config.json`,
`src/pages/store/index.tsx` (8) and `src/pages/dashboard/index.tsx` (5).

Wix account ID: `15f02319-40ff-4288-b8e6-69c791adae5e`

### Authoritative site properties (from the Wix API, 2026-08-25)

Use these as the canonical NAP / business identity values:

| Field | Value |
|-------|-------|
| Business / display name | WECARE.DIGITAL |
| Email | one@wecare.digital |
| Phone | +91 9330994400 |
| Address | The W.B.S.I.D.C Building, Unit No. 1/20, 81/2/7, Phears Ln, Kolkata, WB 700012, IN |
| Currency / locale / TZ | INR / en-IN / Asia/Calcutta |
| Primary category | online-store |
| External site URL | https://www.wecare.digital |

## Order ID Format

```
WD-ORD - {UUID8} - {DD-MM-YYYY} - {HH:MM:SS} - IST
Example: WD-ORD - A3F7B2C1 - 22-02-2026 - 17:43:01 - IST
```

## Wix Data Collections

| Collection | Written By | Key Fields |
|-----------|-----------|------------|
| `OrderIDs` | Velo (Thank You page) | orderId (WD-ORD string), wixOrderId, orderNumber, buyerEmail, buyerPhone, totalAmount, orderDate |
| `OrderCustomIds` | Velo + Lambda | orderId (Wix UUID), customOrderNumber (WD-ORD), memberId, buyerEmail |
| `Stores/Products` | Wix native | Read-only from REST API. SKU prefix: WD- |
| `Stores/Orders` | Wix native | customField writable via Velo only |

## DynamoDB Tables

| Table | Purpose |
|-------|---------|
| `stack-wecare-digital-WixOrderIds` | Lambda order ID mapping (orderId → wdOrderNumber) |
| `stack-wecare-digital-WixProductsCache` | Product cache for dashboard |
| `stack-wecare-digital-WixOrdersCache` | Order cache for dashboard |

## API Keys

- Wix API Key: stored in Lambda env var `WIX_API_KEY` — NEVER hardcode
- Wix Secrets Manager: `WECARE_API_KEY` (shared secret for HTTP functions auth)
