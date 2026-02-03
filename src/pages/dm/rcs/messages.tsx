/**
 * RCS Messages Page
 * Rich Communication Services messages
 */

import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const RcsMessagesPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="RCS Messages | WECARE.DIGITAL" description="RCS messages" />
      <div style={{ padding: '20px' }}>
        <h2 style={{ margin: '0 0 20px' }}>RCS - Messages</h2>
        
        <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '12px', padding: '60px 20px', textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>💬</div>
          <h3 style={{ margin: '0 0 8px', color: '#065f46' }}>RCS Coming Soon</h3>
          <p style={{ margin: '0 0 16px', color: '#6b7280' }}>Rich Communication Services with rich media, carousels, and interactive buttons</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center', marginTop: '20px' }}>
            {['Rich Media', 'Carousels', 'Quick Replies', 'Branded Messages', 'Read Receipts'].map(f => (
              <span key={f} style={{ padding: '6px 12px', background: '#D1FAE5', color: '#065f46', borderRadius: '20px', fontSize: '13px' }}>{f}</span>
            ))}
          </div>
          <a href="https://www.airtel.in/business/b2b/airtel-iq/api-docs/rcs/overview" target="_blank" rel="noopener noreferrer" style={{ display: 'inline-block', marginTop: '24px', color: '#10B981', fontWeight: 500 }}>
            View RCS API Docs →
          </a>
        </div>
      </div>
    </Layout>
  );
};

export default RcsMessagesPage;
