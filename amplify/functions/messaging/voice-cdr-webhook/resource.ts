/**
 * Airtel Voice CDR Webhook Lambda Function Resource
 * Receives Call Detail Records from Airtel Cloud Communication Platform
 */

import { defineFunction } from '@aws-amplify/backend';

export const voiceCdrWebhook = defineFunction({
  name: 'wecare-voice-cdr-webhook',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    LOG_LEVEL: 'INFO',
    VOICE_CDR_TABLE: 'base-wecare-digital-VoiceCDRTable',
  },
});
