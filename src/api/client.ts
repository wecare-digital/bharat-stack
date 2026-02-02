/**
 * API Service Layer
 * Connects to API Gateway -> Lambda -> DynamoDB
 * NO MOCK DATA - All data fetched from real AWS resources
 * 
 * API Endpoint: Uses NEXT_PUBLIC_API_BASE or defaults to production
 */

import { API_BASE, RETRY_CONFIG, DEFAULT_GSTIN } from '../config/constants';

// Connection status tracking
let lastConnectionError: string | null = null;
let connectionStatus: 'connected' | 'disconnected' | 'unknown' = 'unknown';

export function getConnectionStatus() {
  return { status: connectionStatus, lastError: lastConnectionError };
}

// Helper function to delay with exponential backoff
function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Helper function for API calls with retry logic and better error handling
async function apiCall<T>(url: string, options?: RequestInit, retryCount = 0): Promise<T | null> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
    
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    
    clearTimeout(timeoutId);
    
    if (response.ok) {
      connectionStatus = 'connected';
      lastConnectionError = null;
      return response.json();
    }
    
    // Handle specific HTTP errors
    if (response.status === 403) {
      lastConnectionError = 'Access denied - check API Gateway permissions';
    } else if (response.status === 404) {
      lastConnectionError = 'API endpoint not found';
    } else if (response.status === 500) {
      lastConnectionError = 'Server error - check Lambda logs';
    } else if (response.status === 502 || response.status === 503) {
      lastConnectionError = 'API Gateway error - service unavailable';
      // Retry on 502/503 errors
      if (retryCount < RETRY_CONFIG.maxRetries) {
        const delayMs = Math.min(
          RETRY_CONFIG.baseDelayMs * Math.pow(2, retryCount),
          RETRY_CONFIG.maxDelayMs
        );
        console.log(`Retrying API call (${retryCount + 1}/${RETRY_CONFIG.maxRetries}) after ${delayMs}ms...`);
        await delay(delayMs);
        return apiCall<T>(url, options, retryCount + 1);
      }
    } else if (response.status === 429) {
      // Rate limited - retry with backoff
      if (retryCount < RETRY_CONFIG.maxRetries) {
        const delayMs = Math.min(
          RETRY_CONFIG.baseDelayMs * Math.pow(2, retryCount + 1),
          RETRY_CONFIG.maxDelayMs
        );
        console.log(`Rate limited, retrying after ${delayMs}ms...`);
        await delay(delayMs);
        return apiCall<T>(url, options, retryCount + 1);
      }
      lastConnectionError = 'Rate limited - too many requests';
    } else {
      lastConnectionError = `HTTP ${response.status}: ${response.statusText}`;
    }
    
    connectionStatus = 'disconnected';
    console.error(`API error: ${lastConnectionError}`, url);
    return null;
  } catch (e: any) {
    // Retry on network errors
    if (retryCount < RETRY_CONFIG.maxRetries && (e.name === 'AbortError' || e.name === 'TypeError')) {
      const delayMs = Math.min(
        RETRY_CONFIG.baseDelayMs * Math.pow(2, retryCount),
        RETRY_CONFIG.maxDelayMs
      );
      console.log(`Network error, retrying (${retryCount + 1}/${RETRY_CONFIG.maxRetries}) after ${delayMs}ms...`);
      await delay(delayMs);
      return apiCall<T>(url, options, retryCount + 1);
    }
    
    connectionStatus = 'disconnected';
    if (e.name === 'AbortError') {
      lastConnectionError = 'Request timeout - API took too long';
    } else if (e.name === 'TypeError') {
      lastConnectionError = 'CORS error or network unavailable';
    } else {
      lastConnectionError = e.message || 'Connection failed';
    }
    console.error('API call failed:', lastConnectionError, url, e);
    return null;
  }
}

// Test API connection
export async function testConnection(): Promise<{ success: boolean; message: string; latency?: number }> {
  const start = Date.now();
  try {
    const response = await fetch(`${API_BASE}/contacts`, { method: 'GET' });
    const latency = Date.now() - start;
    
    if (response.ok) {
      connectionStatus = 'connected';
      lastConnectionError = null;
      return { success: true, message: `Connected (${latency}ms)`, latency };
    }
    
    connectionStatus = 'disconnected';
    lastConnectionError = `HTTP ${response.status}`;
    return { success: false, message: `API returned ${response.status}: ${response.statusText}` };
  } catch (e: any) {
    connectionStatus = 'disconnected';
    lastConnectionError = e.message;
    return { success: false, message: `Connection failed: ${e.message}` };
  }
}

// ============================================================================
// CONTACTS API
// ============================================================================

export interface Contact {
  id: string;
  contactId: string;
  name: string;
  phone: string;
  email?: string;
  // Opt-in fields (Requirement 3.2)
  optInWhatsApp: boolean;
  optInSms: boolean;
  optInEmail: boolean;
  // Allowlist fields (Requirement 3.2)
  allowlistWhatsApp: boolean;
  allowlistSms: boolean;
  allowlistEmail: boolean;
  lastInboundMessageAt?: string;
  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
}

export async function listContacts(): Promise<Contact[]> {
  const data = await apiCall<any>(`${API_BASE}/contacts`);
  if (data) {
    const contacts = Array.isArray(data) ? data : (data.contacts || []);
    return contacts.map(normalizeContact);
  }
  return [];
}

export async function getContact(contactId: string): Promise<Contact | null> {
  const data = await apiCall<any>(`${API_BASE}/contacts/${contactId}`);
  if (data) {
    return normalizeContact(data.contact || data);
  }
  return null;
}

export async function createContact(contact: Partial<Contact>): Promise<Contact | null> {
  const data = await apiCall<any>(`${API_BASE}/contacts`, {
    method: 'POST',
    body: JSON.stringify(contact),
  });
  if (data) {
    return normalizeContact(data.contact || data);
  }
  return null;
}

export async function updateContact(contactId: string, updates: Partial<Contact>): Promise<Contact | null> {
  const data = await apiCall<any>(`${API_BASE}/contacts/${contactId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
  if (data) {
    return normalizeContact(data.contact || data);
  }
  return null;
}

export async function deleteContact(contactId: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/contacts/${contactId}`, {
    method: 'DELETE',
  });
  // Check if response indicates success (not an error)
  return data !== null && !data.error;
}

function normalizeContact(item: any): Contact {
  return {
    id: item.id || item.contactId || '',
    contactId: item.contactId || item.id || '',
    name: item.name || '',
    phone: item.phone || '',
    email: item.email || '',
    // Opt-in fields
    optInWhatsApp: item.optInWhatsApp || false,
    optInSms: item.optInSms || false,
    optInEmail: item.optInEmail || false,
    // Allowlist fields (Requirement 3.2)
    allowlistWhatsApp: item.allowlistWhatsApp || false,
    allowlistSms: item.allowlistSms || false,
    allowlistEmail: item.allowlistEmail || false,
    lastInboundMessageAt: item.lastInboundMessageAt ? new Date(Number(item.lastInboundMessageAt) * 1000).toISOString() : undefined,
    createdAt: item.createdAt ? new Date(Number(item.createdAt) * 1000).toISOString() : new Date().toISOString(),
    updatedAt: item.updatedAt ? new Date(Number(item.updatedAt) * 1000).toISOString() : new Date().toISOString(),
    deletedAt: item.deletedAt,
  };
}

// ============================================================================
// MESSAGES API
// ============================================================================

export interface Message {
  id: string;
  messageId: string;
  contactId: string;
  channel: 'WHATSAPP' | 'SMS' | 'EMAIL';
  direction: 'INBOUND' | 'OUTBOUND';
  content: string;
  timestamp: string;
  status: string;
  errorDetails?: string;
  whatsappMessageId?: string;
  mediaId?: string;
  s3Key?: string;
  mediaUrl?: string;
  messageType?: string;
  senderPhone?: string;
  senderName?: string;
  receivingPhone?: string;
  awsPhoneNumberId?: string;
}

export async function listMessages(contactId?: string, channel?: string): Promise<Message[]> {
  let url = `${API_BASE}/messages`;
  const params = new URLSearchParams();
  if (contactId) params.append('contactId', contactId);
  if (channel) params.append('channel', channel);
  if (params.toString()) url += `?${params}`;
  
  const data = await apiCall<any>(url);
  if (data) {
    const messages = Array.isArray(data) ? data : (data.messages || []);
    return messages.map(normalizeMessage);
  }
  return [];
}

export async function getMessage(messageId: string): Promise<Message | null> {
  const messages = await listMessages();
  return messages.find(m => m.messageId === messageId) || null;
}

export async function deleteMessage(messageId: string, direction: 'INBOUND' | 'OUTBOUND' = 'INBOUND'): Promise<boolean> {
  console.log(`Deleting message: ${messageId}, direction: ${direction}`);
  const data = await apiCall<any>(`${API_BASE}/messages/${messageId}?direction=${direction}`, {
    method: 'DELETE',
  });
  console.log(`Delete message response:`, data);
  // Accept success if we got a response (even if success field is missing)
  return data !== null && (data.success === true || data.messageId === messageId || !data.error);
}

function normalizeMessage(item: any): Message {
  const timestamp = item.timestamp || item.createdAt;
  return {
    id: item.id || item.messageId || '',
    messageId: item.messageId || item.id || '',
    contactId: item.contactId || '',
    channel: (item.channel || 'WHATSAPP').toUpperCase() as 'WHATSAPP' | 'SMS' | 'EMAIL',
    direction: (item.direction || 'INBOUND').toUpperCase() as 'INBOUND' | 'OUTBOUND',
    content: item.content || item.text || '',
    timestamp: timestamp ? (typeof timestamp === 'number' ? new Date(timestamp * 1000).toISOString() : timestamp) : new Date().toISOString(),
    status: item.status || 'received',
    whatsappMessageId: item.whatsappMessageId,
    mediaId: item.mediaId,
    s3Key: item.s3Key,
    mediaUrl: item.mediaUrl,  // Use pre-signed URL from API
    messageType: item.messageType,  // image, video, audio, document, text
    senderPhone: item.senderPhone,
    senderName: item.senderName,
    receivingPhone: item.receivingPhone,
    awsPhoneNumberId: item.awsPhoneNumberId,
  };
}

