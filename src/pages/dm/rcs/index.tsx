/**
 * RCS Mega Page - Inbox + Campaign + Logs as tabs
 * Uses PageShell for section header + tab bar
 */
import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import PageShell, { ShellTab } from '../../../components/PageShell';

import RcsInbox from './inbox';
import RcsCampaignPage from './campaign';
import RcsLogsPage from './logs';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const TABS: ShellTab[] = [
  { id: 'inbox', label: 'Inbox' },
  { id: 'campaign', label: 'Campaign' },
  { id: 'logs', label: 'Logs' },
];

const RcsPage: React.FC<PageProps> = ({ signOut, user, embedded }) => {
  const shellContent = (
    <PageShell title="RCS" subtitle="Rich Communication Services — Inbox, Campaigns & Logs" tabs={TABS} defaultTab="inbox">
      {(activeTab) => (
        <>
          {activeTab === 'inbox' && <RcsInbox signOut={signOut} user={user} embedded />}
          {activeTab === 'campaign' && <RcsCampaignPage signOut={signOut} user={user} embedded />}
          {activeTab === 'logs' && <RcsLogsPage signOut={signOut} user={user} embedded />}
        </>
      )}
    </PageShell>
  );

  if (embedded) return shellContent;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="RCS" description="RCS Business Messaging" />
      {shellContent}
    </Layout>
  );
};

export default RcsPage;
