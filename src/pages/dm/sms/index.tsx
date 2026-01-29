/**
 * SMS DM Hub - SMS Provider Selection
 * Choose between Airtel IQ SMS and AWS Pinpoint SMS
 */

import React from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const SMS_PROVIDERS = [
  {
    id: 'airtel',
    name: 'Airtel IQ SMS',
    icon: '📱',
    description: 'SMS via Airtel IQ Gateway',
    href: '/dm/sms/airtel',
    status: 'active',
    features: ['Transactional SMS', 'Promotional SMS', 'DLT Compliance', 'India Coverage'],
  },
  {
    id: 'aws',
    name: 'AWS Pinpoint SMS',
    icon: '☎️',
    description: 'SMS via Amazon Pinpoint',
    href: '/dm/sms/aws',
    status: 'active',
    features: ['Global Coverage', 'Two-way SMS', 'Delivery Reports', 'SNS Integration'],
  },
];

const SmsDMHub: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="page">
        <PageHeader 
          title="SMS" 
          subtitle="Select SMS provider"
          icon="sms"
          backLink="/dm"
          backLabel="← DM Hub"
        />

        <div className="providers-grid">
          {SMS_PROVIDERS.map((provider) => (
            <Link key={provider.id} href={provider.href} className="provider-card">
              <div className="provider-icon">{provider.icon}</div>
              <div className="provider-info">
                <h3 className="provider-name">{provider.name}</h3>
                <p className="provider-desc">{provider.description}</p>
                <div className="provider-features">
                  {provider.features.map((f, i) => (
                    <span key={i} className="feature-tag">{f}</span>
                  ))}
                </div>
              </div>
              <span className="provider-arrow">→</span>
            </Link>
          ))}
        </div>
      </div>

      <style jsx>{`
        .page-header { margin-bottom: 24px; }
        .back-link { color: #666; text-decoration: none; font-size: 14px; }
        .page-title { font-size: 24px; font-weight: 500; margin: 8px 0 4px 0; }
        .page-subtitle { color: #666; margin: 0; }
        .providers-grid { display: grid; gap: 16px; max-width: 600px; }
        .provider-card { display: flex; align-items: flex-start; gap: 16px; padding: 20px 24px; background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; text-decoration: none; color: inherit; transition: all 0.2s; }
        .provider-card:hover { border-color: #1a1a1a; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        .provider-icon { font-size: 36px; }
        .provider-info { flex: 1; }
        .provider-name { font-size: 18px; font-weight: 500; margin: 0 0 4px 0; }
        .provider-desc { font-size: 14px; color: #666; margin: 0 0 12px 0; }
        .provider-features { display: flex; flex-wrap: wrap; gap: 6px; }
        .feature-tag { font-size: 11px; background: #f5f5f5; padding: 3px 8px; border-radius: 4px; color: #666; }
        .provider-arrow { font-size: 24px; color: #ccc; align-self: center; }
      `}</style>
    </Layout>
  );
};

export default SmsDMHub;
