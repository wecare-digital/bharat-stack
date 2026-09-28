import type { GetStaticProps } from 'next';
import { useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { listPublicBlogPosts, PublicBlogPost } from '../../lib/public-blog';
import RotatingHero, { CycleWord } from '../../components/RotatingHero';
import Breadcrumbs from '../../components/Breadcrumbs';
import BlogSearch from '../../components/BlogSearch';

interface Props {
  posts: PublicBlogPost[];
}

/**
 * STRUCTURED DATA IS DECLARED HERE, not in _app.tsx.
 *
 * This route is in `isContentPublic`, and _app.tsx renders its shared <Head> behind
 * `!isContentPublic` - so the Organization, WebSite, WebPage and BreadcrumbList graph
 * every other public route gets is deliberately suppressed on /blog/ and /post/[slug]/,
 * to stop two components emitting competing canonicals. The consequence went unnoticed:
 * /blog/ is in the sitemap and indexable but shipped ZERO JSON-LD, while the structured
 * data checker only looked at six hardcoded routes and never asked about this one.
 *
 * THE GRAPH IS SELF-CONTAINED ON PURPOSE. It cannot reference the shared nodes by @id -
 * `#website` and `#organization` are defined in the <Head> that is suppressed here, so
 * pointing at them would emit references that resolve to nothing, which is worse than
 * omitting them. Publisher is therefore inlined.
 */
/**
 * The rotation. Four words, held close in length so the pill barely travels - the same
 * constraint products.ts documents. Tints are the four pairs reused verbatim from the Grahak
 * OS hero; no new colours.
 *
 * THEY DESCRIBE WHAT IS ACTUALLY PUBLISHED HERE. The corpus is short reflective pieces -
 * "A page view is not a person", "Acceptance begins where control ends", "A promise is not a
 * prediction" - so the words name the subject matter rather than promising guides or product
 * updates, which is what the old sub-line implied and the posts do not deliver.
 */
const HERO_WORDS: CycleWord[] = [
  { word: 'clarity', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'practice', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'meaning', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'change', tint: '#ede9fe', dot: '#9849e8' },
];

export default function BlogIndex ( { posts }: Props ) {
  const canonical = 'https://wecare.digital/blog/';
  const DESCRIPTION = 'Ideas, guides and updates from WECARE.DIGITAL.';
  const categories = useMemo(
    () => Array.from( new Set( posts.map( post => post.category ).filter( Boolean ) as string[] ) ).sort( ( a, b ) => a.localeCompare( b ) ),
    [ posts ]
  );
  const [ activeCategory, setActiveCategory ] = useState( 'All' );
  const [ query, setQuery ] = useState( '' );

  /**
   * READ ?q= ON FIRST RENDER, because a post page's search box navigates here with it. Done
   * in a lazy initialiser rather than an effect so the filtered list is correct on the first
   * paint instead of flashing the full 824 and then narrowing. window is guarded because this
   * same initialiser runs during the static export, where there is no location.
   */
  const [ queryReady ] = useState( () => {
    if ( typeof window === 'undefined' ) return false;
    const q = new URLSearchParams( window.location.search ).get( 'q' );
    if ( q ) setQuery( q );
    return true;
  } );
  void queryReady;

  /**
   * Category first, then text. Matching title, excerpt and category means a search for a
   * category name finds those posts even when the pill is on All, which is what someone
   * typing "Practice" expects. Case-insensitive, and trimmed so a stray space from a paste
   * does not empty the list.
   */
  const visiblePosts = useMemo( () => {
    const byCategory = activeCategory === 'All'
      ? posts
      : posts.filter( post => post.category === activeCategory );
    const q = query.trim().toLowerCase();
    if ( !q ) return byCategory;
    return byCategory.filter( post => (
      `${post.title} ${post.excerpt || ''} ${post.category || ''}`.toLowerCase().includes( q )
    ) );
  }, [ posts, activeCategory, query ] );

  const schema = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Blog',
        '@id': `${canonical}#blog`,
        url: canonical,
        name: 'WECARE.DIGITAL Blog',
        description: DESCRIPTION,
        inLanguage: 'en-IN',
        publisher: { '@type': 'Organization', name: 'WECARE.DIGITAL', url: 'https://wecare.digital' },
        breadcrumb: { '@id': `${canonical}#breadcrumb` },
      },
      {
        '@type': 'BreadcrumbList',
        '@id': `${canonical}#breadcrumb`,
        // The tail must be the canonical, slash included, or the breadcrumb describes a
        // URL that redirects. trailingSlash is on for this export.
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://wecare.digital/' },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: canonical },
        ],
      },
    ],
  };

  return (
    <>
      <Head>
        <title>Blog | WECARE.DIGITAL</title>
        <meta name="description" content={ DESCRIPTION } />
        <link rel="canonical" href={ canonical } />
        <meta property="og:type" content="website" />
        <meta property="og:title" content="Blog | WECARE.DIGITAL" />
        <meta property="og:description" content={ DESCRIPTION } />
        <meta property="og:url" content={ canonical } />
        <meta name="robots" content="index, follow, max-image-preview:large" />
        <script type="application/ld+json" dangerouslySetInnerHTML={ { __html: JSON.stringify( schema ) } } />
      </Head>
      {/* THE HOME PAGE'S TOP SECTION, ON THE BLOG. This replaced a plain
          <h1>Blog</h1> plus "Ideas, guides and updates published by the WECARE.DIGITAL
          team." - two lines that named the section and then restated it, on a page that
          otherwise shared nothing with the rest of the site.
          RotatingHero renders the <main> and the <h1> here, which is correct: on this page
          the hero IS the page. Post pages pass `subordinate` instead, because there the
          article owns both. */}
      <RotatingHero
        frame="Notes on"
        words={ HERO_WORDS }
        sub="Short pieces on the distinctions that change how a thing is seen — written by the people doing the work."
        ariaLabel="WECARE.DIGITAL blog"
      >
        <div className="blog-shell">
          <Breadcrumbs items={ [ { label: 'Home', href: '/' }, { label: 'Blog' } ] } />
          {/* Live mode: every post is already in this page, so filtering needs no navigation. */}
          <BlogSearch
            value={ query }
            onChange={ setQuery }
            resultCount={ visiblePosts.length }
            totalCount={ posts.length }
          />

        { posts.length > 0 ? (
          <>
            { categories.length > 1 && (
              <nav className="category-switch" aria-label="Filter posts by category">
                <button
                  type="button"
                  aria-pressed={ activeCategory === 'All' }
                  onClick={ () => setActiveCategory( 'All' ) }
                >
                  All
                </button>
                { categories.map( category => (
                  <button
                    key={ category }
                    type="button"
                    aria-pressed={ activeCategory === category }
                    onClick={ () => setActiveCategory( category ) }
                  >
                    { category }
                  </button>
                ) ) }
              </nav>
            ) }
            <section className="post-grid" aria-label="Published posts">
            { visiblePosts.map( post => (
              <article key={ post.id || post.slug } className="post-card">
                <div className="post-copy">
                  { post.category && <span className="category">{ post.category }</span> }
                  <h2><Link href={ `/post/${post.slug}/` }>{ post.title }</Link></h2>
                  { post.excerpt && <p>{ post.excerpt }</p> }
                  <div className="meta">
                    {/* data-wc-no-translate: an author name is a proper noun, matching the
                        byline in post/[slug].tsx. On the span and not on .meta, because the
                        <time> beside it renders a formatted date that SHOULD translate.
                        This page carries 638 of these - one per post - which made it the
                        single largest source of brand-name text in the export once the
                        article bylines were fixed. */}
                    { post.authorName && <span data-wc-no-translate="true">{ post.authorName }</span> }
                    { post.publishedDate && <time dateTime={ post.publishedDate }>{ new Date( post.publishedDate ).toLocaleDateString( 'en-IN' ) }</time> }
                  </div>
                </div>
              </article>
            ) ) }
            </section>
          </>
        ) : (
          <div className="empty">No posts have been published yet.</div>
        ) }
        </div>
      </RotatingHero>
      <style jsx>{`
        /* NO TOP PADDING AND NO MAX-WIDTH ANY MORE: RotatingHero owns both now.
           This was the page's <main> at padding:156px 24px 96px with its own 1300px measure.
           It is now a <div> inside .rh-layout, which already applies the header offset, the
           page measure and the horizontal gutter - keeping them here would double every one
           of them. Only the space between the hero and the list is left, which is this
           element's own job.
           The font stack goes too: .rh-shell declares it one level up. */
        .blog-shell{margin:0}
        /* .blog-hero IS GONE, with the markup it styled. It held <h1>Blog</h1> and "Ideas,
           guides and updates published by the WECARE.DIGITAL team." - a heading that named the
           section and a line that restated it, on a page sharing no design language with the
           rest of the site. RotatingHero replaced both. */
        h1{font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;letter-spacing:-0.04em;margin:0 0 24px;color:rgba(0,0,0,.95);text-wrap:balance}
        .category-switch{display:flex;gap:8px;overflow-x:auto;margin:0 0 28px;padding:2px 0 6px;scrollbar-width:thin}
        .category-switch button{flex:0 0 auto;min-height:38px;padding:0 14px;border:1px solid #d1d5db;border-radius:999px;background:#fff;color:#1a3a2a;font:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:background-color .18s ease,border-color .18s ease,transform .18s ease}
        .category-switch button:hover{border-color:#d1f470;transform:translateY(-1px)}
        .category-switch button[aria-pressed="true"]{background:#d1f470;border-color:#d1f470}
        .category-switch button:focus-visible{outline:3px solid rgba(26,58,42,.25);outline-offset:3px}
        .post-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}
        .post-card{border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;background:#fff;transition:border-color .18s ease,transform .18s ease}
        .post-card:hover{border-color:#d1f470;transform:translateY(-1px)}
        .post-copy{padding:26px}
        .category{display:inline-block;background:rgba(209,244,112,.28);color:#1a3a2a;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:700;margin-bottom:14px}
        h2{font-size:23px;line-height:1.22;letter-spacing:-.3px;margin:0 0 12px}
        h2 :global(a){color:rgba(0,0,0,.95);text-decoration:none;text-underline-offset:3px}
        h2 :global(a:hover){color:#1a3a2a}
        h2 :global(a:focus-visible){outline:3px solid rgba(26,58,42,.25);outline-offset:3px;border-radius:2px}
        .post-copy p{font-size:16px;line-height:1.5;color:rgba(0,0,0,.72);margin:0 0 20px}
        .meta{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;line-height:1.4;color:#6b7280}
        .empty{border:1px dashed #d1d5db;border-radius:14px;padding:40px;text-align:center;color:#6b7280}
        @media(max-width:1050px){.post-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
        @media(max-width:680px){
          /* Nothing to override: the hero's own narrow-screen padding applies. */
          
          .category-switch{margin-bottom:22px}
          .post-grid{grid-template-columns:1fr;gap:18px}
          .post-copy{padding:22px}
          h2{font-size:22px}
        }
      `}</style>
    </>
  );
}

// Static-export content refresh marker: 2026-09-28 Gastronomy batch 001.
// Publishing to Wix changes the source of truth; a new frontend build snapshots
// the latest published posts into /blog/ and /post/[slug]/ static pages.
export const getStaticProps: GetStaticProps<Props> = async () => {
  const posts = await listPublicBlogPosts();
  return { props: { posts } };
};
