/**
 * WhatsApp Campaign Page
 * Bulk messaging campaigns via WhatsApp
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../../../api/client';
import { WHATSAPP_PHONES } from '../../../config/constants';
import { RefreshIcon } from '../../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'create' | 'logs';

interface Template {
  name: string;
  language: string;
  status: string;
  category: string;
}

interface CampaignLog {
  id: string;
  name: string;
  template: string;
  recipients: number;
  sent: number;
  delivered: number;
  read: number;
  failed: number;
  status: string;
  createdAt: string;
}

const WhatsAppCampaignPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('create');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignLog[]>([]);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form state
  const [campaignName, setCampaignName] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [selectedWaba, setSelectedWaba] = useState(WHATSAPP_PHONES.primary.id);
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [scheduleTime, setScheduleTime] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, templatesData] = await Promise.all([
        api.listContacts(),
        api.listWhatsAppTemplates(WHATSAPP_PHONES.primary.id)
      ]);
      setContacts(contactsData.filter(c => c.phone?.startsWith('+91')));
      setTemplates(templatesData.filter(t => t.status === 'APPROVED'));
      
      // Load campaign logs from messages
      const messages = await api.listMessages(undefined, 'WHATSAPP');
      const campaignMsgs = messages.filter(m => (m as any).campaignId);
      // Group by campaign
      const campaignMap = new Map<string, CampaignLog>();
      campaignMsgs.forEach(m => {
        const cid = (m as any).campaignId;
        if (!campaignMap.has(cid)) {
          campaignMap.set(cid, {
            id: cid,
            name: (m as any).campaignName || cid,
            template: (m as any).templateName || '-',
            recipients: 0,
            sent: 0,
            delivered: 0,
            read: 0,
            failed: 0,
            status: 'completed',
            createdAt: m.timestamp
          });
        }
        const c = campaignMap.get(cid)!;
        c.recipients++;
        if (m.status === 'sent' || m.status === 'delivered' || m.status === 'read') c.sent++;
        if (m.status === 'delivered' || m.status === 'read') c.delivered++;
        if (m.status === 'read') c.read++;
        if (m.status === 'failed') c.failed++;
      });
      setCampaigns(Array.from(campaignMap.values()).sort((a, b) => 
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      ));
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredContacts = contacts.filter(c =>
    c.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.phone?.includes(searchQuery)
  );

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedContacts([]);
    } else {
      setSelectedContacts(filteredContacts.map(c => c.contactId));
    }
    setSelectAll(!selectAll);
  };

  const toggleContact = (id: string) => {
    setSelectedContacts(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  const handleSendCampaign = async () => {
    if (!campaignName.trim()) { setMessage({ type: 'error', text: 'Campaign name required' }); return; }
    if (!selectedTemplate) { setMessage({ type: 'error', text: 'Select a template' }); return; }
    if (selectedContacts.length === 0) { setMessage({ type: 'error', text: 'Select at least one contact' }); return; }

    setSending(true);
    setMessage(null);

    try {
      const campaignId = `WC${Date.now()}`;
      let sent = 0, failed = 0;

      for (const contactId of selectedContacts) {
        try {
          await api.sendWhatsAppTemplate({
            contactId,
            templateName: selectedTemplate,
            phoneNumberId: selectedWaba,
            campaignId,
            campaignName
          });
          sent++;
        } catch (e) {
          failed++;
        }
        // Rate limit: 80 msgs/sec
        if (sent % 50 === 0) await new Promise(r => setTimeout(r, 1000));
      }

      setMessage({ 
        type: sent > 0 ? 'success' : 'error', 
        text: `Campaign sent: ${sent} success, ${failed} failed` 
      });
      setCampaignName('');
      setSelectedContacts([]);
      setSelectAll(false);
      loadData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Campaign failed' });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="campaign-page">
      <div className="campaign-header">
        <h2>WhatsApp Campaign</h2>
        <button className="refresh-btn" onClick={loadData} disabled={loading}>
          {loading ? '...' : <RefreshIcon size={18} />}
        </button>
      </div>

      <div className="sub-tabs">
        <button className={`sub-tab ${activeTab === 'create' ? 'active' : ''}`} onClick={() => setActiveTab('create')}>
          ✏️ Create
        </button>
        <button className={`sub-tab ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>
          📋 Logs ({campaigns.length})
        </button>
      </div>

      {message && (
        <div className={`msg-bar ${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)}>×</button>
        </div>
      )}

      {activeTab === 'create' && (
        <div className="create-section">
          <div className="form-row">
            <div className="form-group">
              <label>Campaign Name *</label>
              <input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My Campaign" />
            </div>
            <div className="form-group">
              <label>Template *</label>
              <select value={selectedTemplate} onChange={e => setSelectedTemplate(e.target.value)}>
                <option value="">Select template</option>
                {templates.map(t => (
                  <option key={t.name} value={t.name}>{t.name} ({t.language})</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Send From</label>
              <select value={selectedWaba} onChange={e => setSelectedWaba(e.target.value)}>
                <option value={WHATSAPP_PHONES.primary.id}>{WHATSAPP_PHONES.primary.name}</option>
                <option value={WHATSAPP_PHONES.secondary.id}>{WHATSAPP_PHONES.secondary.name}</option>
              </select>
            </div>
          </div>

          <div className="contacts-section">
            <div className="contacts-header">
              <h3>Select Recipients ({selectedContacts.length} / {filteredContacts.length})</h3>
              <div className="contacts-actions">
                <input type="text" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="search-input" />
                <button className="select-all-btn" onClick={handleSelectAll}>
                  {selectAll ? 'Deselect All' : 'Select All'}
                </button>
              </div>
            </div>
            <div className="contacts-grid">
              {filteredContacts.slice(0, 100).map(c => (
                <label key={c.contactId} className={`contact-item ${selectedContacts.includes(c.contactId) ? 'selected' : ''}`}>
                  <input type="checkbox" checked={selectedContacts.includes(c.contactId)} onChange={() => toggleContact(c.contactId)} />
                  <span className="contact-name">{c.name || c.phone}</span>
                  <span className="contact-phone">{c.phone}</span>
                </label>
              ))}
              {filteredContacts.length === 0 && <div className="empty">No contacts found</div>}
            </div>
          </div>

          <div className="send-section">
            <button className="send-btn" onClick={handleSendCampaign} disabled={sending || selectedContacts.length === 0}>
              {sending ? `Sending... (${selectedContacts.length})` : `📤 Send to ${selectedContacts.length} contacts`}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="logs-section">
          <table className="logs-table">
            <thead>
              <tr>
                <th>Campaign</th>
                <th>Template</th>
                <th>Recipients</th>
                <th>Sent</th>
                <th>Delivered</th>
                <th>Read</th>
                <th>Failed</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map(c => (
                <tr key={c.id}>
                  <td><strong>{c.name}</strong></td>
                  <td>{c.template}</td>
                  <td>{c.recipients}</td>
                  <td className="success">{c.sent}</td>
                  <td>{c.delivered}</td>
                  <td>{c.read}</td>
                  <td className="error">{c.failed}</td>
                  <td>{new Date(c.createdAt).toLocaleDateString()}</td>
                </tr>
              ))}
              {campaigns.length === 0 && (
                <tr><td colSpan={8} className="empty">No campaigns yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <style jsx>{`
        .campaign-page { padding: 20px; height: 100%; overflow-y: auto; }
        .campaign-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .campaign-header h2 { margin: 0; font-size: 20px; }
        .refresh-btn { padding: 8px 12px; background: #f5f5f5; border: 1px solid #e5e5e5; border-radius: 8px; cursor: pointer; }
        .sub-tabs { display: flex; gap: 8px; margin-bottom: 16px; }
        .sub-tab { padding: 8px 16px; border: 1px solid #e5e5e5; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; }
        .sub-tab.active { background: #f5f5f5; font-weight: 600; }
        .msg-bar { padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; display: flex; justify-content: space-between; font-size: 13px; }
        .msg-bar.success { background: #d1fae5; color: #065f46; }
        .msg-bar.error { background: #fef2f2; color: #dc2626; }
        .msg-bar button { background: none; border: none; font-size: 18px; cursor: pointer; }
        .form-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
        .form-group label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; }
        .form-group input, .form-group select { width: 100%; padding: 10px 12px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 14px; }
        .contacts-section { background: #f9f9f9; border-radius: 12px; padding: 16px; margin-bottom: 20px; }
        .contacts-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 12px; }
        .contacts-header h3 { margin: 0; font-size: 14px; }
        .contacts-actions { display: flex; gap: 8px; }
        .search-input { padding: 8px 12px; border: 1px solid #e5e5e5; border-radius: 6px; font-size: 13px; width: 200px; }
        .select-all-btn { padding: 8px 12px; background: white; border: 1px solid #e5e5e5; border-radius: 6px; cursor: pointer; font-size: 13px; }
        .contacts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 8px; max-height: 300px; overflow-y: auto; }
        .contact-item { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: white; border: 1px solid #e5e5e5; border-radius: 8px; cursor: pointer; }
        .contact-item.selected { background: #f0fdf4; border-color: #10b981; }
        .contact-item input { width: 16px; height: 16px; }
        .contact-name { flex: 1; font-size: 13px; font-weight: 500; }
        .contact-phone { font-size: 12px; color: #666; }
        .send-section { text-align: center; }
        .send-btn { padding: 14px 32px; background: #10b981; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
        .send-btn:disabled { background: #9ca3af; cursor: not-allowed; }
        .logs-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .logs-table th, .logs-table td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e5e5; }
        .logs-table th { background: #f5f5f5; font-weight: 600; font-size: 12px; }
        .logs-table .success { color: #10b981; }
        .logs-table .error { color: #dc2626; }
        .empty { text-align: center; padding: 40px; color: #666; }
        @media (max-width: 768px) { .form-row { grid-template-columns: 1fr; } .contacts-grid { grid-template-columns: 1fr; } }
      `}</style>
    </div>
  );
};

export default WhatsAppCampaignPage;
