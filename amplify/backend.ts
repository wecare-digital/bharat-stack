import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';
import { storage } from './storage/resource';

/**
 * WECARE.DIGITAL Admin Platform Backend
 * 
 * AWS Account: 775261844268
 * Region: us-east-1
 * 
 * This backend defines:
 * - Auth: Cognito (existing user pool)
 * - Data: DynamoDB (24 tables)
 * - Storage: S3 (existing buckets)
 * 
 * Lambda functions (43 Python functions) are deployed separately
 * and already exist in AWS. They are not managed by Amplify Gen 2.
 */
const backend = defineBackend({
  auth,
  data,
  storage,
});

export default backend;
