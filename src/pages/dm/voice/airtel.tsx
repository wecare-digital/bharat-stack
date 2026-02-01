/**
 * IN Voice DM
 * Voice calls via IN Voice API
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const INVoiceDM: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="IN Voice"
      subtitle="Voice API for India"
      icon="voice"
      backLink="/dm/voice"
      backLabel="← Voice"
      features={[
        'Outbound Voice Calls',
        'Click-to-Call Widget',
        'IVR Builder',
        'Call Recording',
        'Call Analytics',
        'DND Compliance',
      ]}
      docsUrl="https://www.airtel.in/business/b2b/airtel-iq/api-docs/voice/callflow-component-apis"
      docsLabel="IN Voice API Docs"
      user={user}
      signOut={signOut}
    />
  );
};

export default INVoiceDM;
