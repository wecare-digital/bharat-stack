/**
 * SEO Platform API Client
 * Connects to the wecare-seo-platform backend (FastAPI)
 */
import { authFetch } from './client';
import { API_BASE } from '../config/constants';

const SEO_API = process.env.NEXT_PUBLIC_SEO_API_URL || '';

function getToken (): string | null {
  if ( typeof window === 'undefined' ) return null;
  return localStorage.getItem( 'seo_token' );
}

async function seoFetch<T> ( path: string, opts: RequestInit = {} ): Promise<T> {
  if ( !SEO_API )
  {
    throw new Error( 'SEO API URL not configured. Set NEXT_PUBLIC_SEO_API_URL in .env.local' );
  }
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...( token ? { Authorization: `Bearer ${token}` } : {} ),
    ...( opts.headers as Record<string, string> || {} ),
  };
  const res = await fetch( `${SEO_API}${path}`, { ...opts, headers } );
  if ( !res.ok )
  {
    const err = await res.json().catch( () => ( { detail: res.statusText } ) );
    throw new Error( err.detail || res.statusText );
  }
  return res.json();
}

// Auth
export const seoLogin = ( email: string, password: string ) =>
  seoFetch<{ access_token: string; user: any }>( '/api/auth/login', {
    method: 'POST', body: JSON.stringify( { email, password } ),
  } );

export const seoRegister = ( email: string, password: string, name?: string ) =>
  seoFetch<{ access_token: string; user: any }>( '/api/auth/register', {
    method: 'POST', body: JSON.stringify( { email, password, name } ),
  } );

// Dashboard
export const getDashboardStats = ( days = 30 ) =>
  seoFetch<any>( `/api/dashboard/summary?days=${days}` );

// Pages
export const listPages = ( params: Record<string, string> = {} ) => {
  const qs = new URLSearchParams( params ).toString();
  return seoFetch<any[]>( `/api/pages/?${qs}` );
};

export const getPage = ( id: number ) => seoFetch<any>( `/api/pages/${id}` );

export const updatePageSeo = ( id: number, data: any ) =>
  seoFetch<any>( `/api/pages/${id}/seo`, { method: 'PATCH', body: JSON.stringify( data ) } );

export const getPageCounts = () => seoFetch<any>( '/api/pages/count' );

export const getPageInspections = ( id: number ) =>
  seoFetch<any[]>( `/api/pages/${id}/inspections` );

// Crawl
export const triggerCrawl = ( site_domain: string, seed_urls?: string[] ) =>
  seoFetch<any>( '/api/crawl/start', { method: 'POST', body: JSON.stringify( { site_domain, seed_urls } ) } );

export const getCrawlHistory = () => seoFetch<any[]>( '/api/crawl/history' );

// Inspection
export const bulkInspect = ( page_ids: number[] ) =>
  seoFetch<any>( '/api/inspect/bulk', { method: 'POST', body: JSON.stringify( { page_ids } ) } );

// Issues
export const listIssues = ( params: Record<string, string> = {} ) => {
  const qs = new URLSearchParams( params ).toString();
  return seoFetch<any[]>( `/api/issues/?${qs}` );
};

export const getIssuesSummary = () => seoFetch<any>( '/api/issues/summary' );

export const resolveIssue = ( id: number ) =>
  seoFetch<any>( `/api/issues/${id}/resolve`, { method: 'POST' } );

// Analytics
export const getSearchConsoleAnalytics = ( days = 30 ) =>
  seoFetch<any>( `/api/analytics/search-console?days=${days}` );

export const getAnalyticsByPage = ( page_url: string, days = 30 ) =>
  seoFetch<any[]>( `/api/analytics/by-page?page_url=${encodeURIComponent( page_url )}&days=${days}` );

export const getHighImpressionLowCtr = () =>
  seoFetch<any[]>( '/api/analytics/high-impression-low-ctr' );

// Tracking
export const getTrackingByPage = ( pageId: number ) =>
  seoFetch<any>( `/api/tracking/by-page/${pageId}` );

export const getTrackingCoverage = () => seoFetch<any>( '/api/tracking/coverage' );

// Schema
export const getSchemaByPage = ( pageId: number ) =>
  seoFetch<any>( `/api/schema/by-page/${pageId}` );

