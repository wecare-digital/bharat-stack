/**
 * SMS Page - AWS Pinpoint SMS: Send, Logs, Campaigns
 * Theme: Emerald green (site theme)
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import { useToastContext } from '../../../contexts/ToastContext';
import { SmsIcon } from '../../../lib/icons';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }
interface Contact { contactId: string; name: string; phone: string; }
interface SmsMessage { 
  messageId: string; contactId: string; contactName?: string; phone: string; 
  content: string; status: string; direction: string; messageType?: string;
  campaignId?: string; campaignName?: string; timestamp: string; 
}
interface Campaign { id: string; name: string; recipients: number; sent: number; delivered: number; failed: number; createdAt: string; }

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';
const ITEMS_PER_PAGE = 25;

const SmsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<'logs' | 'campaign'>('logs');
  const [messages, setMessages] = useState<SmsMessage[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [directionFilter, setDirectionFilter] = useState<'all' | 'inbound' | 'outbound'>('all');
  const [showSendModal, setShowSendModal] = useState(false);
  const [sendPhone, setSendPhone] = useState('');
  const [sendContent, setSendContent] = useState('');
  const [sendMessageType, setSendMessageType] = useState('PROMOTIONAL');
  const [sending, setSending] = useState(false);
  const [showCampaignModal, setShowCampaignModal] = useState(false);
  const [campaignName, setCampaignName] = useState('');
  const [campaignContent, setCampaignContent] = useState('');
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [campaignSending, setCampaignSending] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [showContactPicker, setShowContactPicker] = useState<'single' | 'campaign' | null>(null);
  const [contactSearch, setContactSearch] = useState('');
  const [loadingContacts, setLoadingContacts] = useState(false);
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
      const [messagesData, contactsData] = await Promise.all([api.listSmsAwsMessages(), api.listContacts()]);
      const contactMap = new Map<string, api.Contact>();
      contactsData.forEach(c => contactMap.set(c.contactId, c));
      const formatted: SmsMessage[] = messagesData.map(m => ({
        messageId: m.messageId, contactId: m.contactId, contactName: contactMap.get(m.contactId)?.name,
        phone: m.phoneNumber || contactMap.get(m.contactId)?.phone || '', content: m.content || '', status: m.status || 'unknown',
        direction: m.direction || 'OUTBOUND', messageType: m.messageType, campaignId: (m as any).campaignId,
        campaignName: (m as any).campaignName, timestamp: new Date(m.createdAt * 1000).toISOString()
      })).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      setMessages(formatted);
      const campaignMap = new Map<string, Campaign>();
      formatted.filter(m => m.campaignId).forEach(m => {
        const cid = m.campaignId!;
        if (!campaignMap.has(cid)) campaignMap.set(cid, { id: cid, name: m.campaignName || cid, recipients: 0, sent: 0, delivered: 0, failed: 0, createdAt: m.timestamp });
        const c = campaignMap.get(cid)!; c.recipients++;
        if (m.status === 'sent' || m.status === 'delivered') c.sent++;
        if (m.status === 'delivered') c.delivered++;
        if (m.status === 'failed') c.failed++;
      });
      setCampaigns(Array.from(campaignMap.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
    } catch (err) { console.error('Load error:', err); toast.error('Failed to load data'); } finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { setPage(1); }, [activeTab, searchQuery, directionFilter]);
  useEffect(() => { if (showContactPicker) loadContacts(); }, [showContactPicker, loadContacts]);

  const filteredContacts = contacts.filter(c => c.name.toLowerCase().includes(contactSearch.toLowerCase()) || c.phone.includes(contactSearch));
  const selectContact = (contact: Contact) => {
    if (showContactPicker === 'single') { setSendPhone(contact.phone); setShowContactPicker(null); }
    else if (showContactPicker === 'campaign' && !selectedContacts.includes(contact.contactId)) setSelectedContacts(prev => [...prev, contact.contactId]);
    setContactSearch('');
  };

  const handleSendSms = async () => {
    if (!sendPhone) { toast.error('Phone number required'); return; }
    if (!sendContent) { toast.error('Message required'); return; }
    setSending(true);
    try {
      const response = await fetch(`${API_BASE}/sms-aws/send`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phoneNumber: sendPhone, content: sendContent, messageType: sendMessageType }) });
      const result = await response.json();
      if (result.messageId || result.success) { toast.success('SMS sent!'); setShowSendModal(false); setSendPhone(''); setSendContent(''); await loadData(); }
      else toast.error(result.error || 'Failed to send SMS');
    } catch (err) { toast.error('Failed to send SMS'); } finally { setSending(false); }
  };

  const handleSendCampaign = async () => {
    if (!campaignName.trim() || !campaignContent.trim() || selectedContacts.length === 0) { toast.error('Campaign name, message, and contacts required'); return; }
    setCampaignSending(true);
    try {
      const campaignId = 'SC' + Date.now(); let sent = 0, failed = 0;
      for (const contactId of selectedContacts) {
        const contact = contacts.find(c => c.contactId === contactId);
        if (!contact?.phone) { failed++; continue; }
        try { const response = await fetch(`${API_BASE}/sms-aws/send`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ contactId, phoneNumber: contact.phone, content: campaignContent, messageType: 'PROMOTIONAL', campaignId, campaignName }) }); if (response.ok) sent++; else failed++; } catch { failed++; }
        if (sent % 10 === 0) await new Promise(r => setTimeout(r, 200));
      }
      toast.success(`Campaign sent: ${sent} success, ${failed} failed`);
      setShowCampaignModal(false); setCampaignName(''); setCampaignContent(''); setSelectedContacts([]); await loadData();
    } catch (err) { toast.error('Campaign failed'); } finally { setCampaignSending(false); }
  };

  const filteredMessages = messages.filter(msg => {
    if (directionFilter === 'inbound' && msg.direction !== 'INBOUND') return false;
    if (directionFilter === 'outbound' && msg.direction !== 'OUTBOUND') return false;
    if (searchQuery) { const q = searchQuery.toLowerCase(); return msg.contactName?.toLowerCase().includes(q) || msg.phone?.includes(q) || msg.content?.toLowerCase().includes(q); }
    return true;
  });
  const totalPages = Math.ceil(filteredMessages.length / ITEMS_PER_PAGE);
  const paginatedMessages = filteredMessages.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);
  const inboundCount = messages.filter(m => m.direction === 'INBOUND').length;
  const outboundCount = messages.filter(m => m.direction === 'OUTBOUND').length;
  const tabItems: TabItem[] = [{ id: 'logs', label: `Logs (${messages.length})` }, { id: 'campaign', label: `Campaigns (${campaigns.length})` }];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS | AWS Pinpoint | WECARE.DIGITAL" description="SMS via AWS Pinpoint" />
      <div className="sms-page">
        <div className="page-header">
          <div className="header-title"><SmsIcon size={22} color="#065f46" /><h2>SMS</h2><span className="badge">AWS Pinpoint</span><span className="badge region">us-east-1</span></div>
          <div className="header-actions">
            <Button variant="primary" onClick={() => setShowSendModal(true)}>Send SMS</Button>
            <Button variant="secondary" onClick={() => { setShowCampaignModal(true); loadContacts(); }}>Campaign</Button>
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>
        <div className="tabs-row"><Tabs items={tabItems} activeTab={activeTab} onChange={(id) => setActiveTab(id as 'logs' | 'campaign')} /></div>
        {activeTab === 'logs' && (<>
          <div className="controls-row">
            <div className="filter-tabs">
              <button className={directionFilter === 'all' ? 'active' : ''} onClick={() => setDirectionFilter('all')}>All ({messages.length})</button>
              <button className={directionFilter === 'inbound' ? 'active' : ''} onClick={() => setDirectionFilter('inbound')}>↙ In ({inboundCount})</button>
              <button className={directionFilter === 'outbound' ? 'active' : ''} onClick={() => setDirectionFilter('outbound')}>↗ Out ({outboundCount})</button>
            </div>
            <input type="text" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="search-input" />
            <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
          </div>
          <div className="content-area">{loading ? <div className="loading-state">Loading...</div> : (
            <div className="table-container"><table><thead><tr><th>Time</th><th>Direction</th><th>Contact</th><th>Phone</th><th>Message</th><th>Status</th></tr></thead><tbody>
              {paginatedMessages.map(msg => (<tr key={msg.messageId}><td className="time-cell">{new Date(msg.timestamp).toLocaleString()}</td><td><span className={msg.direction === 'INBOUND' ? 'badge-in' : 'badge-out'}>{msg.direction === 'INBOUND' ? '↙ In' : '↗ Out'}</span></td><td>{msg.contactName || '-'}</td><td className="phone-cell">{msg.phone}</td><td className="content-cell" title={msg.content}>{msg.content?.substring(0, 40)}{msg.content?.length > 40 ? '...' : ''}</td><td><span className={`status-badge ${msg.status?.toLowerCase()}`}>{msg.status}</span></td></tr>))}
              {paginatedMessages.length === 0 && <tr><td colSpan={6} className="empty-state">No messages</td></tr>}
            </tbody></table></div>
          )}</div>
        </>)}
        {activeTab === 'campaign' && (<div className="content-area"><div className="table-container"><table><thead><tr><th>Campaign</th><th>Recipients</th><th>Sent</th><th>Delivered</th><th>Failed</th><th>Date</th></tr></thead><tbody>
          {campaigns.map(c => (<tr key={c.id}><td className="name-cell">{c.name}</td><td>{c.recipients}</td><td className="success-cell">{c.sent}</td><td>{c.delivered}</td><td className="failed-cell">{c.failed}</td><td className="time-cell">{new Date(c.createdAt).toLocaleDateString()}</td></tr>))}
          {campaigns.length === 0 && <tr><td colSpan={6} className="empty-state">No campaigns yet</td></tr>}
        </tbody></table></div></div>)}
      </div>

      {showSendModal && (<div className="modal-overlay" onClick={() => setShowSendModal(false)}><div className="modal-content" onClick={e => e.stopPropagation()}>
        <h3>Send SMS</h3>
        <div className="form-group"><label>Phone Number *</label><div className="input-with-btn"><input type="tel" value={sendPhone} onChange={e => setSendPhone(e.target.value)} placeholder="+1234567890" /><button type="button" className="fetch-btn" onClick={() => setShowContactPicker('single')}>Contacts</button></div></div>
        <div className="form-group"><label>Message *</label><textarea value={sendContent} onChange={e => setSendContent(e.target.value)} placeholder="Enter message..." rows={3} /></div>
        <div className="form-group"><label>Type</label><select value={sendMessageType} onChange={e => setSendMessageType(e.target.value)}><option value="PROMOTIONAL">Promotional</option><option value="TRANSACTIONAL">Transactional</option></select></div>
        <div className="info-box"><strong>AWS Pinpoint:</strong> Region us-east-1</div>
        <div className="modal-actions"><Button variant="secondary" onClick={() => setShowSendModal(false)}>Cancel</Button><Button variant="primary" onClick={handleSendSms} loading={sending} disabled={!sendPhone || !sendContent}>Send</Button></div>
      </div></div>)}

      {showCampaignModal && (<div className="modal-overlay" onClick={() => setShowCampaignModal(false)}><div className="modal-content campaign-modal" onClick={e => e.stopPropagation()}>
        <h3>Create SMS Campaign</h3>
        <div className="form-group"><label>Campaign Name *</label><input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My Campaign" /></div>
        <div className="form-group"><label>Message *</label><textarea value={campaignContent} onChange={e => setCampaignContent(e.target.value)} placeholder="Enter message..." rows={3} /></div>
        <div className="form-group"><label>Recipients ({selectedContacts.length} selected)</label><button type="button" className="fetch-btn full-width" onClick={() => setShowContactPicker('campaign')}>Select Contacts</button>
          {selectedContacts.length > 0 && (<div className="selected-contacts">{selectedContacts.map(id => { const c = contacts.find(x => x.contactId === id); return c ? <span key={id} className="contact-tag">{c.name} <button onClick={() => setSelectedContacts(prev => prev.filter(x => x !== id))}>×</button></span> : null; })}</div>)}
        </div>
        <div className="modal-actions"><Button variant="secondary" onClick={() => setShowCampaignModal(false)}>Cancel</Button><Button variant="primary" onClick={handleSendCampaign} loading={campaignSending} disabled={!campaignName || !campaignContent || selectedContacts.length === 0}>Send to {selectedContacts.length}</Button></div>
      </div></div>)}

      {showContactPicker && (<div className="modal-overlay" onClick={() => setShowContactPicker(null)}><div className="modal-content contact-picker" onClick={e => e.stopPropagation()}>
        <h3>Select Contact{showContactPicker === 'campaign' ? 's' : ''}</h3>
        <input type="text" placeholder="Search..." value={contactSearch} onChange={e => setContactSearch(e.target.value)} className="contact-search" />
        <div className="contact-list">{loadingContacts ? <div className="loading-contacts">Loading...</div> : filteredContacts.length === 0 ? <div className="no-contacts">No contacts</div> : (
          filteredContacts.slice(0, 50).map(contact => (<div key={contact.contactId} className={`contact-row ${selectedContacts.includes(contact.contactId) ? 'selected' : ''}`} onClick={() => selectContact(contact)}><div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div><div className="contact-details"><div className="contact-name">{contact.name}</div><div className="contact-phone">{contact.phone}</div></div>{showContactPicker === 'campaign' && selectedContacts.includes(contact.contactId) && <span className="check">✓</span>}</div>))
        )}</div>
        <div className="modal-actions"><Button variant="secondary" onClick={() => setShowContactPicker(null)}>{showContactPicker === 'campaign' ? 'Done' : 'Cancel'}</Button></div>
      </div></div>)}

      <style jsx>{`
        .sms-page { height: 100%; display: flex; flex-direction: column; background: #f0fdf4; padding: 16px; box-sizing: border-box; overflow: hidden; }
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
        .content-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
        .name-cell { font-weight: 500; color: #065f46; }
        .success-cell { color: #059669; font-weight: 500; }
        .failed-cell { color: #dc2626; font-weight: 500; }
        .badge-in { background: #10b981; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
        .badge-out { background: #64748b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
        .status-badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; background: #f1f5f9; color: #64748b; }
        .status-badge.sent, .status-badge.delivered { background: #d1fae5; color: #059669; }
        .status-badge.failed { background: #fee2e2; color: #dc2626; }
        .empty-state { text-align: center; color: #64748b; padding: 30px !important; }
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 16px; }
        .modal-content { background: #fff; border-radius: 12px; padding: 20px; width: 100%; max-width: 420px; max-height: 90vh; overflow-y: auto; }
        .modal-content.campaign-modal { max-width: 480px; }
        .modal-content h3 { margin: 0 0 16px 0; color: #065f46; }
        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; font-size: 12px; font-weight: 500; margin-bottom: 5px; color: #374151; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; font-family: inherit; box-sizing: border-box; }
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus { outline: none; border-color: #10b981; }
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

export default SmsPage;
