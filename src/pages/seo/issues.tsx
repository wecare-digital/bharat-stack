/**
 * SEO Issues — list all detected SEO issues
 */
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import * as seoApi from '../../api/seo';

interface PageProps { signOut?: () => void; user?: any; }

const SEV_COLORS: Record<string, { bg: string; fg: string }> = {
  critical: { bg: '#fef2f2', fg: '#dc2626' },
  warning: { bg: '#fffbeb', fg: '#d97706' },
  info: { bg: '#eff6ff', fg: '#2563eb' },
};

const SEOIssues: React.FC<PageProps> = ({ signOut, user }) => {
  const router = useRouter();
  const [issues, setIssues] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      seoApi.listIssues().then(setIssues),
      seoApi.getIssuesSummary().then(setSummary),
    ]).finally(() => setLoading(false));
  }, []);

  async function handleResolve(id: number) {
    await seoApi.resolveIssue(id);
    setIssues(prev => prev.filter(i => i.id !== id));
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SEO Issues" description="SEO issues and warnings for wecare.digital" />
      <div className="inner-page">
        <h1 className="inner-page-title">SEO Issues</h1>
        {summary && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Open: {summary.total_open}</span>
            {Object.entries(summary.by_severity || {}).map(([s, c]) => {
              const col = SEV_COLORS[s] || SEV_COLORS.info;
              return <span key={s} style={{ background: col.bg, color: col.fg, padding: '4px 12px', borderRadius: 8, fontSize: 13 }}>{s}: {c as number}</span>;
            })}
          </div>
        )}
        <div className="card" style={{ overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                <th style={{ padding: '10px 12px' }}>Severity</th>
                <th style={{ padding: '10px 12px' }}>Type</th>
                <th style={{ padding: '10px 12px' }}>Description</th>
                <th style={{ padding: '10px 12px' }}>Page</th>
                <th style={{ padding: '10px 12px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {issues.map(i => {
                const col = SEV_COLORS[i.severity] || SEV_COLORS.info;
                return (
                  <tr key={i.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ background: col.bg, color: col.fg, padding: '2px 8px', borderRadius: 6, fontSize: 12 }}>{i.severity}</span>
                    </td>
                    <td style={{ padding: '10px 12px' }}>{i.issue_type}</td>
                    <td style={{ padding: '10px 12px', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{i.description}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ color: '#1a3a2a', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => router.push(`/seo/page/${i.page_id}`)}>#{i.page_id}</span>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <button onClick={() => handleResolve(i.id)} style={{ color: '#16a34a', background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }}>Resolve</button>
                    </td>
                  </tr>
                );
              })}
              {issues.length === 0 && !loading && (
                <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>No open issues</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
};

export default SEOIssues;
