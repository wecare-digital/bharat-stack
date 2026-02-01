/**
 * Forms - Submission Logs
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
      subtitle="View all form submission logs"
      icon="logs"
      backLink="/forms"
      backLabel="← Forms"
      features={[
        'Submission History',
        'Export to CSV',
        'Filter & Search',
        'Response Analytics',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default FormsLogsPage;
