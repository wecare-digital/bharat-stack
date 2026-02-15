/**
 * WhatsApp Mega Page - All WhatsApp features as tabs
 * Uses PageShell for section header + scrollable tab bar
 */

import React, { lazy, Suspense } from 'react';
import Layout from '../../../components/Layout';
import PageShell, { ShellTab } from '../../../components/PageShell';

// Direct imports (these already support embedded)
import InboxPage from './inbox';
import WABADashboard from './waba-dashboard';
import TemplatesPage from './templates';
import WelcomePage from './welcome';

// Direct imports for pages we'll add embedded support to
import CampaignPage from './campaign';
import LogsPage from './logs';
import InteractiveListsPage from './interactive-lists';
import FlowsPage from './flows';
import CallingPage from './calling';
import GroupsPage from './groups';
import BusinessProfilePage from './business-profile';
import WebhooksPage from './webhooks';
import AIConfigPage from './ai-config';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const TABS: ShellTab[] = [
  { id: 'inbox', label: 'Inbox' },
  { id: 'board', label: 'Board' },
  { id: 'campaign', label: 'Campaign' },
  { id: 'templates', label: 'Templates' },
  { id: 'lists', label: 'List Msgs' },
  { id: 'flows', label: 'Flows' },
  { id: 'calling', label: 'Calling' },
  { id: 'groups', label: 'Groups' },
  { id: 'logs', label: 'Logs' },
  { id: 'welcome', label: 'Welcome' },
  { id: 'ai-config', label: 'AI Config' },
  { id: 'profile', label: 'Profile' },
  { id: 'webhooks', label: 'Webhooks' },
  { id: 'waba', label: 'WABA' },
];

const WhatsAppPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <PageShell
        title="WhatsApp"
        subtitle="Business API — Messaging, Campaigns, Templates & More"
        tabs={TABS}
        defaultTab="inbox"
      >
        {(activeTab) => (
          <Suspense fallback={<div style={{ padding: 40, textAlign: 'center' }}>Loading...</div>}>
            {activeTab === 'inbox' && <InboxPage signOut={signOut} user={user} embedded />}
            {activeTab === 'board' && <WABADashboard signOut={signOut} user={user} embedded />}
            {activeTab === 'campaign' && <CampaignPage signOut={signOut} user={user} embedded />}
            {activeTab === 'templates' && <TemplatesPage signOut={signOut} user={user} embedded />}
            {activeTab === 'lists' && <InteractiveListsPage signOut={signOut} user={user} embedded />}
            {activeTab === 'flows' && <FlowsPage signOut={signOut} user={user} embedded />}
            {activeTab === 'calling' && <CallingPage signOut={signOut} user={user} embedded />}
            {activeTab === 'groups' && <GroupsPage signOut={signOut} user={user} embedded />}
            {activeTab === 'logs' && <LogsPage signOut={signOut} user={user} embedded />}
            {activeTab === 'welcome' && <WelcomePage signOut={signOut} user={user} embedded />}
            {activeTab === 'ai-config' && <AIConfigPage signOut={signOut} user={user} embedded />}
            {activeTab === 'profile' && <BusinessProfilePage signOut={signOut} user={user} embedded />}
            {activeTab === 'webhooks' && <WebhooksPage signOut={signOut} user={user} embedded />}
            {activeTab === 'waba' && <WABADashboard signOut={signOut} user={user} embedded />}
          </Suspense>
        )}
      </PageShell>
    </Layout>
  );
};

export default WhatsAppPage;
