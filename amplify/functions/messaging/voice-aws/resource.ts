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
    VOICE_CALLS_TABLE: 'base-wecare-digital-VoiceCalls',
    // Amazon Connect Configuration (us-east-1)
    CONNECT_INSTANCE_ID: '',
    CONNECT_CONTACT_FLOW_ID: '',
    CONNECT_QUEUE_ID: '',
    SOURCE_PHONE_NUMBER: '',
  },
});
