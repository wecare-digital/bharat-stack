import React from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';

interface PageProps { signOut?: () => void; user?: any; }

const DocsRedirect: React.FC<PageProps> = ({ signOut, user }) => {
  const router = useRouter();
  React.useEffect(() => { router.replace('/engage/documents'); }, [router]);
  return (
    <Layout user={user} onSignOut={signOut}>
      <div style={{ padding: '24px 32px', textAlign: 'center', color: '#6b7280' }}>Redirecting to Drop Docs...</div>
    </Layout>
  );
};

export default DocsRedirect;
