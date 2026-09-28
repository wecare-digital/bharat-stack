import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import type { BlogCard } from '../lib/public-blog';
import RotatingHero, { CycleWord } from './RotatingHero';
import Breadcrumbs from './Breadcrumbs';
import BlogSearch from './BlogSearch';

/**
 * The blog index, one page of it.
 *
 * WHY THIS IS A COMPONENT AND NOT JUST src/pages/blog/index.tsx. There are now two routes
 * that render this exact page - /blog/ for the first 24 posts and /blog/page/N/ for the
 * rest - and they must not be two copies of 250 lines of markup and styles. Both pages are
 * thin: they fetch, slice, and hand the slice here.
 *
 * WHY THE BLOG IS PAGINATED AT ALL
 * --------------------------------
 * /blog/ rendered all 834 published posts in one document. Measured at 1280x900 that was
 * 103,908px - 115.5 screens - and the build printed its own warning on every run:
 *
 *   Warning: data for page "/blog" (path "/blog/") is 842 kB which exceeds the
 *   threshold of 128 kB, this amount of data can reduce performance.
 *
 * Two separate costs behind one symptom, and both had to go:
 *
 *   THE PAYLOAD. Every field of every post was serialised into __NEXT_DATA__ and seven
 *   were rendered. See BlogCard in lib/public-blog.ts - projecting to the fields the card
 *   actually prints drops 357 kB of metaDescription, seoTitle, robots, tags, modifiedDate,
 *   url and id that no reader ever saw.
 *
 *   THE DOM. 834 cards is 834 <article>s with links and headings in them, parsed and laid
 *   out before anything is interactive, on a phone as much as a laptop. Projection does not
 *   touch that; only slicing does.
 *
 * Together: ~9 kB and ~3.3 screens per page, against 842 kB and 115.5.
 *
 * WHAT PAGINATION WOULD HAVE BROKEN, AND HOW IT DOES NOT
 * -----------------------------------------------------
 * Search and the category pills both filter across EVERY post, and the reason they could
 * was that every post was in the page - the thing being removed. Narrowing them to the
 * current 24 would have been a silent downgrade: typing a word and being told "3 of 24
 * posts" while 800 unsearched posts sit behind it is worse than no search.
 *
 * So the full list still exists, as /blog/search-index.json - slug, title, excerpt and
 * category only, written by scripts/generate-blog-search-index.js after the build. It is
 * fetched ONCE, LAZILY, on the first keystroke or the first category press, and never on a
 * plain page view. A reader who does not search pays nothing for it.
 *
 * THE URL IS THE SOURCE OF TRUTH FOR A SEARCH, still: ?q= is read on first render exactly as
 * before, so a post page's search box navigating to /blog/?q=x keeps working, and a search
 * result page is linkable. When a query or a non-All category is active the paginator is
 * hidden and all matches are listed, because filtered results are already a narrowing - two
 * layers of it would make finding a post a puzzle.
 *
 * NO-JAVASCRIPT PATH. Pagination is real links to real prerendered pages, so the whole blog
 * is reachable with scripts off - which was NOT true of the single page, where the only way
 * to the 800th post was a 103,908px scroll. Search and categories need JS and always did;
 * BlogSearch already degrades to a GET form that navigates here.
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
export const HERO_WORDS: CycleWord[] = [
  { word: 'clarity', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'practice', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'meaning', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'change', tint: '#ede9fe', dot: '#9849e8' },
];

/** Where the lazily-fetched full list lives. Written post-build, beside the page it serves. */
const SEARCH_INDEX_URL = '/blog/search-index.json';

interface BlogIndexViewProps {
  /** This page's slice, already projected and sorted. */
  posts: BlogCard[];
  /** 1-based. Page 1 is /blog/; every other page is /blog/page/N/. */
  page: number;
  totalPages: number;
  /** Every published post, for the count beside the search box. */
  totalPosts: number;
  /** Every category across the whole corpus, not just this page's - see below. */
  categories: string[];
}

/** /blog/ for page 1, /blog/page/N/ after that. Page 1 must not also exist at page/1/. */
export const blogPageHref = ( page: number ): string =>
  page <= 1 ? '/blog/' : `/blog/page/${page}/`;

/**
 * Which page numbers to render. 35 pages of numbers is its own wall of links, so this shows
 * first, last, and a window around the current page, with gaps marked. Returns numbers and
 * nulls, where null is an elision.
 */
