/**
 * Dashboard - Data Management Tab
 * Enhanced responsive design
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';
import * as api from '../../../api/client';
import { ContactsIcon, MessageIcon, DataIcon, RefreshIcon } from '../../../lib/icons';

interface PageProps { signOut?: () => void; user?: any; }

export default function DashboardDataPage({ signOut, user }: PageProps) {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ contacts: 0, messages: 0 });

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    try {
      const [contacts, messages] = await Promise.all([
        api.listContacts(),
        api.listMessages()
      ]);
      setStats({
        contacts: contacts.length,
        messages: messages.length
      });
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="Data Management | WECARE.DIGITAL"
        description="Manage contacts, messages, and media files"
      />
      <div className="page-content">
        <PageHeader 
          title="Data Management" 
          subtitle="Manage contacts, messages, and media files"
          icon="data"
          actions={
            <button className="btn-secondary" onClick={loadStats} disabled={loading} title="Refresh">
              {loading ? '...' : <RefreshIcon size={18} />}
            </button>
          }
        />

        {/* Stats */}
        <div className="stats-grid stats-compact">
          <div className="stat-card">
            <div className="stat-value">{stats.contacts}</div>
            <div className="stat-label">Contacts</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.messages}</div>
            <div className="stat-label">Messages</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">-</div>
            <div className="stat-label">Media</div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="section">
          <h3 className="section-title">Quick Actions</h3>
          <div className="quick-actions-grid">
            <Link href="/contacts" className="quick-action-card">
              <span className="qa-icon"><ContactsIcon size={24} /></span>
              <span className="qa-title">Contacts</span>
            </Link>
            <Link href="/dm/whatsapp" className="quick-action-card">
              <span className="qa-icon"><MessageIcon size={24} /></span>
              <span className="qa-title">Messages</span>
            </Link>
            <Link href="/dashboard/messages" className="quick-action-card">
              <span className="qa-icon"><DataIcon size={24} /></span>
              <span className="qa-title">Analytics</span>
            </Link>
          </div>
        </div>

        {/* Data Management Info */}
        <div className="section">
          <h3 className="section-title">Storage</h3>
          <p className="section-description">
            All data is stored securely in AWS DynamoDB with automatic backups. 
            Media files are stored in S3 with CloudFront CDN for fast delivery.
          </p>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '12px',
            marginTop: '16px'
          }}>
            <div style={{ 
              padding: '16px', 
              background: 'var(--color-bg-secondary)', 
              borderRadius: '12px' 
            }}>
              <div style={{ fontSize: '12px', color: 'var(--color-muted)', marginBottom: '4px' }}>
                CONTACTS TABLE
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: '13px' }}>
                base-wecare-digital-ContactsTable
              </div>
            </div>
            <div style={{ 
              padding: '16px', 
              background: 'var(--color-bg-secondary)', 
              borderRadius: '12px' 
            }}>
              <div style={{ fontSize: '12px', color: 'var(--color-muted)', marginBottom: '4px' }}>
                MESSAGES TABLE
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: '13px' }}>
                base-wecare-digital-WhatsAppOutboundTable
              </div>
            </div>
            <div style={{ 
              padding: '16px', 
              background: 'var(--color-bg-secondary)', 
              borderRadius: '12px' 
            }}>
              <div style={{ fontSize: '12px', color: 'var(--color-muted)', marginBottom: '4px' }}>
                MEDIA BUCKET
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: '13px' }}>
                auth.wecare.digital
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
