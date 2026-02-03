/**
 * SMS IN Messages Page
 * Inbound SMS messages via Airtel IQ
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { EmptyState } from '../../../components/ui';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const SmsInMessagesPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<api.Message[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listMessages(undefined, 'SMS');
      const inbound = data.filter(m => m.direction === 'INBOUND');
      setMessages(inbound.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()));
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredMessages = messages.filter(m =>
    m.content?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    m.contactId?.includes(searchQuery)
  );

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS IN Messages | WECARE.DIGITAL" description="Inbound SMS messages" />
      <div className="inner-page-container">
        <div className="inner-page-header">
          <div className="inner-page-header-content">
            <h1 className="inner-page-title">SMS IN - Messages</h1>
          </div>
          <div className="inner-page-actions">
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>

        <div className="inner-section">
          <input
            type="text"
            placeholder="Search messages..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="search-input"
            aria-label="Search messages"
          />
        </div>

        <div className="inner-card">
          {filteredMessages.length === 0 ? (
            <EmptyState
              icon="📥"
              title="No Inbound SMS"
              description="Inbound SMS messages will appear here"
            />
          ) : (
            <div className="messages-list-container">
              {filteredMessages.map(m => (
                <div key={m.messageId} className="message-item">
                  <div className="message-item-header">
                    <span className="message-item-sender">{m.contactId}</span>
                    <span className="message-item-time">{new Date(m.timestamp).toLocaleString()}</span>
                  </div>
                  <p className="message-item-content">{m.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default SmsInMessagesPage;
