/**
 * IN SMS DM
 * Direct messaging via Airtel IQ SMS Gateway with DLT Compliance
 * 
 * Features:
 * - DLT compliant SMS (TRAI regulation)
 * - Message Types: PROMOTIONAL, TRANSACTIONAL, SERVICE_IMPLICIT, SERVICE_EXPLICIT
 * - Template ID and Entity ID support
 * - OTP traffic support
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import RichTextEditor from '../../../components/RichTextEditor';
import Button from '../../../components/ui/Button';
import { API_BASE } from '../../../config/constants';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
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
  messageType?: string;
  dltTemplateId?: string;
}

type TabType = 'chat' | 'compose' | 'templates';

const INSmsDM: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const [activeTab, setActiveTab] = useState<TabType>('chat');
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // DLT Configuration - WECARE.DIGITAL defaults
  const [messageType, setMessageType] = useState<string>('SERVICE_IMPLICIT');
  const [dltTemplateId, setDltTemplateId] = useState<string>('1007974344269130859');
  const [sourceAddress, setSourceAddress] = useState<string>('WDBEEP');
  const [isOtp, setIsOtp] = useState<boolean>(false);
  const [apiVersion, setApiVersion] = useState<string>('v4');

  // Registered DLT Templates
  const registeredTemplates = [
    {
      name: 'wecare selfservice ivr template',
      templateId: '1007974344269130859',
      header: 'WDBEEP',
      type: 'Service Implicit',
      content: 'Thanks for reaching out, WECARE.DIGITAL! Please submit your request through our online Self Service Portal at https://wecare.digital/selfservice. Once we receive it, we\'ll review it and contact you if anything else is needed.',
      status: 'REGISTERED'
    }
  ];

  // Compose tab state
  const [composePhone, setComposePhone] = useState<string>('');
  const [composeMessage, setComposeMessage] = useState<string>('');

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
        messageType: (m as any).messageType,
        dltTemplateId: (m as any).dltTemplateId,
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

  // Send SMS via Airtel IQ API
  const sendAirtelSms = async (phone: string, content: string, contactId?: string) => {
    try {
      const response = await fetch(`${API_BASE}/sms/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contactId: contactId || undefined,
          phoneNumber: phone,
          content: content,
          provider: 'airtel',
          messageType: messageType,
          dltTemplateId: dltTemplateId,
          sourceAddress: sourceAddress,
          otp: isOtp,
          apiVersion: apiVersion,
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        return { success: true, messageRequestId: data.messageRequestId };
      } else {
        return { success: false, error: data.error || 'Failed to send SMS' };
      }
    } catch (err: any) {
      return { success: false, error: err.message || 'Network error' };
    }
  };

  const handleSend = async () => {
    if (!selectedContact || !messageText.trim() || sending) return;
    setSending(true);
    setError(null);
    
    try {
      const result = await sendAirtelSms(selectedContact.phone, messageText, selectedContact.id);
      
      if (result.success) {
        setMessageText('');
        setSuccess(`SMS sent! Request ID: ${result.messageRequestId}`);
        await loadData();
        setTimeout(() => setSuccess(null), 5000);
      } else {
        setError(result.error || 'Failed to send SMS');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to send SMS');
    } finally {
      setSending(false);
    }
  };

  const handleComposeSend = async () => {
    if (!composePhone.trim() || !composeMessage.trim() || sending) return;
    setSending(true);
    setError(null);
    
    try {
      const result = await sendAirtelSms(composePhone, composeMessage);
      
      if (result.success) {
        setComposeMessage('');
        setSuccess(`SMS sent to ${composePhone}! Request ID: ${result.messageRequestId}`);
        await loadData();
        setTimeout(() => setSuccess(null), 5000);
      } else {
        setError(result.error || 'Failed to send SMS');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to send SMS');
    } finally {
      setSending(false);
    }
  };

  const pageContent = (
    <div className="sms-page" style={{ height: embedded ? '100%' : 'calc(100vh - 60px)' }}>
      {!embedded && (
        <PageHeader 
          title="Airtel IQ SMS" 
          subtitle="DLT Compliant SMS Gateway"
          icon="sms"
          backLink="/dm/sms"
          backLabel="← SMS"
          actions={
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          }
        />
      )}

      {error && <div className="error-bar">{error} <button onClick={() => setError(null)}>×</button></div>}
      {success && <div className="success-bar">{success} <button onClick={() => setSuccess(null)}>×</button></div>}

        {/* Tabs */}
        <div className="tabs-bar">
          {(['chat', 'compose', 'templates'] as TabType[]).map(tab => (
            <button
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'chat' && 'Chat'}
              {tab === 'compose' && 'Compose'}
              {tab === 'templates' && 'DLT Config'}
            </button>
          ))}
        </div>

        {/* CHAT TAB */}
        {activeTab === 'chat' && (
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
                    <div className="char-info">
                      <span className="msg-type-badge">{messageType}</span>
                      {messageText.length}/160
                    </div>
                  </div>
                  <div className="messages-area">
                    {filteredMessages.map(msg => (
                      <div key={msg.id} className={`message ${msg.direction}`}>
                        <div className="message-bubble">
                          <div className="message-text">{msg.content}</div>
                          <div className="message-meta">
                            <span className="message-time">{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            {msg.messageType && <span className="msg-type-small">{msg.messageType}</span>}
                          </div>
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
          </div>
        )}

        {/* COMPOSE TAB */}
        {activeTab === 'compose' && (
          <div className="compose-tab">
            <div className="compose-form">
              <h3>Send SMS</h3>
              
              <div className="form-group">
                <label>Phone Number</label>
                <input
                  type="tel"
                  value={composePhone}
                  onChange={(e) => setComposePhone(e.target.value.replace(/[^0-9+]/g, ''))}
                  placeholder="Enter 10-digit mobile number"
                />
                <span className="hint">Format: 10 digits (e.g., 9876543210) or 12 digits with country code</span>
              </div>

              <div className="form-group">
                <label>Message</label>
                <textarea
                  value={composeMessage}
                  onChange={(e) => setComposeMessage(e.target.value)}
                  placeholder="Enter your message..."
                  rows={4}
                />
                <span className="hint">{composeMessage.length}/160 characters ({Math.ceil(composeMessage.length / 160) || 1} SMS)</span>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Message Type</label>
                  <select value={messageType} onChange={(e) => setMessageType(e.target.value)}>
                    <option value="SERVICE_IMPLICIT">Service Implicit</option>
                    <option value="SERVICE_EXPLICIT">Service Explicit</option>
                    <option value="TRANSACTIONAL">Transactional</option>
                    <option value="PROMOTIONAL">Promotional</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>API Version</label>
                  <select value={apiVersion} onChange={(e) => setApiVersion(e.target.value)}>
                    <option value="v4">v4 - Standard DLT</option>
                    <option value="v5">v5 - Content Moderation</option>
                    <option value="v6">v6 - Enhanced Response</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>DLT Template ID</label>
                  <input
                    type="text"
                    value={dltTemplateId}
                    onChange={(e) => setDltTemplateId(e.target.value)}
                    placeholder="Enter DLT Template ID"
                  />
                </div>
                <div className="form-group">
                  <label>Header (Source Address)</label>
                  <input
                    type="text"
                    value={sourceAddress}
                    onChange={(e) => setSourceAddress(e.target.value)}
                    placeholder="WECARE"
                  />
                </div>
              </div>

              {messageType === 'SERVICE_IMPLICIT' && (
                <div className="form-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={isOtp}
                      onChange={(e) => setIsOtp(e.target.checked)}
                    />
                    This is an OTP message
                  </label>
                  <span className="hint">Check if this is a One-Time Password message</span>
                </div>
              )}

              <button
                onClick={handleComposeSend}
                disabled={!composePhone.trim() || !composeMessage.trim() || sending}
                className="send-btn"
              >
                {sending ? 'Sending...' : 'Send SMS'}
              </button>
            </div>
          </div>
        )}

        {/* DLT CONFIG TAB */}
        {activeTab === 'templates' && (
          <div className="templates-tab">
            <div className="config-section">
              <h3>DLT Configuration</h3>
              <p className="section-desc">Configure your DLT (Distributed Ledger Technology) settings for TRAI compliance.</p>

              {/* Entity Info */}
              <div className="entity-info">
                <h4>Registered Entity</h4>
                <div className="entity-details">
                  <div className="entity-row">
                    <span className="label">Entity Name:</span>
                    <span className="value">WECARE.DIGITAL</span>
                  </div>
                  <div className="entity-row">
                    <span className="label">Type:</span>
                    <span className="value">ENTERPRISE</span>
                  </div>
                  <div className="entity-row">
                    <span className="label">PE ID:</span>
                    <span className="value mono">1201161991108627443</span>
                  </div>
                </div>
              </div>

              {/* Registered Header */}
              <div className="header-info">
                <h4>Registered Header</h4>
                <table className="dlt-table">
                  <thead>
                    <tr>
                      <th>Header</th>
                      <th>Header DLT ID</th>
                      <th>Comm. Type</th>
                      <th>Category</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><strong>WDBEEP</strong></td>
                      <td className="mono">1405170900886606599</td>
                      <td>Other</td>
                      <td>COMMUNICATION/BROADCAST/ENTERTAINMENT/IT</td>
                      <td><span className="status-badge registered">REGISTERED</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Registered Templates */}
              <div className="templates-info">
                <h4>Registered Templates</h4>
                <table className="dlt-table">
                  <thead>
                    <tr>
                      <th>Template Name</th>
                      <th>Template DLT ID</th>
                      <th>Header</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {registeredTemplates.map((tpl, idx) => (
                      <tr key={idx}>
                        <td><strong>{tpl.name}</strong></td>
                        <td className="mono">{tpl.templateId}</td>
                        <td>{tpl.header}</td>
                        <td>{tpl.type}</td>
                        <td><span className="status-badge registered">{tpl.status}</span></td>
                        <td>
                          <button 
                            className="use-btn"
                            onClick={() => {
                              setDltTemplateId(tpl.templateId);
                              setSourceAddress(tpl.header);
                              setComposeMessage(tpl.content);
                              setActiveTab('compose');
                            }}
                          >
                            Use Template
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="template-preview">
                  <h5>Template Content Preview:</h5>
                  <div className="preview-box">
                    {registeredTemplates[0]?.content}
                  </div>
                </div>
              </div>

              <div className="config-grid">
                <div className="config-card">
                  <h4>Message Type</h4>
                  <select value={messageType} onChange={(e) => setMessageType(e.target.value)}>
                    <option value="SERVICE_IMPLICIT">Service Implicit</option>
                    <option value="SERVICE_EXPLICIT">Service Explicit</option>
                    <option value="TRANSACTIONAL">Transactional</option>
                    <option value="PROMOTIONAL">Promotional</option>
                  </select>
                  <p className="config-hint">
                    {messageType === 'PROMOTIONAL' && 'Marketing messages - DND/preference checked'}
                    {messageType === 'TRANSACTIONAL' && 'Transaction alerts - No DND check'}
                    {messageType === 'SERVICE_IMPLICIT' && 'Service messages with implicit consent'}
                    {messageType === 'SERVICE_EXPLICIT' && 'Service messages requiring explicit consent'}
                  </p>
                </div>

                <div className="config-card">
                  <h4>DLT Template ID</h4>
                  <input
                    type="text"
                    value={dltTemplateId}
                    onChange={(e) => setDltTemplateId(e.target.value)}
                    placeholder="Enter Template ID from DLT portal"
                  />
                  <p className="config-hint">Default: 1007974344269130859</p>
                </div>

                <div className="config-card">
                  <h4>Header (Sender ID)</h4>
                  <input
                    type="text"
                    value={sourceAddress}
                    onChange={(e) => setSourceAddress(e.target.value)}
                    placeholder="WDBEEP"
                  />
                  <p className="config-hint">Registered header: WDBEEP</p>
                </div>

                <div className="config-card">
                  <h4>🔧 API Version</h4>
                  <select value={apiVersion} onChange={(e) => setApiVersion(e.target.value)}>
                    <option value="v4">v4 - Standard DLT</option>
                    <option value="v5">v5 - Content Moderation</option>
                    <option value="v6">v6 - Enhanced Response</option>
                  </select>
                  <p className="config-hint">
                    {apiVersion === 'v4' && 'Standard API with full DLT params'}
                    {apiVersion === 'v5' && 'Auto content moderation, simpler params'}
                    {apiVersion === 'v6' && 'Enhanced response with full details'}
                  </p>
                </div>
              </div>

              <div className="info-box">
                <h4>📚 DLT Registration Links</h4>
                <ul>
                  <li><a href="https://www.youtube.com/watch?v=ZOtG3JNphJc" target="_blank" rel="noopener noreferrer">Registration of Principal Entity →</a></li>
                  <li><a href="https://www.youtube.com/watch?v=bVDw2ylgv_o" target="_blank" rel="noopener noreferrer">Registration of Headers →</a></li>
                  <li><a href="https://www.youtube.com/watch?v=ZEnf_U0UOyk" target="_blank" rel="noopener noreferrer">Content Template Registration →</a></li>
                  <li><a href="https://www.airtel.in/business/commercial-communication/help" target="_blank" rel="noopener noreferrer">DLT Help & Guidelines →</a></li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
  );

  const styles = `
    .sms-page { height: calc(100vh - 60px); display: flex; flex-direction: column; background: #ffffff; }
    .error-bar { background: #fef2f2; color: #dc2626; padding: 8px 16px; font-size: 13px; border-bottom: 1px solid #fecaca; display: flex; justify-content: space-between; align-items: center; }
    .error-bar button { background: none; border: none; font-size: 18px; cursor: pointer; }
    .success-bar { background: #d1fae5; color: #065f46; padding: 8px 16px; font-size: 13px; border-bottom: 1px solid #a7f3d0; display: flex; justify-content: space-between; align-items: center; }
    .success-bar button { background: none; border: none; font-size: 18px; cursor: pointer; }
    .tabs-bar { display: flex; gap: 8px; padding: 12px 16px; border-bottom: 1px solid #e5e5e5; background: #fafafa; }
    .tab-btn { padding: 8px 16px; border: 1px solid #e5e5e5; border-radius: 8px; background: white; cursor: pointer; font-size: 14px; }
    .tab-btn.active { background: #000; color: white; border-color: #000; }
    .sms-layout { display: grid; grid-template-columns: 280px 1fr; flex: 1; overflow: hidden; }
    .contacts-list { flex: 1; overflow-y: auto; }
    .contact-row { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5; }
    .contact-row:hover { background: #f5f5f5; }
    .contact-row.active { background: #f0f0f0; }
    .contact-avatar { width: 40px; height: 40px; background: #e5e5e5; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; }
    .contact-details { flex: 1; }
    .contact-name { font-size: 14px; font-weight: 500; }
    .contact-preview { font-size: 12px; color: #666; }
    .sms-chat { display: flex; flex-direction: column; background: #fafafa; }
    .chat-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #fff; border-bottom: 1px solid #e5e5e5; }
    .chat-contact { display: flex; align-items: center; gap: 12px; }
    .chat-name { font-weight: 500; }
    .chat-phone { font-size: 12px; color: #666; }
    .char-info { font-size: 12px; color: #666; display: flex; align-items: center; gap: 8px; }
    .msg-type-badge { background: #e5e5e5; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
    .messages-area { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 8px; }
    .message { display: flex; max-width: 70%; }
    .message.inbound { align-self: flex-start; }
    .message.outbound { align-self: flex-end; }
    .message-bubble { background: #fff; padding: 10px 14px; border-radius: 12px; border: 1px solid #e5e5e5; }
    .message.outbound .message-bubble { background: #f0f0f0; }
    .message-text { font-size: 14px; }
    .message-meta { display: flex; gap: 8px; align-items: center; margin-top: 4px; }
    .message-time { font-size: 11px; color: #999; }
    .msg-type-small { font-size: 10px; background: #e5e5e5; padding: 1px 4px; border-radius: 3px; }
    .compose-area { padding: 12px 16px; background: #fff; border-top: 1px solid #e5e5e5; }
    .no-chat { flex: 1; display: flex; align-items: center; justify-content: center; color: #666; }
    .compose-tab, .templates-tab { flex: 1; overflow-y: auto; padding: 24px; }
    .compose-form { max-width: 600px; margin: 0 auto; }
    .compose-form h3 { margin: 0 0 20px 0; }
    .form-group { margin-bottom: 16px; }
    .form-group label { display: block; font-weight: 500; margin-bottom: 6px; font-size: 14px; }
    .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px 12px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 14px; }
    .form-group textarea { resize: vertical; }
    .form-group .hint { font-size: 12px; color: #666; margin-top: 4px; display: block; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .checkbox-group label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
    .checkbox-group input[type="checkbox"] { width: 18px; height: 18px; }
    .send-btn { width: 100%; padding: 14px; background: #10b981; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 16px; }
    .send-btn:disabled { background: #9ca3af; cursor: not-allowed; }
    .config-section { max-width: 800px; margin: 0 auto; }
    .config-section h3 { margin: 0 0 8px 0; }
    .section-desc { color: #666; margin-bottom: 24px; }
    .config-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }
    .config-card { background: #f9f9f9; padding: 16px; border-radius: 12px; border: 1px solid #e5e5e5; }
    .config-card h4 { margin: 0 0 12px 0; font-size: 14px; }
    .config-card input, .config-card select { width: 100%; padding: 10px; border: 1px solid #e5e5e5; border-radius: 6px; }
    .config-hint { font-size: 12px; color: #666; margin-top: 8px; }
    .info-box { background: #f0fdf4; padding: 16px; border-radius: 12px; border: 1px solid #bbf7d0; }
    .info-box h4 { margin: 0 0 12px 0; color: #166534; }
    .info-box ul { margin: 0; padding-left: 20px; }
    .info-box li { margin-bottom: 8px; }
    .info-box a { color: #166534; text-decoration: none; }
    .info-box a:hover { text-decoration: underline; }
    .entity-info, .header-info, .templates-info { background: #f9f9f9; padding: 16px; border-radius: 12px; border: 1px solid #e5e5e5; margin-bottom: 20px; }
    .entity-info h4, .header-info h4, .templates-info h4 { margin: 0 0 12px 0; font-size: 14px; }
    .entity-details { display: flex; flex-direction: column; gap: 8px; }
    .entity-row { display: flex; gap: 12px; }
    .entity-row .label { color: #666; min-width: 100px; }
    .entity-row .value { font-weight: 500; }
    .entity-row .value.mono { font-family: monospace; background: #e5e5e5; padding: 2px 6px; border-radius: 4px; }
    .dlt-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .dlt-table th, .dlt-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e5e5e5; }
    .dlt-table th { background: #f0f0f0; font-weight: 600; font-size: 12px; }
    .dlt-table .mono { font-family: monospace; font-size: 11px; }
    .status-badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
    .status-badge.registered { background: #d1fae5; color: #065f46; }
    .use-btn { padding: 6px 12px; background: #10b981; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer; }
    .use-btn:hover { background: #059669; }
    .template-preview { margin-top: 16px; }
    .template-preview h5 { margin: 0 0 8px 0; font-size: 13px; color: #666; }
    .preview-box { background: #fff; padding: 12px; border-radius: 8px; border: 1px solid #e5e5e5; font-size: 13px; line-height: 1.5; color: #333; }
    @media (max-width: 768px) { 
      .sms-layout { grid-template-columns: 1fr; } 
      .sms-sidebar { display: none; }
      .form-row { grid-template-columns: 1fr; }
      .config-grid { grid-template-columns: 1fr; }
    }
  `;

  if (embedded) {
    return (
      <>
        {pageContent}
        <style jsx>{styles}</style>
      </>
    );
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      {pageContent}
      <style jsx>{styles}</style>
    </Layout>
  );
};

export default INSmsDM;