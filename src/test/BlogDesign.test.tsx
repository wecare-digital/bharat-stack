import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import BlogIndex from '../pages/blog/index';
import BlogIndexPage from '../pages/blog/page/[page]';
import BlogPostPage from '../pages/post/[slug]';
import { toBlogCard, blogPageCount, POSTS_PER_PAGE, type BlogCard, type PublicBlogPost } from '../lib/public-blog';
import type { BlogIndexPageProps } from '../lib/blog-index-props';

vi.mock( 'next/head', () => ( { default: ( { children }: { children: React.ReactNode } ) => <>{ children }</> } ) );

const cssOf = ( container: HTMLElement ) =>
  Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

const samplePost: PublicBlogPost = {
  id: 'post-1',
  title: 'A Clear Question Can Change the Work',
  slug: 'a-clear-question-can-change-the-work',
  excerpt: 'A short excerpt that makes the listing readable without turning the card into UI chrome.',
  url: '/post/a-clear-question-can-change-the-work',
  category: 'Conversations',
  tags: [ 'Practice', 'Inquiry' ],
  authorName: 'Anew by WECARE.DIGITAL',
  publishedDate: '2026-09-27T00:00:00Z',
  seoTitle: 'A Clear Question Can Change the Work | WECARE.DIGITAL',
  metaDescription: 'A meta description that belongs to the post page head, not to a listing card.',
  robots: 'index, follow',
  modifiedDate: '2026-09-28T00:00:00Z',
  richContent: {
    nodes: [
      {
        type: 'PARAGRAPH',
        nodes: [ { type: 'TEXT', textData: { text: 'First paragraph.', decorations: [] } } ],
      },
      {
        type: 'PARAGRAPH',
        nodes: [ { type: 'TEXT', textData: { text: 'Second paragraph.', decorations: [] } } ],
      },
      {
        type: 'HEADING',
        headingData: { level: 2 },
        nodes: [ { type: 'TEXT', textData: { text: 'A section', decorations: [] } } ],
      },
    ],
  },
};

const secondPost: PublicBlogPost = {
  ...samplePost,
  id: 'post-2',
  title: 'A Guide to Better Decisions',
  slug: 'a-guide-to-better-decisions',
  category: 'Guides',
};

const firstCard = toBlogCard( samplePost );
const secondCard = toBlogCard( secondPost );

/**
 * Props for one index page, the way lib/blog-index-props.ts builds them: categories come from
 * the whole corpus and totalPosts is the corpus count, NOT this page's length. Tests that pass
 * a page's own cards as the corpus would never catch the bug those two fields exist to prevent.
 */
const propsFor = ( overrides: Partial<BlogIndexPageProps> = {} ): BlogIndexPageProps => ( {
  posts: [ firstCard, secondCard ],
  page: 1,
  totalPages: 1,
  totalPosts: 2,
  // Sorted; categories[0] is the default, served at /blog/. The rest are their own streams.
  categories: [ 'Conversations', 'Guides' ],
  categoryCounts: { Conversations: 1, Guides: 1 },
  // Server-decided, never client state - see the note in BlogIndexView.
  activeCategory: 'Conversations',
  defaultCategory: 'Conversations',
  ...overrides,
} );

/** Stand in for the lazily-fetched /blog/search-index.json. */
function mockSearchIndex ( posts: BlogCard[] ) {
  const fetchMock = vi.fn().mockResolvedValue( {
    ok: true,
    json: async () => ( { ok: true, count: posts.length, posts } ),
  } );
  vi.stubGlobal( 'fetch', fetchMock );
  return fetchMock;
}

afterEach( () => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
} );

