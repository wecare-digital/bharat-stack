/**
 * Voice Logs Page
 * View all voice call logs
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { API_BASE } from '../../../config/constants';
import Button from '../../../components/ui/Button';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface CallLog {
  callId: string;
  phone: string;
  status: string;
  duration: number;
  createdAt: number;
}

const ITEMS_PER_PAGE = 20;

const VoiceLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [filter, setFilter] = useState<'all' | 'answered' | 'completed' | 'failed'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/voice-aws/calls?limit=200`);
      if (response.ok) {
        const data = await response.json();
        setCalls((data.calls || []).sort((a: CallLog, b: CallLog) => b.createdAt - a.createdAt));
      }
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Reset page when filter or search changes
  useEffect(() => { setCurrentPage(1); }, [filter, searchQuery]);

  const filteredCalls = calls.filter(c => {
    const matchesFilter = filter === 'all' || c.status === filter;
    const matchesSearch = !searchQuery || c.phone?.includes(searchQuery);
    return matchesFilter && matchesSearch;
  });

  const totalPages = Math.ceil(filteredCalls.length / ITEMS_PER_PAGE);
  const paginatedCalls = filteredCalls.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = {
      answered: { bg: '#D1FAE5', color: '#065f46' },
      completed: { bg: '#ECFDF5', color: '#065f46' },
      failed: { bg: '#fef2f2', color: '#dc2626' },
      'no-answer': { bg: '#f5f5f5', color: '#6b7280' },
      busy: { bg: '#f5f5f5', color: '#6b7280' },
    };
    const s = styles[status] || { bg: '#f5f5f5', color: '#6b7280' };
    return <span style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, background: s.bg, color: s.color }}>{status}</span>;
  };

  const formatDuration = (seconds: number) => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice Logs | WECARE.DIGITAL" description="View voice call logs" />
      <div style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ margin: 0 }}>Voice Logs</h2>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
        </div>

        {/* Search and Filter Row */}
        <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search by phone..."
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
          <div style={{ display: 'flex', gap: '8px' }}>
            {(['all', 'answered', 'completed', 'failed'] as const).map(f => (
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
                {f} {f !== 'all' && `(${calls.filter(c => c.status === f).length})`}
              </button>
            ))}
          </div>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginBottom: '16px' }}>
            <button
              onClick={() => setCurrentPage(1)}
              disabled={currentPage === 1}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '28px', height: '28px',
                background: currentPage === 1 ? '#f9fafb' : '#ECFDF5',
                border: `1px solid ${currentPage === 1 ? '#e5e7eb' : '#A7F3D0'}`,
                borderRadius: '6px', fontSize: '12px',
                color: currentPage === 1 ? '#9ca3af' : '#10B981',
                cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                opacity: currentPage === 1 ? 0.4 : 1
              }}
            >««</button>
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '28px', height: '28px',
                background: currentPage === 1 ? '#f9fafb' : '#ECFDF5',
                border: `1px solid ${currentPage === 1 ? '#e5e7eb' : '#A7F3D0'}`,
                borderRadius: '6px', fontSize: '12px',
                color: currentPage === 1 ? '#9ca3af' : '#10B981',
                cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                opacity: currentPage === 1 ? 0.4 : 1
              }}
            >‹</button>
            <span style={{ fontSize: '12px', color: '#065f46', padding: '0 8px', fontWeight: 500 }}>
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '28px', height: '28px',
                background: currentPage === totalPages ? '#f9fafb' : '#ECFDF5',
                border: `1px solid ${currentPage === totalPages ? '#e5e7eb' : '#A7F3D0'}`,
                borderRadius: '6px', fontSize: '12px',
                color: currentPage === totalPages ? '#9ca3af' : '#10B981',
                cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                opacity: currentPage === totalPages ? 0.4 : 1
              }}
            >›</button>
            <button
              onClick={() => setCurrentPage(totalPages)}
              disabled={currentPage === totalPages}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '28px', height: '28px',
                background: currentPage === totalPages ? '#f9fafb' : '#ECFDF5',
                border: `1px solid ${currentPage === totalPages ? '#e5e7eb' : '#A7F3D0'}`,
                borderRadius: '6px', fontSize: '12px',
                color: currentPage === totalPages ? '#9ca3af' : '#10B981',
                cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                opacity: currentPage === totalPages ? 0.4 : 1
              }}
            >»»</button>
          </div>
        )}

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Phone</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Duration</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Date</th>
              </tr>
            </thead>
            <tbody>
              {paginatedCalls.map(c => (
                <tr key={c.callId} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '12px 16px', fontSize: '14px' }}>{c.phone}</td>
                  <td style={{ padding: '12px 16px' }}>{getStatusBadge(c.status)}</td>
                  <td style={{ padding: '12px 16px', fontSize: '14px' }}>{formatDuration(c.duration)}</td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>{new Date(c.createdAt * 1000).toLocaleString()}</td>
                </tr>
              ))}
              {filteredCalls.length === 0 && (
                <tr><td colSpan={4} style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>No voice logs found</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Bottom pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginTop: '16px' }}>
            <button
              onClick={() => setCurrentPage(1)}
              disabled={currentPage === 1}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '28px', height: '28px',
                background: currentPage === 1 ? '#f9fafb' : '#ECFDF5',
                border: `1px solid ${currentPage === 1 ? '#e5e7eb' : '#A7F3D0'}`,
                borderRadius: '6px', fontSize: '12px',
                color: currentPage === 1 ? '#9ca3af' : '#10B981',
                cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                opacity: currentPage === 1 ? 0.4 : 1
              }}
            >««</button>
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '28px', height: '28px',
                background: currentPage === 1 ? '#f9fafb' : '#ECFDF5',
                border: `1px solid ${currentPage === 1 ? '#e5e7eb' : '#A7F3D0'}`,
                borderRadius: '6px', fontSize: '12px',
                color: currentPage === 1 ? '#9ca3af' : '#10B981',
                cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                opacity: currentPage === 1 ? 0.4 : 1
              }}
            >‹</button>
            <span style={{ fontSize: '12px', color: '#065f46', padding: '0 8px', fontWeight: 500 }}>
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '28px', height: '28px',
                background: currentPage === totalPages ? '#f9fafb' : '#ECFDF5',
                border: `1px solid ${currentPage === totalPages ? '#e5e7eb' : '#A7F3D0'}`,
                borderRadius: '6px', fontSize: '12px',
                color: currentPage === totalPages ? '#9ca3af' : '#10B981',
                cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                opacity: currentPage === totalPages ? 0.4 : 1
              }}
            >›</button>
            <button
              onClick={() => setCurrentPage(totalPages)}
              disabled={currentPage === totalPages}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '28px', height: '28px',
                background: currentPage === totalPages ? '#f9fafb' : '#ECFDF5',
                border: `1px solid ${currentPage === totalPages ? '#e5e7eb' : '#A7F3D0'}`,
                borderRadius: '6px', fontSize: '12px',
                color: currentPage === totalPages ? '#9ca3af' : '#10B981',
                cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                opacity: currentPage === totalPages ? 0.4 : 1
              }}
            >»»</button>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default VoiceLogsPage;
