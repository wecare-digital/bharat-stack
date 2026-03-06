/**
 * Access Page - Login entry point
 * URL: https://stack.wecare.digital/access
 * 
 * This page shows the login form (via _app.tsx Authenticator).
 * After successful login, redirects to /dashboard.
 */

import React, { useEffect } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const AccessPage: React.FC<PageProps> = ({ user }) => {
  const router = useRouter();

  // If user is authenticated (passed from _app.tsx), redirect to dashboard
  useEffect(() => {
    if (user) {
      router.replace('/dashboard');
    }
  }, [user, router]);

  // Show redirecting message (user is authenticated at this point)
  return (
    <>
      <Head>
        <title>Access | WECARE.DIGITAL</title>
      </Head>
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: '#f5f5f5'
      }}>
        <div style={{ textAlign: 'center' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 300, color: '#1a1a1a', marginBottom: '16px' }}>
            WECARE.DIGITAL
          </h1>
          <p style={{ color: '#666' }}>Redirecting to dashboard...</p>
        </div>
      </div>
    </>
  );
};

export default AccessPage;