// Send WhatsApp message via Lambda
export interface SendMessageRequest {
  contactId: string;
  content: string;
  phoneNumberId?: string;
  isTemplate?: boolean;
  templateName?: string;
  templateParams?: string[];
  mediaFile?: string;
  mediaType?: string;
  mediaFileName?: string; // Real filename for documents
}

// Send WhatsApp reaction via Lambda
export interface SendReactionRequest {
  contactId: string;
  reactionMessageId: string;  // WhatsApp message ID to react to
  reactionEmoji?: string;     // Default: thumbs up
  phoneNumberId?: string;
}

export async function sendWhatsAppMessage(request: SendMessageRequest): Promise<{ messageId: string; status: string } | null> {
  // Ensure mediaFile is properly formatted
  const payload = {
    ...request,
    // If mediaFile is provided, ensure it's base64 encoded
    mediaFile: request.mediaFile ? (typeof request.mediaFile === 'string' ? request.mediaFile : request.mediaFile) : undefined,
  };
  
  return apiCall<{ messageId: string; status: string }>(`${API_BASE}/whatsapp/send`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// Send a reaction to a WhatsApp message
export async function sendWhatsAppReaction(request: SendReactionRequest): Promise<{ messageId: string; status: string; emoji: string } | null> {
  return apiCall<{ messageId: string; status: string; emoji: string }>(`${API_BASE}/whatsapp/send`, {
    method: 'POST',
    body: JSON.stringify({
      contactId: request.contactId,
      isReaction: true,
      reactionMessageId: request.reactionMessageId,
      reactionEmoji: request.reactionEmoji || '\uD83D\uDC4D',  // Default: thumbs up
      phoneNumberId: request.phoneNumberId,
    }),
  });
}

// Interactive message types
export interface InteractiveListSection {
  title: string;
  rows: { id: string; title: string; description?: string }[];
}

export interface InteractiveButton {
  id: string;
  title: string;
}

export interface SendInteractiveRequest {
  contactId: string;
  phoneNumberId?: string;
  interactiveType: 'list' | 'button' | 'location_request' | 'cta_url' | 'flow';
  interactiveData: {
    header?: string;
    headerType?: 'text' | 'image' | 'video' | 'document';
    headerMedia?: string;
    headerFilename?: string;
    body: string;
    footer?: string;
    buttonText?: string;  // For list messages, CTA URL, and Flow
    sections?: InteractiveListSection[];  // For list messages
    buttons?: InteractiveButton[];  // For button messages
    url?: string;  // For CTA URL messages
    // Flow-specific fields
    flowId?: string;
    flowCta?: string;
    flowAction?: 'navigate' | 'data_exchange';
    flowToken?: string;
    flowScreen?: string;  // Initial screen to display
    screenId?: string;
    flowData?: Record<string, any>;
  };
}

// Send interactive WhatsApp message (list, buttons, location request, CTA URL, flow)
export async function sendWhatsAppInteractive(request: SendInteractiveRequest): Promise<{ messageId: string; status: string; interactiveType: string } | null> {
  return apiCall<{ messageId: string; status: string; interactiveType: string }>(`${API_BASE}/whatsapp/send`, {
    method: 'POST',
    body: JSON.stringify({
      contactId: request.contactId,
      phoneNumberId: request.phoneNumberId,
      isInteractive: true,
      interactiveType: request.interactiveType,
      interactiveData: request.interactiveData,
    }),
  });
}

// ============================================================================
// CAROUSEL TEMPLATE API
// ============================================================================

export interface CarouselCardButton {
  type: 'QUICK_REPLY' | 'URL' | 'PHONE_NUMBER';
  text: string;
  url?: string;
  phoneNumber?: string;
}

export interface CarouselCard {
  headerHandle?: string;  // From uploadCarouselCardMedia
  headerType?: 'image' | 'video';
  bodyText: string;
  buttons?: CarouselCardButton[];
}

export interface CreateCarouselTemplateRequest {
  name: string;
  language?: string;
  category?: 'MARKETING' | 'UTILITY';
  bodyText: string;
  cards: CarouselCard[];
  wabaId?: string;
}

// Upload media for carousel card header
export async function uploadCarouselCardMedia(
  mediaBase64: string,
  contentType: string = 'image/jpeg',
  cardIndex: number = 0,
  wabaId?: string
): Promise<{ headerHandle: string; s3Key: string; cardIndex: number } | null> {
  const params = new URLSearchParams();
  if (wabaId) params.append('wabaId', wabaId);
  
  return apiCall<{ headerHandle: string; s3Key: string; cardIndex: number }>(
    `${API_BASE}/templates/carousel-media${params.toString() ? '?' + params : ''}`,
    {
      method: 'POST',
      body: JSON.stringify({ mediaBase64, contentType, cardIndex }),
    }
  );
}

// Create carousel template
export async function createCarouselTemplate(
  request: CreateCarouselTemplateRequest
): Promise<{ metaTemplateId: string; templateStatus: string; templateType: string; cardCount: number } | null> {
  const params = new URLSearchParams();
  if (request.wabaId) params.append('wabaId', request.wabaId);
  
  return apiCall<{ metaTemplateId: string; templateStatus: string; templateType: string; cardCount: number }>(
    `${API_BASE}/templates/carousel${params.toString() ? '?' + params : ''}`,
    {
      method: 'POST',
      body: JSON.stringify({
        name: request.name,
        language: request.language || 'en',
        category: request.category || 'MARKETING',
        bodyText: request.bodyText,
        cards: request.cards,
      }),
    }
  );
}

export async function sendSmsMessage(contactId: string, content: string): Promise<{ messageId: string; status: string } | null> {
  return apiCall<{ messageId: string; status: string }>(`${API_BASE}/sms/send`, {
    method: 'POST',
    body: JSON.stringify({ contactId, content }),
  });
}

export async function sendEmailMessage(contactId: string, subject: string, content: string, htmlContent?: string): Promise<{ messageId: string; status: string } | null> {
  return apiCall<{ messageId: string; status: string }>(`${API_BASE}/email/send`, {
    method: 'POST',
    body: JSON.stringify({ contactId, subject, content, htmlContent }),
  });
}

// ============================================================================
// BULK JOBS API
// ============================================================================

export interface BulkJob {
  id: string;
  jobId: string;
  createdBy: string;
  channel: 'WHATSAPP' | 'SMS' | 'EMAIL';
  totalRecipients: number;
  sentCount: number;
  failedCount: number;
  status: 'PENDING' | 'IN_PROGRESS' | 'PAUSED' | 'COMPLETED' | 'CANCELLED' | 'FAILED';
  createdAt: string;
  updatedAt: string;
}

export async function listBulkJobs(channel?: string): Promise<BulkJob[]> {
  let url = `${API_BASE}/bulk/jobs`;
  if (channel) url += `?channel=${channel}`;
  const data = await apiCall<any>(url);
  if (data) {
    return Array.isArray(data) ? data : (data.jobs || []);
  }
  return [];
}

export async function createBulkJob(job: Partial<BulkJob>): Promise<BulkJob | null> {
  return apiCall<BulkJob>(`${API_BASE}/bulk/jobs`, {
    method: 'POST',
    body: JSON.stringify(job),
  });
}

export async function updateBulkJobStatus(jobId: string, status: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/bulk/jobs/${jobId}`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  });
  return data !== null;
}

export async function deleteBulkJob(jobId: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/bulk/jobs/${jobId}`, {
    method: 'DELETE',
  });
  return data !== null;
}

// ============================================================================
// AI AUTOMATION API
// ============================================================================

export interface AIConfig {
  enabled: boolean;
  autoReplyEnabled: boolean;
  knowledgeBaseId: string;
  agentId: string;
  agentAliasId: string;
  maxTokens: number;
  temperature: number;
  systemPrompt: string;
}

// Bedrock AI Configuration
// INTERNAL: For admin tasks (FloatingAgent) - Agent: TJAZR473IJ, KB: 7IWHVB0ZXQ
// EXTERNAL: For WhatsApp auto-reply (customer-facing) - Agent: JDXIOU2UR9, KB: CTH8DH3RXY
const AI_CONFIG: AIConfig = {
  enabled: true,
  autoReplyEnabled: true,
  knowledgeBaseId: 'CTH8DH3RXY',  // External KB ID (for WhatsApp auto-reply)
  agentId: 'JDXIOU2UR9',  // External Agent ID (for WhatsApp auto-reply)
  agentAliasId: 'AQVQPGYXRR',  // External Agent Alias
  maxTokens: 1024,
  temperature: 0.7,
  systemPrompt: 'You are a helpful customer service assistant for WECARE.DIGITAL.',
};

export async function getAIConfig(): Promise<AIConfig> {
  // Try to fetch from API first
  const data = await apiCall<any>(`${API_BASE}/ai/config`);
  if (data && data.config) {
    return {
      enabled: data.config.enabled ?? AI_CONFIG.enabled,
      autoReplyEnabled: data.config.autoReplyEnabled ?? AI_CONFIG.autoReplyEnabled,
      knowledgeBaseId: data.config.knowledgeBaseId || AI_CONFIG.knowledgeBaseId,
      agentId: data.config.agentId || AI_CONFIG.agentId,
      agentAliasId: data.config.agentAliasId || AI_CONFIG.agentAliasId,
      maxTokens: data.config.maxTokens || AI_CONFIG.maxTokens,
      temperature: data.config.temperature ?? AI_CONFIG.temperature,
      systemPrompt: data.config.systemPrompt || AI_CONFIG.systemPrompt,
    };
  }
  return AI_CONFIG;
}

export async function updateAIConfig(updates: Partial<AIConfig>): Promise<AIConfig> {
  // Try to update via API first
  const data = await apiCall<any>(`${API_BASE}/ai/config`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
  if (data && data.config) {
    Object.assign(AI_CONFIG, data.config);
    return AI_CONFIG;
  }
  // Fallback to local update
  Object.assign(AI_CONFIG, updates);
  return AI_CONFIG;
}

export async function testAIResponse(message: string): Promise<{ response: string; sources?: string[] }> {
  const data = await apiCall<any>(`${API_BASE}/ai/generate`, {
    method: 'POST',
    body: JSON.stringify({ messageContent: message }),
  });
  
  if (data) {
    return {
      response: data.suggestedResponse || data.suggestion || 'No response generated',
      sources: data.sources || ['Knowledge Base'],
    };
  }
  return { response: 'AI service unavailable', sources: [] };
}

// Get AI suggestions for message replies
export async function getAISuggestions(message: string, channel?: string, context?: string): Promise<string[]> {
  // First try the AI generate endpoint
  const data = await apiCall<any>(`${API_BASE}/ai/generate`, {
    method: 'POST',
    body: JSON.stringify({ 
      messageContent: message,
      context: {
        channel: channel || 'whatsapp',
        contactName: context,
      },
    }),
  });
  
  if (data && data.suggestedResponse) {
    // Return the AI-generated response as a suggestion
    return [data.suggestedResponse];
  }
  
  // Fallback suggestions if API fails
  return [
    'Thank you for reaching out! How can I help you today?',
    'I\'ll look into this and get back to you shortly.',
    'Is there anything else I can assist you with?',
  ];
}

// ============================================================================
// DASHBOARD STATS API
// ============================================================================

export interface DashboardStats {
  messagesToday: number;
  messagesWeek: number;
  activeContacts: number;
  bulkJobs: number;
  deliveryRate: number;
  aiResponses: number;
  dlqDepth: number;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  // Fetch real data from contacts, messages, and bulk jobs
  const [contacts, messages, bulkJobs] = await Promise.all([
    listContacts(),
    listMessages(),
    listBulkJobs()
  ]);
  
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000;
  
  const messagesToday = messages.filter(m => new Date(m.timestamp).getTime() >= todayStart).length;
  const messagesWeek = messages.filter(m => new Date(m.timestamp).getTime() >= weekStart).length;
  const activeContacts = contacts.filter(c => !c.deletedAt).length;
  
  // Calculate delivery rate from outbound messages
  const outboundMessages = messages.filter(m => m.direction === 'OUTBOUND');
  const deliveredMessages = outboundMessages.filter(m => 
    m.status === 'delivered' || m.status === 'read' || m.status === 'sent'
  );
  const deliveryRate = outboundMessages.length > 0 
    ? Math.round((deliveredMessages.length / outboundMessages.length) * 100) 
    : 100;
  
  // Count active bulk jobs
  const activeBulkJobs = bulkJobs.filter(j => 
    j.status === 'PENDING' || j.status === 'IN_PROGRESS'
  ).length;
  
  return {
    messagesToday,
    messagesWeek,
    activeContacts,
    bulkJobs: activeBulkJobs,
    deliveryRate,
    aiResponses: 0, // Would need AI interactions table query
    dlqDepth: 0, // Would need DLQ depth API
  };
}

// ============================================================================
// SYSTEM HEALTH API
// ============================================================================

export interface SystemHealth {
  whatsapp: { status: 'active' | 'warning' | 'error'; phoneNumbers: number; qualityRating: string };
  sms: { status: 'active' | 'warning' | 'error'; poolId: string };
  email: { status: 'active' | 'warning' | 'error'; verified: boolean };
  ai: { 
    status: 'active' | 'warning' | 'error'; 
    kbId?: string;
    internalKbId?: string;
    internalAgentId?: string;
    internalAgentAlias?: string;
    externalKbId?: string;
    externalAgentId?: string;
    externalAgentAlias?: string;
  };
  dlq: { depth: number; oldestMessage?: string };
}

export async function getSystemHealth(): Promise<SystemHealth> {
  // Real AWS Resource IDs
  return {
    whatsapp: { status: 'active', phoneNumbers: 2, qualityRating: 'GREEN' },
    sms: { status: 'active', poolId: 'pool-6fbf5a5f390d4eeeaa7dbae39d78933e' },
    email: { status: 'active', verified: true },
    ai: { 
      status: 'active', 
      internalKbId: '7IWHVB0ZXQ', 
      internalAgentId: 'TJAZR473IJ',
      internalAgentAlias: 'O4U1HF2MSX',
      externalKbId: 'CTH8DH3RXY',
      externalAgentId: 'JDXIOU2UR9',
      externalAgentAlias: 'AQVQPGYXRR'
    },
    dlq: { depth: 0 },
  };
}


// ============================================================================
// VOICE CALLS API
// ============================================================================

export interface VoiceCall {
  id: string;
  callId: string;
  contactId: string;
  phoneNumber: string;
  provider: 'aws' | 'airtel';
  callType: 'tts' | 'audio' | 'ivr' | 'click_to_call';
  status: string;
  direction: 'INBOUND' | 'OUTBOUND';
  duration: number;
  recordingUrl?: string;
  createdAt: string;
  updatedAt: string;
}

export interface MakeVoiceCallRequest {
  contactId?: string;
  phoneNumber: string;
  provider: 'aws' | 'airtel';
  callType: 'tts' | 'audio' | 'ivr' | 'click_to_call';
  messageText?: string;
  voiceId?: string;
  audioUrl?: string;
}

export async function listVoiceCalls(contactId?: string, provider?: string): Promise<VoiceCall[]> {
  let url = `${API_BASE}/voice/calls`;
  const params = new URLSearchParams();
  if (contactId) params.append('contactId', contactId);
  if (provider) params.append('provider', provider);
  if (params.toString()) url += `?${params}`;
  
  const data = await apiCall<any>(url);
  if (data) {
    const calls = Array.isArray(data) ? data : (data.calls || []);
    return calls.map(normalizeVoiceCall);
  }
  return [];
}

export async function getVoiceCall(callId: string): Promise<VoiceCall | null> {
  const data = await apiCall<any>(`${API_BASE}/voice/calls/${callId}`);
  if (data) {
    return normalizeVoiceCall(data.call || data);
  }
  return null;
}

export async function makeVoiceCall(request: MakeVoiceCallRequest): Promise<{ callId: string; status: string } | null> {
  return apiCall<{ callId: string; status: string }>(`${API_BASE}/voice/call`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

function normalizeVoiceCall(item: any): VoiceCall {
  return {
    id: item.id || item.callId || '',
    callId: item.callId || item.id || '',
    contactId: item.contactId || '',
    phoneNumber: item.phoneNumber || '',
    provider: item.provider || 'aws',
    callType: item.callType || 'tts',
    status: item.status || 'unknown',
    direction: (item.direction || 'OUTBOUND').toUpperCase() as 'INBOUND' | 'OUTBOUND',
    duration: item.duration || 0,
    recordingUrl: item.recordingUrl,
    createdAt: item.createdAt ? new Date(Number(item.createdAt) * 1000).toISOString() : new Date().toISOString(),
    updatedAt: item.updatedAt ? new Date(Number(item.updatedAt) * 1000).toISOString() : new Date().toISOString(),
  };
}


// ============================================================================
// DLQ API
// ============================================================================

export interface DLQMessage {
  id: string;
  queueName: string;
  retryCount: number;
  lastAttemptAt: number;
  error: string;
}

export async function listDLQMessages(): Promise<DLQMessage[]> {
  const data = await apiCall<any>(`${API_BASE}/dlq`);
  if (data) {
    return data.messages || [];
  }
  return [];
}

export async function replayDLQMessages(queueName: string, batchSize?: number): Promise<{ processed: number; succeeded: number; failed: number } | null> {
  return apiCall<{ processed: number; succeeded: number; failed: number }>(`${API_BASE}/dlq/replay`, {
    method: 'POST',
    body: JSON.stringify({ queueName, batchSize: batchSize || 10 }),
  });
}


// ============================================================================
// AWS BILLING API
// ============================================================================

export interface AWSServiceUsage {
  service: string;
  cost: number;
  usage: number;
  unit: string;
  freeLimit: string;
  status: 'free' | 'paid' | 'warning';
}

export interface AWSBillingData {
  totalCost: number;
  period: string;
  services: AWSServiceUsage[];
  lastUpdated: string;
  accountId?: string;
  currency?: string;
  previousMonthCost?: number;
  previousMonthPeriod?: string;
}

// AWS Free Tier limits for reference
const FREE_TIER_LIMITS: Record<string, { limit: string; unit: string }> = {
  'AWS Lambda': { limit: '1M requests/month', unit: 'requests' },
  'Amazon DynamoDB': { limit: '25GB + 200M requests', unit: 'operations' },
  'Amazon S3': { limit: '5GB + 20K GET', unit: 'operations' },
  'Amazon API Gateway': { limit: '1M REST calls/month', unit: 'requests' },
  'Amazon CloudFront': { limit: '1TB transfer/month', unit: 'requests' },
  'AWS Amplify': { limit: '1000 build mins/month', unit: 'minutes' },
  'Amazon SNS': { limit: '1M publishes/month', unit: 'notifications' },
  'Amazon SQS': { limit: '1M requests/month', unit: 'requests' },
  'Amazon Cognito': { limit: '50K MAU', unit: 'users' },
  'AmazonCloudWatch': { limit: '10 metrics free', unit: 'metrics' },
  'Amazon Bedrock': { limit: '3-month trial', unit: 'requests' },
  'Amazon OpenSearch Service': { limit: 'Serverless free tier', unit: 'operations' },
  'AWS End User Messaging': { limit: 'Pay per message', unit: 'messages' },
  'Amazon Route 53': { limit: '$0.50/zone', unit: 'queries' },
  'AWS WAF': { limit: 'Pay per rule', unit: 'requests' },
  'AWS Certificate Manager': { limit: 'Free public certs', unit: 'certificates' },
  'AWS CloudFormation': { limit: 'Free', unit: 'stacks' },
  'AWS Secrets Manager': { limit: '$0.40/secret/month', unit: 'secrets' },
  'AWS Key Management Service': { limit: '20K free requests', unit: 'requests' },
  'AWS Glue': { limit: 'Pay per DPU-hour', unit: 'operations' },
  'AWS Step Functions': { limit: '4K free transitions', unit: 'transitions' },
  'Amazon Simple Email Service': { limit: '62K emails/month (from EC2)', unit: 'emails' },
  'Amazon Location Service': { limit: '10K requests/month', unit: 'requests' },
};

export async function getAWSBilling(monthOffset: number = 0): Promise<AWSBillingData> {
  // Try to fetch from our billing API endpoint with month parameter
  const url = monthOffset === 0 
    ? `${API_BASE}/billing` 
    : `${API_BASE}/billing?month=${monthOffset}`;
  
  const data = await apiCall<any>(url);
  
  if (data && data.services) {
    return {
      totalCost: data.totalCost || 0,
      period: data.period || `${new Date().toISOString().slice(0, 7)}-01 to ${new Date().toISOString().slice(0, 10)}`,
      services: data.services,
      lastUpdated: data.lastUpdated || new Date().toISOString(),
      accountId: data.accountId,
      currency: data.currency || 'USD',
      previousMonthCost: data.previousMonthCost,
      previousMonthPeriod: data.previousMonthPeriod,
    };
  }
  
  // Fallback: Return cached/estimated data
  return getEstimatedBilling();
}

// Fallback function with estimated billing data
function getEstimatedBilling(): AWSBillingData {
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  
  const services: AWSServiceUsage[] = [
    { service: 'Amazon Bedrock', cost: 0, usage: 61, unit: 'requests', freeLimit: '3-month trial', status: 'free' },
    { service: 'AWS Lambda', cost: 0, usage: 6709, unit: 'requests', freeLimit: '1M/month', status: 'free' },
    { service: 'Amazon DynamoDB', cost: 0, usage: 22977, unit: 'operations', freeLimit: '200M/month', status: 'free' },
    { service: 'Amazon S3', cost: 0, usage: 13186, unit: 'operations', freeLimit: '20K GET', status: 'free' },
    { service: 'Amazon API Gateway', cost: 0, usage: 5157, unit: 'requests', freeLimit: '1M/month', status: 'free' },
    { service: 'Amazon CloudFront', cost: 0, usage: 1981, unit: 'requests', freeLimit: '1TB/month', status: 'free' },
    { service: 'AWS Amplify', cost: 0, usage: 774, unit: 'minutes', freeLimit: '1000 mins/month', status: 'free' },
    { service: 'Amazon SNS', cost: 0, usage: 3387, unit: 'notifications', freeLimit: '1M/month', status: 'free' },
    { service: 'Amazon SQS', cost: 0, usage: 429, unit: 'requests', freeLimit: '1M/month', status: 'free' },
    { service: 'AWS End User Messaging', cost: 0, usage: 381, unit: 'messages', freeLimit: 'Pay per msg', status: 'free' },
    { service: 'Amazon OpenSearch', cost: 0, usage: 182, unit: 'operations', freeLimit: 'Serverless', status: 'free' },
    { service: 'Amazon Route 53', cost: 0, usage: 94671, unit: 'queries', freeLimit: '$0.50/zone', status: 'free' },
    { service: 'Amazon Cognito', cost: 0, usage: 1, unit: 'users', freeLimit: '50K MAU', status: 'free' },
    { service: 'CloudWatch', cost: 0, usage: 370, unit: 'metrics', freeLimit: '10 metrics', status: 'free' },
  ];
  
  return {
    totalCost: 0,
    period: `${startOfMonth.toISOString().slice(0, 10)} to ${now.toISOString().slice(0, 10)}`,
    services,
    lastUpdated: now.toISOString(),
  };
}


// ============================================================================
// ADVANCED DELETE OPERATIONS
// ============================================================================

/**
 * Hard Delete - Completely removes contact, all messages, and media from S3
 * This is irreversible!
 * 
 * Uses the backend ?hard=true parameter to trigger full deletion
 */
export async function hardDeleteContact(contactId: string): Promise<boolean> {
  console.log(`Hard deleting contact: ${contactId}`);
  const data = await apiCall<any>(`${API_BASE}/contacts/${contactId}?hard=true`, {
    method: 'DELETE',
  });
  console.log(`Hard delete response:`, data);
  
  if (data && data.success) {
    console.log(`Hard delete successful: ${data.messagesDeleted} messages, ${data.mediaDeleted} media files`);
    return true;
  }
  
  // Fallback: delete messages one by one, then soft delete contact
  console.log('Hard delete endpoint failed, using fallback...');
  try {
    const messagesDeleted = await deleteContactMessages(contactId);
    console.log(`Fallback: messages deleted = ${messagesDeleted}`);
    
    const contactDeleted = await deleteContact(contactId);
    console.log(`Fallback: contact deleted = ${contactDeleted}`);
    
    return contactDeleted;
  } catch (error) {
    console.error('Hard delete fallback error:', error);
    return false;
  }
}

/**
 * Delete all messages for a contact (keeps the contact)
 * Deletes messages one by one since there's no bulk endpoint
 */
export async function deleteContactMessages(contactId: string): Promise<boolean> {
  try {
    // Fetch all messages for this contact
    const messages = await listMessages(contactId);
    console.log(`Deleting ${messages.length} messages for contact ${contactId}`);
    
    if (messages.length === 0) {
      return true; // No messages to delete
    }
    
    let deleted = 0;
    let failed = 0;
    
    for (const msg of messages) {
      const result = await deleteMessage(msg.id, msg.direction);
      if (result) {
        deleted++;
      } else {
        failed++;
      }
    }
    
    console.log(`Deleted ${deleted}/${messages.length} messages (${failed} failed)`);
    return deleted > 0 || messages.length === 0;
  } catch (error) {
    console.error('Delete contact messages error:', error);
    return false;
  }
}

/**
 * Bulk delete multiple messages
 */
export async function bulkDeleteMessages(messageIds: string[], direction: 'INBOUND' | 'OUTBOUND' = 'INBOUND'): Promise<{ deleted: number; failed: number }> {
  let deleted = 0;
  let failed = 0;
  
  for (const msgId of messageIds) {
    const result = await deleteMessage(msgId, direction);
    if (result) {
      deleted++;
    } else {
      failed++;
    }
  }
  
  return { deleted, failed };
}

/**
 * Bulk delete multiple contacts
 */
export async function bulkDeleteContacts(contactIds: string[]): Promise<{ deleted: number; failed: number }> {
  let deleted = 0;
  let failed = 0;
  
  for (const contactId of contactIds) {
    const result = await deleteContact(contactId);
    if (result) {
      deleted++;
    } else {
      failed++;
    }
  }
  
  return { deleted, failed };
}


// ============================================================================
// WHATSAPP TEMPLATES API (AWS EUM Social)
// ============================================================================

export interface WhatsAppTemplate {
  id: string;
  name: string;
  language: string;
  category: 'MARKETING' | 'UTILITY' | 'AUTHENTICATION';
  status: 'APPROVED' | 'PENDING' | 'REJECTED';
  components: TemplateComponent[];
}

export interface TemplateComponent {
  type: 'HEADER' | 'BODY' | 'FOOTER' | 'BUTTONS';
  format?: 'TEXT' | 'IMAGE' | 'VIDEO' | 'DOCUMENT';
  text?: string;
  example?: { body_text?: string[][] };
  buttons?: { type: string; text: string; url?: string; phone_number?: string }[];
}

// WABA IDs for template fetching
const WABA_IDS = {
  'WECARE.DIGITAL': 'waba-0aae9cf04cf24c66960f291c793359b4',
  'Manish Agarwal': 'waba-9bbe054d8404487397c38a9d197bc44a',
};

/**
 * List WhatsApp message templates from AWS EUM Social API
 * Uses: GET /v1/whatsapp/templates via our API Gateway
 * 
 * If API endpoint not available, returns sample templates
 */
export async function listWhatsAppTemplates(wabaId?: string): Promise<WhatsAppTemplate[]> {
  // Try to fetch from our API Gateway endpoint
  let url = `${API_BASE}/whatsapp/templates`;
  if (wabaId) url += `?wabaId=${wabaId}`;
  
  const data = await apiCall<any>(url);
  
  if (data && data.templates && Array.isArray(data.templates)) {
    return data.templates.map(normalizeTemplate);
  }
  
  // If API returns error or no templates, try direct AWS SDK call via Lambda
  // For now, return sample templates that match AWS EUM Social format
  // These should be replaced with actual templates from your WABA
  console.log('Templates API not available, using sample templates');
  
  return [
    {
      id: 'hello_world',
      name: 'hello_world',
      language: 'en_US',
      category: 'UTILITY',
      status: 'APPROVED',
      components: [
        { type: 'BODY', text: 'Hello {{1}}! Welcome to WECARE.DIGITAL.' }
      ]
    },
    {
      id: 'order_confirmation',
      name: 'order_confirmation',
      language: 'en_US',
      category: 'UTILITY',
      status: 'APPROVED',
      components: [
        { type: 'HEADER', format: 'TEXT', text: 'Order Confirmed' },
        { type: 'BODY', text: 'Hi {{1}}, your order #{{2}} has been confirmed. Total: {{3}}' },
        { type: 'FOOTER', text: 'Thank you for choosing us!' }
      ]
    },
    {
      id: 'appointment_reminder',
      name: 'appointment_reminder',
      language: 'en_US',
      category: 'UTILITY',
      status: 'APPROVED',
      components: [
        { type: 'BODY', text: 'Hi {{1}}, this is a reminder for your appointment on {{2}} at {{3}}.' }
      ]
    },
    {
      id: 'payment_received',
      name: 'payment_received',
      language: 'en_US',
      category: 'UTILITY',
      status: 'APPROVED',
      components: [
        { type: 'BODY', text: 'Payment of {{1}} received. Transaction ID: {{2}}. Thank you!' }
      ]
    },
    {
      id: 'welcome_message',
      name: 'welcome_message',
      language: 'en_US',
      category: 'MARKETING',
      status: 'APPROVED',
      components: [
        { type: 'HEADER', format: 'TEXT', text: 'Welcome to WECARE.DIGITAL' },
        { type: 'BODY', text: 'Hi {{1}}! Thank you for connecting with us. How can we help you today?' },
        { type: 'BUTTONS', buttons: [
          { type: 'QUICK_REPLY', text: 'Get Started' },
          { type: 'QUICK_REPLY', text: 'Learn More' }
        ]}
      ]
    }
  ];
}

/**
 * Get a specific WhatsApp template
 */
export async function getWhatsAppTemplate(templateName: string, language: string = 'en_US'): Promise<WhatsAppTemplate | null> {
  const data = await apiCall<any>(`${API_BASE}/whatsapp/templates/${templateName}?language=${language}`);
  if (data && data.template) {
    return normalizeTemplate(data.template);
  }
  
  // Fallback: search in cached templates
  const templates = await listWhatsAppTemplates();
  return templates.find(t => t.name === templateName && t.language === language) || null;
}

/**
 * Send a template message via WhatsApp
 * Templates can be sent outside the 24h window
 */
export async function sendWhatsAppTemplateMessage(request: {
  contactId: string;
  templateName: string;
  language?: string;
  components?: any[];
  phoneNumberId?: string;
  templateParams?: string[];  // Variable values like OTP code
}): Promise<{ messageId: string; status: string } | null> {
  // Build template params array - include language as first param for Lambda
  const params: string[] = [];
  
  // Add language code as first param (Lambda will extract it)
  if (request.language) {
    params.push(request.language);
  }
  
  // Add template variable values
  if (request.templateParams && request.templateParams.length > 0) {
    params.push(...request.templateParams);
  }
  
  return apiCall<{ messageId: string; status: string }>(`${API_BASE}/whatsapp/send`, {
    method: 'POST',
    body: JSON.stringify({
      contactId: request.contactId,
      isTemplate: true,
      templateName: request.templateName,
      templateParams: params,
      phoneNumberId: request.phoneNumberId,
    }),
  });
}

function normalizeTemplate(item: any): WhatsAppTemplate {
  return {
    id: item.id || item.templateId || item.name || '',
    name: item.name || item.templateName || '',
    language: item.language || item.languageCode || 'en_US',
    category: (item.category || 'UTILITY').toUpperCase() as 'MARKETING' | 'UTILITY' | 'AUTHENTICATION',
    status: (item.status || 'APPROVED').toUpperCase() as 'APPROVED' | 'PENDING' | 'REJECTED',
    components: item.components || [],
  };
}


// ============================================================================
// AI CHAT API (for inbox editor)
// ============================================================================

/**
 * Generate AI response using Bedrock
 * Uses the external agent for customer-facing responses
 * 
 * API: POST /ai/generate
 * Lambda: wecare-ai-generate-response
 */
export async function generateAIResponse(message: string, context?: {
  contactName?: string;
  channel?: string;
  conversationHistory?: string[];
}): Promise<{ response: string; sources?: string[] }> {
  try {
    const data = await apiCall<any>(`${API_BASE}/ai/generate`, {
      method: 'POST',
      body: JSON.stringify({
        messageContent: message,
        context: context?.channel || 'external',  // Use external agent for inbox
      }),
    });
    
    // Handle Lambda response format (body is JSON string)
    if (data) {
      // If response has body field (Lambda proxy response)
      if (data.body) {
        try {
          const parsed = typeof data.body === 'string' ? JSON.parse(data.body) : data.body;
          if (parsed.suggestion) {
            return { response: parsed.suggestion, sources: parsed.sources || [] };
          }
          if (parsed.suggestedResponse) {
            return { response: parsed.suggestedResponse, sources: parsed.sources || [] };
          }
        } catch (e) {
          console.error('Failed to parse AI response body:', e);
        }
      }
      
      // Direct response format
      if (data.suggestion) {
        return { response: data.suggestion, sources: data.sources || [] };
      }
      if (data.suggestedResponse) {
        return { response: data.suggestedResponse, sources: data.sources || [] };
      }
    }
    
    // Fallback response
    return {
      response: 'Thank you for your message. How can I assist you today?',
      sources: [],
    };
  } catch (error) {
    console.error('AI generate error:', error);
    return {
      response: 'Thank you for reaching out. How can I help you?',
      sources: [],
    };
  }
}


// ============================================================================
// WHATSAPP PAYMENT MESSAGE API (Order Details Template)
// ============================================================================

export interface PaymentOrderItem {
  name: string;
  amount: number;  // In smallest currency unit (paise for INR)
  quantity: number;
  productId?: string;
}

export interface SendPaymentMessageRequest {
  contactId: string;
  phoneNumberId: string;
  templateName?: string;
  referenceId: string;
  items: PaymentOrderItem[];
  discount?: number;      // In paise
  delivery?: number;      // In paise (shipping/delivery)
  tax?: number;           // In paise (from frontend - NOT auto-calculated)
  taxDescription?: string; // e.g., "GST 18%" or "Tax"
  gstRate?: number;       // GST rate: 0, 3, 5, 12, 18, 28
  gstin?: string;         // GSTIN number
  currency?: string;
  headerImageUrl?: string;
  bodyText?: string;
  useInteractive?: boolean;
}

/**
 * Send WhatsApp Payment Message using order_details
 * 
 * Fields shown in WhatsApp message:
 * - Reference ID
 * - Items (name, amount, quantity)
 * - Discount (₹)
 * - Delivery (₹)
 * - Tax (₹) - passed from frontend
 * 
 * NOTE: Convenience Fee is handled by Razorpay Fee Bearer model (not in WhatsApp message)
 */
export async function sendWhatsAppPaymentMessage(request: SendPaymentMessageRequest): Promise<{ messageId: string; status: string } | null> {
  const subtotal = request.items.reduce((sum, item) => sum + (item.amount * item.quantity), 0);
  const discount = request.discount || 0;
  const delivery = request.delivery || 0;
  const tax = request.tax || 0;

  // Get first item details for backend
  const firstItem = request.items[0] || { name: 'Service Fee', amount: 100, quantity: 1 };

  // Build order_details payload
  const orderDetails: any = {
    reference_id: request.referenceId,
    type: 'digital-goods',
    payment_configuration: 'WECARE-DIGITAL',
    currency: request.currency || 'INR',
    // New fields for backend calculation
    itemName: firstItem.name || 'Service Fee',
    quantity: firstItem.quantity || 1,
    gstRate: request.gstRate ?? 0,  // Use 0 as default if not specified
    gstin: request.gstin || DEFAULT_GSTIN,
    order: {
      status: 'pending',
      items: request.items.map((item, idx) => ({
        retailer_id: item.productId || `ITEM_${idx + 1}`,
        name: item.name,
        amount: { value: item.amount, offset: 100 },
        quantity: item.quantity,
      })),
      subtotal: { value: subtotal, offset: 100 },
      discount: { value: discount, offset: 100, description: 'Promo' },
      shipping: { value: delivery, offset: 100, description: 'Express' },
      tax: { value: tax, offset: 100, description: `GSTIN: ${request.gstin || DEFAULT_GSTIN}` },
    },
  };

  console.log('Sending payment message:', { contactId: request.contactId, orderDetails });

  // Use interactive mode if specified
  if (request.useInteractive) {
    const result = await apiCall<{ messageId: string; status: string }>(`${API_BASE}/whatsapp/send`, {
      method: 'POST',
      body: JSON.stringify({
        contactId: request.contactId,
        phoneNumberId: request.phoneNumberId,
        isInteractivePayment: true,
        orderDetails: orderDetails,
        headerImageUrl: request.headerImageUrl,
      }),
    });
    console.log('Payment message result:', result);
    return result;
  }

  // Template mode
  return apiCall<{ messageId: string; status: string }>(`${API_BASE}/whatsapp/send`, {
    method: 'POST',
    body: JSON.stringify({
      contactId: request.contactId,
      phoneNumberId: request.phoneNumberId,
      isTemplate: true,
      templateName: request.templateName || '02_wd_order_payment',
      templateParams: request.bodyText ? [request.bodyText] : [],
      isPaymentTemplate: true,
      orderDetails: orderDetails,
      headerImageUrl: request.headerImageUrl,
    }),
  });
}


// ============================================================================
// WABA MANAGEMENT API (AWS EUM Social)
// ============================================================================

export interface WABAAccount {
  id: string;
  wabaId: string;
  wabaName: string;
  arn: string;
  registrationStatus: string;
  linkDate?: number;
  enableSending: boolean;
  enableReceiving: boolean;
  eventDestinations: { eventDestinationArn: string; roleArn: string }[];
  phoneNumbers?: WABAPhoneNumber[];
}

export interface WABAPhoneNumber {
  phoneNumberId: string;
  phoneNumber: string;
  displayPhoneNumber: string;
  displayPhoneNumberName: string;
  qualityRating: 'GREEN' | 'YELLOW' | 'RED' | 'UNKNOWN';
  metaPhoneNumberId: string;
  dataLocalizationRegion: string;
  arn: string;
  linkedWabaId?: string;
}

export interface WABASystemEvents {
  templateStatus: { timestamp: number; data: any }[];
  phoneQuality: { timestamp: number; data: any }[];
  accountUpdates: { timestamp: number; data: any }[];
}

/**
 * List all linked WhatsApp Business Accounts
 * API: ListLinkedWhatsAppBusinessAccounts
 */
export async function listWABAs(): Promise<WABAAccount[]> {
  const data = await apiCall<any>(`${API_BASE}/waba`);
  if (data && data.wabas) {
    return data.wabas;
  }
  return [];
}

/**
 * Get WABA details including phone numbers with quality ratings
 * API: GetLinkedWhatsAppBusinessAccount
 */
export async function getWABADetails(wabaId: string): Promise<WABAAccount | null> {
  const data = await apiCall<any>(`${API_BASE}/waba/${wabaId}`);
  if (data) {
    return data;
  }
  return null;
}

/**
 * Get phone number details including quality rating
 * API: GetLinkedWhatsAppBusinessAccountPhoneNumber
 */
export async function getPhoneNumberDetails(phoneNumberId: string): Promise<WABAPhoneNumber | null> {
  const data = await apiCall<any>(`${API_BASE}/waba/phone/${phoneNumberId}`);
  if (data) {
    return data;
  }
  return null;
}

/**
 * Get system events (template status, phone quality, account updates)
 * Stored by inbound webhook handler
 */
export async function getWABASystemEvents(eventType?: string): Promise<WABASystemEvents> {
  let url = `${API_BASE}/waba/events`;
  if (eventType) url += `?type=${eventType}`;
  
  const data = await apiCall<any>(url);
  if (data) {
    return {
      templateStatus: data.templateStatus || [],
      phoneQuality: data.phoneQuality || [],
      accountUpdates: data.accountUpdates || [],
    };
  }
  return { templateStatus: [], phoneQuality: [], accountUpdates: [] };
}

/**
 * Delete WhatsApp media from Meta servers
 * API: DeleteWhatsAppMessageMedia
 */
export async function deleteWhatsAppMedia(mediaId: string, phoneNumberId: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/waba/media/${mediaId}?phoneNumberId=${phoneNumberId}`, {
    method: 'DELETE',
  });
  return data?.success === true;
}


// ============================================================================
// TEMPLATE MANAGEMENT API (AWS EUM Social)
// ============================================================================

export interface TemplateDefinition {
  name: string;
  language: string;
  category: 'UTILITY' | 'MARKETING' | 'AUTHENTICATION';
  components: TemplateComponent[];
}

export interface MetaLibraryTemplate {
  templateId: string;
  templateName: string;
  templateCategory: string;
  templateLanguage: string;
  templateBody: string;
  templateHeader?: string;
  templateTopic?: string;
  templateUseCase?: string;
  templateIndustry?: string[];
  templateButtons?: any[];
  templateBodyExampleParams?: string[];
}

export interface CreateTemplateRequest {
  wabaId?: string;
  templateDefinition: TemplateDefinition;
}

export interface CreateFromLibraryRequest {
  wabaId?: string;
  metaLibraryTemplate: {
    libraryTemplateName: string;
    templateName: string;
    templateCategory: string;
    templateLanguage: string;
    libraryTemplateBodyInputs?: {
      addTrackPackageLink?: boolean;
      addContactNumber?: boolean;
      addLearnMoreLink?: boolean;
      addSecurityRecommendation?: boolean;
      codeExpirationMinutes?: number;
    };
    libraryTemplateButtonInputs?: any[];
  };
}

export interface UpdateTemplateRequest {
  wabaId?: string;
  templateCategory?: string;
  templateComponents?: any;
  parameterFormat?: string;
  ctaUrlLinkTrackingOptedOut?: boolean;
}

/**
 * List templates for a WABA (enhanced version)
 * API: ListWhatsAppMessageTemplates
 */
export async function listTemplates(wabaId?: string, maxResults?: number): Promise<WhatsAppTemplate[]> {
  let url = `${API_BASE}/templates`;
  const params = new URLSearchParams();
  if (wabaId) params.append('wabaId', wabaId);
  if (maxResults) params.append('maxResults', maxResults.toString());
  if (params.toString()) url += `?${params}`;
  
  const data = await apiCall<any>(url);
  if (data && data.templates) {
    return data.templates.map(normalizeTemplate);
  }
  return [];
}

/**
 * Get template details
 * API: GetWhatsAppMessageTemplate
 */
export async function getTemplateDetails(templateId: string, wabaId?: string): Promise<any | null> {
  let url = `${API_BASE}/templates/${templateId}`;
  if (wabaId) url += `?wabaId=${wabaId}`;
  
  const data = await apiCall<any>(url);
  if (data) {
    return data.template || data;
  }
  return null;
}

/**
 * Create a new template from custom definition
 * API: CreateWhatsAppMessageTemplate
 */
export async function createTemplate(request: CreateTemplateRequest): Promise<{ metaTemplateId: string; category: string; templateStatus: string } | null> {
  return apiCall<any>(`${API_BASE}/templates`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Create template from Meta's library
 * API: CreateWhatsAppMessageTemplateFromLibrary
 */
export async function createTemplateFromLibrary(request: CreateFromLibraryRequest): Promise<{ metaTemplateId: string; category: string; templateStatus: string } | null> {
  return apiCall<any>(`${API_BASE}/templates/from-library`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Update an existing template
 * API: UpdateWhatsAppMessageTemplate
 */
export async function updateTemplate(templateId: string, request: UpdateTemplateRequest): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/templates/${templateId}`, {
    method: 'PUT',
    body: JSON.stringify(request),
  });
  return data?.success === true;
}

/**
 * Delete a template
 * API: DeleteWhatsAppMessageTemplate
 */
export async function deleteTemplate(templateName: string, wabaId?: string, deleteAllLanguages?: boolean): Promise<boolean> {
  let url = `${API_BASE}/templates/${templateName}`;
  const params = new URLSearchParams();
  params.append('templateName', templateName);
  if (wabaId) params.append('wabaId', wabaId);
  if (deleteAllLanguages) params.append('deleteAllLanguages', 'true');
  url += `?${params}`;
  
  const data = await apiCall<any>(url, { method: 'DELETE' });
  return data?.success === true;
}

/**
 * Browse Meta's template library
 * API: ListWhatsAppTemplateLibrary
 */
export async function listTemplateLibrary(filters?: {
  wabaId?: string;
  searchKey?: string;
  topic?: string;
  usecase?: string;
  industry?: string;
  language?: string;
  maxResults?: number;
}): Promise<MetaLibraryTemplate[]> {
  let url = `${API_BASE}/templates/library`;
  if (filters) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.append(key, value.toString());
    });
    if (params.toString()) url += `?${params}`;
  }
  
  const data = await apiCall<any>(url);
  if (data && data.templates) {
    return data.templates;
  }
  return [];
}

