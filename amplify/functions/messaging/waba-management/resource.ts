/**
 * WABA Management Lambda Function Resource
 * 
 * Manages WhatsApp Business Accounts via AWS EUM Social API:
 * - GetLinkedWhatsAppBusinessAccount - Get WABA details (phone quality, limits)
 * - GetLinkedWhatsAppBusinessAccountPhoneNumber - Get phone details
 * - ListLinkedWhatsAppBusinessAccounts - List all WABAs
 * - DeleteWhatsAppMessageMedia - Delete uploaded media
 */

import { defineFunction } from '@aws-amplify/backend';

export const wabaManagement = defineFunction({
  name: 'wecare-waba-management',
  entry: './handler.py',
  runtime: 20,  // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    LOG_LEVEL: 'INFO',
    SYSTEM_CONFIG_TABLE: 'stack-wecare-digital-SystemConfigTable',
    SNS_TOPIC_ARN: `arn:aws:sns:us-east-1:${process.env.AWS_ACCOUNT_ID || '775261844268'}:stack-wecare-digital`,
  },
});
