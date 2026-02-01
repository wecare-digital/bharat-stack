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
import * as api from '../../api/client';
import { 
  DashboardIcon, MessageIcon, PaymentIcon, DataIcon, BillingIcon, 
  AIIcon, LinkIcon, SearchIcon, WhatsAppIcon, InvoiceIcon, 
  ContactsIcon, BulkIcon, SmsIcon, EmailIcon, RefreshIcon,
  DocumentIcon
} from '../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'overview' | 'messages' | 'pay' | 'data' | 'billing' | 'search' | 'ai' | 'webhook' | 'guide';

const PAYMENT_PHONE = '+91 93309 94400';
const PAYMENT_NAME = 'WECARE.DIGITAL';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';

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
  agentId: 'TJAZR473IJ',
  agentAlias: 'O4U1HF2MSX',
  knowledgeBaseId: '7IWHVB0ZXQ',
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

// AWS Resource ARNs for billing display - All resources in account 809904170947
// Comprehensive list including used and available services for future updates
const AWS_RESOURCES: Record<string, { arn: string; accountId: string; details?: string[] }> = {
  // COMPUTE
  'AWS Lambda': { 
    arn: 'arn:aws:lambda:us-east-1:809904170947:function:*', 
    accountId: '809904170947',
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
      'wecare-dlq-replay'
    ]
  },
  'Amazon EC2': { 
    arn: 'arn:aws:ec2:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon ECS': { 
    arn: 'arn:aws:ecs:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'AWS Fargate': { 
    arn: 'arn:aws:ecs:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  
  // DATABASE
  'Amazon DynamoDB': { 
    arn: 'arn:aws:dynamodb:us-east-1:809904170947:table/*', 
    accountId: '809904170947',
    details: [
      'base-wecare-digital-ContactsTable',
      'base-wecare-digital-WhatsAppOutboundTable',
      'base-wecare-digital-MediaFilesTable',
      'base-wecare-digital-RateLimitTable'
    ]
  },
  'Amazon RDS': { 
    arn: 'arn:aws:rds:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon Aurora': { 
    arn: 'arn:aws:rds:us-east-1:809904170947:cluster:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon ElastiCache': { 
    arn: 'arn:aws:elasticache:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  
  // STORAGE
  'Amazon S3': { 
    arn: 'arn:aws:s3:::auth.wecare.digital', 
    accountId: '809904170947',
    details: ['auth.wecare.digital - Media storage for WhatsApp']
  },
  'Amazon EBS': { 
    arn: 'arn:aws:ec2:us-east-1:809904170947:volume/*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon EFS': { 
    arn: 'arn:aws:elasticfilesystem:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  
  // NETWORKING & CDN
  'Amazon CloudFront': { 
    arn: 'arn:aws:cloudfront::809904170947:distribution/*', 
    accountId: '809904170947',
    details: ['CDN for static assets']
  },
  'Amazon Route 53': { 
    arn: 'arn:aws:route53:::hostedzone/*', 
    accountId: '809904170947',
    details: ['wecare.digital', 'base.wecare.digital', 'auth.wecare.digital']
  },
  'Amazon VPC': { 
    arn: 'arn:aws:ec2:us-east-1:809904170947:vpc/*', 
    accountId: '809904170947',
    details: ['Default VPC']
  },
  'Elastic Load Balancing': { 
    arn: 'arn:aws:elasticloadbalancing:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  
  // API & INTEGRATION
  'Amazon API Gateway': { 
    arn: 'arn:aws:apigateway:us-east-1::/restapis/*', 
    accountId: '809904170947',
    details: ['k4vqzmi07b - REST API (prod stage)']
  },
  'AWS AppSync': { 
    arn: 'arn:aws:appsync:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon EventBridge': { 
    arn: 'arn:aws:events:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'AWS Step Functions': { 
    arn: 'arn:aws:states:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  
  // MESSAGING
  'Amazon SNS': { 
    arn: 'arn:aws:sns:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['wecare-whatsapp-inbound-topic']
  },
  'Amazon SQS': { 
    arn: 'arn:aws:sqs:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['wecare-whatsapp-dlq']
  },
  'Amazon SES': { 
    arn: 'arn:aws:ses:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Email sending service']
  },
  'Amazon Pinpoint': { 
    arn: 'arn:aws:mobiletargeting:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['SMS/Voice campaigns']
  },
  'AWS End User Messaging': { 
    arn: 'arn:aws:social-messaging:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: [
      '+91 93309 94400 (WECARE.DIGITAL) - Razorpay enabled',
      '+91 99033 00044 (Manish Agarwal)',
      'WABA ID: 1347766229904230',
      'Service-Linked Role: AWSServiceRoleForSocialMessaging',
      'Policy: AWSSocialMessagingServiceRolePolicy (cloudwatch:PutMetricData)'
    ]
  },
  
  // AI/ML
  'Amazon Bedrock': { 
    arn: 'arn:aws:bedrock:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Knowledge Base: wecare-digital-kb', 'Agent: wecare-digital-agent', 'Model: Claude']
  },
  'Amazon OpenSearch': { 
    arn: 'arn:aws:aoss:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Serverless collection for Bedrock KB vector store']
  },
  'Amazon SageMaker': { 
    arn: 'arn:aws:sagemaker:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon Comprehend': { 
    arn: 'arn:aws:comprehend:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon Rekognition': { 
    arn: 'arn:aws:rekognition:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon Transcribe': { 
    arn: 'arn:aws:transcribe:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon Polly': { 
    arn: 'arn:aws:polly:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'Amazon Translate': { 
    arn: 'arn:aws:translate:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  
  // SECURITY & IDENTITY
  'Amazon Cognito': { 
    arn: 'arn:aws:cognito-idp:us-east-1:809904170947:userpool/*', 
    accountId: '809904170947',
    details: ['User Pool for authentication']
  },
  'AWS IAM': { 
    arn: 'arn:aws:iam::809904170947:*', 
    accountId: '809904170947',
    details: ['wecare-digital-lambda-role', 'amplify-service-role']
  },
  'AWS Secrets Manager': { 
    arn: 'arn:aws:secretsmanager:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'AWS KMS': { 
    arn: 'arn:aws:kms:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Default encryption keys']
  },
  'AWS WAF': { 
    arn: 'arn:aws:wafv2:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  
  // MONITORING & MANAGEMENT
  'CloudWatch': { 
    arn: 'arn:aws:logs:us-east-1:809904170947:log-group:*', 
    accountId: '809904170947',
    details: [
      '/aws/lambda/wecare-outbound-whatsapp',
      '/aws/lambda/wecare-inbound-whatsapp',
      '/aws/lambda/wecare-* (all functions)'
    ]
  },
  'AWS X-Ray': { 
    arn: 'arn:aws:xray:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Not currently used']
  },
  'AWS CloudTrail': { 
    arn: 'arn:aws:cloudtrail:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['API activity logging']
  },
  
  // DEVELOPER TOOLS
  'AWS Amplify': { 
    arn: 'arn:aws:amplify:us-east-1:809904170947:apps/dtiq7il2x5c5g', 
    accountId: '809904170947',
    details: ['App: dtiq7il2x5c5g', 'Branch: base', 'Domain: base.wecare.digital']
  },
  'AWS CodeBuild': { 
    arn: 'arn:aws:codebuild:us-east-1:809904170947:*', 
    accountId: '809904170947',
    details: ['Amplify build process']
  },
  'AWS CodePipeline': { 
    arn: 'arn:aws:codepipeline:us-east-1:809904170947:*', 
    accountId: '809904170947',
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
  const [deleteMode, setDeleteMode] = useState<'messages' | 'hard' | null>(null);
  const [selectedMessages, setSelectedMessages] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  
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
    if (!selectedContact || confirmText !== 'DELETE') return;
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
  }, [activeTab]);

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

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title={PAGE_SEO.dashboard.title}
        description={PAGE_SEO.dashboard.description}
        keywords={PAGE_SEO.dashboard.keywords}
        canonical="/dashboard"
        noindex={true}
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
            {loading ? '...' : '↻'}
          </button>
        </header>

        {/* Tabs */}
        <nav className="dash-tabs">
          {(['overview', 'messages', 'pay', 'data', 'billing', 'ai', 'webhook', 'guide', 'search'] as TabType[]).map(tab => (
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
              {tab === 'ai' && <AIIcon size={16} />}
              {tab === 'webhook' && <LinkIcon size={16} />}
              {tab === 'guide' && <DocumentIcon size={16} />}
              {tab === 'search' && <SearchIcon size={16} />}
              <span>{tab === 'ai' ? 'AI Assistant' : tab === 'webhook' ? 'Webhook' : tab === 'guide' ? 'User Guide' : tab.charAt(0).toUpperCase() + tab.slice(1)}</span>
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
                  <Link href="/bulk" className="action-card">
                    <span className="icon"><BulkIcon size={20} /></span>
                    <span>Bulk</span>
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
                <Link href="/pay" className="btn-primary">+ New Payment</Link>
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
                  className={`danger ${deleteMode === 'hard' ? 'active' : ''}`}
                  onClick={() => setDeleteMode(deleteMode === 'hard' ? null : 'hard')}
                >
                  ⊗ Hard Delete
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
                    <button className="btn-secondary" onClick={() => { setDeleteMode(null); setSelectedMessages([]); }}>Cancel</button>
                    <button className="btn-danger" onClick={handleDeleteMessages} disabled={deleting || selectedMessages.length === 0}>
                      {deleting ? '...' : `Delete ${selectedMessages.length}`}
                    </button>
                  </div>
                </div>
              )}

              {deleteMode === 'hard' && (
                <div className="delete-panel danger">
                  <div className="warning">⚠ Permanently deletes contact, messages, and media files!</div>
                  
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
                    <>
                      <div className="preview">
                        <p>Contact: {contacts.find(c => c.id === selectedContact)?.name || selectedContact}</p>
                        <p>{contactMessages.length} messages, {contactMessages.filter(m => m.s3Key).length} media</p>
                      </div>
                      <div className="form-row">
                        <label>Type DELETE to confirm:</label>
                        <input type="text" value={confirmText} onChange={e => setConfirmText(e.target.value)} placeholder="DELETE" />
                      </div>
                    </>
                  )}
                  
                  <div className="delete-actions">
                    <button className="btn-secondary" onClick={() => { setDeleteMode(null); setSelectedContact(''); setConfirmText(''); }}>Cancel</button>
                    <button className="btn-danger hard" onClick={handleHardDelete} disabled={deleting || confirmText !== 'DELETE'}>
                      {deleting ? '...' : 'Hard Delete'}
                    </button>
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
                <button className="refresh-btn" onClick={() => loadData()}>↻</button>
              </div>
              
              {billingData && (
                <>
                  <div className="billing-summary">
                    <div className="billing-total">
                      <span className="amount">${billingData.totalCost.toFixed(2)}</span>
                      <span className="label">Estimated Cost</span>
                    </div>
                    <div className="billing-meta">
                      <div className="period">{billingData.period}</div>
                      <div className="account">Account: 809904170947</div>
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
                          arn: `arn:aws:*:us-east-1:809904170947:${svc.service.toLowerCase().replace(/\s+/g, '-')}/*`, 
                          accountId: '809904170947' 
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

                <button
                  onClick={handleSaveAiConfig}
                  disabled={aiSaving}
                  className="btn-primary"
                >
                  {aiSaving ? 'Saving...' : 'Save Configuration'}
                </button>
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

                <button
                  onClick={handleTestAi}
                  disabled={aiSaving || !testMessage.trim()}
                  style={{ padding: '0.5rem 1.5rem', background: '#fff', color: '#000', border: '1px solid #000', borderRadius: '13px', cursor: 'pointer', marginBottom: '1rem' }}
                >
                  {aiSaving ? 'Testing...' : 'Test Response'}
                </button>

                {testResult && (
                  <div style={{ padding: '1rem', background: '#f0fdf4', borderRadius: '0.5rem', border: '1px solid #bbf7d0' }}>
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

          {/* WEBHOOK TAB */}
          {activeTab === 'webhook' && (
            <div className="webhook-tab">
              {/* Razorpay Webhook Section */}
              <div className="section" style={{ background: 'linear-gradient(135deg, #072654 0%, #0a3d7c 100%)', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem', color: 'white' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ width: '40px', height: '40px', background: 'white', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#072654" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem' }}>Razorpay Webhook</h3>
                    <span className="badge" style={{ background: '#d1fae5', color: '#111827', marginTop: '4px' }}>Active</span>
                  </div>
                </div>
                
                <div style={{ background: 'rgba(255,255,255,0.1)', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1rem' }}>
                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ fontSize: '0.75rem', opacity: 0.8, display: 'block' }}>Webhook URL</label>
                    <code style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}>https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/razorpay-webhook</code>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', opacity: 0.8, display: 'block' }}>Webhook Secret</label>
                    <code style={{ fontSize: '0.85rem' }}>b@c4mk9t9Z8qLq3</code>
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, marginBottom: '0.5rem', display: 'block' }}>Supported Events</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {[
                      { event: 'payment.captured', desc: 'Payment successful', color: '#10b981' },
                      { event: 'payment.failed', desc: 'Payment failed', color: '#ef4444' },
                      { event: 'payment.authorized', desc: 'Payment authorized', color: '#3b82f6' },
                      { event: 'refund.created', desc: 'Refund initiated', color: '#f59e0b' },
                      { event: 'refund.processed', desc: 'Refund completed', color: '#10b981' },
                      { event: 'order.paid', desc: 'Order paid', color: '#10b981' },
                      { event: 'payment_link.paid', desc: 'Payment link used', color: '#8b5cf6' },
                      { event: 'payment.dispute.*', desc: 'Dispute events', color: '#ef4444' },
                      { event: 'settlement.*', desc: 'Settlement events', color: '#06b6d4' },
                    ].map(({ event, desc, color }) => (
                      <div key={event} style={{ background: 'rgba(255,255,255,0.15)', padding: '0.5rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.8rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                          <span style={{ fontFamily: 'monospace' }}>{event}</span>
                        </div>
                        <div style={{ fontSize: '0.7rem', opacity: 0.7, marginTop: '2px' }}>{desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Razorpay Data Captured */}
              <div className="section" style={{ background: 'white', padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem' }}>
                <h4 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
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
                    <div key={field} style={{ padding: '0.75rem', background: '#f8fafc', borderRadius: '0.375rem', borderLeft: '3px solid #3b82f6' }}>
                      <code style={{ fontSize: '0.85rem', color: '#1e40af' }}>{field}</code>
                      <div style={{ fontSize: '0.75rem', color: '#666', marginTop: '2px' }}>{desc}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Custom Webhooks Section */}
              <div className="section-header" style={{ marginTop: '2rem' }}>
                <h3>Custom Webhooks</h3>
                <button className="btn-primary" onClick={() => setShowWebhookForm(!showWebhookForm)}>
                  {showWebhookForm ? 'Cancel' : '+ Add Webhook'}
                </button>
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

                  <button onClick={handleCreateWebhook} className="btn-primary" disabled={!newWebhook.name || !newWebhook.url}>
                    Create Webhook
                  </button>
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
                            <button
                              onClick={() => handleToggleWebhook(wh.id, !wh.enabled)}
                              style={{ padding: '0.25rem 0.5rem', border: '1px solid #d1d5db', borderRadius: '0.25rem', background: 'white', cursor: 'pointer' }}
                            >
                              {wh.enabled ? 'Disable' : 'Enable'}
                            </button>
                            <button
                              onClick={() => handleDeleteWebhook(wh.id)}
                              style={{ padding: '0.25rem 0.5rem', border: '1px solid #ef4444', borderRadius: '0.25rem', background: 'white', color: '#ef4444', cursor: 'pointer' }}
                            >
                              Delete
                            </button>
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
                    <span className="badge">Razorpay Enabled</span>
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
        .billing-row.warning { background: #fffbeb; }
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
