import { defineFunction } from '@aws-amplify/backend';

export const bulkJobCreate = defineFunction({
  name: 'wecare-bulk-job-create',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    BULK_JOBS_TABLE: 'base-wecare-digital-BulkJobsTable',
    BULK_RECIPIENTS_TABLE: 'base-wecare-digital-BulkRecipientsTable',
    BULK_QUEUE_URL: 'https://sqs.us-east-1.amazonaws.com/775261844268/base-wecare-digital-bulk-queue',
  },
});
