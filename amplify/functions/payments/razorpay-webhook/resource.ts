import { defineFunction } from '@aws-amplify/backend';

export const razorpayWebhook = defineFunction({
  name: 'wecare-razorpay-webhook',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    RAZORPAY_WEBHOOK_SECRET: process.env.RAZORPAY_WEBHOOK_SECRET ?? '',
    PAYMENTS_TABLE: 'base-wecare-digital-PaymentsTable',
    MESSAGES_TABLE: 'base-wecare-digital-WhatsAppInboundTable',
    LOG_LEVEL: 'INFO',
  },
});
