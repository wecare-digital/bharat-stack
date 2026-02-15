/**
 * PageShell Component - WECARE.DIGITAL
 * Wraps inner pages with section header + scrollable tab bar.
 * Sits between Layout's breadcrumbs and page content.
 * Does NOT break existing pages — just wraps them.
 */

import React, { useState } from 'react';

export interface ShellTab {
  id: string;
  label: string;
  icon?: string;
}

interface PageShellProps {
  title: string;
  subtitle?: string;
  tabs: ShellTab[];
  defaultTab?: string;
  actions?: React.ReactNode;
  children: (activeTab: string) => React.ReactNode;
  className?: string;
}

const PageShell: React.FC<PageShellProps> = ({
  title,
  subtitle,
  tabs,
  defaultTab,
  actions,
  children,
  className = '',
}) => {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id || '');

  return (
    <div className={`page-shell ${className}`}>
      {/* Section Header */}
      <div className="ps-header">
        <div className="ps-header-left">
          <h1 className="ps-title">{title}</h1>
          {subtitle && <p className="ps-subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="ps-header-actions">{actions}</div>}
      </div>

      {/* Scrollable Tab Bar */}
      <div className="ps-tabs-wrapper">
        <div className="ps-tabs" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`ps-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="ps-content" role="tabpanel">
        {children(activeTab)}
      </div>
    </div>
  );
};

export default PageShell;
