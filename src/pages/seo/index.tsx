/**
 * SEO Hub — Overview + links to all SEO sub-pages
 * No internal login — matches pattern of /dm, /store, /dashboard
 */
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import SEO from '../../components/SEO';

interface PageProps { signOut?: () => void; user?: any; }

const PUBLIC_SITE = 'https://wecare.digital';
const BLOG_PUBLIC_API = `${process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api'}/seo-tools/blog-public`;

const seoPages = [
  { path: '/seo/blog-manager', label: 'Blog SEO Manager', desc: 'Create AWS-native posts; AI audit, approve and apply SEO', icon: '📝' },
  { path: '/seo/pages-manager', label: 'Site Pages SEO', desc: 'AI SEO for site, system & product pages — Site / System / Products tabs', icon: '📄' },
  { path: '/seo/tools', label: 'SEO Tools', desc: 'Blog SEO, button audit, live checks, PageSpeed', icon: '🔧' },
  { path: '/seo/pages', label: 'Pages Inventory', desc: 'All crawled pages with filters and details', icon: '📄' },
  { path: '/seo/issues', label: 'Issues', desc: 'SEO issues and warnings by priority', icon: '⚠️' },
  { path: '/seo/analytics', label: 'Search Analytics', desc: 'Google Search Console clicks and impressions', icon: '📊' },
  { path: '/seo/schema', label: 'Structured Data', desc: 'JSON-LD schema markup audit', icon: '🏗️' },
  { path: '/seo/properties', label: 'Properties', desc: 'Page-level SEO properties and metadata', icon: '🏷️' },
  { path: '/seo/sitemaps', label: 'Sitemaps', desc: 'Sitemap management and validation', icon: '🗺️' },
  { path: '/seo/tracking', label: 'Tracking', desc: 'Indexing and crawl coverage status', icon: '📡' },
];

const SEOHub: React.FC<PageProps> = ( { signOut, user } ) => {
  const router = useRouter();
  const [ liveStats, setLiveStats ] = useState<any>( null );
  const [ loading, setLoading ] = useState( true );

  useEffect( () => {
    async function fetchLiveStats () {
      try
      {
        const [ siteRes, blogRes ] = await Promise.all( [
          fetch( PUBLIC_SITE, { method: 'GET' } ).catch( () => null ),
          fetch( BLOG_PUBLIC_API ).then( r => r.ok ? r.json() : null ).catch( () => null ),
        ] );
        setLiveStats( {
          status: siteRes?.ok ? 'ok' : 'unknown',
          blogPosts: Array.isArray( blogRes?.posts ) ? blogRes.posts.length : 0,
          publicBase: PUBLIC_SITE.replace( 'https://', '' ),
        } );
      } catch
      {
        setLiveStats( null );
      } finally
      {
        setLoading( false );
      }
    }
    fetchLiveStats();
  }, [] );

  return (
    <Layout user={ user } onSignOut={ signOut }>
      <SEO title="SEO" description="SEO management hub for wecare.digital" />
      <div className="inner-page">
        <div style={ { marginBottom: 24 } }>
          <h1 className="inner-page-title" style={ { margin: '0 0 4px' } }>SEO</h1>
          <p style={ { fontSize: 13, color: '#6b7280', margin: 0 } }>Manage SEO for wecare.digital — pages, schema, indexing, tools</p>
        </div>

        {/* Live Stats */ }
        <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 28 } }>
          <StatCard label="Site Status" value={ loading ? '...' : ( liveStats?.status === 'ok' ? '✅ Live' : '❌ Down' ) } />
          <StatCard label="Published Blog Posts" value={ loading ? '...' : liveStats?.blogPosts } />
          <StatCard label="Blog Source" value="AWS" />
          <StatCard label="Public Host" value={ loading ? '...' : liveStats?.publicBase } />
          <StatCard label="Frontend" value="Amplify" />
        </div>

        {/* Sub-pages */ }
        <div style={ { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 } }>
          { seoPages.map( p => (
            <button
              key={ p.path }
              onClick={ () => router.push( p.path ) }
              style={ {
                display: 'flex', alignItems: 'center', gap: 14, padding: '16px 20px',
                background: '#fff', border: '1.5px solid #e5e7eb', borderRadius: 13,
                cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
                transition: 'all 0.15s', width: '100%',
              } }
              onMouseEnter={ e => { ( e.target as HTMLElement ).style.borderColor = '#d1f470'; } }
              onMouseLeave={ e => { ( e.target as HTMLElement ).style.borderColor = '#e5e7eb'; } }
            >
              <div style={ { fontSize: 24, width: 40, textAlign: 'center', flexShrink: 0 } }>{ p.icon }</div>
              <div style={ { flex: 1 } }>
                <div style={ { fontSize: 15, fontWeight: 600, color: '#1a1a1a' } }>{ p.label }</div>
                <div style={ { fontSize: 12, color: '#6b7280', marginTop: 2 } }>{ p.desc }</div>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
            </button>
          ) ) }
        </div>
      </div>
    </Layout>
  );
};

function StatCard ( { label, value }: { label: string; value: any } ) {
  return (
    <div style={ { background: '#fff', border: '1.5px solid #e5e7eb', borderRadius: 13, padding: '16px 20px' } }>
      <div style={ { fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.5px' } }>{ label }</div>
      <div style={ { fontSize: 24, fontWeight: 700, marginTop: 4, color: '#1a3a2a' } }>{ value ?? '—' }</div>
    </div>
  );
}

export default SEOHub;
