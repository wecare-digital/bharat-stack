import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';
import { storage } from './storage/resource';
import { seoTools } from './functions/operations/seo-tools/resource';
import { addLinkResources } from './link-resources';
import { addBackendResources } from './backend-resources';
import { addSeoResources } from './seo-resources';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';

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
 * - URL Shortener (r.wecare.digital): API Gateway + Lambda + DynamoDB + Route53
 * - Durable Admin SEO audit/log storage and Lambda
 *
 * Lambda functions (42+ Python functions) are deployed separately
 * and already exist in AWS. They are not managed by Amplify Gen 2.
 */
const backend = defineBackend( {
  auth,
  data,
  storage,
  seoTools,
} );

// ─── DynamoDB TTL Configuration ──────────────────────────────────────
// Enable TTL on tables that have expiresAt/ttl fields.
// Amplify Gen 2 doesn't support TTL natively, so we use CDK overrides.
// NOTE: TTL is also enforced directly on the physical tables via
// scripts/_fix_ddb_ttl.py (the CDK override below historically failed silently).
// RateLimitTracker is intentionally OMITTED: its only time field is 'lastUpdatedAt',
// which is NOT an expiry — enabling TTL on it would purge the entire table.
const TTL_CONFIG: Record<string, string> = {
  Message: 'expiresAt',
  DLQMessage: 'expiresAt',
  AuditLog: 'expiresAt',
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
 * SEO Tools Resources
 * Creates retained durable audit/log state. The Admin-only SEO Lambda is
 * Amplify-managed, while routes are registered separately after canary approval.
 */
const seoTable = addSeoResources( dataStack );
seoTable.grantReadWriteData( backend.seoTools.resources.lambda );
( backend.seoTools.resources.lambda as lambda.Function ).addEnvironment(
  'COGNITO_USER_POOL_ID',
  backend.auth.resources.userPool.userPoolId,
);

const dedupTable = dynamodb.Table.fromTableName(
  dataStack,
  'SeoAdminDedupTable',
  'stack-wecare-digital-WebhookDedup',
);
dedupTable.grantWriteData( backend.seoTools.resources.lambda );

const wixApiKey = secretsmanager.Secret.fromSecretNameV2(
  dataStack,
  'SeoWixApiKeySecret',
  'wecare/wix-api-key',
);
wixApiKey.grantRead( backend.seoTools.resources.lambda );

backend.seoTools.resources.lambda.addToRolePolicy( new iam.PolicyStatement( {
  actions: [ 'bedrock:InvokeModel' ],
  resources: [
    'arn:aws:bedrock:*::foundation-model/*',
    `arn:aws:bedrock:*:${dataStack.account}:inference-profile/*`,
    `arn:aws:bedrock:*:${dataStack.account}:application-inference-profile/*`,
  ],
} ) );
backend.seoTools.resources.lambda.addToRolePolicy( new iam.PolicyStatement( {
  actions: [ 'cognito-idp:GetUser', 'cognito-idp:AdminListGroupsForUser' ],
  resources: [ backend.auth.resources.userPool.userPoolArn ],
} ) );

export default backend;
