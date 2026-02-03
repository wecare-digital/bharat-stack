/**
 * Forms Index - Redirects to Create
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const FormsIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/forms/create');
  }, [router]);

  return null;
};

export default FormsIndex;
