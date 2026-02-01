/**
 * Pay Hub - Quick Action Cards
 */

import React from 'react';
import Link from 'next/link';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import { WhatsAppIcon, LinkIcon, LogsIcon } from '../../lib/icons';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const PayHubPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="hub-page">
        <PageHeader 
          title="Payments" 
          subtitle="Send payment requests and track transactions"
          icon="payment"
        />

        <div className="actions-grid">
          <Link href="/pay/wa" className="action-card">
            <span className="icon"><WhatsAppIcon size={28} /></span>
            <span>WhatsApp Pay</span>
          </Link>
          <Link href="/pay/link" className="action-card">
            <span className="icon"><LinkIcon size={28} /></span>
            <span>Pay Link</span>
          </Link>
          <Link href="/pay/logs" className="action-card">
            <span className="icon"><LogsIcon size={28} /></span>
            <span>Logs</span>
          </Link>
        </div>
      </div>

      <style jsx>{`
        .hub-page { padding: 24px; }
        
        .actions-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 16px;
          max-width: 450px;
          margin: 0 auto;
        }
        
        .action-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 24px 16px;
          background: #f5f5f5;
          border-radius: 12px;
          text-decoration: none;
          color: #000;
          transition: all 0.2s ease;
          border: 1px solid transparent;
        }
        
        .action-card:hover {
          background: #fff;
          border-color: #e5e5e5;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
        }
        
        .action-card .icon {
          margin-bottom: 8px;
          color: #000;
        }
        
        .action-card span:last-child {
          font-size: 14px;
          font-weight: 500;
        }
        
        @media (max-width: 480px) {
          .hub-page { padding: 16px; }
          .actions-grid { gap: 12px; }
          .action-card { padding: 20px 12px; }
          .action-card .icon { margin-bottom: 6px; }
          .action-card span:last-child { font-size: 13px; }
        }
      `}</style>
    </Layout>
  );
};

export default PayHubPage;
