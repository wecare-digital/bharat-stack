/**************************************************************
 * backend/pinger.js
 * Periodic SEO/Discovery + Store API health checks
 * With concurrency pooling, staggered delays, and retries
 **************************************************************/
import { fetch } from 'wix-fetch';

const SITE_BASE     = 'https://www.wecare.digital';
const JOB_TAG       = 'pinger';
const CONCURRENCY   = 5;             // reduced from 10 to avoid 429s
const RETRIES       = 2;
const RETRY_BACKOFF = 800;           // ms; linear backoff (increased)
const STAGGER_MS    = 80;            // delay between dispatching requests

function buildTargets() {
  return [
    // Core SEO plumbing
    `${SITE_BASE}/_functions/robots`,
    `${SITE_BASE}/_functions/smindex`,
    `${SITE_BASE}/_functions/sitemap`,
    `${SITE_BASE}/_functions/smextra`,
    `${SITE_BASE}/_functions/smtxt`,

    // AI / discovery feeds
    `${SITE_BASE}/_functions/llms`,
    `${SITE_BASE}/_functions/llmslong`,
    `${SITE_BASE}/_functions/llmstxt`,
    `${SITE_BASE}/_functions/aiindex`,
    `${SITE_BASE}/_functions/siteinfo`,
    `${SITE_BASE}/_functions/discovery`,

    // FAQ / inspectors
    `${SITE_BASE}/_functions/faq`,
    `${SITE_BASE}/_functions/pagemeta?url=${encodeURIComponent(`${SITE_BASE}/`)}`,
    `${SITE_BASE}/_functions/pagehead?url=${encodeURIComponent(`${SITE_BASE}/`)}`,
    `${SITE_BASE}/_functions/seohead?path=/`,
    `${SITE_BASE}/_functions/seohead?path=/blog/example-slug&relaxed=1`,
    `${SITE_BASE}/_functions/canonicalize?url=${encodeURIComponent(`${SITE_BASE}/?utm_source=x`)}`,

    // Keywords & diagnostics
    `${SITE_BASE}/_functions/seoerrors`,
    `${SITE_BASE}/_functions/keywordscloud`,
    `${SITE_BASE}/_functions/keywordscommon`,
    `${SITE_BASE}/_functions/keywordsrelated`,
    `${SITE_BASE}/_functions/keywordsglobal`,
    `${SITE_BASE}/_functions/keywordsmeta`,

    // RSS
    `${SITE_BASE}/_functions/rss`,
    `${SITE_BASE}/_functions/rssblog`,
    `${SITE_BASE}/_functions/rssproducts`,

    // Store API endpoints (new)
    `${SITE_BASE}/_functions/products?limit=1`,
    `${SITE_BASE}/_functions/orders?limit=1`,
    `${SITE_BASE}/_functions/collections?limit=1`,
    `${SITE_BASE}/_functions/stats`,

    // Wix auto sitemaps
    `${SITE_BASE}/pages-sitemap.xml`,
    `${SITE_BASE}/blog-categories-sitemap.xml`,
    `${SITE_BASE}/blog-tags-sitemap.xml`,
    `${SITE_BASE}/blog-posts-sitemap.xml`,
    `${SITE_BASE}/store-products-sitemap.xml`,
  ];
}

function sleep(ms) {
  return new Promise(res => setTimeout(res, ms));
}

async function pingOnce(url) {
  try {
    const res = await fetch(url, {
      method: 'get',
      headers: { 'X-WeCare-Job': JOB_TAG }
    });
    await res.text().catch(() => null);
    return { url, ok: res.ok, status: res.status };
  } catch (e) {
    return { url, ok: false, status: 0, error: String(e && e.message ? e.message : e) };
  }
}

async function pingWithRetry(url, retries = RETRIES) {
  let attempt = 0;
  let last = null;
  while (attempt <= retries) {
    last = await pingOnce(url);
    if (last.ok) return last;
    // Don't retry client errors (except 429)
    if (last.status && last.status >= 400 && last.status < 500 && last.status !== 429) break;
    attempt += 1;
    if (attempt <= retries) await sleep(RETRY_BACKOFF * attempt);
  }
  return last;
}

// Pool executor with staggered dispatch to avoid 429s
async function pingPool(urls, pool = CONCURRENCY) {
  const out = new Array(urls.length);
  let i = 0;
  async function worker() {
    while (i < urls.length) {
      const idx = i++;
      // Stagger: small delay per dispatch to spread load
      if (idx > 0) await sleep(STAGGER_MS);
      out[idx] = await pingWithRetry(urls[idx]);
    }
  }
  const workers = Array.from({ length: Math.min(pool, urls.length) }, worker);
  await Promise.all(workers);
  return out;
}

/**
 * Job entrypoint (called by jobs.config)
 */
export async function pingSeoSurfaces() {
  const started = Date.now();
  const urls = buildTargets();
  const results = await pingPool(urls, CONCURRENCY);

  const ms = Date.now() - started;
  const errors = results.filter(r => !r.ok);
  const rate429 = results.filter(r => r.status === 429);

  if (errors.length) {
    console.warn(
      `[${JOB_TAG}] ${errors.length}/${results.length} failures in ${ms}ms` +
      (rate429.length ? ` (${rate429.length} rate-limited)` : '') +
      `: ${JSON.stringify(errors.slice(0, 5).map(e => ({ url: e.url.split('/_functions/')[1] || e.url, s: e.status })))}`
    );
  } else {
    console.log(`[${JOB_TAG}] ok — ${results.length} targets in ${ms}ms`);
  }

  return {
    ok: errors.length === 0,
    count: results.length,
    tookMs: ms,
    failures: errors.length,
    rateLimited: rate429.length,
    results
  };
}

export async function pingSeoNow() {
  return pingSeoSurfaces();
}

export async function dailySelfHit() {
  return pingSeoSurfaces();
}
