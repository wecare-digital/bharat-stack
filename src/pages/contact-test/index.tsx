import React, { useState } from 'react';
import Head from 'next/head';

const LOGO = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';
const B = (bg: string, c: string, bd?: string): React.CSSProperties => ({
  padding: '10px 20px', background: bg, color: c,
  border: bd || '1.5px solid ' + bg, borderRadius: 13,
  fontSize: 14, fontWeight: 500, cursor: 'pointer',
  transition: 'all 0.15s', fontFamily: 'inherit', lineHeight: 1,
});
const INP = (): React.CSSProperties => ({
  width: '100%', height: 44, padding: '10px 14px', fontSize: 14, color: '#111827',
  background: '#fff', border: '1.5px solid #d1f470', borderRadius: 13,
  outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
});
const TH: React.CSSProperties = { padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: '#1a3a2a', textTransform: 'uppercase', letterSpacing: 0.5 };
const TD: React.CSSProperties = { padding: '12px 16px', color: '#111827' };
const IB: React.CSSProperties = { width: 36, height: 36, borderRadius: 10, background: '#d1f470', display: 'flex', alignItems: 'center', justifyContent: 'center' };
const SL: React.CSSProperties = { textTransform: 'uppercase', letterSpacing: 1, fontSize: 12, color: '#1a3a2a', fontWeight: 600, margin: 0, paddingBottom: 10, borderBottom: '1px solid #d1f470' };

