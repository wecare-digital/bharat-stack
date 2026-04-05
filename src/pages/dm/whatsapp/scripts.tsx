/**
 * WhatsApp Scripts — Content library for all automated messages.
 * Every text, menu, flow message, CTA, and response sent by the bot is listed here
 * for content review, improvement, and consistency management.
 *
 * Sources: SystemConfigTable configs, hardcoded defaults in Lambda, flow trigger messages.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';

interface Props { signOut?: () => void; user?: any; embedded?: boolean; }

interface ScriptItem {
  id: string;
  category: string;
  trigger: string;
  messageType: string;
  content: string;
  phone: string;
  editable: boolean;
  configKey?: string;
}

const CATEGORIES = ['All', 'Welcome', 'Menu', 'Flow Trigger', 'Pay', 'CTA Link', 'System'];

const ScriptsPage: React.FC<Props> = () => {
  const toast = useToastContext();
  const [scripts, setScripts] = useState<ScriptItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [editId, setEditId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');

  const loadScripts = useCallback(async () => {
    setLoading(true);
    const items: ScriptItem[] = [];

    // Hardcoded scripts (Lambda defaults)
    items.push(
      { id: 'welcome_new', category: 'Welcome', trigger: 'Brand-new contact first message', messageType: 'Text', content: "Hi there! 👋 Welcome to WECARE.DIGITAL\n\nShop, pay, track requests, or get support — all right here.\n\nTap *Menu* to get started 👇", phone: 'Both', editable: true, configKey: 'wa_auto_response' },
      { id: 'welcome_hi', category: 'Welcome', trigger: '"hi" / "hello" / "menu" / "start"', messageType: 'Text', content: "Hi! 👋 Here's the menu — tap below to get started 👇", phone: 'Both', editable: true, configKey: 'welcome_message' },
    );

    // Main menu
    items.push(
      { id: 'main_menu', category: 'Menu', trigger: '"hi" / "menu" / "start" (after welcome text)', messageType: 'Interactive List', content: 'Header: WECARE.DIGITAL\nBody: Pick what you need 👇\nButton: Menu\nSections: Explore (4 items)', phone: 'Both', editable: true, configKey: 'welcome_message_config' },
    );

    // Selfservice menu
    items.push(
      { id: 'ss_menu', category: 'Menu', trigger: '"selfservice" / "self-service" / tapping Self Service', messageType: 'Interactive List', content: 'Header: Selfservice\nBody: Choose what you\'d like to do...\nButton: Browse Options\n10 items across 10 sections', phone: 'Both', editable: true, configKey: 'selfservice_menu_config' },
    );

    // Bharat Stack menu
    items.push(
      { id: 'bs_menu', category: 'Menu', trigger: '"bharat stack" / "/bharatstack" / tapping Bharat Stack', messageType: 'Interactive List', content: 'Header: Bharat Stack\nBody: Explore India\'s digital public infrastructure 🇮🇳\n6 items: Aadhaar, UPI, DigiLocker, eSign, ONDC, Account Aggregator', phone: 'Both', editable: true, configKey: 'bharat_stack_menu_config' },
    );

    // Flow trigger messages
    const flowTriggers: Record<string, { keywords: string[]; message: { body: string; flowCta: string }; flowId: string }> = {
      submit_request: { keywords: ['submit request', 'sr'], message: { body: '📋 Start a new support request...', flowCta: 'Submit Request' }, flowId: '931522532810297' },
      track_request: { keywords: ['track request', 'track', 'status'], message: { body: '🔍 Check the status of your request...', flowCta: 'Track Request' }, flowId: '973888792200167' },
      amend_request: { keywords: ['amend request', 'update request'], message: { body: '✏️ Edit or correct a submitted request...', flowCta: 'Update Request' }, flowId: '1533536534833353' },
      schedule_appointment: { keywords: ['appointment', 'book appointment'], message: { body: '📅 Schedule a consultation or service visit...', flowCta: 'Book Appointment' }, flowId: '1475722977488573' },
      rx_slot: { keywords: ['rx slot', 'medical visit'], message: { body: '🩺 Schedule a medical tourism or prescription visit...', flowCta: 'Book Medical Visit' }, flowId: '1892784521355352' },
      drop_docs: { keywords: ['drop docs', 'upload documents'], message: { body: '🖇️ Send supporting documents...', flowCta: 'Upload Documents' }, flowId: '1737801600902350' },
      enterprise_assist: { keywords: ['enterprise', 'b2b'], message: { body: '💼 Corporate, B2B, and bulk enquiries...', flowCta: 'Enterprise Support' }, flowId: '2132515287534606' },
      leave_review: { keywords: ['review', 'feedback'], message: { body: '⭐ Share your experience...', flowCta: 'Leave Feedback' }, flowId: '963443293213262' },
      subscribe: { keywords: ['subscribe', 'register'], message: { body: '🔔 Get updates, offers, and service news...', flowCta: 'Subscribe for Updates' }, flowId: '932104319588449' },
    };

    // Try to load overrides from SystemConfig
    try {
      const configTriggers = await api.getSystemConfig('flow_triggers_config');
      if (configTriggers && typeof configTriggers === 'object') {
        for (const [key, val] of Object.entries(configTriggers as Record<string, any>)) {
          if (val?.message?.body) {
            if (flowTriggers[key]) {
              flowTriggers[key].message.body = val.message.body;
              flowTriggers[key].message.flowCta = val.message.flowCta || flowTriggers[key].message.flowCta;
            }
            if (val.keywords) flowTriggers[key] = { ...flowTriggers[key], keywords: val.keywords };
          }
        }
      }
    } catch { /* use defaults */ }

    for (const [key, ft] of Object.entries(flowTriggers)) {
      items.push({
        id: `flow_${key}`,
        category: 'Flow Trigger',
        trigger: `Keywords: ${ft.keywords.slice(0, 4).join(', ')}`,
        messageType: 'Interactive Flow (Phone 1) / CTA URL (Phone 2)',
        content: `Body: ${ft.message.body}\nCTA: ${ft.message.flowCta}\nFlow ID: ${ft.flowId}`,
        phone: 'Phone 1: Flow form\nPhone 2: CTA link → r.wecare.digital',
        editable: true,
        configKey: 'flow_triggers_config',
      });
    }

    // Pay messages
    items.push(
      { id: 'pay_pulling', category: 'Pay', trigger: '"pay" / "payment" / "invoice" (Phone 1)', messageType: 'Text', content: '👀 Pulling your pending invoice...', phone: 'Phone 1', editable: false },
      { id: 'pay_no_dues', category: 'Pay', trigger: 'No pending invoices found', messageType: 'Text', content: '✅ No pending dues!', phone: 'Phone 1', editable: false },
      { id: 'pay_cta', category: 'Pay', trigger: '"pay" (Phone 2)', messageType: 'CTA URL Button', content: 'CTA: Pay Now → r.wecare.digital/pay', phone: 'Phone 2', editable: false },
    );

    // Phone 2 CTA links
    const ctaLinks = [
      { key: 'sr', label: 'Submit Request' }, { key: 'tr', label: 'Track Request' },
      { key: 'ar', label: 'Update Request' }, { key: 'sa', label: 'Book Appointment' },
      { key: 'rx', label: 'Book Medical Visit' }, { key: 'dd', label: 'Upload Documents' },
      { key: 'ea', label: 'Enterprise Support' }, { key: 'lr', label: 'Leave Feedback' },
      { key: 'sub', label: 'Subscribe' }, { key: 'pay', label: 'Pay Now' },
    ];
    for (const cl of ctaLinks) {
      items.push({
        id: `cta_${cl.key}`,
        category: 'CTA Link',
        trigger: `Phone 2 flow fallback for ${cl.label}`,
        messageType: 'CTA URL Button',
        content: `CTA: ${cl.label} → r.wecare.digital/${cl.key}`,
        phone: 'Phone 2 only',
        editable: false,
      });
    }

    // System messages
    items.push(
      { id: 'sys_reaction', category: 'System', trigger: 'Every inbound message (except reactions)', messageType: 'Reaction', content: '👍 Auto-reaction + read receipt', phone: 'Both', editable: false },
    );

    setScripts(items);
    setLoading(false);
  }, []);

  useEffect(() => { loadScripts(); }, [loadScripts]);

  const filtered = scripts.filter(s => {
    if (filter !== 'All' && s.category !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return s.content.toLowerCase().includes(q) || s.trigger.toLowerCase().includes(q) || s.id.toLowerCase().includes(q);
    }
    return true;
  });

  const catColor: Record<string, string> = {
    Welcome: '#d1f470', Menu: '#bfdbfe', 'Flow Trigger': '#fde68a', Pay: '#bbf7d0', 'CTA Link': '#e0e7ff', System: '#f3f4f6',
  };

  return (
    <div style={{ padding: '12px 0' }}>
      <div style={{ marginBottom: 12 }}>
        <p style={{ fontSize: 12, color: '#6b7280', margin: '0 0 8px' }}>
          Every automated message the bot sends. Use this to review content, check consistency, and improve copy.
        </p>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          {CATEGORIES.map(c => (
            <button key={c} onClick={() => setFilter(c)} style={{
              padding: '4px 10px', borderRadius: 4, border: filter === c ? '1.5px solid #1a3a2a' : '1px solid #d1d5db',
              background: filter === c ? '#1a3a2a' : '#fff', color: filter === c ? '#fff' : '#374151',
              fontSize: 11, fontWeight: 500, cursor: 'pointer',
            }}>{c}</button>
          ))}
          <input placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)}
                 style={{ padding: '4px 10px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 11, marginLeft: 'auto', width: 160 }} />
          <span style={{ fontSize: 11, color: '#9ca3af' }}>{filtered.length} scripts</span>
        </div>
      </div>

      {loading && <p style={{ color: '#9ca3af', fontSize: 12 }}>Loading...</p>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.map(s => (
          <div key={s.id} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, background: '#fff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ padding: '2px 6px', borderRadius: 3, fontSize: 10, fontWeight: 600, background: catColor[s.category] || '#f3f4f6' }}>{s.category}</span>
                <span style={{ fontSize: 10, color: '#9ca3af' }}>{s.messageType}</span>
              </div>
              <span style={{ fontSize: 10, color: '#9ca3af', fontFamily: 'monospace' }}>{s.id}</span>
            </div>
            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>Trigger: {s.trigger}</div>
            <pre style={{ fontSize: 12, color: '#1a3a2a', margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit', lineHeight: 1.5 }}>{s.content}</pre>
            <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 4 }}>Phone: {s.phone}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ScriptsPage;