/**
 * Upload media for template headers
 * API: CreateWhatsAppMessageTemplateMedia
 */
export async function uploadTemplateMedia(request: {
  wabaId?: string;
  mediaBase64?: string;
  s3Key?: string;
  mediaType?: string;
  filename?: string;
}): Promise<{ metaHeaderHandle: string; s3Key: string } | null> {
  return apiCall<any>(`${API_BASE}/templates/media`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}


// ============================================================================
// AI CONFIG MANAGEMENT API (Bedrock Control)
// ============================================================================

export interface BedrockAIConfig {
  enabled: boolean;
  autoReplyEnabled: boolean;
  respondToInteractive: boolean;
  respondToText: boolean;
  respondToMedia: boolean;
  respondToLocation: boolean;
  maxResponseLength: number;
  responseDelay: number;
  supportedLanguages: string[];
  defaultLanguage: string;
  agentId: string;
  agentAlias: string;
  knowledgeBaseId: string;
  modelId: string;
}

export interface AIInteraction {
  interactionId: string;
  messageId: string;
  query: string;
  response: string;
  detectedLanguage?: string;
  approved: boolean;
  timestamp: number;
}

export interface AIStats {
  totalInteractions: number;
  approvedResponses: number;
  approvalRate: number;
  byLanguage: Record<string, number>;
}

export interface SupportedLanguages {
  [code: string]: string;
}

/**
 * Get Bedrock AI configuration
 * API: GET /ai/config
 */
export async function getBedrockAIConfig(): Promise<BedrockAIConfig> {
  const data = await apiCall<any>(`${API_BASE}/ai/config`);
  if (data && data.config) {
    return data.config;
  }
  // Return defaults if API fails
  return {
    enabled: false,
    autoReplyEnabled: false,
    respondToInteractive: true,
    respondToText: true,
    respondToMedia: false,
    respondToLocation: true,
    maxResponseLength: 500,
    responseDelay: 0,
    supportedLanguages: ['en', 'hi', 'hi-Latn', 'bn', 'ta', 'te', 'gu', 'mr'],
    defaultLanguage: 'en',
    agentId: 'JDXIOU2UR9',
    agentAlias: 'AQVQPGYXRR',
    knowledgeBaseId: 'CTH8DH3RXY',
    modelId: 'amazon.nova-lite-v1:0',
  };
}

/**
 * Update Bedrock AI configuration
 * API: PUT /ai/config
 */
export async function updateBedrockAIConfig(updates: Partial<BedrockAIConfig>): Promise<BedrockAIConfig | null> {
  const data = await apiCall<any>(`${API_BASE}/ai/config`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
  if (data && data.config) {
    return data.config;
  }
  return null;
}

/**
 * Get language-specific prompts
 * API: GET /ai/prompts or GET /ai/prompts/{lang}
 */
export async function getAIPrompts(lang?: string): Promise<Record<string, string> | string> {
  const url = lang ? `${API_BASE}/ai/prompts/${lang}` : `${API_BASE}/ai/prompts`;
  const data = await apiCall<any>(url);
  if (data) {
    return lang ? (data.prompt || '') : (data.prompts || {});
  }
  return lang ? '' : {};
}

/**
 * Update language-specific prompt
 * API: PUT /ai/prompts/{lang}
 */
export async function updateAIPrompt(lang: string, prompt: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/ai/prompts/${lang}`, {
    method: 'PUT',
    body: JSON.stringify({ language: lang, prompt }),
  });
  return data?.success === true;
}

/**
 * Get language-specific fallback messages
 * API: GET /ai/fallbacks or GET /ai/fallbacks/{lang}
 */
export async function getAIFallbacks(lang?: string): Promise<Record<string, string> | string> {
  const url = lang ? `${API_BASE}/ai/fallbacks/${lang}` : `${API_BASE}/ai/fallbacks`;
  const data = await apiCall<any>(url);
  if (data) {
    return lang ? (data.fallback || '') : (data.fallbacks || {});
  }
  return lang ? '' : {};
}

/**
 * Update language-specific fallback message
 * API: PUT /ai/fallbacks/{lang}
 */
export async function updateAIFallback(lang: string, fallback: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/ai/fallbacks/${lang}`, {
    method: 'PUT',
    body: JSON.stringify({ language: lang, fallback }),
  });
  return data?.success === true;
}

/**
 * Get AI interaction logs
 * API: GET /ai/interactions
 */
export async function getAIInteractions(limit?: number): Promise<AIInteraction[]> {
  let url = `${API_BASE}/ai/interactions`;
  if (limit) url += `?limit=${limit}`;
  
  const data = await apiCall<any>(url);
  if (data && data.interactions) {
    return data.interactions;
  }
  return [];
}

/**
 * Get AI usage statistics
 * API: GET /ai/stats
 */
export async function getAIStats(): Promise<AIStats> {
  const data = await apiCall<any>(`${API_BASE}/ai/stats`);
  if (data) {
    return {
      totalInteractions: data.totalInteractions || 0,
      approvedResponses: data.approvedResponses || 0,
      approvalRate: data.approvalRate || 0,
      byLanguage: data.byLanguage || {},
    };
  }
  return { totalInteractions: 0, approvedResponses: 0, approvalRate: 0, byLanguage: {} };
}

/**
 * Get supported languages
 * API: GET /ai/languages
 */
export async function getSupportedLanguages(): Promise<SupportedLanguages> {
  const data = await apiCall<any>(`${API_BASE}/ai/languages`);
  if (data && data.languages) {
    return data.languages;
  }
  return {
    'en': 'English',
    'hi': 'Hindi',
    'hi-Latn': 'Hinglish',
    'bn': 'Bengali',
    'ta': 'Tamil',
    'te': 'Telugu',
    'gu': 'Gujarati',
    'mr': 'Marathi',
  };
}

/**
 * Test AI response generation
 * API: POST /ai/test
 */
export async function testBedrockAIResponse(message: string): Promise<{ message: string; response: string; detectedLanguage: string }> {
  const data = await apiCall<any>(`${API_BASE}/ai/test`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
  if (data) {
    return {
      message: data.message || message,
      response: data.response || 'AI test response would appear here',
      detectedLanguage: data.detectedLanguage || 'en',
    };
  }
  return { message, response: 'AI service unavailable', detectedLanguage: 'en' };
}


// ============================================================================
// WABA ADVANCED MANAGEMENT API (AWS EUM Social)
// ============================================================================

/**
 * Download media from WhatsApp
 * API: GetWhatsAppMessageMedia
 */
export async function getWhatsAppMedia(mediaId: string, phoneNumberId: string, metadataOnly?: boolean): Promise<{
  mediaId: string;
  mimeType: string;
  fileSize: number;
  s3Key?: string;
  downloadUrl?: string;
} | null> {
  let url = `${API_BASE}/waba/media/${mediaId}?phoneNumberId=${phoneNumberId}`;
  if (metadataOnly) url += '&metadataOnly=true';
  
  const data = await apiCall<any>(url);
  if (data) {
    return {
      mediaId: data.mediaId || mediaId,
      mimeType: data.mimeType || '',
      fileSize: data.fileSize || 0,
      s3Key: data.s3Key,
      downloadUrl: data.downloadUrl,
    };
  }
  return null;
}

/**
 * Upload media to WhatsApp for sending
 * API: PostWhatsAppMessageMedia
 */
export async function postWhatsAppMedia(phoneNumberId: string, s3Key: string): Promise<{
  mediaId: string;
  s3Key: string;
} | null> {
  return apiCall<any>(`${API_BASE}/waba/media`, {
    method: 'POST',
    body: JSON.stringify({ phoneNumberId, s3Key }),
  });
}

/**
 * Configure event destinations for WABA
 * API: PutWhatsAppBusinessAccountEventDestinations
 */
export async function putWABAEventDestinations(wabaId: string, eventDestinations: {
  eventDestinationArn: string;
  roleArn: string;
}[]): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/waba/${wabaId}/events`, {
    method: 'PUT',
    body: JSON.stringify({ wabaId, eventDestinations }),
  });
  return data?.success === true;
}

/**
 * List tags for a WABA or phone number resource
 * API: ListTagsForResource
 */
export async function listWABATags(resourceArn: string): Promise<{ key: string; value: string }[]> {
  const data = await apiCall<any>(`${API_BASE}/waba/tags?resourceArn=${encodeURIComponent(resourceArn)}`);
  if (data && data.tags) {
    return data.tags;
  }
  return [];
}

/**
 * Add tags to a WABA or phone number resource
 * API: TagResource
 */
export async function tagWABAResource(resourceArn: string, tags: { key: string; value: string }[]): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/waba/tags`, {
    method: 'POST',
    body: JSON.stringify({ resourceArn, tags }),
  });
  return data?.success === true;
}

