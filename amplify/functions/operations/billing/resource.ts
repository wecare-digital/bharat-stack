/**
 * Billing Lambda Resource Definition
 * Fetches AWS Cost Explorer data
 */

import { defineFunction } from '@aws-amplify/backend';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';

export const billingFunction = defineFunction({
  name: 'wecare-billing',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    LOG_LEVEL: 'INFO',
  },
});

// IAM policy for Cost Explorer access
export const billingPolicy = new PolicyStatement({
  effect: Effect.ALLOW,
  actions: [
    'ce:GetCostAndUsage',
    'ce:GetCostForecast',
    'ce:GetDimensionValues',
    'ce:GetTags',
  ],
  resources: ['*'],
});
