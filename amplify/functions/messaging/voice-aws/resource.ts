import { defineFunction } from '@aws-amplify/backend';

export const voiceAws = defineFunction({
  name: 'wecare-voice-aws',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    VOICE_AWS_TABLE: 'stack-wecare-digital-VoiceAwsTable',
    // Amazon Pinpoint Voice v2 (us-east-1)
    VOICE_ORIGINATION_IDENTITY: '+18444891209', // Toll-Free, Intl enabled
    VOICE_ID: 'RAVEENA', // Polly voice (RAVEENA = Indian English, must be UPPERCASE)
  },
});
