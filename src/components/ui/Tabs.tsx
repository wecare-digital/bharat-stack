/**
 * Tabs Component - WECARE.DIGITAL
 * Unified tabs with ARIA roles and keyboard navigation
 */

import React, { useRef, useCallback } from 'react';

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
  const tabsRef = useRef<HTMLDivElement>(null);

  const handleClick = (id: string, disabled?: boolean) => {
    if (disabled) return;
    onChange(id);
  };

  const handleKeyDown = useCallback((e: React.KeyboardEvent, index: number) => {
    const enabledItems = items.filter(i => !i.disabled);
    const currentEnabledIndex = enabledItems.findIndex(i => i.id === items[index].id);
    let nextIndex = -1;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (currentEnabledIndex + 1) % enabledItems.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (currentEnabledIndex - 1 + enabledItems.length) % enabledItems.length;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = enabledItems.length - 1;
    }

    if (nextIndex >= 0) {
      const nextItem = enabledItems[nextIndex];
      onChange(nextItem.id);
      const btn = tabsRef.current?.querySelector(`[data-tab-id="${nextItem.id}"]`) as HTMLElement;
      btn?.focus();
    }
  }, [items, onChange]);

  return (
    <div
      ref={tabsRef}
      className={`tabs tabs-${variant} ${className}`}
      role="tablist"
      aria-orientation="horizontal"
    >
      {items.map((item, index) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={activeTab === item.id}
          aria-controls={`tabpanel-${item.id}`}
          tabIndex={activeTab === item.id ? 0 : -1}
          data-tab-id={item.id}
          className={`tab-btn ${activeTab === item.id ? 'active' : ''}`}
          onClick={() => handleClick(item.id, item.disabled)}
          onKeyDown={(e) => handleKeyDown(e, index)}
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
