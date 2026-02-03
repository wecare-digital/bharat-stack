/**
 * RCS Logs Page
 * Rich Communication Services logs - Coming Soon
 */

import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Breadcrumbs from '../../../components/ui/Breadcrumbs';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const RcsLogs: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="RCS Logs | WECARE.DIGITAL" description="RCS logs" />
      <div style={{ padding: '20px' }}>
        <Breadcrumbs />
        <h2 style={{ margin: '12px 0 20px' }}>RCS Logs</h2>
        
        <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '12px', padding: '60px 20px', textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📋</div>
          <h3 style={{ margin: '0 0 8px', color: '#065f46' }}>RCS Logs Coming Soon</h3>
          <p style={{ margin: '0 0 16px', color: '#6b7280' }}>View delivery reports, read receipts, and message analytics</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center', marginTop: '20px' }}>
            {['Delivery Reports', 'Read Receipts', 'Analytics', 'Export Data'].map(f => (
              <span key={f} style={{ padding: '6px 12px', background: '#D1FAE5', color: '#065f46', borderRadius: '20px', fontSize: '13px' }}>{f}</span>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default RcsLogs;
