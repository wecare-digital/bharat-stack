/**
 * Voice Page with Tabs (Calls + Campaign)
 * AWS Connect Voice Gateway
 */

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';

// Dynamic imports to avoid SSR issues
const VoiceCallsPage = dynamic(() => import('./aws'), { ssr: false });
const VoiceCampaignPage = dynamic(() => import('./aws/campaign'), { ssr: false });

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'calls' | 'campaign';

const VoicePage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('calls');

  const tabStyle = (isActive: boolean): React.CSSProperties => ({
    padding: '10px 18px',
    border: '1.5px solid #10B981',
    borderRadius: '13px',
    background: isActive ? '#D1FAE5' : '#fff',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: isActive ? 600 : 500,
    color: '#111827',
    whiteSpace: 'nowrap',
    transition: 'all 0.15s ease',
    minHeight: '44px',
  });

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Voice | WECARE.DIGITAL"
        description="Voice calls via AWS Connect"
      />
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <div style={{ display: 'flex', gap: '8px', padding: '16px 20px', background: '#f9fafb', borderBottom: '1px solid #e5e7eb', flexShrink: 0, overflowX: 'auto' }}>
          <button 
            type="button"
            style={tabStyle(activeTab === 'calls')}
            onClick={() => setActiveTab('calls')}
          >
            Calls
          </button>
          <button 
            type="button"
            style={tabStyle(activeTab === 'campaign')}
            onClick={() => setActiveTab('campaign')}
          >
            Campaign
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', minHeight: 0, width: '100%' }}>
          {activeTab === 'calls' && <VoiceCallsPage signOut={signOut} user={user} embedded={true} />}
          {activeTab === 'campaign' && <VoiceCampaignPage signOut={signOut} user={user} embedded={true} />}
        </div>
      </div>
    </Layout>
  );
};

export default VoicePage;
