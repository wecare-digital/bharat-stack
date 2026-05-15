import { defineFunction } from '@aws-amplify/backend';

/**
 * Media Cleanup Lambda
 *
 * Deletes expired WhatsApp media IDs from Meta servers (25-day cycle).
 * Scans MediaFilesTable for old records and calls DELETE /{media_id}.
 * Media IDs are globally unique — no phone number needed for deletion.
 */
export const mediaCleanup = defineFunction( {
  name: 'wecare-media-cleanup',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    MEDIA_FILES_TABLE: 'stack-wecare-digital-MediaFilesTable',
    CLEANUP_AGE_DAYS: '25',
    MAX_DELETIONS: '50',
  },
} );
