/**
 * Invoice - Create New Invoice
 */
import React from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';

interface PageProps { signOut?: () => void; user?: any; }

const InvoiceCreatePage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <div style={{ padding: 20, maxWidth: 800, margin: '0 auto' }}>
        <PageHeader 
          title="Create Invoice" 
          subtitle="Generate professional invoices"
          icon="create"
        />
        <div style={{ background: '#f9fafb', borderRadius: 12, padding: 40, textAlign: 'center', marginTop: 20 }}>
          <span style={{ fontSize: 48, opacity: 0.5 }}>🚧</span>
          <p style={{ color: '#666', marginTop: 16 }}>Coming Soon</p>
        </div>
      </div>
    </Layout>
  );
};

export default InvoiceCreatePage;
