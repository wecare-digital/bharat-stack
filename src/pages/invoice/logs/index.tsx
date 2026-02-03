/**
 * Invoice Logs Page - Coming Soon
 */

import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Breadcrumbs from '../../../components/ui/Breadcrumbs';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const InvoiceLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Invoice Logs | WECARE.DIGITAL" description="Invoice logs" />
      <div style={{ padding: '20px' }}>
        <Breadcrumbs />
        <h2 style={{ margin: '12px 0 20px' }}>Invoice Logs</h2>
        
        <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '12px', padding: '60px 20px', textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
          <h3 style={{ margin: '0 0 8px', color: '#065f46' }}>Invoice Logs Coming Soon</h3>
          <p style={{ margin: '0 0 16px', color: '#6b7280' }}>Track invoice status and payment history</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center', marginTop: '20px' }}>
            {['Payment Status', 'Due Dates', 'Overdue Alerts', 'Revenue Reports'].map(f => (
              <span key={f} style={{ padding: '6px 12px', background: '#D1FAE5', color: '#065f46', borderRadius: '20px', fontSize: '13px' }}>{f}</span>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default InvoiceLogsPage;
