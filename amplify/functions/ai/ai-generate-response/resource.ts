import { defineFunction } from '@aws-amplify/backend';

/**
 * AI Generate Response Lambda Function
 * 
 * Purpose: Generate AI response using Bedrock Agent with Knowledge Base
 * Uses Internal Agent for FloatingAgent, External Agent for WhatsApp auto-reply
 */
export const aiGenerateResponse = defineFunction({
  name: 'wecare-ai-generate-response',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    SEND_MODE: 'LIVE',
    // Internal Agent (FloatingAgent - admin tasks)
    INTERNAL_AGENT_ID: 'QIEEHEBTZO',
    INTERNAL_AGENT_ALIAS: 'ASCBD7YPUT',
    INTERNAL_KB_ID: 'D0JU8Q7IQS',
    // External Agent (WhatsApp auto-reply - customer facing)
    EXTERNAL_AGENT_ID: 'Z4YAK0ZLBO',
    EXTERNAL_AGENT_ALIAS: 'WANPKHQGIB',
    EXTERNAL_KB_ID: 'LYMQLKZNY7',
  },
});
