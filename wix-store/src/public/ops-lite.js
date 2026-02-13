/**************************************************************
 * public/ops-lite.js
 * Tiny helper to log backend health in the browser console.
 * - Prefers /_functions/selftest (summarizes pass/fail)
 * - Falls back to /_functions/ping (if open) and /_functions/robots
 * - If selftest missing, also probes a few key surfaces (sitemap/RSS/seohead)
 * - Logs version header, timing, and highlights failures
 **************************************************************/

const SAME_ORIGIN = { credentials: 'same-origin', cache: 'no-store' };

/* --------------------- fetch helpers --------------------- */
async function fetchJSONorText(url) {
  const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
  try {
    const res = await fetch(url, SAME_ORIGIN);
    const ms = Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0);
    const raw = await res.text().catch(() => '');
    let data = null;
    try { data = raw ? JSON.parse(raw) : null; } catch { /* non-JSON */ }
    return {
      ok: res.ok,
      status: res.status,
      url,
      ms,
      version: res.headers.get('X-WeCare-Version') || '',
      ct: (res.headers.get('Content-Type') || '').toLowerCase(),
      data,
      raw
    };
  } catch (e) {
    const ms = Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0);
    return { ok: false, status: 0, url, ms, error: String(e && e.message ? e.message : e) };
  }
}

function summarizeSelftest(payload) {
  if (!payload || typeof payload !== 'object') return { ok: false, total: 0, failed: [] };
  const ok = !!payload.ok;
  const results = Array.isArray(payload.results) ? payload.results : [];
  const failed = results.filter(r => r && r.ok === false);
  return { ok, total: results.length, failed };
}

function logGroup(title, obj, collapsed = true) {
  try {
    if (collapsed && console.groupCollapsed) console.groupCollapsed(title);
    else if (console.group) console.group(title);
    console.log(obj);
    if (console.groupEnd) console.groupEnd();
  } catch { /* no-op */ }
}

/* -------------------- main surface checks -------------------- */
async function trySelftest() {
  const st = await fetchJSONorText('/_functions/selftest');
  if (st.ok && st.data) {
    const sum = summarizeSelftest(st.data);
    logGroup(
      `[WECARE Ops] selftest (${st.status}) ${st.ms}ms ${st.version ? `| v ${st.version}` : ''}`,
      st.data
    );
    if (!sum.ok || (sum.failed && sum.failed.length)) {
      console.warn('[WECARE Ops] selftest failures:', sum.failed?.slice(0, 10) || []);
    }
    return { surface: 'selftest', request: st, summary: sum };
  }
  return null;
}

async function tryPing() {
  const r = await fetchJSONorText('/_functions/ping');
  if (r.ok && r.data) {
    logGroup(
      `[WECARE Ops] ping (${r.status}) ${r.ms}ms ${r.version ? `| v ${r.version}` : ''}`,
      r.data
    );
    return { surface: 'ping', request: r, summary: summarizeSelftest(r.data) };
  } else if (r.status === 403) {
    console.info('[WECARE Ops] ping is protected (403). This is fine if you enabled auth.');
    return { surface: 'ping-locked', request: r, summary: { ok: true } };
  }
  return null;
}

async function tryRobots() {
  const r = await fetchJSONorText('/_functions/robots');
  if (r.ok) {
    console.log(
      `[WECARE Ops] robots ok (${r.status}) ${r.ms}ms ${r.version ? `| v ${r.version}` : ''}`
    );
    return { surface: 'robots', request: r, summary: { ok: true } };
  }
  return null;
}

/* Probe a couple of key surfaces so you get signal even without selftest */
async function probeKeySurfaces() {
  const urls = [
    '/_functions/smindex',
    '/_functions/sitemap',
    '/_functions/smextra',
    '/_functions/smtxt',
    '/_functions/seohead?path=/',
    '/_functions/aiindex',
    '/_functions/faq',
    '/_functions/siteinfo',
    '/_functions/icons',
    '/_functions/rss',
    '/_functions/rssblog',
    '/_functions/rssproducts',
    '/pages-sitemap.xml',
  ];
  const work = urls.map(fetchJSONorText);
  const results = await Promise.all(work);
  const brief = results.map(r => ({
    url: r.url,
    ok: r.ok,
    status: r.status,
    ms: r.ms,
    ct: r.ct
  }));
  logGroup('[WECARE Ops] key surfaces (probe)', brief, false);
  const failures = brief.filter(b => !b.ok);
  if (failures.length) {
    console.warn('[WECARE Ops] surface failures:', failures.slice(0, 10));
  }
  return { surface: 'probe', results: brief, ok: failures.length === 0 };
}

/**
 * Primary helper — keeps your original function name/signature.
 * Returns a compact summary and logs details to the console.
 */
export async function runOpsLite() {
  if (typeof window === 'undefined') return null;

  // 1) Preferred: selftest
  const s1 = await trySelftest();
  if (s1) return s1;

  // 2) Fallback: ping
  const s2 = await tryPing();
  if (s2) return s2;

  // 3) Last-resort: robots
  const s3 = await tryRobots();
  if (s3) return s3;

  // 4) Extra: probe key surfaces so you still get a pulse
  const s4 = await probeKeySurfaces();
  return { surface: 'probe-only', summary: { ok: s4.ok } };
}

/**
 * Convenience initializer — run only if you add ?ops=1 to the URL.
 */
export function initOpsLiteOnDemand() {
  try {
    const url = new URL(window.location.href);
    if (url.searchParams.get('ops') === '1') {
      runOpsLite();
    }
  } catch {
    // ignore
  }
}

/* Optional: expose a manual trigger for dev tools */
try {
  if (typeof window !== 'undefined') {
    window.WECARE_OPS = { run: runOpsLite };
  }
} catch { /* no-op */ }
