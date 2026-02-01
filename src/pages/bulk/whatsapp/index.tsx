/**
 * Bulk WhatsApp - WABA Selection
 * Select which WABA to use for bulk messaging
 */

import React from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import { WHATSAPP_PHONES } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const WABA_ACCOUNTS = [
  {
    id: WHATSAPP_PHONES.primary.id,
    name: WHATSAPP_PHONES.primary.name,
    phone: WHATSAPP_PHONES.primary.display,
    status: 'active',
    quality: 'GREEN',
  },
  {
    id: WHATSAPP_PHONES.secondary.id,
    name: WHATSAPP_PHONES.secondary.name,
    phone: WHATSAPP_PHONES.secondary.display,
    status: 'active',
    quality: 'GREEN',
  },
];

const BulkWhatsAppIndex: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="page">
        <PageHeader 
          title="Bulk WhatsApp" 
          subtitle="Select WABA for bulk messaging"
          icon="whatsapp"
          backLink="/bulk"
          backLabel="← Bulk Hub"
        />

        <div className="waba-grid">
          {WABA_ACCOUNTS.map((waba) => (
            <Link key={waba.id} href={`/bulk/whatsapp/${waba.id}`} className="waba-card">
              <div className="waba-icon">WA</div>
              <div className="waba-info">
                <h3 className="waba-name">{waba.name}</h3>
                <p className="waba-phone">{waba.phone}</p>
                <div className="waba-meta">
                  <span className={`quality-badge ${waba.quality.toLowerCase()}`}>
                    Quality: {waba.quality}
                  </span>
                  <span className={`status-badge ${waba.status}`}>
                    {waba.status === 'active' ? '● Active' : '○ Inactive'}
                  </span>
                </div>
              </div>
              <span className="waba-arrow">→</span>
            </Link>
          ))}
        </div>

        <style jsx>{`
          .page-header { margin-bottom: 24px; }
          .back-link { color: #666; text-decoration: none; font-size: 14px; }
          .back-link:hover { color: #1a1a1a; }
          .page-title { font-size: 24px; font-weight: 500; margin: 8px 0 4px 0; }
          .page-subtitle { color: #666; margin: 0; }
          .waba-grid { display: grid; gap: 16px; max-width: 600px; }
          .waba-card { display: flex; align-items: center; gap: 16px; padding: 20px 24px; background: #fff; border: 1px solid #000; border-radius: 13px; text-decoration: none; color: inherit; transition: all 0.2s; }
          .waba-card:hover { background: #f5f5f5; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
          .waba-icon { font-size: 36px; }
          .waba-info { flex: 1; }
          .waba-name { font-size: 18px; font-weight: 500; margin: 0 0 4px 0; }
          .waba-phone { font-size: 14px; color: #666; margin: 0 0 8px 0; }
          .waba-meta { display: flex; gap: 12px; }
          .quality-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; }
          .quality-badge.green { background: #dcfce7; color: #166534; }
          .quality-badge.yellow { background: #fef3c7; color: #92400e; }
          .quality-badge.red { background: #fee2e2; color: #991b1b; }
          .status-badge { font-size: 11px; color: #22c55e; }
          .status-badge.inactive { color: #999; }
          .waba-arrow { font-size: 24px; color: #ccc; }
        `}</style>
      </div>
    </Layout>
  );
};

export default BulkWhatsAppIndex;
