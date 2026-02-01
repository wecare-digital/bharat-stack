/**
 * Dashboard - Payments Overview
 * Payment statistics and transaction history
 * Enhanced responsive design
 */

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { Sparkline } from '../../../components/Charts';
import { RefreshIcon } from '../../../lib/icons';

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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';

export default function DashboardPaymentsPage({ signOut, user }: PageProps) {
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
      const response = await fetch(`${API_BASE}/payments`);
      if (response.ok) {
        const data = await response.json();
        const paymentsList = Array.isArray(data) ? data : data.payments || [];
        setPayments(paymentsList.map(normalizePayment));
      } else if (response.status === 404) {
        setPayments([]);
      } else {
        setError(`Failed to load payments: ${response.status}`);
        setPayments([]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to connect to payments API');
      setPayments([]);
    } finally {
      setLoading(false);
    }
  };

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

  const channelData = [
    { label: 'WhatsApp', value: stats.byChannel.whatsapp, color: 'var(--color-whatsapp)' },
    { label: 'Pay Link', value: stats.byChannel.link, color: 'var(--color-sms)' },
    { label: 'UPI', value: stats.byChannel.upi, color: 'var(--color-email)' },
  ].filter(d => d.value > 0);

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Payments Overview | WECARE.DIGITAL"
        description="Payment statistics and transaction history"
      />
      <div className="page-content">
        <PageHeader 
          title="Payments Overview" 
          subtitle="Payment statistics and transaction history"
          icon="payment"
          actions={
            <div className="header-actions">
              <button className="btn-secondary" onClick={loadPayments} disabled={loading} title="Refresh">
                {loading ? '...' : <RefreshIcon size={18} />}
              </button>
              <Link href="/pay/wa" className="btn-primary">
                WhatsApp Pay
              </Link>
              <Link href="/pay/link" className="btn-secondary">
                Pay Link
              </Link>
            </div>
          }
        />

        {/* Error Banner */}
        {error && (
          <div className="error-banner" style={{ marginBottom: '20px' }}>
            <span>{error}</span>
            <button onClick={loadPayments}>Retry</button>
          </div>
        )}

        {/* Summary Stats */}
        <div className="stats-grid">
          <div className="stat-card success">
            <div className="stat-value" style={{ color: 'var(--color-success)' }}>
              {formatAmount(stats.totalAmount)}
            </div>
            <div className="stat-label">Total Collected</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: 'var(--color-warning)' }}>
              {formatAmount(stats.pendingAmount)}
            </div>
            <div className="stat-label">Pending</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">Transactions</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: stats.successRate >= 90 ? 'var(--color-success)' : 'var(--color-warning)' }}>
              {stats.successRate}%
            </div>
            <div className="stat-label">Success Rate</div>
          </div>
        </div>

        {/* Charts Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginBottom: '20px' }}>
          <div className="section">
            <h3 className="section-title">Revenue Trend (7 Days)</h3>
            <Sparkline 
              data={stats.byDay} 
              height={100}
              width={280}
              color="var(--color-success)"
            />
          </div>

          <div className="section">
            <h3 className="section-title">By Channel</h3>
            {channelData.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {channelData.map(item => (
                  <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: item.color }} />
                    <span style={{ flex: 1 }}>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty">No data</div>
            )}
          </div>

          <div className="section">
            <h3 className="section-title">Status</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '8px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--color-success)' }} />
                <span style={{ flex: 1 }}>Completed</span>
                <strong>{stats.completed}</strong>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--color-warning)' }} />
                <span style={{ flex: 1 }}>Pending</span>
                <strong>{stats.pending}</strong>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--color-danger)' }} />
                <span style={{ flex: 1 }}>Failed</span>
                <strong>{stats.failed}</strong>
              </div>
            </div>
          </div>
        </div>

        {/* Transactions Table */}
        <div className="section">
          <div className="section-header">
            <h3 className="section-title">Recent Transactions</h3>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {(['all', 'completed', 'pending', 'failed'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`btn-secondary btn-sm ${filter === f ? 'active' : ''}`}
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
                    <td><code style={{ fontSize: '11px', background: 'var(--color-bg-secondary)', padding: '2px 6px', borderRadius: '4px' }}>{payment.referenceId}</code></td>
                    <td>
                      <div>
                        <strong style={{ fontSize: '13px' }}>{payment.contactName || 'Unknown'}</strong>
                        <div style={{ fontSize: '11px', color: 'var(--color-muted)' }}>{payment.contactPhone}</div>
                      </div>
                    </td>
                    <td style={{ fontWeight: 600 }}>{formatAmount(payment.amount, payment.currency)}</td>
                    <td>
                      <span className={`badge ${payment.channel}`}>
                        {payment.channel === 'whatsapp' ? 'WhatsApp' : payment.channel === 'link' ? 'Pay Link' : 'UPI'}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${payment.status}`}>
                        {payment.status}
                      </span>
                    </td>
                    <td style={{ fontSize: '12px', color: 'var(--color-muted)' }}>
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
}
