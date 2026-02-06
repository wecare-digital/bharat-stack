/**
 * Airtel OBD (Outbound Dialer) Campaign Lambda Function
 * Manages bulk voice campaigns via Airtel IQ Telephony API
 * Credentials from Secrets Manager: wecare/airtel/obd
 */

import { defineFunction } from '@aws-amplify/backend';

export const voiceObd = defineFunction({
  name: 'wecare-voice-in-obd',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 120,
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    OBD_CAMPAIGNS_TABLE: 'base-wecare-digital-OBDCampaigns',
    S3_BUCKET: 'wecare-digital-assets',
    AIRTEL_OBD_SECRET_NAME: 'wecare/airtel/obd',
  },
});
