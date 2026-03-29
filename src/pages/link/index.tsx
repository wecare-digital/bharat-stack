/**
 * Link Page - URL Shortener & Deep Links
 * Domain: r.wecare.digital
 * General-purpose short links, click tracking, deep links for iOS/Android
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import Button from '../../components/ui/Button';
import { useToastContext } from '../../contexts/ToastContext';
import { useConfirm } from '../../contexts/ConfirmContext';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';
const SHORT_DOMAIN = 'r.wecare.digital';

interface PageProps { signOut?: () => void; user?: any; }

interface ShortLink {
  shortCode: string;
  shortUrl: string;
  originalUrl: string;
  title: string;
  clicks: number;
  createdAt: string;
  expiresAt?: string;
  deepLink?: boolean;
  iosUrl?: string;
  androidUrl?: string;
  active?: boolean;
}

/* ── Icons ── */
const LinkIcon = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
  </svg>
);
const CopyIcon = ({ size = 14 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>
);
const TrashIcon = ({ size = 14 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
  </svg>
);
const BarChartIcon = ({ size = 14 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
  </svg>
);
const PlusIcon = ({ size = 14 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
);

const LinkPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [links, setLinks] = useState<ShortLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formUrl, setFormUrl] = useState('');
  const [formTitle, setFormTitle] = useState('');
  const [formCode, setFormCode] = useState('');
  const [formDeepLink, setFormDeepLink] = useState(false);
  const [formIosUrl, setFormIosUrl] = useState('');
  const [formAndroidUrl, setFormAndroidUrl] = useState('');
  const [formExpiry, setFormExpiry] = useState('');
  const [analyticsCode, setAnalyticsCode] = useState<string | null>(null);
  const [analyticsData, setAnalyticsData] = useState<any>(null);

  const toast = useToastContext();
  const confirm = useConfirm();

  const totalClicks = links.reduce((s, l) => s + (Number(l.clicks) || 0), 0);
  const deepLinkCount = links.filter(l => l.deepLink).length;

  const loadLinks = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/links`);
      const data = await resp.json();
      setLinks((data.links || []).map((l: any) => ({
        ...l,
        clicks: Number(l.clicks) || 0,
        shortUrl: `https://${SHORT_DOMAIN}/${l.shortCode}`,
      })));
    } catch (err) {
      console.error('Load links error:', err);
      toast.error('Failed to load links');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadLinks(); }, [loadLinks]);

  const generateCode = () => {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let code = '';
    for (let i = 0; i < 6; i++) code += chars[Math.floor(Math.random() * chars.length)];
    setFormCode(code);
  };

  const resetForm = () => {
    setFormUrl(''); setFormTitle(''); setFormCode(''); setFormDeepLink(false);
    setFormIosUrl(''); setFormAndroidUrl(''); setFormExpiry('');
  };

  const handleCreate = async () => {
    if (!formUrl.trim()) return;
    setCreating(true);
    try {
      const resp = await fetch(`${API_BASE}/links`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shortCode: formCode.trim() || undefined,
          originalUrl: formUrl.trim(),
          title: formTitle.trim() || formUrl.trim(),
          deepLink: formDeepLink,
          iosUrl: formIosUrl || undefined,
          androidUrl: formAndroidUrl || undefined,
          expiresAt: formExpiry || undefined,
        }),
      });
      const data = await resp.json();
      if (data.success) {
        toast.success('Link created');
        resetForm();
        setShowForm(false);
        loadLinks();
      } else {
        toast.error(data.error || 'Failed to create link');
      }
    } catch {
      toast.error('Failed to create link');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (code: string) => {
    const ok = await confirm('Delete this short link? This cannot be undone.');
    if (!ok) return;
    try {
      await fetch(`${API_BASE}/links/${code}`, { method: 'DELETE' });
      toast.success('Link deleted');
      loadLinks();
    } catch {
      toast.error('Failed to delete');
    }
  };

  const handleAnalytics = async (code: string) => {
    if (analyticsCode === code) { setAnalyticsCode(null); return; }
    try {
      const resp = await fetch(`${API_BASE}/links/${code}`);
      const data = await resp.json();
      setAnalyticsData(data);
      setAnalyticsCode(code);
    } catch {
      toast.error('Failed to load analytics');
    }
  };

  const copyLink = (url: string, code: string) => {
    navigator.clipboard.writeText(url);
    setCopied(code);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Link" description="URL shortener and deep links — r.wecare.digital" />
      <div className="link-page">
        <div className="link-page-header">
          <div>
            <h1>Link</h1>
            <p>URL shortener &amp; deep links via <strong>{SHORT_DOMAIN}</strong></p>
          </div>
          <Button variant="primary" onClick={() => { setShowForm(true); generateCode(); }}>
            <PlusIcon size={14} /> Create Short Link
          </Button>
        </div>

        <div className="link-stats">
          <div className="link-stat"><div className="link-stat-val">{links.length}</div><div className="link-stat-lbl">Total Links</div></div>
          <div className="link-stat"><div className="link-stat-val">{totalClicks}</div><div className="link-stat-lbl">Total Clicks</div></div>
          <div className="link-stat"><div className="link-stat-val">{deepLinkCount}</div><div className="link-stat-lbl">Deep Links</div></div>
          <div className="link-stat"><div className="link-stat-val">{SHORT_DOMAIN}</div><div className="link-stat-lbl">Domain</div></div>
        </div>

        <div className="link-table-wrap">
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>Loading links...</div>
          ) : links.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>No links yet. Create your first short link.</div>
          ) : (
            <table className="link-table" role="table" aria-label="Short links">
              <thead>
                <tr><th>Short URL</th><th>Destination</th><th>Title</th><th>Clicks</th><th>Deep Link</th><th>Created</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {links.map(l => (
                  <React.Fragment key={l.shortCode}>
                    <tr>
                      <td><a href={l.shortUrl} target="_blank" rel="noopener noreferrer" className="link-short-a">{l.shortUrl.replace('https://', '')}</a></td>
                      <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12, color: '#6b7280' }}>{l.originalUrl}</td>
                      <td style={{ fontWeight: 500, fontSize: 13 }}>{l.title}</td>
                      <td style={{ fontWeight: 600, color: '#1a3a2a' }}>{l.clicks}</td>
                      <td>{l.deepLink ? <span className="link-deep-badge">iOS + Android</span> : <span style={{ color: '#9ca3af', fontSize: 12 }}>No</span>}</td>
                      <td style={{ fontSize: 12, color: '#6b7280' }}>{l.createdAt ? new Date(l.createdAt).toLocaleDateString() : '-'}</td>
                      <td>
                        <div className="link-actions">
                          <button className="link-act-btn" onClick={() => copyLink(l.shortUrl, l.shortCode)} title="Copy" aria-label="Copy link">
                            {copied === l.shortCode ? <span style={{fontSize:11,color:'#1a3a2a'}}>Copied</span> : <CopyIcon />}
                          </button>
                          <button className="link-act-btn" onClick={() => handleAnalytics(l.shortCode)} title="Analytics" aria-label="View analytics"><BarChartIcon /></button>
                          <button className="link-act-btn danger" onClick={() => handleDelete(l.shortCode)} title="Delete" aria-label="Delete link"><TrashIcon /></button>
                        </div>
                      </td>
                    </tr>
                    {analyticsCode === l.shortCode && analyticsData && (
                      <tr><td colSpan={7} style={{ background: '#f9fafb', padding: 12 }}>
                        <div style={{ fontSize: 12, color: '#374151' }}>
                          <strong>Recent Clicks ({(analyticsData.recentClicks || []).length})</strong>
                          {(analyticsData.recentClicks || []).length === 0 ? <p style={{ color: '#9ca3af' }}>No clicks yet</p> : (
                            <div style={{ display: 'grid', gap: 4, marginTop: 6 }}>
                              {(analyticsData.recentClicks || []).slice(0, 10).map((c: any, i: number) => (
                                <div key={i} style={{ display: 'flex', gap: 12, fontSize: 11, color: '#6b7280' }}>
                                  <span>{new Date(c.clickedAt).toLocaleString()}</span>
                                  <span>{c.platform}</span>
                                  <span>{c.sourceIp}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </td></tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Create Modal */}
        {showForm && (
          <div className="link-modal-overlay" onClick={() => setShowForm(false)} role="dialog" aria-modal="true" aria-label="Create short link">
            <div className="link-modal" onClick={e => e.stopPropagation()}>
              <div className="link-modal-bar" />
              <div className="link-modal-header">
                <h2>Create Short Link</h2>
                <button className="link-modal-close" onClick={() => setShowForm(false)} aria-label="Close">&times;</button>
              </div>
              <div className="link-modal-body">
                <label className="link-label">
                  Destination URL <span style={{ color: '#dc2626' }}>*</span>
                  <input className="link-input" type="url" placeholder="https://example.com/page" value={formUrl} onChange={e => setFormUrl(e.target.value)} autoFocus />
                </label>
                <label className="link-label">
                  Title
                  <input className="link-input" type="text" placeholder="My Link" value={formTitle} onChange={e => setFormTitle(e.target.value)} />
                </label>
                <label className="link-label">
                  Custom Code (optional)
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{ fontSize: 13, color: '#6b7280', whiteSpace: 'nowrap' }}>{SHORT_DOMAIN}/</span>
                    <input className="link-input" type="text" placeholder={formCode} value={formCode} onChange={e => setFormCode(e.target.value)} style={{ flex: 1 }} />
                    <button className="link-gen-btn" onClick={generateCode} type="button">Random</button>
                  </div>
                </label>

                <label className="link-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" checked={formDeepLink} onChange={e => setFormDeepLink(e.target.checked)} />
                  <span>Enable Deep Link (iOS / Android)</span>
                </label>

                {formDeepLink && (
                  <div className="link-deep-fields">
                    <label className="link-label">
                      iOS App URL
                      <input className="link-input" type="url" placeholder="myapp://path" value={formIosUrl} onChange={e => setFormIosUrl(e.target.value)} />
                    </label>
                    <label className="link-label">
                      Android App URL
                      <input className="link-input" type="url" placeholder="myapp://path" value={formAndroidUrl} onChange={e => setFormAndroidUrl(e.target.value)} />
                    </label>
                  </div>
                )}

                <label className="link-label">
                  Expiry Date (optional)
                  <input className="link-input" type="date" value={formExpiry} onChange={e => setFormExpiry(e.target.value)} />
                </label>
              </div>
              <div className="link-modal-footer">
                <button className="link-cancel-btn" onClick={() => setShowForm(false)}>Cancel</button>
                <Button variant="primary" onClick={handleCreate} disabled={creating || !formUrl.trim()}>
                  {creating ? 'Creating...' : 'Create Link'}
                </Button>
              </div>
            </div>
          </div>
        )}

      </div>

      {/* Styles now in flex-layout.css — no inline styles needed */}
    </Layout>
  );
};

export default LinkPage;