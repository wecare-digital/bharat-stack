/**
 * Link Logs - View all link activity
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const LinkLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Link Logs"
      subtitle="Track all link clicks and activity"
      icon="logs"
      backLink="/link"
      backLabel="← Link"
      features={[
        'Click Tracking',
        'Geographic Data',
        'Device Analytics',
        'Export Reports',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default LinkLogsPage;
