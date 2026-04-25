/**
 * Site Pages SEO — 37 public pages SEO management
 * View, audit, clean, and apply SEO for all static site pages.
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

interface PageProps { signOut?: () => void; user?: any; }
interface SitePage {
  path: string; name: string; type: string; url: string;
  title: string; metaDescription: string; keywords: string[];
  jsonLdTypes: string[]; hasJsonLd: boolean; canonical: string;
}
const th: React.CSSProperties = { padding: '8px 10px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: '#6b7280' };
const td: React.CSSProperties = { padding: '6px 10px' };
const btn: React.CSSProperties = { padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 11, fontFamily: 'inherit' };

const SitePagesManager: React.FC<PageProps> = ({ signOut, user }) => {
  const [pages, setPages] = useState<SitePage[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all');
  const [log, setLog] = useState<string[]>([]);
  const addLog = (m: string) => setLog(p => [...p, `[${new Date().toLocaleTimeString()}] ${m}`]);

  const fetchPages = useCallback(async () => {
    setLoading(true); addLog('Fetching 37 site pages...');
    try { const d = await (await fetch('/api/seo-tools/site-pages')).json(); if (d.ok) { setPages(d.pages); addLog(`${d.total} pages loaded`); } else addLog(d.error); }
    catch (e: any) { addLog(e.message); } setLoading(false);
  }, []);
  useEffect(() => { fetchPages(); }, [fetchPages]);

  const types = [...new Set(pages.map(p => p.type))];
  const filtered = filter === 'all' ? pages : pages.filter(p => p.type === filter);
  const noSeo = pages.filter(p => !p.hasJsonLd).length;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Site Pages SEO" description="SEO for 37 public pages" />
      <div className="inner-page">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div>
            <h1 className="inner-page-title" style={{ margin: 0 }}>Site Pages SEO</h1>
            <p style={{ color: '#6b7280', fontSize: 13, margin: '4px 0 0' }}>{pages.length} pages | {noSeo} missing JSON-LD | {pages.filter(p => p.hasJsonLd).length} with schema</p>
          </div>
          <button className="btn btn-primary" onClick={fetchPages} disabled={loading} style={{ fontSize: 13 }}>{loading ? 'Loading...' : 'Refresh'}</button>
        </div>

        <div style={{ display: 'flex', gap: 4, marginBottom: 16, flexWrap: 'wrap' }}>
          <button onClick={() => setFilter('all')} style={{ ...btn, background: filter === 'all' ? '#d1f470' : '#f3f4f6', fontWeight: filter === 'all' ? 600 : 400 }}>All ({pages.length})</button>
          {types.map(t => <button key={t} onClick={() => setFilter(t)} style={{ ...btn, background: filter === t ? '#d1f470' : '#f3f4f6', fontWeight: filter === t ? 600 : 400 }}>{t} ({pages.filter(p => p.type === t).length})</button>)}
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead><tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
              <th style={th}>#</th><th style={th}>Page</th><th style={th}>Type</th><th style={th}>Title</th><th style={th}>Meta Description</th><th style={{ ...th, textAlign: 'center' }}>JSON-LD</th><th style={{ ...th, textAlign: 'center' }}>Keywords</th>
            </tr></thead>
            <tbody>{filtered.map((p, i) => (
              <tr key={p.path} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={td}>{i + 1}</td>
                <td style={{ ...td, maxWidth: 180 }}><a href={p.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1a3a2a', textDecoration: 'underline', fontSize: 12 }}>{p.name}</a><div style={{ fontSize: 10, color: '#9ca3af' }}>{p.path}</div></td>
                <td style={td}><span style={{ padding: '2px 8px', background: '#f0fdf4', color: '#166534', borderRadius: 6, fontSize: 10 }}>{p.type}</span></td>
                <td style={{ ...td, maxWidth: 220 }}><div style={{ fontSize: 11 }}>{p.title}</div>{p.title && <div style={{ fontSize: 10, color: p.title.length > 60 ? '#ef4444' : '#22c55e' }}>{p.title.length}ch</div>}</td>
                <td style={{ ...td, maxWidth: 250, fontSize: 11, color: '#6b7280' }}>{p.metaDescription ? p.metaDescription.substring(0, 80) + '...' : '-'}</td>
                <td style={{ ...td, textAlign: 'center' }}>{p.hasJsonLd ? <span style={{ color: '#22c55e', fontSize: 11 }}>{p.jsonLdTypes.join(', ')}</span> : <span style={{ color: '#ef4444', fontSize: 10 }}>missing</span>}</td>
                <td style={{ ...td, textAlign: 'center', fontSize: 11 }}>{p.keywords?.length || 0}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: '#6b7280' }}>{filtered.length} pages shown</div>

        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>JSON-LD Standard for Site Pages</h3>
          <p style={{ fontSize: 12, color: '#6b7280', margin: 0, lineHeight: 1.8 }}>
            Each site page should have: WebPage + BreadcrumbList + FAQPage (AI-generated).<br/>
            Homepage additionally gets: Organization + WebSite + ItemList.<br/>
            FAQ page gets: FAQPage with all Q&A pairs.<br/>
            Contact page should get: LocalBusiness schema.<br/>
            SEO data is managed in sitestore/src/backend/seo-pages-data.js and applied via Velo autoSEO().
          </p>
        </div>

        {log.length > 0 && (<div className="card" style={{ padding: 16, marginTop: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}><h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Activity</h3><button onClick={() => setLog([])} style={{ ...btn, background: '#f3f4f6' }}>Clear</button></div>
          <pre style={{ background: '#0f1117', color: '#a3e635', padding: 16, borderRadius: 8, fontSize: 12, lineHeight: 1.6, maxHeight: 200, overflowY: 'auto', fontFamily: 'Consolas, Monaco, monospace', whiteSpace: 'pre-wrap' }}>{log.join('\n')}</pre>
        </div>)}
      </div>
    </Layout>
  );
};
export default SitePagesManager;
