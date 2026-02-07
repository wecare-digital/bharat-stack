/**
 * SMS-IN Inbox Page - Airtel IQ SMS Integration
 * Send SMS and view SMS logs via Airtel IQ Messaging API
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }
interface Contact { contactId: string; name: string; phone: string; }
interface SmsMessage { 
  messageId: string; 
  phoneNumber: string; 
  content: string; 
  status: string; 
  messageType?: string; 
  senderId?: string;
  dltTemplateId?: string;
  createdAt: number; 
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';
const ITEMS_PER_PAGE = 20;

const SmsInInbox: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<'all' | 'single' | 'bulk'>('all');
  const [messages, setMessages] = useState<SmsMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Send SMS Modal state
  const [showSendModal, setShowSendModal] = useState(false);
  const [sendPhone, setSendPhone] = useState('');
  const [sendContent, setSendContent] = useState('');
  const [sendMessageType, setSendMessageType] = useState('SERVICE_EXPLICIT');
  const [sendDltTemplateId, setSendDltTemplateId] = useState('1007974344269130859');
  const [sending, setSending] = useState(false);
  
  // Bulk SMS Modal state
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkNumbers, setBulkNumbers] = useState('');
  const [bulkContent, setBulkContent] = useState('');
  const [bulkMessageType, setBulkMessageType] = useState('SERVICE_EXPLICIT');
  const [bulkDltTemplateId, setBulkDltTemplateId] = useState('1007974344269130859');
  const [bulkSending, setBulkSending] = useState(false);
  
  // Contacts state
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [showContactPicker, setShowContactPicker] = useState<'single' | 'bulk' | null>(null);
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
      const response = await fetch(`${API_BASE}/sms-in/airtel`).then(r => r.json()).catch(() => ({ messages: [] }));
      setMessages(response.messages || []);
    } catch (err) { 
      console.error('Load error:', err); 
      toast.error('Failed to load data'); 
    } finally { 
      setLoading(false); 
    }
  }, [toast]);

  useEffect(() => { loadData(); const interval = setInterval(loadData, 60000); return () => clearInterval(interval); }, [loadData]);
  useEffect(() => { setPage(1); }, [activeTab, searchQuery]);
  useEffect(() => { if (showContactPicker) loadContacts(); }, [showContactPicker, loadContacts]);

  const filteredContacts = contacts.filter(c => 
    c.name.toLowerCase().includes(contactSearch.toLowerCase()) || 
    c.phone.includes(contactSearch)
  );

  const selectContact = (contact: Contact) => {
    if (showContactPicker === 'single') setSendPhone(contact.phone);
    else if (showContactPicker === 'bulk') {
      const current = bulkNumbers.trim();
      setBulkNumbers(current ? `${current}\n${contact.phone}` : contact.phone);
    }
    setShowContactPicker(null);
    setContactSearch('');
  };

  const handleSendSms = async () => {
    if (!sendPhone || !sendContent) { toast.error('Phone number and message are required'); return; }
    setSending(true);
    try {
      const response = await fetch(`${API_BASE}/sms-in/airtel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phoneNumber: sendPhone, content: sendContent, messageType: sendMessageType, dltTemplateId: sendDltTemplateId })
      });
      const result = await response.json();
      if (result.messageId) {
        toast.success('SMS sent successfully!');
        setShowSendModal(false);
        setSendPhone('');
        setSendContent('');
        await loadData();
      } else {
        toast.error(result.error || 'Failed to send SMS');
      }
    } catch (err) { toast.error('Failed to send SMS'); } finally { setSending(false); }
  };

  const handleBulkSms = async () => {
    if (!bulkNumbers || !bulkContent) { toast.error('Phone numbers and message are required'); return; }
    setBulkSending(true);
    try {
      const numbers = bulkNumbers.split(/[\n,]/).map(n => n.trim()).filter(n => n.length >= 10);
      const response = await fetch(`${API_BASE}/sms-in/airtel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phoneNumbers: numbers, content: bulkContent, messageType: bulkMessageType, dltTemplateId: bulkDltTemplateId, bulk: true })
      });
      const result = await response.json();
      if (result.success || result.messageIds) {
        toast.success(`Bulk SMS sent to ${numbers.length} numbers!`);
        setShowBulkModal(false);
        setBulkNumbers('');
        setBulkContent('');
        await loadData();
      } else {
        toast.error(result.error || 'Failed to send bulk SMS');
      }
    } catch (err) { toast.error('Failed to send bulk SMS'); } finally { setBulkSending(false); }
  };

  // Filter messages
  const filteredMessages = messages.filter(msg => {
    if (activeTab === 'single' && msg.messageType === 'BULK') return false;
    if (activeTab === 'bulk' && msg.messageType !== 'BULK') return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return msg.phoneNumber?.toLowerCase().includes(q) || msg.content?.toLowerCase().includes(q) || msg.status?.toLowerCase().includes(q);
    }
    return true;
  });

  const totalPages = Math.ceil(filteredMessages.length / ITEMS_PER_PAGE);
  const paginatedMessages = filteredMessages.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const singleCount = messages.filter(m => m.messageType !== 'BULK').length;
  const bulkCount = messages.filter(m => m.messageType === 'BULK').length;

  const tabItems: TabItem[] = [
    { id: 'all', label: `All SMS (${messages.length})` },
    { id: 'single', label: `Single (${singleCount})` },
    { id: 'bulk', label: `Bulk (${bulkCount})` }
  ];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS-IN | Airtel IQ | WECARE.DIGITAL" description="Outbound SMS via Airtel IQ Messaging API" />
      <div className="sms-page">
        <div className="page-header">
          <div className="header-title">
            <SmsIcon />
            <h2>SMS IN</h2>
            <span className="badge">Outbound Only</span>
            <span className="badge dlt">DLT Compliant</span>
          </div>
          <div className="header-actions">
            <Button variant="primary" onClick={() => setShowSendModal(true)}>+ Send SMS</Button>
            <Button variant="secondary" onClick={() => setShowBulkModal(true)}>+ Bulk SMS</Button>
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>

        <div className="tabs-row">
          <Tabs items={tabItems} activeTab={activeTab} onChange={(id) => setActiveTab(id as 'all' | 'single' | 'bulk')} />
        </div>

        <div className="controls-row">
          <input type="text" placeholder="Search by phone, content, status..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="search-input" />
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
        </div>

        <div className="content-area">
          {loading ? (
            <div className="loading-state">Loading...</div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Phone Number</th>
                    <th>Message</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Sender ID</th>
                    <th>DLT Template</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedMessages.map(msg => (
                    <tr key={msg.messageId}>
                      <td>{new Date(msg.createdAt * 1000).toLocaleString()}</td>
                      <td className="phone-cell">{msg.phoneNumber}</td>
                      <td className="content-cell" title={msg.content}>{msg.content?.substring(0, 50)}{msg.content?.length > 50 ? '...' : ''}</td>
                      <td><span className="type-badge">{msg.messageType || 'SERVICE'}</span></td>
                      <td><span className={`status-badge ${msg.status?.toLowerCase()}`}>{msg.status}</span></td>
                      <td>{msg.senderId || 'WDBEEP'}</td>
                      <td className="id-cell">{msg.dltTemplateId?.slice(0, 10)}...</td>
                    </tr>
                  ))}
                  {paginatedMessages.length === 0 && (
                    <tr><td colSpan={7} className="empty-state">No SMS messages yet. Click "+ Send SMS" to send your first message.</td></tr>
                  )}
                </tbody>
              </table>
              <div className="api-info">
                <strong>Airtel IQ SMS API Endpoint:</strong>
                <code>{API_BASE}/sms-in/airtel</code>
                <div className="dlt-info">
                  <span>Sender ID: <strong>WDBEEP</strong></span>
                  <span>Entity ID: <strong>1201161991108627443</strong></span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Send SMS Modal */}
      {showSendModal && (
        <div className="modal-overlay" onClick={() => setShowSendModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Send SMS via Airtel IQ</h3>
            <div className="form-group">
              <label>Phone Number *</label>
              <div className="input-with-btn">
                <input type="tel" value={sendPhone} onChange={e => setSendPhone(e.target.value)} placeholder="10-digit mobile number" />
                <button type="button" className="fetch-btn" onClick={() => setShowContactPicker('single')}>📇 Contacts</button>
              </div>
            </div>
            <div className="form-group"><label>Message *</label><textarea value={sendContent} onChange={e => setSendContent(e.target.value)} placeholder="Enter your message..." rows={4} /><small>{sendContent.length} characters</small></div>
            <div className="form-row">
              <div className="form-group">
                <label>Message Type</label>
                <select value={sendMessageType} onChange={e => setSendMessageType(e.target.value)}>
                  <option value="SERVICE_EXPLICIT">SERVICE_EXPLICIT</option>
                  <option value="SERVICE_IMPLICIT">SERVICE_IMPLICIT</option>
                  <option value="TRANSACTIONAL">TRANSACTIONAL</option>
                  <option value="PROMOTIONAL">PROMOTIONAL</option>
                </select>
              </div>
              <div className="form-group"><label>DLT Template ID</label><input type="text" value={sendDltTemplateId} onChange={e => setSendDltTemplateId(e.target.value)} placeholder="DLT Template ID" /></div>
            </div>
            <div className="info-box"><strong>Airtel IQ SMS Configuration:</strong><ul><li>Sender ID: WDBEEP</li><li>Entity ID: 1201161991108627443</li><li>API: iqmessaging.airtel.in</li></ul></div>
            <div className="modal-actions"><Button variant="secondary" onClick={() => setShowSendModal(false)}>Cancel</Button><Button variant="primary" onClick={handleSendSms} loading={sending} disabled={!sendPhone || !sendContent}>Send SMS</Button></div>
          </div>
        </div>
      )}

      {/* Bulk SMS Modal */}
      {showBulkModal && (
        <div className="modal-overlay" onClick={() => setShowBulkModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Send Bulk SMS via Airtel IQ</h3>
            <p className="modal-desc">Send the same message to multiple recipients using Conduit Bulk API.</p>
            <div className="form-group">
              <label>Phone Numbers * (one per line or comma-separated)</label>
              <div className="textarea-with-btn">
                <textarea value={bulkNumbers} onChange={e => setBulkNumbers(e.target.value)} placeholder="9876543210&#10;9876543211&#10;9876543212" rows={4} />
                <button type="button" className="fetch-btn" onClick={() => setShowContactPicker('bulk')}>📇 Add from Contacts</button>
              </div>
              <small>{bulkNumbers.split(/[\n,]/).filter(n => n.trim().length >= 10).length} valid numbers</small>
            </div>
            <div className="form-group"><label>Message *</label><textarea value={bulkContent} onChange={e => setBulkContent(e.target.value)} placeholder="Enter your message..." rows={4} /><small>{bulkContent.length} characters</small></div>
            <div className="form-row">
              <div className="form-group">
                <label>Message Type</label>
                <select value={bulkMessageType} onChange={e => setBulkMessageType(e.target.value)}>
                  <option value="SERVICE_EXPLICIT">SERVICE_EXPLICIT</option>
                  <option value="SERVICE_IMPLICIT">SERVICE_IMPLICIT</option>
                  <option value="TRANSACTIONAL">TRANSACTIONAL</option>
                  <option value="PROMOTIONAL">PROMOTIONAL</option>
                </select>
              </div>
              <div className="form-group"><label>DLT Template ID</label><input type="text" value={bulkDltTemplateId} onChange={e => setBulkDltTemplateId(e.target.value)} placeholder="DLT Template ID" /></div>
            </div>
            <div className="info-box"><strong>Bulk SMS via Conduit API:</strong><ul><li>API: iqmessaging.airtel.in/conduit/api/v1/send-sms-bulk</li><li>Max recipients per request: 1000</li></ul></div>
            <div className="modal-actions"><Button variant="secondary" onClick={() => setShowBulkModal(false)}>Cancel</Button><Button variant="primary" onClick={handleBulkSms} loading={bulkSending} disabled={!bulkNumbers || !bulkContent}>Send Bulk SMS</Button></div>
          </div>
        </div>
      )}

      {/* Contact Picker Modal */}
      {showContactPicker && (
        <div className="modal-overlay" onClick={() => setShowContactPicker(null)}>
          <div className="modal-content contact-picker" onClick={e => e.stopPropagation()}>
            <h3>Select Contact</h3>
            <input type="text" placeholder="Search contacts..." value={contactSearch} onChange={e => setContactSearch(e.target.value)} className="contact-search" />
            <div className="contact-list">
              {loadingContacts ? (
                <div className="loading-contacts">Loading contacts...</div>
              ) : filteredContacts.length === 0 ? (
                <div className="no-contacts">No contacts found</div>
              ) : (
                filteredContacts.slice(0, 50).map(contact => (
                  <div key={contact.contactId} className="contact-row" onClick={() => selectContact(contact)}>
                    <div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div>
                    <div className="contact-details">
                      <div className="contact-name">{contact.name}</div>
                      <div className="contact-phone">{contact.phone}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setShowContactPicker(null)}>Cancel</Button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .sms-page { min-height: calc(100vh - 60px); background: #f0fdf4; padding: 20px; }
        .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header-title { display: flex; align-items: center; gap: 12px; color: #065f46; }
        .header-title h2 { margin: 0; font-size: 1.25rem; }
        .badge { background: #10b981; color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 500; }
        .badge.dlt { background: #059669; }
        .header-actions { display: flex; gap: 8px; }
        .tabs-row { background: #fff; border-radius: 8px; padding: 0 16px; margin-bottom: 16px; border: 1px solid #d1fae5; }
        .controls-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 16px; }
        .search-input { padding: 10px 14px; border: 1px solid #a7f3d0; border-radius: 8px; width: 350px; font-size: 14px; }
        .search-input:focus { outline: none; border-color: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2); }
        .content-area { background: #fff; border-radius: 12px; border: 1px solid #d1fae5; overflow: hidden; }
        .loading-state { padding: 60px; text-align: center; color: #047857; }
        .table-container { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ecfdf5; font-size: 13px; }
        th { background: #ecfdf5; font-weight: 600; color: #065f46; white-space: nowrap; }
        tr:hover { background: #f0fdf4; }
        .phone-cell { font-family: monospace; color: #047857; }
        .content-cell { max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #374151; }
        .id-cell { font-family: monospace; font-size: 11px; color: #6b7280; }
        .type-badge { padding: 3px 8px; border-radius: 4px; font-size: 10px; background: #fef3c7; color: #92400e; }
        .status-badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; background: #f5f5f5; color: #6b7280; }
        .status-badge.sent, .status-badge.delivered { background: #d1fae5; color: #059669; }
        .status-badge.failed { background: #fee2e2; color: #dc2626; }
        .status-badge.pending { background: #fef3c7; color: #92400e; }
        .empty-state { text-align: center; color: #047857; padding: 40px !important; }
        .api-info { padding: 16px; background: #ecfdf5; border-top: 1px solid #d1fae5; }
        .api-info strong { display: block; margin-bottom: 8px; color: #065f46; font-size: 13px; }
        .api-info code { display: block; background: #fff; padding: 10px; border-radius: 6px; font-size: 12px; color: #047857; border: 1px solid #d1fae5; margin-bottom: 12px; }
        .dlt-info { display: flex; gap: 24px; font-size: 13px; color: #065f46; }
        .dlt-info strong { color: #047857; }
        
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .modal-content { background: #fff; border-radius: 12px; padding: 24px; width: 100%; max-width: 520px; max-height: 90vh; overflow-y: auto; }
        .modal-content h3 { margin: 0 0 16px 0; color: #065f46; }
        .modal-desc { margin: 0 0 20px 0; color: #047857; font-size: 14px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #374151; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; font-family: inherit; }
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus { outline: none; border-color: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2); }
        .form-group small { display: block; margin-top: 4px; font-size: 12px; color: #9ca3af; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .info-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px; margin-bottom: 16px; }
        .info-box strong { display: block; margin-bottom: 8px; color: #166534; font-size: 13px; }
        .info-box ul { margin: 0; padding-left: 20px; font-size: 13px; color: #166534; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px; }
        
        .input-with-btn { display: flex; gap: 8px; }
        .input-with-btn input { flex: 1; }
        .textarea-with-btn { display: flex; flex-direction: column; gap: 8px; }
        .fetch-btn { padding: 8px 12px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; color: #065f46; font-size: 12px; cursor: pointer; white-space: nowrap; transition: all 0.15s; }
        .fetch-btn:hover { background: #d1fae5; }
        
        .contact-picker { max-width: 400px; }
        .contact-search { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; margin-bottom: 12px; }
        .contact-search:focus { outline: none; border-color: #10b981; }
        .contact-list { max-height: 300px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
        .contact-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #f3f4f6; transition: background 0.15s; }
        .contact-row:hover { background: #f0fdf4; }
        .contact-row:last-child { border-bottom: none; }
        .contact-avatar { width: 36px; height: 36px; background: #10b981; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; font-size: 14px; }
        .contact-details { flex: 1; }
        .contact-name { font-size: 14px; font-weight: 500; color: #065f46; }
        .contact-phone { font-size: 12px; color: #6b7280; font-family: monospace; }
        .loading-contacts, .no-contacts { padding: 30px; text-align: center; color: #6b7280; }
      `}</style>
    </Layout>
  );
};

const SmsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
);

export default SmsInInbox;
