import { defineFunction } from '@aws-amplify/backend';

export const contactsDelete = defineFunction({
  name: 'wecare-contacts-delete',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 60, // Increased for hard delete operations
  memoryMB: 256,
  environment: { 
    AWS_REGION: 'us-east-1', 
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    INBOUND_TABLE: 'base-wecare-digital-WhatsAppInboundTable',
    OUTBOUND_TABLE: 'base-wecare-digital-WhatsAppOutboundTable',
    MEDIA_BUCKET: 'app.wecare.digital',
    LOG_LEVEL: 'INFO' 
  },
});
