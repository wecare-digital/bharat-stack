/**
 * SMS IN Index - Redirects to Messages
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const SmsInIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/sms-in/messages');
  }, [router]);

  return null;
};

export default SmsInIndex;
