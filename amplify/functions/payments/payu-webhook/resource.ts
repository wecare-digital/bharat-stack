import { defineFunction } from '@aws-amplify/backend';

export const payuWebhook = defineFunction({
  name: 'wecare-payu-webhook',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 256,
  environment: {
    PAYU_MERCHANT_KEY: process.env.PAYU_MERCHANT_KEY ?? 'Ghgoh6',
    PAYU_MERCHANT_SALT: process.env.PAYU_MERCHANT_SALT ?? 'LtQP3Bo4sXMqJgZFz4cK9DpB8fMt3vzl',
    PAYU_CLIENT_ID: process.env.PAYU_CLIENT_ID ?? 'c066d621f07afd57e1797306a33acd5f51d19400adb0741449784dc36c634d75',
    PAYU_CLIENT_SECRET: process.env.PAYU_CLIENT_SECRET ?? '9b5c14bd86f0d8deabad339837e43ebce4cb039a26897d142ba0b1f91c38287f',
    PAYU_MID: '8629516',
    PAYMENTS_TABLE: 'base-wecare-digital-PaymentsTable',
    INVOICES_TABLE: 'base-wecare-digital-InvoicesTable',
    PAYU_WEBHOOK_LOG_TABLE: 'base-wecare-digital-PayUWebhookLogTable',
    LOG_LEVEL: 'INFO',
  },
});
