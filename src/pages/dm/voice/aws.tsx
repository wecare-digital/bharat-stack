/**
 * AWS Voice DM
 * Voice calls via Amazon Connect / Pinpoint Voice
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const AWSVoiceDM: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="AWS Voice"
      subtitle="Amazon Connect & Pinpoint"
      icon="voice"
      backLink="/dm/voice"
      backLabel="← Voice"
      features={[
        'Amazon Connect Contact Center',
        'Omnichannel Routing',
        'AI-powered IVR',
        'Pinpoint Voice Campaigns',
        'Text-to-Speech',
        'Global Coverage',
      ]}
      docsUrl="https://docs.aws.amazon.com/connect/"
      docsLabel="Amazon Connect Docs"
      user={user}
      signOut={signOut}
    />
  );
};

export default AWSVoiceDM;
