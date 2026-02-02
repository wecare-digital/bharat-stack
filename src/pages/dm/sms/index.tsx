/**
 * SMS Page with Tabs (Inbox + Campaign)
 * AWS Pinpoint SMS Gateway
 */

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { Tabs } from '../../../components/ui';

// Dynamic imports to avoid SSR issues
const SmsInboxPage = dynamic(() => import('./aws'), { ssr: false });
const SmsCampaignPage = dynamic(() => import('./aws/campaign'), { ssr: false });

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'inbox' | 'campaign';

const SmsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<TabType>('inbox');

  const tabItems = [
    { id: 'inbox', label: 'Inbox' },
    { id: 'campaign', label: 'Campaign' },
  ];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="SMS | WECARE.DIGITAL"
        description="SMS messaging via AWS Pinpoint"
      />
      <div className="tabbed-page">
        <Tabs
          items={tabItems}
          activeTab={activeTab}
          onChange={(id) => setActiveTab(id as TabType)}
        />
        <div className="tab-content">
          {activeTab === 'inbox' && <SmsInboxPage signOut={signOut} user={user} embedded={true} />}
          {activeTab === 'campaign' && <SmsCampaignPage signOut={signOut} user={user} embedded={true} />}
        </div>
      </div>
    </Layout>
  );
};

export default SmsPage;
