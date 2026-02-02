/**
 * Voice Campaign Page (AWS Connect)
 * Bulk voice campaigns via Amazon Connect
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

interface VoiceCall {
  id: string;
  phoneNumber: string;
  status: string;
  duration: number;
  recordingUrl?: string;
  createdAt: number;
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

const VoiceCampaignPage: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const [activeTab, setActiveTab] = useState<TabType>('create');
  const [loading, setLoading] = useState(false);
  const [calling, setCalling] = useState(false);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignLog[]>([]);
  const [recentCalls, setRecentCalls] = useState<VoiceCall[]>([]);
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
      
      // Load voice calls
      const response = await fetch(`${API_BASE}/voice-aws/calls?limit=100`);
      if (response.ok) {
        const data = await response.json();
        setRecentCalls(data.calls || []);
        
        // Group by campaign
        const campaignCalls = (data.calls || []).filter((c: any) => c.campaignId);
        const campaignMap = new Map<string, CampaignLog>();
        campaignCalls.forEach((c: any) => {
          const cid = c.campaignId;
          if (!campaignMap.has(cid)) {
            campaignMap.set(cid, {
              id: cid,
              name: c.campaignName || cid,
              recipients: 0,
              completed: 0,
              answered: 0,
              failed: 0,
              totalDuration: 0,
              createdAt: new Date(c.createdAt * 1000).toISOString()
            });
          }
          const camp = campaignMap.get(cid)!;
          camp.recipients++;
          if (c.status === 'completed' || c.status === 'answered') camp.completed++;
          if (c.status === 'answered') camp.answered++;
          if (c.status === 'failed' || c.status === 'no-answer') camp.failed++;
          camp.totalDuration += c.duration || 0;
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
    if (!messageText.trim()) { setMessage({ type: 'error', text: 'TTS message required' }); return; }
    if (selectedContacts.length === 0) { setMessage({ type: 'error', text: 'Select at least one contact' }); return; }

    setCalling(true);
    setMessage(null);

    try {
      const campaignId = `VC${Date.now()}`;
      let initiated = 0, failed = 0;

      for (const contactId of selectedContacts) {
        const contact = contacts.find(c => c.contactId === contactId);
        if (!contact?.phone) { failed++; continue; }

        try {
          const response = await fetch(`${API_BASE}/voice-aws/call`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              phoneNumber: contact.phone,
              contactId,
              callType: 'tts',
              messageText,
              voiceId,
              campaignId,
              campaignName
            })
          });
          if (response.ok) initiated++;
          else failed++;
        } catch (e) {
          failed++;
        }
        // Rate limit - 1 call per second
        await new Promise(r => setTimeout(r, 1000));
      }

      setMessage({ 
        type: initiated > 0 ? 'success' : 'error', 
        text: `Campaign started: ${initiated} calls initiated, ${failed} failed` 
      });
      setCampaignName('');
      setMessageText('');
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

  const [playingAudio, setPlayingAudio] = useState<string | null>(null);

  return (
    <div className="campaign-page">
      <div className="campaign-header">
        <h2>Voice Campaign (AWS)</h2>
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
              <input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My Voice Campaign" />
            </div>
            <div className="form-group">
              <label>Voice (Polly)</label>
              <select value={voiceId} onChange={e => setVoiceId(e.target.value)}>
                <option value="Joanna">Joanna (US Female)</option>
                <option value="Matthew">Matthew (US Male)</option>
                <option value="Amy">Amy (UK Female)</option>
                <option value="Brian">Brian (UK Male)</option>
                <option value="Aditi">Aditi (Indian English)</option>
                <option value="Raveena">Raveena (Indian English)</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>TTS Message *</label>
            <textarea value={messageText} onChange={e => setMessageText(e.target.value)} placeholder="Enter the message to be spoken..." rows={4} />
            <span className="hint">This message will be converted to speech using Amazon Polly</span>
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
            <button className="send-btn" onClick={handleStartCampaign} disabled={calling || selectedContacts.length === 0}>
              {calling ? `Calling...` : `Call ${selectedContacts.length} Contacts`}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="logs-section">
          <h3>Campaign Summary</h3>
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

          <h3 style={{ marginTop: 24 }}>Recent Calls</h3>
          <table className="logs-table">
            <thead>
              <tr>
                <th>Phone</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Recording</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {recentCalls.slice(0, 20).map(call => (
                <tr key={call.id}>
                  <td>{call.phoneNumber}</td>
                  <td><span className={`status-badge ${call.status}`}>{call.status}</span></td>
                  <td>{formatDuration(call.duration)}</td>
                  <td>
                    {call.recordingUrl ? (
                      <div className="audio-player">
                        <audio 
                          src={call.recordingUrl} 
                          controls 
                          style={{ height: 32, width: 200 }}
                          onPlay={() => setPlayingAudio(call.id)}
                          onPause={() => setPlayingAudio(null)}
                        />
                      </div>
                    ) : (
                      <span className="no-recording">-</span>
                    )}
                  </td>
                  <td>{new Date(call.createdAt * 1000).toLocaleString()}</td>
                </tr>
              ))}
              {recentCalls.length === 0 && (
                <tr><td colSpan={5} className="empty">No calls yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <style jsx>{`
        /* Uses global .campaign-page styles from inner-pages.css */
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
        .logs-section h3 { margin: 0 0 12px 0; font-size: 16px; }
        .logs-table { }
        .logs-table th, .logs-table td { }
        .logs-table th { }
        .logs-table .success { }
        .logs-table .error { }
        .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; }
        .status-badge.initiated { background: #dbeafe; color: #1d4ed8; }
        .status-badge.completed, .status-badge.answered { background: #D1FAE5; color: #065f46; }
        .status-badge.failed { background: #fef2f2; color: #dc2626; }
        .audio-player audio { border-radius: 4px; }
        .no-recording { color: #9ca3af; }
        .empty { }
        @media (max-width: 768px) { }
      `}</style>
    </div>
  );
};

export default VoiceCampaignPage;
