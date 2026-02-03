/**
 * Docs Index - Redirects to Create
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const DocsIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/docs/create');
  }, [router]);

  return null;
};

export default DocsIndex;
