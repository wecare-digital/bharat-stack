/**
 * Forms - Create New Form
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
      subtitle="Build custom forms for data collection"
      icon="create"
      backLink="/forms"
      backLabel="← Forms"
      features={[
        'Drag & Drop Builder',
        'Custom Fields',
        'Conditional Logic',
        'Validation Rules',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default FormsCreatePage;
