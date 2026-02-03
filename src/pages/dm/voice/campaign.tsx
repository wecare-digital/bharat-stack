/**
 * Voice Campaign Page - Unified
 * Bulk voice calls via AWS Connect
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
  completed: number;
  answered: number;
  failed: number;
  totalDuration: number;
  createdAt: string;
}

const VoiceCampaignPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignLog[]>([]);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form state
  const [campaignName, setCampaignName] = useState('');
  const [messageText, setMessageText] = useState('');
  const [voiceId, setVoiceId] = useState('Joanna');
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const contactsData = await api.listContacts();
      setContacts(contactsData.filter(c => c.phone));
      
      try {
        const response = await fetch(`${API_BASE}/voice-aws/calls?limit=100`);
        if (response.ok) {
          const data = await response.json();
          const campaignCalls = (data.calls || []).filter((c: any) => c.campaignId);
          const campaignMap = new Map<string, CampaignLog>();
          campaignCalls.forEach((c: any) => {
            const cid = c.campaignId;
            if (!campaignMap.has(cid)) {
              campaignMap.set(cid, { id: cid, name: c.campaignName || cid, recipients: 0, completed: 0, answered: 0, failed: 0, totalDuration: 0, createdAt: new Date(c.createdAt * 1000).toISOString() });
            }
            const camp = campaignMap.get(cid)!;
            camp.recipients++;
            if (c.status === 'completed' || c.status === 'answered') camp.completed++;
            if (c.status === 'answered') camp.answered++;
            if (c.status === 'failed' || c.status === 'no-answer') camp.failed++;
            camp.totalDuration += c.duration || 0;
          });
          setCampaigns(Array.from(campaignMap.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
        }
      } catch { /* API may not exist */ }
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
    if (!messageText.trim()) { setMessage({ type: 'error', text: 'Message text required' }); return; }
    if (selectedContacts.length === 0) { setMessage({ type: 'error', text: 'Select at least one contact' }); return; }

    setSending(true);
    setMessage(null);

    try {
      const campaignId = `VC${Date.now()}`;
      let sent = 0, failed = 0;

      for (const contactId of selectedContacts) {
        const contact = contacts.find(c => c.contactId === contactId);
        if (!contact?.phone) { failed++; continue; }
        
        try {
          const response = await fetch(`${API_BASE}/voice-aws/call`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: contact.phone, message: messageText, voiceId, campaignId, campaignName })
          });
          if (response.ok) sent++; else failed++;
        } catch { failed++; }
        await new Promise(r => setTimeout(r, 500));
      }

      setMessage({ type: sent > 0 ? 'success' : 'error', text: `Campaign initiated: ${sent} calls started, ${failed} failed` });
      setCampaignName(''); setMessageText(''); setSelectedContacts([]); setSelectAll(false);
      loadData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Campaign failed' });
    } finally {
      setSending(false);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice Campaign | WECARE.DIGITAL" description="Send bulk voice calls" />
      <div className="campaign-page">
        <div className="campaign-header">
          <h2>Voice Campaign</h2>
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
            <input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My Voice Campaign" />
          </div>
          <div className="form-group">
            <label>Voice</label>
            <select value={voiceId} onChange={e => setVoiceId(e.target.value)}>
              <option value="Joanna">Joanna (Female)</option>
              <option value="Matthew">Matthew (Male)</option>
              <option value="Aditi">Aditi (Hindi)</option>
              <option value="Raveena">Raveena (Indian English)</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label>Message Text *</label>
          <textarea value={messageText} onChange={e => setMessageText(e.target.value)} placeholder="Enter the message to be spoken..." rows={4} />
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
            {sending ? `Calling...` : `Start Campaign to ${selectedContacts.length} Contacts`}
          </Button>
        </div>

        {campaigns.length > 0 && (
          <div style={{ marginTop: '32px' }}>
            <h3 style={{ marginBottom: '16px' }}>Recent Campaigns</h3>
            <table className="logs-table">
              <thead>
                <tr><th>Campaign</th><th>Recipients</th><th>Completed</th><th>Answered</th><th>Failed</th><th>Date</th></tr>
              </thead>
              <tbody>
                {campaigns.slice(0, 5).map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.name}</strong></td>
                    <td>{c.recipients}</td>
                    <td className="success">{c.completed}</td>
                    <td>{c.answered}</td>
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

export default VoiceCampaignPage;
