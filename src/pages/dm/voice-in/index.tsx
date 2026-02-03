/**
 * Voice IN Index - Redirects to Inbox
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const VoiceInIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/voice-in/inbox');
  }, [router]);

  return null;
};

export default VoiceInIndex;
