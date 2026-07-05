/**
 * Partner Token Refresh Lambda Resource  (Option B — Embedded Signup)
 *
 * Refreshes 60-day expiring system-user tokens for onboarded partner WABAs
 * (stored in per-tenant secrets wecare/partners/<wabaId>) before they lapse.
 *
 * Trigger: EventBridge daily schedule (wired in scripts/_deploy_partner_onboarding.py).
 * Deployed out-of-band from Amplify Gen 2 — see amplify/backend.ts.
 */
import { defineFunction } from '@aws-amplify/backend';

export const partnerTokenRefresh = defineFunction( {
    name: 'wecare-partner-token-refresh',
    entry: './handler.py',
    runtime: 20, // Python 3.12
    timeoutSeconds: 120,
    memoryMB: 256,
    environment: {
        LOG_LEVEL: 'INFO',
        META_API_VERSION: 'v25.0',
        META_APP_ID: '2238810740192680',
        META_TOKEN_SECRET: 'wecare/meta-system-user-token',
        PARTNER_SECRET_PREFIX: 'wecare/partners/',
        REFRESH_WINDOW_DAYS: '15',
        SYSTEM_CONFIG_TABLE: 'stack-wecare-digital-SystemConfigTable',
    },
} );
