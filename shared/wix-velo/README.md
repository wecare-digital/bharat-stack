# Shared Wix Velo Code — WECARE.DIGITAL

This folder contains the **source of truth** for Wix Velo backend code shared between two repos:

| Repo | Branch | Purpose |
|------|--------|---------|
| `wecaredigital/stack.wecare.digital` | `stack` | Stack CRM dashboard, Lambdas, Amplify. Has a reference copy at `store/src/` |
| `wecaredigital/store.wecare.digital` | `main` | **LIVE on Wix** — connected via Git Integration. Auto-syncs to Wix Editor on push |

## How It Works

1. Edit files here in `shared/wix-velo/backend/`
2. Run `sync.ps1` to copy to both repos
3. Push both repos

## Important Notes

- **Page files** (e.g. `Thank You Page.f0at2.js`) have Wix internal IDs — they can ONLY be created from the Wix Editor. Don't create page files here.
- **http-functions.js** in the Wix repo is a massive file with SEO/sitemap/RSS/AI feeds code. The stack repo has a simpler version. Don't overwrite the Wix version.
- **orderId.web.js** and **events.js** are the critical shared files — they handle order ID generation.

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
