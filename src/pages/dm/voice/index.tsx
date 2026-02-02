/**
 * Voice Page with Tabs (Calls + Campaign)
 * AWS Connect Voice Gateway
 */

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { Tabs } from '../../../components/ui';

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

  const tabItems = [
    { id: 'calls', label: 'Calls' },
    { id: 'campaign', label: 'Campaign' },
  ];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Voice | WECARE.DIGITAL"
        description="Voice calls via AWS Connect"
      />
      <div className="tabbed-page">
        <Tabs
          items={tabItems}
          activeTab={activeTab}
          onChange={(id) => setActiveTab(id as TabType)}
        />
        <div className="tab-content">
          {activeTab === 'calls' && <VoiceCallsPage signOut={signOut} user={user} embedded={true} />}
          {activeTab === 'campaign' && <VoiceCampaignPage signOut={signOut} user={user} embedded={true} />}
        </div>
      </div>
    </Layout>
  );
};

export default VoicePage;
