/**
 * Coming Soon Component
 * Consistent placeholder for pages under development
 */

import React from 'react';
import Layout from './Layout';
import PageHeader from './PageHeader';

interface ComingSoonProps {
  title: string;
  subtitle?: string;
  icon?: string;
  backLink?: string;
  backLabel?: string;
  features?: string[];
  docsUrl?: string;
  docsLabel?: string;
  user?: any;
  signOut?: () => void;
}

const ComingSoon: React.FC<ComingSoonProps> = ({
  title,
  subtitle,
  icon,
  backLink,
  backLabel,
  features,
  docsUrl,
  docsLabel,
  user,
  signOut,
}) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="page">
        <PageHeader 
          title={title}
          subtitle={subtitle}
          icon={icon}
          backLink={backLink}
          backLabel={backLabel}
        />

        <div className="coming-soon-container">
          <div className="coming-soon-content">
            <h2>Coming Soon</h2>
            <p>{subtitle || 'This feature is under development'}</p>
            
            {features && features.length > 0 && (
              <div className="features-box">
                <h3>Planned Features</h3>
                <ul>
                  {features.map((feature, index) => (
                    <li key={index}>{feature}</li>
                  ))}
                </ul>
              </div>
            )}

            {docsUrl && (
              <div className="docs-link">
                <a href={docsUrl} target="_blank" rel="noopener noreferrer">
                  {docsLabel || 'View Documentation'} →
                </a>
              </div>
            )}
          </div>
        </div>
      </div>

      <style jsx>{`
        .page { padding: 0; }
        .coming-soon-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 60vh;
          text-align: center;
          padding: 40px 20px;
        }
        .coming-soon-content h2 {
          font-size: 28px;
          font-weight: 600;
          color: #000;
          margin: 0 0 8px 0;
        }
        .coming-soon-content p {
          font-size: 16px;
          color: #4a4a4a;
          margin: 0 0 40px 0;
        }
        .features-box {
          background: #f5f5f5;
          border-radius: 12px;
          padding: 24px 32px;
          text-align: left;
          margin-bottom: 24px;
          max-width: 320px;
        }
        .features-box h3 {
          font-size: 14px;
          font-weight: 600;
          color: #000;
          margin: 0 0 16px 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .features-box ul {
          list-style: none;
          padding: 0;
          margin: 0;
        }
        .features-box li {
          padding: 8px 0;
          font-size: 14px;
          color: #000;
          border-bottom: 1px solid #e5e5e5;
        }
        .features-box li:last-child {
          border-bottom: none;
        }
        .docs-link a {
          color: #000;
          text-decoration: none;
          font-size: 14px;
          font-weight: 500;
        }
        .docs-link a:hover {
          text-decoration: underline;
        }
      `}</style>
    </Layout>
  );
};

export default ComingSoon;