const Ic = ({ d, s = 18, c = '#1a3a2a' }: { d: string; s?: number; c?: string }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d}/></svg>
);
const IcUser = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>);
const IcChat = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>);
const IcFile = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>);
const IcSearch = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>);
const IcBell = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>);
const IcSettings = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>);
const IcPlus = ({ s = 14 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>);
const IcSend = ({ s = 16 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>);
const IcTrash = ({ s = 16 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>);
const IcEdit = ({ s = 16 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>);
const IcWarn = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>);
const IcBox = ({ s = 48 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#d1f470" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0022 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>);
const IcCheck = ({ s = 14 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>);
const IcX = ({ s = 14 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>);
const IcInfo = ({ s = 14 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>);
const IcDownload = ({ s = 14 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>);
const IcHome = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>);
const IcMail = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22 6 12 13 2 6"/></svg>);
const IcPhone = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>);
const IcBarChart = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>);
const IcZap = ({ s = 18 }: { s?: number }) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>);

const ContactTestPage: React.FC = () => {
  const [at, sAt] = useState(0);
  const [cp, sCp] = useState(1);
  const [tg, sTg] = useState([true, false, true]);
  const [ac, sAc] = useState<number | null>(0);
  const [inboxSel, setInboxSel] = useState(0);
  const [pgTab, setPgTab] = useState(0);
  const tabs = ['Overview', 'Messages', 'Settings'];
  const st = [{ l: 'Contacts', v: 42, X: IcUser }, { l: 'Messages', v: 84, X: IcChat }, { l: 'Templates', v: 126, X: IcFile }];
  const fq = [
    { t: 'What is WECARE.DIGITAL?', c: 'Unified CRM for WhatsApp, SMS, Voice, Email.' },
    { t: 'How does AI work?', c: 'Bedrock-powered auto-replies and smart routing.' },
    { t: 'Is it secure?', c: 'E2E encryption, AWS infra, Cognito auth.' },
  ];
  const cl = [
    { bg: '#d1f470', l: 'Lime' }, { bg: '#1a3a2a', l: 'Dark Green' },
    { bg: '#1a1a1a', l: 'Text' }, { bg: '#374151', l: 'Secondary' },
    { bg: '#ffffff', l: 'White' }, { bg: '#dc2626', l: 'Danger' },
  ];
  const inboxChats = [
    { name: 'Alice Johnson', msg: 'Thanks for the update!', time: '2m', unread: 2, online: true },
    { name: 'Bob Smith', msg: 'When is the delivery?', time: '15m', unread: 0, online: false },
    { name: 'Carol Davis', msg: 'I need help with my order', time: '1h', unread: 1, online: true },
    { name: 'David Lee', msg: 'Payment confirmed', time: '3h', unread: 0, online: false },
    { name: 'Eve Wilson', msg: 'Can you send the invoice?', time: '5h', unread: 3, online: true },
  ];

  return (
    <>
      <Head><title>Design Reference | Bharat Stack by WECARE.DIGITAL</title></Head>
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '120px 24px 60px', fontFamily: "'Inter',system-ui,sans-serif" }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 4 }}>
          <div style={{ width: 6, height: 36, borderRadius: 3, background: '#d1f470' }} />
          <h1 style={{ fontSize: 32, fontWeight: 700, color: '#1a1a1a', margin: 0 }}>Design Reference</h1>
        </div>
        <p style={{ fontSize: 15, color: '#1a3a2a', marginBottom: 48, paddingLeft: 20 }}>Lime + Dark Green — complete showcase</p>

        {/* COLOR PALETTE */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Color Palette</h2>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 20 }}>
            {cl.map((c, i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <div style={{ width: 64, height: 64, borderRadius: 13, background: c.bg, border: c.bg === '#ffffff' ? '1.5px solid #d1f470' : 'none' }} />
                <div style={{ fontSize: 11, fontWeight: 600, color: '#1a3a2a', marginTop: 6 }}>{c.l}</div>
                <div style={{ fontSize: 10, color: '#374151', fontFamily: 'monospace' }}>{c.bg}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#1a3a2a', marginBottom: 10 }}>Opacity / Tint Variants</div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {[{ bg: 'rgba(209,244,112,0.1)', l: '10%' }, { bg: 'rgba(209,244,112,0.15)', l: '15%' }, { bg: 'rgba(209,244,112,0.2)', l: '20%' }, { bg: 'rgba(209,244,112,0.3)', l: '30%' }, { bg: 'rgba(26,58,42,0.1)', l: 'Grn 10%' }, { bg: 'rgba(26,58,42,0.2)', l: 'Grn 20%' }].map((t, i) => (
                <div key={i} style={{ textAlign: 'center' }}>
                  <div style={{ width: 56, height: 56, borderRadius: 10, background: t.bg, border: '1px solid rgba(209,244,112,0.4)' }} />
                  <div style={{ fontSize: 10, fontWeight: 500, color: '#1a3a2a', marginTop: 4 }}>{t.l}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* TYPOGRAPHY */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Typography</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 20 }}>
            <div style={{ fontSize: 32, fontWeight: 700, color: '#1a1a1a' }}>H1 — Inter 32/700</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: '#1a1a1a' }}>H2 — Inter 24/600</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: '#1a1a1a' }}>H3 — Inter 18/600</div>
            <div style={{ fontSize: 15, color: '#374151' }}>Body — Inter 15/400</div>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#1a3a2a' }}>Caption — Inter 13/500</div>
          </div>
        </section>

        {/* BUTTONS */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Buttons</h2>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 20, alignItems: 'center' }}>
            <button style={B('#d1f470', '#1a3a2a')}>Primary</button>
            <button style={B('#fff', '#1a3a2a', '1.5px solid #d1f470')}>Secondary</button>
            <button style={{ ...B('#d1f470', '#1a3a2a'), opacity: 0.5, cursor: 'not-allowed' }}>Disabled</button>
            <button style={B('#dc2626', '#fff')}>Delete</button>
            <button style={{ ...B('#d1f470', '#1a3a2a'), display: 'flex', alignItems: 'center', gap: 8 }}><IcPlus /> Add New</button>
            <button style={{ ...B('#d1f470', '#1a3a2a'), opacity: 0.7, display: 'flex', alignItems: 'center', gap: 8, cursor: 'wait' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin 0.8s linear infinite' }}><circle cx="12" cy="12" r="10" stroke="rgba(26,58,42,0.2)" strokeWidth="3" /><path d="M12 2a10 10 0 0 1 10 10" stroke="#1a3a2a" strokeWidth="3" strokeLinecap="round" /></svg>
              Sending...
            </button>
            <button style={{ width: 40, height: 40, borderRadius: 10, background: '#d1f470', border: '1.5px solid #d1f470', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcTrash /></button>
            <button style={{ width: 40, height: 40, borderRadius: 10, background: '#fff', border: '1.5px solid #d1f470', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcEdit /></button>
          </div>
        </section>

        {/* BADGES */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Badges</h2>
          <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
            <span style={{ padding: '4px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600, background: '#d1f470', color: '#1a3a2a', border: '1px solid #1a3a2a' }}>Active</span>
            <span style={{ padding: '4px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600, background: '#fff', color: '#1a3a2a', border: '1px solid #d1f470' }}>Pending</span>
            <span style={{ padding: '4px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600, background: '#fef2f2', color: '#dc2626', border: '1px solid #dc2626' }}>Failed</span>
            <span style={{ padding: '4px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600, background: '#1a3a2a', color: '#d1f470' }}>Pro</span>
          </div>
        </section>

        {/* TABS */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Tabs</h2>
          <div style={{ display: 'inline-flex', gap: 6, padding: 4, background: '#f9fafb', borderRadius: 14, border: '2px solid #d1f470', marginTop: 20 }}>
            {tabs.map((t, i) => (
              <button key={i} onClick={() => sAt(i)} style={{ padding: '9px 18px', borderRadius: 10, fontSize: 13, fontWeight: at === i ? 600 : 500, background: at === i ? '#d1f470' : 'transparent', color: '#1a3a2a', border: at === i ? '1.5px solid #d1f470' : '1.5px solid transparent', cursor: 'pointer' }}>{t}</button>
            ))}
          </div>
        </section>

        {/* FORM */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Form</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 400, marginTop: 20 }}>
            <div><label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Name</label><input placeholder="Enter name" style={INP()} /></div>
            <div><label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Email</label><input type="email" placeholder="Enter email" style={INP()} /></div>
            <button style={{ ...B('#d1f470', '#1a3a2a'), width: '100%', textAlign: 'center' }}>Send</button>
          </div>
        </section>

        {/* CARDS */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Cards</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 20 }}>
            {st.map((s, i) => (
              <div key={i} style={{ background: '#fff', border: '1.5px solid #d1f470', borderRadius: 13, padding: '16px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={IB}><s.X /></div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#1a1a1a', lineHeight: 1 }}>{s.v}</div>
                  <div style={{ fontSize: 11, color: '#1a3a2a', textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 2 }}>{s.l}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* TOGGLES */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Toggles</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 300, marginTop: 20 }}>
            {['WhatsApp', 'Email', 'Auto-Reply'].map((l, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 14, color: '#1a1a1a', fontWeight: 500 }}>{l}</span>
                <button onClick={() => sTg(p => { const n = [...p]; n[i] = !n[i]; return n; })} style={{ width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer', position: 'relative', background: tg[i] ? '#d1f470' : '#e5e7eb' }}>
                  <div style={{ width: 18, height: 18, borderRadius: '50%', background: tg[i] ? '#1a3a2a' : '#fff', position: 'absolute', top: 3, left: tg[i] ? 23 : 3, transition: 'all .2s', boxShadow: '0 1px 3px rgba(0,0,0,.15)' }} />
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* FAQ */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>FAQ</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 20, maxWidth: 500 }}>
            {fq.map((f, i) => (
              <div key={i} style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden' }}>
                <button onClick={() => sAc(ac === i ? null : i)} style={{ width: '100%', padding: '14px 16px', background: ac === i ? 'rgba(209,244,112,.15)' : '#fff', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 14, fontWeight: 600, color: '#1a1a1a', fontFamily: 'inherit' }}>
                  {f.t}<span style={{ fontSize: 18, color: '#1a3a2a', transform: ac === i ? 'rotate(45deg)' : 'none', transition: 'transform .2s' }}>+</span>
                </button>
                {ac === i && <div style={{ padding: '0 16px 14px', fontSize: 13, color: '#374151', lineHeight: 1.6 }}>{f.c}</div>}
              </div>
            ))}
          </div>
        </section>

        {/* TABLE */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Table</h2>
          <div style={{ border: '2px solid #d1f470', borderRadius: 13, overflow: 'hidden', marginTop: 20 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead><tr style={{ background: '#d1f470' }}><th style={TH}>Name</th><th style={TH}>Phone</th><th style={TH}>Status</th><th style={TH}>Action</th></tr></thead>
              <tbody>
                {[['Alice', '+91 98xxx', 'Active'], ['Bob', '+91 97xxx', 'Pending'], ['Carol', '+91 96xxx', 'Active']].map(([n, p, s], i) => (
                  <tr key={i} style={{ borderBottom: i < 2 ? '1px solid #d1f470' : 'none' }}>
                    <td style={TD}>{n}</td><td style={{ ...TD, fontFamily: 'monospace', color: '#1a3a2a' }}>{p}</td>
                    <td style={TD}><span style={{ padding: '3px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600, background: s === 'Active' ? '#d1f470' : '#fff', color: '#1a3a2a', border: s === 'Active' ? '1px solid #1a3a2a' : '1px solid #d1f470' }}>{s}</span></td>
                    <td style={TD}><button style={{ padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500, background: '#fff', color: '#1a3a2a', border: '1px solid #d1f470', cursor: 'pointer' }}>Edit</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* PAGINATION */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Pagination</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 20 }}>
            <button style={{ ...B('#fff', '#1a3a2a', '1.5px solid #d1f470'), padding: '8px 14px', fontSize: 13 }}>Prev</button>
            {[1, 2, 3, 4, 5].map(p => (
              <button key={p} onClick={() => sCp(p)} style={{ width: 36, height: 36, borderRadius: 10, fontSize: 13, fontWeight: cp === p ? 700 : 500, background: cp === p ? '#d1f470' : '#fff', color: '#1a3a2a', border: cp === p ? '1.5px solid #1a3a2a' : '1.5px solid #d1f470', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{p}</button>
            ))}
            <button style={{ ...B('#fff', '#1a3a2a', '1.5px solid #d1f470'), padding: '8px 14px', fontSize: 13 }}>Next</button>
          </div>
        </section>

        {/* PROGRESS */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Progress</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 400, marginTop: 20 }}>
            {[{ l: 'Messages Sent', p: 75 }, { l: 'Storage', p: 42 }, { l: 'Campaign', p: 90 }].map((x, i) => (
              <div key={i}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}><span style={{ fontSize: 13, fontWeight: 500, color: '#1a1a1a' }}>{x.l}</span><span style={{ fontSize: 12, fontWeight: 600, color: '#1a3a2a' }}>{x.p}%</span></div>
                <div style={{ height: 8, borderRadius: 4, background: 'rgba(209,244,112,0.2)', overflow: 'hidden' }}><div style={{ height: '100%', width: x.p + '%', borderRadius: 4, background: '#d1f470' }} /></div>
              </div>
            ))}
          </div>
        </section>

        {/* EMPTY STATE */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Empty State</h2>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, padding: '48px 24px', textAlign: 'center', marginTop: 20 }}>
            <div style={{ marginBottom: 16 }}><IcBox /></div>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#1a1a1a', marginBottom: 6 }}>No messages yet</div>
            <div style={{ fontSize: 13, color: '#374151', maxWidth: 280, margin: '0 auto 20px' }}>Send your first message to get started.</div>
            <button style={B('#d1f470', '#1a3a2a')}>Send First Message</button>
          </div>
        </section>

        {/* TOAST */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Toast</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#fff', borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', border: '1.5px solid #d1f470' }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#d1f470', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: '#1a3a2a' }}><IcCheck /></div>
              <span style={{ fontSize: 14, color: '#1a1a1a', flex: 1 }}>Message sent successfully</span>
              <span style={{ fontSize: 11, color: '#1a3a2a', fontWeight: 600, padding: '2px 8px', background: 'rgba(209,244,112,0.2)', borderRadius: 4 }}>SUCCESS</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#fff', borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', border: '1.5px solid #dc2626' }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#fef2f2', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: '#dc2626' }}><IcX /></div>
              <span style={{ fontSize: 14, color: '#1a1a1a', flex: 1 }}>Failed to send message</span>
              <span style={{ fontSize: 11, color: '#dc2626', fontWeight: 600, padding: '2px 8px', background: '#fef2f2', borderRadius: 4 }}>ERROR</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#fff', borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', border: '1.5px solid #f59e0b' }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#fffbeb', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><IcWarn s={14} /></div>
              <span style={{ fontSize: 14, color: '#1a1a1a', flex: 1 }}>API rate limit approaching</span>
              <span style={{ fontSize: 11, color: '#f59e0b', fontWeight: 600, padding: '2px 8px', background: '#fffbeb', borderRadius: 4 }}>WARNING</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#fff', borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', border: '1.5px solid #1a3a2a' }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'rgba(26,58,42,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: '#1a3a2a' }}><IcInfo /></div>
              <span style={{ fontSize: 14, color: '#1a1a1a', flex: 1 }}>New feature available</span>
              <span style={{ fontSize: 11, color: '#1a3a2a', fontWeight: 600, padding: '2px 8px', background: 'rgba(26,58,42,0.1)', borderRadius: 4 }}>INFO</span>
            </div>
          </div>
        </section>

        {/* CONFIRM DIALOG */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Confirm Dialog</h2>
          <div style={{ maxWidth: 400, background: '#fff', borderRadius: 13, boxShadow: '0 8px 30px rgba(0,0,0,0.12)', overflow: 'hidden', border: '1.5px solid #d1f470', marginTop: 20 }}>
            <div style={{ height: 6, background: '#d1f470' }} />
            <div style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#fef2f2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><IcWarn /></div>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a' }}>Delete this contact?</span>
              </div>
              <p style={{ fontSize: 13, color: '#374151', margin: '0 0 20px', paddingLeft: 42 }}>This action cannot be undone.</p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button style={{ ...B('#fff', '#1a3a2a', '1.5px solid #d1f470'), padding: '7px 16px', fontSize: 13 }}>Cancel</button>
                <button style={{ ...B('#dc2626', '#fff'), padding: '7px 16px', fontSize: 13 }}>Delete</button>
              </div>
            </div>
          </div>
        </section>

        {/* TOOLTIP */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Tooltip</h2>
          <div style={{ display: 'flex', gap: 32, alignItems: 'center', marginTop: 20 }}>
            <div style={{ position: 'relative', display: 'inline-block' }}>
              <button style={B('#d1f470', '#1a3a2a')}>Hover me</button>
              <div style={{ position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: 8, padding: '6px 12px', background: '#1a3a2a', color: '#d1f470', fontSize: 12, fontWeight: 500, borderRadius: 8, whiteSpace: 'nowrap' }}>
                Send a WhatsApp message
                <div style={{ position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)', width: 0, height: 0, borderLeft: '6px solid transparent', borderRight: '6px solid transparent', borderTop: '6px solid #1a3a2a' }} />
              </div>
            </div>
          </div>
        </section>

        {/* SPACING + RADIUS + SKELETON */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Spacing</h2>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginTop: 20 }}>
            {[4, 8, 12, 16, 24, 32, 48].map(s => (<div key={s} style={{ textAlign: 'center' }}><div style={{ width: s, height: s, background: '#d1f470', borderRadius: 3, border: '1px solid #1a3a2a' }} /><div style={{ fontSize: 10, color: '#1a3a2a', marginTop: 4, fontFamily: 'monospace' }}>{s}px</div></div>))}
          </div>
        </section>
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Border Radius</h2>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginTop: 20 }}>
            {[{ r: 4, l: '4px' }, { r: 10, l: '10px' }, { r: 13, l: '13px' }, { r: 20, l: '20px' }, { r: 9999, l: 'Full' }].map((x, i) => (<div key={i} style={{ textAlign: 'center' }}><div style={{ width: 48, height: 48, background: '#d1f470', borderRadius: x.r, border: '1.5px solid #1a3a2a' }} /><div style={{ fontSize: 10, color: '#1a3a2a', marginTop: 4, fontFamily: 'monospace' }}>{x.l}</div></div>))}
          </div>
        </section>
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Skeleton</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 20 }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{ border: '1.5px solid #d1f470', borderRadius: 13, padding: '16px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(209,244,112,0.2)', animation: 'pulse 1.5s ease-in-out infinite' }} />
                <div style={{ flex: 1 }}><div style={{ width: '60%', height: 18, borderRadius: 6, background: 'rgba(209,244,112,0.2)', marginBottom: 6, animation: 'pulse 1.5s ease-in-out infinite' }} /><div style={{ width: '40%', height: 10, borderRadius: 4, background: 'rgba(209,244,112,0.15)', animation: 'pulse 1.5s ease-in-out infinite' }} /></div>
              </div>
            ))}
          </div>
        </section>

        {/* MODAL */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Modal</h2>
          <div style={{ position: 'relative', background: 'rgba(0,0,0,0.3)', borderRadius: 13, padding: 40, marginTop: 20, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 260 }}>
            <div style={{ background: '#fff', borderRadius: 13, boxShadow: '0 20px 60px rgba(0,0,0,0.15)', width: '100%', maxWidth: 420, overflow: 'hidden', border: '1.5px solid #d1f470' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid rgba(209,244,112,0.3)' }}>
                <span style={{ fontSize: 16, fontWeight: 600, color: '#1a1a1a' }}>New Contact</span>
                <button style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(209,244,112,0.15)', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcX /></button>
              </div>
              <div style={{ padding: '20px' }}>
                <div style={{ marginBottom: 14 }}><label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Name</label><input placeholder="Enter name" style={INP()} /></div>
                <div style={{ marginBottom: 14 }}><label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Phone</label><input placeholder="+91 98xxx xxxxx" style={INP()} /></div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '12px 20px', borderTop: '1px solid rgba(209,244,112,0.3)' }}>
                <button style={{ ...B('#fff', '#1a3a2a', '1.5px solid #d1f470'), padding: '8px 16px', fontSize: 13 }}>Cancel</button>
                <button style={{ ...B('#d1f470', '#1a3a2a'), padding: '8px 16px', fontSize: 13 }}>Save Contact</button>
              </div>
            </div>
          </div>
        </section>

        {/* SEARCH / COMMAND PALETTE */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Search / Command Palette</h2>
          <div style={{ maxWidth: 480, marginTop: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: '#fff', border: '2px solid #d1f470', borderRadius: 13, boxShadow: '0 4px 16px rgba(0,0,0,0.06)' }}>
              <IcSearch s={18} />
              <input placeholder="Search contacts, messages..." style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, color: '#111827', fontFamily: 'inherit', background: 'transparent' }} />
              <span style={{ fontSize: 11, color: '#1a3a2a', fontWeight: 600, padding: '3px 8px', background: 'rgba(209,244,112,0.2)', borderRadius: 6, fontFamily: 'monospace' }}>Ctrl+K</span>
            </div>
            <div style={{ marginTop: 8, background: '#fff', border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', boxShadow: '0 4px 16px rgba(0,0,0,0.06)' }}>
              {[{ ic: IcUser, t: 'Alice Johnson', sub: 'Contact' }, { ic: IcChat, t: 'Order #1234 thread', sub: 'Message' }, { ic: IcFile, t: 'Invoice template', sub: 'Template' }].map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderBottom: i < 2 ? '1px solid rgba(209,244,112,0.2)' : 'none', cursor: 'pointer', transition: 'background 0.15s' }}>
                  <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><r.ic s={14} /></div>
                  <div style={{ flex: 1 }}><div style={{ fontSize: 13, fontWeight: 500, color: '#1a1a1a' }}>{r.t}</div></div>
                  <span style={{ fontSize: 10, color: '#1a3a2a', fontWeight: 600, padding: '2px 8px', background: 'rgba(209,244,112,0.15)', borderRadius: 4 }}>{r.sub}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* DROPDOWN / SELECT */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Dropdown / Select</h2>
          <div style={{ display: 'flex', gap: 20, marginTop: 20 }}>
            <div style={{ width: 200 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Channel</label>
              <div style={{ position: 'relative' }}>
                <select style={{ ...INP(), appearance: 'none', paddingRight: 36, cursor: 'pointer' }}>
                  <option>WhatsApp</option><option>SMS</option><option>Email</option><option>Voice</option>
                </select>
                <div style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: '#1a3a2a' }}>
                  <Ic d="M6 9l6 6 6-6" s={14} />
                </div>
              </div>
            </div>
            <div style={{ width: 200 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Status</label>
              <div style={{ position: 'relative' }}>
                <select style={{ ...INP(), appearance: 'none', paddingRight: 36, cursor: 'pointer' }}>
                  <option>Active</option><option>Pending</option><option>Archived</option>
                </select>
                <div style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: '#1a3a2a' }}>
                  <Ic d="M6 9l6 6 6-6" s={14} />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* FORM STATES */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Form States</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, maxWidth: 600, marginTop: 20 }}>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#1a3a2a', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Default</label>
              <input placeholder="Enter value" style={INP()} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#1a3a2a', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Focus</label>
              <input placeholder="Focused" style={{ ...INP(), borderColor: '#1a3a2a', boxShadow: '0 0 0 3px rgba(209,244,112,0.3)' }} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#dc2626', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Error</label>
              <input placeholder="Invalid" style={{ ...INP(), borderColor: '#dc2626' }} />
              <div style={{ fontSize: 11, color: '#dc2626', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}><IcWarn s={12} /> Required field</div>
            </div>
          </div>
        </section>

        {/* SPINNER */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Spinner</h2>
          <div style={{ display: 'flex', gap: 24, alignItems: 'center', marginTop: 20 }}>
            {[20, 28, 40].map((sz, i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <svg width={sz} height={sz} viewBox="0 0 24 24" fill="none" style={{ animation: 'spin 0.8s linear infinite' }}><circle cx="12" cy="12" r="10" stroke="rgba(209,244,112,0.3)" strokeWidth="3" /><path d="M12 2a10 10 0 0 1 10 10" stroke="#1a3a2a" strokeWidth="3" strokeLinecap="round" /></svg>
                <div style={{ fontSize: 10, color: '#1a3a2a', marginTop: 6, fontFamily: 'monospace' }}>{sz}px</div>
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', background: 'rgba(209,244,112,0.1)', borderRadius: 10, border: '1px solid #d1f470' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin 0.8s linear infinite' }}><circle cx="12" cy="12" r="10" stroke="rgba(209,244,112,0.3)" strokeWidth="3" /><path d="M12 2a10 10 0 0 1 10 10" stroke="#1a3a2a" strokeWidth="3" strokeLinecap="round" /></svg>
              <span style={{ fontSize: 13, color: '#1a3a2a', fontWeight: 500 }}>Loading messages...</span>
            </div>
          </div>
        </section>

        {/* NOTIFICATION BADGES */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Notification Badges</h2>
          <div style={{ display: 'flex', gap: 24, alignItems: 'center', marginTop: 20 }}>
            {[{ ic: IcBell, n: 3 }, { ic: IcChat, n: 12 }, { ic: IcMail, n: 99 }].map((b, i) => (
              <div key={i} style={{ position: 'relative', display: 'inline-flex' }}>
                <div style={{ width: 40, height: 40, borderRadius: 10, background: '#fff', border: '1.5px solid #d1f470', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><b.ic /></div>
                <span style={{ position: 'absolute', top: -4, right: -4, minWidth: 18, height: 18, borderRadius: 9, background: '#dc2626', color: '#fff', fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 4px', border: '2px solid #fff' }}>{b.n > 9 ? '9+' : b.n}</span>
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#d1f470', border: '1px solid #1a3a2a' }} />
              <span style={{ fontSize: 12, color: '#1a3a2a', fontWeight: 500 }}>Online</span>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#e5e7eb', marginLeft: 12 }} />
              <span style={{ fontSize: 12, color: '#374151', fontWeight: 500 }}>Offline</span>
            </div>
          </div>
        </section>

        {/* SHADOW */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Shadow</h2>
          <div style={{ display: 'flex', gap: 20, marginTop: 20 }}>
            {[{ s: '0 1px 3px rgba(0,0,0,0.06)', l: 'sm' }, { s: '0 4px 12px rgba(0,0,0,0.08)', l: 'md' }, { s: '0 8px 30px rgba(0,0,0,0.12)', l: 'lg' }, { s: '0 20px 60px rgba(0,0,0,0.15)', l: 'xl' }].map((x, i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <div style={{ width: 80, height: 80, borderRadius: 13, background: '#fff', boxShadow: x.s, border: '1px solid rgba(209,244,112,0.2)' }} />
                <div style={{ fontSize: 10, color: '#1a3a2a', marginTop: 8, fontFamily: 'monospace' }}>{x.l}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ICON SET */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Icon Set</h2>
          <p style={{ fontSize: 13, color: '#374151', marginTop: 12, marginBottom: 16 }}>Feather-style SVG icons. Reference: <a href="https://notionicons.so/" target="_blank" rel="noopener noreferrer" style={{ color: '#1a3a2a', fontWeight: 600, textDecoration: 'underline' }}>notionicons.so</a></p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 12, marginTop: 8 }}>
            {[{ I: IcUser, l: 'User' }, { I: IcChat, l: 'Chat' }, { I: IcFile, l: 'File' }, { I: IcSearch, l: 'Search' }, { I: IcBell, l: 'Bell' }, { I: IcSettings, l: 'Settings' }, { I: IcHome, l: 'Home' }, { I: IcMail, l: 'Mail' }, { I: IcPhone, l: 'Phone' }, { I: IcBarChart, l: 'Chart' }, { I: IcZap, l: 'Zap' }, { I: IcSend, l: 'Send' }, { I: IcTrash, l: 'Trash' }, { I: IcEdit, l: 'Edit' }, { I: IcDownload, l: 'Download' }, { I: IcPlus, l: 'Plus' }, { I: IcCheck, l: 'Check' }, { I: IcX, l: 'Close' }, { I: IcInfo, l: 'Info' }, { I: IcWarn, l: 'Warn' }, { I: IcBox, l: 'Box' }].map((x, i) => (
              <div key={i} style={{ textAlign: 'center', padding: '10px 4px', borderRadius: 10, border: '1px solid rgba(209,244,112,0.3)', background: '#fff' }}>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 6, color: '#1a3a2a' }}><x.I s={20} /></div>
                <div style={{ fontSize: 10, color: '#1a3a2a', fontWeight: 500 }}>{x.l}</div>
              </div>
            ))}
          </div>
        </section>

        {/* HEADER REFERENCE */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Header</h2>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', marginTop: 20 }}>
            <div style={{ background: '#fff', padding: '14px 24px', display: 'flex', alignItems: 'center', gap: 6, borderBottom: '1px solid rgba(209,244,112,0.2)' }}>
              <img src={LOGO} alt="Logo" style={{ width: 48, height: 48, borderRadius: 12, objectFit: 'contain' }} />
              <span style={{ color: '#1a1a1a', fontSize: 14, transition: 'color 0.2s', cursor: 'pointer' }}>&#9660;</span>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: '#374151', fontStyle: 'italic' }}>Arrow color: #1a1a1a (matches CRM home page font)</span>
            </div>
            <div style={{ padding: '12px 24px', background: 'rgba(209,244,112,0.05)', fontSize: 12, color: '#374151' }}>
              Fixed top bar. Logo + dropdown arrow in <span style={{ fontFamily: 'monospace', color: '#1a1a1a', fontWeight: 600 }}>#1a1a1a</span> (CRM home font color). Hover: dark green. Dropdown hover: lime tint background. Nav items: CRM, Studio, Sustainability, Sign in.
            </div>
          </div>
        </section>

        {/* FOOTER REFERENCE */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Footer</h2>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', marginTop: 20 }}>
            <div style={{ background: '#fff', padding: '20px 24px', display: 'flex', alignItems: 'center' }}>
              <a href="#" style={{ fontSize: 18, color: '#1a1a1a', textDecoration: 'none', fontWeight: 500, transition: 'opacity 0.2s' }}>Contact us</a>
            </div>
            <div style={{ padding: '12px 24px', background: 'rgba(209,244,112,0.05)', fontSize: 12, color: '#374151' }}>
              Minimal footer. Only &quot;Contact us&quot; link in <span style={{ fontFamily: 'monospace', color: '#1a1a1a', fontWeight: 600 }}>#1a1a1a</span> (CRM home page font color). Hover: opacity change. Links to wecare.digital/contact.
            </div>
          </div>
        </section>

        {/* SIDEBAR */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Sidebar</h2>
          <div style={{ display: 'flex', gap: 16, marginTop: 20 }}>
            <div style={{ width: 220, background: '#fff', border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', flexShrink: 0 }}>
              <div style={{ padding: '16px 14px', borderBottom: '1px solid rgba(209,244,112,0.3)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <img src={LOGO} alt="Logo" style={{ width: 32, height: 32, borderRadius: 8, objectFit: 'contain' }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: '#1a3a2a' }}>WECARE.DIGITAL</span>
              </div>
              {[{ ic: IcHome, l: 'Dashboard', a: true }, { ic: IcChat, l: 'Messages', a: false, sub: true }, { ic: IcUser, l: 'Contacts', a: false }, { ic: IcBarChart, l: 'Analytics', a: false }, { ic: IcSettings, l: 'Settings', a: false }].map((m, i) => (
                <React.Fragment key={i}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', cursor: 'pointer', background: m.a ? 'rgba(209,244,112,0.15)' : 'transparent', borderLeft: m.a ? '3px solid #d1f470' : '3px solid transparent', transition: 'all 0.15s' }}>
                    <m.ic s={16} /><span style={{ fontSize: 13, fontWeight: m.a ? 600 : 500, color: '#1a3a2a' }}>{m.l}</span>
                    {m.sub && <span style={{ marginLeft: 'auto', fontSize: 10, color: '#9ca3af' }}><Ic d="M6 9l6 6 6-6" s={10} /></span>}
                  </div>
                  {m.sub && (
                    <div style={{ paddingLeft: 28 }}>
                      {['WhatsApp', 'SMS', 'Voice', 'Email', 'RCS'].map((ch, ci) => (
                        <div key={ci} style={{ padding: '7px 14px', fontSize: 12, color: '#1a3a2a', cursor: 'pointer', borderLeft: '3px solid transparent', transition: 'all 0.15s' }}>{ch}</div>
                      ))}
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
            <div style={{ flex: 1, fontSize: 12, color: '#374151', lineHeight: 1.8 }}>
              <div style={{ marginBottom: 8, fontWeight: 600, color: '#1a3a2a' }}>Sidebar Specs:</div>
              <div>Width: 220px (collapsed: 60px icon-only)</div>
              <div>Logo + brand name at top</div>
              <div>Active item: lime left border + lime tint bg</div>
              <div>Hover: <span style={{ fontFamily: 'monospace' }}>rgba(209,244,112,0.1)</span></div>
              <div>Icons: 16px Feather-style SVG</div>
              <div>Font: 13px / 500 weight, 600 when active</div>
            </div>
          </div>
        </section>

        {/* BREADCRUMBS */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Breadcrumbs</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 20, fontSize: 13 }}>
            <a href="#" style={{ color: '#1a3a2a', textDecoration: 'none', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4 }}><IcHome s={14} /> Home</a>
            <Ic d="M9 18l6-6-6-6" s={12} c="#374151" />
            <a href="#" style={{ color: '#1a3a2a', textDecoration: 'none', fontWeight: 500 }}>Contacts</a>
            <Ic d="M9 18l6-6-6-6" s={12} c="#374151" />
            <span style={{ color: '#374151' }}>Alice Johnson</span>
          </div>
          <div style={{ marginTop: 12, fontSize: 12, color: '#374151' }}>Separator: chevron-right icon. Current page: muted color. Links: dark green with hover underline.</div>
        </section>

        {/* LOGIN LAYOUT */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Login</h2>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', marginTop: 20, background: '#f9fafb' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 24px' }}>
              <img src={LOGO} alt="Logo" style={{ width: 56, height: 56, borderRadius: 14, objectFit: 'contain', marginBottom: 16 }} />
              <div style={{ fontSize: 18, fontWeight: 600, color: '#1a1a1a', marginBottom: 4 }}>Sign in to Stack CRM</div>
              <div style={{ fontSize: 13, color: '#374151', marginBottom: 24 }}>Enter your credentials to continue</div>
              <div style={{ width: '100%', maxWidth: 320 }}>
                <div style={{ marginBottom: 14 }}><label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Email</label><input placeholder="you@company.com" style={INP()} /></div>
                <div style={{ marginBottom: 20 }}><label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Password</label><input type="password" placeholder="Enter password" style={INP()} /></div>
                <button style={{ ...B('#d1f470', '#1a3a2a'), width: '100%', textAlign: 'center', padding: '12px 20px', fontSize: 15, fontWeight: 600 }}>Sign In</button>
                <div style={{ textAlign: 'center', marginTop: 14, fontSize: 13, color: '#1a3a2a', cursor: 'pointer' }}>Forgot password?</div>
              </div>
            </div>
            <div style={{ padding: '12px 24px', background: 'rgba(209,244,112,0.05)', fontSize: 12, color: '#374151', borderTop: '1px solid rgba(209,244,112,0.2)' }}>
              Cognito-powered auth. Lime primary button, dark green text. Header + Footer wrap the login form. Rounded inputs with lime borders.
            </div>
          </div>
        </section>

        {/* INBOX / CHAT LAYOUT */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Inbox / Chat</h2>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', marginTop: 20, display: 'flex', minHeight: 500, background: '#fff' }}>
            {/* Chat list */}
            <div style={{ width: 260, borderRight: '1px solid rgba(209,244,112,0.3)', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px', background: '#f9fafb', borderRadius: 10, border: '1px solid rgba(209,244,112,0.3)' }}>
                  <IcSearch s={14} /><span style={{ fontSize: 12, color: '#9ca3af' }}>Search chats...</span>
                </div>
                <div style={{ width: 30, height: 30, borderRadius: 8, background: '#d1f470', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#1a3a2a' }}><IcPlus s={14} /></div>
              </div>
              <div style={{ flex: 1, overflow: 'auto' }}>
                {inboxChats.map((ch, i) => (
                  <div key={i} onClick={() => setInboxSel(i)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', cursor: 'pointer', background: inboxSel === i ? 'rgba(209,244,112,0.12)' : 'transparent', borderLeft: inboxSel === i ? '3px solid #d1f470' : '3px solid transparent', transition: 'all 0.15s' }}>
                    <div style={{ position: 'relative', flexShrink: 0 }}>
                      <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 600, color: '#1a3a2a' }}>{ch.name[0]}</div>
                      {ch.online && <div style={{ position: 'absolute', bottom: -1, right: -1, width: 10, height: 10, borderRadius: '50%', background: '#d1f470', border: '2px solid #fff' }} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 13, fontWeight: ch.unread > 0 ? 600 : 500, color: '#1a1a1a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ch.name}</span>
                        <span style={{ fontSize: 10, color: '#9ca3af', flexShrink: 0 }}>{ch.time}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
                        <span style={{ fontSize: 12, color: '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ch.msg}</span>
                        {ch.unread > 0 && <span style={{ minWidth: 18, height: 18, borderRadius: 9, background: '#d1f470', color: '#1a3a2a', fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 4px', flexShrink: 0 }}>{ch.unread}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            {/* Chat area */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 600, color: '#1a3a2a' }}>{inboxChats[inboxSel]?.name[0]}</div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a' }}>{inboxChats[inboxSel]?.name}</div>
                  <div style={{ fontSize: 11, color: inboxChats[inboxSel]?.online ? '#1a3a2a' : '#9ca3af' }}>{inboxChats[inboxSel]?.online ? 'Online' : 'Offline'}</div>
                </div>
                <div style={{ flex: 1 }} />
                <div style={{ display: 'flex', gap: 6 }}>
                  <div style={{ width: 30, height: 30, borderRadius: 8, background: '#fff', border: '1px solid rgba(209,244,112,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}><IcPhone s={14} /></div>
                  <div style={{ width: 30, height: 30, borderRadius: 8, background: '#fff', border: '1px solid rgba(209,244,112,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}><IcSearch s={14} /></div>
                </div>
              </div>
              <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 12, background: '#fafafa', justifyContent: 'flex-end' }}>
                <div style={{ alignSelf: 'flex-start', maxWidth: '70%' }}>
                  <div style={{ padding: '10px 14px', background: '#fff', borderRadius: '4px 13px 13px 13px', border: '1px solid rgba(209,244,112,0.3)', fontSize: 13, color: '#1a1a1a' }}>Hi, I need help with my recent order. Can you check the status?</div>
                  <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 4 }}>10:30 AM</div>
                </div>
                <div style={{ alignSelf: 'flex-end', maxWidth: '70%' }}>
                  <div style={{ padding: '10px 14px', background: '#d1f470', borderRadius: '13px 4px 13px 13px', fontSize: 13, color: '#1a3a2a' }}>Sure! Let me look that up for you. What is your order number?</div>
                  <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 4, textAlign: 'right' }}>10:31 AM</div>
                </div>
                <div style={{ alignSelf: 'flex-start', maxWidth: '70%' }}>
                  <div style={{ padding: '10px 14px', background: '#fff', borderRadius: '4px 13px 13px 13px', border: '1px solid rgba(209,244,112,0.3)', fontSize: 13, color: '#1a1a1a' }}>Order #WC-2024-1234</div>
                  <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 4 }}>10:32 AM</div>
                </div>
                <div style={{ alignSelf: 'flex-end', maxWidth: '70%' }}>
                  <div style={{ padding: '10px 14px', background: '#d1f470', borderRadius: '13px 4px 13px 13px', fontSize: 13, color: '#1a3a2a' }}>Found it! Your order is out for delivery. Expected by 3 PM today.</div>
                  <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 4, textAlign: 'right' }}>10:33 AM</div>
                </div>
              </div>
              <div style={{ padding: '10px 14px', borderTop: '1px solid rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: '#fff', border: '1px solid rgba(209,244,112,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#1a3a2a' }}><IcPlus s={14} /></div>
                <input placeholder="Type a message..." style={{ flex: 1, border: '1.5px solid rgba(209,244,112,0.4)', borderRadius: 10, padding: '8px 12px', fontSize: 13, outline: 'none', fontFamily: 'inherit', background: '#f9fafb' }} />
                <button style={{ width: 36, height: 36, borderRadius: 10, background: '#d1f470', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcSend s={16} /></button>
              </div>
            </div>
          </div>
        </section>

        {/* DASHBOARD LAYOUT */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Dashboard</h2>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', marginTop: 20, background: '#f9fafb', padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <div><div style={{ fontSize: 18, fontWeight: 600, color: '#1a1a1a' }}>Dashboard</div><div style={{ fontSize: 12, color: '#374151' }}>Welcome back</div></div>
              <button style={{ ...B('#d1f470', '#1a3a2a'), padding: '8px 16px', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}><IcPlus s={12} /> New Campaign</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
              {[{ l: 'Total Contacts', v: '2,847', X: IcUser, d: '+12%' }, { l: 'Messages Sent', v: '14,203', X: IcChat, d: '+8%' }, { l: 'Campaigns', v: '23', X: IcBarChart, d: '+3' }, { l: 'Automation', v: '12', X: IcZap, d: 'Active' }].map((s, i) => (
                <div key={i} style={{ background: '#fff', border: '1px solid rgba(209,244,112,0.3)', borderRadius: 13, padding: '16px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><s.X s={16} /></div>
                    <span style={{ fontSize: 11, color: '#1a3a2a', fontWeight: 600, padding: '2px 8px', background: 'rgba(209,244,112,0.15)', borderRadius: 6 }}>{s.d}</span>
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#1a1a1a', lineHeight: 1 }}>{s.v}</div>
                  <div style={{ fontSize: 11, color: '#374151', marginTop: 4 }}>{s.l}</div>
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
              <div style={{ background: '#fff', border: '1px solid rgba(209,244,112,0.3)', borderRadius: 13, padding: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a', marginBottom: 12 }}>Message Activity</div>
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 100 }}>
                  {[40, 65, 45, 80, 55, 90, 70, 85, 60, 75, 95, 50].map((h, i) => (
                    <div key={i} style={{ flex: 1, height: h + '%', background: i === 11 ? '#1a3a2a' : '#d1f470', borderRadius: '4px 4px 0 0', transition: 'height 0.3s' }} />
                  ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                  {['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'].map((m, i) => (
                    <span key={i} style={{ fontSize: 9, color: '#9ca3af', flex: 1, textAlign: 'center' }}>{m}</span>
                  ))}
                </div>
              </div>
              <div style={{ background: '#fff', border: '1px solid rgba(209,244,112,0.3)', borderRadius: 13, padding: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a', marginBottom: 12 }}>Recent Activity</div>
                {[{ t: 'Campaign sent', d: '2m ago' }, { t: 'New contact added', d: '15m ago' }, { t: 'Template approved', d: '1h ago' }, { t: 'Payment received', d: '3h ago' }].map((a, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: i < 3 ? '1px solid rgba(209,244,112,0.15)' : 'none' }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#d1f470', flexShrink: 0 }} />
                    <span style={{ fontSize: 12, color: '#1a1a1a', flex: 1 }}>{a.t}</span>
                    <span style={{ fontSize: 10, color: '#9ca3af' }}>{a.d}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* CONTACTS LIST LAYOUT */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Contacts List</h2>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', marginTop: 20, background: '#fff' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#f9fafb', borderRadius: 10, border: '1px solid rgba(209,244,112,0.3)' }}>
                <IcSearch s={14} /><span style={{ fontSize: 13, color: '#9ca3af' }}>Search contacts...</span>
              </div>
              <button style={{ ...B('#d1f470', '#1a3a2a'), padding: '8px 14px', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}><IcPlus s={12} /> Add</button>
              <button style={{ ...B('#fff', '#1a3a2a', '1.5px solid #d1f470'), padding: '8px 14px', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}><IcDownload s={12} /> Export</button>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ background: 'rgba(209,244,112,0.08)' }}><th style={{ ...TH, width: 40 }}><input type="checkbox" /></th><th style={TH}>Name</th><th style={TH}>Phone</th><th style={TH}>Channel</th><th style={TH}>Status</th><th style={TH}>Actions</th></tr></thead>
              <tbody>
                {[{ n: 'Alice Johnson', p: '+91 98xxx', ch: 'WhatsApp', s: 'Active' }, { n: 'Bob Smith', p: '+91 97xxx', ch: 'SMS', s: 'Pending' }, { n: 'Carol Davis', p: '+91 96xxx', ch: 'Email', s: 'Active' }].map((c, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(209,244,112,0.15)' }}>
                    <td style={{ ...TD, width: 40 }}><input type="checkbox" /></td>
                    <td style={TD}><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 600, color: '#1a3a2a' }}>{c.n[0]}</div>{c.n}</div></td>
                    <td style={{ ...TD, fontFamily: 'monospace', color: '#1a3a2a' }}>{c.p}</td>
                    <td style={TD}>{c.ch}</td>
                    <td style={TD}><span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, background: c.s === 'Active' ? '#d1f470' : '#fff', color: '#1a3a2a', border: '1px solid #d1f470' }}>{c.s}</span></td>
                    <td style={TD}><div style={{ display: 'flex', gap: 4 }}><button style={{ width: 28, height: 28, borderRadius: 6, background: '#fff', border: '1px solid rgba(209,244,112,0.3)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcEdit s={12} /></button><button style={{ width: 28, height: 28, borderRadius: 6, background: '#fff', border: '1px solid rgba(209,244,112,0.3)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcChat s={12} /></button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* SETTINGS LAYOUT */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Settings</h2>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', marginTop: 20, background: '#fff' }}>
            <div style={{ display: 'flex' }}>
              <div style={{ width: 180, borderRight: '1px solid rgba(209,244,112,0.2)', padding: '16px 0' }}>
                {['General', 'Channels', 'API Keys', 'Team', 'Billing'].map((t, i) => (
                  <div key={i} style={{ padding: '8px 16px', fontSize: 13, fontWeight: i === 0 ? 600 : 500, color: '#1a3a2a', cursor: 'pointer', background: i === 0 ? 'rgba(209,244,112,0.12)' : 'transparent', borderLeft: i === 0 ? '3px solid #d1f470' : '3px solid transparent' }}>{t}</div>
                ))}
              </div>
              <div style={{ flex: 1, padding: 20 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#1a1a1a', marginBottom: 16 }}>General Settings</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 400 }}>
                  <div><label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Business Name</label><input defaultValue="WECARE.DIGITAL" style={INP()} /></div>
                  <div><label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#1a3a2a', marginBottom: 6 }}>Timezone</label>
                    <div style={{ position: 'relative' }}><select style={{ ...INP(), appearance: 'none', paddingRight: 36, cursor: 'pointer' }}><option>Asia/Kolkata (IST)</option></select><div style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: '#1a3a2a' }}><Ic d="M6 9l6 6 6-6" s={14} /></div></div>
                  </div>
                  <button style={{ ...B('#d1f470', '#1a3a2a'), width: 'fit-content', padding: '8px 20px', fontSize: 13 }}>Save Changes</button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* INNER PAGE TABS */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Inner Page Tabs</h2>
          <p style={{ fontSize: 13, color: '#374151', marginTop: 12, marginBottom: 16 }}>How tabs appear inside inner pages (contacts detail, settings, etc.)</p>
          <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, overflow: 'hidden', background: '#fff' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(209,244,112,0.2)' }}>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#1a1a1a', marginBottom: 12 }}>Contact Detail</div>
              <div style={{ display: 'flex', gap: 0, borderBottom: '2px solid rgba(209,244,112,0.2)' }}>
                {['Overview', 'Messages', 'Orders', 'Notes', 'Activity'].map((t, i) => (
                  <button key={i} onClick={() => setPgTab(i)} style={{ padding: '10px 18px', fontSize: 13, fontWeight: pgTab === i ? 600 : 500, color: pgTab === i ? '#1a3a2a' : '#6b7280', background: 'transparent', border: 'none', borderBottom: pgTab === i ? '2px solid #d1f470' : '2px solid transparent', cursor: 'pointer', marginBottom: -2, transition: 'all 0.15s', fontFamily: 'inherit' }}>{t}</button>
                ))}
              </div>
            </div>
            <div style={{ padding: 16 }}>
              {pgTab === 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  {[{ l: 'Phone', v: '+91 98xxx xxxxx' }, { l: 'Email', v: 'alice@example.com' }, { l: 'Channel', v: 'WhatsApp' }, { l: 'Status', v: 'Active' }].map((f, i) => (
                    <div key={i} style={{ padding: '10px 14px', background: '#f9fafb', borderRadius: 10, border: '1px solid rgba(209,244,112,0.2)' }}>
                      <div style={{ fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>{f.l}</div>
                      <div style={{ fontSize: 14, fontWeight: 500, color: '#1a1a1a' }}>{f.v}</div>
                    </div>
                  ))}
                </div>
              )}
              {pgTab === 1 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {['Thanks for the update!', 'When is the delivery?', 'Order confirmed'].map((m, i) => (
                    <div key={i} style={{ padding: '10px 14px', background: i % 2 === 0 ? '#fff' : 'rgba(209,244,112,0.08)', borderRadius: 10, border: '1px solid rgba(209,244,112,0.2)', fontSize: 13, color: '#1a1a1a' }}>{m}</div>
                  ))}
                </div>
              )}
              {pgTab === 2 && (
                <div style={{ textAlign: 'center', padding: 24 }}>
                  <IcBox s={36} /><div style={{ fontSize: 14, fontWeight: 500, color: '#374151', marginTop: 8 }}>No orders yet</div>
                </div>
              )}
              {pgTab === 3 && (
                <div style={{ padding: '10px 14px', background: '#fffbeb', borderRadius: 10, border: '1px solid #f59e0b', fontSize: 13, color: '#374151' }}>
                  <span style={{ fontWeight: 600 }}>Note:</span> VIP customer. Priority support enabled.
                </div>
              )}
              {pgTab === 4 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {['Message sent', 'Contact updated', 'Tag added: VIP'].map((a, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#374151' }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#d1f470' }} />{a}<span style={{ marginLeft: 'auto', fontSize: 10, color: '#9ca3af' }}>{i + 1}h ago</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div style={{ padding: '12px 16px', background: 'rgba(209,244,112,0.05)', fontSize: 12, color: '#374151', borderTop: '1px solid rgba(209,244,112,0.2)' }}>
              Underline-style tabs. Active: lime underline + dark green text + 600 weight. Inactive: gray text + 500 weight. Content area changes based on selected tab.
            </div>
          </div>
        </section>

        {/* IMPLEMENTATION NOTES */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Implementation Notes</h2>
          <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, padding: 20, background: '#fff' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcHome s={14} /></div>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a' }}>Inner Pages (Protected)</span>
              </div>
              <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.8 }}>
                <div>All inner pages use the <span style={{ fontFamily: 'monospace', fontSize: 12, padding: '1px 6px', background: 'rgba(209,244,112,0.15)', borderRadius: 4, color: '#1a3a2a' }}>Layout</span> component with sidebar + header.</div>
                <div>Sidebar: 220px wide, collapsible. Active nav item has lime left border + tint background.</div>
                <div>Content area: white background, 13px border-radius on cards, lime borders throughout.</div>
                <div>Tables: lime header row, hover states with <span style={{ fontFamily: 'monospace', fontSize: 12, padding: '1px 6px', background: 'rgba(209,244,112,0.15)', borderRadius: 4, color: '#1a3a2a' }}>rgba(209,244,112,0.08)</span>.</div>
                <div>Inner page tabs: underline style (not pill style). Active = lime underline.</div>
                <div>All buttons follow the primary (lime bg) / secondary (white bg, lime border) pattern.</div>
              </div>
            </div>
            <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, padding: 20, background: '#fff' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcUser s={14} /></div>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a' }}>Login / Auth Pages</span>
              </div>
              <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.8 }}>
                <div>Login page is wrapped by Header + Footer (via <span style={{ fontFamily: 'monospace', fontSize: 12, padding: '1px 6px', background: 'rgba(209,244,112,0.15)', borderRadius: 4, color: '#1a3a2a' }}>_app.tsx AuthGate</span>).</div>
                <div>Cognito Authenticator UI themed with lime primary buttons and dark green text.</div>
                <div>Input fields: 13px border-radius, lime borders, dark green focus ring.</div>
                <div>Centered card layout with logo at top. Clean, minimal design.</div>
              </div>
            </div>
            <div style={{ border: '1.5px solid #d1f470', borderRadius: 13, padding: 20, background: '#fff' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(209,244,112,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a3a2a' }}><IcZap s={14} /></div>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a' }}>Design Tokens</span>
              </div>
              <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.8 }}>
                <div>Primary: <span style={{ fontFamily: 'monospace', fontSize: 12, padding: '1px 6px', background: '#d1f470', borderRadius: 4, color: '#1a3a2a' }}>#d1f470</span> (Lime)</div>
                <div>Dark: <span style={{ fontFamily: 'monospace', fontSize: 12, padding: '1px 6px', background: '#1a3a2a', borderRadius: 4, color: '#d1f470' }}>#1a3a2a</span> (Dark Green)</div>
                <div>Border radius: 13px (cards), 10px (buttons/inputs), 20px (badges)</div>
                <div>Font: Inter, system-ui. Weights: 400 body, 500 labels, 600 headings, 700 titles</div>
                <div>Icons: Feather-style SVG, 14-18px. Source: <a href="https://notionicons.so/" target="_blank" rel="noopener noreferrer" style={{ color: '#1a3a2a', fontWeight: 600 }}>notionicons.so</a></div>
                <div>Shadows: subtle (0.06-0.15 opacity). No harsh drop shadows.</div>
              </div>
            </div>
          </div>
        </section>

        {/* KEYBOARD SHORTCUTS */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Keyboard Shortcuts</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginTop: 20, maxWidth: 500 }}>
            {[{ k: 'Ctrl+K', a: 'Search / Command' }, { k: 'Ctrl+N', a: 'New Contact' }, { k: 'Ctrl+Enter', a: 'Send Message' }, { k: 'Esc', a: 'Close Modal' }, { k: 'Ctrl+/', a: 'Toggle Sidebar' }, { k: 'Ctrl+Shift+M', a: 'New Message' }].map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(209,244,112,0.2)', background: '#fff' }}>
                <span style={{ fontSize: 12, color: '#374151' }}>{s.a}</span>
                <span style={{ fontSize: 11, fontFamily: 'monospace', fontWeight: 600, color: '#1a3a2a', padding: '2px 8px', background: 'rgba(209,244,112,0.15)', borderRadius: 4 }}>{s.k}</span>
              </div>
            ))}
          </div>
        </section>

        {/* MOBILE / RESPONSIVE */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={SL}>Mobile / Responsive</h2>
          <div style={{ display: 'flex', gap: 16, marginTop: 20 }}>
            <div style={{ width: 200, border: '1.5px solid #d1f470', borderRadius: 20, overflow: 'hidden', background: '#fff', boxShadow: '0 4px 16px rgba(0,0,0,0.08)' }}>
              <div style={{ padding: '8px 12px', background: '#fff', borderBottom: '1px solid rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <img src={LOGO} alt="Logo" style={{ width: 20, height: 20, borderRadius: 5, objectFit: 'contain' }} />
                <span style={{ fontSize: 10, fontWeight: 600, color: '#1a3a2a' }}>Stack CRM</span>
                <div style={{ flex: 1 }} />
                <IcBell s={12} />
              </div>
              <div style={{ padding: 8 }}>
                {['Alice', 'Bob', 'Carol'].map((n, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 8px', borderRadius: 8, background: i === 0 ? 'rgba(209,244,112,0.12)' : 'transparent', marginBottom: 2 }}>
                    <div style={{ width: 22, height: 22, borderRadius: 6, background: 'rgba(209,244,112,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 600, color: '#1a3a2a' }}>{n[0]}</div>
                    <div style={{ flex: 1 }}><div style={{ fontSize: 10, fontWeight: 500, color: '#1a1a1a' }}>{n}</div><div style={{ fontSize: 8, color: '#9ca3af' }}>Last message...</div></div>
                  </div>
                ))}
              </div>
              <div style={{ padding: '6px 8px', borderTop: '1px solid rgba(209,244,112,0.2)', display: 'flex', justifyContent: 'space-around' }}>
                {[IcHome, IcChat, IcUser, IcSettings].map((I, i) => (
                  <div key={i} style={{ padding: 4, color: i === 1 ? '#1a3a2a' : '#9ca3af' }}><I s={14} /></div>
                ))}
              </div>
            </div>
            <div style={{ flex: 1, fontSize: 12, color: '#374151', lineHeight: 1.8 }}>
              <div style={{ fontWeight: 600, color: '#1a3a2a', marginBottom: 8 }}>Responsive Breakpoints:</div>
              <div><span style={{ fontFamily: 'monospace', color: '#1a3a2a' }}>{'<'}768px</span> — Mobile: bottom tab nav, stacked layout, full-width cards</div>
              <div><span style={{ fontFamily: 'monospace', color: '#1a3a2a' }}>768-1024px</span> — Tablet: collapsed sidebar (icons only), 2-col grid</div>
              <div><span style={{ fontFamily: 'monospace', color: '#1a3a2a' }}>{'>'}1024px</span> — Desktop: full sidebar, 3-4 col grids</div>
              <div style={{ marginTop: 12, fontWeight: 600, color: '#1a3a2a' }}>Mobile-specific:</div>
              <div>Bottom navigation bar replaces sidebar</div>
              <div>Chat list and chat view are separate screens</div>
              <div>Touch-friendly: min 44px tap targets</div>
              <div>Safe area insets for notch devices</div>
            </div>
          </div>
        </section>

      </div>

      <style jsx>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
      `}</style>
    </>
  );
};

export default ContactTestPage;
