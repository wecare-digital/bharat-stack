/**
 * Pay Flow CRM — Full Management Page
 *
 * Tabs:
 *  1. Customers — CRUD customer records (auto-fill in WhatsApp pay flow)
 *  2. Invoices  — Create & view invoices sent via WhatsApp
 *  3. Pending Dues — View outstanding payment requests
 *  4. Flow Config — Manage pay flow settings (purpose list, GST, shipping, promo, GSTIN)
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import Button from '../../../components/ui/Button';
import * as api from '../../../api/client';
import { API_BASE } from '../../../config/constants';
import type { Invoice, InvoiceDeliveryLog } from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

// ── Shared types ──
interface CustomerRecord {
  id: string; contactId: string; name: string; phone: string; email: string;
  shippingAddress: string; billingAddress: string; createdAt: string; updatedAt: string;
}
// InvoiceRecord now uses the Invoice type from api/client
interface DueRecord {
  id: string; ref: string; customerName: string; customerPhone: string;
  itemName: string; amount: number; status: string; createdAt: string;
}
interface FlowConfig {
  default_gst_rate: number; default_shipping: number; default_promo: number;
  gstin: string; default_item_name: string; purposes: string[];
}

const emptyForm = { name: '', phone: '', email: '', shippingAddress: '', billingAddress: '' };
const emptyInvoiceForm = { items: [{ name: '', unitPrice: '', quantity: '1', gstRate: '18' }], shipping: '49', discount: '15', purpose: '', orderId: '' };
const defaultFlowConfig: FlowConfig = {
  default_gst_rate: 18, default_shipping: 49, default_promo: 15,
  gstin: '19AADFW7431N1ZK', default_item_name: 'Services/Goods',
  purposes: ['BNB Club — Travel','No Fault — ODR','Expo Week — Events','Ritual Guru — Puja','Legal Champ — Docs','Swdhya — Samvad','Gift Card','Advance Payment','Service Fee','Subscription','Consultation'],
};

const TABS: TabItem[] = [
  { id: 'customers', label: 'Customers' },
  { id: 'invoices', label: 'Invoices' },
  { id: 'dues', label: 'Pending Dues' },
  { id: 'config', label: 'Flow Config' },
];

const PayFlowPage: React.FC<PageProps> = ({ signOut, user, embedded }) => {
  const [tab, setTab] = useState('customers');
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // ── Customers state ──
  const [customers, setCustomers] = useState<CustomerRecord[]>([]);
  const [custLoading, setCustLoading] = useState(true);
  const [custSearch, setCustSearch] = useState('');
  const [showCustForm, setShowCustForm] = useState(false);
  const [editCustId, setEditCustId] = useState<string | null>(null);
  const [custForm, setCustForm] = useState(emptyForm);
  const [custSaving, setCustSaving] = useState(false);

  // ── Invoice modal state ──
  const [invoiceCustomer, setInvoiceCustomer] = useState<CustomerRecord | null>(null);
  const [invoiceForm, setInvoiceForm] = useState(emptyInvoiceForm);
  const [invoiceSaving, setInvoiceSaving] = useState(false);

  // ── Invoices list state (from InvoicesTable via invoice engine) ──
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [invLoading, setInvLoading] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [invDetailLoading, setInvDetailLoading] = useState(false);
  const [invDeliveryLogs, setInvDeliveryLogs] = useState<InvoiceDeliveryLog[]>([]);
  const [invActionLoading, setInvActionLoading] = useState<string | null>(null); // 'image' | 'pdf' | 'send' | null

  // ── Dues state ──
  const [dues, setDues] = useState<DueRecord[]>([]);
  const [duesLoading, setDuesLoading] = useState(false);

  // ── Flow config state ──
  const [flowConfig, setFlowConfig] = useState<FlowConfig>(defaultFlowConfig);
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);


  // ── Load customers ──
  const loadCustomers = useCallback(async () => {
    setCustLoading(true);
    try {
      const res = await fetch(`${API_BASE}/contacts`);
      if (!res.ok) throw new Error('Failed to load');
      const json = await res.json();
      const raw: any[] = json.contacts || (Array.isArray(json) ? json : []);
      setCustomers(raw.filter((c: any) => !c.deletedAt).map((c: any) => ({
        id: c.id || c.contactId || '',
        contactId: c.contactId || c.id || '',
        name: c.name || '',
        phone: c.phone || '',
        email: c.email || '',
        shippingAddress: c.shippingAddress || '',
        billingAddress: c.billingAddress || '',
        createdAt: c.createdAt ? new Date(Number(c.createdAt) * 1000).toLocaleDateString() : '',
        updatedAt: c.updatedAt ? new Date(Number(c.updatedAt) * 1000).toLocaleDateString() : '',
      })));
    } catch (err) { console.error('Load customers error:', err); }
    finally { setCustLoading(false); }
  }, []);

  // ── Load invoices from InvoicesTable ──
  const loadInvoices = useCallback(async () => {
    setInvLoading(true);
    try {
      const result = await api.listInvoicesEngine({ limit: 100 });
      setInvoices(result.invoices || []);
    } catch (err) { console.error('Load invoices error:', err); }
    finally { setInvLoading(false); }
  }, []);

  // ── Load single invoice detail ──
  const loadInvoiceDetail = useCallback(async (invoiceId: string) => {
    setInvDetailLoading(true);
    try {
      const inv = await api.getInvoiceEngine(invoiceId);
      if (inv) setSelectedInvoice(inv);
      const logs = await api.getInvoiceDeliveryLog(invoiceId);
      setInvDeliveryLogs(logs.deliveryLogs || []);
    } catch (err) { console.error('Load invoice detail error:', err); }
    finally { setInvDetailLoading(false); }
  }, []);

  // ── Load pending dues ──
  const loadDues = useCallback(async () => {
    setDuesLoading(true);
    try {
      const res = await fetch(`${API_BASE}/messages?messageType=payment_request&status=pending&limit=50`);
      if (!res.ok) throw new Error('Failed');
      const json = await res.json();
      const raw: any[] = json.messages || (Array.isArray(json) ? json : []);
      setDues(raw.map((m: any) => ({
        id: m.messageId || m.id || '',
        ref: m.paymentReferenceId || m.messageId || '',
        customerName: m.paymentCustomerName || m.customerName || '',
        customerPhone: m.senderPhone || '',
        itemName: m.paymentItemName || 'Services/Goods',
        amount: parseFloat(m.paymentTotal || m.paymentAmount || 0),
        status: m.status || 'pending',
        createdAt: m.createdAt ? new Date(Number(m.createdAt) * 1000).toLocaleDateString() : '',
      })));
    } catch (err) { console.error('Load dues error:', err); }
    finally { setDuesLoading(false); }
  }, []);

  // ── Load flow config ──
  const loadFlowConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const data = await api.getSystemConfig('pay_flow_config');
      if (data) setFlowConfig({ ...defaultFlowConfig, ...data });
    } catch (err) { console.error('Load flow config error:', err); }
    finally { setConfigLoading(false); }
  }, []);

  // ── Initial load ──
  useEffect(() => { loadCustomers(); }, [loadCustomers]);
  useEffect(() => { if (tab === 'invoices') loadInvoices(); }, [tab, loadInvoices]);
  useEffect(() => { if (tab === 'dues') loadDues(); }, [tab, loadDues]);
  useEffect(() => { if (tab === 'config') loadFlowConfig(); }, [tab, loadFlowConfig]);


  // ── Customer CRUD ──
  const handleCustSave = async () => {
    if (!custForm.name || !custForm.phone) { setMsg({ type: 'error', text: 'Name and phone required' }); return; }
    setCustSaving(true); setMsg(null);
    try {
      const cleanPhone = custForm.phone.replace(/[\s\-]/g, '');
      if (editCustId) {
        const ok = await api.updateContact(editCustId, { name: custForm.name, phone: cleanPhone, email: custForm.email || undefined, shippingAddress: custForm.shippingAddress || undefined, billingAddress: custForm.billingAddress || undefined } as any);
        setMsg(ok ? { type: 'success', text: 'Customer updated' } : { type: 'error', text: 'Update failed' });
      } else {
        const contact = await api.createContact({ name: custForm.name, phone: cleanPhone, email: custForm.email || undefined } as any);
        if (contact) {
          const extras: any = {};
          if (custForm.shippingAddress) extras.shippingAddress = custForm.shippingAddress;
          if (custForm.billingAddress) extras.billingAddress = custForm.billingAddress;
          if (Object.keys(extras).length) await api.updateContact(contact.id, extras as any);
          setMsg({ type: 'success', text: 'Customer created' });
        } else { setMsg({ type: 'error', text: 'Create failed' }); }
      }
      setShowCustForm(false); setEditCustId(null); setCustForm(emptyForm);
      await loadCustomers();
    } catch (err: any) { setMsg({ type: 'error', text: err.message || 'Error' }); }
    finally { setCustSaving(false); }
  };

  const handleCustEdit = (c: CustomerRecord) => {
    setEditCustId(c.id);
    setCustForm({ name: c.name, phone: c.phone, email: c.email, shippingAddress: c.shippingAddress, billingAddress: c.billingAddress });
    setShowCustForm(true); setMsg(null);
  };

  const handleCustNew = () => { setEditCustId(null); setCustForm(emptyForm); setShowCustForm(true); setMsg(null); };

  // ── Invoice create (uses new Invoice Engine) ──
  const handleCreateInvoice = async () => {
    if (!invoiceCustomer) return;
    if (!invoiceForm.itemName || !invoiceForm.unitPrice || parseFloat(invoiceForm.unitPrice) <= 0) {
      setMsg({ type: 'error', text: 'Item name and price > 0 required' }); return;
    }
    // Mandatory field enforcement for invoice readiness
    const missingFields: string[] = [];
    if (!invoiceCustomer.email) missingFields.push('email');
    if (!invoiceCustomer.shippingAddress) missingFields.push('shipping address');
    if (!invoiceCustomer.billingAddress) missingFields.push('billing address');
    if (missingFields.length > 0) {
      setMsg({ type: 'error', text: `Customer missing: ${missingFields.join(', ')}. Edit customer first.` }); return;
    }
    setInvoiceSaving(true); setMsg(null);
    try {
      const up = parseFloat(invoiceForm.unitPrice) || 0;
      const q = parseInt(invoiceForm.quantity) || 1;
      const result = await api.createInvoiceEngine({
        contactId: invoiceCustomer.contactId,
        customerName: invoiceCustomer.name,
        customerPhone: invoiceCustomer.phone,
        customerEmail: invoiceCustomer.email,
        shippingAddress: invoiceCustomer.shippingAddress,
        billingAddress: invoiceCustomer.billingAddress,
        items: [{ name: invoiceForm.itemName, amount: up, quantity: q }],
        gstRate: parseFloat(invoiceForm.gstRate) || 18,
        shipping: parseFloat(invoiceForm.shipping) || 49,
        discount: parseFloat(invoiceForm.discount) || 15,
        purpose: invoiceForm.purpose,
        orderId: invoiceForm.orderId || 'Offline',
        entryPoint: 'pay_flow',
      });
      if (result?.invoiceId) {
        setMsg({ type: 'success', text: `Invoice ${result.invoiceNumber} created (Rs. ${result.total.toLocaleString()})` });
        setInvoiceCustomer(null);
        if (tab === 'invoices') loadInvoices();
      } else { setMsg({ type: 'error', text: 'Failed to create invoice' }); }
    } catch (err: any) { setMsg({ type: 'error', text: err.message || 'Error' }); }
    finally { setInvoiceSaving(false); }
  };

  // ── Save flow config ──
  const handleSaveConfig = async () => {
    setConfigSaving(true); setMsg(null);
    try {
      const ok = await api.updateSystemConfig('pay_flow_config', flowConfig as any);
      setMsg(ok ? { type: 'success', text: 'Flow config saved' } : { type: 'error', text: 'Save failed' });
    } catch (err: any) { setMsg({ type: 'error', text: err.message || 'Error' }); }
    finally { setConfigSaving(false); }
  };

  // ── Filtered customers ──
  const filteredCust = custSearch.trim()
    ? customers.filter(c => c.name.toLowerCase().includes(custSearch.toLowerCase()) || c.phone.includes(custSearch) || c.email.toLowerCase().includes(custSearch.toLowerCase()))
    : customers;
  const withAddr = customers.filter(c => c.shippingAddress).length;

  // ── Tab counts ──
  const tabsWithCounts: TabItem[] = TABS.map(t => {
    if (t.id === 'customers') return { ...t, count: customers.length };
    if (t.id === 'dues') return { ...t, count: dues.length };
    return t;
  });


  const content = (
    <>
      <div className="crm-page">
        <PageHeader title="Pay Flow CRM" subtitle="Customers, invoices, dues & flow config" icon="payment" backLink="/pay" backLabel="← Pay"
          actions={tab === 'customers' ? <Button variant="primary" onClick={handleCustNew}>+ New Customer</Button> : undefined} />

        {msg && <div className={`crm-msg ${msg.type}`}>{msg.text}<button onClick={() => setMsg(null)}>×</button></div>}

        <Tabs items={tabsWithCounts} activeTab={tab} onChange={setTab} />

        {/* ═══ CUSTOMERS TAB ═══ */}
        {tab === 'customers' && (
          <div className="crm-tab-content">
            <div className="crm-stats">
              <div className="crm-stat"><div className="crm-stat-val">{customers.length}</div><div className="crm-stat-lbl">Total</div></div>
              <div className="crm-stat"><div className="crm-stat-val">{withAddr}</div><div className="crm-stat-lbl">With Address</div></div>
              <div className="crm-stat"><div className="crm-stat-val">{customers.length - withAddr}</div><div className="crm-stat-lbl">Missing Address</div></div>
            </div>
            <div className="crm-info"><span>Tip</span><div><b>How it works:</b> Customer details auto-fill in WhatsApp pay flow. No re-entry needed.</div></div>
            <div className="crm-search">
              <input type="text" placeholder="Search name, phone, email..." value={custSearch} onChange={e => setCustSearch(e.target.value)} />
              {custSearch && <button className="crm-search-x" onClick={() => setCustSearch('')}>×</button>}
            </div>
            {custLoading ? <div className="crm-loading">Loading...</div> : (
              <div className="crm-table-wrap">
                <table className="crm-table">
                  <thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>Shipping</th><th>Billing</th><th>Updated</th><th>Actions</th></tr></thead>
                  <tbody>
                    {filteredCust.map(c => (
                      <tr key={c.id}>
                        <td className="td-name">{c.name || '—'}</td>
                        <td className="td-mono">{c.phone || '—'}</td>
                        <td>{c.email || '—'}</td>
                        <td className="td-addr">{c.shippingAddress ? c.shippingAddress.slice(0, 40) + (c.shippingAddress.length > 40 ? '…' : '') : <span className="td-miss">Not set</span>}</td>
                        <td className="td-addr">{c.billingAddress ? c.billingAddress.slice(0, 40) + (c.billingAddress.length > 40 ? '…' : '') : <span className="td-miss">Not set</span>}</td>
                        <td className="td-date">{c.updatedAt}</td>
                        <td><div style={{ display: 'flex', gap: 4 }}>
                          <button className="btn-edit" onClick={() => handleCustEdit(c)}>Edit</button>
                          <button className="btn-inv" onClick={() => { setInvoiceCustomer(c); setInvoiceForm(emptyInvoiceForm); setMsg(null); }}>Invoice</button>
                        </div></td>
                      </tr>
                    ))}
                    {!filteredCust.length && <tr><td colSpan={7} className="td-empty">{custSearch ? 'No matches' : 'No customers yet'}</td></tr>}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ═══ INVOICES TAB ═══ */}
        {tab === 'invoices' && (
          <div className="crm-tab-content">
            {selectedInvoice ? (
              /* ── Invoice Detail View ── */
              <div className="inv-detail">
                <button className="inv-back" onClick={() => { setSelectedInvoice(null); setInvDeliveryLogs([]); }}>← Back to list</button>
                {invDetailLoading ? <div className="crm-loading">Loading...</div> : (
                  <>
                    <div className="inv-header">
                      <div>
                        <div className="inv-num">{selectedInvoice.invoiceNumber || 'Draft'}</div>
                        <div className="inv-meta">{selectedInvoice.customerName} — {selectedInvoice.customerPhone}</div>
                        {selectedInvoice.customerEmail && <div className="inv-meta">Email: {selectedInvoice.customerEmail}</div>}
                        {selectedInvoice.purpose && <div className="inv-meta">Purpose: {selectedInvoice.purpose}</div>}
                        <div className="inv-meta">Entry: {selectedInvoice.entryPoint || '—'} | Payment: <span className={`badge ${selectedInvoice.paymentStatus}`}>{selectedInvoice.paymentStatus || '—'}</span></div>
                      </div>
                      <div className="inv-total-box">
                        <div className="inv-total-label">Total</div>
                        <div className="inv-total-val">Rs. {(selectedInvoice.total || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                        <span className={`badge ${selectedInvoice.status}`}>{selectedInvoice.status}</span>
                      </div>
                    </div>

                    {/* Addresses */}
                    <div className="inv-addr-row">
                      <div className="inv-addr"><div className="inv-addr-label">Bill To</div><div>{selectedInvoice.billingAddress || '—'}</div></div>
                      <div className="inv-addr"><div className="inv-addr-label">Ship To</div><div>{selectedInvoice.shippingAddress || '—'}</div></div>
                    </div>

                    {/* Items */}
                    {selectedInvoice.items && selectedInvoice.items.length > 0 && (
                      <table className="crm-table" style={{ marginBottom: 12 }}>
                        <thead><tr><th>#</th><th>Item</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead>
                        <tbody>
                          {selectedInvoice.items.map((it, i) => (
                            <tr key={i}><td>{i + 1}</td><td>{it.name}</td><td>{it.quantity}</td><td>Rs. {it.amount.toLocaleString()}</td><td>Rs. {(it.amount * it.quantity).toLocaleString()}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    )}

                    {/* Breakdown */}
                    <div className="inv-breakdown">
                      <div className="inv-bk-row"><span>Subtotal</span><span>Rs. {(selectedInvoice.subtotal || 0).toFixed(2)}</span></div>
                      {selectedInvoice.discount > 0 && <div className="inv-bk-row"><span>Discount</span><span>-Rs. {selectedInvoice.discount.toFixed(2)}</span></div>}
                      {selectedInvoice.shipping > 0 && <div className="inv-bk-row"><span>Shipping</span><span>Rs. {selectedInvoice.shipping.toFixed(2)}</span></div>}
                      <div className="inv-bk-row"><span>CGST @{(selectedInvoice.gstRate / 2).toFixed(1)}%</span><span>Rs. {(selectedInvoice.tax / 2).toFixed(2)}</span></div>
                      <div className="inv-bk-row"><span>SGST @{(selectedInvoice.gstRate / 2).toFixed(1)}%</span><span>Rs. {(selectedInvoice.tax / 2).toFixed(2)}</span></div>
                      {selectedInvoice.convenienceFee > 0 && <div className="inv-bk-row"><span>Conv. Fee</span><span>Rs. {selectedInvoice.convenienceFee.toFixed(2)}</span></div>}
                      <div className="inv-bk-row inv-bk-total"><span>Grand Total</span><span>Rs. {(selectedInvoice.total || 0).toFixed(2)}</span></div>
                    </div>

                    {/* Actions */}
                    <div className="inv-actions">
                      <Button variant="primary" loading={invActionLoading === 'image'} onClick={async () => {
                        setInvActionLoading('image'); setMsg(null);
                        try {
                          const r = await api.generateInvoiceImage(selectedInvoice.invoiceId);
                          if (r?.imageUrl) { window.open(r.imageUrl, '_blank'); setMsg({ type: 'success', text: 'Image generated' }); }
                          else setMsg({ type: 'error', text: 'Image generation failed' });
                        } catch { setMsg({ type: 'error', text: 'Error generating image' }); }
                        finally { setInvActionLoading(null); }
                      }}>Download Image</Button>
                      <Button variant="secondary" loading={invActionLoading === 'pdf'} onClick={async () => {
                        setInvActionLoading('pdf'); setMsg(null);
                        try {
                          const r = await api.generateInvoicePdf(selectedInvoice.invoiceId);
                          if (r?.pdfUrl) { window.open(r.pdfUrl, '_blank'); setMsg({ type: 'success', text: 'PDF generated' }); }
                          else setMsg({ type: 'error', text: 'PDF generation failed' });
                        } catch { setMsg({ type: 'error', text: 'Error generating PDF' }); }
                        finally { setInvActionLoading(null); }
                      }}>Download PDF</Button>
                      <Button variant="primary" loading={invActionLoading === 'send'} onClick={async () => {
                        if (!selectedInvoice.customerPhone) { setMsg({ type: 'error', text: 'No phone number' }); return; }
                        setInvActionLoading('send'); setMsg(null);
                        try {
                          const r = await api.sendInvoiceWhatsApp(selectedInvoice.invoiceId, selectedInvoice.customerPhone);
                          if (r?.status === 'sent' || r?.status === 'delivered' || r?.waMessageId) {
                            setMsg({ type: 'success', text: `Invoice sent to ${selectedInvoice.customerPhone}` });
                            loadInvoiceDetail(selectedInvoice.invoiceId);
                          } else setMsg({ type: 'error', text: 'WhatsApp send failed' });
                        } catch { setMsg({ type: 'error', text: 'Error sending' }); }
                        finally { setInvActionLoading(null); }
                      }}>Send on WhatsApp</Button>
                    </div>

                    {/* Delivery Logs */}
                    {invDeliveryLogs.length > 0 && (
                      <div style={{ marginTop: 16 }}>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 8 }}>Delivery Log</div>
                        <table className="crm-table">
                          <thead><tr><th>Time</th><th>Channel</th><th>To</th><th>Status</th><th>WA ID</th></tr></thead>
                          <tbody>
                            {invDeliveryLogs.map((log, i) => (
                              <tr key={i}>
                                <td className="td-date">{log.timestamp ? new Date(log.timestamp * 1000).toLocaleString() : '—'}</td>
                                <td>{log.channel}</td>
                                <td className="td-mono">{log.toNumber}</td>
                                <td><span className={`badge ${log.status}`}>{log.status}</span></td>
                                <td className="td-mono" style={{ fontSize: '0.7rem' }}>{log.waMessageId ? log.waMessageId.slice(-8) : '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* Metadata */}
                    <div className="inv-meta-grid">
                      <div><span>Invoice ID:</span> <span className="td-mono">{selectedInvoice.invoiceId.slice(0, 8)}...</span></div>
                      <div><span>Payment ID:</span> <span className="td-mono">{selectedInvoice.paymentId || '—'}</span></div>
                      <div><span>Order ID:</span> <span className="td-mono">{selectedInvoice.orderId || '—'}</span></div>
                      <div><span>GSTIN:</span> <span className="td-mono">{selectedInvoice.gstin || '—'}</span></div>
                      <div><span>Created:</span> <span>{selectedInvoice.createdAt ? new Date(selectedInvoice.createdAt * 1000).toLocaleString() : '—'}</span></div>
                      {selectedInvoice.paidAt > 0 && <div><span>Paid:</span> <span>{new Date(selectedInvoice.paidAt * 1000).toLocaleString()}</span></div>}
                    </div>
                  </>
                )}
              </div>
            ) : (
              /* ── Invoice List View ── */
              <>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                  <Button variant="primary" onClick={() => { setTab('customers'); setMsg({ type: 'success', text: 'Select a customer, then click "Invoice" to create one.' }); }}>+ New Invoice</Button>
                </div>
                {invLoading ? <div className="crm-loading">Loading invoices...</div> : (
                  <>
                    <div className="crm-stats">
                      <div className="crm-stat"><div className="crm-stat-val">{invoices.length}</div><div className="crm-stat-lbl">Total Invoices</div></div>
                      <div className="crm-stat"><div className="crm-stat-val">{invoices.filter(i => i.paymentStatus === 'captured' || i.status === 'paid').length}</div><div className="crm-stat-lbl">Paid</div></div>
                      <div className="crm-stat"><div className="crm-stat-val">{invoices.filter(i => i.status === 'created' || i.status === 'sent').length}</div><div className="crm-stat-lbl">Pending</div></div>
                      <div className="crm-stat"><div className="crm-stat-val">Rs. {invoices.reduce((s, i) => s + (i.total || 0), 0).toLocaleString()}</div><div className="crm-stat-lbl">Total Value</div></div>
                    </div>
                    <div className="crm-table-wrap">
                      <table className="crm-table">
                        <thead><tr><th>Invoice #</th><th>Customer</th><th>Purpose</th><th>Entry</th><th>Amount</th><th>Status</th><th>Date</th><th>Actions</th></tr></thead>
                        <tbody>
                          {invoices.map(inv => (
                            <tr key={inv.invoiceId}>
                              <td className="td-mono" style={{ cursor: 'pointer', color: '#059669' }} onClick={() => loadInvoiceDetail(inv.invoiceId)}>{inv.invoiceNumber || inv.invoiceId.slice(0, 8)}</td>
                              <td className="td-name">{inv.customerName || inv.customerPhone}</td>
                              <td>{inv.purpose || '—'}</td>
                              <td style={{ fontSize: '0.75rem' }}>{inv.entryPoint || '—'}</td>
                              <td className="td-name">Rs. {(inv.total || 0).toLocaleString()}</td>
                              <td><span className={`badge ${inv.paymentStatus || inv.status}`}>{inv.paymentStatus || inv.status}</span></td>
                              <td className="td-date">{inv.createdAt ? new Date(inv.createdAt * 1000).toLocaleDateString() : '—'}</td>
                              <td>
                                <button className="btn-inv" onClick={() => loadInvoiceDetail(inv.invoiceId)}>View</button>
                              </td>
                            </tr>
                          ))}
                          {!invoices.length && <tr><td colSpan={8} className="td-empty">No invoices yet. Invoices are created automatically when payments are captured via Razorpay webhook, or manually from the Customers tab.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        )}

        {/* ═══ PENDING DUES TAB ═══ */}
        {tab === 'dues' && (
          <div className="crm-tab-content">
            {duesLoading ? <div className="crm-loading">Loading dues...</div> : (
              <>
                <div className="crm-stats">
                  <div className="crm-stat"><div className="crm-stat-val">{dues.length}</div><div className="crm-stat-lbl">Pending</div></div>
                  <div className="crm-stat"><div className="crm-stat-val">₹{dues.reduce((s, d) => s + (d.amount || 0), 0).toLocaleString()}</div><div className="crm-stat-lbl">Total Outstanding</div></div>
                </div>
                <div className="crm-info"><span>Info</span><div>These are payment requests sent via WhatsApp that haven't been paid yet. Customers see these as "Pending Dues" when they start the pay flow.</div></div>
                <div className="crm-table-wrap">
                  <table className="crm-table">
                    <thead><tr><th>#</th><th>Customer</th><th>Phone</th><th>Item</th><th>Amount</th><th>Ref</th><th>Date</th></tr></thead>
                    <tbody>
                      {dues.map((d, i) => (
                        <tr key={d.id}>
                          <td>{i + 1}</td>
                          <td className="td-name">{d.customerName || '—'}</td>
                          <td className="td-mono">{d.customerPhone}</td>
                          <td>{d.itemName}</td>
                          <td className="td-name">₹{d.amount.toLocaleString()}</td>
                          <td className="td-mono">{d.ref.length > 8 ? '…' + d.ref.slice(-6) : d.ref}</td>
                          <td className="td-date">{d.createdAt}</td>
                        </tr>
                      ))}
                      {!dues.length && <tr><td colSpan={7} className="td-empty">No pending dues</td></tr>}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {/* ═══ FLOW CONFIG TAB ═══ */}
        {tab === 'config' && (
          <div className="crm-tab-content">
            {configLoading ? <div className="crm-loading">Loading config...</div> : (
              <div className="crm-config">
                <div className="crm-info"><span>Config</span><div>These settings control the WhatsApp pay flow: GST rate, shipping, promo discount, GSTIN, and purpose list. Changes apply immediately to new pay flows.</div></div>
                <div className="crm-config-grid">
                  {[
                    { label: 'GST Rate (%)', key: 'default_gst_rate', type: 'number' },
                    { label: 'Shipping (₹)', key: 'default_shipping', type: 'number' },
                    { label: 'Promo Discount (₹)', key: 'default_promo', type: 'number' },
                    { label: 'GSTIN', key: 'gstin', type: 'text' },
                    { label: 'Default Item Name', key: 'default_item_name', type: 'text' },
                  ].map(f => (
                    <div key={f.key} className="crm-field">
                      <label>{f.label}</label>
                      <input type={f.type} value={(flowConfig as any)[f.key] ?? ''} onChange={e => setFlowConfig(prev => ({ ...prev, [f.key]: f.type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value }))} />
                    </div>
                  ))}
                </div>
                <div className="crm-field" style={{ marginTop: 16 }}>
                  <label>Purpose List (one per line)</label>
                  <textarea rows={12} value={(flowConfig.purposes || []).join('\n')} onChange={e => setFlowConfig(prev => ({ ...prev, purposes: e.target.value.split('\n').filter(Boolean) }))} />
                </div>
                <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
                  <Button variant="primary" onClick={handleSaveConfig} loading={configSaving}>{configSaving ? 'Saving...' : 'Save Config'}</Button>
                  <Button variant="secondary" onClick={() => { setFlowConfig(defaultFlowConfig); setMsg({ type: 'success', text: 'Reset to defaults' }); }}>Reset Defaults</Button>
                </div>
              </div>
            )}
          </div>
        )}


        {/* ═══ CUSTOMER FORM MODAL ═══ */}
        {showCustForm && (
          <div className="crm-overlay" onClick={() => { setShowCustForm(false); setEditCustId(null); }}>
            <div className="crm-modal" onClick={e => e.stopPropagation()}>
              <h3>{editCustId ? 'Edit Customer' : 'New Customer'}</h3>
              <p className="crm-modal-sub">{editCustId ? 'Update details — auto-fills in WhatsApp pay flow' : 'Add customer — auto-fills in WhatsApp pay flow'}</p>
              {[
                { label: 'Full Name *', key: 'name', type: 'text', ph: 'Rahul Sharma' },
                { label: 'Phone *', key: 'phone', type: 'tel', ph: '+919876543210' },
                { label: 'Email', key: 'email', type: 'email', ph: 'rahul@example.com' },
                { label: 'Shipping Address', key: 'shippingAddress', type: 'text', ph: '123 Park Street, Kolkata 700016' },
                { label: 'Billing Address', key: 'billingAddress', type: 'text', ph: 'Same as shipping or different' },
              ].map(f => (
                <div key={f.key} className="crm-field">
                  <label>{f.label}</label>
                  <input type={f.type} value={(custForm as any)[f.key] || ''} placeholder={f.ph} onChange={e => setCustForm(prev => ({ ...prev, [f.key]: e.target.value }))} />
                </div>
              ))}
              <div className="crm-modal-actions">
                <Button variant="secondary" onClick={() => { setShowCustForm(false); setEditCustId(null); }}>Cancel</Button>
                <Button variant="primary" onClick={handleCustSave} loading={custSaving}>{custSaving ? 'Saving...' : editCustId ? 'Update' : 'Create'}</Button>
              </div>
            </div>
          </div>
        )}

        {/* ═══ INVOICE MODAL ═══ */}
        {invoiceCustomer && (
          <div className="crm-overlay" onClick={() => setInvoiceCustomer(null)}>
            <div className="crm-modal" onClick={e => e.stopPropagation()}>
              <h3>Create Invoice</h3>
              <p className="crm-modal-sub">For {invoiceCustomer.name} ({invoiceCustomer.phone})</p>
              <div className="crm-cust-info">
                <div>Name: {invoiceCustomer.name}</div>
                <div>Phone: {invoiceCustomer.phone}</div>
                {invoiceCustomer.email && <div>Email: {invoiceCustomer.email}</div>}
                {invoiceCustomer.billingAddress && <div>Bill To: {invoiceCustomer.billingAddress}</div>}
                {invoiceCustomer.shippingAddress && <div>Ship To: {invoiceCustomer.shippingAddress}</div>}
              </div>
              {[
                { label: 'Item Name *', key: 'itemName', type: 'text', ph: 'Product or service' },
                { label: 'Unit Price (₹) *', key: 'unitPrice', type: 'number', ph: '500' },
                { label: 'Quantity', key: 'quantity', type: 'number', ph: '1' },
                { label: 'GST Rate (%)', key: 'gstRate', type: 'number', ph: '18' },
                { label: 'Shipping (₹)', key: 'shipping', type: 'number', ph: '49' },
                { label: 'Promo Discount (₹)', key: 'discount', type: 'number', ph: '15' },
                { label: 'Purpose', key: 'purpose', type: 'text', ph: 'e.g. BNB Club' },
                { label: 'Order ID', key: 'orderId', type: 'text', ph: 'Offline' },
              ].map(f => (
                <div key={f.key} className="crm-field">
                  <label>{f.label}</label>
                  <input type={f.type} value={(invoiceForm as any)[f.key] || ''} placeholder={f.ph} onChange={e => setInvoiceForm(prev => ({ ...prev, [f.key]: e.target.value }))} />
                </div>
              ))}
              {invoiceForm.unitPrice && parseFloat(invoiceForm.unitPrice) > 0 && (() => {
                const up = parseFloat(invoiceForm.unitPrice) || 0, q = parseInt(invoiceForm.quantity) || 1;
                const sub = up * q, disc = Math.min(parseFloat(invoiceForm.discount) || 15, sub);
                const ap = sub - disc, gst = ap * (parseFloat(invoiceForm.gstRate) || 18) / 100;
                const ship = parseFloat(invoiceForm.shipping) || 49, conv = ap * 0.02 * 1.18;
                const total = ap + gst + ship + conv;
                return (
                  <div className="crm-preview">
                    <div>Subtotal: ₹{sub.toFixed(2)}</div>
                    {disc > 0 && <div>Promo: -₹{disc.toFixed(2)}</div>}
                    <div>GST: ₹{gst.toFixed(2)}</div><div>Shipping: ₹{ship.toFixed(2)}</div>
                    <div>Conv Fee: ₹{conv.toFixed(2)}</div>
                    <div className="crm-preview-total">Total: ₹{total.toFixed(2)}</div>
                  </div>
                );
              })()}
              <div className="crm-modal-actions">
                <Button variant="secondary" onClick={() => setInvoiceCustomer(null)}>Cancel</Button>
                <Button variant="primary" onClick={handleCreateInvoice} loading={invoiceSaving}>{invoiceSaving ? 'Creating...' : 'Create & Send'}</Button>
              </div>
            </div>
          </div>
        )}
      </div>


      <style jsx>{`
        .crm-page { padding: 20px; max-width: 1200px; margin: 0 auto; }
        .crm-msg { padding: 10px 14px; border-radius: 10px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
        .crm-msg.success { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
        .crm-msg.error { background: #ECFDF5; color: #059669; border: 1px solid #6ee7b7; }
        .crm-msg button { background: none; border: none; font-size: 16px; cursor: pointer; color: inherit; }
        .crm-tab-content { margin-top: 16px; }
        .crm-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }
        .crm-stat { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; text-align: center; }
        .crm-stat-val { font-size: 1.5rem; font-weight: 700; color: #111827; }
        .crm-stat-lbl { font-size: 0.75rem; color: #6b7280; margin-top: 2px; }
        .crm-info { display: flex; gap: 10px; align-items: flex-start; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; font-size: 0.85rem; color: #166534; }
        .crm-search { position: relative; margin-bottom: 16px; }
        .crm-search input { width: 100%; padding: 10px 14px; border: 1.5px solid #10B981; border-radius: 10px; font-size: 14px; box-sizing: border-box; }
        .crm-search input:focus { outline: none; box-shadow: 0 0 0 3px rgba(16,185,129,0.2); }
        .crm-search-x { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); background: none; border: none; font-size: 18px; cursor: pointer; color: #6b7280; }
        .crm-loading { text-align: center; padding: 3rem; color: #6b7280; }
        .crm-table-wrap { overflow-x: auto; }
        .crm-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        .crm-table th { text-align: left; padding: 10px 12px; background: #f9fafb; border-bottom: 2px solid #e5e7eb; font-weight: 600; color: #374151; white-space: nowrap; }
        .crm-table td { padding: 10px 12px; border-bottom: 1px solid #f3f4f6; }
        .crm-table tr:hover { background: #f0fdf4; }
        .td-name { font-weight: 600; color: #111827; }
        .td-mono { font-family: monospace; font-size: 0.8rem; }
        .td-addr { max-width: 200px; font-size: 0.8rem; color: #4b5563; }
        .td-date { font-size: 0.75rem; color: #9ca3af; white-space: nowrap; }
        .td-miss { color: #d1d5db; font-style: italic; font-size: 0.8rem; }
        .td-empty { text-align: center; padding: 2rem; color: #9ca3af; }
        .btn-edit { padding: 4px 12px; border-radius: 6px; border: 1px solid #6366f1; background: #eef2ff; color: #4f46e5; cursor: pointer; font-size: 0.75rem; }
        .btn-edit:hover { background: #e0e7ff; }
        .btn-inv { padding: 4px 12px; border-radius: 6px; border: 1px solid #10B981; background: #ecfdf5; color: #059669; cursor: pointer; font-size: 0.75rem; }
        .btn-inv:hover { background: #d1fae5; }
        .badge { padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; }
        .badge.pending { background: #fef3c7; color: #92400e; }
        .badge.paid, .badge.captured { background: #d1fae5; color: #065f46; }
        .badge.sent, .badge.delivered { background: #dbeafe; color: #1e40af; }
        .badge.failed, .badge.cancelled { background: #ECFDF5; color: #065f46; }
        .badge.created { background: #f3f4f6; color: #374151; }
        .crm-config { max-width: 600px; }
        .crm-config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .crm-field { margin-bottom: 12px; }
        .crm-field label { display: block; font-size: 0.75rem; color: #6b7280; margin-bottom: 3px; font-weight: 600; }
        .crm-field input, .crm-field textarea { width: 100%; padding: 8px 12px; border: 1.5px solid #d1d5db; border-radius: 8px; font-size: 0.9rem; box-sizing: border-box; font-family: inherit; }
        .crm-field input:focus, .crm-field textarea:focus { outline: none; border-color: #10B981; box-shadow: 0 0 0 3px rgba(16,185,129,0.15); }
        .crm-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .crm-modal { background: #fff; border-radius: 12px; padding: 24px; width: 440px; max-height: 85vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
        .crm-modal h3 { margin: 0 0 4px; font-size: 1.1rem; }
        .crm-modal-sub { margin: 0 0 16px; font-size: 0.8rem; color: #6b7280; }
        .crm-modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
        .crm-cust-info { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; font-size: 0.8rem; color: #4b5563; line-height: 1.6; }
        .crm-preview { background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; font-size: 0.8rem; color: #92400e; line-height: 1.6; }
        .crm-preview-total { font-weight: 700; margin-top: 4px; padding-top: 4px; border-top: 1px solid #fde68a; }
        .inv-detail { }
        .inv-back { background: none; border: none; color: #059669; cursor: pointer; font-size: 0.85rem; margin-bottom: 12px; padding: 0; }
        .inv-back:hover { text-decoration: underline; }
        .inv-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
        .inv-num { font-size: 1.2rem; font-weight: 700; font-family: monospace; color: #111827; }
        .inv-meta { font-size: 0.8rem; color: #6b7280; margin-top: 2px; }
        .inv-total-box { text-align: right; }
        .inv-total-label { font-size: 0.75rem; color: #6b7280; }
        .inv-total-val { font-size: 1.4rem; font-weight: 700; color: #059669; }
        .inv-addr-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
        .inv-addr { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; font-size: 0.8rem; color: #4b5563; }
        .inv-addr-label { font-weight: 600; font-size: 0.75rem; color: #374151; margin-bottom: 4px; }
        .inv-breakdown { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; max-width: 360px; }
        .inv-bk-row { display: flex; justify-content: space-between; font-size: 0.8rem; color: #4b5563; padding: 3px 0; }
        .inv-bk-total { font-weight: 700; color: #111827; border-top: 2px solid #10B981; padding-top: 6px; margin-top: 4px; font-size: 0.9rem; }
        .inv-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
        .inv-meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.75rem; color: #6b7280; margin-top: 16px; padding-top: 12px; border-top: 1px solid #e5e7eb; }
        .inv-meta-grid span:first-child { font-weight: 600; color: #374151; }
        @media (max-width: 768px) {
          .crm-stats { grid-template-columns: 1fr 1fr; }
          .crm-config-grid { grid-template-columns: 1fr; }
          .crm-modal { width: 95%; margin: 0 10px; }
        }
      `}</style>
    </>
  );

  if (embedded) return content;

  return (
    <Layout user={user} onSignOut={signOut}>
      {content}
    </Layout>
  );
};

export default PayFlowPage;
