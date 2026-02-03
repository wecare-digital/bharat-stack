/**
 * SMS Index - Redirects to SMS IN Messages
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const SmsIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/sms-in/messages');
  }, [router]);

  return null;
};

export default SmsIndex;
