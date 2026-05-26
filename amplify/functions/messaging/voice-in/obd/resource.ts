/**
 * Airtel OBD (Outbound Dialer) Campaign Lambda Function
 * Manages bulk voice campaigns via Airtel IQ Telephony API
 * Credentials from Secrets Manager: wecare/airtel/obd
 */

import { defineFunction } from '@aws-amplify/backend';

export const voiceObd = defineFunction( {
  name: 'wecare-voice-in-obd',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 120,
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    OBD_CAMPAIGNS_TABLE: 'stack-wecare-digital-OBDCampaigns',
    VOICE_CDR_TABLE: 'stack-wecare-digital-VoiceCDRTable',
    S3_BUCKET: 'app.wecare.digital',
    AIRTEL_OBD_SECRET_NAME: 'wecare/airtel/obd',
    SINCH_RCS_ENABLED: 'true',
  },
} );
