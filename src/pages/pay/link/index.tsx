/**
 * Pay Link - Payment Link Generator
 * Generate shareable payment links for any channel
 */

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const PayLinkPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [referenceId, setReferenceId] = useState('');
  const [amount, setAmount] = useState<number>(0);
  const [description, setDescription] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [expiryDays, setExpiryDays] = useState<number>(7);
  const [generatedLink, setGeneratedLink] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    handleGenerateReferenceId();
  }, []);

  const handleGenerateReferenceId = () => {
    // WDPL = WeCare Digital Payment Link (no underscore)
    const uuid = crypto.randomUUID().replace(/-/g, '').substring(0, 8).toUpperCase();
    setReferenceId(`WDPL${uuid}`);
  };

  const generatePaymentLink = () => {
    // TODO: Integrate with Razorpay Payment Links API
    // For now, generate a placeholder link
    const baseUrl = 'https://rzp.io/i/';
    const linkId = crypto.randomUUID().replace(/-/g, '').substring(0, 10);
    setGeneratedLink(`${baseUrl}${linkId}`);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(generatedLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="pay-link-page">
        <PageHeader 
          title="Pay Link" 
          subtitle="Generate shareable payment links for any channel"
          icon="link"
        />

        <div className="coming-soon-banner">
          <div className="banner-icon">🚧</div>
          <div className="banner-content">
            <h3>Coming Soon</h3>
            <p>Payment Link generation via Razorpay API is under development</p>
          </div>
        </div>

        <div className="page-layout">
          <div className="link-form">
            <div className="form-section">
              <h3>🔖 Reference ID</h3>
              <div className="ref-row">
                <input type="text" value={referenceId} readOnly />
                <button type="button" onClick={handleGenerateReferenceId} className="gen-btn">New</button>
              </div>
            </div>

            <div className="form-section">
              <h3>💰 Payment Details</h3>
              <div className="form-grid">
                <div className="form-field">
                  <label>Amount (₹) *</label>
                  <input
                    type="number"
                    value={amount || ''}
                    onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
                    placeholder="0.00"
                    min="1"
                    step="0.01"
                  />
                </div>
                <div className="form-field">
                  <label>Expiry (Days)</label>
                  <select value={expiryDays} onChange={(e) => setExpiryDays(parseInt(e.target.value))}>
                    <option value={1}>1 Day</option>
                    <option value={3}>3 Days</option>
                    <option value={7}>7 Days</option>
                    <option value={15}>15 Days</option>
                    <option value={30}>30 Days</option>
                  </select>
                </div>
                <div className="form-field full-width">
                  <label>Description</label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Payment for services"
                  />
                </div>
              </div>
            </div>

            <div className="form-section">
              <h3>👤 Customer Details (Optional)</h3>
              <div className="form-grid">
                <div className="form-field">
                  <label>Name</label>
                  <input
                    type="text"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Customer Name"
                  />
                </div>
                <div className="form-field">
                  <label>Phone</label>
                  <input
                    type="tel"
                    value={customerPhone}
                    onChange={(e) => setCustomerPhone(e.target.value)}
                    placeholder="+91 XXXXX XXXXX"
                  />
                </div>
                <div className="form-field full-width">
                  <label>Email</label>
                  <input
                    type="email"
                    value={customerEmail}
                    onChange={(e) => setCustomerEmail(e.target.value)}
                    placeholder="customer@email.com"
                  />
                </div>
              </div>
            </div>

            <button
              className="generate-btn"
              onClick={generatePaymentLink}
              disabled={amount <= 0}
            >
              🔗 Generate Payment Link
            </button>
          </div>

          <div className="link-preview">
            <h3>📋 Generated Link</h3>
            <div className="preview-card">
              {generatedLink ? (
                <>
                  <div className="link-display">
                    <input type="text" value={generatedLink} readOnly />
                    <button onClick={copyToClipboard} className="copy-btn">
                      {copied ? '✓ Copied' : '📋 Copy'}
                    </button>
                  </div>
                  <div className="link-details">
                    <div className="detail-row"><span>Amount:</span><span>₹{amount.toFixed(2)}</span></div>
                    <div className="detail-row"><span>Reference:</span><span>{referenceId}</span></div>
                    <div className="detail-row"><span>Expires:</span><span>{expiryDays} days</span></div>
                    {description && <div className="detail-row"><span>Description:</span><span>{description}</span></div>}
                  </div>
                  <div className="share-buttons">
                    <button className="share-btn whatsapp">💬 WhatsApp</button>
                    <button className="share-btn email">📧 Email</button>
                    <button className="share-btn sms">📱 SMS</button>
                  </div>
                </>
              ) : (
                <div className="empty-state">
                  <div className="empty-icon">🔗</div>
                  <p>Enter payment details and click Generate to create a payment link</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .pay-link-page { padding: 20px; max-width: 1100px; margin: 0 auto; }
        .page-header { margin-bottom: 20px; }
        .page-header h1 { font-size: 22px; margin: 0 0 4px 0; }
        .page-header p { color: #666; margin: 0; font-size: 14px; }
        
        .coming-soon-banner { display: flex; align-items: center; gap: 16px; background: #fef3c7; padding: 16px 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #fcd34d; }
        .banner-icon { font-size: 32px; }
        .banner-content h3 { margin: 0 0 4px 0; font-size: 16px; color: #92400e; }
        .banner-content p { margin: 0; font-size: 13px; color: #a16207; }
        
        .page-layout { display: grid; grid-template-columns: 1fr 400px; gap: 20px; }
        
        .link-form { background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .form-section { margin-bottom: 24px; }
        .form-section h3 { font-size: 13px; margin: 0 0 12px 0; color: #333; }
        
        .ref-row { display: flex; gap: 8px; }
        .ref-row input { flex: 1; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; background: #f9fafb; }
        .gen-btn { padding: 8px 12px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 6px; cursor: pointer; font-size: 12px; }
        .gen-btn:hover { background: #e5e5e5; }
        
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .form-field { }
        .form-field.full-width { grid-column: span 2; }
        .form-field label { display: block; font-size: 11px; color: #666; margin-bottom: 4px; }
        .form-field input, .form-field select { width: 100%; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; box-sizing: border-box; }
        .form-field input:focus, .form-field select:focus { outline: none; border-color: #3b82f6; }
        
        .generate-btn { width: 100%; padding: 12px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
        .generate-btn:hover:not(:disabled) { background: #2563eb; }
        .generate-btn:disabled { background: #ccc; cursor: not-allowed; }
        
        .link-preview h3 { font-size: 13px; margin: 0 0 10px 0; }
        .preview-card { background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 2px solid #3b82f6; }
        
        .link-display { display: flex; gap: 8px; margin-bottom: 16px; }
        .link-display input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; background: #f9fafb; }
        .copy-btn { padding: 10px 16px; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; white-space: nowrap; }
        .copy-btn:hover { background: #2563eb; }
        
        .link-details { padding: 12px; background: #f9fafb; border-radius: 6px; margin-bottom: 16px; }
        .detail-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 12px; }
        .detail-row span:first-child { color: #666; }
        .detail-row span:last-child { font-weight: 500; }
        
        .share-buttons { display: flex; gap: 8px; }
        .share-btn { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 6px; cursor: pointer; font-size: 12px; background: #fff; }
        .share-btn:hover { background: #f9fafb; }
        .share-btn.whatsapp:hover { border-color: #25D366; color: #25D366; }
        .share-btn.email:hover { border-color: #3b82f6; color: #3b82f6; }
        .share-btn.sms:hover { border-color: #8b5cf6; color: #8b5cf6; }
        
        .empty-state { text-align: center; padding: 40px 20px; color: #9ca3af; }
        .empty-icon { font-size: 48px; margin-bottom: 12px; opacity: 0.5; }
        .empty-state p { margin: 0; font-size: 13px; }
        
        @media (max-width: 800px) {
          .page-layout { grid-template-columns: 1fr; }
          .form-grid { grid-template-columns: 1fr; }
          .form-field.full-width { grid-column: span 1; }
        }
      `}</style>
    </Layout>
  );
};

export default PayLinkPage;
