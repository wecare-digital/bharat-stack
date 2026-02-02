/**
 * Pay Page with Tabs (WhatsApp | Link | Logs)
 * Payment requests and transactions
 */

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import { Tabs } from '../../components/ui';

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

  const tabItems = [
    { id: 'whatsapp', label: 'WhatsApp' },
    { id: 'link', label: 'Link' },
    { id: 'logs', label: 'Logs' },
  ];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Payments | WECARE.DIGITAL"
        description="Send payment requests and track transactions"
      />
      <div className="tabbed-page">
        <Tabs
          items={tabItems}
          activeTab={activeTab}
          onChange={(id) => setActiveTab(id as TabType)}
        />
        <div className="tab-content">
          {activeTab === 'whatsapp' && <WhatsAppPay signOut={signOut} user={user} />}
          {activeTab === 'link' && <PayLink signOut={signOut} user={user} />}
          {activeTab === 'logs' && <PayLogs signOut={signOut} user={user} />}
        </div>
      </div>
    </Layout>
  );
};

export default PayPage;
