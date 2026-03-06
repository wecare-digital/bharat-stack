/**
 * Template Analytics Lambda Resource Definition
 * Aggregates template message metrics
 */

import { defineFunction } from '@aws-amplify/backend';

export const templateAnalyticsFunction = defineFunction({
  name: 'wecare-template-analytics',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    OUTBOUND_TABLE: 'stack-wecare-digital-WhatsAppOutboundTable',
    LOG_LEVEL: 'INFO',
  },
});
