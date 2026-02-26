/**
 * Tab-level Error Boundary
 * Catches errors within individual dashboard tabs without crashing the whole page.
 */
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  tabName: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class TabErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[${this.props.tabName}] Tab error:`, error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⚠️</div>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.1rem', color: '#1a1a1a' }}>
            {this.props.tabName} tab encountered an error
          </h3>
          <p style={{ color: '#666', fontSize: '0.9rem', margin: '0 0 1rem' }}>
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              padding: '8px 20px', background: '#111', color: '#fff',
              border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: '0.9rem',
            }}
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default TabErrorBoundary;
