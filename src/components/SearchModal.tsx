/**
 * Global Search Modal Component
 * Quick search across contacts, messages, and navigation
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/router';

interface SearchResult {
  id: string;
  type: 'contact' | 'message' | 'page' | 'action';
  title: string;
  subtitle?: string;
  icon: string;
  path?: string;
  action?: () => void;
}

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  contacts?: { id: string; name: string; phone: string }[];
  messages?: { id: string; content: string; contactId: string }[];
}

const NAVIGATION_ITEMS: SearchResult[] = [
  { id: 'nav-dashboard', type: 'page', title: 'Dashboard', subtitle: 'Overview & stats', icon: '⊞', path: '/dashboard' },
  { id: 'nav-messages', type: 'page', title: 'WhatsApp Inbox', subtitle: 'Messages', icon: '◇', path: '/dm/whatsapp' },
  { id: 'nav-contacts', type: 'page', title: 'Contacts', subtitle: 'Manage contacts', icon: '⊕', path: '/contacts' },
  { id: 'nav-templates', type: 'page', title: 'Templates', subtitle: 'WhatsApp templates', icon: '⎙', path: '/dm/whatsapp/templates' },
  { id: 'nav-bulk', type: 'page', title: 'Bulk Messages', subtitle: 'Send bulk campaigns', icon: '⫶', path: '/bulk/whatsapp' },
  { id: 'nav-pay', type: 'page', title: 'Payments', subtitle: 'WhatsApp Pay', icon: '◈', path: '/pay' },
  { id: 'nav-billing', type: 'page', title: 'Billing', subtitle: 'AWS costs', icon: '⧉', path: '/dashboard/billing' },
  { id: 'nav-ai', type: 'page', title: 'AI Config', subtitle: 'Bedrock settings', icon: '◇', path: '/dm/whatsapp/ai-config' },
];

const DEFAULT_RESULTS = NAVIGATION_ITEMS.slice(0, 6);

const SearchModal: React.FC<SearchModalProps> = ({ isOpen, onClose, contacts = [], messages = [] }) => {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>(DEFAULT_RESULTS);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setResults(DEFAULT_RESULTS);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Search logic - only run when query changes
  useEffect(() => {
    if (!query.trim()) {
      return; // Keep default results
    }

    const q = query.toLowerCase();
    const searchResults: SearchResult[] = [];

    // Search navigation
    NAVIGATION_ITEMS.forEach(item => {
      if (item.title.toLowerCase().includes(q) || item.subtitle?.toLowerCase().includes(q)) {
        searchResults.push(item);
      }
    });

    // Search contacts
    contacts.forEach(contact => {
      if (contact.name?.toLowerCase().includes(q) || contact.phone?.includes(q)) {
        searchResults.push({
          id: `contact-${contact.id}`,
          type: 'contact',
          title: contact.name || contact.phone,
          subtitle: contact.phone,
          icon: '👤',
          path: `/dm/whatsapp?contact=${contact.id}`,
        });
      }
    });

    // Search messages (limited)
    messages.slice(0, 100).forEach(msg => {
      if (msg.content?.toLowerCase().includes(q)) {
        searchResults.push({
          id: `msg-${msg.id}`,
          type: 'message',
          title: msg.content.substring(0, 50) + (msg.content.length > 50 ? '...' : ''),
          subtitle: `Message`,
          icon: '💬',
        });
      }
    });

    setResults(searchResults.slice(0, 10));
    setSelectedIndex(0);
  }, [query, contacts, messages]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      e.preventDefault();
      const result = results[selectedIndex];
      if (result.path) {
        router.push(result.path);
        onClose();
      } else if (result.action) {
        result.action();
        onClose();
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  }, [results, selectedIndex, router, onClose]);

  if (!isOpen) return null;

  return (
    <div className="search-overlay" onClick={onClose}>
      <div className="search-modal" onClick={e => e.stopPropagation()}>
        <div className="search-input-wrapper">
          <span className="search-icon">Search</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search contacts, messages, pages..."
          />
          <span className="search-hint">ESC to close</span>
        </div>
        
        <div className="search-results">
          {results.length === 0 ? (
            <div className="search-empty">
              <span>No results found</span>
            </div>
          ) : (
            results.map((result, index) => (
              <div
                key={result.id}
                className={`search-result-item ${index === selectedIndex ? 'selected' : ''}`}
                onClick={() => {
                  if (result.path) {
                    router.push(result.path);
                    onClose();
                  } else if (result.action) {
                    result.action();
                    onClose();
                  }
                }}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <div className="search-result-icon">{result.icon}</div>
                <div className="search-result-info">
                  <div className="search-result-title">{result.title}</div>
                  {result.subtitle && (
                    <div className="search-result-subtitle">{result.subtitle}</div>
                  )}
                </div>
                <div className="search-result-type">{result.type}</div>
              </div>
            ))
          )}
        </div>
        
        <div className="search-footer">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>ESC Close</span>
        </div>
      </div>

      <style jsx>{`
        .search-hint {
          font-size: 12px;
          color: #9ca3af;
          padding: 4px 8px;
          background: #f3f4f6;
          border-radius: 4px;
        }
        .search-result-type {
          font-size: 10px;
          color: #9ca3af;
          text-transform: uppercase;
          padding: 2px 6px;
          background: #f3f4f6;
          border-radius: 4px;
        }
        .search-footer {
          display: flex;
          gap: 16px;
          padding: 12px 20px;
          background: #f9fafb;
          border-top: 1px solid #e5e7eb;
          font-size: 12px;
          color: #6b7280;
        }
      `}</style>
    </div>
  );
};

export default SearchModal;
