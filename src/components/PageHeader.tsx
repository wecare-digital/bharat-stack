/**
 * PageHeader Component - WECARE.DIGITAL
 * Consistent page headers with icons matching sidebar
 * Centralized layout with improved UX
 */
import React from 'react';
import Link from 'next/link';
import { IconMap } from '../lib/icons';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  icon?: string;
  backLink?: string;
  backLabel?: string;
  actions?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  icon,
  backLink,
  backLabel = '← Back',
  actions,
}) => {
  const Icon = icon ? IconMap[icon] : null;

  return (
    <div className="page-header">
      {backLink && (
        <Link href={backLink} className="back-link">
          {backLabel}
        </Link>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
        {Icon && (
          <div className="page-header-icon">
            <Icon size={24} />
          </div>
        )}
        <div className="page-header-content">
          <h1 className="page-title">{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </div>
  );
};

export default PageHeader;
