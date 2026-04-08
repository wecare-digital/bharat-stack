import { defineFunction } from '@aws-amplify/backend';

export const payuWebhook = defineFunction({
  name: 'wecare-payu-webhook',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 256,
  environment: {
    // ⚠️ All secrets MUST come from environment variables or Secrets Manager.
    // Never hardcode credentials as fallback defaults.
    PAYU_MERCHANT_KEY: process.env.PAYU_MERCHANT_KEY ?? '',
    PAYU_MERCHANT_SALT: process.env.PAYU_MERCHANT_SALT ?? '',
    PAYU_CLIENT_ID: process.env.PAYU_CLIENT_ID ?? '',
    PAYU_CLIENT_SECRET: process.env.PAYU_CLIENT_SECRET ?? '',
    PAYU_MID: process.env.PAYU_MID ?? '',
    PAYMENTS_TABLE: 'stack-wecare-digital-PaymentsTable',
    INVOICES_TABLE: 'stack-wecare-digital-InvoicesTable',
    PAYU_WEBHOOK_LOG_TABLE: 'stack-wecare-digital-PayUWebhookLogTable',
    LOG_LEVEL: 'INFO',
  },
});
