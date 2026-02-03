/**
 * WhatsApp Board Page
 * WABA Dashboard with phone numbers, system events, templates, welcome config
 */

import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import WABADashboard from './waba-dashboard';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const WhatsAppBoardPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="WhatsApp Board | WECARE.DIGITAL"
        description="WhatsApp Business Account Dashboard"
      />
      <WABADashboard embedded={true} />
    </Layout>
  );
};

export default WhatsAppBoardPage;
