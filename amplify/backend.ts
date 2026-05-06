import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';
import { storage } from './storage/resource';
import { addLinkResources } from './link-resources';
import { addBackendResources } from './backend-resources';
import { addPushResources } from './push-resources';

/**
 * WECARE.DIGITAL Admin Platform Backend
 *
 * AWS Account: 775261844268
 * Region: us-east-1
 *
 * This backend defines:
 * - Auth: Cognito (existing user pool via referenceAuth)
 * - Data: DynamoDB (~58 tables via AppSync)
 * - Storage: S3 (existing bucket: app.wecare.digital)
 *
 * Additional CDK resources:
 * - SQS Queues (4): inbound-dlq, bulk-queue, bulk-dlq, outbound-dlq
 * - CloudWatch Alarms, Dashboard, Log Retention
 * - WAF Web ACL for webhook endpoints
 * - Push Notification infrastructure (DynamoDB + SNS)
 * - URL Shortener (r.wecare.digital): API Gateway + Lambda + DynamoDB + Route53
 *
 * Lambda functions (42+ Python functions) are deployed separately
 * and already exist in AWS. They are not managed by Amplify Gen 2.
 */
const backend = defineBackend( {
  auth,
  data,
  storage,
} );

// ─── DynamoDB TTL Configuration ──────────────────────────────────────
// Enable TTL on tables that have expiresAt/ttl fields.
// Amplify Gen 2 doesn't support TTL natively, so we use CDK overrides.
const TTL_CONFIG: Record<string, string> = {
  Message: 'expiresAt',
  DLQMessage: 'expiresAt',
  AuditLog: 'expiresAt',
  RateLimitTracker: 'lastUpdatedAt',
  VoiceCall: 'expiresAt',
  SmsAws: 'expiresAt',
  VoiceAws: 'expiresAt',
  AirtelSMS: 'expiresAt',
  RcsMessages: 'expiresAt',
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

try
{
  const dataStack = backend.data.resources.cfnResources;
  for ( const [ modelName, ttlAttribute ] of Object.entries( TTL_CONFIG ) )
  {
    const table = dataStack.amplifyDynamoDbTables[ modelName ];
    if ( table )
    {
      ( table as any ).addPropertyOverride( 'TimeToLiveSpecification', {
        AttributeName: ttlAttribute,
        Enabled: true,
      } );
    }
  }
} catch ( e )
{
  // TTL override may fail in some Amplify Gen 2 versions — log and continue
  console.warn( 'TTL CDK override skipped:', e );
}

// ─── Additional CDK Resources ────────────────────────────────────────
// All additional infrastructure is attached to the data stack so it
// deploys as part of the Amplify backend.
const dataStack = backend.data.resources.stacks[ 'data' ];

/**
 * URL Shortener Resources
 * Creates Route53 CNAME for r.wecare.digital -> API Gateway,
 * DynamoDB tables, ACM cert, and Lambda integration.
 */
addLinkResources( dataStack );

/**
 * Backend Infrastructure Resources
 * Creates SQS queues, CloudWatch alarms/dashboard, log retention,
 * WAF Web ACL, and per-Lambda error alarms.
 */
addBackendResources( dataStack );

/**
 * Push Notification Resources
 * Creates PushTokensTable (DynamoDB) and IAM policies for
 * SNS platform application access (FCM + APNs).
 */
addPushResources( dataStack );

export default backend;