describe( 'Blog design alignment', () => {
  /**
   * REWRITTEN WITH THE PAGE, AND THE INTENT IS UNCHANGED.
   *
   * This asserted that /blog/ matched the home page's hero typography by pinning blog-LOCAL
   * copies of those rungs: .blog-hero h1 reading "Blog", .blog-shell{max-width:1300px, a
   * clamp(36px,4.3vw,60px) h1 rule and a .blog-hero>p body rule. That was the right intent
   * pursued by duplication - the numbers were re-typed into this page, so they could drift
   * from the home page they were copied from and this test would have kept passing.
   *
   * The page now renders the actual RotatingHero the home page uses, so the typography cannot
   * drift: there is one declaration, in one component. The assertions therefore move from
   * "these numbers appear in this page's CSS" to "this page renders that component".
   *
   * THE ONE THING KEPT VERBATIM is the no-repeated-brand-eyebrow rule, because that is a
   * design decision rather than an implementation detail. The home page removed its own copy
   * of the lime badge for exactly this reason - it restated the header's lockup 109px below
   * it - so badgeLabel is deliberately not passed here, and RotatingHero renders no
   * .brand-badge without it.
   */
  it( 'renders the homepage rotating hero on /blog/, and still does not repeat the brand eyebrow', () => {
    const { container } = render( <BlogIndex { ...propsFor() } /> );

    // The shared hero, not a local copy of its numbers.
    expect( container.querySelector( '.rh-hero' ) ).not.toBeNull();
    expect( container.querySelector( '.rh-head' ) ).not.toBeNull();

    // The old markup is gone, along with the line that restated the heading.
    expect( container.querySelector( '.blog-hero' ) ).toBeNull();
    expect( container.textContent ).not.toContain( 'Ideas, guides and updates published' );

    // The brand lockup must not appear twice on the page: header owns it.
    expect( container.querySelector( '.brand-badge' ) ).toBeNull();
    expect( container.querySelector( '.eyebrow' ) ).toBeNull();

    // Exactly one h1, and it is the hero's - the page has no competing headline.
    expect( container.querySelectorAll( 'h1' ) ).toHaveLength( 1 );

    // The breadcrumb and the blog-scoped search box are both present.
    expect( container.querySelector( 'nav[aria-label="Breadcrumb"]' ) ).not.toBeNull();
    expect( container.querySelector( 'form[role="search"]' ) ).not.toBeNull();
  } );

  /**
   * NO "ALL" PILL, AND THE FIRST CATEGORY IS THE DEFAULT. Owner instruction, and the corpus
   * supports it: measured live, 834 posts carry two categories - Conversations 824 (98.8%) and
   * Gastronomy 10 (1.2%). "All" selected 834 where the next pill selected 824, so the control
   * offered a choice between two lists that are the same list.
   */
  it( 'has no All pill, and the categories are links rather than buttons', () => {
    /*
     * "All" selected 864 posts where the next pill selected 824 - two options, one list - so it
     * went on owner instruction.
     *
     * LINKS, NOT BUTTONS, and that is the load-bearing part. Filtering the full-corpus pages
     * client-side to honour the instruction left 40 posts on no index page and rendered /blog/
     * with ZERO cards, because the 40 Gastronomy posts are the newest and filled page 1. Each
     * category is now its own prerendered stream, so the switch is navigation.
     */
    render( <BlogIndex { ...propsFor() } /> );

    expect( screen.queryByRole( 'button', { name: 'All' } ) ).toBeNull();
    // No buttons at all in the switch - if these are buttons again, the streams are gone.
    expect( screen.queryByRole( 'button', { name: 'Conversations' } ) ).toBeNull();

    // The active one is not a link, and says so to a screen reader.
    const here = document.querySelector( '.category-switch .cat-here' );
    expect( here?.textContent ).toContain( 'Conversations' );
    expect( here ).toHaveAttribute( 'aria-current', 'page' );

    // The other is a real href to its own stream.
    const other = screen.getByRole( 'link', { name: /Guides/ } );
    expect( String( other.getAttribute( 'href' ) ).replace( /\/$/, '' ) ).toBe( '/blog/topic/guides' );
  } );

  it( 'keeps the post count OFF the category pills, and on the line that reports it', () => {
    /*
     * REVERSED ON OWNER INSTRUCTION. This test used to assert the opposite - that each pill
     * showed its own size, "Conversations 824" - so it is inverted rather than deleted: the
     * count must now be absent from the pills, and the assertion is what stops it drifting back.
     *
     * It is asserted as "no digits in the nav" rather than "no <i> element", because the element
     * is an implementation detail and a future pill could reintroduce the number some other way.
     *
     * The second half matters as much as the first: `categoryCounts` is still a live prop, feeding
     * the search box's "N of M posts" denominator, so the count was moved off the pills rather
     * than deleted from the page. Without that assertion this test would pass just as well if the
     * counts had been ripped out altogether, which is not what was asked for. That line only
     * renders while a query is active - BlogSearch omits it when there is nothing to count - so
     * the search has to be driven to see it.
     */
    render( <BlogIndex { ...propsFor( { categoryCounts: { Conversations: 824, Guides: 40 } } ) } /> );

    const nav = document.querySelector( '.category-switch' );
    expect( nav?.textContent ).toContain( 'Conversations' );
    expect( nav?.textContent ).toContain( 'Guides' );
    expect( nav?.textContent ).not.toMatch( /\d/ );
    expect( nav?.querySelector( 'i' ) ).toBeNull();

    // The denominator still comes from categoryCounts, on the line that is meant to report it.
    fireEvent.change( screen.getByLabelText( 'Search the blog' ), { target: { value: 'a' } } );
    expect( document.querySelector( '.bs-count' )?.textContent ).toContain( 'of 824 posts' );
  } );

  it( 'needs no fetch to render a category stream, because the page IS the category', () => {
    /*
     * The payload win survives the change: a plain page view fetches nothing, because the
     * server already sliced this page to one category.
     */
    const fetchMock = mockSearchIndex( [ firstCard, secondCard ] );
    render( <BlogIndex { ...propsFor() } /> );
    expect( fetchMock ).not.toHaveBeenCalled();
    expect( screen.getByRole( 'heading', { name: samplePost.title } ) ).toBeInTheDocument();
  } );

  it( 'scopes a search to the category the reader is in', async () => {
    /*
     * The index covers all 864 posts, so it has to be narrowed: someone reading Conversations
     * who searches "paneer" should get nothing, not a Gastronomy post from a stream they are
     * not in.
     */
    mockSearchIndex( [ firstCard, secondCard ] );
    render( <BlogIndex { ...propsFor() } /> );
    const box = screen.getByLabelText( 'Search the blog' );

    fireEvent.change( box, { target: { value: 'Better Decisions' } } );
    await waitFor( () => {
      expect( screen.queryByRole( 'heading', { name: samplePost.title } ) ).toBeNull();
    } );
    // The Guides post matches the text but is in another stream, so it stays out.
    expect( screen.queryByRole( 'heading', { name: secondPost.title } ) ).toBeNull();

    fireEvent.change( box, { target: { value: 'Clear Question' } } );
    await waitFor( () => {
      expect( screen.getByRole( 'heading', { name: samplePost.title } ) ).toBeInTheDocument();
    } );

    fireEvent.change( box, { target: { value: '   ' } } );
    await waitFor( () => {
      expect( screen.getByRole( 'heading', { name: samplePost.title } ) ).toBeInTheDocument();
    } );
  } );

  it( 'keeps listing cards typographic, readable and responsive rather than dashboard-like', () => {
    const { container } = render( <BlogIndex { ...propsFor() } /> );
    const css = cssOf( container );

    expect( css ).toContain( '.post-card{border:1px solid #e5e7eb;border-radius:14px' );
    expect( css ).toContain( 'h2{font-size:23px;line-height:1.22' );
    expect( css ).toContain( '.post-copy p{font-size:16px;line-height:1.5' );
    expect( css ).toContain( '@media(max-width:1050px)' );
    expect( css ).toContain( '@media(max-width:680px)' );
    expect( css ).toContain( ':global(a:focus-visible)' );
  } );
} );

