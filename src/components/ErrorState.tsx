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
    <div style={{ fontSize: 36, marginBottom: 12 }}>⚠️</div>
    <p style={{ fontSize: 16, fontWeight: 600, color: '#374151', margin: '0 0 8px' }}>{message}</p>
    {detail && <p style={{ fontSize: 13, color: '#6b7280', margin: '0 0 16px' }}>{detail}</p>}
    {onRetry && (
      <button
        onClick={onRetry}
        style={{
          padding: '8px 20px',
          background: '#059669',
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