export const updateSchema = ( pageId: number, data: any ) =>
  seoFetch<any>( `/api/schema/by-page/${pageId}`, { method: 'PATCH', body: JSON.stringify( data ) } );

export const regenerateSchema = ( pageId: number ) =>
  seoFetch<any>( `/api/schema/regenerate/${pageId}`, { method: 'POST' } );

export const getSchemaCoverage = () => seoFetch<any>( '/api/schema/coverage' );

// Properties
export const listProperties = () => seoFetch<any[]>( '/api/properties/' );

export const syncProperties = () =>
  seoFetch<any>( '/api/properties/sync', { method: 'POST' } );

// Sitemaps
export const submitSitemap = ( url: string, property_id: number ) =>
  seoFetch<any>( '/api/sitemaps/submit', { method: 'POST', body: JSON.stringify( { url, property_id } ) } );

// Health
export const seoHealth = () => seoFetch<any>( '/api/health' );

/** Authenticated client for the Admin-only SEO tools Lambda. */
export function seoToolsFetch ( path: string, init: RequestInit = {} ): Promise<Response> {
  const route = path.replace( /^\/+/, '' );
  return authFetch( `${API_BASE}/seo-tools/${route}`, init );
}

/* ------------------------------------------------------------------------- *
 * Blog source intake (Admin-only, /api/seo-tools/blog-sources*)
 *
 * The shapes below mirror `amplify/functions/operations/seo-tools/blog_sources.py`
 * and `blog_draft.py`. They are written out rather than typed as `any` because the
 * admin page branches on `status`, `alreadyKnown` and `uploadUrl`, and a silent
 * rename on the Python side should show up as a type error here rather than as an
 * upload that appears to succeed and moves nothing.
 *
 * Note what is NOT here: the presigned PUT. That request goes straight to S3 and
 * must not carry a Cognito Authorization header, so it is a bare `fetch` at the
 * call site rather than anything routed through `seoToolsFetch`.
 * ------------------------------------------------------------------------- */

/** One source as the list route projects it. Never carries the extracted text. */
export interface BlogSourceView {
  sourceId: string;
  sourceType: string;
  sourceRef: string;
  sourceSha256: string;
  /**
   * The apex URL of an uploaded PDF, or `''`.
   *
   * `blog_sources.source_url` returns `''` rather than a URL that would 403, so a prefix
   * moved back under the gated root degrades to no link instead of a dead one. Treat an
   * empty string as "there is nothing to open", never as a bug.
   */
  sourceUrl: string;
  status: string;
  category: string;
  articleClass: string;
  sourceTitle: string;
  sourceDate: string;
  sourcePages: number;
  sourceBytes: number;
  extractedChars: number;
  extractedWords: number;
  contentSha256: string;
  slug: string;
  title: string;
  articleStatus: string;
  aiDraftStatus: string;
  gateBlocking: string[];
  gateReview: string[];
  error: string;
  createdAt: string;
  updatedAt: string;
}

/** The gate's verdict on a proposed article. `humanGatesOutstanding` is why it cannot publish. */
export interface BlogDraftAssessment {
  status: string;
  words: number;
  blocking: string[];
  review: string[];
  humanGatesOutstanding: string[];
}

export interface BlogAiDraft {
  status: string;
  model: string;
  proposedAt: string;
  proposedBy: string;
  notes: string;
  inputTokens: number;
  outputTokens: number;
  proposal: Record<string, unknown>;
  assessment: BlogDraftAssessment;
}

/** The single-source route adds the extract and the draft to the list projection. */
export interface BlogSourceDetail extends BlogSourceView {
  sourceExtract: string;
  draftRecord: Record<string, unknown>;
  aiDraft: BlogAiDraft | Record<string, never>;
}

export interface BlogSourcesResponse {
  ok: boolean;
  categories: string[];
  articleClasses: string[];
  humanGates: string[];
  /** False when ENABLE_BEDROCK_ASSIST is off, in which case blog-draft refuses. */
  aiDraftEnabled: boolean;
  maxSourceBytes: number;
  total: number;
  byStatus: Record<string, number>;
  byCategory: Record<string, number>;
  pending: number;
  extracted: number;
  failed: number;
  sources: BlogSourceView[];
}

export interface BlogSourceRegisterEntry {
  sourceType: 'pdf' | 'url';
  fileName?: string;
  sha256?: string;
  bytes?: number;
  url?: string;
  category?: string;
  articleClass?: string;
}

