/**
 * Scheduled Messages Lambda Resource Definition
 * Manages scheduled template messages with CRUD and scheduled sending
 */

import { defineFunction } from '@aws-amplify/backend';

export const scheduledMessagesFunction = defineFunction({
  name: 'wecare-scheduled-messages',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 256,
  environment: {
    SCHEDULED_TABLE: 'stack-wecare-digital-ScheduledMessagesTable',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    OUTBOUND_LAMBDA: 'wecare-outbound-whatsapp',
    LOG_LEVEL: 'INFO',
  },
});
