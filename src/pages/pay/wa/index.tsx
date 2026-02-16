/**
 * Pay WA - WhatsApp Interactive Payment Page
 * 
 * Message Structure:
 * BODY TEXT: Your payment is overdue—please tap below to complete it 💳🤝
 * 
 * CART ITEMS:
 * - Name: (user input)
 * - Amount: ₹(user input)
 * - Quantity: (user input)
 * - Convenience Fee (Collected by Bank): ₹(auto-calculated by backend: 2% + 18% GST)
 * 
 * BREAKDOWN:
 * - Subtotal: ₹(auto from items)
 * - Promo: ₹(user input)
 * - Express: ₹(user input)
 * - Tax: ₹(GST auto-calculated based on rate selected) | "GSTIN: 19AADFW7431N1ZK"
 * 
 * TOTAL: ₹(auto-calculated by WhatsApp)
 * 
 * All fields mandatory (show even if 0)
 * 
 * Status Messages:
 * 1. Payment Request: Your payment is overdue—please tap below to complete it 💳🤝
 * 2. Payment Success (Captured): Payment of ₹{amount} received successfully! Thank you ✅
 * 3. Payment Failed: Payment failed. Please try again ❌
 */

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import Button from '../../../components/ui/Button';
import * as api from '../../../api/client';
import { formatReferenceNumber, generateReferenceId } from '../../../lib/formatters';
import { PAYMENT_CONFIG, GST_RATES, CONVENIENCE_FEE, DEFAULT_GSTIN, WHATSAPP_PHONES, PAYMENT_PHONES, PAYMENT_DETAILS, PAYMENT_UNLOCK_PASSWORD } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
}

interface Contact {
  id: string;
  contactId: string;
  name: string;
  phone: string;
  email?: string;
  shippingAddress?: string;
  billingAddress?: string;
}

