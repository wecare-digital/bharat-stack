import { defineFunction } from '@aws-amplify/backend';

export const bulkWorker = defineFunction({
  name: 'wecare-bulk-worker',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 120,
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    BULK_JOBS_TABLE: 'stack-wecare-digital-BulkJobsTable',
    BULK_RECIPIENTS_TABLE: 'stack-wecare-digital-BulkRecipientsTable',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    OUTBOUND_TABLE: 'stack-wecare-digital-WhatsAppOutboundTable',
    SEND_MODE: 'LIVE',
    DEFAULT_PHONE_NUMBER_ID: 'phone-number-id-waba3-direct-1016149501586345',
    RATE_LIMIT_PER_SECOND: '80',
  },
});
