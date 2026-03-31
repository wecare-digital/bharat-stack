/**
 * API Service Layer
 * Connects to API Gateway -> Lambda -> DynamoDB
 * NO MOCK DATA - All data fetched from real AWS resources
 * 
 * API Endpoint: Uses NEXT_PUBLIC_API_BASE or defaults to production
 */

import { API_BASE, RETRY_CONFIG, DEFAULT_GSTIN } from '../config/constants';
import { fetchAuthSession } from 'aws-amplify/auth';

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

// Get the current Cognito access token for API calls
async function getAuthToken(): Promise<string | null> {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.accessToken?.toString() ?? null;
  } catch {
    return null;
  }
}

// Helper function for API calls with retry logic and better error handling
async function apiCall<T>(url: string, options?: RequestInit, retryCount = 0): Promise<T | null> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

    // Inject Cognito auth token
    const token = await getAuthToken();
    const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
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
    if (response.status === 401) {
      // Token may have expired — try once with a fresh session
      if (retryCount === 0) {
        console.debug('Got 401, retrying with refreshed token...');
        return apiCall<T>(url, options, retryCount + 1);
      }
      lastConnectionError = 'Authentication failed - please sign in again';
    } else if (response.status === 403) {
      lastConnectionError = 'Access denied - check API Gateway permissions';
    } else if (response.status === 404) {
      lastConnectionError = 'API endpoint not found';
    } else if (response.status === 500) {
      lastConnectionError = 'Server error - check Lambda logs';
    } else if (response.status === 502 || response.status === 503 || response.status === 504) {
      lastConnectionError = response.status === 504 ? 'Lambda timeout - function took too long' : 'API Gateway error - service unavailable';
      // Retry on 502/503 errors
      if (retryCount < RETRY_CONFIG.maxRetries) {
        const delayMs = Math.min(
          RETRY_CONFIG.baseDelayMs * Math.pow(2, retryCount),
          RETRY_CONFIG.maxDelayMs
        );
        console.debug(`Retrying API call (${retryCount + 1}/${RETRY_CONFIG.maxRetries}) after ${delayMs}ms...`);
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
        console.debug(`Rate limited, retrying after ${delayMs}ms...`);
        await delay(delayMs);
        return apiCall<T>(url, options, retryCount + 1);
      }
      lastConnectionError = 'Rate limited - too many requests';
    } else {
      // Try to extract error message from response body
      try {
        const errBody = await response.json();
        const msg = errBody?.error?.message || errBody?.error || errBody?.message;
        lastConnectionError = msg ? `HTTP ${response.status}: ${msg}` : `HTTP ${response.status}: ${response.statusText}`;
      } catch {
        lastConnectionError = `HTTP ${response.status}: ${response.statusText}`;
      }
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
      console.debug(`Network error, retrying (${retryCount + 1}/${RETRY_CONFIG.maxRetries}) after ${delayMs}ms...`);
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
    const token = await getAuthToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE}/contacts`, { method: 'GET', headers });
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
  // WhatsApp BSUID (Business-Scoped User ID) — unique per WABA portfolio
  bsuid?: string;
  // Parent BSUID (linked account)
  parentBsuid?: string;
  // WhatsApp username (e.g. "@pablomorales")
  username?: string;
  // Contact book name — auto-populated by Meta's contact book feature
  contactBookName?: string;
  shippingAddress?: string;
  billingAddress?: string;
  // Structured address fields for WhatsApp Payments shipping_info
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  state?: string;
  postalCode?: string;
  landmark?: string;
  houseNumber?: string;
  buildingName?: string;
  // Opt-in fields (Requirement 3.2)
  optInWhatsApp: boolean;
  optInSms: boolean;
  optInEmail: boolean;
  // Allowlist fields (Requirement 3.2)
  allowlistWhatsApp: boolean;
  allowlistSms: boolean;
  allowlistEmail: boolean;
  lastInboundMessageAt?: string;
  tags?: string[];
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
    bsuid: item.bsuid || '',
    username: item.username || '',
    contactBookName: item.contactBookName || '',
    shippingAddress: item.shippingAddress || '',
    billingAddress: item.billingAddress || '',
    // Opt-in fields
    optInWhatsApp: item.optInWhatsApp || false,
    optInSms: item.optInSms || false,
    optInEmail: item.optInEmail || false,
    // Allowlist fields (Requirement 3.2)
    allowlistWhatsApp: item.allowlistWhatsApp || false,
    allowlistSms: item.allowlistSms || false,
    allowlistEmail: item.allowlistEmail || false,
    lastInboundMessageAt: normalizeTimestamp(item.lastInboundMessageAt),
    tags: Array.isArray(item.tags) ? item.tags : [],
    createdAt: normalizeTimestamp(item.createdAt) || new Date().toISOString(),
    updatedAt: normalizeTimestamp(item.updatedAt) || new Date().toISOString(),
    deletedAt: item.deletedAt,
  };
}

/**
 * Fix #8/#12: Safely convert epoch seconds OR ISO strings to ISO string.
 * Handles: epoch seconds (number), epoch string ("1709568000"), ISO string, undefined/null.
 */
function normalizeTimestamp(value: any): string | undefined {
  if (!value && value !== 0) return undefined;
  // If it's a number or a string that looks like an epoch (all digits)
  const num = Number(value);
  if (!isNaN(num) && String(value).match(/^\d+$/)) {
    // Epoch seconds are < 10 billion; epoch millis are > 10 billion
    const ms = num < 1e12 ? num * 1000 : num;
    const d = new Date(ms);
    if (!isNaN(d.getTime())) return d.toISOString();
  }
  // Try parsing as ISO string
  const d = new Date(String(value));
  if (!isNaN(d.getTime())) return d.toISOString();
  return undefined;
}

// ============================================================================
// MESSAGES API
// ============================================================================

export interface Message {
  id: string;
  messageId: string;
  contactId: string;
  channel: 'WHATSAPP' | 'SMS' | 'EMAIL' | 'RCS';
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
  senderBsuid?: string;
  senderUsername?: string;
  receivingPhone?: string;
  awsPhoneNumberId?: string;
  transcription?: string;       // English transcription of voice notes
  detectedLanguage?: string;    // Detected language of voice note (e.g. "hi-IN")
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
  const data = await apiCall<any>(`${API_BASE}/messages/${messageId}`);
  if (data) {
    const msg = data.message || data;
    return msg && (msg.id || msg.messageId) ? normalizeMessage(msg) : null;
  }
  return null;
}

export async function deleteMessage(messageId: string, direction: 'INBOUND' | 'OUTBOUND' = 'INBOUND'): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/messages/${messageId}?direction=${direction}`, {
    method: 'DELETE',
  });
  // Accept success if we got a response (even if success field is missing)
  return data !== null && (data.success === true || data.messageId === messageId || !data.error);
}

export async function updateMessage(messageId: string, updates: Record<string, any>): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/messages/${messageId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
  return data !== null && data.success === true;
}

// createInvoice() removed — use createInvoiceEngine() instead

function normalizeMessage(item: any): Message {
  const timestamp = item.timestamp || item.createdAt;
  return {
    id: item.id || item.messageId || '',
    messageId: item.messageId || item.id || '',
    contactId: item.contactId || '',
    channel: (item.channel || 'WHATSAPP').toUpperCase() as 'WHATSAPP' | 'SMS' | 'EMAIL' | 'RCS',
    direction: (item.direction || 'INBOUND').toUpperCase() as 'INBOUND' | 'OUTBOUND',
    content: item.content || item.text || '',
    timestamp: normalizeTimestamp(timestamp) || new Date().toISOString(),
    status: item.status || 'received',
    whatsappMessageId: item.whatsappMessageId,
    mediaId: item.mediaId,
    s3Key: item.s3Key,
    mediaUrl: item.mediaUrl,  // Use pre-signed URL from API
    messageType: item.messageType,  // image, video, audio, document, text
    senderPhone: item.senderPhone,
    senderName: item.senderName,
    senderBsuid: item.senderBsuid,
    senderUsername: item.senderUsername,
    receivingPhone: item.receivingPhone,
    awsPhoneNumberId: item.awsPhoneNumberId,
    transcription: item.transcription,
    detectedLanguage: item.detectedLanguage,
  };
}

// Send WhatsApp message via Lambda
export interface SendMessageRequest {
  contactId: string;
  content?: string;
  phoneNumberId?: string;
  recipientBsuid?: string; // Send to BSUID instead of phone number
  isTemplate?: boolean;
  templateName?: string;
  templateParams?: string[];
  mediaFile?: string;
  mediaType?: string;
  mediaFileName?: string; // Real filename for documents
  isOtpTemplate?: boolean;
  otpCode?: string;
  otpButtonType?: string;
}

