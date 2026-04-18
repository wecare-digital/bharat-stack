/**
 * SEO Platform API Client
 * Connects to the wecare-seo-platform backend (FastAPI)
 */

const SEO_API = process.env.NEXT_PUBLIC_SEO_API_URL || 'http://localhost:8000';

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('seo_token');
}

async function seoFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(opts.headers as Record<string, string> || {}),
  };
  const res = await fetch(`${SEO_API}${path}`, { ...opts, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// Auth
export const seoLogin = (email: string, password: string) =>
  seoFetch<{ access_token: string; user: any }>('/api/auth/login', {
    method: 'POST', body: JSON.stringify({ email, password }),
  });

export const seoRegister = (email: string, password: string, name?: string) =>
  seoFetch<{ access_token: string; user: any }>('/api/auth/register', {
    method: 'POST', body: JSON.stringify({ email, password, name }),
  });

// Dashboard
export const getDashboardStats = (days = 30) =>
  seoFetch<any>(`/api/dashboard/summary?days=${days}`);

// Pages
export const listPages = (params: Record<string, string> = {}) => {
  const qs = new URLSearchParams(params).toString();
  return seoFetch<any[]>(`/api/pages/?${qs}`);
};

export const getPage = (id: number) => seoFetch<any>(`/api/pages/${id}`);

export const updatePageSeo = (id: number, data: any) =>
  seoFetch<any>(`/api/pages/${id}/seo`, { method: 'PATCH', body: JSON.stringify(data) });

export const getPageCounts = () => seoFetch<any>('/api/pages/count');

export const getPageInspections = (id: number) =>
  seoFetch<any[]>(`/api/pages/${id}/inspections`);

// Crawl
export const triggerCrawl = (site_domain: string, seed_urls?: string[]) =>
  seoFetch<any>('/api/crawl/start', { method: 'POST', body: JSON.stringify({ site_domain, seed_urls }) });

export const getCrawlHistory = () => seoFetch<any[]>('/api/crawl/history');

// Inspection
export const bulkInspect = (page_ids: number[]) =>
  seoFetch<any>('/api/inspect/bulk', { method: 'POST', body: JSON.stringify({ page_ids }) });

// Issues
export const listIssues = (params: Record<string, string> = {}) => {
  const qs = new URLSearchParams(params).toString();
  return seoFetch<any[]>(`/api/issues/?${qs}`);
};

export const getIssuesSummary = () => seoFetch<any>('/api/issues/summary');

export const resolveIssue = (id: number) =>
  seoFetch<any>(`/api/issues/${id}/resolve`, { method: 'POST' });

// Analytics
export const getSearchConsoleAnalytics = (days = 30) =>
  seoFetch<any>(`/api/analytics/search-console?days=${days}`);

export const getAnalyticsByPage = (page_url: string, days = 30) =>
  seoFetch<any[]>(`/api/analytics/by-page?page_url=${encodeURIComponent(page_url)}&days=${days}`);

export const getHighImpressionLowCtr = () =>
  seoFetch<any[]>('/api/analytics/high-impression-low-ctr');

// Tracking
export const getTrackingByPage = (pageId: number) =>
  seoFetch<any>(`/api/tracking/by-page/${pageId}`);

export const getTrackingCoverage = () => seoFetch<any>('/api/tracking/coverage');

// Schema
export const getSchemaByPage = (pageId: number) =>
  seoFetch<any>(`/api/schema/by-page/${pageId}`);

export const updateSchema = (pageId: number, data: any) =>
  seoFetch<any>(`/api/schema/by-page/${pageId}`, { method: 'PATCH', body: JSON.stringify(data) });

export const regenerateSchema = (pageId: number) =>
  seoFetch<any>(`/api/schema/regenerate/${pageId}`, { method: 'POST' });

export const getSchemaCoverage = () => seoFetch<any>('/api/schema/coverage');

// Properties
export const listProperties = () => seoFetch<any[]>('/api/properties/');

export const syncProperties = () =>
  seoFetch<any>('/api/properties/sync', { method: 'POST' });

// Sitemaps
export const submitSitemap = (url: string, property_id: number) =>
  seoFetch<any>('/api/sitemaps/submit', { method: 'POST', body: JSON.stringify({ url, property_id }) });

// Health
export const seoHealth = () => seoFetch<any>('/api/health');
