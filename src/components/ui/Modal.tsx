/**
 * Reusable Modal Component
 * Focus trap, ARIA roles, keyboard navigation
 */

import React, { useEffect, useCallback, useRef } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  closeOnOverlay?: boolean;
  closeOnEsc?: boolean;
}

const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  closeOnOverlay = true,
  closeOnEsc = true,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const handleEsc = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && closeOnEsc) onClose();
  }, [onClose, closeOnEsc]);

  // Focus trap
  useEffect(() => {
    if (!isOpen) return;

    previousFocusRef.current = document.activeElement as HTMLElement;
    document.addEventListener('keydown', handleEsc);
    document.body.style.overflow = 'hidden';

    // Focus first focusable element
    const timer = setTimeout(() => {
      const modal = modalRef.current;
      if (!modal) return;
      const focusable = modal.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length > 0) focusable[0].focus();
    }, 50);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
      previousFocusRef.current?.focus();
    };
  }, [isOpen, handleEsc]);

  // Tab trap
  useEffect(() => {
    if (!isOpen) return;
    const trap = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const modal = modalRef.current;
      if (!modal) return;
      const focusable = modal.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', trap);
    return () => document.removeEventListener('keydown', trap);
  }, [isOpen]);

  if (!isOpen) return null;

  const sizeStyles = { sm: '400px', md: '500px', lg: '700px', xl: '900px' };

  return (
    <div style={overlayStyle} onClick={closeOnOverlay ? onClose : undefined}>
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        style={{ ...modalStyle, maxWidth: sizeStyles[size] }}
        onClick={e => e.stopPropagation()}
      >
        <div style={headerStyle}>
          <h2 id="modal-title" style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>{title}</h2>
          <button onClick={onClose} style={closeButtonStyle} aria-label="Close modal">×</button>
        </div>
        <div style={bodyStyle}>{children}</div>
        {footer && <div style={footerStyle}>{footer}</div>}
      </div>
    </div>
  );
};

const overlayStyle: React.CSSProperties = {
  position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
  background: 'rgba(0,0,0,0.5)', display: 'flex',
  alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  padding: '20px',
};

const modalStyle: React.CSSProperties = {
  background: '#fff', borderRadius: '16px', width: '100%',
  maxHeight: '90vh', overflow: 'hidden', display: 'flex',
  flexDirection: 'column', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)',
};

const headerStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  padding: '16px 20px', borderBottom: '1px solid #e5e7eb',
};

const closeButtonStyle: React.CSSProperties = {
  background: 'none', border: 'none', fontSize: '24px',
  cursor: 'pointer', color: '#6b7280', padding: '0 4px',
  lineHeight: 1,
};

const bodyStyle: React.CSSProperties = {
  padding: '20px', flex: 1, overflowY: 'auto',
};

const footerStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: '12px',
  padding: '16px 20px', borderTop: '1px solid #e5e7eb',
};

export default Modal;
