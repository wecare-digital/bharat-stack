/**
 * Voice AWS Page
 * Make and view voice calls via AWS Connect
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { EmptyState } from '../../../components/ui';
import Button from '../../../components/ui/Button';
import { API_BASE } from '../../../config/constants';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface VoiceCall {
  id: string;
  callId: string;
  contactId: string;
  phoneNumber: string;
  callType: string;
  status: string;
  direction: string;
  duration: number;
  voiceId?: string;
  messageText?: string;
  connectContactId?: string;
  createdAt: number;
  updatedAt: number;
}

const ITEMS_PER_PAGE = 20;

// AWS Polly voice options
const POLLY_VOICES = [
  { id: 'Joanna', name: 'Joanna (US Female)', lang: 'en-US' },
  { id: 'Matthew', name: 'Matthew (US Male)', lang: 'en-US' },
  { id: 'Amy', name: 'Amy (UK Female)', lang: 'en-GB' },
  { id: 'Brian', name: 'Brian (UK Male)', lang: 'en-GB' },
  { id: 'Aditi', name: 'Aditi (Indian Female)', lang: 'hi-IN' },
  { id: 'Raveena', name: 'Raveena (Indian Female)', lang: 'en-IN' },
  { id: 'Kajal', name: 'Kajal (Indian Female)', lang: 'en-IN' },
];

const VoiceAwsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [calling, setCalling] = useState(false);
  const [calls, setCalls] = useState<VoiceCall[]>([]);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  
  // Call form state
  const [showCallForm, setShowCallForm] = useState(false);
  const [selectedContact, setSelectedContact] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [callType, setCallType] = useState<'tts' | 'audio'>('tts');
  const [messageText, setMessageText] = useState('');
  const [voiceId, setVoiceId] = useState('Joanna');
  const [audioUrl, setAudioUrl] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch voice calls from voice-aws Lambda
      const response = await fetch(`${API_BASE}/voice-aws/calls?limit=100`);
      if (response.ok) {
        const data = await response.json();
        setCalls(data.calls || []);
      }
      
      // Also load contacts for the call form
      const contactsData = await api.listContacts();
      setContacts(contactsData);
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Reset page when search changes
  useEffect(() => { setCurrentPage(1); }, [searchQuery]);

  const filteredCalls = calls.filter(c =>
    c.phoneNumber?.includes(searchQuery) ||
    c.contactId?.includes(searchQuery) ||
    c.messageText?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalPages = Math.ceil(filteredCalls.length / ITEMS_PER_PAGE) || 1;
  const paginatedCalls = filteredCalls.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const handleMakeCall = async () => {
    if ((!selectedContact && !phoneNumber.trim()) || (callType === 'tts' && !messageText.trim())) return;
    
    setCalling(true);
    try {
      const response = await fetch(`${API_BASE}/voice-aws/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contactId: selectedContact || undefined,
          phoneNumber: phoneNumber || undefined,
          callType,
          messageText: callType === 'tts' ? messageText : undefined,
          voiceId: callType === 'tts' ? voiceId : undefined,
          audioUrl: callType === 'audio' ? audioUrl : undefined,
        }),
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`Call initiated! Call ID: ${result.callId}`);
        setMessageText('');
        setPhoneNumber('');
        setSelectedContact('');
        setAudioUrl('');
        setShowCallForm(false);
        await loadData();
      } else {
        const error = await response.json();
        alert(`Failed to make call: ${error.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Call error:', err);
      alert('Failed to initiate call');
    } finally {
      setCalling(false);
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try {
      // Delete logic would go here
      setSelectedIds(new Set());
      await loadData();
    } catch (err) {
      console.error('Delete error:', err);
    } finally {
      setDeleting(false);
    }
  };

  const toggleSelect = (id: string) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedIds(newSet);
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = {
      initiated: { bg: '#fef3c7', color: '#92400e' },
      ringing: { bg: '#dbeafe', color: '#1e40af' },
      answered: { bg: '#D1FAE5', color: '#065f46' },
      completed: { bg: '#ECFDF5', color: '#065f46' },
      failed: { bg: '#fef2f2', color: '#dc2626' },
      busy: { bg: '#fef2f2', color: '#dc2626' },
      no_answer: { bg: '#f5f5f5', color: '#6b7280' },
    };
    const s = styles[status?.toLowerCase()] || { bg: '#f5f5f5', color: '#6b7280' };
    return <span style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, background: s.bg, color: s.color }}>{status}</span>;
  };

  const formatDuration = (seconds: number) => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Pagination button style helper
  const getPaginationBtnStyle = (disabled: boolean) => ({
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    width: '28px', height: '28px',
    background: disabled ? '#f9fafb' : '#ECFDF5',
    border: `1px solid ${disabled ? '#e5e7eb' : '#A7F3D0'}`,
    borderRadius: '6px', fontSize: '12px',
    color: disabled ? '#9ca3af' : '#10B981',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1
  });

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice AWS | WECARE.DIGITAL" description="Make voice calls via AWS Connect" />
      <div style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ margin: 0 }}>Voice - AWS Connect</h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button variant="primary" onClick={() => setShowCallForm(!showCallForm)}>
              {showCallForm ? 'Cancel' : '📞 Make Call'}
            </Button>
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>

        {/* Make Call Form */}
        {showCallForm && (
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '20px', marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '16px' }}>Make Voice Call via AWS Connect</h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px', color: '#374151' }}>
                  Select Contact
                </label>
                <select
                  value={selectedContact}
                  onChange={e => { setSelectedContact(e.target.value); setPhoneNumber(''); }}
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '14px' }}
                >
                  <option value="">-- Select Contact --</option>
                  {contacts.filter(c => c.phone).map(c => (
                    <option key={c.contactId} value={c.contactId}>{c.name} ({c.phone})</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px', color: '#374151' }}>
                  Or Enter Phone Number
                </label>
                <input
                  type="tel"
                  value={phoneNumber}
                  onChange={e => { setPhoneNumber(e.target.value); setSelectedContact(''); }}
                  placeholder="+1234567890"
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box' }}
                />
              </div>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px', color: '#374151' }}>
                  Call Type
                </label>
                <select
                  value={callType}
                  onChange={e => setCallType(e.target.value as 'tts' | 'audio')}
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '14px' }}
                >
                  <option value="tts">Text-to-Speech (TTS)</option>
                  <option value="audio">Pre-recorded Audio</option>
                </select>
              </div>
              
              {callType === 'tts' && (
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px', color: '#374151' }}>
                    Voice (AWS Polly)
                  </label>
                  <select
                    value={voiceId}
                    onChange={e => setVoiceId(e.target.value)}
                    style={{ width: '100%', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '14px' }}
                  >
                    {POLLY_VOICES.map(v => (
                      <option key={v.id} value={v.id}>{v.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            
            {callType === 'tts' ? (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px', color: '#374151' }}>
                  Message to Speak
                </label>
                <textarea
                  value={messageText}
                  onChange={e => setMessageText(e.target.value)}
                  placeholder="Enter the message to be spoken..."
                  rows={3}
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '14px', resize: 'vertical', boxSizing: 'border-box' }}
                />
              </div>
            ) : (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px', color: '#374151' }}>
                  Audio URL (S3 or public URL)
                </label>
                <input
                  type="url"
                  value={audioUrl}
                  onChange={e => setAudioUrl(e.target.value)}
                  placeholder="https://s3.amazonaws.com/bucket/audio.mp3"
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box' }}
                />
              </div>
            )}
            
            <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '12px', marginBottom: '16px' }}>
              <p style={{ margin: 0, fontSize: '13px', color: '#92400e' }}>
                ⚠️ <strong>Note:</strong> AWS Connect must be configured with Instance ID, Contact Flow ID, and Source Phone Number for calls to work.
              </p>
            </div>
            
            <Button 
              variant="primary" 
              onClick={handleMakeCall} 
              disabled={calling || (!selectedContact && !phoneNumber) || (callType === 'tts' && !messageText.trim())}
              loading={calling}
            >
              📞 Initiate Call
            </Button>
          </div>
        )}

        {/* Search and Delete Row */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
          <button
            onClick={handleDeleteSelected}
            disabled={selectedIds.size === 0 || deleting}
            title="Delete selected"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: '40px', height: '40px',
              background: selectedIds.size === 0 ? '#f9fafb' : '#ECFDF5',
              border: `1.5px solid ${selectedIds.size === 0 ? '#e5e7eb' : '#A7F3D0'}`,
              borderRadius: '10px',
              cursor: selectedIds.size === 0 ? 'not-allowed' : 'pointer',
              opacity: selectedIds.size === 0 ? 0.5 : 1,
              transition: 'all 0.15s ease',
              color: selectedIds.size === 0 ? '#9ca3af' : '#10B981'
            }}
            onMouseEnter={e => { if (selectedIds.size > 0) { e.currentTarget.style.background = '#fef2f2'; e.currentTarget.style.borderColor = '#ef4444'; e.currentTarget.style.color = '#ef4444'; }}}
            onMouseLeave={e => { e.currentTarget.style.background = selectedIds.size === 0 ? '#f9fafb' : '#ECFDF5'; e.currentTarget.style.borderColor = selectedIds.size === 0 ? '#e5e7eb' : '#A7F3D0'; e.currentTarget.style.color = selectedIds.size === 0 ? '#9ca3af' : '#10B981'; }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              <line x1="10" y1="11" x2="10" y2="17"></line>
              <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>
          </button>
          <input
            type="text"
            placeholder="Search calls..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              fontSize: '13px',
              width: '200px',
              transition: 'all 0.15s ease'
            }}
          />
        </div>

        {/* Pagination - Always visible */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginBottom: '16px' }}>
          <button onClick={() => setCurrentPage(1)} disabled={currentPage === 1} style={getPaginationBtnStyle(currentPage === 1)}>««</button>
          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} style={getPaginationBtnStyle(currentPage === 1)}>‹</button>
          <span style={{ fontSize: '12px', color: '#065f46', padding: '0 8px', fontWeight: 500 }}>Page {currentPage} of {totalPages}</span>
          <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage >= totalPages} style={getPaginationBtnStyle(currentPage >= totalPages)}>›</button>
          <button onClick={() => setCurrentPage(totalPages)} disabled={currentPage >= totalPages} style={getPaginationBtnStyle(currentPage >= totalPages)}>»»</button>
        </div>

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', overflow: 'hidden' }}>
          {filteredCalls.length === 0 ? (
            <EmptyState
              icon="📞"
              title="No Voice Calls"
              description="Make your first voice call using AWS Connect"
            />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', width: '40px' }}>
                    <input
                      type="checkbox"
                      checked={paginatedCalls.length > 0 && paginatedCalls.every(c => selectedIds.has(c.id))}
                      onChange={e => {
                        if (e.target.checked) {
                          const newSet = new Set(selectedIds);
                          paginatedCalls.forEach(c => newSet.add(c.id));
                          setSelectedIds(newSet);
                        } else {
                          const newSet = new Set(selectedIds);
                          paginatedCalls.forEach(c => newSet.delete(c.id));
                          setSelectedIds(newSet);
                        }
                      }}
                      style={{ accentColor: '#10B981' }}
                    />
                  </th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Phone</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Type</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Status</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Duration</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Voice</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Date</th>
                </tr>
              </thead>
              <tbody>
                {paginatedCalls.map(c => (
                  <tr key={c.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                    <td style={{ padding: '12px 16px' }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(c.id)}
                        onChange={() => toggleSelect(c.id)}
                        style={{ accentColor: '#10B981' }}
                      />
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '14px' }}>{c.phoneNumber}</td>
                    <td style={{ padding: '12px 16px', fontSize: '12px', color: '#6b7280', textTransform: 'uppercase' }}>{c.callType}</td>
                    <td style={{ padding: '12px 16px' }}>{getStatusBadge(c.status)}</td>
                    <td style={{ padding: '12px 16px', fontSize: '14px' }}>{formatDuration(c.duration)}</td>
                    <td style={{ padding: '12px 16px', fontSize: '12px', color: '#6b7280' }}>{c.voiceId || '-'}</td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>{new Date(c.createdAt * 1000).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Bottom pagination - Always visible */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginTop: '16px' }}>
          <button onClick={() => setCurrentPage(1)} disabled={currentPage === 1} style={getPaginationBtnStyle(currentPage === 1)}>««</button>
          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} style={getPaginationBtnStyle(currentPage === 1)}>‹</button>
          <span style={{ fontSize: '12px', color: '#065f46', padding: '0 8px', fontWeight: 500 }}>Page {currentPage} of {totalPages}</span>
          <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage >= totalPages} style={getPaginationBtnStyle(currentPage >= totalPages)}>›</button>
          <button onClick={() => setCurrentPage(totalPages)} disabled={currentPage >= totalPages} style={getPaginationBtnStyle(currentPage >= totalPages)}>»»</button>
        </div>
      </div>
    </Layout>
  );
};

export default VoiceAwsPage;
