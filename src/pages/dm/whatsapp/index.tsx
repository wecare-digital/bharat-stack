/**
 * WhatsApp Page with Tabs (Board + Inbox + Campaign)
 * WhatsApp Business API
 */

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';

// Dynamic imports to avoid SSR issues with complex components
const WhatsAppBoard = dynamic(() => import('./waba-dashboard'), { ssr: false });
const WhatsAppInbox = dynamic(() => import('./inbox'), { ssr: false });
const WhatsAppCampaign = dynamic(() => import('./campaign'), { ssr: false });

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'board' | 'inbox' | 'campaign';

const WhatsAppPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('inbox');

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="WhatsApp | WECARE.DIGITAL"
        description="WhatsApp Business API - Inbox, Board, and Campaigns"
      />
      <div className="tabbed-page">
        <div className="page-tabs">
          <button 
            className={`tab-btn ${activeTab === 'board' ? 'active' : ''}`}
            onClick={() => setActiveTab('board')}
          >
            Board
          </button>
          <button 
            className={`tab-btn ${activeTab === 'inbox' ? 'active' : ''}`}
            onClick={() => setActiveTab('inbox')}
          >
            Inbox
          </button>
          <button 
            className={`tab-btn ${activeTab === 'campaign' ? 'active' : ''}`}
            onClick={() => setActiveTab('campaign')}
          >
            Campaign
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'board' && <WhatsAppBoard signOut={signOut} user={user} embedded={true} />}
          {activeTab === 'inbox' && <WhatsAppInbox signOut={signOut} user={user} embedded={true} />}
          {activeTab === 'campaign' && <WhatsAppCampaign signOut={signOut} user={user} embedded={true} />}
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
        .tab-content { flex: 1; overflow: hidden; }
        .tab-content > :global(div) { height: 100%; }
        @media (max-width: 768px) {
          .page-tabs { padding: 12px 16px; gap: 6px; }
          .tab-btn { padding: 8px 12px; font-size: 13px; }
        }
      `}</style>
    </Layout>
  );
};

export default WhatsAppPage;
