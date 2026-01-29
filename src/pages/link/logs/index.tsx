/**
 * Link Logs - View all link activity
 */

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface LinkLog {
  id: string;
  shortCode: string;
  type: 'payment' | 'form' | 'redirect' | 'file';
  destination: string;
  clicks: number;
  status: 'active' | 'expired' | 'disabled';
  createdAt: string;
  lastClickedAt?: string;
}

const LinkLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [logs, setLogs] = useState<LinkLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    // Simulated data - replace with API call
    setTimeout(() => {
      setLogs([]);
      setLoading(false);
    }, 500);
  }, []);

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { bg: string; color: string; label: string }> = {
      active: { bg: '#dcfce7', color: '#166534', label: 'Active' },
      expired: { bg: '#f3f4f6', color: '#6b7280', label: 'Expired' },
      disabled: { bg: '#fee2e2', color: '#991b1b', label: 'Disabled' },
    };
    return badges[status] || badges.active;
  };

  const getTypeBadge = (type: string) => {
    const badges: Record<string, { bg: string; color: string; icon: string }> = {
      payment: { bg: '#dcfce7', color: '#166534', icon: '💳' },
      form: { bg: '#dbeafe', color: '#1e40af', icon: '📝' },
      redirect: { bg: '#fef3c7', color: '#92400e', icon: '↗' },
      file: { bg: '#ede9fe', color: '#5b21b6', icon: '📁' },
    };
    return badges[type] || badges.redirect;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', { 
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="logs-page">
        <PageHeader 
          title="Link Logs" 
          subtitle="Track all link clicks and activity"
          icon="logs"
        />

        <div className="filters">
          <div className="filter-group">
            <label>Type:</label>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All Types</option>
              <option value="payment">💳 Payment</option>
              <option value="form">📝 Form</option>
              <option value="redirect">↗ Redirect</option>
              <option value="file">📁 File</option>
            </select>
          </div>
          <button className="refresh-btn" onClick={() => setLoading(true)} disabled={loading}>
            {loading ? '...' : '🔄'} Refresh
          </button>
        </div>

        <div className="table-container">
          <table className="logs-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Short Code</th>
                <th>Destination</th>
                <th>Clicks</th>
                <th>Status</th>
                <th>Created</th>
                <th>Last Click</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="loading-cell">Loading link logs...</td></tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-cell">
                    <div className="empty-state">
                      <span className="empty-icon">🔗</span>
                      <p>No links created yet</p>
                    </div>
                  </td>
                </tr>
              ) : (
                logs.map(log => {
                  const typeBadge = getTypeBadge(log.type);
                  const statusBadge = getStatusBadge(log.status);
                  return (
                    <tr key={log.id}>
                      <td>
                        <span className="type-badge" style={{ background: typeBadge.bg, color: typeBadge.color }}>
                          {typeBadge.icon} {log.type}
                        </span>
                      </td>
                      <td className="code-cell"><code>{log.shortCode}</code></td>
                      <td className="dest-cell">{log.destination}</td>
                      <td className="clicks-cell">{log.clicks}</td>
                      <td>
                        <span className="status-badge" style={{ background: statusBadge.bg, color: statusBadge.color }}>
                          {statusBadge.label}
                        </span>
                      </td>
                      <td className="date-cell">{formatDate(log.createdAt)}</td>
                      <td className="date-cell">{log.lastClickedAt ? formatDate(log.lastClickedAt) : '—'}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="summary-cards">
          <div className="summary-card">
            <div className="card-icon">🔗</div>
            <div className="card-info">
              <span className="card-value">{logs.length}</span>
              <span className="card-label">Total Links</span>
            </div>
          </div>
          <div className="summary-card success">
            <div className="card-icon">✅</div>
            <div className="card-info">
              <span className="card-value">{logs.filter(l => l.status === 'active').length}</span>
              <span className="card-label">Active</span>
            </div>
          </div>
          <div className="summary-card warning">
            <div className="card-icon">👆</div>
            <div className="card-info">
              <span className="card-value">{logs.reduce((sum, l) => sum + l.clicks, 0)}</span>
              <span className="card-label">Total Clicks</span>
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .logs-page { padding: 20px; max-width: 1200px; margin: 0 auto; }
        .page-header { margin-bottom: 20px; }
        .page-header h1 { font-size: 22px; margin: 0 0 4px 0; }
        .page-header p { color: #666; margin: 0; font-size: 14px; }
        .filters { display: flex; gap: 16px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
        .filter-group { display: flex; align-items: center; gap: 8px; }
        .filter-group label { font-size: 13px; color: #666; }
        .filter-group select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 13px; }
        .refresh-btn { padding: 8px 16px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 8px; cursor: pointer; font-size: 13px; margin-left: auto; }
        .refresh-btn:hover { background: #e5e5e5; }
        .table-container { background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); overflow: hidden; margin-bottom: 20px; }
        .logs-table { width: 100%; border-collapse: collapse; }
        .logs-table th { background: #f9fafb; padding: 12px 16px; text-align: left; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; border-bottom: 1px solid #e5e7eb; }
        .logs-table td { padding: 12px 16px; border-bottom: 1px solid #f3f4f6; font-size: 13px; }
        .logs-table tr:last-child td { border-bottom: none; }
        .logs-table tr:hover { background: #f9fafb; }
        .type-badge, .status-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
        .code-cell code { background: #f3f4f6; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-family: monospace; }
        .clicks-cell { font-weight: 600; color: #3b82f6; }
        .date-cell { color: #6b7280; font-size: 12px; }
        .loading-cell, .empty-cell { text-align: center; padding: 40px !important; color: #9ca3af; }
        .empty-state { display: flex; flex-direction: column; align-items: center; gap: 8px; }
        .empty-icon { font-size: 32px; opacity: 0.5; }
        .summary-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
        .summary-card { display: flex; align-items: center; gap: 12px; background: #fff; padding: 16px 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .card-icon { font-size: 24px; }
        .card-info { display: flex; flex-direction: column; }
        .card-value { font-size: 24px; font-weight: 700; color: #111; }
        .card-label { font-size: 12px; color: #6b7280; }
        .summary-card.success .card-value { color: #166534; }
        .summary-card.warning .card-value { color: #3b82f6; }
        @media (max-width: 800px) {
          .summary-cards { grid-template-columns: 1fr; }
        }
      `}</style>
    </Layout>
  );
};

export default LinkLogsPage;
