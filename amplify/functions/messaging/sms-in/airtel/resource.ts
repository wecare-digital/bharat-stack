/**
 * Airtel IQ SMS Lambda Function
 * Send SMS via Airtel IQ Messaging API with Basic auth
 * Supports v4, v5 (content moderation), v6 API versions
 * DLT compliant (entityId, dltTemplateId per TRAI TCCCPR 2019)
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
    AIRTEL_SMS_TABLE: 'stack-wecare-digital-AirtelSMSTable',
    DLT_TEMPLATES_TABLE: 'stack-wecare-digital-DLTTemplates',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    AIRTEL_SMS_HOST: 'iqmessaging.airtel.in',
    AIRTEL_SMS_SECRET_NAME: 'wecare/airtel/sms',
  },
});
