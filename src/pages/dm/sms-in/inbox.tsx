/**
 * SMS-IN Inbox Page - Airtel IQ SMS Integration
 * Send and receive SMS via Airtel IQ Messaging API
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import { SkeletonContact } from '../../../components/Skeleton';
import { useToastContext } from '../../../contexts/ToastContext';
import { CloseIcon, SmsIcon } from '../../../lib/icons';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }
interface Contact { id: string; name: string; phone: string; unread: number; lastMessage?: string; }
interface SmsMessage { id: string; direction: 'inbound' | 'outbound'; content: string; timestamp: string; status: string; contactId: string; messageType?: string; senderId?: string; }

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';
const CONTACTS_PER_PAGE = 20;

const SmsInInbox: React.FC<PageProps> = ({ signOut, user }) => {
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [messages, setMessages] = useState<SmsMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [contactsPage, setContactsPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  
  // Send SMS state
  const [showSendModal, setShowSendModal] = useState(false);
  const [sendPhone, setSendPhone] = useState('');
  const [sendContent, setSendContent] = useState('');
  const [sendMessageType, setSendMessageType] = useState('SERVICE_EXPLICIT');
  const [sendDltTemplateId, setSendDltTemplateId] = useState('1007974344269130859');
  const [sending, setSending] = useState(false);
  
  const toast = useToastContext();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch contacts and Airtel SMS messages
      const [contactsData, smsResponse] = await Promise.all([
        api.listContacts(),
        fetch(`${API_BASE}/sms-in/airtel`).then(r => r.json()).catch(() => ({ messages: [] }))
      ]);
      
      const smsMessages = smsResponse.messages || [];
      
      const displayContacts: Contact[] = contactsData.filter(c => c.phone).map(c => {
        const contactMsgs = smsMessages.filter((m: any) => m.phoneNumber?.includes(c.phone?.slice(-10)) || m.contactId === c.contactId);
        const lastMsg = contactMsgs[0];
        return { 
          id: c.contactId, 
          name: c.name || c.phone || 'Unknown', 
          phone: c.phone || '', 
          unread: contactMsgs.filter((m: any) => m.direction === 'INBOUND' && m.status === 'received').length, 
          lastMessage: lastMsg?.content?.substring(0, 40) || '' 
        };
      });
      
      setContacts(displayContacts);
      setMessages(smsMessages.map((m: any) => ({ 
        id: m.messageId, 
        direction: (m.direction || 'OUTBOUND').toLowerCase() as 'inbound' | 'outbound', 
        content: m.content || '', 
        timestamp: m.timestamp ? new Date(m.timestamp * 1000).toISOString() : new Date().toISOString(), 
        status: m.status?.toLowerCase() || 'sent', 
        contactId: m.contactId || '',
        messageType: m.messageType,
        senderId: m.senderId
      })));
    } catch (err) { 
      console.error('Load error:', err);
      toast.error('Failed to load data'); 
    } finally { 
      setLoading(false); 
    }
  }, [toast]);

  useEffect(() => { loadData(); const interval = setInterval(loadData, 60000); return () => clearInterval(interval); }, [loadData]);
  useEffect(() => { setContactsPage(1); }, [searchQuery]);

  const filteredContacts = contacts.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.phone.includes(searchQuery));
  const totalContactPages = Math.ceil(filteredContacts.length / CONTACTS_PER_PAGE);
  const paginatedContacts = filteredContacts.slice((contactsPage - 1) * CONTACTS_PER_PAGE, contactsPage * CONTACTS_PER_PAGE);
  const filteredMessages = messages.filter(m => selectedContact && (m.contactId === selectedContact.id || selectedContact.phone?.slice(-10) === m.contactId?.slice(-10)));

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try { 
      for (const id of selectedIds) { await api.deleteContact(id); } 
      toast.success(`Deleted ${selectedIds.size} contact(s)`); 
      setSelectedIds(new Set()); 
      setSelectedContact(null); 
      await loadData(); 
    } catch (err) { 
      toast.error('Failed to delete contacts'); 
    } finally { 
      setDeleting(false); 
    }
  };

  const toggleSelect = (id: string) => { 
    const newSet = new Set(selectedIds); 
    if (newSet.has(id)) newSet.delete(id); 
    else newSet.add(id); 
    setSelectedIds(newSet); 
  };

  const handleSendSms = async () => {
    if (!sendPhone || !sendContent) {
      toast.error('Phone number and message are required');
      return;
    }
    setSending(true);
    try {
      const response = await fetch(`${API_BASE}/sms-in/airtel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phoneNumber: sendPhone,
          content: sendContent,
          messageType: sendMessageType,
          dltTemplateId: sendDltTemplateId
        })
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
    } catch (err) {
      toast.error('Failed to send SMS');
    } finally {
      setSending(false);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS-IN Inbox | Airtel IQ | WECARE.DIGITAL" description="Send SMS via Airtel IQ Messaging API" />
      <div className="inbox-page">
        <div className="inbox-header">
          <div className="header-title">
            <SmsIcon size={24} />
            <h2>Airtel IQ SMS</h2>
            <span className="badge">DLT Compliant</span>
          </div>
          <div className="inbox-actions">
            <Button variant="primary" onClick={() => setShowSendModal(true)}>+ Send SMS</Button>
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>
        
        <div className="inbox-layout">
          <div className="inbox-sidebar">
            <div className="sidebar-controls">
              <button onClick={handleDeleteSelected} disabled={selectedIds.size === 0 || deleting} title="Delete selected" className="delete-btn">
                <CloseIcon size={20} strokeWidth={2} color="#10b981" />
              </button>
              <input type="text" placeholder="Search contacts..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="search-input" />
            </div>
            <div className="sidebar-pagination"><Pagination currentPage={contactsPage} totalPages={totalContactPages} onPageChange={setContactsPage} /></div>
            <div className="contacts-list">
              {loading ? Array.from({ length: 5 }).map((_, i) => <div key={i} className="contact-skeleton"><SkeletonContact /></div>) : paginatedContacts.map(contact => (
                <div key={contact.id} className={`contact-item ${selectedContact?.id === contact.id ? 'selected' : ''} ${selectedIds.has(contact.id) ? 'checked' : ''}`} onClick={() => setSelectedContact(contact)}>
                  <input type="checkbox" checked={selectedIds.has(contact.id)} onChange={() => toggleSelect(contact.id)} onClick={e => e.stopPropagation()} />
                  <div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div>
                  <div className="contact-info">
                    <div className="contact-name">{contact.name}{contact.unread > 0 && <span className="unread-badge">{contact.unread}</span>}</div>
                    <div className="contact-phone">{contact.phone}</div>
                    <div className="contact-preview">{contact.lastMessage || 'No messages'}</div>
                  </div>
                </div>
              ))}
              {!loading && filteredContacts.length === 0 && <div className="empty-contacts">No contacts with phone</div>}
            </div>
          </div>
          
          <div className="inbox-messages">
            {selectedContact ? (
              <>
                <div className="messages-header">
                  <div className="contact-avatar large">{selectedContact.name.charAt(0).toUpperCase()}</div>
                  <div>
                    <div className="contact-name">{selectedContact.name}</div>
                    <div className="contact-phone">{selectedContact.phone}</div>
                  </div>
                  <Button variant="primary" size="sm" onClick={() => { setSendPhone(selectedContact.phone); setShowSendModal(true); }}>Send SMS</Button>
                </div>
                <div className="messages-list">
                  {filteredMessages.map(msg => (
                    <div key={msg.id} className={`message-card ${msg.direction}`}>
                      <div className="message-meta">
                        <span className="message-direction">{msg.direction === 'inbound' ? '↙ Received' : '↗ Sent'}</span>
                        <span className="message-time">{new Date(msg.timestamp).toLocaleString()}</span>
                      </div>
                      <div className="message-content">{msg.content}</div>
                      <div className="message-footer">
                        <span className={`status-badge ${msg.status}`}>{msg.status}</span>
                        {msg.messageType && <span className="type-badge">{msg.messageType}</span>}
                        {msg.senderId && <span className="sender-badge">via {msg.senderId}</span>}
                      </div>
                    </div>
                  ))}
                  {filteredMessages.length === 0 && <div className="empty-messages">No SMS messages with this contact</div>}
                </div>
              </>
            ) : (
              <div className="no-selection">
                <SmsIcon size={48} />
                <p>Select a contact</p>
                <small>Choose a contact from the list to view SMS history</small>
                <Button variant="primary" onClick={() => setShowSendModal(true)} style={{ marginTop: '1rem' }}>+ Send New SMS</Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Send SMS Modal */}
      {showSendModal && (
        <div className="modal-overlay" onClick={() => setShowSendModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Send SMS via Airtel IQ</h3>
            
            <div className="form-group">
              <label>Phone Number *</label>
              <input type="tel" value={sendPhone} onChange={e => setSendPhone(e.target.value)} placeholder="10-digit mobile number" />
            </div>
            
            <div className="form-group">
              <label>Message *</label>
              <textarea value={sendContent} onChange={e => setSendContent(e.target.value)} placeholder="Enter your message..." rows={4} />
              <small>{sendContent.length} characters</small>
            </div>
            
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
              
              <div className="form-group">
                <label>DLT Template ID</label>
                <input type="text" value={sendDltTemplateId} onChange={e => setSendDltTemplateId(e.target.value)} placeholder="DLT Template ID" />
              </div>
            </div>
            
            <div className="info-box">
              <strong>Airtel IQ SMS Configuration:</strong>
              <ul>
                <li>Sender ID: WDBEEP</li>
                <li>Entity ID: 1201161991108627443</li>
                <li>API: iqmessaging.airtel.in</li>
              </ul>
            </div>
            
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setShowSendModal(false)}>Cancel</Button>
              <Button variant="primary" onClick={handleSendSms} loading={sending} disabled={!sendPhone || !sendContent}>Send SMS</Button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .inbox-page { height: calc(100vh - 60px); display: flex; flex-direction: column; background: #f0fdf4; }
        .inbox-header { padding: 12px 20px; background: #fff; border-bottom: 2px solid #10b981; display: flex; justify-content: space-between; align-items: center; }
        .header-title { display: flex; align-items: center; gap: 12px; color: #065f46; }
        .header-title h2 { margin: 0; font-size: 1.25rem; color: #065f46; }
        .badge { background: #10b981; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
        .inbox-actions { display: flex; gap: 8px; }
        .inbox-layout { display: grid; grid-template-columns: 320px 1fr; flex: 1; overflow: hidden; }
        .inbox-sidebar { background: #fff; border-right: 1px solid #d1fae5; display: flex; flex-direction: column; }
        .sidebar-controls { display: flex; gap: 8px; padding: 12px; border-bottom: 1px solid #d1fae5; background: #ecfdf5; }
        .delete-btn { display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; background: #fff; border: 1px solid #10b981; border-radius: 13px; cursor: pointer; flex-shrink: 0; transition: all 0.15s; }
        .delete-btn:hover:not(:disabled) { background: #d1fae5; }
        .delete-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .search-input { flex: 1; padding: 8px 12px; border: 1px solid #a7f3d0; border-radius: 8px; font-size: 13px; background: #fff; }
        .search-input:focus { outline: none; border-color: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2); }
        .sidebar-pagination { padding: 10px 12px; border-bottom: 1px solid #d1fae5; background: #f0fdf4; }
        .contacts-list { flex: 1; overflow-y: auto; }
        .contact-skeleton { padding: 12px 16px; }
        .contact-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #ecfdf5; transition: background 0.15s; }
        .contact-item:hover { background: #ecfdf5; }
        .contact-item.selected { background: #d1fae5; border-left: 3px solid #10b981; }
        .contact-item.checked { background: #d1fae5; }
        .contact-item input[type="checkbox"] { margin-top: 12px; accent-color: #10b981; }
        .contact-avatar { width: 40px; height: 40px; background: #10b981; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; flex-shrink: 0; }
        .contact-avatar.large { width: 44px; height: 44px; }
        .contact-info { flex: 1; min-width: 0; }
        .contact-name { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; color: #065f46; }
        .unread-badge { background: #10b981; color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }
        .contact-phone { font-size: 12px; color: #047857; }
        .contact-preview { font-size: 12px; color: #6ee7b7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px; }
        .empty-contacts { padding: 40px 20px; text-align: center; color: #047857; }
        .inbox-messages { display: flex; flex-direction: column; background: #f0fdf4; }
        .messages-header { display: flex; align-items: center; gap: 12px; padding: 16px 20px; background: #fff; border-bottom: 1px solid #d1fae5; }
        .messages-list { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
        .message-card { background: #fff; border: 1px solid #d1fae5; border-radius: 12px; padding: 16px; }
        .message-card.inbound { border-left: 3px solid #10b981; background: #ecfdf5; }
        .message-card.outbound { border-left: 3px solid #059669; }
        .message-meta { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .message-direction { font-size: 12px; color: #047857; }
        .message-time { font-size: 12px; color: #9ca3af; }
        .message-content { font-size: 14px; line-height: 1.5; color: #374151; }
        .message-footer { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
        .status-badge { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: #f5f5f5; color: #6b7280; }
        .status-badge.sent { background: #dbeafe; color: #1d4ed8; }
        .status-badge.delivered { background: #d1fae5; color: #059669; }
        .status-badge.failed { background: #fee2e2; color: #dc2626; }
        .type-badge { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: #fef3c7; color: #92400e; }
        .sender-badge { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: #e0e7ff; color: #4338ca; }
        .empty-messages { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #6b7280; }
        .no-selection { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #6b7280; gap: 8px; }
        .no-selection p { margin: 0; font-weight: 500; }
        .no-selection small { color: #9ca3af; }
        
        /* Modal Styles */
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .modal-content { background: #fff; border-radius: 12px; padding: 24px; width: 100%; max-width: 500px; max-height: 90vh; overflow-y: auto; }
        .modal-content h3 { margin: 0 0 20px 0; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #374151; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; }
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus { outline: none; border-color: #000; }
        .form-group small { display: block; margin-top: 4px; font-size: 12px; color: #9ca3af; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .info-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px; margin-bottom: 16px; }
        .info-box strong { display: block; margin-bottom: 8px; color: #166534; }
        .info-box ul { margin: 0; padding-left: 20px; font-size: 13px; color: #166534; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px; }
      `}</style>
    </Layout>
  );
};

export default SmsInInbox;
