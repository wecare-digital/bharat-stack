/**
 * Legacy outbound-dialler campaign records, IVR prompt audio and CDR ingestion.
 *
 * Campaign creation, status polling and the provider prompt/contact uploads were
 * removed on 2026-09-19: they drove a retired India voice provider, and PSTN voice
 * is now Plivo. Those routes answer 410.
 *
 * Retained: Polly text-to-speech and the S3 prompt audio library, neither of which
 * is provider-specific, plus historical record reads and CDR ingestion.
 *
 * Removed with the dialler: the credential id this function loaded. The secret
 * still exists in Secrets Manager with no reader and is deleted under separate
 * destructive approval.
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
    SINCH_RCS_ENABLED: 'true',
  },
} );
