import { defineFunction } from '@aws-amplify/backend';

export const voiceCalls = defineFunction({
  name: 'wecare-voice-calls',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    VOICE_CALLS_TABLE: 'base-wecare-digital-VoiceCalls',
    CONNECT_INSTANCE_ID: '',
    CONNECT_CONTACT_FLOW_ID: '',
    CONNECT_QUEUE_ID: '',
    SOURCE_PHONE_NUMBER: '',
    // Airtel CCP Click-to-Call Configuration
    AIRTEL_CCP_HOST: 'cpaas.airtel.in',
    AIRTEL_CCP_USERNAME: '',
    AIRTEL_CCP_PASSWORD: '',
    AIRTEL_CCP_CALL_FLOW_ID: '',
    AIRTEL_CCP_CUSTOMER_ID: '',
    AIRTEL_CCP_CALLER_ID: '9319767034',
    AIRTEL_CDR_WEBHOOK_URL: 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook',
    AIRTEL_EVENTS_WEBHOOK_URL: 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook',
  },
});
