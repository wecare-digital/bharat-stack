/**
 * SMS IN Index - Redirects to Inbox
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const SmsInIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/sms-in/inbox');
  }, [router]);

  return null;
};

export default SmsInIndex;
