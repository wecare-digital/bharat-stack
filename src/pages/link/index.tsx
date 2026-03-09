/**
 * Link Page - URL Shortener & Deep Links
 * Domain: r.wecare.digital
 * Create short links, track clicks, manage deep links for iOS/Android
 */
import React, { useState, useEffect } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import Button from '../../components/ui/Button';
import { API_BASE } from '../../config/constants';

interface PageProps { signOut?: () => void; user?: any; }

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
const QRIcon = ({ size = 14 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="2" width="8" height="8" rx="1"/><rect x="14" y="2" width="8" height="8" rx="1"/><rect x="2" y="14" width="8" height="8" rx="1"/><rect x="14" y="14" width="4" height="4"/><line x1="22" y1="14" x2="22" y2="22"/><line x1="14" y1="22" x2="22" y2="22"/>
  </svg>
);

const SHORT_DOMAIN = 'r.wecare.digital';

interface ShortLink {
  id: string;
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
}

const LinkPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [links, setLinks] = useState<ShortLink[]>([
    { id: 'l1', shortCode: 'pay-wd01', shortUrl: `https://${SHORT_DOMAIN}/pay-wd01`, originalUrl: 'https://stack.wecare.digital/pay?ref=WD-PAY-A1B2C3D4&amount=2500', title: 'Payment Link - Rs 2,500', clicks: 47, createdAt: '2026-03-08T10:00:00Z', deepLink: true, iosUrl: 'wecare://pay?ref=WD-PAY-A1B2C3D4', androidUrl: 'wecare://pay?ref=WD-PAY-A1B2C3D4' },
    { id: 'l2', shortCode: 'wa-camp', shortUrl: `https://${SHORT_DOMAIN}/wa-camp`, originalUrl: 'https://stack.wecare.digital/dm/whatsapp?tab=campaign', title: 'WhatsApp Campaign', clicks: 123, createdAt: '2026-03-07T14:30:00Z' },
    { id: 'l3', shortCode: 'inv-mar', shortUrl: `https://${SHORT_DOMAIN}/inv-mar`, originalUrl: 'https://stack.wecare.digital/pay/invoices?month=march', title: 'March Invoices', clicks: 18, createdAt: '2026-03-06T09:00:00Z', deepLink: true, iosUrl: 'wecare://pay/invoices', androidUrl: 'wecare://pay/invoices' },
  ]);

  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  // Create form
  const [showForm, setShowForm] = useState(false);
  const [formUrl, setFormUrl] = useState('');
  const [formTitle, setFormTitle] = useState('');
  const [formCode, setFormCode] = useState('');
  const [formDeepLink, setFormDeepLink] = useState(false);
  const [formIosUrl, setFormIosUrl] = useState('');
  const [formAndroidUrl, setFormAndroidUrl] = useState('');
  const [formExpiry, setFormExpiry] = useState('');

  // Stats
  const totalClicks = links.reduce((s, l) => s + l.clicks, 0);
  const deepLinkCount = links.filter(l => l.deepLink).length;

  const generateCode = () => {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let code = '';
    for (let i = 0; i < 6; i++) code += chars[Math.floor(Math.random() * chars.length)];
    setFormCode(code);
  };

  const handleCreate = async () => {
    if (!formUrl.trim()) return;
    setCreating(true);
    const code = formCode.trim() || Math.random().toString(36).slice(2, 8);
    try {
      await fetch(`${API_BASE}/links`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shortCode: code,
          originalUrl: formUrl,
          title: formTitle || formUrl,
          deepLink: formDeepLink,
          iosUrl: formIosUrl || undefined,
          androidUrl: formAndroidUrl || undefined,
          expiresAt: formExpiry || undefined,
        }),
      });
    } catch { /* API not deployed yet */ }

    setLinks(prev => [{
      id: `l${Date.now()}`,
      shortCode: code,
      shortUrl: `https://${SHORT_DOMAIN}/${code}`,
      originalUrl: formUrl,
      title: formTitle || formUrl,
      clicks: 0,
      createdAt: new Date().toISOString(),
      deepLink: formDeepLink,
      iosUrl: formIosUrl || undefined,
      androidUrl: formAndroidUrl || undefined,
      expiresAt: formExpiry || undefined,
    }, ...prev]);

    setFormUrl(''); setFormTitle(''); setFormCode(''); setFormDeepLink(false);
    setFormIosUrl(''); setFormAndroidUrl(''); setFormExpiry('');
    setShowForm(false);
    setCreating(false);
  };

  const copyLink = (url: string, id: string) => {
    navigator.clipboard.writeText(url);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const deleteLink = (id: string) => {
    setLinks(prev => prev.filter(l => l.id !== id));
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Link | WECARE.DIGITAL" description="URL shortener and deep links — r.wecare.digital" />
      <div className="link-page">
        <div className="link-page-header">
          <div>
            <h1>Link</h1>
            <p>URL shortener &amp; deep links via <strong>{SHORT_DOMAIN}</strong></p>
          </div>
          <Button variant="primary" onClick={() => { setShowForm(true); generateCode(); }}>
            <LinkIcon size={14} /> Create Short Link
          </Button>
        </div>

        {/* Stats */}
        <div className="link-stats">
          <div className="link-stat"><div className="link-stat-val">{links.length}</div><div className="link-stat-lbl">Total Links</div></div>
          <div className="link-stat"><div className="link-stat-val">{totalClicks}</div><div className="link-stat-lbl">Total Clicks</div></div>
          <div className="link-stat"><div className="link-stat-val">{deepLinkCount}</div><div className="link-stat-lbl">Deep Links</div></div>
          <div className="link-stat"><div className="link-stat-val">{SHORT_DOMAIN}</div><div className="link-stat-lbl">Domain</div></div>
        </div>

        {/* Links Table */}
        <div className="link-table-wrap">
          <table className="link-table">
            <thead>
              <tr><th>Short URL</th><th>Destination</th><th>Title</th><th>Clicks</th><th>Deep Link</th><th>Created</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {links.map(l => (
                <tr key={l.id}>
                  <td>
                    <div className="link-short-url">
                      <a href={l.shortUrl} target="_blank" rel="noopener noreferrer">{l.shortUrl}</a>
                    </div>
                  </td>
                  <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12, color: '#6b7280' }}>{l.originalUrl}</td>
                  <td style={{ fontWeight: 500, fontSize: 13 }}>{l.title}</td>
                  <td style={{ fontWeight: 600, color: '#1a3a2a' }}>{l.clicks}</td>
                  <td>{l.deepLink ? <span className="link-deep-badge">iOS + Android</span> : <span style={{ color: '#9ca3af', fontSize: 12 }}>No</span>}</td>
                  <td style={{ fontSize: 12, color: '#6b7280' }}>{new Date(l.createdAt).toLocaleDateString()}</td>
                  <td>
                    <div className="link-actions">
                      <button className="link-act-btn" onClick={() => copyLink(l.shortUrl, l.id)} title="Copy">
                        {copied === l.id ? <span style={{fontSize:11,color:'#1a3a2a'}}>Copied</span> : <CopyIcon />}
                      </button>
                      <button className="link-act-btn" title="Analytics"><BarChartIcon /></button>
                      <button className="link-act-btn" title="QR Code"><QRIcon /></button>
                      <button className="link-act-btn danger" onClick={() => deleteLink(l.id)} title="Delete"><TrashIcon /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Create Modal */}
        {showForm && (
          <div className="link-modal-bg" onClick={() => setShowForm(false)}>
            <div className="link-modal" onClick={e => e.stopPropagation()}>
              <div className="link-modal-head">
                <span>Create Short Link</span>
                <button onClick={() => setShowForm(false)} className="link-modal-close">x</button>
              </div>
              <div className="link-modal-body">
                <div className="link-field">
                  <label>Destination URL *</label>
                  <input type="url" value={formUrl} onChange={e => setFormUrl(e.target.value)} placeholder="https://stack.wecare.digital/..." />
                </div>
                <div className="link-field">
                  <label>Title</label>
                  <input type="text" value={formTitle} onChange={e => setFormTitle(e.target.value)} placeholder="Payment Link, Campaign, etc." />
                </div>
                <div className="link-field">
                  <label>Custom Short Code</label>
                  <div className="link-code-row">
                    <span className="link-code-prefix">https://{SHORT_DOMAIN}/</span>
                    <input type="text" value={formCode} onChange={e => setFormCode(e.target.value)} placeholder="auto" style={{ flex: 1 }} />
                    <Button variant="secondary" size="sm" onClick={generateCode}>Random</Button>
                  </div>
                </div>
                <div className="link-field">
                  <label>Expiry (optional)</label>
                  <input type="date" value={formExpiry} onChange={e => setFormExpiry(e.target.value)} />
                </div>
                <div className="link-field">
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={formDeepLink} onChange={e => setFormDeepLink(e.target.checked)} style={{ width: 18, height: 18 }} />
                    Enable Deep Link (iOS + Android app)
                  </label>
                </div>
                {formDeepLink && (
                  <>
                    <div className="link-field">
                      <label>iOS Deep Link URL</label>
                      <input type="text" value={formIosUrl} onChange={e => setFormIosUrl(e.target.value)} placeholder="wecare://pay?ref=..." />
                    </div>
                    <div className="link-field">
                      <label>Android Deep Link URL</label>
                      <input type="text" value={formAndroidUrl} onChange={e => setFormAndroidUrl(e.target.value)} placeholder="wecare://pay?ref=..." />
                    </div>
                  </>
                )}
              </div>
              <div className="link-modal-foot">
                <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
                <Button variant="primary" onClick={handleCreate} disabled={!formUrl.trim() || creating} loading={creating}>Create Link</Button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .link-page{padding:16px 20px;max-width:1100px;margin:0 auto}
        .link-page-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}
        .link-page-header h1{font-size:22px;font-weight:700;color:#111827;margin:0 0 4px}
        .link-page-header p{font-size:13px;color:#6b7280;margin:0}
        .link-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
        .link-stat{padding:16px;background:#fff;border:1px solid #e5e7eb;border-radius:10px}
        .link-stat-val{font-size:20px;font-weight:700;color:#1a3a2a}
        .link-stat-lbl{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
        .link-table-wrap{overflow-x:auto;border:1px solid #e5e7eb;border-radius:10px;background:#fff}
        .link-table{width:100%;border-collapse:collapse;font-size:13px}
        .link-table th{padding:10px 14px;text-align:left;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#6b7280;background:#f9fafb;border-bottom:1px solid #e5e7eb}
        .link-table td{padding:10px 14px;border-bottom:1px solid #f3f4f6}
        .link-table tr:last-child td{border-bottom:none}
        .link-short-url a{color:#1a3a2a;font-weight:600;font-size:13px;text-decoration:none}
        .link-short-url a:hover{text-decoration:underline}
        .link-deep-badge{padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;background:#f0fdf4;color:#1a3a2a;border:1px solid #d1f470}
        .link-actions{display:flex;gap:4px}
        .link-act-btn{width:32px;height:32px;border:1px solid #e5e7eb;border-radius:6px;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#6b7280;transition:all .15s}
        .link-act-btn:hover{border-color:#1a3a2a;color:#1a3a2a;background:#f9fdf0}
        .link-act-btn.danger:hover{border-color:#dc2626;color:#dc2626;background:#fef2f2}
        .link-modal-bg{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.3)}
        .link-modal{background:#fff;border-radius:13px;width:100%;max-width:520px;box-shadow:0 20px 60px rgba(0,0,0,.15);border:1.5px solid #d1f470;overflow:hidden;margin:16px}
        .link-modal-head{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid rgba(209,244,112,.3);font-size:16px;font-weight:600;color:#111827}
        .link-modal-close{width:28px;height:28px;border-radius:8px;background:rgba(209,244,112,.15);border:none;cursor:pointer;font-size:16px;color:#1a3a2a;display:flex;align-items:center;justify-content:center}
        .link-modal-body{padding:20px;display:flex;flex-direction:column;gap:14px}
        .link-modal-foot{display:flex;justify-content:flex-end;gap:8px;padding:12px 20px;border-top:1px solid rgba(209,244,112,.3)}
        .link-field label{display:block;font-size:12px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px}
        .link-field input,.link-field select{width:100%;padding:10px 12px;border:1.5px solid #d1f470;border-radius:13px;font-size:14px;color:#1a1a1a;background:#fff;min-height:44px;font-family:inherit;box-sizing:border-box}
        .link-field input:focus{outline:none;box-shadow:0 0 0 3px rgba(209,244,112,.3)}
        .link-code-row{display:flex;align-items:center;gap:6px}
        .link-code-prefix{font-size:12px;color:#6b7280;white-space:nowrap;padding:10px 0 10px 12px;background:#f9fafb;border:1.5px solid #d1f470;border-right:none;border-radius:13px 0 0 13px;min-height:44px;display:flex;align-items:center}
        .link-code-row input{border-radius:0 13px 13px 0!important;border-left:none!important}
        @media(max-width:768px){.link-stats{grid-template-columns:repeat(2,1fr)}.link-page-header{flex-direction:column;gap:12px}.link-modal{position:fixed;bottom:0;left:0;right:0;top:auto;max-width:100%;margin:0;border-radius:16px 16px 0 0;max-height:85vh;overflow-y:auto}.link-modal-bg{align-items:flex-end}}
        @media(max-width:480px){.link-stats{grid-template-columns:1fr}.link-page{padding:12px}}
      `}</style>
    </Layout>
  );
};

export default LinkPage;