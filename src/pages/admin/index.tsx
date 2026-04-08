/**
 * Admin Index — Redirects to Project Control Center
 * All admin functionality is now unified under /admin/system-architecture
 */
import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function AdminIndex() {
  const router = useRouter();
  useEffect(() => { router.replace('/admin/system-architecture'); }, [router]);
  return null;
}
