/**
 * Coming Soon Component
 * Consistent placeholder for pages under development
 * Enhanced responsive design
 */

import Layout from './Layout';
import PageHeader from './PageHeader';
import SEO from './SEO';
import { IconMap } from '../lib/icons';

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

export default function ComingSoon({
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
}: ComingSoonProps) {
  const Icon = icon ? IconMap[icon] : null;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title={`${title} | WECARE.DIGITAL`}
        description={subtitle || 'Coming soon'}
      />
      <div className="hub-page">
        <PageHeader 
          title={title}
          subtitle={subtitle}
          icon={icon}
          backLink={backLink}
          backLabel={backLabel}
        />

        <div className="coming-soon-page">
          {Icon && (
            <div className="coming-soon-icon">
              <Icon size={40} />
            </div>
          )}
          
          <h2 className="coming-soon-title">Coming Soon</h2>
          <p className="coming-soon-subtitle">{subtitle || 'This feature is under development'}</p>
          
          {features && features.length > 0 && (
            <div className="coming-soon-features">
              <h3>Planned Features</h3>
              <ul>
                {features.map((feature, index) => (
                  <li key={index}>{feature}</li>
                ))}
              </ul>
            </div>
          )}

          {docsUrl && (
            <div className="coming-soon-docs">
              <a href={docsUrl} target="_blank" rel="noopener noreferrer">
                {docsLabel || 'View Documentation'} →
              </a>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
