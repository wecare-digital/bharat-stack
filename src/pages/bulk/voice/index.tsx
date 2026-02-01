/**
 * Bulk Voice Hub - Provider Selection
 * Clean, responsive design
 */

import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import { VoiceIcon } from '../../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const providers = [
  { href: '/bulk/voice/airtel', label: 'IN Voice', sublabel: 'Airtel IQ' },
  { href: '/bulk/voice/aws', label: 'AWS Pinpoint', sublabel: 'Global' },
];

export default function BulkVoiceHub({ signOut, user }: PageProps) {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Bulk Voice | WECARE.DIGITAL"
        description="Make bulk voice calls via Airtel IQ or AWS Pinpoint"
      />
      <div className="hub-page">
        <PageHeader 
          title="Bulk Voice" 
          subtitle="Select voice provider"
          icon="voice"
          backLink="/bulk"
          backLabel="← Bulk"
        />

        <div className="hub-grid hub-grid-2">
          {providers.map(({ href, label, sublabel }) => (
            <Link key={href} href={href} className="hub-card hub-card-voice">
              <span className="hub-icon"><VoiceIcon size={32} /></span>
              <span className="hub-label">{label}</span>
              <span className="hub-sublabel">{sublabel}</span>
            </Link>
          ))}
        </div>
      </div>
    </Layout>
  );
}
