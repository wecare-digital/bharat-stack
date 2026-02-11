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
    BULK_JOBS_TABLE: 'base-wecare-digital-BulkJobsTable',
    BULK_RECIPIENTS_TABLE: 'base-wecare-digital-BulkRecipientsTable',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    OUTBOUND_TABLE: 'base-wecare-digital-WhatsAppOutboundTable',
    SEND_MODE: 'LIVE',
    DEFAULT_PHONE_NUMBER_ID: 'phone-number-id-5e020cecd221429996f6ae721cc42206',
    RATE_LIMIT_PER_SECOND: '80',
  },
});