export interface BlogSourceRegisterRequest {
  category: string;
  articleClass: string;
  sources: BlogSourceRegisterEntry[];
}

/** One registration outcome. `uploadUrl` is empty for a URL and for an already-known source. */
export interface BlogSourceRegistration {
  sourceId: string;
  sourceRef: string;
  sourceType: string;
  status: string;
  alreadyKnown: boolean;
  uploadUrl: string;
  expiresInSeconds?: number;
}

export interface BlogSourceRegisterResponse {
  ok: boolean;
  sources: BlogSourceRegistration[];
  bucket: string;
}

export interface BlogSourceConfirmResponse {
  ok: boolean;
  confirmed: string[];
  /** Registered, but `head_object` found no bytes — the PUT never landed. */
  missingUpload: string[];
  unknownSourceId: string[];
  workerStarted: boolean;
}

export interface BlogSourceRetryResponse {
  ok: boolean;
  sourceId: string;
  status: string;
  workerStarted: boolean;
}

export interface BlogDraftResponse {
  ok: boolean;
  sourceId: string;
  aiDraft: BlogAiDraft;
  /** Always false coming out of a model call — no field it writes can set a human gate. */
  readyToPublish: boolean;
  note: string;
}

export interface BlogDraftAcceptResponse {
  ok: boolean;
  sourceId: string;
  articleStatus: string;
  blocking: string[];
  review: string[];
  humanGatesOutstanding: string[];
  readyToPublish: boolean;
}

/**
 * JSON over `seoToolsFetch`, raising on a transport failure OR on `ok: false`.
 *
 * The handler answers a rejected request with HTTP 400 and `{ ok: false, error }`, so
 * checking only `response.ok` would swallow the message the operator needs — which for
 * this surface is usually the specific validation the backend refused on.
 */
async function seoToolsJson<T> ( path: string, init: RequestInit = {} ): Promise<T> {
  const response = await seoToolsFetch( path, init );
  const payload = await response.json().catch( () => ( {} ) ) as T & { ok?: boolean; error?: string };
  if ( !response.ok || payload.ok === false )
  {
    throw new Error( payload.error || response.statusText || `seo-tools/${path} failed` );
  }
  return payload;
}

/** Every source with its status, plus the enums and flags the page renders against. */
export const listBlogSources = () => seoToolsJson<BlogSourcesResponse>( 'blog-sources' );

/** One source including its extract and draft. Split out because the extract is large. */
export const getBlogSource = ( sourceId: string ) =>
  seoToolsJson<{ ok: boolean; source: BlogSourceDetail }>(
    `blog-sources/${encodeURIComponent( sourceId )}` );

/** Register sources and get one presigned PUT per PDF. No bytes are sent by this call. */
export const registerBlogSources = ( body: BlogSourceRegisterRequest ) =>
  seoToolsJson<BlogSourceRegisterResponse>( 'blog-sources', {
    method: 'POST', body: JSON.stringify( body ),
  } );

/** Tell the backend the bytes arrived. It verifies each key itself, then starts the worker. */
export const confirmBlogSources = ( sourceIds: string[] ) =>
  seoToolsJson<BlogSourceConfirmResponse>( 'blog-sources/confirm', {
    method: 'POST', body: JSON.stringify( { sourceIds } ),
  } );

/** Put a failed source back in the queue. */
export const retryBlogSource = ( sourceId: string ) =>
  seoToolsJson<BlogSourceRetryResponse>( 'blog-sources/retry', {
    method: 'POST', body: JSON.stringify( { sourceId } ),
  } );

/** Ask the model for an article. A proposal only — it cannot reach READY_TO_PUBLISH. */
export const proposeBlogDraft = ( sourceId: string ) =>
  seoToolsJson<BlogDraftResponse>( 'blog-draft', {
    method: 'POST', body: JSON.stringify( { sourceId } ),
  } );

/** Accept a proposal, with a human's edits, as the working draft. Still not an approval. */
export const acceptBlogDraft = ( sourceId: string, edits: Record<string, unknown> ) =>
  seoToolsJson<BlogDraftAcceptResponse>( 'blog-draft-accept', {
    method: 'POST', body: JSON.stringify( { sourceId, edits } ),
  } );
