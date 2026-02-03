/**
 * Voice Inbox Page
 * Inbox view for voice calls via AWS Connect
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Breadcrumbs from '../../../components/ui/Breadcrumbs';
import Button from '../../../components/ui/Button';
import { SkeletonContact } from '../../../components/Skeleton';
import { useToastContext } from '../../../contexts/ToastContext';
import { API_BASE } from '../../../config/constants';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface Contact {
  id: string;
  name: string;
  phone: string;
  lastCall?: string;
  callCount: number;
}

interface VoiceCall {
  id: string;
  callId: string;
  phoneNumber: string;
  status: string;
  duration: number;
  callType: string;
  voiceId?: string;
  messageText?: string;
  createdAt: number;
}

const CONTACTS_PER_PAGE = 20;

const VoiceInbox: React.FC<PageProps> = ({ signOut, user }) => {
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [calls, setCalls] = useState<VoiceCall[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [contactsPage, setContactsPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const toast = useToastContext();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, callsResponse] = await Promise.all([
        api.listContacts(),
        fetch(`${API_BASE}/voice-aws/calls?limit=100`),
      ]);

      let callsData: VoiceCall[] = [];
      if (callsResponse.ok) {
        const data = await callsResponse.json();
        callsData = data.calls || [];
      }

      const displayContacts: Contact[] = contactsData
        .filter(c => c.phone)
        .map(c => {
          const contactCalls = callsData.filter(call => call.phoneNumber === c.phone);
          const lastCall = contactCalls[0];
          return {
            id: c.contactId,
            name: c.name || c.phone || 'Unknown',
            phone: c.phone || '',
            lastCall: lastCall ? new Date(lastCall.createdAt * 1000).toLocaleString() : undefined,
            callCount: contactCalls.length,
          };
        });

      setContacts(displayContacts);
      setCalls(callsData);
    } catch (err) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); const interval = setInterval(loadData, 60000); return () => clearInterval(interval); }, [loadData]);
  useEffect(() => { setContactsPage(1); }, [searchQuery]);

  const filteredContacts = contacts.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.phone.includes(searchQuery));
  const totalContactPages = Math.ceil(filteredContacts.length / CONTACTS_PER_PAGE);
  const paginatedContacts = filteredContacts.slice((contactsPage - 1) * CONTACTS_PER_PAGE, contactsPage * CONTACTS_PER_PAGE);
  const filteredCalls = calls.filter(c => selectedContact && c.phoneNumber === selectedContact.phone);

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try { for (const id of selectedIds) { await api.deleteContact(id); } toast.success(`Deleted ${selectedIds.size} contact(s)`); setSelectedIds(new Set()); setSelectedContact(null); await loadData(); } catch (err) { toast.error('Failed to delete contacts'); } finally { setDeleting(false); }
  };

  const toggleSelect = (id: string) => { const newSet = new Set(selectedIds); if (newSet.has(id)) newSet.delete(id); else newSet.add(id); setSelectedIds(newSet); };

  const formatDuration = (seconds: number) => { if (!seconds) return '-'; const mins = Math.floor(seconds / 60); const secs = seconds % 60; return `${mins}:${secs.toString().padStart(2, '0')}`; };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = { completed: { bg: '#ECFDF5', color: '#065f46' }, answered: { bg: '#D1FAE5', color: '#065f46' }, failed: { bg: '#fef2f2', color: '#dc2626' }, busy: { bg: '#fef2f2', color: '#dc2626' }, no_answer: { bg: '#f5f5f5', color: '#6b7280' }, initiated: { bg: '#fef3c7', color: '#92400e' }, ringing: { bg: '#dbeafe', color: '#1e40af' } };
    const s = styles[status?.toLowerCase()] || { bg: '#f5f5f5', color: '#6b7280' };
    return <span style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, background: s.bg, color: s.color }}>{status}</span>;
  };

  const getPaginationBtnStyle = (disabled: boolean) => ({ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '28px', height: '28px', background: disabled ? '#f9fafb' : '#ECFDF5', border: `1px solid ${disabled ? '#e5e7eb' : '#A7F3D0'}`, borderRadius: '6px', fontSize: '12px', color: disabled ? '#9ca3af' : '#10B981', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.4 : 1 });

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice Inbox | WECARE.DIGITAL" description="Voice calls inbox via AWS Connect" />
      <div style={{ height: 'calc(100vh - 60px)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '12px 20px', background: '#fff', borderBottom: '1px solid #e5e7eb' }}>
          <Breadcrumbs />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '24px', color: '#10B981' }}>📞</span>
              <div><h1 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>Voice Inbox</h1><span style={{ fontSize: '13px', color: '#6b7280' }}>AWS Connect</span></div>
            </div>
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', flex: 1, overflow: 'hidden' }}>
          <div style={{ background: '#fff', borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '12px', borderBottom: '1px solid #e5e7eb' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button onClick={handleDeleteSelected} disabled={selectedIds.size === 0 || deleting} title="Delete selected" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '36px', height: '36px', background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '8px', cursor: selectedIds.size === 0 ? 'not-allowed' : 'pointer', opacity: selectedIds.size === 0 ? 0.5 : 1, color: '#10B981', flexShrink: 0 }} onMouseEnter={e => { if (selectedIds.size > 0) { e.currentTarget.style.background = '#fef2f2'; e.currentTarget.style.borderColor = '#dc2626'; e.currentTarget.style.color = '#dc2626'; }}} onMouseLeave={e => { e.currentTarget.style.background = '#ECFDF5'; e.currentTarget.style.borderColor = '#A7F3D0'; e.currentTarget.style.color = '#10B981'; }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
                </button>
                <input type="text" placeholder="Search contacts..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} style={{ flex: 1, padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '13px' }} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #f3f4f6' }}>
                <button onClick={() => setContactsPage(1)} disabled={contactsPage === 1} style={getPaginationBtnStyle(contactsPage === 1)}>««</button>
                <button onClick={() => setContactsPage(p => Math.max(1, p - 1))} disabled={contactsPage === 1} style={getPaginationBtnStyle(contactsPage === 1)}>‹</button>
                <span style={{ fontSize: '12px', color: '#065f46', padding: '0 8px', fontWeight: 500 }}>Page {contactsPage} of {totalContactPages || 1}</span>
                <button onClick={() => setContactsPage(p => Math.min(totalContactPages || 1, p + 1))} disabled={contactsPage >= (totalContactPages || 1)} style={getPaginationBtnStyle(contactsPage >= (totalContactPages || 1))}>›</button>
                <button onClick={() => setContactsPage(totalContactPages || 1)} disabled={contactsPage >= (totalContactPages || 1)} style={getPaginationBtnStyle(contactsPage >= (totalContactPages || 1))}>»»</button>
              </div>
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} style={{ padding: '12px 16px' }}>
                    <SkeletonContact />
                  </div>
                ))
              ) : paginatedContacts.map(contact => (
                <div key={contact.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '12px 16px', cursor: 'pointer', borderBottom: '1px solid #f5f5f5', background: selectedContact?.id === contact.id ? '#ECFDF5' : selectedIds.has(contact.id) ? '#f0fdf4' : 'transparent' }} onClick={() => setSelectedContact(contact)}>
                  <input type="checkbox" checked={selectedIds.has(contact.id)} onChange={() => toggleSelect(contact.id)} onClick={e => e.stopPropagation()} style={{ accentColor: '#10B981', marginTop: '12px' }} />
                  <div style={{ width: '40px', height: '40px', background: '#D1FAE5', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 500, color: '#065f46', flexShrink: 0 }}>{contact.name.charAt(0).toUpperCase()}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '14px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>{contact.name}{contact.callCount > 0 && <span style={{ background: '#10B981', color: '#fff', fontSize: '11px', padding: '2px 6px', borderRadius: '10px' }}>{contact.callCount}</span>}</div>
                    <div style={{ fontSize: '12px', color: '#6b7280' }}>{contact.phone}</div>
                    <div style={{ fontSize: '12px', color: '#9ca3af', marginTop: '4px' }}>{contact.lastCall || 'No calls'}</div>
                  </div>
                </div>
              ))}
              {!loading && filteredContacts.length === 0 && <div style={{ padding: '40px 20px', textAlign: 'center', color: '#6b7280' }}>No contacts with phone</div>}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', background: '#f9fafb' }}>
            {selectedContact ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', background: '#fff', borderBottom: '1px solid #e5e7eb' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ width: '44px', height: '44px', background: '#D1FAE5', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 500, color: '#065f46' }}>{selectedContact.name.charAt(0).toUpperCase()}</div>
                    <div><div style={{ fontWeight: 500 }}>{selectedContact.name}</div><div style={{ fontSize: '12px', color: '#6b7280' }}>{selectedContact.phone}</div></div>
                  </div>
                </div>
                <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {filteredCalls.map(call => (
                    <div key={call.id} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '16px', borderLeft: '3px solid #10B981' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span style={{ fontSize: '12px', color: '#6b7280' }}>↗ Outbound Call</span>
                        <span style={{ fontSize: '12px', color: '#9ca3af' }}>{new Date(call.createdAt * 1000).toLocaleString()}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '8px' }}>
                        {getStatusBadge(call.status)}
                        <span style={{ fontSize: '14px', color: '#374151' }}>Duration: {formatDuration(call.duration)}</span>
                      </div>
                      {call.messageText && <div style={{ fontSize: '14px', lineHeight: 1.5, color: '#374151', background: '#f9fafb', padding: '8px 12px', borderRadius: '6px' }}>{call.messageText}</div>}
                      {call.voiceId && <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px' }}>Voice: {call.voiceId}</div>}
                    </div>
                  ))}
                  {filteredCalls.length === 0 && <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#6b7280' }}>No calls with this contact</div>}
                </div>
              </>
            ) : (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#6b7280' }}><div style={{ fontSize: '48px', marginBottom: '16px' }}>📞</div><p style={{ margin: 0 }}>Select a contact</p><small>Choose a contact to view call history</small></div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default VoiceInbox;
