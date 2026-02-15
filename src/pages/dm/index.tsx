/**
 * Messages Mega Page - All channels as tabs
 * Uses PageShell for section header + scrollable tab bar
 * Each tab embeds a channel mega-page (which has its own inner PageShell)
 */

import React from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import PageShell, { ShellTab } from '../../components/PageShell';

import WhatsAppPage from './whatsapp';
import SmsPage from './sms';
import VoicePage from './voice';
import EmailPage from './ses';
import RcsPage from './rcs';
import MessageLogsPage from './logs';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const TABS: ShellTab[] = [
  { id: 'whatsapp', label: 'WhatsApp' },
  { id: 'sms', label: 'SMS' },
  { id: 'voice', label: 'Voice' },
  { id: 'email', label: 'Email' },
  { id: 'rcs', label: 'RCS' },
  { id: 'logs', label: 'All Logs' },
];

const MessagesPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Messages | WECARE.DIGITAL" description="Direct Messaging — WhatsApp, SMS, Voice, Email, RCS" />
      <PageShell title="Messages" subtitle="WhatsApp, SMS, Voice, Email, RCS" tabs={TABS} defaultTab="whatsapp">
        {(activeTab) => (
          <>
            {activeTab === 'whatsapp' && <WhatsAppPage signOut={signOut} user={user} embedded />}
            {activeTab === 'sms' && <SmsPage signOut={signOut} user={user} embedded />}
            {activeTab === 'voice' && <VoicePage signOut={signOut} user={user} embedded />}
            {activeTab === 'email' && <EmailPage signOut={signOut} user={user} embedded />}
            {activeTab === 'rcs' && <RcsPage signOut={signOut} user={user} embedded />}
            {activeTab === 'logs' && <MessageLogsPage signOut={signOut} user={user} embedded />}
          </>
        )}
      </PageShell>
    </Layout>
  );
};

export default MessagesPage;
