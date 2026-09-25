/**
 * Keyboard Shortcuts Modal - WECARE.DIGITAL
 * Shows available keyboard shortcuts
 */

import React, { useEffect, useState } from 'react';
import { lockScroll, unlockScroll } from '../../lib/scrollLock';

interface Shortcut {
  keys: string[];
  description: string;
  category: string;
}

const SHORTCUTS: Shortcut[] = [
  // Navigation
  { keys: ['Ctrl', 'K'], description: 'Open search', category: 'Navigation' },
  { keys: ['/'], description: 'Focus search', category: 'Navigation' },
  { keys: ['Esc'], description: 'Close modal / Clear search', category: 'Navigation' },
  
  // Actions
  { keys: ['Ctrl', 'S'], description: 'Save (in forms)', category: 'Actions' },
  { keys: ['Ctrl', 'Enter'], description: 'Submit / Send', category: 'Actions' },
  
  // Help
  { keys: ['?'], description: 'Show keyboard shortcuts', category: 'Help' },
];

interface KeyboardShortcutsProps {
  isOpen: boolean;
  onClose: () => void;
}

const KeyboardShortcuts: React.FC<KeyboardShortcutsProps> = ({ isOpen, onClose }) => {
  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);
  
  // Prevent page scroll when open. See src/lib/scrollLock.ts for why this is not
  // `document.body.style.overflow` any more: the page scrolls inside the DOCUMENT, not
  // inside body, so locking body alone would fail silently.
  useEffect(() => {
    if (isOpen) {
      lockScroll();
    } else {
      unlockScroll();
    }
    return () => { unlockScroll(); };
  }, [isOpen]);
  
  if (!isOpen) return null;
  
  // Group shortcuts by category
  const categories = SHORTCUTS.reduce((acc, shortcut) => {
    if (!acc[shortcut.category]) acc[shortcut.category] = [];
    acc[shortcut.category].push(shortcut);
    return acc;
  }, {} as Record<string, Shortcut[]>);
  
  return (
    <div className="shortcuts-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="shortcuts-title">
      <div className="shortcuts-modal" onClick={e => e.stopPropagation()}>
        <div className="shortcuts-header">
          <h2 id="shortcuts-title">Keyboard Shortcuts</h2>
          <button className="shortcuts-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        
        <div className="shortcuts-content">
          {Object.entries(categories).map(([category, shortcuts]) => (
            <div key={category} className="shortcuts-category">
              <h3 className="shortcuts-category-title">{category}</h3>
              <ul className="shortcuts-list">
                {shortcuts.map((shortcut, index) => (
                  <li key={index} className="shortcuts-item">
                    <span className="shortcuts-description">{shortcut.description}</span>
                    <span className="shortcuts-keys">
                      {shortcut.keys.map((key, i) => (
                        <React.Fragment key={i}>
                          <kbd className="shortcuts-key">{key}</kbd>
                          {i < shortcut.keys.length - 1 && <span className="shortcuts-plus">+</span>}
                        </React.Fragment>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        
        <div className="shortcuts-footer">
          <span className="shortcuts-hint">Press <kbd>?</kbd> to toggle this panel</span>
        </div>
      </div>
    </div>
  );
};

export default KeyboardShortcuts;

// Hook to manage keyboard shortcuts modal
export function useKeyboardShortcutsModal() {
  const [isOpen, setIsOpen] = useState(false);
  
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if typing in input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        return;
      }
      
      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setIsOpen(prev => !prev);
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);
  
  return { isOpen, setIsOpen, open: () => setIsOpen(true), close: () => setIsOpen(false) };
}
