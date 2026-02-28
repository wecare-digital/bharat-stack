import { defineFunction } from '@aws-amplify/backend';

/**
 * AI Generate Response Lambda Function
 * 
 * INTERNAL: Bedrock Agent (FloatingAgent) for admin tasks
 * EXTERNAL: Bedrock Converse API (Nova Lite) for WhatsApp auto-reply
 *   - Multimodal: text, images, audio, video, documents
 *   - Conversation history via DynamoDB (with idle timeout)
 *   - Processing lock to prevent duplicate AI calls
 *   - Bedrock Guardrails integration
 *   - KB retrieval for grounded answers
 *   - Intent classification + human escalation
 *   - Tool use via Converse API toolConfig (KB search, contact lookup, brand info)
 *   - Message size validation (truncation)
 */
export const aiGenerateResponse = defineFunction({
  name: 'wecare-ai-generate-response',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 120, // Increased for multimodal processing
  memoryMB: 1024, // Increased for media handling
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    SEND_MODE: 'LIVE',
    // Internal Agent (FloatingAgent — admin tasks, unchanged)
    INTERNAL_AGENT_ID: 'QIEEHEBTZO',
    INTERNAL_AGENT_ALIAS: 'ASCBD7YPUT',
    INTERNAL_KB_ID: 'D0JU8Q7IQS',
    // External (WhatsApp — Converse API)
    EXTERNAL_KB_ID: 'static-faq',
    MODEL_ID: 'amazon.nova-lite-v1:0',
    GUARDRAIL_ID: '', // Set to your Bedrock Guardrail ID when created
    GUARDRAIL_VERSION: 'DRAFT',
    // Media
    MEDIA_BUCKET: 'app.wecare.digital',
    // Contacts table (for tool use — contact lookup)
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    // System config (for bot flow config — dashboard manageable)
    SYSTEM_CONFIG_TABLE: 'base-wecare-digital-SystemConfigTable',
    // Conversation history
    CONVERSATION_TABLE: 'base-wecare-digital-ConversationHistoryTable',
    // Messages table (for payment due checks)
    MESSAGES_TABLE: 'base-wecare-digital-WhatsAppInboundTable',
    MAX_HISTORY_MESSAGES: '20',
    MAX_SESSION_MESSAGES: '50',
    CONVERSATION_TTL_HOURS: '24',
    // Session idle timeout (minutes) — reset conversation if idle
    SESSION_IDLE_TIMEOUT_MINUTES: '15',
    // Input text size limit — truncate to prevent token abuse
    MAX_INPUT_TEXT_LENGTH: '2000',
  },
});
