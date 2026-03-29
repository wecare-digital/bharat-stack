import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';
import { storage } from './storage/resource';
import { addLinkResources } from './link-resources';

/**
 * WECARE.DIGITAL Admin Platform Backend
 * 
 * AWS Account: 775261844268
 * Region: us-east-1
 * 
 * This backend defines:
 * - Auth: Cognito (existing user pool)
 * - Data: DynamoDB (41 tables)
 * - Storage: S3 (existing buckets)
 * 
 * Lambda functions (42 Python functions) are deployed separately
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
  WebhookDedup: 'ttl',
  SystemEvent: 'ttl',
  CatalogCache: 'ttl',
  AdClickAttribution: 'ttl',
  WhatsAppCalling: 'ttl',
  RazorpayWebhookLog: 'expiresAt',
  PayUWebhookLog: 'expiresAt',
};

try {
  const dataStack = backend.data.resources.cfnResources;
  for (const [modelName, ttlAttribute] of Object.entries(TTL_CONFIG)) {
    const table = dataStack.amplifyDynamoDbTables[modelName];
    if (table) {
      (table as any).addPropertyOverride('TimeToLiveSpecification', {
        AttributeName: ttlAttribute,
        Enabled: true,
      });
    }
  }
} catch (e) {
  // TTL override may fail in some Amplify Gen 2 versions — log and continue
  console.warn('TTL CDK override skipped:', e);
}

export default backend;

/**
 * URL Shortener Resources
 * Creates Route53 CNAME for r.wecare.digital -> API Gateway,
 * DynamoDB tables, ACM cert, and Lambda integration.
 */
const linkStack = backend.data.resources.stacks['data'];
addLinkResources(linkStack);