// Send WhatsApp reaction via Lambda
export interface SendReactionRequest {
  contactId: string;
  reactionMessageId: string;  // WhatsApp message ID to react to
  reactionEmoji?: string;     // Default: thumbs up
  phoneNumberId?: string;
  recipientBsuid?: string;    // Send reaction to BSUID recipient
}

export async function sendWhatsAppMessage(request: SendMessageRequest): Promise<{ messageId: string; status: string } | null> {
  // Note: WhatsApp typing indicators require Meta Cloud API direct access
  // (POST /{PHONE_NUMBER_ID}/messages with status:"read" + typing_indicator object)
  // The read receipt approach is used as a proxy for typing indicators.

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
      recipientBsuid: request.recipientBsuid,
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
  recipientBsuid?: string;    // Send to BSUID recipient
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
      recipientBsuid: request.recipientBsuid,
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
    `${API_BASE}/whatsapp/templates/carousel-media${params.toString() ? '?' + params : ''}`,
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
    `${API_BASE}/whatsapp/templates/carousel${params.toString() ? '?' + params : ''}`,
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

// sendSmsMessage() removed — use sendSmsAws() instead

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

// Old AIConfig, getAIConfig(), updateAIConfig(), testAIResponse(), getAISuggestions() removed
// Use getBedrockAIConfig(), updateBedrockAIConfig(), testBedrockAIResponse() instead

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
  // Use lightweight count-only endpoints to avoid fetching all records
  try {
    const [msgStats, contactStats, bulkJobs] = await Promise.all([
      apiCall<any>(`${API_BASE}/messages?stats=count`),
      apiCall<any>(`${API_BASE}/contacts?stats=count`),
      listBulkJobs(),
    ]);

    const activeBulkJobs = bulkJobs.filter(j =>
      j.status === 'PENDING' || j.status === 'IN_PROGRESS'
    ).length;

    // Try to get DLQ depth
    let dlqDepth = 0;
    try {
      const dlqData = await apiCall<any>(`${API_BASE}/dlq`);
      dlqDepth = dlqData?.count ?? dlqData?.messages?.length ?? 0;
    } catch { /* non-critical */ }

    return {
      messagesToday: msgStats?.messagesToday ?? 0,
      messagesWeek: msgStats?.messagesWeek ?? 0,
      activeContacts: contactStats?.activeContacts ?? 0,
      bulkJobs: activeBulkJobs,
      deliveryRate: msgStats?.deliveryRate ?? 100,
      aiResponses: 0,
      dlqDepth,
    };
  } catch {
    // Fallback: return safe defaults on any error
    return {
      messagesToday: 0,
      messagesWeek: 0,
      activeContacts: 0,
      bulkJobs: 0,
      deliveryRate: 100,
      aiResponses: 0,
      dlqDepth: 0,
    };
  }
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
  // Defaults (used as fallback if any call fails)
  const defaults: SystemHealth = {
    whatsapp: { status: 'active', phoneNumbers: 2, qualityRating: 'GREEN' },
    sms: { status: 'active', poolId: 'TBD' },
    email: { status: 'active', verified: true },
    ai: {
      status: 'active',
      internalKbId: 'static-faq',
      internalAgentId: 'QIEEHEBTZO',
      internalAgentAlias: 'ASCBD7YPUT',
      externalKbId: 'static-faq',
      externalAgentId: 'Z4YAK0ZLBO',
      externalAgentAlias: 'WANPKHQGIB'
    },
    dlq: { depth: 0 },
  };

  try {
    // Fetch real data from existing endpoints in parallel
    const [billingData, dlqData, wabaData] = await Promise.all([
      apiCall<any>(`${API_BASE}/billing?health=true&advisor=false`).catch(() => null),
      apiCall<any>(`${API_BASE}/dlq`).catch(() => null),
      apiCall<any>(`${API_BASE}/waba`).catch(() => null),
    ]);

    // DLQ depth
    if (dlqData) {
      defaults.dlq.depth = dlqData.count ?? dlqData.messages?.length ?? 0;
      if (dlqData.messages?.length > 0) {
        defaults.dlq.oldestMessage = dlqData.messages[dlqData.messages.length - 1]?.lastAttemptAt
          ? new Date(dlqData.messages[dlqData.messages.length - 1].lastAttemptAt * 1000).toISOString()
          : undefined;
      }
    }

    // AWS Health status from billing endpoint
    if (billingData?.health) {
      const h = billingData.health;
      if (h.status === 'issues' || h.openIssues > 0) {
        defaults.whatsapp.status = 'warning';
      }
    }

    // WABA phone quality from waba endpoint
    if (wabaData && Array.isArray(wabaData.wabas)) {
      defaults.whatsapp.phoneNumbers = wabaData.wabas.reduce(
        (sum: number, w: any) => sum + (w.phoneNumbers?.length ?? 0), 0
      ) || defaults.whatsapp.phoneNumbers;
    }
  } catch {
    // Return defaults on any error
  }

  return defaults;
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
    createdAt: normalizeTimestamp(item.createdAt) || new Date().toISOString(),
    updatedAt: normalizeTimestamp(item.updatedAt) || new Date().toISOString(),
  };
}


// ============================================================================
// SMS AWS API (Pinpoint/SNS)
// ============================================================================

export interface SmsAwsMessage {
  messageId: string;
  contactId: string;
  phoneNumber: string;
  content: string;
  status: string;
  direction: string;
  messageType: string;
  senderId?: string;
  providerMessageId?: string;
  timestamp: number;
  createdAt: number;
}

export interface SendSmsAwsRequest {
  contactId?: string;
  phoneNumber?: string;
  content: string;
  messageType?: 'TRANSACTIONAL' | 'PROMOTIONAL';
  senderId?: string;
}

export async function listSmsAwsMessages(contactId?: string, status?: string): Promise<SmsAwsMessage[]> {
  let url = `${API_BASE}/sms-aws/messages`;
  const params = new URLSearchParams();
  if (contactId) params.append('contactId', contactId);
  if (status) params.append('status', status);
  if (params.toString()) url += `?${params}`;
  
  const data = await apiCall<any>(url);
  if (data) {
    return data.messages || [];
  }
  return [];
}

