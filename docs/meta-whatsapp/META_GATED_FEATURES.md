# Meta-Gated Features

These require Meta approval / business eligibility / special API access. Each is behind a feature flag and defaults OFF (except Flows). Code is present but must not be claimed production-ready without the listed access + a live test.

| Feature | Flag | Default | Blocker before live | Status |
|---------|------|---------|---------------------|--------|
| WhatsApp Flows | `WA_FLOWS_ENABLED` | true | Flow must be published; endpoint reachable; QA recipient | FEATURE_FLAGGED_META_GATED |
| Payments India / UPI | `WA_PAYMENTS_ENABLED` | false | Payments onboarding + payment config approved on WABA | BLOCKED_BY_META_PERMISSION until enabled |
| Marketing Messages API | `WA_MARKETING_MESSAGES_ENABLED` | false | MM API access + approved marketing templates | FEATURE_FLAGGED_META_GATED |
| Calling API | `WA_CALLING_ENABLED` | false | Calling API access granted on WABA | BLOCKED_BY_META_PERMISSION until enabled |
| Groups API | `WA_GROUPS_ENABLED` | false | Groups API access + OBA business | BLOCKED_BY_META_PERMISSION until enabled |
| Catalog/product messages | (uses `WA_CATALOG_ID`) | n/a | Commerce catalog connected to WABA | FEATURE_FLAGGED_META_GATED |

## Flag enforcement guidance
Flags are documented here and in `.env.local.example`. Handlers should check the corresponding env flag before invoking the gated path and return a clear `feature_disabled` response when off. Where a handler does not yet check its flag, that is a follow-up hardening item (the capability code exists but should be guarded at the entry point).
