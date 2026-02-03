/**
 * Voice IN Calls Page
 * Inbound voice calls
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { EmptyState } from '../../../components/ui';
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

  const getStatusClass = (status: string) => {
    if (status === 'answered' || status === 'completed') return 'success';
    if (status === 'missed') return 'danger';
    return 'muted';
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice IN Calls | WECARE.DIGITAL" description="Inbound voice calls" />
      <div className="inner-page-container">
        <div className="inner-page-header">
          <div className="inner-page-header-content">
            <h1 className="inner-page-title">Voice IN - Calls</h1>
          </div>
          <div className="inner-page-actions">
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>

        <div className="inner-section">
          <input
            type="text"
            placeholder="Search by phone..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="search-input"
            aria-label="Search calls"
          />
        </div>

        <div className="table-container">
          {filteredCalls.length === 0 ? (
            <EmptyState
              icon="📞"
              title="No Inbound Calls"
              description="Inbound voice calls will appear here"
            />
          ) : (
            <table className="inner-table">
              <thead>
                <tr>
                  <th>From</th>
                  <th>To</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {filteredCalls.map(c => (
                  <tr key={c.callId}>
                    <td>{c.from}</td>
                    <td>{c.to}</td>
                    <td><span className={`status-badge ${getStatusClass(c.status)}`}>{c.status}</span></td>
                    <td>{formatDuration(c.duration)}</td>
                    <td className="text-muted">{new Date(c.timestamp).toLocaleString()}</td>
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
