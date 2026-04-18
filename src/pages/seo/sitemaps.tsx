/**
 * SEO Sitemaps — Submit sitemaps to Google Search Console
 */
import React, { useState } from 'react';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';
import * as seoApi from '../../api/seo';

interface PageProps { signOut?: () => void; user?: any; }

const SEOSitemaps: React.FC<PageProps> = ({ signOut, user }) => {
  const [url, setUrl] = useState('');
  const [propertyId, setPropertyId] = useState('1');
  const [result, setResult] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setResult('');
    try {
      const res = await seoApi.submitSitemap(url, Number(propertyId));
      setResult(`Submitted: ${res.submitted}`);
    } catch (err: any) {
      setResult(`Error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SEO Sitemaps" />
      <div className="inner-page">
        <h1 className="inner-page-title">Sitemaps</h1>
        <div className="card" style={{ maxWidth: 500 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Submit Sitemap to Google</h3>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <input placeholder="Sitemap URL (e.g. https://www.wecare.digital/sitemap.xml)" value={url}
              onChange={e => setUrl(e.target.value)} className="input" required />
            <input placeholder="Property ID" value={propertyId} onChange={e => setPropertyId(e.target.value)}
              className="input" required />
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit Sitemap'}
            </button>
            {result && <p style={{ fontSize: 14, color: result.startsWith('Error') ? '#dc2626' : '#16a34a' }}>{result}</p>}
          </form>
        </div>
      </div>
    </Layout>
  );
};

export default SEOSitemaps;
