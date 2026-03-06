import { defineFunction } from '@aws-amplify/backend';

export const aiConfigManagement = defineFunction({
  name: 'wecare-ai-config-management',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    LOG_LEVEL: 'INFO',
    SYSTEM_CONFIG_TABLE: 'stack-wecare-digital-SystemConfigTable',
    AI_INTERACTIONS_TABLE: 'stack-wecare-digital-AIInteractionsTable',
  },
});
