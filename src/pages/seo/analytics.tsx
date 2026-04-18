/**
 * SEO Analytics — Search Console performance data
 */
import React, { useState, useEffect } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import * as seoApi from '../../api/seo';

interface PageProps { signOut?: () => void; user?: any; }

const SEOAnalytics: React.FC<PageProps> = ({ signOut, user }) => {
  const [data, setData] = useState<any>(null);
  const [hilc, setHilc] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      seoApi.getSearchConsoleAnalytics().then(setData).catch(() => null),
      seoApi.getHighImpressionLowCtr().then(setHilc).catch(() => []),
    ]).finally(() => setLoading(false));
  }, []);

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SEO Analytics" />
      <div className="inner-page">
        <h1 className="inner-page-title">Search Analytics</h1>
        {data && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
            <StatCard label="Clicks (30d)" value={data.total_clicks?.toLocaleString()} />
            <StatCard label="Impressions (30d)" value={data.total_impressions?.toLocaleString()} />
            <StatCard label="Avg Position" value={data.avg_position} />
            <StatCard label="Avg CTR" value={`${((data.avg_ctr || 0) * 100).toFixed(2)}%`} />
          </div>
        )}
        {hilc.length > 0 && (
          <div className="card">
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>High Impressions, Low CTR</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                  <th style={{ padding: '8px 12px' }}>Page</th>
                  <th style={{ padding: '8px 12px' }}>Impressions</th>
                  <th style={{ padding: '8px 12px' }}>Clicks</th>
                  <th style={{ padding: '8px 12px' }}>CTR</th>
                  <th style={{ padding: '8px 12px' }}>Avg Position</th>
                </tr>
              </thead>
              <tbody>
                {hilc.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '8px 12px', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.page_url}</td>
                    <td style={{ padding: '8px 12px' }}>{r.impressions?.toLocaleString()}</td>
                    <td style={{ padding: '8px 12px' }}>{r.clicks}</td>
                    <td style={{ padding: '8px 12px' }}>{((r.avg_ctr || 0) * 100).toFixed(2)}%</td>
                    <td style={{ padding: '8px 12px' }}>{r.avg_position?.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {loading && <div className="card" style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>Loading analytics...</div>}
      </div>
    </Layout>
  );
};

function StatCard({ label, value }: { label: string; value: any }) {
  return (
    <div className="card" style={{ padding: '16px 20px' }}>
      <div style={{ fontSize: 12, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, marginTop: 4, color: '#1a3a2a' }}>{value ?? '—'}</div>
    </div>
  );
}

export default SEOAnalytics;
