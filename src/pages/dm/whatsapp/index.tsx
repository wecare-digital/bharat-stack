/**
 * WhatsApp Page with Tabs (Board + Inbox + Campaign)
 */

import React, { useState, lazy, Suspense } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';

// Lazy load components
const WhatsAppBoard = lazy(() => import('./waba-dashboard'));
const WhatsAppInbox = lazy(() => import('./inbox'));
const WhatsAppCampaign = lazy(() => import('./campaign'));

const LoadingFallback = () => (
  <div style={{ padding: 40, textAlign: 'center', color: '#666' }}>
    Loading...
  </div>
);

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
        description="WhatsApp Business API"
      />
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ display: 'flex', gap: 8, padding: '16px 20px', background: '#f9fafb', borderBottom: '1px solid #e5e7eb', flexShrink: 0 }}>
          <button 
            onClick={() => setActiveTab('board')}
            style={{ 
              padding: '10px 20px', 
              background: activeTab === 'board' ? '#D1FAE5' : '#fff',
              color: '#111827',
              border: '1.5px solid #10B981',
              borderRadius: 13,
              cursor: 'pointer',
              fontWeight: activeTab === 'board' ? 600 : 500,
              fontSize: 14
            }}
          >
            Board
          </button>
          <button 
            onClick={() => setActiveTab('inbox')}
            style={{ 
              padding: '10px 20px', 
              background: activeTab === 'inbox' ? '#D1FAE5' : '#fff',
              color: '#111827',
              border: '1.5px solid #10B981',
              borderRadius: 13,
              cursor: 'pointer',
              fontWeight: activeTab === 'inbox' ? 600 : 500,
              fontSize: 14
            }}
          >
            Inbox
          </button>
          <button 
            onClick={() => setActiveTab('campaign')}
            style={{ 
              padding: '10px 20px', 
              background: activeTab === 'campaign' ? '#D1FAE5' : '#fff',
              color: '#111827',
              border: '1.5px solid #10B981',
              borderRadius: 13,
              cursor: 'pointer',
              fontWeight: activeTab === 'campaign' ? 600 : 500,
              fontSize: 14
            }}
          >
            Campaign
          </button>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <Suspense fallback={<LoadingFallback />}>
            {activeTab === 'board' && <WhatsAppBoard embedded={true} />}
            {activeTab === 'inbox' && <WhatsAppInbox embedded={true} />}
            {activeTab === 'campaign' && <WhatsAppCampaign embedded={true} />}
          </Suspense>
        </div>
      </div>
    </Layout>
  );
};

export default WhatsAppPage;
