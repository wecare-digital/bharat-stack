/**
 * RCS Index - Redirects to Messages
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const RcsIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/rcs/messages');
  }, [router]);

  return null;
};

export default RcsIndex;
