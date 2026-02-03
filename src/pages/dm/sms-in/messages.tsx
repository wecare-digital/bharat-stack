/**
 * SMS IN Messages Page
 * Inbound SMS messages via Airtel IQ
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
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
      // Filter for inbound messages
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
      <div style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ margin: 0 }}>SMS IN - Messages</h2>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <input
            type="text"
            placeholder="Search messages..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              maxWidth: '300px',
              padding: '10px 14px',
              border: '1.5px solid #d1d5db',
              borderRadius: '13px',
              fontSize: '14px'
            }}
          />
        </div>

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', overflow: 'hidden' }}>
          {filteredMessages.length === 0 ? (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: '#6b7280' }}>
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>📥</div>
              <h3 style={{ margin: '0 0 8px', color: '#111827' }}>No Inbound SMS</h3>
              <p style={{ margin: 0 }}>Inbound SMS messages will appear here</p>
            </div>
          ) : (
            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
              {filteredMessages.map(m => (
                <div key={m.messageId} style={{ padding: '16px', borderBottom: '1px solid #e5e7eb' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 600, color: '#111827' }}>{m.contactId}</span>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>{new Date(m.timestamp).toLocaleString()}</span>
                  </div>
                  <p style={{ margin: 0, color: '#374151', fontSize: '14px' }}>{m.content}</p>
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
