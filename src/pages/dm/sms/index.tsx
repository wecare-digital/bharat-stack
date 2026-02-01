import React from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { SmsIcon } from '../../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const providers = [
  { href: '/dm/sms/airtel', label: 'IN SMS', sublabel: 'Airtel' },
  { href: '/dm/sms/aws', label: 'AWS Pinpoint', sublabel: 'Global' },
];

export default function SmsDMHub({ signOut, user }: PageProps) {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="SMS | WECARE.DIGITAL"
        description="Send SMS via Airtel or AWS Pinpoint"
      />
      <div className="hub-page">
        <PageHeader 
          title="SMS" 
          subtitle="Select SMS provider"
          icon="sms"
          backLink="/dm"
          backLabel="← Messages"
        />

        <div className="hub-grid hub-grid-2">
          {providers.map(({ href, label, sublabel }) => (
            <Link key={href} href={href} className="hub-card hub-card-sms">
              <span className="hub-icon"><SmsIcon size={32} /></span>
              <span className="hub-label">{label}</span>
              <span className="hub-sublabel">{sublabel}</span>
            </Link>
          ))}
        </div>
      </div>
    </Layout>
  );
}
