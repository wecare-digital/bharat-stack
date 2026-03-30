import { defineFunction } from '@aws-amplify/backend';

export const outboundSms = defineFunction({
  name: 'wecare-outbound-sms',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    MESSAGES_TABLE: 'stack-wecare-digital-MessagesTable',
    PINPOINT_APP_ID: 'c40d842c24b14fd5931f50d6ce1bb06d',
    ORIGINATION_NUMBER: '',
    SENDER_ID: 'WDBEEP',
    // Airtel IQ SMS Configuration
    AIRTEL_IQ_HOST: 'iqmessaging.airtel.in',
    AIRTEL_IQ_USERNAME: '',
    AIRTEL_IQ_PASSWORD: '',
    AIRTEL_IQ_CUSTOMER_ID: '',
    // DLT Registration Details - WECARE.DIGITAL
    AIRTEL_IQ_ENTITY_ID: '1201161991108627443',  // PE ID
    AIRTEL_IQ_SOURCE_ADDRESS: 'WDBEEP',  // Header (DLT ID: 1405170900886606599)
  },
});
