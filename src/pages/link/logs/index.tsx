/**
 * Link Logs Page - Coming Soon
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
      title="Link Analytics"
      subtitle="Track link clicks, conversions, and engagement"
      icon="logs"
      backLink="/link"
      backLabel="← Links"
      features={[
        'Click Tracking',
        'Geo Analytics',
        'Device Stats',
        'Conversion Rate',
        'UTM Parameters',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default LinkLogsPage;
