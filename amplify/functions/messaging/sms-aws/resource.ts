import { defineFunction } from '@aws-amplify/backend';

export const smsAws = defineFunction({
  name: 'wecare-sms-aws',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    SMS_AWS_TABLE: 'stack-wecare-digital-SmsAwsTable',
    // Amazon Pinpoint SMS Voice v2 (us-east-1)
    ORIGINATION_IDENTITY: '', // Phone number or sender ID registered in Pinpoint
    SENDER_ID: 'WECARE',
  },
});
