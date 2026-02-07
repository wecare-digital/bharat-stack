/**
 * Airtel IQ SMS Lambda Function
 * Send SMS via Airtel IQ Messaging API with HMAC auth
 * Credentials from Secrets Manager: wecare/airtel/sms
 */

import { defineFunction } from '@aws-amplify/backend';

export const smsAirtel = defineFunction({
  name: 'wecare-sms-in-airtel',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    AIRTEL_SMS_TABLE: 'base-wecare-digital-AirtelSMSTable',
    DLT_TEMPLATES_TABLE: 'base-wecare-digital-DLTTemplates',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    AIRTEL_SMS_HOST: 'iqmessaging.airtel.in',
    AIRTEL_SMS_SECRET_NAME: 'wecare/airtel/sms',
  },
});
