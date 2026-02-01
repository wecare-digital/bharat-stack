/**
 * Bulk Logs - View all bulk message campaigns
 */

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface BulkLog {
  id: string;
  channel: 'whatsapp' | 'sms' | 'email' | 'voice' | 'rcs';
  campaignName: string;
  totalRecipients: number;
  sent: number;
  delivered: number;
  failed: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused';
  createdAt: string;
}

const BulkLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [logs, setLogs] = useState<BulkLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    loadBulkLogs();
  }, []);

  const loadBulkLogs = async () => {
    setLoading(true);
    try {
      const jobs = await api.listBulkJobs();
      // Map API response to BulkLog format
      const mappedLogs: BulkLog[] = jobs.map(job => ({
        id: job.jobId || job.id,
        channel: (job.channel?.toLowerCase() || 'whatsapp') as BulkLog['channel'],
        campaignName: `Campaign ${job.jobId?.slice(-6) || 'Unknown'}`,
        totalRecipients: job.totalRecipients || 0,
        sent: job.sentCount || 0,
        delivered: job.sentCount || 0,
        failed: job.failedCount || 0,
        status: (job.status?.toLowerCase() || 'pending') as BulkLog['status'],
        createdAt: job.createdAt || new Date().toISOString(),
      }));
      setLogs(mappedLogs);
    } catch (err) {
      console.error('Failed to load bulk logs:', err);
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  const getChannelBadge = (channel: string) => {
    const badges: Record<string, { bg: string; color: string; icon: string; label: string }> = {
      whatsapp: { bg: '#f5f5f5', color: '#000', icon: '💬', label: 'WhatsApp' },
      sms: { bg: '#f5f5f5', color: '#000', icon: '📱', label: 'SMS' },
      email: { bg: '#f5f5f5', color: '#000', icon: '📧', label: 'Email' },
      voice: { bg: '#f5f5f5', color: '#000', icon: '📞', label: 'Voice' },
      rcs: { bg: '#f5f5f5', color: '#000', icon: '💎', label: 'RCS' },
    };
    return badges[channel] || badges.whatsapp;
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { bg: string; color: string; label: string }> = {
      pending: { bg: '#f5f5f5', color: '#4a4a4a', label: 'Pending' },
      running: { bg: '#e5e5e5', color: '#000', label: 'Running' },
      completed: { bg: '#f0f0f0', color: '#000', label: 'Completed' },
      failed: { bg: '#f5f5f5', color: '#4a4a4a', label: 'Failed' },
      paused: { bg: '#f5f5f5', color: '#6b6b6b', label: 'Paused' },
    };
    return badges[status] || { bg: '#f5f5f5', color: '#6b6b6b', label: status };
  };

  const filteredLogs = logs.filter(log => {
    if (channelFilter !== 'all' && log.channel !== channelFilter) return false;
    if (statusFilter !== 'all' && log.status !== statusFilter) return false;
    return true;
  });

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', { 
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="logs-page">
        <div className="page-header">
          <h1>📊 Bulk Campaign Logs</h1>
          <p>View all bulk message campaigns across channels</p>
        </div>

        <div className="filters">
          <div className="filter-group">
            <label>Channel:</label>
            <select value={channelFilter} onChange={(e) => setChannelFilter(e.target.value)}>
              <option value="all">All Channels</option>
              <option value="whatsapp">💬 WhatsApp</option>
              <option value="sms">📱 SMS</option>
              <option value="email">📧 Email</option>
              <option value="voice">📞 Voice</option>
              <option value="rcs">💎 RCS</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Status:</label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="all">All Status</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="pending">Pending</option>
              <option value="paused">Paused</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <button className="refresh-btn" onClick={loadBulkLogs} disabled={loading}>
            {loading ? '...' : '🔄'} Refresh
          </button>
        </div>

        <div className="table-container">
          <table className="logs-table">
            <thead>
              <tr>
                <th>Channel</th>
                <th>Campaign</th>
                <th>Recipients</th>
                <th>Sent</th>
                <th>Delivered</th>
                <th>Failed</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="loading-cell">Loading bulk logs...</td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty-cell">
                    <div className="empty-state">
                      <span className="empty-icon">📭</span>
                      <p>No bulk campaigns found</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredLogs.map(log => {
                  const channelBadge = getChannelBadge(log.channel);
                  const statusBadge = getStatusBadge(log.status);
                  return (
                    <tr key={log.id}>
                      <td>
                        <span className="channel-badge" style={{ background: channelBadge.bg, color: channelBadge.color }}>
                          {channelBadge.icon} {channelBadge.label}
                        </span>
                      </td>
                      <td className="campaign-cell">{log.campaignName}</td>
                      <td className="num-cell">{log.totalRecipients.toLocaleString()}</td>
                      <td className="num-cell">{log.sent.toLocaleString()}</td>
                      <td className="num-cell success">{log.delivered.toLocaleString()}</td>
                      <td className="num-cell error">{log.failed.toLocaleString()}</td>
                      <td>
                        <span className="status-badge" style={{ background: statusBadge.bg, color: statusBadge.color }}>
                          {statusBadge.label}
                        </span>
                      </td>
                      <td className="date-cell">{formatDate(log.createdAt)}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="summary-cards">
          <div className="summary-card">
            <div className="card-icon">📤</div>
            <div className="card-info">
              <span className="card-value">{logs.length}</span>
              <span className="card-label">Campaigns</span>
            </div>
          </div>
          <div className="summary-card running">
            <div className="card-icon">▶</div>
            <div className="card-info">
              <span className="card-value">{logs.filter(l => l.status === 'running').length}</span>
              <span className="card-label">Running</span>
            </div>
          </div>
          <div className="summary-card success">
            <div className="card-icon">✅</div>
            <div className="card-info">
              <span className="card-value">{logs.filter(l => l.status === 'completed').length}</span>
              <span className="card-label">Completed</span>
            </div>
          </div>
          <div className="summary-card error">
            <div className="card-icon">❌</div>
            <div className="card-info">
              <span className="card-value">{logs.filter(l => l.status === 'failed').length}</span>
              <span className="card-label">Failed</span>
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
        .refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .table-container { background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); overflow: hidden; margin-bottom: 20px; }
        
        .logs-table { width: 100%; border-collapse: collapse; }
        .logs-table th { background: #f9fafb; padding: 12px 16px; text-align: left; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; border-bottom: 1px solid #e5e7eb; }
        .logs-table td { padding: 12px 16px; border-bottom: 1px solid #f3f4f6; font-size: 13px; }
        .logs-table tr:last-child td { border-bottom: none; }
        .logs-table tr:hover { background: #f9fafb; }
        
        .channel-badge, .status-badge { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
        
        .campaign-cell { font-weight: 500; }
        .num-cell { font-family: monospace; text-align: right; }
        .num-cell.success { color: #000; font-weight: 500; }
        .num-cell.error { color: #4a4a4a; }
        .date-cell { color: #6b7280; font-size: 12px; }
        
        .loading-cell, .empty-cell { text-align: center; padding: 40px !important; color: #9ca3af; }
        .empty-state { display: flex; flex-direction: column; align-items: center; gap: 8px; }
        .empty-icon { font-size: 32px; opacity: 0.5; }
        .empty-state p { margin: 0; }
        
        .summary-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
        .summary-card { display: flex; align-items: center; gap: 12px; background: #fff; padding: 16px 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .card-icon { font-size: 24px; }
        .card-info { display: flex; flex-direction: column; }
        .card-value { font-size: 24px; font-weight: 700; color: #111; }
        .card-label { font-size: 12px; color: #6b7280; }
        .summary-card.running .card-value { color: #000; }
        .summary-card.success .card-value { color: #000; }
        .summary-card.error .card-value { color: #4a4a4a; }
        
        @media (max-width: 800px) {
          .summary-cards { grid-template-columns: repeat(2, 1fr); }
          .filters { flex-direction: column; align-items: stretch; }
          .refresh-btn { margin-left: 0; }
          .table-container { overflow-x: auto; }
        }
      `}</style>
    </Layout>
  );
};

export default BulkLogsPage;
