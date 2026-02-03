/**
 * Docs Logs Page - Coming Soon
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
      title="Document Logs"
      subtitle="Track document views, downloads, and signatures"
      icon="logs"
      backLink="/docs"
      backLabel="← Documents"
      features={[
        'View History',
        'Download Logs',
        'Signature Status',
        'Document Analytics',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default DocsLogsPage;
