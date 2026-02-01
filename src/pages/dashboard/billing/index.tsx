/**
 * Dashboard - Billing Tab
 * AWS resource usage and cost tracking
 * Enhanced responsive design
 */

import { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { BarChart } from '../../../components/Charts';
import * as api from '../../../api/client';
import { RefreshIcon } from '../../../lib/icons';

interface PageProps { signOut?: () => void; user?: any; }

export default function DashboardBillingPage({ signOut, user }: PageProps) {
  const [billing, setBilling] = useState<api.AWSBillingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<'list' | 'chart'>('list');

  useEffect(() => {
    loadBilling();
  }, []);

  const loadBilling = async () => {
    setLoading(true);
    try {
      const data = await api.getAWSBilling();
      setBilling(data);
    } catch (err) {
      console.error('Failed to load billing:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'free': return 'var(--color-success)';
      case 'paid': return 'var(--color-sms)';
      case 'warning': return 'var(--color-warning)';
      default: return 'var(--color-muted)';
    }
  };

  const formatCost = (cost: number) => cost === 0 ? 'Free' : `$${cost.toFixed(2)}`;

  const formatUsage = (usage: number, unit: string) => {
    if (usage >= 1000000) return `${(usage / 1000000).toFixed(1)}M ${unit}`;
    if (usage >= 1000) return `${(usage / 1000).toFixed(1)}K ${unit}`;
    return `${usage} ${unit}`;
  };

  const chartData = billing?.services.slice(0, 10).map(s => ({
    label: s.service.replace('Amazon ', '').replace('AWS ', ''),
    value: s.usage,
  })) || [];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="AWS Billing | WECARE.DIGITAL"
        description="Resource usage and cost tracking"
      />
      <div className="page-content">
        <PageHeader 
          title="AWS Billing" 
          subtitle="Resource usage and cost tracking"
          icon="billing"
          actions={
            <div className="header-actions">
              <button className="btn-secondary" onClick={loadBilling} disabled={loading}>
                <RefreshIcon size={16} />
                {loading ? 'Loading...' : 'Refresh'}
              </button>
              <button 
                className={`btn-secondary ${view === 'list' ? 'active' : ''}`}
                onClick={() => setView('list')}
              >
                List
              </button>
              <button 
                className={`btn-secondary ${view === 'chart' ? 'active' : ''}`}
                onClick={() => setView('chart')}
              >
                Charts
              </button>
            </div>
          }
        />

        {/* Summary Cards */}
        <div className="stats-grid">
          <div className="stat-card success">
            <div className="stat-value" style={{ color: 'var(--color-success)' }}>
              {billing ? formatCost(billing.totalCost) : '-'}
            </div>
            <div className="stat-label">Total Cost (MTD)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{billing?.services.length || 0}</div>
            <div className="stat-label">Active Services</div>
          </div>
          <div className="stat-card success">
            <div className="stat-value" style={{ color: 'var(--color-success)' }}>
              {billing?.services.filter(s => s.status === 'free').length || 0}
            </div>
            <div className="stat-label">Free Tier</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: 'var(--color-warning)' }}>
              {billing?.services.filter(s => s.status === 'warning').length || 0}
            </div>
            <div className="stat-label">Near Limit</div>
          </div>
        </div>

        {/* Account Info */}
        <div className="section" style={{ marginBottom: '20px' }}>
          <div style={{ 
            display: 'flex', 
            gap: '20px', 
            flexWrap: 'wrap', 
            fontSize: '13px', 
            color: 'var(--color-muted)' 
          }}>
            <span>Account: 809904170947</span>
            <span>Region: us-east-1</span>
            <span>Period: {billing?.period || '-'}</span>
            <span>Updated: {billing?.lastUpdated ? new Date(billing.lastUpdated).toLocaleString() : '-'}</span>
          </div>
        </div>

        {view === 'chart' && billing && (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', 
            gap: '20px',
            marginBottom: '20px'
          }}>
            <div className="section">
              <h3 className="section-title">Usage by Service</h3>
              <BarChart data={chartData} height={250} />
            </div>
            <div className="section">
              <h3 className="section-title">Service Distribution</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {billing.services.slice(0, 6).map((s, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ 
                      width: '12px', 
                      height: '12px', 
                      borderRadius: '50%', 
                      background: s.status === 'free' ? 'var(--color-success)' : s.status === 'warning' ? 'var(--color-warning)' : 'var(--color-sms)' 
                    }} />
                    <span style={{ flex: 1, fontSize: '13px' }}>{s.service.replace('Amazon ', '').replace('AWS ', '')}</span>
                    <strong style={{ fontSize: '13px' }}>{s.usage}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {view === 'list' && (
          <div className="section">
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Usage</th>
                    <th>Free Tier Limit</th>
                    <th>Cost</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={5} className="empty-table">Loading billing data...</td></tr>
                  ) : billing?.services.map((service, idx) => (
                    <tr key={idx}>
                      <td><strong>{service.service}</strong></td>
                      <td>{formatUsage(service.usage, service.unit)}</td>
                      <td style={{ color: 'var(--color-muted)', fontSize: '12px' }}>{service.freeLimit}</td>
                      <td style={{ fontWeight: 600, color: service.cost > 0 ? 'var(--color-sms)' : 'var(--color-success)' }}>
                        {formatCost(service.cost)}
                      </td>
                      <td>
                        <span className={`badge ${service.status}`}>
                          {service.status === 'free' ? 'Free Tier' : service.status === 'warning' ? 'Near Limit' : 'Paid'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!loading && (!billing || billing.services.length === 0) && (
                    <tr><td colSpan={5} className="empty-table">No billing data available</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Free Tier Tips */}
        <div className="section" style={{ background: '#f0fdf4', borderColor: '#047857' }}>
          <h3 className="section-title" style={{ color: '#065f46' }}>Free Tier Tips</h3>
          <ul style={{ 
            margin: 0, 
            paddingLeft: '20px', 
            fontSize: '13px', 
            color: '#374151', 
            lineHeight: 2 
          }}>
            <li>Lambda: 1M free requests/month, 400K GB-seconds compute</li>
            <li>DynamoDB: 25GB storage, 200M read/write requests</li>
            <li>S3: 5GB storage, 20K GET, 2K PUT requests</li>
            <li>API Gateway: 1M REST API calls/month</li>
            <li>Amplify: 1000 build minutes, 15GB hosting/month</li>
          </ul>
        </div>
      </div>
    </Layout>
  );
}
