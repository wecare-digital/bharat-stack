/**
 * SMS IN Index - Redirects to SMS (merged page)
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const SmsInIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/sms');
  }, [router]);

  return null;
};

export default SmsInIndex;