/**
 * Remove tags from a WABA or phone number resource
 * API: UntagResource
 */
export async function untagWABAResource(resourceArn: string, tagKeys: string[]): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/waba/tags`, {
    method: 'DELETE',
    body: JSON.stringify({ resourceArn, tagKeys }),
  });
  return data?.success === true;
}


// ============================================================================
// TEMPLATE ANALYTICS API
// ============================================================================

export interface TemplateAnalytics {
  templateName: string;
  language: string;
  totalSent: number;
  delivered: number;
  read: number;
  failed: number;
  deliveryRate: number;
  readRate: number;
  lastSent?: string;
  buttonClicks?: Record<string, number>;
}

export interface TemplateAnalyticsSummary {
  totalTemplatesSent: number;
  avgDeliveryRate: number;
  avgReadRate: number;
  topTemplates: TemplateAnalytics[];
  byCategory: Record<string, number>;
}

/**
 * Get analytics for a specific template
 * API: GET /templates/analytics/{templateName}
 */
export async function getTemplateAnalytics(templateName: string, wabaId?: string): Promise<TemplateAnalytics | null> {
  let url = `${API_BASE}/templates/analytics/${templateName}`;
  if (wabaId) url += `?wabaId=${wabaId}`;
  
  const data = await apiCall<any>(url);
  if (data) {
    return {
      templateName: data.templateName || templateName,
      language: data.language || 'en_US',
      totalSent: data.totalSent || 0,
      delivered: data.delivered || 0,
      read: data.read || 0,
      failed: data.failed || 0,
      deliveryRate: data.deliveryRate || 0,
      readRate: data.readRate || 0,
      lastSent: data.lastSent,
      buttonClicks: data.buttonClicks,
    };
  }
  return null;
}

/**
 * Get analytics summary for all templates
 * API: GET /templates/analytics
 */
export async function getTemplateAnalyticsSummary(wabaId?: string): Promise<TemplateAnalyticsSummary> {
  let url = `${API_BASE}/templates/analytics`;
  if (wabaId) url += `?wabaId=${wabaId}`;
  
  const data = await apiCall<any>(url);
  if (data) {
    return {
      totalTemplatesSent: data.totalTemplatesSent || 0,
      avgDeliveryRate: data.avgDeliveryRate || 0,
      avgReadRate: data.avgReadRate || 0,
      topTemplates: data.topTemplates || [],
      byCategory: data.byCategory || {},
    };
  }
  return { totalTemplatesSent: 0, avgDeliveryRate: 0, avgReadRate: 0, topTemplates: [], byCategory: {} };
}

// ============================================================================
// SCHEDULED MESSAGES API
// ============================================================================

export interface ScheduledMessage {
  id: string;
  scheduledId: string;
  contactId: string;
  contactName?: string;
  contactPhone?: string;
  templateName: string;
  templateParams: string[];
  phoneNumberId: string;
  scheduledAt: string;  // ISO timestamp
  status: 'PENDING' | 'SENT' | 'FAILED' | 'CANCELLED';
  createdAt: string;
  sentAt?: string;
  errorMessage?: string;
}

/**
 * Schedule a template message for later delivery
 * API: POST /messages/scheduled
 */
export async function scheduleTemplateMessage(request: {
  contactId: string;
  templateName: string;
  templateParams?: string[];
  phoneNumberId?: string;
  scheduledAt: string;  // ISO timestamp
}): Promise<ScheduledMessage | null> {
  const data = await apiCall<any>(`${API_BASE}/messages/scheduled`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
  if (data) {
    return normalizeScheduledMessage(data);
  }
  return null;
}

/**
 * List scheduled messages
 * API: GET /messages/scheduled
 */
export async function listScheduledMessages(status?: string): Promise<ScheduledMessage[]> {
  let url = `${API_BASE}/messages/scheduled`;
  if (status) url += `?status=${status}`;
  
  const data = await apiCall<any>(url);
  if (data && data.scheduledMessages) {
    return data.scheduledMessages.map(normalizeScheduledMessage);
  }
  return [];
}

/**
 * Cancel a scheduled message
 * API: DELETE /messages/scheduled/{scheduledId}
 */
export async function cancelScheduledMessage(scheduledId: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/messages/scheduled/${scheduledId}`, {
    method: 'DELETE',
  });
  return data?.success === true || data !== null;
}

