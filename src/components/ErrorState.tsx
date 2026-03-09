/**
 * Reusable error state component for pages that fail to load data.
 * Prevents blank pages by always showing a message + retry button.
 */
import React from 'react';

interface ErrorStateProps {
  message?: string;
  detail?: string;
  onRetry?: () => void;
}

const ErrorState: React.FC<ErrorStateProps> = ({
  message = 'Something went wrong',
  detail,
  onRetry,
}) => (
  <div style={{
    textAlign: 'center',
    padding: '48px 24px',
    maxWidth: 400,
    margin: '0 auto',
  }}>
    <div style={{ marginBottom: 12 }}><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div>
    <p style={{ fontSize: 16, fontWeight: 600, color: '#374151', margin: '0 0 8px' }}>{message}</p>
    {detail && <p style={{ fontSize: 13, color: '#6b7280', margin: '0 0 16px' }}>{detail}</p>}
    {onRetry && (
      <button
        onClick={onRetry}
        style={{
          padding: '8px 20px',
          background: '#1a3a2a',
          color: '#fff',
          border: 'none',
          borderRadius: 8,
          cursor: 'pointer',
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        Retry
      </button>
    )}
  </div>
);

export default ErrorState;
