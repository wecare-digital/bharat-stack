/**
 * SMS IN Campaign Page (Airtel IQ)
 * Bulk SMS campaigns via Airtel IQ for India with DLT compliance
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../../../../api/client';
import { API_BASE } from '../../../../config/constants';
import { RefreshIcon } from '../../../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'create' | 'logs' | 'dlt';

interface CampaignLog {
  id: string;
  name: string;
  recipients: number;
  sent: number;
  delivered: number;
  failed: number;
  status: string;
  createdAt: string;
}

const SmsInCampaignPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('create');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignLog[]>([]);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form state
  const [campaignName, setCampaignName] = useState('');
  const [messageContent, setMessageContent] = useState('');
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  
  // DLT Config
  const [messageType, setMessageType] = useState('SERVICE_IMPLICIT');
  const [dltTemplateId, setDltTemplateId] = useState('1007974344269130859');
  const [sourceAddress, setSourceAddress] = useState('WDBEEP');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const contactsData = await api.listContacts();
      // Filter for Indian numbers only
      setContacts(contactsData.filter(c => c.phone?.startsWith('+91')));
      
      // Load SMS campaign logs
      const messages = await api.listMessages(undefined, 'SMS');
      const campaignMsgs = messages.filter(m => (m as any).campaignId && (m as any).provider === 'airtel');
      const campaignMap = new Map<string, CampaignLog>();
      campaignMsgs.forEach(m => {
        const cid = (m as any).campaignId;
        if (!campaignMap.has(cid)) {
          campaignMap.set(cid, {
            id: cid,
            name: (m as any).campaignName || cid,
            recipients: 0,
            sent: 0,
            delivered: 0,
            failed: 0,
            status: 'completed',
            createdAt: m.timestamp
          });
        }
        const c = campaignMap.get(cid)!;
        c.recipients++;
        if (m.status === 'sent' || m.status === 'delivered') c.sent++;
        if (m.status === 'delivered') c.delivered++;
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
    if (!messageContent.trim()) { setMessage({ type: 'error', text: 'Message content required' }); return; }
    if (selectedContacts.length === 0) { setMessage({ type: 'error', text: 'Select at least one contact' }); return; }

    setSending(true);
    setMessage(null);

    try {
      const campaignId = `AIC${Date.now()}`;
      let sent = 0, failed = 0;

      for (const contactId of selectedContacts) {
        const contact = contacts.find(c => c.contactId === contactId);
        if (!contact?.phone) { failed++; continue; }

        try {
          const response = await fetch(`${API_BASE}/sms/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contactId,
              phoneNumber: contact.phone,
              content: messageContent,
              provider: 'airtel',
              messageType,
              dltTemplateId,
              sourceAddress,
              campaignId,
              campaignName
            })
          });
          if (response.ok) sent++;
          else failed++;
        } catch (e) {
          failed++;
        }
        // Rate limit - 5 msgs/sec for Airtel
        if (sent % 5 === 0) await new Promise(r => setTimeout(r, 1000));
      }

      setMessage({ 
        type: sent > 0 ? 'success' : 'error', 
        text: `Campaign sent: ${sent} success, ${failed} failed` 
      });
      setCampaignName('');
      setMessageContent('');
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
        <h2>SMS IN Campaign (Airtel)</h2>
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
        <button className={`sub-tab ${activeTab === 'dlt' ? 'active' : ''}`} onClick={() => setActiveTab('dlt')}>
          ⚙️ DLT Config
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
              <input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My SMS Campaign" />
            </div>
            <div className="form-group">
              <label>Message Type</label>
              <select value={messageType} onChange={e => setMessageType(e.target.value)}>
                <option value="SERVICE_IMPLICIT">Service Implicit</option>
                <option value="SERVICE_EXPLICIT">Service Explicit</option>
                <option value="TRANSACTIONAL">Transactional</option>
                <option value="PROMOTIONAL">Promotional</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Message Content * ({messageContent.length}/160)</label>
            <textarea value={messageContent} onChange={e => setMessageContent(e.target.value)} placeholder="Enter your DLT-approved message..." rows={3} maxLength={1600} />
            <span className="hint">{Math.ceil(messageContent.length / 160) || 1} SMS segment(s) • Header: {sourceAddress}</span>
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
              {filteredContacts.length === 0 && <div className="empty">No Indian contacts found (+91)</div>}
            </div>
          </div>

          <div className="send-section">
            <button className="send-btn" onClick={handleSendCampaign} disabled={sending || selectedContacts.length === 0}>
              {sending ? `Sending...` : `📤 Send to ${selectedContacts.length} contacts`}
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
                <th>Recipients</th>
                <th>Sent</th>
                <th>Delivered</th>
                <th>Failed</th>
                <th>Rate</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map(c => (
                <tr key={c.id}>
                  <td><strong>{c.name}</strong></td>
                  <td>{c.recipients}</td>
                  <td className="success">{c.sent}</td>
                  <td>{c.delivered}</td>
                  <td className="error">{c.failed}</td>
                  <td>{c.sent > 0 ? Math.round((c.delivered / c.sent) * 100) : 0}%</td>
                  <td>{new Date(c.createdAt).toLocaleDateString()}</td>
                </tr>
              ))}
              {campaigns.length === 0 && (
                <tr><td colSpan={7} className="empty">No campaigns yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'dlt' && (
        <div className="dlt-section">
          <div className="dlt-info">
            <h3>DLT Configuration</h3>
            <p>Configure your DLT (Distributed Ledger Technology) settings for TRAI compliance.</p>
          </div>

          <div className="dlt-card">
            <h4>📋 Registered Entity</h4>
            <div className="dlt-row"><span>Entity Name:</span><strong>WECARE.DIGITAL</strong></div>
            <div className="dlt-row"><span>PE ID:</span><code>1201161991108627443</code></div>
          </div>

          <div className="dlt-card">
            <h4>📡 Registered Header</h4>
            <div className="dlt-row"><span>Header:</span><strong>WDBEEP</strong></div>
            <div className="dlt-row"><span>Header DLT ID:</span><code>1405170900886606599</code></div>
          </div>

          <div className="dlt-card">
            <h4>📝 Template</h4>
            <div className="form-group">
              <label>DLT Template ID</label>
              <input type="text" value={dltTemplateId} onChange={e => setDltTemplateId(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Source Address (Header)</label>
              <input type="text" value={sourceAddress} onChange={e => setSourceAddress(e.target.value)} />
            </div>
          </div>
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
        .form-row { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px 12px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 14px; }
        .form-group textarea { resize: vertical; font-family: inherit; }
        .hint { font-size: 12px; color: #666; margin-top: 4px; display: block; }
        .contacts-section { background: #f9f9f9; border-radius: 12px; padding: 16px; margin-bottom: 20px; }
        .contacts-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 12px; }
        .contacts-header h3 { margin: 0; font-size: 14px; }
        .contacts-actions { display: flex; gap: 8px; }
        .search-input { padding: 8px 12px; border: 1px solid #e5e5e5; border-radius: 6px; font-size: 13px; width: 200px; }
        .select-all-btn { padding: 8px 12px; background: white; border: 1px solid #e5e5e5; border-radius: 6px; cursor: pointer; font-size: 13px; }
        .contacts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 8px; max-height: 250px; overflow-y: auto; }
        .contact-item { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: white; border: 1px solid #e5e5e5; border-radius: 8px; cursor: pointer; }
        .contact-item.selected { background: #fef3c7; border-color: #f59e0b; }
        .contact-item input { width: 16px; height: 16px; }
        .contact-name { flex: 1; font-size: 13px; font-weight: 500; }
        .contact-phone { font-size: 12px; color: #666; }
        .send-section { text-align: center; }
        .send-btn { padding: 14px 32px; background: #f59e0b; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
        .send-btn:disabled { background: #9ca3af; cursor: not-allowed; }
        .logs-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .logs-table th, .logs-table td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e5e5; }
        .logs-table th { background: #f5f5f5; font-weight: 600; font-size: 12px; }
        .logs-table .success { color: #10b981; }
        .logs-table .error { color: #dc2626; }
        .empty { text-align: center; padding: 40px; color: #666; }
        .dlt-section { max-width: 600px; }
        .dlt-info { margin-bottom: 20px; }
        .dlt-info h3 { margin: 0 0 8px 0; }
        .dlt-info p { margin: 0; color: #666; font-size: 14px; }
        .dlt-card { background: #f9f9f9; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
        .dlt-card h4 { margin: 0 0 12px 0; font-size: 14px; }
        .dlt-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; }
        .dlt-row code { background: #e5e5e5; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
        @media (max-width: 768px) { .form-row { grid-template-columns: 1fr; } .contacts-grid { grid-template-columns: 1fr; } }
      `}</style>
    </div>
  );
};

export default SmsInCampaignPage;
