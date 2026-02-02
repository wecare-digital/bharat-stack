/**
 * Pay Page with Tabs (WhatsApp | Link | Logs)
 * Payment requests and transactions
 */

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

// Dynamic imports
const WhatsAppPay = dynamic(() => import('./wa/index'), { ssr: false });
const PayLink = dynamic(() => import('./link/index'), { ssr: false });
const PayLogs = dynamic(() => import('./logs/index'), { ssr: false });

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'whatsapp' | 'link' | 'logs';

const PayPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('whatsapp');

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Payments | WECARE.DIGITAL"
        description="Send payment requests and track transactions"
      />
      <div className="tabbed-page">
        <div className="page-tabs">
          <button 
            className={`tab-btn ${activeTab === 'whatsapp' ? 'active' : ''}`}
            onClick={() => setActiveTab('whatsapp')}
          >
            WhatsApp
          </button>
          <button 
            className={`tab-btn ${activeTab === 'link' ? 'active' : ''}`}
            onClick={() => setActiveTab('link')}
          >
            Link
          </button>
          <button 
            className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
            onClick={() => setActiveTab('logs')}
          >
            Logs
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'whatsapp' && <WhatsAppPay signOut={signOut} user={user} />}
          {activeTab === 'link' && <PayLink signOut={signOut} user={user} />}
          {activeTab === 'logs' && <PayLogs signOut={signOut} user={user} />}
        </div>
      </div>

      <style jsx>{`
        .tabbed-page { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
        .page-tabs { 
          display: flex; 
          gap: 8px; 
          padding: 16px 20px; 
          background: var(--color-bg-secondary, #f9fafb); 
          border-bottom: 1px solid var(--color-border, #e5e7eb);
          flex-shrink: 0;
          overflow-x: auto;
        }
        .tab-btn { 
          padding: 8px 16px; 
          border: none; 
          border-radius: 6px; 
          background: transparent; 
          cursor: pointer; 
          font-size: 14px;
          font-weight: 500;
          color: var(--color-muted, #6b7280);
          white-space: nowrap;
          transition: all 0.15s ease;
        }
        .tab-btn:hover { background: var(--color-bg, #f3f4f6); color: var(--color-text, #111827); }
        .tab-btn.active { 
          background: var(--color-primary, #10b981); 
          color: white; 
        }
        .tab-content { flex: 1; overflow: auto; }
        @media (max-width: 768px) {
          .page-tabs { padding: 12px 16px; gap: 6px; }
          .tab-btn { padding: 8px 12px; font-size: 13px; }
        }
      `}</style>
    </Layout>
  );
};

export default PayPage;
