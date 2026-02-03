/**
 * Link Index - Redirects to Create
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const LinkIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/link/create');
  }, [router]);

  return null;
};

export default LinkIndex;
