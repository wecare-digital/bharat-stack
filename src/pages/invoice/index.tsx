/**
 * Invoice Index - Redirects to Create
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const InvoiceIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/invoice/create');
  }, [router]);

  return null;
};

export default InvoiceIndex;
