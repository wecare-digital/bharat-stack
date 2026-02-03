/**
 * Pay Index - Redirects to Link
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const PayIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/pay/link');
  }, [router]);

  return null;
};

export default PayIndex;
