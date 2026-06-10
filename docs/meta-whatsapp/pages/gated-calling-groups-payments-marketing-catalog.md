# Build Spec — Calling / Groups / Payments / Marketing / Catalog (Meta-gated)

Meta refs: /calling, /groups, /payments/payments-in/*, /marketing-messages/overview, /catalogs/catalogs-overview

| Capability | Repo | Flag | Status |
|-----------|------|------|--------|
| Calling | `whatsapp-calling`, `WhatsAppCallingTable`, `/whatsapp/calling` | `WA_CALLING_ENABLED=false` | BLOCKED_BY_META_PERMISSION until access granted |
| Groups | `WhatsAppGroupTable`, group webhook fields, `/wa-business/groups*` | `WA_GROUPS_ENABLED=false` | BLOCKED_BY_META_PERMISSION (OBA + Groups access) |
| Payments India/UPI | payment template + order_details button (`outbound-whatsapp`), `payu`/`razorpay` webhooks, `/wa-business/payment-config/check` | `WA_PAYMENTS_ENABLED=false` | BLOCKED_BY_META_PERMISSION until payments onboarding |
| Marketing Messages | template categories | `WA_MARKETING_MESSAGES_ENABLED=false` | FEATURE_FLAGGED_META_GATED |
| Catalog/products | `catalog-management`, `CatalogCacheTable`, needs `WA_CATALOG_ID` | n/a | FEATURE_FLAGGED_META_GATED |

These are NOT counted against core launch readiness. Code is present; each needs Meta enablement + a live test before "production-ready".
