/**
 * Dashboard - Payments Overview
 * Payment statistics and transaction history
 */
import React, { useState, useEffect, useMemo } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import { BarChart, DonutChart, Sparkline } from '../../../components/Charts';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }

interface Payment {
  id: string;
  referenceId: string;
  amount: number;
  currency: string;
  status: 'pending' | 'completed' | 'failed' | 'refunded';
  contactId: string;
  contactName?: string;
  contactPhone?: string;
  channel: 'whatsapp' | 'link' | 'upi';
  createdAt: string;
  completedAt?: string;
}

const DashboardPaymentsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'completed' | 'pending' | 'failed'>('all');

  useEffect(() => {
    loadPayments();
  }, []);

  const loadPayments = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch from payments API
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod'}/payments`);
      if (response.ok) {
        const data = await response.json();
        const paymentsList = Array.isArray(data) ? data : data.payments || [];
        setPayments(paymentsList.map(normalizePayment));
      } else if (response.status === 404) {
        // No payments yet - this is OK
        setPayments([]);
      } else {
        setError(`Failed to load payments: ${response.status} ${response.statusText}`);
        setPayments([]);
      }
    } catch (err: any) {
      console.error('Failed to load payments:', err);
      setError(err.message || 'Failed to connect to payments API');
      setPayments([]);
    } finally {
      setLoading(false);
    }
  };

  // Normalize payment data from API
  const normalizePayment = (p: any): Payment => ({
    id: p.id || p.paymentId || '',
    referenceId: p.referenceId || p.orderId || '',
    amount: p.amount || p.amountInRupees * 100 || 0,
    currency: p.currency || 'INR',
    status: (p.status || 'pending').toLowerCase() as Payment['status'],
    contactId: p.contactId || '',
    contactName: p.contactName || p.email || '',
    contactPhone: p.contact || p.contactPhone || '',
    channel: p.channel || (p.source?.includes('whatsapp') ? 'whatsapp' : 'link'),
    createdAt: p.createdAt ? new Date(p.createdAt * 1000).toISOString() : new Date().toISOString(),
    completedAt: p.completedAt ? new Date(p.completedAt * 1000).toISOString() : undefined,
  });

  // Calculate stats
  const stats = useMemo(() => {
    const completed = payments.filter(p => p.status === 'completed');
    const pending = payments.filter(p => p.status === 'pending');
    const failed = payments.filter(p => p.status === 'failed');
    
    const totalAmount = completed.reduce((sum, p) => sum + p.amount, 0);
    const pendingAmount = pending.reduce((sum, p) => sum + p.amount, 0);
    
    const byChannel = {
      whatsapp: payments.filter(p => p.channel === 'whatsapp').length,
      link: payments.filter(p => p.channel === 'link').length,
      upi: payments.filter(p => p.channel === 'upi').length,
    };

    // Last 7 days trend
    const last7Days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - (6 - i));
      return d.toISOString().slice(0, 10);
    });
    
    const byDay = last7Days.map(date => {
      const dayPayments = completed.filter(p => p.completedAt?.slice(0, 10) === date);
      return dayPayments.reduce((sum, p) => sum + p.amount, 0);
    });

    return {
      total: payments.length,
      completed: completed.length,
      pending: pending.length,
      failed: failed.length,
      totalAmount,
      pendingAmount,
      byChannel,
      byDay,
      successRate: payments.length > 0 ? Math.round((completed.length / payments.length) * 100) : 0,
    };
  }, [payments]);

  const filteredPayments = filter === 'all' 
    ? payments 
    : payments.filter(p => p.status === filter);

  const formatAmount = (amount: number, currency: string = 'INR') => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
    }).format(amount / 100);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return '#4CAF50';
      case 'pending': return '#FF9800';
      case 'failed': return '#F44336';
      case 'refunded': return '#9C27B0';
      default: return '#666';
    }
  };

  const channelData = [
    { label: 'WhatsApp', value: stats.byChannel.whatsapp, color: '#25D366' },
    { label: 'Pay Link', value: stats.byChannel.link, color: '#2196F3' },
    { label: 'UPI', value: stats.byChannel.upi, color: '#9C27B0' },
  ].filter(d => d.value > 0);

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="page">
        <PageHeader 
          title="Payments Overview" 
          subtitle="Payment statistics and transaction history"
          icon="payment"
          actions={
            <div className="header-actions">
              <button className="btn-secondary" onClick={loadPayments} disabled={loading}>
                ↻ {loading ? 'Loading...' : 'Refresh'}
              </button>
              <a href="/pay/wa" className="btn-primary" style={{ background: '#25D366' }}>+ WhatsApp Pay</a>
              <a href="/pay/link" className="btn-secondary">+ Pay Link</a>
            </div>
          }
        />

        {/* Error Banner */}
        {error && (
          <div style={{ 
            background: '#FFF3E0', 
            border: '1px solid #FF9800', 
            borderRadius: 8, 
            padding: 16, 
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 12
          }}>
            <span style={{ fontSize: 20 }}>⚠️</span>
            <div>
              <strong style={{ color: '#E65100' }}>Unable to load payments</strong>
              <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>{error}</div>
            </div>
            <button 
              onClick={loadPayments} 
              style={{ marginLeft: 'auto', padding: '6px 12px', borderRadius: 4, border: '1px solid #FF9800', background: 'white', cursor: 'pointer' }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Summary Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#4CAF50' }}>
              {formatAmount(stats.totalAmount)}
            </div>
            <div className="stat-label">Total Collected</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#FF9800' }}>
              {formatAmount(stats.pendingAmount)}
            </div>
            <div className="stat-label">Pending</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">Total Transactions</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: stats.successRate >= 90 ? '#4CAF50' : '#FF9800' }}>
              {stats.successRate}%
            </div>
            <div className="stat-label">Success Rate</div>
          </div>
        </div>

        {/* Charts Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20, marginTop: 20 }}>
          {/* Revenue Trend */}
          <div className="section" style={{ padding: 20 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>Revenue Trend (7 Days)</h3>
            <Sparkline 
              data={stats.byDay} 
              height={100} 
              color="#4CAF50"
              showArea={true}
            />
          </div>

          {/* Channel Distribution */}
          <div className="section" style={{ padding: 20 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>By Channel</h3>
            {channelData.length > 0 ? (
              <DonutChart data={channelData} size={140} />
            ) : (
              <div style={{ textAlign: 'center', color: '#666', padding: 30 }}>No data</div>
            )}
          </div>

          {/* Status Breakdown */}
          <div className="section" style={{ padding: 20 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>Status</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#4CAF50' }} />
                <span style={{ flex: 1 }}>Completed</span>
                <strong>{stats.completed}</strong>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FF9800' }} />
                <span style={{ flex: 1 }}>Pending</span>
                <strong>{stats.pending}</strong>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#F44336' }} />
                <span style={{ flex: 1 }}>Failed</span>
                <strong>{stats.failed}</strong>
              </div>
            </div>
          </div>
        </div>

        {/* Transactions Table */}
        <div className="section" style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>Recent Transactions</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['all', 'completed', 'pending', 'failed'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  style={{
                    padding: '4px 12px',
                    borderRadius: 16,
                    border: 'none',
                    background: filter === f ? '#1a1a1a' : '#f3f4f6',
                    color: filter === f ? '#fff' : '#666',
                    fontSize: 12,
                    cursor: 'pointer',
                  }}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Contact</th>
                  <th>Amount</th>
                  <th>Channel</th>
                  <th>Status</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {filteredPayments.map(payment => (
                  <tr key={payment.id}>
                    <td><code style={{ fontSize: 11 }}>{payment.referenceId}</code></td>
                    <td>
                      <div>
                        <strong>{payment.contactName || 'Unknown'}</strong>
                        <div style={{ fontSize: 11, color: '#666' }}>{payment.contactPhone}</div>
                      </div>
                    </td>
                    <td style={{ fontWeight: 600 }}>{formatAmount(payment.amount, payment.currency)}</td>
                    <td>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontSize: 10,
                        background: payment.channel === 'whatsapp' ? '#25D36620' : payment.channel === 'link' ? '#2196F320' : '#9C27B020',
                        color: payment.channel === 'whatsapp' ? '#25D366' : payment.channel === 'link' ? '#2196F3' : '#9C27B0',
                      }}>
                        {payment.channel === 'whatsapp' ? 'WhatsApp' : payment.channel === 'link' ? 'Pay Link' : 'UPI'}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontSize: 10,
                        background: getStatusColor(payment.status) + '20',
                        color: getStatusColor(payment.status),
                      }}>
                        {payment.status}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: '#666' }}>
                      {new Date(payment.createdAt).toLocaleString()}
                    </td>
                  </tr>
                ))}
                {filteredPayments.length === 0 && (
                  <tr><td colSpan={6} className="empty-table">{loading ? 'Loading...' : 'No transactions found'}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default DashboardPaymentsPage;
