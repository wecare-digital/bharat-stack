/**
 * RCS Inbox Page - Unified Chat Style
 * Matches WhatsApp inbox UX pattern
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import RichTextEditor from '../../../components/RichTextEditor';
import Button from '../../../components/ui/Button';
import Modal from '../../../components/ui/Modal';
import Pagination from '../../../components/ui/Pagination';
import { SkeletonContact } from '../../../components/Skeleton';
import { useToastContext } from '../../../contexts/ToastContext';
import { CloseIcon } from '../../../lib/icons';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }
interface Contact { id: string; name: string; phone: string; unread: number; lastMessage?: string; lastMessageTime?: string; }
interface RcsMessage { id: string; direction: 'inbound' | 'outbound'; content: string; timestamp: string; status: string; contactId: string; }

const CONTACTS_PER_PAGE = 20;

const AVATAR_COLORS = [
  '#059669', '#0891b2', '#7c3aed', '#db2777', '#ea580c',
  '#2563eb', '#4f46e5', '#0d9488', '#c026d3', '#d97706',
];

const getAvatarColor = (name: string): string => {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
};

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp);
  const diff = Date.now() - date.getTime();
  if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diff < 604800000) return date.toLocaleDateString([], { weekday: 'short' });
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
};

const RcsInbox: React.FC<PageProps> = ({ signOut, user, embedded }) => {
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [messages, setMessages] = useState<RcsMessage[]>([]);
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showCompose, setShowCompose] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [contactsPage, setContactsPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [mobileShowChat, setMobileShowChat] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const toast = useToastContext();

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  useEffect(() => { scrollToBottom(); }, [messages, selectedContact]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, messagesData] = await Promise.all([api.listContacts(), api.listMessages(undefined, 'RCS')]);
      const contactMsgMap = new Map<string, { lastMsg: any; unread: number }>();
      messagesData.forEach(m => {
        const existing = contactMsgMap.get(m.contactId);
        const msgTime = new Date(m.timestamp).getTime();
        if (!existing || msgTime > new Date(existing.lastMsg.timestamp).getTime()) {
          contactMsgMap.set(m.contactId, {
            lastMsg: m,
            unread: (existing?.unread || 0) + (m.direction === 'INBOUND' && m.status === 'received' ? 1 : 0),
          });
        }
      });
      const displayContacts: Contact[] = contactsData.filter(c => c.phone).map(c => {
        const msgInfo = contactMsgMap.get(c.contactId);
        return {
          id: c.contactId,
          name: c.name || c.phone || 'Unknown',
          phone: c.phone || '',
          unread: msgInfo?.unread || 0,
          lastMessage: msgInfo?.lastMsg?.content?.substring(0, 40) || '',
          lastMessageTime: msgInfo?.lastMsg?.timestamp,
        };
      }).sort((a, b) => {
        if (!a.lastMessageTime) return 1;
        if (!b.lastMessageTime) return -1;
        return new Date(b.lastMessageTime).getTime() - new Date(a.lastMessageTime).getTime();
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
  const filteredMessages = messages.filter(m => selectedContact && m.contactId === selectedContact.id).sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  const handleSend = async () => {
    if (!selectedContact || !messageText.trim() || sending) return;
    setSending(true);
    try {
      toast.warning('RCS sending not yet implemented');
      setMessageText(''); setShowCompose(false);
    } catch (err) { toast.error('Failed to send RCS message'); } finally { setSending(false); }
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try { for (const id of selectedIds) { await api.deleteContact(id); } toast.success(`Deleted ${selectedIds.size} contact(s)`); setSelectedIds(new Set()); setSelectedContact(null); await loadData(); } catch (err) { toast.error('Failed to delete contacts'); } finally { setDeleting(false); }
  };

  const toggleSelect = (id: string) => { const newSet = new Set(selectedIds); if (newSet.has(id)) newSet.delete(id); else newSet.add(id); setSelectedIds(newSet); };

  const content = (
    <>
      <div className={`whatsapp-inbox ${mobileShowChat ? 'mobile-chat-active' : ''}`}>
        {/* Contacts Sidebar */}
        <div className="contacts-sidebar">
          <div className="sidebar-header">
            <div className="sidebar-controls">
              <button onClick={handleDeleteSelected} disabled={selectedIds.size === 0 || deleting} title="Delete selected" className="delete-all-btn">
                {deleting ? '...' : <CloseIcon size={16} strokeWidth={2} color="currentColor" />}
              </button>
              <input type="text" placeholder="Search contacts..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="contacts-search" />
            </div>
            <div className="contacts-pagination top">
              <Pagination currentPage={contactsPage} totalPages={totalContactPages} onPageChange={setContactsPage} />
            </div>
          </div>
          <div className="contacts-list">
            {loading ? Array.from({ length: 5 }).map((_, i) => <div key={i} style={{ padding: '12px 16px' }}><SkeletonContact /></div>) : paginatedContacts.map(contact => (
              <div key={contact.id} className={`contact-item ${selectedContact?.id === contact.id ? 'selected' : ''}`} onClick={() => { setSelectedContact(contact); setMobileShowChat(true); }}>
                <input type="checkbox" checked={selectedIds.has(contact.id)} onChange={() => toggleSelect(contact.id)} onClick={e => e.stopPropagation()} style={{ accentColor: '#059669', width: 16, height: 16, flexShrink: 0 }} />
                <div className="contact-avatar" style={{ background: getAvatarColor(contact.name), color: '#fff' }}>{contact.name.charAt(0).toUpperCase()}</div>
                <div className="contact-info">
                  <div className="contact-name">{contact.name}</div>
                  <div className="contact-last-msg">{contact.lastMessage || 'No messages'}</div>
                </div>
                <div className="contact-meta">
                  {contact.lastMessageTime && <span className="contact-time">{formatTime(contact.lastMessageTime)}</span>}
                  {contact.unread > 0 && <span className="unread-badge">{contact.unread}</span>}
                </div>
              </div>
            ))}
            {!loading && filteredContacts.length === 0 && <div style={{ padding: '40px 20px', textAlign: 'center', color: '#6b7280' }}>No contacts with phone</div>}
          </div>
        </div>

        {/* Chat Area */}
        <div className="chat-area">
          {selectedContact ? (
            <>
              <div className="chat-header">
                <div className="chat-contact-info">
                  <button className="mobile-back-btn" onClick={() => setMobileShowChat(false)} aria-label="Back to contacts">‹</button>
                  <div className="contact-avatar" style={{ width: 40, height: 40, fontSize: 16, background: getAvatarColor(selectedContact.name), color: '#fff' }}>{selectedContact.name.charAt(0).toUpperCase()}</div>
                  <div>
                    <div className="chat-contact-name">{selectedContact.name}</div>
                    <div className="chat-contact-phone">{selectedContact.phone}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button variant="primary" size="sm" onClick={() => setShowCompose(true)}>Compose</Button>
                  <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" size="sm" onClick={loadData} disabled={loading} loading={loading} />
                </div>
              </div>
              <div className="messages-area">
                {filteredMessages.map((msg, idx) => {
                  const showDate = idx === 0 || new Date(msg.timestamp).toDateString() !== new Date(filteredMessages[idx - 1].timestamp).toDateString();
                  return (
                    <React.Fragment key={msg.id}>
                      {showDate && <div className="date-divider"><span>{new Date(msg.timestamp).toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })}</span></div>}
                      <div className={`message-bubble ${msg.direction}`}>
                        <div className="message-content">{msg.content}</div>
                        <div className="message-footer">
                          <span className="message-time">{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          {msg.direction === 'outbound' && <span className={`message-status ${msg.status}`}>{msg.status === 'delivered' ? '✓✓' : '✓'}</span>}
                        </div>
                      </div>
                    </React.Fragment>
                  );
                })}
                {filteredMessages.length === 0 && <div className="empty-chat"><div className="empty-chat-icon">💬</div><h3>No RCS messages</h3><p>Messages with this contact will appear here</p></div>}
                <div ref={messagesEndRef} />
              </div>
            </>
          ) : (
            <div className="empty-chat">
              <div className="empty-chat-icon">💬</div>
              <h3>RCS Inbox</h3>
              <p>Select a contact to view messages</p>
            </div>
          )}
        </div>
      </div>

      <Modal isOpen={showCompose && !!selectedContact} onClose={() => setShowCompose(false)} title="Send RCS Message" size="md" footer={<><Button variant="secondary" onClick={() => setShowCompose(false)}>Cancel</Button><Button variant="primary" onClick={handleSend} disabled={sending || !messageText.trim()} loading={sending}>{sending ? 'Sending...' : 'Send RCS'}</Button></>}>
        {selectedContact && (<>
          <div className="form-group"><label>To</label><input type="text" value={`${selectedContact.name} (${selectedContact.phone})`} disabled /></div>
          <div className="form-group"><label>Message</label><RichTextEditor value={messageText} onChange={setMessageText} placeholder="Write your RCS message..." channel="sms" showAISuggestions={true} contactContext={selectedContact.name} /></div>
        </>)}
      </Modal>
    </>
  );

  if (embedded) return content;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="RCS Inbox | WECARE.DIGITAL" description="RCS Business Messaging inbox" />
      {content}
    </Layout>
  );
};

export default RcsInbox;
