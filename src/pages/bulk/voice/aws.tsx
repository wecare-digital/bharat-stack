/**
 * Bulk AWS Voice Campaigns
 * Voice campaigns via Amazon Pinpoint
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const BulkAWSVoice: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Bulk Voice - AWS Pinpoint"
      subtitle="Voice campaigns via Amazon Pinpoint"
      icon="voice"
      backLink="/bulk/voice"
      backLabel="← Bulk Voice"
      features={[
        'Text-to-Speech (Polly)',
        'SSML Support',
        'Multiple Voices',
        'Global Coverage',
        'Event Tracking',
      ]}
      docsUrl="https://docs.aws.amazon.com/pinpoint/latest/developerguide/send-voice-message.html"
      docsLabel="AWS Pinpoint Voice Docs"
      user={user}
      signOut={signOut}
    />
  );
};

export default BulkAWSVoice;
