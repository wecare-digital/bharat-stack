/**
 * SEO Properties — Google Search Console properties
 */
import React, { useState, useEffect } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import * as seoApi from '../../api/seo';

interface PageProps { signOut?: () => void; user?: any; }

const SEOProperties: React.FC<PageProps> = ({ signOut, user }) => {
  const [properties, setProperties] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    seoApi.listProperties().then(setProperties).catch(() => []).finally(() => setLoading(false));
  }, []);

  async function handleSync() {
    setSyncing(true);
    try {
      await seoApi.syncProperties();
      const updated = await seoApi.listProperties();
      setProperties(updated);
    } catch (e: any) { alert(e.message); }
    finally { setSyncing(false); }
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SEO Properties" />
      <div className="inner-page">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 className="inner-page-title" style={{ margin: 0 }}>Search Console Properties</h1>
          <button className="btn btn-primary" onClick={handleSync} disabled={syncing}>
            {syncing ? 'Syncing...' : 'Sync Properties'}
          </button>
        </div>
        <div className="card" style={{ overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                <th style={{ padding: '10px 12px' }}>Site URL</th>
                <th style={{ padding: '10px 12px' }}>Permission</th>
                <th style={{ padding: '10px 12px' }}>Active</th>
                <th style={{ padding: '10px 12px' }}>Last Synced</th>
              </tr>
            </thead>
            <tbody>
              {properties.map(p => (
                <tr key={p.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '10px 12px', fontWeight: 500 }}>{p.site_url}</td>
                  <td style={{ padding: '10px 12px' }}>{p.permission_level || '—'}</td>
                  <td style={{ padding: '10px 12px' }}>{p.is_active ? '✓' : '✗'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: '#6b7280' }}>{p.last_synced_at || 'Never'}</td>
                </tr>
              ))}
              {properties.length === 0 && !loading && (
                <tr><td colSpan={4} style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>No properties. Connect Google account and sync.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
};

export default SEOProperties;