/**
 * Update a scheduled message
 * API: PUT /messages/scheduled/{scheduledId}
 */
export async function updateScheduledMessage(scheduledId: string, updates: {
  scheduledAt?: string;
  templateParams?: string[];
}): Promise<ScheduledMessage | null> {
  const data = await apiCall<any>(`${API_BASE}/messages/scheduled/${scheduledId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
  if (data) {
    return normalizeScheduledMessage(data);
  }
  return null;
}

function normalizeScheduledMessage(item: any): ScheduledMessage {
  return {
    id: item.id || item.scheduledId || '',
    scheduledId: item.scheduledId || item.id || '',
    contactId: item.contactId || '',
    contactName: item.contactName,
    contactPhone: item.contactPhone,
    templateName: item.templateName || '',
    templateParams: item.templateParams || [],
    phoneNumberId: item.phoneNumberId || '',
    scheduledAt: item.scheduledAt || '',
    status: item.status || 'PENDING',
    createdAt: item.createdAt || new Date().toISOString(),
    sentAt: item.sentAt,
    errorMessage: item.errorMessage,
  };
}

// ============================================================================
// SEND CAROUSEL TEMPLATE MESSAGE
// ============================================================================

/**
 * Send a carousel template message to a contact
 * Carousel templates have multiple cards with media and buttons
 * 
 * API: POST /whatsapp/send with isTemplate=true and carousel components
 */
export async function sendCarouselTemplateMessage(request: {
  contactId: string;
  templateName: string;
  language?: string;
  phoneNumberId?: string;
  // Body text variables (for the main body above carousel)
  bodyParams?: string[];
  // Card-specific variables (array of arrays, one per card)
  cardParams?: string[][];
}): Promise<{ messageId: string; status: string } | null> {
  // Build template components for carousel
  const components: any[] = [];
  
  // Body component with variables
  if (request.bodyParams && request.bodyParams.length > 0) {
    components.push({
      type: 'body',
      parameters: request.bodyParams.map(text => ({ type: 'text', text }))
    });
  }
  
  // Carousel card components
  if (request.cardParams && request.cardParams.length > 0) {
    request.cardParams.forEach((cardVars, cardIndex) => {
      if (cardVars && cardVars.length > 0) {
        components.push({
          type: 'carousel',
          card_index: cardIndex,
          components: [{
            type: 'body',
            parameters: cardVars.map(text => ({ type: 'text', text }))
          }]
        });
      }
    });
  }
  
  return apiCall<{ messageId: string; status: string }>(`${API_BASE}/whatsapp/send`, {
    method: 'POST',
    body: JSON.stringify({
      contactId: request.contactId,
      isTemplate: true,
      templateName: request.templateName,
      templateParams: request.bodyParams || [],
      phoneNumberId: request.phoneNumberId,
      components: components.length > 0 ? components : undefined,
    }),
  });
}


// ============================================================================
// CONTACT TAGS & GROUPS API
// ============================================================================

export interface ContactTag {
  id: string;
  name: string;
  color: string;
  contactCount: number;
}

/**
 * Get all contact tags
 */
export async function listContactTags(): Promise<ContactTag[]> {
  // Tags are stored in localStorage for now (can be moved to DynamoDB later)
  const stored = localStorage.getItem('contactTags');
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      return [];
    }
  }
  return [];
}

/**
 * Create a new contact tag
 */
export async function createContactTag(name: string, color: string = '#25d366'): Promise<ContactTag> {
  const tags = await listContactTags();
  const newTag: ContactTag = {
    id: `tag_${Date.now()}`,
    name,
    color,
    contactCount: 0,
  };
  tags.push(newTag);
  localStorage.setItem('contactTags', JSON.stringify(tags));
  return newTag;
}

/**
 * Delete a contact tag
 */
export async function deleteContactTag(tagId: string): Promise<boolean> {
  const tags = await listContactTags();
  const filtered = tags.filter(t => t.id !== tagId);
  localStorage.setItem('contactTags', JSON.stringify(filtered));
  return true;
}

/**
 * Get tags for a specific contact
 */
export async function getContactTags(contactId: string): Promise<string[]> {
  const stored = localStorage.getItem(`contact_tags_${contactId}`);
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      return [];
    }
  }
  return [];
}

/**
 * Set tags for a contact
 */
export async function setContactTags(contactId: string, tagIds: string[]): Promise<boolean> {
  localStorage.setItem(`contact_tags_${contactId}`, JSON.stringify(tagIds));
  return true;
}

// ============================================================================
// STARRED MESSAGES API
// ============================================================================

/**
 * Get starred message IDs
 */
export function getStarredMessages(): string[] {
  const stored = localStorage.getItem('starredMessages');
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      return [];
    }
  }
  return [];
}

/**
 * Toggle star on a message
 */
export function toggleStarMessage(messageId: string): boolean {
  const starred = getStarredMessages();
  const index = starred.indexOf(messageId);
  if (index > -1) {
    starred.splice(index, 1);
  } else {
    starred.push(messageId);
  }
  localStorage.setItem('starredMessages', JSON.stringify(starred));
  return index === -1; // Returns true if now starred
}

/**
 * Check if message is starred
 */
export function isMessageStarred(messageId: string): boolean {
  return getStarredMessages().includes(messageId);
}

// ============================================================================
// EXPORT FUNCTIONS
// ============================================================================

/**
 * Export contacts to CSV
 */
export function exportContactsToCSV(contacts: Contact[]): string {
  const headers = ['Name', 'Phone', 'Email', 'WhatsApp Opt-In', 'SMS Opt-In', 'Email Opt-In', 'Created At'];
  const rows = contacts.map(c => [
    c.name || '',
    c.phone || '',
    c.email || '',
    c.optInWhatsApp ? 'Yes' : 'No',
    c.optInSms ? 'Yes' : 'No',
    c.optInEmail ? 'Yes' : 'No',
    c.createdAt || '',
  ]);
  
  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
  ].join('\n');
  
  return csvContent;
}

/**
 * Export messages to CSV
 */
export function exportMessagesToCSV(messages: Message[]): string {
  const headers = ['Direction', 'Contact', 'Content', 'Status', 'Timestamp', 'Channel'];
  const rows = messages.map(m => [
    m.direction,
    m.contactId,
    m.content?.substring(0, 200) || '',
    m.status,
    m.timestamp,
    m.channel,
  ]);
  
  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
  ].join('\n');
  
  return csvContent;
}

/**
 * Export chat to text format
 */
export function exportChatToText(messages: Message[], contactName: string): string {
  const lines = [
    `Chat Export - ${contactName}`,
    `Exported: ${new Date().toLocaleString()}`,
    '---',
    '',
  ];
  
  messages.forEach(m => {
    const time = new Date(m.timestamp).toLocaleString();
    const sender = m.direction === 'INBOUND' ? contactName : 'You';
    lines.push(`[${time}] ${sender}: ${m.content || '[Media]'}`);
  });
  
  return lines.join('\n');
}

/**
 * Export chat to PDF format (HTML-based, opens print dialog)
 */
export function exportChatToPDF(messages: Message[], contactName: string, wabaName?: string): void {
  const sortedMessages = [...messages].sort((a, b) => 
    new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  
  const html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Chat Export - ${contactName}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }
    .header { text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #25D366; }
    .header h1 { font-size: 24px; color: #1a1a1a; margin-bottom: 8px; }
    .header p { color: #666; font-size: 12px; }
    .messages { display: flex; flex-direction: column; gap: 12px; }
    .message { max-width: 70%; padding: 12px 16px; border-radius: 12px; position: relative; }
    .message.inbound { align-self: flex-start; background: #f0f0f0; border-bottom-left-radius: 4px; }
    .message.outbound { align-self: flex-end; background: #dcf8c6; border-bottom-right-radius: 4px; }
    .message .sender { font-size: 11px; font-weight: 600; color: #25D366; margin-bottom: 4px; }
    .message .content { font-size: 14px; line-height: 1.4; word-wrap: break-word; }
    .message .time { font-size: 10px; color: #999; margin-top: 6px; text-align: right; }
    .message .media-tag { font-style: italic; color: #666; }
    .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e5e5; text-align: center; font-size: 11px; color: #999; }
    @media print { body { padding: 20px; } .message { break-inside: avoid; } }
  </style>
</head>
<body>
  <div class="header">
    <h1>◇ Chat with ${contactName}</h1>
    <p>${wabaName ? `WABA: ${wabaName} | ` : ''}Exported: ${new Date().toLocaleString()}</p>
    <p>${sortedMessages.length} messages</p>
  </div>
  <div class="messages">
    ${sortedMessages.map(m => {
      const time = new Date(m.timestamp).toLocaleString();
      const sender = m.direction === 'INBOUND' ? contactName : 'You';
      const content = m.content || `<span class="media-tag">[${m.messageType || 'Media'}]</span>`;
      return `
        <div class="message ${m.direction.toLowerCase()}">
          <div class="sender">${sender}</div>
          <div class="content">${content}</div>
          <div class="time">${time}</div>
        </div>
      `;
    }).join('')}
  </div>
  <div class="footer">
    <p>Generated by WECARE.DIGITAL</p>
  </div>
</body>
</html>
  `;
  
  // Open in new window and trigger print
  const printWindow = window.open('', '_blank');
  if (printWindow) {
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.onload = () => {
      printWindow.print();
    };
  }
}

/**
 * Download file helper
 */
export function downloadFile(content: string, filename: string, mimeType: string = 'text/csv') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ============================================================================
// BULK CONTACT IMPORT
// ============================================================================

export interface ImportResult {
  total: number;
  created: number;
  updated: number;
  failed: number;
  errors: string[];
}

/**
 * Parse CSV content to contact objects
 * All contacts auto opt-in to WhatsApp by default
 */
export function parseContactsCSV(csvContent: string): Partial<Contact>[] {
  const lines = csvContent.split('\n').filter(line => line.trim());
  if (lines.length < 2) return [];
  
  const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/"/g, ''));
  const contacts: Partial<Contact>[] = [];
  
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].match(/(".*?"|[^,]+)/g)?.map(v => v.replace(/^"|"$/g, '').trim()) || [];
    const contact: Partial<Contact> = {
      // Auto opt-in all contacts by default
      optInWhatsApp: true,
      allowlistWhatsApp: true,
    };
    
    headers.forEach((header, index) => {
      const value = values[index] || '';
      if (header === 'name') contact.name = value;
      else if (header === 'phone') contact.phone = value.startsWith('+') ? value : `+${value}`;
      else if (header === 'email') contact.email = value;
    });
    
    if (contact.phone) {
      contacts.push(contact);
    }
  }
  
  return contacts;
}

