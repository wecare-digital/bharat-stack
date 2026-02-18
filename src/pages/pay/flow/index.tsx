/* Pay Flow CRM - WECARE.DIGITAL */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import PageShell, { ShellTab } from '../../../components/PageShell';
import Button from '../../../components/ui/Button';
import * as api from '../../../api/client';
import type { Invoice, InvoiceDeliveryLog, Contact, CreateInvoiceEngineRequest } from '../../../api/client';

interface PP { signOut?: () => void; user?: any; embedded?: boolean; }
interface FC { default_gst_rate:number; default_shipping:number; default_promo:number; gstin:string; default_item_name:string; purposes:string[]; }
interface IR { name:string; unitPrice:string; quantity:string; gstRate:string; }

const EMPTY_FORM = { name:'',phone:'',email:'',shippingAddress:'',billingAddress:'' };
const NEW_ITEM = ():IR => ({ name:'', unitPrice:'', quantity:'1', gstRate:'18' });
const EMPTY_INV = { items:[NEW_ITEM()] as IR[], shipping:'49', discount:'15', purpose:'', orderId:'', greenPacking:'', notificationFee:'' };
const DEF_CFG:FC = { default_gst_rate:18, default_shipping:49, default_promo:15, gstin:'19AADFW7431N1ZK', default_item_name:'Services/Goods', purposes:['BNB Club','No Fault','Expo Week','Ritual Guru','Legal Champ','Gift Card','Service Fee','Consultation'] };
const TABS:ShellTab[] = [
  { id:'customers', label:'Customers' },
  { id:'create', label:'Create Invoice' },
  { id:'invoices', label:'Invoices' },
  { id:'dues', label:'Pending Dues' },
  { id:'config', label:'Flow Config' },
];
const STATUS_FILTERS = [
  { id:'all', label:'All' },
  { id:'created', label:'Created' },
  { id:'pending_payment', label:'Pending' },
  { id:'paid', label:'Paid' },
  { id:'cancelled', label:'Cancelled' },
];
const badgeClass = (inv:Invoice) => inv.status==='paid'||inv.paymentStatus==='captured'?'success':inv.status==='cancelled'?'danger':'muted';
const fmtDate = (ts:number) => ts ? new Date(ts).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}) : '\u2014';
const fmtMoney = (n:number) => `\u20B9${(n||0).toLocaleString('en-IN',{minimumFractionDigits:2})}`;

