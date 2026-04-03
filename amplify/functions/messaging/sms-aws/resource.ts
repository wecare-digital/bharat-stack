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
    // Toll-free +18444891209 PENDING registration — use account default until approved
    // Once approved, set to '+18444891209' to use toll-free as origination
    ORIGINATION_IDENTITY: '',
    SENDER_ID: 'WECARE',
    // India Pinpoint (ap-south-1) — for SMS template management & India sender ID
    INDIA_SENDER_ID: 'WDBEEP',
    INDIA_PINPOINT_APP_ID: '',
  },
});
