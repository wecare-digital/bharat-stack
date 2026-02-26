/**
 * Pay Tab — Payment records and management
 */
import React, { useState } from 'react';
import Link from 'next/link';
import Button from '../../../components/ui/Button';
import * as api from '../../../api/client';
import { PAYMENT_CONFIG } from '../../../config/constants';
import type { DashboardData } from '../../../types/dashboard';

interface PayTabProps {
  data: DashboardData;
  onRefresh: () => void;
}

const PAYMENT_PHONE = PAYMENT_CONFIG.phoneDisplay;
const PAYMENT_NAME = PAYMENT_CONFIG.phoneName;

const PayTab: React.FC<PayTabProps> = ({ data, onRefresh }) => {
  const { messages } = data;
  const [editPayment, setEditPayment] = useState<any>(null);
  const [editSaving, setEditSaving] = useState(false);

  const paymentMessages = messages.filter(
    m => m.messageType === 'payment' || m.messageType === 'payment_request',
  );
  const capturedPayments = paymentMessages.filter(m => (m as any).paymentStatus === 'captured').length;
  const failedPayments = paymentMessages.filter(m => (m as any).paymentStatus === 'failed').length;
  const pendingPayments = paymentMessages.filter(m => m.status === 'pending').length;

  const handleSavePayment = async () => {
    if (!editPayment) return;
    setEditSaving(true);
    try {
      const ok = await api.updateMessage(editPayment.id, {
        paymentItemName: editPayment.paymentItemName,
        paymentQuantity: Number(editPayment.paymentQuantity) || 1,
        paymentGstRate: Number(editPayment.paymentGstRate) || 18,
        paymentPurpose: editPayment.paymentPurpose,
        paymentDueRef: editPayment.paymentDueRef,
        paymentDiscount: Number(editPayment.paymentDiscount) || 0,
        paymentShipping: Number(editPayment.paymentShipping) || 0,
        status: editPayment.status,
      });
      if (ok) {
        setEditPayment(null);
        onRefresh();
      }
    } catch (err) {
      console.error('Save payment error:', err);
    } finally {
      setEditSaving(false);
    }
  };

  const downloadInvoicePdf = (invoiceUrl: string, refId: string) => {
    const link = document.createElement('a');
    link.href = invoiceUrl;
    link.download = `invoice-${refId}.png`;
    link.target = '_blank';
    link.click();
  };

  return (
    <div className="pay-tab">
      <div className="section-header">
        <h3>Payment Records</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link href="/contacts">
            <button className="btn-outline-success">+ Customer</button>
          </Link>
          <Link href="/pay"><Button variant="primary">+ New Payment</Button></Link>
        </div>
      </div>

      <div className="stats-grid small">
        <div className="stat-card success">
          <div className="stat-value">{capturedPayments}</div>
          <div className="stat-label">Captured</div>
        </div>
        <div className="stat-card error">
          <div className="stat-value">{failedPayments}</div>
          <div className="stat-label">Failed</div>
        </div>
        <div className="stat-card warning">
          <div className="stat-value">{pendingPayments}</div>
          <div className="stat-label">Pending</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{paymentMessages.length}</div>
          <div className="stat-label">Total</div>
        </div>
      </div>

      <div className="payment-info">
        <span>Payments sent from: <strong>{PAYMENT_PHONE}</strong> ({PAYMENT_NAME})</span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Phone</th>
              <th>Item</th>
              <th>Qty</th>
              <th>Subtotal</th>
              <th>GST</th>
              <th>Promo</th>
              <th>Ship</th>
              <th>Total</th>
              <th>Source</th>
              <th>Status</th>
              <th>Invoice</th>
              <th>Time</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {paymentMessages.map(p => {
              const pa = p as any;
              const subtotal = pa.paymentSubtotal ? (pa.paymentSubtotal / 100).toFixed(2) : '-';
              const gstAmt = pa.paymentGstAmount ? `₹${(pa.paymentGstAmount / 100).toFixed(2)} (${pa.paymentGstRate || 18}%)` : '-';
              const disc = pa.paymentDiscount ? `₹${(pa.paymentDiscount / 100).toFixed(2)}` : '₹0';
              const ship = pa.paymentShipping ? `₹${(pa.paymentShipping / 100).toFixed(2)}` : '-';
              const total = pa.paymentTotal ? `₹${(pa.paymentTotal / 100).toFixed(2)}` : p.content;
              const source = pa.paymentSource || (pa.messageType === 'payment' ? 'webhook' : 'dashboard');
              const invoiceUrl = pa.invoiceS3Key
                ? `https://app.wecare.digital/${pa.invoiceS3Key}`
                : pa.paymentReferenceId ? `https://app.wecare.digital/invoices/${pa.paymentReferenceId}.png` : '';
              return (
                <tr key={p.id} className={pa.paymentStatus || p.status}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{pa.paymentReferenceId || '-'}</td>
                  <td>{p.senderPhone || '-'}</td>
                  <td>{pa.paymentItemName || '-'}</td>
                  <td>{pa.paymentQuantity || 1}</td>
                  <td>₹{subtotal}</td>
                  <td>{gstAmt}</td>
                  <td>{disc}</td>
                  <td>{ship}</td>
                  <td style={{ fontWeight: 600 }}>{total}</td>
                  <td>
                    <span className={`badge ${source === 'whatsapp_bot' ? 'info' : ''}`}>
                      {source === 'whatsapp_bot' ? 'WA Bot' : source}
                    </span>
                  </td>
                  <td><span className={`badge ${pa.paymentStatus || p.status}`}>{pa.paymentStatus || p.status}</span></td>
                  <td>
                    {invoiceUrl ? (
                      <span style={{ display: 'flex', gap: 4 }}>
                        <a href={invoiceUrl} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.7rem', color: '#10B981', textDecoration: 'none' }}>📄</a>
                        <button onClick={() => downloadInvoicePdf(invoiceUrl, pa.paymentReferenceId || p.id)} className="btn-download" title="Download">⬇</button>
                      </span>
                    ) : '-'}
                  </td>
                  <td style={{ fontSize: '0.75rem' }}>{new Date(p.timestamp).toLocaleString()}</td>
                  <td>
                    <button onClick={() => setEditPayment({ ...pa, id: p.id })} className="btn-edit">✏️ Edit</button>
                  </td>
                </tr>
              );
            })}
            {paymentMessages.length === 0 && (
              <tr><td colSpan={14} className="empty">No payment records</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Edit Payment Modal */}
      {editPayment && (
        <div className="modal-overlay" onClick={() => setEditPayment(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 16px', fontSize: '1rem' }}>
              Edit Payment — {editPayment.paymentReferenceId || editPayment.id}
            </h3>
            {[
              { label: 'Item Name', key: 'paymentItemName', type: 'text' },
              { label: 'Quantity', key: 'paymentQuantity', type: 'number' },
              { label: 'GST Rate (%)', key: 'paymentGstRate', type: 'number' },
              { label: 'Purpose', key: 'paymentPurpose', type: 'text' },
              { label: 'Due Reference', key: 'paymentDueRef', type: 'text' },
              { label: 'Discount (paise)', key: 'paymentDiscount', type: 'number' },
              { label: 'Shipping (paise)', key: 'paymentShipping', type: 'number' },
            ].map(f => (
              <div key={f.key} style={{ marginBottom: 10 }}>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#6b7280', marginBottom: 2 }}>{f.label}</label>
                <input
                  type={f.type}
                  value={editPayment[f.key] ?? ''}
                  onChange={e => setEditPayment((prev: any) => ({ ...prev, [f.key]: e.target.value }))}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem' }}
                />
              </div>
            ))}
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'block', fontSize: '0.75rem', color: '#6b7280', marginBottom: 2 }}>Status</label>
              <select
                value={editPayment.status || editPayment.paymentStatus || 'pending'}
                onChange={e => setEditPayment((prev: any) => ({ ...prev, status: e.target.value }))}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem' }}
              >
                <option value="pending">Pending</option>
                <option value="captured">Captured</option>
                <option value="failed">Failed</option>
                <option value="refunded">Refunded</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
              <button onClick={() => setEditPayment(null)} className="btn-cancel">Cancel</button>
              <button onClick={handleSavePayment} disabled={editSaving} className="btn-save">
                {editSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PayTab;