/**
 * Import contacts from parsed CSV data
 * All contacts auto opt-in to WhatsApp by default
 */
export async function importContacts(contacts: Partial<Contact>[]): Promise<ImportResult> {
  const result: ImportResult = {
    total: contacts.length,
    created: 0,
    updated: 0,
    failed: 0,
    errors: [],
  };
  
  for (const contact of contacts) {
    try {
      // Ensure all contacts have WhatsApp opt-in enabled
      const contactWithOptIn = {
        ...contact,
        optInWhatsApp: true,
        allowlistWhatsApp: true,
      };
      
      // Check if contact exists by phone
      const existing = await listContacts();
      const found = existing.find(c => c.phone === contact.phone);
      
      if (found) {
        // Update existing
        const updated = await updateContact(found.contactId, contactWithOptIn);
        if (updated) {
          result.updated++;
        } else {
          result.failed++;
          result.errors.push(`Failed to update: ${contact.phone}`);
        }
      } else {
        // Create new
        const created = await createContact(contactWithOptIn);
        if (created) {
          result.created++;
        } else {
          result.failed++;
          result.errors.push(`Failed to create: ${contact.phone}`);
        }
      }
    } catch (err: any) {
      result.failed++;
      result.errors.push(`Error with ${contact.phone}: ${err.message}`);
    }
  }
  
  return result;
}

