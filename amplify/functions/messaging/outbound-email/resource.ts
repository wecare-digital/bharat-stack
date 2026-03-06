import { defineFunction } from '@aws-amplify/backend';

export const outboundEmail = defineFunction({
  name: 'wecare-outbound-email',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    MESSAGES_TABLE: 'stack-wecare-digital-MessagesTable',
    FROM_EMAIL: 'noreply@wecare.digital',
    REPLY_TO_EMAIL: 'support@wecare.digital',
  },
});