const PayWAPage: React.FC<PageProps> = ({ signOut, user, embedded }) => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedContact, setSelectedContact] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form state - multi-item with per-item GST
  const [referenceId, setReferenceId] = useState('');
  const [items, setItems] = useState<{ name: string; amount: number; quantity: number; gstRate: number }[]>([{ name: '', amount: 0, quantity: 1, gstRate: 0 }]);
  const [discount, setDiscount] = useState<number>(0);
  const [shipping, setShipping] = useState<number>(0);
  const [gstin, setGstin] = useState<string>(DEFAULT_GSTIN);
  const [orderId, setOrderId] = useState<string>('');
  const [selectedPhone, setSelectedPhone] = useState<string>(PAYMENT_CONFIG.phoneNumberId);
  const [phone2Unlocked, setPhone2Unlocked] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [passwordError, setPasswordError] = useState('');
  // Get payment config name for the selected phone (each WABA has its own config name)
  const getPaymentConfigName = () => {
    const phone = PAYMENT_PHONES.find(p => p.id === selectedPhone);
    return phone?.paymentConfigName || 'WECARE-DIGITAL';
  };
  const selectedPhoneConfig = PAYMENT_PHONES.find(p => p.id === selectedPhone);
  const isPhoneLocked = selectedPhoneConfig?.paymentProtected && !phone2Unlocked;

  const handlePhoneChange = (phoneId: string) => {
    setSelectedPhone(phoneId);
    setPasswordError('');
    setPasswordInput('');
  };

  const handleUnlockPhone = () => {
    if (passwordInput === PAYMENT_UNLOCK_PASSWORD) {
      setPhone2Unlocked(true);
      setPasswordError('');
      setPasswordInput('');
    } else {
      setPasswordError('Incorrect password');
    }
  };

  useEffect(() => {
    loadContacts();
    setReferenceId(generateReferenceId());
  }, []);

  const loadContacts = async () => {
    setLoading(true);
    try {
      const data = await api.listContacts();
      const indianContacts = data.filter(c => c.phone?.startsWith('+91')).map(c => ({
        id: c.id,
        contactId: c.contactId,
        name: c.name,
        phone: c.phone,
        email: c.email,
        shippingAddress: c.shippingAddress,
        billingAddress: c.billingAddress,
      }));
      setContacts(indianContacts);
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to load contacts' });
    } finally {
      setLoading(false);
    }
  };

  const calculateConvenienceFee = () => {
    const itemTotal = items.reduce((s, i) => s + i.amount * i.quantity, 0);
    const feeBase = itemTotal * (CONVENIENCE_FEE.percent / 100);
    const feeGst = feeBase * (CONVENIENCE_FEE.gstPercent / 100);
    return feeBase + feeGst;
  };

  const calculateItemTotal = () => items.reduce((s, i) => s + i.amount * i.quantity, 0);
  const calculateTax = () => items.reduce((s, i) => s + i.amount * i.quantity * i.gstRate / 100, 0);
  const calculateSubtotal = () => calculateItemTotal();
  const calculateTotal = () => calculateSubtotal() + calculateConvenienceFee() - discount + shipping + calculateTax();

  const handleGenerateReferenceId = () => {
    setReferenceId(generateReferenceId());
  };

  const sendPaymentRequest = async () => {
    if (!selectedContact) { setMessage({ type: 'error', text: 'Please select a contact' }); return; }
    if (!referenceId) { setMessage({ type: 'error', text: 'Please generate a Reference ID' }); return; }
    const validItems = items.filter(i => i.name.trim() && i.amount > 0);
    if (validItems.length === 0) { setMessage({ type: 'error', text: 'At least one item with name and amount required' }); return; }

    // Mandatory field enforcement for invoice readiness
    const contact = contacts.find(c => c.contactId === selectedContact);
    if (contact) {
      const missing: string[] = [];
      if (!contact.email) missing.push('email');
      if (!contact.shippingAddress) missing.push('shipping address');
      if (!contact.billingAddress) missing.push('billing address');
      if (missing.length > 0) {
        setMessage({ type: 'error', text: `Contact missing: ${missing.join(', ')}. Update at /contacts first.` });
        return;
      }
    }

    setSending(true);
    setMessage(null);

    try {
      const totalTaxPaise = validItems.reduce((s, i) => s + Math.round(i.amount * 100 * i.quantity * i.gstRate / 100), 0);
      const result = await api.sendWhatsAppPaymentMessage({
        contactId: selectedContact,
        phoneNumberId: selectedPhone,
        referenceId: referenceId,
        items: validItems.map((i, idx) => ({ name: i.name, amount: Math.round(i.amount * 100), quantity: i.quantity, gstRate: i.gstRate, productId: `ITEM_${idx + 1}` })),
        discount: Math.round(discount * 100),
        delivery: Math.round(shipping * 100),
        tax: totalTaxPaise,
        gstin: gstin,
        orderId: orderId || 'Offline',
        useInteractive: true,
        paymentConfiguration: getPaymentConfigName(),
      });

      if (result) {
        setMessage({ type: 'success', text: `Payment request sent! ID: ${result.messageId}` });
        setReferenceId(generateReferenceId());
        setItems([{ name: '', amount: 0, quantity: 1, gstRate: 0 }]);
        setDiscount(0);
        setShipping(0);
        setOrderId('');
      } else {
        const connStatus = api.getConnectionStatus();
        setMessage({ type: 'error', text: `Failed: ${connStatus.lastError || 'Unknown error'}` });
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to send' });
    } finally {
      setSending(false);
    }
  };

  const selectedContactInfo = contacts.find(c => c.contactId === selectedContact);

  const content = (
    <>
      <div className="pay-page">
        <PageHeader 
          title="WhatsApp Pay" 
          subtitle="Send payment requests via WhatsApp UPI (India only)"
          icon="whatsapp"
        />

        <div className="sender-notice">
          <div className="sender-icon">Phone</div>
          <div className="sender-info">
            <div className="sender-label">Sending From</div>
            <select value={selectedPhone} onChange={e => handlePhoneChange(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '13px', marginBottom: '4px' }}>
              {PAYMENT_PHONES.map(p => (
                <option key={p.id} value={p.id}>{p.display} ({p.name}){p.paymentProtected ? ' (Protected)' : ''}</option>
              ))}
            </select>
            {isPhoneLocked && (
              <div style={{ marginTop: '6px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                <input
                  type="password"
                  value={passwordInput}
                  onChange={e => { setPasswordInput(e.target.value); setPasswordError(''); }}
                  onKeyDown={e => e.key === 'Enter' && handleUnlockPhone()}
                  placeholder="Enter password to unlock"
                  style={{ padding: '5px 10px', borderRadius: '8px', border: passwordError ? '1.5px solid #059669' : '1.5px solid #e5e7eb', fontSize: '12px', flex: 1 }}
                />
                <button onClick={handleUnlockPhone} style={{ padding: '5px 12px', borderRadius: '8px', background: '#10B981', color: '#fff', border: 'none', fontSize: '12px', cursor: 'pointer' }}>Unlock</button>
              </div>
            )}
            {isPhoneLocked && passwordError && (
              <div style={{ color: '#059669', fontSize: '11px', marginTop: '4px' }}>{passwordError}</div>
            )}
            {selectedPhoneConfig?.paymentProtected && phone2Unlocked && (
              <div style={{ color: '#10B981', fontSize: '11px', marginTop: '4px' }}>Unlocked for this session</div>
            )}
            <div style={{ marginTop: '6px', fontSize: '12px', color: '#4a4a4a' }}>
              Razorpay Gateway (UPI + Cards + Netbanking)
            </div>
          </div>
          <div className="sender-badge"><span className="badge-dot"></span>Razorpay</div>
        </div>

        {/* Payment Config Info */}
        <div style={{ background: '#f9fafb', padding: 12, borderRadius: 10, marginBottom: 16, fontSize: 12, color: '#4a4a4a', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
          <div>MID: <span style={{ color: '#111', fontFamily: 'monospace' }}>{PAYMENT_DETAILS.razorpayMID}</span></div>
          <div>UPI: <span style={{ color: '#111', fontFamily: 'monospace' }}>{PAYMENT_DETAILS.upiId}</span></div>
          <div>MCC: {PAYMENT_DETAILS.mcc} | Purpose: {PAYMENT_DETAILS.purposeCode}</div>
          <div>Config: <span style={{ fontFamily: 'monospace' }}>{getPaymentConfigName()}</span></div>
        </div>

        {message && (
          <div className={`message-bar ${message.type}`}>
            {message.text}
            <button onClick={() => setMessage(null)}>×</button>
          </div>
        )}

        <div className="pay-layout">
          <div className="order-form">
            <div className="form-section">
              <h3>Recipient *</h3>
              <select value={selectedContact} onChange={(e) => setSelectedContact(e.target.value)} disabled={loading}>
                <option value="">Select contact (+91 only)</option>
                {contacts.map(c => <option key={c.contactId} value={c.contactId}>{c.name || c.phone} - {c.phone}</option>)}
              </select>
              {selectedContactInfo && (() => {
                const m: string[] = [];
                if (!selectedContactInfo.email) m.push('email');
                if (!selectedContactInfo.shippingAddress) m.push('shipping address');
                if (!selectedContactInfo.billingAddress) m.push('billing address');
                return m.length > 0 ? (
                  <div style={{ marginTop: 6, padding: '8px 12px', background: '#fef3c7', border: '1px solid #fde68a', borderRadius: 8, fontSize: 12, color: '#92400e' }}>
                    Missing: {m.join(', ')}. <a href="/contacts" style={{ color: '#059669', textDecoration: 'underline' }}>Update contact</a> before sending payment.
                  </div>
                ) : null;
              })()}
            </div>

            <div className="form-section">
              <h3>Reference ID</h3>
              <div className="ref-row">
                <input type="text" value={formatReferenceNumber(referenceId)} readOnly placeholder="WDSRXXXXXXXX" />
                <Button variant="secondary" size="sm" onClick={handleGenerateReferenceId}>New</Button>
              </div>
            </div>

            <div className="form-section">
              <h3>Order ID</h3>
              <input type="text" value={orderId} onChange={(e) => setOrderId(e.target.value)} placeholder="Blank = Offline" />
            </div>

            <div className="form-section">
              <h3>Item Details *</h3>
              {items.map((item, idx) => (
                <div key={idx} className="item-row" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 60px 90px 30px', gap: 8, marginBottom: 8, alignItems: 'end' }}>
                  <div className="item-field"><label>{idx === 0 ? 'Item *' : `Item ${idx+1} *`}</label><input type="text" value={item.name} onChange={(e) => { const n = [...items]; n[idx] = {...n[idx], name: e.target.value}; setItems(n); }} placeholder="Service Fee" /></div>
                  <div className="item-field"><label>₹ *</label><input type="number" value={item.amount || ''} onChange={(e) => { const n = [...items]; n[idx] = {...n[idx], amount: parseFloat(e.target.value) || 0}; setItems(n); }} placeholder="0" min="0" step="0.01" /></div>
                  <div className="item-field"><label>Qty</label><input type="number" value={item.quantity} onChange={(e) => { const n = [...items]; n[idx] = {...n[idx], quantity: parseInt(e.target.value) || 1}; setItems(n); }} min="1" /></div>
                  <div className="item-field"><label>GST%</label><select value={item.gstRate} onChange={(e) => { const n = [...items]; n[idx] = {...n[idx], gstRate: parseInt(e.target.value)}; setItems(n); }}>{GST_RATES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}</select></div>
                  <div style={{ paddingBottom: 2 }}>
                    {items.length > 1 && <button type="button" onClick={() => setItems(items.filter((_, i) => i !== idx))} style={{ background: 'none', border: 'none', color: '#059669', fontSize: 18, cursor: 'pointer', padding: 0 }} title="Remove">×</button>}
                  </div>
                </div>
              ))}
              <button type="button" onClick={() => setItems([...items, { name: '', amount: 0, quantity: 1, gstRate: 0 }])} style={{ padding: '4px 12px', borderRadius: 8, background: '#ECFDF5', color: '#059669', border: '1px solid #A7F3D0', fontSize: 12, cursor: 'pointer', marginTop: 4 }}>+ Add Item</button>
            </div>

            <div className="form-section">
              <h3>Breakdown</h3>
              <div className="breakdown-grid">
                <div className="breakdown-field"><label>Promo (₹)</label><input type="number" value={discount || ''} onChange={(e) => setDiscount(parseFloat(e.target.value) || 0)} placeholder="0" min="0" step="0.01" /></div>
                <div className="breakdown-field"><label>Express / Shipping (₹)</label><input type="number" value={shipping || ''} onChange={(e) => setShipping(parseFloat(e.target.value) || 0)} placeholder="0" min="0" step="0.01" /></div>
                <div className="breakdown-field"><label>GSTIN</label><input type="text" value={gstin} onChange={(e) => setGstin(e.target.value)} placeholder="19AADFW7431N1ZK" /></div>
              </div>
            </div>

            {/* Live Calculation Summary */}
            <div className="form-section" style={{ background: '#ECFDF5', padding: 14, borderRadius: 13, border: '1px solid #A7F3D0' }}>
              <h3 style={{ margin: '0 0 8px 0', fontSize: 13 }}>Calculation Summary</h3>
              {items.filter(i => i.name.trim() && i.amount > 0).map((item, idx) => {
                const lineTotal = item.amount * item.quantity;
                const lineTax = lineTotal * item.gstRate / 100;
                return (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '2px 0' }}>
                    <span>{item.name} (×{item.quantity}) @ {item.gstRate}% GST</span>
                    <span>₹{lineTotal.toFixed(2)} + ₹{lineTax.toFixed(2)} tax</span>
                  </div>
                );
              })}
              <div style={{ borderTop: '1px dashed #059669', marginTop: 6, paddingTop: 6, fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
                <span>Conv. Fee (2% + 18% GST)</span><span>₹{calculateConvenienceFee().toFixed(2)}</span>
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 6, display: 'flex', justifyContent: 'space-between' }}>
                <span>Total</span><span>₹{calculateTotal().toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="order-preview">
            <h3>Preview</h3>
            <div className="preview-card">
              <div className="preview-header"><span className="wa-icon">WA</span><span>Interactive Payment</span></div>
              <div className="preview-body">Your payment is overdue - please tap below to complete it</div>
              <div className="preview-section">
                <div className="section-title">CART ITEMS</div>
                {items.filter(i => i.name.trim()).map((item, idx) => (
                  <div key={idx} className="cart-item"><span>{item.name}</span><span>₹{item.amount.toFixed(2)} × {item.quantity} = ₹{(item.amount * item.quantity).toFixed(2)}</span></div>
                ))}
                {items.filter(i => i.name.trim()).length === 0 && <div className="cart-item"><span>—</span><span>₹0.00</span></div>}
                <div className="cart-item conv-fee"><span>Conv. Fee (Bank)</span><span>₹{calculateConvenienceFee().toFixed(2)}</span></div>
              </div>
              <div className="preview-section">
                <div className="section-title">BREAKDOWN</div>
                <div className="breakdown-row"><span>Subtotal</span><span>₹{calculateSubtotal().toFixed(2)}</span></div>
                <div className="breakdown-row"><span>Promo</span><span>-₹{discount.toFixed(2)}</span></div>
                <div className="breakdown-row"><span>Shipping</span><span>₹{shipping.toFixed(2)}</span></div>
                <div className="breakdown-row"><span>Tax (GST)</span><span>₹{calculateTax().toFixed(2)}</span></div>
              </div>
              <div className="preview-total"><span>TOTAL</span><span>₹{calculateTotal().toFixed(2)}</span></div>
              <div className="preview-config">
                <small>To: {selectedContactInfo?.name || '—'}</small>
                <small>Ref: {formatReferenceNumber(referenceId)}</small>
                <small>Order: {orderId || 'Offline'}</small>
              </div>
            </div>
            <Button variant="primary" className="send-btn" onClick={sendPaymentRequest} disabled={sending || !selectedContact || items.filter(i => i.name.trim() && i.amount > 0).length === 0 || isPhoneLocked} loading={sending}>
              {isPhoneLocked ? 'Unlock phone to send' : sending ? 'Sending...' : 'Send Payment'}
            </Button>
          </div>
        </div>
      </div>

      <style jsx>{`
        .pay-page { padding: 20px; max-width: 1100px; margin: 0 auto; }
        .pay-header { margin-bottom: 20px; }
        .pay-header h1 { font-size: 22px; margin: 0 0 4px 0; }
        .pay-header p { color: #4a4a4a; margin: 0; font-size: 14px; }
        .sender-notice { display: flex; align-items: center; gap: 16px; background: #ECFDF5; padding: 12px 16px; border-radius: 13px; margin-bottom: 16px; border: 1.5px solid #10B981; }
        .sender-icon { font-size: 14px; font-weight: 600; color: #10B981; }
        .sender-info { flex: 1; }
        .sender-label { font-size: 10px; color: #4a4a4a; text-transform: uppercase; }
        .sender-number { font-size: 16px; font-weight: 600; color: #111827; }
        .sender-name { font-size: 12px; color: #4a4a4a; }
        .sender-badge { display: flex; align-items: center; gap: 4px; background: #10B981; color: #fff; padding: 4px 10px; border-radius: 16px; font-size: 11px; }
        .badge-dot { width: 6px; height: 6px; background: #fff; border-radius: 50%; }
        .message-bar { padding: 10px 14px; border-radius: 13px; margin-bottom: 12px; display: flex; justify-content: space-between; font-size: 13px; border: 1.5px solid #10B981; }
        .message-bar.success { background: #ECFDF5; color: #111827; }
        .message-bar.error { background: #ECFDF5; color: #059669; border-color: #059669; }
        .message-bar button { background: none; border: none; font-size: 16px; cursor: pointer; }
        .pay-layout { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
        .order-form { background: #fff; border-radius: 13px; padding: 20px; border: 1px solid #e5e5e5; }
        .form-section { margin-bottom: 20px; }
        .form-section h3 { font-size: 14px; margin: 0 0 10px 0; color: #000; font-weight: 600; }
        .form-section select, .form-section input { width: 100%; padding: 10px 12px; border: 1.5px solid #10B981; border-radius: 13px; font-size: 14px; box-sizing: border-box; background: #fff; }
        .form-section select:hover, .form-section input:hover { background: #ECFDF5; }
        .form-section select:focus, .form-section input:focus { outline: none; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.3); background: #fff; }
        .ref-row { display: flex; gap: 8px; }
        .ref-row input { flex: 1; background: #f5f5f5; }
        .item-grid { display: grid; grid-template-columns: 2fr 1fr 60px; gap: 10px; }
        .item-field label { display: block; font-size: 12px; color: #4a4a4a; margin-bottom: 4px; }
        .breakdown-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .breakdown-field label { display: block; font-size: 12px; color: #4a4a4a; margin-bottom: 4px; }
        .breakdown-field.full-width { grid-column: span 2; }
        .order-preview h3 { font-size: 14px; margin: 0 0 10px 0; font-weight: 600; }
        .preview-card { background: #fff; border-radius: 13px; padding: 16px; margin-bottom: 12px; border: 1.5px solid #10B981; }
        .preview-header { display: flex; align-items: center; gap: 6px; padding-bottom: 10px; border-bottom: 1px solid #e5e5e5; margin-bottom: 10px; font-weight: 600; font-size: 14px; }
        .wa-icon { font-size: 12px; background: #10B981; color: #fff; padding: 2px 6px; border-radius: 4px; }
        .preview-body { background: #ECFDF5; padding: 10px; border-radius: 10px; font-size: 13px; margin-bottom: 12px; color: #111827; }
        .preview-section { margin-bottom: 12px; padding: 10px; background: #f5f5f5; border-radius: 10px; }
        .section-title { font-size: 10px; color: #4a4a4a; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; }
        .cart-item { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }
        .cart-item.conv-fee { color: #4a4a4a; font-style: italic; }
        .breakdown-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 13px; }
        .preview-total { display: flex; justify-content: space-between; padding: 10px; background: #10B981; color: #fff; border-radius: 10px; font-size: 16px; font-weight: 600; }
        .preview-config { display: flex; flex-direction: column; gap: 2px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #e5e5e5; }
        .preview-config small { color: #4a4a4a; font-size: 11px; }
        .send-btn { width: 100%; }
        @media (max-width: 800px) { .pay-layout { grid-template-columns: 1fr; } .item-grid { grid-template-columns: 1fr; } .breakdown-grid { grid-template-columns: 1fr; } .breakdown-field.full-width { grid-column: span 1; } }
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

export default PayWAPage;
