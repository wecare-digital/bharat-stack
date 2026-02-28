/**
 * Messages Tab — Search and browse messages with pagination
 */
import React, { useState } from 'react';
import Button from '../../../components/ui/Button';
import type { DashboardData } from '../../../types/dashboard';

interface MessagesTabProps {
  data: DashboardData;
}

const PAGE_SIZE = 30;

const MessagesTab: React.FC<MessagesTabProps> = ({ data }) => {
  const { contacts, messages } = data;
  const [searchQuery, setSearchQuery] = useState('');
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const filteredMessages = searchQuery.trim()
    ? messages.filter(m =>
        m.content?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contacts.find(c => c.id === m.contactId)?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contacts.find(c => c.id === m.contactId)?.phone?.includes(searchQuery),
      )
    : messages;

  const visibleMessages = filteredMessages.slice(0, visibleCount);
  const hasMore = visibleCount < filteredMessages.length;

  return (
    <div className="messages-tab">
      <div className="search-bar">
        <input
          type="search"
          placeholder="Search messages..."
          value={searchQuery}
          onChange={e => { setSearchQuery(e.target.value); setVisibleCount(PAGE_SIZE); }}
          aria-label="Search messages"
        />
        {searchQuery && <button onClick={() => { setSearchQuery(''); setVisibleCount(PAGE_SIZE); }} aria-label="Clear search">×</button>}
      </div>

      <div style={{ fontSize: '12px', color: '#6b7280', padding: '8px 0' }}>
        Showing {visibleMessages.length} of {filteredMessages.length} messages
      </div>

      <div className="msg-list full">
        {visibleMessages.map(msg => {
          const contact = contacts.find(c => c.id === msg.contactId);
          return (
            <div key={msg.id} className={`msg-item ${msg.direction.toLowerCase()}`}>
              <span className="dir">{msg.direction === 'INBOUND' ? '↓' : '↑'}</span>
              <span className="name">{contact?.name || contact?.phone || '...'}</span>
              <span className="content">{msg.content?.slice(0, 60) || '[Media]'}</span>
              <span className="time">{new Date(msg.timestamp).toLocaleString()}</span>
              <span className="status">{msg.status}</span>
            </div>
          );
        })}
        {filteredMessages.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">No messages found</div>
            <div className="empty-state-description">
              {searchQuery ? 'Try different search terms.' : 'Messages will appear here once received.'}
            </div>
          </div>
        )}
      </div>

      {hasMore && (
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <Button variant="secondary" size="sm" onClick={() => setVisibleCount(prev => prev + PAGE_SIZE)}>
            Load More ({filteredMessages.length - visibleCount} remaining)
          </Button>
        </div>
      )}
    </div>
  );
};

export default MessagesTab;
