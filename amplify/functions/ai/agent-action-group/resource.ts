import { defineFunction } from '@aws-amplify/backend';

/**
 * Bedrock Agent Action Group Handler
 * 
 * Purpose: Handle action requests from internal Bedrock Agent
 * Agent ID: QIEEHEBTZO
 * Agent Alias: ASCBD7YPUT
 * KB ID: static-faq
 * 
 * Actions: send-whatsapp, send-sms, send-email, create-contact,
 *          update-contact, delete-contact, search-contacts, get-contact,
 *          delete-message, get-messages, create-invoice, get-stats
 */
export const agentActionGroup = defineFunction({
  name: 'wecare-agent-action-group',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    MESSAGES_INBOUND_TABLE: 'base-wecare-digital-WhatsAppInboundTable',
    MESSAGES_OUTBOUND_TABLE: 'base-wecare-digital-WhatsAppOutboundTable',
    OUTBOUND_WHATSAPP_FUNCTION: 'wecare-outbound-whatsapp',
    OUTBOUND_SMS_FUNCTION: 'wecare-outbound-sms',
    OUTBOUND_EMAIL_FUNCTION: 'wecare-outbound-email',
  },
});
