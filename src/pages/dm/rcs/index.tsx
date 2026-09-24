/**
 * RCS Mega Page - Inbox + Campaign + Logs as tabs
 * Uses PageShell for section header + tab bar
 */
import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import PageShell, { ShellTab } from '../../../components/PageShell';

// The unified inbox, preset to RCS. ./inbox was 273 lines of which 196 were
// byte-identical to ses/inbox, and dm/inbox already reads AND writes RCS.
import UnifiedInbox from '../inbox';
import RcsSendPage from './send';
import RcsTemplatesPage from './templates';
// dm/broadcast is the multi-channel superset. ./campaign made no send call at
// all - it was campaign history synthesised from listMessages.
import BroadcastPage from '../broadcast';
// Unified logs, preset to this channel. ./logs was 119 lines calling the same
// api.listMessages as dm/logs against the same canonical table.
import MessageLogsPage from '../logs';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const TABS: ShellTab[] = [
  { id: 'inbox', label: 'Inbox' },
  { id: 'send', label: 'Send' },
  { id: 'templates', label: 'Templates' },
  { id: 'campaign', label: 'Campaign' },
  { id: 'logs', label: 'Logs' },
];

const RcsPage: React.FC<PageProps> = ( { signOut, user, embedded } ) => {
  const shellContent = (
    <PageShell title="RCS" subtitle="Rich Communication Services — Inbox, Campaigns & Logs" tabs={ TABS } defaultTab="inbox">
      { ( activeTab ) => (
        <>
          { activeTab === 'inbox' && <UnifiedInbox signOut={ signOut } user={ user } embedded channel="rcs" /> }
          { activeTab === 'send' && <RcsSendPage signOut={ signOut } user={ user } embedded /> }
          { activeTab === 'templates' && <RcsTemplatesPage signOut={ signOut } user={ user } embedded /> }
          { activeTab === 'campaign' && <BroadcastPage signOut={ signOut } user={ user } embedded /> }
          { activeTab === 'logs' && <MessageLogsPage signOut={ signOut } user={ user } embedded channel="rcs" /> }
        </>
      ) }
    </PageShell>
  );

  if ( embedded ) return shellContent;

  return (
    <Layout user={ user } onSignOut={ signOut }>
      <SEO title="RCS" description="RCS Business Messaging" />
      { shellContent }
    </Layout>
  );
};

export default RcsPage;
