/**
 * Docs - Create New Document
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const DocsCreatePage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Create Document"
      subtitle="Create and manage documents"
      icon="create"
      backLink="/docs"
      backLabel="Docs"
      features={[
        'Rich Text Editor',
        'Templates',
        'Collaboration',
        'Version History',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default DocsCreatePage;
