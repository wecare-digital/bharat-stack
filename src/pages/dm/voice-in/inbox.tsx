/**
 * Voice-IN Inbox Page - Airtel Voice Integration (C2C + OBD + CDR)
 * Click-to-Call, OBD Campaigns, and Call Detail Records
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import { SkeletonContact } from '../../../components/Skeleton';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }
interface Contact { id: string; name: string; phone: string; callCount: number; lastCall?: string; }
interface C2CCall { callId: string; contactId: string; fromNumber: string; toNumber: string; callerId: string; status: string; duration: number; recordingUrl?: string; correlationId?: string; createdAt: number; }
interface CDRRecord { id: string; vmSessionId: string; clientCorrelationId: string; callType: string; overallCallStatus: string; callerNumber: string; destinationNumber: string; durationSec: number; conversationDurationSec: number; hangupStatus: string; recordingURL?: string; circleNameCaller?: string; operatorNameCaller?: string; createdAt: number; }

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';
const CONTACTS_PER_PAGE = 20;

const VoiceInInbox: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<'c2c' | 'cdr'>('c2c');
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [c2cCalls, setC2cCalls] = useState<C2CCall[]>([]);
  const [cdrs, setCdrs] = useState<CDRRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [contactsPage, setContactsPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  
  const [showC2CModal, setShowC2CModal] = useState(false);
  const [c2cFromNumber, setC2cFromNumber] = useState('');
  const [c2cToNumber, setC2cToNumber] = useState('');
  const [c2cRecording, setC2cRecording] = useState(true);
  const [c2cCalling, setC2cCalling] = useState(false);
  
  const toast = useToastContext();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, c2cResponse, cdrResponse] = await Promise.all([
        api.listContacts(),
        fetch(`${API_BASE}/voice-in/c2c`).then(r => r.json()).catch(() => ({ calls: [] })),
        fetch(`${API_BASE}/voice-cdr-webhook`).then(r => r.json()).catch(() => ({ cdrs: [] }))
      ]);
      const calls = c2cResponse.calls || [];
      const cdrRecords = cdrResponse.cdrs || [];
      const displayContacts: Contact[] = contactsData.filter(c => c.phone).map(c => {
        const contactCalls = calls.filter((m: any) => m.toNumber?.includes(c.phone?.slice(-10)) || m.fromNumber?.includes(c.phone?.slice(-10)));
        const lastCall = contactCalls[0];
        return { id: c.contactId, name: c.name || c.phone || 'Unknown', phone: c.phone || '', callCount: contactCalls.length, lastCall: lastCall?.createdAt ? new Date(lastCall.createdAt * 1000).toISOString() : undefined };
      });
      setContacts(displayContacts);
      setC2cCalls(calls);
      setCdrs(cdrRecords);
    } catch (err) { console.error('Load error:', err); toast.error('Failed to load data'); } finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadData(); const interval = setInterval(loadData, 60000); return () => clearInterval(interval); }, [loadData]);
  useEffect(() => { setContactsPage(1); }, [searchQuery]);

  const filteredContacts = contacts.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.phone.includes(searchQuery));
  const totalContactPages = Math.ceil(filteredContacts.length / CONTACTS_PER_PAGE);
  const paginatedContacts = filteredContacts.slice((contactsPage - 1) * CONTACTS_PER_PAGE, contactsPage * CONTACTS_PER_PAGE);
  const filteredCalls = c2cCalls.filter(c => selectedContact && (c.toNumber?.includes(selectedContact.phone?.slice(-10)) || c.fromNumber?.includes(selectedContact.phone?.slice(-10))));

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try { for (const id of selectedIds) { await api.deleteContact(id); } toast.success(`Deleted ${selectedIds.size} contact(s)`); setSelectedIds(new Set()); setSelectedContact(null); await loadData(); } catch (err) { toast.error('Failed to delete contacts'); } finally { setDeleting(false); }
  };

  const toggleSelect = (id: string) => { const newSet = new Set(selectedIds); if (newSet.has(id)) newSet.delete(id); else newSet.add(id); setSelectedIds(newSet); };
  const formatDuration = (seconds: number) => { const mins = Math.floor(seconds / 60); const secs = Math.round(seconds % 60); return `${mins}:${secs.toString().padStart(2, '0')}`; };

  const handleC2CCall = async () => {
    if (!c2cFromNumber || !c2cToNumber) { toast.error('Both phone numbers are required'); return; }
    setC2cCalling(true);
    try {
      const response = await fetch(`${API_BASE}/voice-in/c2c`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ fromNumber: c2cFromNumber, toNumber: c2cToNumber, enableRecording: c2cRecording }) });
      const result = await response.json();
      if (result.callId) { toast.success('Click-to-Call initiated!'); setShowC2CModal(false); setC2cFromNumber(''); setC2cToNumber(''); await loadData(); } else { toast.error(result.error || 'Failed to initiate call'); }
    } catch (err) { toast.error('Failed to initiate call'); } finally { setC2cCalling(false); }
  };

  const tabItems: TabItem[] = [{ id: 'c2c', label: 'Click-to-Call' }, { id: 'cdr', label: 'Call Records (CDR)' }];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice-IN | Airtel IQ | WECARE.DIGITAL" description="Voice calls via Airtel IQ" />
      <div className="inbox-page">
        <div className="inbox-header">
          <div className="header-title"><PhoneIcon /><h2>Airtel IQ Voice</h2><span className="badge">C2C + CDR</span></div>
          <div className="inbox-actions">
            <Button variant="primary" onClick={() => setShowC2CModal(true)}>+ Click-to-Call</Button>
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>
        <div className="tabs-container"><Tabs items={tabItems} activeTab={activeTab} onChange={(id) => setActiveTab(id as 'c2c' | 'cdr')} /></div>
        <div className="inbox-layout">
          <div className="inbox-sidebar">
            <div className="sidebar-controls">
              <button onClick={handleDeleteSelected} disabled={selectedIds.size === 0 || deleting} title="Delete selected" className="delete-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
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
                    <div className="contact-name">{contact.name}{contact.callCount > 0 && <span className="call-badge">{contact.callCount}</span>}</div>
                    <div className="contact-phone">{contact.phone}</div>
                    <div className="contact-preview">{contact.lastCall ? new Date(contact.lastCall).toLocaleDateString() : 'No calls'}</div>
                  </div>
                </div>
              ))}
              {!loading && filteredContacts.length === 0 && <div className="empty-contacts">No contacts with phone</div>}
            </div>
          </div>
          <div className="inbox-messages">
            {activeTab === 'c2c' && (selectedContact ? (
              <>
                <div className="messages-header">
                  <div className="contact-avatar large">{selectedContact.name.charAt(0).toUpperCase()}</div>
                  <div><div className="contact-name">{selectedContact.name}</div><div className="contact-phone">{selectedContact.phone}</div></div>
                  <Button variant="primary" size="sm" onClick={() => { setC2cToNumber(selectedContact.phone); setShowC2CModal(true); }}>Call</Button>
                </div>
                <div className="messages-list">
                  {filteredCalls.map(call => (
                    <div key={call.callId} className="message-card outbound">
                      <div className="message-meta"><span className="message-direction">↗ Outgoing C2C</span><span className="message-time">{new Date(call.createdAt * 1000).toLocaleString()}</span></div>
                      <div className="message-content"><strong>Duration:</strong> {formatDuration(call.duration)}<span className="type-tag">C2C</span></div>
                      <div className="message-footer">
                        <span className={`status-badge ${call.status}`}>{call.status}</span>
                        {call.correlationId && <span className="correlation-id">ID: {call.correlationId.slice(0, 8)}...</span>}
                        {call.recordingUrl && <a href={call.recordingUrl} target="_blank" rel="noopener noreferrer" className="recording-link">🎙️ Recording</a>}
                      </div>
                    </div>
                  ))}
                  {filteredCalls.length === 0 && <div className="empty-messages">No call records with this contact</div>}
                </div>
              </>
            ) : (
              <div className="no-selection"><PhoneIcon /><p>Click-to-Call (C2C)</p><small>Connect two parties on a call via Airtel Kong API</small><Button variant="primary" onClick={() => setShowC2CModal(true)} style={{ marginTop: '1rem' }}>+ New C2C Call</Button></div>
            ))}
            {activeTab === 'cdr' && (
              <div className="cdr-content">
                <div className="cdr-header"><h3>Call Detail Records</h3><small>CDR webhook: POST /voice-cdr-webhook</small></div>
                <div className="cdr-info"><p>CDR events are received via webhook from Airtel and stored in DynamoDB.</p><code>https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook</code></div>
                <div className="all-calls">
                  {cdrs.slice(0, 20).map(cdr => (
                    <div key={cdr.id} className="cdr-row">
                      <span className="cdr-time">{new Date(cdr.createdAt * 1000).toLocaleString()}</span>
                      <span className={`cdr-status ${cdr.overallCallStatus?.toLowerCase()}`}>{cdr.overallCallStatus}</span>
                      <span className="cdr-duration">{formatDuration(cdr.durationSec)}</span>
                      <span className="cdr-type">{cdr.callType}</span>
                    </div>
                  ))}
                  {cdrs.length === 0 && <div className="empty-cdr">No CDR records yet</div>}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      {showC2CModal && (
        <div className="modal-overlay" onClick={() => setShowC2CModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Click-to-Call (C2C)</h3>
            <p className="modal-desc">Connect two parties on a call. First participant will be called, then connected to the second.</p>
            <div className="form-group"><label>From Number (First Participant) *</label><input type="tel" value={c2cFromNumber} onChange={e => setC2cFromNumber(e.target.value)} placeholder="10-digit mobile number" /></div>
            <div className="form-group"><label>To Number (Second Participant) *</label><input type="tel" value={c2cToNumber} onChange={e => setC2cToNumber(e.target.value)} placeholder="10-digit mobile number" /></div>
            <div className="form-group checkbox-group"><label><input type="checkbox" checked={c2cRecording} onChange={e => setC2cRecording(e.target.checked)} />Enable Call Recording</label></div>
            <div className="info-box"><strong>Airtel C2C Configuration:</strong><ul><li>Caller ID: 8047311032</li><li>API: iqvoice.airtel.in (Kong HMAC Auth)</li><li>App ID: WECAREDIG_fD4BKqUbC8k90jNrPR0n</li></ul></div>
            <div className="modal-actions"><Button variant="secondary" onClick={() => setShowC2CModal(false)}>Cancel</Button><Button variant="primary" onClick={handleC2CCall} loading={c2cCalling} disabled={!c2cFromNumber || !c2cToNumber}>Initiate Call</Button></div>
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
        .tabs-container { background: #fff; border-bottom: 1px solid #d1fae5; padding: 0 20px; }
        .inbox-layout { display: grid; grid-template-columns: 320px 1fr; flex: 1; overflow: hidden; }
        .inbox-sidebar { background: #fff; border-right: 1px solid #d1fae5; display: flex; flex-direction: column; }
        .sidebar-controls { display: flex; gap: 8px; padding: 12px; border-bottom: 1px solid #d1fae5; background: #ecfdf5; }
        .delete-btn { display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; background: #fff; border: 1px solid #10b981; border-radius: 13px; cursor: pointer; color: #10b981; flex-shrink: 0; transition: all 0.15s; }
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
        .call-badge { background: #10b981; color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }
        .contact-phone { font-size: 12px; color: #047857; }
        .contact-preview { font-size: 12px; color: #6ee7b7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px; }
        .empty-contacts { padding: 40px 20px; text-align: center; color: #047857; }
        .inbox-messages { display: flex; flex-direction: column; background: #f0fdf4; overflow-y: auto; }
        .messages-header { display: flex; align-items: center; gap: 12px; padding: 16px 20px; background: #fff; border-bottom: 1px solid #d1fae5; }
        .messages-list { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
        .message-card { background: #fff; border: 1px solid #d1fae5; border-radius: 12px; padding: 16px; }
        .message-card.inbound { border-left: 3px solid #10b981; background: #ecfdf5; }
        .message-card.outbound { border-left: 3px solid #059669; }
        .message-meta { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .message-direction { font-size: 12px; color: #047857; }
        .message-time { font-size: 12px; color: #9ca3af; }
        .message-content { font-size: 14px; line-height: 1.5; color: #374151; display: flex; align-items: center; gap: 12px; }
        .type-tag { background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
        .message-footer { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        .status-badge { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: #f5f5f5; color: #6b7280; }
        .status-badge.initiated, .status-badge.completed { background: #d1fae5; color: #059669; }
        .status-badge.failed { background: #fee2e2; color: #dc2626; }
        .correlation-id { font-size: 11px; color: #9ca3af; font-family: monospace; }
        .recording-link { font-size: 12px; color: #10b981; text-decoration: none; }
        .recording-link:hover { text-decoration: underline; }
        .empty-messages { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #047857; }
        .no-selection { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #047857; gap: 8px; padding: 40px; }
        .no-selection p { margin: 0; font-weight: 500; }
        .no-selection small { color: #6ee7b7; text-align: center; }
        .cdr-content { padding: 20px; }
        .cdr-header { margin-bottom: 20px; }
        .cdr-header h3 { margin: 0 0 4px 0; color: #065f46; }
        .cdr-header small { color: #047857; }
        .cdr-info { background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
        .cdr-info p { margin: 0 0 8px 0; color: #065f46; }
        .cdr-info code { display: block; background: #fff; padding: 8px; border-radius: 4px; font-size: 12px; word-break: break-all; color: #047857; border: 1px solid #d1fae5; }
        .all-calls { display: flex; flex-direction: column; gap: 8px; }
        .cdr-row { display: grid; grid-template-columns: 180px 100px 80px 80px; gap: 12px; padding: 12px; background: #fff; border: 1px solid #d1fae5; border-radius: 8px; font-size: 13px; }
        .cdr-time { color: #374151; }
        .cdr-status { text-transform: capitalize; }
        .cdr-status.initiated, .cdr-status.completed, .cdr-status.success { color: #059669; }
        .cdr-status.failed { color: #dc2626; }
        .cdr-duration { color: #047857; }
        .cdr-type { color: #6ee7b7; text-transform: uppercase; font-size: 11px; }
        .empty-cdr { padding: 40px; text-align: center; color: #047857; }
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .modal-content { background: #fff; border-radius: 12px; padding: 24px; width: 100%; max-width: 480px; max-height: 90vh; overflow-y: auto; }
        .modal-content h3 { margin: 0 0 8px 0; color: #065f46; }
        .modal-desc { margin: 0 0 20px 0; color: #047857; font-size: 14px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #374151; }
        .form-group input[type="tel"], .form-group input[type="text"] { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; }
        .form-group input:focus { outline: none; border-color: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2); }
        .checkbox-group label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
        .checkbox-group input[type="checkbox"] { width: 18px; height: 18px; accent-color: #10b981; }
        .info-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px; margin-bottom: 16px; }
        .info-box strong { display: block; margin-bottom: 8px; color: #166534; }
        .info-box ul { margin: 0; padding-left: 20px; font-size: 13px; color: #166534; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px; }
      `}</style>
    </Layout>
  );
};

const PhoneIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>
  </svg>
);

export default VoiceInInbox;
