/**
 * Forms Create Page - Coming Soon
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const FormsCreatePage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Create Form"
      subtitle="Create custom forms with drag-and-drop builder"
      icon="create"
      backLink="/forms"
      backLabel="← Forms"
      features={[
        'Drag & Drop Builder',
        'Custom Fields',
        'Validation Rules',
        'Conditional Logic',
        'File Uploads',
        'Submission Tracking',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default FormsCreatePage;
