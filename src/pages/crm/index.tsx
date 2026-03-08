import { useEffect } from 'react';
import { useRouter } from 'next/router';

const CrmRedirect = () => {
  const router = useRouter();
  useEffect(() => { router.replace('/'); }, [router]);
  return null;
};

export default CrmRedirect;
