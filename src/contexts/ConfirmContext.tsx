/**
 * Confirm Dialog Context
 * Unified confirm dialog for the entire app.
 * Site theme: Lime #d1f470 + Dark #1a3a2a.
 *
 * Usage:
 *   const confirm = useConfirm();
 *   if (await confirm('Delete 25 contacts?')) { ... }
 *   if (await confirm({ title: 'Hard Delete', message: <p>Gone forever</p>, confirmInput: 'DELETE', danger: true })) { ... }
 */

import React, { createContext, useContext, useState, useCallback, useRef, useEffect, ReactNode } from 'react';

interface ConfirmOptions {
  title?: string;
  message: ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmInput?: string;   // If set, user must type this exact string to enable confirm
  danger?: boolean;        // Red-tinted destructive action styling
}

type ConfirmFn = (messageOrOptions: string | ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | undefined>(undefined);

interface DialogState {
  isOpen: boolean;
  title: string;
  message: ReactNode;
  confirmText: string;
  cancelText: string;
  confirmInput?: string;
  danger: boolean;
}

export const ConfirmProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [dialog, setDialog] = useState<DialogState>({
    isOpen: false, title: 'Confirm', message: '', confirmText: 'Confirm', cancelText: 'Cancel', danger: false,
  });
  const [inputValue, setInputValue] = useState('');
  const resolveRef = useRef<((value: boolean) => void) | null>(null);

  // Reset input when dialog closes
  useEffect(() => {
    if (!dialog.isOpen) setInputValue('');
  }, [dialog.isOpen]);

  const confirm: ConfirmFn = useCallback((messageOrOptions) => {
    const opts: ConfirmOptions = typeof messageOrOptions === 'string'
      ? { message: messageOrOptions } : messageOrOptions;

    const msgStr = typeof opts.message === 'string' ? opts.message.toLowerCase() : '';
    const isDestructive = opts.danger || ['delete', 'remove', 'clear', 'cancel', 'reset'].some(k => msgStr.includes(k));

    setDialog({
      isOpen: true,
      title: opts.title || (isDestructive ? 'Are you sure?' : 'Confirm'),
      message: opts.message,
      confirmText: opts.confirmText || (isDestructive ? 'Yes, proceed' : 'Confirm'),
      cancelText: opts.cancelText || 'Cancel',
      confirmInput: opts.confirmInput,
      danger: opts.danger || false,
    });

    return new Promise<boolean>((resolve) => { resolveRef.current = resolve; });
  }, []);

  const handleClose = useCallback((result: boolean) => {
    setDialog(prev => ({ ...prev, isOpen: false }));
    resolveRef.current?.(result);
    resolveRef.current = null;
  }, []);

  const canConfirm = !dialog.confirmInput || inputValue === dialog.confirmInput;

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {dialog.isOpen && (
        <div
          role="dialog" aria-modal="true"
          aria-labelledby="confirm-title" aria-describedby="confirm-msg"
          onKeyDown={e => { if (e.key === 'Escape') handleClose(false); if (e.key === 'Enter' && canConfirm) handleClose(true); }}
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
              background: '#fff', borderRadius: '13px', width: '100%', maxWidth: '420px',
              boxShadow: '0 8px 30px rgba(0,0,0,0.12)', overflow: 'hidden',
              animation: 'confirmIn 0.15s ease-out',
              border: '1.5px solid #d1f470',
            }}
          >
            {/* Accent bar */}
            <div style={{ height: '6px', background: dialog.danger ? '#dc2626' : '#d1f470' }} />

            <div style={{ padding: '20px 20px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <div style={{
                  width: '32px', height: '32px', borderRadius: '50%',
                  background: dialog.danger ? '#fef2f2' : '#f9fafb',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  {dialog.danger ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
                    </svg>
                  )}
                </div>
                <h3 id="confirm-title" style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#1a1a1a' }}>
                  {dialog.title}
                </h3>
              </div>
              <div id="confirm-msg" style={{
                margin: '0 0 16px', fontSize: '13px', lineHeight: 1.5, color: 'rgba(0, 0, 0, 0.54)', paddingLeft: '42px',
              }}>
                {dialog.message}
              </div>

              {/* Type-to-confirm input */}
              {dialog.confirmInput && (
                <div style={{ paddingLeft: '42px', marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '12px', color: '#6b7280', marginBottom: '6px', fontWeight: 500 }}>
                    Type &quot;{dialog.confirmInput}&quot; to confirm:
                  </label>
                  <input
                    type="text"
                    value={inputValue}
                    onChange={e => setInputValue(e.target.value)}
                    placeholder={dialog.confirmInput}
                    autoFocus
                    style={{
                      width: '100%', padding: '8px 12px', border: '1.5px solid #d1f470',
                      borderRadius: '13px', fontSize: '13px', outline: 'none',
                      boxSizing: 'border-box',
                    }}
                    onFocus={e => { e.target.style.borderColor = dialog.danger ? '#dc2626' : '#1a3a2a'; e.target.style.boxShadow = '0 0 0 3px rgba(209,244,112,0.3)'; }}
                    onBlur={e => { e.target.style.borderColor = '#d1f470'; e.target.style.boxShadow = 'none'; }}
                  />
                </div>
              )}
            </div>

            <div style={{
              display: 'flex', justifyContent: 'flex-end', gap: '8px',
              padding: '12px 20px', background: '#f9fafb', borderTop: '1px solid #f3f4f6',
            }}>
              <button
                onClick={() => handleClose(false)}
                autoFocus={!dialog.confirmInput}
                style={{
                  padding: '7px 16px', border: '1.5px solid #d1f470', borderRadius: '13px',
                  background: '#fff', color: '#374151', fontSize: '13px', fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                {dialog.cancelText}
              </button>
              <button
                onClick={() => handleClose(true)}
                disabled={!canConfirm}
                style={{
                  padding: '7px 16px', border: 'none', borderRadius: '13px',
                  background: !canConfirm ? '#d1d5db' : (dialog.danger ? '#dc2626' : '#d1f470'),
                  color: dialog.danger ? '#fff' : '#1a3a2a', fontSize: '13px', fontWeight: 500,
                  cursor: canConfirm ? 'pointer' : 'not-allowed',
                  opacity: canConfirm ? 1 : 0.6,
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
