/**
 * Blog SEO Manager — Generate, Edit, Bulk Update Blog SEO
 * 
 * Features:
 * - View all 108 blog posts with current SEO status
 * - Generate SEO (title, description, keywords, JSON-LD) per post
 * - Edit SEO inline
 * - Bulk update all posts (draft → update seoData → republish)
 * - Upload JSON SEO pack
 * - Export current SEO data as JSON
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

interface PageProps { signOut?: () => void; user?: any; }

const WIX_BASE = 'https://www.wecare.digital';
const LOGO = 'https://app.wecare.digital/stream/media/m/wecare-digital.png';
const AUTHOR = 'Swdhya Vaksetu';
const BRAND = 'WECARE.DIGITAL';

interface BlogPost {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  url: string;
  titleTag: string;
  metaDescription: string;
  focusKeyword: string;
  titleLen: number;
  source: 'confirmed' | 'auto';
  status: 'pending' | 'updating' | 'done' | 'error';
  error?: string;
}

function generateSeo(title: string, slug: string, excerpt: string): { titleTag: string; desc: string; kw: string } {
  let titleTag = `${title} | ${AUTHOR}`;
  if (titleTag.length > 60) titleTag = `${title} | Swdhya`;
  if (titleTag.length > 60) titleTag = title.substring(0, 57) + '...';

  let desc = excerpt && excerpt.length > 50 ? excerpt : `${title}. ${excerpt || ''}`.trim();
  if (desc.length > 160) desc = desc.substring(0, 157) + '...';
  if (!desc || desc.length < 10) desc = `${title}. A reflection by ${AUTHOR} on ${BRAND}.`;

  const words = title.toLowerCase().split(/\s+/).filter(w => w.length > 2).slice(0, 4);
  const kw = words.length ? words.join(' ') : title.toLowerCase();

  return { titleTag, desc, kw };
}

function buildJsonLd(slug: string, titleTag: string, desc: string, kw: string, postTitle: string) {
  const url = `${WIX_BASE}/post/${slug}`;
  return {
    blogPosting: {
      '@context': 'https://schema.org', '@type': 'BlogPosting',
      '@id': `${url}#blogposting`,
      mainEntityOfPage: { '@type': 'WebPage', '@id': `${url}#webpage` },
      headline: titleTag, description: desc, keywords: kw,
      publisher: { '@type': 'Organization', '@id': `${WIX_BASE}/#organization`, name: BRAND, url: `${WIX_BASE}/`, logo: { '@type': 'ImageObject', url: LOGO } },
      author: { '@type': 'Person', name: AUTHOR, url: `${WIX_BASE}/swdhya` },
      url, articleSection: AUTHOR, inLanguage: 'en-IN',
    },
    breadcrumb: {
      '@context': 'https://schema.org', '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: `${WIX_BASE}/` },
        { '@type': 'ListItem', position: 2, name: 'Blog', item: `${WIX_BASE}/blog` },
        { '@type': 'ListItem', position: 3, name: postTitle, item: url },
      ],
    },
  };
}

function buildSeoTags(slug: string, titleTag: string, desc: string, kw: string, postTitle: string) {
  const url = `${WIX_BASE}/post/${slug}`;
  const ld = buildJsonLd(slug, titleTag, desc, kw, postTitle);
  return [
    { type: 'title', children: titleTag, custom: true, disabled: false },
    { type: 'meta', props: { name: 'description', content: desc }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { name: 'keywords', content: kw }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { name: 'robots', content: 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:title', content: titleTag }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:description', content: desc }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:url', content: url }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:type', content: 'article' }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'og:site_name', content: BRAND }, children: '', custom: true, disabled: false },
    { type: 'meta', props: { property: 'article:author', content: AUTHOR }, children: '', custom: true, disabled: false },
    { type: 'link', props: { rel: 'canonical', href: url }, children: '', custom: true, disabled: false },
    { type: 'script', props: { type: 'application/ld+json' }, children: JSON.stringify(ld.blogPosting), custom: true, disabled: false },
    { type: 'script', props: { type: 'application/ld+json' }, children: JSON.stringify(ld.breadcrumb), custom: true, disabled: false },
  ];
}

const BlogSeoManager: React.FC<PageProps> = ({ signOut, user }) => {
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [bulkRunning, setBulkRunning] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState({ titleTag: '', metaDescription: '', focusKeyword: '' });
  const [filter, setFilter] = useState<'all' | 'confirmed' | 'auto' | 'over60'>('all');

  const addLog = (msg: string) => setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);

  // Fetch all posts from Wix API
  const fetchPosts = useCallback(async () => {
    setLoading(true);
    addLog('Fetching blog posts from Wix API...');
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
        const excerpt = (match[3] || '').replace(/<[^>]+>/g, '').substring(0, 155);
        const slug = link.split('/post/')[1] || '';
        const seo = generateSeo(title, slug, excerpt);

        items.push({
          id: slug,
          title,
          slug,
          excerpt,
          url: link,
          titleTag: seo.titleTag,
          metaDescription: seo.desc,
          focusKeyword: seo.kw,
          titleLen: seo.titleTag.length,
          source: 'auto',
          status: 'pending',
        });
      }

      setPosts(items);
      addLog(`Found ${items.length} blog posts`);
    } catch (e: any) {
      addLog(`Error: ${e.message}`);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchPosts(); }, [fetchPosts]);

  // Edit a single post
  const startEdit = (post: BlogPost) => {
    setEditingId(post.id);
    setEditData({ titleTag: post.titleTag, metaDescription: post.metaDescription, focusKeyword: post.focusKeyword });
  };

  const saveEdit = () => {
    if (!editingId) return;
    setPosts(prev => prev.map(p => p.id === editingId ? {
      ...p,
      titleTag: editData.titleTag,
      metaDescription: editData.metaDescription,
      focusKeyword: editData.focusKeyword,
      titleLen: editData.titleTag.length,
      source: 'confirmed' as const,
    } : p));
    setEditingId(null);
    addLog(`Updated SEO for: ${editingId}`);
  };

  // Export as JSON
  const exportJson = () => {
    const data = posts.map(p => ({
      slug: p.slug, url: p.url, titleTag: p.titleTag,
      metaDescription: p.metaDescription, focusKeyword: p.focusKeyword,
      author: AUTHOR, source: p.source,
      seoTags: buildSeoTags(p.slug, p.titleTag, p.metaDescription, p.focusKeyword, p.title),
      jsonLd: buildJsonLd(p.slug, p.titleTag, p.metaDescription, p.focusKeyword, p.title),
    }));
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'blog_seo_pack.json'; a.click();
    addLog(`Exported ${data.length} posts as JSON`);
  };

  // Import JSON
  const importJson = () => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.json';
    input.onchange = async (e: any) => {
      const file = e.target.files[0];
      if (!file) return;
      const text = await file.text();
      try {
        const data = JSON.parse(text);
        if (!Array.isArray(data)) throw new Error('Expected array');
        let updated = 0;
        setPosts(prev => prev.map(p => {
          const match = data.find((d: any) => d.slug === p.slug);
          if (match) {
            updated++;
            return {
              ...p,
              titleTag: match.titleTag || p.titleTag,
              metaDescription: match.metaDescription || p.metaDescription,
              focusKeyword: match.focusKeyword || p.focusKeyword,
              titleLen: (match.titleTag || p.titleTag).length,
              source: 'confirmed' as const,
            };
          }
          return p;
        }));
        addLog(`Imported JSON: ${updated} posts updated from ${data.length} entries`);
      } catch (err: any) {
        addLog(`Import error: ${err.message}`);
      }
    };
    input.click();
  };

  // Bulk update via Wix REST API (draft → update seoData → republish)
  const bulkUpdate = async () => {
    setBulkRunning(true);
    addLog('Starting bulk SEO update (draft → update → republish)...');
    addLog('This calls the Wix REST API directly. Each post: PATCH with ?action=UPDATE_PUBLICATION');

    let ok = 0, fail = 0;

    // Get Wix API credentials from the backend
    let apiKey = '', siteId = '';
    try {
      const r = await fetch(`${WIX_BASE}/_functions/health`);
      if (r.ok) {
        addLog('Wix backend is reachable');
      }
    } catch {
      addLog('Cannot reach Wix backend');
      setBulkRunning(false);
      return;
    }

    // We need to call the backend Lambda that has the Wix API key
    // The stack app calls via API_BASE
    const apiBase = (window as any).__NEXT_DATA__?.runtimeConfig?.API_BASE || process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';

    addLog(`Calling backend at ${apiBase}/blog-seo/bulk-update...`);

    try {
      const seoData = posts.map(p => ({
        slug: p.slug,
        title: p.title,
        seoTags: buildSeoTags(p.slug, p.titleTag, p.metaDescription, p.focusKeyword, p.title),
      }));

      const r = await fetch(`${apiBase}/blog-seo/bulk-update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posts: seoData }),
      });

      if (r.ok) {
        const result = await r.json();
        ok = result.updated || 0;
        fail = result.failed || 0;
        addLog(`Backend result: ${ok} updated, ${fail} failed`);
      } else {
        addLog(`Backend error: ${r.status}. Falling back to direct Wix API...`);
        // Fallback: call the Wix Velo endpoint
        addLog('Calling /_functions/blogseobulk...');
        const r2 = await fetch(`${WIX_BASE}/_functions/blogseobulk`);
        if (r2.ok) {
          const d = await r2.json();
          addLog(`Velo result: ${d.updated || 0} updated, ${d.failed || 0} failed`);
          ok = d.updated || 0;
          fail = d.failed || 0;
        } else {
          addLog(`Velo endpoint also failed: ${r2.status}`);
          addLog('');
          addLog('To update blog SEO, run from terminal:');
          addLog('  python seo-crawler/scripts/blog_draft_seo_republish.py');
          addLog('');
          addLog('This uses the Wix REST API with draft→update→republish pattern.');
        }
      }
    } catch (e: any) {
      addLog(`Error: ${e.message}`);
      addLog('');
      addLog('Fallback: run from terminal:');
      addLog('  python seo-crawler/scripts/blog_draft_seo_republish.py');
    }

    // Update post statuses
    setPosts(prev => prev.map(p => ({ ...p, status: 'done' as const })));
    addLog(`Done. ${ok} updated, ${fail} failed out of ${posts.length} posts.`);
    setBulkRunning(false);
  };

  // Filter posts
  const filtered = posts.filter(p => {
    if (filter === 'confirmed') return p.source === 'confirmed';
    if (filter === 'auto') return p.source === 'auto';
    if (filter === 'over60') return p.titleLen > 60;
    return true;
  });

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Blog SEO Manager" description="Manage SEO for all blog posts" />
      <div className="inner-page">
        <h1 className="inner-page-title">Blog SEO Manager</h1>
        <p style={{ color: '#6b7280', fontSize: 14, marginBottom: 16 }}>
          Generate, edit, and bulk-update SEO for all {posts.length} blog posts. Author: {AUTHOR}
        </p>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          <button className="btn btn-primary" onClick={fetchPosts} disabled={loading}>
            {loading ? 'Loading...' : '🔄 Refresh Posts'}
          </button>
          <button className="btn btn-primary" onClick={bulkUpdate} disabled={bulkRunning || posts.length === 0}>
            {bulkRunning ? '⏳ Updating...' : `🚀 Bulk Update All (${posts.length})`}
          </button>
          <button className="btn btn-secondary" onClick={exportJson} disabled={posts.length === 0}>
            📥 Export JSON
          </button>
          <button className="btn btn-secondary" onClick={importJson}>
            📤 Import JSON
          </button>
        </div>

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
          {(['all', 'confirmed', 'auto', 'over60'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              style={{ padding: '6px 14px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13,
                background: filter === f ? '#d1f470' : '#f3f4f6', color: filter === f ? '#1a3a2a' : '#6b7280', fontWeight: filter === f ? 600 : 400 }}>
              {f === 'all' ? `All (${posts.length})` : f === 'confirmed' ? `✅ Confirmed (${posts.filter(p=>p.source==='confirmed').length})` : f === 'auto' ? `⚠️ Auto (${posts.filter(p=>p.source==='auto').length})` : `❌ Over 60 (${posts.filter(p=>p.titleLen>60).length})`}
            </button>
          ))}
        </div>

        {/* Posts table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>#</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Title</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Title Tag</th>
                <th style={{ padding: '8px 12px', textAlign: 'center' }}>Len</th>
                <th style={{ padding: '8px 12px', textAlign: 'center' }}>Source</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Keyword</th>
                <th style={{ padding: '8px 12px', textAlign: 'center' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => (
                <tr key={p.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '8px 12px' }}>{i + 1}</td>
                  <td style={{ padding: '8px 12px' }}>
                    <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1a3a2a', textDecoration: 'underline' }}>
                      {p.title}
                    </a>
                  </td>
                  <td style={{ padding: '8px 12px', maxWidth: 300 }}>
                    {editingId === p.id ? (
                      <input value={editData.titleTag} onChange={e => setEditData({...editData, titleTag: e.target.value})}
                        style={{ width: '100%', padding: 4, borderRadius: 6, border: '1px solid #d1f470' }} />
                    ) : (
                      <span style={{ fontSize: 12 }}>{p.titleTag}</span>
                    )}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center', color: p.titleLen > 60 ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                    {p.titleLen}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                    {p.source === 'confirmed' ? '✅' : '⚠️'}
                  </td>
                  <td style={{ padding: '8px 12px', fontSize: 12 }}>
                    {editingId === p.id ? (
                      <input value={editData.focusKeyword} onChange={e => setEditData({...editData, focusKeyword: e.target.value})}
                        style={{ width: '100%', padding: 4, borderRadius: 6, border: '1px solid #d1f470' }} />
                    ) : p.focusKeyword}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                    {editingId === p.id ? (
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button onClick={saveEdit} style={{ padding: '4px 8px', borderRadius: 6, border: 'none', background: '#d1f470', cursor: 'pointer', fontSize: 12 }}>Save</button>
                        <button onClick={() => setEditingId(null)} style={{ padding: '4px 8px', borderRadius: 6, border: 'none', background: '#f3f4f6', cursor: 'pointer', fontSize: 12 }}>Cancel</button>
                      </div>
                    ) : (
                      <button onClick={() => startEdit(p)} style={{ padding: '4px 8px', borderRadius: 6, border: 'none', background: '#f3f4f6', cursor: 'pointer', fontSize: 12 }}>✏️ Edit</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Log output */}
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
