/**
 * Voice Index - Redirects to AWS Voice
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const VoiceIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/voice/aws');
  }, [router]);

  return null;
};

export default VoiceIndex;
