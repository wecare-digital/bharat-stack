/**
 * Error Boundary Component
 * Catches JavaScript errors in child components and displays fallback UI
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/dashboard';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={styles.container}>
          <div style={styles.card}>
            <div style={styles.icon}>Warning</div>
            <h2 style={styles.title}>Something went wrong</h2>
            <p style={styles.message}>
              An unexpected error occurred. Please try refreshing the page.
            </p>
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details style={styles.details}>
                <summary style={styles.summary}>Error Details</summary>
                <pre style={styles.errorText}>
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}
            <div style={styles.buttons}>
              <button style={styles.primaryBtn} onClick={this.handleReload}>
                ↻ Refresh Page
              </button>
              <button style={styles.secondaryBtn} onClick={this.handleGoHome}>
                ⌂ Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
    padding: '20px',
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: '12px',
    padding: '40px',
    maxWidth: '500px',
    textAlign: 'center',
    boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
  },
  icon: {
    fontSize: '48px',
    marginBottom: '16px',
  },
  title: {
    fontSize: '24px',
    fontWeight: 600,
    color: '#1a1a1a',
    margin: '0 0 12px 0',
  },
  message: {
    fontSize: '14px',
    color: '#666',
    margin: '0 0 24px 0',
    lineHeight: 1.5,
  },
  details: {
    textAlign: 'left',
    marginBottom: '24px',
    backgroundColor: '#f9f9f9',
    borderRadius: '8px',
    padding: '12px',
  },
  summary: {
    cursor: 'pointer',
    fontWeight: 500,
    color: '#333',
  },
  errorText: {
    fontSize: '12px',
    color: '#c00',
    overflow: 'auto',
    maxHeight: '200px',
    marginTop: '12px',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  buttons: {
    display: 'flex',
    gap: '12px',
    justifyContent: 'center',
  },
  primaryBtn: {
    padding: '12px 24px',
    backgroundColor: '#1a1a1a',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 500,
  },
  secondaryBtn: {
    padding: '12px 24px',
    backgroundColor: '#fff',
    color: '#1a1a1a',
    border: '1px solid #ddd',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 500,
  },
};

export default ErrorBoundary;
