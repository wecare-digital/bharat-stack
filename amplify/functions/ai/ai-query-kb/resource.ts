import { defineFunction } from '@aws-amplify/backend';

/**
 * AI Query Knowledge Base Lambda Function
 * 
 * Purpose: Query Bedrock Knowledge Base for context
 * Uses External KB for WhatsApp auto-reply, Internal KB for admin tasks
 */
export const aiQueryKb = defineFunction({
  name: 'wecare-ai-query-kb',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    SEND_MODE: 'LIVE',
    INTERNAL_KB_ID: 'static-faq',
    EXTERNAL_KB_ID: 'static-faq',
  },
});
