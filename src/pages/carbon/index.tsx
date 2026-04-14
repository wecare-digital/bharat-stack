import React from 'react';
import Layout from '../../components/Layout';
import EmptyState from '../../components/ui/EmptyState';

interface PageProps { signOut?: () => void; user?: any; }

const CarbonPage: React.FC<PageProps> = ({ signOut, user }) => (
  <Layout user={user} onSignOut={signOut}>
    <div style={{ padding: '24px 32px' }}>
      <EmptyState icon="default" title="Carbon Dashboard" description="Sustainability and carbon tracking features coming soon." />
    </div>
  </Layout>
);

export default CarbonPage;
