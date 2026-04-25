/**
 * WECARE.DIGITAL Shared Configuration
 * 
 * Centralized configuration for all Lambda functions.
 * Environment variables override these defaults.
 */

// AWS Region
export const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
export const AWS_ACCOUNT_ID = process.env.AWS_ACCOUNT_ID || '';

// DynamoDB Tables (actual deployed names)
export const TABLES = {
  CONTACTS: process.env.CONTACTS_TABLE || 'stack-wecare-digital-ContactsTable',
  MESSAGES_INBOUND: process.env.MESSAGES_INBOUND_TABLE || 'stack-wecare-digital-WhatsAppInboundTable',
  MESSAGES_OUTBOUND: process.env.MESSAGES_OUTBOUND_TABLE || 'stack-wecare-digital-WhatsAppOutboundTable',
  BULK_JOBS: process.env.BULK_JOBS_TABLE || 'stack-wecare-digital-BulkJobsTable',
  BULK_RECIPIENTS: process.env.BULK_RECIPIENTS_TABLE || 'stack-wecare-digital-BulkRecipientsTable',
  USERS: process.env.USERS_TABLE || 'stack-wecare-digital-UsersTable',
  MEDIA_FILES: process.env.MEDIA_FILES_TABLE || 'stack-wecare-digital-MediaFilesTable',
  DLQ_MESSAGES: process.env.DLQ_MESSAGES_TABLE || 'stack-wecare-digital-DLQMessagesTable',
  AUDIT_LOGS: process.env.AUDIT_LOGS_TABLE || 'stack-wecare-digital-AuditLogsTable',
  AI_INTERACTIONS: process.env.AI_INTERACTIONS_TABLE || 'stack-wecare-digital-AIInteractionsTable',
  RATE_LIMIT: process.env.RATE_LIMIT_TABLE || 'stack-wecare-digital-RateLimitTable',
  SYSTEM_CONFIG: process.env.SYSTEM_CONFIG_TABLE || 'stack-wecare-digital-SystemConfigTable',
  VOICE_CALLS: process.env.VOICE_CALLS_TABLE || 'stack-wecare-digital-VoiceCalls',
  SMS_AWS: process.env.SMS_AWS_TABLE || 'stack-wecare-digital-SmsAwsTable',
  VOICE_AWS: process.env.VOICE_AWS_TABLE || 'stack-wecare-digital-VoiceAwsTable',
  WIX_PRODUCTS_CACHE: process.env.WIX_PRODUCTS_CACHE_TABLE || 'stack-wecare-digital-WixProductsCache',
  WIX_ORDERS_CACHE: process.env.WIX_ORDERS_CACHE_TABLE || 'stack-wecare-digital-WixOrdersCache',
};

// Wix Store Configuration
export const WIX_CONFIG = {
  API_BASE_URL: 'https://www.wixapis.com',
  API_KEY: process.env.WIX_API_KEY || '',
  SITE_ID: process.env.WIX_SITE_ID || '',
  ACCOUNT_ID: process.env.WIX_ACCOUNT_ID || '',
};

// S3 Buckets
export const S3_BUCKETS = {
  MEDIA: 'app.wecare.digital',
  REPORTS: 'app.wecare.digital',
};

// S3 Prefixes
// User/transactional data under stack/ (factory reset = wipe stack/ only)
// Static internal assets under stream/ (never wiped)
export const S3_PREFIXES = {
  MEDIA_INBOUND: 'stack/whatsapp-media/incoming/',
  MEDIA_OUTBOUND: 'stack/whatsapp-media/outgoing/',
  REPORTS: 'stack/reports/',
};

// WhatsApp Configuration
export const WHATSAPP_CONFIG = {
  META_API_VERSION: 'v25.0',
  PHONE_NUMBER_ID_1: process.env.WHATSAPP_PHONE_NUMBER_ID_1 || 'phone-number-id-waba1-direct-1016149501586345',
  PHONE_NUMBER_ID_2: process.env.WHATSAPP_PHONE_NUMBER_ID_2 || 'phone-number-id-waba-t-direct-1055232054343117',
  DISPLAY_PHONE_1: '+91 93309 94400',
  DISPLAY_PHONE_2: '+91 99033 00044',
  // New WABA IDs after migration
  WABA_ID_1: '2094615664435155',  // WECARE.DIGITAL (Direct API, current)
  WABA_ID_2: '2513394156072604',  // Manish Agarwal (migrated, Direct API)
  WABA_ID_3: '2094615664435155',  // WECARE.DIGITAL (Direct API, SIP calling, primary)
  RATE_LIMIT_PER_SECOND: 80,
};

