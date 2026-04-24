/**
 * Blog SEO Manager — View, Edit, Push SEO for all blog posts
 *
 * Features:
 * - Fetch all posts from Wix Blog API via webhook
 * - View SEO status (title, desc, keywords, JSON-LD count)
 * - Edit SEO inline per post
 * - Push SEO per post or bulk via /api/seo-tools/blog-seo-webhook
 * - Import/Export JSON
 * - No meta keywords tag — keywords in schema only
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

interface PageProps { signOut?: () => void; user?: any; }

const WIX_BASE = 'https://www.wecare.digital';
const BRAND = 'WECARE.DIGITAL';
const AUTHOR = 'Swdhya Vaksetu';
const WEBHOOK = '';  // Not used — calls Wix Velo endpoints directly
const WIX_VELO_BASE = 'https://www.wecare.digital/_functions';

interface BlogPost {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  url: string;
  seoTitle: string;
  metaDescription: string;
  focusKeyword: string;
  keywords: string[];
  titleLen: number;
  descLen: number;
  jsonLdCount: number;
  hasCustomSeo: boolean;
  status: 'pending' | 'pushing' | 'done' | 'skipped' | 'error';
  error?: string;
}

function generateSeoTitle(title: string): string {
  let t = `${title} | ${BRAND}`;
  if (t.length > 60) t = title.length <= 60 ? title : title.substring(0, 57) + '...';
  return t;
}

function generateDescription(excerpt: string, title: string): string {
  if (excerpt && excerpt.length >= 30) {
    return excerpt.length <= 160 ? excerpt : excerpt.substring(0, excerpt.lastIndexOf(' ', 155)) + '...';
  }
  return `${title}. Read more on ${BRAND}.`.substring(0, 160);
}

function generateKeywords(title: string): string[] {
  const stop = new Set(['the','a','an','and','or','but','in','on','at','to','for','of','with','by','as','is','was','are','it','its','this','that']);
  const words = title.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/).filter(w => w.length > 2 && !stop.has(w));
  const kw = [title.toLowerCase()];
  words.forEach(w => { if (!kw.includes(w)) kw.push(w); });
  return kw.slice(0, 10);
}

const BlogSeoManager: React.FC<PageProps> = ({ signOut, user }) => {
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [bulkRunning, setBulkRunning] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState({ seoTitle: '', metaDescription: '', focusKeyword: '', keywords: '' });
  const [filter, setFilter] = useState<'all' | 'hasSeo' | 'noSeo' | 'over60'>('all');

  const addLog = (msg: string) => setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);

  // Fetch posts from Wix RSS (works without API key from browser)
  const fetchPosts = useCallback(async () => {
    setLoading(true);
    addLog('Fetching blog posts from Wix...');
    try {
      const r = await fetch(`${WIX_BASE}/_functions/rssblog`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const xml = await r.text();
      const items: BlogPost[] = [];
      const regex = /<item>[\s\S]*?<title><!\[CDATA\[(.*?)\]\]><\/title>[\s\S]*?<link>(.*?)<\/link>[\s\S]*?(?:<description><!\[CDATA\[(.*?)\]\]><\/description>)?[\s\S]*?<\/item>/g;
      let match;
      while ((match = regex.exec(xml)) !== null) {
        const title = match[1] || '';
        const link = match[2] || '';
        const excerpt = (match[3] || '').replace(/<[^>]+>/g, '').substring(0, 200);
        const slug = link.split('/post/')[1] || '';
        const seoTitle = generateSeoTitle(title);
        const desc = generateDescription(excerpt, title);
        const keywords = generateKeywords(title);
        items.push({
          id: slug, title, slug, excerpt, url: link,
          seoTitle, metaDescription: desc, focusKeyword: keywords[0] || '',
          keywords, titleLen: seoTitle.length, descLen: desc.length,
          jsonLdCount: 0, hasCustomSeo: false, status: 'pending',
        });
      }
      setPosts(items);
      addLog(`Found ${items.length} blog posts`);
    } catch (e: any) { addLog(`Error: ${e.message}`); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchPosts(); }, [fetchPosts]);

  // Push SEO for a single post via Wix Velo endpoint
  const pushSingle = async (post: BlogPost) => {
    setPosts(prev => prev.map(p => p.id === post.id ? { ...p, status: 'pushing' } : p));
    addLog(`Pushing SEO for "${post.title}"...`);
    try {
      const r = await fetch(`${WIX_VELO_BASE}/blogseoapply?slug=${encodeURIComponent(post.slug)}`);
      const data = await r.json();
      if (data.ok) {
        setPosts(prev => prev.map(p => p.id === post.id ? { ...p, status: 'done', hasCustomSeo: true, jsonLdCount: 2 } : p));
        addLog(`  ✅ Pushed — ${data.tagCount} tags, focus: "${data.focusKeyword}"`);
      } else {
        setPosts(prev => prev.map(p => p.id === post.id ? { ...p, status: 'error', error: data.error } : p));
        addLog(`  ❌ Error: ${data.error}`);
      }
    } catch (e: any) {
      setPosts(prev => prev.map(p => p.id === post.id ? { ...p, status: 'error', error: e.message } : p));
      addLog(`  ❌ ${e.message}`);
    }
  };

  // Bulk push all posts via Wix Velo endpoint
  const bulkPush = async () => {
    setBulkRunning(true);
    addLog('Starting bulk SEO push via Wix Velo...');
    try {
      const r = await fetch(`${WIX_VELO_BASE}/blogseobulk`);
      const data = await r.json();
      if (data.ok) {
        addLog(`✅ Bulk done: ${data.updated || 0} updated, ${data.failed || 0} failed out of ${data.total || 0}`);
        if (data.errors?.length) data.errors.forEach((e: any) => addLog(`  ⚠️ ${e.title}: ${e.error}`));
        setPosts(prev => prev.map(p => ({ ...p, status: 'done' as const })));
      } else {
        addLog(`❌ Error: ${data.error}`);
      }
    } catch (e: any) {
      addLog(`❌ ${e.message}`);
      addLog('Try pushing posts one by one using the 🚀 button');
    }
    setBulkRunning(false);
  };

  // Edit
  const startEdit = (p: BlogPost) => {
    setEditingId(p.id);
    setEditData({ seoTitle: p.seoTitle, metaDescription: p.metaDescription, focusKeyword: p.focusKeyword, keywords: p.keywords.join(', ') });
  };
  const saveEdit = () => {
    if (!editingId) return;
    const kw = editData.keywords.split(',').map(k => k.trim()).filter(Boolean);
    setPosts(prev => prev.map(p => p.id === editingId ? {
      ...p, seoTitle: editData.seoTitle, metaDescription: editData.metaDescription,
      focusKeyword: editData.focusKeyword, keywords: kw,
      titleLen: editData.seoTitle.length, descLen: editData.metaDescription.length,
    } : p));
    setEditingId(null);
    addLog(`Updated: ${editingId}`);
  };

  // Export/Import
  const exportJson = () => {
    const data = posts.map(p => ({ slug: p.slug, title: p.title, url: p.url, seoTitle: p.seoTitle, metaDescription: p.metaDescription, focusKeyword: p.focusKeyword, keywords: p.keywords, excerpt: p.excerpt }));
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'blog_seo_108.json'; a.click();
    addLog(`Exported ${data.length} posts`);
  };
  const importJson = () => {
    const input = document.createElement('input'); input.type = 'file'; input.accept = '.json';
    input.onchange = async (e: any) => {
      const text = await e.target.files[0]?.text();
      if (!text) return;
      try {
        const data = JSON.parse(text);
        let updated = 0;
        setPosts(prev => prev.map(p => {
          const m = data.find((d: any) => d.slug === p.slug);
          if (m) { updated++; return { ...p, seoTitle: m.seoTitle || p.seoTitle, metaDescription: m.metaDescription || p.metaDescription, focusKeyword: m.focusKeyword || p.focusKeyword, keywords: m.keywords || p.keywords, titleLen: (m.seoTitle || p.seoTitle).length, descLen: (m.metaDescription || p.metaDescription).length }; }
          return p;
        }));
        addLog(`Imported: ${updated} posts updated`);
      } catch (err: any) { addLog(`Import error: ${err.message}`); }
    };
    input.click();
  };

  const filtered = posts.filter(p => {
    if (filter === 'hasSeo') return p.hasCustomSeo || p.status === 'done';
    if (filter === 'noSeo') return !p.hasCustomSeo && p.status === 'pending';
    if (filter === 'over60') return p.titleLen > 60;
    return true;
  });

  const stats = { total: posts.length, done: posts.filter(p => p.status === 'done' || p.hasCustomSeo).length, over60: posts.filter(p => p.titleLen > 60).length, pending: posts.filter(p => p.status === 'pending').length };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Blog SEO Manager" description="Manage SEO for all blog posts" />
      <div className="inner-page">
        <h1 className="inner-page-title">Blog SEO Manager</h1>
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 16 }}>
          {stats.total} posts | {stats.done} with SEO | {stats.pending} pending | {stats.over60} title &gt;60 chars
        </p>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          <button className="btn btn-primary" onClick={fetchPosts} disabled={loading}>{loading ? 'Loading...' : '🔄 Refresh'}</button>
          <button className="btn btn-primary" onClick={bulkPush} disabled={bulkRunning || posts.length === 0}>{bulkRunning ? '⏳ Pushing...' : `🚀 Bulk Push All (${stats.pending})`}</button>
          <button className="btn btn-secondary" onClick={exportJson} disabled={posts.length === 0}>📥 Export</button>
          <button className="btn btn-secondary" onClick={importJson}>📤 Import</button>
        </div>

        <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
          {(['all', 'noSeo', 'hasSeo', 'over60'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{ padding: '6px 14px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, background: filter === f ? '#d1f470' : '#f3f4f6', color: filter === f ? '#1a3a2a' : '#6b7280', fontWeight: filter === f ? 600 : 400 }}>
              {f === 'all' ? `All (${stats.total})` : f === 'noSeo' ? `⏳ Pending (${stats.pending})` : f === 'hasSeo' ? `✅ Done (${stats.done})` : `⚠️ >60 (${stats.over60})`}
            </button>
          ))}
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                <th style={{ padding: '8px 10px', textAlign: 'left' }}>#</th>
                <th style={{ padding: '8px 10px', textAlign: 'left' }}>Post</th>
                <th style={{ padding: '8px 10px', textAlign: 'left' }}>SEO Title</th>
                <th style={{ padding: '8px 10px', textAlign: 'center' }}>T</th>
                <th style={{ padding: '8px 10px', textAlign: 'center' }}>D</th>
                <th style={{ padding: '8px 10px', textAlign: 'left' }}>Focus Keyword</th>
                <th style={{ padding: '8px 10px', textAlign: 'center' }}>Status</th>
                <th style={{ padding: '8px 10px', textAlign: 'center' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => (
                <tr key={p.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '6px 10px' }}>{i + 1}</td>
                  <td style={{ padding: '6px 10px', maxWidth: 180 }}>
                    <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1a3a2a', textDecoration: 'underline', fontSize: 12 }}>{p.title}</a>
                  </td>
                  <td style={{ padding: '6px 10px', maxWidth: 250 }}>
                    {editingId === p.id ? <input value={editData.seoTitle} onChange={e => setEditData({ ...editData, seoTitle: e.target.value })} style={{ width: '100%', padding: 3, borderRadius: 6, border: '1px solid #d1f470', fontSize: 11 }} /> : <span style={{ fontSize: 11 }}>{p.seoTitle}</span>}
                  </td>
                  <td style={{ padding: '6px 10px', textAlign: 'center', color: p.titleLen > 60 ? '#ef4444' : '#22c55e', fontWeight: 600, fontSize: 11 }}>{p.titleLen}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'center', color: p.descLen > 160 ? '#ef4444' : '#22c55e', fontWeight: 600, fontSize: 11 }}>{p.descLen}</td>
                  <td style={{ padding: '6px 10px', fontSize: 11 }}>
                    {editingId === p.id ? <input value={editData.focusKeyword} onChange={e => setEditData({ ...editData, focusKeyword: e.target.value })} style={{ width: '100%', padding: 3, borderRadius: 6, border: '1px solid #d1f470', fontSize: 11 }} /> : p.focusKeyword}
                  </td>
                  <td style={{ padding: '6px 10px', textAlign: 'center', fontSize: 11 }}>
                    {p.status === 'done' ? '✅' : p.status === 'skipped' ? '⏭️' : p.status === 'pushing' ? '⏳' : p.status === 'error' ? '❌' : '⏳'}
                  </td>
                  <td style={{ padding: '6px 10px', textAlign: 'center' }}>
                    {editingId === p.id ? (
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button onClick={saveEdit} style={{ padding: '3px 8px', borderRadius: 6, border: 'none', background: '#d1f470', cursor: 'pointer', fontSize: 11 }}>Save</button>
                        <button onClick={() => setEditingId(null)} style={{ padding: '3px 8px', borderRadius: 6, border: 'none', background: '#f3f4f6', cursor: 'pointer', fontSize: 11 }}>✕</button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button onClick={() => startEdit(p)} style={{ padding: '3px 8px', borderRadius: 6, border: 'none', background: '#f3f4f6', cursor: 'pointer', fontSize: 11 }}>✏️</button>
                        <button onClick={() => pushSingle(p)} disabled={p.status === 'pushing'} style={{ padding: '3px 8px', borderRadius: 6, border: 'none', background: '#d1f470', cursor: 'pointer', fontSize: 11 }}>🚀</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {log.length > 0 && (
          <div className="card" style={{ padding: 16, marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Log</h3>
              <button className="btn btn-secondary" onClick={() => setLog([])} style={{ fontSize: 12, padding: '4px 12px' }}>Clear</button>
            </div>
            <pre style={{ background: '#0f1117', color: '#a3e635', padding: 16, borderRadius: 8, fontSize: 12, lineHeight: 1.6, maxHeight: 300, overflowY: 'auto', fontFamily: 'Consolas, Monaco, monospace', whiteSpace: 'pre-wrap' }}>
              {log.join('\n')}
            </pre>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default BlogSeoManager;
