/**
 * SMS Logs Page
 * View all SMS message logs
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const SmsLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<api.Message[]>([]);
  const [filter, setFilter] = useState<'all' | 'sent' | 'delivered' | 'failed'>('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listMessages(undefined, 'SMS');
      setMessages(data.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()));
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredMessages = messages.filter(m => {
    if (filter === 'all') return true;
    return m.status === filter;
  });

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = {
      sent: { bg: '#ECFDF5', color: '#065f46' },
      delivered: { bg: '#D1FAE5', color: '#065f46' },
      failed: { bg: '#fef2f2', color: '#dc2626' },
      pending: { bg: '#f5f5f5', color: '#6b7280' },
    };
    const s = styles[status] || styles.pending;
    return <span style={{ padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, background: s.bg, color: s.color }}>{status}</span>;
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS Logs | WECARE.DIGITAL" description="View SMS message logs" />
      <div style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ margin: 0 }}>SMS Logs</h2>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
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

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>To</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Message</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Date</th>
              </tr>
            </thead>
            <tbody>
              {filteredMessages.slice(0, 100).map(m => (
                <tr key={m.messageId} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '12px 16px', fontSize: '14px' }}>{m.contactId}</td>
                  <td style={{ padding: '12px 16px', fontSize: '14px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.content}</td>
                  <td style={{ padding: '12px 16px' }}>{getStatusBadge(m.status)}</td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', color: '#6b7280' }}>{new Date(m.timestamp).toLocaleString()}</td>
                </tr>
              ))}
              {filteredMessages.length === 0 && (
                <tr><td colSpan={4} style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>No SMS logs found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
};

export default SmsLogsPage;
