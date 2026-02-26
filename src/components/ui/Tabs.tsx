/**
 * Tabs Component - WECARE.DIGITAL
 * Unified tabs for inner pages
 */

import React from 'react';

export interface TabItem {
  id: string;
  label: string;
  count?: number;
  disabled?: boolean;
}

interface TabsProps {
  items: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  variant?: 'main' | 'sub';
  className?: string;
}

const Tabs: React.FC<TabsProps> = ({
  items,
  activeTab,
  onChange,
  variant = 'main',
  className = '',
}) => {
  const handleClick = (id: string, disabled?: boolean) => {
    if (disabled) return;
    onChange(id);
  };

  return (
    <div 
      className={`tabs tabs-${variant} ${className}`}
      role="tablist"
    >
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`tab-btn ${activeTab === item.id ? 'active' : ''}`}
          onClick={() => handleClick(item.id, item.disabled)}
          disabled={item.disabled || false}
        >
          {item.label}
          {item.count !== undefined && (
            <span className="tab-count">({item.count})</span>
          )}
        </button>
      ))}
    </div>
  );
};

export default Tabs;
