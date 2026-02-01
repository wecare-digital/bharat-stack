import React from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import { SmsIcon } from '../../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

export default function SmsDMHub({ signOut, user }: PageProps) {
  return (
    <Layout user={user} onSignOut={signOut}>
      <div style={{ padding: '24px' }}>
        <PageHeader 
          title="SMS" 
          subtitle="Select SMS provider"
          icon="sms"
          backLink="/dm"
          backLabel="Back"
        />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', maxWidth: '300px', margin: '0 auto' }}>
          <Link href="/dm/sms/airtel" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px 16px', background: '#f5f5f5', borderRadius: '12px', textDecoration: 'none', color: '#000' }}>
            <span style={{ marginBottom: '8px' }}><SmsIcon size={28} /></span>
            <span style={{ fontSize: '14px', fontWeight: 500 }}>Airtel IQ</span>
          </Link>
          <Link href="/dm/sms/aws" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px 16px', background: '#f5f5f5', borderRadius: '12px', textDecoration: 'none', color: '#000' }}>
            <span style={{ marginBottom: '8px' }}><SmsIcon size={28} /></span>
            <span style={{ fontSize: '14px', fontWeight: 500 }}>AWS Pinpoint</span>
          </Link>
        </div>
      </div>
    </Layout>
  );
}
