/**
 * Voice IN Index - Redirects to Calls
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const VoiceInIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/voice-in/calls');
  }, [router]);

  return null;
};

export default VoiceInIndex;
