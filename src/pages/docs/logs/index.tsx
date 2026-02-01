/**
 * Docs - Document Logs
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const DocsLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Document History"
      subtitle="View all documents"
      icon="logs"
      backLink="/docs"
      backLabel="← Docs"
      features={[
        'Document History',
        'Version Control',
        'Search & Filter',
        'Export Options',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default DocsLogsPage;
