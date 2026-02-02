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
            💬 WhatsApp
          </button>
          <button 
            className={`tab-btn ${activeTab === 'link' ? 'active' : ''}`}
            onClick={() => setActiveTab('link')}
          >
            🔗 Link
          </button>
          <button 
            className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
            onClick={() => setActiveTab('logs')}
          >
            📋 Logs
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'whatsapp' && <WhatsAppPay signOut={signOut} user={user} />}
          {activeTab === 'link' && <PayLink signOut={signOut} user={user} />}
          {activeTab === 'logs' && <PayLogs signOut={signOut} user={user} />}
        </div>
      </div>

      <style jsx>{`
        .tabbed-page { display: flex; flex-direction: column; height: calc(100vh - 60px); }
        .page-tabs { 
          display: flex; 
          gap: 4px; 
          padding: 12px 16px; 
          background: #fafafa; 
          border-bottom: 1px solid #e5e5e5;
          flex-shrink: 0;
        }
        .tab-btn { 
          padding: 10px 20px; 
          border: 1px solid #e5e5e5; 
          border-radius: 8px; 
          background: white; 
          cursor: pointer; 
          font-size: 14px;
          font-weight: 500;
          transition: all 0.15s ease;
        }
        .tab-btn:hover { background: #f5f5f5; }
        .tab-btn.active { 
          background: #000; 
          color: white; 
          border-color: #000; 
        }
        .tab-content { flex: 1; overflow: auto; }
      `}</style>
    </Layout>
  );
};

export default PayPage;
