/**
 * SMS IN Logs Page
 * Inbound SMS logs
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

const SmsInLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<api.Message[]>([]);

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

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS IN Logs | WECARE.DIGITAL" description="Inbound SMS logs" />
      <div className="inner-page-container">
        <div className="inner-page-header">
          <div className="inner-page-header-content">
            <h1 className="inner-page-title">SMS IN - Logs</h1>
          </div>
          <div className="inner-page-actions">
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>

        <div className="table-container">
          <table className="inner-table">
            <thead>
              <tr>
                <th>From</th>
                <th>Message</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {messages.slice(0, 100).map(m => (
                <tr key={m.messageId}>
                  <td>{m.contactId}</td>
                  <td className="text-truncate">{m.content}</td>
                  <td><span className="status-badge success">received</span></td>
                  <td className="text-muted">{new Date(m.timestamp).toLocaleString()}</td>
                </tr>
              ))}
              {messages.length === 0 && (
                <tr><td colSpan={4} className="empty-row">No inbound SMS logs</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
};

export default SmsInLogsPage;
