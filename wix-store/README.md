# WECARE.DIGITAL — Wix Store (Velo Code)

Pulled from: https://github.com/wecaredigital/store.wecare.digital.git

## Site Info
- **Site**: WECARE.DIGITAL
- **Site ID**: `461dece3-613a-42b3-a30c-ed9256898e78`
- **Account ID**: `6b2d7a93-ef14-45ab-a04e-d445f599e9f4`
- **URL**: https://www.wecare.digital/
- **Editor Type**: Wix Editor

## What's Here

### Backend (`src/backend/`)
| File | Purpose |
|------|---------|
| `orderId.web.js` | Custom order ID generation (ORDER ID : DD-MM-YYYY - HH:MM:SS - IST - XXXXXXXXXX). Uses `OrderIDs` collection. Web module callable from frontend. |
| `events.js` | Auto-generates random 8-char SKU on product creation + variant SKUs (PRODUCTSKU-01, -02...) |
| `sku-batch.web.js` | Batch assign SKUs to all products (Admin only). Handles variants with collision avoidance. |
| `http-functions.js` | SEO + AI + Discovery endpoints (1272 lines). Sitemaps, robots.txt, JSON-LD, FAQ, keywords, RSS feeds, canonical, diagnostics. **No store API endpoints yet.** |
| `pinger.js` | Scheduled health check — pings all SEO/discovery endpoints every 4 hours. |
| `jobs.config` | Cron: `dailySelfHit` every 4 hours (`0 */4 * * *`) |
| `permissions.json` | All web methods open to anyone (siteOwner, siteMember, anonymous) |

### Public (`src/public/`)
| File | Purpose |
|------|---------|
| `global-apply.js` | Full SEO automation: title, meta, canonical, hreflang, OG/Twitter, JSON-LD, FAQ schema, RSS autodiscovery. SPA-safe. |
| `seo-bridge.js` | JSON-LD bridge for structured data from `/_functions/seohead`. Skips if global already applied. |
| `ops-lite.js` | Browser console health check. Probes selftest/ping/robots endpoints. Activated with `?ops=1`. |
| `site-hygiene.js` | Strips tracking params, normalizes URLs via canonicalizer, enforces `<img alt>` via MutationObserver. |

### Pages (`src/pages/`)
51 page-level Velo files for all site pages (HOME, stores, self-service, blog, checkout, etc.)

## Key Finding
The existing `http-functions.js` is entirely SEO/AI/Discovery focused — it does NOT have any store API endpoints (products, orders, collections). Our new WECARE integration endpoints in `wix-velo/backend/http-functions.js` can be safely merged in.
