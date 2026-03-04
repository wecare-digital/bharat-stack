/**
 * Confirm Dialog Context
 * Replaces browser window.confirm() with a themed modal dialog.
 * Site theme: Emerald #059669 throughout.
 * Usage: const confirm = useConfirm();
 *        if (await confirm('Delete 25 contacts?')) { ... }
 */

import React, { createContext, useContext, useState, useCallback, useRef, ReactNode } from 'react';

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
}

type ConfirmFn = (messageOrOptions: string | ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | undefined>(undefined);

interface DialogState {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  cancelText: string;
}

export const ConfirmProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [dialog, setDialog] = useState<DialogState>({
    isOpen: false, title: 'Confirm', message: '', confirmText: 'Confirm', cancelText: 'Cancel',
  });
  const resolveRef = useRef<((value: boolean) => void) | null>(null);

  const confirm: ConfirmFn = useCallback((messageOrOptions) => {
    const opts: ConfirmOptions = typeof messageOrOptions === 'string'
      ? { message: messageOrOptions } : messageOrOptions;

    const lower = opts.message.toLowerCase();
    const isDestructive = ['delete', 'remove', 'clear', 'cancel', 'reset'].some(k => lower.includes(k));

    setDialog({
      isOpen: true,
      title: opts.title || (isDestructive ? 'Are you sure?' : 'Confirm'),
      message: opts.message,
      confirmText: opts.confirmText || (isDestructive ? 'Yes, proceed' : 'Confirm'),
      cancelText: opts.cancelText || 'Cancel',
    });

    return new Promise<boolean>((resolve) => { resolveRef.current = resolve; });
  }, []);

  const handleClose = useCallback((result: boolean) => {
    setDialog(prev => ({ ...prev, isOpen: false }));
    resolveRef.current?.(result);
    resolveRef.current = null;
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {dialog.isOpen && (
        <div
          role="dialog" aria-modal="true"
          aria-labelledby="confirm-title" aria-describedby="confirm-msg"
          onKeyDown={e => { if (e.key === 'Escape') handleClose(false); if (e.key === 'Enter') handleClose(true); }}
          onClick={() => handleClose(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 10000, padding: '20px', backdropFilter: 'blur(2px)',
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: '#fff', borderRadius: '12px', width: '100%', maxWidth: '380px',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)', overflow: 'hidden',
              animation: 'confirmIn 0.15s ease-out',
            }}
          >
            {/* Accent bar */}
            <div style={{ height: '3px', background: '#059669' }} />

            <div style={{ padding: '20px 20px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <div style={{
                  width: '32px', height: '32px', borderRadius: '50%', background: '#ecfdf5',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
                  </svg>
                </div>
                <h3 id="confirm-title" style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#111827' }}>
                  {dialog.title}
                </h3>
              </div>
              <p id="confirm-msg" style={{
                margin: '0 0 20px', fontSize: '13px', lineHeight: 1.5, color: '#4b5563', paddingLeft: '42px',
              }}>
                {dialog.message}
              </p>
            </div>

            <div style={{
              display: 'flex', justifyContent: 'flex-end', gap: '8px',
              padding: '12px 20px', background: '#f9fafb', borderTop: '1px solid #f3f4f6',
            }}>
              <button
                onClick={() => handleClose(false)} autoFocus
                style={{
                  padding: '7px 16px', border: '1px solid #d1d5db', borderRadius: '8px',
                  background: '#fff', color: '#374151', fontSize: '13px', fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                {dialog.cancelText}
              </button>
              <button
                onClick={() => handleClose(true)}
                style={{
                  padding: '7px 16px', border: 'none', borderRadius: '8px',
                  background: '#059669', color: '#fff', fontSize: '13px', fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                {dialog.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
      <style>{`@keyframes confirmIn { from { opacity:0; transform:scale(.96) translateY(-8px); } to { opacity:1; transform:scale(1) translateY(0); } }`}</style>
    </ConfirmContext.Provider>
  );
};

export const useConfirm = (): ConfirmFn => {
  const context = useContext(ConfirmContext);
  if (!context) throw new Error('useConfirm must be used within a ConfirmProvider');
  return context;
};

export default ConfirmContext;
