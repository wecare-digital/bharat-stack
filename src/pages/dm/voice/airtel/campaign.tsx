/**
 * Voice IN Campaign Page (Airtel CCP)
 * Bulk voice campaigns via Airtel CCP for India
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
  completed: number;
  answered: number;
  failed: number;
  totalDuration: number;
  createdAt: string;
}

const VoiceInCampaignPage: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const [activeTab, setActiveTab] = useState<TabType>('create');
  const [loading, setLoading] = useState(false);
  const [calling, setCalling] = useState(false);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignLog[]>([]);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form state
  const [campaignName, setCampaignName] = useState('');
  const [agentNumber, setAgentNumber] = useState('');
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [enableRecording, setEnableRecording] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const contactsData = await api.listContacts();
      // Filter for Indian numbers only
      setContacts(contactsData.filter(c => c.phone?.startsWith('+91')));
      
      // Load voice CDR for campaigns
      const response = await fetch(`${API_BASE}/voice-cdr-read?limit=200`);
      if (response.ok) {
        const data = await response.json();
        const records = data.records || [];
        
        // Group by campaign
        const campaignRecords = records.filter((r: any) => r.campaignId);
        const campaignMap = new Map<string, CampaignLog>();
        campaignRecords.forEach((r: any) => {
          const cid = r.campaignId;
          if (!campaignMap.has(cid)) {
            campaignMap.set(cid, {
              id: cid,
              name: r.campaignName || cid,
              recipients: 0,
              completed: 0,
              answered: 0,
              failed: 0,
              totalDuration: 0,
              createdAt: new Date(r.createdAt * 1000).toISOString()
            });
          }
          const camp = campaignMap.get(cid)!;
          camp.recipients++;
          if (r.overallCallStatus === 'Answered') {
            camp.completed++;
            camp.answered++;
          }
          if (r.overallCallStatus === 'Missed' || r.overallCallStatus === 'Busy') camp.failed++;
          camp.totalDuration += r.conversationDurationSec || 0;
        });
        setCampaigns(Array.from(campaignMap.values()).sort((a, b) => 
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        ));
      }
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

  const handleStartCampaign = async () => {
    if (!campaignName.trim()) { setMessage({ type: 'error', text: 'Campaign name required' }); return; }
    if (!agentNumber.trim()) { setMessage({ type: 'error', text: 'Agent number required' }); return; }
    if (selectedContacts.length === 0) { setMessage({ type: 'error', text: 'Select at least one contact' }); return; }

    setCalling(true);
    setMessage(null);

    try {
      const campaignId = `AVC${Date.now()}`;
      let initiated = 0, failed = 0;

      for (const contactId of selectedContacts) {
        const contact = contacts.find(c => c.contactId === contactId);
        if (!contact?.phone) { failed++; continue; }

        try {
          const response = await fetch(`${API_BASE}/voice/call`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              callType: 'c2c',
              fromNumber: agentNumber,
              toNumber: contact.phone,
              enableRecording,
              provider: 'airtel_ccp',
              campaignId,
              campaignName
            })
          });
          if (response.ok) initiated++;
          else failed++;
        } catch (e) {
          failed++;
        }
        // Rate limit - 1 call per 2 seconds for C2C
        await new Promise(r => setTimeout(r, 2000));
      }

      setMessage({ 
        type: initiated > 0 ? 'success' : 'error', 
        text: `Campaign started: ${initiated} calls initiated, ${failed} failed` 
      });
      setCampaignName('');
      setSelectedContacts([]);
      setSelectAll(false);
      loadData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Campaign failed' });
    } finally {
      setCalling(false);
    }
  };

  const formatDuration = (seconds: number): string => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="campaign-page">
      <div className="campaign-header">
        <h2>Voice IN Campaign (Airtel)</h2>
        <button className="refresh-btn" onClick={loadData} disabled={loading}>
          {loading ? '...' : <RefreshIcon size={18} />}
        </button>
      </div>

      <div className="info-banner">
        <span>📞 Inbound: +91 9319767034</span>
        <span>•</span>
        <span>Click-to-Call (C2C) campaigns via Airtel CCP</span>
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
              <input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My Voice Campaign" />
            </div>
            <div className="form-group">
              <label>Your Agent Number *</label>
              <input type="tel" value={agentNumber} onChange={e => setAgentNumber(e.target.value.replace(/[^0-9+]/g, ''))} placeholder="+91 XXXXXXXXXX" />
              <span className="hint">You will receive the call first, then connected to customer</span>
            </div>
          </div>

          <div className="form-group checkbox-row">
            <label>
              <input type="checkbox" checked={enableRecording} onChange={e => setEnableRecording(e.target.checked)} />
              Enable call recording
            </label>
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
            <button className="send-btn" onClick={handleStartCampaign} disabled={calling || selectedContacts.length === 0 || !agentNumber}>
              {calling ? `Calling...` : `📞 Call ${selectedContacts.length} contacts`}
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
                <th>Completed</th>
                <th>Answered</th>
                <th>Failed</th>
                <th>Total Duration</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map(c => (
                <tr key={c.id}>
                  <td><strong>{c.name}</strong></td>
                  <td>{c.recipients}</td>
                  <td className="success">{c.completed}</td>
                  <td>{c.answered}</td>
                  <td className="error">{c.failed}</td>
                  <td>{formatDuration(c.totalDuration)}</td>
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
        .campaign-page { padding: 20px; height: 100%; overflow-y: auto; }
        .campaign-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .campaign-header h2 { margin: 0; font-size: 20px; }
        .refresh-btn { padding: 8px 12px; background: #f5f5f5; border: 1px solid #e5e5e5; border-radius: 8px; cursor: pointer; }
        .info-banner { display: flex; gap: 12px; align-items: center; background: #fef3c7; padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; color: #92400e; }
        .sub-tabs { display: flex; gap: 8px; margin-bottom: 16px; }
        .sub-tab { padding: 8px 16px; border: 1px solid #e5e5e5; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; }
        .sub-tab.active { background: #f5f5f5; font-weight: 600; }
        .msg-bar { padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; display: flex; justify-content: space-between; font-size: 13px; }
        .msg-bar.success { background: #d1fae5; color: #065f46; }
        .msg-bar.error { background: #fef2f2; color: #dc2626; }
        .msg-bar button { background: none; border: none; font-size: 18px; cursor: pointer; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; }
        .form-group input, .form-group select { width: 100%; padding: 10px 12px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 14px; }
        .hint { font-size: 12px; color: #666; margin-top: 4px; display: block; }
        .checkbox-row label { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px; }
        .checkbox-row input { width: 18px; height: 18px; }
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
        @media (max-width: 768px) { .form-row { grid-template-columns: 1fr; } .contacts-grid { grid-template-columns: 1fr; } }
      `}</style>
    </div>
  );
};

export default VoiceInCampaignPage;
