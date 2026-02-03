/**
 * Voice Index - Redirects to Inbox
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const VoiceIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/voice/inbox');
  }, [router]);

  return null;
};

export default VoiceIndex;
