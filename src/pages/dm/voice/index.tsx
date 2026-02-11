/**
 * Voice Page - AWS Pinpoint Voice (us-east-1)
 * Consolidated: Make Calls, Campaign, Logs
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import { useToastContext } from '../../../contexts/ToastContext';
import { VoiceIcon } from '../../../lib/icons';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }
interface Contact { contactId: string; name: string; phone: string; }
interface VoiceCall {
  callId: string;
  contactId: string;
  contactName?: string;
  phoneNumber: string;
  direction: string;
  status: string;
  duration: number;
  callType: string;
  message?: string;
  campaignId?: string;
  campaignName?: string;
  createdAt: string;
}
interface Campaign {
  id: string;
  name: string;
  recipients: number;
  connected: number;
  completed: number;
  failed: number;
  createdAt: string;
}

const ITEMS_PER_PAGE = 25;
const VoicePage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<'logs' | 'campaign'>('logs');
  const [calls, setCalls] = useState<VoiceCall[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [directionFilter, setDirectionFilter] = useState<'all' | 'inbound' | 'outbound'>('all');
  
  const [showCallModal, setShowCallModal] = useState(false);
  const [callPhone, setCallPhone] = useState('');
  const [callMessage, setCallMessage] = useState('');
  const [calling, setCalling] = useState(false);
  
  const [showCampaignModal, setShowCampaignModal] = useState(false);
  const [campaignName, setCampaignName] = useState('');
  const [campaignMessage, setCampaignMessage] = useState('');
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [campaignSending, setCampaignSending] = useState(false);

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [showContactPicker, setShowContactPicker] = useState<'single' | 'campaign' | null>(null);
  const [contactSearch, setContactSearch] = useState('');
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [clearing, setClearing] = useState(false);
  
  const toast = useToastContext();

  const loadContacts = useCallback(async () => {
    setLoadingContacts(true);
    try {
      const data = await api.listContacts();
      setContacts(data.filter(c => c.phone).map(c => ({ contactId: c.contactId, name: c.name || c.phone || 'Unknown', phone: c.phone || '' })));
    } catch (err) { console.error('Load contacts error:', err); } finally { setLoadingContacts(false); }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [callsData, contactsData] = await Promise.all([api.listVoiceAwsCalls(), api.listContacts()]);
      const contactMap = new Map<string, api.Contact>();
      contactsData.forEach(c => contactMap.set(c.contactId, c));
      
      let formattedCalls: VoiceCall[];
      if (callsData.length > 0) {
        formattedCalls = callsData.map(c => ({
          callId: c.callId, contactId: c.contactId, contactName: contactMap.get(c.contactId)?.name,
          phoneNumber: c.phoneNumber || contactMap.get(c.contactId)?.phone || '', direction: c.direction || 'OUTBOUND',
          status: c.status || 'unknown', duration: c.duration || 0, callType: c.callType || 'tts',
          message: (c as any).messageText, campaignId: (c as any).campaignId, campaignName: (c as any).campaignName, createdAt: c.createdAt ? new Date(c.createdAt * 1000).toISOString() : new Date().toISOString()
        }));
      } else {
        const sharedCalls = await api.listVoiceCalls(undefined, 'aws');
        formattedCalls = sharedCalls.map(c => ({
          callId: c.callId, contactId: c.contactId, contactName: contactMap.get(c.contactId)?.name,
          phoneNumber: c.phoneNumber || contactMap.get(c.contactId)?.phone || '', direction: c.direction || 'OUTBOUND',
          status: c.status || 'unknown', duration: c.duration || 0, callType: c.callType || 'tts',
          message: '', campaignId: undefined, campaignName: undefined, createdAt: c.createdAt
        }));
      }
      formattedCalls.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      
      setCalls(formattedCalls);
      const campaignMap = new Map<string, Campaign>();
      formattedCalls.filter(c => c.campaignId).forEach(c => {
        const cid = c.campaignId!;
        if (!campaignMap.has(cid)) campaignMap.set(cid, { id: cid, name: c.campaignName || cid, recipients: 0, connected: 0, completed: 0, failed: 0, createdAt: c.createdAt });
        const camp = campaignMap.get(cid)!; camp.recipients++;
        if (c.status === 'connected' || c.status === 'completed') camp.connected++;
        if (c.status === 'completed') camp.completed++;
        if (c.status === 'failed') camp.failed++;
      });
      setCampaigns(Array.from(campaignMap.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
    } catch (err) { console.error('Load error:', err); toast.error('Failed to load data'); } finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { setPage(1); }, [activeTab, searchQuery, directionFilter]);
  useEffect(() => { if (showContactPicker) loadContacts(); }, [showContactPicker, loadContacts]);

  const filteredContacts = contacts.filter(c => c.name.toLowerCase().includes(contactSearch.toLowerCase()) || c.phone.includes(contactSearch));
  const selectContact = (contact: Contact) => {
    if (showContactPicker === 'single') { setCallPhone(contact.phone); setShowContactPicker(null); }
    else if (showContactPicker === 'campaign' && !selectedContacts.includes(contact.contactId)) setSelectedContacts(prev => [...prev, contact.contactId]);
    setContactSearch('');
  };
  const formatDuration = (seconds: number) => { if (!seconds) return '0:00'; const mins = Math.floor(seconds / 60); const secs = Math.round(seconds % 60); return `${mins}:${secs.toString().padStart(2, '0')}`; };

  const handleMakeCall = async () => {
    if (!callPhone) { toast.error('Phone number required'); return; }
    setCalling(true);
    try {
      const result = await api.makeVoiceAwsCall({ phoneNumber: callPhone, messageText: callMessage || 'Hello, this is a call from WECARE Digital.', callType: 'tts' });
      if (result && (result.callId || result.status)) { toast.success('Call initiated!'); setShowCallModal(false); setCallPhone(''); setCallMessage(''); await loadData(); }
      else toast.error('Failed to initiate call');
    } catch (err) { toast.error('Failed to make call'); } finally { setCalling(false); }
  };

  const handleSendCampaign = async () => {
    if (!campaignName.trim() || !campaignMessage.trim() || selectedContacts.length === 0) { toast.error('Campaign name, message, and contacts required'); return; }
    setCampaignSending(true);
    try {
      let sent = 0, failed = 0;
      for (const contactId of selectedContacts) {
        const contact = contacts.find(c => c.contactId === contactId);
        if (!contact?.phone) { failed++; continue; }
        try { const result = await api.makeVoiceAwsCall({ contactId, phoneNumber: contact.phone, messageText: campaignMessage, callType: 'tts' }); if (result && result.callId) sent++; else failed++; } catch { failed++; }
        if (sent % 5 === 0) await new Promise(r => setTimeout(r, 500));
      }
      toast.success(`Campaign initiated: ${sent} calls, ${failed} failed`);
      setShowCampaignModal(false); setCampaignName(''); setCampaignMessage(''); setSelectedContacts([]); await loadData();
    } catch (err) { toast.error('Campaign failed'); } finally { setCampaignSending(false); }
  };

  const handleClearLogs = async () => {
    if (!confirm('Clear all voice logs? This cannot be undone.')) return;
    setClearing(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital'}/voice-aws/clear-logs`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' }
      });
      const result = await response.json();
      if (result.success) { toast.success(`Cleared ${result.deletedCount || 0} logs`); await loadData(); }
      else toast.error(result.error || 'Failed to clear logs');
    } catch (err) { toast.error('Failed to clear logs'); } finally { setClearing(false); }
  };
  const filteredCalls = calls.filter(call => {
    if (directionFilter === 'inbound' && call.direction !== 'INBOUND') return false;
    if (directionFilter === 'outbound' && call.direction !== 'OUTBOUND') return false;
    if (searchQuery) { const q = searchQuery.toLowerCase(); return call.contactName?.toLowerCase().includes(q) || call.phoneNumber?.includes(q) || call.status?.toLowerCase().includes(q); }
    return true;
  });
  const totalPages = Math.ceil(filteredCalls.length / ITEMS_PER_PAGE);
  const paginatedCalls = filteredCalls.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);
  const inboundCount = calls.filter(c => c.direction === 'INBOUND').length;
  const outboundCount = calls.filter(c => c.direction === 'OUTBOUND').length;
  const tabItems: TabItem[] = [{ id: 'logs', label: `Logs (${calls.length})` }, { id: 'campaign', label: `Campaigns (${campaigns.length})` }];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice | AWS Pinpoint | WECARE.DIGITAL" description="Voice calls via AWS Pinpoint" />
      <div className="voice-page">
        <div className="page-header">
          <div className="header-title"><VoiceIcon size={22} color="#065f46" /><h2>Voice</h2><span className="badge">AWS Pinpoint</span><span className="badge region">us-east-1</span></div>
          <div className="header-actions">
            <Button variant="primary" onClick={() => setShowCallModal(true)}>Make Call</Button>
            <Button variant="secondary" onClick={() => { setShowCampaignModal(true); loadContacts(); }}>Campaign</Button>
            <Button variant="secondary" onClick={handleClearLogs} disabled={clearing} loading={clearing}>Clear</Button>
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>
        <div className="tabs-row"><Tabs items={tabItems} activeTab={activeTab} onChange={(id) => setActiveTab(id as 'logs' | 'campaign')} /></div>
        {activeTab === 'logs' && (<>
          <div className="controls-row">
            <div className="filter-tabs">
              <button className={directionFilter === 'all' ? 'active' : ''} onClick={() => setDirectionFilter('all')}>All ({calls.length})</button>
              <button className={directionFilter === 'inbound' ? 'active' : ''} onClick={() => setDirectionFilter('inbound')}> In ({inboundCount})</button>
              <button className={directionFilter === 'outbound' ? 'active' : ''} onClick={() => setDirectionFilter('outbound')}> Out ({outboundCount})</button>
            </div>
            <input type="text" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="search-input" />
            <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
          </div>
          <div className="content-area">{loading ? <div className="loading-state">Loading...</div> : (
            <div className="table-container"><table><thead><tr><th>Time</th><th>Direction</th><th>Contact</th><th>Phone</th><th>Duration</th><th>Type</th><th>Status</th></tr></thead><tbody>
              {paginatedCalls.map(call => (<tr key={call.callId}><td className="time-cell">{new Date(call.createdAt).toLocaleString()}</td><td><span className={call.direction === 'INBOUND' ? 'badge-in' : 'badge-out'}>{call.direction === 'INBOUND' ? ' In' : ' Out'}</span></td><td>{call.contactName || '-'}</td><td className="phone-cell">{call.phoneNumber}</td><td>{formatDuration(call.duration)}</td><td><span className="type-badge">{call.callType}</span></td><td><span className={`status-badge ${call.status?.toLowerCase()}`}>{call.status}</span></td></tr>))}
              {paginatedCalls.length === 0 && <tr><td colSpan={7} className="empty-state">No calls</td></tr>}
            </tbody></table></div>
          )}</div>
        </>)}
        {activeTab === 'campaign' && (<div className="content-area"><div className="table-container"><table><thead><tr><th>Campaign</th><th>Recipients</th><th>Connected</th><th>Completed</th><th>Failed</th><th>Date</th></tr></thead><tbody>
          {campaigns.map(c => (<tr key={c.id}><td className="name-cell">{c.name}</td><td>{c.recipients}</td><td className="success-cell">{c.connected}</td><td>{c.completed}</td><td className="failed-cell">{c.failed}</td><td className="time-cell">{new Date(c.createdAt).toLocaleDateString()}</td></tr>))}
          {campaigns.length === 0 && <tr><td colSpan={6} className="empty-state">No campaigns yet</td></tr>}
        </tbody></table></div></div>)}
      </div>

      {showCallModal && (<div className="modal-overlay" onClick={() => setShowCallModal(false)}><div className="modal-content" onClick={e => e.stopPropagation()}>
        <h3>Make Voice Call</h3>
        <div className="form-group"><label>Phone Number *</label><div className="input-with-btn"><input type="tel" value={callPhone} onChange={e => setCallPhone(e.target.value)} placeholder="+1234567890" /><button type="button" className="fetch-btn" onClick={() => setShowContactPicker('single')}>Contacts</button></div></div>
        <div className="form-group"><label>Message (Text-to-Speech)</label><textarea value={callMessage} onChange={e => setCallMessage(e.target.value)} placeholder="Enter message to be spoken..." rows={3} /></div>
        <div className="info-box"><strong>AWS Pinpoint Voice:</strong> Region us-east-1 | TTS via Polly</div>
        <div className="modal-actions"><Button variant="secondary" onClick={() => setShowCallModal(false)}>Cancel</Button><Button variant="primary" onClick={handleMakeCall} loading={calling} disabled={!callPhone}>Call</Button></div>
      </div></div>)}

      {showCampaignModal && (<div className="modal-overlay" onClick={() => setShowCampaignModal(false)}><div className="modal-content campaign-modal" onClick={e => e.stopPropagation()}>
        <h3>Create Voice Campaign</h3>
        <div className="form-group"><label>Campaign Name *</label><input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My Campaign" /></div>
        <div className="form-group"><label>Voice Message (TTS) *</label><textarea value={campaignMessage} onChange={e => setCampaignMessage(e.target.value)} placeholder="Enter message to be spoken..." rows={3} /></div>
        <div className="form-group"><label>Recipients ({selectedContacts.length} selected)</label><button type="button" className="fetch-btn full-width" onClick={() => setShowContactPicker('campaign')}>Select Contacts</button>
          {selectedContacts.length > 0 && (<div className="selected-contacts">{selectedContacts.map(id => { const c = contacts.find(x => x.contactId === id); return c ? <span key={id} className="contact-tag">{c.name} <button onClick={() => setSelectedContacts(prev => prev.filter(x => x !== id))}></button></span> : null; })}</div>)}
        </div>
        <div className="modal-actions"><Button variant="secondary" onClick={() => setShowCampaignModal(false)}>Cancel</Button><Button variant="primary" onClick={handleSendCampaign} loading={campaignSending} disabled={!campaignName || !campaignMessage || selectedContacts.length === 0}>Call {selectedContacts.length} Contacts</Button></div>
      </div></div>)}
      {showContactPicker && (<div className="modal-overlay" onClick={() => setShowContactPicker(null)}><div className="modal-content contact-picker" onClick={e => e.stopPropagation()}>
        <h3>Select Contact{showContactPicker === 'campaign' ? 's' : ''}</h3>
        <input type="text" placeholder="Search..." value={contactSearch} onChange={e => setContactSearch(e.target.value)} className="contact-search" />
        <div className="contact-list">{loadingContacts ? <div className="loading-contacts">Loading...</div> : filteredContacts.length === 0 ? <div className="no-contacts">No contacts</div> : (
          filteredContacts.slice(0, 50).map(contact => (<div key={contact.contactId} className={`contact-row ${selectedContacts.includes(contact.contactId) ? 'selected' : ''}`} onClick={() => selectContact(contact)}><div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div><div className="contact-details"><div className="contact-name">{contact.name}</div><div className="contact-phone">{contact.phone}</div></div>{showContactPicker === 'campaign' && selectedContacts.includes(contact.contactId) && <span className="check"></span>}</div>))
        )}</div>
        <div className="modal-actions"><Button variant="secondary" onClick={() => setShowContactPicker(null)}>{showContactPicker === 'campaign' ? 'Done' : 'Cancel'}</Button></div>
      </div></div>)}

      <style jsx>{`
        .voice-page { height: 100%; display: flex; flex-direction: column; background: #f0fdf4; padding: 16px; box-sizing: border-box; overflow: hidden; }
        .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
        .header-title { display: flex; align-items: center; gap: 10px; color: #065f46; flex-wrap: wrap; }
        .header-title h2 { margin: 0; font-size: 1.1rem; }
        .badge { background: #10b981; color: #fff; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 500; }
        .badge.region { background: #059669; }
        .header-actions { display: flex; gap: 6px; flex-wrap: wrap; }
        .tabs-row { background: #fff; border-radius: 8px; padding: 0 12px; margin-bottom: 12px; border: 1px solid #d1fae5; flex-shrink: 0; }
        .controls-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; flex-shrink: 0; }
        .filter-tabs { display: flex; gap: 6px; }
        .filter-tabs button { padding: 6px 12px; border: 1px solid #d1fae5; background: #fff; border-radius: 6px; cursor: pointer; font-size: 12px; }
        .filter-tabs button.active { background: #10b981; color: #fff; border-color: #10b981; }
        .search-input { padding: 8px 12px; border: 1px solid #a7f3d0; border-radius: 8px; width: 200px; font-size: 13px; }
        .search-input:focus { outline: none; border-color: #10b981; }
        .content-area { flex: 1; background: #fff; border-radius: 12px; border: 1px solid #d1fae5; overflow: auto; min-height: 0; }
        .loading-state { padding: 40px; text-align: center; color: #047857; }
        .table-container { min-width: 100%; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #ecfdf5; font-size: 12px; white-space: nowrap; }
        th { background: #ecfdf5; font-weight: 600; color: #065f46; position: sticky; top: 0; z-index: 1; }
        tr:hover { background: #f0fdf4; }
        .time-cell { font-size: 11px; color: #64748b; }
        .phone-cell { font-family: monospace; color: #047857; font-size: 11px; }
        .name-cell { font-weight: 500; color: #065f46; }
        .success-cell { color: #059669; font-weight: 500; }
        .failed-cell { color: #dc2626; font-weight: 500; }
        .badge-in { background: #10b981; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
        .badge-out { background: #64748b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
        .type-badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; background: #ecfdf5; color: #065f46; }
        .status-badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; background: #f1f5f9; color: #64748b; }
        .status-badge.connected, .status-badge.completed { background: #d1fae5; color: #059669; }
        .status-badge.initiated, .status-badge.sent { background: #dbeafe; color: #1d4ed8; }
        .status-badge.pending { background: #fef3c7; color: #92400e; }
        .status-badge.failed { background: #fee2e2; color: #dc2626; }
        .empty-state { text-align: center; color: #64748b; padding: 30px !important; }
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 16px; }
        .modal-content { background: #fff; border-radius: 12px; padding: 20px; width: 100%; max-width: 420px; max-height: 90vh; overflow-y: auto; }
        .modal-content.campaign-modal { max-width: 480px; }
        .modal-content h3 { margin: 0 0 16px 0; color: #065f46; }
        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; font-size: 12px; font-weight: 500; margin-bottom: 5px; color: #374151; }
        .form-group input, .form-group textarea { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; font-family: inherit; box-sizing: border-box; }
        .form-group input:focus, .form-group textarea:focus { outline: none; border-color: #10b981; }
        .input-with-btn { display: flex; gap: 6px; }
        .input-with-btn input { flex: 1; }
        .fetch-btn { padding: 8px 12px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; color: #065f46; font-size: 12px; cursor: pointer; }
        .fetch-btn:hover { background: #d1fae5; }
        .fetch-btn.full-width { width: 100%; }
        .info-box { background: #ecfdf5; border: 1px solid #d1fae5; border-radius: 8px; padding: 10px; margin-bottom: 14px; font-size: 12px; color: #065f46; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
        .selected-contacts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
        .contact-tag { display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: #ecfdf5; border-radius: 4px; font-size: 11px; color: #065f46; }
        .contact-tag button { background: none; border: none; color: #10b981; cursor: pointer; font-size: 14px; padding: 0; }
        .contact-picker { max-width: 360px; }
        .contact-search { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; margin-bottom: 10px; box-sizing: border-box; }
        .contact-list { max-height: 280px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
        .contact-row { display: flex; align-items: center; gap: 10px; padding: 8px 10px; cursor: pointer; border-bottom: 1px solid #f3f4f6; }
        .contact-row:hover { background: #f0fdf4; }
        .contact-row.selected { background: #ecfdf5; }
        .contact-avatar { width: 32px; height: 32px; background: #10b981; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; font-size: 13px; }
        .contact-details { flex: 1; }
        .contact-name { font-size: 13px; font-weight: 500; color: #065f46; }
        .contact-phone { font-size: 11px; color: #64748b; font-family: monospace; }
        .check { color: #059669; font-weight: bold; }
        .loading-contacts, .no-contacts { padding: 20px; text-align: center; color: #64748b; }
      `}</style>
    </Layout>
  );
};

export default VoicePage;