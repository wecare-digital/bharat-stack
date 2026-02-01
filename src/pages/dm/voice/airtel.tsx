/**
 * Airtel IQ Voice DM
 * Voice calls via Airtel IQ Voice API
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const AirtelVoiceDM: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Airtel IQ Voice"
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
      docsLabel="Airtel IQ Voice API Docs"
      user={user}
      signOut={signOut}
    />
  );
};

export default AirtelVoiceDM;
