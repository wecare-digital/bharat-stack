/**
 * Dashboard - Messages Analytics
 * Message statistics, trends, and channel breakdown
 * Enhanced responsive design
 */

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { BarChart, Sparkline, DateRangePicker } from '../../../components/Charts';
import * as api from '../../../api/client';
import { RefreshIcon } from '../../../lib/icons';

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

export default function DashboardMessagesPage({ signOut, user }: PageProps) {
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
    { label: 'WhatsApp', value: stats.byChannel.whatsapp, color: 'var(--color-whatsapp)' },
    { label: 'SMS', value: stats.byChannel.sms, color: 'var(--color-sms)' },
    { label: 'Email', value: stats.byChannel.email, color: 'var(--color-email)' },
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
      <SEO 
        title="Messages Analytics | WECARE.DIGITAL"
        description="Message statistics, trends, and channel breakdown"
      />
      <div className="page-content">
        <PageHeader 
          title="Messages Analytics" 
          subtitle="Message statistics, trends, and channel breakdown"
          icon="message"
          actions={
            <div className="header-actions">
              <button className="btn-secondary" onClick={loadMessages} disabled={loading} title="Refresh">
                {loading ? '...' : <RefreshIcon size={18} />}
              </button>
              <Link href="/dm/whatsapp" className="btn-primary">
                WhatsApp Inbox
              </Link>
            </div>
          }
        />

        {/* Date Range Picker */}
        <div className="section" style={{ marginBottom: '20px', padding: '16px' }}>
          <DateRangePicker
            startDate={dateRange.start.toISOString().split('T')[0]}
            endDate={dateRange.end.toISOString().split('T')[0]}
            onStartChange={(date) => setDateRange(prev => ({ ...prev, start: new Date(date) }))}
            onEndChange={(date) => setDateRange(prev => ({ ...prev, end: new Date(date) }))}
          />
        </div>

        {/* Summary Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total.toLocaleString()}</div>
            <div className="stat-label">Total Messages</div>
          </div>
          <div className="stat-card accent">
            <div className="stat-value" style={{ color: 'var(--color-whatsapp)' }}>{stats.inbound.toLocaleString()}</div>
            <div className="stat-label">Inbound</div>
          </div>
          <div className="stat-card accent2">
            <div className="stat-value" style={{ color: 'var(--color-sms)' }}>{stats.outbound.toLocaleString()}</div>
            <div className="stat-label">Outbound</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: deliveryRate >= 95 ? 'var(--color-success)' : 'var(--color-warning)' }}>
              {deliveryRate}%
            </div>
            <div className="stat-label">Delivery Rate</div>
          </div>
        </div>

        {/* Charts Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px', marginBottom: '20px' }}>
          <div className="section">
            <h3 className="section-title">Message Trend (7 Days)</h3>
            <Sparkline 
              data={stats.byDay.map(d => d.count)} 
              height={120}
              width={300}
              color="var(--color-whatsapp)"
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px', fontSize: '11px', color: 'var(--color-muted)' }}>
              {stats.byDay.map(d => (
                <span key={d.date}>{new Date(d.date).toLocaleDateString('en', { weekday: 'short' })}</span>
              ))}
            </div>
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
              <div className="empty">No messages yet</div>
            )}
          </div>

          <div className="section">
            <h3 className="section-title">Direction</h3>
            <BarChart data={directionData} height={160} />
          </div>
        </div>

        {/* Delivery Stats */}
        <div className="section">
          <h3 className="section-title">Delivery Performance</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                <span>Delivered</span>
                <span>{stats.delivered} / {stats.outbound}</span>
              </div>
              <div style={{ background: 'var(--color-border)', borderRadius: '6px', height: '10px', overflow: 'hidden' }}>
                <div style={{ 
                  width: `${deliveryRate}%`, 
                  height: '100%', 
                  background: deliveryRate >= 95 ? 'var(--color-success)' : 'var(--color-warning)',
                  borderRadius: '6px',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                <span>Read</span>
                <span>{stats.read} / {stats.delivered}</span>
              </div>
              <div style={{ background: 'var(--color-border)', borderRadius: '6px', height: '10px', overflow: 'hidden' }}>
                <div style={{ 
                  width: `${readRate}%`, 
                  height: '100%', 
                  background: 'var(--color-sms)',
                  borderRadius: '6px',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                <span>Failed</span>
                <span style={{ color: stats.failed > 0 ? 'var(--color-danger)' : 'var(--color-muted)' }}>{stats.failed}</span>
              </div>
              <div style={{ background: 'var(--color-border)', borderRadius: '6px', height: '10px', overflow: 'hidden' }}>
                <div style={{ 
                  width: `${stats.outbound > 0 ? (stats.failed / stats.outbound) * 100 : 0}%`, 
                  height: '100%', 
                  background: 'var(--color-danger)',
                  borderRadius: '6px',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
          </div>
        </div>

        {/* Recent Messages */}
        <div className="section">
          <div className="section-header">
            <h3 className="section-title">Recent Messages</h3>
            <Link href="/dm/whatsapp" className="link">View All →</Link>
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
                    <td style={{ fontSize: '12px', color: 'var(--color-muted)' }}>
                      {new Date(msg.timestamp).toLocaleString()}
                    </td>
                    <td>
                      <span className={`badge ${msg.channel?.toLowerCase()}`}>
                        {msg.channel}
                      </span>
                    </td>
                    <td>
                      <span style={{ color: msg.direction === 'INBOUND' ? 'var(--color-whatsapp)' : 'var(--color-sms)' }}>
                        {msg.direction === 'INBOUND' ? '← In' : '→ Out'}
                      </span>
                    </td>
                    <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {msg.content || `[${msg.messageType || 'media'}]`}
                    </td>
                    <td>
                      <span className={`badge ${msg.status}`}>
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
}
