/**
 * Forms Logs Page - Coming Soon
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const FormsLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Form Submissions"
      subtitle="View and manage form submissions"
      icon="logs"
      backLink="/forms"
      backLabel="Forms"
      features={[
        'View Submissions',
        'Export to CSV',
        'Filter & Search',
        'Submission Analytics',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default FormsLogsPage;
