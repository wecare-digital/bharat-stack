/**
 * SEO Tools — Blog SEO Bulk Update, Button Audit, Google Indexing, PageSpeed
 *
 * Calls Wix Velo backend for blog SEO updates.
 * Calls wecare.digital/_functions/ for live site checks.
 * Calls Google APIs via the Next.js API route for indexing + PageSpeed.
 */
import React, { useState } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

interface PageProps { signOut?: () => void; user?: any; }

const WIX_BASE = 'https://www.wecare.digital';

const SEOTools: React.FC<PageProps> = ({ signOut, user }) => {
  const [log, setLog] = useState<string[]>([]);
  const [running, setRunning] = useState('');

  function addLog(msg: string) {
    setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }

  // ── Blog SEO Bulk Update ──
  async function runBlogSeo() {
    setRunning('blog');
    setLog([]);
    addLog('Starting blog SEO bulk update via Wix API...');
    try {
      const res = await fetch('/api/seo-tools/blog-seo', { method: 'POST' });
      const data = await res.json();
      if (data.error) {
        addLog(`Error: ${data.error}`);
      } else {
        addLog(`Products updated: ${data.products ?? '—'}`);
        addLog(`Blog posts: ${data.blog_ok ?? 0} updated, ${data.blog_fail ?? 0} failed`);
        addLog(`FAQ seeded: ${data.faq_seeded ?? '—'}`);
        addLog(`Google URLs submitted: ${data.google ?? '—'}`);
      }
      addLog('Done.');
    } catch (e: any) {
      addLog(`Failed: ${e.message}`);
    }
    setRunning('');
  }

  // ── Button Audit ──
  async function runButtonAudit() {
    setRunning('buttons');
    setLog([]);
    addLog('Fetching homepage to audit buttons...');
    try {
      const res = await fetch('/api/seo-tools/button-audit', { method: 'POST' });
      const data = await res.json();
      addLog(`Pages checked: ${data.pages_checked ?? 0}`);
      addLog(`Total buttons found: ${data.total_buttons ?? 0}`);
      addLog(`Compliant (13px radius): ${data.compliant ?? 0}`);
      addLog(`Non-compliant: ${data.non_compliant ?? 0}`);
      if (data.details) {
        data.details.forEach((d: any) => {
          addLog(`  ${d.page}: ${d.buttons} buttons, ${d.compliant} OK, ${d.issues} issues`);
        });
      }
      addLog(data.note || '');
      addLog('Done.');
    } catch (e: any) {
      addLog(`Failed: ${e.message}`);
    }
    setRunning('');
  }

  // ── Google Indexing ──
  async function runGoogleIndex() {
    setRunning('google');
    setLog([]);
    addLog('Submitting URLs to Google Indexing API...');
    try {
      const res = await fetch('/api/seo-tools/google-index', { method: 'POST' });
      const data = await res.json();
      if (data.error) {
        addLog(`Error: ${data.error}`);
      } else {
        addLog(`URLs submitted: ${data.submitted ?? 0} / ${data.total ?? 0}`);
        addLog(`Quota status: ${data.quota_note || 'OK'}`);
      }
      addLog('Done.');
    } catch (e: any) {
      addLog(`Failed: ${e.message}`);
    }
    setRunning('');
  }

  // ── PageSpeed Check ──
  async function runPageSpeed() {
    setRunning('pagespeed');
    setLog([]);
    addLog('Running PageSpeed Insights on sample pages...');
    try {
      const res = await fetch('/api/seo-tools/pagespeed', { method: 'POST' });
      const data = await res.json();
      if (data.error) {
        addLog(`Error: ${data.error}`);
      } else if (data.results) {
        data.results.forEach((r: any) => {
          addLog(`  ${r.url}: perf=${r.perf}, seo=${r.seo}`);
        });
      }
      addLog('Done.');
    } catch (e: any) {
      addLog(`Failed: ${e.message}`);
    }
    setRunning('');
  }

  // ── Live SEO Check ──
  async function runLiveSeoCheck() {
    setRunning('livecheck');
    setLog([]);
    addLog('Checking live SEO endpoints...');
    try {
      // Health
      const hRes = await fetch(`${WIX_BASE}/_functions/health`);
      const health = await hRes.json();
      addLog(`Health: ${health.status} — ${health.productCount} products`);

      // SEO head for homepage
      const sRes = await fetch(`${WIX_BASE}/_functions/seohead?path=/`);
      if (sRes.ok) {
        const seo = await sRes.json();
        addLog(`Homepage title: ${seo.title || '(not set)'}`);
        addLog(`Homepage desc: ${(seo.description || '(not set)').substring(0, 80)}...`);
        addLog(`Keywords: ${(seo.keywords || []).join(', ').substring(0, 80)}`);
        addLog(`Structured data: ${(seo.structuredData || []).length} schemas`);
      } else {
        addLog(`SEO head: ${sRes.status}`);
      }

      // FAQ
      const fRes = await fetch(`${WIX_BASE}/_functions/faq`);
      if (fRes.ok) {
        const faq = await fRes.json();
        const count = Object.values(faq.faqs || {}).flat().length;
        addLog(`FAQ items: ${count}`);
      }

      addLog('Done.');
    } catch (e: any) {
      addLog(`Failed: ${e.message}`);
    }
    setRunning('');
  }

  const tools = [
    { id: 'blog', label: 'Update Blog + Product SEO', desc: 'Bulk update all blog post and product SEO tags via Wix API (titles, descriptions, schema, OG tags)', action: runBlogSeo, icon: '📝' },
    { id: 'buttons', label: 'Audit Buttons', desc: 'Check all buttons across pages for 13px border-radius and no text underline compliance', action: runButtonAudit, icon: '🔘' },
    { id: 'google', label: 'Google Indexing Submit', desc: 'Push all site URLs to Google Indexing API for faster crawling', action: runGoogleIndex, icon: '🔍' },
    { id: 'pagespeed', label: 'PageSpeed Check', desc: 'Run Google PageSpeed Insights on sample pages (mobile)', action: runPageSpeed, icon: '⚡' },
    { id: 'livecheck', label: 'Live SEO Check', desc: 'Check live Wix site SEO endpoints (health, seohead, FAQ)', action: runLiveSeoCheck, icon: '📊' },
  ];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SEO Tools" description="SEO management tools for wecare.digital" />
      <div className="inner-page">
        <h1 className="inner-page-title">SEO Tools</h1>
        <p style={{ color: '#6b7280', fontSize: 14, marginBottom: 24 }}>
          Run SEO operations on wecare.digital — blog SEO, button audit, Google indexing, PageSpeed.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 24 }}>
          {tools.map(t => (
            <div key={t.id} className="card" style={{ padding: '16px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>{t.icon} {t.label}</div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{t.desc}</div>
                </div>
              </div>
              <button
                className="btn btn-primary"
                onClick={t.action}
                disabled={!!running}
                style={{ marginTop: 8, width: '100%' }}
              >
                {running === t.id ? 'Running...' : 'Run'}
              </button>
            </div>
          ))}
        </div>

        {log.length > 0 && (
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Output</h3>
              <button className="btn btn-secondary" onClick={() => setLog([])} style={{ fontSize: 12, padding: '4px 12px' }}>Clear</button>
            </div>
            <pre style={{
              background: '#0f1117', color: '#a3e635', padding: 16, borderRadius: 8,
              fontSize: 12, lineHeight: 1.6, maxHeight: 400, overflowY: 'auto',
              fontFamily: 'Consolas, Monaco, monospace', whiteSpace: 'pre-wrap',
            }}>
              {log.join('\n')}
            </pre>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default SEOTools;
