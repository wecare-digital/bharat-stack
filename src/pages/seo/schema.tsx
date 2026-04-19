/**
 * SEO Schema — Structured data coverage overview
 */
import React, { useState, useEffect } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import * as seoApi from '../../api/seo';

interface PageProps { signOut?: () => void; user?: any; }

const SEOSchema: React.FC<PageProps> = ({ signOut, user }) => {
  const [coverage, setCoverage] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    seoApi.getSchemaCoverage().then(setCoverage).catch(() => null).finally(() => setLoading(false));
  }, []);

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SEO Schema" description="Structured data and schema markup for wecare.digital" />
      <div className="inner-page">
        <h1 className="inner-page-title">Structured Data / Schema</h1>
        {coverage && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
            <StatCard label="Total" value={coverage.total} />
            <StatCard label="Valid" value={coverage.valid} color="#16a34a" />
            <StatCard label="Invalid" value={coverage.invalid} color="#dc2626" />
            <StatCard label="Missing" value={coverage.missing} color="#d97706" />
            <StatCard label="Draft" value={coverage.draft} />
          </div>
        )}
        {loading && <div className="card" style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>Loading...</div>}
      </div>
    </Layout>
  );
};

function StatCard({ label, value, color }: { label: string; value: any; color?: string }) {
  return (
    <div className="card" style={{ padding: '16px 20px' }}>
      <div style={{ fontSize: 12, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, marginTop: 4, color: color || '#1a3a2a' }}>{value ?? '—'}</div>
    </div>
  );
}

export default SEOSchema;
