/**
 * SMS Campaign Page - Unified
 * Bulk SMS campaigns via AWS Pinpoint
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import * as api from '../../../api/client';
import { API_BASE } from '../../../config/constants';
import Button from '../../../components/ui/Button';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface CampaignLog {
  id: string;
  name: string;
  recipients: number;
  sent: number;
  delivered: number;
  failed: number;
  createdAt: string;
}

const SmsCampaignPage: React.FC<PageProps> = ({ signOut, user }) => {
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
      
      const messages = await api.listMessages(undefined, 'SMS');
      const campaignMsgs = messages.filter(m => (m as any).campaignId && (m as any).provider === 'aws');
      const campaignMap = new Map<string, CampaignLog>();
      campaignMsgs.forEach(m => {
        const cid = (m as any).campaignId;
        if (!campaignMap.has(cid)) {
          campaignMap.set(cid, { id: cid, name: (m as any).campaignName || cid, recipients: 0, sent: 0, delivered: 0, failed: 0, createdAt: m.timestamp });
        }
        const c = campaignMap.get(cid)!;
        c.recipients++;
        if (m.status === 'sent' || m.status === 'delivered') c.sent++;
        if (m.status === 'delivered') c.delivered++;
        if (m.status === 'failed') c.failed++;
      });
      setCampaigns(Array.from(campaignMap.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredContacts = contacts.filter(c =>
    c.name?.toLowerCase().includes(searchQuery.toLowerCase()) || c.phone?.includes(searchQuery)
  );

  const handleSelectAll = () => {
    if (selectAll) setSelectedContacts([]);
    else setSelectedContacts(filteredContacts.map(c => c.contactId));
    setSelectAll(!selectAll);
  };

  const toggleContact = (id: string) => {
    setSelectedContacts(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]);
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
            body: JSON.stringify({ contactId, content: messageContent, senderId, messageType: 'TRANSACTIONAL', campaignId, campaignName })
          });
          if (response.ok) sent++; else failed++;
        } catch { failed++; }
        if (sent % 10 === 0) await new Promise(r => setTimeout(r, 200));
      }

      setMessage({ type: sent > 0 ? 'success' : 'error', text: `Campaign sent: ${sent} success, ${failed} failed` });
      setCampaignName(''); setMessageContent(''); setSelectedContacts([]); setSelectAll(false);
      loadData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Campaign failed' });
    } finally {
      setSending(false);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS Campaign | WECARE.DIGITAL" description="Send bulk SMS campaigns" />
      <div className="campaign-page">
        <div className="campaign-header">
          <h2>SMS Campaign</h2>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
        </div>

        {message && (
          <div className={`msg-bar ${message.type}`}>
            {message.text}
            <button onClick={() => setMessage(null)}>×</button>
          </div>
        )}

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
          <span style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px', display: 'block' }}>{Math.ceil(messageContent.length / 160) || 1} SMS segment(s)</span>
        </div>

        <div className="contacts-section">
          <div className="contacts-header">
            <h3>Select Recipients ({selectedContacts.length} / {filteredContacts.length})</h3>
            <div className="contacts-actions">
              <input type="text" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="search-input" />
              <button className="select-all-btn" onClick={handleSelectAll}>{selectAll ? 'Deselect All' : 'Select All'}</button>
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
          <Button variant="primary" className="send-btn" onClick={handleSendCampaign} disabled={sending || selectedContacts.length === 0} loading={sending}>
            {sending ? `Sending...` : `Send Campaign to ${selectedContacts.length} Contacts`}
          </Button>
        </div>

        {campaigns.length > 0 && (
          <div style={{ marginTop: '32px' }}>
            <h3 style={{ marginBottom: '16px' }}>Recent Campaigns</h3>
            <table className="logs-table">
              <thead>
                <tr><th>Campaign</th><th>Recipients</th><th>Sent</th><th>Delivered</th><th>Failed</th><th>Date</th></tr>
              </thead>
              <tbody>
                {campaigns.slice(0, 5).map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.name}</strong></td>
                    <td>{c.recipients}</td>
                    <td className="success">{c.sent}</td>
                    <td>{c.delivered}</td>
                    <td className="error">{c.failed}</td>
                    <td>{new Date(c.createdAt).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default SmsCampaignPage;
