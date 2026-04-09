/**
 * Admin — Redirects to Project Control Center
 * All admin functionality is now under /dashboard/system-architecture
 */
import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function AdminIndex() {
  const router = useRouter();
  useEffect(() => { router.replace('/dashboard/system-architecture'); }, [router]);
  return null;
}