/**
 * PAGINATION.
 *
 * /blog/ rendered all 834 posts in one document - 103,908px at 1280x900, and a build warning
 * on every run that its 842 kB of props exceeded the 128 kB threshold. These assertions pin
 * the three things that were easy to get wrong while splitting it, all of which would have
 * been invisible on a page that merely looked right:
 *
 *   1. Page 1 links to /blog/, never /blog/page/1/. A second URL for the same 24 cards is
 *      duplicate content, and every page is self-canonical, so both would be indexed.
 *   2. The paginator disappears while a search or category is active. Filtered results are
 *      already a narrowing and all matches are shown; paging them too would put two
 *      independent narrowings between a reader and one post.
 *   3. Search counts and searches the WHOLE corpus, not the page. "3 of 24" would be a lie
 *      about what was searched.
 */
describe( 'Blog pagination', () => {
  /*
   * All one category, and deliberately so: these cases are about paging, and mixing categories
   * in here would mean the default-category filter silently removed cards from every count. The
   * category behaviour has its own cases above.
   */
  const manyCards: BlogCard[] = Array.from( { length: 5 }, ( _, i ) => ( {
    slug: `post-${i + 1}`,
    title: `Post number ${i + 1}`,
    excerpt: `Excerpt for post ${i + 1}.`,
    category: 'Conversations',
  } ) );

  /**
   * TRAILING SLASHES ARE COMPARED LOOSELY HERE, ON PURPOSE.
   *
   * next.config.js sets trailingSlash:true, and next/link normalises against that config at
   * runtime - which jsdom does not load, so a Link given '/blog/' renders href="/blog" in
   * this environment and href="/blog/" in the export. Pinning the slash here would assert a
   * property of the test environment rather than of the site.
   *
   * The slash IS asserted, by routegraph.js, against the built HTML: its "MIXED TRAILING
   * SLASH - href without the slash trailingSlash:true emits" check reads the real hrefs out
   * of out/ and is currently 0. That is the right place for it - this test owns which page a
   * link points at, and routegraph owns how the URL is spelled.
   */
  const samePath = ( href: string | null ) => String( href ).replace( /\/$/, '' ) || '/';

  it( 'sends page 1 to /blog/ rather than to /blog/page/1/', () => {
    const { container } = render( <BlogIndexPage { ...propsFor( { posts: manyCards, page: 2, totalPages: 3, totalPosts: 60 } ) } /> );

    const newer = container.querySelector( 'a[rel="prev"]' );
    expect( newer ).not.toBeNull();
    expect( samePath( newer!.getAttribute( 'href' ) ) ).toBe( '/blog' );

    // And the numbered link for page 1 agrees with it - not /blog/page/1/.
    const one = Array.from( container.querySelectorAll( 'a.pager-num' ) )
      .find( node => node.textContent?.trim().endsWith( '1' ) );
    expect( samePath( one!.getAttribute( 'href' ) ) ).toBe( '/blog' );
  } );

  it( 'marks the current page and offers only the directions that exist', () => {
    const { container: first } = render( <BlogIndex { ...propsFor( { posts: manyCards, page: 1, totalPages: 3, totalPosts: 60 } ) } /> );
    // Page 1 has no previous page: the control is rendered so the row does not reflow, but it
    // is not a link and is hidden from the accessibility tree.
    expect( first.querySelector( 'a[rel="prev"]' ) ).toBeNull();
    expect( first.querySelector( '.pager-step.is-off[aria-hidden="true"]' ) ).not.toBeNull();
    expect( samePath( first.querySelector( 'a[rel="next"]' )!.getAttribute( 'href' ) ) ).toBe( '/blog/page/2' );
    // Scoped to the pager: Breadcrumbs marks its own last crumb aria-current="page", so an
    // unscoped query finds "Blog" first and would pass on page 1 for the wrong reason.
    expect( first.querySelector( '.pager [aria-current="page"]' )!.textContent ).toBe( '1' );

    const { container: last } = render( <BlogIndexPage { ...propsFor( { posts: manyCards, page: 3, totalPages: 3, totalPosts: 60 } ) } /> );
    expect( last.querySelector( 'a[rel="next"]' ) ).toBeNull();
    expect( samePath( last.querySelector( 'a[rel="prev"]' )!.getAttribute( 'href' ) ) ).toBe( '/blog/page/2' );
    expect( last.querySelector( '.pager [aria-current="page"]' )!.textContent ).toBe( '3' );
  } );

  it( 'hides the paginator while a search or a category is narrowing the list', async () => {
    mockSearchIndex( manyCards );
    const { container } = render( <BlogIndex { ...propsFor( { posts: manyCards, page: 1, totalPages: 3, totalPosts: 60 } ) } /> );

    expect( container.querySelector( 'nav[aria-label="Blog pages"]' ) ).not.toBeNull();

    fireEvent.change( screen.getByLabelText( 'Search the blog' ), { target: { value: 'number 3' } } );
    await waitFor( () => {
      expect( container.querySelector( 'nav[aria-label="Blog pages"]' ) ).toBeNull();
    } );
    // The grid relabels itself, so a screen reader is told these are matches and not the page.
    expect( container.querySelector( 'section[aria-label="Matching posts"]' ) ).not.toBeNull();

    // Clearing the query brings the paginator back.
    fireEvent.change( screen.getByLabelText( 'Search the blog' ), { target: { value: '' } } );
    await waitFor( () => {
      expect( container.querySelector( 'nav[aria-label="Blog pages"]' ) ).not.toBeNull();
    } );
  } );

  it( 'searches every published post, not just the page in front of the reader', async () => {
    /**
     * THE CASE THIS EXISTS FOR. The page carries 2 cards; the corpus has 5. A search for a
     * post that is NOT on this page must find it, which is only possible via the lazily
     * fetched index - and the announced count must be against the corpus. Before pagination
     * this was free because every post was in the page; it is now the thing most likely to
     * regress, and it would regress silently.
     */
    const fetchMock = mockSearchIndex( manyCards );
    render( <BlogIndex { ...propsFor( {
      posts: manyCards.slice( 0, 2 ), page: 1, totalPages: 3, totalPosts: 5,
      // The announced denominator is the ACTIVE CATEGORY's corpus count, not the whole corpus:
      // with "All" gone, "3 of 834" would be counting a list the reader is not looking at.
      categories: [ 'Conversations' ], categoryCounts: { Conversations: 5 },
    } ) } /> );

    // Nothing is fetched for a plain page view.
    expect( fetchMock ).not.toHaveBeenCalled();

    fireEvent.change( screen.getByLabelText( 'Search the blog' ), { target: { value: 'number 5' } } );

    await waitFor( () => {
      expect( screen.getByRole( 'heading', { name: 'Post number 5' } ) ).toBeInTheDocument();
    } );
    expect( fetchMock ).toHaveBeenCalledWith( '/blog/search-index.json', expect.anything() );
    // Counted against all 5, not against the 2 on this page.
    expect( screen.getByText( '1 of 5 posts' ) ).toBeInTheDocument();

    // And it is fetched ONCE however much more is typed.
    fireEvent.change( screen.getByLabelText( 'Search the blog' ), { target: { value: 'number' } } );
    await waitFor( () => {
      expect( screen.getByRole( 'heading', { name: 'Post number 4' } ) ).toBeInTheDocument();
    } );
    expect( fetchMock ).toHaveBeenCalledTimes( 1 );
  } );

  it( 'says so when the search index cannot be loaded instead of silently searching one page', async () => {
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( { ok: false, status: 502, json: async () => ( {} ) } ) );
    render( <BlogIndex { ...propsFor( { posts: manyCards.slice( 0, 2 ), page: 1, totalPages: 3, totalPosts: 5 } ) } /> );

    fireEvent.change( screen.getByLabelText( 'Search the blog' ), { target: { value: 'number' } } );

    await waitFor( () => {
      expect( screen.getByRole( 'status' ).textContent ).toContain( 'could not be loaded' );
    } );
    // It still filters what it has rather than showing nothing.
    expect( screen.getByRole( 'heading', { name: 'Post number 1' } ) ).toBeInTheDocument();
  } );

  it( 'projects a post down to the fields a card renders, and drops the 357 kB it does not', () => {
    const card = toBlogCard( samplePost ) as unknown as Record<string, unknown>;

    // Kept: everything the card prints, plus coverImage when present.
    expect( Object.keys( card ).sort() ).toEqual(
      [ 'authorName', 'category', 'excerpt', 'publishedDate', 'slug', 'title' ]
    );

    // Dropped: the post page's head fields and the crawler hints. These were 357 kB of the
    // 842 kB payload across 834 posts, and no listing card ever rendered one of them.
    for ( const field of [ 'metaDescription', 'seoTitle', 'robots', 'tags', 'modifiedDate', 'url', 'id', 'richContent' ] ) {
      expect( card ).not.toHaveProperty( field );
    }
  } );

  it( 'never reports zero pages, so an empty blog still has a /blog/', () => {
    expect( blogPageCount( 0 ) ).toBe( 1 );
    expect( blogPageCount( 1 ) ).toBe( 1 );
    expect( blogPageCount( POSTS_PER_PAGE ) ).toBe( 1 );
    expect( blogPageCount( POSTS_PER_PAGE + 1 ) ).toBe( 2 );
    // The live corpus at the time of the split.
    expect( blogPageCount( 834 ) ).toBe( 35 );
  } );
} );

