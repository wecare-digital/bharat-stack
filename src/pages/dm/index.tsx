/**
 * DM Hub - Direct Messaging Hub
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
  { href: '/dm/whatsapp', icon: WhatsAppIcon, label: 'WhatsApp', variant: 'whatsapp' },
  { href: '/dm/sms', icon: SmsIcon, label: 'SMS', variant: 'sms' },
  { href: '/dm/ses', icon: EmailIcon, label: 'Email', variant: 'email' },
  { href: '/dm/voice', icon: VoiceIcon, label: 'Voice', variant: 'voice' },
  { href: '/dm/rcs', icon: RcsIcon, label: 'RCS', variant: 'rcs' },
  { href: '/dm/logs', icon: LogsIcon, label: 'Logs', variant: '' },
];

export default function DMHub({ signOut, user }: PageProps) {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Direct Messaging | WECARE.DIGITAL"
        description="Send messages across all channels - WhatsApp, SMS, Email, Voice, RCS"
      />
      <div className="hub-page">
        <PageHeader 
          title="Direct Messaging" 
          subtitle="Send messages across all channels"
          icon="message"
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
