/**
 * SMS Campaign Page (AWS Pinpoint)
 * Bulk SMS campaigns via Amazon Pinpoint
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../../../../api/client';
import { API_BASE } from '../../../../config/constants';
import { RefreshIcon } from '../../../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
}

type TabType = 'create' | 'logs';

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

const SmsCampaignPage: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
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
  const [senderId, setSenderId] = useState('WECARE');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const contactsData = await api.listContacts();
      setContacts(contactsData.filter(c => c.phone));
      
      // Load SMS campaign logs
      const messages = await api.listMessages(undefined, 'SMS');
      const campaignMsgs = messages.filter(m => (m as any).campaignId && (m as any).provider === 'aws');
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
      const campaignId = `SC${Date.now()}`;
      let sent = 0, failed = 0;

      for (const contactId of selectedContacts) {
        try {
          const response = await fetch(`${API_BASE}/sms-aws/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contactId,
              content: messageContent,
              senderId,
              messageType: 'TRANSACTIONAL',
              campaignId,
              campaignName
            })
          });
          if (response.ok) sent++;
          else failed++;
        } catch (e) {
          failed++;
        }
        // Rate limit
        if (sent % 10 === 0) await new Promise(r => setTimeout(r, 200));
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
        <h2>SMS Campaign (AWS)</h2>
        <button className="refresh-btn" onClick={loadData} disabled={loading}>
          {loading ? '...' : <RefreshIcon size={18} />}
        </button>
      </div>

      <div className="sub-tabs">
        <button className={`sub-tab ${activeTab === 'create' ? 'active' : ''}`} onClick={() => setActiveTab('create')}>
          Create Campaign
        </button>
        <button className={`sub-tab ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>
          Campaign Logs ({campaigns.length})
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
              <label>Sender ID</label>
              <input type="text" value={senderId} onChange={e => setSenderId(e.target.value)} placeholder="WECARE" maxLength={11} />
            </div>
          </div>

          <div className="form-group">
            <label>Message Content * ({messageContent.length}/160)</label>
            <textarea value={messageContent} onChange={e => setMessageContent(e.target.value)} placeholder="Enter your SMS message..." rows={3} maxLength={1600} />
            <span className="hint">{Math.ceil(messageContent.length / 160) || 1} SMS segment(s)</span>
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
              {sending ? `Sending...` : `Send Campaign to ${selectedContacts.length} Contacts`}
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

      <style jsx>{`
        .campaign-page { }
        .campaign-header { }
        .campaign-header h2 { }
        .refresh-btn { }
        .sub-tabs { }
        .sub-tab { }
        .sub-tab.active { }
        .msg-bar { }
        .msg-bar.success { }
        .msg-bar.error { }
        .msg-bar button { }
        .form-row { }
        .form-group { }
        .form-group label { }
        .form-group input, .form-group select, .form-group textarea { }
        .form-group textarea { }
        .hint { font-size: 12px; color: #6b7280; margin-top: 4px; display: block; }
        .contacts-section { }
        .contacts-header { }
        .contacts-header h3 { }
        .contacts-actions { }
        .search-input { }
        .select-all-btn { }
        .contacts-grid { }
        .contact-item { }
        .contact-item.selected { }
        .contact-item input { }
        .contact-name { }
        .contact-phone { }
        .send-section { }
        .send-btn { }
        .send-btn:disabled { }
        .logs-table { }
        .logs-table th, .logs-table td { }
        .logs-table th { }
        .logs-table .success { }
        .logs-table .error { }
        .empty { }
        @media (max-width: 768px) { }
      `}</style>
    </div>
  );
};

export default SmsCampaignPage;
