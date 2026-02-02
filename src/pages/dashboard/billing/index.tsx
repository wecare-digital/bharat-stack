/**
 * Dashboard - Billing Tab
 * AWS Billing, Health, and Trusted Advisor
 */

import { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { BarChart } from '../../../components/Charts';
import * as api from '../../../api/client';
import { RefreshIcon } from '../../../lib/icons';

interface PageProps { signOut?: () => void; user?: any; }

// Generate last 12 months for dropdown
function getMonthOptions() {
  const months = [];
  const now = new Date();
  for (let i = 0; i < 12; i++) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push({
      value: -i,
      label: date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }),
      key: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`,
    });
  }
  return months;
}

export default function DashboardBillingPage({ signOut, user }: PageProps) {
  const [billing, setBilling] = useState<api.AWSBillingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'billing' | 'health' | 'advisor'>('billing');
  const [view, setView] = useState<'list' | 'chart'>('list');
  const [selectedMonth, setSelectedMonth] = useState(0);
  const monthOptions = getMonthOptions();

  useEffect(() => {
    loadBilling(selectedMonth);
  }, [selectedMonth]);

  const loadBilling = async (month: number = 0) => {
    setLoading(true);
    try {
      const data = await api.getAWSBilling(month);
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
        title="AWS Billing & Health | WECARE.DIGITAL"
        description="Billing, Health, and Trusted Advisor"
      />
      <div className="page-content">
        <PageHeader 
          title="AWS Management" 
          subtitle="Billing, Health & Trusted Advisor"
          icon="billing"
          actions={
            <div className="header-actions">
              <button className="btn-secondary" onClick={() => loadBilling(selectedMonth)} disabled={loading} title="Refresh">
                {loading ? '...' : <RefreshIcon size={18} />}
              </button>
            </div>
          }
        />

        {/* Tab Navigation */}
        <div className="tab-bar" style={{ marginBottom: '20px' }}>
          <button 
            className={`tab-btn ${activeTab === 'billing' ? 'active' : ''}`}
            onClick={() => setActiveTab('billing')}
          >
            💰 Billing
            {billing && billing.totalCost > 0 && (
              <span className="tab-badge" style={{ background: '#fef3c7', color: '#92400e' }}>
                ${billing.totalCost.toFixed(0)}
              </span>
            )}
          </button>
          <button 
            className={`tab-btn ${activeTab === 'health' ? 'active' : ''}`}
            onClick={() => setActiveTab('health')}
          >
            🏥 Health
            {billing?.health && billing.health.openIssues > 0 && (
              <span className="tab-badge" style={{ background: '#fee2e2', color: '#dc2626' }}>
                {billing.health.openIssues}
              </span>
            )}
          </button>
          <button 
            className={`tab-btn ${activeTab === 'advisor' ? 'active' : ''}`}
            onClick={() => setActiveTab('advisor')}
          >
            🛡️ Trusted Advisor
            {billing?.trustedAdvisor && (billing.trustedAdvisor.actionRecommended > 0 || billing.trustedAdvisor.investigationRecommended > 0) && (
              <span className="tab-badge" style={{ background: '#fef3c7', color: '#92400e' }}>
                {billing.trustedAdvisor.actionRecommended + billing.trustedAdvisor.investigationRecommended}
              </span>
            )}
          </button>
        </div>

        {/* Billing Tab */}
        {activeTab === 'billing' && (
          <>
            {/* View Toggle */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px', gap: '8px' }}>
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

        {/* Summary Cards */}
        <div className="stats-grid">
          <div className="stat-card" style={{ background: billing && billing.totalCost > 0 ? '#fef3c7' : '#ecfdf5' }}>
            <div className="stat-value" style={{ color: billing && billing.totalCost > 0 ? '#d97706' : 'var(--color-success)' }}>
              ${billing ? billing.totalCost.toFixed(2) : '0.00'}
            </div>
            <div className="stat-label">{selectedMonth === 0 ? 'Current Month (MTD)' : 'Total Cost'}</div>
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
            <div className="stat-value" style={{ color: '#dc2626' }}>
              {billing?.services.filter(s => s.status === 'paid').length || 0}
            </div>
            <div className="stat-label">Paid Services</div>
          </div>
        </div>

        {/* Month Filter & Account Info */}
        <div className="section" style={{ marginBottom: '20px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ fontSize: '13px', fontWeight: 500 }}>Invoice Month:</label>
              <select 
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(Number(e.target.value))}
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-bg)',
                  fontSize: '13px',
                  minWidth: '180px',
                }}
              >
                {monthOptions.map((opt) => (
                  <option key={opt.key} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div style={{ 
              display: 'flex', 
              gap: '20px', 
              flexWrap: 'wrap', 
              fontSize: '13px', 
              color: 'var(--color-muted)' 
            }}>
              <span>Account: {billing?.accountId || '809904170947'}</span>
              <span>Currency: {billing?.currency || 'USD'}</span>
              <span>Period: {billing?.period || '-'}</span>
            </div>
          </div>
        </div>

        {/* Previous Month Comparison (only for current month) */}
        {selectedMonth === 0 && billing?.previousMonthCost !== undefined && (
          <div className="section" style={{ marginBottom: '20px', background: '#f0f9ff', borderColor: '#bae6fd' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <span style={{ fontSize: '13px', color: '#0369a1' }}>Previous Month Total: </span>
                <strong style={{ fontSize: '16px', color: '#0c4a6e' }}>${billing.previousMonthCost.toFixed(2)}</strong>
              </div>
              <div style={{ fontSize: '13px', color: '#0369a1' }}>
                {billing.totalCost < billing.previousMonthCost 
                  ? `↓ ${((billing.previousMonthCost - billing.totalCost) / billing.previousMonthCost * 100).toFixed(0)}% less so far`
                  : billing.totalCost > billing.previousMonthCost
                    ? `↑ ${((billing.totalCost - billing.previousMonthCost) / billing.previousMonthCost * 100).toFixed(0)}% more than last month`
                    : 'Same as last month'
                }
              </div>
            </div>
          </div>
        )}

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

        {/* Cost Optimizer Recommendations */}
        {billing?.recommendations && billing.recommendations.length > 0 && (
          <div className="section" style={{ marginTop: '20px' }}>
            <h3 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px' }}>💡</span>
              Cost Optimization Recommendations
              <span style={{ 
                background: '#fef3c7', 
                color: '#92400e', 
                padding: '2px 8px', 
                borderRadius: '12px', 
                fontSize: '12px',
                fontWeight: 500
              }}>
                Save up to ${billing.recommendations.reduce((sum, r) => sum + (r.potentialSavings || 0), 0).toFixed(2)}/month
              </span>
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
              {billing.recommendations.map((rec, idx) => (
                <div 
                  key={idx} 
                  style={{ 
                    padding: '16px',
                    borderRadius: '8px',
                    border: '1px solid',
                    borderColor: rec.severity === 'high' ? '#fca5a5' : rec.severity === 'medium' ? '#fcd34d' : rec.severity === 'info' ? '#93c5fd' : '#d1d5db',
                    background: rec.severity === 'high' ? '#fef2f2' : rec.severity === 'medium' ? '#fffbeb' : rec.severity === 'info' ? '#eff6ff' : '#f9fafb',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '250px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span style={{ 
                          fontSize: '11px', 
                          fontWeight: 600, 
                          textTransform: 'uppercase',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: rec.severity === 'high' ? '#dc2626' : rec.severity === 'medium' ? '#d97706' : rec.severity === 'info' ? '#2563eb' : '#6b7280',
                          color: 'white'
                        }}>
                          {rec.severity}
                        </span>
                        <strong style={{ fontSize: '14px' }}>{rec.title}</strong>
                      </div>
                      <p style={{ margin: '8px 0', fontSize: '13px', color: '#4b5563', lineHeight: 1.5 }}>
                        {rec.description}
                      </p>
                      <div style={{ fontSize: '12px', color: '#6b7280' }}>
                        <strong>Action:</strong> {rec.action}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      {rec.potentialSavings > 0 && (
                        <div style={{ 
                          fontSize: '18px', 
                          fontWeight: 700, 
                          color: '#059669',
                          marginBottom: '8px'
                        }}>
                          Save ${rec.potentialSavings.toFixed(2)}
                        </div>
                      )}
                      {rec.link && (
                        <a 
                          href={rec.link} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          style={{
                            display: 'inline-block',
                            padding: '6px 12px',
                            background: '#2563eb',
                            color: 'white',
                            borderRadius: '6px',
                            fontSize: '12px',
                            textDecoration: 'none',
                          }}
                        >
                          Open Console →
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Free Tier Tips */}
        <div className="section" style={{ background: '#ecfdf5', borderColor: '#a7f3d0' }}>
          <h3 className="section-title" style={{ color: '#111827' }}>Free Tier Tips</h3>
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
          </>
        )}

        {/* Health Tab */}
        {activeTab === 'health' && (
          <>
            {/* Health Summary Cards */}
            <div className="stats-grid">
              <div className="stat-card" style={{ background: billing?.health?.openIssues === 0 ? '#ecfdf5' : '#fef2f2' }}>
                <div className="stat-value" style={{ color: billing?.health?.openIssues === 0 ? '#059669' : '#dc2626' }}>
                  {billing?.health?.openIssues ?? 0}
                </div>
                <div className="stat-label">Open Issues</div>
              </div>
              <div className="stat-card">
                <div className="stat-value" style={{ color: '#2563eb' }}>
                  {billing?.health?.scheduledChanges ?? 0}
                </div>
                <div className="stat-label">Scheduled Changes</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {billing?.health?.otherNotifications ?? 0}
                </div>
                <div className="stat-label">Other Notifications</div>
              </div>
              <div className="stat-card" style={{ background: billing?.health?.status === 'healthy' ? '#ecfdf5' : '#fef3c7' }}>
                <div className="stat-value" style={{ color: billing?.health?.status === 'healthy' ? '#059669' : '#d97706' }}>
                  {billing?.health?.status === 'healthy' ? '✓' : '⚠'}
                </div>
                <div className="stat-label">Overall Status</div>
              </div>
            </div>

            {/* Health Events */}
            {billing?.health?.events && billing.health.events.length > 0 && (
              <div className="section" style={{ marginTop: '20px' }}>
                <h3 className="section-title">Open Issues</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {billing.health.events.map((event: any, idx: number) => (
                    <div key={idx} style={{ 
                      padding: '16px', 
                      borderRadius: '8px', 
                      border: '1px solid #fca5a5',
                      background: '#fef2f2'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <strong>{event.service}</strong>
                          <p style={{ margin: '4px 0', fontSize: '13px', color: '#4b5563' }}>
                            {event.eventTypeCode}
                          </p>
                          <span style={{ fontSize: '12px', color: '#6b7280' }}>
                            Region: {event.region} | Started: {event.startTime ? new Date(event.startTime).toLocaleString() : 'N/A'}
                          </span>
                        </div>
                        <span className="badge error">{event.statusCode}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Scheduled Changes */}
            {billing?.health?.scheduledEvents && billing.health.scheduledEvents.length > 0 && (
              <div className="section" style={{ marginTop: '20px' }}>
                <h3 className="section-title">Scheduled Changes</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {billing.health.scheduledEvents.map((event: any, idx: number) => (
                    <div key={idx} style={{ 
                      padding: '16px', 
                      borderRadius: '8px', 
                      border: '1px solid #93c5fd',
                      background: '#eff6ff'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <strong>{event.service}</strong>
                          <p style={{ margin: '4px 0', fontSize: '13px', color: '#4b5563' }}>
                            {event.eventTypeCode}
                          </p>
                          <span style={{ fontSize: '12px', color: '#6b7280' }}>
                            Region: {event.region} | Scheduled: {event.startTime ? new Date(event.startTime).toLocaleString() : 'N/A'}
                          </span>
                        </div>
                        <span className="badge info">Scheduled</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* No Issues Message */}
            {billing?.health?.openIssues === 0 && billing?.health?.scheduledChanges === 0 && (
              <div className="section" style={{ background: '#ecfdf5', borderColor: '#a7f3d0', textAlign: 'center', padding: '40px' }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>✓</div>
                <h3 style={{ color: '#059669', margin: '0 0 8px 0' }}>All Systems Healthy</h3>
                <p style={{ color: '#6b7280', margin: 0 }}>No open issues or scheduled changes affecting your account.</p>
              </div>
            )}

            {/* Health Info */}
            <div className="section" style={{ marginTop: '20px', background: '#f0f9ff', borderColor: '#bae6fd' }}>
              <h3 className="section-title" style={{ color: '#0369a1' }}>About AWS Health</h3>
              <p style={{ fontSize: '13px', color: '#4b5563', margin: 0, lineHeight: 1.6 }}>
                AWS Health provides personalized information about events that can affect your AWS infrastructure. 
                It shows service events, scheduled changes, and account-specific notifications.
              </p>
              <a 
                href="https://health.aws.amazon.com/health/home" 
                target="_blank" 
                rel="noopener noreferrer"
                style={{ display: 'inline-block', marginTop: '12px', color: '#2563eb', fontSize: '13px' }}
              >
                Open AWS Health Dashboard →
              </a>
            </div>
          </>
        )}

        {/* Trusted Advisor Tab */}
        {activeTab === 'advisor' && (
          <>
            {/* Advisor Summary Cards */}
            <div className="stats-grid">
              <div className="stat-card" style={{ background: '#fef2f2' }}>
                <div className="stat-value" style={{ color: '#dc2626' }}>
                  {billing?.trustedAdvisor?.actionRecommended ?? 0}
                </div>
                <div className="stat-label">Action Recommended</div>
              </div>
              <div className="stat-card" style={{ background: '#fef3c7' }}>
                <div className="stat-value" style={{ color: '#d97706' }}>
                  {billing?.trustedAdvisor?.investigationRecommended ?? 0}
                </div>
                <div className="stat-label">Investigation Recommended</div>
              </div>
              <div className="stat-card" style={{ background: '#ecfdf5' }}>
                <div className="stat-value" style={{ color: '#059669' }}>
                  {billing?.trustedAdvisor?.noProblemsDetected ?? 0}
                </div>
                <div className="stat-label">No Problems</div>
              </div>
              <div className="stat-card">
                <div className="stat-value" style={{ color: '#6b7280' }}>
                  {billing?.trustedAdvisor?.notAvailable ?? 0}
                </div>
                <div className="stat-label">Not Available</div>
              </div>
            </div>

            {/* Category Breakdown */}
            {billing?.trustedAdvisor?.categories && (
              <div className="section" style={{ marginTop: '20px' }}>
                <h3 className="section-title">Check Categories</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                  {Object.entries(billing.trustedAdvisor.categories).map(([category, counts]: [string, any]) => (
                    <div key={category} style={{ 
                      padding: '16px', 
                      borderRadius: '8px', 
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg-secondary)'
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: '8px', textTransform: 'capitalize' }}>
                        {category.replace('_', ' ')}
                      </div>
                      <div style={{ display: 'flex', gap: '12px', fontSize: '13px' }}>
                        <span style={{ color: '#dc2626' }}>❌ {counts.error}</span>
                        <span style={{ color: '#d97706' }}>⚠️ {counts.warning}</span>
                        <span style={{ color: '#059669' }}>✓ {counts.ok}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Checks with Issues */}
            {billing?.trustedAdvisor?.checks && billing.trustedAdvisor.checks.length > 0 && (
              <div className="section" style={{ marginTop: '20px' }}>
                <h3 className="section-title">Checks Requiring Attention</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {billing.trustedAdvisor.checks.map((check: any, idx: number) => (
                    <div key={idx} style={{ 
                      padding: '16px', 
                      borderRadius: '8px', 
                      border: '1px solid',
                      borderColor: check.status === 'error' ? '#fca5a5' : '#fcd34d',
                      background: check.status === 'error' ? '#fef2f2' : '#fffbeb'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <span style={{ 
                              fontSize: '11px', 
                              fontWeight: 600, 
                              textTransform: 'uppercase',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: check.status === 'error' ? '#dc2626' : '#d97706',
                              color: 'white'
                            }}>
                              {check.status === 'error' ? 'Action' : 'Warning'}
                            </span>
                            <strong style={{ fontSize: '14px' }}>{check.name}</strong>
                          </div>
                          <p style={{ margin: '8px 0', fontSize: '13px', color: '#4b5563' }}>
                            {check.description}
                          </p>
                          <div style={{ fontSize: '12px', color: '#6b7280' }}>
                            Category: {check.category.replace('_', ' ')} | Resources flagged: {check.resourcesFlagged}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* No Issues Message */}
            {billing?.trustedAdvisor?.actionRecommended === 0 && billing?.trustedAdvisor?.investigationRecommended === 0 && (
              <div className="section" style={{ background: '#ecfdf5', borderColor: '#a7f3d0', textAlign: 'center', padding: '40px' }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>🛡️</div>
                <h3 style={{ color: '#059669', margin: '0 0 8px 0' }}>All Checks Passed</h3>
                <p style={{ color: '#6b7280', margin: 0 }}>No action or investigation recommended by Trusted Advisor.</p>
              </div>
            )}

            {/* Error Message */}
            {billing?.trustedAdvisor?.error && (
              <div className="section" style={{ background: '#fef3c7', borderColor: '#fcd34d' }}>
                <h3 className="section-title" style={{ color: '#92400e' }}>⚠️ Limited Access</h3>
                <p style={{ fontSize: '13px', color: '#78350f', margin: 0 }}>
                  {billing.trustedAdvisor.error}
                </p>
                <p style={{ fontSize: '13px', color: '#78350f', margin: '8px 0 0 0' }}>
                  Full Trusted Advisor access requires AWS Business or Enterprise Support plan.
                </p>
              </div>
            )}

            {/* Trusted Advisor Info */}
            <div className="section" style={{ marginTop: '20px', background: '#f0f9ff', borderColor: '#bae6fd' }}>
              <h3 className="section-title" style={{ color: '#0369a1' }}>About Trusted Advisor</h3>
              <p style={{ fontSize: '13px', color: '#4b5563', margin: 0, lineHeight: 1.6 }}>
                AWS Trusted Advisor inspects your AWS environment and provides recommendations for cost optimization, 
                security, fault tolerance, performance, and service limits.
              </p>
              <a 
                href="https://console.aws.amazon.com/trustedadvisor/home" 
                target="_blank" 
                rel="noopener noreferrer"
                style={{ display: 'inline-block', marginTop: '12px', color: '#2563eb', fontSize: '13px' }}
              >
                Open Trusted Advisor Console →
              </a>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
