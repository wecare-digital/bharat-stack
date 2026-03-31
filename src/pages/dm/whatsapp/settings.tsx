/**
 * WhatsApp Settings — All WhatsApp features except Inbox
 * Uses PageShell for section header + scrollable tab bar
 */

import React, { Suspense } from 'react';
import Layout from '../../../components/Layout';
import PageShell, { ShellTab } from '../../../components/PageShell';

import WABADashboard from './waba-dashboard';
import TemplatesPage from './templates';
import WelcomePage from './welcome';
import CampaignPage from './campaign';
import LogsPage from './logs';
import InteractiveListsPage from './interactive-lists';
import FlowsPage from './flows';
import CallingPage from './calling';
import GroupsPage from './groups';
import BusinessProfilePage from './business-profile';
import WebhooksPage from './webhooks';
import AIConfigPage from './ai-config';
import FlowResponsesPage from './flow-responses';
import FlowHubPage from './flow-hub';
import MigrationPage from './migration';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const TABS: ShellTab[] = [
  { id: 'campaign', label: 'Campaign' },
  { id: 'templates', label: 'Templates' },
  { id: 'lists', label: 'List Msgs', divider: true },
  { id: 'flows', label: 'Flows' },
  { id: 'flow-hub', label: 'Flows Hub' },
  { id: 'flow-responses', label: 'Flow Data' },
  { id: 'welcome', label: 'Welcome' },
  { id: 'ai-config', label: 'AI Config' },
  { id: 'calling', label: 'Calling', divider: true },
  { id: 'groups', label: 'Groups' },
  { id: 'logs', label: 'Logs', divider: true },
  { id: 'profile', label: 'Profile', divider: true },
  { id: 'webhooks', label: 'Webhooks' },
  { id: 'waba', label: 'WABA' },
  { id: 'migration', label: 'Migration' },
];

const WhatsAppSettingsPage: React.FC<PageProps> = ({ signOut, user }) => (
  <Layout user={user} onSignOut={signOut}>
    <PageShell
      title="WhatsApp"
      subtitle="Business API — Messaging, Campaigns, Templates & More"
      tabs={TABS}
      defaultTab="campaign"
    >
      {(activeTab) => (
        <Suspense fallback={<div style={{ padding: 40, textAlign: 'center' }}>Loading...</div>}>
          {activeTab === 'campaign' && <CampaignPage signOut={signOut} user={user} embedded />}
          {activeTab === 'templates' && <TemplatesPage signOut={signOut} user={user} embedded />}
          {activeTab === 'lists' && <InteractiveListsPage signOut={signOut} user={user} embedded />}
          {activeTab === 'flows' && <FlowsPage signOut={signOut} user={user} embedded />}
          {activeTab === 'flow-hub' && <FlowHubPage signOut={signOut} user={user} embedded />}
          {activeTab === 'flow-responses' && <FlowResponsesPage signOut={signOut} user={user} embedded />}
          {activeTab === 'welcome' && <WelcomePage signOut={signOut} user={user} embedded />}
          {activeTab === 'ai-config' && <AIConfigPage signOut={signOut} user={user} embedded />}
          {activeTab === 'calling' && <CallingPage signOut={signOut} user={user} embedded />}
          {activeTab === 'groups' && <GroupsPage signOut={signOut} user={user} embedded />}
          {activeTab === 'logs' && <LogsPage signOut={signOut} user={user} embedded />}
          {activeTab === 'profile' && <BusinessProfilePage signOut={signOut} user={user} embedded />}
          {activeTab === 'webhooks' && <WebhooksPage signOut={signOut} user={user} embedded />}
          {activeTab === 'waba' && <WABADashboard signOut={signOut} user={user} embedded />}
          {activeTab === 'migration' && <MigrationPage signOut={signOut} user={user} embedded />}
        </Suspense>
      )}
    </PageShell>
  </Layout>
);

export default WhatsAppSettingsPage;
