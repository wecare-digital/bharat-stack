/**
 * Voice Logs Page
 * AWS Connect voice call logs
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Breadcrumbs from '../../../components/ui/Breadcrumbs';
import { SkeletonTable } from '../../../components/Skeleton';
import { useToastContext } from '../../../contexts/ToastContext';
import { API_BASE } from '../../../config/constants';
import Button from '../../../components/ui/Button';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface VoiceCall {
  id: string;
  callId: string;
  phoneNumber: string;
  status: string;
  duration: number;
  callType: string;
  voiceId?: string;
  createdAt: number;
}

const ITEMS_PER_PAGE = 20;

const VoiceLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [calls, setCalls] = useState<VoiceCall[]>([]);
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/voice-aws/calls?limit=100`);
      if (response.ok) {
        const data = await response.json();
        setCalls((data.calls || []).sort((a: VoiceCall, b: VoiceCall) => b.createdAt - a.createdAt));
      }
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { setCurrentPage(1); }, [filter, searchQuery]);

  const filteredCalls = calls.filter(c => {
    const matchesFilter = filter === 'all' || (filter === 'completed' && ['completed', 'answered'].includes(c.status?.toLowerCase())) || (filter === 'failed' && ['failed', 'busy', 'no_answer'].includes(c.status?.toLowerCase()));
    const matchesSearch = !searchQuery || c.phoneNumber?.includes(searchQuery);
    return matchesFilter && matchesSearch;
  });

  const totalPages = Math.ceil(filteredCalls.length / ITEMS_PER_PAGE);
  const paginatedCalls = filteredCalls.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);

  const formatDuration = (seconds: number) => { if (!seconds) return '-'; const mins = Math.floor(seconds / 60); const secs = seconds % 60; return `${mins}:${secs.toString().padStart(2, '0')}`; };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = { completed: { bg: '#ECFDF5', color: '#065f46' }, answered: { bg: '#D1FAE5', color: '#065f46' }, failed: { bg: '#fef2f2', color: '#dc2626' }, busy: { bg: '#fef2f2', color: '#dc2626' }, no_answer: { bg: '#f5f5f5', color: '#6b7280' }, initiated: { bg: '#fef3c7', color: '#92400e' }, ringing: { bg: '#dbeafe', color: '#1e40af' } };
    const s = styles[status?.toLowerCase()] || { bg: '#f5f5f5', color: '#6b7280' };
    return <span style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, background: s.bg, color: s.color }}>{status}</span>;
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try { setSelectedIds(new Set()); await loadData(); } catch (err) { console.error('Delete error:', err); } finally { setDeleting(false); }
  };

  const toggleSelect = (id: string) => { const newSet = new Set(selectedIds); if (newSet.has(id)) newSet.delete(id); else newSet.add(id); setSelectedIds(newSet); };

  const getPaginationBtnStyle = (disabled: boolean) => ({ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '28px', height: '28px', background: disabled ? '#f9fafb' : '#ECFDF5', border: `1px solid ${disabled ? '#e5e7eb' : '#A7F3D0'}`, borderRadius: '6px', fontSize: '12px', color: disabled ? '#9ca3af' : '#10B981', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.4 : 1 });

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice Logs | WECARE.DIGITAL" description="View voice call logs" />
      <div style={{ padding: '20px' }}>
        <Breadcrumbs />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', marginTop: '12px' }}>
          <h2 style={{ margin: 0 }}>Voice Logs</h2>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
          <button onClick={handleDeleteSelected} disabled={selectedIds.size === 0 || deleting} title="Delete selected" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '40px', height: '40px', background: selectedIds.size === 0 ? '#f9fafb' : '#ECFDF5', border: `1.5px solid ${selectedIds.size === 0 ? '#e5e7eb' : '#A7F3D0'}`, borderRadius: '10px', cursor: selectedIds.size === 0 ? 'not-allowed' : 'pointer', opacity: selectedIds.size === 0 ? 0.5 : 1, color: selectedIds.size === 0 ? '#9ca3af' : '#10B981' }} onMouseEnter={e => { if (selectedIds.size > 0) { e.currentTarget.style.background = '#fef2f2'; e.currentTarget.style.borderColor = '#ef4444'; e.currentTarget.style.color = '#ef4444'; }}} onMouseLeave={e => { e.currentTarget.style.background = selectedIds.size === 0 ? '#f9fafb' : '#ECFDF5'; e.currentTarget.style.borderColor = selectedIds.size === 0 ? '#e5e7eb' : '#A7F3D0'; e.currentTarget.style.color = selectedIds.size === 0 ? '#9ca3af' : '#10B981'; }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
          </button>
          <input type="text" placeholder="Search by phone..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} style={{ padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '13px', width: '200px' }} />
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
          {(['all', 'completed', 'failed'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{ padding: '8px 16px', border: '1.5px solid #10B981', borderRadius: '13px', background: filter === f ? '#D1FAE5' : '#fff', color: '#111827', fontWeight: filter === f ? 600 : 500, cursor: 'pointer', textTransform: 'capitalize' }}>
              {f} {f !== 'all' && `(${calls.filter(c => f === 'completed' ? ['completed', 'answered'].includes(c.status?.toLowerCase()) : ['failed', 'busy', 'no_answer'].includes(c.status?.toLowerCase())).length})`}
            </button>
          ))}
        </div>

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
                  <input type="checkbox" checked={paginatedCalls.length > 0 && paginatedCalls.every(c => selectedIds.has(c.id))} onChange={e => { if (e.target.checked) { const newSet = new Set(selectedIds); paginatedCalls.forEach(c => newSet.add(c.id)); setSelectedIds(newSet); } else { const newSet = new Set(selectedIds); paginatedCalls.forEach(c => newSet.delete(c.id)); setSelectedIds(newSet); }}} style={{ accentColor: '#10B981' }} />
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
                  <td style={{ padding: '12px 16px' }}><input type="checkbox" checked={selectedIds.has(c.id)} onChange={() => toggleSelect(c.id)} style={{ accentColor: '#10B981' }} /></td>
                  <td style={{ padding: '12px 16px', fontSize: '14px' }}>{c.phoneNumber}</td>
                  <td style={{ padding: '12px 16px', fontSize: '12px', color: '#6b7280', textTransform: 'uppercase' }}>{c.callType}</td>
                  <td style={{ padding: '12px 16px' }}>{getStatusBadge(c.status)}</td>
                  <td style={{ padding: '12px 16px', fontSize: '14px' }}>{formatDuration(c.duration)}</td>
                  <td style={{ padding: '12px 16px', fontSize: '12px', color: '#6b7280' }}>{c.voiceId || '-'}</td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>{new Date(c.createdAt * 1000).toLocaleString()}</td>
                </tr>
              ))}
              {filteredCalls.length === 0 && <tr><td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>No voice call logs found</td></tr>}
            </tbody>
          </table>
        </div>

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

export default VoiceLogsPage;
