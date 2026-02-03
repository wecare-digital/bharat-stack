/**
 * RCS Inbox Page
 * Rich Communication Services inbox - Coming Soon
 */

import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Breadcrumbs from '../../../components/ui/Breadcrumbs';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const RcsInbox: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="RCS Inbox | WECARE.DIGITAL" description="RCS inbox" />
      <div className="rcs-page">
        <Breadcrumbs />
        <h2 className="page-title">RCS Inbox</h2>
        
        <div className="coming-soon-card">
          <div className="icon">💬</div>
          <h3>RCS Inbox Coming Soon</h3>
          <p>Rich Communication Services with rich media, carousels, and interactive buttons</p>
          <div className="features">
            {['Rich Media', 'Carousels', 'Quick Replies', 'Branded Messages', 'Read Receipts'].map(f => (
              <span key={f} className="feature-tag">{f}</span>
            ))}
          </div>
          <a href="https://www.airtel.in/business/b2b/airtel-iq/api-docs/rcs/overview" target="_blank" rel="noopener noreferrer" className="docs-link">
            View RCS API Docs →
          </a>
        </div>
      </div>

      <style jsx>{`
        .rcs-page {
          padding: 20px;
        }
        .page-title {
          margin: 12px 0 20px;
        }
        .coming-soon-card {
          background: #f5f5f5;
          border: 1px solid #e5e5e5;
          border-radius: 12px;
          padding: 60px 20px;
          text-align: center;
        }
        .icon {
          font-size: 48px;
          margin-bottom: 16px;
        }
        .coming-soon-card h3 {
          margin: 0 0 8px;
          color: #000;
        }
        .coming-soon-card p {
          margin: 0 0 16px;
          color: #6b7280;
        }
        .features {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          justify-content: center;
          margin-top: 20px;
        }
        .feature-tag {
          padding: 6px 12px;
          background: #fff;
          color: #000;
          border: 1px solid #e5e5e5;
          border-radius: 20px;
          font-size: 13px;
        }
        .docs-link {
          display: inline-block;
          margin-top: 24px;
          color: #000;
          font-weight: 500;
        }
        .docs-link:hover {
          text-decoration: underline;
        }
      `}</style>
    </Layout>
  );
};

export default RcsInbox;