// SNS Topics
export const SNS_TOPICS = {
  WHATSAPP_EVENTS: `arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:stack-wecare-digital`,
};

// Cognito
export const COGNITO_CONFIG = {
  USER_POOL_ID: 'us-east-1_cSx0RHCIR',
  APP_CLIENT_ID: '1j8kbi48m4v2rped3n224rlevb',
  SSO_DOMAIN: 'https://signin.wecare.digital',
};

// Bedrock AI Configuration
// Architecture:
//   - SEO Audit: InvokeModel (Claude Opus 4.6 → Nova Pro fallback) via bedrock.ts
//   - WhatsApp Auto-Reply: Converse API (Nova Lite) — no agent needed
//   - Internal Admin: Converse API (Nova Lite) — agent optional, Converse works standalone
//   - WhatsApp Voice/Calling: Converse API (Nova Lite) — agent fallback if configured
//
// Agent Status (2026-04-25):
//   - 4UUQYFWX64 (wecare-digital-agent): NOT_PREPARED — needs action groups + prepare
//   - Old IDs (QIEEHEBTZO, Z4YAK0ZLBO): no longer exist
//
// Foundation Models (confirmed working):
//   - amazon.nova-pro-v1:0: SEO audit quality (confirmed working)
//   - amazon.nova-lite-v1:0: WhatsApp/admin tasks (confirmed working)
//   - us.anthropic.claude-opus-4-6-v1: SEO audit premium (agreement accepted, payment propagating)
export const BEDROCK_CONFIG = {
  // Internal Agent (FloatingAgent - admin tasks)
  // Falls back to Converse API if agent is not prepared
  INTERNAL_AGENT_ID: process.env.INTERNAL_AGENT_ID || '4UUQYFWX64',
  INTERNAL_AGENT_ALIAS: process.env.INTERNAL_AGENT_ALIAS || 'TSTALIASID',
  INTERNAL_KB_ID: process.env.INTERNAL_KB_ID || 'static-faq',
  
  // External (WhatsApp auto-reply) — uses Converse API directly, no agent needed
  EXTERNAL_AGENT_ID: process.env.EXTERNAL_AGENT_ID || '4UUQYFWX64',
  EXTERNAL_AGENT_ALIAS: process.env.EXTERNAL_AGENT_ALIAS || 'TSTALIASID',
  EXTERNAL_KB_ID: process.env.EXTERNAL_KB_ID || 'static-faq',
  
  // Models
  FOUNDATION_MODEL: 'amazon.nova-lite-v1:0',
  FOUNDATION_MODEL_PRO: 'amazon.nova-pro-v1:0',
  SEO_MODEL: process.env.BEDROCK_MODEL_ID || 'us.anthropic.claude-opus-4-6-v1',
  MODEL_ARN: 'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0',
};

// TTL Configuration (in seconds)
export const TTL_CONFIG = {
  MESSAGES: 30 * 24 * 60 * 60,      // 30 days
  DLQ_MESSAGES: 7 * 24 * 60 * 60,   // 7 days
  AUDIT_LOGS: 180 * 24 * 60 * 60,   // 180 days
  RATE_LIMIT: 24 * 60 * 60,         // 24 hours
  VOICE_CALLS: 90 * 24 * 60 * 60,   // 90 days
};

// Rate Limits
export const RATE_LIMITS = {
  WHATSAPP_PER_SECOND: 80,
  SMS_PER_SECOND: 5,
  EMAIL_PER_SECOND: 10,
  API_PER_SECOND: 1000,
};

// CloudWatch Metrics
export const METRICS_NAMESPACE = 'WECARE.DIGITAL';