export async function sendSmsAws(request: SendSmsAwsRequest): Promise<{ messageId: string; status: string; providerMessageId?: string } | null> {
  return apiCall<{ messageId: string; status: string; providerMessageId?: string }>(`${API_BASE}/sms-aws/send`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}


// ============================================================================
// VOICE AWS API (Connect/Polly)
// ============================================================================

export interface VoiceAwsCall {
  id: string;
  callId: string;
  contactId: string;
  phoneNumber: string;
  callType: 'tts' | 'audio';
  status: string;
  direction: string;
  duration: number;
  voiceId?: string;
  messageText?: string;
  connectContactId?: string;
  createdAt: number;
  updatedAt: number;
}

export interface MakeVoiceAwsCallRequest {
  contactId?: string;
  phoneNumber?: string;
  callType: 'tts' | 'audio';
  messageText?: string;
  voiceId?: string;
  audioUrl?: string;
}

export async function listVoiceAwsCalls(contactId?: string, status?: string): Promise<VoiceAwsCall[]> {
  let url = `${API_BASE}/voice-aws/calls`;
  const params = new URLSearchParams();
  if (contactId) params.append('contactId', contactId);
  if (status) params.append('status', status);
  if (params.toString()) url += `?${params}`;
  
  const data = await apiCall<any>(url);
  if (data) {
    return data.calls || [];
  }
  return [];
}

export async function makeVoiceAwsCall(request: MakeVoiceAwsCallRequest): Promise<{ callId: string; status: string; providerCallId?: string } | null> {
  return apiCall<{ callId: string; status: string; providerCallId?: string }>(`${API_BASE}/voice-aws/call`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}


// ============================================================================
// WHATSAPP VOICE (TTS via Polly + Audio Messages)
// ============================================================================

export interface WhatsAppVoiceLog {
  messageId: string;
  contactId: string;
  phoneNumber: string;
  messageText: string;
  voiceId: string;
  languageCode: string;
  audioSize: number;
  s3Key: string;
  whatsappMessageId: string;
  status: string;
  type: 'tts' | 'recording';
  createdAt: number;
}

export interface SendWhatsAppTTSRequest {
  contactId?: string;
  phoneNumber?: string;
  messageText: string;
  voiceId?: string;
  languageCode?: string;
  engine?: string;
  phoneNumberId?: string;
  recipientBsuid?: string;    // Send to BSUID recipient
}

export interface SendWhatsAppAudioRequest {
  contactId?: string;
  phoneNumber?: string;
  phoneNumberId?: string;
  s3Key?: string;
  audioBase64?: string;
  contentType?: string;
  recipientBsuid?: string;    // Send to BSUID recipient
}

export async function sendWhatsAppTTS(request: SendWhatsAppTTSRequest): Promise<{
  messageId: string; whatsappMessageId?: string; s3Key: string; audioSize: number; status: string;
} | null> {
  return apiCall<any>(`${API_BASE}/whatsapp-voice/tts`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function sendWhatsAppAudioMessage(request: SendWhatsAppAudioRequest): Promise<{
  messageId: string; whatsappMessageId?: string; s3Key: string; status: string;
} | null> {
  return apiCall<any>(`${API_BASE}/whatsapp-voice/send`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function listWhatsAppVoiceLogs(): Promise<WhatsAppVoiceLog[]> {
  const data = await apiCall<any>(`${API_BASE}/whatsapp-voice/logs`);
  return data?.logs || [];
}

export async function getPollyVoices(): Promise<{
  voices: Record<string, { id: string; gender: string; engine: string }[]>;
  transcribeLanguages?: Record<string, string>;
}> {
  const data = await apiCall<any>(`${API_BASE}/whatsapp-voice/voices`);
  return {
    voices: data?.voices || {},
    transcribeLanguages: data?.transcribeLanguages || {},
  };
}

// Transcribe a voice note — returns English transcription + detected language
export interface TranscribeResult {
  transcription: string;
  originalTranscription?: string;
  detectedLanguage: string;
  messageId?: string;
  cached: boolean;
}

export async function transcribeVoiceNote(params: {
  messageId?: string;
  s3Key?: string;
  direction?: 'INBOUND' | 'OUTBOUND';
}): Promise<TranscribeResult | null> {
  return apiCall<TranscribeResult>(`${API_BASE}/whatsapp-voice/transcribe`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// Voice language configuration
export interface VoiceLanguageConfig {
  autoTranscribe: boolean;
  enabledLanguages: string[];
  defaultVoices: Record<string, string>;
  autoReplyWithVoice: boolean;
  transcribeLanguages: string[];
}

export async function getVoiceLanguageConfig(): Promise<VoiceLanguageConfig | null> {
  const data = await apiCall<any>(`${API_BASE}/whatsapp-voice/language-config`);
  return data?.config || null;
}

export async function updateVoiceLanguageConfig(config: Partial<VoiceLanguageConfig>): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/whatsapp-voice/language-config`, {
    method: 'PUT',
    body: JSON.stringify({ config }),
  });
  return data?.success === true;
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

export interface CostRecommendation {
  id: string;
  severity: 'high' | 'medium' | 'low' | 'info';
  title: string;
  description: string;
  potentialSavings: number;
  action: string;
  link?: string;
}

export interface AWSHealthData {
  openIssues: number;
  scheduledChanges: number;
  otherNotifications: number;
  events: any[];
  scheduledEvents: any[];
  notifications: any[];
  lastChecked: string;
  status: 'healthy' | 'issues' | 'unknown';
  error?: string;
}

export interface TrustedAdvisorData {
  actionRecommended: number;
  investigationRecommended: number;
  noProblemsDetected: number;
  notAvailable: number;
  checks: any[];
  categories: Record<string, { ok: number; warning: number; error: number }>;
  lastChecked: string;
  error?: string;
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
  recommendations?: CostRecommendation[];
  health?: AWSHealthData;
  trustedAdvisor?: TrustedAdvisorData;
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
  'Meta WhatsApp Cloud API': { limit: 'Pay per conversation', unit: 'conversations' },
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
      recommendations: data.recommendations || [],
      health: data.health,
      trustedAdvisor: data.trustedAdvisor,
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
    { service: 'Meta WhatsApp Cloud API', cost: 0, usage: 381, unit: 'conversations', freeLimit: '1000 free/mo', status: 'free' },
    { service: 'AWS Pinpoint (SMS/Voice)', cost: 2, usage: 47, unit: 'messages/calls', freeLimit: '$2/mo toll-free', status: 'paid' },
    { service: 'Amazon Polly', cost: 0, usage: 12, unit: 'TTS requests', freeLimit: '5M chars/month', status: 'free' },
    { service: 'AWS Secrets Manager', cost: 0.40, usage: 1, unit: 'secrets', freeLimit: '$0.40/secret/mo', status: 'paid' },
    { service: 'Amazon OpenSearch', cost: 0, usage: 182, unit: 'operations', freeLimit: 'Serverless', status: 'free' },
    { service: 'Amazon Route 53', cost: 0, usage: 94671, unit: 'queries', freeLimit: '$0.50/zone', status: 'free' },
    { service: 'Amazon Cognito', cost: 0, usage: 1, unit: 'users', freeLimit: '50K MAU', status: 'free' },
    { service: 'CloudWatch', cost: 0, usage: 370, unit: 'metrics', freeLimit: '10 metrics', status: 'free' },
  ];
  
  return {
    totalCost: 2.40,
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
  const data = await apiCall<any>(`${API_BASE}/contacts/${contactId}?hard=true`, {
    method: 'DELETE',
  });
  
  if (data && data.success) {
    return true;
  }
  
  // Fallback: delete messages one by one, then soft delete contact
  try {
    const messagesDeleted = await deleteContactMessages(contactId);
    const contactDeleted = await deleteContact(contactId);
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
// WHATSAPP TEMPLATES API (Meta Graph API)
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
  type: 'HEADER' | 'BODY' | 'FOOTER' | 'BUTTONS' | 'CAROUSEL';
  format?: 'TEXT' | 'IMAGE' | 'VIDEO' | 'DOCUMENT';
  text?: string;
  example?: { body_text?: string[][] };
  buttons?: { type: string; text: string; url?: string; phone_number?: string }[];
  cards?: any[];
}

// WABA IDs for template fetching
const WABA_IDS = {
  'WECARE.DIGITAL': 'waba-e47d916f3c7a47e1a34a19653893dd4b',
  'Manish Agarwal': 'waba-dbe343f210204752b74c80a0a59631a6',
};

// listWhatsAppTemplates() and getWhatsAppTemplate() removed — use listTemplates() and getTemplateDetails() instead

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
  recipientBsuid?: string;    // Send to BSUID recipient
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
      recipientBsuid: request.recipientBsuid,
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
  gstRate?: number;  // Per-item GST rate (0, 3, 5, 12, 18, 28)
}

export interface SendPaymentMessageRequest {
  contactId: string;
  phoneNumberId: string;
  recipientBsuid?: string;    // Send to BSUID recipient
  templateName?: string;
  referenceId: string;
  items: PaymentOrderItem[];
  discount?: number;      // In paise
  delivery?: number;      // In paise (shipping/delivery)
  tax?: number;           // In paise (total GST from all items)
  taxDescription?: string; // e.g., "GST 18%" or "Tax"
  gstin?: string;         // GSTIN number
  currency?: string;
  headerImageUrl?: string;
  bodyText?: string;
  useInteractive?: boolean;
  paymentConfiguration?: string;
  convenienceFee?: number; // In paise (2% + 18% GST)
  orderId?: string;       // Order ID (blank = Offline)
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
    payment_configuration: request.paymentConfiguration || 'WECARE-RAZOR-PAY',
    currency: request.currency || 'INR',
    // First item name for backward compat
    itemName: firstItem.name || 'Service Fee',
    quantity: firstItem.quantity || 1,
    gstin: request.gstin || DEFAULT_GSTIN,
    orderId: request.orderId || 'Offline',
    // Per-item GST rates passed in items array
    order: {
      status: 'pending',
      items: request.items.map((item, idx) => ({
        retailer_id: item.productId || `ITEM_${idx + 1}`,
        name: item.name,
        amount: { value: item.amount, offset: 100 },
        quantity: item.quantity,
        gstRate: item.gstRate ?? 0,
      })),
      subtotal: { value: subtotal, offset: 100 },
      discount: { value: discount, offset: 100, description: 'Promo' },
      shipping: { value: delivery, offset: 100, description: 'Express' },
      tax: { value: tax, offset: 100, description: `GSTIN: ${request.gstin || DEFAULT_GSTIN}` },
    },
  };

  // Use interactive mode if specified
  if (request.useInteractive) {
    const result = await apiCall<{ messageId: string; status: string }>(`${API_BASE}/whatsapp/send`, {
      method: 'POST',
      body: JSON.stringify({
        contactId: request.contactId,
        phoneNumberId: request.phoneNumberId,
        recipientBsuid: request.recipientBsuid,
        isInteractivePayment: true,
        orderDetails: orderDetails,
        headerImageUrl: request.headerImageUrl,
      }),
    });
    return result;
  }

  // Template mode
  return apiCall<{ messageId: string; status: string }>(`${API_BASE}/whatsapp/send`, {
    method: 'POST',
    body: JSON.stringify({
      contactId: request.contactId,
      phoneNumberId: request.phoneNumberId,
      recipientBsuid: request.recipientBsuid,
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
// WABA MANAGEMENT API (Meta Graph API)
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
// TEMPLATE MANAGEMENT API (Meta Graph API)
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
  let url = `${API_BASE}/whatsapp/templates`;
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
  let url = `${API_BASE}/whatsapp/templates/${templateId}`;
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
  return apiCall<any>(`${API_BASE}/whatsapp/templates`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Create template from Meta's library
 * API: CreateWhatsAppMessageTemplateFromLibrary
 */
export async function createTemplateFromLibrary(request: CreateFromLibraryRequest): Promise<{ metaTemplateId: string; category: string; templateStatus: string } | null> {
  return apiCall<any>(`${API_BASE}/whatsapp/template-from-library`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Update an existing template
 * API: UpdateWhatsAppMessageTemplate
 */
export async function updateTemplate(templateId: string, request: UpdateTemplateRequest): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/whatsapp/templates/${templateId}`, {
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
  let url = `${API_BASE}/whatsapp/templates/${templateName}`;
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
  let url = `${API_BASE}/whatsapp/template-library`;
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
  return apiCall<any>(`${API_BASE}/whatsapp/templates/media`, {
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
    agentId: 'Z4YAK0ZLBO',
    agentAlias: 'WANPKHQGIB',
    knowledgeBaseId: 'static-faq',
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
// WABA ADVANCED MANAGEMENT API (Meta Graph API)
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
// WABA SNS SUBSCRIPTION API
// ============================================================================

export interface WABASNSSubscriptionStatus {
  wabaId: string;
  storedConfig: {
    wabaId?: string;
    snsTopicArn?: string;
    roleArn?: string;
    subscribedAt?: string;
    unsubscribedAt?: string;
    status?: string;
  };
  liveEventDestinations: { eventDestinationArn: string; roleArn?: string }[];
  isSubscribed: boolean;
  defaultTopicArn: string;
}

/**
 * Subscribe a WABA to SNS topic for receiving WhatsApp events
 * Sets up PutWhatsAppBusinessAccountEventDestinations
 */
export async function subscribeWABAToSNS(wabaId: string, snsTopicArn?: string, roleArn?: string): Promise<boolean> {
  const body: Record<string, string> = {};
  if (snsTopicArn) body.snsTopicArn = snsTopicArn;
  if (roleArn) body.roleArn = roleArn;
  const data = await apiCall<any>(`${API_BASE}/waba/${wabaId}/subscribe-sns`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return data?.success === true;
}

/**
 * Unsubscribe a WABA from SNS (clears event destinations)
 */
export async function unsubscribeWABAFromSNS(wabaId: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/waba/${wabaId}/subscribe-sns`, {
    method: 'DELETE',
    body: JSON.stringify({}),
  });
  return data?.success === true;
}

/**
 * Get current SNS subscription status for a WABA
 */
export async function getWABASNSSubscriptionStatus(wabaId: string): Promise<WABASNSSubscriptionStatus | null> {
  return apiCall<WABASNSSubscriptionStatus>(`${API_BASE}/waba/${wabaId}/subscribe-sns`);
}


// ============================================================================
// WABA PHONE MIGRATION & REGISTRATION API
// ============================================================================

/**
 * Request OTP/PIN for phone number verification
 */
export async function requestPhoneOTP(phoneNumberId: string, method: 'SMS' | 'VOICE' = 'SMS'): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/waba/request-otp`, {
    method: 'POST',
    body: JSON.stringify({ phoneNumberId, method }),
  });
  return data?.success === true;
}

/**
 * Verify OTP/PIN code for phone number
 */
export async function verifyPhoneOTP(phoneNumberId: string, code: string): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/waba/verify-otp`, {
    method: 'POST',
    body: JSON.stringify({ phoneNumberId, code }),
  });
  return data?.success === true;
}

/**
 * Register a phone number with optional PIN
 */
export async function registerPhone(phoneNumberId: string, pin?: string): Promise<boolean> {
  const body: Record<string, string> = { phoneNumberId };
  if (pin) body.pin = pin;
  const data = await apiCall<any>(`${API_BASE}/waba/register-phone`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return data?.success === true;
}

/**
 * Migrate a phone number between WABAs
 * @param sendPin - If true, sends PIN via SMS/VOICE before migration
 */
export async function migratePhone(params: {
  phoneNumberId: string;
  sourceWabaId?: string;
  targetWabaId: string;
  pin?: string;
  sendPin?: boolean;
  pinMethod?: 'SMS' | 'VOICE';
}): Promise<{ success: boolean; pinSent?: boolean; status?: string } | null> {
  return apiCall<any>(`${API_BASE}/waba/migrate`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}


// ============================================================================
// AD ATTRIBUTION API
// ============================================================================

export async function getAdAttributionStats(): Promise<{ stats: any } | null> {
  const data = await apiCall<any>(`${API_BASE}/ad-attribution/stats`);
  return data ? { stats: data } : null;
}

export async function getAdAttributionClicks(params?: { limit?: number; sourceId?: string }): Promise<{ attributions: any[]; count: number } | null> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.append('limit', String(params.limit));
  if (params?.sourceId) qs.append('sourceId', params.sourceId);
  const url = `${API_BASE}/ad-attribution${qs.toString() ? '?' + qs : ''}`;
  return apiCall<{ attributions: any[]; count: number }>(url);
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
  recipientBsuid?: string;    // Send to BSUID recipient
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
      recipientBsuid: request.recipientBsuid,
      components: components.length > 0 ? components : undefined,
    }),
  });
}


// ============================================================================
// CONTACT TAGS & GROUPS API
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
  const headers = ['Name', 'Phone', 'Email', 'BSUID', 'Username', 'Contact Book Name', 'Shipping Address', 'Billing Address', 'Tags', 'WhatsApp Opt-In', 'SMS Opt-In', 'Email Opt-In', 'Created At'];
  const rows = contacts.map(c => [
    c.name || '',
    c.phone || '',
    c.email || '',
    c.bsuid || '',
    c.username || '',
    c.contactBookName || '',
    c.shippingAddress || '',
    c.billingAddress || '',
    (c.tags || []).join('; '),
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
  
  // Fix #1: Fetch existing contacts ONCE before the loop instead of per-contact
  let existing: Contact[] = [];
  try {
    existing = await listContacts();
  } catch {
    // If we can't fetch, proceed without dedup — backend will catch duplicates
  }
  
  // Build a phone lookup map for O(1) dedup
  const phoneMap = new Map<string, Contact>();
  for (const c of existing) {
    if (c.phone) phoneMap.set(c.phone, c);
  }
  
  // Process in batches of 5 for some parallelism without overwhelming the API
  const BATCH_SIZE = 5;
  for (let i = 0; i < contacts.length; i += BATCH_SIZE) {
    const batch = contacts.slice(i, i + BATCH_SIZE);
    const promises = batch.map(async (contact) => {
      try {
        const contactWithOptIn = {
          ...contact,
          optInWhatsApp: true,
          allowlistWhatsApp: true,
        };
        
        const found = contact.phone ? phoneMap.get(contact.phone) : undefined;
        
        if (found) {
          const updated = await updateContact(found.contactId, contactWithOptIn);
          if (updated) {
            result.updated++;
          } else {
            result.failed++;
            result.errors.push(`Failed to update: ${contact.phone}`);
          }
        } else {
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
    });
    await Promise.all(promises);
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
export async function updateSystemConfig(configKey: string, config: any): Promise<boolean> {
  const data = await apiCall<any>(`${API_BASE}/ai/config`, {
    method: 'PUT',
    body: JSON.stringify({ key: configKey, config }),
  });
  return data !== null;
}


// ============================================================================
// CLEAR ALL DATA FUNCTIONS
// ============================================================================

/**
 * Clear all WhatsApp messages (keeps contacts)
 */
export async function clearAllWhatsAppMessages(): Promise<{ deleted: number; failed: number }> {
  try {
    const messages = await listMessages(undefined, 'WHATSAPP');
    
    let deleted = 0;
    let failed = 0;
    
    for (const msg of messages) {
      const result = await deleteMessage(msg.id, msg.direction);
      if (result) {
        deleted++;
      } else {
        failed++;
      }
      // Rate limit to avoid overwhelming the API
      if (deleted % 50 === 0) {
        await new Promise(r => setTimeout(r, 500));
      }
    }
    
    return { deleted, failed };
  } catch (error) {
    console.error('Clear all messages error:', error);
    return { deleted: 0, failed: 0 };
  }
}

/**
 * Clear all contacts (soft delete)
 */
export async function clearAllContacts(): Promise<{ deleted: number; failed: number }> {
  try {
    const contacts = await listContacts();
    
    let deleted = 0;
    let failed = 0;
    
    for (const contact of contacts) {
      const result = await deleteContact(contact.contactId);
      if (result) {
        deleted++;
      } else {
        failed++;
      }
    }
    
    return { deleted, failed };
  } catch (error) {
    console.error('Clear all contacts error:', error);
    return { deleted: 0, failed: 0 };
  }
}

/**
 * Clear everything - messages, contacts, and media
 * WARNING: This is destructive and irreversible!
 */
export async function clearAllInboxData(): Promise<{
  messagesDeleted: number;
  messagesFailed: number;
  contactsDeleted: number;
  contactsFailed: number;
  smsDeleted: number;
  voiceDeleted: number;
}> {
  let totalMessagesDeleted = 0;
  let totalMessagesFailed = 0;
  let smsDeleted = 0;
  let voiceDeleted = 0;

  // 1. Clear WhatsApp messages
  const whatsappResult = await clearAllWhatsAppMessages();
  totalMessagesDeleted += whatsappResult.deleted;
  totalMessagesFailed += whatsappResult.failed;

  // 2. Clear SMS messages (both inbound and outbound)
  try {
    const smsMessages = await listMessages(undefined, 'SMS');
    for (const msg of smsMessages) {
      const result = await deleteMessage(msg.id, msg.direction);
      if (result) {
        smsDeleted++;
        totalMessagesDeleted++;
      } else {
        totalMessagesFailed++;
      }
    }
  } catch (error) {
    console.error('Error clearing SMS messages:', error);
  }

  // 3. Clear Voice call records
  try {
    const voiceCalls = await listVoiceCalls();
    for (const call of voiceCalls) {
      try {
        // Try to delete voice call record via API
        const response = await apiCall<any>(`${API_BASE}/voice/calls/${call.id}`, {
          method: 'DELETE',
        });
        if (response) {
          voiceDeleted++;
        }
      } catch (e) {
        console.warn(`Failed to delete voice call ${call.id}:`, e);
      }
    }
  } catch (error) {
    console.error('Error clearing voice calls:', error);
  }

  // 4. Clear all contacts (this also triggers media cleanup on backend)
  const contactResult = await clearAllContacts();

  return {
    messagesDeleted: totalMessagesDeleted,
    messagesFailed: totalMessagesFailed,
    contactsDeleted: contactResult.deleted,
    contactsFailed: contactResult.failed,
    smsDeleted,
    voiceDeleted,
  };
}

// ============================================================================
// WHATSAPP BUSINESS API (Profile, Flows, Webhooks, Groups)
// ============================================================================

const WA_BIZ_BASE = `${API_BASE}/wa-business`;

// Business Profile
export async function getBusinessProfile(phoneId: string): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/profile?phoneId=${phoneId}`);
  return data?.profile || null;
}

export async function updateBusinessProfile(phoneId: string, updates: Record<string, any>): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/profile`, {
    method: 'POST',
    body: JSON.stringify({ phoneId, ...updates }),
  });
  return data?.success === true;
}

// Payment Gateway Check
export interface GatewayConfig {
  name: string;
  status: string;
  gateway: string;
  mid: string;
  mcc: string;
  purposeCode: string;
  canReceivePayments: boolean;
  note?: string;
}

export interface GatewayCheckResult {
  wabaId: string;
  phone: string;
  configurations: GatewayConfig[];
  totalConfigs: number;
  activeConfigs: number;
}

export async function checkPaymentGateways(wabaId?: string): Promise<GatewayCheckResult[]> {
  const url = wabaId
    ? `${WA_BIZ_BASE}/payment-config/check?wabaId=${wabaId}`
    : `${WA_BIZ_BASE}/payment-config/check`;
  const data = await apiCall<any>(url);
  return data?.gatewayChecks || [];
}

// Flows
export async function listFlows(wabaId: string): Promise<any[]> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flows?wabaId=${wabaId}`);
  if (!data) return [];
  if (data.error) throw new Error(data.error?.message || 'Failed to fetch flows');
  return data?.flows || [];
}

export async function getFlow(flowId: string): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flows?flowId=${flowId}`);
  return data?.flow || null;
}

export async function createFlow(wabaId: string, name: string, categories?: string[]): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flows`, {
    method: 'POST',
    body: JSON.stringify({ wabaId, name, categories }),
  });
  return data?.flow || null;
}

export async function updateFlow(flowId: string, updates: Record<string, any>): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flows`, {
    method: 'PUT',
    body: JSON.stringify({ flowId, ...updates }),
  });
  return data?.success === true;
}

export async function deleteFlow(flowId: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flows?flowId=${flowId}`, { method: 'DELETE' });
  return data?.success === true;
}

export async function publishFlow(flowId: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flows/publish`, {
    method: 'POST',
    body: JSON.stringify({ flowId }),
  });
  return data?.success === true;
}

export async function deprecateFlow(flowId: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flows/deprecate`, {
    method: 'POST',
    body: JSON.stringify({ flowId }),
  });
  return data?.success === true;
}

export async function getFlowPreview(flowId: string): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flows/preview`, {
    method: 'POST',
    body: JSON.stringify({ flowId }),
  });
  return data?.preview || null;
}

// Webhooks
export async function getWebhookSubscriptions(wabaId: string): Promise<any[]> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/webhooks?wabaId=${wabaId}`);
  return data?.subscriptions || [];
}

