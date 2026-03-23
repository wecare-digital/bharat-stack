import { defineFunction } from '@aws-amplify/backend';

export const outboundVoice = defineFunction({
  name: 'wecare-outbound-voice',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    VOICE_TABLE: 'stack-wecare-digital-VoiceCalls',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    AIRTEL_SECRET: 'wecare/airtel/c2c',
    CDR_WEBHOOK_URL: 'https://api.wecare.digital/voice-in/c2c',
  },
});
