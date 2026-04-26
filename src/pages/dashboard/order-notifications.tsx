/**
 * Order Notifications Dashboard — WECARE.DIGITAL
 *
 * Admin view showing delivery status of WhatsApp, SMS, and RCS
 * notifications for every order. Data from OrderNotifications collection.
 *
 * Features:
 * - Real-time order notification status (WhatsApp / SMS / RCS)
 * - Filter by status, date, channel
 * - Retry failed notifications
 * - Connect to external store (future: Shopify, WooCommerce)
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

interface PageProps { signOut?: () => void; user?: any; }

const C = {
  bg: '#fff', bgSoft: '#f9fafb', lime: '#d1f470', text: '#374151',
  textDark: '#1a3a2a', textMuted: '#6b7280', border: '#f3f4f6',
  green: '#059669', greenBg: '#f0fdf4', red: '#dc2626', redBg: '#fef2f2',
  amber: '#d97706', amberBg: '#fffbeb', blue: '#2563eb', blueBg: '#eff6ff',
  radius: 13,
};

interface OrderNotif {
  orderId: string;
  wdOrderId: string;
  phone: string;
  email: string;
  whatsappStatus: string;
  whatsappMessageId: string;
  whatsappError: string;
  smsStatus: string;
  smsMessageId: string;
  smsError: string;
  rcsStatus: string;
  createdAt: string;
  updatedAt: string;
}

const statusPill = (status: string) => {
  const colors: Record<string, { bg: string; color: string }> = {
    sent: { bg: C.greenBg, color: C.green },
    delivered: { bg: C.greenBg, color: C.green },
    pending: { bg: C.amberBg, color: C.amber },
    failed: { bg: C.redBg, color: C.red },
    not_available: { bg: C.bgSoft, color: C.textMuted },
  };
  const c = colors[status] || colors.not_available;
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 10,
      fontSize: 11, fontWeight: 600, background: c.bg, color: c.color,
    }}>
      {status.replace(/_/g, ' ').toUpperCase()}
    </span>
  );
};

export default function OrderNotificationsPage({ signOut, user }: PageProps) {
  const [notifications, setNotifications] = useState<OrderNotif[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState('');

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/store/order-notifications' + (filter !== 'all' ? '?status=' + filter : ''));
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setNotifications(data.notifications || []);
      setError('');
    } catch (e: any) {
      setError(e.message);
      // Demo data for development
      setNotifications([
        {
          orderId: 'demo-001', wdOrderId: 'WD-ORD - A3F7B2C1 - 25-04-2026 - 17:43:01 - IST',
          phone: '+919330994400', email: 'one@wecare.digital',
          whatsappStatus: 'sent', whatsappMessageId: 'wamid.xxx', whatsappError: '',
          smsStatus: 'sent', smsMessageId: 'airtel-xxx', smsError: '',
          rcsStatus: 'not_available', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
        },
      ]);
    }
    setLoading(false);
  }, [filter]);

  useEffect(() => { fetchNotifications(); }, [fetchNotifications]);

  const retryNotification = async (orderId: string, channel: string) => {
    try {
      await fetch('/api/store/order-notifications/retry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orderId, channel }),
      });
      fetchNotifications();
    } catch {}
  };

  const stats = {
    total: notifications.length,
    waSent: notifications.filter(n => n.whatsappStatus === 'sent' || n.whatsappStatus === 'delivered').length,
    waFailed: notifications.filter(n => n.whatsappStatus === 'failed').length,
    smsSent: notifications.filter(n => n.smsStatus === 'sent' || n.smsStatus === 'delivered').length,
    smsFailed: notifications.filter(n => n.smsStatus === 'failed').length,
  };

  return (
    <Layout signOut={signOut} user={user}>
      <SEO title="Order Notifications" />
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: C.textDark, margin: 0 }}>Order Notifications</h1>
            <p style={{ fontSize: 13, color: C.textMuted, margin: '4px 0 0' }}>
              WhatsApp (WABA1 +919330994400) · SMS (Airtel WDBEEP) · RCS (coming soon)
            </p>
          </div>
          <button onClick={fetchNotifications} style={{
            padding: '8px 16px', background: C.lime, border: 'none', borderRadius: 10,
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>
            Refresh
          </button>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Total Orders', value: stats.total, bg: C.bgSoft },
            { label: 'WhatsApp Sent', value: stats.waSent, bg: C.greenBg },
            { label: 'WhatsApp Failed', value: stats.waFailed, bg: C.redBg },
            { label: 'SMS Sent', value: stats.smsSent, bg: C.greenBg },
            { label: 'SMS Failed', value: stats.smsFailed, bg: C.redBg },
          ].map((s, i) => (
            <div key={i} style={{ padding: 14, background: s.bg, borderRadius: C.radius, border: '2px solid ' + C.border }}>
              <div style={{ fontSize: 10, color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: C.textDark }}>{s.value}</div>
            </div>
          ))}
        </div>

        {/* Filter */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {['all', 'sent', 'failed', 'pending'].map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{
              padding: '6px 14px', borderRadius: 10, border: '2px solid ' + (filter === f ? C.lime : C.border),
              background: filter === f ? C.lime : C.bg, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>
              {f.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Table */}
        <div style={{ border: '2px solid ' + C.border, borderRadius: C.radius, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: C.bgSoft }}>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Order</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Phone</th>
                <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600 }}>WhatsApp</th>
                <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600 }}>SMS</th>
                <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600 }}>RCS</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Date</th>
                <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ padding: 20, textAlign: 'center', color: C.textMuted }}>Loading...</td></tr>
              ) : notifications.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: 20, textAlign: 'center', color: C.textMuted }}>No notifications found</td></tr>
              ) : notifications.map((n, i) => (
                <tr key={n.orderId} style={{ borderTop: '1px solid ' + C.border, background: i % 2 === 0 ? C.bg : C.bgSoft }}>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ fontFamily: 'monospace', fontSize: 11, fontWeight: 600 }}>{n.wdOrderId || n.orderId.substring(0, 12)}</div>
                  </td>
                  <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 12 }}>{n.phone}</td>
                  <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                    {statusPill(n.whatsappStatus)}
                    {n.whatsappError && <div style={{ fontSize: 10, color: C.red, marginTop: 2 }}>{n.whatsappError.substring(0, 40)}</div>}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                    {statusPill(n.smsStatus)}
                    {n.smsError && <div style={{ fontSize: 10, color: C.red, marginTop: 2 }}>{n.smsError.substring(0, 40)}</div>}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'center' }}>{statusPill(n.rcsStatus)}</td>
                  <td style={{ padding: '10px 12px', fontSize: 11, color: C.textMuted }}>
                    {new Date(n.createdAt).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                    {(n.whatsappStatus === 'failed' || n.smsStatus === 'failed') && (
                      <button onClick={() => retryNotification(n.orderId, n.whatsappStatus === 'failed' ? 'whatsapp' : 'sms')} style={{
                        padding: '4px 10px', background: C.amberBg, border: '1px solid ' + C.amber,
                        borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer', color: C.amber,
                      }}>
                        Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {error && <p style={{ fontSize: 12, color: C.amber, marginTop: 8 }}>API: {error} (showing demo data)</p>}

        {/* Config Info */}
        <div style={{ marginTop: 24, padding: 16, background: C.bgSoft, borderRadius: C.radius, border: '2px solid ' + C.border }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 8px' }}>Configuration</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, fontSize: 12 }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>WhatsApp</div>
              <div>WABA1: +91 9330994400</div>
              <div>Template: wd_order</div>
              <div>Phone ID: 1016149501586345</div>
            </div>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>SMS (Airtel IQ)</div>
              <div>Header: WDBEEP</div>
              <div>DLT: 1007723091207562020</div>
              <div>Entity: 1201161991108627443</div>
              <div>Type: SERVICE_IMPLICIT</div>
            </div>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>RCS (Coming Soon)</div>
              <div>Provider: Airtel RCS</div>
              <div>Status: Not yet available</div>
              <div>Will use same DLT entity</div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