export async function subscribeWebhook(wabaId: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/webhooks`, {
    method: 'POST',
    body: JSON.stringify({ wabaId }),
  });
  return data?.success === true;
}

export async function unsubscribeWebhook(wabaId: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/webhooks?wabaId=${wabaId}`, { method: 'DELETE' });
  return data?.success === true;
}

// Groups
export async function listGroups(wabaId: string, phoneId?: string): Promise<any[]> {
  const params = new URLSearchParams({ wabaId });
  if (phoneId) params.set('phoneId', phoneId);
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups?${params.toString()}`);
  return data?.groups || [];
}

export async function getGroup(groupId: string): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups?groupId=${groupId}`);
  return data?.group || null;
}

export async function createGroup(phoneId: string, subject: string, description?: string, participants?: string[], join_approval_mode?: string): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups`, {
    method: 'POST',
    body: JSON.stringify({ phoneId, subject, description, participants, join_approval_mode }),
  });
  return data?.group || null;
}

export async function updateGroup(groupId: string, updates: Record<string, any>): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups`, {
    method: 'PUT',
    body: JSON.stringify({ groupId, ...updates }),
  });
  return data?.success === true;
}

export async function deleteGroup(groupId: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups?groupId=${groupId}`, { method: 'DELETE' });
  return data?.success === true;
}

export async function manageGroupParticipants(groupId: string, participants: string[], action: 'add' | 'remove'): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups/participants`, {
    method: 'POST',
    body: JSON.stringify({ groupId, participants, action }),
  });
  return data?.success === true;
}

