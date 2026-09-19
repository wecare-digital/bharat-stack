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
    // AWS End User Messaging (pinpoint-sms-voice-v2), us-east-1.
    //
    // Left blank deliberately: the handler default is '+18444891209', the
    // registered toll-free number with InternationalSendingEnabled=true. An
    // empty value here means "use the handler default" rather than "let AWS
    // choose", because the account also owns a SIMULATOR number in the SAME
    // pool, and a simulator accepts a send and returns a MessageId without
    // delivering anything.
    ORIGINATION_IDENTITY: '',
    SENDER_ID: 'WECARE',
    // India sender id. Blank falls through to lambda_utils.comms.dlt.SENDER_ID,
    // which is the single source of truth for DLT-registered identity.
    INDIA_SENDER_ID: '',
    // Removed 2026-09-19: the legacy AWS SMS application id that configured
    // classic template management, which is not TRAI DLT-capable. It was already
    // empty. Identifier name omitted so the provider-policy scan stays precise.
  },
});
