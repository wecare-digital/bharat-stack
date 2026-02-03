/**
 * WhatsApp Index - Redirects to Inbox
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

const WhatsAppIndex = () => {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/dm/whatsapp/inbox');
  }, [router]);

  return null;
};

export default WhatsAppIndex;
