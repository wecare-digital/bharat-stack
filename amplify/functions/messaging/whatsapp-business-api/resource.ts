import { defineFunction } from '@aws-amplify/backend';

export const whatsappBusinessApi = defineFunction({
  name: 'wecare-whatsapp-business-api',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    META_API_VERSION: 'v20.0',
    META_TOKEN_SECRET: 'wecare/meta-system-user-token',
  },
});
