import { defineFunction } from '@aws-amplify/backend';

export const mediaCleanup = defineFunction({
  name: 'wecare-media-cleanup',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    MEDIA_FILES_TABLE: 'stack-wecare-digital-MediaFilesTable',
    WHATSAPP_PHONE_NUMBER_ID_1: 'phone-number-id-waba3-direct-1016149501586345',
    CLEANUP_AGE_DAYS: '25',
    MAX_DELETIONS: '50',
  },
});
