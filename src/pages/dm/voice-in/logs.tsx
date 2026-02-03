/**
 * Voice IN Logs Page
 * Inbound voice call logs
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

const VoiceInLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [calls, setCalls] = useState<CallRecord[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/voice-cdr?direction=inbound&limit=200`);
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

  const formatDuration = (seconds: number) => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice IN Logs | WECARE.DIGITAL" description="Inbound voice call logs" />
      <div className="inner-page-container">
        <div className="inner-page-header">
          <div className="inner-page-header-content">
            <h1 className="inner-page-title">Voice IN - Logs</h1>
          </div>
          <div className="inner-page-actions">
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>

        <div className="table-container">
          <table className="inner-table">
            <thead>
              <tr>
                <th>Call ID</th>
                <th>From</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {calls.slice(0, 100).map(c => (
                <tr key={c.callId}>
                  <td className="text-mono text-muted">{c.callId?.slice(0, 12)}...</td>
                  <td>{c.from}</td>
                  <td><span className="status-badge success">{c.status}</span></td>
                  <td>{formatDuration(c.duration)}</td>
                  <td className="text-muted">{new Date(c.timestamp).toLocaleString()}</td>
                </tr>
              ))}
              {calls.length === 0 && (
                <tr><td colSpan={5} className="empty-row">No inbound call logs</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
};

export default VoiceInLogsPage;
