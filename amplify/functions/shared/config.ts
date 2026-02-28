/**
 * WECARE.DIGITAL Shared Configuration
 * 
 * Centralized configuration for all Lambda functions.
 * Environment variables override these defaults.
 */

// AWS Region
export const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
export const AWS_ACCOUNT_ID = process.env.AWS_ACCOUNT_ID || '775261844268';

// DynamoDB Tables (actual deployed names)
export const TABLES = {
  CONTACTS: process.env.CONTACTS_TABLE || 'base-wecare-digital-ContactsTable',
  MESSAGES_INBOUND: process.env.MESSAGES_INBOUND_TABLE || 'base-wecare-digital-WhatsAppInboundTable',
  MESSAGES_OUTBOUND: process.env.MESSAGES_OUTBOUND_TABLE || 'base-wecare-digital-WhatsAppOutboundTable',
  BULK_JOBS: process.env.BULK_JOBS_TABLE || 'base-wecare-digital-BulkJobsTable',
  BULK_RECIPIENTS: process.env.BULK_RECIPIENTS_TABLE || 'base-wecare-digital-BulkRecipientsTable',
  USERS: process.env.USERS_TABLE || 'base-wecare-digital-UsersTable',
  MEDIA_FILES: process.env.MEDIA_FILES_TABLE || 'base-wecare-digital-MediaFilesTable',
  DLQ_MESSAGES: process.env.DLQ_MESSAGES_TABLE || 'base-wecare-digital-DLQMessagesTable',
  AUDIT_LOGS: process.env.AUDIT_LOGS_TABLE || 'base-wecare-digital-AuditLogsTable',
  AI_INTERACTIONS: process.env.AI_INTERACTIONS_TABLE || 'base-wecare-digital-AIInteractionsTable',
  RATE_LIMIT: process.env.RATE_LIMIT_TABLE || 'base-wecare-digital-RateLimitTable',
  SYSTEM_CONFIG: process.env.SYSTEM_CONFIG_TABLE || 'base-wecare-digital-SystemConfigTable',
  VOICE_CALLS: process.env.VOICE_CALLS_TABLE || 'base-wecare-digital-VoiceCalls',
  SMS_AWS: process.env.SMS_AWS_TABLE || 'base-wecare-digital-SmsAwsTable',
  VOICE_AWS: process.env.VOICE_AWS_TABLE || 'base-wecare-digital-VoiceAwsTable',
  WIX_PRODUCTS_CACHE: process.env.WIX_PRODUCTS_CACHE_TABLE || 'base-wecare-digital-WixProductsCache',
  WIX_ORDERS_CACHE: process.env.WIX_ORDERS_CACHE_TABLE || 'base-wecare-digital-WixOrdersCache',
};

// Wix Store Configuration
export const WIX_CONFIG = {
  API_BASE_URL: 'https://www.wixapis.com',
  API_KEY: process.env.WIX_API_KEY || '',
  SITE_ID: process.env.WIX_SITE_ID || '',
  ACCOUNT_ID: process.env.WIX_ACCOUNT_ID || '6b2d7a93-ef14-45ab-a04e-d445f599e9f4',
};

// S3 Buckets
export const S3_BUCKETS = {
  MEDIA: 'app.wecare.digital',
  REPORTS: 'app.wecare.digital',
};

// S3 Prefixes
export const S3_PREFIXES = {
  MEDIA_INBOUND: 'whatsapp-media/whatsapp-media-incoming/',
  MEDIA_OUTBOUND: 'whatsapp-media/whatsapp-media-outgoing/',
  REPORTS: 'stream/',
  EXTERNAL_KB: 'stream/gen-ai/external-kb/',
  INTERNAL_KB: 'stream/gen-ai/internal-kb/',
};

// WhatsApp Configuration
export const WHATSAPP_CONFIG = {
  META_API_VERSION: 'v20.0',
  PHONE_NUMBER_ID_1: process.env.WHATSAPP_PHONE_NUMBER_ID_1 || 'phone-number-id-5e020cecd221429996f6ae721cc42206',
  PHONE_NUMBER_ID_2: process.env.WHATSAPP_PHONE_NUMBER_ID_2 || 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c',
  DISPLAY_PHONE_1: '+91 93309 94400',
  DISPLAY_PHONE_2: '+91 99033 00044',
  RATE_LIMIT_PER_SECOND: 80,
};

// SNS Topics
export const SNS_TOPICS = {
  WHATSAPP_EVENTS: `arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:base-wecare-digital`,
};

// Cognito
export const COGNITO_CONFIG = {
  USER_POOL_ID: 'us-east-1_cSx0RHCIR',
  APP_CLIENT_ID: '1j8kbi48m4v2rped3n224rlevb',
  SSO_DOMAIN: 'https://signin.wecare.digital',
};

// Bedrock AI Configuration
export const BEDROCK_CONFIG = {
  // Internal Agent (FloatingAgent - admin tasks)
  INTERNAL_AGENT_ID: process.env.INTERNAL_AGENT_ID || 'QIEEHEBTZO',
  INTERNAL_AGENT_ALIAS: process.env.INTERNAL_AGENT_ALIAS || 'ASCBD7YPUT',
  INTERNAL_KB_ID: process.env.INTERNAL_KB_ID || 'static-faq',
  
  // External Agent (WhatsApp auto-reply - customer facing)
  EXTERNAL_AGENT_ID: process.env.EXTERNAL_AGENT_ID || 'Z4YAK0ZLBO',
  EXTERNAL_AGENT_ALIAS: process.env.EXTERNAL_AGENT_ALIAS || 'WANPKHQGIB',
  EXTERNAL_KB_ID: process.env.EXTERNAL_KB_ID || 'static-faq',
  
  // Model
  FOUNDATION_MODEL: 'amazon.nova-lite-v1:0',
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