describe( 'Blog post page', () => {
  it( 'uses a reading measure and paragraph rhythm appropriate for long-form posts', () => {
    const { container } = render( <BlogPostPage post={ samplePost } /> );
    const css = cssOf( container );

    expect( css ).toContain( '.article-shell{max-width:1300px' );
    expect( css ).toContain( 'article{max-width:700px' );
    expect( css ).toContain( 'h1{font-size:clamp(36px,4.3vw,60px);line-height:1.04;letter-spacing:-0.04em;color:rgba(0,0,0,.95)' );
    expect( css ).toContain( 'text-wrap:balance;max-width:20ch' );
    expect( css ).toContain( 'font-size:20px;line-height:1.55;letter-spacing:-.125px' );
    expect( css ).toContain( '.content :global(p + p){margin-top:28px}' );
  } );

  it( 'finishes the rich-content styles for headings, lists, quotes and accessible links', () => {
    const { container } = render( <BlogPostPage post={ samplePost } /> );
    const css = cssOf( container );

    expect( css ).toContain( '.content :global(h2){font-size:30px;line-height:1.15' );
    expect( css ).toContain( '.content :global(ul),.content :global(ol){margin:28px 0;padding-inline-start:1.4em}' );
    expect( css ).toContain( '.content :global(li + li){margin-top:10px}' );
    expect( css ).toContain( '.content :global(blockquote){margin:36px 0;padding:2px 0 2px 22px;border-inline-start:3px solid #d1f470;font-size:21px;line-height:1.5;' );
    expect( css ).toContain( '.content :global(a:focus-visible){outline:3px solid rgba(26,58,42,.25);outline-offset:3px;border-radius:2px}' );
  } );
} );
