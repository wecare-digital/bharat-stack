/**
 * System Cleanup Lambda Resource Definition
 * Selective cleanup of DynamoDB tables and S3 prefixes
 */

import { defineFunction } from '@aws-amplify/backend';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';

export const systemCleanupFunction = defineFunction({
  name: 'wecare-system-cleanup',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 300,
  memoryMB: 512,
  environment: {
    LOG_LEVEL: 'INFO',
    MEDIA_BUCKET: 'app.wecare.digital',
  },
});

export const systemCleanupPolicy = new PolicyStatement({
  effect: Effect.ALLOW,
  actions: [
    'dynamodb:Scan',
    'dynamodb:DeleteItem',
    'dynamodb:BatchWriteItem',
    'dynamodb:DescribeTable',
    's3:ListBucket',
    's3:DeleteObject',
    's3:DeleteObjects',
  ],
  resources: ['*'],
});
