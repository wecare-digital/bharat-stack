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

  const openEditCust = (c:Contact) => { setEditCust(c); setCustForm({name:c.name||'',phone:c.phone||'',email:c.email||'',shippingAddress:c.shippingAddress||'',billingAddress:c.billingAddress||''}); };
  const closeEditCust = () => { setEditCust(null); setCustForm(EMPTY_FORM); };
  const saveCust = async () => {
    if(!editCust) return; setCustSaving(true);
    try {
      if(editCust.id) { await api.updateContact(editCust.id, custForm); showMsg('Customer updated'); }
      else { await api.createContact(custForm); showMsg('Customer created'); }
      closeEditCust(); loadCustomers();
    } catch(e) { showMsg('Save failed','error'); }
    setCustSaving(false);
  };

  const updateItem = (idx:number, field:keyof IR, val:string) => {
    const items = [...invForm.items]; items[idx] = {...items[idx],[field]:val}; setInvForm({...invForm, items});
  };
  const addItem = () => setInvForm({...invForm, items:[...invForm.items, NEW_ITEM()]});
  const removeItem = (idx:number) => { if(invForm.items.length<=1) return; setInvForm({...invForm, items:invForm.items.filter((_,i)=>i!==idx)}); };
  const calcSubtotal = () => invForm.items.reduce((s,it) => s + (parseFloat(it.unitPrice)||0)*(parseInt(it.quantity)||0), 0);
  const calcTax = () => invForm.items.reduce((s,it) => { const line=(parseFloat(it.unitPrice)||0)*(parseInt(it.quantity)||0); return s + line*(parseFloat(it.gstRate)||0)/100; }, 0);
  const calcTotal = () => calcSubtotal() + calcTax() + (parseFloat(invForm.shipping)||0) - (parseFloat(invForm.discount)||0) + (parseFloat(invForm.greenPacking)||0) + (parseFloat(invForm.notificationFee)||0);

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
      if(r) { showMsg(`Invoice ${r.invoiceNumber} created`); setInvForm({...EMPTY_INV, items:[NEW_ITEM()]}); setSelCustomer(null); loadInvoices(); }
      else showMsg('Create failed','error');
    } catch(e) { showMsg('Create failed','error'); }
    setCreating(false);
  };

  const doSendPaymentLink = async (inv:Invoice) => {
    setActionLoading('send');
    try { const r = await api.sendPaymentLink(inv.invoiceId); if(r) { showMsg('Payment link sent'); loadInvoices(); } else showMsg('Send failed','error'); } catch(e) { showMsg('Send failed','error'); }
    setActionLoading('');
  };
  const doCancelInvoice = async (inv:Invoice) => {
    if(!confirm('Cancel this invoice?')) return; setActionLoading('cancel');
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

  const shellContent = (
    <PageShell title="Flow CRM" subtitle="Customers, Invoices & Payments" tabs={TABS} defaultTab="customers">
      {(activeTab) => (
        <div className="inner-page">
          {msg && <div className={`msg-bar ${msg.type}`} style={{margin:'0 0 16px'}}>{msg.text}<button onClick={()=>setMsg(null)} style={{background:'none',border:'none',cursor:'pointer',marginLeft:8}}>{'\u2715'}</button></div>}

          {activeTab === 'customers' && (
            <div style={{padding:20}}>
              <div style={{display:'flex',gap:12,alignItems:'center',marginBottom:16,flexWrap:'wrap'}}>
                <input className="search-input" placeholder="Search customers..." value={custSearch} onChange={e=>setCustSearch(e.target.value)} />
                <Button variant="primary" size="sm" onClick={()=>{setEditCust({} as Contact); setCustForm(EMPTY_FORM);}}>+ New Customer</Button>
                <Button variant="secondary" size="sm" icon="refresh" loading={custLoading} onClick={loadCustomers}>Refresh</Button>
              </div>
              <div className="stats-grid" style={{marginBottom:16}}>
                <div className="stat-card accent"><div style={{fontSize:24,fontWeight:700}}>{customers.length}</div><div style={{fontSize:12,color:'#6b7280'}}>Total Customers</div></div>
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
                        <td style={{maxWidth:150,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{c.shippingAddress||'\u2014'}</td>
                        <td style={{maxWidth:150,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{c.billingAddress||'\u2014'}</td>
                        <td>{fmtDate(new Date(c.updatedAt||c.createdAt||'').getTime())}</td>
                        <td><Button variant="ghost" size="sm" onClick={()=>openEditCust(c)}>Edit</Button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {editCust && (
                <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.4)',zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center'}} onClick={closeEditCust}>
                  <div style={{background:'#fff',borderRadius:16,padding:24,width:'90%',maxWidth:480,maxHeight:'90vh',overflowY:'auto',boxShadow:'0 20px 60px rgba(0,0,0,0.2)'}} onClick={e=>e.stopPropagation()}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
                      <h3 style={{margin:0}}>{editCust.id ? 'Edit Customer' : 'New Customer'}</h3>
                      <Button variant="ghost" size="sm" onClick={closeEditCust}>{'\u2715'}</Button>
                    </div>
                    <div className="form-group"><label>Name</label><input type="text" value={custForm.name} onChange={e=>setCustForm({...custForm,name:e.target.value})} /></div>
                    <div className="form-group"><label>Phone</label><input type="tel" value={custForm.phone} onChange={e=>setCustForm({...custForm,phone:e.target.value})} /></div>
                    <div className="form-group"><label>Email</label><input type="email" value={custForm.email} onChange={e=>setCustForm({...custForm,email:e.target.value})} /></div>
                    <div className="form-group"><label>Shipping Address</label><textarea value={custForm.shippingAddress} onChange={e=>setCustForm({...custForm,shippingAddress:e.target.value})} /></div>
                    <div className="form-group"><label>Billing Address</label><textarea value={custForm.billingAddress} onChange={e=>setCustForm({...custForm,billingAddress:e.target.value})} /></div>
                    <div style={{display:'flex',gap:8,justifyContent:'flex-end'}}>
                      <Button variant="secondary" size="sm" onClick={closeEditCust}>Cancel</Button>
                      <Button variant="primary" size="sm" loading={custSaving} onClick={saveCust}>Save</Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'create' && (
            <div style={{padding:20}}>
              {!selCustomer ? (
                <div>
                  <h3 style={{margin:'0 0 12px',fontSize:18}}>Step 1 &mdash; Select Customer</h3>
                  <input className="search-input" placeholder="Search..." value={custSearch} onChange={e=>setCustSearch(e.target.value)} style={{marginBottom:16,maxWidth:400}} />
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))',gap:12}}>
                    {filteredCust.map(c=>(
                      <div key={c.id} onClick={()=>setSelCustomer(c)} style={{display:'flex',alignItems:'center',gap:12,padding:'12px 16px',background:'#fff',border:'1.5px solid #e5e7eb',borderRadius:12,cursor:'pointer',transition:'all 0.15s'}}>
                        <div style={{width:40,height:40,borderRadius:'50%',background:'#059669',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:700,fontSize:16,flexShrink:0}}>{(c.name||'?')[0].toUpperCase()}</div>
                        <div style={{flex:1,minWidth:0}}>
                          <div style={{fontWeight:600,fontSize:14,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{c.name||'Unknown'}</div>
                          <div style={{fontSize:12,color:'#6b7280'}}>{c.phone||'\u2014'}</div>
                        </div>
                      </div>
                    ))}
                    {filteredCust.length===0 && <div style={{color:'#9ca3af',padding:20}}>No customers. Create one in the Customers tab.</div>}
                  </div>
                </div>
              ) : (
                <div>
                  <div className="info-banner" style={{marginBottom:16}}>
                    <div style={{flex:1}}><strong>{selCustomer.name}</strong> &mdash; {selCustomer.phone} {selCustomer.email ? ` · ${selCustomer.email}` : ''}</div>
                    <Button variant="ghost" size="sm" onClick={()=>setSelCustomer(null)}>Change</Button>
                  </div>
                  <h3 style={{margin:'0 0 12px',fontSize:18}}>Step 2 &mdash; Invoice Details</h3>
                  <div className="table-container" style={{marginBottom:16}}>
                    <table className="inner-table">
                      <thead><tr><th>#</th><th>Item Name</th><th>Price (&rupee;)</th><th>Qty</th><th>GST %</th><th>Line Total</th><th></th></tr></thead>
                      <tbody>
                        {invForm.items.map((it,i)=>{
                          const line = (parseFloat(it.unitPrice)||0)*(parseInt(it.quantity)||0);
                          const gst = line*(parseFloat(it.gstRate)||0)/100;
                          return (
                            <tr key={i}>
                              <td>{i+1}</td>
                              <td><input type="text" value={it.name} onChange={e=>updateItem(i,'name',e.target.value)} placeholder={config.default_item_name} style={{width:'100%',border:'none',background:'transparent',fontSize:13}} /></td>
                              <td><input type="number" value={it.unitPrice} onChange={e=>updateItem(i,'unitPrice',e.target.value)} style={{width:80,border:'1px solid #e5e7eb',borderRadius:8,padding:'4px 8px',fontSize:13}} /></td>
                              <td><input type="number" value={it.quantity} onChange={e=>updateItem(i,'quantity',e.target.value)} style={{width:50,border:'1px solid #e5e7eb',borderRadius:8,padding:'4px 8px',fontSize:13}} /></td>
                              <td><input type="number" value={it.gstRate} onChange={e=>updateItem(i,'gstRate',e.target.value)} style={{width:50,border:'1px solid #e5e7eb',borderRadius:8,padding:'4px 8px',fontSize:13}} /></td>
                              <td style={{fontWeight:600}}>{fmtMoney(line+gst)}</td>
                              <td>{invForm.items.length>1 && <button onClick={()=>removeItem(i)} style={{background:'none',border:'none',color:'#ef4444',cursor:'pointer',fontSize:16}}>{'\u2715'}</button>}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <Button variant="secondary" size="sm" onClick={addItem} style={{marginBottom:20}}>+ Add Item</Button>
                  <h4 style={{margin:'0 0 8px',fontSize:15}}>Additional Charges</h4>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:16,maxWidth:500}}>
                    <div className="form-group"><label>Express / Shipping ({'\u20B9'})</label><input type="number" value={invForm.shipping} onChange={e=>setInvForm({...invForm,shipping:e.target.value})} /></div>
                    <div className="form-group"><label>Promo / Discount ({'\u20B9'})</label><input type="number" value={invForm.discount} onChange={e=>setInvForm({...invForm,discount:e.target.value})} /></div>
                    <div className="form-group"><label>Green Packing ({'\u20B9'})</label><input type="number" value={invForm.greenPacking} onChange={e=>setInvForm({...invForm,greenPacking:e.target.value})} placeholder="0" /></div>
                    <div className="form-group"><label>Notification / Alert Fee ({'\u20B9'})</label><input type="number" value={invForm.notificationFee} onChange={e=>setInvForm({...invForm,notificationFee:e.target.value})} placeholder="0" /></div>
                  </div>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:16,maxWidth:500}}>
                    <div className="form-group">
                      <label>Brand</label>
                      <select value={invForm.purpose} onChange={e=>setInvForm({...invForm,purpose:e.target.value})}>
                        <option value="">&mdash; Select &mdash;</option>
                        {config.purposes.map(p=><option key={p} value={p}>{p}</option>)}
                      </select>
                    </div>
                    <div className="form-group"><label>Order ID</label><input type="text" value={invForm.orderId} onChange={e=>setInvForm({...invForm,orderId:e.target.value})} placeholder="Optional" /></div>
                  </div>
                  <div className="inner-card" style={{marginBottom:20,maxWidth:500}}>
                    <h4 style={{margin:'0 0 8px',fontSize:14}}>Preview</h4>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13}}><span>Subtotal</span><span>{fmtMoney(calcSubtotal())}</span></div>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13}}><span>Tax (GST)</span><span>{fmtMoney(calcTax())}</span></div>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13}}><span>Express</span><span>{fmtMoney(parseFloat(invForm.shipping)||0)}</span></div>
                    {(parseFloat(invForm.greenPacking)||0)>0 && <div style={{display:'flex',justifyContent:'space-between',fontSize:13}}><span>Green Packing</span><span>{fmtMoney(parseFloat(invForm.greenPacking)||0)}</span></div>}
                    {(parseFloat(invForm.notificationFee)||0)>0 && <div style={{display:'flex',justifyContent:'space-between',fontSize:13}}><span>Notification Fee</span><span>{fmtMoney(parseFloat(invForm.notificationFee)||0)}</span></div>}
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13}}><span>Promo</span><span>&minus;{fmtMoney(parseFloat(invForm.discount)||0)}</span></div>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:15,fontWeight:700,borderTop:'1px solid #e5e7eb',paddingTop:8,marginTop:8}}><span>Total</span><span>{fmtMoney(calcTotal())}</span></div>
                  </div>
                  <Button variant="primary" size="md" loading={creating} onClick={submitInvoice}>Create Invoice</Button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'invoices' && (
            <div style={{padding:20}}>
              <div style={{display:'flex',gap:8,marginBottom:16,flexWrap:'wrap'}}>
                {STATUS_FILTERS.map(f=>(
                  <button key={f.id} className={`btn btn-sm ${statusFilter===f.id?'btn-primary':'btn-secondary'}`} onClick={()=>setStatusFilter(f.id)}>{f.label}</button>
                ))}
                <div style={{flex:1}} />
                <Button variant="secondary" size="sm" icon="refresh" loading={invLoading} onClick={loadInvoices}>Refresh</Button>
              </div>
              <div className="stats-grid" style={{marginBottom:16}}>
                <div className="stat-card accent"><div style={{fontSize:24,fontWeight:700}}>{invStats.total}</div><div style={{fontSize:12,color:'#6b7280'}}>Total</div></div>
                <div className="stat-card"><div style={{fontSize:24,fontWeight:700}}>{invStats.paid}</div><div style={{fontSize:12,color:'#6b7280'}}>Paid</div></div>
                <div className="stat-card"><div style={{fontSize:24,fontWeight:700}}>{invStats.pending}</div><div style={{fontSize:12,color:'#6b7280'}}>Pending</div></div>
                <div className="stat-card"><div style={{fontSize:24,fontWeight:700}}>{fmtMoney(invStats.totalAmt)}</div><div style={{fontSize:12,color:'#6b7280'}}>Total Value</div></div>
              </div>
              <div style={{display:'flex',gap:16}}>
                <div style={{flex:1,minWidth:0}}>
                  <div className="table-container">
                    <table className="inner-table">
                      <thead><tr><th>#</th><th>Ref</th><th>Customer</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
                      <tbody>
                        {invoices.length===0 && <tr className="empty-row"><td colSpan={6}>No invoices</td></tr>}
                        {invoices.map((inv,i)=>(
                          <tr key={inv.invoiceId} onClick={()=>selectInvoice(inv)} style={{cursor:'pointer',background:selInvoice?.invoiceId===inv.invoiceId?'#ECFDF5':undefined}}>
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
                {selInvoice && (
                  <div style={{width:340,flexShrink:0,background:'#fff',border:'1px solid #e5e7eb',borderRadius:16,padding:20,position:'sticky',top:0,maxHeight:'calc(100vh - 200px)',overflowY:'auto'}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
                      <h3 style={{margin:0,fontSize:16}}>Invoice Detail</h3>
                      <button onClick={()=>setSelInvoice(null)} style={{background:'none',border:'none',cursor:'pointer',fontSize:18}}>{'\u2715'}</button>
                    </div>
                    <div className={`status-badge ${badgeClass(selInvoice)}`} style={{marginBottom:12}}>{selInvoice.status}</div>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Ref</span><span style={{fontFamily:'monospace'}}>{selInvoice.referenceId||'\u2014'}</span></div>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Order</span><span>{selInvoice.orderId||'\u2014'}</span></div>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Customer</span><span>{selInvoice.customerName||'\u2014'}</span></div>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Phone</span><span>{selInvoice.customerPhone||'\u2014'}</span></div>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Brand</span><span>{selInvoice.purpose||'\u2014'}</span></div>
                    <div style={{borderTop:'1px solid #e5e7eb',margin:'12px 0',paddingTop:12}}>
                      <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Subtotal</span><span>{fmtMoney(selInvoice.subtotal)}</span></div>
                      <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Tax</span><span>{fmtMoney(selInvoice.tax)}</span></div>
                      <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Express</span><span>{fmtMoney(selInvoice.shipping)}</span></div>
                      <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Promo</span><span>&minus;{fmtMoney(selInvoice.discount)}</span></div>
                      {selInvoice.convenienceFee>0 && <div style={{display:'flex',justifyContent:'space-between',fontSize:13,marginBottom:6}}><span style={{color:'#6b7280'}}>Conv Fee</span><span>{fmtMoney(selInvoice.convenienceFee)}</span></div>}
                      <div style={{display:'flex',justifyContent:'space-between',fontSize:15,fontWeight:700}}><span>Total</span><span>{fmtMoney(selInvoice.total)}</span></div>
                    </div>
                    {selInvoice.items && selInvoice.items.length>0 && (
                      <div style={{borderTop:'1px solid #e5e7eb',margin:'12px 0',paddingTop:12}}>
                        <div style={{fontSize:13,fontWeight:600,marginBottom:8}}>Items</div>
                        {selInvoice.items.map((it,i)=>(
                          <div key={i} style={{display:'flex',justifyContent:'space-between',fontSize:12,marginBottom:4}}>
                            <span>{it.name} &times;{it.quantity}</span><span>{fmtMoney(it.amount*it.quantity)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div style={{display:'flex',flexDirection:'column',gap:8,marginTop:12}}>
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
                      <div style={{borderTop:'1px solid #e5e7eb',margin:'12px 0',paddingTop:12}}>
                        <div style={{fontSize:13,fontWeight:600,marginBottom:8}}>Delivery Logs</div>
                        {deliveryLogs.map((log,i)=>(
                          <div key={i} style={{fontSize:11,marginBottom:6,padding:'6px 8px',background:'#f9fafb',borderRadius:8}}>
                            <div><strong>{log.channel}</strong> &rarr; {log.toNumber}</div>
                            <div>Status: {log.status} &middot; {new Date(log.timestamp).toLocaleString('en-IN')}</div>
                            {log.error && <div style={{color:'#ef4444'}}>{log.error}</div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'dues' && (
            <div style={{padding:20}}>
              <div className="stats-grid" style={{marginBottom:16}}>
                <div className="stat-card accent"><div style={{fontSize:24,fontWeight:700}}>{invoices.filter(i=>i.status==='pending_payment').length}</div><div style={{fontSize:12,color:'#6b7280'}}>Pending Invoices</div></div>
                <div className="stat-card"><div style={{fontSize:24,fontWeight:700}}>{fmtMoney(invoices.filter(i=>i.status==='pending_payment').reduce((s,i)=>s+i.total,0))}</div><div style={{fontSize:12,color:'#6b7280'}}>Total Dues</div></div>
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

          {activeTab === 'config' && (
            <div style={{padding:20,maxWidth:600}}>
              <h3 style={{margin:'0 0 16px',fontSize:18}}>Flow Configuration</h3>
              <div className="form-group"><label>Default GST Rate (%)</label><input type="number" value={config.default_gst_rate} onChange={e=>setConfig({...config,default_gst_rate:parseFloat(e.target.value)||0})} /></div>
              <div className="form-group"><label>Default Express / Shipping</label><input type="number" value={config.default_shipping} onChange={e=>setConfig({...config,default_shipping:parseFloat(e.target.value)||0})} /></div>
              <div className="form-group"><label>Default Promo / Discount</label><input type="number" value={config.default_promo} onChange={e=>setConfig({...config,default_promo:parseFloat(e.target.value)||0})} /></div>
              <div className="form-group"><label>GSTIN</label><input type="text" value={config.gstin} onChange={e=>setConfig({...config,gstin:e.target.value})} /></div>
              <div className="form-group"><label>Default Item Name</label><input type="text" value={config.default_item_name} onChange={e=>setConfig({...config,default_item_name:e.target.value})} /></div>
              <div className="form-group">
                <label>Brands (one per line)</label>
                <textarea rows={6} value={config.purposes.join('\n')} onChange={e=>setConfig({...config,purposes:e.target.value.split('\n').filter(Boolean)})} />
              </div>
              <Button variant="primary" size="sm" loading={configSaving} onClick={()=>{setConfigSaving(true);setTimeout(()=>{setConfigSaving(false);showMsg('Config saved');},500);}}>Save Config</Button>
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