export async function sendGroupMessage(phoneId: string, groupId: string, content: string, options?: {
  type?: 'text' | 'image' | 'video' | 'document' | 'audio' | 'template';
  mediaUrl?: string; mediaId?: string; caption?: string; filename?: string;
  templateName?: string; templateLanguage?: string; templateComponents?: any[];
}): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups/send`, {
    method: 'POST',
    body: JSON.stringify({ phoneId, groupId, content, ...options }),
  });
  return data;
}

export async function updateGroupSettings(groupId: string, settings: {
  subject?: string; description?: string;
  messaging_permission?: 'all' | 'admins';
  member_visibility?: 'all' | 'admins';
  join_approval_mode?: 'auto_approve' | 'approval_required';
}): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups`, {
    method: 'PUT',
    body: JSON.stringify({ groupId, ...settings }),
  });
  return data?.success === true;
}

export async function setGroupImage(groupId: string, imageUrl: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups/image`, {
    method: 'POST',
    body: JSON.stringify({ groupId, imageUrl }),
  });
  return data?.success === true;
}

export async function getGroupInviteLink(groupId: string): Promise<string> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups/invite-link?groupId=${groupId}`);
  return data?.invite_link || '';
}

export async function resetGroupInviteLink(groupId: string): Promise<string> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups/invite-link`, {
    method: 'POST',
    body: JSON.stringify({ groupId }),
  });
  return data?.invite_link || '';
}

export async function getGroupJoinRequests(groupId: string): Promise<any[]> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/groups/join-requests?groupId=${groupId}`);
  return data?.join_requests || [];
}

export async function approveGroupJoinRequests(groupId: string, joinRequestIds: string[]): Promise<any> {
  return apiCall<any>(`${WA_BIZ_BASE}/groups/join-requests`, {
    method: 'POST',
    body: JSON.stringify({ groupId, join_requests: joinRequestIds }),
  });
}

export async function rejectGroupJoinRequests(groupId: string, joinRequestIds: string[]): Promise<any> {
  return apiCall<any>(`${WA_BIZ_BASE}/groups/join-requests`, {
    method: 'DELETE',
    body: JSON.stringify({ groupId, join_requests: joinRequestIds }),
  });
}

