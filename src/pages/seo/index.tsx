/**
 * SEO Dashboard — Overview stats for wecare.digital + stack.wecare.digital
 */
import React, { useState, useEffect } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import * as seoApi from '../../api/seo';

interface PageProps { signOut?: () => void; user?: any; }

const SEODashboard: React.FC<PageProps> = ({ signOut, user }) => {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [connected, setConnected] = useState(false);

  // Auth state for SEO backend
  const [seoToken, setSeoToken] = useState('');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem('seo_token');
    if (t) { setSeoToken(t); loadStats(); }
    else setLoading(false);
  }, []);

  async function loadStats() {
    setLoading(true);
    setError('');
    try {
      const data = await seoApi.getDashboardStats();
      setStats(data);
      setConnected(true);
    } catch (e: any) {
      setError(e.message);
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginLoading(true);
    try {
      const res = await seoApi.seoLogin(loginEmail, loginPass);
      localStorage.setItem('seo_token', res.access_token);
      setSeoToken(res.access_token);
      await loadStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoginLoading(false);
    }
  }

  async function handleRegister() {
    setLoginLoading(true);
    try {
      const res = await seoApi.seoRegister(loginEmail, loginPass, 'Admin');
      localStorage.setItem('seo_token', res.access_token);
      setSeoToken(res.access_token);
      await loadStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoginLoading(false);
    }
  }

  if (!seoToken) {
    return (
      <Layout user={user} onSignOut={signOut}>
        <SEO title="SEO Platform" description="SEO management for wecare.digital" />
        <div className="inner-page">
          <h1 className="inner-page-title">SEO Platform</h1>
          <div className="card" style={{ maxWidth: 420, margin: '40px auto' }}>
            <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Connect to SEO Backend</h2>
            {error && <p style={{ color: '#dc2626', fontSize: 14, marginBottom: 12 }}>{error}</p>}
            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <input type="email" placeholder="Email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)}
                className="input" required />
              <input type="password" placeholder="Password" value={loginPass} onChange={e => setLoginPass(e.target.value)}
                className="input" required />
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="submit" className="btn btn-primary" disabled={loginLoading}>
                  {loginLoading ? 'Connecting...' : 'Sign In'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={handleRegister} disabled={loginLoading}>
                  Register
                </button>
              </div>
            </form>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SEO Dashboard" description="SEO overview for wecare.digital" />
      <div className="inner-page">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h1 className="inner-page-title" style={{ margin: 0 }}>SEO Dashboard</h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary" onClick={loadStats} disabled={loading}>
              {loading ? 'Loading...' : 'Refresh'}
            </button>
            <button className="btn btn-secondary" onClick={() => { localStorage.removeItem('seo_token'); setSeoToken(''); setStats(null); }}>
              Disconnect
            </button>
          </div>
        </div>

        {error && <div className="card" style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#dc2626', marginBottom: 16 }}>{error}</div>}

        {stats && (
          <>
            <div className="stat-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
              <StatCard label="Total Pages" value={stats.total_pages} />
              <StatCard label="Indexed" value={stats.indexed_pages} color="#16a34a" />
              <StatCard label="Not Indexed" value={stats.not_indexed_pages} color="#dc2626" />
              <StatCard label="Issues" value={stats.pages_with_issues} color="#ea580c" />
              <StatCard label="Tracking %" value={`${stats.tracking_coverage_pct}%`} />
              <StatCard label="Schema %" value={`${stats.schema_coverage_pct}%`} />
              <StatCard label="Clicks (30d)" value={stats.total_clicks_30d?.toLocaleString()} />
              <StatCard label="Impressions (30d)" value={stats.total_impressions_30d?.toLocaleString()} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="card">
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Pages by Domain</h3>
                {Object.entries(stats.pages_by_domain || {}).map(([d, c]) => (
                  <div key={d} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 14, borderBottom: '1px solid #f3f4f6' }}>
                    <span>{d}</span><span style={{ fontWeight: 600 }}>{c as number}</span>
                  </div>
                ))}
              </div>
              <div className="card">
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Pages by Type</h3>
                {Object.entries(stats.pages_by_type || {}).map(([t, c]) => (
                  <div key={t} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 14, borderBottom: '1px solid #f3f4f6' }}>
                    <span>{t}</span><span style={{ fontWeight: 600 }}>{c as number}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
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

export default SEODashboard;
