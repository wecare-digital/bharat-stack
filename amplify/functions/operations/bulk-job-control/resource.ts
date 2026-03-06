import { defineFunction } from '@aws-amplify/backend';

export const bulkJobControl = defineFunction({
  name: 'wecare-bulk-job-control',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    BULK_JOBS_TABLE: 'stack-wecare-digital-BulkJobsTable',
    BULK_RECIPIENTS_TABLE: 'stack-wecare-digital-BulkRecipientsTable',
    BULK_QUEUE_URL: `https://sqs.us-east-1.amazonaws.com/${process.env.AWS_ACCOUNT_ID || '775261844268'}/stack-wecare-digital-bulk-queue`,
    REPORT_BUCKET: 'app.wecare.digital',
    REPORT_PREFIX: 'stack/reports/',
  },
});
