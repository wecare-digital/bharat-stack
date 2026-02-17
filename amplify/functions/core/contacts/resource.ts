import { defineFunction } from '@aws-amplify/backend';

/**
 * Unified Contacts Lambda Function
 * 
 * Replaces: contacts-create, contacts-read, contacts-update, contacts-delete, contacts-search
 * Routes by HTTP method: GET (list/read/search), POST (create), PUT (update), DELETE (soft/hard)
 */
export const contacts = defineFunction({
  name: 'wecare-contacts',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60, // Increased for hard delete operations
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    INBOUND_TABLE: 'base-wecare-digital-WhatsAppInboundTable',
    OUTBOUND_TABLE: 'base-wecare-digital-WhatsAppOutboundTable',
    MEDIA_BUCKET: 'app.wecare.digital',
  },
});
