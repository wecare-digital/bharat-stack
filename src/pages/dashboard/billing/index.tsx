/**
 * Dashboard - Billing Tab
 * AWS resource usage and cost tracking
 */
import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import { BarChart, DonutChart, ProgressBar } from '../../../components/Charts';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }

const DashboardBillingPage: React.FC<PageProps> = ({ signOut, user }) => {
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
      case 'free': return '#4CAF50';
      case 'paid': return '#2196F3';
      case 'warning': return '#FF9800';
      default: return '#666';
    }
  };

  const formatCost = (cost: number) => {
    return cost === 0 ? 'Free' : `$${cost.toFixed(2)}`;
  };

  const formatUsage = (usage: number, unit: string) => {
    if (usage >= 1000000) return `${(usage / 1000000).toFixed(1)}M ${unit}`;
    if (usage >= 1000) return `${(usage / 1000).toFixed(1)}K ${unit}`;
    return `${usage} ${unit}`;
  };

  // Prepare chart data
  const chartData = billing?.services.slice(0, 10).map(s => ({
    label: s.service.replace('Amazon ', '').replace('AWS ', ''),
    value: s.usage,
  })) || [];

  const donutData = billing?.services.slice(0, 6).map(s => ({
    label: s.service.replace('Amazon ', '').replace('AWS ', ''),
    value: s.usage,
    color: s.status === 'free' ? '#4CAF50' : s.status === 'warning' ? '#FF9800' : '#2196F3',
  })) || [];

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="page">
        <PageHeader 
          title="AWS Billing" 
          subtitle="Resource usage and cost tracking"
          icon="billing"
          actions={
            <div className="header-actions">
              <button className="btn-secondary" onClick={loadBilling} disabled={loading}>
                ↻ {loading ? 'Loading...' : 'Refresh'}
              </button>
              <button 
                className={`btn-secondary ${view === 'list' ? 'active' : ''}`}
                onClick={() => setView('list')}
              >
                ☰ List
              </button>
              <button 
                className={`btn-secondary ${view === 'chart' ? 'active' : ''}`}
                onClick={() => setView('chart')}
              >
                ◫ Charts
              </button>
            </div>
          }
        />

        {/* Summary Cards */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#4CAF50' }}>
              {billing ? formatCost(billing.totalCost) : '-'}
            </div>
            <div className="stat-label">Total Cost (MTD)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{billing?.services.length || 0}</div>
            <div className="stat-label">Active Services</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#4CAF50' }}>
              {billing?.services.filter(s => s.status === 'free').length || 0}
            </div>
            <div className="stat-label">Within Free Tier</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#FF9800' }}>
              {billing?.services.filter(s => s.status === 'warning').length || 0}
            </div>
            <div className="stat-label">Near Limit</div>
          </div>
        </div>

        {/* Account Info */}
        <div className="section" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 13, color: '#666' }}>
            <span>◈ Account: 809904170947</span>
            <span>◈ Region: us-east-1</span>
            <span>◈ Period: {billing?.period || '-'}</span>
            <span>◈ Updated: {billing?.lastUpdated ? new Date(billing.lastUpdated).toLocaleString() : '-'}</span>
          </div>
        </div>

        {view === 'chart' && billing && (
          <div className="section">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 20 }}>
              <div style={{ background: '#fff', borderRadius: 12, padding: 20, border: '1px solid #e5e7eb' }}>
                <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>Usage by Service</h3>
                <BarChart data={chartData} height={250} />
              </div>
              <div style={{ background: '#fff', borderRadius: 12, padding: 20, border: '1px solid #e5e7eb' }}>
                <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>Service Distribution</h3>
                <DonutChart data={donutData} size={200} />
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
                      <td style={{ color: '#666', fontSize: 12 }}>{service.freeLimit}</td>
                      <td style={{ fontWeight: 500, color: service.cost > 0 ? '#2196F3' : '#4CAF50' }}>
                        {formatCost(service.cost)}
                      </td>
                      <td>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: 12,
                          fontSize: 11,
                          fontWeight: 500,
                          background: getStatusColor(service.status) + '20',
                          color: getStatusColor(service.status),
                        }}>
                          {service.status === 'free' ? '✓ Free Tier' : service.status === 'warning' ? '⚠ Near Limit' : '$ Paid'}
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
        <div className="section" style={{ marginTop: 20 }}>
          <div style={{ background: '#f0fdf4', borderRadius: 12, padding: 16, border: '1px solid #bbf7d0' }}>
            <h4 style={{ margin: '0 0 8px', fontSize: 13, color: '#166534' }}>◈ Free Tier Tips</h4>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: '#166534', lineHeight: 1.8 }}>
              <li>Lambda: 1M free requests/month, 400K GB-seconds compute</li>
              <li>DynamoDB: 25GB storage, 200M read/write requests</li>
              <li>S3: 5GB storage, 20K GET, 2K PUT requests</li>
              <li>API Gateway: 1M REST API calls/month</li>
              <li>Amplify: 1000 build minutes, 15GB hosting/month</li>
            </ul>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default DashboardBillingPage;
