/**
 * Email Mega Page - Inbox + Campaign + Logs as tabs
 * Uses PageShell for section header + tab bar
 */
import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import PageShell, { ShellTab } from '../../../components/PageShell';

import EmailInbox from './inbox';
import EmailCampaignPage from './campaign';
import EmailLogsPage from './logs';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const TABS: ShellTab[] = [
  { id: 'inbox', label: 'Inbox' },
  { id: 'campaign', label: 'Campaign' },
  { id: 'logs', label: 'Logs' },
];

const EmailPage: React.FC<PageProps> = ({ signOut, user, embedded }) => {
  const shellContent = (
    <PageShell title="Email" subtitle="AWS SES — Inbox, Campaigns & Logs" tabs={TABS} defaultTab="inbox">
      {(activeTab) => (
        <>
          {activeTab === 'inbox' && <EmailInbox signOut={signOut} user={user} embedded />}
          {activeTab === 'campaign' && <EmailCampaignPage signOut={signOut} user={user} embedded />}
          {activeTab === 'logs' && <EmailLogsPage signOut={signOut} user={user} embedded />}
        </>
      )}
    </PageShell>
  );

  if (embedded) return shellContent;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Email | WECARE.DIGITAL" description="Email — AWS SES" />
      {shellContent}
    </Layout>
  );
};

export default EmailPage;
