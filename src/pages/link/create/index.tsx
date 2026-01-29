/**
 * Link Create - Create Shareable Links
 */

import React from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const LinkCreatePage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="page">
        <PageHeader 
          title="Create Link" 
          subtitle="Create shareable links for payments, forms, and more"
          icon="create"
        />
        <div className="section">
          <div className="empty-state">
            <p>🔗 Link creation coming soon</p>
            <p className="help-text">Create shareable links for payments, forms, and more</p>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default LinkCreatePage;
