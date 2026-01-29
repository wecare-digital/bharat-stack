/**
 * Payment Logs - View all payment requests (WA + Link)
 */

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface PaymentLog {
  id: string;
  referenceId: string;
  type: 'wa' | 'link';
  amount: number;
  status: 'pending' | 'sent' | 'delivered' | 'read' | 'paid' | 'failed' | 'expired';
  recipient: string;
  recipientName?: string;
  createdAt: string;
  paidAt?: string;
  itemName?: string;
}

const PaymentLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [logs, setLogs] = useState<PaymentLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'wa' | 'link'>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    loadPaymentLogs();
  }, []);

  const loadPaymentLogs = async () => {
    setLoading(true);
    try {
      // Fetch messages that are payment-related (contain WDSR or WDPL reference)
      const messages = await api.listMessages();
      
      // Filter for payment messages (outbound with payment reference)
      const paymentMessages = messages
        .filter(m => m.direction === 'OUTBOUND' && m.content?.includes('payment'))
        .map(m => {
          // Extract reference ID from message content or metadata (with or without underscore for backwards compat)
          const refMatch = m.content?.match(/WDSR_?[A-Z0-9]+|WDPL_?[A-Z0-9]+/);
          const refId = refMatch ? refMatch[0].replace('_', '') : m.messageId?.substring(0, 12).toUpperCase();
          
          return {
            id: m.messageId,
            referenceId: refId || `REF${m.messageId?.substring(0, 8)}`,
            type: refId?.startsWith('WDPL') ? 'link' : 'wa' as 'wa' | 'link',
            amount: 0, // Would need to parse from content
            status: m.status as PaymentLog['status'],
            recipient: m.contactId,
            createdAt: m.timestamp,
            itemName: 'Payment Request',
          };
        });

      setLogs(paymentMessages);
    } catch (err) {
      console.error('Failed to load payment logs:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { bg: string; color: string; label: string }> = {
      pending: { bg: '#fef3c7', color: '#92400e', label: 'Pending' },
      sent: { bg: '#dbeafe', color: '#1e40af', label: 'Sent' },
      delivered: { bg: '#dcfce7', color: '#166534', label: 'Delivered' },
      read: { bg: '#e0e7ff', color: '#3730a3', label: 'Read' },
      paid: { bg: '#dcfce7', color: '#166534', label: '✓ Paid' },
      failed: { bg: '#fee2e2', color: '#991b1b', label: 'Failed' },
      expired: { bg: '#f3f4f6', color: '#6b7280', label: 'Expired' },
    };
    return badges[status] || badges.pending;
  };

  const getTypeBadge = (type: 'wa' | 'link') => {
    if (type === 'wa') {
      return { bg: '#dcfce7', color: '#166534', icon: '💬', label: 'WhatsApp' };
    }
    return { bg: '#dbeafe', color: '#1e40af', icon: '🔗', label: 'Link' };
  };

  const filteredLogs = logs.filter(log => {
    if (filter !== 'all' && log.type !== filter) return false;
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

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="logs-page">
        <PageHeader 
          title="Payment Logs" 
          subtitle="View all payment requests sent via WhatsApp and Payment Links"
          icon="logs"
        />

        <div className="filters">
          <div className="filter-group">
            <label>Type:</label>
            <select value={filter} onChange={(e) => setFilter(e.target.value as any)}>
              <option value="all">All Types</option>
              <option value="wa">💬 WhatsApp</option>
              <option value="link">🔗 Link</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Status:</label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="sent">Sent</option>
              <option value="delivered">Delivered</option>
              <option value="paid">Paid</option>
              <option value="failed">Failed</option>
              <option value="expired">Expired</option>
            </select>
          </div>
          <button className="refresh-btn" onClick={loadPaymentLogs} disabled={loading}>
            {loading ? '...' : '🔄'} Refresh
          </button>
        </div>

        <div className="table-container">
          <table className="logs-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Reference ID</th>
                <th>Recipient</th>
                <th>Item</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="loading-cell">Loading payment logs...</td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-cell">
                    <div className="empty-state">
                      <span className="empty-icon">📭</span>
                      <p>No payment logs found</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredLogs.map(log => {
                  const typeBadge = getTypeBadge(log.type);
                  const statusBadge = getStatusBadge(log.status);
                  return (
                    <tr key={log.id}>
                      <td>
                        <span className="type-badge" style={{ background: typeBadge.bg, color: typeBadge.color }}>
                          {typeBadge.icon} {typeBadge.label}
                        </span>
                      </td>
                      <td className="ref-cell">
                        <code>{log.referenceId}</code>
                      </td>
                      <td>
                        <div className="recipient-cell">
                          <span className="recipient-name">{log.recipientName || '—'}</span>
                          <span className="recipient-id">{log.recipient}</span>
                        </div>
                      </td>
                      <td>{log.itemName || '—'}</td>
                      <td className="amount-cell">
                        {log.amount > 0 ? `₹${(log.amount / 100).toFixed(2)}` : '—'}
                      </td>
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
              <span className="card-label">Total Sent</span>
            </div>
          </div>
          <div className="summary-card success">
            <div className="card-icon">✅</div>
            <div className="card-info">
              <span className="card-value">{logs.filter(l => l.status === 'paid').length}</span>
              <span className="card-label">Paid</span>
            </div>
          </div>
          <div className="summary-card warning">
            <div className="card-icon">⏳</div>
            <div className="card-info">
              <span className="card-value">{logs.filter(l => ['pending', 'sent', 'delivered'].includes(l.status)).length}</span>
              <span className="card-label">Pending</span>
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
        
        .type-badge { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
        .status-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
        
        .ref-cell code { background: #f3f4f6; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-family: monospace; }
        .recipient-cell { display: flex; flex-direction: column; gap: 2px; }
        .recipient-name { font-weight: 500; }
        .recipient-id { font-size: 11px; color: #9ca3af; }
        .amount-cell { font-weight: 600; color: #166534; }
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
        .summary-card.success .card-value { color: #166534; }
        .summary-card.warning .card-value { color: #92400e; }
        .summary-card.error .card-value { color: #991b1b; }
        
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

export default PaymentLogsPage;
