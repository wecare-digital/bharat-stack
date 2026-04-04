/**
 * WhatsApp Auto-Response Manager
 * Manage welcome messages, keyword triggers, and menu configurations.
 * Responses are stored in SystemConfigTable and served by the inbound handler.
 * NO AI — only configured responses are sent.
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import { useToastContext } from '../../contexts/ToastContext';
import * as api from '../../api/client';

interface PageProps { signOut?: () => void; user?: any; }

// ── Types ──
interface KeywordRule {
  id: string;
  keywords: string[];
  response: string;
  responseType: 'text' | 'flow' | 'list' | 'buttons';
  flowId?: string;
  flowCta?: string;
  enabled: boolean;
}

interface MenuSection {
  title: string;
  rows: { id: string; title: string; description: string }[];
}

interface MenuConfig {
  header: string;
  body: string;
  footer: string;
  buttonText: string;
  sections: MenuSection[];
}

// ── Default configs ──
const DEFAULT_WELCOME = '👋 Welcome to WECARE.DIGITAL! How can we help you today?';

const DEFAULT_MENU: MenuConfig = {
  header: 'WECARE.DIGITAL',
  body: 'Pick what you need 👇',
  footer: 'wecare.digital',
  buttonText: 'Menu',
  sections: [
    {
      title: 'Bharat Stack',
      rows: [
        { id: 'bs_aadhaar', title: 'Aadhaar Services', description: 'Verify, link, update Aadhaar' },
        { id: 'bs_upi', title: 'UPI Payments', description: 'Send, receive, check balance' },
        { id: 'bs_digilocker', title: 'DigiLocker', description: 'Access digital documents' },
        { id: 'bs_esign', title: 'eSign', description: 'Digital signature services' },
      ],
    },
    {
      title: 'Self Service',
      rows: [
        { id: 'ss_subscribe', title: 'Subscribe', description: 'Register for updates & orders' },
        { id: 'ss_orders', title: 'My Orders', description: 'Track and manage orders' },
        { id: 'ss_payments', title: 'Payments', description: 'Pay dues, view invoices' },
        { id: 'ss_support', title: 'Submit Request', description: 'Raise a service request' },
      ],
    },
  ],
};

const DEFAULT_KEYWORDS: KeywordRule[] = [
  { id: 'kw_subscribe', keywords: ['subscribe', 'signup', 'sign up', 'register', 'join'], response: '📋 Subscribe to WECARE.DIGITAL — fill in your details to get started.', responseType: 'flow', flowId: '', flowCta: 'Subscribe Now', enabled: false },
  { id: 'kw_pay', keywords: ['pay', 'payment', 'invoice', 'bill', 'due'], response: 'Checking your pending payments...', responseType: 'text', enabled: true },
  { id: 'kw_order', keywords: ['order', 'track', 'delivery', 'shipping'], response: 'Let me check your order status. Please share your order number.', responseType: 'text', enabled: true },
  { id: 'kw_help', keywords: ['help', 'support', 'issue', 'problem', 'complaint'], response: 'We\'re here to help! Please describe your issue and we\'ll get back to you.', responseType: 'text', enabled: true },
  { id: 'kw_hours', keywords: ['hours', 'timing', 'open', 'available', 'when'], response: '🕐 Business hours: Mon–Fri, 9 AM – 6 PM IST (excluding public holidays).', responseType: 'text', enabled: true },
];

const CodeRepo: React.FC<PageProps> = ({ signOut, user }) => {
  const toast = useToastContext();
  const [activeTab, setActiveTab] = useState<'welcome' | 'keywords' | 'menu'>('welcome');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Welcome message state
  const [welcomeMsg, setWelcomeMsg] = useState(DEFAULT_WELCOME);
  const [welcomeEnabled, setWelcomeEnabled] = useState(true);

  // Keyword rules state
  const [keywords, setKeywords] = useState<KeywordRule[]>(DEFAULT_KEYWORDS);
  const [editingKw, setEditingKw] = useState<KeywordRule | null>(null);

  // Menu config state
  const [menu, setMenu] = useState<MenuConfig>(DEFAULT_MENU);

  // AI auto-response toggle
  const [aiEnabled, setAiEnabled] = useState(false);

  // Load config from API
  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.getSystemConfig('wa_auto_response');
      if (resp) {
        if (resp.welcomeMessage) setWelcomeMsg(resp.welcomeMessage);
        if (resp.welcomeEnabled !== undefined) setWelcomeEnabled(resp.welcomeEnabled);
        if (resp.keywords) setKeywords(resp.keywords);
        if (resp.menu) setMenu(resp.menu);
        if (resp.aiEnabled !== undefined) setAiEnabled(resp.aiEnabled);
      }
      // Also load AI config separately
      const aiResp = await api.getSystemConfig('ai_config');
      if (aiResp && aiResp.enabled !== undefined) {
        setAiEnabled(aiResp.enabled);
      }
    } catch {
      // Use defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  // Save config
  const saveConfig = async () => {
    setSaving(true);
    try {
      await api.updateSystemConfig('wa_auto_response', {
        welcomeMessage: welcomeMsg,
        welcomeEnabled,
        keywords,
        menu,
        aiEnabled,
      });
      // Also update AI config separately so the inbound handler picks it up
      await api.updateSystemConfig('ai_config', { enabled: aiEnabled });
      toast.success('Configuration saved');
    } catch {
      toast.error('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  // Keyword handlers
  const toggleKw = (id: string) => {
    setKeywords(prev => prev.map(k => k.id === id ? { ...k, enabled: !k.enabled } : k));
  };

  const deleteKw = (id: string) => {
    setKeywords(prev => prev.filter(k => k.id !== id));
  };

  const addKw = () => {
    const newKw: KeywordRule = {
      id: `kw_${Date.now()}`,
      keywords: [''],
      response: '',
      responseType: 'text',
      enabled: true,
    };
    setEditingKw(newKw);
  };

  const saveKw = (kw: KeywordRule) => {
    setKeywords(prev => {
      const exists = prev.find(k => k.id === kw.id);
      if (exists) return prev.map(k => k.id === kw.id ? kw : k);
      return [...prev, kw];
    });
    setEditingKw(null);
  };

  // Menu handlers
  const addMenuRow = (sectionIdx: number) => {
    setMenu(prev => {
      const sections = [...prev.sections];
      sections[sectionIdx] = {
        ...sections[sectionIdx],
        rows: [...sections[sectionIdx].rows, { id: `row_${Date.now()}`, title: '', description: '' }],
      };
      return { ...prev, sections };
    });
  };

  const removeMenuRow = (sectionIdx: number, rowIdx: number) => {
    setMenu(prev => {
      const sections = [...prev.sections];
      sections[sectionIdx] = {
        ...sections[sectionIdx],
        rows: sections[sectionIdx].rows.filter((_, i) => i !== rowIdx),
      };
      return { ...prev, sections };
    });
  };

  const addSection = () => {
    setMenu(prev => ({
      ...prev,
      sections: [...prev.sections, { title: 'New Section', rows: [] }],
    }));
  };

  const S = {
    tab: (active: boolean): React.CSSProperties => ({
      padding: '8px 16px', border: 'none', borderBottom: active ? '2px solid #1a3a2a' : '2px solid transparent',
      background: 'none', cursor: 'pointer', fontSize: 13, fontWeight: active ? 600 : 400,
      color: active ? '#1a3a2a' : '#6b7280',
    }),
    card: { border: '1px solid #d1f470', borderRadius: 8, padding: 16, marginBottom: 12, background: '#fff' } as React.CSSProperties,
    input: { width: '100%', padding: '8px 10px', border: '1px solid #d1f470', borderRadius: 6, fontSize: 13 } as React.CSSProperties,
    textarea: { width: '100%', padding: '8px 10px', border: '1px solid #d1f470', borderRadius: 6, fontSize: 13, minHeight: 80, resize: 'vertical' as const, fontFamily: 'inherit' },
    btn: { padding: '6px 14px', border: '1.5px solid #d1f470', borderRadius: 6, background: '#fff', cursor: 'pointer', fontSize: 12, fontWeight: 600, color: '#1a3a2a' } as React.CSSProperties,
    btnPrimary: { padding: '8px 20px', border: 'none', borderRadius: 6, background: '#d1f470', cursor: 'pointer', fontSize: 13, fontWeight: 600, color: '#1a3a2a' } as React.CSSProperties,
    toggle: (on: boolean): React.CSSProperties => ({
      width: 36, height: 20, borderRadius: 10, border: 'none', cursor: 'pointer',
      background: on ? '#1a3a2a' : '#d1d5db', position: 'relative', transition: 'all 0.2s',
    }),
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="WhatsApp Auto-Response" description="Manage welcome messages and keyword responses" noindex={true} />
      <div className="inner-page" style={{ padding: '20px 24px', maxWidth: 900 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, color: '#1a3a2a' }}>WhatsApp Auto-Response</h2>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#6b7280' }}>
              Manage welcome messages, keyword triggers, and menu options
            </p>
          </div>
          <button style={S.btnPrimary} onClick={saveConfig} disabled={saving}>
            {saving ? 'Saving...' : 'Save All'}
          </button>
        </div>

        {/* Tabs */}
        <div style={{ borderBottom: '1px solid #e5e7eb', marginBottom: 16, display: 'flex', gap: 4 }}>
          <button style={S.tab(activeTab === 'welcome')} onClick={() => setActiveTab('welcome')}>Welcome Message</button>
          <button style={S.tab(activeTab === 'keywords')} onClick={() => setActiveTab('keywords')}>Keyword Responses</button>
          <button style={S.tab(activeTab === 'menu')} onClick={() => setActiveTab('menu')}>Menu Config</button>
        </div>

        {/* ── Welcome Message Tab ── */}
        {activeTab === 'welcome' && (
          <div>
            {/* AI Auto-Response Control */}
            <div style={{ ...S.card, borderLeft: '3px solid #1a3a2a' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div>
                  <label style={{ fontSize: 14, fontWeight: 600, color: '#1a3a2a' }}>AI Response Smoothing</label>
                  <p style={{ margin: '2px 0 0', fontSize: 11, color: '#6b7280' }}>
                    When ON, AI polishes your configured responses — better grammar, tone, and context.
                    It does NOT generate free-form answers. Only your welcome message, keyword responses, and menu options are sent.
                  </p>
                </div>
                <button
                  style={S.toggle(aiEnabled)}
                  onClick={() => setAiEnabled(!aiEnabled)}
                  aria-label="Toggle AI smoothing"
                >
                  <span style={{
                    position: 'absolute', top: 2, left: aiEnabled ? 18 : 2,
                    width: 16, height: 16, borderRadius: '50%', background: '#fff', transition: 'left 0.2s',
                  }} />
                </button>
              </div>
              <p style={{ margin: 0, fontSize: 11, color: aiEnabled ? '#1a3a2a' : '#6b7280', fontWeight: 600 }}>
                {aiEnabled
                  ? '✅ AI smoothing ON — Responses are polished before sending. Content stays within your configured messages.'
                  : '📝 AI smoothing OFF — Responses sent exactly as configured, word for word.'}
              </p>
              <div style={{ marginTop: 8, padding: '6px 10px', background: '#f9fafb', borderRadius: 6, fontSize: 11, color: '#6b7280' }}>
                <span style={{ fontWeight: 600 }}>Meta Policy (Jan 2026):</span> General-purpose AI chatbots are prohibited.
                Customer support bots, FAQ handling, order tracking, and transactional automation are allowed.
                AI here only smooths your pre-configured responses — it never acts as a standalone assistant.
              </div>
            </div>

            {/* Welcome Message */}
            <div style={S.card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <label style={{ fontSize: 14, fontWeight: 600, color: '#1a3a2a' }}>Welcome Message</label>
                <button
                  style={S.toggle(welcomeEnabled)}
                  onClick={() => setWelcomeEnabled(!welcomeEnabled)}
                  aria-label="Toggle welcome message"
                >
                  <span style={{
                    position: 'absolute', top: 2, left: welcomeEnabled ? 18 : 2,
                    width: 16, height: 16, borderRadius: '50%', background: '#fff', transition: 'left 0.2s',
                  }} />
                </button>
              </div>
              <p style={{ fontSize: 12, color: '#6b7280', margin: '0 0 8px' }}>
                Sent when a user messages &quot;hi&quot;, &quot;hello&quot;, &quot;hey&quot;, &quot;menu&quot;, or &quot;start&quot;.
              </p>
              <textarea
                style={S.textarea}
                value={welcomeMsg}
                onChange={e => setWelcomeMsg(e.target.value)}
                placeholder="Enter welcome message..."
              />
            </div>
          </div>
        )}

        {/* ── Keyword Responses Tab ── */}
        {activeTab === 'keywords' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <p style={{ fontSize: 12, color: '#6b7280', margin: 0 }}>
                When a user sends a matching keyword, the configured response is sent. No AI involved.
              </p>
              <button style={S.btn} onClick={addKw}>+ Add Rule</button>
            </div>

            {keywords.map(kw => (
              <div key={kw.id} style={{ ...S.card, opacity: kw.enabled ? 1 : 0.6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
                      {kw.keywords.map((k, i) => (
                        <span key={i} style={{ padding: '2px 8px', background: '#d1f470', borderRadius: 4, fontSize: 11, fontWeight: 500 }}>{k}</span>
                      ))}
                    </div>
                    <p style={{ margin: 0, fontSize: 13, color: '#374151' }}>{kw.response}</p>
                    {kw.responseType === 'flow' && kw.flowId && (
                      <p style={{ margin: '4px 0 0', fontSize: 11, color: '#6b7280' }}>Flow: {kw.flowId}</p>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <button style={S.toggle(kw.enabled)} onClick={() => toggleKw(kw.id)} aria-label="Toggle rule">
                      <span style={{ position: 'absolute', top: 2, left: kw.enabled ? 18 : 2, width: 16, height: 16, borderRadius: '50%', background: '#fff', transition: 'left 0.2s' }} />
                    </button>
                    <button style={{ ...S.btn, fontSize: 11, padding: '4px 8px' }} onClick={() => setEditingKw(kw)}>Edit</button>
                    <button style={{ ...S.btn, fontSize: 11, padding: '4px 8px', color: '#dc2626', borderColor: '#fecaca' }} onClick={() => deleteKw(kw.id)}>Del</button>
                  </div>
                </div>
              </div>
            ))}

            {/* Edit modal */}
            {editingKw && (
              <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                <div style={{ background: '#fff', borderRadius: 12, padding: 20, width: 480, maxHeight: '80vh', overflow: 'auto' }}>
                  <h3 style={{ margin: '0 0 12px', fontSize: 16, color: '#1a3a2a' }}>Edit Keyword Rule</h3>
                  <div style={{ marginBottom: 10 }}>
                    <label style={{ fontSize: 12, fontWeight: 600 }}>Keywords (comma-separated)</label>
                    <input
                      style={S.input}
                      value={editingKw.keywords.join(', ')}
                      onChange={e => setEditingKw({ ...editingKw, keywords: e.target.value.split(',').map(s => s.trim().toLowerCase()).filter(Boolean) })}
                    />
                  </div>
                  <div style={{ marginBottom: 10 }}>
                    <label style={{ fontSize: 12, fontWeight: 600 }}>Response</label>
                    <textarea
                      style={S.textarea}
                      value={editingKw.response}
                      onChange={e => setEditingKw({ ...editingKw, response: e.target.value })}
                    />
                  </div>
                  <div style={{ marginBottom: 10 }}>
                    <label style={{ fontSize: 12, fontWeight: 600 }}>Type</label>
                    <select
                      style={S.input}
                      value={editingKw.responseType}
                      onChange={e => setEditingKw({ ...editingKw, responseType: e.target.value as any })}
                    >
                      <option value="text">Text</option>
                      <option value="flow">Flow</option>
                    </select>
                  </div>
                  {editingKw.responseType === 'flow' && (
                    <>
                      <div style={{ marginBottom: 10 }}>
                        <label style={{ fontSize: 12, fontWeight: 600 }}>Flow ID</label>
                        <input style={S.input} value={editingKw.flowId || ''} onChange={e => setEditingKw({ ...editingKw, flowId: e.target.value })} />
                      </div>
                      <div style={{ marginBottom: 10 }}>
                        <label style={{ fontSize: 12, fontWeight: 600 }}>Flow CTA Button Text</label>
                        <input style={S.input} value={editingKw.flowCta || ''} onChange={e => setEditingKw({ ...editingKw, flowCta: e.target.value })} />
                      </div>
                    </>
                  )}
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                    <button style={S.btn} onClick={() => setEditingKw(null)}>Cancel</button>
                    <button style={S.btnPrimary} onClick={() => saveKw(editingKw)}>Save</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Menu Config Tab ── */}
        {activeTab === 'menu' && (
          <div>
            <div style={S.card}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600 }}>Header</label>
                  <input style={S.input} value={menu.header} onChange={e => setMenu({ ...menu, header: e.target.value })} />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600 }}>Button Text</label>
                  <input style={S.input} value={menu.buttonText} onChange={e => setMenu({ ...menu, buttonText: e.target.value })} />
                </div>
              </div>
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 12, fontWeight: 600 }}>Body</label>
                <input style={S.input} value={menu.body} onChange={e => setMenu({ ...menu, body: e.target.value })} />
              </div>
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 12, fontWeight: 600 }}>Footer</label>
                <input style={S.input} value={menu.footer} onChange={e => setMenu({ ...menu, footer: e.target.value })} />
              </div>
            </div>

            {/* Sections */}
            {menu.sections.map((section, si) => (
              <div key={si} style={{ ...S.card, borderLeft: '3px solid #d1f470' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <input
                    style={{ ...S.input, fontWeight: 600, fontSize: 14, border: 'none', padding: '4px 0' }}
                    value={section.title}
                    onChange={e => {
                      const sections = [...menu.sections];
                      sections[si] = { ...sections[si], title: e.target.value };
                      setMenu({ ...menu, sections });
                    }}
                    placeholder="Section title"
                  />
                  <button style={{ ...S.btn, fontSize: 11 }} onClick={() => addMenuRow(si)}>+ Row</button>
                </div>

                {section.rows.map((row, ri) => (
                  <div key={ri} style={{ display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: 6, marginBottom: 6 }}>
                    <input
                      style={{ ...S.input, fontSize: 12 }}
                      value={row.title}
                      onChange={e => {
                        const sections = [...menu.sections];
                        const rows = [...sections[si].rows];
                        rows[ri] = { ...rows[ri], title: e.target.value };
                        sections[si] = { ...sections[si], rows };
                        setMenu({ ...menu, sections });
                      }}
                      placeholder="Title"
                    />
                    <input
                      style={{ ...S.input, fontSize: 12 }}
                      value={row.description}
                      onChange={e => {
                        const sections = [...menu.sections];
                        const rows = [...sections[si].rows];
                        rows[ri] = { ...rows[ri], description: e.target.value };
                        sections[si] = { ...sections[si], rows };
                        setMenu({ ...menu, sections });
                      }}
                      placeholder="Description"
                    />
                    <button
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626', fontSize: 14 }}
                      onClick={() => removeMenuRow(si, ri)}
                      aria-label="Remove row"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            ))}

            <button style={S.btn} onClick={addSection}>+ Add Section</button>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default CodeRepo;
