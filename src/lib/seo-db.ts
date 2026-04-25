/**
 * SEO Audit Database — JSON file storage for pilot phase.
 * Stores audit results, AI logs, and automation settings.
 * Migrate to DynamoDB after pilot succeeds.
 */
import fs from 'fs';
import path from 'path';

const DATA_DIR = path.join(process.cwd(), '.seo-data');

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function readJson<T>(file: string, fallback: T): T {
  ensureDir();
  const fp = path.join(DATA_DIR, file);
  if (!fs.existsSync(fp)) return fallback;
  try { return JSON.parse(fs.readFileSync(fp, 'utf-8')); }
  catch { return fallback; }
}

function writeJson(file: string, data: any) {
  ensureDir();
  fs.writeFileSync(path.join(DATA_DIR, file), JSON.stringify(data, null, 2));
}

// ── BlogSEOAudit ──

export interface BlogSEOAudit {
  id: string;
  blogPostId: string;
  blogSlug: string;
  blogTitle: string;
  pageType: 'blog' | 'page' | 'product' | 'system';
  currentSeoTitle: string;
  suggestedSeoTitle: string;
  currentMetaDescription: string;
  suggestedMetaDescription: string;
  focusKeyword: string;
  secondaryKeywords: string[];
  suggestedTags: string[];
  suggestedJsonLd: any;
  internalLinkSuggestions: any[];
  imageAltSuggestions: any[];
  seoScoreBefore: number;
  seoScoreAfter: number;
  scoreBreakdown: any;
  warnings: string[];
  fullAiResponse: any;
  aiProvider: string;
  aiModel: string;
  status: 'draft' | 'pending_review' | 'approved' | 'applied' | 'rejected';
  createdAt: string;
  updatedAt: string;
  appliedAt?: string;
  reviewedBy?: string;
}

export function listAudits(): BlogSEOAudit[] {
  return readJson<BlogSEOAudit[]>('audits.json', []);
}

export function getAudit(id: string): BlogSEOAudit | undefined {
  return listAudits().find(a => a.id === id);
}

export function getAuditBySlug(slug: string): BlogSEOAudit | undefined {
  const audits = listAudits();
  return audits.filter(a => a.blogSlug === slug).sort((a, b) =>
    new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )[0];
}

export function saveAudit(audit: BlogSEOAudit) {
  const audits = listAudits();
  const idx = audits.findIndex(a => a.id === audit.id);
  if (idx >= 0) audits[idx] = audit;
  else audits.push(audit);
  writeJson('audits.json', audits);
}

export function updateAuditStatus(id: string, status: BlogSEOAudit['status'], reviewedBy?: string): BlogSEOAudit | null {
  const audits = listAudits();
  const audit = audits.find(a => a.id === id);
  if (!audit) return null;
  audit.status = status;
  audit.updatedAt = new Date().toISOString();
  if (reviewedBy) audit.reviewedBy = reviewedBy;
  if (status === 'applied') audit.appliedAt = new Date().toISOString();
  writeJson('audits.json', audits);
  return audit;
}

// ── AILog ──

export interface AILog {
  id: string;
  blogPostId: string;
  blogSlug: string;
  requestPayload: any;
  responsePayload: any;
  inputTokens: number;
  outputTokens: number;
  costEstimate: number;
  provider: string;
  model: string;
  status: 'success' | 'error';
  errorMessage?: string;
  durationMs: number;
  createdAt: string;
}

export function listLogs(): AILog[] {
  return readJson<AILog[]>('ai-logs.json', []);
}

export function saveLog(log: AILog) {
  const logs = listLogs();
  logs.push(log);
  writeJson('ai-logs.json', logs);
}

// ── AutomationSettings ──

export interface AutomationSettings {
  autoRunForFutureBlogs: boolean;
  requireManualApproval: boolean;
  aiProvider: string;
  modelName: string;
  maxTitleLength: number;
  maxMetaDescriptionLength: number;
  maxTags: number;
  lastRunAt?: string;
}

const DEFAULT_SETTINGS: AutomationSettings = {
  autoRunForFutureBlogs: true,
  requireManualApproval: true,
  aiProvider: 'aws-bedrock',
  modelName: 'anthropic.claude-opus-4-6-v1',
  maxTitleLength: 60,
  maxMetaDescriptionLength: 160,
  maxTags: 10,
};

export function getSettings(): AutomationSettings {
  return readJson<AutomationSettings>('settings.json', DEFAULT_SETTINGS);
}

export function updateSettings(updates: Partial<AutomationSettings>) {
  const settings = { ...getSettings(), ...updates };
  writeJson('settings.json', settings);
  return settings;
}
