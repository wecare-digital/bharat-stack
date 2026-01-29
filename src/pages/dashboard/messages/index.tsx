/**
 * Dashboard - Messages Analytics
 * Message statistics, trends, and channel breakdown
 */
import React, { useState, useEffect, useMemo } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import { BarChart, DonutChart, Sparkline, DateRangePicker } from '../../../components/Charts';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }

interface MessageStats {
  total: number;
  inbound: number;
  outbound: number;
  delivered: number;
  read: number;
  failed: number;
  byChannel: { whatsapp: number; sms: number; email: number };
  byDay: { date: string; count: number }[];
}

const DashboardMessagesPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [messages, setMessages] = useState<api.Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState<{ start: Date; end: Date }>({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    end: new Date(),
  });

  useEffect(() => {
    loadMessages();
  }, []);

  const loadMessages = async () => {
    setLoading(true);
    try {
      const data = await api.listMessages();
      setMessages(data);
    } catch (err) {
      console.error('Failed to load messages:', err);
    } finally {
      setLoading(false);
    }
  };

  // Calculate stats from messages
  const stats: MessageStats = useMemo(() => {
    const filtered = messages.filter(m => {
      const ts = new Date(m.timestamp);
      return ts >= dateRange.start && ts <= dateRange.end;
    });

    const byDay: Record<string, number> = {};
    const last7Days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - (6 - i));
      return d.toISOString().slice(0, 10);
    });
    last7Days.forEach(d => byDay[d] = 0);

    filtered.forEach(m => {
      const day = m.timestamp.slice(0, 10);
      if (byDay[day] !== undefined) byDay[day]++;
    });

    return {
      total: filtered.length,
      inbound: filtered.filter(m => m.direction === 'INBOUND').length,
      outbound: filtered.filter(m => m.direction === 'OUTBOUND').length,
      delivered: filtered.filter(m => m.status === 'delivered' || m.status === 'sent').length,
      read: filtered.filter(m => m.status === 'read').length,
      failed: filtered.filter(m => m.status === 'failed').length,
      byChannel: {
        whatsapp: filtered.filter(m => m.channel === 'WHATSAPP').length,
        sms: filtered.filter(m => m.channel === 'SMS').length,
        email: filtered.filter(m => m.channel === 'EMAIL').length,
      },
      byDay: Object.entries(byDay).map(([date, count]) => ({ date, count })),
    };
  }, [messages, dateRange]);

  const channelData = [
    { label: 'WhatsApp', value: stats.byChannel.whatsapp, color: '#25D366' },
    { label: 'SMS', value: stats.byChannel.sms, color: '#2196F3' },
    { label: 'Email', value: stats.byChannel.email, color: '#9C27B0' },
  ].filter(d => d.value > 0);

  const directionData = [
    { label: 'Inbound', value: stats.inbound },
    { label: 'Outbound', value: stats.outbound },
  ];

  const deliveryRate = stats.outbound > 0 
    ? Math.round((stats.delivered / stats.outbound) * 100) 
    : 100;

  const readRate = stats.delivered > 0 
    ? Math.round((stats.read / stats.delivered) * 100) 
    : 0;

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="page">
        <PageHeader 
          title="Messages Analytics" 
          subtitle="Message statistics, trends, and channel breakdown"
          icon="message"
          actions={
            <div className="header-actions">
              <button className="btn-secondary" onClick={loadMessages} disabled={loading}>
                ↻ {loading ? 'Loading...' : 'Refresh'}
              </button>
              <a href="/dm/whatsapp" className="btn-primary">→ WhatsApp Inbox</a>
            </div>
          }
        />

        {/* Date Range Picker */}
        <div className="section" style={{ marginBottom: 20 }}>
          <DateRangePicker
            startDate={dateRange.start}
            endDate={dateRange.end}
            onChange={(start, end) => setDateRange({ start, end })}
          />
        </div>

        {/* Summary Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total.toLocaleString()}</div>
            <div className="stat-label">Total Messages</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#25D366' }}>{stats.inbound.toLocaleString()}</div>
            <div className="stat-label">Inbound</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#2196F3' }}>{stats.outbound.toLocaleString()}</div>
            <div className="stat-label">Outbound</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: deliveryRate >= 95 ? '#4CAF50' : '#FF9800' }}>
              {deliveryRate}%
            </div>
            <div className="stat-label">Delivery Rate</div>
          </div>
        </div>

        {/* Charts Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: 20, marginTop: 20 }}>
          {/* Message Trend */}
          <div className="section" style={{ padding: 20 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>Message Trend (7 Days)</h3>
            <Sparkline 
              data={stats.byDay.map(d => d.count)} 
              height={120} 
              color="#25D366"
              showArea={true}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: '#666' }}>
              {stats.byDay.map(d => (
                <span key={d.date}>{new Date(d.date).toLocaleDateString('en', { weekday: 'short' })}</span>
              ))}
            </div>
          </div>

          {/* Channel Distribution */}
          <div className="section" style={{ padding: 20 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>By Channel</h3>
            {channelData.length > 0 ? (
              <DonutChart data={channelData} size={160} />
            ) : (
              <div style={{ textAlign: 'center', color: '#666', padding: 40 }}>No messages yet</div>
            )}
          </div>

          {/* Direction Breakdown */}
          <div className="section" style={{ padding: 20 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>Direction</h3>
            <BarChart data={directionData} height={160} />
          </div>
        </div>

        {/* Delivery Stats */}
        <div className="section" style={{ marginTop: 20, padding: 20 }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 500 }}>Delivery Performance</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 20 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
                <span>Delivered</span>
                <span>{stats.delivered} / {stats.outbound}</span>
              </div>
              <div style={{ background: '#e5e7eb', borderRadius: 4, height: 8, overflow: 'hidden' }}>
                <div style={{ 
                  width: `${deliveryRate}%`, 
                  height: '100%', 
                  background: deliveryRate >= 95 ? '#4CAF50' : '#FF9800',
                  borderRadius: 4,
                }} />
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
                <span>Read</span>
                <span>{stats.read} / {stats.delivered}</span>
              </div>
              <div style={{ background: '#e5e7eb', borderRadius: 4, height: 8, overflow: 'hidden' }}>
                <div style={{ 
                  width: `${readRate}%`, 
                  height: '100%', 
                  background: '#2196F3',
                  borderRadius: 4,
                }} />
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
                <span>Failed</span>
                <span style={{ color: stats.failed > 0 ? '#F44336' : '#666' }}>{stats.failed}</span>
              </div>
              <div style={{ background: '#e5e7eb', borderRadius: 4, height: 8, overflow: 'hidden' }}>
                <div style={{ 
                  width: `${stats.outbound > 0 ? (stats.failed / stats.outbound) * 100 : 0}%`, 
                  height: '100%', 
                  background: '#F44336',
                  borderRadius: 4,
                }} />
              </div>
            </div>
          </div>
        </div>

        {/* Recent Messages Preview */}
        <div className="section" style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>Recent Messages</h3>
            <a href="/dm/whatsapp" style={{ fontSize: 12, color: '#25D366' }}>View All →</a>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Channel</th>
                  <th>Direction</th>
                  <th>Content</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {messages.slice(0, 10).map(msg => (
                  <tr key={msg.messageId}>
                    <td style={{ fontSize: 12, color: '#666' }}>
                      {new Date(msg.timestamp).toLocaleString()}
                    </td>
                    <td>
                      <span style={{
                        padding: '2px 6px',
                        borderRadius: 4,
                        fontSize: 10,
                        background: msg.channel === 'WHATSAPP' ? '#25D36620' : msg.channel === 'SMS' ? '#2196F320' : '#9C27B020',
                        color: msg.channel === 'WHATSAPP' ? '#25D366' : msg.channel === 'SMS' ? '#2196F3' : '#9C27B0',
                      }}>
                        {msg.channel}
                      </span>
                    </td>
                    <td>
                      <span style={{ color: msg.direction === 'INBOUND' ? '#25D366' : '#2196F3' }}>
                        {msg.direction === 'INBOUND' ? '← In' : '→ Out'}
                      </span>
                    </td>
                    <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {msg.content || `[${msg.messageType || 'media'}]`}
                    </td>
                    <td>
                      <span style={{
                        padding: '2px 6px',
                        borderRadius: 4,
                        fontSize: 10,
                        background: msg.status === 'read' ? '#4CAF5020' : msg.status === 'delivered' ? '#2196F320' : msg.status === 'failed' ? '#F4433620' : '#66666620',
                        color: msg.status === 'read' ? '#4CAF50' : msg.status === 'delivered' ? '#2196F3' : msg.status === 'failed' ? '#F44336' : '#666',
                      }}>
                        {msg.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {messages.length === 0 && (
                  <tr><td colSpan={5} className="empty-table">{loading ? 'Loading...' : 'No messages yet'}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default DashboardMessagesPage;
