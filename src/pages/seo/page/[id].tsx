/**
 * SEO Page Detail — view/edit SEO, tracking, schema for a single page
 */
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import * as seoApi from '../../../api/seo';

interface PageProps { signOut?: () => void; user?: any; }

const SEOPageDetail: React.FC<PageProps> = ({ signOut, user }) => {
  const router = useRouter();
  const { id } = router.query;
  const [page, setPage] = useState<any>(null);
  const [tracking, setTracking] = useState<any>(null);
  const [schema, setSchema] = useState<any>(null);
  const [inspections, setInspections] = useState<any[]>([]);
  const [tab, setTab] = useState<'seo' | 'tracking' | 'schema' | 'inspections'>('seo');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    const pid = Number(id);
    setLoading(true);
    Promise.all([
      seoApi.getPage(pid).then(setPage),
      seoApi.getTrackingByPage(pid).then(setTracking).catch(() => null),
      seoApi.getSchemaByPage(pid).then(setSchema).catch(() => null),
      seoApi.getPageInspections(pid).then(setInspections).catch(() => []),
    ]).finally(() => setLoading(false));
  }, [id]);

  async function handleInspect() {
    if (!page) return;
    try {
      await seoApi.bulkInspect([page.id]);
      alert('Inspection queued');
      const data = await seoApi.getPageInspections(page.id);
      setInspections(data);
    } catch (e: any) { alert(e.message); }
  }

  async function handleRegenSchema() {
    if (!page) return;
    try {
      const data = await seoApi.regenerateSchema(page.id);
      setSchema(data);
    } catch (e: any) { alert(e.message); }
  }

  if (loading) return (
    <Layout user={user} onSignOut={signOut}>
      <div className="inner-page"><div className="card" style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>Loading...</div></div>
    </Layout>
  );

  if (!page) return (
    <Layout user={user} onSignOut={signOut}>
      <div className="inner-page"><div className="card" style={{ padding: 40, textAlign: 'center', color: '#dc2626' }}>Page not found</div></div>
    </Layout>
  );

  const tabs = ['seo', 'tracking', 'schema', 'inspections'] as const;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title={`SEO: ${page.title || page.normalized_url}`} description="SEO page details and audit" />
      <div className="inner-page">
        <div style={{ marginBottom: 16 }}>
          <button className="btn btn-secondary" onClick={() => router.push('/seo/pages')} style={{ marginBottom: 8 }}>← Back to Pages</button>
          <h1 className="inner-page-title" style={{ margin: 0, fontSize: 18, wordBreak: 'break-all' }}>{page.normalized_url}</h1>
          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
            <span style={{ background: '#dbeafe', color: '#1e40af', padding: '2px 10px', borderRadius: 8, fontSize: 12 }}>{page.page_type}</span>
            <span style={{ background: '#f3f4f6', padding: '2px 10px', borderRadius: 8, fontSize: 12 }}>HTTP {page.http_status || '?'}</span>
            <span style={{ background: '#f3f4f6', padding: '2px 10px', borderRadius: 8, fontSize: 12 }}>{page.site_domain}</span>
            {page.is_noindex && <span style={{ background: '#fef2f2', color: '#dc2626', padding: '2px 10px', borderRadius: 8, fontSize: 12 }}>noindex</span>}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 2, borderBottom: '2px solid #e5e7eb', marginBottom: 16 }}>
          {tabs.map(t => (
            <button key={t} onClick={() => setTab(t)}
              style={{ padding: '10px 20px', fontSize: 14, fontWeight: tab === t ? 600 : 400, background: 'none', border: 'none',
                borderBottom: tab === t ? '2px solid #1a3a2a' : '2px solid transparent', color: tab === t ? '#1a3a2a' : '#6b7280', cursor: 'pointer' }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        <div className="card">
          {tab === 'seo' && (
            <div style={{ display: 'grid', gap: 8 }}>
              <Row label="Title" value={page.title} />
              <Row label="Meta Description" value={page.meta_description} />
              <Row label="Canonical" value={page.canonical_url} />
              <Row label="H1 Count" value={page.h1_count} />
              <Row label="H2 Count" value={page.h2_count} />
              <Row label="Robots" value={page.robots_meta} />
              <Row label="X-Robots-Tag" value={page.x_robots_tag} />
              <Row label="Discovery Source" value={page.discovery_source} />
              <Row label="First Seen" value={page.first_seen_at} />
              <Row label="Last Crawled" value={page.crawl_timestamp} />
              {page.og_tags && <Row label="OG Tags" value={JSON.stringify(page.og_tags)} />}
              {page.redirect_chain?.length > 0 && <Row label="Redirects" value={JSON.stringify(page.redirect_chain)} />}
            </div>
          )}

          {tab === 'tracking' && (
            tracking ? (
              <div style={{ display: 'grid', gap: 8 }}>
                <Row label="GA4 Status" value={tracking.ga4_status} color={tracking.ga4_status === 'present' ? '#16a34a' : '#dc2626'} />
                <Row label="GA4 ID" value={tracking.ga4_measurement_id} />
                <Row label="GTM Status" value={tracking.gtm_status} />
                <Row label="GTM Container" value={tracking.gtm_container_id} />
                <Row label="Google Ads" value={tracking.google_ads_status} />
                <Row label="Pageview Tracking" value={tracking.pageview_tracking ? 'Yes' : 'No'} />
                <Row label="Tag IDs Found" value={tracking.tag_ids_found?.join(', ')} />
                {tracking.missing_tags_warnings?.map((w: string, i: number) => (
                  <div key={i} style={{ color: '#dc2626', fontSize: 13, padding: '4px 0' }}>⚠ {w}</div>
                ))}
              </div>
            ) : <div style={{ color: '#6b7280', padding: 20 }}>No tracking data. Run a crawl first.</div>
          )}

          {tab === 'schema' && (
            schema ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div>
                    <Row label="Template" value={schema.template_type} />
                    <Row label="Status" value={schema.schema_status} color={schema.schema_status === 'valid' ? '#16a34a' : '#ea580c'} />
                  </div>
                  <button className="btn btn-secondary" onClick={handleRegenSchema}>Regenerate</button>
                </div>
                {schema.validation_errors?.length > 0 && (
                  <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 8 }}>Errors: {schema.validation_errors.join(', ')}</div>
                )}
                <pre style={{ background: '#f9fafb', padding: 16, borderRadius: 8, fontSize: 12, overflow: 'auto', maxHeight: 400 }}>
                  {JSON.stringify(schema.override_json_ld || schema.generated_json_ld, null, 2)}
                </pre>
              </div>
            ) : <div style={{ color: '#6b7280', padding: 20 }}>No schema data. Run a crawl first.</div>
          )}

          {tab === 'inspections' && (
            <div>
              <button className="btn btn-primary" onClick={handleInspect} style={{ marginBottom: 12 }}>Inspect Now</button>
              {inspections.length > 0 ? (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                      <th style={{ padding: '8px 12px' }}>Status</th>
                      <th style={{ padding: '8px 12px' }}>Coverage</th>
                      <th style={{ padding: '8px 12px' }}>Indexing</th>
                      <th style={{ padding: '8px 12px' }}>Google Canonical</th>
                      <th style={{ padding: '8px 12px' }}>Inspected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inspections.map((insp: any) => (
                      <tr key={insp.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ padding: '8px 12px' }}>
                          <span style={{ background: insp.index_status === 'indexed' ? '#dcfce7' : '#fef2f2',
                            color: insp.index_status === 'indexed' ? '#166534' : '#dc2626',
                            padding: '2px 8px', borderRadius: 6, fontSize: 12 }}>{insp.index_status}</span>
                        </td>
                        <td style={{ padding: '8px 12px' }}>{insp.coverage_state || '—'}</td>
                        <td style={{ padding: '8px 12px' }}>{insp.indexing_state || '—'}</td>
                        <td style={{ padding: '8px 12px', fontSize: 12 }}>{insp.google_canonical || '—'}</td>
                        <td style={{ padding: '8px 12px', fontSize: 12 }}>{insp.inspected_at || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <div style={{ color: '#6b7280', padding: 20 }}>No inspections yet.</div>}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

function Row({ label, value, color }: { label: string; value: any; color?: string }) {
  return (
    <div style={{ display: 'flex', fontSize: 14, padding: '4px 0' }}>
      <span style={{ width: 160, color: '#6b7280', flexShrink: 0 }}>{label}</span>
      <span style={{ color: color || '#1a1a1a', wordBreak: 'break-all' }}>{value ?? '—'}</span>
    </div>
  );
}

export default SEOPageDetail;
