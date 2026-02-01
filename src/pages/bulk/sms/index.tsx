/**
 * Bulk SMS Hub - Provider Selection
 * Clean, responsive design
 */

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
  { href: '/bulk/sms/airtel', label: 'IN SMS', sublabel: 'Airtel IQ' },
  { href: '/bulk/sms/aws', label: 'AWS Pinpoint', sublabel: 'Global' },
];

export default function BulkSmsHub({ signOut, user }: PageProps) {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Bulk SMS | WECARE.DIGITAL"
        description="Send bulk SMS messages via Airtel IQ or AWS Pinpoint"
      />
      <div className="hub-page">
        <PageHeader 
          title="Bulk SMS" 
          subtitle="Select SMS provider"
          icon="sms"
          backLink="/bulk"
          backLabel="← Bulk"
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
