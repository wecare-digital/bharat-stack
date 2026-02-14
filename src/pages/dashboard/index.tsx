/**
 * Unified Dashboard - WECARE.DIGITAL
 * Clean tabbed interface with Overview, Messages, Payments, Data, Billing
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Layout from '../../components/Layout';
import Link from 'next/link';
import { BarChart, DonutChart, Sparkline, ProgressBar, DateRangePicker } from '../../components/Charts';
import { SkeletonStat, SkeletonCard } from '../../components/Skeleton';
import SEO, { PAGE_SEO } from '../../components/SEO';
import Button from '../../components/ui/Button';
import Tabs, { TabItem } from '../../components/ui/Tabs';
import * as api from '../../api/client';
import { 
  DashboardIcon, MessageIcon, PaymentIcon, DataIcon, BillingIcon, 
  AIIcon, LinkIcon, SearchIcon, WhatsAppIcon, InvoiceIcon, 
  ContactsIcon, BulkIcon, SmsIcon, EmailIcon, RefreshIcon,
  DocumentIcon, HealthIcon, AdvisorIcon
} from '../../lib/icons';
import { AWS_ACCOUNT_ID, AWS_REGION, PAYMENT_CONFIG, API_BASE } from '../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'overview' | 'messages' | 'pay' | 'data' | 'billing' | 'health' | 'advisor' | 'search' | 'ai' | 'botflow' | 'webhook' | 'guide';

const PAYMENT_PHONE = PAYMENT_CONFIG.phoneDisplay;
const PAYMENT_NAME = PAYMENT_CONFIG.phoneName;

const AIRTEL_REFERENCE_TEXT = `WECARE.DIGITAL - AIRTEL INTEGRATION DETAILS
============================================

CUSTOMER DETAILS:
━━━━━━━━━━━━━━━━━
Customer ID: WECAREDIG_v6J1SyLLI2auy7Lw9JrW
App ID: WECAREDIG_fD4BKqUbC8k90jNrPR0n
Contact Email: voice@wecare.digital
Inbound Number: +91 9319767034

CALLER IDs:
━━━━━━━━━━━
C2C Caller ID: 8047311032
OBD Caller ID: 8040761117

SMS CONFIGURATION:
━━━━━━━━━━━━━━━━━━
Sender ID: WDBEEP
Entity ID (PE ID): 1201161991108627443
Default DLT Template ID: 1007974344269130859
API Host: iqmessaging.airtel.in
Auth: Basic (base64 of username:password)
  Kong Username: WECAREDIG_v6J1SyLLI2auy7Lw9JrW
  Kong Password: sN$~|(I@112
  Base64 Token: V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy

SMS API Versions:
• v4 Single/Multiple SMS:  POST https://iqmessaging.airtel.in/api/v4/send-sms
• v5 Content Moderation:   POST https://iqmessaging.airtel.in/api/v5/send-sms-cm
• v6 Enhanced Response:    POST https://iqmessaging.airtel.in/api/v6/send-sms
• Bulk SMS (Conduit):      POST https://iqmessaging.airtel.in/conduit/api/v1/send-sms-bulk

v4/v5/v6 Headers: Authorization: Basic <token>, Content-Type: application/json, customerId
Bulk/Conduit Headers: Authorization: Basic <token>, Content-Type: application/json (NO customerId)

NOTE: v4 destinationAddress is an array — supports single AND multiple recipients in one call.
      Bulk (Conduit) is a different format: array of objects with msisdn, content, header, etc.

DLT Requirements (TRAI TCCCPR 2019):
• PE ID (entityId): 1201161991108627443
• Sender ID (header): WDBEEP — registered on DLT portal
• Content Template ID (dltTemplateId): must be registered on DLT portal
• MSISDN: 10 or 12 digits (India)
• v5 does NOT require DLT fields (content moderation auto-handles)
• Promotional messages: No DLR sent back (except NACK from DLT)

Message Types: PROMOTIONAL, TRANSACTIONAL, SERVICE_IMPLICIT, SERVICE_EXPLICIT
OTP: Set otp=true with SERVICE_IMPLICIT for OTP traffic
metaData: Optional key-value map, flows end-to-end to IQ reporting and callbacks

ALL WEBHOOK URLs:
━━━━━━━━━━━━━━━━━
API Base: https://api.wecare.digital

1. SMS-IN (Send SMS via our API — supports v4/v5/v6 + bulk):
   POST /sms-in/airtel
   Full URL: https://api.wecare.digital/sms-in/airtel
   Also: GET (list), DELETE (delete msg), DELETE /clear-logs
   Templates: GET/POST/DELETE /sms-in/airtel/templates

2. Voice Click-to-Call (C2C):
   POST /voice-in/c2c
   Full URL: https://api.wecare.digital/voice-in/c2c

3. Voice OBD (Outbound Dialer):
   POST /voice-in/obd
   Full URL: https://api.wecare.digital/voice-in/obd

4. Voice CDR Webhook (Airtel → Us, for ALL callbacks - inbound & outbound):
   POST /voice-cdr-webhook
   Full URL: https://api.wecare.digital/voice-cdr-webhook

5. Voice CDR Read (Dashboard / UI - read CDRs with stats):
   GET /voice-cdr-read
   Full URL: https://api.wecare.digital/voice-cdr-read
   Params: ?callType=INBOUND&status=Answered&dashboard=true&limit=50

6. WhatsApp Calling Webhook (Meta → Us, for call events):
   GET  /whatsapp-calling  (webhook verification)
   POST /whatsapp-calling  (call events: connect, terminate, permission)
   Full URL: https://api.wecare.digital/whatsapp-calling
   Verify Token: wecare_calling_verify_2026
   Subscribed Fields: calls
   Lambda: wecare-whatsapp-calling

IP WHITELIST:
━━━━━━━━━━━━
We do NOT need to whitelist IPs for sending SMS traffic.
However, if encountering 403 errors on API calls, please whitelist
these Airtel API IPs on your server and retry:
• 125.19.17.212
• 125.17.6.54
• 122.187.47.153

CLICK-TO-CALL (C2C) CALLBACK BODY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
We accept the DEFAULT Airtel callback body format.
The callback body is NOT customized from our end.
No custom callback body configuration needed from Airtel side.

C2C CDR callbacks can be sent to ANY of these URLs (all accept CDR):
• https://api.wecare.digital/voice-cdr-webhook  (preferred)
• https://api.wecare.digital/voice-in/c2c       (also accepts CDR callbacks)

OBD CALLBACK BODY:
━━━━━━━━━━━━━━━━━━
We accept the DEFAULT Airtel callback body format (both camelCase and Display_Format).
No custom callback body configuration needed from Airtel side.

OBD CDR callbacks can be sent to ANY of these URLs (all accept CDR):
• https://api.wecare.digital/voice-cdr-webhook  (preferred)
• https://api.wecare.digital/voice-in/obd       (also accepts CDR callbacks)

CDR WEBHOOK (INBOUND + OUTBOUND):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The /voice-cdr-webhook handles CDRs for ALL call types:
• INBOUND calls (direct calls to +91 9319767034)
• OUTBOUND calls (C2C initiated calls)
• OUTBOUND calls (OBD campaign calls)

We accept BOTH Airtel CDR formats:
• Format A (camelCase): vmSessionId, callerNumber, overallCallStatus, etc.
• Format B (Display): Session_ID, Caller_Number, Overall_Call_Status, etc.

OLD WEBHOOK URL (DEPRECATED - DO NOT USE):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook
→ REPLACE WITH: https://api.wecare.digital/voice-cdr-webhook

Expected CDR callback fields:
{
  "vmSessionId": "unique-session-id",
  "clientCorrelationId": "xchange-tracking-id",
  "callType": "INBOUND" | "OUTBOUND",
  "overallCallStatus": "Answered" | "Missed" | "Busy" | "Disconnected",
  "callerNumber": "9876543210",
  "destinationNumber": "9123456789",
  "duration": 45000,           // milliseconds
  "conversationDuration": 40000,
  "billableDuration": 40000,
  "hangUpStatus": "USER_INITIATED" | "SYSTEM_INITIATED",
  "recordingURL": "https://...",
  "timestamp": "2024-01-15T10:30:00Z"
}

SAMPLE callBackURLs FOR C2C/OBD API:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"callBackURLs": [
  {
    "eventType": "CDR",
    "notifyURL": "https://api.wecare.digital/voice-cdr-webhook",
    "method": "POST",
    "headers": {}
  },
  {
    "eventType": "ALL",
    "notifyURL": "https://api.wecare.digital/voice-cdr-webhook",
    "method": "POST",
    "headers": {}
  }
]

ISSUES / NOTES:
━━━━━━━━━━━━━━━
• All endpoints return HTTP 200 OK on successful receipt
• Content-Type: application/json
• Domain to whitelist: api.wecare.digital
• Recordings are stored in S3: s3://app.wecare.digital/voice/
• If 403 errors persist after IP whitelisting, check API Gateway resource policy
• SMS does NOT require IP whitelisting for sending traffic
• OLD URL DEPRECATED: k4vqzmi07b.execute-api.us-east-1.amazonaws.com → use api.wecare.digital
• CDR callbacks accepted on ALL voice endpoints (/voice-cdr-webhook, /voice-in/c2c, /voice-in/obd)
• Both Airtel CDR formats accepted (camelCase and Display_Format with underscores)

Thank you,
WECARE.DIGITAL Team`;

interface InternalAIConfig {
  enabled: boolean;
  agentId: string;
  agentAlias: string;
  knowledgeBaseId: string;
  modelId: string;
  maxTokens: number;
  temperature: number;
  systemPrompt: string;
}

const DEFAULT_AI_CONFIG: InternalAIConfig = {
  enabled: true,
  agentId: 'QIEEHEBTZO',
  agentAlias: 'ASCBD7YPUT',
  knowledgeBaseId: 'D0JU8Q7IQS',
  modelId: 'amazon.nova-lite-v1:0',
  maxTokens: 1024,
  temperature: 0.7,
  systemPrompt: `You are WECARE.DIGITAL's internal admin assistant.
Help operators with:
- Sending WhatsApp messages
- Finding and managing contacts
- Checking message statistics
- Answering questions about the platform`,
};

interface WebhookConfig {
  id: string;
  name: string;
  url: string;
  events: string[];
  enabled: boolean;
  secret?: string;
  createdAt: string;
}

// AWS Resource ARNs for billing display - uses centralized AWS_ACCOUNT_ID and AWS_REGION
// Comprehensive list including used and available services for future updates
const AWS_RESOURCES: Record<string, { arn: string; accountId: string; details?: string[] }> = {
  // COMPUTE
  'AWS Lambda': { 
    arn: `arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: [
      'wecare-outbound-whatsapp',
      'wecare-inbound-whatsapp', 
      'wecare-contacts-create',
      'wecare-contacts-delete',
      'wecare-contacts-search',
      'wecare-messages-read',
      'wecare-messages-delete',
      'wecare-whatsapp-templates',
      'wecare-ai-generate-response',
      'wecare-ai-query-kb',
      'wecare-outbound-sms',
      'wecare-bulk-job-control',
      'wecare-dlq-replay',
      'wecare-sms-aws (Pinpoint SMS v2)',
      'wecare-voice-aws (Pinpoint Voice v2)',
      'wecare-voice-in-c2c (Airtel C2C)',
      'wecare-voice-in-obd (Airtel OBD)',
      'wecare-voice-cdr (Airtel CDR)',
      'wecare-sms-in-airtel (Airtel SMS)',
      'wecare-billing',
      'wecare-scheduled-messages',
      'wecare-template-analytics',
      'wecare-waba-management',
      'wecare-ai-config-management',
      'wecare-ai-agent-action-group'
    ]
  },
  'Amazon EC2': { 
    arn: `arn:aws:ec2:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon ECS': { 
    arn: `arn:aws:ecs:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'AWS Fargate': { 
    arn: `arn:aws:ecs:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  
  // DATABASE
  'Amazon DynamoDB': { 
    arn: `arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/*`, 
    accountId: AWS_ACCOUNT_ID,
    details: [
      'base-wecare-digital-ContactsTable',
      'base-wecare-digital-WhatsAppOutboundTable',
      'base-wecare-digital-MediaFilesTable',
      'base-wecare-digital-RateLimitTable',
      'base-wecare-digital-SmsAwsTable (Pinpoint SMS logs)',
      'base-wecare-digital-VoiceAwsTable (Pinpoint Voice logs)',
      'base-wecare-digital-VoiceInC2CTable (Airtel C2C)',
      'base-wecare-digital-VoiceInOBDTable (Airtel OBD)',
      'base-wecare-digital-VoiceCDRTable (Airtel CDR)',
      'base-wecare-digital-SmsInAirtelTable (Airtel SMS)',
      'base-wecare-digital-ScheduledMessagesTable',
      'base-wecare-digital-TemplateAnalyticsTable'
    ]
  },
  'Amazon RDS': { 
    arn: `arn:aws:rds:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon Aurora': { 
    arn: `arn:aws:rds:${AWS_REGION}:${AWS_ACCOUNT_ID}:cluster:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon ElastiCache': { 
    arn: `arn:aws:elasticache:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  
  // STORAGE
  'Amazon S3': { 
    arn: 'arn:aws:s3:::app.wecare.digital', 
    accountId: AWS_ACCOUNT_ID,
    details: ['app.wecare.digital - Media storage for WhatsApp']
  },
  'Amazon EBS': { 
    arn: `arn:aws:ec2:${AWS_REGION}:${AWS_ACCOUNT_ID}:volume/*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon EFS': { 
    arn: `arn:aws:elasticfilesystem:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  
  // NETWORKING & CDN
  'Amazon CloudFront': { 
    arn: `arn:aws:cloudfront::${AWS_ACCOUNT_ID}:distribution/*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['CDN for static assets']
  },
  'Amazon Route 53': { 
    arn: 'arn:aws:route53:::hostedzone/*', 
    accountId: AWS_ACCOUNT_ID,
    details: ['wecare.digital', 'base.wecare.digital', 'app.wecare.digital']
  },
  'Amazon VPC': { 
    arn: `arn:aws:ec2:${AWS_REGION}:${AWS_ACCOUNT_ID}:vpc/*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Default VPC']
  },
  'Elastic Load Balancing': { 
    arn: `arn:aws:elasticloadbalancing:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  
  // API & INTEGRATION
  'Amazon API Gateway': { 
    arn: `arn:aws:apigateway:${AWS_REGION}::/restapis/*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['api.wecare.digital - HTTP API (prod stage, auto-deploy)', 'Routes: /contacts, /messages, /whatsapp/*, /sms-aws/*, /voice-aws/*, /voice-in/*, /voice-cdr-webhook, /sms-in/*, /billing, /ai/*, /templates/*, /waba/*']
  },
  'AWS AppSync': { 
    arn: `arn:aws:appsync:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon EventBridge': { 
    arn: `arn:aws:events:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'AWS Step Functions': { 
    arn: `arn:aws:states:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  
  // MESSAGING
  'Amazon SNS': { 
    arn: `arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['wecare-whatsapp-inbound-topic']
  },
  'Amazon SQS': { 
    arn: `arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['wecare-whatsapp-dlq']
  },
  'Amazon SES': { 
    arn: `arn:aws:ses:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Email sending service']
  },
  'Amazon Pinpoint': { 
    arn: `arn:aws:sms-voice:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: [
      'SMS: Sender ID WECARE (no pool, account default)',
      'Voice: +18444891209 (Toll-Free, Intl enabled)',
      'Voice: +18444891209 (Toll-Free, Intl enabled, PENDING)',
      'Pool: TBD (pending toll-free approval)',
      'Protect Config: protect-b137924dfb934c32b1d10c28b737d08c (account default)',
      'Tables: SmsAwsTable, VoiceAwsTable'
    ]
  },
  'AWS End User Messaging': { 
    arn: `arn:aws:social-messaging:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: [
      '+91 93309 94400 (WECARE.DIGITAL) - Razorpay + UPI enabled',
      '+91 99033 00044 (Manish Agarwal)',
      'WABA 1: 1912405516040025 (WECARE.DIGITAL)',
      'WABA 2: 1633959101297902 (Manish Agarwal)',
      'Service-Linked Role: AWSServiceRoleForSocialMessaging',
      'Policy: AWSSocialMessagingServiceRolePolicy (cloudwatch:PutMetricData)'
    ]
  },
  
  // AI/ML
  'Amazon Bedrock': { 
    arn: `arn:aws:bedrock:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Knowledge Base: wecare-digital-kb', 'Agent: wecare-digital-agent', 'Model: Claude']
  },
  'Amazon OpenSearch': { 
    arn: `arn:aws:aoss:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Serverless collection for Bedrock KB vector store']
  },
  'Amazon SageMaker': { 
    arn: `arn:aws:sagemaker:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon Comprehend': { 
    arn: `arn:aws:comprehend:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon Rekognition': { 
    arn: `arn:aws:rekognition:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon Transcribe': { 
    arn: `arn:aws:transcribe:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'Amazon Polly': { 
    arn: `arn:aws:polly:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['TTS for Pinpoint Voice calls (Voice ID: RAVEENA)']
  },
  'Amazon Translate': { 
    arn: `arn:aws:translate:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  
  // SECURITY & IDENTITY
  'Amazon Cognito': { 
    arn: `arn:aws:cognito-idp:${AWS_REGION}:${AWS_ACCOUNT_ID}:userpool/*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['User Pool for authentication']
  },
  'AWS IAM': { 
    arn: `arn:aws:iam::${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['wecare-digital-lambda-role', 'amplify-service-role']
  },
  'AWS Secrets Manager': { 
    arn: `arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['wecare/airtel-iq (Airtel IQ API credentials)']
  },
  'AWS KMS': { 
    arn: `arn:aws:kms:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Default encryption keys']
  },
  'AWS WAF': { 
    arn: `arn:aws:wafv2:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  
  // MONITORING & MANAGEMENT
  'CloudWatch': { 
    arn: `arn:aws:logs:${AWS_REGION}:${AWS_ACCOUNT_ID}:log-group:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: [
      '/aws/lambda/wecare-outbound-whatsapp',
      '/aws/lambda/wecare-inbound-whatsapp',
      '/aws/lambda/wecare-* (all functions)'
    ]
  },
  'AWS X-Ray': { 
    arn: `arn:aws:xray:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
  'AWS CloudTrail': { 
    arn: `arn:aws:cloudtrail:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['API activity logging']
  },
  
  // DEVELOPER TOOLS
  'AWS Amplify': { 
    arn: `arn:aws:amplify:${AWS_REGION}:${AWS_ACCOUNT_ID}:apps/d3nadrc9t6n3f8`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['App: d3nadrc9t6n3f8', 'Branch: base', 'Domain: base.wecare.digital']
  },
  'AWS CodeBuild': { 
    arn: `arn:aws:codebuild:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Amplify build process']
  },
  'AWS CodePipeline': { 
    arn: `arn:aws:codepipeline:${AWS_REGION}:${AWS_ACCOUNT_ID}:*`, 
    accountId: AWS_ACCOUNT_ID,
    details: ['Not currently used']
  },
};

const Dashboard: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [loading, setLoading] = useState(true);
  const [apiConnected, setApiConnected] = useState(false);
  const [apiLatency, setApiLatency] = useState<number | null>(null);

  // Data
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [messages, setMessages] = useState<api.Message[]>([]);
  const [billingData, setBillingData] = useState<api.AWSBillingData | null>(null);
  
  // UI State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedContact, setSelectedContact] = useState('');
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const lastMessageCount = useRef(0);

  // Delete state
  const [deleteMode, setDeleteMode] = useState<'messages' | 'hard' | 'clearAll' | null>(null);
  const [selectedMessages, setSelectedMessages] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [showHardDeleteModal, setShowHardDeleteModal] = useState(false);
  const [showClearAllModal, setShowClearAllModal] = useState(false);
  
  // Billing expanded rows
  const [expandedServices, setExpandedServices] = useState<Set<string>>(new Set());

  // AI Config state
  const [aiConfig, setAiConfig] = useState<InternalAIConfig>(DEFAULT_AI_CONFIG);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiSaving, setAiSaving] = useState(false);
  const [testMessage, setTestMessage] = useState('');
  const [testResult, setTestResult] = useState<string | null>(null);

  // Webhook state
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [webhookLoading, setWebhookLoading] = useState(false);
  const [newWebhook, setNewWebhook] = useState({ name: '', url: '', events: ['message.received', 'message.sent'] });
  const [showWebhookForm, setShowWebhookForm] = useState(false);

  // Bot Flow state
  const [botFlowConfigs, setBotFlowConfigs] = useState<Record<string, any>>({});
  const [botFlowLoading, setBotFlowLoading] = useState(false);
  const [botFlowSaving, setBotFlowSaving] = useState(false);
  const [botFlowEditKey, setBotFlowEditKey] = useState('');
  const [botFlowEditValue, setBotFlowEditValue] = useState('');

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    
    const connectionTest = await api.testConnection();
    setApiConnected(connectionTest.success);
    setApiLatency(connectionTest.latency || null);
    
    if (!connectionTest.success) {
      if (!silent) setLoading(false);
      return;
    }
    
    try {
      const [contactsData, messagesData, billingResult] = await Promise.all([
        api.listContacts(),
        api.listMessages(),
        api.getAWSBilling()
      ]);
      
      lastMessageCount.current = messagesData.length;
      setContacts(contactsData);
      setMessages(messagesData);
      setBillingData(billingResult);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => loadData(true), 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleDeleteMessages = async () => {
    if (selectedMessages.length === 0) return;
    setDeleting(true);
    try {
      for (const msgId of selectedMessages) {
        const msg = messages.find(m => m.id === msgId);
        if (msg) await api.deleteMessage(msgId, msg.direction);
      }
      setSelectedMessages([]);
      setDeleteMode(null);
      await loadData();
    } catch (err) {
      console.error('Delete error:', err);
    } finally {
      setDeleting(false);
    }
  };

  const handleHardDelete = async () => {
    if (!selectedContact) return;
    setShowHardDeleteModal(false);
    setDeleting(true);
    try {
      await api.hardDeleteContact(selectedContact);
      setSelectedContact('');
      setDeleteMode(null);
      setConfirmText('');
      await loadData();
    } catch (err) {
      console.error('Delete error:', err);
    } finally {
      setDeleting(false);
    }
  };

  // Clear ALL data across all channels - SMS, Voice, WhatsApp, S3, etc.
  const handleClearAllData = async () => {
    setShowClearAllModal(false);
    setDeleting(true);
    try {
      // Clear all inbox data (messages + contacts)
      const result = await api.clearAllInboxData();
      console.log('Clear all result:', result);
      setDeleteMode(null);
      setConfirmText('');
      await loadData();
    } catch (err) {
      console.error('Clear all error:', err);
    } finally {
      setDeleting(false);
    }
  };

  const toggleServiceExpand = (service: string) => {
    setExpandedServices(prev => {
      const next = new Set(prev);
      if (next.has(service)) next.delete(service);
      else next.add(service);
      return next;
    });
  };

  // AI Config handlers
  const loadAiConfig = async () => {
    setAiLoading(true);
    try {
      const res = await fetch(`${API_BASE}/ai/internal/config`);
      if (res.ok) {
        const data = await res.json();
        if (data.config) {
          setAiConfig({ ...DEFAULT_AI_CONFIG, ...data.config });
        }
      }
    } catch (error) {
      console.log('Using default internal AI config');
    }
    setAiLoading(false);
  };

  const handleSaveAiConfig = async () => {
    setAiSaving(true);
    try {
      const res = await fetch(`${API_BASE}/ai/internal/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(aiConfig),
      });
      if (!res.ok) console.error('Failed to save AI config');
    } catch (error) {
      console.error('Failed to save AI config');
    }
    setAiSaving(false);
  };

  const handleTestAi = async () => {
    if (!testMessage.trim()) return;
    setAiSaving(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/ai/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messageContent: testMessage,
          context: 'internal-admin',
        }),
      });
      const data = await res.json();
      const body = typeof data.body === 'string' ? JSON.parse(data.body) : data;
      setTestResult(body.suggestedResponse || body.suggestion || 'No response');
    } catch (error) {
      setTestResult('Error: Failed to get AI response');
    }
    setAiSaving(false);
  };

  // Webhook handlers
  const loadWebhooks = async () => {
    setWebhookLoading(true);
    try {
      const res = await fetch(`${API_BASE}/webhooks`);
      if (res.ok) {
        const data = await res.json();
        setWebhooks(data.webhooks || []);
      }
    } catch (error) {
      console.log('No webhooks configured');
    }
    setWebhookLoading(false);
  };

  const handleCreateWebhook = async () => {
    if (!newWebhook.name || !newWebhook.url) return;
    try {
      const res = await fetch(`${API_BASE}/webhooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newWebhook),
      });
      if (res.ok) {
        setNewWebhook({ name: '', url: '', events: ['message.received', 'message.sent'] });
        setShowWebhookForm(false);
        loadWebhooks();
      }
    } catch (error) {
      console.error('Failed to create webhook');
    }
  };

  const handleToggleWebhook = async (id: string, enabled: boolean) => {
    try {
      await fetch(`${API_BASE}/webhooks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      loadWebhooks();
    } catch (error) {
      console.error('Failed to toggle webhook');
    }
  };

  const handleDeleteWebhook = async (id: string) => {
    try {
      await fetch(`${API_BASE}/webhooks/${id}`, { method: 'DELETE' });
      loadWebhooks();
    } catch (error) {
      console.error('Failed to delete webhook');
    }
  };

  // Load AI config and webhooks when switching to those tabs
  useEffect(() => {
    if (activeTab === 'ai') loadAiConfig();
    if (activeTab === 'webhook') loadWebhooks();
    if (activeTab === 'botflow') loadBotFlowConfigs();
  }, [activeTab]);

  const loadBotFlowConfigs = async () => {
    setBotFlowLoading(true);
    try {
      const res = await fetch(`${API_BASE}/ai/botflow`);
      if (res.ok) {
        const data = await res.json();
        setBotFlowConfigs(data.configs || {});
      }
    } catch (error) {
      console.log('Failed to load bot flow configs');
    }
    setBotFlowLoading(false);
  };

  const handleSaveBotFlowConfig = async (configKey: string, configValue: any) => {
    setBotFlowSaving(true);
    try {
      const res = await fetch(`${API_BASE}/ai/botflow`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ configKey, configValue }),
      });
      if (res.ok) {
        setBotFlowConfigs(prev => ({ ...prev, [configKey]: configValue }));
        setBotFlowEditKey('');
        setBotFlowEditValue('');
      }
    } catch (error) {
      console.error('Failed to save bot flow config');
    }
    setBotFlowSaving(false);
  };

  // Stats
  const todayMessages = messages.filter(m => {
    const msgDate = new Date(m.timestamp);
    const today = new Date();
    return msgDate.toDateString() === today.toDateString();
  });
  const inboundCount = messages.filter(m => m.direction === 'INBOUND').length;
  const outboundCount = messages.filter(m => m.direction === 'OUTBOUND').length;
  const paymentMessages = messages.filter(m => m.messageType === 'payment');
  const capturedPayments = paymentMessages.filter(m => (m as any).paymentStatus === 'captured').length;
  const failedPayments = paymentMessages.filter(m => (m as any).paymentStatus === 'failed').length;

  // Filter messages
  const filteredMessages = searchQuery.trim()
    ? messages.filter(m =>
        m.content?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contacts.find(c => c.id === m.contactId)?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contacts.find(c => c.id === m.contactId)?.phone?.includes(searchQuery)
      )
    : messages;

  const contactMessages = selectedContact
    ? filteredMessages.filter(m => m.contactId === selectedContact)
    : filteredMessages;

  // Confirmation Modal Component
  const ConfirmModal = ({ 
    isOpen, 
    title, 
    message, 
    confirmText = 'Confirm',
    confirmInput,
    onConfirm, 
    onCancel 
  }: {
    isOpen: boolean;
    title: string;
    message: React.ReactNode;
    confirmText?: string;
    confirmInput?: string;
    onConfirm: () => void;
    onCancel: () => void;
  }) => {
    const [inputValue, setInputValue] = React.useState('');
    
    React.useEffect(() => {
      if (!isOpen) setInputValue('');
    }, [isOpen]);
    
    if (!isOpen) return null;
    
    const canConfirm = !confirmInput || inputValue === confirmInput;
    
    return (
      <div className="confirm-modal-overlay" onClick={onCancel}>
        <div className="confirm-modal" onClick={e => e.stopPropagation()}>
          <div className="confirm-modal-header">
            <h3>{title}</h3>
          </div>
          <div className="confirm-modal-body">
            {message}
            {confirmInput && (
              <div className="confirm-input-wrapper">
                <label>Type "{confirmInput}" to confirm:</label>
                <input
                  type="text"
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  placeholder={confirmInput}
                  autoFocus
                />
              </div>
            )}
          </div>
          <div className="confirm-modal-footer">
            <button className="confirm-modal-cancel" onClick={onCancel}>Cancel</button>
            <button 
              className="confirm-modal-confirm"
              onClick={onConfirm}
              disabled={!canConfirm}
            >
              {confirmText}
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title={PAGE_SEO.dashboard.title}
        description={PAGE_SEO.dashboard.description}
        keywords={PAGE_SEO.dashboard.keywords}
        canonical="/dashboard"
        noindex={true}
      />
      
      {/* Confirmation Modals */}
      <ConfirmModal
        isOpen={showHardDeleteModal}
        title="Hard Delete Contact"
        message={
          <div>
            <p>This will permanently delete:</p>
            <ul style={{ margin: '8px 0 8px 20px', lineHeight: 1.6 }}>
              <li>Contact: {contacts.find(c => c.id === selectedContact)?.name || selectedContact}</li>
              <li>{contactMessages.length} messages</li>
              <li>{contactMessages.filter(m => m.s3Key).length} media files from S3</li>
            </ul>
            <p style={{ color: '#065f46', fontWeight: 500 }}>This action cannot be undone!</p>
          </div>
        }
        confirmInput="DELETE"
        confirmText="Hard Delete"
        onConfirm={handleHardDelete}
        onCancel={() => setShowHardDeleteModal(false)}
      />
      
      <ConfirmModal
        isOpen={showClearAllModal}
        title="Clear All Data"
        message={
          <div>
            <p style={{ color: '#065f46', fontWeight: 500, marginBottom: 12 }}>
              ⚠️ WARNING: This will permanently delete ALL data:
            </p>
            <ul style={{ margin: '0 0 12px 20px', lineHeight: 1.6 }}>
              <li>All WhatsApp messages (inbound & outbound)</li>
              <li>All SMS messages (inbound & outbound)</li>
              <li>All SMS IN messages</li>
              <li>All Voice call records (inbound & outbound)</li>
              <li>All Voice IN call records</li>
              <li>All {contacts.length} contacts</li>
              <li>All {messages.filter(m => m.s3Key).length} media files from S3</li>
            </ul>
            <p style={{ color: '#065f46', fontWeight: 500 }}>
              This action cannot be undone!
            </p>
          </div>
        }
        confirmInput="DELETE ALL"
        confirmText="Clear Everything"
        onConfirm={handleClearAllData}
        onCancel={() => setShowClearAllModal(false)}
      />
      
      <div className="dash">
        {/* Header */}
        <header className="dash-header">
          <div className="dash-brand">
            <h1>Overview</h1>
            <div className="dash-status">
              <span className={`status-dot ${apiConnected ? 'online' : 'offline'}`} />
              <span>{apiConnected ? `${apiLatency}ms` : 'Offline'}</span>
              <span className="sep">•</span>
              <span>{lastRefresh.toLocaleTimeString()}</span>
            </div>
          </div>
          <button className="refresh-btn" onClick={() => loadData()} disabled={loading}>
            {loading ? '...' : <RefreshIcon size={18} />}
          </button>
        </header>

        {/* Tabs */}
        <nav className="dash-tabs">
          {(['overview', 'messages', 'pay', 'data', 'billing', 'health', 'advisor', 'ai', 'botflow', 'webhook', 'guide', 'search'] as TabType[]).map(tab => (
            <button
              key={tab}
              className={`tab ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'overview' && <DashboardIcon size={16} />}
              {tab === 'messages' && <MessageIcon size={16} />}
              {tab === 'pay' && <PaymentIcon size={16} />}
              {tab === 'data' && <DataIcon size={16} />}
              {tab === 'billing' && <BillingIcon size={16} />}
              {tab === 'health' && <HealthIcon size={16} />}
              {tab === 'advisor' && <AdvisorIcon size={16} />}
              {tab === 'ai' && <AIIcon size={16} />}
              {tab === 'botflow' && <WhatsAppIcon size={16} />}
              {tab === 'webhook' && <LinkIcon size={16} />}
              {tab === 'guide' && <DocumentIcon size={16} />}
              {tab === 'search' && <SearchIcon size={16} />}
              <span>{tab === 'ai' ? 'AI' : tab === 'botflow' ? 'Bot Flow' : tab === 'webhook' ? 'Webhook' : tab === 'guide' ? 'Guide' : tab === 'health' ? 'Health' : tab === 'advisor' ? 'Advisor' : tab.charAt(0).toUpperCase() + tab.slice(1)}</span>
            </button>
          ))}
        </nav>

        {/* Tab Content */}
        <div className="tab-content">
          {/* OVERVIEW TAB */}
          {activeTab === 'overview' && (
            <div className="overview">
              <div className="section full-width">
                <h3>Statistics</h3>
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-value">{contacts.length}</div>
                    <div className="stat-label">Contacts</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{messages.length}</div>
                    <div className="stat-label">Messages</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{todayMessages.length}</div>
                    <div className="stat-label">Today</div>
                  </div>
                  <div className="stat-card accent">
                    <div className="stat-value">{inboundCount}</div>
                    <div className="stat-label">Inbound</div>
                  </div>
                  <div className="stat-card accent2">
                    <div className="stat-value">{outboundCount}</div>
                    <div className="stat-label">Outbound</div>
                  </div>
                  <div className="stat-card success">
                    <div className="stat-value">{capturedPayments}</div>
                    <div className="stat-label">Paid</div>
                  </div>
                </div>
              </div>

              <div className="section">
                <h3>Quick Actions</h3>
                <div className="actions-grid">
                  <Link href="/dm/whatsapp" className="action-card">
                    <span className="icon"><WhatsAppIcon size={20} /></span>
                    <span>WhatsApp</span>
                  </Link>
                  <Link href="/pay" className="action-card">
                    <span className="icon"><PaymentIcon size={20} /></span>
                    <span>Pay</span>
                  </Link>
                  <Link href="/invoice" className="action-card">
                    <span className="icon"><InvoiceIcon size={20} /></span>
                    <span>Invoice</span>
                  </Link>
                  <Link href="/link" className="action-card">
                    <span className="icon"><LinkIcon size={20} /></span>
                    <span>Link</span>
                  </Link>
                  <Link href="/contacts" className="action-card">
                    <span className="icon"><ContactsIcon size={20} /></span>
                    <span>Contacts</span>
                  </Link>
                  <Link href="/dm/whatsapp" className="action-card" onClick={() => setActiveTab('overview')}>
                    <span className="icon"><BulkIcon size={20} /></span>
                    <span>Campaign</span>
                  </Link>
                  <Link href="/dm/sms" className="action-card">
                    <span className="icon"><SmsIcon size={20} /></span>
                    <span>SMS</span>
                  </Link>
                  <Link href="/dm/ses" className="action-card">
                    <span className="icon"><EmailIcon size={20} /></span>
                    <span>Email</span>
                  </Link>
                </div>
              </div>

              <div className="section">
                <h3>WhatsApp Numbers</h3>
                <div className="phones-grid">
                  <div className="phone-card">
                    <div className="phone-name">WECARE.DIGITAL</div>
                    <div className="phone-num">+91 93309 94400</div>
                    <span className="badge">Razorpay</span>
                  </div>
                  <div className="phone-card">
                    <div className="phone-name">Manish Agarwal</div>
                    <div className="phone-num">+91 99033 00044</div>
                    <span className="badge">Active</span>
                  </div>
                </div>
              </div>

              <div className="section full-width">
                <div className="section-header">
                  <h3>Recent Messages</h3>
                  <Link href="/dm/whatsapp" className="link">View All →</Link>
                </div>
                <div className="msg-list">
                  {messages.slice(0, 5).map(msg => {
                    const contact = contacts.find(c => c.id === msg.contactId);
                    return (
                      <div key={msg.id} className={`msg-item ${msg.direction.toLowerCase()}`}>
                        <span className="dir">{msg.direction === 'INBOUND' ? '↓' : '↑'}</span>
                        <span className="name">{contact?.name || contact?.phone || '...'}</span>
                        <span className="content">{msg.content?.slice(0, 50) || '[Media]'}</span>
                        <span className="time">{new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</span>
                      </div>
                    );
                  })}
                  {messages.length === 0 && <div className="empty">No messages yet</div>}
                </div>
              </div>
            </div>
          )}

          {/* MESSAGES TAB */}
          {activeTab === 'messages' && (
            <div className="messages-tab">
              <div className="search-bar">
                <input
                  type="text"
                  placeholder="Search messages..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
                {searchQuery && <button onClick={() => setSearchQuery('')}>×</button>}
              </div>
              
              <div className="msg-list full">
                {filteredMessages.slice(0, 50).map(msg => {
                  const contact = contacts.find(c => c.id === msg.contactId);
                  return (
                    <div key={msg.id} className={`msg-item ${msg.direction.toLowerCase()}`}>
                      <span className="dir">{msg.direction === 'INBOUND' ? '↓' : '↑'}</span>
                      <span className="name">{contact?.name || contact?.phone || '...'}</span>
                      <span className="content">{msg.content?.slice(0, 60) || '[Media]'}</span>
                      <span className="time">{new Date(msg.timestamp).toLocaleString()}</span>
                      <span className="status">{msg.status}</span>
                    </div>
                  );
                })}
                {filteredMessages.length === 0 && <div className="empty">No messages found</div>}
              </div>
            </div>
          )}

          {/* PAY TAB */}
          {activeTab === 'pay' && (
            <div className="pay-tab">
              <div className="section-header">
                <h3>Payment Records</h3>
                <Link href="/pay"><Button variant="primary">+ New Payment</Button></Link>
              </div>
              
              <div className="stats-grid small">
                <div className="stat-card success">
                  <div className="stat-value">{capturedPayments}</div>
                  <div className="stat-label">Captured</div>
                </div>
                <div className="stat-card error">
                  <div className="stat-value">{failedPayments}</div>
                  <div className="stat-label">Failed</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{paymentMessages.length}</div>
                  <div className="stat-label">Total</div>
                </div>
              </div>

              <div className="payment-info">
                <span>Payments sent from: <strong>{PAYMENT_PHONE}</strong> ({PAYMENT_NAME})</span>
              </div>

              <table className="data-table">
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Phone</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {paymentMessages.map(p => (
                    <tr key={p.id} className={(p as any).paymentStatus}>
                      <td>{(p as any).paymentReferenceId || '-'}</td>
                      <td>{p.senderPhone || '-'}</td>
                      <td>{p.content}</td>
                      <td><span className={`badge ${(p as any).paymentStatus}`}>{(p as any).paymentStatus || p.status}</span></td>
                      <td>{new Date(p.timestamp).toLocaleString()}</td>
                    </tr>
                  ))}
                  {paymentMessages.length === 0 && (
                    <tr><td colSpan={5} className="empty">No payment records</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* DATA TAB */}
          {activeTab === 'data' && (
            <div className="data-tab">
              <h3>Data Management</h3>
              
              <div className="delete-options">
                <button 
                  className={deleteMode === 'messages' ? 'active' : ''} 
                  onClick={() => setDeleteMode(deleteMode === 'messages' ? null : 'messages')}
                >
                  ◫ Delete Messages
                </button>
                <button 
                  className={deleteMode === 'hard' ? 'active' : ''}
                  onClick={() => setDeleteMode(deleteMode === 'hard' ? null : 'hard')}
                >
                  ⊗ Hard Delete Contact
                </button>
                <button 
                  className={deleteMode === 'clearAll' ? 'active' : ''}
                  onClick={() => setDeleteMode(deleteMode === 'clearAll' ? null : 'clearAll')}
                >
                  ⊘ Clear All Data
                </button>
              </div>

              {deleteMode === 'messages' && (
                <div className="delete-panel">
                  <div className="form-row">
                    <label>Filter by Contact</label>
                    <select value={selectedContact} onChange={e => setSelectedContact(e.target.value)}>
                      <option value="">All contacts</option>
                      {contacts.map(c => (
                        <option key={c.id} value={c.id}>{c.name || c.phone}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div className="msg-select-list">
                    <div className="select-header">
                      <span>{selectedMessages.length} selected</span>
                      <button onClick={() => setSelectedMessages(
                        selectedMessages.length === contactMessages.length ? [] : contactMessages.map(m => m.id)
                      )}>
                        {selectedMessages.length === contactMessages.length ? 'Deselect All' : 'Select All'}
                      </button>
                    </div>
                    {contactMessages.slice(0, 30).map(msg => (
                      <label key={msg.id} className="msg-select-row">
                        <input
                          type="checkbox"
                          checked={selectedMessages.includes(msg.id)}
                          onChange={() => setSelectedMessages(prev =>
                            prev.includes(msg.id) ? prev.filter(id => id !== msg.id) : [...prev, msg.id]
                          )}
                        />
                        <span className="dir">{msg.direction === 'INBOUND' ? '↓' : '↑'}</span>
                        <span className="content">{msg.content?.slice(0, 40) || '[Media]'}</span>
                        <span className="time">{new Date(msg.timestamp).toLocaleDateString()}</span>
                      </label>
                    ))}
                  </div>
                  
                  <div className="delete-actions">
                    <Button variant="secondary" onClick={() => { setDeleteMode(null); setSelectedMessages([]); }}>Cancel</Button>
                    <Button variant="danger" onClick={handleDeleteMessages} disabled={deleting || selectedMessages.length === 0} loading={deleting}>
                      Delete {selectedMessages.length}
                    </Button>
                  </div>
                </div>
              )}

              {deleteMode === 'hard' && (
                <div className="delete-panel">
                  <div className="warning">This will permanently delete the contact, all their messages, and media files.</div>
                  
                  <div className="form-row">
                    <label>Select Contact</label>
                    <select value={selectedContact} onChange={e => setSelectedContact(e.target.value)}>
                      <option value="">Select...</option>
                      {contacts.map(c => (
                        <option key={c.id} value={c.id}>{c.name || c.phone}</option>
                      ))}
                    </select>
                  </div>
                  
                  {selectedContact && (
                    <div className="preview">
                      <p>Contact: {contacts.find(c => c.id === selectedContact)?.name || selectedContact}</p>
                      <p>{contactMessages.length} messages, {contactMessages.filter(m => m.s3Key).length} media files</p>
                    </div>
                  )}
                  
                  <div className="delete-actions">
                    <Button variant="secondary" onClick={() => { setDeleteMode(null); setSelectedContact(''); }}>Cancel</Button>
                    <Button variant="danger" onClick={() => setShowHardDeleteModal(true)} disabled={deleting || !selectedContact} loading={deleting}>
                      Hard Delete
                    </Button>
                  </div>
                </div>
              )}

              {deleteMode === 'clearAll' && (
                <div className="delete-panel">
                  <div className="warning">
                    This will permanently delete ALL data including:
                    <ul style={{ margin: '8px 0 0 16px', fontSize: '12px' }}>
                      <li>All WhatsApp messages (inbound & outbound)</li>
                      <li>All SMS messages (inbound & outbound)</li>
                      <li>All SMS IN messages</li>
                      <li>All Voice call records (inbound & outbound)</li>
                      <li>All Voice IN call records</li>
                      <li>All contacts</li>
                      <li>All media files from S3</li>
                    </ul>
                  </div>
                  
                  <div className="preview">
                    <p>Total Contacts: {contacts.length}</p>
                    <p>Total Messages: {messages.length}</p>
                    <p>Media Files: {messages.filter(m => m.s3Key).length}</p>
                  </div>
                  
                  <div className="delete-actions">
                    <Button variant="secondary" onClick={() => setDeleteMode(null)}>Cancel</Button>
                    <Button variant="danger" onClick={() => setShowClearAllModal(true)} disabled={deleting} loading={deleting}>
                      Clear All Data
                    </Button>
                  </div>
                </div>
              )}

              {!deleteMode && (
                <div className="stats-grid">
                  <div className="stat-card"><div className="stat-value">{contacts.length}</div><div className="stat-label">Contacts</div></div>
                  <div className="stat-card"><div className="stat-value">{messages.length}</div><div className="stat-label">Messages</div></div>
                  <div className="stat-card"><div className="stat-value">{messages.filter(m => m.s3Key).length}</div><div className="stat-label">Media</div></div>
                </div>
              )}
            </div>
          )}
          {/* BILLING TAB */}
          {activeTab === 'billing' && (
            <div className="billing-tab">
              <div className="section-header">
                <h3>AWS Billing & Usage</h3>
                <button className="refresh-btn" onClick={() => loadData()} disabled={loading}><RefreshIcon size={18} /></button>
              </div>
              
              {loading && !billingData && (
                <div style={{ textAlign: 'center', padding: '3rem' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⏳</div>
                  <p style={{ color: '#6b7280' }}>Loading billing data...</p>
                </div>
              )}

              {!loading && !billingData && (
                <div style={{ background: '#f0fdf4', borderRadius: '8px', textAlign: 'center', padding: '3rem', border: '1px solid #a7f3d0' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⚠️</div>
                  <h3 style={{ color: '#065f46', margin: '0 0 0.5rem' }}>Unable to Load Billing Data</h3>
                  <p style={{ color: '#6b7280', margin: 0 }}>Check API connection or try refreshing.</p>
                </div>
              )}

              {billingData && (
                <>
                  <div className="billing-summary">
                    <div className="billing-total">
                      <span className="amount">${billingData.totalCost.toFixed(2)}</span>
                      <span className="label">Estimated Cost</span>
                    </div>
                    <div className="billing-meta">
                      <div className="period">{billingData.period}</div>
                      <div className="account">Account: {AWS_ACCOUNT_ID}</div>
                    </div>
                  </div>

                  <table className="billing-table">
                    <thead>
                      <tr>
                        <th></th>
                        <th>Service</th>
                        <th>Usage</th>
                        <th>Free Limit</th>
                        <th>Cost</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {billingData.services.map((svc, idx) => {
                        const resource = AWS_RESOURCES[svc.service] || { 
                          arn: `arn:aws:*:${AWS_REGION}:${AWS_ACCOUNT_ID}:${svc.service.toLowerCase().replace(/\s+/g, '-')}/*`, 
                          accountId: AWS_ACCOUNT_ID 
                        };
                        const isExpanded = expandedServices.has(svc.service);
                        return (
                          <React.Fragment key={idx}>
                            <tr className={`billing-row ${svc.status}`}>
                              <td className="expand-cell">
                                <button className="expand-btn" onClick={() => toggleServiceExpand(svc.service)}>
                                  {isExpanded ? '−' : '+'}
                                </button>
                              </td>
                              <td className="service-name">{svc.service}</td>
                              <td>{svc.usage.toLocaleString()} <small>{svc.unit}</small></td>
                              <td>{svc.freeLimit}</td>
                              <td>${svc.cost.toFixed(4)}</td>
                              <td>
                                <span className={`badge ${svc.status}`}>
                                  {svc.status === 'free' ? 'Free' : svc.status === 'warning' ? 'Near' : 'Paid'}
                                </span>
                              </td>
                            </tr>
                            {isExpanded && (
                              <tr className="resource-row">
                                <td></td>
                                <td colSpan={5}>
                                  <div className="resource-details">
                                    <div><strong>Account ID:</strong> {resource.accountId}</div>
                                    <div><strong>Resource ARN:</strong> <code>{resource.arn}</code></div>
                                    {resource.details && resource.details.length > 0 && (
                                      <div className="resource-list">
                                        <strong>Resources:</strong>
                                        <ul>
                                          {resource.details.map((detail, i) => (
                                            <li key={i}>{detail}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}

          {/* HEALTH TAB */}
          {activeTab === 'health' && (
            <div className="health-tab">
              <div className="section-header">
                <h3>AWS Health</h3>
                <button className="refresh-btn" onClick={() => loadData()} disabled={loading}><RefreshIcon size={18} /></button>
              </div>
              
              {loading && !billingData?.health && (
                <div className="loading-state">
                  <div className="loading-icon"><RefreshIcon size={32} /></div>
                  <p>Loading health data...</p>
                </div>
              )}

              {!loading && billingData?.health && (
                <>
                  <div className="stats-grid small">
                    <div className={`stat-card ${billingData?.health?.openIssues === 0 ? 'success' : 'error'}`}>
                      <div className="stat-value">
                        {billingData?.health?.openIssues ?? 0}
                      </div>
                      <div className="stat-label">Open Issues</div>
                    </div>
                    <div className="stat-card accent">
                      <div className="stat-value">
                        {billingData?.health?.scheduledChanges ?? 0}
                      </div>
                      <div className="stat-label">Scheduled Changes</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{billingData?.health?.otherNotifications ?? 0}</div>
                      <div className="stat-label">Notifications</div>
                    </div>
                    <div className={`stat-card ${billingData?.health?.status === 'healthy' ? 'success' : 'warning'}`}>
                      <div className="stat-value status-icon">
                        {billingData?.health?.status === 'healthy' ? <HealthIcon size={24} /> : <AdvisorIcon size={24} />}
                      </div>
                      <div className="stat-label">Status</div>
                    </div>
                  </div>

                  {billingData?.health?.events && billingData.health.events.length > 0 && (
                    <div className="section issues-section">
                      <h4>Open Issues</h4>
                      {billingData.health.events.map((event: any, idx: number) => (
                        <div key={idx} className="issue-card error">
                          <div className="issue-card-header">
                            <strong>{event.service}</strong>
                            <span className="issue-badge error">{event.statusCode}</span>
                          </div>
                          <p>{event.eventTypeCode}</p>
                          <div className="meta">Region: {event.region}</div>
                          <a href="https://health.aws.amazon.com/health/home" target="_blank" rel="noopener noreferrer" className="resolve-btn">
                            View & Resolve
                          </a>
                        </div>
                      ))}
                    </div>
                  )}

                  {(billingData.health.openIssues === 0 && billingData.health.scheduledChanges === 0) && (
                    <div className="health-status-card healthy">
                      <div className="status-icon"><HealthIcon size={48} /></div>
                      <h3>All Systems Healthy</h3>
                      <p>No open issues or scheduled changes.</p>
                    </div>
                  )}
                </>
              )}

              {!loading && !billingData?.health && (
                <div className="health-status-card info">
                  <div className="status-icon"><DataIcon size={48} /></div>
                  <h3>Health Data Unavailable</h3>
                  <p>AWS Health API requires Business or Enterprise Support plan.</p>
                </div>
              )}

              <div className="info-banner-blue">
                <p>
                  AWS Health provides personalized information about events that can affect your AWS infrastructure.
                  <a href="https://health.aws.amazon.com/health/home" target="_blank" rel="noopener noreferrer">
                    Open AWS Health Dashboard
                  </a>
                </p>
              </div>
            </div>
          )}

          {/* ADVISOR TAB */}
          {activeTab === 'advisor' && (
            <div className="advisor-tab">
              <div className="section-header">
                <h3>Trusted Advisor</h3>
                <button className="refresh-btn" onClick={() => loadData()} disabled={loading}><RefreshIcon size={18} /></button>
              </div>
              
              {loading && !billingData?.trustedAdvisor && (
                <div className="loading-state">
                  <div className="loading-icon"><RefreshIcon size={32} /></div>
                  <p>Loading Trusted Advisor data...</p>
                </div>
              )}

              {!loading && billingData?.trustedAdvisor && (
                <>
                  <div className="stats-grid small">
                    <div className="stat-card error">
                      <div className="stat-value">{billingData?.trustedAdvisor?.actionRecommended ?? 0}</div>
                      <div className="stat-label">Action Required</div>
                    </div>
                    <div className="stat-card warning">
                      <div className="stat-value">{billingData?.trustedAdvisor?.investigationRecommended ?? 0}</div>
                      <div className="stat-label">Investigation</div>
                    </div>
                    <div className="stat-card success">
                      <div className="stat-value">{billingData?.trustedAdvisor?.noProblemsDetected ?? 0}</div>
                      <div className="stat-label">No Problems</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{billingData?.trustedAdvisor?.notAvailable ?? 0}</div>
                      <div className="stat-label">Not Available</div>
                    </div>
                  </div>

                  {billingData?.trustedAdvisor?.categories && Object.keys(billingData.trustedAdvisor.categories).length > 0 && (
                    <div className="category-grid">
                      {Object.entries(billingData.trustedAdvisor.categories).map(([key, counts]: [string, any]) => (
                        <div key={key} className="category-card">
                          <div className="category-icon">
                            {key === 'cost_optimizing' ? <BillingIcon size={24} /> : 
                             key === 'security' ? <AdvisorIcon size={24} /> : 
                             key === 'fault_tolerance' ? <HealthIcon size={24} /> : 
                             key === 'performance' ? <AIIcon size={24} /> : 
                             <DataIcon size={24} />}
                          </div>
                          <div className="category-name">{key.replace('_', ' ')}</div>
                          <div className="category-counts">
                            {counts.error > 0 && <span className="count-badge error">{counts.error}</span>}
                            {counts.warning > 0 && <span className="count-badge warning">{counts.warning}</span>}
                            {counts.ok > 0 && <span className="count-badge ok">{counts.ok}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {billingData?.trustedAdvisor?.checks && billingData.trustedAdvisor.checks.length > 0 && (
                    <div className="section issues-section">
                      <h4>Checks Requiring Attention</h4>
                      {billingData.trustedAdvisor.checks.map((check: any, idx: number) => (
                        <div key={idx} className={`issue-card ${check.status === 'error' ? 'error' : 'warning'}`}>
                          <div className="issue-card-header">
                            <strong>{check.name}</strong>
                            <span className={`issue-badge ${check.status === 'error' ? 'error' : 'warning'}`}>
                              {check.status === 'error' ? 'Action' : 'Warning'}
                            </span>
                          </div>
                          <p>{check.description}</p>
                          <div className="meta">Resources: {check.resourcesFlagged}</div>
                          <a href={`https://console.aws.amazon.com/trustedadvisor/home#/category/${check.category}`} 
                             target="_blank" rel="noopener noreferrer" className="resolve-btn">
                            View & Resolve
                          </a>
                        </div>
                      ))}
                    </div>
                  )}

                  {(billingData.trustedAdvisor.actionRecommended === 0 && billingData.trustedAdvisor.investigationRecommended === 0) && (
                    <div className="health-status-card healthy">
                      <div className="status-icon"><AdvisorIcon size={48} /></div>
                      <h3>All Checks Passed</h3>
                      <p>No action or investigation recommended.</p>
                    </div>
                  )}
                </>
              )}

              {!loading && !billingData?.trustedAdvisor && (
                <div className="health-status-card info">
                  <div className="status-icon"><DataIcon size={48} /></div>
                  <h3>Trusted Advisor Data Unavailable</h3>
                  <p>Full Trusted Advisor access requires Business or Enterprise Support plan.</p>
                </div>
              )}

              <div className="info-banner-blue">
                <p>
                  AWS Trusted Advisor inspects your AWS environment and provides recommendations.
                  <a href="https://console.aws.amazon.com/trustedadvisor/home" target="_blank" rel="noopener noreferrer">
                    Open Trusted Advisor Console
                  </a>
                </p>
              </div>
            </div>
          )}

          {/* AI ASSISTANT TAB */}
          {activeTab === 'ai' && (
            <div className="ai-tab">
              <div className="section-header">
                <h3>Internal AI Assistant</h3>
                <span className="subtitle">Configure the FloatingAgent AI for admin tasks</span>
              </div>

              {/* Info Cards */}
              <div className="stats-grid small" style={{ marginBottom: '1.5rem' }}>
                <div className="stat-card">
                  <div className="stat-label">Agent ID</div>
                  <div className="stat-value" style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{aiConfig.agentId}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Agent Alias</div>
                  <div className="stat-value" style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{aiConfig.agentAlias}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Knowledge Base</div>
                  <div className="stat-value" style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{aiConfig.knowledgeBaseId}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Model</div>
                  <div className="stat-value" style={{ fontSize: '0.85rem' }}>Nova Lite</div>
                </div>
              </div>

              {/* Configuration */}
              <div className="section" style={{ background: 'white', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h4 style={{ marginBottom: '1rem' }}>Configuration</h4>
                
                <div style={{ marginBottom: '1rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={aiConfig.enabled}
                      onChange={(e) => setAiConfig({ ...aiConfig, enabled: e.target.checked })}
                      style={{ width: '1.25rem', height: '1.25rem' }}
                    />
                    <span style={{ fontWeight: 600 }}>Enable Internal AI Assistant</span>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Max Tokens</label>
                    <input
                      type="number"
                      value={aiConfig.maxTokens}
                      onChange={(e) => setAiConfig({ ...aiConfig, maxTokens: parseInt(e.target.value) || 1024 })}
                      min={256}
                      max={4096}
                      style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Temperature</label>
                    <input
                      type="number"
                      value={aiConfig.temperature}
                      onChange={(e) => setAiConfig({ ...aiConfig, temperature: parseFloat(e.target.value) || 0.7 })}
                      min={0}
                      max={1}
                      step={0.1}
                      style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                    />
                  </div>
                </div>

                <div style={{ marginBottom: '1rem' }}>
                  <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>System Prompt</label>
                  <textarea
                    value={aiConfig.systemPrompt}
                    onChange={(e) => setAiConfig({ ...aiConfig, systemPrompt: e.target.value })}
                    rows={6}
                    style={{ width: '100%', padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.375rem', fontFamily: 'monospace', fontSize: '0.85rem' }}
                  />
                </div>

                <Button
                  variant="primary"
                  onClick={handleSaveAiConfig}
                  disabled={aiSaving}
                  loading={aiSaving}
                >
                  Save Configuration
                </Button>
              </div>

              {/* Test Section */}
              <div className="section" style={{ background: 'white', padding: '1.5rem', borderRadius: '0.5rem' }}>
                <h4 style={{ marginBottom: '1rem' }}>Test Internal AI</h4>
                <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
                  Test how the internal AI responds to admin commands.
                </p>
                
                <div style={{ marginBottom: '1rem' }}>
                  <textarea
                    value={testMessage}
                    onChange={(e) => setTestMessage(e.target.value)}
                    rows={2}
                    style={{ width: '100%', padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                    placeholder="Try: 'Show today's stats' or 'Find contact +919330994400'"
                  />
                </div>

                <Button
                  variant="primary"
                  onClick={handleTestAi}
                  disabled={aiSaving || !testMessage.trim()}
                  loading={aiSaving}
                  style={{ marginBottom: '1rem' }}
                >
                  Test Response
                </Button>

                {testResult && (
                  <div style={{ padding: '1rem', background: '#ECFDF5', borderRadius: '0.5rem', border: '1px solid #A7F3D0' }}>
                    <div style={{ fontWeight: 500, marginBottom: '0.5rem' }}>AI Response:</div>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{testResult}</div>
                  </div>
                )}
              </div>

              {/* Architecture Info */}
              <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem', fontSize: '0.85rem', color: '#666' }}>
                <strong>Architecture Note:</strong> This is the Internal AI used by the FloatingAgent for admin tasks.
                For WhatsApp auto-reply AI (customer-facing), go to Messages → WhatsApp → AI Config.
              </div>

            </div>
          )}

          {/* BOT FLOW TAB */}
          {activeTab === 'botflow' && (
            <div className="botflow-tab">
              <div className="section-header">
                <h3>WhatsApp Bot Flow Config</h3>
                <Button variant="secondary" onClick={loadBotFlowConfigs} loading={botFlowLoading}>
                  <RefreshIcon size={14} /> Refresh
                </Button>
              </div>
              <p style={{ color: '#666', marginBottom: '1rem', fontSize: '0.9rem' }}>
                Manage welcome messages, menus, options, rating, and language picker configs stored in SystemConfigTable.
              </p>

              {botFlowLoading ? (
                <SkeletonCard />
              ) : (
                <>
                  {/* Config cards */}
                  {[
                    { key: 'welcome_message_config', label: 'Welcome / Main Menu', desc: 'Header, body, footer, button text, sections & rows for the main menu' },
                    { key: 'bot_options_config', label: 'Options Menu', desc: 'Do more / Done buttons shown after each action' },
                    { key: 'bot_rating_config', label: 'Rating Menu', desc: 'Feedback buttons shown when user is done' },
                    { key: 'bot_language_picker_config', label: 'Language Picker', desc: 'Language selection list' },
                    { key: 'bot_flow_config', label: 'Full Bot Flow', desc: 'Complete bot flow config (welcome, menus, responses, flows, toggles)' },
                  ].map(item => (
                    <div key={item.key} style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid #e5e7eb', borderRadius: '0.5rem', background: '#fff' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <div>
                          <strong>{item.label}</strong>
                          <div style={{ fontSize: '0.8rem', color: '#888' }}>{item.desc}</div>
                          <div style={{ fontSize: '0.75rem', color: '#aaa', fontFamily: 'monospace' }}>key: {item.key}</div>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <Button
                            variant="secondary"
                            onClick={() => {
                              setBotFlowEditKey(item.key);
                              setBotFlowEditValue(JSON.stringify(botFlowConfigs[item.key] || {}, null, 2));
                            }}
                          >
                            {botFlowConfigs[item.key] ? 'Edit' : 'Create'}
                          </Button>
                        </div>
                      </div>
                      {botFlowConfigs[item.key] && (
                        <pre style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '0.375rem', fontSize: '0.75rem', maxHeight: '200px', overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                          {JSON.stringify(botFlowConfigs[item.key], null, 2)}
                        </pre>
                      )}
                      {!botFlowConfigs[item.key] && (
                        <div style={{ padding: '0.5rem', color: '#999', fontSize: '0.85rem' }}>
                          Not configured — using Lambda defaults
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Edit modal */}
                  {botFlowEditKey && (
                    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                      <div style={{ background: '#fff', borderRadius: '0.75rem', padding: '1.5rem', width: '90%', maxWidth: '700px', maxHeight: '80vh', overflow: 'auto' }}>
                        <h4 style={{ marginBottom: '0.5rem' }}>Edit: {botFlowEditKey}</h4>
                        <p style={{ fontSize: '0.8rem', color: '#888', marginBottom: '1rem' }}>Paste valid JSON. This will be stored in SystemConfigTable.</p>
                        <textarea
                          value={botFlowEditValue}
                          onChange={(e) => setBotFlowEditValue(e.target.value)}
                          rows={20}
                          style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.8rem', padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.375rem', resize: 'vertical' }}
                        />
                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
                          <Button variant="secondary" onClick={() => { setBotFlowEditKey(''); setBotFlowEditValue(''); }}>
                            Cancel
                          </Button>
                          <Button
                            variant="primary"
                            loading={botFlowSaving}
                            onClick={() => {
                              try {
                                const parsed = JSON.parse(botFlowEditValue);
                                handleSaveBotFlowConfig(botFlowEditKey, parsed);
                              } catch {
                                alert('Invalid JSON');
                              }
                            }}
                          >
                            Save
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}

              <div style={{ marginTop: '1rem', padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem', fontSize: '0.85rem', color: '#666' }}>
                <strong>How it works:</strong> Configs stored here override Lambda defaults. The inbound handler reads these on each message.
                Leave empty to use the hardcoded defaults in the Lambda code.
              </div>
            </div>
          )}

          {/* WEBHOOK TAB */}
          {activeTab === 'webhook' && (
            <div className="webhook-tab">
              {/* Razorpay Webhook Section */}
              <div className="section" style={{ background: '#ffffff', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1rem', color: '#111827', border: '1px solid #10B981' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ width: '40px', height: '40px', background: '#ECFDF5', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #A7F3D0' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>Razorpay Webhook</h3>
                    <span className="badge" style={{ background: '#D1FAE5', color: '#111827', marginTop: '4px' }}>Active</span>
                  </div>
                </div>
                
                <div style={{ background: '#ECFDF5', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #A7F3D0' }}>
                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Webhook URL</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827' }}>https://api.wecare.digital/razorpay-webhook</code>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Webhook Secret</label>
                    <code style={{ fontSize: '0.85rem', color: '#111827' }}>b@c4mk9t9Z8qLq3</code>
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, marginBottom: '0.5rem', display: 'block', color: '#111827' }}>Supported Events</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {[
                      { event: 'payment.captured', desc: 'Payment successful', color: '#10b981' },
                      { event: 'payment.failed', desc: 'Payment failed', color: '#ef4444' },
                      { event: 'payment.authorized', desc: 'Payment authorized', color: '#10b981' },
                      { event: 'refund.created', desc: 'Refund initiated', color: '#6b7280' },
                      { event: 'refund.processed', desc: 'Refund completed', color: '#10b981' },
                      { event: 'order.paid', desc: 'Order paid', color: '#10b981' },
                      { event: 'payment_link.paid', desc: 'Payment link used', color: '#10b981' },
                      { event: 'payment.dispute.*', desc: 'Dispute events', color: '#ef4444' },
                      { event: 'settlement.*', desc: 'Settlement events', color: '#10b981' },
                    ].map(({ event, desc, color }) => (
                      <div key={event} style={{ background: '#D1FAE5', padding: '0.5rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.8rem', border: '1px solid #A7F3D0' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                          <span style={{ fontFamily: 'monospace', color: '#111827' }}>{event}</span>
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '2px' }}>{desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Razorpay Data Captured */}
              <div className="section" style={{ background: 'white', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', border: '1px solid #10B981' }}>
                <h4 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#111827' }}>
                  <DataIcon size={18} />
                  Data Captured for Payments
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                  {[
                    { field: 'paymentId', desc: 'Razorpay Payment ID' },
                    { field: 'orderId', desc: 'Razorpay Order ID' },
                    { field: 'referenceId', desc: 'Custom Reference ID' },
                    { field: 'amount', desc: 'Amount in paise' },
                    { field: 'amountInRupees', desc: 'Amount in rupees' },
                    { field: 'currency', desc: 'Currency (INR)' },
                    { field: 'method', desc: 'UPI, Card, Netbanking, Wallet' },
                    { field: 'contact', desc: 'Customer phone' },
                    { field: 'email', desc: 'Customer email' },
                    { field: 'status', desc: 'captured, failed, etc.' },
                    { field: 'notes', desc: 'Custom metadata' },
                    { field: 'createdAt', desc: 'Timestamp' },
                  ].map(({ field, desc }) => (
                    <div key={field} style={{ padding: '0.75rem', background: '#ECFDF5', borderRadius: '0.375rem', borderLeft: '3px solid #10B981' }}>
                      <code style={{ fontSize: '0.85rem', color: '#059669' }}>{field}</code>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '2px' }}>{desc}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Airtel Voice Webhook Section */}
              <div className="section" style={{ background: '#ffffff', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', color: '#111827', border: '1px solid #E53935' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ width: '40px', height: '40px', background: '#FFEBEE', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #FFCDD2' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" stroke="#E53935" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>Airtel Cloud Communication Platform</h3>
                    <span className="badge" style={{ background: '#FFEBEE', color: '#C62828', marginTop: '4px' }}>Voice CDR (Inbound + Outbound) + C2C + OBD</span>
                  </div>
                </div>
                
                {/* Webhook URLs */}
                <div style={{ background: '#FFEBEE', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #FFCDD2' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#C62828' }}>📌 Webhook URLs for Airtel Configuration</h4>
                  
                  <div style={{ marginBottom: '0.75rem', background: '#FFF9C4', padding: '0.75rem', borderRadius: '4px', border: '1px solid #FFF176' }}>
                    <label style={{ fontSize: '0.75rem', color: '#F57F17', display: 'block', fontWeight: 600 }}>⚠️ OLD URL (DEPRECATED - ask Airtel to replace)</label>
                    <code style={{ fontSize: '0.8rem', color: '#E65100', textDecoration: 'line-through' }}>https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook</code>
                  </div>

                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>CDR Webhook URL (Airtel → Us, for callBackURLs eventType: "CDR" and "ALL")</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>https://api.wecare.digital/voice-cdr-webhook</code>
                    <div style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '2px' }}>Accepts both Airtel CDR formats (camelCase and Display_Format)</div>
                  </div>
                  
                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>C2C API (Click-to-Call) — also accepts CDR callbacks</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>https://api.wecare.digital/voice-in/c2c</code>
                  </div>

                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>OBD API (Outbound Dialer) — also accepts CDR callbacks</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>https://api.wecare.digital/voice-in/obd</code>
                  </div>

                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>CDR Read API (Internal dashboard — not for Airtel)</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>https://api.wecare.digital/voice-cdr-read</code>
                  </div>
                  
                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>HTTP Method</label>
                    <code style={{ fontSize: '0.85rem', color: '#111827' }}>POST</code>
                  </div>
                  
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Content-Type</label>
                    <code style={{ fontSize: '0.85rem', color: '#111827' }}>application/json</code>
                  </div>
                </div>

                {/* Contact Info */}
                <div style={{ background: '#FFF3E0', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #FFE0B2' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#E65100' }}>📞 Contact Information</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Inbound Number</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>+91 9319767034</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Contact Email</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>voice@wecare.digital</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Customer ID</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>WECAREDIG_v6J1SyLLI2auy7Lw9JrW</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>App ID</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>WECAREDIG_fD4BKqUbC8k90jNrPR0n</code>
                    </div>
                  </div>
                </div>

                {/* Sample callBackURLs Config */}
                <div style={{ background: '#E8F5E9', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #C8E6C9' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#2E7D32' }}>✅ Sample callBackURLs Configuration</h4>
                  <pre style={{ fontSize: '0.75rem', color: '#111827', background: '#fff', padding: '0.75rem', borderRadius: '4px', overflow: 'auto', margin: 0 }}>{`"callBackURLs": [
  {
    "eventType": "CDR",
    "notifyURL": "https://api.wecare.digital/voice-cdr-webhook",
    "method": "POST",
    "headers": {}
  },
  {
    "eventType": "ALL",
    "notifyURL": "https://api.wecare.digital/voice-cdr-webhook",
    "method": "POST",
    "headers": {}
  }
]`}</pre>
                </div>

                {/* Supported Event Types */}
                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, marginBottom: '0.5rem', display: 'block', color: '#111827' }}>Supported Event Types</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {[
                      { event: 'CDR', desc: 'Call Detail Records', color: '#E53935' },
                      { event: 'ALL', desc: 'All real-time events', color: '#E53935' },
                      { event: 'CALL', desc: 'Call state changes', color: '#FB8C00' },
                      { event: 'MEDIA', desc: 'Audio playback events', color: '#7B1FA2' },
                      { event: 'DTMF', desc: 'Keypad input events', color: '#1976D2' },
                      { event: 'RECORD', desc: 'Recording events', color: '#388E3C' },
                    ].map(({ event, desc, color }) => (
                      <div key={event} style={{ background: '#FFEBEE', padding: '0.5rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.8rem', border: '1px solid #FFCDD2' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                          <span style={{ fontFamily: 'monospace', color: '#111827', fontWeight: 500 }}>{event}</span>
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '2px' }}>{desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Message to Share with Airtel */}
              <div className="section" style={{ background: '#E3F2FD', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', border: '1px solid #90CAF9' }}>
                <h4 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#1565C0' }}>
                  📋 Complete Airtel Integration Reference
                </h4>
                <div style={{ background: '#fff', padding: '1rem', borderRadius: '0.5rem', border: '1px solid #BBDEFB' }}>
                  <pre style={{ fontSize: '0.8rem', color: '#111827', whiteSpace: 'pre-wrap', margin: 0, lineHeight: 1.6 }}>{AIRTEL_REFERENCE_TEXT}</pre>
                </div>
                <button 
                  onClick={() => {
                    navigator.clipboard.writeText(AIRTEL_REFERENCE_TEXT);
                    alert('Message copied to clipboard!');
                  }}
                  style={{ marginTop: '1rem', padding: '0.75rem 1.5rem', background: '#1976D2', color: '#fff', border: 'none', borderRadius: '0.5rem', cursor: 'pointer', fontWeight: 500 }}
                >
                  📋 Copy Full Reference to Clipboard
                </button>
              </div>

              {/* Voice CDR Data Captured */}
              <div className="section" style={{ background: 'white', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', border: '1px solid #10B981' }}>
                <h4 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#111827' }}>
                  <DataIcon size={18} />
                  Data Captured for Voice CDR
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                  {[
                    { field: 'vmSessionId', desc: 'Unique session identifier' },
                    { field: 'clientCorrelationId', desc: 'Xchange ID for tracking' },
                    { field: 'customerId', desc: 'Customer identifier' },
                    { field: 'callType', desc: 'INBOUND or OUTBOUND' },
                    { field: 'overallCallStatus', desc: 'Answered, Missed, Busy' },
                    { field: 'callerNumber', desc: 'Caller phone number' },
                    { field: 'destinationNumber', desc: 'Destination phone' },
                    { field: 'calledNumber', desc: 'Called number (VN)' },
                    { field: 'durationSec', desc: 'Total duration (seconds)' },
                    { field: 'fromWaitingTimeSec', desc: 'IVR/wait time' },
                    { field: 'conversationDurationSec', desc: 'Talk time (seconds)' },
                    { field: 'billableDurationSec', desc: 'Billable duration' },
                    { field: 'circleNameCaller', desc: 'Caller state/circle' },
                    { field: 'operatorNameCaller', desc: 'Caller telecom operator' },
                    { field: 'recordingURL', desc: 'Call recording URL' },
                    { field: 'hangupCause', desc: 'USER/SYSTEM_INITIATED' },
                  ].map(({ field, desc }) => (
                    <div key={field} style={{ padding: '0.75rem', background: '#ECFDF5', borderRadius: '0.375rem', borderLeft: '3px solid #10B981' }}>
                      <code style={{ fontSize: '0.85rem', color: '#059669' }}>{field}</code>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '2px' }}>{desc}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Airtel SMS Webhook Section */}
              <div className="section" style={{ background: '#ffffff', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', color: '#111827', border: '1px solid #1976D2' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ width: '40px', height: '40px', background: '#E3F2FD', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #90CAF9' }}>
                    <SmsIcon size={24} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>Airtel IQ SMS</h3>
                    <span className="badge" style={{ background: '#E3F2FD', color: '#1565C0', marginTop: '4px' }}>DLT Compliant</span>
                  </div>
                </div>
                
                <div style={{ background: '#E3F2FD', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #90CAF9' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#1565C0' }}>📌 SMS API Endpoints</h4>
                  
                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Send SMS (via our API — supports v4/v5/v6)</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>POST https://api.wecare.digital/sms-in/airtel</code>
                  </div>
                  
                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>List SMS Messages</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>GET https://api.wecare.digital/sms-in/airtel</code>
                  </div>

                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Delete SMS Message</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>DELETE https://api.wecare.digital/sms-in/airtel?messageId=xxx</code>
                  </div>

                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Clear All SMS Logs</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>DELETE https://api.wecare.digital/sms-in/airtel/clear-logs</code>
                  </div>

                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>DLT Templates (CRUD)</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.5rem', display: 'block', borderRadius: '4px', marginTop: '4px' }}>GET/POST/DELETE https://api.wecare.digital/sms-in/airtel/templates</code>
                  </div>

                  <h4 style={{ margin: '0.75rem 0 0.5rem 0', fontSize: '0.85rem', color: '#1565C0' }}>Airtel IQ Direct Endpoints (3 versions)</h4>
                  {[
                    { label: 'v4 — Single / Multiple SMS', url: 'POST https://iqmessaging.airtel.in/api/v4/send-sms' },
                    { label: 'v5 — Content Moderation (no DLT fields needed)', url: 'POST https://iqmessaging.airtel.in/api/v5/send-sms-cm' },
                    { label: 'v6 — Enhanced Response (echo-back fields)', url: 'POST https://iqmessaging.airtel.in/api/v6/send-sms' },
                    { label: 'Bulk SMS (Conduit API — per-recipient payload)', url: 'POST https://iqmessaging.airtel.in/conduit/api/v1/send-sms-bulk' },
                  ].map(({ label, url }) => (
                    <div key={label} style={{ marginBottom: '0.5rem' }}>
                      <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block' }}>{label}</label>
                      <code style={{ fontSize: '0.8rem', wordBreak: 'break-all', color: '#111827', background: '#fff', padding: '0.35rem 0.5rem', display: 'inline-block', borderRadius: '4px', marginTop: '2px' }}>{url}</code>
                    </div>
                  ))}
                  <div style={{ fontSize: '0.75rem', color: '#1565C0', marginTop: '0.5rem', fontStyle: 'italic' }}>
                    v4/v5/v6: Basic auth + customerId header · Bulk/Conduit: Basic auth only (no customerId)
                  </div>
                </div>

                <div style={{ background: '#FFF3E0', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #FFE0B2' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#E65100' }}>📞 DLT Configuration (TRAI TCCCPR 2019)</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Sender ID (Header)</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>WDBEEP</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>PE ID (Entity ID)</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>1201161991108627443</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Default Template ID</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>1007974344269130859</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>API Host</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>iqmessaging.airtel.in</code>
                    </div>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#E65100', marginTop: '0.75rem', lineHeight: '1.5' }}>
                    ⚠ v5 (Content Moderation) does NOT require DLT fields — auto-handled by Airtel.<br/>
                    ⚠ Promotional messages: No DLR sent back (except NACK from DLT).<br/>
                    ⚠ MSISDN must be 10 or 12 digits (India format).
                  </div>
                </div>

                <div style={{ background: '#E8F5E9', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #C8E6C9' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#2E7D32' }}>✅ Sample Send SMS Requests</h4>
                  <pre style={{ fontSize: '0.75rem', color: '#111827', background: '#fff', padding: '0.75rem', borderRadius: '4px', overflow: 'auto', margin: 0 }}>{`# Single SMS (v4)
POST /sms-in/airtel
{
  "phoneNumber": "9876543210",
  "content": "Your OTP is 123456",
  "messageType": "SERVICE_EXPLICIT",
  "dltTemplateId": "1007974344269130859"
}

# Multiple Recipients (same v4 endpoint)
POST /sms-in/airtel
{
  "phoneNumbers": ["8130078559", "7089012345"],
  "content": "Hello from WECARE.DIGITAL",
  "messageType": "SERVICE_EXPLICIT",
  "dltTemplateId": "1007974344269130859"
}

# Bulk via Conduit API (different format per recipient)
POST /sms-in/airtel
{
  "bulk": true,
  "phoneNumbers": ["8130078559", "7089012345"],
  "content": "Hello from WECARE.DIGITAL",
  "messageType": "SERVICE_EXPLICIT",
  "dltTemplateId": "1007101741507674990"
}

apiVersion: "v4" (default) | "v5" (content mod) | "v6" (enhanced)
metaData: { "key": "value" } (optional, flows to IQ reporting)`}</pre>
                </div>

                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, marginBottom: '0.5rem', display: 'block', color: '#111827' }}>Supported Message Types</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {[
                      { type: 'SERVICE_EXPLICIT', desc: 'Service messages (opt-in)', color: '#1976D2' },
                      { type: 'SERVICE_IMPLICIT', desc: 'Service messages (implicit)', color: '#1976D2' },
                      { type: 'TRANSACTIONAL', desc: 'OTP, alerts, etc.', color: '#388E3C' },
                      { type: 'PROMOTIONAL', desc: 'Marketing messages', color: '#F57C00' },
                    ].map(({ type, desc, color }) => (
                      <div key={type} style={{ background: '#E3F2FD', padding: '0.5rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.8rem', border: '1px solid #90CAF9' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                          <span style={{ fontFamily: 'monospace', color: '#111827', fontWeight: 500 }}>{type}</span>
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '2px' }}>{desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* AWS Pinpoint SMS & Voice Section */}
              <div className="section" style={{ background: '#ffffff', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', color: '#111827', border: '1px solid #10B981' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ width: '40px', height: '40px', background: '#ECFDF5', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #A7F3D0' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>AWS Pinpoint SMS & Voice v2</h3>
                    <span className="badge" style={{ background: '#D1FAE5', color: '#065f46', marginTop: '4px' }}>us-east-1 | Active</span>
                  </div>
                </div>
                
                <div style={{ background: '#ECFDF5', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #A7F3D0' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#065f46' }}>📌 API Endpoints</h4>
                  {[
                    { label: 'Send SMS', method: 'POST', path: '/sms-aws/send' },
                    { label: 'List SMS Messages', method: 'GET', path: '/sms-aws/messages' },
                    { label: 'Delete SMS Message', method: 'DELETE', path: '/sms-aws/messages/{messageId}' },
                    { label: 'Clear SMS Logs', method: 'DELETE', path: '/sms-aws/clear-logs' },
                    { label: 'Make Voice Call (TTS)', method: 'POST', path: '/voice-aws/call' },
                    { label: 'List Voice Calls', method: 'GET', path: '/voice-aws/calls' },
                    { label: 'Delete Voice Call', method: 'DELETE', path: '/voice-aws/calls/{callId}' },
                    { label: 'Clear Voice Logs', method: 'DELETE', path: '/voice-aws/clear-logs' },
                  ].map(({ label, method, path }) => (
                    <div key={path} style={{ marginBottom: '0.5rem' }}>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>{label}</label>
                      <code style={{ fontSize: '0.8rem', color: '#111827', background: '#fff', padding: '0.35rem 0.5rem', display: 'inline-block', borderRadius: '4px', marginTop: '2px' }}>
                        <span style={{ color: method === 'POST' ? '#059669' : method === 'DELETE' ? '#dc2626' : '#1d4ed8', fontWeight: 600 }}>{method}</span> https://api.wecare.digital{path}
                      </code>
                    </div>
                  ))}
                </div>

                <div style={{ background: '#FFF3E0', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #FFE0B2' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#E65100' }}>📞 Phone Numbers & Configuration</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Voice (Toll-Free, Intl)</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>+1 (844) 489-1209</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Toll-Free Status</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>PENDING Registration</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>SMS Sender ID</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>WECARE</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>TTS Voice</label>
                      <code style={{ fontSize: '0.85rem', color: '#111827' }}>RAVEENA (Indian English)</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Pool ID</label>
                      <code style={{ fontSize: '0.75rem', color: '#111827' }}>TBD (pending toll-free approval)</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Protect Config</label>
                      <code style={{ fontSize: '0.75rem', color: '#111827' }}>protect-b137924dfb934c32b1d10c28b737d08c</code>
                    </div>
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, marginBottom: '0.5rem', display: 'block', color: '#111827' }}>Lambda Functions</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {[
                      { name: 'wecare-sms-aws', desc: 'SMS send + CRUD', color: '#10b981' },
                      { name: 'wecare-voice-aws', desc: 'Voice call + CRUD', color: '#10b981' },
                    ].map(({ name, desc, color }) => (
                      <div key={name} style={{ background: '#ECFDF5', padding: '0.5rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.8rem', border: '1px solid #A7F3D0' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                          <span style={{ fontFamily: 'monospace', color: '#111827', fontWeight: 500 }}>{name}</span>
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '2px' }}>{desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* WhatsApp Inbound Messages Webhook */}
              <div className="section" style={{ background: '#ffffff', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', color: '#111827', border: '1px solid #25D366' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ width: '40px', height: '40px', background: '#ECFDF5', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #A7F3D0' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" stroke="#25D366" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>WhatsApp Inbound Messages</h3>
                    <span className="badge" style={{ background: '#D1FAE5', color: '#065f46', marginTop: '4px' }}>AWS EUM Managed | Active</span>
                  </div>
                </div>

                <div style={{ background: '#ECFDF5', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #A7F3D0' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#065f46' }}>📌 Webhook Configuration</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.85rem' }}>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Webhook URL</span><code style={{ color: '#111827' }}>https://api.wecare.digital/whatsapp/inbound</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Method</span><code style={{ color: '#111827' }}>POST</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Lambda</span><code style={{ color: '#111827' }}>wecare-inbound-whatsapp-handler</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Verify Token</span><code style={{ color: '#111827' }}>N/A (AWS EUM managed)</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Subscribed Fields</span><code style={{ color: '#111827' }}>messages</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>WABA 1</span><code style={{ color: '#111827' }}>1912405516040025 (WECARE.DIGITAL)</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>WABA 2</span><code style={{ color: '#111827' }}>1633959101297902 (Manish Agarwal)</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Meta App</span><code style={{ color: '#111827' }}>891766673609917 (wecare_token)</code></div>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#065f46', marginTop: '0.75rem', fontStyle: 'italic' }}>
                    Managed by AWS End User Messaging (EUM) — webhook verification handled automatically by AWS.
                  </div>
                </div>
              </div>

              {/* WhatsApp Calling Webhook */}
              <div className="section" style={{ background: '#ffffff', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', color: '#111827', border: '1px solid #25D366' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ width: '40px', height: '40px', background: '#ECFDF5', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #A7F3D0' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M15.05 5A5 5 0 0119 8.95M15.05 1A9 9 0 0123 8.94m-1 7.98v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" stroke="#25D366" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>WhatsApp Business Calling</h3>
                    <span className="badge" style={{ background: '#D1FAE5', color: '#065f46', marginTop: '4px' }}>Meta Graph API + WebRTC | Active</span>
                  </div>
                </div>

                <div style={{ background: '#ECFDF5', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #A7F3D0' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#065f46' }}>📌 Webhook Configuration (Meta App Dashboard)</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.85rem' }}>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Callback URL</span><code style={{ color: '#111827', background: '#fff', padding: '0.25rem 0.5rem', borderRadius: '4px', display: 'inline-block' }}>https://api.wecare.digital/whatsapp-calling</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Verify Token</span><code style={{ color: '#111827', background: '#fff', padding: '0.25rem 0.5rem', borderRadius: '4px', display: 'inline-block' }}>wecare_calling_verify_2026</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Subscribed Fields</span><code style={{ color: '#111827' }}>calls</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Lambda</span><code style={{ color: '#111827' }}>wecare-whatsapp-calling</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>Meta App ID</span><code style={{ color: '#111827' }}>891766673609917 (wecare_token)</code></div>
                    <div><span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block' }}>DynamoDB Table</span><code style={{ color: '#111827' }}>WhatsAppCallingTable</code></div>
                  </div>

                  <div style={{ marginTop: '0.75rem' }}>
                    <span style={{ color: '#6b7280', fontSize: '0.75rem', display: 'block', marginBottom: '0.25rem' }}>API Routes (all on api.wecare.digital)</span>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem', fontSize: '0.8rem' }}>
                      {[
                        { m: 'GET', p: '/whatsapp-calling', d: 'Webhook verify' },
                        { m: 'POST', p: '/whatsapp-calling', d: 'Call events from Meta' },
                        { m: 'GET', p: '/whatsapp-calling/active', d: 'Active/ringing calls' },
                        { m: 'GET', p: '/whatsapp-calling/logs', d: 'Call event logs' },
                        { m: 'POST', p: '/whatsapp-calling/accept', d: 'Accept call (SDP answer)' },
                        { m: 'POST', p: '/whatsapp-calling/reject', d: 'Reject ringing call' },
                        { m: 'POST', p: '/whatsapp-calling/hangup', d: 'Hang up active call' },
                        { m: 'POST', p: '/whatsapp-calling/outbound', d: 'Outbound call / permission' },
                        { m: 'GET', p: '/whatsapp-calling/config', d: 'Auto-pickup config' },
                        { m: 'POST', p: '/whatsapp-calling/config', d: 'Update config' },
                        { m: 'DELETE', p: '/whatsapp-calling', d: 'Clear logs' },
                      ].map(({ m, p, d }) => (
                        <div key={`${m}${p}`} style={{ background: '#fff', padding: '0.25rem 0.5rem', borderRadius: '4px' }}>
                          <code><span style={{ color: m === 'POST' ? '#059669' : m === 'DELETE' ? '#dc2626' : '#1d4ed8', fontWeight: 600, fontSize: '0.7rem' }}>{m}</span> <span style={{ fontSize: '0.75rem' }}>{p}</span></code>
                          <span style={{ fontSize: '0.65rem', color: '#9ca3af', marginLeft: '4px' }}>{d}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ background: '#FFF3E0', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem', border: '1px solid #FFE0B2' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#E65100' }}>📞 Phone Numbers (Calling-Ready)</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>+91 93309 94400 (WECARE.DIGITAL)</label>
                      <code style={{ fontSize: '0.8rem', color: '#111827' }}>Meta ID: 960395407161423 · TIER_1K</code>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>+91 99033 00044 (Manish Agarwal)</label>
                      <code style={{ fontSize: '0.8rem', color: '#111827' }}>Meta ID: 997428863451102 · TIER_10K</code>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <button onClick={() => { navigator.clipboard.writeText('https://api.wecare.digital/whatsapp-calling'); alert('Callback URL copied!'); }}
                    style={{ padding: '0.5rem 1rem', background: '#25D366', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500 }}>
                    📋 Copy Callback URL
                  </button>
                  <button onClick={() => { navigator.clipboard.writeText('wecare_calling_verify_2026'); alert('Verify token copied!'); }}
                    style={{ padding: '0.5rem 1rem', background: '#065f46', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500 }}>
                    📋 Copy Verify Token
                  </button>
                  <a href="https://developers.facebook.com/apps/891766673609917/webhooks/" target="_blank" rel="noopener noreferrer"
                    style={{ padding: '0.5rem 1rem', background: '#1877F2', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500, textDecoration: 'none', display: 'inline-block' }}>
                    🔗 Open Meta App Dashboard
                  </a>
                </div>
              </div>

              {/* Custom Webhooks Section */}
              <div className="section-header" style={{ marginTop: '2rem' }}>
                <h3>Custom Webhooks</h3>
                <Button variant={showWebhookForm ? 'secondary' : 'primary'} onClick={() => setShowWebhookForm(!showWebhookForm)}>
                  {showWebhookForm ? 'Cancel' : '+ Add Webhook'}
                </Button>
              </div>

              {/* Add Webhook Form */}
              {showWebhookForm && (
                <div className="section" style={{ background: 'white', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                  <h4 style={{ marginBottom: '1rem' }}>New Webhook</h4>
                  
                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Name</label>
                    <input
                      type="text"
                      value={newWebhook.name}
                      onChange={(e) => setNewWebhook({ ...newWebhook, name: e.target.value })}
                      placeholder="My Webhook"
                      style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                    />
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>URL</label>
                    <input
                      type="url"
                      value={newWebhook.url}
                      onChange={(e) => setNewWebhook({ ...newWebhook, url: e.target.value })}
                      placeholder="https://your-server.com/webhook"
                      style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                    />
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500 }}>Events</label>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                      {['message.received', 'message.sent', 'message.delivered', 'message.read', 'payment.captured', 'payment.failed', 'contact.created', 'contact.updated'].map(event => (
                        <label key={event} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.5rem', background: '#f3f4f6', borderRadius: '0.25rem', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={newWebhook.events.includes(event)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setNewWebhook({ ...newWebhook, events: [...newWebhook.events, event] });
                              } else {
                                setNewWebhook({ ...newWebhook, events: newWebhook.events.filter(ev => ev !== event) });
                              }
                            }}
                          />
                          <span style={{ fontSize: '0.85rem' }}>{event}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <Button variant="primary" onClick={handleCreateWebhook} disabled={!newWebhook.name || !newWebhook.url}>
                    Create Webhook
                  </Button>
                </div>
              )}

              {/* Webhooks List */}
              {webhookLoading ? (
                <div style={{ textAlign: 'center', padding: '2rem' }}>Loading webhooks...</div>
              ) : webhooks.length === 0 ? (
                <div className="empty-state">
                  <span className="icon"><LinkIcon size={32} /></span>
                  <p>No custom webhooks configured</p>
                  <p style={{ fontSize: '0.85rem', color: '#666' }}>Add a webhook to receive real-time notifications</p>
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>URL</th>
                      <th>Events</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {webhooks.map(wh => (
                      <tr key={wh.id}>
                        <td>{wh.name}</td>
                        <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{wh.url}</td>
                        <td>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                            {wh.events.slice(0, 3).map(ev => (
                              <span key={ev} className="badge">{ev}</span>
                            ))}
                            {wh.events.length > 3 && <span className="badge">+{wh.events.length - 3}</span>}
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${wh.enabled ? 'success' : ''}`}>
                            {wh.enabled ? 'Active' : 'Disabled'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleWebhook(wh.id, !wh.enabled)}
                            >
                              {wh.enabled ? 'Disable' : 'Enable'}
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => handleDeleteWebhook(wh.id)}
                            >
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {/* Info */}
              <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem', fontSize: '0.85rem', color: '#666' }}>
                <strong>Webhook Info:</strong> Webhooks send HTTP POST requests to your URL when events occur.
                Each request includes a signature header (X-Razorpay-Signature) for HMAC SHA256 verification.
              </div>
            </div>
          )}

          {/* USER GUIDE TAB */}
          {activeTab === 'guide' && (
            <div className="guide-tab">
              <div className="section">
                <h3>Welcome to WECARE.DIGITAL</h3>
                <p style={{ color: 'var(--notion-text-secondary)', marginBottom: '24px' }}>
                  Your multi-channel messaging platform for WhatsApp, SMS, Email, and Voice communications.
                </p>
              </div>

              <div className="section">
                <h3>Getting Started</h3>
                <div className="guide-cards">
                  <div className="guide-card">
                    <span className="guide-icon"><WhatsAppIcon size={24} /></span>
                    <h4>WhatsApp Messaging</h4>
                    <p>Send and receive WhatsApp messages. Go to Messages → WhatsApp to start conversations.</p>
                  </div>
                  <div className="guide-card">
                    <span className="guide-icon"><PaymentIcon size={24} /></span>
                    <h4>Payments</h4>
                    <p>Send payment requests via WhatsApp using Razorpay integration. Navigate to Pay → WhatsApp Pay.</p>
                  </div>
                  <div className="guide-card">
                    <span className="guide-icon"><ContactsIcon size={24} /></span>
                    <h4>Contacts</h4>
                    <p>Manage your contact list. Import/export contacts and organize them for campaigns.</p>
                  </div>
                  <div className="guide-card">
                    <span className="guide-icon"><BulkIcon size={24} /></span>
                    <h4>Bulk Messaging</h4>
                    <p>Send messages to multiple recipients at once. Use templates for consistent communication.</p>
                  </div>
                </div>
              </div>

              <div className="section">
                <h3>Key Features</h3>
                <ul className="guide-list">
                  <li><strong>Multi-Channel:</strong> WhatsApp, SMS (AWS Pinpoint, IN SMS), Email (SES), Voice calls</li>
                  <li><strong>Templates:</strong> Create and manage WhatsApp message templates</li>
                  <li><strong>AI Assistant:</strong> Get AI-powered response suggestions</li>
                  <li><strong>Webhooks:</strong> Integrate with external systems via webhooks</li>
                  <li><strong>Billing:</strong> Track AWS resource usage and costs</li>
                  <li><strong>Bulk Operations:</strong> Send campaigns to multiple contacts</li>
                </ul>
              </div>

              <div className="section">
                <h3>WhatsApp Numbers</h3>
                <div className="phones-grid">
                  <div className="phone-card">
                    <div className="phone-name">WECARE.DIGITAL</div>
                    <div className="phone-num">+91 93309 94400</div>
                    <span className="badge">Razorpay + UPI</span>
                  </div>
                  <div className="phone-card">
                    <div className="phone-name">Manish Agarwal</div>
                    <div className="phone-num">+91 99033 00044</div>
                    <span className="badge">Active</span>
                  </div>
                </div>
              </div>

              <div className="section">
                <h3>Need Help?</h3>
                <p style={{ color: 'var(--notion-text-secondary)' }}>
                  Use the AI Assistant tab for quick answers, or contact support for technical issues.
                </p>
              </div>
            </div>
          )}

          {/* SEARCH TAB */}
          {activeTab === 'search' && (
            <div className="search-tab">
              <div className="search-bar large">
                <input
                  type="text"
                  placeholder="Search contacts, messages, content..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  autoFocus
                />
                {searchQuery && <button onClick={() => setSearchQuery('')}>×</button>}
              </div>

              {searchQuery.trim() && (
                <>
                  {/* Contact Results */}
                  {contacts.filter(c => 
                    c.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                    c.phone?.includes(searchQuery)
                  ).length > 0 && (
                    <div className="section">
                      <h3>Contacts</h3>
                      <div className="search-results">
                        {contacts.filter(c => 
                          c.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          c.phone?.includes(searchQuery)
                        ).slice(0, 10).map(c => (
                          <div key={c.id} className="result-item contact">
                            <span className="icon"><ContactsIcon size={18} /></span>
                            <span className="name">{c.name || 'Unknown'}</span>
                            <span className="phone">{c.phone}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Message Results */}
                  {filteredMessages.length > 0 && (
                    <div className="section">
                      <h3>Messages ({filteredMessages.length})</h3>
                      <div className="msg-list full">
                        {filteredMessages.slice(0, 20).map(msg => {
                          const contact = contacts.find(c => c.id === msg.contactId);
                          return (
                            <div key={msg.id} className={`msg-item ${msg.direction.toLowerCase()}`}>
                              <span className="dir">{msg.direction === 'INBOUND' ? '↓' : '↑'}</span>
                              <span className="name">{contact?.name || contact?.phone || '...'}</span>
                              <span className="content">{msg.content?.slice(0, 60) || '[Media]'}</span>
                              <span className="time">{new Date(msg.timestamp).toLocaleString()}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* No Results */}
                  {contacts.filter(c => 
                    c.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                    c.phone?.includes(searchQuery)
                  ).length === 0 && filteredMessages.length === 0 && (
                    <div className="empty-state">
                      <span className="icon"><SearchIcon size={32} /></span>
                      <p>No results for "{searchQuery}"</p>
                    </div>
                  )}
                </>
              )}

              {!searchQuery.trim() && (
                <div className="empty-state">
                  <span className="icon"><SearchIcon size={32} /></span>
                  <p>Type to search contacts and messages</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Billing table expand styles - other styles in Dashboard.css */}
      <style jsx>{`
        .billing-row.warning { background: #ECFDF5; }
        .billing-row.paid { background: #fef2f2; }
        .expand-cell { width: 30px; }
        .expand-btn { width: 28px; height: 28px; border: 1px solid var(--notion-border, #e9e9e7); border-radius: 6px; background: var(--notion-bg, #fff); cursor: pointer; font-size: 16px; color: var(--notion-text-secondary, #787774); }
        .expand-btn:hover { background: var(--notion-bg-hover, #efefef); color: var(--notion-text, #37352f); }
        .resource-row { background: var(--notion-bg-secondary, #f7f6f3); }
        .resource-details { padding: 12px 0; font-size: 14px; }
        .resource-details div { margin: 6px 0; color: var(--notion-text-secondary, #787774); }
        .resource-details strong { color: var(--notion-text, #37352f); }
        .resource-details code { background: var(--notion-bg-hover, #efefef); padding: 4px 8px; border-radius: 4px; font-size: 13px; word-break: break-all; font-family: var(--font-mono, monospace); }
        .resource-list { margin-top: 12px; }
        .resource-list ul { margin: 8px 0 0 20px; padding: 0; }
        .resource-list li { margin: 4px 0; color: var(--notion-text-secondary, #787774); font-family: var(--font-mono, monospace); font-size: 13px; }
      `}</style>
    </Layout>
  );
};

export default Dashboard;
