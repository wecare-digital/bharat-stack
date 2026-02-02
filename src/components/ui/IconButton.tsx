/**
 * IconButton Component - WECARE.DIGITAL
 * Unified icon-only button with tooltip and accessibility
 * Used for: Refresh, Close, Settings, etc.
 */

import React from 'react';
import Spinner from './Spinner';

export type IconButtonSize = 'sm' | 'md' | 'lg';

// Icon components
const RefreshIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 4v6h-6" />
    <path d="M1 20v-6h6" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

const CloseIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const SettingsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const icons: Record<string, React.FC> = {
  refresh: RefreshIcon,
  close: CloseIcon,
  settings: SettingsIcon,
};

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: 'refresh' | 'close' | 'settings';
  ariaLabel: string;
  tooltip?: string;
  size?: IconButtonSize;
  loading?: boolean;
  variant?: 'default' | 'ghost' | 'danger';
}

const IconButton: React.FC<IconButtonProps> = ({
  icon,
  ariaLabel,
  tooltip,
  size = 'md',
  loading = false,
  disabled = false,
  variant = 'default',
  className = '',
  ...props
}) => {
  const IconComponent = icons[icon];
  const isDisabled = disabled || loading;

  return (
    <button
      type="button"
      className={`icon-btn icon-btn-${size} icon-btn-${variant} ${loading ? 'icon-btn-loading' : ''} ${className}`}
      disabled={isDisabled}
      aria-label={ariaLabel}
      title={tooltip || ariaLabel}
      {...props}
    >
      {loading ? <Spinner size={size === 'lg' ? 'md' : 'sm'} /> : <IconComponent />}
    </button>
  );
};

export default IconButton;
