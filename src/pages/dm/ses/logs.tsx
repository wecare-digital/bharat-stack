/**
 * Email Logs Page
 * AWS SES email logs
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Breadcrumbs from '../../../components/ui/Breadcrumbs';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
}

const ITEMS_PER_PAGE = 20;

const EmailLogsPage: React.FC<PageProps> = ({ signOut, user, embedded }) => {
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<api.Message[]>([]);
  const [filter, setFilter] = useState<'all' | 'sent' | 'delivered' | 'failed'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listMessages(undefined, 'EMAIL');
      setMessages(data.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()));
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Reset page when filter or search changes
  useEffect(() => { setCurrentPage(1); }, [filter, searchQuery]);

  const filteredMessages = messages.filter(m => {
    const matchesFilter = filter === 'all' || m.status === filter;
    const matchesSearch = !searchQuery || 
      m.contactId?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.content?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const totalPages = Math.ceil(filteredMessages.length / ITEMS_PER_PAGE);
  const paginatedMessages = filteredMessages.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = {
      sent: { bg: '#ECFDF5', color: '#065f46' },
      delivered: { bg: '#D1FAE5', color: '#065f46' },
      opened: { bg: '#D1FAE5', color: '#065f46' },
      failed: { bg: '#ECFDF5', color: '#059669' },
      bounced: { bg: '#ECFDF5', color: '#059669' },
      pending: { bg: '#f5f5f5', color: '#6b7280' },
    };
    const s = styles[status] || styles.pending;
    return <span style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, background: s.bg, color: s.color }}>{status}</span>;
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try {
      for (const id of selectedIds) {
        await api.deleteMessage(id, 'OUTBOUND');
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

  const content = (
      <div style={{ padding: '20px' }}>
        <Breadcrumbs />
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', marginTop: '12px' }}>
          <h2 style={{ margin: 0 }}>Email Logs</h2>
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
            onMouseEnter={e => { if (selectedIds.size > 0) { e.currentTarget.style.background = '#ECFDF5'; e.currentTarget.style.borderColor = '#059669'; e.currentTarget.style.color = '#059669'; }}}
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
            placeholder="Search emails..."
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

        {/* Filter Row */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
          {(['all', 'sent', 'delivered', 'failed'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '8px 16px',
                border: '1.5px solid #10B981',
                borderRadius: '13px',
                background: filter === f ? '#D1FAE5' : '#fff',
                color: '#111827',
                fontWeight: filter === f ? 600 : 500,
                cursor: 'pointer',
                textTransform: 'capitalize'
              }}
            >
              {f} {f !== 'all' && `(${messages.filter(m => m.status === f).length})`}
            </button>
          ))}
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
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', width: '40px' }}>
                  <input
                    type="checkbox"
                    checked={paginatedMessages.length > 0 && paginatedMessages.every(m => selectedIds.has(m.messageId))}
                    onChange={e => {
                      if (e.target.checked) {
                        const newSet = new Set(selectedIds);
                        paginatedMessages.forEach(m => newSet.add(m.messageId));
                        setSelectedIds(newSet);
                      } else {
                        const newSet = new Set(selectedIds);
                        paginatedMessages.forEach(m => newSet.delete(m.messageId));
                        setSelectedIds(newSet);
                      }
                    }}
                    style={{ accentColor: '#10B981' }}
                  />
                </th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>To</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Subject</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Date</th>
              </tr>
            </thead>
            <tbody>
              {paginatedMessages.map(m => (
                <tr key={m.messageId} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '12px 16px' }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(m.messageId)}
                      onChange={() => toggleSelect(m.messageId)}
                      style={{ accentColor: '#10B981' }}
                    />
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: '14px' }}>{m.contactId}</td>
                  <td style={{ padding: '12px 16px', fontSize: '14px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.content}</td>
                  <td style={{ padding: '12px 16px' }}>{getStatusBadge(m.status)}</td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>{new Date(m.timestamp).toLocaleString()}</td>
                </tr>
              ))}
              {filteredMessages.length === 0 && (
                <tr><td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>No email logs found</td></tr>
              )}
            </tbody>
          </table>
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
  );

  if (embedded) return content;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Email Logs | WECARE.DIGITAL" description="View email logs" />
      {content}
    </Layout>
  );
};

export default EmailLogsPage;
