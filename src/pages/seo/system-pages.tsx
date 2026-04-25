/**
 * System Pages SEO — Dedicated noindex monitoring & audit
 * Tabs: Pages | Audit | Logs | Instructions
 * Schema: noindex/nofollow — monitor for accidental indexing
 * Uses /api/seo-tools/page-clean and /api/seo-tools/page-audit
 */
import React, { useState, useCallback, useEffect } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import InstructionsContent from './InstructionsContent';

interface PageProps { signOut?: () => void; user?: any; }
interface SystemPage { path: string; name: string; url: string; }
interface Audit {
  id: string; blogSlug: string; blogTitle: string; pageType: string;
  currentSeoTitle: string; suggestedSeoTitle: string;
  currentMetaDescription: string; suggestedMetaDescription: string;
  focusKeyword: string; secondaryKeywords: string[];
  suggestedJsonLd: any; internalLinkSuggestions: any[]; imageAltSuggestions: any[];
  seoScoreBefore: number; seoScoreAfter: number; scoreBreakdown: any;
  warnings: string[]; fullAiResponse: any; aiModel: string;
  status: string; createdAt: string; appliedAt?: string;
}
type Tab = 'pages' | 'audit' | 'logs' | 'instructions';
const th: React.CSSProperties = { padding: '8px 10px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: '#6b7280' };
const td: React.CSSProperties = { padding: '6px 10px' };
const btn: React.CSSProperties = { padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 11, fontFamily: 'inherit' };
const BASE = 'https://www.wecare.digital';

const PAGES: SystemPage[] = [
  { path: '/cart-page', name: 'Cart', url: `${BASE}/cart-page` },
  { path: '/checkout', name: 'Checkout', url: `${BASE}/checkout` },
  { path: '/thank-you', name: 'Thank You', url: `${BASE}/thank-you` },
  { path: '/login', name: 'Login', url: `${BASE}/login` },
  { path: '/signup', name: 'Sign Up', url: `${BASE}/signup` },
  { path: '/404', name: '404 Not Found', url: `${BASE}/404` },
  { path: '/members-area', name: 'Members Area', url: `${BASE}/members-area` },
  { path: '/order-confirmation', name: 'Order Confirmation', url: `${BASE}/order-confirmation` },
  { path: '/my-account', name: 'My Account', url: `${BASE}/my-account` },
  { path: '/my-orders', name: 'My Orders', url: `${BASE}/my-orders` },
  { path: '/my-addresses', name: 'My Addresses', url: `${BASE}/my-addresses` },
  { path: '/my-wallet', name: 'My Wallet', url: `${BASE}/my-wallet` },
];

const SystemPagesManager: React.FC<PageProps> = ({ signOut, user }) => {
  const [tab, setTab] = useState<Tab>('pages');
  const [audits, setAudits] = useState<Audit[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [auditingSlug, setAuditingSlug] = useState<string | null>(null);
  const [bulkRunning, setBulkRunning] = useState<string | null>(null);
  const [selectedAudit, setSelectedAudit] = useState<Audit | null>(null);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [log, setLog] = useState<string[]>([]);
  const addLog = (m: string) => setLog(p => [...p, `[${new Date().toLocaleTimeString()}] ${m}`]);

  const fetchAudits = useCallback(async () => {
    try { const d = await (await fetch('/api/seo-tools/seo-logs?type=audits')).json(); if (d.ok) setAudits((d.audits || []).filter((a: Audit) => a.pageType === 'system')); } catch {}
  }, []);
  const fetchLogs = useCallback(async () => {
    try { const d = await (await fetch('/api/seo-tools/seo-logs?type=logs')).json(); if (d.ok) setLogs(d.logs || []); } catch {}
  }, []);
  useEffect(() => { fetchAudits(); }, [fetchAudits]);

  const getAudit = (slug: string) => audits.filter(a => a.blogSlug === slug).sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt))[0];

  const cleanPage = async (path: string, name: string) => {
    addLog(`Cleaning "${name}"...`);
    try { const d = await (await fetch('/api/seo-tools/page-clean', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, name, pageType: 'system' }) })).json();
      if (d.ok) { addLog(`Cleaned: ${d.cleaned.auditsRemoved} audit(s) removed`); await fetchAudits(); } else addLog(`Clean failed: ${d.error}`);
    } catch (e: any) { addLog(e.message); }
  };
  const runAudit = async (path: string, name: string) => {
    setAuditingSlug(path); addLog(`Auditing "${name}"...`);
    try { const d = await (await fetch('/api/seo-tools/page-audit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, name, pageType: 'system' }) })).json();
      if (d.ok) { addLog(`Done: ${d.audit.seoScoreBefore} > ${d.audit.seoScoreAfter} | $${d.log?.costEstimate || 0}`); await fetchAudits(); setSelectedAudit(d.audit); setTab('audit'); }
      else addLog(`Failed: ${d.error}`);
    } catch (e: any) { addLog(e.message); } setAuditingSlug(null);
  };
  const cleanAndAudit = async (path: string, name: string) => { await cleanPage(path, name); await runAudit(path, name); };
  const handleAction = async (id: string, action: string) => {
    addLog(`${action} ${id.substring(0, 20)}...`);
    try { const d = await (await fetch('/api/seo-tools/seo-approve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auditId: id, action, reviewedBy: user?.username || 'admin' }) })).json();
      if (d.ok) { addLog(`${action} done`); await fetchAudits(); if (selectedAudit?.id === id) setSelectedAudit(d.audit); } else addLog(d.error);
    } catch (e: any) { addLog(e.message); }
  };
  const bulkClean = async (paths: string[]) => { setBulkRunning('clean'); for (const p of paths) { const pg = PAGES.find(x => x.path === p); await cleanPage(p, pg?.name || p); await new Promise(r => setTimeout(r, 500)); } addLog('Bulk clean done'); setBulkRunning(null); };
  const bulkAudit = async (paths: string[]) => { setBulkRunning('audit'); let ok = 0; for (const p of paths) { const pg = PAGES.find(x => x.path === p); addLog(`Auditing ${ok+1}/${paths.length}`); try { const d = await (await fetch('/api/seo-tools/page-audit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: p, name: pg?.name || p, pageType: 'system' }) })).json(); if (d.ok) ok++; } catch {} await new Promise(r => setTimeout(r, 1000)); } addLog(`Bulk audit done: ${ok}/${paths.length}`); await fetchAudits(); setBulkRunning(null); };

  const toggleSel = (s: string) => setSelected(p => { const n = new Set(p); n.has(s) ? n.delete(s) : n.add(s); return n; });
  const filtered = search ? PAGES.filter(p => { const q = search.toLowerCase(); return p.name.toLowerCase().includes(q) || p.path.toLowerCase().includes(q); }) : PAGES;
  const selAll = () => setSelected(new Set(filtered.map(p => p.path)));
  const selNone = () => setSelected(new Set());

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="System Pages SEO" description="noindex monitoring" />
      <div className="inner-page">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div>
            <h1 className="inner-page-title" style={{ margin: 0 }}>System Pages SEO</h1>
            <p style={{ color: '#6b7280', fontSize: 13, margin: '4px 0 0' }}>{PAGES.length} system pages | noindex monitoring | {audits.length} audited</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '2px solid #e5e7eb', paddingBottom: 8 }}>
          {([['pages','⚙️ Pages'],['audit','🔍 Audit'],['logs','📋 Logs'],['instructions','📖 Instructions']] as [Tab,string][]).map(([t,l]) => (
            <button key={t} onClick={() => { setTab(t); if (t==='logs') fetchLogs(); }} style={{ padding: '8px 16px', borderRadius: '8px 8px 0 0', border: 'none', cursor: 'pointer', fontSize: 13, background: tab===t ? '#d1f470' : 'transparent', color: tab===t ? '#1a3a2a' : '#6b7280', fontWeight: tab===t ? 600 : 400 }}>{l}</button>
          ))}
        </div>

        {tab === 'pages' && (<>
          <div className="card" style={{ padding: 16, marginBottom: 16, borderLeft: '4px solid #f59e0b' }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, color: '#92400e', marginBottom: 4 }}>System Pages — noindex by default</h3>
            <p style={{ fontSize: 12, color: '#6b7280', margin: 0 }}>These pages should have <code style={{ background: '#f3f4f6', padding: '1px 4px', borderRadius: 3 }}>noindex, nofollow</code>. Monitor for accidental indexing.</p>
          </div>
          <div style={{ marginBottom: 10 }}><input value={search} onChange={e => { setSearch(e.target.value); selNone(); }} placeholder="🔍 Search system pages..." style={{ width: '100%', padding: '8px 14px', borderRadius: 8, border: '1.5px solid #e5e7eb', fontSize: 13, fontFamily: 'inherit' }} /></div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
            {selected.size > 0 && (<div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: '#6b7280' }}>{selected.size} selected</span>
              <button onClick={() => bulkClean([...selected])} disabled={!!bulkRunning} style={{ ...btn, background: '#fef3c7', fontWeight: 600 }}>{bulkRunning==='clean' ? 'Cleaning...' : `Bulk Clean (${selected.size})`}</button>
              <button onClick={() => bulkAudit([...selected])} disabled={!!bulkRunning} style={{ ...btn, background: '#d1f470', fontWeight: 600 }}>{bulkRunning==='audit' ? 'Auditing...' : `Bulk Audit (${selected.size})`}</button>
              <button onClick={selNone} style={{ ...btn, background: '#f3f4f6' }}>Clear</button>
            </div>)}
            <div style={{ flex: 1 }} />
            {selected.size === 0 && filtered.length > 0 && <button onClick={selAll} style={{ ...btn, background: '#f3f4f6' }}>Select All ({filtered.length})</button>}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead><tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                <th style={{ ...th, width: 30 }}><input type="checkbox" checked={selected.size===filtered.length && filtered.length>0} onChange={() => selected.size===filtered.length ? selNone() : selAll()} /></th>
                <th style={th}>#</th><th style={th}>Page</th><th style={th}>Path</th><th style={{ ...th, textAlign: 'center' }}>Robots</th><th style={{ ...th, textAlign: 'center' }}>Score</th><th style={{ ...th, textAlign: 'center' }}>Status</th><th style={{ ...th, textAlign: 'center' }}>Actions</th>
              </tr></thead>
              <tbody>{filtered.map((p, i) => { const a = getAudit(p.path); const busy = auditingSlug===p.path; return (
                <tr key={p.path} style={{ borderBottom: '1px solid #f3f4f6', background: selected.has(p.path) ? '#f0fdf4' : undefined }}>
                  <td style={td}><input type="checkbox" checked={selected.has(p.path)} onChange={() => toggleSel(p.path)} /></td>
                  <td style={td}>{i+1}</td>
                  <td style={{ ...td, fontWeight: 600 }}>{p.name}</td>
                  <td style={{ ...td, fontSize: 11, color: '#6b7280', fontFamily: 'monospace' }}>{p.path}</td>
                  <td style={{ ...td, textAlign: 'center' }}><span style={{ padding: '2px 8px', background: '#fef3c7', color: '#92400e', borderRadius: 6, fontSize: 10, fontWeight: 600 }}>noindex</span></td>
                  <td style={{ ...td, textAlign: 'center' }}>{a ? <><span style={{ color: '#ef4444', fontSize: 11 }}>{a.seoScoreBefore}</span><span style={{ color: '#9ca3af' }}>{' > '}</span><span style={{ color: '#22c55e', fontWeight: 700, fontSize: 11 }}>{a.seoScoreAfter}</span></> : '-'}</td>
                  <td style={{ ...td, textAlign: 'center' }}>{a ? <StatusBadge status={a.status} /> : <span style={{ color: '#9ca3af', fontSize: 10 }}>-</span>}</td>
                  <td style={{ ...td, textAlign: 'center' }}><div style={{ display: 'flex', gap: 3, justifyContent: 'center' }}>
                    <button onClick={() => cleanAndAudit(p.path, p.name)} disabled={busy||!!bulkRunning} style={{ ...btn, background: '#fef3c7' }}>Clean+Audit</button>
                    <button onClick={() => runAudit(p.path, p.name)} disabled={busy||!!bulkRunning} style={{ ...btn, background: busy ? '#e5e7eb' : '#d1f470' }}>{busy ? 'Running...' : 'Audit'}</button>
                    {a && <button onClick={() => { setSelectedAudit(a); setTab('audit'); }} style={{ ...btn, background: '#f3f4f6' }}>View</button>}
                    <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ ...btn, background: '#f3f4f6', textDecoration: 'none', color: '#374151', display: 'inline-flex', alignItems: 'center' }}>Open</a>
                  </div></td>
                </tr>); })}</tbody>
            </table>
          </div>
          <div style={{ marginTop: 8, fontSize: 12, color: '#6b7280' }}>{filtered.length} system pages</div>
          <div className="card" style={{ padding: 16, marginTop: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>System Pages SEO Rules</h3>
            <div style={{ display: 'grid', gap: 8, fontSize: 12, color: '#6b7280', lineHeight: 1.6 }}>
              <div><span style={{ fontWeight: 600, color: '#374151' }}>Cart / Checkout:</span> noindex, nofollow. No JSON-LD. Canonical self-referencing.</div>
              <div><span style={{ fontWeight: 600, color: '#374151' }}>404 Page:</span> HTTP 404 status. No indexing. Custom design recommended.</div>
              <div><span style={{ fontWeight: 600, color: '#374151' }}>Login / Signup:</span> noindex. Prevent password pages from search.</div>
              <div><span style={{ fontWeight: 600, color: '#374151' }}>Members Area:</span> noindex, nofollow. All member pages behind auth.</div>
              <div><span style={{ fontWeight: 600, color: '#374151' }}>Order Pages:</span> noindex. Transactional pages with personal data.</div>
            </div>
          </div>
        </>)}
        {tab === 'audit' && <AuditDetail audit={selectedAudit} audits={audits} onSelect={setSelectedAudit} onAction={handleAction} />}
        {tab === 'logs' && <LogsView logs={logs} />}
        {tab === 'instructions' && <InstructionsContent />}
        {log.length > 0 && (<div className="card" style={{ padding: 16, marginTop: 16 }}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}><h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Activity</h3><button className="btn btn-secondary" onClick={() => setLog([])} style={{ fontSize: 12, padding: '4px 12px' }}>Clear</button></div><pre style={{ background: '#0f1117', color: '#a3e635', padding: 16, borderRadius: 8, fontSize: 12, lineHeight: 1.6, maxHeight: 200, overflowY: 'auto', fontFamily: 'Consolas, Monaco, monospace', whiteSpace: 'pre-wrap' }}>{log.join('\n')}</pre></div>)}
      </div>
    </Layout>
  );
};

function AuditDetail({ audit, audits, onSelect, onAction }: { audit: Audit|null; audits: Audit[]; onSelect: (a: Audit) => void; onAction: (id: string, action: string) => void }) {
  if (!audit) return (<div>{audits.length===0 ? <div className="card" style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>No audits yet. Run an audit from Pages tab.</div> :
    <div style={{ display: 'grid', gap: 8 }}>{audits.slice(0,20).map(a => (
      <button key={a.id} onClick={() => onSelect(a)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: '#fff', border: '1.5px solid #e5e7eb', borderRadius: 10, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit', width: '100%' }}>
        <div><div style={{ fontSize: 14, fontWeight: 600 }}>{a.blogTitle}</div><div style={{ fontSize: 11, color: '#6b7280' }}>{a.blogSlug} — {new Date(a.createdAt).toLocaleString()}</div></div>
        <div><span style={{ color: '#ef4444' }}>{a.seoScoreBefore}</span> {'>'} <span style={{ color: '#22c55e', fontWeight: 700 }}>{a.seoScoreAfter}</span></div>
      </button>))}</div>}</div>);
  const ai = audit.fullAiResponse || {};
  return (<div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <div><h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>{audit.blogTitle}</h2><div style={{ fontSize: 12, color: '#6b7280' }}>{audit.blogSlug} — {new Date(audit.createdAt).toLocaleString()} — {audit.status}</div></div>
      <button onClick={() => onSelect(null as any)} style={{ ...btn, background: '#f3f4f6' }}>Back</button>
    </div>
    <div className="card" style={{ padding: 16, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
      <div style={{ textAlign: 'center' }}><div style={{ fontSize: 11, color: '#6b7280' }}>BEFORE</div><div style={{ fontSize: 32, fontWeight: 800, color: '#ef4444' }}>{audit.seoScoreBefore}</div></div>
      <div style={{ fontSize: 24, color: '#9ca3af' }}>{'>'}</div>
      <div style={{ textAlign: 'center' }}><div style={{ fontSize: 11, color: '#6b7280' }}>AFTER</div><div style={{ fontSize: 32, fontWeight: 800, color: '#22c55e' }}>{audit.seoScoreAfter}</div></div>
      <div style={{ flex: 1 }} />
      {audit.status==='pending_review' && <div style={{ display: 'flex', gap: 8 }}><button onClick={() => onAction(audit.id,'approve')} style={{ ...btn, background: '#d1f470', fontWeight: 600, padding: '6px 16px' }}>Approve</button><button onClick={() => onAction(audit.id,'reject')} style={{ ...btn, background: '#fee2e2', padding: '6px 16px' }}>Reject</button></div>}
      {audit.status==='approved' && <button onClick={() => onAction(audit.id,'apply')} style={{ ...btn, background: '#d1f470', fontWeight: 600, padding: '6px 16px' }}>Apply</button>}
      {audit.status==='applied' && <span style={{ padding: '6px 14px', background: '#dcfce7', color: '#166534', borderRadius: 8, fontSize: 12, fontWeight: 600 }}>Applied</span>}
    </div>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
      <div className="card" style={{ padding: 16 }}><h3 style={{ fontSize: 13, fontWeight: 600, color: '#ef4444', marginBottom: 12 }}>Current</h3><CF label="SEO Title" value={audit.currentSeoTitle} max={60} /><CF label="Meta Description" value={audit.currentMetaDescription} max={160} /></div>
      <div className="card" style={{ padding: 16 }}><h3 style={{ fontSize: 13, fontWeight: 600, color: '#22c55e', marginBottom: 12 }}>AI Suggested</h3><CF label="SEO Title" value={audit.suggestedSeoTitle} max={60} /><CF label="Meta Description" value={audit.suggestedMetaDescription} max={160} /></div>
    </div>
    <div className="card" style={{ padding: 16, marginBottom: 16 }}><h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>🏷️ Meta Tags</h3><div style={{ display: 'grid', gap: 4 }}>{(ai.metaTags || []).map((t: any, i: number) => <div key={i} style={{ display: 'flex', gap: 8, padding: '3px 8px', background: i%2===0?'#f9fafb':'#fff', borderRadius: 4, fontSize: 11 }}><span style={{ color: '#6b7280', minWidth: 160, fontFamily: 'monospace' }}>{t.property || t.name}</span><span style={{ color: '#111827', flex: 1, wordBreak: 'break-word' }}>{t.content}</span></div>)}</div></div>
    {audit.warnings?.length > 0 && <div className="card" style={{ padding: 16, marginBottom: 16, borderLeft: '4px solid #f59e0b' }}><h3 style={{ fontSize: 13, fontWeight: 600, color: '#92400e', marginBottom: 8 }}>⚠️ Warnings</h3>{audit.warnings.map((w: string, i: number) => <div key={i} style={{ fontSize: 12, color: '#92400e', padding: '2px 0' }}>- {w}</div>)}</div>}
    {audit.scoreBreakdown && <div className="card" style={{ padding: 16, marginBottom: 16 }}><h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📊 Score Breakdown</h3><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>{Object.entries(audit.scoreBreakdown).map(([k,v]:any) => <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px', background: '#f9fafb', borderRadius: 6, fontSize: 11 }}><span style={{ color: '#6b7280' }}>{k}</span><span><span style={{ color: '#ef4444' }}>{v.before}</span>{' > '}<span style={{ color: '#22c55e', fontWeight: 600 }}>{v.after}</span>/{v.max}</span></div>)}</div></div>}
    {audit.suggestedJsonLd && <div className="card" style={{ padding: 16 }}><h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>🏗️ JSON-LD</h3><pre style={{ background: '#0f1117', color: '#a3e635', padding: 16, borderRadius: 8, fontSize: 11, maxHeight: 400, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(audit.suggestedJsonLd, null, 2)}</pre></div>}
  </div>);
}
function CF({ label, value, max }: { label: string; value: string; max: number }) { const len = value?.length || 0; return (<div style={{ marginBottom: 12 }}><div style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase', marginBottom: 2 }}>{label}</div><div style={{ fontSize: 12, color: '#111827', lineHeight: 1.5 }}>{value || '(empty)'}</div>{value && <div style={{ fontSize: 10, color: len > max ? '#ef4444' : '#22c55e', marginTop: 2 }}>{len}/{max} {len > max ? 'over limit' : 'ok'}</div>}</div>); }
function StatusBadge({ status }: { status: string }) { const bg = status==='applied'?'#dcfce7':status==='approved'?'#dbeafe':status==='pending_review'?'#fef3c7':'#f3f4f6'; const color = status==='applied'?'#166534':status==='approved'?'#1e40af':status==='pending_review'?'#92400e':'#6b7280'; return <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 600, background: bg, color }}>{status.replace('_',' ')}</span>; }
function LogsView({ logs }: { logs: any[] }) { if (!logs.length) return <div className="card" style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>No logs yet.</div>; return (<div style={{ overflowX: 'auto' }}><table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}><thead><tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}><th style={th}>Time</th><th style={th}>Slug</th><th style={th}>Model</th><th style={{ ...th, textAlign: 'center' }}>Tokens</th><th style={{ ...th, textAlign: 'center' }}>Cost</th><th style={{ ...th, textAlign: 'center' }}>Status</th></tr></thead><tbody>{logs.slice().reverse().map((l,i) => (<tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}><td style={td}>{new Date(l.createdAt).toLocaleString()}</td><td style={td}>{l.blogSlug}</td><td style={{ ...td, fontSize: 10 }}>{l.model?.split('.').pop()?.substring(0,25)}</td><td style={{ ...td, textAlign: 'center' }}>{l.inputTokens}+{l.outputTokens}</td><td style={{ ...td, textAlign: 'center', fontWeight: 600 }}>${l.costEstimate}</td><td style={{ ...td, textAlign: 'center', color: l.status==='success'?'#22c55e':'#ef4444' }}>{l.status}</td></tr>))}</tbody></table></div>); }
export default SystemPagesManager;
