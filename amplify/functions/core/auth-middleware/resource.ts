import { defineFunction } from '@aws-amplify/backend';

export const authMiddleware = defineFunction({
  name: 'wecare-auth-middleware',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30, // Cognito API calls can be slow
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    COGNITO_USER_POOL_ID: 'us-east-1_cSx0RHCIR',
  },
});
