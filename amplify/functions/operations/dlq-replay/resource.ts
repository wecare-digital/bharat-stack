import { defineFunction } from '@aws-amplify/backend';

export const dlqReplay = defineFunction({
  name: 'wecare-dlq-replay',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 60,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    MAX_RETRIES: '5',
    BATCH_SIZE: '100',
    DLQ_MESSAGES_TABLE: 'base-wecare-digital-DLQMessagesTable',
    INBOUND_DLQ_URL: `https://sqs.us-east-1.amazonaws.com/${process.env.AWS_ACCOUNT_ID || '775261844268'}/base-wecare-digital-inbound-dlq`,
    BULK_DLQ_URL: `https://sqs.us-east-1.amazonaws.com/${process.env.AWS_ACCOUNT_ID || '775261844268'}/base-wecare-digital-bulk-dlq`,
    INBOUND_HANDLER_FUNCTION: 'inbound-whatsapp-handler',
    BULK_WORKER_FUNCTION: 'bulk-worker',
  },
});
