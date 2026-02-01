/**
 * Voice IN CDR Dashboard
 * 
 * Displays Call Detail Records from Cloud Communication Platform
 * Inbound Number: +91 9319767034
 * Email: voice@wecare.digital
 * 
 * Tabs: CDR Logs, Statistics, Dialer
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { API_BASE } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'cdr' | 'stats' | 'dialer';

interface CDRRecord {
  id: string;
  vmSessionId: string;
  clientCorrelationId: string;
  customerId: string;
  timestamp: string;
  callType: 'INBOUND' | 'OUTBOUND';
  overallCallStatus: string;
  callerNumber: string;
  destinationNumber: string;
  calledNumber: string;
  callerId: string;
  durationSec: number;
  fromWaitingTimeSec: number;
  conversationDurationSec: number;
  billableDurationSec: number;
  callerNumberStatus: string;
  destinationNumberStatus: string;
  circleNameCaller: string;
  circleNameDestination: string;
  operatorNameCaller: string;
  operatorNameDestination: string;
  recordingURL: string;
  hangupStatus: string;
  hangupCause: string;
  createdAt: number;
}

interface CDRStats {
  total: number;
  inbound: number;
  outbound: number;
  answered: number;
  missed: number;
  busy: number;
  avgDuration: number;
  avgWaitTime: number;
  totalBillable: number;
  byCircle: Record<string, number>;
  byOperator: Record<string, number>;
}

// Stat Card Component
const StatCard: React.FC<{ label: string; value: number; icon: string; color: string }> = ({ label, value, icon, color }) => (
  <div style={{
    padding: '20px',
    background: 'white',
    borderRadius: '12px',
    border: '1px solid var(--color-border)',
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
      <span style={{ fontSize: '20px' }}>{icon}</span>
      <span style={{ fontSize: '13px', color: 'var(--color-muted)' }}>{label}</span>
    </div>
    <div style={{ fontSize: '28px', fontWeight: 700, color }}>{value}</div>
  </div>
);

const AirtelVoiceCDR: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('cdr');
  const [records, setRecords] = useState<CDRRecord[]>([]);
  const [stats, setStats] = useState<CDRStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Filters
  const [callTypeFilter, setCallTypeFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  // Dialer state
  const [dialerNumber, setDialerNumber] = useState('');
  const [calling, setCalling] = useState(false);

  // Fetch CDR records
  const fetchCDRRecords = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (callTypeFilter) params.append('callType', callTypeFilter);
      if (statusFilter) params.append('status', statusFilter);
      if (searchQuery) params.append('search', searchQuery);
      params.append('limit', '50');
      
      const response = await fetch(`${API_BASE}/voice-cdr-read?${params.toString()}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      setRecords(data.records || []);
      setStats(data.stats || null);
    } catch (err: any) {
      console.error('Failed to fetch CDR records:', err);
      setError(err.message || 'Failed to load CDR records');
      setRecords([]);
      setStats({
        total: 0, inbound: 0, outbound: 0, answered: 0, missed: 0, busy: 0,
        avgDuration: 0, avgWaitTime: 0, totalBillable: 0, byCircle: {}, byOperator: {}
      });
    } finally {
      setLoading(false);
    }
  }, [callTypeFilter, statusFilter, searchQuery]);

  useEffect(() => {
    fetchCDRRecords();
  }, [fetchCDRRecords]);

  // Format duration from seconds to mm:ss
  const formatDuration = (seconds: number): string => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Format timestamp
  const formatTimestamp = (epoch: number): string => {
    if (!epoch) return '-';
    const date = new Date(epoch * 1000);
    return date.toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  // Get status badge color
  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case 'answered': return '#10b981';
      case 'missed': return '#ef4444';
      case 'busy': return '#f59e0b';
      case 'disconnected': return '#6b7280';
      default: return '#6b7280';
    }
  };

  // Dialer handlers
  const handleDial = () => {
    if (!dialerNumber.trim()) return;
    setCalling(true);
    setTimeout(() => setCalling(false), 3000);
  };

  const handleKeyPress = (key: string) => {
    if (key === 'backspace') {
      setDialerNumber(prev => prev.slice(0, -1));
    } else if (key === 'call') {
      handleDial();
    } else {
      setDialerNumber(prev => prev + key);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Voice IN CDR | WECARE.DIGITAL"
        description="Voice IN Cloud Communication Platform - Call Detail Records"
      />
      <div className="page-content">
        <PageHeader 
          title="Voice IN CDR" 
          subtitle="Call Detail Records Dashboard"
          icon="voice"
        />

        {/* Info Banner */}
        <div style={{
          background: '#ffffff',
          color: '#111827',
          padding: '16px 20px',
          borderRadius: '12px',
          marginBottom: '24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          border: '1px solid #10B981'
        }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '16px', color: '#111827' }}>Inbound Number: +91 9319767034</div>
            <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
              Email: voice@wecare.digital | Cloud Communication Platform
            </div>
          </div>
          <button
            onClick={fetchCDRRecords}
            disabled={loading}
            className="refresh-btn"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>

        {/* Tabs */}
        <div className="tabs-nav" style={{ marginBottom: '24px', display: 'flex', gap: '8px' }}>
          {(['cdr', 'stats', 'dialer'] as TabType[]).map(tab => (
            <button
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'cdr' && 'CDR Logs'}
              {tab === 'stats' && 'Statistics'}
              {tab === 'dialer' && 'Dialer'}
            </button>
          ))}
        </div>

        {/* CDR LOGS TAB */}
        {activeTab === 'cdr' && (
          <div className="section">
            {/* Filters */}
            <div style={{
              display: 'flex',
              gap: '12px',
              marginBottom: '20px',
              flexWrap: 'wrap'
            }}>
              <select
                value={callTypeFilter}
                onChange={(e) => setCallTypeFilter(e.target.value)}
                className="filter-select"
              >
                <option value="">All Call Types</option>
                <option value="INBOUND">Inbound</option>
                <option value="OUTBOUND">Outbound</option>
              </select>
              
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="filter-select"
              >
                <option value="">All Status</option>
                <option value="Answered">Answered</option>
                <option value="Missed">Missed</option>
                <option value="Busy">Busy</option>
              </select>
              
              <input
                type="text"
                placeholder="Search by Call ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input"
                style={{ flex: 1, minWidth: '200px' }}
              />
            </div>

            {/* Error Message */}
            {error && (
              <div style={{
                padding: '12px 16px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                color: '#dc2626',
                marginBottom: '16px'
              }}>
                {error}
              </div>
            )}

            {/* CDR Table */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                <thead>
                  <tr style={{ background: 'var(--color-bg-secondary)' }}>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Date/Time</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Call ID</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Type</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Caller</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Destination</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Status</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Wait Time</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Duration</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Circle</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Recording</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={10} style={{ padding: '40px', textAlign: 'center', color: 'var(--color-muted)' }}>
                        Loading CDR records...
                      </td>
                    </tr>
                  ) : records.length === 0 ? (
                    <tr>
                      <td colSpan={10} style={{ padding: '40px', textAlign: 'center', color: 'var(--color-muted)' }}>
                        No CDR records found. Records will appear here when webhook data is received.
                      </td>
                    </tr>
                  ) : (
                    records.map((record) => (
                      <tr key={record.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <td style={{ padding: '12px' }}>
                          <div style={{ fontWeight: 500 }}>{formatTimestamp(record.createdAt)}</div>
                          <div style={{ fontSize: '12px', color: 'var(--color-muted)' }}>{record.timestamp}</div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                            {record.clientCorrelationId || record.vmSessionId?.slice(0, 12)}
                          </div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{
                            padding: '4px 8px',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: 500,
                            background: record.callType === 'INBOUND' ? '#dbeafe' : '#fef3c7',
                            color: record.callType === 'INBOUND' ? '#1d4ed8' : '#92400e'
                          }}>
                            {record.callType === 'INBOUND' ? 'Inbound' : 'Outbound'}
                          </span>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div>{record.callerNumber}</div>
                          <div style={{ fontSize: '12px', color: 'var(--color-muted)' }}>
                            {record.callerNumberStatus}
                          </div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div>{record.destinationNumber}</div>
                          <div style={{ fontSize: '12px', color: 'var(--color-muted)' }}>
                            {record.destinationNumberStatus}
                          </div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{
                            padding: '4px 10px',
                            borderRadius: '12px',
                            fontSize: '12px',
                            fontWeight: 500,
                            background: `${getStatusColor(record.overallCallStatus)}20`,
                            color: getStatusColor(record.overallCallStatus)
                          }}>
                            {record.overallCallStatus}
                          </span>
                        </td>
                        <td style={{ padding: '12px', fontFamily: 'monospace' }}>
                          {formatDuration(record.fromWaitingTimeSec)}
                        </td>
                        <td style={{ padding: '12px', fontFamily: 'monospace' }}>
                          {formatDuration(record.conversationDurationSec)}
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div>{record.circleNameCaller || '-'}</div>
                          <div style={{ fontSize: '12px', color: 'var(--color-muted)' }}>
                            {record.operatorNameCaller}
                          </div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          {record.recordingURL ? (
                            <a
                              href={record.recordingURL}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                padding: '6px 12px',
                                background: 'var(--color-primary)',
                                color: 'white',
                                borderRadius: '6px',
                                fontSize: '12px',
                                textDecoration: 'none'
                              }}
                            >
                              Play
                            </a>
                          ) : (
                            <span style={{ color: 'var(--color-muted)', fontSize: '12px' }}>-</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* STATISTICS TAB */}
        {activeTab === 'stats' && (
          <div className="section">
            <h3 className="section-title">Call Statistics</h3>
            
            {/* Summary Cards */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '16px',
              marginBottom: '24px'
            }}>
              <StatCard label="Total Calls" value={stats?.total || 0} icon="T" color="#6366f1" />
              <StatCard label="Inbound" value={stats?.inbound || 0} icon="I" color="#3b82f6" />
              <StatCard label="Outbound" value={stats?.outbound || 0} icon="O" color="#8b5cf6" />
              <StatCard label="Answered" value={stats?.answered || 0} icon="A" color="#10b981" />
              <StatCard label="Missed" value={stats?.missed || 0} icon="M" color="#ef4444" />
              <StatCard label="Busy" value={stats?.busy || 0} icon="B" color="#f59e0b" />
            </div>

            {/* Duration Stats */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
              gap: '16px',
              marginBottom: '24px'
            }}>
              <div style={{ padding: '20px', background: 'var(--color-bg-secondary)', borderRadius: '12px' }}>
                <div style={{ fontSize: '14px', color: 'var(--color-muted)', marginBottom: '8px' }}>
                  Avg. Conversation Duration
                </div>
                <div style={{ fontSize: '28px', fontWeight: 700 }}>
                  {formatDuration(stats?.avgDuration || 0)}
                </div>
              </div>
              <div style={{ padding: '20px', background: 'var(--color-bg-secondary)', borderRadius: '12px' }}>
                <div style={{ fontSize: '14px', color: 'var(--color-muted)', marginBottom: '8px' }}>
                  Avg. Customer Waiting Time
                </div>
                <div style={{ fontSize: '28px', fontWeight: 700 }}>
                  {formatDuration(stats?.avgWaitTime || 0)}
                </div>
              </div>
              <div style={{ padding: '20px', background: 'var(--color-bg-secondary)', borderRadius: '12px' }}>
                <div style={{ fontSize: '14px', color: 'var(--color-muted)', marginBottom: '8px' }}>
                  Total Billable Duration
                </div>
                <div style={{ fontSize: '28px', fontWeight: 700 }}>
                  {formatDuration(stats?.totalBillable || 0)}
                </div>
              </div>
            </div>

            {/* Circle and Operator Breakdown */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '20px'
            }}>
              <div style={{ padding: '20px', background: 'var(--color-bg-secondary)', borderRadius: '12px' }}>
                <h4 style={{ marginBottom: '16px' }}>Calls by Circle (State)</h4>
                {stats?.byCircle && Object.keys(stats.byCircle).length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {Object.entries(stats.byCircle)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 10)
                      .map(([circle, count]) => (
                        <div key={circle} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>{circle}</span>
                          <span style={{
                            padding: '2px 8px',
                            background: 'var(--color-primary)',
                            color: 'white',
                            borderRadius: '12px',
                            fontSize: '12px'
                          }}>{count}</span>
                        </div>
                      ))}
                  </div>
                ) : (
                  <div style={{ color: 'var(--color-muted)', fontSize: '14px' }}>No data available</div>
                )}
              </div>

              <div style={{ padding: '20px', background: 'var(--color-bg-secondary)', borderRadius: '12px' }}>
                <h4 style={{ marginBottom: '16px' }}>Calls by Operator</h4>
                {stats?.byOperator && Object.keys(stats.byOperator).length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {Object.entries(stats.byOperator)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 10)
                      .map(([operator, count]) => (
                        <div key={operator} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>{operator}</span>
                          <span style={{
                            padding: '2px 8px',
                            background: '#d1fae5',
                            color: '#111827',
                            borderRadius: '12px',
                            fontSize: '12px'
                          }}>{count}</span>
                        </div>
                      ))}
                  </div>
                ) : (
                  <div style={{ color: 'var(--color-muted)', fontSize: '14px' }}>No data available</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* DIALER TAB */}
        {activeTab === 'dialer' && (
          <div className="section">
            <h3 className="section-title">Voice Dialer</h3>
            <p style={{ color: 'var(--color-muted)', marginBottom: '20px' }}>
              Make outbound voice calls using Cloud Communication Platform.
            </p>

            <div style={{ maxWidth: '320px', margin: '0 auto' }}>
              <div style={{
                background: 'var(--color-bg-secondary)',
                padding: '20px',
                borderRadius: '12px',
                marginBottom: '16px',
                textAlign: 'center',
              }}>
                <input
                  type="text"
                  value={dialerNumber}
                  onChange={(e) => setDialerNumber(e.target.value.replace(/[^0-9+]/g, ''))}
                  placeholder="Enter phone number"
                  style={{
                    width: '100%',
                    fontSize: '24px',
                    fontWeight: 600,
                    textAlign: 'center',
                    border: 'none',
                    background: 'transparent',
                    outline: 'none',
                    letterSpacing: '2px',
                  }}
                />
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '12px',
                marginBottom: '16px',
              }}>
                {['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'].map(key => (
                  <button
                    key={key}
                    onClick={() => handleKeyPress(key)}
                    className="dialer-key"
                  >
                    {key}
                  </button>
                ))}
              </div>

              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  onClick={() => handleKeyPress('backspace')}
                  className="action-btn"
                  style={{ flex: 1 }}
                >
                  Delete
                </button>
                <button
                  onClick={handleDial}
                  disabled={!dialerNumber.trim() || calling}
                  className="action-btn"
                  style={{ flex: 2 }}
                >
                  {calling ? 'Calling...' : 'Call'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* CDR Field Reference */}
        <div style={{
          marginTop: '24px',
          padding: '16px',
          background: '#ECFDF5',
          borderRadius: '13px',
          borderLeft: '4px solid #10B981'
        }}>
          <strong>CDR Webhook</strong>
          <p style={{ margin: '8px 0 0', fontSize: '13px', color: '#666' }}>
            Webhook receives CDR data including: vmSessionId, clientCorrelationId, callType, overallCallStatus, 
            duration fields, caller/destination numbers, circle/operator info, and recording URLs.
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default AirtelVoiceCDR;
