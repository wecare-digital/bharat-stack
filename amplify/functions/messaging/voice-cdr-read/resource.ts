/**
 * Voice CDR Read Lambda Function Resource
 * Reads Call Detail Records from DynamoDB
 */

import { defineFunction } from '@aws-amplify/backend';

export const voiceCdrRead = defineFunction({
  name: 'wecare-voice-cdr-read',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    LOG_LEVEL: 'INFO',
    VOICE_CDR_TABLE: 'stack-wecare-digital-VoiceCDRTable',
  },
});
