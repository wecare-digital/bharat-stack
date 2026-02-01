/**
 * Invoice Hub - Quick Action Cards
 */

import React from 'react';
import Link from 'next/link';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import SEO from '../../components/SEO';
import { CreateIcon, LogsIcon } from '../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const InvoicePage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Invoice | WECARE.DIGITAL"
        description="Create and manage invoices"
      />
      <div className="hub-page">
        <PageHeader 
          title="Invoice" 
          subtitle="Create and manage invoices"
          icon="invoice"
        />

        <div className="hub-grid hub-grid-2">
          <Link href="/invoice/create" className="hub-card">
            <span className="hub-icon"><CreateIcon size={32} /></span>
            <span className="hub-label">Create</span>
          </Link>
          <Link href="/invoice/logs" className="hub-card">
            <span className="hub-icon"><LogsIcon size={32} /></span>
            <span className="hub-label">Logs</span>
          </Link>
        </div>
      </div>
    </Layout>
  );
};

export default InvoicePage;
