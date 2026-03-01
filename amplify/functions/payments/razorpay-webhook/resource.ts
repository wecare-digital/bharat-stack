import { defineFunction } from '@aws-amplify/backend';

export const razorpayWebhook = defineFunction({
  name: 'wecare-razorpay-webhook',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60, // Razorpay webhooks may retry/be slow
  memoryMB: 256,
  environment: {
    RAZORPAY_WEBHOOK_SECRET: process.env.RAZORPAY_WEBHOOK_SECRET ?? '',
    PAYMENTS_TABLE: 'base-wecare-digital-PaymentsTable',
    INVOICES_TABLE: 'base-wecare-digital-InvoicesTable',
    MESSAGES_TABLE: 'base-wecare-digital-WhatsAppInboundTable',
    WEBHOOK_LOG_TABLE: 'base-wecare-digital-RazorpayWebhookLogTable',
    LOG_LEVEL: 'INFO',
  },
});
