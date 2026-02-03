/**
 * RCS Index - Redirects to Inbox
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const RcsIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/rcs/inbox');
  }, [router]);

  return null;
};

export default RcsIndex;
