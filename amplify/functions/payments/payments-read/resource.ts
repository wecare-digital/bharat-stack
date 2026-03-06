import { defineFunction } from '@aws-amplify/backend';

export const paymentsRead = defineFunction({
  name: 'wecare-payments-read',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    PAYMENTS_TABLE: 'stack-wecare-digital-PaymentsTable',
  },
});