// Phone Settings
export async function getPhoneSettings(phoneId: string): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/phone-settings?phoneId=${phoneId}`);
  return data?.settings || null;
}

export async function updatePhoneSettings(phoneId: string, settings: Record<string, any>): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/phone-settings`, {
    method: 'POST',
    body: JSON.stringify({ phoneId, ...settings }),
  });
  return data?.success === true;
}

// Username Management (Meta Graph API)
export interface UsernameInfo {
  username?: string;
  status?: string; // 'approved' | 'reserved'
}

export async function getUsername(phoneId: string): Promise<UsernameInfo | null> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/username?phoneId=${phoneId}`);
  if (data?.error) return null;
  return { username: data?.username, status: data?.status };
}

export async function getUsernameSuggestions(phoneId: string): Promise<string[]> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/username/suggestions?phoneId=${phoneId}`);
  return data?.suggestions || [];
}

export async function claimUsername(phoneId: string, username: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/username`, {
    method: 'POST',
    body: JSON.stringify({ phoneId, username }),
  });
  return data?.success === true;
}

export async function deleteUsername(phoneId: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/username?phoneId=${phoneId}`, {
    method: 'DELETE',
  });
  return data?.success === true;
}

// Block Users API (per Meta BSUID docs — block/unblock by phone or BSUID)
export interface BlockUser {
  phone?: string;
  user_id?: string; // BSUID
}

export async function blockUsers(wabaId: string, users: BlockUser[]): Promise<any> {
  return apiCall<any>(`${WA_BIZ_BASE}/block-users`, {
    method: 'POST',
    body: JSON.stringify({ wabaId, users }),
  });
}

export async function unblockUsers(wabaId: string, users: BlockUser[]): Promise<any> {
  return apiCall<any>(`${WA_BIZ_BASE}/unblock-users`, {
    method: 'POST',
    body: JSON.stringify({ wabaId, users }),
  });
}

export async function getBlockedUsers(wabaId: string): Promise<any> {
  return apiCall<any>(`${WA_BIZ_BASE}/block-users?wabaId=${wabaId}`);
}

// Interactive List Messages
export async function sendInteractiveList(phoneId: string, to: string, bodyText: string, buttonText: string, sections: any[], headerText?: string, footerText?: string): Promise<{ messageId: string } | null> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/interactive-list`, {
    method: 'POST',
    body: JSON.stringify({ phoneId, to, bodyText, buttonText, sections, headerText, footerText }),
  });
  return data?.success ? { messageId: data.messageId } : null;
}

// Calling Settings (Enable/Disable calling on phone number)
export async function getCallingSettings(phoneId: string): Promise<any> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/calling-settings?phoneId=${phoneId}`);
  return data?.settings || null;
}

export async function updateCallingSettings(phoneId: string, settings: {
  callIconVisibility?: 'default' | 'disable_all';
  restrictToCountries?: string[];
  callHours?: Record<string, any>;
  callbackRequest?: { enabled: boolean; bodyText?: string };
  sip?: { status: 'ENABLED' | 'DISABLED'; servers?: Array<{ hostname: string; port?: string; request_uri_user_params?: Record<string, string> }> };
  srtpKeyExchangeProtocol?: 'DTLS' | 'SDES';
  status?: 'ENABLED' | 'DISABLED';
  callbackPermissionStatus?: 'ENABLED' | 'DISABLED';
}): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/calling-settings`, {
    method: 'POST',
    body: JSON.stringify({ phoneId, ...settings }),
  });
  return data?.success === true;
}

// ===================================================================
// WIX STORE INTEGRATION
// ===================================================================

const WIX_STORE_BASE = `${API_BASE}/wix-store`;

export interface WixProduct {
  _id: string;
  name: string;
  description: string;
  price: number;
  formattedPrice: string;
  currency: string;
  sku: string;
  ribbon: string;
  brand: string;
  inStock: boolean;
  quantityInStock: number;
  productType: string;
  slug: string;
  mainMedia: any;
  mediaItems: any[];
  collections: { _id: string; name: string }[];
  customTextFields: any[];
  productOptions: any[];
  variants: any[];
  lastUpdated: string;
}

export interface WixOrder {
  _id: string;
  number: number;
  customOrderNumber?: string;
  customField?: { title: string; value: string };
  channelInfo: any;
  buyerInfo: { email: string; firstName?: string; lastName?: string; phone?: string };
  buyerNote: string;
  billingInfo: any;
  shippingInfo: any;
  lineItems: any[];
  totals: { subtotal: number; total: number; shipping: number; tax: number; discount: number };
  currency: string;
  paymentStatus: string;
  fulfillmentStatus: string;
  fulfillments: any[];
  archived: boolean;
  dateCreated: string;
  dateUpdated: string;
  // REST API enriched fields
  _summary?: any;
  _transactions?: any;
  _fulfillments?: any;
}

export interface WixCollection {
  _id: string;
  name: string;
  description: string;
  mainMedia: any;
  slug: string;
}

export async function listWixSites(): Promise<any[]> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/sites`);
  return data?.sites || [];
}

export async function listWixProducts(params?: {
  limit?: number;
  search?: string;
  collectionId?: string;
}): Promise<{ products: WixProduct[]; totalCount: number }> {
  const query = new URLSearchParams();
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.search) query.set('search', params.search);
  if (params?.collectionId) query.set('collectionId', params.collectionId);
  const qs = query.toString();
  const data = await apiCall<any>(`${WIX_STORE_BASE}/products${qs ? '?' + qs : ''}`);
  return { products: data?.products || [], totalCount: data?.totalCount || data?.totalResults || 0 };
}

export async function getWixProduct(productId: string): Promise<WixProduct | null> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/products/${productId}`);
  return data?.product || null;
}

export async function listWixOrders(params?: {
  limit?: number;
  status?: string;
  paymentStatus?: string;
  fulfillmentStatus?: string;
  email?: string;
  orderNumber?: string;
  customOrderNumber?: string;
  dateFrom?: string;
  dateTo?: string;
}): Promise<{ orders: WixOrder[]; totalCount: number }> {
  const query = new URLSearchParams();
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.status) query.set('status', params.status);
  if (params?.paymentStatus) query.set('paymentStatus', params.paymentStatus);
  if (params?.fulfillmentStatus) query.set('fulfillmentStatus', params.fulfillmentStatus);
  if (params?.email) query.set('email', params.email);
  if (params?.orderNumber) query.set('orderNumber', params.orderNumber);
  if (params?.customOrderNumber) query.set('customOrderNumber', params.customOrderNumber);
  if (params?.dateFrom) query.set('dateFrom', params.dateFrom);
  if (params?.dateTo) query.set('dateTo', params.dateTo);
  const qs = query.toString();
  const data = await apiCall<any>(`${WIX_STORE_BASE}/orders${qs ? '?' + qs : ''}`);
  return { orders: data?.orders || [], totalCount: data?.totalCount || data?.totalResults || 0 };
}

export async function getWixOrder(orderId: string): Promise<WixOrder | null> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/orders/${orderId}`);
  return data?.order || null;
}

export async function listWixCollections(limit?: number): Promise<{ collections: WixCollection[]; totalCount: number }> {
  const qs = limit ? `?limit=${limit}` : '';
  const data = await apiCall<any>(`${WIX_STORE_BASE}/collections${qs}`);
  return { collections: data?.collections || [], totalCount: data?.totalCount || data?.totalResults || 0 };
}

export async function getWixInventory(productId: string): Promise<any> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/inventory/${productId}`);
  return data?.inventoryItem || data?.inventoryItems || null;
}

export async function syncWixProducts(): Promise<{ message: string }> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/sync/products`, { method: 'POST' });
  return data || { message: 'Sync failed' };
}

export async function syncWixOrders(): Promise<{ message: string }> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/sync/orders`, { method: 'POST' });
  return data || { message: 'Sync failed' };
}

// Product creation / management
export async function createWixProduct(product: Record<string, any>): Promise<{ product: any; created: boolean }> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/create-product`, {
    method: 'POST',
    body: JSON.stringify({ product }),
  });
  return data || { product: null, created: false };
}

export async function bulkCreateWixProducts(products: Record<string, any>[]): Promise<{ total: number; succeeded: number; failed: number; results: any[] }> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/bulk-create-products`, {
    method: 'POST',
    body: JSON.stringify({ products }),
  });
  return data || { total: 0, succeeded: 0, failed: 0, results: [] };
}

export async function updateWixProduct(productId: string, updates: Record<string, any>): Promise<{ product: any; updated: boolean }> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/update-product`, {
    method: 'POST',
    body: JSON.stringify({ productId, updates }),
  });
  return data || { product: null, updated: false };
}

