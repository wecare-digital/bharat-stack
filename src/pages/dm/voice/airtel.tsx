/**
 * Voice IN CDR Dashboard
 * 
 * Displays Call Detail Records from Cloud Communication Platform
 * Inbound Number: +91 9319767034
 * Email: voice@wecare.digital
 * 
 * Tabs: CDR Logs, Statistics, Dialer
 * Features: Click-to-Call (C2C), Callback, Outbound calls
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import { API_BASE } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
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

const AirtelVoiceCDR: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
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
  const [agentNumber, setAgentNumber] = useState('');
  const [calling, setCalling] = useState(false);
  const [callResult, setCallResult] = useState<{ success: boolean; message: string } | null>(null);
  const [enableRecording, setEnableRecording] = useState(true);

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

  // Click-to-Call handler (C2C)
  const handleClickToCall = async () => {
    if (!dialerNumber.trim() || !agentNumber.trim()) {
      setCallResult({ success: false, message: 'Both agent number and customer number are required' });
      return;
    }
    
    setCalling(true);
    setCallResult(null);
    
    try {
      const response = await fetch(`${API_BASE}/voice/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          callType: 'c2c',
          fromNumber: agentNumber.trim(),
          toNumber: dialerNumber.trim(),
          enableRecording: enableRecording,
          provider: 'airtel_ccp'
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setCallResult({ 
          success: true, 
          message: `Call initiated! Correlation ID: ${data.correlationId || data.callId}` 
        });
      } else {
        setCallResult({ 
          success: false, 
          message: data.error || 'Failed to initiate call' 
        });
      }
    } catch (err: any) {
      setCallResult({ success: false, message: err.message || 'Network error' });
    } finally {
      setCalling(false);
    }
  };

  // Callback handler - calls customer first, then connects to agent
  const handleCallback = async (customerNumber: string) => {
    if (!agentNumber.trim()) {
      setCallResult({ success: false, message: 'Please enter your agent number first' });
      setActiveTab('dialer');
      return;
    }
    
    setCalling(true);
    setCallResult(null);
    
    try {
      const response = await fetch(`${API_BASE}/voice/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          callType: 'c2c',
          fromNumber: agentNumber.trim(),
          toNumber: customerNumber,
          enableRecording: true,
          provider: 'airtel_ccp'
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setCallResult({ 
          success: true, 
          message: `Callback initiated to ${customerNumber}` 
        });
      } else {
        setCallResult({ 
          success: false, 
          message: data.error || 'Failed to initiate callback' 
        });
      }
    } catch (err: any) {
      setCallResult({ success: false, message: err.message || 'Network error' });
    } finally {
      setCalling(false);
    }
  };

  // Dialer handlers
  const handleKeyPress = (key: string) => {
    if (key === 'backspace') {
      setDialerNumber(prev => prev.slice(0, -1));
    } else if (key === 'call') {
      handleClickToCall();
    } else {
      setDialerNumber(prev => prev + key);
    }
  };

  const content = (
    <>
      <SEO 
        title="Voice IN CDR | WECARE.DIGITAL"
        description="Voice IN Cloud Communication Platform - Call Detail Records"
      />
      <div className="page-content" style={{ height: embedded ? '100%' : 'auto' }}>
        {!embedded && (
          <PageHeader 
            title="Voice IN CDR" 
            subtitle="Call Detail Records Dashboard"
            icon="voice"
          />
        )}

        {/* Info Banner */}
        <div className="info-banner" style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '16px', color: '#065f46' }}>Inbound Number: +91 9319767034</div>
            <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
              Email: voice@wecare.digital | Cloud Communication Platform
            </div>
          </div>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={fetchCDRRecords} disabled={loading} loading={loading} />
        </div>

        {/* Call Result Toast */}
        {callResult && (
          <div style={{
            padding: '12px 16px',
            background: callResult.success ? '#d1fae5' : '#f3f4f6',
            border: `1px solid ${callResult.success ? '#a7f3d0' : '#d1d5db'}`,
            borderRadius: '8px',
            color: callResult.success ? '#065f46' : '#6b7280',
            marginBottom: '16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <span>{callResult.message}</span>
            <button 
              onClick={() => setCallResult(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px' }}
            >
              ×
            </button>
          </div>
        )}

        {/* Tabs */}
        <div className="tabs" style={{ marginBottom: '24px' }}>
          {(['cdr', 'stats', 'dialer'] as TabType[]).map(tab => (
            <button
              key={tab}
              className={`tab ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'cdr' && 'CDR Logs'}
              {tab === 'stats' && 'Statistics'}
              {tab === 'dialer' && 'Click-to-Call'}
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
                background: '#f3f4f6',
                border: '1px solid #d1d5db',
                borderRadius: '8px',
                color: '#6b7280',
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
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Actions</th>
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
                            background: record.callType === 'INBOUND' ? '#f5f5f5' : '#f0fdf4',
                            color: record.callType === 'INBOUND' ? '#000' : '#065f46'
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
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            {/* Callback Button - for inbound calls */}
                            {record.callType === 'INBOUND' && record.callerNumber && (
                              <button
                                onClick={() => handleCallback(record.callerNumber)}
                                disabled={calling}
                                title={`Callback ${record.callerNumber}`}
                                style={{
                                  padding: '6px 10px',
                                  background: '#10b981',
                                  color: 'white',
                                  borderRadius: '6px',
                                  fontSize: '12px',
                                  border: 'none',
                                  cursor: calling ? 'not-allowed' : 'pointer',
                                  opacity: calling ? 0.6 : 1,
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px'
                                }}
                              >
                                📞 Callback
                              </button>
                            )}
                            {/* Recording Button */}
                            {record.recordingURL ? (
                              <a
                                href={record.recordingURL}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  padding: '6px 10px',
                                  background: 'var(--color-primary)',
                                  color: 'white',
                                  borderRadius: '6px',
                                  fontSize: '12px',
                                  textDecoration: 'none',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px'
                                }}
                              >
                                🎵 Play
                              </a>
                            ) : (
                              <span style={{ color: 'var(--color-muted)', fontSize: '12px' }}>-</span>
                            )}
                          </div>
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
              <StatCard label="Total Calls" value={stats?.total || 0} icon="T" color="#000" />
              <StatCard label="Inbound" value={stats?.inbound || 0} icon="I" color="#4a4a4a" />
              <StatCard label="Outbound" value={stats?.outbound || 0} icon="O" color="#6b6b6b" />
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

        {/* DIALER TAB - Click-to-Call */}
        {activeTab === 'dialer' && (
          <div className="section">
            <h3 className="section-title">Click-to-Call (C2C)</h3>
            <p style={{ color: 'var(--color-muted)', marginBottom: '20px' }}>
              Connect two participants via Airtel CCP. The agent is called first, then connected to the customer.
            </p>

            <div style={{ maxWidth: '400px', margin: '0 auto' }}>
              {/* Agent Number Input */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500, fontSize: '14px' }}>
                  Your Number (Agent)
                </label>
                <input
                  type="tel"
                  value={agentNumber}
                  onChange={(e) => setAgentNumber(e.target.value.replace(/[^0-9+]/g, ''))}
                  placeholder="Enter your 10-digit number"
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    fontSize: '16px',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    outline: 'none',
                  }}
                />
                <div style={{ fontSize: '12px', color: 'var(--color-muted)', marginTop: '4px' }}>
                  You will receive the call first, then be connected to the customer
                </div>
              </div>

              {/* Customer Number Display */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500, fontSize: '14px' }}>
                  Customer Number
                </label>
                <div style={{
                  background: 'var(--color-bg-secondary)',
                  padding: '16px',
                  borderRadius: '8px',
                  marginBottom: '8px',
                }}>
                  <input
                    type="tel"
                    value={dialerNumber}
                    onChange={(e) => setDialerNumber(e.target.value.replace(/[^0-9+]/g, ''))}
                    placeholder="Enter customer number"
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
              </div>

              {/* Dial Pad */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '10px',
                marginBottom: '16px',
              }}>
                {['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'].map(key => (
                  <button
                    key={key}
                    onClick={() => handleKeyPress(key)}
                    className="dialer-key"
                    style={{
                      padding: '16px',
                      fontSize: '20px',
                      fontWeight: 600,
                      border: '1px solid var(--color-border)',
                      borderRadius: '8px',
                      background: 'white',
                      cursor: 'pointer',
                    }}
                  >
                    {key}
                  </button>
                ))}
              </div>

              {/* Recording Toggle */}
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                marginBottom: '16px',
                padding: '12px',
                background: 'var(--color-bg-secondary)',
                borderRadius: '8px'
              }}>
                <input
                  type="checkbox"
                  id="enableRecording"
                  checked={enableRecording}
                  onChange={(e) => setEnableRecording(e.target.checked)}
                  style={{ width: '18px', height: '18px' }}
                />
                <label htmlFor="enableRecording" style={{ fontSize: '14px', cursor: 'pointer' }}>
                  Enable call recording
                </label>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '12px' }}>
                <Button
                  variant="secondary"
                  onClick={() => handleKeyPress('backspace')}
                  style={{ flex: 1 }}
                >
                  ⌫ Delete
                </Button>
                <Button
                  variant="primary"
                  onClick={handleClickToCall}
                  disabled={!dialerNumber.trim() || !agentNumber.trim() || calling}
                  loading={calling}
                  style={{ flex: 2 }}
                >
                  {calling ? '📞 Connecting...' : '📞 Click to Call'}
                </Button>
              </div>

              {/* How it works */}
              <div style={{
                marginTop: '24px',
                padding: '16px',
                background: '#f0fdf4',
                borderRadius: '8px',
                border: '1px solid #bbf7d0'
              }}>
                <div style={{ fontWeight: 600, marginBottom: '8px', color: '#166534' }}>How Click-to-Call Works:</div>
                <ol style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#166534', lineHeight: 1.6 }}>
                  <li>You (agent) receive a call on your number</li>
                  <li>Once you answer, the customer is called</li>
                  <li>Both parties are connected with optional recording</li>
                  <li>CDR with recording URL is sent to webhook</li>
                </ol>
              </div>
            </div>
          </div>
        )}

        {/* CDR Field Reference */}
        <div className="info-banner" style={{
          marginTop: '24px',
          borderLeft: '4px solid #10B981'
        }}>
          <strong>Airtel CCP Click-to-Call API</strong>
          <p style={{ margin: '8px 0 0', fontSize: '13px', color: '#6b7280' }}>
            Click-to-Call connects two participants with recording. Agent receives call first, then customer is patched in.
            CDR webhook receives: correlationId, callType, overallCallStatus, duration fields, participant info, and recording URLs.
          </p>
        </div>
      </div>
    </>
  );

  if (embedded) {
    return content;
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      {content}
    </Layout>
  );
};

export default AirtelVoiceCDR;