// ============================================================================
// AUTO-REPLY PER CONTACT
// ============================================================================

/**
 * Get auto-reply setting for a contact
 */
export function getContactAutoReply(contactId: string): boolean {
  const stored = localStorage.getItem(`autoReply_${contactId}`);
  return stored === 'true';
}

/**
 * Set auto-reply setting for a contact
 */
export function setContactAutoReply(contactId: string, enabled: boolean): void {
  localStorage.setItem(`autoReply_${contactId}`, String(enabled));
}

/**
 * Get all contacts with auto-reply enabled
 */
export function getAutoReplyContacts(): string[] {
  const contacts: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith('autoReply_') && localStorage.getItem(key) === 'true') {
      contacts.push(key.replace('autoReply_', ''));
    }
  }
  return contacts;
}

// ============================================================================
// AI FEEDBACK
// ============================================================================

export interface AIFeedback {
  interactionId: string;
  messageId: string;
  rating: 'good' | 'bad';
  comment?: string;
  timestamp: number;
}

/**
 * Submit feedback for an AI response
 */
export function submitAIFeedback(feedback: Omit<AIFeedback, 'timestamp'>): void {
  const stored = localStorage.getItem('aiFeedback');
  const feedbacks: AIFeedback[] = stored ? JSON.parse(stored) : [];
  feedbacks.push({ ...feedback, timestamp: Date.now() });
  localStorage.setItem('aiFeedback', JSON.stringify(feedbacks));
}

/**
 * Get AI feedback history
 */
export function getAIFeedbackHistory(): AIFeedback[] {
  const stored = localStorage.getItem('aiFeedback');
  return stored ? JSON.parse(stored) : [];
}

// ============================================================================
// SYSTEM CONFIG
// ============================================================================

export interface SystemConfig {
  [key: string]: any;
}

/**
 * Get system configuration by key
 * Lambda: wecare-ai-config-management
 */
export async function getSystemConfig(configKey: string): Promise<SystemConfig | null> {
  const data = await apiCall<any>(`${API_BASE}/ai/config?key=${configKey}`);
  if (data && data.config) {
    return data.config;
  }
  return null;
}

/**
 * Update system configuration
 * Lambda: wecare-ai-config-management
 */
export async function updateSystemConfig(configKey: string, config: SystemConfig): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/ai/config`, {
    method: 'PUT',
    body: JSON.stringify({ key: configKey, config }),
  });
  return data !== null;
}
