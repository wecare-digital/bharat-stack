/**
 * Voice DM Hub - Provider Selection
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
  { href: '/dm/voice/airtel', label: 'IN Voice', sublabel: 'Airtel IQ' },
  { href: '/dm/voice/aws', label: 'AWS Connect', sublabel: 'Global' },
];

export default function VoiceDMHub({ signOut, user }: PageProps) {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Voice | WECARE.DIGITAL"
        description="Make voice calls via Airtel IQ or AWS Connect"
      />
      <div className="hub-page">
        <PageHeader 
          title="Voice" 
          subtitle="Select voice provider"
          icon="voice"
          backLink="/dm"
          backLabel="← Messages"
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
