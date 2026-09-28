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
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    INBOUND_TABLE: 'stack-wecare-digital-WhatsAppInboundTable',
    OUTBOUND_TABLE: 'stack-wecare-digital-WhatsAppOutboundTable',
    // The handler already defaults to media_paths.BUCKET, so this line only mattered
    // on deploy — where it would have overridden a correct default with the bucket
    // deleted on 2026-09-28.
    MEDIA_BUCKET: 'wecare-digital-get',
  },
});
