/**
 * SMS-IN Inbox Page - Black/White Theme (Inbound SMS via Indian DLT)
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import { SkeletonContact } from '../../../components/Skeleton';
import { useToastContext } from '../../../contexts/ToastContext';
import { CloseIcon } from '../../../lib/icons';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }
interface Contact { id: string; name: string; phone: string; unread: number; lastMessage?: string; }
interface SmsMessage { id: string; direction: 'inbound' | 'outbound'; content: string; timestamp: string; status: string; contactId: string; }

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
  const toast = useToastContext();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, messagesData] = await Promise.all([api.listContacts(), api.listMessages(undefined, 'SMS_IN')]);
      const displayContacts: Contact[] = contactsData.filter(c => c.phone).map(c => {
        const contactMsgs = messagesData.filter(m => m.contactId === c.contactId);
        const lastMsg = contactMsgs[0];
        return { id: c.contactId, name: c.name || c.phone || 'Unknown', phone: c.phone || '', unread: contactMsgs.filter(m => m.direction === 'INBOUND' && m.status === 'received').length, lastMessage: lastMsg?.content?.substring(0, 40) || '' };
      });
      setContacts(displayContacts);
      setMessages(messagesData.map(m => ({ id: m.messageId, direction: m.direction.toLowerCase() as 'inbound' | 'outbound', content: m.content || '', timestamp: m.timestamp, status: m.status?.toLowerCase() || 'sent', contactId: m.contactId })));
    } catch (err) { toast.error('Failed to load data'); } finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadData(); const interval = setInterval(loadData, 60000); return () => clearInterval(interval); }, [loadData]);
  useEffect(() => { setContactsPage(1); }, [searchQuery]);


  const filteredContacts = contacts.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.phone.includes(searchQuery));
  const totalContactPages = Math.ceil(filteredContacts.length / CONTACTS_PER_PAGE);
  const paginatedContacts = filteredContacts.slice((contactsPage - 1) * CONTACTS_PER_PAGE, contactsPage * CONTACTS_PER_PAGE);
  const filteredMessages = messages.filter(m => selectedContact && m.contactId === selectedContact.id);

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try { for (const id of selectedIds) { await api.deleteContact(id); } toast.success(`Deleted ${selectedIds.size} contact(s)`); setSelectedIds(new Set()); setSelectedContact(null); await loadData(); } catch (err) { toast.error('Failed to delete contacts'); } finally { setDeleting(false); }
  };

  const toggleSelect = (id: string) => { const newSet = new Set(selectedIds); if (newSet.has(id)) newSet.delete(id); else newSet.add(id); setSelectedIds(newSet); };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS-IN Inbox | WECARE.DIGITAL" description="Inbound SMS inbox via Indian DLT" />
      <div className="inbox-page">
        <div className="inbox-header">
          <div className="inbox-actions">
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
                <div className="messages-header"><div className="contact-avatar large">{selectedContact.name.charAt(0).toUpperCase()}</div><div><div className="contact-name">{selectedContact.name}</div><div className="contact-phone">{selectedContact.phone}</div></div></div>
                <div className="messages-list">
                  {filteredMessages.map(msg => (
                    <div key={msg.id} className={`message-card ${msg.direction}`}>
                      <div className="message-meta"><span className="message-direction">{msg.direction === 'inbound' ? '↙ Received' : '↗ Sent'}</span><span className="message-time">{new Date(msg.timestamp).toLocaleString()}</span></div>
                      <div className="message-content">{msg.content}</div>
                      <div className="message-status"><span className={`status-badge ${msg.status}`}>{msg.status}</span></div>
                    </div>
                  ))}
                  {filteredMessages.length === 0 && <div className="empty-messages">No SMS messages with this contact</div>}
                </div>
              </>
            ) : (<div className="no-selection"><p>Select a contact</p><small>Choose a contact from the list to view inbound SMS</small></div>)}
          </div>
        </div>
      </div>

      <style jsx>{`
        .inbox-page { height: calc(100vh - 60px); display: flex; flex-direction: column; background: #fafafa; }
        .inbox-header { padding: 12px 20px; background: #fff; border-bottom: 1px solid #e5e5e5; display: flex; justify-content: flex-end; }
        .inbox-actions { display: flex; gap: 8px; }
        .inbox-layout { display: grid; grid-template-columns: 320px 1fr; flex: 1; overflow: hidden; }
        .inbox-sidebar { background: #fff; border-right: 1px solid #e5e5e5; display: flex; flex-direction: column; }
        .sidebar-controls { display: flex; gap: 8px; padding: 12px; border-bottom: 1px solid #f0f0f0; }
        .delete-btn { display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; background: #fff; border: 1px solid #10b981; border-radius: 13px; cursor: pointer; flex-shrink: 0; transition: all 0.15s; }
        .delete-btn:hover:not(:disabled) { background: #f0fdf4; }
        .delete-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .search-input { flex: 1; padding: 8px 12px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 13px; }
        .search-input:focus { outline: none; border-color: #000; }
        .sidebar-pagination { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }
        .contacts-list { flex: 1; overflow-y: auto; }
        .contact-skeleton { padding: 12px 16px; }
        .contact-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5; transition: background 0.15s; }
        .contact-item:hover { background: #fafafa; }
        .contact-item.selected { background: #f5f5f5; }
        .contact-item.checked { background: #f9fafb; }
        .contact-item input[type="checkbox"] { margin-top: 12px; accent-color: #000; }
        .contact-avatar { width: 40px; height: 40px; background: #000; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; flex-shrink: 0; }
        .contact-avatar.large { width: 44px; height: 44px; }
        .contact-info { flex: 1; min-width: 0; }
        .contact-name { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; }
        .unread-badge { background: #000; color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }
        .contact-phone { font-size: 12px; color: #6b7280; }
        .contact-preview { font-size: 12px; color: #9ca3af; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px; }
        .empty-contacts { padding: 40px 20px; text-align: center; color: #6b7280; }
        .inbox-messages { display: flex; flex-direction: column; background: #fafafa; }
        .messages-header { display: flex; align-items: center; gap: 12px; padding: 16px 20px; background: #fff; border-bottom: 1px solid #e5e5e5; }
        .messages-list { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
        .message-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 16px; }
        .message-card.inbound { border-left: 3px solid #000; }
        .message-card.outbound { border-left: 3px solid #9ca3af; }
        .message-meta { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .message-direction { font-size: 12px; color: #6b7280; }
        .message-time { font-size: 12px; color: #9ca3af; }
        .message-content { font-size: 14px; line-height: 1.5; color: #374151; }
        .message-status { margin-top: 12px; }
        .status-badge { font-size: 12px; padding: 4px 8px; border-radius: 6px; background: #f5f5f5; color: #6b7280; }
        .status-badge.delivered { background: #f0f0f0; color: #000; }
        .empty-messages { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #6b7280; }
        .no-selection { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #6b7280; }
        .no-selection p { margin: 0; font-weight: 500; }
        .no-selection small { color: #9ca3af; }
      `}</style>
    </Layout>
  );
};

export default SmsInInbox;