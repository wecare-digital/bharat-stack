/**
 * RCS Campaign Page
 * Rich Communication Services campaigns
 */

import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const RcsCampaignPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="RCS Campaign | WECARE.DIGITAL" description="RCS campaigns" />
      <div style={{ padding: '20px' }}>
        <h2 style={{ margin: '0 0 20px' }}>RCS - Campaign</h2>
        
        <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '12px', padding: '60px 20px', textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📢</div>
          <h3 style={{ margin: '0 0 8px', color: '#065f46' }}>RCS Campaigns Coming Soon</h3>
          <p style={{ margin: '0 0 16px', color: '#6b7280' }}>Send rich media campaigns with carousels, cards, and interactive elements</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center', marginTop: '20px' }}>
            {['Bulk Campaigns', 'Rich Cards', 'Carousel Templates', 'Action Buttons', 'Analytics'].map(f => (
              <span key={f} style={{ padding: '6px 12px', background: '#D1FAE5', color: '#065f46', borderRadius: '20px', fontSize: '13px' }}>{f}</span>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default RcsCampaignPage;
