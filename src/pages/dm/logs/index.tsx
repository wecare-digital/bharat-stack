/**
 * Message Logs - View all messages across channels
 */

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface MessageLog {
  id: string;
  channel: 'whatsapp' | 'sms' | 'email' | 'voice' | 'rcs';
  direction: 'INBOUND' | 'OUTBOUND';
  recipient: string;
  content: string;
  status: string;
  createdAt: string;
}

const MessageLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [logs, setLogs] = useState<MessageLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [directionFilter, setDirectionFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    loadMessageLogs();
  }, []);

  const loadMessageLogs = async () => {
    setLoading(true);
    try {
      const messages = await api.listMessages();
      const messageLogs = messages.map(m => ({
        id: m.messageId,
        channel: (m.channel?.toLowerCase() || 'whatsapp') as MessageLog['channel'],
        direction: m.direction as 'INBOUND' | 'OUTBOUND',
        recipient: m.contactId,
        content: m.content || '',
        status: m.status || 'unknown',
        createdAt: m.timestamp,
      }));
      setLogs(messageLogs);
    } catch (err) {
      console.error('Failed to load message logs:', err);
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
      sent: { bg: '#e5e5e5', color: '#000', label: 'Sent' },
      delivered: { bg: '#f0f0f0', color: '#000', label: 'Delivered' },
      read: { bg: '#f0f0f0', color: '#000', label: 'Read' },
      failed: { bg: '#f5f5f5', color: '#4a4a4a', label: 'Failed' },
      received: { bg: '#f0f0f0', color: '#000', label: 'Received' },
    };
    return badges[status] || { bg: '#f5f5f5', color: '#6b6b6b', label: status };
  };

  const getDirectionBadge = (direction: string) => {
    if (direction === 'INBOUND') {
      return { bg: '#e5e5e5', color: '#000', icon: '↓', label: 'In' };
    }
    return { bg: '#f0f0f0', color: '#000', icon: '↑', label: 'Out' };
  };

  const filteredLogs = logs.filter(log => {
    if (channelFilter !== 'all' && log.channel !== channelFilter) return false;
    if (directionFilter !== 'all' && log.direction !== directionFilter) return false;
    if (statusFilter !== 'all' && log.status !== statusFilter) return false;
    return true;
  });

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', { 
      day: '2-digit', 
      month: 'short', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const truncateContent = (content: string, maxLen: number = 50) => {
    if (content.length <= maxLen) return content;
    return content.substring(0, maxLen) + '...';
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="logs-page">
        <PageHeader 
          title="Message Logs" 
          subtitle="View all messages across WhatsApp, SMS, Email, Voice, and RCS"
          icon="logs"
        />

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
            <label>Direction:</label>
            <select value={directionFilter} onChange={(e) => setDirectionFilter(e.target.value)}>
              <option value="all">All</option>
              <option value="INBOUND">↓ Inbound</option>
              <option value="OUTBOUND">↑ Outbound</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Status:</label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="all">All Status</option>
              <option value="sent">Sent</option>
              <option value="delivered">Delivered</option>
              <option value="read">Read</option>
              <option value="received">Received</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <button className="refresh-btn" onClick={loadMessageLogs} disabled={loading}>
            {loading ? '...' : '🔄'} Refresh
          </button>
        </div>

        <div className="table-container">
          <table className="logs-table">
            <thead>
              <tr>
                <th>Channel</th>
                <th>Dir</th>
                <th>Recipient</th>
                <th>Content</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="loading-cell">Loading message logs...</td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="empty-cell">
                    <div className="empty-state">
                      <span className="empty-icon">📭</span>
                      <p>No messages found</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredLogs.slice(0, 100).map(log => {
                  const channelBadge = getChannelBadge(log.channel);
                  const statusBadge = getStatusBadge(log.status);
                  const dirBadge = getDirectionBadge(log.direction);
                  return (
                    <tr key={log.id}>
                      <td>
                        <span className="channel-badge" style={{ background: channelBadge.bg, color: channelBadge.color }}>
                          {channelBadge.icon} {channelBadge.label}
                        </span>
                      </td>
                      <td>
                        <span className="dir-badge" style={{ background: dirBadge.bg, color: dirBadge.color }}>
                          {dirBadge.icon}
                        </span>
                      </td>
                      <td className="recipient-cell">{log.recipient}</td>
                      <td className="content-cell" title={log.content}>{truncateContent(log.content)}</td>
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
              <span className="card-label">Total</span>
            </div>
          </div>
          <div className="summary-card outbound">
            <div className="card-icon">↑</div>
            <div className="card-info">
              <span className="card-value">{logs.filter(l => l.direction === 'OUTBOUND').length}</span>
              <span className="card-label">Outbound</span>
            </div>
          </div>
          <div className="summary-card inbound">
            <div className="card-icon">↓</div>
            <div className="card-info">
              <span className="card-value">{logs.filter(l => l.direction === 'INBOUND').length}</span>
              <span className="card-label">Inbound</span>
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
        
        .channel-badge, .status-badge, .dir-badge { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
        .dir-badge { padding: 4px 8px; }
        
        .recipient-cell { font-family: monospace; font-size: 12px; }
        .content-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #666; }
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
        .summary-card.outbound .card-value { color: #000; }
        .summary-card.inbound .card-value { color: #000; }
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

export default MessageLogsPage;