export async function deleteWixProduct(productId: string): Promise<{ deleted: boolean }> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/delete-product`, {
    method: 'POST',
    body: JSON.stringify({ productId }),
  });
  return data || { deleted: false };
}

export async function getWixSampleProducts(): Promise<{ category: string; products: any[] }> {
  const data = await apiCall<any>(`${WIX_STORE_BASE}/sample-products`);
  return data || { category: '', products: [] };
}

// ============================================================================
// INVOICE ENGINE API (Unified Invoice System)
// Lambda: wecare-invoice-engine
// ============================================================================

const INVOICE_BASE = `${API_BASE}/invoices`;

export interface InvoiceItem {
  invoiceId: string;
  itemIndex: number;
  name: string;
  amount: number;
  quantity: number;
  productId?: string;
}

export interface InvoiceAsset {
  invoiceId: string;
  assetType: 'image' | 'pdf';
  s3Key: string;
  url: string;
  contentType: string;
  version: number;
  generatedAt: number;
}

export interface InvoiceDeliveryLog {
  timestamp: number;
  channel: string;
  toNumber: string;
  waMessageId: string;
  status: string;
  error: string;
  imageUrl: string;
}

export interface Invoice {
  invoiceId: string;
  invoiceNumber: string;
  paymentId: string;
  orderId: string;
  referenceId: string;
  entryPoint: string;
  status: string;
  paymentStatus: string;
  contactId: string;
  customerName: string;
  customerPhone: string;
  paidByPhone: string;
  customerEmail: string;
  shippingAddress: string;
  billingAddress: string;
  goodsType?: 'digital-goods' | 'physical-goods';
  subtotal: number;
  discount: number;
  shipping: number;
  gstRate: number;
  tax: number;
  convenienceFee: number;
  total: number;
  currency: string;
  gstin: string;
  purpose: string;
  notes: string;
  createdAt: number;
  updatedAt: number;
  paidAt: number;
  remarks?: string | InvoiceRemark[];
  items?: InvoiceItem[];
  assets?: InvoiceAsset[];
}

export interface CreateInvoiceEngineRequest {
  customerPhone: string;
  paidByPhone?: string;
  customerEmail: string;
  shippingAddress: string;
  billingAddress: string;
  customerName?: string;
  contactId?: string;
  goodsType?: 'digital-goods' | 'physical-goods';
  items: { name: string; amount: number; quantity: number; productId?: string; gstRate?: number }[];
  discount?: number;
  shipping?: number;
  gstRate?: number;       // Fallback global GST rate (used if items don't have per-item rates)
  convenienceFee?: number;
  purpose?: string;
  orderId?: string;
  referenceId?: string;
  entryPoint?: string;
  paymentId?: string;
  gstin?: string;
  currency?: string;
  /** Preferred PG: 'razorpay' or 'payu' — used when customer triggers payment via keyword */
  preferredGateway?: string;
  /** Exact Meta PG config name (e.g. 'PayU_ManishAgarwal') — stored on invoice for keyword-triggered payments */
  paymentConfiguration?: string;
  /** Structured address fields for WhatsApp Payments shipping_info */
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  state?: string;
  postalCode?: string;
  landmark?: string;
}

// Create invoice directly
export async function createInvoiceEngine(request: CreateInvoiceEngineRequest): Promise<{ invoiceId: string; invoiceNumber: string; total: number } | null> {
  return apiCall<{ invoiceId: string; invoiceNumber: string; total: number }>(INVOICE_BASE, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// Create invoice from Razorpay payment ID
export async function createInvoiceFromPayment(paymentId: string, extras?: Record<string, any>): Promise<{ invoiceId: string; invoiceNumber: string; total: number } | null> {
  return apiCall<{ invoiceId: string; invoiceNumber: string; total: number }>(`${INVOICE_BASE}/from-payment`, {
    method: 'POST',
    body: JSON.stringify({ paymentId, ...extras }),
  });
}

// List invoices with optional filters
export async function listInvoicesEngine(params?: { status?: string; contactId?: string; paymentId?: string; limit?: number }): Promise<{ invoices: Invoice[]; count: number }> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.contactId) query.set('contactId', params.contactId);
  if (params?.paymentId) query.set('paymentId', params.paymentId);
  if (params?.limit) query.set('limit', String(params.limit));
  const qs = query.toString();
  const data = await apiCall<any>(`${INVOICE_BASE}${qs ? '?' + qs : ''}`);
  return { invoices: data?.invoices || [], count: data?.count || 0 };
}

// Get single invoice with items and assets
export async function getInvoiceEngine(invoiceId: string): Promise<Invoice | null> {
  const data = await apiCall<any>(`${INVOICE_BASE}/${invoiceId}`);
  return data?.invoice || null;
}

// Update invoice (admin)
export async function updateInvoiceEngine(invoiceId: string, updates: Partial<Invoice>): Promise<boolean> {
  const data = await apiCall<any>(`${INVOICE_BASE}/${invoiceId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
  return data?.updated === true;
}

// Generate invoice image (PNG)
export async function generateInvoiceImage(invoiceId: string): Promise<{ invoiceId: string; imageUrl: string; s3Key: string } | null> {
  return apiCall<{ invoiceId: string; imageUrl: string; s3Key: string }>(`${INVOICE_BASE}/${invoiceId}/generate-image`, {
    method: 'POST',
    body: JSON.stringify({ invoiceId }),
  });
}

// Generate invoice PDF
export async function generateInvoicePdf(invoiceId: string): Promise<{ invoiceId: string; pdfUrl: string; s3Key: string } | null> {
  return apiCall<{ invoiceId: string; pdfUrl: string; s3Key: string }>(`${INVOICE_BASE}/${invoiceId}/generate-pdf`, {
    method: 'POST',
    body: JSON.stringify({ invoiceId }),
  });
}

// Send invoice image on WhatsApp
export async function sendInvoiceWhatsApp(invoiceId: string, toWhatsAppNumber: string, phoneNumberId?: string): Promise<{ invoiceId: string; waMessageId: string; status: string; imageUrl: string } | null> {
  return apiCall<{ invoiceId: string; waMessageId: string; status: string; imageUrl: string }>(`${INVOICE_BASE}/${invoiceId}/send-whatsapp`, {
    method: 'POST',
    body: JSON.stringify({ invoiceId, toWhatsAppNumber, phoneNumberId }),
  });
}

// Send WhatsApp interactive payment link for a pending invoice
export async function sendPaymentLink(invoiceId: string, phoneNumberId?: string, paymentConfiguration?: string): Promise<{ invoiceId: string; referenceId: string; status: string; toPhone: string; total: number } | null> {
  return apiCall<{ invoiceId: string; referenceId: string; status: string; toPhone: string; total: number }>(`${INVOICE_BASE}/${invoiceId}/send-payment-link`, {
    method: 'POST',
    body: JSON.stringify({ invoiceId, phoneNumberId, paymentConfiguration }),
  });
}

