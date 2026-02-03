/**
 * SMS Index - Redirects to AWS SMS
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const SmsIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/sms/aws');
  }, [router]);

  return null;
};

export default SmsIndex;
