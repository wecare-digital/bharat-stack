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
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    VOICE_AWS_TABLE: 'base-wecare-digital-VoiceAwsTable',
    // Amazon Pinpoint Voice v2 (us-east-1)
    VOICE_ORIGINATION_IDENTITY: '', // Phone number registered for voice in Pinpoint
    VOICE_ID: 'Aditi', // Polly voice (Aditi = Hindi/English)
  },
});
