/**
 * Confirm Dialog Context
 * Replaces browser window.confirm() with a themed modal dialog.
 * Usage: const confirm = useConfirm();
 *        if (await confirm('Delete 25 contacts?')) { ... }
 */

import React, { createContext, useContext, useState, useCallback, useRef, ReactNode } from 'react';

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'default';
}

type ConfirmFn = (messageOrOptions: string | ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | undefined>(undefined);

interface DialogState {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  cancelText: string;
  variant: 'danger' | 'warning' | 'default';
}

export const ConfirmProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [dialog, setDialog] = useState<DialogState>({
    isOpen: false, title: 'Confirm', message: '', confirmText: 'Confirm',
    cancelText: 'Cancel', variant: 'default',
  });
  const resolveRef = useRef<((value: boolean) => void) | null>(null);

  const confirm: ConfirmFn = useCallback((messageOrOptions) => {
    const opts: ConfirmOptions = typeof messageOrOptions === 'string'
      ? { message: messageOrOptions }
      : messageOrOptions;

    // Auto-detect variant from message content
    let variant = opts.variant || 'default';
    if (!opts.variant) {
      const lower = opts.message.toLowerCase();
      if (lower.includes('delete') || lower.includes('remove') || lower.includes('clear') || lower.includes('cancel')) {
        variant = 'danger';
      } else if (lower.includes('warning') || lower.includes('reset') || lower.includes('undo')) {
        variant = 'warning';
      }
    }

    setDialog({
      isOpen: true,
      title: opts.title || (variant === 'danger' ? 'Are you sure?' : 'Confirm'),
      message: opts.message,
      confirmText: opts.confirmText || (variant === 'danger' ? 'Delete' : 'Confirm'),
      cancelText: opts.cancelText || 'Cancel',
      variant,
    });

    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  const handleClose = useCallback((result: boolean) => {
    setDialog(prev => ({ ...prev, isOpen: false }));
    resolveRef.current?.(result);
    resolveRef.current = null;
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') handleClose(false);
    if (e.key === 'Enter') handleClose(true);
  }, [handleClose]);

  const variantColors = {
    danger: { bg: '#dc2626', hover: '#b91c1c', icon: '&#9888;' },
    warning: { bg: '#d97706', hover: '#b45309', icon: '&#9888;' },
    default: { bg: '#059669', hover: '#047857', icon: '&#10003;' },
  };
  const colors = variantColors[dialog.variant];

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {dialog.isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-dialog-title"
          aria-describedby="confirm-dialog-message"
          onKeyDown={handleKeyDown}
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.4)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', zIndex: 10000,
            padding: '20px', backdropFilter: 'blur(2px)',
          }}
          onClick={() => handleClose(false)}
        >
          <div
            style={{
              background: '#fff', borderRadius: '12px', width: '100%', maxWidth: '420px',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)',
              overflow: 'hidden', animation: 'confirmSlideIn 0.15s ease-out',
            }}
            onClick={e => e.stopPropagation()}
          >
            {/* Header accent */}
            <div style={{ height: '3px', background: colors.bg }} />

            <div style={{ padding: '24px 24px 0' }}>
              {/* Icon + Title */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '50%',
                  background: dialog.variant === 'danger' ? '#fef2f2' : dialog.variant === 'warning' ? '#fffbeb' : '#ecfdf5',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  {dialog.variant === 'danger' ? (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
                    </svg>
                  ) : dialog.variant === 'warning' ? (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
                    </svg>
                  )}
                </div>
                <h3 id="confirm-dialog-title" style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#111827' }}>
                  {dialog.title}
                </h3>
              </div>

              {/* Message */}
              <p id="confirm-dialog-message" style={{
                margin: '0 0 24px', fontSize: '14px', lineHeight: '1.5', color: '#4b5563',
                paddingLeft: '48px',
              }}>
                {dialog.message}
              </p>
            </div>

            {/* Actions */}
            <div style={{
              display: 'flex', justifyContent: 'flex-end', gap: '8px',
              padding: '16px 24px', background: '#f9fafb', borderTop: '1px solid #f3f4f6',
            }}>
              <button
                onClick={() => handleClose(false)}
                autoFocus={dialog.variant === 'danger'}
                style={{
                  padding: '8px 16px', border: '1px solid #d1d5db', borderRadius: '8px',
                  background: '#fff', color: '#374151', fontSize: '14px', fontWeight: 500,
                  cursor: 'pointer', transition: 'background 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = '#f3f4f6')}
                onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
              >
                {dialog.cancelText}
              </button>
              <button
                onClick={() => handleClose(true)}
                autoFocus={dialog.variant !== 'danger'}
                style={{
                  padding: '8px 16px', border: 'none', borderRadius: '8px',
                  background: colors.bg, color: '#fff', fontSize: '14px', fontWeight: 500,
                  cursor: 'pointer', transition: 'background 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = colors.hover)}
                onMouseLeave={e => (e.currentTarget.style.background = colors.bg)}
              >
                {dialog.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes confirmSlideIn {
          from { opacity: 0; transform: scale(0.95) translateY(-10px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </ConfirmContext.Provider>
  );
};

export const useConfirm = (): ConfirmFn => {
  const context = useContext(ConfirmContext);
  if (!context) {
    throw new Error('useConfirm must be used within a ConfirmProvider');
  }
  return context;
};

export default ConfirmContext;
