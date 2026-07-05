/**
 * Partner Onboarding Lambda Function Resource  (Option B — Embedded Signup)
 *
 * Completes WhatsApp Embedded Signup for external businesses that connect their
 * own WABA to WECARE.DIGITAL via the public /partners/ page. Exchanges the OAuth
 * code for a business token server-side, provisions the WABA, and stores a
 * per-tenant record + secret.
 *
 * Route (added to HTTP API zllr9lrg7j): POST /partners/embedded-signup
 * Deployed via scripts/_deploy_partner_onboarding.py (this repo deploys Lambdas
 * out-of-band from Amplify Gen 2 — see amplify/backend.ts).
 */
import { defineFunction } from '@aws-amplify/backend';

export const partnerOnboarding = defineFunction( {
    name: 'wecare-partner-onboarding',
    entry: './handler.py',
    runtime: 20, // Python 3.12
    timeoutSeconds: 30,
    memoryMB: 256,
    environment: {
        LOG_LEVEL: 'INFO',
        META_API_VERSION: 'v25.0',
        META_APP_ID: '2238810740192680',
        META_TOKEN_SECRET: 'wecare/meta-system-user-token',
        SYSTEM_CONFIG_TABLE: 'stack-wecare-digital-SystemConfigTable',
        WA_REG_PIN: '',
        META_EXTENDED_CREDIT_ID: '',
        COGNITO_USER_POOL_ID: 'us-east-1_cSx0RHCIR',
        PARTNER_GROUP: 'Partner',
    },
} );