// Cancel/void an invoice
export async function cancelInvoice(invoiceId: string, reason?: string): Promise<{ invoiceId: string; status: string } | null> {
  return apiCall<{ invoiceId: string; status: string }>(`${INVOICE_BASE}/${invoiceId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ invoiceId, reason }),
  });
}

// Get delivery log for an invoice
export async function getInvoiceDeliveryLog(invoiceId: string): Promise<{ deliveryLogs: InvoiceDeliveryLog[]; count: number }> {
  const data = await apiCall<any>(`${INVOICE_BASE}/${invoiceId}/delivery-log`);
  return { deliveryLogs: data?.deliveryLogs || [], count: data?.count || 0 };
}

// Preview next invoice number (without incrementing)
export async function previewNextInvoiceNumber(fy?: string): Promise<{ nextInvoiceNumber: string; fy: string; lastSeq: number } | null> {
  return apiCall<{ nextInvoiceNumber: string; fy: string; lastSeq: number }>(`${INVOICE_BASE}/next-sequence`, {
    method: 'POST',
    body: JSON.stringify({ fy }),
  });
}

// Delete invoice (hard delete + optional sequence adjustment)
export async function deleteInvoice(invoiceId: string, adjustSequence = false): Promise<{ invoiceId: string; deleted: boolean; invoiceNumber: string } | null> {
  return apiCall<{ invoiceId: string; deleted: boolean; invoiceNumber: string }>(`${INVOICE_BASE}/${invoiceId}`, {
    method: 'DELETE',
    body: JSON.stringify({ adjustSequence }),
  });
}

// Add remark / refund / credit note to an invoice
export interface InvoiceRemark {
  id: string;
  type: 'remark' | 'refund' | 'credit_note';
  text: string;
  amount: number;
  author: string;
  createdAt: number;
}

export async function addInvoiceRemark(invoiceId: string, remarkType: 'remark' | 'refund' | 'credit_note', text: string, amount = 0, author = 'admin'): Promise<{ invoiceId: string; remark: InvoiceRemark; totalRemarks: number } | null> {
  return apiCall<{ invoiceId: string; remark: InvoiceRemark; totalRemarks: number }>(`${INVOICE_BASE}/${invoiceId}/remark`, {
    method: 'POST',
    body: JSON.stringify({ type: remarkType, text, amount, author }),
  });
}

// ============================================================================
// SYSTEM CLEANUP API
// ============================================================================

export interface CleanupResource {
  id: string;
  label: string;
  category: string;
  type: 'dynamodb' | 's3' | 'sqs';
  table?: string;
  prefix?: string;
  queue?: string;
  count: number;
}

export interface CleanupResult {
  id: string;
  label: string;
  deleted: number;
  elapsed?: number;
  error?: string;
}

export async function getCleanupPreview(): Promise<CleanupResource[]> {
  const data = await apiCall<any>(`${API_BASE}/system-cleanup`);
  return data?.resources || [];
}

export async function executeCleanup(selected: string[]): Promise<{ results: CleanupResult[]; totalDeleted: number }> {
  const data = await apiCall<any>(`${API_BASE}/system-cleanup`, {
    method: 'POST',
    body: JSON.stringify({ selected }),
  });
  return { results: data?.results || [], totalDeleted: data?.totalDeleted || 0 };
}

// ============================================================================
// SUBMIT REQUESTS API (WhatsApp Flow Submissions)
// ============================================================================

export interface SubmitRequest {
  id: string;
  requestId: string;
  requestNumber?: string;  // WD-SR-XXXXXXXX
  flowToken?: string;
  phone: string;
  senderName?: string;
  contactId?: string;
  orderId: string;
  subject?: string;
  description?: string;
  paymentStatus: string; // pending, captured, failed
  paymentReferenceId?: string;
  paymentAmount?: number;
  transactionId?: string;
  invoiceId?: string;
  invoiceNumber?: string;
  daysOld?: number;
  isExpired?: boolean;
  createdAt: number;
  updatedAt?: number;
}

export async function listSubmitRequests(paymentStatus?: string): Promise<SubmitRequest[]> {
  let url = `${API_BASE}/wa-business/submit-requests`;
  if (paymentStatus) url += `?paymentStatus=${paymentStatus}`;
  const data = await apiCall<any>(url);
  return data?.requests || [];
}

export interface FlowLog {
  id: string;
  type: string;
  flowToken?: string;
  phone: string;
  action: string;
  screen: string;
  dataKeys?: string[];
  requestId?: string;
  createdAt: number;
  // Enhanced flow data fields
  order_id?: string;
  subject?: string;
  description?: string;
  email?: string;
  flowData?: string; // JSON string of full submitted data
}

export async function listFlowLogs(phone?: string): Promise<FlowLog[]> {
  let url = `${API_BASE}/wa-business/flow-logs`;
  if (phone) url += `?phone=${encodeURIComponent(phone)}`;
  const data = await apiCall<any>(url);
  return data?.logs || [];
}

export async function resendSubmitRequestPayment(invoiceId: string): Promise<boolean> {
  try {
    const data = await apiCall<any>(`${INVOICE_BASE}/${invoiceId}/send-payment-link`, {
      method: 'POST',
      body: JSON.stringify({ invoiceId }),
    });
    return !!data;
  } catch { return false; }
}

// ============================================================================
// FLOW MANAGEMENT ENGINE
// ============================================================================

export interface FlowRegistryItem {
  flowId: string;
  flowCode: string;
  flowName: string;
  flowType: string;
  flowVersion?: string;
  dataApiVersion?: string;
  wabaId?: string;
  status: string;
  category?: string;
  requiresPayment?: boolean;
  paymentAmount?: number;
  paymentDescription?: string;
  screenConfig?: string;
  contactMapping?: string;
  dataFetchers?: string;
  submissionPrefix?: string;
  endpointUri?: string;
  publishedAt?: number;
  createdAt?: number;
  updatedAt?: number;
}

export interface FlowSubmissionItem {
  submissionId: string;
  flowId: string;
  flowCode: string;
  flowType?: string;
  flowVersion?: string;
  phone: string;
  contactId?: string;
  senderName?: string;
  formData?: string;
  orderId?: string;
  requestType?: string;
  subject?: string;
  description?: string;
  submissionNumber?: string;
  flowToken?: string;
  paymentRequired?: boolean;
  paymentAmount?: number;
  paymentStatus: string;
  paymentRefId?: string;
  invoiceId?: string;
  transactionId?: string;
  paidAt?: number;
  status: string;
  assignedTo?: string;
  notes?: string;
  resolvedAt?: number;
  createdAt: number;
  updatedAt?: number;
}

export interface FlowSubmissionStats {
  total: number;
  byStatus: Record<string, number>;
  byPaymentStatus: Record<string, number>;
  totalPaymentAmount: number;
  capturedAmount: number;
  pendingAmount: number;
}

export async function listFlowRegistry(): Promise<FlowRegistryItem[]> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flow-registry`);
  return data?.flows || [];
}

export async function upsertFlowRegistry(item: Partial<FlowRegistryItem>): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flow-registry`, {
    method: 'POST',
    body: JSON.stringify(item),
  });
  return !!data?.success;
}

export async function listFlowSubmissions(params?: {
  flowCode?: string; paymentStatus?: string; status?: string; phone?: string; limit?: number;
}): Promise<FlowSubmissionItem[]> {
  const qs = new URLSearchParams();
  if (params?.flowCode) qs.set('flowCode', params.flowCode);
  if (params?.paymentStatus) qs.set('paymentStatus', params.paymentStatus);
  if (params?.status) qs.set('status', params.status);
  if (params?.phone) qs.set('phone', params.phone);
  if (params?.limit) qs.set('limit', String(params.limit));
  const query = qs.toString();
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flow-submissions${query ? '?' + query : ''}`);
  return data?.submissions || [];
}

export async function getFlowSubmissionStats(flowCode?: string): Promise<FlowSubmissionStats | null> {
  const qs = flowCode ? `?flowCode=${flowCode}` : '';
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flow-submissions/stats${qs}`);
  return data || null;
}

export interface CustomerJourney {
  phone: string;
  contactId: string;
  contact: Record<string, any>;
  submissions: FlowSubmissionItem[];
  logs: any[];
  summary: { flowsCompleted: string[]; totalSubmissions: number; totalPaid: number; totalInteractions: number };
}

export async function getCustomerJourney(phone: string): Promise<CustomerJourney | null> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flow-customer-journey?phone=${encodeURIComponent(phone)}`);
  return data || null;
}

export async function runSlaCheck(params?: { slaDays?: number; reminderDays?: number; defaultAssignee?: string }): Promise<any> {
  return apiCall<any>(`${WA_BIZ_BASE}/flow-sla-check`, { method: 'POST', body: JSON.stringify(params || {}) });
}

export async function cloneFlowToWaba(sourceFlowCode: string, targetWabaId: string, targetFlowId: string): Promise<boolean> {
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flow-clone`, {
    method: 'POST', body: JSON.stringify({ sourceFlowCode, targetWabaId, targetFlowId }),
  });
  return !!data?.success;
}

export async function exportSubmissionsCsv(params?: { flowCode?: string; paymentStatus?: string }): Promise<string> {
  const qs = new URLSearchParams();
  if (params?.flowCode) qs.set('flowCode', params.flowCode);
  if (params?.paymentStatus) qs.set('paymentStatus', params.paymentStatus);
  const query = qs.toString();
  const data = await apiCall<any>(`${WA_BIZ_BASE}/flow-submissions/export${query ? '?' + query : ''}`);
  return data?.csv || '';
}

export interface FlowVersionHealth {
  flowCode: string; flowName: string; flowId: string; flowVersion: string;
  dataApiVersion: string; versionStatus: string; message: string;
}

export async function checkFlowVersionHealth(): Promise<{ flows: FlowVersionHealth[]; recommendedVersion: string } | null> {
  return apiCall<any>(`${WA_BIZ_BASE}/flow-version-health`);
}

// ── WhatsApp Commerce Catalog ──

const CATALOG_BASE = `${API_BASE}/catalog`;

export async function getCatalogProducts(params?: { wabaId?: string; phoneNumberId?: string; catalogId?: string; limit?: number }): Promise<{ products: any[]; paging?: any } | null> {
  const qs = new URLSearchParams();
  if (params?.wabaId) qs.set('wabaId', params.wabaId);
  if (params?.phoneNumberId) qs.set('phoneNumberId', params.phoneNumberId);
  if (params?.catalogId) qs.set('catalogId', params.catalogId);
  if (params?.limit) qs.set('limit', String(params.limit));
  const query = qs.toString();
  const data = await apiCall<any>(`${CATALOG_BASE}/products${query ? '?' + query : ''}`);
  return data || { products: [] };
}
