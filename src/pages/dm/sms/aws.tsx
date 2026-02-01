/**
 * AWS Pinpoint SMS DM
 * Direct messaging via Amazon Pinpoint SMS
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import RichTextEditor from '../../../components/RichTextEditor';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface Contact {
  id: string;
  name: string;
  phone: string;
  unread: number;
  lastMessage?: string;
}

interface Message {
  id: string;
  direction: 'inbound' | 'outbound';
  content: string;
  timestamp: string;
  status: string;
  contactId: string;
}

const AWSSmsDM: React.FC<PageProps> = ({ signOut, user }) => {
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, messagesData] = await Promise.all([
        api.listContacts(),
        api.listMessages(undefined, 'SMS'),
      ]);
      setContacts(contactsData.filter(c => c.phone).map(c => ({
        id: c.contactId,
        name: c.name || c.phone,
        phone: c.phone,
        unread: 0,
        lastMessage: '',
      })));
      setMessages(messagesData.map(m => ({
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
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const filteredMessages = messages.filter(m => selectedContact && m.contactId === selectedContact.id);

  const handleSend = async () => {
    if (!selectedContact || !messageText.trim() || sending) return;
    setSending(true);
    try {
      const result = await api.sendSmsMessage(selectedContact.id, messageText);
      if (result) {
        setMessageText('');
        await loadData();
      } else {
        setError('Failed to send SMS');
      }
    } catch (err) {
      setError('Failed to send SMS');
    } finally {
      setSending(false);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="sms-page">
        <PageHeader 
          title="AWS Pinpoint SMS" 
          subtitle="Global SMS Gateway"
          icon="sms"
          backLink="/dm/sms"
          backLabel="← SMS"
          action={
            <button onClick={loadData} className="refresh-btn" disabled={loading}>
              {loading ? '...' : '↻'}
            </button>
          }
        />

        {error && <div className="error-bar">{error}</div>}

        <div className="sms-layout">
          <div className="sms-sidebar">
            <div className="sidebar-search">
              <input type="text" placeholder="Search contacts..." />
            </div>
            <div className="contacts-list">
              {contacts.map(contact => (
                <div key={contact.id} className={`contact-row ${selectedContact?.id === contact.id ? 'active' : ''}`} onClick={() => setSelectedContact(contact)}>
                  <div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div>
                  <div className="contact-details">
                    <div className="contact-name">{contact.name}</div>
                    <div className="contact-preview">{contact.phone}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="sms-chat">
            {selectedContact ? (
              <>
                <div className="chat-header">
                  <div className="chat-contact">
                    <div className="contact-avatar">{selectedContact.name.charAt(0).toUpperCase()}</div>
                    <div>
                      <div className="chat-name">{selectedContact.name}</div>
                      <div className="chat-phone">{selectedContact.phone}</div>
                    </div>
                  </div>
                  <div className="char-info">{messageText.length}/160</div>
                </div>
                <div className="messages-area">
                  {filteredMessages.map(msg => (
                    <div key={msg.id} className={`message ${msg.direction}`}>
                      <div className="message-bubble">
                        <div className="message-text">{msg.content}</div>
                        <div className="message-time">{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
                <div className="compose-area">
                  <RichTextEditor value={messageText} onChange={setMessageText} placeholder="Type an SMS..." channel="sms" showCharCount={true} maxLength={1600} onSend={handleSend} disabled={sending} />
                </div>
              </>
            ) : (
              <div className="no-chat"><p>Select a contact to start messaging</p></div>
            )}
          </div>

          <div className="info-panel">
            <h3>AWS Pinpoint SMS</h3>
            <div className="info-section"><h4>Features</h4><ul><li>Global Coverage</li><li>Two-way SMS</li><li>Delivery Reports</li><li>SNS Integration</li></ul></div>
            <div className="info-section"><h4>Documentation</h4><a href="https://docs.aws.amazon.com/pinpoint/latest/userguide/channels-sms.html" target="_blank" rel="noopener noreferrer">AWS Pinpoint SMS Docs →</a></div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .sms-page { height: calc(100vh - 60px); display: flex; flex-direction: column; background: #ffffff; }
        .refresh-btn { background: #f5f5f5; border: 1px solid #e5e5e5; color: #000; padding: 8px 12px; border-radius: 8px; cursor: pointer; }
        .refresh-btn:hover { background: #e5e5e5; }
        .error-bar { background: #f5f5f5; color: #000; padding: 8px 16px; font-size: 13px; border-bottom: 1px solid #e5e5e5; }
        .sms-layout { display: grid; grid-template-columns: 280px 1fr 260px; flex: 1; overflow: hidden; }
        .sms-sidebar { background: #fff; border-right: 1px solid #e5e5e5; display: flex; flex-direction: column; }
        .sidebar-search { padding: 12px; border-bottom: 1px solid #e5e5e5; }
        .sidebar-search input { width: 100%; padding: 10px 14px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 14px; }
        .contacts-list { flex: 1; overflow-y: auto; }
        .contact-row { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5; }
        .contact-row:hover { background: #f9f9f9; }
        .contact-row.active { background: #f0f0f0; }
        .contact-avatar { width: 40px; height: 40px; background: #e5e5e5; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; color: #000; }
        .contact-details { flex: 1; }
        .contact-name { font-size: 14px; font-weight: 500; color: #000; }
        .contact-preview { font-size: 12px; color: #4a4a4a; }
        .sms-chat { display: flex; flex-direction: column; background: #fafafa; }
        .chat-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #fff; border-bottom: 1px solid #e5e5e5; }
        .chat-contact { display: flex; align-items: center; gap: 12px; }
        .chat-name { font-weight: 500; color: #000; }
        .chat-phone { font-size: 12px; color: #4a4a4a; }
        .char-info { font-size: 12px; color: #4a4a4a; }
        .messages-area { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 8px; }
        .message { display: flex; max-width: 70%; }
        .message.inbound { align-self: flex-start; }
        .message.outbound { align-self: flex-end; }
        .message-bubble { background: #fff; padding: 10px 14px; border-radius: 12px; border: 1px solid #e5e5e5; }
        .message.outbound .message-bubble { background: #000; color: #fff; border-color: #000; }
        .message-text { font-size: 14px; }
        .message-time { font-size: 11px; opacity: 0.7; margin-top: 4px; text-align: right; }
        .compose-area { padding: 12px 16px; background: #fff; border-top: 1px solid #e5e5e5; }
        .no-chat { flex: 1; display: flex; align-items: center; justify-content: center; color: #4a4a4a; }
        .info-panel { background: #fff; border-left: 1px solid #e5e5e5; padding: 20px; overflow-y: auto; }
        .info-panel h3 { font-size: 16px; margin: 0 0 20px 0; color: #000; }
        .info-section { margin-bottom: 20px; }
        .info-section h4 { font-size: 12px; color: #4a4a4a; text-transform: uppercase; margin: 0 0 8px 0; }
        .info-section ul { list-style: none; padding: 0; margin: 0; font-size: 13px; color: #000; }
        .info-section li { padding: 4px 0; }
        .info-section a { color: #000; text-decoration: none; font-size: 13px; }
        .info-section a:hover { text-decoration: underline; }
        @media (max-width: 1024px) { .sms-layout { grid-template-columns: 240px 1fr; } .info-panel { display: none; } }
        @media (max-width: 768px) { .sms-layout { grid-template-columns: 1fr; } .sms-sidebar { display: none; } }
      `}</style>
    </Layout>
  );
};

export default AWSSmsDM;
