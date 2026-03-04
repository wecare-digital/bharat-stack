/**
 * WhatsApp Flow Responses
 * View submit requests and flow interaction logs from WhatsApp Flows
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const FlowResponsesPage: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const toast = useToastContext();
  const [activeSection, setActiveSection] = useState<'requests' | 'logs'>('requests');
  const [requests, setRequests] = useState<api.SubmitRequest[]>([]);
  const [logs, setLogs] = useState<api.FlowLog[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [phoneFilter, setPhoneFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [requestsError, setRequestsError] = useState<string | null>(null);
  const [logsError, setLogsError] = useState<string | null>(null);

  const loadRequests = useCallback(async () => {
    setRequestsLoading(true);
    setRequestsError(null);
    try {
      const data = await api.listSubmitRequests(statusFilter || undefined);
      setRequests(data);
    } catch (e: any) {
      const msg = e?.message || 'Failed to load requests';
      setRequestsError(msg);
      toast.error(msg);
    }
    setRequestsLoading(false);
  }, [statusFilter, toast]);

  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    setLogsError(null);
    try {
      const data = await api.listFlowLogs(phoneFilter || undefined);
      setLogs(data);
    } catch (e: any) {
      const msg = e?.message || 'Failed to load flow logs';
      setLogsError(msg);
      toast.error(msg);
    }
    setLogsLoading(false);
  }, [phoneFilter, toast]);

  useEffect(() => {
    if (activeSection === 'requests') loadRequests();
    else loadLogs();
  }, [activeSection, loadRequests, loadLogs]);

  const formatDate = (ts: number) => {
    if (!ts) return '-';
    return new Date(ts * 1000).toLocaleString();
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: '#059669', paid: '#059669', completed: '#059669', failed: '#059669', expired: '#9ca3af',
    };
    return (
      <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, color: '#fff', background: colors[status] || '#6b7280' }}>
        {status?.toUpperCase() || 'UNKNOWN'}
      </span>
    );
  };

  const content = (
    <>
      <SEO title="Flow Responses" description="WhatsApp Flow Responses & Logs" noindex />
      <div style={{ padding: '16px 24px', maxWidth: 1200, margin: '0 auto', background: '#fff' }}>
        <h2 style={{ margin: '0 0 16px', fontSize: 20 }}>Flow Responses</h2>

        {/* Section Tabs */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <button onClick={() => setActiveSection('requests')}
            style={{ padding: '8px 16px', borderRadius: 6, border: activeSection === 'requests' ? '2px solid #059669' : '1px solid #ddd', background: activeSection === 'requests' ? '#ecfdf5' : '#fff', cursor: 'pointer', fontSize: 13, fontWeight: activeSection === 'requests' ? 600 : 400 }}>
            Submit Requests ({requests.length})
          </button>
          <button onClick={() => setActiveSection('logs')}
            style={{ padding: '8px 16px', borderRadius: 6, border: activeSection === 'logs' ? '2px solid #059669' : '1px solid #ddd', background: activeSection === 'logs' ? '#ecfdf5' : '#fff', cursor: 'pointer', fontSize: 13, fontWeight: activeSection === 'logs' ? 600 : 400 }}>
            Flow Interaction Logs ({logs.length})
          </button>
        </div>

        {/* SUBMIT REQUESTS */}
        {activeSection === 'requests' && (
          <div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
              <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
                style={{ padding: '6px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}>
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="paid">Paid</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>
              <button onClick={loadRequests} disabled={requestsLoading}
                style={{ padding: '6px 14px', border: '1px solid #ddd', borderRadius: 6, background: '#fff', cursor: 'pointer', fontSize: 13 }}>
                {requestsLoading ? 'Loading...' : '↻ Refresh'}
              </button>
            </div>

            {requestsLoading && requests.length === 0 ? (
              <p style={{ textAlign: 'center', padding: 40, color: '#666' }}>Loading submit requests...</p>
            ) : requestsError && requests.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
                <p style={{ fontSize: 16, color: '#059669' }}>Failed to load requests</p>
                <p style={{ fontSize: 13, marginTop: 8 }}>{requestsError}</p>
                <button onClick={loadRequests} style={{ marginTop: 12, padding: '8px 16px', background: '#059669', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>Retry</button>
              </div>
            ) : requests.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
                <p style={{ fontSize: 16 }}>No submit requests yet</p>
                <p style={{ fontSize: 13 }}>Requests appear here when users complete the WhatsApp Flow</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                      <th style={{ padding: '8px 10px' }}>Phone</th>
                      <th style={{ padding: '8px 10px' }}>Name</th>
                      <th style={{ padding: '8px 10px' }}>Request #</th>
                      <th style={{ padding: '8px 10px' }}>Invoice #</th>
                      <th style={{ padding: '8px 10px' }}>Order ID</th>
                      <th style={{ padding: '8px 10px' }}>Subject</th>
                      <th style={{ padding: '8px 10px' }}>Payment</th>
                      <th style={{ padding: '8px 10px' }}>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map(req => (
                      <tr key={req.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace' }}>{req.phone || '-'}</td>
                        <td style={{ padding: '8px 10px' }}>{req.senderName || '-'}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11 }}>{req.requestNumber || '-'}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11 }}>{req.invoiceNumber || '-'}</td>
                        <td style={{ padding: '8px 10px' }}>{req.orderId || '-'}</td>
                        <td style={{ padding: '8px 10px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{req.subject || '-'}</td>
                        <td style={{ padding: '8px 10px' }}>{getStatusBadge(req.paymentStatus)}</td>
                        <td style={{ padding: '8px 10px', fontSize: 12, color: '#666' }}>{formatDate(req.createdAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* FLOW INTERACTION LOGS */}
        {activeSection === 'logs' && (
          <div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
              <input value={phoneFilter} onChange={e => setPhoneFilter(e.target.value)} placeholder="Filter by phone..."
                style={{ padding: '6px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, width: 200 }} />
              <button onClick={loadLogs} disabled={logsLoading}
                style={{ padding: '6px 14px', border: '1px solid #ddd', borderRadius: 6, background: '#fff', cursor: 'pointer', fontSize: 13 }}>
                {logsLoading ? 'Loading...' : '↻ Refresh'}
              </button>
            </div>

            {logsLoading && logs.length === 0 ? (
              <p style={{ textAlign: 'center', padding: 40, color: '#666' }}>Loading flow logs...</p>
            ) : logsError && logs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
                <p style={{ fontSize: 16, color: '#059669' }}>Failed to load flow logs</p>
                <p style={{ fontSize: 13, marginTop: 8 }}>{logsError}</p>
                <button onClick={loadLogs} style={{ marginTop: 12, padding: '8px 16px', background: '#059669', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>Retry</button>
              </div>
            ) : logs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
                <p style={{ fontSize: 16 }}>No flow interaction logs yet</p>
                <p style={{ fontSize: 13 }}>Logs appear here when users interact with WhatsApp Flows</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                      <th style={{ padding: '8px 10px' }}>Phone</th>
                      <th style={{ padding: '8px 10px' }}>Action</th>
                      <th style={{ padding: '8px 10px' }}>Screen</th>
                      <th style={{ padding: '8px 10px' }}>Data</th>
                      <th style={{ padding: '8px 10px' }}>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map(log => {
                      let parsedData: Record<string, any> | null = null;
                      try { if (log.flowData) parsedData = JSON.parse(log.flowData); } catch {}
                      return (
                        <tr key={log.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                          <td style={{ padding: '8px 10px', fontFamily: 'monospace' }}>{log.phone || '-'}</td>
                          <td style={{ padding: '8px 10px' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, background: log.action === 'INIT' ? '#ecfdf5' : log.action === 'data_exchange' ? '#ecfdf5' : '#f3f4f6' }}>
                              {log.action}
                            </span>
                          </td>
                          <td style={{ padding: '8px 10px' }}>{log.screen || '-'}</td>
                          <td style={{ padding: '8px 10px', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11, fontFamily: 'monospace' }}>
                            {parsedData ? Object.entries(parsedData).map(([k, v]) => `${k}: ${v}`).join(', ') : (log.dataKeys?.join(', ') || '-')}
                          </td>
                          <td style={{ padding: '8px 10px', fontSize: 12, color: '#666' }}>{formatDate(log.createdAt)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );

  if (embedded) return content;

  return (
    <Layout user={user} onSignOut={signOut}>
      {content}
    </Layout>
  );
};

export default FlowResponsesPage;
