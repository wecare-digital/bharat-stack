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
 * - Data: DynamoDB (35 tables)
 * - Storage: S3 (existing buckets)
 * 
 * Lambda functions (47 Python functions) are deployed separately
 * and already exist in AWS. They are not managed by Amplify Gen 2.
 */
const backend = defineBackend({
  auth,
  data,
  storage,
});

/**
 * DynamoDB TTL Configuration
 * 
 * Enable TTL on tables that have expiresAt/ttl fields.
 * Amplify Gen 2 doesn't support TTL natively, so we use CDK overrides.
 */
const TTL_CONFIG: Record<string, string> = {
  Message: 'expiresAt',
  DLQMessage: 'expiresAt',
  AuditLog: 'expiresAt',
  RateLimitTracker: 'lastUpdatedAt',
  VoiceCall: 'expiresAt',
  SmsAws: 'expiresAt',
  VoiceAws: 'expiresAt',
  AirtelSMS: 'expiresAt',
  AirtelC2C: 'expiresAt',
  VoiceCDR: 'expiresAt',
  OBDCampaign: 'ttl',
  WhatsAppVoice: 'expiresAt',
  WhatsAppInbound: 'expiresAt',
  WhatsAppOutbound: 'expiresAt',
};

const dataStack = backend.data.resources.cfnResources;
for (const [modelName, ttlAttribute] of Object.entries(TTL_CONFIG)) {
  const table = dataStack.amplifyDynamoDbTables[modelName];
  if (table) {
    table.addPropertyOverride('TimeToLiveSpecification', {
      AttributeName: ttlAttribute,
      Enabled: true,
    });
  }
}

export default backend;
