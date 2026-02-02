/**
 * SMS Page with Tabs (Inbox + Campaign)
 * AWS Pinpoint SMS Gateway
 */

import React, { useState } from 'react';
import { useRouter } from 'next/router';

// Import the actual pages
import SmsInboxPage from './aws';
import SmsCampaignPage from './aws/campaign';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

type TabType = 'inbox' | 'campaign';

const SmsPage: React.FC<PageProps> = ({ signOut, user }) => {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('inbox');

  return (
    <div className="tabbed-page">
      <div className="page-tabs">
        <button 
          className={`tab-btn ${activeTab === 'inbox' ? 'active' : ''}`}
          onClick={() => setActiveTab('inbox')}
        >
          📥 Inbox
        </button>
        <button 
          className={`tab-btn ${activeTab === 'campaign' ? 'active' : ''}`}
          onClick={() => setActiveTab('campaign')}
        >
          📢 Campaign
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'inbox' && <SmsInboxPage signOut={signOut} user={user} />}
        {activeTab === 'campaign' && <SmsCampaignPage signOut={signOut} user={user} />}
      </div>

      <style jsx>{`
        .tabbed-page { display: flex; flex-direction: column; height: 100vh; }
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
        .tab-content { flex: 1; overflow: hidden; }
        .tab-content > :global(div) { height: 100%; }
      `}</style>
    </div>
  );
};

export default SmsPage;
