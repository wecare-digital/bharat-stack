/**
 * SMS IN Messages Page
 * Inbound SMS messages via Airtel IQ
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { EmptyState } from '../../../components/ui';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const ITEMS_PER_PAGE = 20;

const SmsInMessagesPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<api.Message[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listMessages(undefined, 'SMS');
      const inbound = data.filter(m => m.direction === 'INBOUND');
      setMessages(inbound.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()));
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Reset page when search changes
  useEffect(() => { setCurrentPage(1); }, [searchQuery]);

  const filteredMessages = messages.filter(m =>
    m.content?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    m.contactId?.includes(searchQuery)
  );

  const totalPages = Math.ceil(filteredMessages.length / ITEMS_PER_PAGE);
  const paginatedMessages = filteredMessages.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try {
      for (const id of selectedIds) {
        await api.deleteMessage(id, 'INBOUND');
      }
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

  // Pagination button style helper
  const getPaginationBtnStyle = (disabled: boolean) => ({
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    width: '28px', height: '28px',
    background: disabled ? '#f9fafb' : '#ECFDF5',
    border: `1px solid ${disabled ? '#e5e7eb' : '#A7F3D0'}`,
    borderRadius: '6px', fontSize: '12px',
    color: disabled ? '#9ca3af' : '#10B981',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.4 : 1
  });

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS IN Messages | WECARE.DIGITAL" description="Inbound SMS messages" />
      <div style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ margin: 0 }}>SMS IN - Messages</h2>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
        </div>

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
            placeholder="Search messages..."
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
          <span style={{ fontSize: '12px', color: '#065f46', padding: '0 8px', fontWeight: 500 }}>Page {currentPage} of {totalPages || 1}</span>
          <button onClick={() => setCurrentPage(p => Math.min(totalPages || 1, p + 1))} disabled={currentPage >= (totalPages || 1)} style={getPaginationBtnStyle(currentPage >= (totalPages || 1))}>›</button>
          <button onClick={() => setCurrentPage(totalPages || 1)} disabled={currentPage >= (totalPages || 1)} style={getPaginationBtnStyle(currentPage >= (totalPages || 1))}>»»</button>
        </div>

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', overflow: 'hidden' }}>
          {filteredMessages.length === 0 ? (
            <EmptyState
              icon="📥"
              title="No Inbound SMS"
              description="Inbound SMS messages will appear here"
            />
          ) : (
            <div style={{ padding: '8px' }}>
              {paginatedMessages.map(m => (
                <div 
                  key={m.messageId} 
                  style={{ 
                    display: 'flex', 
                    alignItems: 'flex-start', 
                    gap: '12px',
                    padding: '16px',
                    borderBottom: '1px solid #f3f4f6',
                    background: selectedIds.has(m.messageId) ? '#ECFDF5' : 'transparent'
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(m.messageId)}
                    onChange={() => toggleSelect(m.messageId)}
                    style={{ accentColor: '#10B981', marginTop: '4px' }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontWeight: 600, fontSize: '14px', color: '#111827' }}>{m.contactId}</span>
                      <span style={{ fontSize: '12px', color: '#6b7280' }}>{new Date(m.timestamp).toLocaleString()}</span>
                    </div>
                    <p style={{ margin: 0, fontSize: '14px', color: '#374151', lineHeight: 1.5 }}>{m.content}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Bottom pagination - Always visible */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginTop: '16px' }}>
          <button onClick={() => setCurrentPage(1)} disabled={currentPage === 1} style={getPaginationBtnStyle(currentPage === 1)}>««</button>
          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} style={getPaginationBtnStyle(currentPage === 1)}>‹</button>
          <span style={{ fontSize: '12px', color: '#065f46', padding: '0 8px', fontWeight: 500 }}>Page {currentPage} of {totalPages || 1}</span>
          <button onClick={() => setCurrentPage(p => Math.min(totalPages || 1, p + 1))} disabled={currentPage >= (totalPages || 1)} style={getPaginationBtnStyle(currentPage >= (totalPages || 1))}>›</button>
          <button onClick={() => setCurrentPage(totalPages || 1)} disabled={currentPage >= (totalPages || 1)} style={getPaginationBtnStyle(currentPage >= (totalPages || 1))}>»»</button>
        </div>
      </div>
    </Layout>
  );
};

export default SmsInMessagesPage;
