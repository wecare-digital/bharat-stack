/**
 * Voice IN Calls Page
 * Inbound voice calls
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

interface CallRecord {
  callId: string;
  from: string;
  to: string;
  status: string;
  duration: number;
  timestamp: string;
}

const VoiceInCallsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/voice-cdr?direction=inbound&limit=100`);
      if (response.ok) {
        const data = await response.json();
        setCalls(data.records || []);
      }
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredCalls = calls.filter(c =>
    c.from?.includes(searchQuery) || c.to?.includes(searchQuery)
  );

  const formatDuration = (seconds: number) => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = {
      answered: { bg: '#D1FAE5', color: '#065f46' },
      completed: { bg: '#ECFDF5', color: '#065f46' },
      missed: { bg: '#fef2f2', color: '#dc2626' },
      busy: { bg: '#f5f5f5', color: '#6b7280' },
    };
    const s = styles[status] || { bg: '#f5f5f5', color: '#6b7280' };
    return <span style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, background: s.bg, color: s.color }}>{status}</span>;
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice IN Calls | WECARE.DIGITAL" description="Inbound voice calls" />
      <div style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ margin: 0 }}>Voice IN - Calls</h2>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <input
            type="text"
            placeholder="Search by phone..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              maxWidth: '300px',
              padding: '10px 14px',
              border: '1.5px solid #d1d5db',
              borderRadius: '13px',
              fontSize: '14px'
            }}
          />
        </div>

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', overflow: 'hidden' }}>
          {filteredCalls.length === 0 ? (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: '#6b7280' }}>
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>📞</div>
              <h3 style={{ margin: '0 0 8px', color: '#111827' }}>No Inbound Calls</h3>
              <p style={{ margin: 0 }}>Inbound voice calls will appear here</p>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>From</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>To</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Status</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Duration</th>
                  <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Date</th>
                </tr>
              </thead>
              <tbody>
                {filteredCalls.map(c => (
                  <tr key={c.callId} style={{ borderBottom: '1px solid #e5e7eb' }}>
                    <td style={{ padding: '12px 16px', fontSize: '14px' }}>{c.from}</td>
                    <td style={{ padding: '12px 16px', fontSize: '14px' }}>{c.to}</td>
                    <td style={{ padding: '12px 16px' }}>{getStatusBadge(c.status)}</td>
                    <td style={{ padding: '12px 16px', fontSize: '14px' }}>{formatDuration(c.duration)}</td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>{new Date(c.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default VoiceInCallsPage;
