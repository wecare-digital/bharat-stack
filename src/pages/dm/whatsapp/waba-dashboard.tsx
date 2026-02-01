/**
 * WABA Dashboard
 * Shows WhatsApp Business Account details, phone quality, messaging limits, and system events
 * 
 * APIs Used:
 * - GetLinkedWhatsAppBusinessAccount
 * - GetLinkedWhatsAppBusinessAccountPhoneNumber
 * - ListLinkedWhatsAppBusinessAccounts
 * - System events from webhook handler
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import Toast, { useToast } from '../../../components/Toast';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const QUALITY_COLORS: Record<string, string> = {
  GREEN: '#25D366',
  YELLOW: '#FFC107',
  RED: '#DC3545',
  UNKNOWN: '#6c757d',
};

const QUALITY_LABELS: Record<string, string> = {
  GREEN: 'High Quality',
  YELLOW: 'Medium Quality',
  RED: 'Low Quality',
  UNKNOWN: 'Unknown',
};

const WABADashboard: React.FC<PageProps> = ({ signOut, user }) => {
  const router = useRouter();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [wabas, setWabas] = useState<api.WABAAccount[]>([]);
  const [selectedWaba, setSelectedWaba] = useState<api.WABAAccount | null>(null);
  const [systemEvents, setSystemEvents] = useState<api.WABASystemEvents>({
    templateStatus: [],
    phoneQuality: [],
    accountUpdates: [],
  });
  const [activeTab, setActiveTab] = useState<'overview' | 'events'>('overview');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Load WABAs and system events in parallel
      const [wabasData, eventsData] = await Promise.all([
        api.listWABAs(),
        api.getWABASystemEvents(),
      ]);

      setWabas(wabasData);
      setSystemEvents(eventsData);

      // Auto-select first WABA if none selected
      if (wabasData.length > 0 && !selectedWaba) {
        // Load full details for first WABA
        const details = await api.getWABADetails(wabasData[0].id);
        if (details) {
          setSelectedWaba(details);
        }
      }
    } catch (err) {
      console.error('Failed to load WABA data:', err);
      toast.error('Failed to load WABA data');
    } finally {
      setLoading(false);
    }
  }, [selectedWaba]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const handleSelectWaba = async (wabaId: string) => {
    try {
      const details = await api.getWABADetails(wabaId);
      if (details) {
        setSelectedWaba(details);
      }
    } catch (err) {
      toast.error('Failed to load WABA details');
    }
  };

  const formatTimestamp = (ts: number) => {
    return new Date(ts * 1000).toLocaleString();
  };

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'APPROVED': return 'OK';
      case 'REJECTED': return 'X';
      case 'PENDING': return '...';
      case 'PAUSED': return '||';
      case 'DISABLED': return 'OFF';
      case 'FLAGGED': return '!';
      case 'UNFLAGGED': return 'OK';
      default: return '-';
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <Toast toasts={toast.toasts} onRemove={toast.removeToast} />
      <div className="page waba-dashboard">
        <PageHeader 
          title="WABA Dashboard" 
          subtitle="WhatsApp Business Account details, phone quality, and system events"
          icon="whatsapp"
          backLink="/dm/whatsapp"
          backLabel="← Back"
          actions={
            <button className="refresh-btn" onClick={loadData} disabled={loading}>
              {loading ? '...' : '↻ Refresh'}
            </button>
          }
        />

        {loading && wabas.length === 0 ? (
          <div className="loading-state">Loading WABA data...</div>
        ) : (
          <div className="dashboard-content">
            {/* WABA Selector */}
            <div className="waba-selector-section">
              <label>Select WABA:</label>
              <select
                value={selectedWaba?.id || ''}
                onChange={(e) => handleSelectWaba(e.target.value)}
              >
                {wabas.map((waba) => (
                  <option key={waba.id} value={waba.id}>
                    {waba.wabaName || waba.wabaId}
                  </option>
                ))}
              </select>
            </div>

            {/* Tabs */}
            <div className="tabs">
              <button
                className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
                onClick={() => setActiveTab('overview')}
              >
                Phone Numbers
              </button>
              <button
                className={`tab ${activeTab === 'events' ? 'active' : ''}`}
                onClick={() => setActiveTab('events')}
              >
                System Events
              </button>
            </div>

            {/* Overview Tab */}
            {activeTab === 'overview' && selectedWaba && (
              <div className="overview-section">
                {/* WABA Info Card */}
                <div className="info-card">
                  <h3>Account Information</h3>
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="label">WABA Name</span>
                      <span className="value">{selectedWaba.wabaName || 'N/A'}</span>
                    </div>
                    <div className="info-item">
                      <span className="label">WABA ID</span>
                      <span className="value code">{selectedWaba.wabaId}</span>
                    </div>
                    <div className="info-item">
                      <span className="label">Status</span>
                      <span className={`value status ${selectedWaba.registrationStatus?.toLowerCase()}`}>
                        {selectedWaba.registrationStatus || 'Unknown'}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="label">Sending</span>
                      <span className={`value ${selectedWaba.enableSending ? 'enabled' : 'disabled'}`}>
                        {selectedWaba.enableSending ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="label">Receiving</span>
                      <span className={`value ${selectedWaba.enableReceiving ? 'enabled' : 'disabled'}`}>
                        {selectedWaba.enableReceiving ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Phone Numbers */}
                <div className="phone-numbers-section">
                  <h3>Phone Numbers ({selectedWaba.phoneNumbers?.length || 0})</h3>
                  <div className="phone-cards">
                    {selectedWaba.phoneNumbers?.map((phone) => (
                      <div key={phone.phoneNumberId} className="phone-card">
                        <div className="phone-header">
                          <span className="phone-name">{phone.displayPhoneNumberName || 'Phone'}</span>
                          <span
                            className="quality-badge"
                            style={{ backgroundColor: QUALITY_COLORS[phone.qualityRating] }}
                          >
                            {QUALITY_LABELS[phone.qualityRating]}
                          </span>
                        </div>
                        <div className="phone-number">{phone.displayPhoneNumber || phone.phoneNumber}</div>
                        <div className="phone-details">
                          <div className="detail">
                            <span className="label">Phone ID</span>
                            <span className="value code">{phone.phoneNumberId}</span>
                          </div>
                          <div className="detail">
                            <span className="label">Meta ID</span>
                            <span className="value code">{phone.metaPhoneNumberId || 'N/A'}</span>
                          </div>
                          <div className="detail">
                            <span className="label">Region</span>
                            <span className="value">{phone.dataLocalizationRegion || 'Default'}</span>
                          </div>
                        </div>
                        <div className="quality-indicator">
                          <div
                            className="quality-bar"
                            style={{
                              width: phone.qualityRating === 'GREEN' ? '100%' :
                                     phone.qualityRating === 'YELLOW' ? '60%' :
                                     phone.qualityRating === 'RED' ? '30%' : '0%',
                              backgroundColor: QUALITY_COLORS[phone.qualityRating],
                            }}
                          />
                        </div>
                      </div>
                    ))}
                    {(!selectedWaba.phoneNumbers || selectedWaba.phoneNumbers.length === 0) && (
                      <div className="empty-state">No phone numbers found</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Events Tab */}
            {activeTab === 'events' && (
              <div className="events-section">
                {/* Template Status Events */}
                <div className="events-card">
                  <h3>Template Status Updates</h3>
                  <div className="events-list">
                    {systemEvents.templateStatus.length > 0 ? (
                      systemEvents.templateStatus.map((event, idx) => (
                        <div key={idx} className="event-item">
                          <span className="event-icon">{getEventIcon(event.data?.event)}</span>
                          <div className="event-content">
                            <div className="event-title">
                              {event.data?.templateName || 'Template'} - {event.data?.event}
                            </div>
                            <div className="event-details">
                              Language: {event.data?.templateLanguage || 'N/A'}
                              {event.data?.reason && event.data.reason !== 'NONE' && (
                                <span className="event-reason"> • Reason: {event.data.reason}</span>
                              )}
                            </div>
                            <div className="event-time">{formatTimestamp(event.timestamp)}</div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="empty-state">No template status events</div>
                    )}
                  </div>
                </div>

                {/* Phone Quality Events */}
                <div className="events-card">
                  <h3>Phone Quality Updates</h3>
                  <div className="events-list">
                    {systemEvents.phoneQuality.length > 0 ? (
                      systemEvents.phoneQuality.map((event, idx) => (
                        <div key={idx} className="event-item">
                          <span
                            className="event-icon quality-dot"
                            style={{ backgroundColor: QUALITY_COLORS[event.data?.qualityScore] }}
                          />
                          <div className="event-content">
                            <div className="event-title">
                              {event.data?.displayPhone || 'Phone'} - Quality: {event.data?.qualityScore}
                            </div>
                            <div className="event-details">
                              {event.data?.event && <span>Event: {event.data.event}</span>}
                              {event.data?.currentLimit && (
                                <span> • Limit: {event.data.currentLimit}</span>
                              )}
                            </div>
                            <div className="event-time">{formatTimestamp(event.timestamp)}</div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="empty-state">No phone quality events</div>
                    )}
                  </div>
                </div>

                {/* Account Updates */}
                <div className="events-card">
                  <h3>Account Updates</h3>
                  <div className="events-list">
                    {systemEvents.accountUpdates.length > 0 ? (
                      systemEvents.accountUpdates.map((event, idx) => (
                        <div key={idx} className="event-item">
                          <span className="event-icon">-</span>
                          <div className="event-content">
                            <div className="event-title">
                              {event.data?.event || 'Account Update'}
                            </div>
                            <div className="event-details">
                              {event.data?.phoneNumber && <span>Phone: {event.data.phoneNumber}</span>}
                              {event.data?.currentLimit && (
                                <span> • New Limit: {event.data.currentLimit}</span>
                              )}
                              {event.data?.restrictionType && (
                                <span className="restriction"> • Restriction: {event.data.restrictionType}</span>
                              )}
                            </div>
                            <div className="event-time">{formatTimestamp(event.timestamp)}</div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="empty-state">No account updates</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <style jsx>{`
        .waba-dashboard {
          padding: 20px;
          max-width: 1200px;
          margin: 0 auto;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .back-btn {
          background: none;
          border: 1px solid #ddd;
          padding: 8px 16px;
          border-radius: 8px;
          cursor: pointer;
        }

        .back-btn:hover {
          background: #f5f5f5;
        }

        h1 {
          margin: 0;
          font-size: 24px;
        }

        .refresh-btn {
          background: #fff;
          color: #000;
          border: 1px solid #000;
          padding: 10px 20px;
          border-radius: 13px;
          cursor: pointer;
        }

        .refresh-btn:hover {
          background: #f5f5f5;
        }

        .refresh-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .loading-state, .empty-state {
          text-align: center;
          padding: 40px;
          color: #666;
        }

        .waba-selector-section {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 20px;
        }

        .waba-selector-section select {
          padding: 10px 16px;
          border: 1px solid #ddd;
          border-radius: 8px;
          font-size: 14px;
          min-width: 300px;
        }

        .tabs {
          display: flex;
          gap: 8px;
          margin-bottom: 24px;
          border-bottom: 1px solid #eee;
          padding-bottom: 12px;
        }

        .tab {
          background: #fff;
          border: 1px solid #000;
          padding: 10px 20px;
          cursor: pointer;
          border-radius: 13px;
          font-size: 14px;
          color: #000;
        }

        .tab:hover {
          background: #f5f5f5;
        }

        .tab.active {
          background: #f5f5f5;
          color: #000;
          font-weight: 600;
        }

        .info-card {
          background: white;
          border: 1px solid #eee;
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 24px;
        }

        .info-card h3 {
          margin: 0 0 16px 0;
          font-size: 16px;
          color: #333;
        }

        .info-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: 16px;
        }

        .info-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .info-item .label {
          font-size: 12px;
          color: #666;
          text-transform: uppercase;
        }

        .info-item .value {
          font-size: 14px;
          font-weight: 500;
        }

        .info-item .value.code {
          font-family: monospace;
          font-size: 12px;
          background: #f5f5f5;
          padding: 4px 8px;
          border-radius: 4px;
        }

        .info-item .value.enabled {
          color: #25D366;
        }

        .info-item .value.disabled {
          color: #DC3545;
        }

        .phone-numbers-section h3 {
          margin: 0 0 16px 0;
        }

        .phone-cards {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
          gap: 16px;
        }

        .phone-card {
          background: white;
          border: 1px solid #eee;
          border-radius: 12px;
          padding: 16px;
        }

        .phone-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }

        .phone-name {
          font-weight: 600;
        }

        .quality-badge {
          padding: 4px 12px;
          border-radius: 20px;
          font-size: 12px;
          color: white;
        }

        .phone-number {
          font-size: 20px;
          font-weight: 600;
          margin-bottom: 12px;
          color: #333;
        }

        .phone-details {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 12px;
        }

        .phone-details .detail {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
        }

        .phone-details .label {
          color: #666;
        }

        .phone-details .value.code {
          font-family: monospace;
          background: #f5f5f5;
          padding: 2px 6px;
          border-radius: 4px;
        }

        .quality-indicator {
          height: 4px;
          background: #eee;
          border-radius: 2px;
          overflow: hidden;
        }

        .quality-bar {
          height: 100%;
          transition: width 0.3s ease;
        }

        .events-section {
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        .events-card {
          background: white;
          border: 1px solid #eee;
          border-radius: 12px;
          padding: 20px;
        }

        .events-card h3 {
          margin: 0 0 16px 0;
          font-size: 16px;
        }

        .events-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-height: 300px;
          overflow-y: auto;
        }

        .event-item {
          display: flex;
          gap: 12px;
          padding: 12px;
          background: #f9f9f9;
          border-radius: 8px;
        }

        .event-icon {
          font-size: 20px;
        }

        .event-icon.quality-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          margin-top: 4px;
        }

        .event-content {
          flex: 1;
        }

        .event-title {
          font-weight: 500;
          margin-bottom: 4px;
        }

        .event-details {
          font-size: 12px;
          color: #666;
        }

        .event-reason {
          color: #DC3545;
        }

        .restriction {
          color: #DC3545;
        }

        .event-time {
          font-size: 11px;
          color: #999;
          margin-top: 4px;
        }
      `}</style>
    </Layout>
  );
};

export default WABADashboard;
