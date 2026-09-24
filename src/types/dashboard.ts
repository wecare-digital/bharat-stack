/**
 * Dashboard shared types — WECARE.DIGITAL
 */
import * as api from '../api/client';

export interface PageProps {
  signOut?: () => void;
  user?: any;
}

export type TabType =
  | 'overview'
  | 'messages'
  | 'pay'
  | 'factoryreset'
  | 'billing'
  | 'health'
  | 'advisor'
  | 'search'
  | 'ai'
  | 'botflow'
  | 'webhook'
  | 'guide'
  | 'requests'
  | 'internalchat'
  | 'appbuilder'
  | 'system'
  | 'infra';

export interface DashboardData {
  contacts: api.Contact[];
  messages: api.Message[];
  billingData: api.AWSBillingData | null;
  apiConnected: boolean;
  apiLatency: number | null;
  lastRefresh: Date;
  loading: boolean;
}

export interface InternalAIConfig {
  enabled: boolean;
  agentId: string;
  agentAlias: string;
  knowledgeBaseId: string;
  modelId: string;
  maxTokens: number;
  temperature: number;
  systemPrompt: string;
}

export interface WebhookConfig {
  id: string;
  name: string;
  url: string;
  events: string[];
  enabled: boolean;
  secret?: string;
  createdAt: string;
}

export const DEFAULT_AI_CONFIG: InternalAIConfig = {
  enabled: true,
  // No fabricated defaults. Re-measured 2026-09-23: the account's only Bedrock
  // Agent is an empty never-prepared shell and there are 0 knowledge bases, so
  // '4UUQYFWX64' / 'TSTALIASID' / 'static-faq' named nothing. This object is
  // rendered in the dashboard, where a plausible id reads as configuration.
  agentId: process.env.NEXT_PUBLIC_BEDROCK_AGENT_ID || '',
  agentAlias: process.env.NEXT_PUBLIC_BEDROCK_AGENT_ALIAS || '',
  knowledgeBaseId: process.env.NEXT_PUBLIC_BEDROCK_KB_ID || '',
  modelId: 'amazon.nova-pro-v1:0',
  maxTokens: 1024,
  temperature: 0.7,
  systemPrompt: `You are WECARE.DIGITAL's internal admin assistant.
Help operators with:
- Sending WhatsApp messages
- Finding and managing contacts
- Checking message statistics
- Answering questions about the platform`,
};
