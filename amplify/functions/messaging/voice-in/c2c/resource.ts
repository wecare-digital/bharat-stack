/**
 * Legacy click-to-call records and CDR ingestion.
 *
 * Outbound initiation was removed on 2026-09-19: it dialled a retired India voice
 * provider, and PSTN voice is now Plivo. This function retains historical record
 * reads, CDR callback ingestion and retention deletes.
 *
 * Removed with it: the vendor gateway host and the credential id it loaded. The
 * secret still exists in Secrets Manager with no reader and is deleted under
 * separate destructive approval.
 *
 * LEGACY_C2C_TABLE replaces a provider-named variable. The physical table name is
 * unchanged, because it holds real historical records.
 */

import { defineFunction } from '@aws-amplify/backend';

export const voiceC2c = defineFunction( {
  name: 'wecare-voice-in-c2c',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    LEGACY_C2C_TABLE: 'stack-wecare-digital-AirtelC2CTable',
    VOICE_CDR_TABLE: 'stack-wecare-digital-VoiceCDRTable',
    SINCH_RCS_ENABLED: 'true',
  },
} );
