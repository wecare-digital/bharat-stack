/**
 * Bulk Hub - Bulk Messaging Hub
 * Clean, responsive design with enhanced UX
 */

import Link from 'next/link';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import SEO from '../../components/SEO';
import { WhatsAppIcon, SmsIcon, EmailIcon, VoiceIcon, RcsIcon, LogsIcon } from '../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const channels = [
  { href: '/bulk/whatsapp', icon: WhatsAppIcon, label: 'WhatsApp', variant: 'whatsapp' },
  { href: '/bulk/sms', icon: SmsIcon, label: 'SMS', variant: 'sms' },
  { href: '/bulk/ses', icon: EmailIcon, label: 'Email', variant: 'email' },
  { href: '/bulk/voice', icon: VoiceIcon, label: 'Voice', variant: 'voice' },
  { href: '/bulk/rcs', icon: RcsIcon, label: 'RCS', variant: 'rcs' },
  { href: '/bulk/logs', icon: LogsIcon, label: 'Logs', variant: '' },
];

export default function BulkHub({ signOut, user }: PageProps) {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Bulk Messaging | WECARE.DIGITAL"
        description="Send messages to multiple recipients across all channels"
      />
      <div className="hub-page">
        <PageHeader 
          title="Bulk Messaging" 
          subtitle="Send messages to multiple recipients"
          icon="bulk"
        />

        <div className="hub-grid">
          {channels.map(({ href, icon: Icon, label, variant }) => (
            <Link 
              key={href} 
              href={href} 
              className={`hub-card ${variant ? `hub-card-${variant}` : ''}`}
            >
              <span className="hub-icon"><Icon size={32} /></span>
              <span className="hub-label">{label}</span>
            </Link>
          ))}
        </div>
      </div>
    </Layout>
  );
}
