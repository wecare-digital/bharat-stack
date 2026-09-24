/**
 * Email Mega Page - Inbox + Campaign + Logs as tabs
 * Uses PageShell for section header + tab bar
 */
import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import PageShell, { ShellTab } from '../../../components/PageShell';

// The unified inbox, preset to Email. ./inbox was a 263-line twin of rcs/inbox
// and dm/inbox already reads and writes email.
import UnifiedInbox from '../inbox';
// dm/broadcast is the multi-channel superset and already sends email.
import BroadcastPage from '../broadcast';
// Unified logs, preset to this channel. ./logs was 268 lines over the same table;
// its one unique feature, row delete, moved into dm/logs.
import MessageLogsPage from '../logs';

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
          {activeTab === 'inbox' && <UnifiedInbox signOut={signOut} user={user} embedded channel="email" />}
          {activeTab === 'campaign' && <BroadcastPage signOut={signOut} user={user} embedded />}
          {activeTab === 'logs' && <MessageLogsPage signOut={signOut} user={user} embedded channel="email" />}
        </>
      )}
    </PageShell>
  );

  if (embedded) return shellContent;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Email" description="Email — AWS SES" />
      {shellContent}
    </Layout>
  );
};

export default EmailPage;
