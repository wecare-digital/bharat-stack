export interface PublicBlogPost {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  url: string;
  content?: string;
  richContent?: { nodes?: any[] };
  seoTitle?: string;
  metaDescription?: string;
  focusKeyword?: string;
  keywords?: string[];
  jsonLd?: Record<string, any>;
  publishedDate?: string;
  modifiedDate?: string;
  coverImage?: string;
  category?: string;
  tags?: string[];
  hashtags?: string[];
  authorName?: string;
  robots?: string;
}

/**
 * WHAT A BLOG CARD ACTUALLY NEEDS - seven fields of the eighteen the API returns.
 *
 * THIS TYPE IS THE FIX FOR AN 842 kB PAGE. /blog/ shipped every field of all 834 posts
 * into __NEXT_DATA__ and rendered seven of them. Measured against the live endpoint,
 * the response is 874 kB and breaks down like this:
 *
 *   excerpt 180k  metaDescription 122k  url 61k  seoTitle 52k  slug 37k  title 35k
 *   robots 33k  id 32k  tags 25k  modifiedDate 22k  publishedDate 21k  authorName 20k
 *   category 12k  + focusKeyword/keywords/jsonLd/coverImage/hashtags ~7k
 *
 * metaDescription, seoTitle, robots, tags, modifiedDate, url and id are 357 kB that no
 * card renders - metaDescription and seoTitle exist for the POST page's <head>, and it
 * fetches its own post. `id` goes too: it was only ever the React key, and slug is
 * unique and already present.
 *
 * Kept deliberately: excerpt is the single largest field and it stays, because the card
 * prints it and search matches on it. coverImage is kept although the card does not use
 * it today - it is 1.7 kB across all 834 posts, which is the cost of one small image, and
 * leaving it out would make adding card art a data change rather than a markup one.
 */
export interface BlogCard {
  slug: string;
  title: string;
  excerpt?: string;
  category?: string;
  publishedDate?: string;
  authorName?: string;
  coverImage?: string;
}

/** Narrow a full post to the card fields. One place, so a page cannot widen it by accident. */
export function toBlogCard ( post: PublicBlogPost ): BlogCard {
  return {
    slug: post.slug,
    title: post.title,
    // `|| undefined` rather than passing '' through: Next refuses to serialise undefined
    // in props, and an empty string would render an empty <p>. Normalised here so every
    // consumer gets the same shape.
    ...( post.excerpt ? { excerpt: post.excerpt } : {} ),
    ...( post.category ? { category: post.category } : {} ),
    ...( post.publishedDate ? { publishedDate: post.publishedDate } : {} ),
    ...( post.authorName ? { authorName: post.authorName } : {} ),
    ...( post.coverImage ? { coverImage: post.coverImage } : {} ),
  };
}

/**
 * HOW MANY CARDS ON A PAGE. 24 divides cleanly by the grid's 3 and 2 column counts, so no
 * page ends on a ragged row at any width, and it puts /blog/ at roughly 3.3 screens instead
 * of the 115.5 screens 834 cards measured.
 */
export const POSTS_PER_PAGE = 24;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
const PUBLIC_BLOG_API = `${API_BASE}/seo-tools/blog-public`;

/**
 * BUILD-TIME MEMO, and it is not premature.
 *
 * getStaticPaths for /post/[slug] calls this once, and now getStaticProps for /blog/ and
 * each of the 35 /blog/page/N pages does too. Without a memo that is 36 requests for the
 * same 874 kB during one build - 31 MB over the wire to render data that cannot change
 * mid-build. The module is evaluated once per build process, so a module-level promise is
 * the whole mechanism needed.
 *
 * THE PROMISE IS CACHED, NOT THE RESULT, so concurrent callers share one in-flight request
 * instead of each starting their own before the first resolves. Next renders pages in
 * parallel, so that case is the normal one rather than the edge.
 *
 * A FAILED FETCH IS NOT CACHED. listPublicBlogPosts swallows errors and returns [], so a
 * cached rejection is impossible - but a cached EMPTY ARRAY from one bad request would
 * poison every later page in the build, turning a two-second network blip into a site with
 * no blog. generate-sitemap.js already refuses to write a sitemap with zero post pages for
 * exactly that reason; this clears the memo instead, so the next caller retries.
 */
let postsPromise: Promise<PublicBlogPost[]> | null = null;

export async function listPublicBlogPosts (): Promise<PublicBlogPost[]> {
  if ( postsPromise ) return postsPromise;
  postsPromise = fetchAllPosts();
  const posts = await postsPromise;
  if ( posts.length === 0 ) postsPromise = null;
  return posts;
}

async function fetchAllPosts (): Promise<PublicBlogPost[]> {
  try {
    const response = await fetch( PUBLIC_BLOG_API, {
      headers: { Accept: 'application/json' },
    } );
    if ( !response.ok ) return [];
    const body = await response.json();
    return body?.ok && Array.isArray( body.posts ) ? body.posts : [];
  } catch
  {
    return [];
  }
}

/**
 * The card list in the order the index shows it: newest first.
 *
 * SORTED HERE RATHER THAN TRUSTED FROM THE API, because pagination makes order load-bearing
 * in a way a single page did not. With one page, an inconsistent order shuffled cards; with
 * 35 pages, it can move a post between pages between builds, so a link to /blog/page/7/
 * silently comes to mean something else. Posts with no publishedDate sort last rather than
 * being dropped - a post with a missing date is a data problem, not a reason to hide it.
 */
export function listBlogCards ( posts: PublicBlogPost[] ): BlogCard[] {
  return posts
    .slice()
    .sort( ( a, b ) => {
      const at = a.publishedDate ? Date.parse( a.publishedDate ) : NaN;
      const bt = b.publishedDate ? Date.parse( b.publishedDate ) : NaN;
      if ( Number.isNaN( at ) && Number.isNaN( bt ) ) return a.slug.localeCompare( b.slug );
      if ( Number.isNaN( at ) ) return 1;
      if ( Number.isNaN( bt ) ) return -1;
      return bt - at;
    } )
    .map( toBlogCard );
}

/** Total index pages for a post count. Always at least 1, so an empty blog still has /blog/. */
export function blogPageCount ( total: number ): number {
  return Math.max( 1, Math.ceil( total / POSTS_PER_PAGE ) );
}

export async function getPublicBlogPost ( slug: string ): Promise<PublicBlogPost | null> {
  try {
    const response = await fetch( `${PUBLIC_BLOG_API}/${encodeURIComponent( slug )}`, {
      headers: { Accept: 'application/json' },
    } );
    if ( !response.ok ) return null;
    const body = await response.json();
    return body?.ok && body.post ? body.post : null;
  } catch
  {
    return null;
  }
}
