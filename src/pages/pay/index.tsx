/**
 * Pay Hub - Payments Hub
 * Clean, responsive design with enhanced UX
 */

import Link from 'next/link';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import SEO from '../../components/SEO';
import { WhatsAppIcon, LinkIcon, LogsIcon } from '../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const paymentOptions = [
  { href: '/pay/wa', icon: WhatsAppIcon, label: 'WhatsApp Pay', sublabel: 'Razorpay', variant: 'whatsapp' },
  { href: '/pay/link', icon: LinkIcon, label: 'Pay Link', sublabel: 'Share link', variant: '' },
  { href: '/pay/logs', icon: LogsIcon, label: 'Logs', sublabel: 'History', variant: '' },
];

export default function PayHub({ signOut, user }: PageProps) {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Payments | WECARE.DIGITAL"
        description="Send payment requests and track transactions"
      />
      <div className="hub-page">
        <PageHeader 
          title="Payments" 
          subtitle="Send payment requests and track transactions"
          icon="payment"
        />

        <div className="hub-grid">
          {paymentOptions.map(({ href, icon: Icon, label, sublabel, variant }) => (
            <Link 
              key={href} 
              href={href} 
              className={`hub-card ${variant ? `hub-card-${variant}` : ''}`}
            >
              <span className="hub-icon"><Icon size={32} /></span>
              <span className="hub-label">{label}</span>
              {sublabel && <span className="hub-sublabel">{sublabel}</span>}
            </Link>
          ))}
        </div>
      </div>
    </Layout>
  );
}
