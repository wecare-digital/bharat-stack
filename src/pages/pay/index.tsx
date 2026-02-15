/**
 * Pay Mega Page - Flow + WhatsApp + Link as tabs
 * Uses PageShell for section header + tab bar
 */
import React from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import PageShell, { ShellTab } from '../../components/PageShell';

import PayFlowPage from './flow';
import PayWAPage from './wa';
import PayLinkPage from './link';

interface PageProps { signOut?: () => void; user?: any; }

const TABS: ShellTab[] = [
  { id: 'flow', label: 'Flow CRM' },
  { id: 'wa', label: 'WhatsApp Pay' },
  { id: 'link', label: 'Pay Link' },
];

const PayPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Pay | WECARE.DIGITAL" description="Payments — Flow CRM, WhatsApp Pay & Pay Links" />
      <PageShell title="Pay" subtitle="Flow CRM, WhatsApp Pay & Payment Links" tabs={TABS} defaultTab="flow">
        {(activeTab) => (
          <>
            {activeTab === 'flow' && <PayFlowPage signOut={signOut} user={user} embedded />}
            {activeTab === 'wa' && <PayWAPage signOut={signOut} user={user} embedded />}
            {activeTab === 'link' && <PayLinkPage signOut={signOut} user={user} embedded />}
          </>
        )}
      </PageShell>
    </Layout>
  );
};

export default PayPage;