/* ── Component ── */
const PayFlowPage: React.FC<PP> = ({ signOut, user, embedded }) => {
  const [customers, setCustomers] = useState<Contact[]>([]);
  const [custSearch, setCustSearch] = useState('');
  const [custLoading, setCustLoading] = useState(false);
  const [editCust, setEditCust] = useState<Partial<Contact>|null>(null);
  const [custForm, setCustForm] = useState(EMPTY_FORM);
  const [custSaving, setCustSaving] = useState(false);
  const [selCustomer, setSelCustomer] = useState<Contact|null>(null);
  const [invForm, setInvForm] = useState({...EMPTY_INV});
  const [creating, setCreating] = useState(false);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [invLoading, setInvLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [selInvoice, setSelInvoice] = useState<Invoice|null>(null);
  const [deliveryLogs, setDeliveryLogs] = useState<InvoiceDeliveryLog[]>([]);
  const [actionLoading, setActionLoading] = useState('');
  const [config, setConfig] = useState<FC>(DEF_CFG);
  const [configSaving, setConfigSaving] = useState(false);
  const [msg, setMsg] = useState<{text:string;type:'success'|'error'}|null>(null);
  const showMsg = (text:string, type:'success'|'error'='success') => { setMsg({text,type}); setTimeout(()=>setMsg(null),4000); };

  /* Loaders */
  const loadCustomers = useCallback(async () => {
    setCustLoading(true);
    try { const c = await api.listContacts(); setCustomers(c||[]); } catch(e) { console.error(e); }
    setCustLoading(false);
  },[]);
  const loadInvoices = useCallback(async () => {
    setInvLoading(true);
    try {
      const params = statusFilter==='all' ? {} : { status: statusFilter };
      const r = await api.listInvoicesEngine(params);
      setInvoices(r.invoices||[]);
    } catch(e) { console.error(e); }
    setInvLoading(false);
  },[statusFilter]);
  const loadDeliveryLogs = useCallback(async (id:string) => {
    try { const r = await api.getInvoiceDeliveryLog(id); setDeliveryLogs(r.deliveryLogs||[]); } catch(e) { console.error(e); }
  },[]);
  useEffect(() => { loadCustomers(); loadInvoices(); }, [loadCustomers, loadInvoices]);

  /* Customer handlers */
  const openEditCust = (c:Contact) => { setEditCust(c); setCustForm({name:c.name||'',phone:c.phone||'',email:c.email||'',shippingAddress:c.shippingAddress||'',billingAddress:c.billingAddress||''}); };
  const closeEditCust = () => { setEditCust(null); setCustForm(EMPTY_FORM); };
  const saveCust = async () => {
    if(!editCust) return;
    setCustSaving(true);
    try {
      if(editCust.id) { await api.updateContact(editCust.id, custForm); showMsg('Customer updated'); }
      else { await api.createContact(custForm); showMsg('Customer created'); }
      closeEditCust(); loadCustomers();
    } catch(e) { showMsg('Save failed','error'); }
    setCustSaving(false);
  };

  /* Invoice form handlers */
  const updateItem = (idx:number, field:keyof IR, val:string) => {
    const items = [...invForm.items]; items[idx] = {...items[idx],[field]:val}; setInvForm({...invForm, items});
  };
  const addItem = () => setInvForm({...invForm, items:[...invForm.items, NEW_ITEM()]});
  const removeItem = (idx:number) => { if(invForm.items.length<=1) return; setInvForm({...invForm, items:invForm.items.filter((_,i)=>i!==idx)}); };
  const calcSubtotal = () => invForm.items.reduce((s,it) => s + (parseFloat(it.unitPrice)||0)*(parseInt(it.quantity)||0), 0);
  const calcTax = () => invForm.items.reduce((s,it) => { const line=(parseFloat(it.unitPrice)||0)*(parseInt(it.quantity)||0); return s + line*(parseFloat(it.gstRate)||0)/100; }, 0);
  const calcTotal = () => {
    return calcSubtotal() + calcTax() + (parseFloat(invForm.shipping)||0) - (parseFloat(invForm.discount)||0) + (parseFloat(invForm.greenPacking)||0) + (parseFloat(invForm.notificationFee)||0);
  };

  const submitInvoice = async () => {
    if(!selCustomer) { showMsg('Select a customer first','error'); return; }
    if(!invForm.items.some(it=>parseFloat(it.unitPrice)>0)) { showMsg('Add at least one item','error'); return; }
    setCreating(true);
    try {
      const req: CreateInvoiceEngineRequest = {
        customerPhone: selCustomer.phone, customerEmail: selCustomer.email||'',
        customerName: selCustomer.name, contactId: selCustomer.id,
        shippingAddress: selCustomer.shippingAddress||'', billingAddress: selCustomer.billingAddress||'',
        items: invForm.items.map(it=>({ name:it.name||config.default_item_name, amount:parseFloat(it.unitPrice)||0, quantity:parseInt(it.quantity)||1, gstRate:parseFloat(it.gstRate)||config.default_gst_rate })),
        shipping: (parseFloat(invForm.shipping)||0) + (parseFloat(invForm.greenPacking)||0) + (parseFloat(invForm.notificationFee)||0),
        discount: parseFloat(invForm.discount)||0, gstRate: config.default_gst_rate,
        purpose: invForm.purpose, orderId: invForm.orderId, gstin: config.gstin,
      };
      const r = await api.createInvoiceEngine(req);
      if(r) { showMsg(`Invoice ${r.invoiceNumber} created \u2014 \u20B9${r.total}`); setInvForm({...EMPTY_INV, items:[NEW_ITEM()]}); setSelCustomer(null); loadInvoices(); }
      else showMsg('Create failed','error');
    } catch(e) { showMsg('Create failed','error'); }
    setCreating(false);
  };

  /* Invoice action handlers */
  const doSendPaymentLink = async (inv:Invoice) => {
    setActionLoading('send');
    try { const r = await api.sendPaymentLink(inv.invoiceId); if(r) { showMsg('Payment link sent'); loadInvoices(); } else showMsg('Send failed','error'); } catch(e) { showMsg('Send failed','error'); }
    setActionLoading('');
  };
  const doCancelInvoice = async (inv:Invoice) => {
    if(!confirm('Cancel this invoice?')) return;
    setActionLoading('cancel');
    try { const r = await api.cancelInvoice(inv.invoiceId); if(r) { showMsg('Invoice cancelled'); setSelInvoice(null); loadInvoices(); } else showMsg('Cancel failed','error'); } catch(e) { showMsg('Cancel failed','error'); }
    setActionLoading('');
  };
  const doGenerateImage = async (inv:Invoice) => {
    setActionLoading('img');
    try { await api.generateInvoiceImage(inv.invoiceId); showMsg('Image generated'); } catch(e) { showMsg('Failed','error'); }
    setActionLoading('');
  };
  const doGeneratePdf = async (inv:Invoice) => {
    setActionLoading('pdf');
    try { await api.generateInvoicePdf(inv.invoiceId); showMsg('PDF generated'); } catch(e) { showMsg('Failed','error'); }
    setActionLoading('');
  };
  const selectInvoice = (inv:Invoice) => { setSelInvoice(inv); loadDeliveryLogs(inv.invoiceId); };

  /* Computed */
  const filteredCust = customers.filter(c => {
    if(!custSearch) return true;
    const q = custSearch.toLowerCase();
    return (c.name||'').toLowerCase().includes(q) || (c.phone||'').includes(q) || (c.email||'').toLowerCase().includes(q);
  });
  const invStats = {
    total: invoices.length,
    paid: invoices.filter(i=>i.status==='paid'||i.paymentStatus==='captured').length,
    pending: invoices.filter(i=>i.status==='pending_payment').length,
    totalAmt: invoices.reduce((s,i)=>s+i.total,0),
  };

  /* ═══ RENDER ═══ */
  const shellContent = (
    <PageShell title="Flow CRM" subtitle="Customers, Invoices & Payments" tabs={TABS} defaultTab="customers">
      {(activeTab) => (
        <div className="inner-page">
          {msg && <div className={`msg-bar ${msg.type}`} style={{margin:'0 0 16px'}}>{msg.text}<button onClick={()=>setMsg(null)} style={{background:'none',border:'none',cursor:'pointer',marginLeft:8}}>{'\u2715'}</button></div>}

          {/* CUSTOMERS TAB */}
          {activeTab === 'customers' && (
            <div className="pf-tab-body">
              <div className="pf-toolbar">
                <input className="search-input" placeholder="Search customers\u2026" value={custSearch} onChange={e=>setCustSearch(e.target.value)} />
                <Button variant="primary" size="sm" onClick={()=>{setEditCust({} as Contact); setCustForm(EMPTY_FORM);}}>+ New Customer</Button>
                <Button variant="secondary" size="sm" icon="refresh" loading={custLoading} onClick={loadCustomers}>Refresh</Button>
              </div>
              <div className="stats-grid" style={{marginBottom:16}}>
                <div className="stat-card accent"><div className="pf-stat-value">{customers.length}</div><div className="pf-stat-label">Total Customers</div></div>
              </div>
              <div className="table-container">
                <table className="inner-table">
                  <thead><tr><th>#</th><th>Name</th><th>Phone</th><th>Email</th><th>Shipping</th><th>Billing</th><th>Updated</th><th>Actions</th></tr></thead>
                  <tbody>
                    {filteredCust.length===0 && <tr className="empty-row"><td colSpan={8}>No customers found</td></tr>}
                    {filteredCust.map((c,i)=>(
                      <tr key={c.id}>
                        <td>{i+1}</td>
                        <td style={{fontWeight:600}}>{c.name||'\u2014'}</td>
                        <td>{c.phone||'\u2014'}</td>
                        <td>{c.email||'\u2014'}</td>
                        <td className="pf-cell-truncate">{c.shippingAddress||'\u2014'}</td>
                        <td className="pf-cell-truncate">{c.billingAddress||'\u2014'}</td>
                        <td>{fmtDate(new Date(c.updatedAt||c.createdAt||'').getTime())}</td>
                        <td><Button variant="ghost" size="sm" onClick={()=>openEditCust(c)}>Edit</Button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {editCust && (
                <div className="pf-modal-overlay" onClick={closeEditCust}>
                  <div className="pf-modal-box" onClick={e=>e.stopPropagation()}>
                    <div className="pf-modal-header">
                      <h3>{editCust.id ? 'Edit Customer' : 'New Customer'}</h3>
                      <Button variant="ghost" size="sm" onClick={closeEditCust}>{'\u2715'}</Button>
                    </div>
                    <div className="form-group"><label>Name</label><input type="text" value={custForm.name} onChange={e=>setCustForm({...custForm,name:e.target.value})} /></div>
                    <div className="form-group"><label>Phone</label><input type="tel" value={custForm.phone} onChange={e=>setCustForm({...custForm,phone:e.target.value})} /></div>
                    <div className="form-group"><label>Email</label><input type="email" value={custForm.email} onChange={e=>setCustForm({...custForm,email:e.target.value})} /></div>
                    <div className="form-group"><label>Shipping Address</label><textarea value={custForm.shippingAddress} onChange={e=>setCustForm({...custForm,shippingAddress:e.target.value})} /></div>
                    <div className="form-group"><label>Billing Address</label><textarea value={custForm.billingAddress} onChange={e=>setCustForm({...custForm,billingAddress:e.target.value})} /></div>
                    <div className="pf-modal-actions">
                      <Button variant="secondary" size="sm" onClick={closeEditCust}>Cancel</Button>
                      <Button variant="primary" size="sm" loading={custSaving} onClick={saveCust}>Save</Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* CREATE INVOICE TAB */}
          {activeTab === 'create' && (
            <div className="pf-tab-body">
              {!selCustomer ? (
                <div>
                  <h3 style={{margin:'0 0 12px',fontSize:18}}>Step 1 {'\u2014'} Select Customer</h3>
                  <input className="search-input" placeholder="Search\u2026" value={custSearch} onChange={e=>setCustSearch(e.target.value)} style={{marginBottom:16,maxWidth:400}} />
                  <div className="pf-cust-grid">
                    {filteredCust.map(c=>(
                      <div key={c.id} onClick={()=>setSelCustomer(c)} className="pf-cust-card">
                        <div className="pf-cust-avatar">{(c.name||'?')[0].toUpperCase()}</div>
                        <div className="pf-cust-info">
                          <div className="pf-cust-name">{c.name||'Unknown'}</div>
                          <div className="pf-cust-phone">{c.phone||'\u2014'}</div>
                        </div>
                      </div>
                    ))}
                    {filteredCust.length===0 && <div className="pf-empty">No customers. Create one in the Customers tab.</div>}
                  </div>
                </div>
              ) : (
                <div>
                  <div className="info-banner" style={{marginBottom:16}}>
                    <div style={{flex:1}}><strong>{selCustomer.name}</strong> {'\u2014'} {selCustomer.phone} {selCustomer.email ? ` \u00B7 ${selCustomer.email}` : ''}</div>
                    <Button variant="ghost" size="sm" onClick={()=>setSelCustomer(null)}>Change</Button>
                  </div>
                  <h3 style={{margin:'0 0 12px',fontSize:18}}>Step 2 {'\u2014'} Invoice Details</h3>
                  <div className="table-container" style={{marginBottom:16}}>
                    <table className="inner-table">
                      <thead><tr><th>#</th><th>Item Name</th><th>Price ({'\u20B9'})</th><th>Qty</th><th>GST %</th><th>Line Total</th><th></th></tr></thead>
                      <tbody>
                        {invForm.items.map((it,i)=>{
                          const line = (parseFloat(it.unitPrice)||0)*(parseInt(it.quantity)||0);
                          const gst = line*(parseFloat(it.gstRate)||0)/100;
                          return (
                            <tr key={i}>
                              <td>{i+1}</td>
                              <td><input type="text" value={it.name} onChange={e=>updateItem(i,'name',e.target.value)} placeholder={config.default_item_name} className="pf-inline-input" /></td>
                              <td><input type="number" value={it.unitPrice} onChange={e=>updateItem(i,'unitPrice',e.target.value)} className="pf-num-input" /></td>
                              <td><input type="number" value={it.quantity} onChange={e=>updateItem(i,'quantity',e.target.value)} className="pf-num-input-sm" /></td>
                              <td><input type="number" value={it.gstRate} onChange={e=>updateItem(i,'gstRate',e.target.value)} className="pf-num-input-sm" /></td>
                              <td style={{fontWeight:600}}>{fmtMoney(line+gst)}</td>
                              <td>{invForm.items.length>1 && <button onClick={()=>removeItem(i)} className="pf-remove-btn">{'\u2715'}</button>}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <Button variant="secondary" size="sm" onClick={addItem} style={{marginBottom:20}}>+ Add Item</Button>
                  <h4 style={{margin:'0 0 8px',fontSize:15}}>Additional Charges</h4>
                  <div className="pf-form-grid">
                    <div className="form-group"><label>Express / Shipping ({'\u20B9'})</label><input type="number" value={invForm.shipping} onChange={e=>setInvForm({...invForm,shipping:e.target.value})} /></div>
                    <div className="form-group"><label>Promo / Discount ({'\u20B9'})</label><input type="number" value={invForm.discount} onChange={e=>setInvForm({...invForm,discount:e.target.value})} /></div>
                    <div className="form-group"><label>Green Packing ({'\u20B9'})</label><input type="number" value={invForm.greenPacking} onChange={e=>setInvForm({...invForm,greenPacking:e.target.value})} placeholder="0" /></div>
                    <div className="form-group"><label>Notification / Alert Fee ({'\u20B9'})</label><input type="number" value={invForm.notificationFee} onChange={e=>setInvForm({...invForm,notificationFee:e.target.value})} placeholder="0" /></div>
                  </div>
                  <div className="pf-form-grid">
                    <div className="form-group">
                      <label>Brand</label>
                      <select value={invForm.purpose} onChange={e=>setInvForm({...invForm,purpose:e.target.value})}>
                        <option value="">{'\u2014'} Select {'\u2014'}</option>
                        {config.purposes.map(p=><option key={p} value={p}>{p}</option>)}
                      </select>
                    </div>
                    <div className="form-group"><label>Order ID</label><input type="text" value={invForm.orderId} onChange={e=>setInvForm({...invForm,orderId:e.target.value})} placeholder="Optional" /></div>
                  </div>
                  <div className="inner-card" style={{marginBottom:20,maxWidth:500}}>
                    <h4 style={{margin:'0 0 8px',fontSize:14}}>Preview</h4>
                    <div className="pf-preview-row"><span>Subtotal</span><span>{fmtMoney(calcSubtotal())}</span></div>
                    <div className="pf-preview-row"><span>Tax (GST)</span><span>{fmtMoney(calcTax())}</span></div>
                    <div className="pf-preview-row"><span>Express</span><span>{fmtMoney(parseFloat(invForm.shipping)||0)}</span></div>
                    {(parseFloat(invForm.greenPacking)||0)>0 && <div className="pf-preview-row"><span>Green Packing</span><span>{fmtMoney(parseFloat(invForm.greenPacking)||0)}</span></div>}
                    {(parseFloat(invForm.notificationFee)||0)>0 && <div className="pf-preview-row"><span>Notification Fee</span><span>{fmtMoney(parseFloat(invForm.notificationFee)||0)}</span></div>}
                    <div className="pf-preview-row"><span>Promo</span><span>{'\u2212'}{fmtMoney(parseFloat(invForm.discount)||0)}</span></div>
                    <div className="pf-preview-total"><span>Total</span><span>{fmtMoney(calcTotal())}</span></div>
                  </div>
                  <Button variant="primary" size="md" loading={creating} onClick={submitInvoice}>Create Invoice</Button>
                </div>
              )}
            </div>
          )}

          {/* INVOICES TAB */}
          {activeTab === 'invoices' && (
            <div className="pf-tab-body">
              <div className="pf-filter-bar">
                {STATUS_FILTERS.map(f=>(
                  <button key={f.id} className={`btn btn-sm ${statusFilter===f.id?'btn-primary':'btn-secondary'}`} onClick={()=>setStatusFilter(f.id)}>{f.label}</button>
                ))}
                <div style={{flex:1}} />
                <Button variant="secondary" size="sm" icon="refresh" loading={invLoading} onClick={loadInvoices}>Refresh</Button>
              </div>
              <div className="stats-grid" style={{marginBottom:16}}>
                <div className="stat-card accent"><div className="pf-stat-value">{invStats.total}</div><div className="pf-stat-label">Total</div></div>
                <div className="stat-card"><div className="pf-stat-value">{invStats.paid}</div><div className="pf-stat-label">Paid</div></div>
                <div className="stat-card"><div className="pf-stat-value">{invStats.pending}</div><div className="pf-stat-label">Pending</div></div>
                <div className="stat-card"><div className="pf-stat-value">{fmtMoney(invStats.totalAmt)}</div><div className="pf-stat-label">Total Value</div></div>
              </div>
              <div className="pf-inv-layout">
                <div className="pf-inv-list">
                  <div className="table-container">
                    <table className="inner-table">
                      <thead><tr><th>#</th><th>Ref</th><th>Customer</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
                      <tbody>
                        {invoices.length===0 && <tr className="empty-row"><td colSpan={6}>No invoices</td></tr>}
                        {invoices.map((inv,i)=>(
                          <tr key={inv.invoiceId} onClick={()=>selectInvoice(inv)} style={{cursor:'pointer'}} className={selInvoice?.invoiceId===inv.invoiceId?'pf-row-selected':''}>
                            <td>{i+1}</td>
                            <td style={{fontFamily:'monospace',fontSize:12}}>{inv.referenceId||'\u2014'}</td>
                            <td style={{fontWeight:600}}>{inv.customerName||inv.customerPhone||'\u2014'}</td>
                            <td>{fmtMoney(inv.total)}</td>
                            <td><span className={`status-badge ${badgeClass(inv)}`}>{inv.status}</span></td>
                            <td>{fmtDate(inv.createdAt)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Side Panel */}
                {selInvoice && (
                  <div className="pf-side-panel">
                    <div className="pf-side-panel-header">
                      <h3>Invoice Detail</h3>
                      <button onClick={()=>setSelInvoice(null)} className="pf-close-btn">{'\u2715'}</button>
                    </div>
                    <div className={`status-badge ${badgeClass(selInvoice)}`} style={{marginBottom:12}}>{selInvoice.status}</div>
                    <div className="pf-detail-row"><span className="label">Ref</span><span className="mono">{selInvoice.referenceId||'\u2014'}</span></div>
                    <div className="pf-detail-row"><span className="label">Order</span><span>{selInvoice.orderId||'\u2014'}</span></div>
                    <div className="pf-detail-row"><span className="label">Customer</span><span>{selInvoice.customerName||'\u2014'}</span></div>
                    <div className="pf-detail-row"><span className="label">Phone</span><span>{selInvoice.customerPhone||'\u2014'}</span></div>
                    <div className="pf-detail-row"><span className="label">Brand</span><span>{selInvoice.purpose||'\u2014'}</span></div>
                    <div className="pf-section-divider">
                      <div className="pf-detail-row"><span className="label">Subtotal</span><span>{fmtMoney(selInvoice.subtotal)}</span></div>
                      <div className="pf-detail-row"><span className="label">Tax</span><span>{fmtMoney(selInvoice.tax)}</span></div>
                      <div className="pf-detail-row"><span className="label">Express</span><span>{fmtMoney(selInvoice.shipping)}</span></div>
                      <div className="pf-detail-row"><span className="label">Promo</span><span>{'\u2212'}{fmtMoney(selInvoice.discount)}</span></div>
                      {selInvoice.convenienceFee>0 && <div className="pf-detail-row"><span className="label">Conv Fee</span><span>{fmtMoney(selInvoice.convenienceFee)}</span></div>}
                      <div className="pf-detail-total"><span>Total</span><span>{fmtMoney(selInvoice.total)}</span></div>
                    </div>
                    {selInvoice.items && selInvoice.items.length>0 && (
                      <div className="pf-section-divider">
                        <div className="pf-section-title">Items</div>
                        {selInvoice.items.map((it,i)=>(
                          <div key={i} style={{display:'flex',justifyContent:'space-between',fontSize:12,marginBottom:4}}>
                            <span>{it.name} {'\u00D7'}{it.quantity}</span><span>{fmtMoney(it.amount*it.quantity)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="pf-action-stack">
                      {(selInvoice.status==='created'||selInvoice.status==='pending_payment') && (
                        <Button variant="primary" size="sm" loading={actionLoading==='send'} onClick={()=>doSendPaymentLink(selInvoice)}>
                          {selInvoice.status==='pending_payment'?'Resend Payment Link':'Send Payment Link'}
                        </Button>
                      )}
                      <Button variant="secondary" size="sm" loading={actionLoading==='img'} onClick={()=>doGenerateImage(selInvoice)}>Generate Image</Button>
                      <Button variant="secondary" size="sm" loading={actionLoading==='pdf'} onClick={()=>doGeneratePdf(selInvoice)}>Generate PDF</Button>
                      {selInvoice.status!=='paid'&&selInvoice.status!=='cancelled' && (
                        <Button variant="danger" size="sm" loading={actionLoading==='cancel'} onClick={()=>doCancelInvoice(selInvoice)}>Cancel Invoice</Button>
                      )}
                    </div>
                    {deliveryLogs.length>0 && (
                      <div className="pf-section-divider">
                        <div className="pf-section-title">Delivery Logs</div>
                        {deliveryLogs.map((log,i)=>(
                          <div key={i} className="pf-log-entry">
                            <div><strong>{log.channel}</strong> {'\u2192'} {log.toNumber}</div>
                            <div>Status: {log.status} {'\u00B7'} {new Date(log.timestamp).toLocaleString('en-IN')}</div>
                            {log.error && <div className="pf-log-error">{log.error}</div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PENDING DUES TAB */}
          {activeTab === 'dues' && (
            <div className="pf-tab-body">
              <div className="stats-grid" style={{marginBottom:16}}>
                <div className="stat-card accent"><div className="pf-stat-value">{invoices.filter(i=>i.status==='pending_payment').length}</div><div className="pf-stat-label">Pending Invoices</div></div>
                <div className="stat-card"><div className="pf-stat-value">{fmtMoney(invoices.filter(i=>i.status==='pending_payment').reduce((s,i)=>s+i.total,0))}</div><div className="pf-stat-label">Total Dues</div></div>
              </div>
              <div className="table-container">
                <table className="inner-table">
                  <thead><tr><th>#</th><th>Ref</th><th>Customer</th><th>Phone</th><th>Amount</th><th>Created</th><th>Actions</th></tr></thead>
                  <tbody>
                    {invoices.filter(i=>i.status==='pending_payment').length===0 && <tr className="empty-row"><td colSpan={7}>No pending dues</td></tr>}
                    {invoices.filter(i=>i.status==='pending_payment').map((inv,i)=>(
                      <tr key={inv.invoiceId}>
                        <td>{i+1}</td>
                        <td style={{fontFamily:'monospace',fontSize:12}}>{inv.referenceId||'\u2014'}</td>
                        <td style={{fontWeight:600}}>{inv.customerName||'\u2014'}</td>
                        <td>{inv.customerPhone||'\u2014'}</td>
                        <td>{fmtMoney(inv.total)}</td>
                        <td>{fmtDate(inv.createdAt)}</td>
                        <td><Button variant="primary" size="sm" loading={actionLoading==='send'} onClick={()=>doSendPaymentLink(inv)}>Resend</Button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* CONFIG TAB */}
          {activeTab === 'config' && (
            <div className="pf-config">
              <h3 style={{margin:'0 0 16px',fontSize:18}}>Flow Configuration</h3>
              <div className="form-group"><label>Default GST Rate (%)</label><input type="number" value={config.default_gst_rate} onChange={e=>setConfig({...config,default_gst_rate:parseFloat(e.target.value)||0})} /></div>
              <div className="form-group"><label>Default Express / Shipping ({'\u20B9'})</label><input type="number" value={config.default_shipping} onChange={e=>setConfig({...config,default_shipping:parseFloat(e.target.value)||0})} /></div>
              <div className="form-group"><label>Default Promo / Discount ({'\u20B9'})</label><input type="number" value={config.default_promo} onChange={e=>setConfig({...config,default_promo:parseFloat(e.target.value)||0})} /></div>
              <div className="form-group"><label>GSTIN</label><input type="text" value={config.gstin} onChange={e=>setConfig({...config,gstin:e.target.value})} /></div>
              <div className="form-group"><label>Default Item Name</label><input type="text" value={config.default_item_name} onChange={e=>setConfig({...config,default_item_name:e.target.value})} /></div>
              <div className="form-group">
                <label>Brands (one per line)</label>
                <textarea rows={6} value={config.purposes.join('\n')} onChange={e=>setConfig({...config,purposes:e.target.value.split('\n').filter(Boolean)})} />
              </div>
              <Button variant="primary" size="sm" loading={configSaving} onClick={()=>{setConfigSaving(true);setTimeout(()=>{setConfigSaving(false);showMsg('Config saved');},500);}}>Save Config</Button>
            </div>
          )}

          {/* REMARK / REFUND / CREDIT NOTE MODAL */}
          {remarkModal && (
            <div className="pf-modal-overlay" onClick={()=>setRemarkModal(null)}>
              <div className="pf-modal-box" onClick={e=>e.stopPropagation()}>
                <div className="pf-modal-header">
                  <h3>{remarkModal.type==='remark'?'Add Remark':remarkModal.type==='refund'?'Record Refund':'Credit Note'}</h3>
                  <Button variant="ghost" size="sm" onClick={()=>setRemarkModal(null)}>{'\u2715'}</Button>
                </div>
                <div className="pf-detail-row" style={{marginBottom:12}}>
                  <span className="label">Invoice</span>
                  <span className="mono">{remarkModal.inv.referenceId||remarkModal.inv.invoiceNumber}</span>
                </div>
                {(remarkModal.type==='refund'||remarkModal.type==='credit_note') && (
                  <div className="form-group">
                    <label>Amount ({'\u20B9'})</label>
                    <input type="number" value={remarkAmount} onChange={e=>setRemarkAmount(e.target.value)} placeholder="0" />
                  </div>
                )}
                <div className="form-group">
                  <label>{remarkModal.type==='remark'?'Note':'Reason'}</label>
                  <textarea rows={3} value={remarkText} onChange={e=>setRemarkText(e.target.value)} placeholder={remarkModal.type==='remark'?'Enter remark...':'Reason for '+remarkModal.type.replace('_',' ')+'...'} />
                </div>
                <div className="pf-modal-actions">
                  <Button variant="secondary" size="sm" onClick={()=>setRemarkModal(null)}>Cancel</Button>
                  <Button variant={remarkModal.type==='refund'?'danger':'primary'} size="sm" loading={actionLoading==='remark'} onClick={submitRemark}>
                    {remarkModal.type==='remark'?'Save Remark':remarkModal.type==='refund'?'Confirm Refund':'Issue Credit Note'}
                  </Button>
                </div>
              </div>
            </div>
          )}

        </div>
      )}
    </PageShell>
  );

  if (embedded) return shellContent;
  return <Layout user={user} onSignOut={signOut}>{shellContent}</Layout>;
};

export default PayFlowPage;
