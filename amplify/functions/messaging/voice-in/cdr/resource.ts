/**
 * Airtel Voice CDR Webhook Lambda Function
 * Receives Call Detail Records from Airtel Cloud Communication Platform
 */

import { defineFunction } from '@aws-amplify/backend';

export const voiceCdr = defineFunction( {
  name: 'wecare-voice-in-cdr',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    VOICE_CDR_TABLE: 'stack-wecare-digital-VoiceCDRTable',
    SINCH_RCS_ENABLED: 'true',
  },
} );
