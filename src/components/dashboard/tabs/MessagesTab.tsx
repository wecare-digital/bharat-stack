/**
 * Messages Tab — Search and browse messages
 */
import React, { useState } from 'react';
import type { DashboardData } from '../../../types/dashboard';

interface MessagesTabProps {
  data: DashboardData;
}

const MessagesTab: React.FC<MessagesTabProps> = ({ data }) => {
  const { contacts, messages } = data;
  const [searchQuery, setSearchQuery] = useState('');

  const filteredMessages = searchQuery.trim()
    ? messages.filter(m =>
        m.content?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contacts.find(c => c.id === m.contactId)?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contacts.find(c => c.id === m.contactId)?.phone?.includes(searchQuery),
      )
    : messages;

  return (
    <div className="messages-tab">
      <div className="search-bar">
        <input
          type="text"
          placeholder="Search messages..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          aria-label="Search messages"
        />
        {searchQuery && <button onClick={() => setSearchQuery('')}>×</button>}
      </div>

      <div className="msg-list full">
        {filteredMessages.slice(0, 50).map(msg => {
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
        {filteredMessages.length === 0 && <div className="empty">No messages found</div>}
      </div>
    </div>
  );
};

export default MessagesTab;
