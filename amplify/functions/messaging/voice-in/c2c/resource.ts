/**
 * Airtel Click-to-Call (C2C) Lambda Function
 * Connects two users on a call via Airtel Kong API
 * Credentials from Secrets Manager: wecare/airtel/c2c
 */

import { defineFunction } from '@aws-amplify/backend';

export const voiceC2c = defineFunction({
  name: 'wecare-voice-in-c2c',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    VOICE_CALLS_TABLE: 'base-wecare-digital-VoiceCalls',
    AIRTEL_KONG_HOST: 'iqvoice.airtel.in',
    AIRTEL_C2C_SECRET_NAME: 'wecare/airtel/c2c',
  },
});