function pageWindow ( page: number, totalPages: number ): ( number | null )[] {
  if ( totalPages <= 7 ) return Array.from( { length: totalPages }, ( _, i ) => i + 1 );
  const around = [ page - 1, page, page + 1 ].filter( n => n > 1 && n < totalPages );
  const shown = [ 1, ...around, totalPages ];
  const out: ( number | null )[] = [];
  for ( let i = 0; i < shown.length; i++ ) {
    if ( i > 0 && shown[ i ] - shown[ i - 1 ] > 1 ) out.push( null );
    out.push( shown[ i ] );
  }
  return out;
}

const BlogIndexView: React.FC<BlogIndexViewProps> = ( { posts, page, totalPages, totalPosts, categories } ) => {
  const [ activeCategory, setActiveCategory ] = useState( 'All' );
  const [ query, setQuery ] = useState( '' );

  /** The full corpus, or null until something needs it. */
  const [ allCards, setAllCards ] = useState<BlogCard[] | null>( null );
  const [ indexState, setIndexState ] = useState<'idle' | 'loading' | 'ready' | 'failed'>( 'idle' );
  const requested = useRef( false );

  /**
   * Fetch the full list once. Guarded by a ref rather than by indexState because two events
   * in the same tick - a keystroke and a category press - would both see 'idle' and both
   * start a request; a ref is written synchronously and settles it.
   */
  const loadIndex = useCallback( () => {
    if ( requested.current ) return;
    requested.current = true;
    setIndexState( 'loading' );
    fetch( SEARCH_INDEX_URL, { headers: { Accept: 'application/json' } } )
      .then( r => ( r.ok ? r.json() : Promise.reject( new Error( String( r.status ) ) ) ) )
      .then( ( body: { posts?: BlogCard[] } ) => {
        if ( !Array.isArray( body?.posts ) ) throw new Error( 'shape' );
        setAllCards( body.posts );
        setIndexState( 'ready' );
      } )
      .catch( () => {
        // Leave requested.current true: retrying on every keystroke against an endpoint
        // that just failed turns one bad response into a request per character.
        setIndexState( 'failed' );
      } );
  }, [] );

  /**
   * READ ?q= ON FIRST RENDER, because a post page's search box navigates here with it. Done
   * in a lazy initialiser rather than an effect so the filtered list is correct on the first
   * paint instead of flashing this page's 24 and then narrowing. window is guarded because
   * this same initialiser runs during the static export, where there is no location.
   */
  const [ initialQuery ] = useState( () => {
    if ( typeof window === 'undefined' ) return '';
    return new URLSearchParams( window.location.search ).get( 'q' ) || '';
  } );

  useEffect( () => {
    if ( initialQuery ) { setQuery( initialQuery ); loadIndex(); }
  }, [ initialQuery, loadIndex ] );

  const onQueryChange = useCallback( ( next: string ) => {
    setQuery( next );
    if ( next.trim() ) loadIndex();
  }, [ loadIndex ] );

  const onCategory = useCallback( ( next: string ) => {
    setActiveCategory( next );
    if ( next !== 'All' ) loadIndex();
  }, [ loadIndex ] );

  const filtering = Boolean( query.trim() ) || activeCategory !== 'All';

  /**
   * Category first, then text. Matching title, excerpt and category means a search for a
   * category name finds those posts even when the pill is on All, which is what someone
   * typing "Practice" expects. Case-insensitive, and trimmed so a stray space from a paste
   * does not empty the list.
   *
   * SEARCHES THE FULL CORPUS ONCE IT IS LOADED, and this page's slice before then. That
   * fallback is what keeps the first keystroke from showing an empty grid while the index is
   * in flight - it narrows what is already on screen, then widens when the list lands.
   */
  const searchable = allCards || posts;
  const visiblePosts = useMemo( () => {
    if ( !filtering ) return posts;
    const byCategory = activeCategory === 'All'
      ? searchable
      : searchable.filter( post => post.category === activeCategory );
    const q = query.trim().toLowerCase();
    if ( !q ) return byCategory;
    return byCategory.filter( post => (
      `${post.title} ${post.excerpt || ''} ${post.category || ''}`.toLowerCase().includes( q )
    ) );
  }, [ posts, searchable, activeCategory, query, filtering ] );

  const windowed = pageWindow( page, totalPages );

  return (
    <RotatingHero
      frame="Notes on"
      words={ HERO_WORDS }
      sub="Short pieces on the distinctions that change how a thing is seen — written by the people doing the work."
      ariaLabel="WECARE.DIGITAL blog"
    >
      <div className="blog-shell">
        <Breadcrumbs
          items={ page > 1
            ? [ { label: 'Home', href: '/' }, { label: 'Blog', href: '/blog/' }, { label: `Page ${page}` } ]
            : [ { label: 'Home', href: '/' }, { label: 'Blog' } ] }
        />
        {/* Live mode. The count reported is against the WHOLE corpus, not this page - "3 of
            834" is the true answer and "3 of 24" would be a lie about what was searched. */}
        <BlogSearch
          value={ query }
          onChange={ onQueryChange }
          resultCount={ visiblePosts.length }
          totalCount={ totalPosts }
        />

        { indexState === 'failed' && filtering && (
          <p className="blog-degraded" role="status">
            The full post list could not be loaded, so this is searching the { posts.length } posts
            on this page only. <a href="/blog/">Reload the blog</a> to try again.
          </p>
        ) }

        { totalPosts > 0 ? (
          <>
            {/* CATEGORIES COME FROM THE WHOLE CORPUS, passed in as a prop, not derived from
                this page's 24. Deriving them locally would give each page a different set of
                pills - page 3 would offer four categories and page 9 a different four - which
                reads as the filter being broken rather than as the data being sliced. */}
            { categories.length > 1 && (
              <nav className="category-switch" aria-label="Filter posts by category">
                <button type="button" aria-pressed={ activeCategory === 'All' } onClick={ () => onCategory( 'All' ) }>
                  All
                </button>
                { categories.map( category => (
                  <button
                    key={ category }
                    type="button"
                    aria-pressed={ activeCategory === category }
                    onClick={ () => onCategory( category ) }
                  >
                    { category }
                  </button>
                ) ) }
              </nav>
            ) }

            { visiblePosts.length > 0 ? (
              <section className="post-grid" aria-label={ filtering ? 'Matching posts' : 'Published posts' }>
                { visiblePosts.map( post => (
                  <article key={ post.slug } className="post-card">
                    <div className="post-copy">
                      { post.category && <span className="category">{ post.category }</span> }
                      <h2><Link href={ `/post/${post.slug}/` }>{ post.title }</Link></h2>
                      { post.excerpt && <p>{ post.excerpt }</p> }
                      <div className="meta">
                        {/* data-wc-no-translate: an author name is a proper noun, matching the
                            byline in post/[slug].tsx. On the span and not on .meta, because the
                            <time> beside it renders a formatted date that SHOULD translate.
                            This page carried 834 of these - one per post - which made it the
                            single largest source of brand-name text in the export once the
                            article bylines were fixed. Pagination cuts that to 24 a page. */}
                        { post.authorName && <span data-wc-no-translate="true">{ post.authorName }</span> }
                        { post.publishedDate && <time dateTime={ post.publishedDate }>{ new Date( post.publishedDate ).toLocaleDateString( 'en-IN' ) }</time> }
                      </div>
                    </div>
                  </article>
                ) ) }
              </section>
            ) : (
              <div className="empty">
                { indexState === 'loading' ? 'Searching all posts…' : 'No posts match that search.' }
              </div>
            ) }

            {/* THE PAGINATOR IS HIDDEN WHILE FILTERING. A filtered list is already a
                narrowing of the whole corpus and every match is shown; paging it as well
                would mean two independent narrowings between a reader and one post. */}
            { !filtering && totalPages > 1 && (
              <nav className="pager" aria-label="Blog pages">
                {/* rel=prev/next as well as the visible label: Google retired them as an
                    indexing signal, they are still the semantic relationship, and some
                    readers' browsers and extensions use them to move between pages. */}
                { page > 1
                  ? <Link className="pager-step" rel="prev" href={ blogPageHref( page - 1 ) }>← Newer</Link>
                  : <span className="pager-step is-off" aria-hidden="true">← Newer</span> }

                <ol className="pager-list">
                  { windowed.map( ( n, i ) => (
                    <li key={ n === null ? `gap-${i}` : n }>
                      { n === null
                        // A real character, not a styled empty element: a screen reader
                        // needs something between "1" and "17" or the jump is silent.
                        ? <span className="pager-gap">…</span>
                        : n === page
                          // aria-current is what says WHICH page this is. Bold alone says it
                          // to sighted readers only, and a link to the page you are on is a
                          // control that does nothing.
                          ? <span className="pager-num is-here" aria-current="page">{ n }</span>
                          : <Link className="pager-num" href={ blogPageHref( n ) }>
                            <span className="pager-sr">Page </span>{ n }
                          </Link> }
                    </li>
                  ) ) }
                </ol>

                { page < totalPages
                  ? <Link className="pager-step" rel="next" href={ blogPageHref( page + 1 ) }>Older →</Link>
                  : <span className="pager-step is-off" aria-hidden="true">Older →</span> }
              </nav>
            ) }
          </>
        ) : (
          <div className="empty">No posts have been published yet.</div>
        ) }
      </div>

      <style jsx>{`
        /* NO TOP PADDING AND NO MAX-WIDTH: RotatingHero owns both. This was the page's
           <main> at padding:156px 24px 96px with its own 1300px measure. It is now a <div>
           inside .rh-layout, which already applies the header offset, the page measure and
           the horizontal gutter - keeping them here would double every one of them. Only the
           space between the hero and the list is left, which is this element's own job.
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

        /* The degraded-search notice. Same lime-tint-plus-edge treatment as the legal
           notice, because it does the same job: something a reader must see before they
           trust what is below it. Not a red error - the page still works, it is just
           narrower than it should be. */
        .blog-degraded{
          margin:0 0 28px;padding:14px 16px;
          background:rgba(209,244,112,.22);border-left:4px solid #d1f470;border-radius:8px;
          font-size:16px;line-height:1.55;color:rgba(0,0,0,.898);
        }
        .blog-degraded :global(a){color:#1a3a2a;font-weight:600}

        /* THE PAGER. 44px minimum touch target on every control - that is the WCAG 2.5.8
           floor and a row of page numbers is exactly the case it exists for. Sizes reuse
           existing rungs: 12px radius from the search field, the lime-on-dark-green pairing
           from the closing band's button for the current page. */
        .pager{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:48px 0 0;padding:24px 0 0;border-top:1px solid #e5e7eb}
        .pager-list{display:flex;align-items:center;gap:4px;flex-wrap:wrap;margin:0;padding:0;list-style:none}
        .pager-num,.pager-step,.pager-gap{
          display:inline-flex;align-items:center;justify-content:center;
          min-width:44px;min-height:44px;padding:0 12px;
          border-radius:12px;font-size:16px;font-weight:600;
          color:#1a3a2a;text-decoration:none;
        }
        .pager-num:hover,.pager-step:hover{background:rgba(209,244,112,.28)}
        .pager-num:focus-visible,.pager-step:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}
        /* The current page: filled, and it is a <span>, so there is nothing to hover. */
        .pager-num.is-here{background:#d1f470;border:2px solid #1a3a2a;cursor:default}
        .pager-gap{color:rgba(0,0,0,.42);font-weight:400;min-width:24px;padding:0}
        .pager-step{border:2px solid rgba(26,58,42,.22)}
        /* The end of the run. Rendered rather than omitted so the row does not reflow as a
           reader pages through, and aria-hidden so it is not announced as a dead control. */
        .pager-step.is-off{color:rgba(0,0,0,.32);border-color:#e5e7eb;cursor:default}
        /* "Page 7" to a screen reader, "7" on screen: a bare number read out of the list
           context is ambiguous. Same clip technique as .bs-label. */
        .pager-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}

        @media(max-width:1050px){.post-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
        @media(max-width:680px){
          /* Nothing to override for the hero: its own narrow-screen padding applies. */
          .category-switch{margin-bottom:22px}
          .post-grid{grid-template-columns:1fr;gap:18px}
          .post-copy{padding:22px}
          h2{font-size:22px}
          /* The numbers wrap to their own row under the prev/next pair rather than
             squeezing: 35 pages cannot share a 390px line with two labelled steps. */
          .pager{gap:8px}
          .pager-list{order:3;width:100%;justify-content:center}
          .pager-step{flex:1}
        }
        @media(prefers-reduced-motion:reduce){
          .post-card,.category-switch button{transition:none}
          .post-card:hover,.category-switch button:hover{transform:none}
        }
      `}</style>
    </RotatingHero>
  );
};

export default BlogIndexView;
