/**
 * Pay Mega Page - Flow + WhatsApp + Link as tabs
 * Uses PageShell for section header + tab bar
 */
import React from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import PageShell, { ShellTab } from '../../components/PageShell';

import PayFlowPage from './flow';
import PayLinkPage from './link';

interface PageProps { signOut?: () => void; user?: any; }

const TABS: ShellTab[] = [
  { id: 'flow', label: 'Flow' },
  { id: 'link', label: 'Link' },
];

const PayPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Pay | WECARE.DIGITAL" description="Payments — Flow CRM, WhatsApp Pay & Pay Links" />
      <PageShell title="Pay" subtitle="Invoices, WhatsApp Pay & Payment Links" tabs={TABS} defaultTab="flow">
        {(activeTab) => (
          <>
            {activeTab === 'flow' && <PayFlowPage signOut={signOut} user={user} embedded />}
            {activeTab === 'link' && <PayLinkPage signOut={signOut} user={user} embedded />}
          </>
        )}
      </PageShell>
    </Layout>
  );
};

export default PayPage;
