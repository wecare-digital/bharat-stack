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
  return orderPostsNewestFirst( posts ).map( toBlogCard );
}

/**
 * The corpus in index order, still as FULL posts.
 *
 * Extracted from listBlogCards so there is exactly one definition of "newest first" on the site.
 * The post page's newer/older pager walks the same sequence the index paginates, and it needs
 * fields the card projection drops - `tags`, for related posts - so it cannot go through
 * listBlogCards. Two comparators would be two orders, and the note above is explicit that order
 * is load-bearing here: a pager that disagreed with the index by one would offer a reader a
 * "newer" post that the listing shows as older.
 */
export function orderPostsNewestFirst ( posts: PublicBlogPost[] ): PublicBlogPost[] {
  return posts
    .slice()
    .sort( ( a, b ) => {
      const at = a.publishedDate ? Date.parse( a.publishedDate ) : NaN;
      const bt = b.publishedDate ? Date.parse( b.publishedDate ) : NaN;
      if ( Number.isNaN( at ) && Number.isNaN( bt ) ) return a.slug.localeCompare( b.slug );
      if ( Number.isNaN( at ) ) return 1;
      if ( Number.isNaN( bt ) ) return -1;
      return bt - at;
    } );
}

/** Total index pages for a post count. Always at least 1, so an empty blog still has /blog/. */
export function blogPageCount ( total: number ): number {
  return Math.max( 1, Math.ceil( total / POSTS_PER_PAGE ) );
}

/**
 * PER-SLUG BUILD-TIME MEMO. The same mechanism as postsPromise above, and it was missing
 * here, which cost roughly four times more upstream requests than the build needs.
 *
 * MEASURED, not guessed. API Gateway access logs for 24h on 2026-09-28:
 *
 *     185,576 requests to /seo-tools/blog-public*, all userAgent "node"
 *     890 distinct paths - exactly the 889 slugs plus the list endpoint
 *     each slug hit ~219 times, against 54 Amplify builds in the same window
 *
 * 219 / 54 is about 4 fetches of every slug per build. 117 of those requests came back
 * 429, so it was consuming API Gateway stage capacity from every other route on the API.
 *
 * WHY FOUR AND NOT ONE. Next renders with 9 workers and more than one page type resolves a
 * post: /post/[slug] via getStaticProps, and the blog index, its 35 paginated pages and the
 * per-category streams all sit on the same corpus. Without a memo each of those paths is an
 * independent fetch of the same document, and the module-level memo on the LIST call is
 * exactly why the list was not also multiplied.
 *
 * THE PER-SLUG FETCH ITSELF IS NECESSARY and must not be replaced by a filter over
 * listPublicBlogPosts(): the single-post response carries `content` and `richContent`, which
 * the list response omits. Checked against the live API rather than assumed. So the fix is
 * to fetch each slug once, not to stop fetching.
 *
 * A NULL IS NOT CACHED, matching listPublicBlogPosts. getPublicBlogPost returns null both
 * for "no such post" and for "the request failed", and those must not be treated alike: a
 * cached failure would turn one network blip into a permanently missing page for the rest of
 * the build. Caching the promise rather than the value also means concurrent callers share
 * one in-flight request instead of each starting their own, which is the normal case here
 * because Next renders pages in parallel.
 */
const postPromises = new Map<string, Promise<PublicBlogPost | null>>();

export async function getPublicBlogPost ( slug: string ): Promise<PublicBlogPost | null> {
  const cached = postPromises.get( slug );
  if ( cached ) return cached;
  const pending = fetchPost( slug );
  postPromises.set( slug, pending );
  const post = await pending;
  if ( post === null ) postPromises.delete( slug );
  return post;
}

async function fetchPost ( slug: string ): Promise<PublicBlogPost | null> {
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
