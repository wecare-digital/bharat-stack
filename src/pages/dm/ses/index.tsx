/**
 * Email DM - AWS SES
 * Direct messaging via AWS Simple Email Service
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import RichTextEditor from '../../../components/RichTextEditor';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface Contact {
  id: string;
  name: string;
  email: string;
  unread: number;
  lastMessage?: string;
}

interface Email {
  id: string;
  direction: 'inbound' | 'outbound';
  subject?: string;
  content: string;
  timestamp: string;
  status: string;
  contactId: string;
}

const SesDM: React.FC<PageProps> = ({ signOut, user }) => {
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [emails, setEmails] = useState<Email[]>([]);
  const [subject, setSubject] = useState('');
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCompose, setShowCompose] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, messagesData] = await Promise.all([
        api.listContacts(),
        api.listMessages(undefined, 'EMAIL'),
      ]);

      const displayContacts: Contact[] = contactsData
        .filter(c => c.email)
        .map(c => {
          const contactMsgs = messagesData.filter(m => m.contactId === c.contactId);
          const lastMsg = contactMsgs[0];
          return {
            id: c.contactId,
            name: c.name || c.email || 'Unknown',
            email: c.email || '',
            unread: contactMsgs.filter(m => m.direction === 'INBOUND' && m.status === 'received').length,
            lastMessage: lastMsg?.content?.substring(0, 40) || '',
          };
        });

      setContacts(displayContacts);
      setEmails(messagesData.map(m => ({
        id: m.messageId,
        direction: m.direction.toLowerCase() as 'inbound' | 'outbound',
        content: m.content || '',
        timestamp: m.timestamp,
        status: m.status?.toLowerCase() || 'sent',
        contactId: m.contactId,
      })));
    } catch (err) {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, [loadData]);

  const filteredEmails = emails.filter(e => selectedContact && e.contactId === selectedContact.id);

  const handleSend = async () => {
    if (!selectedContact || !messageText.trim() || !subject.trim() || sending) return;
    setSending(true);
    setError(null);

    try {
      const result = await api.sendEmailMessage(selectedContact.id, subject, messageText);
      if (result) {
        setSubject('');
        setMessageText('');
        setShowCompose(false);
        await loadData();
      } else {
        setError('Email sending not yet implemented');
      }
    } catch (err) {
      setError('Failed to send email');
    } finally {
      setSending(false);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="ses-page">
        <div className="ses-header">
          <a href="/dm" className="back-btn">←</a>
          <div className="ses-header-info">
            <span className="ses-icon">✉️</span>
            <div>
              <h1>Email - AWS SES</h1>
              <span className="ses-provider">Simple Email Service</span>
            </div>
          </div>
          <button onClick={() => setShowCompose(true)} className="compose-btn" disabled={!selectedContact}>
            ✎ Compose
          </button>
          <button onClick={loadData} className="refresh-btn" disabled={loading}>
            {loading ? '...' : '↻'}
          </button>
        </div>

        {error && <div className="error-bar">{error}</div>}

        <div className="ses-layout">
          {/* Contacts Sidebar */}
          <div className="ses-sidebar">
            <div className="sidebar-search">
              <input type="text" placeholder="Search contacts..." />
            </div>
            <div className="contacts-list">
              {contacts.map(contact => (
                <div
                  key={contact.id}
                  className={`contact-row ${selectedContact?.id === contact.id ? 'active' : ''}`}
                  onClick={() => setSelectedContact(contact)}
                >
                  <div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div>
                  <div className="contact-details">
                    <div className="contact-name">
                      {contact.name}
                      {contact.unread > 0 && <span className="unread">{contact.unread}</span>}
                    </div>
                    <div className="contact-email">{contact.email}</div>
                    <div className="contact-preview">{contact.lastMessage || 'No emails'}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Email List */}
          <div className="ses-main">
            {selectedContact ? (
              <>
                <div className="email-header">
                  <div className="email-contact">
                    <div className="contact-avatar large">{selectedContact.name.charAt(0).toUpperCase()}</div>
                    <div>
                      <div className="email-name">{selectedContact.name}</div>
                      <div className="email-address">{selectedContact.email}</div>
                    </div>
                  </div>
                </div>

                <div className="emails-list">
                  {filteredEmails.map(email => (
                    <div key={email.id} className={`email-item ${email.direction}`}>
                      <div className="email-item-header">
                        <span className="email-direction">
                          {email.direction === 'inbound' ? '↙ Received' : '↗ Sent'}
                        </span>
                        <span className="email-time">
                          {new Date(email.timestamp).toLocaleString()}
                        </span>
                      </div>
                      {email.subject && <div className="email-subject">{email.subject}</div>}
                      <div className="email-body">{email.content}</div>
                      <div className="email-status">
                        <span className={`status-badge ${email.status}`}>
                          {email.status === 'delivered' ? '✓ Delivered' : 
                           email.status === 'opened' ? '◉ Opened' : '✓ Sent'}
                        </span>
                      </div>
                    </div>
                  ))}
                  {filteredEmails.length === 0 && (
                    <div className="no-emails">No emails with this contact</div>
                  )}
                </div>
              </>
            ) : (
              <div className="no-contact">
                <p>✉️ Select a contact</p>
                <small>Choose a contact from the list to view emails</small>
              </div>
            )}
          </div>

          {/* Info Panel */}
          <div className="info-panel">
            <h3>AWS SES</h3>
            <div className="info-section">
              <h4>Sender Identity</h4>
              <p>noreply@wecare.digital</p>
              <span className="verified-badge">✓ Verified</span>
            </div>
            <div className="info-section">
              <h4>Sending Limits</h4>
              <p>50,000 emails/day</p>
            </div>
            <div className="info-section">
              <h4>Features</h4>
              <ul className="feature-list">
                <li>✓ Transactional Email</li>
                <li>✓ HTML Templates</li>
                <li>✓ Bounce Handling</li>
                <li>✓ Open/Click Tracking</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Compose Modal */}
        {showCompose && selectedContact && (
          <div className="modal-overlay" onClick={() => setShowCompose(false)}>
            <div className="compose-modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Compose Email</h2>
                <button onClick={() => setShowCompose(false)}>✕</button>
              </div>
              <div className="compose-form">
                <div className="form-row">
                  <label>To</label>
                  <input type="text" value={`${selectedContact.name} <${selectedContact.email}>`} disabled />
                </div>
                <div className="form-row">
                  <label>Subject</label>
                  <input 
                    type="text" 
                    value={subject} 
                    onChange={e => setSubject(e.target.value)}
                    placeholder="Enter subject..."
                  />
                </div>
                <div className="form-row">
                  <label>Message</label>
                  <RichTextEditor
                    value={messageText}
                    onChange={setMessageText}
                    placeholder="Write your email..."
                    channel="email"
                    showAISuggestions={true}
                    contactContext={selectedContact.name}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn-secondary" onClick={() => setShowCompose(false)}>Cancel</button>
                <button 
                  className="btn-primary" 
                  onClick={handleSend}
                  disabled={sending || !subject.trim() || !messageText.trim()}
                >
                  {sending ? 'Sending...' : 'Send Email'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .ses-page { height: calc(100vh - 60px); display: flex; flex-direction: column; }
        .ses-header { display: flex; align-items: center; gap: 16px; padding: 12px 20px; background: #000; color: #fff; }
        .back-btn, .refresh-btn { background: rgba(255,255,255,0.2); border: none; color: #fff; padding: 8px 12px; border-radius: 8px; cursor: pointer; text-decoration: none; }
        .compose-btn { background: #fff; border: none; color: #000; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: 500; }
        .ses-header-info { display: flex; align-items: center; gap: 12px; flex: 1; }
        .ses-icon { font-size: 28px; }
        .ses-header h1 { font-size: 18px; font-weight: 500; margin: 0; }
        .ses-provider { font-size: 13px; opacity: 0.9; }
        .error-bar { background: #f5f5f5; color: #000; padding: 8px 16px; font-size: 13px; }
        .ses-layout { display: grid; grid-template-columns: 280px 1fr 260px; flex: 1; overflow: hidden; }
        .ses-sidebar { background: #fff; border-right: 1px solid #e5e5e5; display: flex; flex-direction: column; }
        .sidebar-search { padding: 12px; border-bottom: 1px solid #e5e5e5; }
        .sidebar-search input { width: 100%; padding: 10px 14px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 14px; }
        .contacts-list { flex: 1; overflow-y: auto; }
        .contact-row { display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5; }
        .contact-row:hover { background: #f9f9f9; }
        .contact-row.active { background: #f0f0f0; }
        .contact-avatar { width: 40px; height: 40px; background: #e5e5e5; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; color: #666; flex-shrink: 0; }
        .contact-avatar.large { width: 44px; height: 44px; }
        .contact-details { flex: 1; min-width: 0; }
        .contact-name { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; }
        .contact-email { font-size: 12px; color: #666; }
        .contact-preview { font-size: 12px; color: #999; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px; }
        .unread { background: #000; color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }
        .ses-main { display: flex; flex-direction: column; background: #f5f5f5; }
        .email-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: #fff; border-bottom: 1px solid #e5e5e5; }
        .email-contact { display: flex; align-items: center; gap: 12px; }
        .email-name { font-weight: 500; }
        .email-address { font-size: 12px; color: #666; }
        .emails-list { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
        .email-item { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px; }
        .email-item.inbound { border-left: 3px solid #000; }
        .email-item.outbound { border-left: 3px solid #4a4a4a; }
        .email-item-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .email-direction { font-size: 12px; color: #666; }
        .email-time { font-size: 12px; color: #999; }
        .email-subject { font-weight: 500; margin-bottom: 8px; }
        .email-body { font-size: 14px; line-height: 1.5; color: #333; }
        .email-status { margin-top: 12px; }
        .status-badge { font-size: 12px; padding: 4px 8px; border-radius: 4px; background: #f0f0f0; }
        .no-emails, .no-contact { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #999; }
        .info-panel { background: #fff; border-left: 1px solid #e5e5e5; padding: 20px; overflow-y: auto; }
        .info-panel h3 { font-size: 16px; margin: 0 0 20px 0; }
        .info-section { margin-bottom: 20px; }
        .info-section h4 { font-size: 12px; color: #666; text-transform: uppercase; margin: 0 0 8px 0; }
        .info-section p { margin: 0; font-size: 14px; }
        .verified-badge { font-size: 11px; color: #000; }
        .feature-list { list-style: none; padding: 0; margin: 0; font-size: 13px; }
        .feature-list li { padding: 4px 0; }
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .compose-modal { background: #fff; border-radius: 12px; width: 90%; max-width: 600px; max-height: 90vh; overflow: hidden; display: flex; flex-direction: column; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e5e5e5; }
        .modal-header h2 { margin: 0; font-size: 18px; }
        .modal-header button { background: none; border: none; font-size: 20px; cursor: pointer; }
        .compose-form { padding: 20px; flex: 1; overflow-y: auto; }
        .form-row { margin-bottom: 16px; }
        .form-row label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; }
        .form-row input { width: 100%; padding: 10px 12px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 14px; }
        .form-row input:disabled { background: #f5f5f5; }
        .modal-footer { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 20px; border-top: 1px solid #e5e5e5; }
        .btn-secondary { background: #fff; border: 1px solid #e5e5e5; padding: 10px 20px; border-radius: 8px; cursor: pointer; }
        .btn-primary { background: #1a1a1a; color: #fff; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; }
        .btn-primary:disabled { background: #ccc; }
      `}</style>
    </Layout>
  );
};

export default SesDM;
