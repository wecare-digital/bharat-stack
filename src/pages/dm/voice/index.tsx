/**
 * Voice Index - Redirects to Voice IN Calls
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const VoiceIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/voice-in/calls');
  }, [router]);

  return null;
};

export default VoiceIndex;
